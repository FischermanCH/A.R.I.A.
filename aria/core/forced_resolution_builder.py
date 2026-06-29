from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aria.core.action_plan import MemoryHints
from aria.core.agentic_prompt_flow import agentic_context_debug_line
from aria.core.connection_dossiers import with_capability_draft_updates
from aria.core.connection_semantic_resolver import SemanticConnectionHint
from aria.core.connection_semantic_resolver import build_routing_decision_record
from aria.core.pipeline_action_flow_helpers import append_debug_detail_lines


@dataclass(slots=True)
class ForcedResolutionCallbacks:
    build_forced_with_records: Callable[..., Awaitable[dict[str, Any]]]
    build_kind_only_resolution: Callable[..., Awaitable[dict[str, Any]]]
    chain_complete: Callable[[dict[str, Any]], bool]
    apply_requested_guard: Callable[..., dict[str, Any]]
    resolved_routing_detail_lines: Callable[[dict[str, Any]], list[str]]
    append_routing_record: Callable[[dict[str, Any], Any], dict[str, Any]]
    attach_connection_candidates_debug: Callable[[dict[str, Any], list[Any]], dict[str, Any]]


@dataclass(slots=True)
class ForcedResolutionRecordCallbacks:
    build_forced_resolution: Callable[..., Awaitable[dict[str, Any]]]
    resolved_routing_detail_lines: Callable[[dict[str, Any]], list[str]]
    append_routing_record: Callable[[dict[str, Any], Any], dict[str, Any]]
    attach_connection_candidates_debug: Callable[[dict[str, Any], list[Any]], dict[str, Any]]


class ForcedResolutionBuilder:
    def __init__(
        self,
        *,
        routing_debug_enabled: Callable[[], bool],
    ) -> None:
        self._routing_debug_enabled = routing_debug_enabled

    async def finalize(
        self,
        message: str,
        *,
        effective_kind: str,
        forced_ref: str,
        language: str | None,
        effective_llm_client: Any | None,
        working_draft: Any,
        hints: MemoryHints,
        resolved: dict[str, Any],
        semantic_record: Any | None,
        planner_connection_candidates: list[Any],
        callbacks: ForcedResolutionCallbacks,
    ) -> dict[str, Any]:
        if (
            effective_kind == "ssh"
            and forced_ref
            and not str(getattr(working_draft, "capability", "") or "").strip()
        ):
            working_draft = with_capability_draft_updates(
                working_draft,
                capability="ssh_command",
                connection_kind="ssh",
                explicit_connection_ref=forced_ref,
            )
            resolved = append_debug_detail_lines(
                resolved,
                agentic_context_debug_line(
                    "capability_draft",
                    {
                        "capability": "ssh_command",
                        "kind": "ssh",
                        "explicit_ref": forced_ref,
                        "requested_ref": "-",
                        "path": "-",
                        "content": str(getattr(working_draft, "content", "") or "").strip() or "-",
                    },
                ),
                routing_debug_enabled=self._routing_debug_enabled(),
            )

        forced_source = str(hints.source or "memory_hint")
        forced_reason = str(hints.matched_text or forced_ref)
        forced_llm_client = (
            None
            if str(hints.source or "").strip() in {"semantic_alias", "semantic_llm", "explicit_ref"}
            else effective_llm_client
        )
        forced_resolved = await callbacks.build_forced_with_records(
            message,
            effective_kind=effective_kind,
            forced_ref=forced_ref,
            language=language,
            llm_client=forced_llm_client,
            capability_draft=working_draft,
            source=forced_source,
            reason=forced_reason,
            prior_resolved=resolved,
            semantic_record=semantic_record,
            planner_connection_candidates=planner_connection_candidates,
        )
        if callbacks.chain_complete(forced_resolved):
            return callbacks.apply_requested_guard(
                forced_resolved,
                capability_draft=working_draft,
                language=language,
            )

        payload = dict((forced_resolved.get("payload_debug") or {}).get("payload", {}) or {})
        missing_fields = [str(item or "").strip() for item in list(payload.get("missing_fields", []) or [])]
        if forced_ref and missing_fields == ["connection_ref"]:
            forced_resolved = await callbacks.build_forced_with_records(
                message,
                effective_kind=effective_kind,
                forced_ref=forced_ref,
                language=language,
                llm_client=None,
                capability_draft=working_draft,
                source=forced_source,
                reason=forced_reason,
                prior_resolved=resolved,
                semantic_record=semantic_record,
                planner_connection_candidates=planner_connection_candidates,
            )
            if callbacks.chain_complete(forced_resolved):
                return callbacks.apply_requested_guard(
                    forced_resolved,
                    capability_draft=working_draft,
                    language=language,
                )

        kind_only = await callbacks.build_kind_only_resolution(
            message,
            connection_kind=effective_kind,
            language=language,
            llm_client=None,
            capability_draft=working_draft,
            source=str(hints.source or "kind_inferred"),
            reason=str(hints.matched_text or forced_ref or effective_kind),
        )
        kind_only["detail_lines"] = callbacks.resolved_routing_detail_lines(resolved)
        kind_only = callbacks.append_routing_record(
            kind_only,
            build_routing_decision_record(
                stage="kind_only_resolution",
                candidates=[],
                hint=SemanticConnectionHint(
                    connection_kind=effective_kind,
                    connection_ref="",
                    source=str(hints.source or "kind_inferred"),
                    note=str(hints.matched_text or forced_ref or effective_kind),
                ),
                preferred_kind=effective_kind,
            ),
        )
        kind_only = callbacks.attach_connection_candidates_debug(kind_only, planner_connection_candidates)
        return callbacks.apply_requested_guard(kind_only, capability_draft=working_draft, language=language)

    async def build_with_records(
        self,
        message: str,
        *,
        effective_kind: str,
        forced_ref: str,
        language: str | None,
        llm_client: Any | None,
        capability_draft: Any,
        source: str,
        reason: str,
        prior_resolved: dict[str, Any],
        semantic_record: Any | None,
        planner_connection_candidates: list[Any],
        callbacks: ForcedResolutionRecordCallbacks,
    ) -> dict[str, Any]:
        forced_resolved = await callbacks.build_forced_resolution(
            message,
            connection_kind=effective_kind,
            connection_ref=forced_ref,
            language=language,
            llm_client=llm_client,
            capability_draft=capability_draft,
            source=source,
            reason=reason,
        )
        forced_resolved["detail_lines"] = [
            *callbacks.resolved_routing_detail_lines(prior_resolved),
            *callbacks.resolved_routing_detail_lines(forced_resolved),
        ]
        if semantic_record is not None:
            forced_resolved = callbacks.append_routing_record(forced_resolved, semantic_record)
        forced_resolved = callbacks.append_routing_record(
            forced_resolved,
            build_routing_decision_record(
                stage="forced_connection_resolution",
                candidates=[],
                hint=SemanticConnectionHint(
                    connection_kind=effective_kind,
                    connection_ref=forced_ref,
                    source=source,
                    note=reason,
                ),
                preferred_kind=effective_kind,
            ),
        )
        return callbacks.attach_connection_candidates_debug(forced_resolved, planner_connection_candidates)
