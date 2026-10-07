"""Declarative metadata for agentic action draft and policy contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_draft_policy",
    "name": "Action Draft Policy",
    "parent": "actions",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns action draft and normalized policy-result contracts plus debug-line projections without changing policy decisions, guardrails, or execution.",
    "python": [
        "aria/modules/action_draft_policy/contracts.py",
        "aria/modules/action_draft_policy/guardrail_drafts.py",
    ],
    "tests": [
        "tests/test_guardrail_drafts.py",
        "tests/test_usage_meter.py",
        "tests/test_agentic_execution.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "agentic_prompt_flow",
        "platform_primitives",
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
        "policy_decision_behavior",
        "guardrail_behavior",
        "confirmation_semantics",
        "routing_authority",
        "runtime_dispatch_or_execution",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/action-control-observability-import-rail-alpha731.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Action draft/policy and Guardrail-draft implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "No policy action, payload, Guardrail authority, debug boundary, or conversion function is changed.",
    ],
}
