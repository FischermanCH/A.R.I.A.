from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS


class FakeTracker:
    def __init__(self, log_file: str, *, enabled: bool) -> None:
        self.log_file = log_file
        self.enabled = enabled

    async def prune_old_entries(self, retention_days: int) -> dict[str, int]:
        assert retention_days == 17
        return {"removed": 4}


class FakeAuditLog:
    def prune_old_entries(self, retention_days: int) -> dict[str, int]:
        assert retention_days == 17
        return {"removed": 3}


def _settings(*, enabled: bool, backend: str = "qdrant") -> SimpleNamespace:
    return SimpleNamespace(
        token_tracking=SimpleNamespace(log_file="synthetic.jsonl", enabled=True, retention_days=17),
        memory=SimpleNamespace(
            enabled=enabled,
            backend=backend,
            collections=SimpleNamespace(
                sessions=SimpleNamespace(compress_after_days=8, monthly_after_days=31),
            ),
        ),
        embeddings=SimpleNamespace(),
        auto_memory=SimpleNamespace(learning_governor=SimpleNamespace()),
    )


def test_maintenance_legacy_module_is_identity_alias() -> None:
    assert importlib.import_module("aria.modules.ops_config_backup.maintenance") is importlib.import_module(
        "aria.modules.ops_config_backup.maintenance"
    )


def test_disabled_maintenance_uses_only_injected_pruners(monkeypatch) -> None:
    maintenance = importlib.import_module("aria.modules.ops_config_backup.maintenance")
    tracker_module = importlib.import_module("aria.modules.model_usage_observability.token_tracker")
    monkeypatch.setattr(maintenance, "load_settings", lambda _path: _settings(enabled=False))
    monkeypatch.setattr(maintenance, "GLOBAL_LLM_AUDIT_LOG", FakeAuditLog())
    monkeypatch.setattr(tracker_module, "TokenTracker", FakeTracker)
    monkeypatch.setattr(
        maintenance,
        "MemorySkill",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("MemorySkill must remain skipped")),
    )

    stats = asyncio.run(maintenance.run_memory_maintenance("synthetic.yaml"))

    assert stats == {
        "users": 0,
        "compressed_week": 0,
        "compressed_month": 0,
        "collections_removed": 0,
        "document_meta_documents": 0,
        "token_log_removed": 4,
        "llm_audit_removed": 3,
    }


def test_maintenance_manifest_owns_canonical_implementation() -> None:
    assert "aria/modules/ops_config_backup/maintenance.py" in MODULE_MANIFESTS["ops_config_backup"]["python"]


def test_qdrant_maintenance_uses_only_injected_callbacks(monkeypatch) -> None:
    maintenance = importlib.import_module("aria.modules.ops_config_backup.maintenance")
    tracker_module = importlib.import_module("aria.modules.model_usage_observability.token_tracker")
    calls: list[object] = []

    class FakeMemorySkill:
        def __init__(self, **kwargs) -> None:
            calls.append(("init", tuple(sorted(kwargs))))

        async def compress_all_users(self, *, compress_after_days: int, monthly_after_days: int):
            calls.append(("compress", compress_after_days, monthly_after_days))
            return {"users": 2, "compressed_week": 5, "compressed_month": 1, "collections_removed": 6}

        async def rebuild_document_meta_catalogs_for_known_users(self):
            calls.append("document_meta")
            return {"documents": 9}

    monkeypatch.setattr(maintenance, "load_settings", lambda _path: _settings(enabled=True))
    monkeypatch.setattr(maintenance, "GLOBAL_LLM_AUDIT_LOG", FakeAuditLog())
    monkeypatch.setattr(maintenance, "UsageMeter", lambda _settings: object())
    monkeypatch.setattr(maintenance, "MemorySkill", FakeMemorySkill)
    monkeypatch.setattr(tracker_module, "TokenTracker", FakeTracker)

    stats = asyncio.run(maintenance.run_memory_maintenance("synthetic.yaml"))

    assert calls == [
        ("init", ("embeddings", "memory", "usage_meter")),
        ("compress", 8, 31),
        "document_meta",
    ]
    assert stats == {
        "users": 2,
        "compressed_week": 5,
        "compressed_month": 1,
        "collections_removed": 6,
        "document_meta_documents": 9,
        "token_log_removed": 4,
        "llm_audit_removed": 3,
    }


def test_production_code_has_no_legacy_maintenance_import() -> None:
    offenders = []
    alias = Path("aria/core/maintenance.py")
    for path in sorted(Path("aria").rglob("*.py")):
        if path == alias:
            continue
        source = path.read_text(encoding="utf-8")
        if "from aria.modules.ops_config_backup.maintenance" in source or "import aria.modules.ops_config_backup.maintenance" in source:
            offenders.append(str(path))
    assert offenders == []
