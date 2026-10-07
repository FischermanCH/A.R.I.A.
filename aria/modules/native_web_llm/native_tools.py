"""Native read-only public Web evidence tool owned by Native Web LLM."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from aria.modules.native_web_llm.contracts import NativeWebRequest
from aria.modules.native_web_llm.source_policy import resolve_native_web_source_policy
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

WEB_EVIDENCE_SOURCE_AUTHORITY = "native_web_llm:provider_evidence"


def _terminal_web_content(answer: str, citations: tuple[Any, ...]) -> str:
    source_lines = []
    for citation in citations[:6]:
        title = str(citation.title or citation.url).replace("[", "\\[").replace("]", "\\]")
        source_lines.append(f"- [{title}]({citation.url})")
    return f"{answer.strip()}\n\nSources:\n" + "\n".join(source_lines)


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def search_fetch(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) != {"query"} or not isinstance(arguments.get("query"), str):
            raise ValueError("native_agent_web_arguments_invalid")
        query = str(arguments["query"]).strip()
        if not query:
            raise ValueError("native_agent_web_arguments_invalid")
        web_config = getattr(getattr(runtime_owner, "settings", None), "web_llm", None)
        gateway = getattr(runtime_owner, "web_llm_gateway", None)
        if (
            gateway is None or web_config is None or not bool(getattr(web_config, "enabled", False))
            or not str(getattr(web_config, "model", "") or "").strip()
            or not str(getattr(web_config, "capability_verified_at", "") or "").strip()
        ):
            raise RuntimeError("native_agent_web_gateway_unavailable")
        policy = resolve_native_web_source_policy(query)
        evidence_store = getattr(runtime_owner, "web_evidence_store", None)
        prior_evidence = await evidence_store.lookup(query) if evidence_store is not None else ()
        configured_domains = tuple(
            str(value or "").strip().lower()
            for value in getattr(web_config, "allowed_domains", ()) if str(value or "").strip()
        )
        configured_prefixes = tuple(
            str(value or "").strip()
            for value in getattr(web_config, "required_url_prefixes", ()) if str(value or "").strip()
        )
        request = NativeWebRequest(
            question=query, current_date=datetime.now(timezone.utc).date().isoformat(),
            prior_evidence=tuple(prior_evidence),
            allowed_domains=configured_domains or policy.allowed_domains,
            required_url_prefixes=configured_prefixes or policy.required_url_prefixes,
            authority_mode=policy.authority_mode,
            search_context_size="high",
            max_search_uses=int(getattr(web_config, "max_search_uses", 3) or 3),
            max_output_tokens=int(getattr(web_config, "max_output_tokens", 1200) or 1200),
        )
        result = await gateway.answer(
            request, source="native_agent", operation="web_search_fetch", user_id=context.user_id,
        )
        runtime_owner._native_web_debug_details = dict(result.diagnostics)
        if not result.passed:
            errors = ",".join(result.errors) or "native_web_evidence_invalid"
            raise RuntimeError(f"native_agent_web_evidence_invalid:{errors}")
        if evidence_store is not None:
            evidence_store.schedule_update(query, result)
        return NativeToolResult(_terminal_web_content(result.answer, result.citations), "web_search")

    return (NativeToolBinding(contract=NativeToolContract(
        owner_module_id="native_web_llm", name="web_search_fetch",
        description="Search fresh public Web sources through ARIA's configured native Web gateway and return a citation-bound answer with URLs. Read-only.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        effect="read_only", confirmation_required=False,
        source_authority=WEB_EVIDENCE_SOURCE_AUTHORITY, user_scoped=True,
        rollout_flag="native_agent_memory_enabled", order=350, terminal=True,
    ), handler=search_fetch),)
