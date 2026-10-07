"""Declarative metadata for the config backup boundary."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "config_backup",
    "name": "Config Backup",
    "parent": "ops_config_backup",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "description": "Owns config-backup parsing, validation, snapshot/restore contracts and the protected backup surface without owning wider operations runtime controls.",
    "routes_prefixes": [
        "/config/backup",
    ],
    "routes": [
        "/config/backup",
    ],
    "api_routes": [
        "/config/backup/export",
        "/config/backup/import",
    ],
    "python": [
        "aria/modules/config_backup/backup.py",
    ],
    "templates": [
        "config_backup.html",
    ],
    "tests": [
        "tests/test_config_backup.py",
        "tests/test_config_backup_chat_history_storage_import_boundary.py",
        "tests/test_module_registry.py",
        "tests/test_module_registry_read_model.py",
    ],
    "depends_on": [
        "auth_ui",
        "config_ui",
        "configuration_foundations",
        "memory_export",
        "ops_config_backup",
        "recipe_store",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
        {
            "id": "filesystem.caller_supplied_paths",
            "category": "data_boundary",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "memory_export_behavior",
        "logs_cleanup_behavior",
        "factory_reset_behavior",
        "runtime_diagnostics_behavior",
        "service_restart_behavior",
        "memory_reindex_behavior",
        "qdrant_runtime_access",
        "docker_build_export",
        "productive_config_secret_user_recipe_or_prompt_access",
        "productive_backup_or_restore_execution",
    ],
    "acceptance": ".codex/aria_acceptance/config-backup-chat-history-storage-import-rail-alpha734.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Route registration remains in existing FastAPI code and is not generated from this manifest.",
        "Memory export is linked from the backup page but remains outside this submodule.",
    ],
}
