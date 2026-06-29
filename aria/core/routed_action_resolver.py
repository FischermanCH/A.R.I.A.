from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from dataclasses import replace
from typing import Any

from aria.core.action_plan import CapabilityDraft
from aria.core.action_plan import MemoryHints
from aria.core.agentic_prompt_flow import agentic_context_debug_line
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_ref_scope import ConnectionRefScope
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.connection_semantic_resolver import SemanticConnectionHint
from aria.core.connection_semantic_resolver import build_routing_decision_record
from aria.core.connection_semantic_resolver import connection_label_match_score
from aria.core.connection_dossiers import with_capability_draft_updates
from aria.core.routing_resolver import infer_preferred_connection_kind


@dataclass(slots=True)
class RoutedActionResolverRequest:
    message: str
    user_id: str
    language: str | None = None
    capability_draft: Any | None = None
    llm_client: Any | None | object = ...


@dataclass(slots=True)
class RoutedActionResolverPrelude:
    effective_llm_client: Any | None
    effective_kind: str
    candidate_connections: dict[str, Any]
    working_draft: Any
    ref_scope: ConnectionRefScope
    semantic_llm_client: Any | None


@dataclass(slots=True)
class RoutedActionResolverInitialChain:
    resolved: dict[str, Any]
    working_draft: Any
    chain_complete: bool


@dataclass(slots=True)
class RoutedActionResolverEarlyOutcome:
    handled: bool
    resolved: dict[str, Any] | None = None


@dataclass(slots=True)
class RoutedActionSemanticHintUpdate:
    resolved: dict[str, Any]
    hints: MemoryHints
    semantic_record: Any | None


@dataclass(slots=True)
class RoutedActionForcedRefUpdate:
    resolved: dict[str, Any]
    working_draft: Any
    hints: MemoryHints
    forced_ref: str
    semantic_record: Any | None = None
    planner_connection_candidates: list[Any] | None = None


@dataclass(slots=True)
class RoutedActionResolverCallbacks:
    resolve_unified: Callable[..., Awaitable[dict[str, Any] | None]]
    connection_pools: Callable[[], dict[str, dict[str, Any]]]
    default_llm_client: Callable[[], Any | None]
    resolve_live_routing_chain: Callable[..., Awaitable[dict[str, Any]]]
    append_debug_detail_lines: Callable[..., dict[str, Any]]
    chain_complete: Callable[[dict[str, Any]], bool]
    chain_has_signal: Callable[[dict[str, Any] | None], bool]
    append_chain_routing_record: Callable[[dict[str, Any]], dict[str, Any]]
    refresh_ssh_command: Callable[..., Awaitable[tuple[dict[str, Any], Any]]]
    refresh_file_operation: Callable[..., Awaitable[tuple[dict[str, Any], Any]]]
    refresh_message_operation: Callable[..., Awaitable[tuple[dict[str, Any], Any]]]
    refresh_read_operation: Callable[..., Awaitable[tuple[dict[str, Any], Any]]]
    apply_requested_guard: Callable[..., dict[str, Any]]


@dataclass(slots=True)
class RoutedActionBuildCallbacks:
    build_kind_only_resolution: Callable[..., Awaitable[dict[str, Any]]]
    build_forced_resolution: Callable[..., Awaitable[dict[str, Any]]]
    resolved_detail_lines: Callable[[dict[str, Any]], list[str]]
    append_routing_record: Callable[[dict[str, Any], Any], dict[str, Any]]
    attach_candidates_debug: Callable[[dict[str, Any], list[Any]], dict[str, Any]]


@dataclass(slots=True)
class RoutedActionSshCallbacks:
    narrow_plural_targets: Callable[..., tuple[dict[str, Any], dict[str, Any], list[Any]]]
    prepare_plural_command: Callable[..., Awaitable[tuple[dict[str, Any], Any]]]
    apply_plural_resolution: Callable[..., dict[str, Any]]


@dataclass(slots=True)
class RoutedActionSemanticCallbacks:
    semantic_resolver: Any
    requested_ref_matches_candidate: Callable[..., bool]


@dataclass(slots=True)
class RoutedActionGuardCallbacks:
    apply_requested_guard: Callable[..., dict[str, Any]]
    finalize_forced_resolution: Callable[..., Awaitable[dict[str, Any]]] | None = None


class RoutedActionResolver:
    def __init__(self, *, callbacks: RoutedActionResolverCallbacks) -> None:
        self._callbacks = callbacks

    def prepare_request(self, request: RoutedActionResolverRequest) -> RoutedActionResolverPrelude:
        default_llm_client = self._callbacks.default_llm_client()
        effective_llm_client = default_llm_client if request.llm_client is ... else request.llm_client
        connection_pools = self._callbacks.connection_pools()
        effective_kind = normalize_connection_kind(
            str(getattr(request.capability_draft, "connection_kind", "") or "")
        )
        if not effective_kind:
            effective_kind = infer_preferred_connection_kind(
                request.message,
                available_kinds=connection_pools.keys(),
            )
        candidate_connections = connection_pools.get(effective_kind, {}) if effective_kind else {}
        if isinstance(candidate_connections, dict) and len(candidate_connections) <= 1:
            effective_llm_client = None

        working_draft = request.capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(capability="", connection_kind=effective_kind)
        ref_scope = ConnectionRefScope.from_draft(working_draft)
        if effective_kind == "rss":
            effective_llm_client = None
        semantic_llm_client = (
            default_llm_client
            if default_llm_client is not None
            and effective_kind != "rss"
            and not ref_scope.has_explicit
            else None
        )
        return RoutedActionResolverPrelude(
            effective_llm_client=effective_llm_client,
            effective_kind=effective_kind,
            candidate_connections=candidate_connections,
            working_draft=working_draft,
            ref_scope=ref_scope,
            semantic_llm_client=semantic_llm_client,
        )

    async def resolve_initial_chain(
        self,
        request: RoutedActionResolverRequest,
        prelude: RoutedActionResolverPrelude,
    ) -> RoutedActionResolverInitialChain:
        resolved = await self._callbacks.resolve_live_routing_chain(
            request.message,
            preferred_kind=prelude.effective_kind,
            llm_client=prelude.effective_llm_client,
            language=request.language,
        )
        resolved = self._callbacks.append_debug_detail_lines(
            resolved,
            agentic_context_debug_line(
                "capability_draft",
                {
                    "capability": str(getattr(prelude.working_draft, "capability", "") or "").strip() or "-",
                    "kind": prelude.effective_kind or "-",
                    **prelude.ref_scope.debug_fields(),
                    "path": str(getattr(prelude.working_draft, "path", "") or "").strip() or "-",
                    "content": str(getattr(prelude.working_draft, "content", "") or "").strip() or "-",
                },
            ),
            agentic_context_debug_line(
                "candidate_pool",
                {
                    "effective_kind": prelude.effective_kind or "-",
                    "candidates": ", ".join(
                        sorted(
                            str(ref).strip()
                            for ref in prelude.candidate_connections.keys()
                            if str(ref).strip()
                        )
                    )
                    or "-",
                },
            ),
        )
        if prelude.effective_llm_client is not None and not self._callbacks.chain_complete(resolved):
            fallback_resolved = await self._callbacks.resolve_live_routing_chain(
                request.message,
                preferred_kind=prelude.effective_kind,
                llm_client=None,
                language=request.language,
            )
            if self._callbacks.chain_has_signal(fallback_resolved):
                resolved = fallback_resolved
        resolved = self._callbacks.append_chain_routing_record(resolved)

        working_draft = prelude.working_draft
        for refresh in (
            self._callbacks.refresh_ssh_command,
            self._callbacks.refresh_file_operation,
            self._callbacks.refresh_message_operation,
            self._callbacks.refresh_read_operation,
        ):
            resolved, working_draft = await refresh(
                resolved,
                message=request.message,
                user_id=request.user_id,
                capability_draft=working_draft,
                language=request.language,
            )
        return RoutedActionResolverInitialChain(
            resolved=resolved,
            working_draft=working_draft,
            chain_complete=self._callbacks.chain_complete(resolved),
        )

    def resolve_candidate_pool_outcome(
        self,
        *,
        prelude: RoutedActionResolverPrelude,
        initial_chain: RoutedActionResolverInitialChain,
        language: str | None,
    ) -> RoutedActionResolverEarlyOutcome:
        candidate_connections = prelude.candidate_connections
        if initial_chain.chain_complete and (
            not isinstance(candidate_connections, dict) or not candidate_connections
        ):
            return RoutedActionResolverEarlyOutcome(
                handled=True,
                resolved=self._callbacks.apply_requested_guard(
                    initial_chain.resolved,
                    capability_draft=initial_chain.working_draft,
                    language=language,
                ),
            )
        if not isinstance(candidate_connections, dict) or not candidate_connections:
            return RoutedActionResolverEarlyOutcome(handled=True)
        return RoutedActionResolverEarlyOutcome(handled=False)

    def append_memory_hint_routing_debug(
        self,
        resolved: dict[str, Any],
        hints: MemoryHints,
    ) -> dict[str, Any]:
        return self._callbacks.append_debug_detail_lines(
            resolved,
            "Routing Debug: memory_hint "
            f"source={str(hints.source or '').strip() or '-'} "
            f"ref={str(hints.connection_ref or '').strip() or '-'} "
            f"matched_text={str(hints.matched_text or '').strip() or '-'}",
        )

    def planner_connection_candidates_for_semantic_hints(
        self,
        resolved: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
        *,
        routing_candidates_from_resolved: Callable[[dict[str, Any]], list[Any]],
    ) -> list[Any]:
        if semantic_candidates:
            return list(semantic_candidates)
        return routing_candidates_from_resolved(resolved)

    @staticmethod
    def hints_with_semantic_connection(
        hints: MemoryHints,
        semantic_hint: SemanticConnectionHint,
        *,
        effective_kind: str,
    ) -> MemoryHints:
        return replace(
            hints,
            connection_kind=semantic_hint.connection_kind or effective_kind,
            connection_ref=semantic_hint.connection_ref,
            source=semantic_hint.source or hints.source,
            notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
        )

    def resolve_strong_semantic_candidate_override(
        self,
        *,
        resolved: dict[str, Any],
        hints: MemoryHints,
        semantic_candidates: list[SemanticConnectionCandidate],
        ref_scope: ConnectionRefScope,
        plural_target_scope: bool,
        effective_kind: str,
    ) -> RoutedActionSemanticHintUpdate:
        semantic_record: Any | None = None
        if (
            str(hints.connection_ref or "").strip()
            and str(hints.source or "").strip() == "memory_hint"
            and semantic_candidates
        ):
            top_candidate = semantic_candidates[0]
            top_ref = str(top_candidate.connection_ref or "").strip()
            top_score = int(getattr(top_candidate, "score", 0) or 0)
            if (
                top_ref
                and top_ref != str(hints.connection_ref or "").strip()
                and top_score >= 1000
                and not ref_scope.has_requested
                and not plural_target_scope
            ):
                old_ref = str(hints.connection_ref or "").strip()
                resolved = self._callbacks.append_debug_detail_lines(
                    resolved,
                    "Routing Debug: memory_hint ignored_by_explicit_target "
                    f"ref={old_ref} explicit_ref={top_ref}",
                )
                resolved = self._callbacks.append_debug_detail_lines(
                    resolved,
                    f"Routing Debug: explicit_ref selected ref={top_ref}",
                )
                hints = replace(
                    hints,
                    connection_kind=top_candidate.connection_kind or effective_kind,
                    connection_ref=top_ref,
                    source="explicit_ref",
                    matched_text=top_ref,
                    notes=list(hints.notes) + ([top_candidate.note] if top_candidate.note else []),
                )
                semantic_record = build_routing_decision_record(
                    stage="explicit_connection_resolution",
                    candidates=semantic_candidates,
                    hint=SemanticConnectionHint(
                        connection_kind=top_candidate.connection_kind or effective_kind,
                        connection_ref=top_ref,
                        source="explicit_ref",
                        note=top_ref,
                    ),
                    preferred_kind=effective_kind,
                )
        return RoutedActionSemanticHintUpdate(
            resolved=resolved,
            hints=hints,
            semantic_record=semantic_record,
        )

    def resolve_semantic_candidate_hint(
        self,
        message: str,
        *,
        semantic_resolver: Any,
        requested_connection_ref_matches_candidate: Callable[..., bool],
        resolved: dict[str, Any],
        hints: MemoryHints,
        effective_kind: str,
        candidate_connections: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
        ref_scope: ConnectionRefScope,
    ) -> RoutedActionSemanticHintUpdate:
        semantic_record: Any | None = None
        semantic_hint = semantic_resolver.resolve_connection(
            message,
            {effective_kind: candidate_connections},
        )
        if semantic_hint.connection_ref and (
            not ref_scope.has_requested
            or requested_connection_ref_matches_candidate(
                ref_scope.requested_ref,
                connection_kind=effective_kind,
                connection_ref=semantic_hint.connection_ref,
                row=dict(candidate_connections).get(semantic_hint.connection_ref, {}),
            )
        ):
            hints = self.hints_with_semantic_connection(
                hints,
                semantic_hint,
                effective_kind=effective_kind,
            )
            semantic_record = build_routing_decision_record(
                stage="semantic_candidate_resolution",
                candidates=semantic_candidates,
                hint=semantic_hint,
                preferred_kind=effective_kind,
            )
        elif semantic_hint.connection_ref and ref_scope.has_requested:
            resolved = self._callbacks.append_debug_detail_lines(
                resolved,
                "Routing Debug: semantic_hint blocked "
                f"requested_ref={ref_scope.requested_ref} ref={semantic_hint.connection_ref}",
            )
        return RoutedActionSemanticHintUpdate(
            resolved=resolved,
            hints=hints,
            semantic_record=semantic_record,
        )

    async def resolve_semantic_llm_hint(
        self,
        message: str,
        *,
        semantic_resolver: Any,
        requested_connection_ref_matches_candidate: Callable[..., bool],
        resolved: dict[str, Any],
        hints: MemoryHints,
        effective_kind: str,
        candidate_connections: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
        ref_scope: ConnectionRefScope,
    ) -> RoutedActionSemanticHintUpdate:
        semantic_record: Any | None = None
        semantic_hint = await semantic_resolver.resolve_connection_with_llm(
            message,
            {effective_kind: candidate_connections},
            preferred_kind=effective_kind,
        )
        if semantic_hint.connection_ref and (
            not ref_scope.has_requested
            or requested_connection_ref_matches_candidate(
                ref_scope.requested_ref,
                connection_kind=effective_kind,
                connection_ref=semantic_hint.connection_ref,
                row=dict(candidate_connections).get(semantic_hint.connection_ref, {}),
            )
        ):
            hints = self.hints_with_semantic_connection(
                hints,
                semantic_hint,
                effective_kind=effective_kind,
            )
            semantic_record = build_routing_decision_record(
                stage="semantic_llm_resolution",
                candidates=semantic_candidates,
                hint=semantic_hint,
                preferred_kind=effective_kind,
            )
        elif semantic_hint.connection_ref and ref_scope.has_requested:
            resolved = self._callbacks.append_debug_detail_lines(
                resolved,
                "Routing Debug: semantic_llm blocked "
                f"requested_ref={ref_scope.requested_ref} ref={semantic_hint.connection_ref}",
            )
        return RoutedActionSemanticHintUpdate(
            resolved=resolved,
            hints=hints,
            semantic_record=semantic_record,
        )

    async def revalidate_ssh_memory_hint_with_semantic_llm(
        self,
        message: str,
        *,
        semantic_resolver: Any,
        resolved: dict[str, Any],
        hints: MemoryHints,
        effective_kind: str,
        candidate_connections: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
    ) -> RoutedActionSemanticHintUpdate:
        semantic_record: Any | None = None
        semantic_hint = await semantic_resolver.resolve_connection_with_llm(
            message,
            {effective_kind: candidate_connections},
            preferred_kind=effective_kind,
            force_llm=True,
            include_all_profiles=True,
        )
        if semantic_hint.connection_ref and semantic_hint.connection_ref in candidate_connections:
            old_ref = str(hints.connection_ref or "").strip()
            if semantic_hint.connection_ref != old_ref:
                resolved = self._callbacks.append_debug_detail_lines(
                    resolved,
                    "Routing Debug: memory_hint ignored_by_semantic_llm "
                    f"ref={old_ref} selected={semantic_hint.connection_ref}",
                )
            hints = self.hints_with_semantic_connection(
                hints,
                semantic_hint,
                effective_kind=effective_kind,
            )
            semantic_record = build_routing_decision_record(
                stage="semantic_llm_resolution",
                candidates=semantic_candidates,
                hint=semantic_hint,
                preferred_kind=effective_kind,
            )
        return RoutedActionSemanticHintUpdate(
            resolved=resolved,
            hints=hints,
            semantic_record=semantic_record,
        )

    def resolve_plural_scope_memory_hint(
        self,
        message: str,
        *,
        narrow_ssh_plural_target_connections_by_context: Callable[..., tuple[dict[str, Any], dict[str, Any], list[Any]]],
        resolved: dict[str, Any],
        working_draft: Any,
        hints: MemoryHints,
        effective_kind: str,
        plural_target_scope: bool,
        candidate_connections: dict[str, Any],
        planner_connection_candidates: list[Any],
    ) -> RoutedActionForcedRefUpdate:
        forced_ref = str(hints.connection_ref or "").strip()
        if forced_ref and plural_target_scope and effective_kind == "ssh":
            narrowed_resolved, scoped_connections, semantic_scope_candidates = (
                narrow_ssh_plural_target_connections_by_context(
                    resolved,
                    message=message,
                    candidate_connections=candidate_connections,
                )
            )
            forced_ref_score = connection_label_match_score(message, forced_ref)
            if (
                len(scoped_connections) > 1
                and forced_ref_score < 1000
                and (forced_ref not in scoped_connections or forced_ref in scoped_connections)
            ):
                resolved = self._callbacks.append_debug_detail_lines(
                    narrowed_resolved,
                    "Routing Debug: memory_hint ignored_by_plural_target_context "
                    f"ref={forced_ref} refs={', '.join(scoped_connections.keys())}",
                )
                hints = replace(
                    hints,
                    connection_ref="",
                    source="",
                    matched_text="",
                )
                forced_ref = ""
                planner_connection_candidates = semantic_scope_candidates or planner_connection_candidates
        return RoutedActionForcedRefUpdate(
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            forced_ref=forced_ref,
            planner_connection_candidates=planner_connection_candidates,
        )

    def block_requested_ref_memory_hint_mismatch(
        self,
        *,
        requested_connection_ref_matches_candidate: Callable[..., bool],
        resolved: dict[str, Any],
        working_draft: Any,
        hints: MemoryHints,
        effective_kind: str,
        candidate_connections: dict[str, Any],
    ) -> RoutedActionForcedRefUpdate:
        forced_ref = str(hints.connection_ref or "").strip()
        requested_ref = ConnectionRefScope.from_draft(working_draft).requested_ref
        if (
            forced_ref
            and requested_ref
            and str(hints.source or "").strip() == "memory_hint"
            and not requested_connection_ref_matches_candidate(
                requested_ref,
                connection_kind=effective_kind,
                connection_ref=forced_ref,
                row=dict(candidate_connections).get(forced_ref, {}),
            )
        ):
            resolved = self._callbacks.append_debug_detail_lines(
                resolved,
                "Routing Debug: memory_hint blocked "
                f"requested_ref={requested_ref} ref={forced_ref}",
            )
            hints = replace(
                hints,
                connection_ref="",
                source="",
                matched_text="",
            )
            forced_ref = ""
        return RoutedActionForcedRefUpdate(
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            forced_ref=forced_ref,
        )

    def bind_requested_ref_from_semantic_candidate(
        self,
        message: str,
        *,
        semantic_resolver: Any,
        requested_connection_ref_matches_candidate: Callable[..., bool],
        resolved: dict[str, Any],
        working_draft: Any,
        hints: MemoryHints,
        effective_kind: str,
        candidate_connections: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
    ) -> RoutedActionForcedRefUpdate:
        semantic_record: Any | None = None
        forced_ref = str(hints.connection_ref or "").strip()
        requested_ref = ConnectionRefScope.from_draft(working_draft).requested_ref
        if not forced_ref and requested_ref and semantic_candidates:
            requested_hint = semantic_resolver.resolve_connection(
                message,
                {effective_kind: candidate_connections},
            )
            if requested_hint.connection_ref and requested_connection_ref_matches_candidate(
                requested_ref,
                connection_kind=effective_kind,
                connection_ref=requested_hint.connection_ref,
                row=dict(candidate_connections).get(requested_hint.connection_ref, {}),
            ):
                hints = self.hints_with_semantic_connection(
                    hints,
                    replace(requested_hint, source=requested_hint.source or "semantic_alias"),
                    effective_kind=effective_kind,
                )
                forced_ref = str(requested_hint.connection_ref or "").strip()
                if forced_ref:
                    working_draft = with_capability_draft_updates(
                        working_draft,
                        explicit_connection_ref=forced_ref,
                        requested_connection_ref="",
                    )
                    resolved = self._callbacks.append_debug_detail_lines(
                        resolved,
                        agentic_context_debug_line(
                            "capability_draft",
                            {
                                "capability": str(getattr(working_draft, "capability", "") or "-").strip() or "-",
                                "kind": effective_kind or "-",
                                "explicit_ref": forced_ref,
                                "requested_ref": "-",
                                "path": str(getattr(working_draft, "path", "") or "").strip() or "-",
                                "content": str(getattr(working_draft, "content", "") or "").strip() or "-",
                            },
                        ),
                    )
                    resolved = self._callbacks.append_debug_detail_lines(
                        resolved,
                        f"Routing Debug: explicit_ref selected ref={forced_ref}",
                    )
                    resolved = self._callbacks.append_debug_detail_lines(
                        resolved,
                        f"Routing: explicit_connection_resolution selected `{effective_kind}/{forced_ref}` source=explicit_ref note={forced_ref}",
                    )
                semantic_record = build_routing_decision_record(
                    stage="semantic_candidate_resolution",
                    candidates=semantic_candidates,
                    hint=requested_hint,
                    preferred_kind=effective_kind,
                )
        return RoutedActionForcedRefUpdate(
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            forced_ref=forced_ref,
            semantic_record=semantic_record,
        )

    @staticmethod
    def apply_default_single_profile(
        *,
        working_draft: Any,
        hints: MemoryHints,
        candidate_connections: dict[str, Any],
    ) -> RoutedActionForcedRefUpdate:
        forced_ref = str(hints.connection_ref or "").strip()
        if not forced_ref and len(candidate_connections) == 1:
            forced_ref = str(next(iter(candidate_connections.keys())) or "").strip()
            if forced_ref and not str(hints.source or "").strip():
                hints = replace(hints, source="default_single_profile")
        return RoutedActionForcedRefUpdate(
            resolved={},
            working_draft=working_draft,
            hints=hints,
            forced_ref=forced_ref,
        )

    async def refine_rss_forced_ref(
        self,
        message: str,
        *,
        semantic_resolver: Any,
        resolved: dict[str, Any],
        working_draft: Any,
        hints: MemoryHints,
        effective_kind: str,
        candidate_connections: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
    ) -> RoutedActionForcedRefUpdate:
        semantic_record: Any | None = None
        forced_ref = str(hints.connection_ref or "").strip()
        if not forced_ref and effective_kind == "rss" and candidate_connections:
            semantic_hint = await semantic_resolver.resolve_rss_ref(
                message,
                candidate_connections,
                candidates=semantic_candidates,
            )
            if semantic_hint.connection_ref:
                hints = self.hints_with_semantic_connection(
                    hints,
                    semantic_hint,
                    effective_kind=effective_kind,
                )
                forced_ref = str(semantic_hint.connection_ref or "").strip()
                semantic_record = build_routing_decision_record(
                    stage="rss_semantic_refine",
                    candidates=semantic_candidates,
                    hint=semantic_hint,
                    preferred_kind=effective_kind,
                )
        return RoutedActionForcedRefUpdate(
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            forced_ref=forced_ref,
            semantic_record=semantic_record,
        )

    async def resolve_kind_only_or_plural_context(
        self,
        message: str,
        *,
        user_id: str,
        language: str | None,
        effective_kind: str,
        working_draft: Any,
        hints: MemoryHints,
        resolved: dict[str, Any],
        plural_target_scope: bool,
        candidate_connections: dict[str, Any],
        planner_connection_candidates: list[Any],
        build_callbacks: RoutedActionBuildCallbacks,
        ssh_callbacks: RoutedActionSshCallbacks,
        guard_callbacks: RoutedActionGuardCallbacks,
    ) -> dict[str, Any]:
        prior_plural_detail_lines = build_callbacks.resolved_detail_lines(resolved)
        kind_only = await build_callbacks.build_kind_only_resolution(
            message,
            connection_kind=effective_kind,
            language=language,
            llm_client=None,
            capability_draft=working_draft,
            source="kind_inferred",
            reason=str(hints.matched_text or effective_kind),
        )
        kind_only["detail_lines"] = prior_plural_detail_lines
        kind_only = build_callbacks.append_routing_record(
            kind_only,
            build_routing_decision_record(
                stage="kind_only_resolution",
                candidates=[],
                hint=SemanticConnectionHint(
                    connection_kind=effective_kind,
                    connection_ref="",
                    source="kind_inferred",
                    note=str(hints.matched_text or effective_kind),
                ),
                preferred_kind=effective_kind,
            ),
        )
        kind_only = build_callbacks.attach_candidates_debug(kind_only, planner_connection_candidates)
        if plural_target_scope:
            scoped_connections = candidate_connections
            kind_only, scoped_connections, semantic_scope_candidates = ssh_callbacks.narrow_plural_targets(
                kind_only,
                message=message,
                candidate_connections=candidate_connections,
            )
            if len(scoped_connections) == 1:
                scoped_ref = str(next(iter(scoped_connections.keys())) or "").strip()
                if scoped_ref:
                    scoped_resolved = await build_callbacks.build_forced_resolution(
                        message,
                        connection_kind=effective_kind,
                        connection_ref=scoped_ref,
                        language=language,
                        llm_client=None,
                        capability_draft=working_draft,
                        source="plural_target_context",
                        reason=scoped_ref,
                    )
                    scoped_resolved["detail_lines"] = build_callbacks.resolved_detail_lines(kind_only)
                    scoped_resolved = build_callbacks.append_routing_record(
                        scoped_resolved,
                        build_routing_decision_record(
                            stage="plural_target_context_resolution",
                            candidates=semantic_scope_candidates or planner_connection_candidates,
                            hint=SemanticConnectionHint(
                                connection_kind=effective_kind,
                                connection_ref=scoped_ref,
                                source="plural_target_context",
                                note=scoped_ref,
                            ),
                            preferred_kind=effective_kind,
                        ),
                    )
                    scoped_resolved = build_callbacks.attach_candidates_debug(
                        scoped_resolved,
                        semantic_scope_candidates or planner_connection_candidates,
                    )
                    return guard_callbacks.apply_requested_guard(
                        scoped_resolved,
                        capability_draft=working_draft,
                        language=language,
                    )
            kind_only, working_draft = await ssh_callbacks.prepare_plural_command(
                kind_only,
                message=message,
                user_id=user_id,
                candidate_connections=scoped_connections,
                capability_draft=working_draft,
                language=language,
            )
            kind_only = ssh_callbacks.apply_plural_resolution(
                kind_only,
                candidate_connections=scoped_connections,
                capability_draft=working_draft,
                language=language,
            )
        return guard_callbacks.apply_requested_guard(kind_only, capability_draft=working_draft, language=language)

    async def resolve_forced_or_kind_only_routed_action(
        self,
        message: str,
        *,
        user_id: str,
        language: str | None,
        effective_kind: str,
        effective_llm_client: Any | None,
        working_draft: Any,
        hints: MemoryHints,
        resolved: dict[str, Any],
        plural_target_scope: bool,
        candidate_connections: dict[str, Any],
        semantic_candidates: list[SemanticConnectionCandidate],
        semantic_record: Any | None,
        planner_connection_candidates: list[Any],
        semantic_callbacks: RoutedActionSemanticCallbacks,
        build_callbacks: RoutedActionBuildCallbacks,
        ssh_callbacks: RoutedActionSshCallbacks,
        guard_callbacks: RoutedActionGuardCallbacks,
    ) -> dict[str, Any]:
        forced_update = self.resolve_plural_scope_memory_hint(
            message,
            narrow_ssh_plural_target_connections_by_context=ssh_callbacks.narrow_plural_targets,
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            effective_kind=effective_kind,
            plural_target_scope=plural_target_scope,
            candidate_connections=candidate_connections,
            planner_connection_candidates=planner_connection_candidates,
        )
        resolved = forced_update.resolved
        working_draft = forced_update.working_draft
        hints = forced_update.hints
        forced_ref = forced_update.forced_ref
        planner_connection_candidates = forced_update.planner_connection_candidates or planner_connection_candidates

        forced_update = self.block_requested_ref_memory_hint_mismatch(
            requested_connection_ref_matches_candidate=semantic_callbacks.requested_ref_matches_candidate,
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            effective_kind=effective_kind,
            candidate_connections=candidate_connections,
        )
        resolved = forced_update.resolved
        hints = forced_update.hints
        forced_ref = forced_update.forced_ref

        forced_update = self.bind_requested_ref_from_semantic_candidate(
            message,
            semantic_resolver=semantic_callbacks.semantic_resolver,
            requested_connection_ref_matches_candidate=semantic_callbacks.requested_ref_matches_candidate,
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            effective_kind=effective_kind,
            candidate_connections=candidate_connections,
            semantic_candidates=semantic_candidates,
        )
        resolved = forced_update.resolved
        working_draft = forced_update.working_draft
        hints = forced_update.hints
        forced_ref = forced_update.forced_ref
        semantic_record = forced_update.semantic_record or semantic_record

        forced_update = self.apply_default_single_profile(
            working_draft=working_draft,
            hints=hints,
            candidate_connections=candidate_connections,
        )
        working_draft = forced_update.working_draft
        hints = forced_update.hints
        forced_ref = forced_update.forced_ref

        forced_update = await self.refine_rss_forced_ref(
            message,
            semantic_resolver=semantic_callbacks.semantic_resolver,
            resolved=resolved,
            working_draft=working_draft,
            hints=hints,
            effective_kind=effective_kind,
            candidate_connections=candidate_connections,
            semantic_candidates=semantic_candidates,
        )
        resolved = forced_update.resolved
        working_draft = forced_update.working_draft
        hints = forced_update.hints
        forced_ref = forced_update.forced_ref
        semantic_record = forced_update.semantic_record or semantic_record

        if not forced_ref:
            return await self.resolve_kind_only_or_plural_context(
                message,
                user_id=user_id,
                language=language,
                effective_kind=effective_kind,
                working_draft=working_draft,
                hints=hints,
                resolved=resolved,
                plural_target_scope=plural_target_scope,
                candidate_connections=candidate_connections,
                planner_connection_candidates=planner_connection_candidates,
                build_callbacks=build_callbacks,
                ssh_callbacks=ssh_callbacks,
                guard_callbacks=guard_callbacks,
            )

        if guard_callbacks.finalize_forced_resolution is None:
            raise RuntimeError("finalize_forced_resolution callback is required for forced routed actions")
        return await guard_callbacks.finalize_forced_resolution(
            message,
            effective_kind=effective_kind,
            forced_ref=forced_ref,
            language=language,
            effective_llm_client=effective_llm_client,
            working_draft=working_draft,
            hints=hints,
            resolved=resolved,
            semantic_record=semantic_record,
            planner_connection_candidates=planner_connection_candidates,
        )

    async def resolve(self, request: RoutedActionResolverRequest) -> dict[str, Any] | None:
        return await self._callbacks.resolve_unified(
            request.message,
            user_id=request.user_id,
            language=request.language,
            capability_draft=request.capability_draft,
            llm_client=request.llm_client,
        )
