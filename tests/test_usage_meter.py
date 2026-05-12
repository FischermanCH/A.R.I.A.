from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.config import EmbeddingsConfig
from aria.core.config import MemoryConfig
from aria.core.embedding_client import EmbeddingClient
from aria.core.llm_client import LLMClient
from aria.core.usage_meter import UsageMeter
from aria.skills.memory import MemorySkill


def _settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "llm": {"model": "gpt-5.1", "api_key": "test"},
            "embeddings": {"model": "text-embedding-3-small", "api_key": "test"},
            "token_tracking": {
                "enabled": True,
                "log_file": str(tmp_path / "tokens.jsonl"),
            },
            "pricing": {
                "enabled": False,
                "chat_models": {},
                "embedding_models": {},
            },
        }
    )


def _read_log_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_llm_client_logs_direct_calls_via_usage_meter(monkeypatch, tmp_path: Path) -> None:
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    monkeypatch.setattr("aria.core.llm_client._acompletion", _fake_completion)

    settings = _settings(tmp_path)
    meter = UsageMeter(settings)
    client = LLMClient(settings.llm, usage_meter=meter)

    asyncio.run(
        client.chat(
            [{"role": "user", "content": "Hallo"}],
            source="rss_metadata",
            operation="suggest_metadata",
            user_id="neo",
        )
    )

    rows = _read_log_rows(tmp_path / "tokens.jsonl")
    assert len(rows) == 1
    assert rows[0]["source"] == "rss_metadata"
    assert rows[0]["user_id"] == "neo"
    assert rows[0]["chat_model"] == "gpt-5.1"
    assert rows[0]["total_tokens"] == 15
    assert rows[0]["embedding_total_tokens"] == 0


def test_embedding_client_logs_direct_calls_via_usage_meter(monkeypatch, tmp_path: Path) -> None:
    async def _fake_embedding(**_kwargs):
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage=SimpleNamespace(prompt_tokens=6, completion_tokens=0, total_tokens=6),
        )

    monkeypatch.setattr("aria.core.embedding_client._aembedding", _fake_embedding)

    settings = _settings(tmp_path)
    meter = UsageMeter(settings)
    client = EmbeddingClient(settings.embeddings, usage_meter=meter)

    asyncio.run(
        client.embed(
            ["healthcheck"],
            source="rag_ingest",
            operation="document_chunk",
            user_id="neo",
        )
    )

    rows = _read_log_rows(tmp_path / "tokens.jsonl")
    assert len(rows) == 1
    assert rows[0]["source"] == "rag_ingest"
    assert rows[0]["user_id"] == "neo"
    assert rows[0]["chat_model"] == ""
    assert rows[0]["embedding_model"] == "openai/text-embedding-3-small"
    assert rows[0]["total_tokens"] == 0
    assert rows[0]["embedding_total_tokens"] == 6
    assert rows[0]["embedding_calls"] == 1


def test_memory_skill_uses_shared_usage_meter_for_default_embedding_client(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    meter = UsageMeter(settings)

    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory"),
        embeddings=EmbeddingsConfig(model="text-embedding-3-small"),
        usage_meter=meter,
    )

    assert skill.embedding_client.usage_meter is meter


def test_usage_meter_scope_aggregates_without_immediate_log(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    meter = UsageMeter(settings)

    async def _run() -> dict[str, object]:
        with meter.scope(request_id="req-1", user_id="neo", source="web", router_level=2) as scope:
            await meter.record_llm_call(
                model="gpt-5.1",
                usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                source="rss_metadata",
                operation="suggest_metadata",
                user_id="neo",
            )
            await meter.record_embedding_call(
                model="openai/text-embedding-3-small",
                usage={"prompt_tokens": 7, "completion_tokens": 0, "total_tokens": 7},
                source="rag_ingest",
                operation="document_chunk",
                user_id="neo",
            )
            return meter.snapshot_scope(scope)

    snapshot = asyncio.run(_run())

    assert _read_log_rows(tmp_path / "tokens.jsonl") == []
    assert snapshot["usage"]["total_tokens"] == 5
    assert snapshot["embedding_usage"]["total_tokens"] == 7
    assert snapshot["embedding_usage"]["calls"] == 1


def test_usage_meter_prices_known_claude_and_openai_embedding_models(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.pricing.enabled = True
    meter = UsageMeter(settings)

    async def _run() -> tuple[float | None, float | None]:
        chat_cost = await meter.record_llm_call(
            model="anthropic/claude-sonnet-4-5",
            usage={"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
            source="test",
            operation="chat",
        )
        embedding_cost = await meter.record_embedding_call(
            model="openai/text-embedding-3-small",
            usage={"prompt_tokens": 500, "completion_tokens": 0, "total_tokens": 500},
            source="test",
            operation="embed",
        )
        return chat_cost, embedding_cost

    chat_cost, embedding_cost = asyncio.run(_run())

    assert chat_cost is not None
    assert chat_cost > 0.0
    assert embedding_cost is not None
    assert embedding_cost > 0.0
    rows = _read_log_rows(tmp_path / "tokens.jsonl")
    assert rows[0]["chat_model"] == "anthropic/claude-sonnet-4-5"
    assert rows[0]["total_cost_usd"] == chat_cost
    assert rows[1]["embedding_model"] == "openai/text-embedding-3-small"
    assert rows[1]["total_cost_usd"] == embedding_cost


def test_usage_meter_prices_configured_embedding_model_alias(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.pricing.enabled = True
    settings.pricing.model_aliases = {"company/fast-embed": "openai/text-embedding-3-small"}
    meter = UsageMeter(settings)

    async def _run() -> float | None:
        return await meter.record_embedding_call(
            model="company/fast-embed",
            usage={"prompt_tokens": 500, "completion_tokens": 0, "total_tokens": 500},
            source="test",
            operation="embed",
        )

    embedding_cost = asyncio.run(_run())

    assert embedding_cost is not None
    assert embedding_cost > 0.0
    rows = _read_log_rows(tmp_path / "tokens.jsonl")
    assert rows[0]["embedding_model"] == "company/fast-embed"
    assert rows[0]["total_cost_usd"] == embedding_cost
