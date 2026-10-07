"""Declarative metadata for execution dry-run composition."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "execution_dry_run",
    "name": "Execution Dry-Run",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "actions",
    "description": "Owns non-executing Guardrail/confirmation dry-run composition and visible decision text without authorizing or dispatching runtime work.",
    "python": [
        "aria/modules/execution_dry_run/dry_run.py",
        "aria/modules/execution_dry_run/text.py",
    ],
    "tests": [
        "tests/test_execution_dry_run.py",
        "tests/test_execution_dry_run_import_boundary.py",
        "tests/test_error_handling.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "action_draft_policy",
        "config_ui",
        "connections_catalog",
        "execution_dry_run_payloads",
        "http_api_policy",
        "platform_primitives",
        "recipe_runtime",
        "ssh_policy",
        "runtime_guardrails",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "guardrail_or_policy_behavior_changes",
        "confirmation_authorization_or_token_handling",
        "runtime_dispatch_or_execution",
        "routing_or_source_authority_changes",
        "connection_or_secret_access",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/execution-dry-run-import-rail-alpha731.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "Dry-run evaluates existing policy and Guardrail contracts but never dispatches or consumes confirmation.",
    ],
}
