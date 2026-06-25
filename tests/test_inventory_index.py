from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.inventory_index import InventoryIndexStore, build_inventory_documents, inventory_collection_name, inventory_documents_fingerprint


class FakeEmbeddingResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.usage = {"prompt_tokens": len(vectors), "completion_tokens": 0, "total_tokens": len(vectors)}
        self.model = "fake-embedding"


class FakeEmbeddingClient:
    async def embed(self, inputs, **kwargs):  # noqa: ANN001
        _ = kwargs
        vectors: list[list[float]] = []
        for text in inputs:
            lower = str(text or "").lower()
            security = 1.0 if any(token in lower for token in ("security", "sicherheit", "cve", "pentest", "incident")) else 0.0
            rss = 1.0 if "rss" in lower else 0.0
            vectors.append([security, rss])
        return FakeEmbeddingResponse(vectors)


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, object]] = {}

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    async def create_collection(self, collection_name: str, vectors_config) -> None:  # noqa: ANN001
        self.collections[collection_name] = {"size": int(vectors_config.size), "points": []}

    async def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)

    async def get_collection(self, collection_name: str):  # noqa: ANN201
        points = list(self.collections.get(collection_name, {}).get("points", []) or [])
        return SimpleNamespace(points_count=len(points), config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=self.collections[collection_name]["size"]))))

    async def upsert(self, collection_name: str, points: list[object]) -> None:
        current = list(self.collections.setdefault(collection_name, {"size": len(points[0].vector) if points else 0, "points": []})["points"])
        by_id = {str(getattr(point, "id", "")): point for point in current}
        for point in points:
            by_id[str(getattr(point, "id", ""))] = point
        self.collections[collection_name]["points"] = list(by_id.values())

    async def scroll(self, collection_name: str, limit: int = 100, offset=None, with_payload: bool = True, with_vectors: bool = False):  # noqa: ANN001, ARG002
        rows = list(self.collections.get(collection_name, {}).get("points", []) or [])
        start = int(offset or 0)
        batch = rows[start : start + limit]
        next_offset = start + limit if start + limit < len(rows) else None
        return batch, next_offset

    async def query_points(self, collection_name: str, query: list[float], limit: int = 5):  # noqa: ANN001
        rows = []
        for point in list(self.collections.get(collection_name, {}).get("points", []) or []):
            vector = list(getattr(point, "vector", []) or [])
            score = sum(float(a) * float(b) for a, b in zip(vector, query, strict=False))
            rows.append(SimpleNamespace(id=getattr(point, "id", ""), payload=getattr(point, "payload", {}) or {}, score=score))
        rows.sort(key=lambda item: item.score, reverse=True)
        return SimpleNamespace(points=rows[:limit])


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "rss": {
                    "infoguard-pentest": {
                        "feed_url": "https://labs.infoguard.ch/archive/category/Pentest/",
                        "title": "InfoGuard Labs Pentest Archiv",
                        "description": "Security Testing und Schwachstellen",
                        "group_name": "Security",
                        "tags": ["Pentest", "IT-Sicherheit", "CVE"],
                    }
                },
                "website": {
                    "sports-watch": {
                        "url": "https://example.invalid/sports",
                        "title": "Sports Watch",
                        "group_name": "Sport",
                        "tags": ["Sport"],
                    }
                },
            },
        }
    )


def test_inventory_documents_keep_safe_metadata_and_exclude_urls() -> None:
    docs = build_inventory_documents(_settings())
    text = "\n".join(doc.text for doc in docs)

    assert any(doc.kind == "surface" and doc.ref == "connections" for doc in docs)
    assert any(doc.kind == "surface" and doc.ref == "memory" for doc in docs)
    assert "InfoGuard Labs Pentest Archiv" in text
    assert "Security" in text
    assert "IT-Sicherheit" in text
    assert "https://labs.infoguard.ch" not in text
    assert "example.invalid" not in text


def test_inventory_index_rebuild_keeps_backup_and_queries_security() -> None:
    settings = _settings()
    docs = build_inventory_documents(settings)
    qdrant = FakeQdrant()
    store = InventoryIndexStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=inventory_collection_name(settings))

    first = asyncio.run(store.rebuild_documents(docs, index_hash=inventory_documents_fingerprint(docs), backup_collection_name=inventory_collection_name(settings, backup=True)))
    second = asyncio.run(store.rebuild_documents(docs, index_hash=inventory_documents_fingerprint(docs), backup_collection_name=inventory_collection_name(settings, backup=True)))
    hits = asyncio.run(store.query_inventory("IT-Security", surface_id="connections", limit=5, score_threshold=0.1))

    assert first["documents"] == len(docs)
    assert second["backup_documents"] == len(docs)
    assert hits
    assert hits[0]["kind"] == "rss"
    assert hits[0]["ref"] == "infoguard-pentest"
