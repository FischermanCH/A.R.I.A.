"""Declarative metadata for the existing SFTP administration surface."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "sftp_admin_ui",
    "name": "SFTP Admin UI",
    "parent": "sftp",
    "status": "surface_context_active",
    "risk": "high",
    "lifecycle": "bootstrap_static",
    "description": "Owns SFTP config templates, provider route registration, page context, metadata helper, and save adapter without invoking probe/runtime operations.",
    "routes_prefixes": ["/config/connections/sftp"],
    "routes": [
        "/config/connections/sftp",
        "/config/connections/sftp/save",
        "/config/connections/sftp/suggest-metadata",
    ],
    "templates": ["config_connections_sftp.html"],
    "python": [
        "aria/modules/sftp_admin_ui/context.py",
        "aria/modules/sftp_admin_ui/metadata.py",
        "aria/modules/sftp_admin_ui/mutations.py",
        "aria/modules/sftp_admin_ui/reader.py",
    ],
    "tests": [
        "tests/test_sftp_module_isolation.py",
        "tests/test_config_routes.py",
        "tests/test_connection_admin.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "sftp",
        "config_ui",
        "connections_mutations",
        "connections_profiles",
        "auth_policy",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/connections_ui_readonly/context_helpers.py::SFTP context adapter",
        "aria/modules/connections_ui_readonly/detail_routes.py::SFTP detail route registration adapter",
        "aria/modules/connections_ui_readonly/metadata_routes.py::SFTP metadata route registration adapter",
        "aria/modules/connections_mutations/handlers.py::SFTP save adapter",
        "aria/modules/connections_mutations/routes.py::SFTP mutation route registration adapter",
    ],
    "explicitly_excluded": [
        "secret_access",
        "runtime_access",
        "ssh_command_execution",
    ],
    "acceptance": ".codex/aria_acceptance/module-dispatch-confidence-authority-alpha818.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": ["Central web modules compose SFTP route registrars; SFTP page context, metadata helper, and mutation adapter are owned here."],
}
