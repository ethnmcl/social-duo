from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from social_duo.agents.prompts import EDITOR_SYSTEM
from social_duo.providers.llm import LLMClient
from social_duo.types.schemas import EditorOutput


class EditorAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def _parse(self, content: str) -> EditorOutput:
        data = json.loads(content)
        return EditorOutput.model_validate(data)

    def _call(self, messages: list[dict], *, temperature: float = 0.2) -> EditorOutput:
        resp = self.llm.chat(messages, temperature=temperature, max_tokens=700, response_format={"type": "json_object"})
        content = resp["choices"][0]["message"]["content"]
        try:
            return self._parse(content)
        except (json.JSONDecodeError, ValidationError):
            correction = messages + [
                {"role": "user", "content": "Return valid JSON only. Do not include extra text."}
            ]
            resp = self.llm.chat(correction, temperature=0.1, max_tokens=700, response_format={"type": "json_object"})
            content = resp["choices"][0]["message"]["content"]
            return self._parse(content)

    def critique(self, context: dict[str, Any]) -> EditorOutput:
        prompt = self._build_prompt(context)
        messages = [
            {"role": "system", "content": EDITOR_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        return self._call(messages)

    def _build_prompt(self, context: dict[str, Any]) -> str:
        base = [
            f"Draft: {context.get('draft')}",
            f"Platform: {context.get('platform')}",
            f"Constraints: {context.get('constraints')}",
            f"Brand voice: {context.get('brand_voice')}",
            f"CTA required: {context.get('cta_required')}",
            f"CTA text: {context.get('cta_text')}",
            f"Facts: {context.get('facts')}",
            f"Don'ts: {context.get('donts')}",
            f"Risk level: {context.get('risk')}",
            f"Scoring metrics: {context.get('metrics')}",
            f"Constraint issues: {context.get('constraint_issues')}",
        ]
        if context.get("source_text"):
            base.append(f"Source text: {context['source_text']}")
        if context.get("goal"):
            base.append(f"Goal: {context['goal']}")
        if context.get("style"):
            base.append(f"Reply style: {context['style']}")
        if context.get("stance"):
            base.append(f"Reply stance: {context['stance']}")

        return "\n".join(base)
