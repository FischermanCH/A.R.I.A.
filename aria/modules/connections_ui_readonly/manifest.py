"""Declarative metadata for read-only connection UI boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_ui_readonly",
    "name": "Connections UI Readonly",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "connections",
    "description": "Owns read-only connection page context, route shape, template selection, metadata suggestion route shape, and UI summary helpers without owning mutation handlers or runtime probes.",
    "python": [
        "aria/modules/connections_ui_readonly/context_helpers.py",
        "aria/modules/connections_ui_readonly/detail_routes.py",
        "aria/modules/connections_ui_readonly/metadata_routes.py",
        "aria/modules/connections_ui_readonly/page_helpers.py",
        "aria/modules/connections_ui_readonly/reader_helpers.py",
        "aria/modules/connections_ui_readonly/ui_helpers.py",
        "aria/modules/connections_ui_readonly/surface_helpers.py",
        "aria/modules/connections_ui_readonly/surface_routes.py",
    ],
    "routes": [
        "/connections",
        "/connections/status",
        "/connections/types",
        "/connections/templates",
    ],
    "templates": [
        "_connection_*.html",
        "_connections_*.html",
        "connections_hub.html",
        "connections_status.html",
        "connections_types.html",
        "connections_templates.html",
        "connections_*.html",
        "config_connections_*.html",
    ],
    "tests": [
        "tests/test_connection_context_helpers.py",
        "tests/test_config_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_profiles",
        "connections_runtime_status",
        "config_ui",
        "navigation_shell",
        "platform_primitives",
        "sftp_admin_ui",
        "ssh_admin_ui",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "connection_mutation_handlers",
        "profile_persistence_behavior",
        "raw_config_write_behavior",
        "secret_material_access",
        "runtime_probe_behavior",
        "managed_service_live_probe_behavior",
        "rss_ping_behavior",
        "ssh_key_generation",
        "ssh_key_exchange",
        "factory_reset",
        "qdrant_clear",
        "route_registration_changes",
    ],
    "acceptance": ".codex/aria_acceptance/connections-ui-composition-ownership-rail-alpha744.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This intentionally excludes connection_mutation_handlers.py, connection_mutation_routes.py, and connection_support_helpers.py.",
        "aria.modules.config_ui.routes composes canonical implementations from aria.modules.connections_ui_readonly.",
        "Historical aria.web helper and route paths remain identity aliases.",
        "Future UI behavior work needs route/template acceptance and must avoid live probes unless explicitly permitted.",
    ],
}
