"""Declarative metadata for the existing watched-website config UI surface."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "website_ui",
    "name": "Website UI",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "connections",
    "description": "Owns the existing watched-website configuration UI template, visible website config UI paths, and website metadata seed extraction without owning website probe, profile persistence, metadata LLM suggestions, or runtime execution.",
    "templates": [
        "config_connections_websites.html",
    ],
    "routes": [
        "/config/connections/websites",
        "/config/connections/websites/save",
        "/config/connections/websites/suggest-metadata",
    ],
    "python": ["aria/modules/website_ui/links.py", "aria/modules/website_ui/metadata.py"],
    "tests": [
        "tests/test_module_registry_read_model.py",
        "tests/test_config_routes.py",
    ],
    "depends_on": [
        "config_ui",
        "connections",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/connections_ui_readonly/page_helpers.py",
        "aria/modules/connections_ui_readonly/detail_routes.py",
    ],
    "explicitly_excluded": [
        "fastapi_route_registration_from_manifest",
        "website_probe_behavior",
        "website_profile_persistence_behavior",
        "website_metadata_llm_suggestion_behavior",
        "connection_mutation_behavior",
        "runtime_execution",
        "routing_semantics",
        "auth_session_cookie_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-website-ui-readpoint-alpha696.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This module is a UI/readpoint boundary only; route decorators and handlers remain explicit in existing web modules.",
        "The broader connections and website flows still own profile persistence, probe behavior, metadata suggestions, and result summaries.",
    ],
}
