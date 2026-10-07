"""Declarative metadata for action confirmation boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_confirmation",
    "name": "Action Confirmation",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "actions",
    "description": "Owns the one-shot action confirmation ledger boundary that atomically consumes signed confirmations before side effects.",
    "python": [
        "aria/modules/action_confirmation/ledger.py",
    ],
    "tests": [
        "tests/test_action_confirmation_ledger.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "actions",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "confirmation_semantics",
        "ledger_storage_behavior",
        "pending_cookie_encoding",
        "chat_pending_flow_behavior",
        "routed_action_resolution_behavior",
        "runtime_action_execution",
        "guardrail_policy_behavior",
        "ssh_execution",
        "http_api_execution",
        "external_side_effects",
    ],
    "acceptance": ".codex/aria_acceptance/native-write-phrasing-toolchoice-fix-alpha850-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The ledger is canonical in this module and remains instantiated in aria/main.py; the aria.core path is an identity-preserving alias.",
        "This slice does not change token scope, replay handling, retention, SQLite schema, or fail-closed behavior.",
        "Future behavior work needs end-to-end confirmation acceptance before touching runtime actions.",
    ],
}
