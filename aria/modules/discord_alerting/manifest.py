"""Declarative metadata for Discord alert delivery."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "discord_alerting",
    "name": "Discord Alerting",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "connections",
    "description": "Owns explicitly invoked Discord alert selection, rendering, and transport without sending on import.",
    "python": [
        "aria/modules/discord_alerting/alerts.py",
    ],
    "tests": [
        "tests/test_notification_inbound_storage_import_boundary.py",
        "tests/test_discord_alerts.py",
        "tests/test_runtime_endpoint.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "integration_support",
    ],
    "external_boundaries": [
        {
            "id": "urllib.webhook_transport",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "automatic_or_real_webhook_delivery",
        "connection_profile_secret_or_runtime_access",
        "notification_selection_or_message_behavior_changes",
        "runtime_routing_guardrail_or_confirmation_changes",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/notification-inbound-storage-import-rail-alpha737.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility path is retired; this module is the canonical owner.",
        "Tests patch the transport and perform no network request.",
    ],
}
