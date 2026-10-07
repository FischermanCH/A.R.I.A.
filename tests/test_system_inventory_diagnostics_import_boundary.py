from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.system_inventory.index", "aria.modules.system_inventory.index"),
    ("aria.modules.system_inventory.admin", "aria.modules.system_inventory.admin"),
    ("aria.modules.system_diagnostics.qdrant_collection_classifier", "aria.modules.system_diagnostics.qdrant_collection_classifier"),
    ("aria.modules.system_diagnostics.qdrant_storage", "aria.modules.system_diagnostics.qdrant_storage"),
    ("aria.modules.runtime_diagnostics.runtime", "aria.modules.runtime_diagnostics.runtime"),
)


def test_legacy_system_inventory_and_diagnostics_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_system_inventory_and_diagnostics_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.system_inventory.index": "build_inventory_documents",
        "aria.modules.system_inventory.admin": "rebuild_inventory_index",
        "aria.modules.system_diagnostics.qdrant_collection_classifier": "classify_qdrant_collection",
        "aria.modules.system_diagnostics.qdrant_storage": "build_qdrant_storage_warning",
        "aria.modules.runtime_diagnostics.runtime": "build_runtime_diagnostics",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
