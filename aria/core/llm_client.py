from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import time

from litellm import acompletion

from aria.core.config import LLMConfig
from aria.core.usage_meter import UsageMeter


class LLMClientError(RuntimeError):
    """Fehler beim Aufruf des LLM."""


@dataclass
class LLMResponse:
    content: str
    usage: dict[str, int]
    raw: Any
    model: str = ""
    metered: bool = False
    cost_usd: float | None = None


class LLMClient:
    def __init__(self, config: LLMConfig, usage_meter: UsageMeter | None = None):
        self.model = config.model
        self.api_base = config.api_base
        self.api_key = config.api_key
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.timeout_seconds = config.timeout_seconds
        self.usage_meter = usage_meter

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        source: str = "",
        operation: str = "",
        user_id: str = "",
        request_id: str = "",
    ) -> LLMResponse:
        start = time.perf_counter()
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

        metered = False
        cost_usd: float | None = None
        if self.usage_meter is not None:
            duration_ms = int((time.perf_counter() - start) * 1000)
            cost_usd = await self.usage_meter.record_llm_call(
                model=str(self.model or "").strip(),
                usage=usage,
                source=source,
                operation=operation,
                user_id=user_id,
                request_id=request_id,
                duration_ms=duration_ms,
            )
            metered = True

        return LLMResponse(
            content=content,
            usage=usage,
            raw=response,
            model=str(self.model or "").strip(),
            metered=metered,
            cost_usd=cost_usd,
        )
