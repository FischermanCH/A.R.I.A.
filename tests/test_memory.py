import asyncio
from types import SimpleNamespace

from aria.core.config import EmbeddingsConfig, MemoryConfig
from aria.core.embedding_client import EmbeddingClient
from aria.skills.memory import MemorySkill


class FakeQdrant:
    def __init__(self):
        self.points = []
        self.collections: dict[str, list] = {}

    @staticmethod
    def _matches_filter(payload, query_filter) -> bool:
        if not query_filter or not getattr(query_filter, "must", None):
            return True
        data = payload or {}
        for condition in query_filter.must:
            key = getattr(condition, "key", "")
            match = getattr(condition, "match", None)
            if not key or match is None:
                continue
            value = data.get(key)
            if hasattr(match, "value"):
                if value != getattr(match, "value", None):
                    return False
            elif hasattr(match, "any"):
                options = set(getattr(match, "any", []) or [])
                if value not in options:
                    return False
        return True

    async def collection_exists(self, collection_name: str):
        if self.collections:
            return collection_name in self.collections
        return True

    async def create_collection(self, collection_name: str, vectors_config=None, **kwargs):
        _ = (vectors_config, kwargs)
        self.collections.setdefault(collection_name, [])
        return None

    async def upsert(self, collection_name: str, points):
        self.points.extend(points)
        self.collections.setdefault(collection_name, [])
        self.collections[collection_name].extend(points)

    async def query_points(self, collection_name: str, query, query_filter, limit: int):
        _ = query
        src = self.collections.get(collection_name, self.points)
        filtered = [
            p for p in src if self._matches_filter((getattr(p, "payload", {}) or {}), query_filter)
        ]
        filtered = filtered[:limit]
        return SimpleNamespace(points=filtered)

    async def scroll(
        self,
        collection_name: str,
        scroll_filter=None,
        limit: int = 100,
        offset=None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ):
        _ = (offset, with_payload, with_vectors)
        src = self.collections.get(collection_name, [])
        if scroll_filter and getattr(scroll_filter, "must", None):
            src = [
                p for p in src if self._matches_filter((getattr(p, "payload", {}) or {}), scroll_filter)
            ]
        return src[:limit], None

    async def get_collections(self):
        names = sorted(self.collections.keys()) if self.collections else ["aria_memory"]
        return SimpleNamespace(collections=[SimpleNamespace(name=n) for n in names])

    async def delete_collection(self, collection_name: str):
        self.collections.pop(collection_name, None)
        return None

    async def delete(self, collection_name: str, points_selector=None, wait: bool = True):
        _ = wait
        ids = set(getattr(points_selector, "points", []) or [])
        src = self.collections.get(collection_name, [])
        self.collections[collection_name] = [
            point for point in src if getattr(point, "id", None) not in ids
        ]
        return None


async def _run_memory() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    skill.qdrant = FakeQdrant()
    skill._collection_ready = True

    async def fake_embed(_text: str, **kwargs):
        _ = kwargs
        return [0.1, 0.2, 0.3], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[assignment]

    await skill.execute("merk", {"action": "store", "text": "NAS 10.0.10.100", "user_id": "u1"})
    await skill.execute("merk", {"action": "store", "text": "anderes", "user_id": "u2"})
    pref_store = await skill.execute(
        "ich bevorzuge direkte antworten",
        {
            "action": "store",
            "text": "User bevorzugt direkte Antworten",
            "user_id": "u1",
            "memory_type": "preference",
            "source": "auto",
        },
    )
    assert pref_store.success is True

    recalled = await skill.execute("NAS", {"action": "recall", "user_id": "u1", "top_k": 3})
    assert recalled.success is True
    assert "10.0.10.100" in recalled.content
    assert "anderes" not in recalled.content
    assert any((p.payload or {}).get("type") == "preference" for p in skill.qdrant.points)
    assert any((p.payload or {}).get("source") == "auto" for p in skill.qdrant.points)


def test_memory_filters_by_user_id() -> None:
    asyncio.run(_run_memory())


async def _run_document_ingest_store() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    skill.qdrant = FakeQdrant()
    skill._collection_ready = True

    async def fake_embed(_text: str, **kwargs):
        _ = kwargs
        return [0.1, 0.2, 0.3], {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}

    skill._embed = fake_embed  # type: ignore[assignment]

    from aria.core.document_ingest import prepare_uploaded_document

    prepared = prepare_uploaded_document(
        filename="netzwerk-notizen.md",
        data=("Gateway 10.0.0.1\n\n" + "Switch im Rack A.\n" * 80).encode("utf-8"),
        content_type="text/markdown",
        chunk_size=420,
    )

    result = await skill.store_document(
        user_id="u1",
        document=prepared,
        base_collection="aria_docs_demo",
    )

    assert result.success is True
    assert result.metadata["collection"] == "aria_docs_demo"
    assert int(result.metadata["chunk_count"]) == len(prepared.chunks)
    assert any((p.payload or {}).get("source") == "rag_upload" for p in skill.qdrant.points)
    assert any((p.payload or {}).get("source") == "rag_document_guide" for p in skill.qdrant.points)
    assert any((p.payload or {}).get("document_name") == "netzwerk-notizen.md" for p in skill.qdrant.points)
    assert all((p.payload or {}).get("type") == "knowledge" for p in skill.qdrant.points)
    assert all((p.payload or {}).get("embedding_fingerprint") for p in skill.qdrant.points)
    assert all((p.payload or {}).get("embedding_model") == "openai/fake-embeddings" for p in skill.qdrant.points)

    listed_documents = await skill.list_memories_global(user_id="u1", type_filter="document", limit=20)
    assert listed_documents
    assert all(str(row.get("type", "")) == "document" for row in listed_documents)
    assert all(str(row.get("label", "")) == "DOKUMENT" for row in listed_documents)
    assert any(str(row.get("document_name", "")) == "netzwerk-notizen.md" for row in listed_documents)
    assert all(str(row.get("source", "")) != "rag_document_guide" for row in listed_documents)

    recalled_documents = await skill.search_memories(
        user_id="u1",
        query="Gateway 10.0.0.1",
        type_filter="document",
        top_k=10,
    )
    assert recalled_documents
    assert all(str(row.get("type", "")) == "document" for row in recalled_documents)
    assert all(str(row.get("label", "")) == "DOKUMENT" for row in recalled_documents)

    recalled_in_chat = await skill.execute(
        "Was sagt das Dokument über Gateway 10.0.0.1?",
        {"action": "recall", "user_id": "u1", "top_k": 3},
    )
    assert recalled_in_chat.success is True
    assert "[DOKUMENT: netzwerk-notizen.md]" in recalled_in_chat.content
    assert "Gateway 10.0.0.1" in recalled_in_chat.content
    source_lines = [str(row).strip() for row in (recalled_in_chat.metadata or {}).get("detail_lines", [])]
    assert any(line.startswith("Quelle: netzwerk-notizen.md · aria_docs_demo · Chunk ") for line in source_lines)
    sources = list((recalled_in_chat.metadata or {}).get("sources") or [])
    assert sources
    assert str(sources[0].get("document_name", "")) == "netzwerk-notizen.md"
    assert str(sources[0].get("collection", "")) == "aria_docs_demo"

    removed = await skill.delete_document(
        user_id="u1",
        collection="aria_docs_demo",
        document_id=str(result.metadata["document_id"]),
        document_name="",
    )
    assert removed == len(prepared.chunks)
    listed_after_delete = await skill.list_memories_global(user_id="u1", type_filter="document", limit=20)
    assert listed_after_delete == []
    assert "aria_doc_guides_u1" not in skill.qdrant.collections


def test_store_document_chunks_with_metadata() -> None:
    asyncio.run(_run_document_ingest_store())


async def _run_embedding_fingerprint_switch_hides_old_memory() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    skill.qdrant = FakeQdrant()
    skill._collection_ready = True

    async def fake_embed(_text: str, **kwargs):
        _ = kwargs
        return [0.1, 0.2, 0.3], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[assignment]

    stored = await skill.execute("merk", {"action": "store", "text": "Gateway 10.0.0.1", "user_id": "u1"})
    assert stored.success is True
    assert any((p.payload or {}).get("embedding_fingerprint") for p in skill.qdrant.points)

    new_embeddings = EmbeddingsConfig(model="text-embedding-3-small")
    skill.embeddings = new_embeddings
    skill.embedding_client = EmbeddingClient(new_embeddings)
    skill.memory.embedding_fingerprint = skill.embedding_client.fingerprint()
    skill.memory.embedding_model = skill.embedding_client._resolve_model()

    recalled = await skill.execute("Gateway", {"action": "recall", "user_id": "u1", "top_k": 3})
    assert recalled.success is True
    assert "10.0.0.1" not in recalled.content


def test_embedding_fingerprint_switch_hides_old_memory() -> None:
    asyncio.run(_run_embedding_fingerprint_switch_hides_old_memory())


def test_recall_source_entries_are_sorted_for_humans() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )

    entries = skill._build_recall_source_entries(
        [
            {
                "type": "session",
                "label": "KONTEXT",
                "collection": "aria_sessions_demo_260406",
                "document_name": "",
                "chunk_index": 0,
                "chunk_total": 0,
            },
            {
                "type": "fact",
                "label": "FAKT",
                "collection": "aria_facts_demo",
                "document_name": "",
                "chunk_index": 0,
                "chunk_total": 0,
            },
            {
                "type": "document",
                "label": "DOKUMENT",
                "collection": "aria_docs_demo_manuals",
                "document_name": "demo.pdf",
                "chunk_index": 3,
                "chunk_total": 12,
            },
            {
                "type": "knowledge",
                "label": "WISSEN",
                "collection": "aria_context-mem_demo",
                "document_name": "",
                "chunk_index": 0,
                "chunk_total": 0,
            },
        ],
        max_items=4,
    )

    assert [str(entry.get("type", "")) for entry in entries] == [
        "document",
        "fact",
        "knowledge",
        "session",
    ]
    assert str(entries[0].get("detail", "")) == "Quelle: demo.pdf · aria_docs_demo_manuals · Chunk 3/12"


def test_document_guide_targets_prefer_keyword_matched_document() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )

    targets = skill._build_document_targets_from_guides(
        [
            {
                "document_id": "mill-doc",
                "document_name": "Mill Manual.pdf",
                "collection": "aria_docs_fischerman",
                "guide_score": 0.74,
                "keyword_hits": 1,
                "text_hits": 2,
            },
            {
                "document_id": "arlo-doc",
                "document_name": "Arlo Ultra.pdf",
                "collection": "aria_docs_fischerman",
                "guide_score": 0.71,
                "keyword_hits": 0,
                "text_hits": 2,
            },
        ]
    )

    assert len(targets) == 1
    assert str(targets[0].get("document_id", "")) == "mill-doc"


def test_document_guide_targets_keep_close_scored_same_keyword_matches() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )

    targets = skill._build_document_targets_from_guides(
        [
            {
                "document_id": "net-1",
                "document_name": "Network Atlas.pdf",
                "collection": "aria_docs_fischerman",
                "guide_score": 0.82,
                "keyword_hits": 1,
                "text_hits": 2,
            },
            {
                "document_id": "net-2",
                "document_name": "Network Rack Notes.pdf",
                "collection": "aria_docs_fischerman",
                "guide_score": 0.78,
                "keyword_hits": 1,
                "text_hits": 1,
            },
        ]
    )

    assert {str(item.get("document_id", "")) for item in targets} == {"net-1", "net-2"}


async def _run_session_vs_user_recall() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrant()
    skill.qdrant = fake
    user_id = "DemoUser"

    day = "260323"
    fake.collections = {
        "aria_facts_demo_user": [
            SimpleNamespace(
                id="f1",
                payload={"text": "mein Default Gateway Eins 10.0.3.1 ist", "user_id": user_id},
            ),
        ],
        f"aria_sessions_demo_user_{day}": [
            SimpleNamespace(
                id="s1",
                payload={"text": "Hostname: server-main, IP: 10.0.1.1", "user_id": user_id},
            ),
        ],
    }

    recalled = await skill._recall_keyword_fallback(
        query="Was weisst du ueber mein Netzwerk?",
        user_id=user_id,
        top_k=3,
        collections=list(fake.collections.keys()),
    )
    assert recalled.success is True
    assert "10.0.3.1" in recalled.content
    assert "10.0.1.1" in recalled.content


def test_session_and_user_memory_recall_are_combined() -> None:
    asyncio.run(_run_session_vs_user_recall())


async def _run_weighted_multi_collection_recall_prefers_fact_over_session() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=2),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrant()
    skill.qdrant = fake

    async def fake_embed(_text: str, **kwargs):
        _ = kwargs
        return [0.1, 0.2, 0.3], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[assignment]
    fake.collections = {
        "aria_facts_demouser": [
            SimpleNamespace(
                id="fact-1",
                score=0.81,
                payload={
                    "text": "Mein NAS heisst Atlas",
                    "user_id": "DemoUser",
                    "type": "fact",
                },
            )
        ],
        "aria_sessions_demouser_260403": [
            SimpleNamespace(
                id="session-1",
                score=0.95,
                payload={
                    "text": "Mein NAS hiess im alten Test mal Beta",
                    "user_id": "DemoUser",
                    "type": "session",
                    "created_at": "2026-04-03T08:00:00+00:00",
                },
            )
        ],
    }

    recalled = await skill.execute("NAS Name", {"action": "recall", "user_id": "DemoUser", "top_k": 2})

    assert recalled.success is True
    lines = [line.strip() for line in recalled.content.splitlines() if line.strip()]
    assert lines[0].startswith("- [FAKT] Mein NAS heisst Atlas")
    assert any(line.startswith("- [KONTEXT] Mein NAS hiess im alten Test mal Beta") for line in lines[1:])


def test_weighted_multi_collection_recall_prefers_fact_over_session() -> None:
    asyncio.run(_run_weighted_multi_collection_recall_prefers_fact_over_session())


async def _run_empty_collection_cleanup_global() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrant()
    skill.qdrant = fake
    fake.collections = {
        "aria_memory_demo_user_session_empty1": [],
        "aria_memory_demo_user_session_empty2": [],
        "aria_facts_demo_user": [
            SimpleNamespace(id="p1", payload={"text": "gateway 10.0.3.1", "user_id": "DemoUser"})
        ],
    }

    removed = await skill.cleanup_empty_collections_global()
    assert len(removed) == 2
    assert "aria_memory_demo_user_session_empty1" in removed
    assert "aria_memory_demo_user_session_empty2" in removed
    assert "aria_facts_demo_user" in fake.collections


def test_cleanup_removes_empty_memory_collections() -> None:
    asyncio.run(_run_empty_collection_cleanup_global())


async def _run_operational_session_cleanup() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrant()
    skill.qdrant = fake
    fake.collections = {
        "aria_sessions_demo_user_260326": [
            SimpleNamespace(
                id="keep-1",
                payload={"text": "Hostname: server-main, IP: 10.0.1.1", "user_id": "DemoUser", "source": "auto_session"},
            ),
            SimpleNamespace(
                id="drop-1",
                payload={"text": "systemupdate server-main", "user_id": "DemoUser", "source": "auto_session"},
            ),
            SimpleNamespace(
                id="drop-2",
                payload={"text": "welche skills sind aktiv", "user_id": "DemoUser", "source": "auto_session"},
            ),
        ],
    }

    stats = await skill.cleanup_operational_session_entries(
        ["systemupdate", "welche skills sind aktiv"]
    )
    assert int(stats["removed_points"]) == 2
    remaining = fake.collections["aria_sessions_demo_user_260326"]
    assert len(remaining) == 1
    assert remaining[0].id == "keep-1"


def test_cleanup_removes_operational_session_noise() -> None:
    asyncio.run(_run_operational_session_cleanup())


async def _run_forget_apply_removes_empty_collections() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrant()
    skill.qdrant = fake
    fake.collections = {
        "aria_facts_demouser": [
            SimpleNamespace(id="p1", payload={"text": "Router steht im Rack", "user_id": "DemoUser"}),
        ],
    }

    result = await skill._forget_apply(
        user_id="DemoUser",
        candidates=[{"collection": "aria_facts_demouser", "id": "p1"}],
    )

    assert result.success is True
    assert "1 Eintraege entfernt" in result.content
    assert "aria_facts_demouser" not in fake.collections


def test_forget_apply_removes_empty_collections_immediately() -> None:
    asyncio.run(_run_forget_apply_removes_empty_collections())
