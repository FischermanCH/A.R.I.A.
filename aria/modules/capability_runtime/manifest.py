"""Declarative metadata for generic capability runtime execution."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "capability_runtime",
    "name": "Capability Runtime",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "actions",
    "description": "Owns the existing generic capability execution handler boundary without registering or invoking runtime work.",
    "python": [
        "aria/modules/capability_runtime/handler.py",
    ],
    "tests": [
        "tests/test_agentic_execution.py",
        "tests/test_runtime_handler_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "runtime_execution_registry",
        "action_runtime_debug",
        "ssh_runtime",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "runtime_handler_registration_or_order_changes",
        "runtime_dispatch_or_execution",
        "connection_or_secret_access",
        "runtime_learning_writes",
        "guardrail_or_confirmation_changes",
        "routing_or_source_authority_changes",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/connection-semantic-runtime-handlers-import-rail-alpha728.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Pipeline still owns handler construction and first-match registration order.",
        "The aria.core path is an identity-preserving compatibility alias.",
        "No handler is instantiated or invoked by this manifest.",
    ],
}
