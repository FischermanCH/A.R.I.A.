from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any
import time

from aria.core.config import LLMConfig
from aria.core.i18n import I18NStore
from aria.core.llm_audit import GLOBAL_LLM_AUDIT_LOG
from aria.core.usage_meter import UsageMeter

_LLM_CLIENT_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _llm_text(key: str, default: str = "", **values: object) -> str:
    template = _LLM_CLIENT_I18N.t("de", f"llm_client.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


class LLMClientError(RuntimeError):
    """Raised when a model call fails or returns an unusable response."""


def _load_litellm_acompletion() -> Any:
    try:
        return getattr(import_module("litellm"), "acompletion")
    except ModuleNotFoundError as exc:
        raise LLMClientError(
            _llm_text(
                "litellm_missing",
                "LiteLLM is not installed. Install ARIA with the model gateway extra: pip install 'aria-agent[model-gateway]'.",
            )
        ) from exc
    except AttributeError as exc:
        raise LLMClientError(
            _llm_text(
                "litellm_missing_acompletion",
                "LiteLLM is installed but does not expose acompletion(). Please update the litellm package.",
            )
        ) from exc


async def _acompletion(**kwargs: Any) -> Any:
    return await _load_litellm_acompletion()(**kwargs)


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
            response = await _acompletion(
                model=self.model,
                messages=messages,
                api_base=self.api_base,
                api_key=self.api_key or None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            GLOBAL_LLM_AUDIT_LOG.record(
                model=str(self.model or "").strip(),
                messages=messages,
                source=source,
                operation=operation,
                user_id=user_id,
                request_id=request_id,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise LLMClientError(_llm_text("request_failed", "LLM request failed: {error}", error=exc)) from exc

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
            duration_ms = int((time.perf_counter() - start) * 1000)
            GLOBAL_LLM_AUDIT_LOG.record(
                model=str(self.model or "").strip(),
                messages=messages,
                source=source,
                operation=operation,
                user_id=user_id,
                request_id=request_id,
                duration_ms=duration_ms,
                usage=usage,
                error=f"empty_response{finish_hint}",
            )
            raise LLMClientError(
                _llm_text("empty_response", "LLM response from model {model} did not contain text{finish_hint}.", model=self.model, finish_hint=finish_hint)
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

        GLOBAL_LLM_AUDIT_LOG.record(
            model=str(self.model or "").strip(),
            messages=messages,
            source=source,
            operation=operation,
            user_id=user_id,
            request_id=request_id,
            duration_ms=int((time.perf_counter() - start) * 1000),
            usage=usage,
            response=content,
        )

        return LLMResponse(
            content=content,
            usage=usage,
            raw=response,
            model=str(self.model or "").strip(),
            metered=metered,
            cost_usd=cost_usd,
        )
