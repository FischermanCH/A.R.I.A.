from __future__ import annotations

from dataclasses import replace
from importlib import import_module
import time
from typing import Any, Awaitable, Callable

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.model_usage_observability.usage_meter import UsageMeter
from aria.modules.native_web_llm.authority import validate_native_web_result
from aria.modules.native_web_llm.contracts import NativeWebRequest, NativeWebResult
from aria.modules.native_web_llm.normalization import as_mapping, normalize_native_web_response


ProviderCall = Callable[..., Awaitable[Any]]


class NativeWebLLMError(RuntimeError):
    pass


def _load_provider_call(transport: str) -> ProviderCall:
    litellm = import_module("litellm")
    name = "aresponses" if transport == "openai_responses" else "acompletion"
    provider_call = getattr(litellm, name, None)
    if not callable(provider_call):
        raise NativeWebLLMError(f"native_web_transport_unavailable:{transport}")
    return provider_call


def _bounded_history(history: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for role, content in history[-4:]:
        clean_role = str(role or "").strip().lower()
        clean_content = " ".join(str(content or "").split())[:1200]
        if clean_role in {"user", "assistant"} and clean_content:
            rows.append({"role": clean_role, "content": clean_content})
    return rows


def _instructions(request: NativeWebRequest) -> str:
    language = "German" if str(request.language or "de").lower().startswith("de") else "the user's language"
    authority = (
        "Use official primary sources for current product, version, price, legal, medical or safety claims. "
        "If the required primary evidence is unavailable, say so instead of presenting an unsupported claim."
    )
    return (
        f"Answer the user directly in {language}. The current date is {request.current_date or 'unknown'}. "
        "Use native web search. Return provider citations for every current factual claim. "
        "If the query or any provided hint contains an older year or an outdated model, ignore it and "
        f"return the CURRENT state as of {request.current_date or 'unknown'} via live web search - never anchor "
        "to a past year. "
        f"{authority} Do not describe the search process and do not answer from model memory alone."
    )


def _request_input(request: NativeWebRequest) -> str:
    sections = [request.question.strip()]
    history = _bounded_history(request.recent_history)
    if history:
        sections.append(
            "Bounded conversation context:\n"
            + "\n".join(f"{row['role']}: {row['content']}" for row in history)
        )
    return "\n\n".join(sections)


def _gpt5_reasoning_effort(model: str) -> str:
    model_id = str(model or "").strip().lower().rsplit("/", 1)[-1]
    if not model_id.startswith("gpt-5"):
        return ""
    suffix = model_id[len("gpt-5") : len("gpt-5") + 1]
    return "low" if not suffix or suffix in {".", "-", "_"} else ""


def _actual_provider_input(provider_kwargs: dict[str, Any]) -> str:
    direct_input = provider_kwargs.get("input")
    if isinstance(direct_input, str):
        return direct_input
    messages = provider_kwargs.get("messages")
    if isinstance(messages, list):
        for row in reversed(messages):
            if isinstance(row, dict) and str(row.get("role") or "").strip() == "user":
                return str(row.get("content") or "")
    return ""


class NativeWebLLMGateway:
    def __init__(
        self,
        config: LLMConfig,
        *,
        transport: str = "openai_responses",
        usage_meter: UsageMeter | None = None,
        provider_call: ProviderCall | None = None,
    ) -> None:
        self.config = config
        self.transport = str(transport or "openai_responses").strip()
        self.usage_meter = usage_meter
        self._provider_call = provider_call

    def _call(self) -> ProviderCall:
        return self._provider_call or _load_provider_call(self.transport)

    async def answer(
        self,
        request: NativeWebRequest,
        *,
        source: str = "web",
        operation: str = "native_web_answer",
        user_id: str = "",
        request_id: str = "",
    ) -> NativeWebResult:
        if not request.question.strip():
            raise NativeWebLLMError("native_web_question_missing")
        if not 1 <= int(request.max_search_uses or 0) <= 3:
            raise NativeWebLLMError("native_web_search_budget_invalid")
        provider_kwargs = self._provider_kwargs(request)
        started = time.perf_counter()
        try:
            response = await self._call()(**provider_kwargs)
        except Exception as exc:
            raise NativeWebLLMError(f"native_web_provider_failed:{type(exc).__name__}") from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        result = normalize_native_web_response(as_mapping(response), duration_ms=duration_ms)
        result = validate_native_web_result(result, request)
        cost_usd: float | None = None
        metered = False
        if self.usage_meter is not None:
            record = getattr(self.usage_meter, "record_web_llm_call", None)
            if callable(record):
                cost_usd = await record(
                    model=result.model or self.config.model,
                    usage=result.usage,
                    native_search_uses=result.native_search_uses,
                    source=source,
                    operation=operation,
                    user_id=user_id,
                    request_id=request_id,
                    duration_ms=duration_ms,
                )
                metered = True
        diagnostics = {
            "request_input": _actual_provider_input(provider_kwargs),
            "model": str(provider_kwargs.get("model") or self.config.model),
            "search_context_size": str(request.search_context_size or ""),
            "max_output_tokens": int(
                provider_kwargs.get("max_output_tokens") or provider_kwargs.get("max_tokens") or 0
            ),
            "source_urls": [str(citation.url) for citation in result.citations[:8]],
            "web_uses": result.native_search_uses,
            "transport": self.transport,
            "provider_requests": 1,
            "main_llm_requests": 0,
            "retries": 0,
            "native_search_uses": result.native_search_uses,
            "citation_count": len(result.citations),
            "citation_hosts": sorted(
                {
                    str(citation.url).split("/", 3)[2].lower()
                    for citation in result.citations
                    if str(citation.url).startswith(("http://", "https://"))
                }
            ),
            "reasoning_effort": _gpt5_reasoning_effort(self.config.model) or "provider_default",
            "request_text_chars": len(_instructions(request)) + len(_request_input(request)),
        }
        return replace(result, metered=metered, cost_usd=cost_usd, diagnostics=diagnostics)

    def _provider_kwargs(self, request: NativeWebRequest) -> dict[str, Any]:
        common = {
            "model": self.config.model,
            "api_base": self.config.api_base,
            "api_key": self.config.api_key or None,
            "timeout": self.config.timeout_seconds,
        }
        if self.transport == "openai_responses":
            tool: dict[str, Any] = {
                "type": "web_search",
                "search_context_size": request.search_context_size,
            }
            if request.allowed_domains:
                tool["filters"] = {"allowed_domains": list(request.allowed_domains)}
            kwargs = {
                **common,
                "input": _request_input(request),
                "instructions": _instructions(request),
                "tools": [tool],
                "include": ["web_search_call.action.sources"],
                "max_output_tokens": min(request.max_output_tokens, self.config.max_tokens),
            }
            reasoning_effort = _gpt5_reasoning_effort(self.config.model)
            if reasoning_effort:
                kwargs["reasoning"] = {"effort": reasoning_effort}
            return kwargs
        messages = [
            {"role": "system", "content": _instructions(request)},
            *_bounded_history(request.recent_history),
            {"role": "user", "content": request.question},
        ]
        kwargs: dict[str, Any] = {
            **common,
            "messages": messages,
            "max_tokens": min(request.max_output_tokens, self.config.max_tokens),
        }
        if self.transport == "anthropic_native":
            kwargs["tools"] = [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": request.max_search_uses,
                }
            ]
        elif self.transport == "openai_web_search_options":
            kwargs["web_search_options"] = {"search_context_size": request.search_context_size}
        else:
            raise NativeWebLLMError(f"native_web_transport_unknown:{self.transport}")
        return kwargs
