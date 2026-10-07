"""Declarative metadata for bounded system and Qdrant diagnostics."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "system_diagnostics",
    "name": "System Diagnostics",
    "parent": "ui_admin",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns pure Qdrant collection classification and caller-supplied local storage diagnostics.",
    "python": [
        "aria/modules/system_diagnostics/qdrant_collection_classifier.py",
        "aria/modules/system_diagnostics/qdrant_storage.py",
    ],
    "tests": [
        "tests/test_qdrant_collection_classifier.py",
        "tests/test_qdrant_storage_diagnostics.py",
        "tests/test_system_inventory_diagnostics_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [],
    "explicitly_excluded": [
        "automatic_or_productive_runtime_probes",
        "productive_qdrant_or_filesystem_access",
        "qdrant_collection_or_storage_mutation",
        "routing_source_confirmation_or_guardrail_changes",
    ],
    "acceptance": ".codex/aria_acceptance/system-inventory-diagnostics-import-rail-alpha733.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "Importing the module does not inspect storage, create clients, probe services, or mutate Qdrant.",
    ],
}
