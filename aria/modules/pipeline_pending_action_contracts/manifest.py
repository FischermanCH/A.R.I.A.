"""Declarative metadata for Pipeline pending action contract boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "pipeline_pending_action_contracts",
    "name": "Pipeline Pending Action Contracts",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "actions",
    "description": "Owns Pipeline pending-action payload, missing-input, confirmation-copy, intent, state, and debug-detail contracts without owning runtime action execution.",
    "python": [
        "aria/modules/pipeline_pending_action_contracts/contracts.py",
    ],
    "tests": [
        "tests/test_pipeline.py::test_pipeline_pending_input_can_fill_missing_connection_ref",
        "tests/test_pipeline.py::test_pipeline_pending_input_uses_validated_structured_connection_ref",
        "tests/test_pipeline.py::test_pipeline_blocks_incomplete_pending_action_contract_before_execution",
        "tests/test_pipeline_action_support_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "action_confirmation",
        "connections_semantic",
        "action_planner_templates",
        "recipe_runtime",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/pipeline_orchestrator/pipeline.py::_pending_follow_up_value",
        "aria/modules/pipeline_orchestrator/pipeline.py::_resolve_pending_missing_input",
        "aria/modules/pipeline_orchestrator/pipeline.py::_action_contract_missing_fields",
        "aria/modules/pipeline_orchestrator/pipeline.py::_action_contract_is_complete",
        "aria/modules/pipeline_orchestrator/pipeline.py::_pending_input_to_draft",
        "aria/modules/pipeline_orchestrator/pipeline.py::_apply_filled_pending_input",
        "aria/modules/pipeline_orchestrator/pipeline.py::_build_pending_action_state",
        "aria/modules/pipeline_orchestrator/pipeline.py::_pending_action_turn_context",
        "aria/modules/pipeline_orchestrator/pipeline.py::arbitrate_pending_routed_action_input",
        "aria/modules/pipeline_orchestrator/pipeline.py::execute_pending_routed_action",
        "aria/modules/pipeline_orchestrator/pipeline.py::continue_pending_routed_action_input",
    ],
    "explicitly_excluded": [
        "runtime_action_execution",
        "confirmed_action_execution_behavior",
        "confirmation_ledger_semantics",
        "pending_cookie_or_token_behavior",
        "guardrail_policy_behavior",
        "dry_run_policy_changes",
        "routing_authority_behavior",
        "turn_arbitration_policy_changes",
        "runtime_learning_behavior",
        "host_artifact_learning_behavior",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-pipeline-pending-action-contracts-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "execute_pending_routed_action and continue_pending_routed_action_input are listed because they contain contract gates; this metadata slice does not own their execution paths.",
        "The helper implementation is canonical in this module; the aria.core path is an identity-preserving compatibility alias.",
        "Future behavior work must keep contract validation separate from runtime execution.",
        "Focused tests use fake LLM/settings and monkeypatch runtime execution where needed.",
        "The alpha741 ownership rail changes no confirmation, pending execution, policy, Guardrail, target, or routing semantics.",
    ],
}
