"""Declarative metadata for capability error and missing-input messages."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "capability_error_messages",
    "name": "Capability Error Messages",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns descriptive boundaries for missing capability inputs, sanitized runtime exceptions, guardrail-block explanations, and HTTP/API status error messages without changing execution or policy behavior.",
    "python": [
        "aria/modules/capability_error_messages/messages.py",
    ],
    "tests": [
        "tests/test_error_handling.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "actions",
        "connections_catalog",
        "http_api",
        "platform_primitives",
        "runtime_result_summary",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/pipeline_orchestrator/pipeline.py::format_capability_* call sites",
    ],
    "explicitly_excluded": [
        "runtime_execution_behavior",
        "guardrail_policy_behavior",
        "confirmation_semantics",
        "routing_decision_behavior",
        "source_authority_behavior",
        "http_api_execution_behavior",
        "action_result_payload_shape",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/provider-planning-policy-import-rail-alpha730.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Messages are user-visible and must not reclassify guardrail blocks as technical failures.",
        "Future wording or classification changes need focused acceptance because they affect operator interpretation of failed actions.",
    ],
}
