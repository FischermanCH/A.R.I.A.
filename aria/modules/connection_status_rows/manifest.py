"""Declarative metadata for cached connection status row boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connection_status_rows",
    "name": "Connection Status Rows",
    "status": "integration_contract_active",
    "lifecycle": "contract_only",
    "risk": "medium_high",
    "parent": "connections",
    "description": "Owns cached/page-probe connection status row rendering boundaries without owning or executing live connection probes.",
    "python": [
    ],
    "tests": [
        "tests/test_connection_runtime.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_health_cache",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/connections_runtime_status/runtime.py::build_connection_status_row",
        "aria/modules/connections_runtime_status/runtime.py::build_connection_status_rows",
        "aria/modules/connections_runtime_status/runtime.py::build_settings_connection_status_rows",
        "aria/modules/connections_runtime_status/runtime.py::_cached_connection_status_row",
        "aria/modules/connections_runtime_status/runtime.py::_cached_rss_connection_status",
        "aria/modules/connections_runtime_status/runtime.py::_last_rss_connection_status",
    ],
    "explicitly_excluded": [
        "live_connection_probes",
        "test_connection_runtime_dispatch",
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
        "This remains function-level ownership inside the canonical connections_runtime_status module because status rows and probe adapters still share one implementation file.",
        "Focused tests must rely on monkeypatched probes/fake urlopen only; no live probe execution is allowed.",
    ],
}
