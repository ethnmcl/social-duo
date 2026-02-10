from __future__ import annotations

import os
import time
from typing import Any

import httpx


class OpenAICompatibleClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required.")

    def chat(self, messages: list[dict], *, temperature: float, max_tokens: int, response_format: dict | None = None) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    raise RuntimeError(f"LLM error {resp.status_code}: {resp.text}")
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"LLM request failed: {last_err}")
