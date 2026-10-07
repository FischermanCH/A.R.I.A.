"""Declarative metadata for inbound event normalization and storage."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "inbound_event_storage",
    "name": "Inbound Event Storage",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "http_api",
    "description": "Owns bounded inbound event redaction, normalization, idempotency, retention, and SQLite storage without registering routes.",
    "python": [
        "aria/modules/inbound_event_storage/store.py",
        "aria/modules/inbound_event_storage/routes.py",
    ],
    "tests": [
        "tests/test_notification_inbound_storage_import_boundary.py",
        "tests/test_inbound_event_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "configuration_foundations",
    ],
    "external_boundaries": [
        {
            "id": "sqlite3",
            "category": "data_boundary",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "productive_inbound_event_database_or_token_access",
        "route_registration_or_auth_token_behavior_changes",
        "redaction_idempotency_retention_or_storage_behavior_changes",
        "runtime_routing_source_guardrail_or_confirmation_changes",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/runtime-inbound-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility path is retired; this module is the canonical owner.",
        "Tests create SQLite databases under pytest tmp_path only.",
    ],
}
