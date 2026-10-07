"""Declarative metadata for non-executing runtime execution registry boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "runtime_execution_registry",
    "name": "Runtime Execution Registry",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "actions",
    "description": "Owns descriptive boundaries for AgenticExecutionRequest/Result, AgenticExecutionHandler protocol, AgenticExecutionRegistry first-match dispatch contract, and runtime adapter status metadata without owning concrete runtime handler execution.",
    "python": [
        "aria/modules/runtime_execution_registry/contracts.py",
        "aria/modules/runtime_execution_registry/registry.py",
    ],
    "tests": [
        "tests/test_agentic_execution.py::test_agentic_execution_result_keeps_pipeline_tuple_shape",
        "tests/test_agentic_execution.py::test_agentic_execution_registry_runs_first_matching_handler",
        "tests/test_agentic_execution.py::test_agentic_execution_registry_exposes_runtime_adapter_status",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "pipeline_pending_action_contracts",
        "rss",
        "http_api",
    ],
    "external_boundaries": [
        {
            "id": "runtime_action_execution_boundary",
            "category": "runtime_callback",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "concrete_runtime_handler_execution",
        "ssh_runtime_execution",
        "http_api_runtime_execution",
        "rss_runtime_execution",
        "file_or_message_runtime_execution",
        "handler_order_behavior_changes",
        "runtime_adapter_status_behavior_changes",
        "runtime_learning_behavior",
        "guardrail_policy_behavior",
        "confirmation_semantics",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-runtime-execution-registry-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The canonical contracts and first-match registry live here; the private Core compatibility paths are retired.",
        "The import boundary is non-executing; concrete handlers remain excluded.",
        "AgenticExecutionRegistry.execute_first is a dispatch contract, but changing handler order is behavior and remains forbidden here.",
        "Future wiring must keep runtime execution behind accepted confirmation/guardrail contracts.",
    ],
}
