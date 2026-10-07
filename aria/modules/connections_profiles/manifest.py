"""Declarative metadata for connection profile persistence boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_profiles",
    "name": "Connections Profiles",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "connections",
    "description": "Owns connection profile CRUD metadata, ref sanitizing, raw config read/write helpers, secure-store binding, inbound webhook token provisioning, and admin error text without changing persistence behavior.",
    "python": [
        "aria/modules/connections_profiles/admin.py",
    ],
    "routes": [
        "/config/connections/delete",
        "/config/connections/import-sample",
    ],
    "tests": [
        "tests/test_connection_admin.py",
        "tests/test_connection_cleanup.py",
        "tests/test_connections_profile_admin_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_runtime_status",
        "configuration_foundations",
        "security_storage",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "profile_persistence_behavior",
        "raw_config_write_behavior",
        "secure_store_behavior",
        "secret_material_access",
        "inbound_webhook_token_semantics",
        "connection_health_delete_behavior",
        "runtime_reload_behavior",
        "route_registration",
        "chat_pending_flow_behavior",
        "runtime_execution",
    ],
    "acceptance": ".codex/aria_acceptance/connections-profile-admin-ownership-rail-alpha739.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Focused tests use tmp_path and FakeStore only; no live config or user secrets are accessed.",
        "The alpha739 ownership rail changes no profile CRUD behavior; future behavior work still needs a separate acceptance matrix because this boundary touches config, secure store, health cache, and chat/admin flows.",
    ],
}
