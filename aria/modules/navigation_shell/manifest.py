"""Declarative metadata for the navigation shell module."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "navigation_shell",
    "name": "Navigation Shell",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns the canonical navigation implementation, base shell, section navigation metadata, and shared admin/config navigation templates.",
    "python": [
        "aria/modules/navigation_shell/navigation.py",
        "aria/modules/navigation_shell/request_helpers.py",
        "aria/modules/navigation_shell/ui_helpers.py",
        "aria/modules/navigation_shell/config_helpers.py",
    ],
    "templates": [
        "base.html",
        "_admin_nav_items.html",
        "_admin_section_nav.html",
        "_section_nav.html",
    ],
    "routes": [
        "/favicon.ico",
    ],
    "nav_node_ids": [
        "admin.access",
        "admin.activities",
        "admin.error_interpreter",
        "admin.files",
        "admin.intelligence",
        "admin.llm_debug",
        "admin.mode",
        "admin.memory.maintenance",
        "admin.modules",
        "admin.native_toolcall_selftest",
        "admin.ui_audit",
        "admin.operations",
        "admin.recipes.system",
        "about.licenses",
        "connections.overview",
        "connections.status",
        "connections.templates",
        "connections.types",
        "memory.auto",
        "memory.create",
        "memory.import",
        "memory.overview",
        "persona.appearance",
        "persona.language",
        "persona.prompts",
        "recipes.mine",
        "recipes.overview",
        "recipes.start",
        "settings.overview",
        "settings.persona",
        "settings.updates",
    ],
    "static": [
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon-48x48.png",
        "favicon.ico",
        "logo-aria-v01.png",
        "app-busy-state.js",
        "style.css",
        "vendor/htmx-1.9.12.min.js",
    ],
    "static_prefixes": [
        "background-",
    ],
    "public_path_prefixes": [
        "/static/",
    ],
    "tests": [
        "tests/test_config_routes.py",
        "tests/test_main_request_helpers.py",
        "tests/test_package_artifact_hygiene.py",
    ],
    "depends_on": [
        "action_contracts",
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "chat_surface_behavior",
        "module_route_registration",
        "runtime_actions",
    ],
    "acceptance": ".codex/aria_acceptance/web-ui-composition-ownership-rail-alpha744.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "aria.modules.navigation_shell.navigation is the canonical implementation.",
        "Request, UI, and config-navigation helpers are canonical in aria.modules.navigation_shell; historical aria.web paths are identity aliases.",
    ],
}
