from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthorityChainBoundary:
    boundary_id: str
    component: str
    decision: str
    effect: str
    authority: str
    manifest_class: str
    source_marker: str
    owner_note: str


ALLOWED_AUTHORITY_EFFECTS: frozenset[str] = frozenset(
    {
        "candidate_only",
        "contract_bound",
        "legacy_fallback",
        "observability_only",
        "validation_only",
    }
)


AUTHORITY_CHAIN_BOUNDARIES: tuple[AuthorityChainBoundary, ...] = (
    AuthorityChainBoundary(
        boundary_id="keyword_router",
        component="router.KeywordRouter",
        decision="keyword_route",
        effect="candidate_only",
        authority="signal_only",
        manifest_class="mitigated_p1",
        source_marker="class KeywordRouter",
        owner_note="KeywordRouter remains a weak turn-intent signal; unavailable or low-confidence arbitration falls back to chat, not keyword intent.",
    ),
    AuthorityChainBoundary(
        boundary_id="turn_intent_keyword_fallback",
        component="turn_intent_arbitration.TurnIntentArbiter",
        decision="arbiter_unavailable_or_low_confidence",
        effect="validation_only",
        authority="safe_chat_fallback",
        manifest_class="mitigated_p1",
        source_marker='source="safe_fallback"',
        owner_note="Keyword-router signals no longer become terminal when turn-intent arbitration is unavailable or low confidence.",
    ),
    AuthorityChainBoundary(
        boundary_id="capability_router_kind_inference",
        component="capability_router.CapabilityRouter",
        decision="_resolve_connection_kind",
        effect="contract_bound",
        authority="capability_contract",
        manifest_class="mitigated_p1",
        source_marker="def _resolve_connection_kind",
        owner_note="Free-text kind inference removed; only explicit kind or single executor contract can bind here.",
    ),
    AuthorityChainBoundary(
        boundary_id="routed_action_legacy_kind_inference",
        component="routed_action_resolver.RoutedActionResolver",
        decision="legacy_kind_inference",
        effect="observability_only",
        authority="none",
        manifest_class="red_p1",
        source_marker="legacy_kind_inference",
        owner_note="Free-text kind inference is trace-only when no draft/contract authority exists.",
    ),
    AuthorityChainBoundary(
        boundary_id="routing_resolver_kind_inference",
        component="routing_resolver.RoutingResolver",
        decision="resolve_connection",
        effect="contract_bound",
        authority="explicit_preferred_kind",
        manifest_class="mitigated_p1",
        source_marker='if effective_preferred_kind == "auto":',
        owner_note="RoutingResolver no longer infers preferred kind from free text; only explicit preferred_kind filters candidates.",
    ),
    AuthorityChainBoundary(
        boundary_id="routing_admin_kind_inference",
        component="routing_admin.resolve_connection_routing_chain",
        decision="inferred_preferred_kind",
        effect="observability_only",
        authority="diagnostic_only",
        manifest_class="mitigated_p1",
        source_marker='"inferred_preferred_kind_authority": "diagnostic_only"',
        owner_note="Workbench reports free-text kind inference for comparison only; effective routing uses explicit preferred_kind.",
    ),
    AuthorityChainBoundary(
        boundary_id="active_learning_hint_kind_inference",
        component="active_learning_hint_runtime.should_skip_active_learning_hints_for_turn",
        decision="skip_active_learning_hints",
        effect="observability_only",
        authority="none",
        manifest_class="mitigated_p1",
        source_marker="def should_skip_active_learning_hints_for_turn",
        owner_note="Free-text kind inference removed; active learning hints stay weak LLM context instead of being semantically suppressed.",
    ),
    AuthorityChainBoundary(
        boundary_id="semantic_candidate_override",
        component="routed_action_resolver.RoutedActionResolver",
        decision="resolve_strong_semantic_candidate_override",
        effect="contract_bound",
        authority="semantic_candidate",
        manifest_class="mitigated_p1",
        source_marker="def resolve_strong_semantic_candidate_override",
        owner_note="Strong semantic candidates may replace stale memory hints only as semantic_candidate_resolution; candidate proof must not be promoted to explicit-ref authority.",
    ),
    AuthorityChainBoundary(
        boundary_id="pre_rag_action_gate",
        component="pipeline_ssh_helpers.PipelineSshHelpers",
        decision="ssh_requested_runtime_effect",
        effect="validation_only",
        authority="policy_guardrail",
        manifest_class="red_p1",
        source_marker="boundary\": \"pre_rag_action_gate",
        owner_note="Pre-RAG gate may block risky runtime effects but must not select free semantic targets.",
    ),
    AuthorityChainBoundary(
        boundary_id="meta_catalog_backup_fallback",
        component="agentic_context_runtime.AgenticContextRuntime",
        decision="meta_catalog_contract_fallback",
        effect="legacy_fallback",
        authority="backup_fallback",
        manifest_class="red_p1",
        source_marker="legacy_semantics=enabled",
        owner_note="Legacy arbiter only runs when the strict meta-catalog contract returns fallback.",
    ),
    AuthorityChainBoundary(
        boundary_id="ssh_plural_scope_legacy_narrowing",
        component="ssh_target_scope_policy.SshTargetScopePolicy",
        decision="narrow_plural_target_connections_by_context",
        effect="candidate_only",
        authority="candidate_only",
        manifest_class="red_p0",
        source_marker="legacy_semantic_heuristic component=ssh_target_scope_policy",
        owner_note="Disabled heuristic is kept as a trace marker and returns no narrowed candidates.",
    ),
)


def authority_chain_boundary_map() -> dict[str, AuthorityChainBoundary]:
    return {boundary.boundary_id: boundary for boundary in AUTHORITY_CHAIN_BOUNDARIES}


def red_authority_boundaries() -> tuple[AuthorityChainBoundary, ...]:
    return tuple(
        boundary for boundary in AUTHORITY_CHAIN_BOUNDARIES if boundary.manifest_class.startswith("red_")
    )
