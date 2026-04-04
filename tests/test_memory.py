import asyncio
from types import SimpleNamespace

from aria.core.config import EmbeddingsConfig, MemoryConfig
from aria.skills.memory import MemorySkill


class FakeQdrant:
    def __init__(self):
        self.points = []
        self.collections: dict[str, list] = {}

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
        user_id = query_filter.must[0].match.value
        src = self.collections.get(collection_name, self.points)
        filtered = [p for p in src if (p.payload or {}).get("user_id") == user_id]
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
            user_id = scroll_filter.must[0].match.value
            src = [p for p in src if (getattr(p, "payload", {}) or {}).get("user_id") == user_id]
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

    async def fake_embed(_text: str):
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

    async def fake_embed(_text: str):
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
