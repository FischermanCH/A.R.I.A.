"""Declarative metadata for the release/update module.

This file documents current ownership only. It does not wire routes or alter
update execution behavior.
"""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "release_update",
    "name": "Release Update",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "low_medium_build_gated",
    "description": "Owns release labels, update UI, update helper client metadata, and local update helper scripts.",
    "routes": [
        "/health",
        "/update-reconnect-sw.js",
        "/updates",
        "/updates/running",
        "/updates/relogin",
        "/updates/run",
        "/updates/status",
    ],
    "api_routes": [
        "/updates/status",
    ],
    "templates": [
        "updates.html",
        "updates_running.html",
    ],
    "static": [
        "update-reconnect-sw.js",
    ],
    "python": [
        "aria/modules/release_update/release_meta.py",
        "aria/modules/release_update/routes.py",
        "aria/update_helper.py",
        "aria/modules/release_update/helper_client.py",
        "aria/modules/release_update/update_check.py",
        "aria/modules/release_update/native_tools.py",
    ],
    "integration_points": ["aria/modules/release_update/native_tools.py::native_tool_contributions"],
    "scripts": [
        "docker/update-local-aria.sh",
        "docker/aria-host-update.sh",
        "docker/aria-pull-shortcut.sh",
    ],
    "tests": [
        "tests/test_update_helper.py",
        "tests/test_update_check.py",
        "tests/test_updates_ui.py",
        "tests/test_release_update_client_import_boundary.py",
        "tests/test_update_local_script.py",
        "tests/test_host_update_script.py",
    ],
    "depends_on": [
        "auth_policy",
        "configuration_foundations",
        "security_storage",
        "auth_ui",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "config_backup",
        "runtime_diagnostics",
        "chat_admin_update_flows",
        "docker_build_export",
        "web_search",
        "memory",
        "routing",
        "ssh",
        "rss",
        "http_api",
    ],
    "acceptance": ".codex/aria_acceptance/native-agent-admin-diagnostics-alpha846-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Release metadata, update discovery/cache, and helper client implementations are canonical in aria.modules.release_update; aria.core paths are identity-preserving aliases.",
        "Existing app wiring remains in aria/main.py.",
        "release_update.routes also currently owns /health and /api/system/preflight; /health is used as a passive restart-poll readpoint, final owner remains unresolved.",
        "This manifest is descriptive only and must not be treated as behavior acceptance.",
    ],
}
