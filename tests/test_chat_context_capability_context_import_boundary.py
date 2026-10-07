from __future__ import annotations

import importlib


def test_capability_context_core_path_is_identity_alias() -> None:
    pairs = (
        ("aria.modules.capability_context.store", "aria.modules.capability_context.store"),
    )

    for legacy_name, canonical_name in pairs:
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)

        assert legacy is canonical
