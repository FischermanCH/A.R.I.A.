"""Declarative metadata for execution dry-run payload contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "execution_dry_run_payloads",
    "name": "Execution Dry-Run Payloads",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "actions",
    "description": "Owns descriptive boundaries for turning routing/action candidates into non-executing payload dry-run structures and template payload previews without changing guardrails, confirmation, routing, or runtime execution behavior.",
    "python": [
        "aria/modules/execution_dry_run_payloads/payloads.py",
        "aria/modules/execution_dry_run_payloads/template_payloads.py",
    ],
    "tests": [
        "tests/test_execution_dry_run.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "action_planner_templates",
        "action_planner_result_state",
        "pipeline_pending_action_contracts",
        "platform_primitives",
        "connections_catalog",
        "recipes",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/pipeline_orchestrator/pipeline.py::build_payload_dry_run call sites",
        "aria/modules/ssh_runtime/pipeline_helpers.py::build_payload_dry_run call sites",
        "aria/modules/connection_routing/admin.py::build_payload_dry_run call sites",
    ],
    "explicitly_excluded": [
        "guardrail_policy_behavior",
        "confirmation_semantics",
        "runtime_execution_behavior",
        "runtime_handler_dispatch",
        "routing_decision_behavior",
        "source_authority_behavior",
        "stored_recipe_execution",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/action-planning-connection-status-import-rail-alpha729.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Dry-run payload implementations are canonical in this module; aria.core paths are identity-preserving compatibility aliases.",
        "Dry-run payloads are the bridge between selected action candidates and later guardrail/confirmation previews.",
        "Future payload-shape changes need focused acceptance because downstream guardrail and execution previews consume these structures.",
    ],
}
