"""Declarative metadata for explicitly invoked bounded runtime probes."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "runtime_diagnostics",
    "name": "Runtime Diagnostics",
    "parent": "ops_config_backup",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns explicitly invoked runtime diagnostic payloads while client creation and probe execution remain caller controlled.",
    "python": [
        "aria/modules/runtime_diagnostics/runtime.py",
    ],
    "tests": [
        "tests/test_runtime_diagnostics.py",
        "tests/test_system_inventory_diagnostics_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "configuration_foundations",
        "model_gateway_clients",
        "model_usage_observability",
        "platform_primitives",
        "system_diagnostics",
        "qdrant_gateway",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "automatic_or_productive_runtime_probes",
        "productive_qdrant_embedding_llm_or_filesystem_access",
        "service_restart_or_runtime_mutation",
        "routing_source_confirmation_or_guardrail_changes",
    ],
    "acceptance": ".codex/aria_acceptance/system-inventory-diagnostics-import-rail-alpha733.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Importing the module does not create clients, probe services, inspect storage, or mutate runtime state.",
    ],
}
