from __future__ import annotations

import importlib


def test_session_compression_legacy_path_is_canonical_module_identity() -> None:
    legacy = importlib.import_module("aria.modules.memory_session_compression.service")
    canonical = importlib.import_module("aria.modules.memory_session_compression.service")

    assert legacy is canonical
    assert legacy.SessionCompressionService is canonical.SessionCompressionService
