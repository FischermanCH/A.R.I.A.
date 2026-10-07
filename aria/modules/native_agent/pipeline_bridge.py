"""Default-off pre-arbitration bridge for the standalone native agent."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.platform_primitives.actionable_sequence import (
    CrossHostRecipeSuggestionStore,
    ObservedSequenceStore,
)
from aria.modules.platform_primitives.observed_claims import ObservedClaimStore
from aria.modules.native_agent.tool_registry import (
    NATIVE_TOOL_RELEVANCE_THRESHOLD,
    assemble_native_tools,
    filter_tools_by_configured_connections,
    select_relevant_native_tools,
)
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_contracts.text import pipeline_text


def _web_debug_detail_lines(details: Any) -> list[str]:
    if not isinstance(details, dict) or not details:
        return []
    query = json.dumps(str(details.get("request_input") or ""), ensure_ascii=False)
    urls = [str(url) for url in details.get("source_urls", ())[:8] if str(url)]
    return [
        f"Routing Debug: web_llm_query={query}",
        "Routing Debug: web_llm_params "
        f"model={details.get('model') or '-'} "
        f"ctx={details.get('search_context_size') or '-'} "
        f"effort={details.get('reasoning_effort') or '-'} "
        f"max_out={int(details.get('max_output_tokens') or 0)}",
        f"Routing Debug: web_llm_sources={','.join(urls) or '-'} "
        f"web_uses={int(details.get('web_uses') or 0)}",
    ]


def _native_llm_timing_detail_line(outcome: Any) -> str:
    calls = tuple(getattr(outcome, "llm_calls", ()) or ())
    durations = [max(0, int(getattr(call, "duration_ms", 0) or 0)) for call in calls]
    return (
        "Routing Debug: native_llm_timing "
        f"calls={len(calls)} total_ms={sum(durations)} per_call_ms={durations} "
        f"cache_read={sum(int(getattr(call, 'cache_read_input_tokens', 0) or 0) for call in calls)} "
        f"cache_write={sum(int(getattr(call, 'cache_creation_input_tokens', 0) or 0) for call in calls)} "
        f"tools={max((int(getattr(call, 'tool_count', 0) or 0) for call in calls), default=0)} "
        f"input_tokens={sum(int(getattr(call, 'input_tokens', 0) or 0) for call in calls)}"
    )


def _safe_mcp_status_value(value: object, *, limit: int = 80) -> str:
    return "".join(
        character
        for character in str(value or "")
        if character.isalnum() or character in "_.-"
    )[:limit] or "unknown"


def _mcp_unreachable_context_notes(statuses: Any) -> tuple[str, ...]:
    notes: list[str] = []
    for status in tuple(statuses or ()):
        if bool(getattr(status, "connected", False)):
            continue
        server_name = _safe_mcp_status_value(getattr(status, "server_name", ""), limit=64)
        error = _safe_mcp_status_value(
            getattr(status, "error", "") or "discovery_pending",
        )
        notes.append(
            f"MCP server {server_name} capability EXISTS but is temporarily unreachable ({error}). "
            "If the user's request needs it, say plainly that this MCP server is temporarily unreachable; "
            "never claim ARIA lacks the capability. Point the user to Reconnect at "
            "/config/connections/mcp or ask them to restart the bridge."
        )
    return tuple(notes)


def _mcp_unreachable_footer(
    *, message: str, language: str, statuses: Any,
    successful_servers: frozenset[str] = frozenset(),
    failed_servers: frozenset[str] = frozenset(),
) -> str:
    message_tokens = set(re.findall(r"[a-z0-9]+", str(message or "").casefold()))
    for status in tuple(statuses or ()):
        server_name = _safe_mcp_status_value(getattr(status, "server_name", ""), limit=64)
        server_key = re.sub(r"[^a-z0-9]+", "_", server_name.casefold()).strip("_")
        if server_key in successful_servers:
            continue
        # A cached discovery status can still say connected when the first live
        # tools/call after a bridge outage fails.  The call result is the fresher
        # per-turn truth, so a failed call must be allowed to produce the honest
        # footer even before background discovery refreshes the server status.
        if bool(getattr(status, "connected", False)) and server_key not in failed_servers:
            continue
        server_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", server_name.casefold())
            if len(token) >= 5
        }
        if not message_tokens.intersection(server_tokens) and server_key not in failed_servers:
            continue
        error = _safe_mcp_status_value(
            getattr(status, "error", "") or "discovery_pending",
        )
        return pipeline_text(
            language,
            "mcp_unreachable_footer",
            "⚠️ MCP server {server} is currently unreachable ({error}). "
            "[Reconnect](/config/connections/mcp)",
            server=server_name,
            error=error,
        )
    return ""


_MCP_UNREACHABLE_FOOTER_LINE = re.compile(
    r"(?im)^[ \t]*⚠️[ \t]*(?:Der[ \t]+)?MCP[- ]Server\b[^\n]*"
    r"(?:\[Neu verbinden\]|\[Reconnect\])\(/config/connections/mcp\)[ \t]*$"
)


def _strip_mcp_unreachable_history_footers(
    recent_history: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if recent_history is None:
        return None
    cleaned: list[dict[str, Any]] = []
    for row in recent_history:
        copied = dict(row)
        if str(copied.get("role") or "") == "assistant":
            text = _MCP_UNREACHABLE_FOOTER_LINE.sub("", str(copied.get("text") or ""))
            copied["text"] = re.sub(r"\n{3,}", "\n\n", text).strip()
        cleaned.append(copied)
    return cleaned


def _contains_normalized_footer(text: str, footer: str) -> bool:
    normalize = lambda value: " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))
    normalized_footer = normalize(footer)
    return bool(normalized_footer and normalized_footer in normalize(text))


def _dedupe_mcp_unreachable_footer_lines(text: str) -> str:
    seen: set[str] = set()

    def keep_first(match: re.Match[str]) -> str:
        normalized = " ".join(re.findall(r"[a-z0-9]+", match.group(0).casefold()))
        if normalized in seen:
            return ""
        seen.add(normalized)
        return match.group(0).strip()

    return re.sub(r"\n{3,}", "\n\n", _MCP_UNREACHABLE_FOOTER_LINE.sub(keep_first, text)).strip()


def native_agent_enabled(settings: Any) -> bool:
    config = getattr(settings, "agentic_loop", None)
    return bool(getattr(config, "enabled", False) and (
        getattr(config, "native_agent_memory_enabled", False)
        or getattr(config, "native_agent_connections_enabled", False)
        or getattr(config, "native_agent_admin_enabled", False)
        or getattr(config, "native_agent_admin_write_enabled", False)
        or getattr(config, "native_agent_write_notes_enabled", False)
        or getattr(config, "native_agent_write_memory_enabled", False)
        or getattr(config, "native_agent_ssh_enabled", False)
        or getattr(config, "native_agent_messaging_enabled", False)
        or getattr(config, "native_agent_infra_write_enabled", False)
        or getattr(config, "native_agent_recipe_execute_enabled", False)
        or getattr(config, "native_agent_recipe_learn_enabled", False)
        or getattr(config, "native_agent_memory_learn_enabled", False)
        or getattr(config, "native_agent_mcp_enabled", False)
    ))


async def run_native_agent_first_stage(
    owner: Any, *, message: str, user_id: str, request_id: str, source: str, start: float,
    auth_role: str = "", recent_history: list[dict[str, Any]] | None = None,
    confirmation_token: str = "",
    step_callback: Any = None,
    pause_check: Any = None,
    pause_refused: Any = None,
    correction_drain: Any = None,
    detached_check: Any = None,
    usage_callback: Any = None,
    resume_state: dict[str, Any] | None = None,
    language: str = "en",
) -> PipelineResult | None:
    if not native_agent_enabled(owner.settings):
        return None
    config = owner.settings.agentic_loop

    enabled_flags = {
        flag for flag in (
            "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
            "native_agent_admin_write_enabled",
            "native_agent_write_notes_enabled",
            "native_agent_write_memory_enabled",
            "native_agent_ssh_enabled",
            "native_agent_messaging_enabled",
            "native_agent_infra_write_enabled",
            "native_agent_recipe_execute_enabled",
            "native_agent_recipe_learn_enabled",
            "native_agent_memory_learn_enabled",
            "native_agent_mcp_enabled",
        )
        if bool(getattr(config, flag, False))
    }
    mcp_detail_lines: list[str] = []
    mcp_statuses: tuple[Any, ...] = ()
    mcp_client = getattr(owner, "_native_mcp_client", None)
    if "native_agent_mcp_enabled" in enabled_flags and mcp_client is not None:
        discover = getattr(mcp_client, "discover_all", None)
        if callable(discover):
            await discover(block_cold=True)
        statuses = getattr(mcp_client, "statuses", None)
        if callable(statuses):
            mcp_statuses = tuple(statuses())
            for status in mcp_statuses:
                line = (
                    "Routing Debug: mcp "
                    f"server={''.join(character if character.isalnum() or character in '_-' else '_' for character in str(status.server_name))[:64]} "
                    f"status={'connected' if status.connected else 'error'} "
                    f"tool_count={max(0, int(status.tool_count))}"
                )
                if status.error:
                    line += f" error={str(status.error)[:80]}"
                mcp_detail_lines.append(line)
    bindings = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=enabled_flags,
    )
    bindings = filter_tools_by_configured_connections(bindings, owner.settings)
    tool_selector_detail = ""
    if not str(confirmation_token or "").strip():
        tool_selector_total = len(bindings)
        tool_selector_has_extras = any(
            binding.contract.name.startswith("mcp__") for binding in bindings
        )
        tool_selector = getattr(owner, "_native_tool_relevance_selector", None)
        tool_selector_started = time.perf_counter()
        bindings = await select_relevant_native_tools(
            message,
            bindings,
            selector=tool_selector,
            top_k=int(getattr(config, "native_tool_selector_top_k", 16) or 16),
        )
        if tool_selector_total > NATIVE_TOOL_RELEVANCE_THRESHOLD and tool_selector_has_extras:
            selector_telemetry = getattr(tool_selector, "last_telemetry", None)
            selector_ms = max(0, int(getattr(selector_telemetry, "duration_ms", 0) or 0))
            if selector_telemetry is None:
                selector_ms = max(0, int((time.perf_counter() - tool_selector_started) * 1000))
            tool_selector_detail = (
                "Routing Debug: tool_selector active=yes "
                f"selected={len(bindings)}/{tool_selector_total} ms={selector_ms} "
                f"fallback={'yes' if bool(getattr(selector_telemetry, 'fallback', False)) else 'no'}"
            )

    runtime_root = Path(getattr(owner, "_project_root", Path.cwd())) / "data" / "runtime"
    pending_store = getattr(owner, "_native_pending_store", None)
    if pending_store is None:
        pending_store = NativePendingStore(runtime_root / "native_pending_actions.sqlite3")
        owner._native_pending_store = pending_store
    confirmation_ledger = getattr(owner, "_native_confirmation_ledger", None)
    if confirmation_ledger is None:
        confirmation_ledger = ActionConfirmationLedger(runtime_root / "action_confirmations.sqlite3")
        owner._native_confirmation_ledger = confirmation_ledger
    observed_sequence_store = getattr(owner, "_native_observed_sequence_store", None)
    if observed_sequence_store is None:
        observed_sequence_store = ObservedSequenceStore(runtime_root / "observed_sequences.json")
        owner._native_observed_sequence_store = observed_sequence_store
    observed_claim_store = getattr(owner, "_native_observed_claim_store", None)
    if observed_claim_store is None:
        observed_claim_store = ObservedClaimStore(runtime_root / "observed_claims.json")
        owner._native_observed_claim_store = observed_claim_store
    suggestion_store = getattr(owner, "_native_cross_host_recipe_suggestions", None)
    if suggestion_store is None:
        suggestion_store = CrossHostRecipeSuggestionStore()
        owner._native_cross_host_recipe_suggestions = suggestion_store
    recipe_embedding_cache = getattr(owner, "_native_recipe_embedding_cache", None)
    if recipe_embedding_cache is None:
        recipe_embedding_cache = {}
        owner._native_recipe_embedding_cache = recipe_embedding_cache
    recipe_loader = getattr(owner, "_load_stored_recipe_runtime", None)
    try:
        existing_recipes = tuple(recipe_loader()) if callable(recipe_loader) else ()
    except Exception:
        existing_recipes = ()

    usage_meter = getattr(owner, "usage_meter", None) or getattr(owner.settings, "_aria_usage_meter", None)
    async def personal_claim_semantic_checker(
        user_id: str, embedding: Any, top_k: int,
    ) -> bool:
        checker = getattr(owner, "_native_personal_claim_semantic_checker", None)
        if not callable(checker):
            checker = getattr(getattr(owner, "memory_skill", None), "personal_claim_semantic_match", None)
        if not callable(checker):
            raise RuntimeError("personal_claim_semantic_checker_unavailable")
        return bool(await checker(user_id=user_id, embedding=embedding, top_k=top_k))

    owner._native_web_debug_details = None
    outcome = await run_native_agent_turn(
        message=message, user_id=user_id, auth_role=auth_role,
        turn_id=request_id, llm_config=owner.settings.llm,
        tool_bindings=bindings,
        recent_history=_strip_mcp_unreachable_history_footers(recent_history),
        pending_store=pending_store,
        confirmation_ledger=confirmation_ledger,
        confirmation_token=confirmation_token,
        usage_meter=usage_meter,
        completion=getattr(owner, "_native_agent_completion", None),
        trace_root=Path("data/modules/native_agent"),
        observed_sequence_store=observed_sequence_store,
        existing_recipes=existing_recipes,
        embedding_client=getattr(owner, "embedding_client", None),
        recipe_embedding_cache=recipe_embedding_cache,
        cross_host_suggestion_store=suggestion_store,
        memory_learning_enabled=bool(getattr(config, "native_agent_memory_learn_enabled", False)),
        observed_claim_store=observed_claim_store,
        personal_claim_semantic_checker=personal_claim_semantic_checker,
        step_callback=step_callback,
        pause_check=pause_check,
        pause_refused=pause_refused,
        correction_drain=correction_drain,
        detached_check=detached_check,
        usage_callback=usage_callback,
        resume_state=resume_state,
        system_context_notes=_mcp_unreachable_context_notes(mcp_statuses),
        mcp_vision_enabled=bool(getattr(config, "native_agent_mcp_vision_enabled", True)),
        mcp_vision_max_live_images=int(
            getattr(config, "native_agent_mcp_vision_max_live_images", 4) or 4
        ),
        mcp_vision_max_lifetime_images=int(
            getattr(config, "native_agent_mcp_vision_max_lifetime_images", 24) or 24
        ),
        max_steps=int(getattr(config, "native_agent_max_steps", 32) or 32),
        max_provider_calls=int(getattr(config, "native_agent_max_provider_calls", 32) or 32),
        language=language,
    )
    duration_ms = int((time.perf_counter() - start) * 1000)
    native_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    snapshot_scope_fn = getattr(usage_meter, "snapshot_scope", None)
    if callable(snapshot_scope_fn):
        try:
            snap_usage = (snapshot_scope_fn(None) or {}).get("usage") or {}
            native_usage = {
                "prompt_tokens": int(snap_usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(snap_usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(snap_usage.get("total_tokens", 0) or 0),
            }
        except Exception:
            native_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if outcome.accumulated_usage:
        native_usage = {
            key: max(0, int(native_usage.get(key, 0) or 0))
            + max(0, int(outcome.accumulated_usage.get(key, 0) or 0))
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
    flush_scope = getattr(usage_meter, "flush_current_scope", None)
    if callable(flush_scope):
        try:
            activity_intents = ["native_agent"]
            activity_intents.extend(
                intent
                for intent in dict.fromkeys(
                    str(value).strip() for value in tuple(outcome.used_intents or ())
                )
                if intent and intent != "native_agent"
            )
            activity_errors = (
                [outcome.reason or outcome.kind]
                if outcome.kind not in {"final_answer", "pending_confirmation", "confirmation_refused"}
                else []
            )
            await flush_scope(
                intents=activity_intents,
                duration_ms=duration_ms,
                skill_errors=activity_errors,
                activity=dict(outcome.activity) if outcome.activity else None,
            )
        except Exception:
            pass
    detail = (
        "Routing Debug: native_agent_position=pre_arbitration short_circuit=true "
        f"outcome={outcome.kind} provider_calls={outcome.provider_calls} "
        f"used_tools={','.join(outcome.used_tool_names)} reason={outcome.reason or '-'}"
    )
    detail_lines = [detail, _native_llm_timing_detail_line(outcome)]
    detail_lines.append(
        "Routing Debug: native_finish_reason="
        + (str(getattr(outcome, "finish_reason", "") or "-")[:80])
    )
    if outcome.warning:
        detail_lines.append("Routing Debug: native_agent_summary_warning=yes")
    if outcome.finalizer_error_detail:
        detail_lines.append(
            "Routing Debug: native_agent_finalizer_error="
            + str(outcome.finalizer_error_detail)[:480]
        )
    if str(outcome.reason).startswith("native_agent_budget_"):
        detail_lines.append("Routing Debug: native_agent_budget_incomplete=yes")
    if tool_selector_detail:
        detail_lines.append(tool_selector_detail)
    detail_lines.extend(mcp_detail_lines)
    if int(getattr(outcome, "mcp_vision_images", 0) or 0) > 0:
        detail_lines.append(
            "Routing Debug: mcp_vision "
            f"images={max(0, int(outcome.mcp_vision_images))} "
            f"live={max(0, int(getattr(outcome, 'mcp_vision_live_images', 0) or 0))} "
            f"replaced={max(0, int(getattr(outcome, 'mcp_vision_replaced_images', 0) or 0))} "
            f"bytes={max(0, int(outcome.mcp_vision_bytes))}"
        )
    if bool(getattr(outcome, "mcp_vision_degraded", False)):
        detail_lines.append("Routing Debug: mcp_vision degraded=provider_rejected_image")
    if str(getattr(outcome, "llm_param_compat_model", "") or "").strip():
        detail_lines.append(
            "Routing Debug: llm_param_compat "
            f"model={str(outcome.llm_param_compat_model).strip()[:120]} omitted=temperature"
        )
    if outcome.recurrence_signature_hash:
        recurrence_similarity = max(0.0, min(1.0, float(outcome.recurrence_similarity)))
        detail_lines.append(
            "Routing Debug: recurrence "
            f"sig={outcome.recurrence_signature_hash} count={outcome.recurrence_count} "
            f"offered={str(outcome.recurrence_offered).lower()} "
            f"near_sim={recurrence_similarity:.2f} "
            f"emb={'yes' if outcome.recurrence_embedding_used else 'no'}"
        )
    memory_learning_detail = (
        "Routing Debug: memory_learn_extraction "
        f"pre_filter={outcome.memory_learn_pre_filter} "
        f"extraction_ms={max(0, int(outcome.memory_learn_extraction_ms))} "
        f"claim={'yes' if outcome.memory_learn_claim else 'no'}"
    )
    if outcome.memory_learn_claim:
        memory_learn_value = " ".join(str(outcome.memory_learn_value or "").split())[:60]
        memory_learning_detail += (
            f" value={memory_learn_value or '-'} "
            f"sig={outcome.memory_recurrence_signature_hash or '-'} "
            f"count={outcome.memory_recurrence_count} "
            f"offered={str(outcome.memory_recurrence_offered).lower()}"
        )
    detail_lines.append(memory_learning_detail)
    detail_lines.append(
        "Routing Debug: semantic "
        f"match_recipe={outcome.semantic_match_recipe or '-'} sim={outcome.semantic_similarity:.2f}"
    )
    if bool(getattr(config, "native_web_debug_details", False)):
        detail_lines.extend(_web_debug_detail_lines(getattr(owner, "_native_web_debug_details", None)))
    if outcome.kind == "pending_confirmation":
        return PipelineResult(
            request_id=request_id, text=outcome.message,
            usage=dict(native_usage),
            intents=["notes_write"], skill_errors=[], router_level=2,
            duration_ms=duration_ms, detail_lines=list(detail_lines),
            routed_action_confirm_command=outcome.confirm_command,
            routed_action_confirm_preview=outcome.message,
        )
    if outcome.kind == "confirmation_refused":
        return PipelineResult(
            request_id=request_id, text=outcome.message,
            usage=dict(native_usage),
            intents=["native_agent"], skill_errors=[], router_level=2,
            duration_ms=duration_ms, detail_lines=list(detail_lines), clear_routed_action_affordance=True,
        )
    if outcome.kind != "final_answer":
        error_text = (
            "The native agent could not complete this turn safely."
            if outcome.kind == "fail_closed"
            else outcome.message or "The native agent could not complete this turn."
        )
        return PipelineResult(
            request_id=request_id, text=error_text,
            usage=dict(native_usage),
            intents=["native_agent"], skill_errors=[outcome.reason or outcome.kind], router_level=2,
            duration_ms=duration_ms, detail_lines=list(detail_lines),
            clear_routed_action_affordance=outcome.clear_confirmation_affordance,
        )
    final_text = _dedupe_mcp_unreachable_footer_lines(outcome.message)
    successful_servers = frozenset(
        str(name).split("__", 2)[1]
        for name in outcome.successful_tool_names
        if str(name).startswith("mcp__") and len(str(name).split("__", 2)) == 3
    )
    failed_servers = frozenset(
        str(name).split("__", 2)[1]
        for name in outcome.used_tool_names
        if str(name).startswith("mcp__")
        and len(str(name).split("__", 2)) == 3
        and str(name) not in outcome.successful_tool_names
    )
    footer = _mcp_unreachable_footer(
        message=message, language=language, statuses=mcp_statuses,
        successful_servers=successful_servers, failed_servers=failed_servers,
    )
    if footer and not _contains_normalized_footer(final_text, footer):
        final_text = f"{final_text.rstrip()}\n\n{footer}" if final_text.strip() else footer
    return PipelineResult(
        request_id=request_id, text=final_text,
        usage=dict(native_usage),
        intents=[outcome.used_intents[-1] if outcome.used_intents else "chat"],
        skill_errors=[], router_level=2,
        duration_ms=duration_ms, detail_lines=list(detail_lines),
        clear_routed_action_affordance=outcome.clear_confirmation_affordance,
        suggestion_affordance=dict(outcome.suggestion_affordance) if outcome.suggestion_affordance else None,
    )
