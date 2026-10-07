"""Declarative metadata for the memory export surface."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "memory_export",
    "name": "Memory Export",
    "parent": "memory",
    "status": "route_contract_active",
    "lifecycle": "contract_only",
    "risk": "medium_high",
    "description": "Owns the memory JSON export route metadata and its config-backup page link without changing export payload, Qdrant access, or user-memory behavior.",
    "routes": [
        "/memories/export",
    ],
    "api_routes": [
        "/memories/export",
    ],
    "python": [
    ],
    "templates": [],
    "tests": [
        "tests/test_config_backup.py",
        "tests/test_module_registry.py",
        "tests/test_module_registry_read_model.py",
    ],
    "depends_on": [
        "auth_ui",
        "configuration_foundations",
        "memory",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "memory_export_payload_behavior",
        "memory_export_filename_behavior",
        "memory_export_content_disposition_behavior",
        "qdrant_runtime_access",
        "user_memory_read",
        "user_memory_write",
        "memory_import_behavior",
        "memory_restore_behavior",
        "memory_delete_behavior",
        "docker_build_export",
        "user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-memory-export-readpoint-alpha692.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This slice only makes the config-backup page read the existing /memories/export route path through module_route_path('memory_export', ...).",
        "The live alpha691 readability observation for downloaded memory JSON remains an open product finding; no behavior is accepted as fixed here.",
        "Route registration and export response construction remain in aria/web/memories_routes.py.",
        "The config_backup.html template is owned by config_backup; memory_export owns only its linked route metadata.",
        "The consuming config_backup page depends on memory_export; memory_export does not depend on its consumer.",
    ],
}
