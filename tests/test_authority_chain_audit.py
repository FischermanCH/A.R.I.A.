from __future__ import annotations

from pathlib import Path

from aria.core.authority_chain_audit import ALLOWED_AUTHORITY_EFFECTS
from aria.core.authority_chain_audit import AUTHORITY_CHAIN_BOUNDARIES
from aria.core.authority_chain_audit import authority_chain_boundary_map
from aria.core.authority_chain_audit import red_authority_boundaries

ROOT = Path(__file__).resolve().parents[1]


def test_authority_chain_manifest_covers_known_legacy_boundaries() -> None:
    boundaries = authority_chain_boundary_map()

    assert set(boundaries) == {
        "keyword_router",
        "turn_intent_keyword_fallback",
        "capability_router_kind_inference",
        "routed_action_legacy_kind_inference",
        "routing_resolver_kind_inference",
        "routing_admin_kind_inference",
        "active_learning_hint_kind_inference",
        "semantic_candidate_override",
        "pre_rag_action_gate",
        "meta_catalog_backup_fallback",
        "ssh_plural_scope_legacy_narrowing",
    }


def test_authority_chain_manifest_uses_bounded_effects() -> None:
    for boundary in AUTHORITY_CHAIN_BOUNDARIES:
        assert boundary.effect in ALLOWED_AUTHORITY_EFFECTS
        assert boundary.authority
        assert boundary.source_marker
        assert boundary.owner_note


def test_red_authority_boundaries_do_not_gain_unclassified_terminal_authority() -> None:
    terminal_effects = {"runtime_execution", "hard_route", "free_semantic_authority"}

    for boundary in red_authority_boundaries():
        assert boundary.effect not in terminal_effects
        if boundary.authority == "none":
            assert boundary.effect == "observability_only"
        if boundary.effect == "validation_only":
            assert boundary.authority in {"policy_guardrail", "runtime_guardrail"}


def test_authority_chain_manifest_source_markers_still_exist() -> None:
    sources = {
        "router.KeywordRouter": ROOT / "aria/core/router.py",
        "turn_intent_arbitration.TurnIntentArbiter": ROOT / "aria/core/turn_intent_arbitration.py",
        "capability_router.CapabilityRouter": ROOT / "aria/core/capability_router.py",
        "routed_action_resolver.RoutedActionResolver": ROOT / "aria/core/routed_action_resolver.py",
        "routing_resolver.RoutingResolver": ROOT / "aria/core/routing_resolver.py",
        "routing_admin.resolve_connection_routing_chain": ROOT / "aria/core/routing_admin.py",
        "active_learning_hint_runtime.should_skip_active_learning_hints_for_turn": ROOT / "aria/core/active_learning_hint_runtime.py",
        "pipeline_ssh_helpers.PipelineSshHelpers": ROOT / "aria/core/pipeline_ssh_helpers.py",
        "agentic_context_runtime.AgenticContextRuntime": ROOT / "aria/core/agentic_context_runtime.py",
        "ssh_target_scope_policy.SshTargetScopePolicy": ROOT / "aria/core/ssh_target_scope_policy.py",
    }

    for boundary in AUTHORITY_CHAIN_BOUNDARIES:
        source = sources[boundary.component]
        assert boundary.source_marker in source.read_text(encoding="utf-8")


def test_capability_router_kind_inference_stays_removed() -> None:
    source = (ROOT / "aria/core/capability_router.py").read_text(encoding="utf-8")

    assert "infer_preferred_connection_kind" not in source
    assert authority_chain_boundary_map()["capability_router_kind_inference"].manifest_class == "mitigated_p1"


def test_routing_resolver_does_not_call_free_text_kind_inference() -> None:
    source = (ROOT / "aria/core/routing_resolver.py").read_text(encoding="utf-8")
    resolve_connection_source = source.split("    async def resolve_connection", 1)[1]

    assert "infer_preferred_connection_kind(" not in resolve_connection_source
    assert authority_chain_boundary_map()["routing_resolver_kind_inference"].manifest_class == "mitigated_p1"


def test_routing_admin_kind_inference_is_diagnostic_only() -> None:
    source = (ROOT / "aria/core/routing_admin.py").read_text(encoding="utf-8")
    resolve_chain_source = source.split("async def resolve_connection_routing_chain", 1)[1]

    assert "effective_preferred = inferred_preferred" not in resolve_chain_source
    assert '"inferred_preferred_kind_authority": "diagnostic_only"' in resolve_chain_source
    assert authority_chain_boundary_map()["routing_admin_kind_inference"].effect == "observability_only"


def test_active_learning_hint_kind_inference_stays_removed() -> None:
    source = (ROOT / "aria/core/active_learning_hint_runtime.py").read_text(encoding="utf-8")

    assert "infer_preferred_connection_kind" not in source
    assert authority_chain_boundary_map()["active_learning_hint_kind_inference"].manifest_class == "mitigated_p1"


def test_turn_intent_keyword_fallback_stays_chat_safe() -> None:
    source = (ROOT / "aria/core/turn_intent_arbitration.py").read_text(encoding="utf-8")

    assert 'source="safe_fallback"' in source
    assert "source=\"keyword_router\"" not in source.split("class TurnIntentArbiter", 1)[1]
    assert authority_chain_boundary_map()["turn_intent_keyword_fallback"].authority == "safe_chat_fallback"


def test_keyword_router_is_signal_only_boundary() -> None:
    boundary = authority_chain_boundary_map()["keyword_router"]

    assert boundary.effect == "candidate_only"
    assert boundary.authority == "signal_only"
    assert boundary.manifest_class == "mitigated_p1"


def test_semantic_candidate_override_cannot_promote_to_explicit_ref_authority() -> None:
    source = (ROOT / "aria/core/routed_action_resolver.py").read_text(encoding="utf-8")
    body = source.split("    def resolve_strong_semantic_candidate_override", 1)[1].split(
        "    def resolve_semantic_candidate_hint",
        1,
    )[0]
    boundary = authority_chain_boundary_map()["semantic_candidate_override"]

    assert 'source="explicit_ref"' not in body
    assert "explicit_connection_resolution" not in body
    assert "semantic_candidate_resolution" in body
    assert "memory_hint ignored_by_semantic_candidate" in body
    assert boundary.effect == "contract_bound"
    assert boundary.authority == "semantic_candidate"
    assert boundary.manifest_class == "mitigated_p1"


def test_meta_catalog_backup_fallback_cannot_reauthorize_runtime_actions() -> None:
    source = (ROOT / "aria/core/pipeline.py").read_text(encoding="utf-8")
    action_stage = source.split("    async def _run_process_action_recipe_stage", 1)[1].split(
        "    async def _load_process_context",
        1,
    )[0]

    assert "meta_catalog_backup_fallback phase=action_preflight" in action_stage
    assert "legacy_semantics=blocked" in action_stage
    assert "reason=missing_meta_catalog_action_contract" in action_stage
    assert "legacy_backup_action_contract phase=action_preflight" not in action_stage
