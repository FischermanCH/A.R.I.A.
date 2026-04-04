import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aria.core.config import EmbeddingsConfig, MemoryConfig
from aria.skills.memory import MemorySkill


class FakeQdrantCompression:
    def __init__(self) -> None:
        self.collections: dict[str, list] = {}

    async def collection_exists(self, collection_name: str):
        return collection_name in self.collections

    async def create_collection(self, collection_name: str, vectors_config):
        _ = vectors_config
        self.collections.setdefault(collection_name, [])
        return None

    async def get_collection(self, collection_name: str):
        _ = collection_name
        vectors = SimpleNamespace(size=3)
        params = SimpleNamespace(vectors=vectors)
        config = SimpleNamespace(params=params)
        return SimpleNamespace(config=config)

    async def upsert(self, collection_name: str, points):
        self.collections.setdefault(collection_name, [])
        self.collections[collection_name].extend(points)
        return None

    async def scroll(
        self,
        collection_name: str,
        scroll_filter,
        limit: int,
        offset=None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ):
        _ = (offset, with_payload, with_vectors)
        user_id = scroll_filter.must[0].match.value
        points = [
            p for p in self.collections.get(collection_name, [])
            if (getattr(p, "payload", {}) or {}).get("user_id") == user_id
        ]
        return points[:limit], None

    async def get_collections(self):
        items = [SimpleNamespace(name=name) for name in sorted(self.collections.keys())]
        return SimpleNamespace(collections=items)

    async def delete_collection(self, collection_name: str):
        self.collections.pop(collection_name, None)
        return None


async def _run_compression() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrantCompression()
    skill.qdrant = fake

    async def fake_embed(_text: str):
        return [0.1, 0.2, 0.3], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[assignment]

    user_id = "DemoUser"
    slug = skill._slug_user_id(user_id)
    day_week = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%y%m%d")
    day_month = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%y%m%d")
    week_collection = f"aria_sessions_{slug}_{day_week}"
    month_collection = f"aria_sessions_{slug}_{day_month}"

    fake.collections[week_collection] = [
        SimpleNamespace(
            id="a1",
            payload={
                "text": "Host A 10.0.1.10",
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "session",
            },
        )
    ]
    fake.collections[month_collection] = [
        SimpleNamespace(
            id="b1",
            payload={
                "text": "Host B 10.0.1.20",
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "session",
            },
        )
    ]

    result = await skill.compress_old_sessions(
        user_id=user_id,
        compress_after_days=7,
        monthly_after_days=30,
    )
    assert result["compressed_week"] >= 1
    assert result["compressed_month"] >= 1
    assert result["collections_removed"] >= 2
    assert week_collection in result["compressed_collections"]
    assert month_collection in result["removed_collections"]

    context_collection = f"aria_context-mem_{slug}"
    assert context_collection in fake.collections
    payloads = [getattr(point, "payload", {}) for point in fake.collections[context_collection]]
    assert any(str(p.get("source", "")) == "compression" for p in payloads)
    assert any(str(p.get("type", "")) == "knowledge" for p in payloads)
    assert any("Behalte nur wichtige Fakten" in str(p.get("text", "")) for p in payloads)
    assert week_collection not in fake.collections
    assert month_collection not in fake.collections


async def _run_compression_skips_recent() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrantCompression()
    skill.qdrant = fake

    async def fake_embed(_text: str):
        return [0.1, 0.2, 0.3], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[assignment]

    user_id = "DemoUser"
    slug = skill._slug_user_id(user_id)
    day_recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%y%m%d")
    recent_collection = f"aria_sessions_{slug}_{day_recent}"
    fake.collections[recent_collection] = [
        SimpleNamespace(
            id="r1",
            payload={
                "text": "Aktueller Context",
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "session",
            },
        )
    ]

    result = await skill.compress_old_sessions(
        user_id=user_id,
        compress_after_days=7,
        monthly_after_days=30,
    )
    assert result["compressed_week"] == 0
    assert result["compressed_month"] == 0
    assert result["collections_removed"] == 0
    assert recent_collection in result["skipped_recent"]
    assert recent_collection in fake.collections


async def _run_compress_all_users() -> None:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    fake = FakeQdrantCompression()
    skill.qdrant = fake

    async def fake_embed(_text: str):
        return [0.1, 0.2, 0.3], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    skill._embed = fake_embed  # type: ignore[assignment]

    old_day = (datetime.now(timezone.utc) - timedelta(days=9)).strftime("%y%m%d")
    fake.collections[f"aria_sessions_usera_{old_day}"] = [
        SimpleNamespace(id="u1", payload={"text": "A", "user_id": "usera", "timestamp": datetime.now(timezone.utc).isoformat()})
    ]
    fake.collections[f"aria_sessions_userb_{old_day}"] = [
        SimpleNamespace(id="u2", payload={"text": "B", "user_id": "userb", "timestamp": datetime.now(timezone.utc).isoformat()})
    ]

    stats = await skill.compress_all_users(compress_after_days=7, monthly_after_days=30)
    assert stats["users"] >= 2
    assert stats["compressed_week"] >= 2
    assert stats["collections_removed"] >= 2


def test_session_compression_promotes_old_sessions() -> None:
    asyncio.run(_run_compression())


def test_session_compression_ignores_recent_sessions() -> None:
    asyncio.run(_run_compression_skips_recent())


def test_compress_all_users_detects_multiple_users() -> None:
    asyncio.run(_run_compress_all_users())
