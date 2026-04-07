from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.embedding_client import EmbeddingClient
from aria.core.llm_client import LLMClient
from aria.core.usage_meter import UsageMeter


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

    monkeypatch.setattr("aria.core.llm_client.acompletion", _fake_completion)

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

    monkeypatch.setattr("aria.core.embedding_client.aembedding", _fake_embedding)

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
