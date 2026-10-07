"""Declarative metadata for the connections catalog submodule."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_catalog",
    "name": "Connections Catalog",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "connections",
    "description": "Owns read-only connection kind normalization, catalog rows, field specs, menu/status/overview metadata, template-name mapping, routing specs, and payload sanitizing.",
    "routes_prefixes": [],
    "python": [
        "aria/modules/connections_catalog/catalog.py",
    ],
    "templates": [],
    "tests": [
        "tests/test_connection_catalog.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "profile_persistence_behavior",
        "secret_material_access",
        "connection_runtime_execution",
        "live_health_probe_behavior",
        "route_registration",
        "template_rendering",
        "routing_authority_behavior",
        "action_execution_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/connections-provider-import-train-alpha727.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The catalog implementation and product consumers use aria.modules.connections_catalog.catalog.",
        "This catalog remains read-only and does not generate runtime or dispatch behavior.",
    ],
}
