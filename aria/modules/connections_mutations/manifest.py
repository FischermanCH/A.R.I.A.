"""Declarative metadata for connection mutation composition boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_mutations",
    "name": "Connections Mutations",
    "parent": "connections",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns connection mutation route/composition metadata without changing or executing save, delete, import, probe, key, or runtime behavior.",
    "python": [
        "aria/modules/connections_mutations/admin_helpers.py",
        "aria/modules/connections_mutations/handlers.py",
        "aria/modules/connections_mutations/routes.py",
        "aria/modules/connections_mutations/support_helpers.py",
    ],
    "tests": [
        "tests/test_config_routes.py",
        "tests/test_connection_admin.py",
        "tests/test_connection_cleanup.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_profiles",
        "connections_runtime_status",
        "runtime_guardrails",
        "platform_primitives",
        "qdrant_gateway",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "profile_save_delete_or_import",
        "secret_material_access",
        "live_connection_probes",
        "ssh_key_generation_or_exchange",
        "rss_ping_or_opml_mutation",
        "qdrant_clear_or_reindex",
        "guardrail_policy_changes",
        "runtime_reload_or_execution",
        "route_registration_changes",
    ],
    "acceptance": ".codex/aria_acceptance/connections-mutations-composition-ownership-rail-alpha745.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Provider-specific callbacks remain injected by aria.modules.config_ui.routes and are not imported or generated from this manifest.",
        "Provider routes remain owned by their existing provider manifests.",
        "No mutation handler is invoked by this metadata-only slice.",
    ],
}
