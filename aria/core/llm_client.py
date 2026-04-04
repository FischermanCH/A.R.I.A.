from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litellm import acompletion

from aria.core.config import LLMConfig


class LLMClientError(RuntimeError):
    """Fehler beim Aufruf des LLM."""


@dataclass
class LLMResponse:
    content: str
    usage: dict[str, int]
    raw: Any


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.model = config.model
        self.api_base = config.api_base
        self.api_key = config.api_key
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.timeout_seconds = config.timeout_seconds

    async def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        try:
            response = await acompletion(
                model=self.model,
                messages=messages,
                api_base=self.api_base,
                api_key=self.api_key or None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMClientError(f"LLM-Request fehlgeschlagen: {exc}") from exc

        content = ""
        usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        if getattr(response, "choices", None):
            first_choice = response.choices[0]
            message = getattr(first_choice, "message", None)
            content = getattr(message, "content", "") or ""
            finish_reason = getattr(first_choice, "finish_reason", None)
        else:
            finish_reason = None

        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": int(getattr(response.usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(response.usage, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(response.usage, "total_tokens", 0) or 0),
            }

        if not content.strip():
            finish_hint = f", finish_reason={finish_reason}" if finish_reason else ""
            raise LLMClientError(
                f"LLM-Response ohne Textinhalt vom Modell {self.model}{finish_hint}."
            )

        return LLMResponse(content=content, usage=usage, raw=response)
