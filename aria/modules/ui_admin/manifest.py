"""Declarative metadata for the UI/admin module.

This file documents current ownership only. It does not wire routes, alter
auth/session behavior, or change config persistence.
"""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "ui_admin",
    "name": "UI Admin",
    "status": "surface_namespace_active",
    "lifecycle": "contract_only",
    "risk": "medium_needs_proof",
    "description": "Historical administrative web-shell container; narrower auth_ui, config_ui, navigation_shell, and stats_ui modules now own concrete readpoints.",
    "candidate_submodules": [
        "auth_ui",
        "config_ui",
        "navigation_shell",
        "stats_ui",
    ],
    "submodule_status": "canonical_owners_active",
    "routes_prefixes": [],
    "python": [
    ],
    "templates": [
        "_admin*.html",
    ],
    "static": [],
    "tests": [
        "tests/test_auth_middleware.py",
        "tests/test_auth_surface_routes.py",
        "tests/test_config_routes.py",
        "tests/test_main_config_cache.py",
        "tests/test_main_request_helpers.py",
        "tests/test_stats_routes.py",
    ],
    "depends_on": [
        "configuration_foundations",
        "auth_ui",
        "platform_primitives",
        "release_update",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "release_update_behavior",
        "config_backup",
        "runtime_diagnostics",
        "connection_profile_mutation",
        "routing_semantics",
        "web_search",
        "memory",
        "chat_pipeline",
        "ssh",
        "rss",
        "http_api",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-ui-admin-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Existing app wiring remains in aria/main.py.",
        "This module is probably too broad and should split before behavior moves.",
        "Concrete config templates are owned by config_ui; ui_admin no longer claims config*.html wildcard ownership.",
        "Auth, navigation shell, stats, and static surface ownership moved to their narrower metadata modules.",
        "Config connection pages overlap with the connections module.",
        "Config routing pages overlap with the routing module.",
        "Config backup and operations diagnostics overlap with ops_config_backup.",
    ],
}
