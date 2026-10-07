from __future__ import annotations

import importlib


def test_legacy_connection_status_modules_are_canonical_modules() -> None:
    legacy_health = importlib.import_module("aria.modules.connections_health_cache.health")
    canonical_health = importlib.import_module("aria.modules.connections_health_cache.health")
    legacy_runtime = importlib.import_module("aria.modules.connections_runtime_status.runtime")
    canonical_runtime = importlib.import_module("aria.modules.connections_runtime_status.runtime")

    assert legacy_health is canonical_health
    assert legacy_runtime is canonical_runtime


def test_legacy_connection_status_objects_are_canonical_objects() -> None:
    legacy_health = importlib.import_module("aria.modules.connections_health_cache.health")
    canonical_health = importlib.import_module("aria.modules.connections_health_cache.health")
    legacy_runtime = importlib.import_module("aria.modules.connections_runtime_status.runtime")
    canonical_runtime = importlib.import_module("aria.modules.connections_runtime_status.runtime")

    assert legacy_health.get_connection_health is canonical_health.get_connection_health
    assert legacy_health.record_connection_health is canonical_health.record_connection_health
    assert legacy_health.delete_connection_health is canonical_health.delete_connection_health
    assert legacy_runtime.build_connection_status_row is canonical_runtime.build_connection_status_row
    assert legacy_runtime.build_settings_connection_status_rows is canonical_runtime.build_settings_connection_status_rows
    assert legacy_runtime.test_connection is canonical_runtime.test_connection
