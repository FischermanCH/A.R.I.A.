"""Declarative metadata for action runtime debug helpers."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_runtime_debug",
    "name": "Action Runtime Debug",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns pure runtime- and routing-debug projection helpers for accepted ActionPlan and resolved-action payloads without selecting, registering, or executing runtime actions.",
    "python": [
        "aria/modules/action_runtime_debug/debug.py",
        "aria/modules/action_runtime_debug/routing.py",
    ],
    "tests": [
        "tests/test_agentic_runtime_debug.py",
        "tests/test_pipeline_action_support_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "action_draft_policy",
        "connections_catalog",
        "connections_semantic",
        "pipeline_pending_action_contracts",
    ],
    "external_boundaries": [
        {
            "id": "runtime_handlers",
            "category": "runtime_callback",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "runtime_action_execution",
        "runtime_handler_registration_or_order_changes",
        "guardrail_or_confirmation_behavior",
        "routing_or_source_authority_behavior",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/action-runtime-debug-boundary-import-rail-alpha735.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility paths are retired; this module is the canonical owner.",
        "This module projects already-normalized ActionPlan and resolved-routing data into debug output only.",
        "The alpha741 ownership rail changes no route, target, policy, confirmation, or runtime decision.",
    ],
}
