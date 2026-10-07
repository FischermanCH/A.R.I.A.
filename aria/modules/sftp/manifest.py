"""Declarative metadata for the SFTP provider boundary."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "sftp",
    "name": "SFTP",
    "status": "provider_runtime_status_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "connections",
    "description": "Owns the SFTP provider namespace and SFTP status probe adapter without importing SSH.",
    "candidate_submodules": [
        "sftp_admin_ui",
    ],
    "routes_prefixes": [],
    "routes": [],
    "python": [
        "aria/modules/sftp/action_resolution.py",
        "aria/modules/sftp/profile_admin.py",
        "aria/modules/sftp/runtime_execution.py",
        "aria/modules/sftp/status.py",
    ],
    "templates": [],
    "tests": [
        "tests/test_sftp_module_isolation.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections",
        "action_contracts",
        "platform_primitives",
        "runtime_guardrails",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "ssh_command_execution",
        "ssh_connection_open",
        "sftp_connection_open",
        "host_filesystem_access",
        "user_secret_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/module-dispatch-confidence-authority-alpha818.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "SFTP is a separate provider namespace from SSH.",
        "The SFTP status probe adapter is owned here and is invoked only through the generic connection status registry.",
        "Shared Paramiko transport may later move behind a neutral transport port; SFTP must not import SSH modules.",
    ],
}
