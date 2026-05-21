from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Any, Awaitable, Callable

from aria.core.action_plan import ActionPlan
from aria.core.agentic_execution import AgenticExecutionHooks
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution import AgenticExecutionResult
from aria.core.agentic_runtime_debug import runtime_debug_line_for_plan
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import normalize_connection_kind


@dataclass(slots=True)
class RSSFeedExecutionHooks(AgenticExecutionHooks):
    execute_plan: Callable[[ActionPlan, str], Awaitable[str]]
    remember_action: Callable[[str, ActionPlan], None]
    rss_group_bundle_for_query: Callable[[str, str], Awaitable[tuple[str, list[str]] | None]]
    rss_group_bundle_from_candidate_aliases: Callable[[str, str, list[dict[str, Any]]], tuple[str, list[str]] | None]
    build_rss_group_bundle_note: Callable[[str, list[str]], str]
    rss_digest_options_note_for_query: Callable[[str, str], Awaitable[str]]


class RSSFeedExecutionHandler:
    def __init__(self, hooks: RSSFeedExecutionHooks) -> None:
        self._hooks = hooks

    def can_handle(self, request: AgenticExecutionRequest) -> bool:
        payload = dict(request.payload or {})
        return (
            normalize_capability(str(payload.get("capability", "") or "")) == "feed_read"
            and normalize_connection_kind(str(payload.get("connection_kind", "") or "")) == "rss"
        )

    async def execute(self, request: AgenticExecutionRequest) -> AgenticExecutionResult:
        plan = self._hooks.payload_to_action_plan(request.payload)
        if not str(getattr(plan, "requested_connection_ref", "") or "").strip():
            plan = await self._enrich_plan_with_rss_notes(request, plan)
        intents = [f"capability:{plan.capability}"] if str(plan.capability or "").strip() else ["chat"]
        detail_lines: list[str] = []
        if self._hooks.routing_debug_enabled():
            detail_lines.append(runtime_debug_line_for_plan(plan))
        detail_lines.extend(self._hooks.build_capability_detail_lines(plan, request.language))
        try:
            result_text = await self._hooks.execute_plan(plan, request.language)
        except Exception as exc:
            error_text = self._hooks.format_execution_error(plan, exc, request.language)
            error_code = f"capability_{plan.capability}_error:{type(exc).__name__}"
            return AgenticExecutionResult(intents=intents, text=error_text, detail_lines=detail_lines, errors=[error_code])

        if plan.is_complete:
            self._hooks.remember_action(request.user_id, plan)
        self._hooks.learning_service.record_capability_success(
            action=request.action,
            plan=plan,
            result_text=result_text,
            user_message=str(request.resolved.get("query", "") or ""),
            user_id=request.user_id,
            language=request.language,
            detail_lines=detail_lines,
        )
        return AgenticExecutionResult(intents=intents, text=result_text, detail_lines=detail_lines, errors=[])

    async def _enrich_plan_with_rss_notes(self, request: AgenticExecutionRequest, plan: ActionPlan) -> ActionPlan:
        query = str(request.resolved.get("query", "") or "")
        notes = list(plan.notes or [])
        rss_bundle = await self._hooks.rss_group_bundle_for_query(query, plan.connection_ref)
        if rss_bundle is None:
            rss_bundle = self._hooks.rss_group_bundle_from_candidate_aliases(
                query,
                plan.connection_ref,
                list(request.resolved.get("connection_candidates_debug", []) or []),
            )
        if rss_bundle is not None:
            notes.append(self._hooks.build_rss_group_bundle_note(*rss_bundle))
        digest_options_note = await self._hooks.rss_digest_options_note_for_query(query, request.language)
        if digest_options_note:
            notes.append(digest_options_note)
        if notes == list(plan.notes or []):
            return plan
        return replace(plan, notes=notes)
