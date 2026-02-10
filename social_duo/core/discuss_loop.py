from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from social_duo.agents.prompts_discuss import AGENT_DISCUSS_SYSTEM
from social_duo.core.constraints import list_platforms, platform_constraint, validate_text
from social_duo.providers.llm import LLMClient
from social_duo.types.discuss_schemas import DiscussArtifact, DiscussTurn
from social_duo.types.schemas import AppConfig


@dataclass
class DiscussLoopResult:
    transcript: list[dict[str, Any]]
    artifacts: list[DiscussArtifact]
    stop_reason: str


class DiscussLoopError(RuntimeError):
    def __init__(self, message: str, transcript: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.transcript = transcript


class DiscussParseError(RuntimeError):
    def __init__(self, message: str, raw: str) -> None:
        super().__init__(message)
        self.raw = raw


def _build_context(
    *,
    config: AppConfig,
    platform: str,
    mode: str,
    risk: str,
    turn_index: int,
    chosen: dict | None,
    artifacts: list[dict[str, Any]],
    must_converge: bool,
    constraint_issues: list[str],
    expected_intent: str,
    agent_name: str,
) -> str:
    constraints = {p: platform_constraint(config, p).model_dump() for p in list_platforms(platform)}
    platform_rule = (
        "If platform=all, produce one artifact per platform. "
        "If platform is a single target, produce 3 variants for that platform."
    )
    schema = (
        '{"type":"DISCUSS","intent":"PROPOSE_TOPIC|CRITIQUE|SHORTLIST|DECIDE|DRAFT|REVISE|SIMULATE_COMMENT|REPLY|WRAPUP",'
        '"message":"short message","candidates":[{"topic":"...","angle":"...","platform":"x|linkedin|instagram|threads"}],'
        '"chosen":{"topic":"...","angle":"...","platform":"x|linkedin|instagram|threads"},'
        '"artifacts":[{"kind":"post|thread|reply","platform":"x|linkedin|instagram|threads","content":"..."}],"stop":false}'
    )
    return "\n".join(
        [
            f"Turn: {turn_index}",
            f"Mode: {mode}",
            f"Risk level: {risk}",
            f"Platform target: {platform}",
            f"Constraints: {json.dumps(constraints)}",
            platform_rule,
            f"Chosen: {json.dumps(chosen) if chosen else None}",
            f"Artifacts so far: {json.dumps(artifacts)}",
            f"Must converge now: {must_converge}",
            f"Constraint issues: {constraint_issues}",
            f"Agent: {agent_name}",
            f"Expected intent: {expected_intent}",
            f"Schema: {schema}",
            "Reminder: Output ONLY valid JSON per schema with all keys present. Each artifact MUST include platform. Do NOT echo this context.",
        ]
    )


def _call_agent(
    llm: LLMClient,
    *,
    system: str,
    context: str,
    history: list[dict[str, Any]],
    temperature: float,
) -> tuple[DiscussTurn, str]:
    messages = [{"role": "system", "content": system}]
    for item in history[-8:]:
        messages.append({"role": "assistant", "content": json.dumps(item["turn"])})
    messages.append({"role": "user", "content": context})

    resp = llm.chat(messages, temperature=temperature, max_tokens=900, response_format={"type": "json_object"})
    content = resp["choices"][0]["message"]["content"]

    try:
        data = json.loads(content)
        turn = DiscussTurn.model_validate(data)
        return turn, content
    except (json.JSONDecodeError, ValidationError) as exc:
        correction = messages + [
            {
                "role": "user",
                "content": "Return ONLY valid JSON that matches the schema. Include platform on every artifact item. No extra text.",
            }
        ]
        resp = llm.chat(correction, temperature=temperature, max_tokens=900, response_format={"type": "json_object"})
        content = resp["choices"][0]["message"]["content"]
        try:
            data = json.loads(content)
            turn = DiscussTurn.model_validate(data)
            return turn, content
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise DiscussParseError(f"Invalid JSON after retry: {exc2}", content) from exc


def _collect_artifacts(turn: DiscussTurn, artifacts: list[DiscussArtifact]) -> None:
    for artifact in turn.artifacts:
        artifacts.append(artifact)


def _validate_artifacts(
    *,
    config: AppConfig,
    platform: str,
    artifacts: list[DiscussArtifact],
) -> list[str]:
    issues: list[str] = []
    for artifact in artifacts:
        if artifact.platform not in list_platforms(platform):
            continue
        if artifact.kind in {"post", "thread"}:
            problems, _ = validate_text(
                artifact.content,
                config=config,
                platform=artifact.platform,
                cta_required=False,
                cta_text=None,
            )
            issues.extend(problems)
    return issues


def run_discuss_loop(
    *,
    llm: LLMClient,
    config: AppConfig,
    platform: str,
    turns: int,
    mode: str,
    risk: str,
    stop_on: str,
) -> DiscussLoopResult:
    transcript: list[dict[str, Any]] = []
    artifacts: list[DiscussArtifact] = []
    chosen: dict | None = None
    has_decided = False
    has_draft = False
    has_comments = False
    has_replies = False
    wrapup_required = False

    for idx in range(turns):
        agent_name = "AgentA" if idx % 2 == 0 else "AgentB"
        system = AGENT_DISCUSS_SYSTEM
        temperature = 0.6

        must_converge = idx >= 5 and (not chosen or not artifacts)
        if idx >= turns - 2 and has_draft and has_comments and has_replies:
            wrapup_required = True

        if not chosen:
            expected_intent = "PROPOSE_TOPIC or SHORTLIST"
        elif not has_decided:
            expected_intent = "DECIDE"
        elif not has_draft:
            expected_intent = "DRAFT"
        elif mode == "posts":
            expected_intent = "WRAPUP"
        elif not has_comments:
            expected_intent = "SIMULATE_COMMENT"
        elif not has_replies:
            expected_intent = "REPLY"
        elif wrapup_required:
            expected_intent = "WRAPUP"
        else:
            expected_intent = "REVISE or WRAPUP"

        constraint_issues = _validate_artifacts(config=config, platform=platform, artifacts=artifacts)
        context = _build_context(
            config=config,
            platform=platform,
            mode=mode,
            risk=risk,
            turn_index=idx + 1,
            chosen=chosen,
            artifacts=[a.model_dump() for a in artifacts],
            must_converge=must_converge,
            constraint_issues=constraint_issues,
            expected_intent=expected_intent,
            agent_name=agent_name,
        )

        try:
            turn, raw = _call_agent(
                llm,
                system=system,
                context=context,
                history=transcript,
                temperature=temperature,
            )
        except DiscussParseError as exc:
            transcript.append(
                {
                    "agent": agent_name,
                    "turn": {"parse_error": str(exc)},
                    "raw": exc.raw,
                }
            )
            raise DiscussLoopError(f"{agent_name} failed to return valid JSON: {exc}", transcript) from exc
        except Exception as exc:  # noqa: BLE001
            raise DiscussLoopError(f"{agent_name} failed to return valid JSON: {exc}", transcript) from exc

        if turn.type != "DISCUSS":
            raise DiscussLoopError("Invalid discuss turn type", transcript)

        if turn.chosen:
            chosen = turn.chosen.model_dump()
            has_decided = True

        _collect_artifacts(turn, artifacts)
        for artifact in turn.artifacts:
            if artifact.kind in {"post", "thread"}:
                has_draft = True
            if artifact.kind == "reply" and artifact.content.strip().lower().startswith("comment:"):
                has_comments = True
            if artifact.kind == "reply" and artifact.content.strip().lower().startswith("reply:"):
                has_replies = True
        if mode == "posts" and has_draft:
            has_comments = True
            has_replies = True

        transcript.append(
            {
                "agent": agent_name,
                "turn": turn.model_dump(),
                "raw": raw,
            }
        )

        if stop_on == "manual" and turn.stop:
            return DiscussLoopResult(transcript=transcript, artifacts=artifacts, stop_reason="manual")
        if stop_on == "artifact" and turn.intent == "WRAPUP":
            return DiscussLoopResult(transcript=transcript, artifacts=artifacts, stop_reason="artifact")
        if stop_on == "artifact" and mode == "posts" and has_draft and turn.intent == "WRAPUP":
            return DiscussLoopResult(transcript=transcript, artifacts=artifacts, stop_reason="artifact")

    return DiscussLoopResult(transcript=transcript, artifacts=artifacts, stop_reason="turns")
