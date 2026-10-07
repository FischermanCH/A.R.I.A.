"""Declarative metadata for the existing RSS config UI surface."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "rss_ui",
    "name": "RSS UI",
    "status": "surface_contract_active",
    "lifecycle": "contract_only",
    "risk": "medium",
    "parent": "rss",
    "description": "Owns the existing RSS configuration UI template and visible RSS config UI paths without owning feed fetch, OPML, profile persistence, metadata suggestions, or runtime execution.",
    "templates": [
        "config_connections_rss.html",
    ],
    "routes": [
        "/config/connections/rss",
        "/config/connections/rss/poll-interval/save",
        "/config/connections/rss/export-opml",
        "/config/connections/rss/import-opml",
        "/config/connections/rss/ping-now",
        "/config/connections/rss/save",
        "/config/connections/rss/suggest-metadata",
    ],
    "python": [
    ],
    "tests": [
        "tests/test_module_registry_read_model.py",
        "tests/test_config_routes.py",
    ],
    "depends_on": [
        "config_ui",
        "connections",
        "rss",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/connections_ui_readonly/detail_routes.py",
    ],
    "explicitly_excluded": [
        "fastapi_route_registration_from_manifest",
        "rss_feed_fetch_behavior",
        "rss_opml_import_export_behavior",
        "rss_profile_persistence_behavior",
        "rss_metadata_suggestion_behavior",
        "rss_refresh_group_llm_behavior",
        "connection_mutation_behavior",
        "runtime_execution",
        "routing_semantics",
        "auth_session_cookie_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-rss-ui-readpoint-alpha696.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This module is a UI/readpoint boundary only; route decorators and handlers remain explicit in existing web modules.",
        "The broader rss module still owns feed execution, grouping, OPML helpers, runtime metadata, and result summaries.",
    ],
}
