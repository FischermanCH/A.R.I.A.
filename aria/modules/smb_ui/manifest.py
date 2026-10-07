"""Declarative metadata for the existing SMB config UI surface."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "smb_ui",
    "name": "SMB UI",
    "status": "surface_contract_active",
    "lifecycle": "contract_only",
    "risk": "medium",
    "parent": "connections",
    "description": "Owns the existing SMB configuration UI template and visible save path without owning share probes, guardrail behavior, profile persistence, secure-store behavior, or runtime execution.",
    "templates": [
        "config_connections_smb.html",
    ],
    "routes": [
        "/config/connections/smb",
        "/config/connections/smb/save",
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
        "smb_probe_behavior",
        "smb_profile_persistence_behavior",
        "secure_store_behavior",
        "guardrail_behavior",
        "connection_mutation_behavior",
        "runtime_execution",
        "routing_semantics",
        "auth_session_cookie_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-simple-connection-ui-readpoints-alpha697.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
