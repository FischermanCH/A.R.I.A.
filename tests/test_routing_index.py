from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.routing_index import (
    RoutingIndexStore,
    build_connection_routing_documents,
    routing_collection_name,
    routing_documents_fingerprint,
)


class FakeEmbeddingResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.usage = {"prompt_tokens": len(vectors), "completion_tokens": 0, "total_tokens": len(vectors)}
        self.model = "fake-embedding"


class FakeEmbeddingClient:
    async def embed(self, inputs, **kwargs):  # noqa: ANN001
        _ = kwargs
        return FakeEmbeddingResponse([[float(index + 1), 0.5] for index, _text in enumerate(inputs)])


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, int] = {}
        self.upserts: list[tuple[str, list[object]]] = []

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    async def create_collection(self, collection_name: str, vectors_config) -> None:  # noqa: ANN001
        self.collections[collection_name] = int(vectors_config.size)

    async def get_collection(self, collection_name: str):  # noqa: ANN201
        size = self.collections.get(collection_name)
        if size is None:
            raise ValueError("missing collection")
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=size))))

    async def upsert(self, collection_name: str, points: list[object]) -> None:
        self.upserts.append((collection_name, list(points)))


def test_build_connection_routing_documents_keeps_metadata_and_excludes_secrets() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "ssh": {
                    " pihole1 ": {
                        "host": "pihole1.black.lan",
                        "user": "root",
                        "key_path": "/secrets/pihole_ed25519",
                        "title": "Pi-hole DNS",
                        "description": "DNS blocker and DHCP helper",
                        "aliases": ["dns blocker"],
                        "tags": ["infra", "dns"],
                        "service_url": "https://pihole1.black.lan/admin",
                    }
                },
                "discord": {
                    "alerts-discord": {
                        "webhook_url": "https://discord.com/api/webhooks/123/VERY_SECRET_TOKEN",
                        "title": "Alerts",
                        "tags": ["ops"],
                    }
                },
            },
        }
    )

    docs = build_connection_routing_documents(settings)

    ssh_doc = next(doc for doc in docs if doc.kind == "ssh")
    assert ssh_doc.ref == "pihole1"
    assert ssh_doc.title == "Pi-hole DNS"
    assert "dns blocker" in ssh_doc.aliases
    assert "infra" in ssh_doc.tags
    assert "run command" in ssh_doc.supported_actions
    assert "pihole1.black.lan" in ssh_doc.text
    assert "/secrets/pihole_ed25519" not in ssh_doc.text

    all_text = "\n".join(doc.text for doc in docs)
    assert "VERY_SECRET_TOKEN" not in all_text
    assert "webhooks/123" not in all_text


async def _upsert_documents() -> tuple[dict[str, object], FakeQdrant]:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "ssh": {
                    "pihole1": {
                        "host": "pihole1.black.lan",
                        "title": "Pi-hole DNS",
                    }
                }
            },
        }
    )
    docs = build_connection_routing_documents(settings)
    qdrant = FakeQdrant()
    store = RoutingIndexStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name="aria_routing_connections_test",
    )
    result = await store.upsert_documents(docs)
    return result, qdrant


def test_routing_index_store_upserts_documents() -> None:
    result, qdrant = asyncio.run(_upsert_documents())

    assert result["documents"] == 1
    assert result["collections"] == ["aria_routing_connections_test"]
    assert result["routing_index_hash"]
    assert qdrant.collections == {"aria_routing_connections_test": 2}
    assert len(qdrant.upserts) == 1
    _collection, points = qdrant.upserts[0]
    payload = points[0].payload
    assert payload["scope"] == "connection"
    assert payload["kind"] == "ssh"
    assert payload["ref"] == "pihole1"
    assert payload["embedding_model"] == "fake-embedding"
    assert payload["routing_index_hash"] == result["routing_index_hash"]
    assert payload["routing_index_document_count"] == 1


def test_routing_documents_fingerprint_is_stable_and_changes_with_metadata() -> None:
    base = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {"ssh": {"pihole1": {"title": "Pi-hole DNS"}}},
        }
    )
    changed = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {"ssh": {"pihole1": {"title": "Pi-hole DNS", "tags": ["dns"]}}},
        }
    )

    first = routing_documents_fingerprint(build_connection_routing_documents(base))
    second = routing_documents_fingerprint(build_connection_routing_documents(base))
    third = routing_documents_fingerprint(build_connection_routing_documents(changed))

    assert first == second
    assert third != first


def test_routing_index_query_does_not_create_missing_collection() -> None:
    qdrant = FakeQdrant()
    store = RoutingIndexStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name="aria_routing_connections_test",
    )

    rows = asyncio.run(store.query_connections("dns server"))

    assert rows == []
    assert qdrant.collections == {}
    assert qdrant.upserts == []


def test_routing_collection_name_supports_instance_suffix() -> None:
    assert routing_collection_name("connections", instance_key="ARIA Black LAN:8810") == "aria_routing_connections_aria_black_lan_8810"
