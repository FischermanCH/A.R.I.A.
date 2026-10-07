"""Declarative metadata for operator trace boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "operator_trace_boundary",
    "name": "Operator Trace Boundary",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "actions",
    "description": "Owns descriptive boundaries for deriving ordered operator_trace detail lines from existing routing/debug/runtime detail lines without changing routing, policy, confirmation, or execution behavior.",
    "python": [
        "aria/modules/operator_trace_boundary/operator_trace.py",
    ],
    "tests": [
        "tests/test_agentic_operator_trace.py",
        "tests/test_agentic_stabilization_gate.py::test_operator_trace_maps_stabilization_gate_contract_lines",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "pipeline_pending_action_contracts",
        "runtime_execution_registry",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/pipeline_orchestrator/pipeline.py::append_operator_trace_detail_lines call sites",
    ],
    "explicitly_excluded": [
        "routing_decision_behavior",
        "policy_or_guardrail_behavior",
        "confirmation_semantics",
        "runtime_execution_behavior",
        "source_authority_behavior",
        "operator_trace_mapping_behavior_changes",
        "detail_line_source_behavior_changes",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/action-control-observability-import-rail-alpha731.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The trace projection is canonical in this module; the aria.core path is an identity-preserving alias.",
        "Operator traces are derived from existing detail lines and must not become a second source of routing truth.",
        "Future trace mapping changes need acceptance because trace lines are used as live diagnostic evidence.",
    ],
}
