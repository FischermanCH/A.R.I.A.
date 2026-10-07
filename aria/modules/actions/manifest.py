"""Declarative metadata for action planning, confirmation, and resolution."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "actions",
    "name": "Actions",
    "status": "domain_namespace_active",
    "lifecycle": "contract_only",
    "risk": "high",
    "description": "Owns action candidates, planning, confirmation ledger, guarded resolution, and execution flow contracts without changing execution behavior.",
    "candidate_submodules": [
        "action_contracts",
        "action_planner_templates",
        "action_planner_result_state",
        "action_draft_policy",
        "action_confirmation",
        "action_pending_chat_boundary",
        "pipeline_pending_action_contracts",
        "runtime_execution_registry",
        "operator_trace_boundary",
        "runtime_result_summary",
        "capability_error_messages",
        "capability_runtime",
        "execution_dry_run_payloads",
        "execution_dry_run",
        "action_result_summary",
    ],
    "python": [],
    "tests": [
        "tests/test_action_*.py",
        "tests/test_connection_action_contract.py",
        "tests/test_execution_dry_run.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "runtime_guardrails",
    ],
    "external_boundaries": [
        {
            "id": "kernel.trace",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "runtime_execution_behavior",
        "confirmation_semantics",
        "ledger_storage_behavior",
        "routing_authority",
        "ssh_policy_behavior",
        "http_api_policy_behavior",
        "dry_run_semantics",
        "action_result_payload_shape",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-actions-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Concrete Python ownership is delegated to the listed narrow action submodules.",
        "Action confirmation ledger is instantiated in aria/main.py and remains unchanged.",
        "Actions are a core security boundary; every later behavior change needs end-to-end acceptance.",
        "Recipes and connections depend on actions but must not bypass confirmation/guardrails.",
    ],
}
