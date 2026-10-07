"""Declarative metadata for memory admin UI templates and visible GET routes."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "memory_admin_ui",
    "name": "Memory Admin UI",
    "parent": "memory",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": (
        "Owns existing memory administration route composition, UI templates, and visible route metadata "
        "without changing Qdrant, user-memory, import/export, recall, learning, or mutation behavior."
    ),
    "routes": [
        "/memories",
        "/memories/import",
        "/memories/create",
        "/memories/maintenance",
        "/memories/maintenance/cleanup-legacy-learning",
        "/memories/maintenance/reset-learning-suggestions",
        "/memories/config",
        "/config/memory",
        "/memories/auto-memory",
        "/memories/auto-memory/claim-action",
        "/memories/auto-memory/correct-claim",
        "/memories/auto-memory/delete-claim",
        "/memories/auto-memory/delete-point",
        "/memories/browser/delete-document",
        "/memories/browser/delete-point",
        "/memories/config/backend-save",
        "/memories/config/compress",
        "/memories/config/compression-save",
        "/memories/config/create",
        "/memories/config/select",
        "/memories/upload",
    ],
    "templates": [
        "memories_overview.html",
        "memories_import.html",
        "memories_create.html",
        "memories_maintenance.html",
        "config_memory.html",
        "memories_auto_memory.html",
    ],
    "python": [
        "aria/modules/memory_admin_ui/routes.py",
    ],
    "tests": [
        "tests/test_memories_routes.py",
        "tests/test_module_registry_read_model.py",
    ],
    "depends_on": [
        "document_ingest",
        "integration_support",
        "memory",
        "memory_export",
        "navigation_shell",
        "ops_config_backup",
        "pipeline_orchestrator",
        "platform_primitives",
        "system_diagnostics",
        "system_inventory",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "qdrant_runtime_access",
        "user_memory_read",
        "user_memory_write",
        "memory_export_payload_behavior",
        "memory_import_behavior",
        "memory_create_behavior",
        "memory_delete_behavior",
        "memory_compression_behavior",
        "memory_reindex_behavior",
        "learning_worker_behavior",
        "auto_memory_behavior",
        "personal_claim_mutation_behavior",
        "route_registration_from_manifest",
    ],
    "acceptance": ".codex/aria_acceptance/memory-map-legacy-route-consolidation-alpha699.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Route handlers remain registered explicitly by aria.main with unchanged dependency injection.",
        "The ownership move executes no POST action and performs no Qdrant-backed data access.",
    ],
}
