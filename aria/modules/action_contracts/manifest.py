"""Declarative metadata for action contract boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_contracts",
    "name": "Action Contracts",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "actions",
    "description": "Owns formal capability/action-plan contracts, executor bindings, policy-family metadata, guardrail-kind metadata, confirmation flags, and runtime payload projection without executing actions.",
    "python": [
        "aria/modules/action_contracts/plan.py",
        "aria/modules/action_contracts/connection.py",
        "aria/modules/action_contracts/capabilities.py",
        "aria/modules/action_contracts/native_tools.py",
    ],
    "integration_points": ["aria/modules/action_contracts/native_tools.py::native_tool_contributions"],
    "tests": [
        "tests/test_connection_action_contract.py",
        "tests/test_capability_catalog.py",
        "tests/test_kernel_contracts_gateway_support_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "action_planner_behavior",
        "routed_action_resolution_behavior",
        "action_execution_behavior",
        "confirmation_ledger_storage",
        "guardrail_policy_behavior",
        "ssh_policy_behavior",
        "http_api_policy_behavior",
        "chat_pending_flow_behavior",
        "pipeline_orchestration_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/kernel-contracts-gateway-support-import-rail-alpha737.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This is the second recommended small Critical subslice after connections_catalog.",
        "Product code imports canonical module contracts; aria.core paths are identity-preserving compatibility aliases.",
        "Runtime payload projection is declarative here; no runtime executor is called.",
        "Capability catalog behavior is canonical in this module and the core path is an identity alias.",
    ],
}
