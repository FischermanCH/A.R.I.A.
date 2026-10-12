from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import EmbeddingsConfig, MCPServerConfig, MemoryConfig
from aria.modules.document_memory.native_tools import native_tool_contributions
from aria.modules.mcp.runtime import MCPClientManager
from aria.modules.memory.recall_sources import bounded_document_excerpt
from aria.modules.memory_learning_bridge.skill import MemorySkill


ROOT = Path(__file__).resolve().parents[1]


def test_alpha985_release_metadata_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release_meta = (ROOT / "aria/modules/release_update/release_meta.py").read_text(encoding="utf-8")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in release_meta
    assert "## 0.1.0-alpha985" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 0.1.0-alpha985" in (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8")
    assert "0.1.0-alpha983" in (ROOT / "README.md").read_text(encoding="utf-8")


class _LeafletQdrant:
    def __init__(self) -> None:
        self.collection = "aria_docs_alice_leaflets"
        self.points = [
            SimpleNamespace(
                id="heading",
                score=0.99,
                payload={
                    "text": "In welcher Dosierung wird Simponi angewendet?",
                    "user_id": "Alice",
                    "type": "knowledge",
                    "source": "rag_upload",
                    "document_id": "simponi-leaflet",
                    "document_name": "Simponi Beipackzettel.pdf",
                    "chunk_index": 1,
                    "chunk_total": 2,
                },
            ),
            SimpleNamespace(
                id="dosage",
                score=0.10,
                payload={
                    "text": "Die empfohlene Dosis ist 50 mg einmal im Monat.\nÄndern Sie die Dosis nicht selbstständig.",
                    "user_id": "Alice",
                    "type": "knowledge",
                    "source": "rag_upload",
                    "document_id": "simponi-leaflet",
                    "document_name": "Simponi Beipackzettel.pdf",
                    "chunk_index": 2,
                    "chunk_total": 2,
                },
            ),
            SimpleNamespace(
                id="foreign-dosage",
                score=0.09,
                payload={
                    "text": "Fremder Inhalt darf nie sichtbar sein.",
                    "user_id": "Bob",
                    "type": "knowledge",
                    "source": "rag_upload",
                    "document_id": "simponi-leaflet",
                    "document_name": "Simponi Beipackzettel.pdf",
                    "chunk_index": 2,
                    "chunk_total": 2,
                },
            ),
        ]

    async def collection_exists(self, *, collection_name: str) -> bool:
        return collection_name == self.collection

    async def query_points(self, **_kwargs):  # noqa: ANN003, ANN202
        # Reproduce the live shape: semantic search finds only the section heading.
        return SimpleNamespace(points=[self.points[0]])

    async def scroll(self, *, collection_name: str, **_kwargs):  # noqa: ANN003, ANN202
        assert collection_name == self.collection
        return self.points, None


def _leaflet_skill() -> MemorySkill:
    skill = MemorySkill(
        memory=MemoryConfig(
            enabled=True,
            qdrant_url="http://unused:6333",
            collection="aria_memory",
            top_k=3,
        ),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    skill.qdrant = _LeafletQdrant()

    async def fake_embed(_text: str, **_kwargs):  # noqa: ANN202
        return [1.0, 0.0], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[method-assign]
    return skill


def test_two_chunk_leaflet_returns_heading_and_owned_following_dosage_in_order() -> None:
    async def scenario() -> None:
        skill = _leaflet_skill()

        class ScopedLeafletSkill:
            async def execute(self, *, query, params):  # noqa: ANN001, ANN202
                return await skill.execute(query, {
                    **dict(params),
                    "document_ids": ["simponi-leaflet"],
                    "document_target_collections": ["aria_docs_alice_leaflets"],
                })

        binding = native_tool_contributions(SimpleNamespace(memory_skill=ScopedLeafletSkill()))[0]
        result = await binding.handler(
            SimpleNamespace(user_id="alice"),
            {"action": "answer", "query": "Dosierung Simponi"},
        )
        payload = json.loads(result.content)

        assert payload["status"] == "ok"
        rows = payload["documents"]
        assert [row["chunk_index"] for row in rows] == ["1", "2"]
        assert all(row["document_name"] == "Simponi Beipackzettel.pdf" for row in rows)
        assert rows[0]["excerpt"] == "In welcher Dosierung wird Simponi angewendet?"
        assert rows[1]["excerpt"] == (
            "Die empfohlene Dosis ist 50 mg einmal im Monat.\n"
            "Ändern Sie die Dosis nicht selbstständig."
        )
        assert rows[1]["neighbor"] == "true"
        assert "Fremder Inhalt" not in result.content
        assert len(result.content) <= 12_000

    asyncio.run(scenario())


def test_document_source_metadata_keeps_multiline_excerpt_outside_legacy_content_cap() -> None:
    async def scenario() -> None:
        skill = _leaflet_skill()
        result = await skill.execute(
            "Dosierung Simponi",
            {
                "action": "recall",
                "user_id": "alice",
                "top_k": 4,
                "include_documents": True,
                "docs_only": True,
                "document_ids": ["simponi-leaflet"],
                "document_target_collections": ["aria_docs_alice_leaflets"],
            },
        )

        assert len(result.content) <= skill.max_context_chars + len("\n[... gekuerzt]")
        sources = result.metadata["sources"]
        assert [source["chunk_index"] for source in sources] == [1, 2]
        assert "\nÄndern Sie" in sources[1]["excerpt"]
        assert sources[1]["neighbor"] is True
        assert sources[0]["score"] > sources[1]["score"]

    asyncio.run(scenario())


def test_document_excerpt_uses_readable_boundary_and_explicit_ellipsis() -> None:
    text = ("Erster vollständiger Satz. " * 90) + "Schluss"
    excerpt = bounded_document_excerpt(text)
    assert len(excerpt) <= 1_600
    assert excerpt.endswith("…")
    assert excerpt[-2] == "."


def test_short_middle_heading_adds_owned_previous_and_following_chunks_once() -> None:
    async def scenario() -> None:
        skill = _leaflet_skill()
        qdrant = skill.qdrant
        qdrant.points = [SimpleNamespace(
            id="intro", score=0.1, payload={
                "text": "Vorheriger Abschnitt mit Kontext.", "user_id": "Alice",
                "type": "knowledge", "source": "rag_upload",
                "document_id": "simponi-leaflet", "document_name": "Simponi Beipackzettel.pdf",
                "chunk_index": 1, "chunk_total": 3,
            },
        ), SimpleNamespace(
            id="dosage", score=0.1, payload={
                "text": "Die empfohlene Dosis ist 50 mg einmal im Monat.", "user_id": "Alice",
                "type": "knowledge", "source": "rag_upload",
                "document_id": "simponi-leaflet", "document_name": "Simponi Beipackzettel.pdf",
                "chunk_index": 3, "chunk_total": 3,
            },
        )]
        anchor = {
            "score": 0.9, "label": "DOKUMENT", "type": "document",
            "text": "Dosierung:", "collection": qdrant.collection,
            "document_id": "simponi-leaflet", "document_name": "Simponi Beipackzettel.pdf",
            "chunk_index": 2, "chunk_total": 3, "source": "rag_upload",
        }
        rows = await skill._expand_document_context_rows([anchor, dict(anchor)], user_id="alice")
        assert [row["chunk_index"] for row in rows] == [1, 2, 3]
        assert rows[0]["neighbor"] is True and rows[2]["neighbor"] is True
        assert "Fremder Inhalt" not in " ".join(row["text"] for row in rows)

    asyncio.run(scenario())


def test_mcp_failures_use_exponential_backoff_and_reset_after_success() -> None:
    async def scenario() -> None:
        now = [100.0]
        calls: list[float] = []
        manager = MCPClientManager(
            {
                "down": MCPServerConfig.model_validate({
                    "transport": "sse",
                    "url": "https://mcp.invalid/events",
                    "enabled": True,
                }),
            },
            clock=lambda: now[0],
        )

        async def fail_then_recover(_server_name, _config):  # noqa: ANN001, ANN202
            calls.append(now[0])
            if len(calls) < 4:
                raise ConnectionError("offline")
            return ()

        manager._discover_server = fail_then_recover  # type: ignore[method-assign]

        await manager.discover_all(refresh=True)
        assert manager.failure_backoff_seconds("down") == 30

        now[0] = 129.0
        await manager.discover_all(block_cold=True)
        assert calls == [100.0]

        now[0] = 130.0
        await manager.discover_all(block_cold=True)
        assert calls == [100.0, 130.0]
        assert manager.failure_backoff_seconds("down") == 60

        now[0] = 189.0
        await manager.discover_all(block_cold=True)
        assert calls == [100.0, 130.0]

        now[0] = 190.0
        await manager.discover_all(block_cold=True)
        assert calls == [100.0, 130.0, 190.0]
        assert manager.failure_backoff_seconds("down") == 120

        now[0] = 310.0
        await manager.discover_all(block_cold=True)
        assert calls == [100.0, 130.0, 190.0, 310.0]
        assert manager.failure_backoff_seconds("down") == 0
        assert manager.statuses()[0].connected is True
        await manager.close()

    asyncio.run(scenario())


def test_mcp_failure_backoff_caps_at_ten_minutes() -> None:
    manager = MCPClientManager({})
    for failure in range(1, 8):
        manager._record_discovery_failure("down", now=float(failure))
    assert manager.failure_backoff_seconds("down") == 600
