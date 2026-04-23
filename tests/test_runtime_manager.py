from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import asyncio

from aria.core.capability_context import CapabilityContextStore
from aria.web.runtime_manager import RuntimeBundle
from aria.web.runtime_manager import RuntimeManager
import aria.web.runtime_manager as runtime_manager_mod


class _DummyRuntimeManager(RuntimeManager):
    def __init__(self, **kwargs) -> None:
        self.built_settings: list[object] = []
        super().__init__(**kwargs)

    def _build_runtime_bundle(self, runtime_settings) -> RuntimeBundle:  # type: ignore[override]
        self.built_settings.append(runtime_settings)
        marker = object()
        return RuntimeBundle(
            settings=runtime_settings,
            prompt_loader=marker,
            usage_meter=marker,
            llm_client=marker,
            pipeline=marker,
        )


def test_runtime_manager_reload_runtime_rebuilds_bundle_and_resets_diagnostics(tmp_path: Path, monkeypatch) -> None:
    initial_settings = SimpleNamespace(name="initial")
    updated_settings = SimpleNamespace(name="updated")
    manager = _DummyRuntimeManager(
        base_dir=tmp_path,
        config_path=tmp_path / "config.yaml",
        initial_settings=initial_settings,
        capability_context_store=CapabilityContextStore(tmp_path / "capability_context.json"),
    )
    manager.set_startup_diagnostics({"status": "ok", "checked_at": "2026-04-22T12:00:00Z", "checks": [{"id": "qdrant"}]})
    monkeypatch.setattr(runtime_manager_mod, "load_settings", lambda _path: updated_settings)

    result = manager.reload_runtime()

    assert result is updated_settings
    assert manager.get_settings() is updated_settings
    assert manager.built_settings == [initial_settings, updated_settings]
    assert manager.get_startup_diagnostics() == {"status": "warn", "checked_at": "", "checks": []}


def test_runtime_manager_reset_startup_diagnostics_returns_empty_snapshot(tmp_path: Path) -> None:
    manager = _DummyRuntimeManager(
        base_dir=tmp_path,
        config_path=tmp_path / "config.yaml",
        initial_settings=SimpleNamespace(name="initial"),
        capability_context_store=CapabilityContextStore(tmp_path / "capability_context.json"),
    )
    manager.set_startup_diagnostics({"status": "error", "checked_at": "now", "checks": [{"id": "llm"}]})

    snapshot = manager.reset_startup_diagnostics()

    assert snapshot == {"status": "warn", "checked_at": "", "checks": []}
    assert manager.get_startup_diagnostics() == snapshot


def test_runtime_manager_get_or_refresh_startup_diagnostics_reuses_cached_snapshot(tmp_path: Path) -> None:
    manager = _DummyRuntimeManager(
        base_dir=tmp_path,
        config_path=tmp_path / "config.yaml",
        initial_settings=SimpleNamespace(name="initial"),
        capability_context_store=CapabilityContextStore(tmp_path / "capability_context.json"),
    )
    cached = {"status": "ok", "checked_at": "2026-04-22T12:00:00Z", "checks": [{"id": "qdrant"}]}
    manager.set_startup_diagnostics(cached)
    refresh_calls = 0

    async def _refresher() -> dict[str, object]:
        nonlocal refresh_calls
        refresh_calls += 1
        return {"status": "warn", "checked_at": "new", "checks": []}

    snapshot = asyncio.run(manager.get_or_refresh_startup_diagnostics(_refresher))

    assert snapshot == cached
    assert refresh_calls == 0
