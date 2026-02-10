from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def chat(self, messages: list[dict], *, temperature: float, max_tokens: int, response_format: dict | None = None) -> dict:
        raise NotImplementedError
