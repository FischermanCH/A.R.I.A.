from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import Settings
from aria.modules.configuration_foundations.config import ChatPricingModelConfig
from aria.modules.configuration_foundations.config import EmbeddingsConfig
from aria.modules.configuration_foundations.config import MemoryConfig
from aria.modules.model_gateway_clients.embedding import EmbeddingClient
from aria.modules.action_draft_policy.guardrail_drafts import build_guardrail_draft_context, suggest_guardrail_with_llm
from aria.modules.model_gateway_clients.llm import LLMClient
from aria.modules.model_usage_observability.usage_meter import UsageMeter
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

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

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


def test_guardrail_draft_llm_call_is_metered(monkeypatch, tmp_path: Path) -> None:
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"ref":"no-sudo","kind":"ssh_command","title":"No sudo",'
                            '"description":"Blocks sudo.","allow_terms":[],"deny_terms":["sudo"],'
                            '"scope_summary":"SSH only","review_notes":[],"examples":[],"confidence":0.8}'
                        )
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=42, completion_tokens=21, total_tokens=63),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    settings = _settings(tmp_path)
    meter = UsageMeter(settings)
    client = LLMClient(settings.llm, usage_meter=meter)

    asyncio.run(
        suggest_guardrail_with_llm(
            llm_client=client,
            instruction="Keine sudo Befehle auf Ubuntu.",
            draft_context=build_guardrail_draft_context({}, guardrail_kind="ssh_command"),
            user_id="neo",
            request_id="guardrail-test",
        )
    )

    rows = _read_log_rows(tmp_path / "tokens.jsonl")
    assert len(rows) == 1
    assert rows[0]["source"] == "guardrail_draft"
    assert rows[0]["intents"] == ["llm:draft_ssh_command"]
    assert rows[0]["user_id"] == "neo"
    assert rows[0]["request_id"] == "guardrail-test"
    assert rows[0]["total_tokens"] == 63


def test_embedding_client_logs_direct_calls_via_usage_meter(monkeypatch, tmp_path: Path) -> None:
    async def _fake_embedding(**_kwargs):
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage=SimpleNamespace(prompt_tokens=6, completion_tokens=0, total_tokens=6),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.embedding._aembedding", _fake_embedding)

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


def test_web_llm_usage_tracks_role_search_count_and_tool_cost(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.pricing.enabled = True
    settings.pricing.chat_models["openai/gpt-5.6-luna"] = ChatPricingModelConfig(
        input_per_million=0.2,
        output_per_million=1.2,
        native_web_search_per_call=0.01,
    )
    meter = UsageMeter(settings)

    cost = asyncio.run(
        meter.record_web_llm_call(
            model="openai/gpt-5.6-luna",
            usage={"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
            native_search_uses=2,
            source="web",
            operation="native_web_answer",
            user_id="neo",
            request_id="web-1",
            duration_ms=8000,
        )
    )

    assert cost == 0.02032
    rows = _read_log_rows(tmp_path / "tokens.jsonl")
    assert len(rows) == 1
    assert rows[0]["llm_role"] == "web"
    assert rows[0]["native_web_search_uses"] == 2
    assert rows[0]["native_web_search_cost_usd"] == 0.02


def test_web_llm_scope_flushes_exactly_once_with_role_and_search_receipt(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.pricing.enabled = True
    settings.pricing.chat_models["openai/gpt-5.6-luna"] = ChatPricingModelConfig(
        input_per_million=0.2,
        output_per_million=1.2,
        native_web_search_per_call=0.01,
    )
    meter = UsageMeter(settings)

    async def _run() -> tuple[bool, bool]:
        with meter.scope(request_id="web-scope", user_id="neo", source="web_chat", router_level=0):
            await meter.record_web_llm_call(
                model="openai/gpt-5.6-luna",
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                native_search_uses=2,
            )
            first = await meter.flush_current_scope(
                intents=["web_search"],
                duration_ms=8044,
                skill_errors=[],
            )
            second = await meter.flush_current_scope(
                intents=["web_search"],
                duration_ms=8044,
                skill_errors=[],
            )
            return first, second

    first, second = asyncio.run(_run())
    rows = _read_log_rows(tmp_path / "tokens.jsonl")

    assert (first, second) == (True, False)
    assert len(rows) == 1
    assert rows[0]["request_id"] == "web-scope"
    assert rows[0]["llm_role"] == "web"
    assert rows[0]["native_web_search_uses"] == 2
    assert rows[0]["total_tokens"] == 120
    stats = asyncio.run(meter.token_tracker.get_stats(days=7))
    assert stats["llm_requests_by_role"] == {"web": 1}
    assert stats["native_web_search_uses"] == 2
    assert stats["native_web_search_cost_usd"] == 0.02


def test_native_scope_flush_persists_activity_projection_metadata(tmp_path: Path) -> None:
    meter = UsageMeter(_settings(tmp_path))

    async def _run() -> None:
        with meter.scope(request_id="native-run", user_id="alice", source="web", router_level=2):
            await meter.record_llm_call(
                model="fake", usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            )
            await meter.flush_current_scope(
                intents=["native_agent", "recipes_execute"], duration_ms=1234, skill_errors=[],
                activity={"title": "SSH Update", "target": "srv-dev02", "success": True},
            )

    asyncio.run(_run())
    rows = _read_log_rows(tmp_path / "tokens.jsonl")

    assert len(rows) == 1
    assert rows[0]["user_id"] == "alice"
    assert rows[0]["intents"] == ["native_agent", "recipes_execute"]
    assert rows[0]["activity"] == {
        "title": "SSH Update", "target": "srv-dev02", "success": True,
    }


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
