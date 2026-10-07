"""Declarative metadata for runtime result summaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "runtime_result_summary",
    "name": "Runtime Result Summary",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "actions",
    "description": "Owns descriptive boundaries for converting existing runtime result text into chat-facing summaries without changing execution, policy, confirmation, routing, or source authority behavior.",
    "python": [
        "aria/modules/runtime_result_summary/summarizers/__init__.py",
        "aria/modules/runtime_result_summary/summarizers/file_operation.py",
        "aria/modules/runtime_result_summary/summarizers/http_api.py",
        "aria/modules/runtime_result_summary/summarizers/imap.py",
        "aria/modules/runtime_result_summary/summarizers/rss.py",
        "aria/modules/runtime_result_summary/summarizers/ssh.py",
    ],
    "tests": [
        "tests/test_result_summarizers.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "runtime_execution_registry",
        "pipeline_pending_action_contracts",
        "platform_primitives",
        "ssh",
        "http_api",
        "rss",
        "connections",
        "actions",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/pipeline_capability_execution/executor.py::summarize_* call sites",
    ],
    "explicitly_excluded": [
        "runtime_execution_behavior",
        "runtime_handler_dispatch",
        "action_result_payload_shape",
        "confirmation_semantics",
        "policy_or_guardrail_behavior",
        "routing_decision_behavior",
        "source_authority_behavior",
        "operator_trace_mapping_behavior_changes",
        "runtime_learning_behavior",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/action-control-observability-import-rail-alpha731.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Summarizers are canonical in this module; the aria.core package and submodule paths are identity-preserving aliases.",
        "Summaries are user-visible evidence and therefore medium/high risk even though they do not execute runtime work.",
        "Future summary behavior changes need focused acceptance because incorrect summaries can make live runtime outcomes look better or worse than the raw result.",
    ],
}
