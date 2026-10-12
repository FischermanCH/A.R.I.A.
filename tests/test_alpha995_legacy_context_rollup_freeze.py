from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import (
    EmbeddingsConfig,
    MemoryConfig,
    Settings,
    load_settings,
)
from aria.modules.memory_learning_bridge.skill import MemorySkill
from aria.modules.model_usage_observability.usage_meter import UsageMeter


ROOT = Path(__file__).resolve().parents[1]


def test_alpha995_release_metadata_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in (
        ROOT / "aria/modules/release_update/release_meta.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").startswith(
        "# Changelog\n\n## 0.1.0-alpha1007"
    )
    assert "public release remains `0.1.0-alpha983`" in (
        ROOT / "CHANGELOG.md"
    ).read_text(encoding="utf-8")


def test_legacy_context_rollup_writers_and_module_are_retired() -> None:
    main_source = (ROOT / "aria/main.py").read_text(encoding="utf-8")
    maintenance_source = (
        ROOT / "aria/modules/ops_config_backup/maintenance.py"
    ).read_text(encoding="utf-8")
    skill_source = (
        ROOT / "aria/modules/memory_learning_bridge/skill.py"
    ).read_text(encoding="utf-8")
    registry_source = (ROOT / "aria/modules/registry.py").read_text(encoding="utf-8")

    assert "compress_all_users" not in main_source
    assert "compress_all_users" not in maintenance_source
    assert "compress_old_sessions" not in skill_source
    assert 'action == "compress_sessions"' not in skill_source
    assert "memory_session_compression" not in registry_source
    assert not (ROOT / "aria/modules/memory_session_compression/service.py").exists()
    assert not (ROOT / "aria/modules/memory_session_compression/manifest.py").exists()


def test_legacy_context_config_keys_are_ignored_with_log_note(
    tmp_path: Path, caplog,
) -> None:  # noqa: ANN001
    caplog.set_level(logging.INFO)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
llm:
  model: fake/model
memory:
  compression_summary_prompt: prompts/recipes/memory_compress.md
  collections:
    sessions:
      prefix: aria_sessions
      weight: 0.5
      top_k: 2
      time_decay: true
      archive_after_days: 90
      compress_after_days: 7
      monthly_after_days: 30
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert not hasattr(settings.memory, "compression_summary_prompt")
    assert not hasattr(settings.memory.collections.sessions, "archive_after_days")
    assert not hasattr(settings.memory.collections.sessions, "compress_after_days")
    assert not hasattr(settings.memory.collections.sessions, "monthly_after_days")
    assert "retired legacy context-rollup settings" in caplog.text.lower()


def test_recall_targets_keep_existing_sessions_and_context_dimension_variants_only() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(qdrant_url="http://unused:6333"),
        embeddings=EmbeddingsConfig(model="fake"),
    )
    existing_session = "aria_sessions_neo_250101"
    context_dimension = "aria_context-mem_neo_dim_3"

    async def collection_names() -> list[str]:
        return [existing_session, context_dimension]

    skill._list_collection_names = collection_names  # type: ignore[method-assign]
    targets = asyncio.run(skill._build_recall_targets("neo"))
    names = {str(target["collection"]) for target in targets}
    generated_today = f"aria_sessions_neo_{datetime.now().strftime('%y%m%d')}"

    assert existing_session in names
    assert context_dimension in names
    assert generated_today not in names


def test_legacy_rollup_count_is_read_only_and_user_scoped() -> None:
    from aria.modules.memory_admin_ui import routes

    calls: list[dict[str, object]] = []

    class FakeMemorySkill:
        async def list_memories_global(self, **kwargs):  # noqa: ANN003, ANN202
            calls.append(dict(kwargs))
            return [
                {
                    "id": "week-1",
                    "collection": "aria_context-mem_neo",
                    "type": "knowledge",
                    "source": "compression",
                    "rollup_level": "week",
                    "rollup_bucket": "2026-W01",
                },
                {
                    "id": "month-1",
                    "collection": "aria_context-mem_neo_dim_3",
                    "type": "knowledge",
                    "source": "compression",
                    "rollup_level": "month",
                    "rollup_bucket": "2026-01",
                },
                {
                    "id": "knowledge-1",
                    "collection": "aria_knowledge_neo",
                    "type": "knowledge",
                    "source": "manual",
                },
            ]

    count = asyncio.run(
        routes._count_legacy_context_rollups(FakeMemorySkill(), user_id="neo")
    )

    assert count == 2
    assert calls == [
        {
            "user_id": "neo",
            "type_filter": "knowledge",
            "limit": 10000,
        }
    ]


def test_legacy_rollup_post_routes_are_passive_redirects() -> None:
    source = (ROOT / "aria/modules/memory_admin_ui/routes.py").read_text(encoding="utf-8")

    assert '@app.post("/memories/maintenance")' in source
    assert '@app.post("/memories/config/compress")' in source
    assert '@app.post("/config/memory/compress")' in source
    assert '@app.post("/memories/config/compression-save")' in source
    assert '@app.post("/config/memory/compression-save")' in source
    assert "compress_old_sessions" not in source
    assert '"action": "compress_sessions"' not in source
    assert "write_raw_config(raw)" not in source[source.index('@app.post("/memories/config/compression-save")'):]


def test_memory_skill_embedding_call_is_metered_as_embedding(
    monkeypatch, tmp_path: Path,
) -> None:  # noqa: ANN001
    async def fake_embedding(**_kwargs):  # noqa: ANN003, ANN202
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage=SimpleNamespace(
                prompt_tokens=9, completion_tokens=0, total_tokens=9,
            ),
        )

    monkeypatch.setattr(
        "aria.modules.model_gateway_clients.embedding._aembedding", fake_embedding,
    )
    log_path = tmp_path / "tokens.jsonl"
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake/model"},
            "embeddings": {"model": "fake-embedding"},
            "token_tracking": {"enabled": True, "log_file": str(log_path)},
            "pricing": {"enabled": False},
        }
    )
    skill = MemorySkill(
        memory=settings.memory,
        embeddings=settings.embeddings,
        usage_meter=UsageMeter(settings),
    )

    vector, usage = asyncio.run(
        skill._embed(
            "synthetic memory query",
            source="memory_recall",
            operation="recall_query",
            user_id="neo",
        )
    )

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert vector == [0.1, 0.2, 0.3]
    assert usage["total_tokens"] == 9
    assert len(rows) == 1
    assert rows[0]["source"] == "memory_recall"
    assert rows[0]["embedding_calls"] == 1
    assert rows[0]["embedding_total_tokens"] == 9
    assert rows[0]["total_tokens"] == 0
