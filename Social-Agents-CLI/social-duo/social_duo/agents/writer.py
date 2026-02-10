from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from social_duo.agents.prompts import WRITER_SYSTEM
from social_duo.providers.llm import LLMClient
from social_duo.types.schemas import WriterOutput


class WriterAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def _parse(self, content: str) -> WriterOutput:
        data = json.loads(content)
        return WriterOutput.model_validate(data)

    def _call(self, messages: list[dict], *, temperature: float = 0.7) -> WriterOutput:
        resp = self.llm.chat(messages, temperature=temperature, max_tokens=800, response_format={"type": "json_object"})
        content = resp["choices"][0]["message"]["content"]
        try:
            return self._parse(content)
        except (json.JSONDecodeError, ValidationError):
            correction = messages + [
                {"role": "user", "content": "Return valid JSON only. Do not include extra text."}
            ]
            resp = self.llm.chat(correction, temperature=0.2, max_tokens=800, response_format={"type": "json_object"})
            content = resp["choices"][0]["message"]["content"]
            return self._parse(content)

    def draft(self, context: dict[str, Any]) -> WriterOutput:
        prompt = self._build_prompt(context, mode="draft")
        messages = [
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        return self._call(messages)

    def revise(self, context: dict[str, Any]) -> WriterOutput:
        prompt = self._build_prompt(context, mode="revise")
        messages = [
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        return self._call(messages, temperature=0.4)

    def _build_prompt(self, context: dict[str, Any], *, mode: str) -> str:
        base = [
            f"Mode: {mode}",
            f"Goal: {context.get('goal')}",
            f"Topic: {context.get('topic')}",
            f"Platform: {context.get('platform')}",
            f"Audience: {context.get('audience')}",
            f"Tone: {context.get('tone')}",
            f"Length: {context.get('length')}",
            f"CTA required: {context.get('cta_required')}",
            f"CTA text: {context.get('cta_text')}",
            f"Keywords: {', '.join(context.get('keywords', []))}",
            f"Don'ts: {', '.join(context.get('donts', []))}",
            f"Facts: {context.get('facts')}",
            f"Brand voice: {context.get('brand_voice')}",
            f"Platform constraints: {context.get('constraints')}",
            f"Thread count: {context.get('thread_count')}",
        ]

        if context.get("source_text"):
            base.append(f"Source text: {context['source_text']}")
        if context.get("instruction"):
            base.append(f"Instruction: {context['instruction']}")
        if context.get("editor_feedback"):
            base.append(f"Editor feedback: {context['editor_feedback']}")
        if context.get("edited_version"):
            base.append(f"Editor suggested revision: {context['edited_version']}")

        return "\n".join(base)
