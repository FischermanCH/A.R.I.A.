from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.release_update.update_check", "aria.modules.release_update.update_check"),
    ("aria.modules.release_update.helper_client", "aria.modules.release_update.helper_client"),
)


def test_legacy_release_update_client_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_release_update_client_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.release_update.update_check": "get_update_status",
        "aria.modules.release_update.helper_client": "resolve_update_helper_config",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
