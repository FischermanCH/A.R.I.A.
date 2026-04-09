from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core import runtime_diagnostics


class _FakeQdrantClient:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name="a"), SimpleNamespace(name="b")])

    async def close(self) -> None:
        return None


async def _fake_embedding(self, inputs, **kwargs):
    _ = (self, inputs, kwargs)
    return SimpleNamespace(vectors=[[0.1, 0.2]], usage={"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1})


async def _build_ok_result(tmp_path: Path, monkeypatch) -> dict[str, object]:
    prompts_dir = tmp_path / "prompts" / "skills"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "prompts" / "persona.md").write_text("Name: NOVA\n", encoding="utf-8")
    (prompts_dir / "memory.md").write_text("# prompt\n", encoding="utf-8")

    monkeypatch.setattr(runtime_diagnostics, "create_async_qdrant_client", lambda **kwargs: _FakeQdrantClient(**kwargs))
    monkeypatch.setattr(runtime_diagnostics.EmbeddingClient, "embed", _fake_embedding)

    async def _fake_chat(self, messages, **kwargs):
        _ = (messages, kwargs)
        return SimpleNamespace(content="OK")

    monkeypatch.setattr(runtime_diagnostics.LLMClient, "chat", _fake_chat)

    settings = Settings.model_validate(
        {
            "llm": {"model": "fake-chat"},
            "embeddings": {"model": "fake-embed"},
            "prompts": {"persona": "prompts/persona.md", "skills_dir": "prompts/skills"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
        }
    )
    return await runtime_diagnostics.build_runtime_diagnostics(tmp_path, settings)


def test_build_runtime_diagnostics_returns_ok_when_all_checks_pass(tmp_path, monkeypatch) -> None:
    result = asyncio.run(_build_ok_result(tmp_path, monkeypatch))

    assert result["status"] == "ok"
    checks = {row["id"]: row for row in result["checks"]}
    assert checks["prompts"]["status"] == "ok"
    assert checks["qdrant"]["status"] == "ok"
    assert checks["llm"]["status"] == "ok"
    assert checks["embeddings"]["status"] == "ok"


def test_probe_prompt_files_reports_missing_persona(tmp_path) -> None:
    prompts_dir = tmp_path / "prompts" / "skills"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    result = runtime_diagnostics.probe_prompt_files(
        tmp_path,
        SimpleNamespace(persona="prompts/persona.md", skills_dir="prompts/skills"),
    )

    assert result["status"] == "error"
    assert "persona" in result["detail"]


def test_probe_qdrant_skips_when_memory_is_disabled() -> None:
    result = asyncio.run(
        runtime_diagnostics.probe_qdrant(
            SimpleNamespace(enabled=False, backend="qdrant", qdrant_url="http://qdrant:6333", qdrant_api_key="")
        )
    )

    assert result["status"] == "skipped"


def test_probe_qdrant_warns_when_local_storage_has_missing_collections(tmp_path, monkeypatch) -> None:
    storage_dir = tmp_path / "data" / "qdrant" / "collections" / "aria_facts_whity"
    storage_dir.mkdir(parents=True, exist_ok=True)

    class EmptyClient:
        async def get_collections(self):
            return SimpleNamespace(collections=[])

        async def close(self) -> None:
            return None

    monkeypatch.setattr(runtime_diagnostics, "create_async_qdrant_client", lambda **kwargs: EmptyClient())

    result = asyncio.run(
        runtime_diagnostics.probe_qdrant(
            SimpleNamespace(enabled=True, backend="qdrant", qdrant_url="http://localhost:6333", qdrant_api_key=""),
            base_dir=tmp_path,
        )
    )

    assert result["status"] == "warn"
    assert result["summary_key"] == "qdrant_storage_warning"


def test_probe_llm_reports_error_when_request_fails(monkeypatch) -> None:
    async def _failing_chat(self, messages, **kwargs):
        _ = (messages, kwargs)
        raise runtime_diagnostics.LLMClientError("boom")

    monkeypatch.setattr(runtime_diagnostics.LLMClient, "chat", _failing_chat)

    result = asyncio.run(
        runtime_diagnostics.probe_llm(
            SimpleNamespace(
                model="fake",
                api_base="http://llm.local",
                api_key="",
                temperature=0.2,
                max_tokens=128,
                timeout_seconds=5,
                model_copy=lambda update: SimpleNamespace(
                    model="fake",
                    api_base="http://llm.local",
                    api_key="",
                    temperature=update["temperature"],
                    max_tokens=update["max_tokens"],
                    timeout_seconds=update["timeout_seconds"],
                ),
            )
        )
    )

    assert result["status"] == "error"
    assert "LLM nicht erreichbar" in result["summary"]


def test_embedding_vector_present_accepts_dict_payloads() -> None:
    response = SimpleNamespace(data=[{"embedding": [0.1, 0.2, 0.3]}])

    assert runtime_diagnostics._embedding_vector_present(response) is True
