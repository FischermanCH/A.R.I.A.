"""Declarative metadata for the existing Google Calendar config UI surface."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "google_calendar_ui",
    "name": "Google Calendar UI",
    "status": "surface_contract_active",
    "lifecycle": "contract_only",
    "risk": "medium",
    "parent": "connections",
    "description": "Owns the existing Google Calendar configuration UI template and visible save path without owning iCal fetches, OAuth/provider behavior, profile persistence, secure-store behavior, or runtime execution.",
    "templates": [
        "config_connections_google_calendar.html",
    ],
    "routes": [
        "/config/connections/google-calendar",
        "/config/connections/google-calendar/save",
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
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/connections_ui_readonly/page_helpers.py",
        "aria/modules/connections_ui_readonly/detail_routes.py",
    ],
    "explicitly_excluded": [
        "fastapi_route_registration_from_manifest",
        "google_calendar_ical_fetch_behavior",
        "google_calendar_oauth_or_provider_behavior",
        "google_calendar_profile_persistence_behavior",
        "secure_store_behavior",
        "connection_mutation_behavior",
        "runtime_execution",
        "routing_semantics",
        "auth_session_cookie_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-critical-config-ui-readpoints-alpha698.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
