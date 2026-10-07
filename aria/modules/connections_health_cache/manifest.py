"""Declarative metadata for connection health cache boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_health_cache",
    "name": "Connections Health Cache",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "connections",
    "description": "Owns cached connection health store read/write/delete helpers and status-change alert boundary without owning live connection probes.",
    "python": [
        "aria/modules/connections_health_cache/health.py",
    ],
    "tests": [
        "tests/test_connection_health.py",
        "tests/test_connection_cleanup.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "discord_alerting",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "live_connection_probes",
        "ssh_connection_test",
        "http_api_connection_test",
        "managed_service_live_probe",
        "rss_fetch_runtime",
        "smtp_imap_connection_test",
        "smb_connection_test",
        "mqtt_connection_test",
        "discord_webhook_test",
        "profile_persistence_behavior",
        "runtime_execution",
    ],
    "acceptance": ".codex/aria_acceptance/action-planning-connection-status-import-rail-alpha729.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Live probes remain owned by connections_runtime_status and are not executed by this import-boundary rail.",
        "Focused tests monkeypatch the health store path to tmp_path; no live runtime health store is accessed.",
        "Status-change Discord alerts use the registered discord_alerting boundary; alert behavior is not changed.",
    ],
}
