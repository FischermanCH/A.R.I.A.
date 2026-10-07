"""Declarative metadata for system inventory indexing and administration."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "system_inventory",
    "name": "System Inventory",
    "parent": "ui_admin",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns deterministic inventory documents, fingerprints, index storage, and explicitly invoked inventory rebuild/status projection.",
    "python": [
        "aria/modules/system_inventory/index.py",
        "aria/modules/system_inventory/admin.py",
        "aria/modules/system_inventory/context_adapters.py",
        "aria/modules/system_inventory/managed_action_catalog.py",
    ],
    "tests": [
        "tests/test_inventory_index.py",
        "tests/test_system_inventory_diagnostics_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "action_contracts",
        "model_gateway_clients",
        "model_usage_observability",
        "qdrant_gateway",
        "connection_routing",
        "pipeline_contracts",
    ],
    "external_boundaries": [
        {
            "id": "meta_catalog_rebuild_bridge",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "automatic_or_productive_inventory_rebuild",
        "productive_qdrant_embedding_or_user_data_access",
        "routing_or_source_authority_changes",
        "runtime_dispatch_generation",
    ],
    "acceptance": ".codex/aria_acceptance/system-inventory-diagnostics-import-rail-alpha733.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "Importing the module does not build documents, create a client, inspect a store, or rebuild an index.",
        "The managed action catalog is retained locally without the deleted legacy routing ring.",
    ],
}
