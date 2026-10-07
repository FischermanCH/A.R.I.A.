from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aria.modules.native_web_llm.contracts import NativeWebRequest
from aria.modules.native_web_llm.dispatch import select_web_followup_history
from aria.modules.native_web_llm.gateway import NativeWebLLMError
from aria.modules.native_web_llm.source_policy import resolve_native_web_source_policy
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_contracts.text import pipeline_text


class NativeWebPipelineMixin:
    async def process_native_web(
        self,
        message: str,
        *,
        user_id: str = "web",
        source: str = "web",
        language: str | None = None,
        recent_history: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        started = time.perf_counter()
        request_id = str(uuid4())
        web_config = self.settings.web_llm
        unavailable_error = "native_web_llm_not_configured"
        if (
            self.web_llm_gateway is None
            or not web_config.enabled
            or not web_config.model
            or not web_config.capability_verified_at
        ):
            return PipelineResult(
                request_id=request_id,
                text=pipeline_text(language, "native_web.not_configured", "The Web-LLM is not active and capability-tested yet. I did not make a web request."),
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                intents=["web_search"],
                skill_errors=[unavailable_error],
                router_level=0,
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail_lines=[
                    "Routing Debug: web_dispatch effective=web main_llm_calls=0 provider_requests=0 retries=0",
                ],
            )

        policy = resolve_native_web_source_policy(message)
        configured_domains = tuple(
            str(value or "").strip().lower()
            for value in web_config.allowed_domains
            if str(value or "").strip()
        )
        configured_prefixes = tuple(
            str(value or "").strip()
            for value in web_config.required_url_prefixes
            if str(value or "").strip()
        )
        history = select_web_followup_history(recent_history, limit=4)
        evidence_started = time.perf_counter()
        prior_evidence = (
            await self.web_evidence_store.lookup(message)
            if self.web_evidence_store is not None
            else ()
        )
        evidence_lookup_ms = int((time.perf_counter() - evidence_started) * 1000)
        request = NativeWebRequest(
            question=str(message or "").strip(),
            language=str(language or "de"),
            current_date=datetime.now(timezone.utc).date().isoformat(),
            recent_history=history,
            prior_evidence=prior_evidence,
            allowed_domains=configured_domains or policy.allowed_domains,
            required_url_prefixes=configured_prefixes or policy.required_url_prefixes,
            authority_mode=policy.authority_mode,
            search_context_size=web_config.search_context_size,
            max_search_uses=web_config.max_search_uses,
            max_output_tokens=web_config.max_output_tokens,
        )
        try:
            result = await self.web_llm_gateway.answer(
                request,
                source=source,
                operation="native_web_answer",
                user_id=user_id,
                request_id=request_id,
            )
        except NativeWebLLMError as exc:
            error_code = str(exc).split(":", 1)[0]
            return PipelineResult(
                request_id=request_id,
                text=pipeline_text(language, "native_web.provider_failed", "Web search could not provide a reliable answer. No Main-LLM fallback was executed."),
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                intents=["web_search"],
                skill_errors=[error_code],
                router_level=0,
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail_lines=[
                    "Routing Debug: web_dispatch effective=web main_llm_calls=0 provider_requests=1 retries=0",
                    f"Routing Debug: native_web_provider result=error code={error_code}",
                ],
            )

        errors = list(result.errors)
        evidence_update_scheduled = bool(
            self.web_evidence_store is not None
            and self.web_evidence_store.schedule_update(message, result)
        )
        text = result.answer
        if errors:
            text = pipeline_text(
                language,
                "native_web.authority_failed",
                "Web search did not return sufficiently reliable, authorized evidence, so I am not showing a potentially incorrect answer.",
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        flush_scope = getattr(self.usage_meter, "flush_current_scope", None)
        if callable(flush_scope):
            await flush_scope(intents=["web_search"], duration_ms=duration_ms, skill_errors=errors)
        detail_lines = [
            "Routing Debug: web_dispatch effective=web main_llm_calls=0 provider_requests=1 retries=0",
            "Routing Debug: native_web_llm "
            f"model={result.model or web_config.model} transport={web_config.transport} "
            f"search_uses={result.native_search_uses} citations={len(result.citations)} "
            f"authority={policy.policy_id} duration_ms={result.duration_ms}",
            "Routing Debug: native_web_evidence "
            f"lookup_count={1 if self.web_evidence_store is not None else 0} "
            f"cache={'hit' if prior_evidence else 'miss'} rows={len(prior_evidence)} "
            f"lookup_ms={evidence_lookup_ms} async_update={str(evidence_update_scheduled).lower()}",
            "Routing Debug: native_web_usage "
            f"prompt_tokens={int(result.usage.get('prompt_tokens', 0) or 0)} "
            f"completion_tokens={int(result.usage.get('completion_tokens', 0) or 0)} "
            f"reasoning_tokens={int(result.usage.get('reasoning_tokens', 0) or 0)} "
            f"cached_tokens={int(result.usage.get('cached_tokens', 0) or 0)} "
            f"total_tokens={int(result.usage.get('total_tokens', 0) or 0)} "
            f"request_text_chars={int(result.diagnostics.get('request_text_chars', 0) or 0)} "
            f"reasoning_effort={str(result.diagnostics.get('reasoning_effort', 'provider_default'))}",
            "Routing Debug: native_web_citations "
            + " | ".join(citation.url[:220] for citation in result.citations[:6]),
        ]
        if errors:
            detail_lines.append("Routing Debug: native_web_validation errors=" + ",".join(errors))
        return PipelineResult(
            request_id=request_id,
            text=text,
            usage=dict(result.usage),
            intents=["web_search"],
            skill_errors=errors,
            router_level=0,
            duration_ms=duration_ms,
            chat_cost_usd=result.cost_usd,
            total_cost_usd=result.cost_usd,
            detail_lines=detail_lines,
        )
