from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from social_duo.agents.editor import EditorAgent
from social_duo.agents.writer import WriterAgent
from social_duo.core.constraints import validate_text
from social_duo.types.schemas import AppConfig, EditorOutput, WriterOutput


@dataclass
class LoopResult:
    final: WriterOutput
    editor: EditorOutput
    trace: list[dict[str, Any]]


class LoopError(RuntimeError):
    def __init__(self, message: str, trace: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.trace = trace


def run_loop(
    *,
    writer: WriterAgent,
    editor: EditorAgent,
    config: AppConfig,
    context: dict[str, Any],
    rounds: int,
) -> LoopResult:
    trace: list[dict[str, Any]] = []
    last_editor: EditorOutput | None = None
    draft: WriterOutput | None = None

    for i in range(rounds):
        try:
            if i == 0:
                draft = writer.draft(context)
            else:
                revise_context = dict(context)
                revise_context["editor_feedback"] = [issue.detail for issue in last_editor.issues] if last_editor else []
                revise_context["edited_version"] = last_editor.edited_version if last_editor else ""
                draft = writer.revise(revise_context)
        except Exception as exc:  # noqa: BLE001
            raise LoopError(f"Writer failed: {exc}", trace) from exc

        trace.append({"agent": "WriterAgent", "role": "draft", "content": draft.model_dump()})

        try:
            issues, metrics = validate_text(
                draft.recommended,
                config=config,
                platform=context["platform"],
                cta_required=context.get("cta_required", False),
                cta_text=context.get("cta_text"),
            )
        except Exception as exc:  # noqa: BLE001
            raise LoopError(f"Constraint check failed: {exc}", trace) from exc

        editor_context = dict(context)
        editor_context.update(
            {
                "draft": draft.recommended,
                "metrics": metrics,
                "constraint_issues": issues,
            }
        )

        try:
            last_editor = editor.critique(editor_context)
            trace.append({"agent": "EditorAgent", "role": "critique", "content": last_editor.model_dump()})
        except Exception as exc:  # noqa: BLE001
            raise LoopError(f"Editor failed: {exc}", trace) from exc

        if last_editor.verdict == "PASS":
            break

    if draft is None or last_editor is None:
        raise RuntimeError("Loop did not produce output.")

    return LoopResult(final=draft, editor=last_editor, trace=trace)
