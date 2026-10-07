"""Declarative metadata for broad operations config surfaces."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "ops_config_backup",
    "name": "Ops Config Backup",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns selected operations config pages, runtime diagnostics metadata, maintenance and secure migration helpers until narrower ops modules are proven.",
    "routes_prefixes": [
        "/config/operations",
        "/config/logs",
    ],
    "routes": [
        "/config/operations",
        "/config/operations/service-restart",
        "/config/logs",
        "/config/logs/save",
        "/config/logs/cleanup",
        "/config/logs/reset",
        "/config/logs/factory-reset",
        "/memories/reindex/run",
        "/memories/reindex/save",
    ],
    "python": [
        "aria/modules/ops_config_backup/maintenance.py",
        "aria/modules/ops_config_backup/detail_routes.py",
    ],
    "templates": [
        "config_operations.html",
        "config_logs.html",
    ],
    "tests": [
        "tests/test_config_backup.py",
        "tests/test_maintenance_kernel_ownership_import_boundary.py",
        "tests/test_runtime_diagnostics.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "auth_ui",
        "config_ui",
        "configuration_foundations",
        "memory",
        "model_usage_observability",
        "runtime_diagnostics",
        "security_storage",
        "system_inventory",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "config_backup_submodule",
        "release_update_behavior",
        "service_restart_behavior",
        "memory_reindex_behavior",
        "qdrant_runtime_access",
        "docker_build_export",
        "user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/config-ui-composition-ownership-rail-alpha745.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Config backup was split into the narrower config_backup submodule after alpha691.",
        "This module may later split into config_backup, ops_diagnostics, and maintenance.",
        "Existing route wiring remains in aria/main.py through config route registration.",
        "This manifest is descriptive only and must not be treated as backup/diagnostics behavior acceptance.",
    ],
}
