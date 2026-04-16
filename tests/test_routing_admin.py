from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.routing_admin import (
    build_connection_routing_index_status,
    rebuild_connection_routing_index,
    routing_connections_collection_name,
    test_connection_routing_query as run_connection_routing_query,
)
from aria.core.routing_index import build_connection_routing_documents
from aria.core.routing_index import routing_documents_fingerprint


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "aria": {"public_url": "http://aria.black.lan:8810"},
            "llm": {"model": "fake"},
            "embeddings": {"model": "embed-small", "api_base": "http://litellm:4000"},
            "memory": {
                "enabled": True,
                "backend": "qdrant",
                "qdrant_url": "http://qdrant:6333",
            },
            "connections": {
                "ssh": {
                    "pihole1": {
                        "host": "pihole1.lan",
                        "user": "root",
                        "description": "Pi-hole DNS server",
                        "tags": ["dns", "pi-hole"],
                    }
                }
            },
        }
    )


def test_routing_admin_status_reports_missing_index() -> None:
    settings = _settings()

    class FakeQdrant:
        async def get_collections(self) -> object:
            return SimpleNamespace(collections=[])

    meta = asyncio.run(build_connection_routing_index_status(settings, qdrant_client=FakeQdrant()))

    assert meta["status"] == "warn"
    assert meta["document_count"] == 1
    assert meta["indexed_count"] == 0
    assert "not been built" in meta["message"]


def test_routing_admin_status_counts_matching_routing_collections() -> None:
    settings = _settings()
    collection = routing_connections_collection_name(settings)
    current_hash = routing_documents_fingerprint(build_connection_routing_documents(settings))

    class FakeQdrant:
        async def get_collections(self) -> object:
            return SimpleNamespace(collections=[SimpleNamespace(name=collection)])

        async def get_collection(self, collection_name: str) -> object:
            assert collection_name == collection
            return SimpleNamespace(points_count=1)

        async def scroll(self, *, collection_name: str, limit: int, with_payload: bool, with_vectors: bool) -> tuple[list[object], None]:
            assert collection_name == collection
            assert limit == 16
            assert with_payload is True
            assert with_vectors is False
            return [SimpleNamespace(payload={"routing_index_hash": current_hash})], None

    meta = asyncio.run(build_connection_routing_index_status(settings, qdrant_client=FakeQdrant()))

    assert meta["status"] == "ok"
    assert meta["collection_name"] == collection
    assert meta["collection_names"] == [collection]
    assert meta["document_count"] == 1
    assert meta["indexed_count"] == 1
    assert meta["current_config_hash"] == current_hash
    assert meta["indexed_config_hash"] == current_hash
    assert meta["stale"] is False


def test_routing_admin_status_detects_stale_index_hash() -> None:
    settings = _settings()
    collection = routing_connections_collection_name(settings)

    class FakeQdrant:
        async def get_collections(self) -> object:
            return SimpleNamespace(collections=[SimpleNamespace(name=collection)])

        async def get_collection(self, collection_name: str) -> object:
            return SimpleNamespace(points_count=1)

        async def scroll(self, **_kwargs: object) -> tuple[list[object], None]:
            return [SimpleNamespace(payload={"routing_index_hash": "old-index-hash"})], None

    meta = asyncio.run(build_connection_routing_index_status(settings, qdrant_client=FakeQdrant()))

    assert meta["status"] == "warn"
    assert meta["stale"] is True
    assert meta["indexed_config_hash"] == "old-index-hash"
    assert "outdated" in meta["message"]


def test_routing_admin_rebuild_upserts_generated_documents() -> None:
    settings = _settings()
    collection = routing_connections_collection_name(settings)
    upserts: list[tuple[str, int]] = []
    payloads: list[dict[str, object]] = []

    class FakeQdrant:
        async def collection_exists(self, collection_name: str) -> bool:
            assert collection_name == collection
            return False

        async def create_collection(self, **kwargs: object) -> None:
            assert kwargs["collection_name"] == collection

        async def upsert(self, *, collection_name: str, points: list[object]) -> None:
            upserts.append((collection_name, len(points)))
            payloads.extend(dict(point.payload) for point in points)

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            return SimpleNamespace(
                vectors=[[0.1, 0.2, 0.3] for _text in inputs],
                usage={"total_tokens": len(inputs)},
                model="openai/embed-small",
            )

    meta = asyncio.run(
        rebuild_connection_routing_index(
            settings,
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
        )
    )

    assert meta["status"] == "ok"
    assert meta["document_count"] == 1
    assert meta["indexed_count"] == 1
    assert meta["current_config_hash"]
    assert meta["indexed_config_hash"] == meta["current_config_hash"]
    assert meta["stale"] is False
    assert meta["embedding_model"] == "openai/embed-small"
    assert upserts == [(collection, 1)]
    assert payloads[0]["routing_index_hash"] == meta["current_config_hash"]


def test_routing_admin_testbench_uses_qdrant_after_deterministic_miss() -> None:
    settings = _settings()
    collection = routing_connections_collection_name(settings)

    class FakeQdrant:
        async def collection_exists(self, collection_name: str) -> bool:
            return collection_name == collection

        async def get_collection(self, collection_name: str) -> object:
            assert collection_name == collection
            return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=3))))

        async def query_points(self, *, collection_name: str, query: list[float], limit: int) -> list[object]:
            assert collection_name == collection
            assert query == [0.1, 0.2, 0.3]
            assert limit == 20
            return [
                SimpleNamespace(
                    score=0.87,
                    payload={
                        "scope": "connection",
                        "kind": "ssh",
                        "ref": "pihole1",
                        "title": "Pi-hole DNS",
                        "description": "DNS blocker",
                    },
                )
            ]

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            assert inputs == ["mach server healthcheck"]
            return SimpleNamespace(vectors=[[0.1, 0.2, 0.3]], usage={}, model="openai/embed-small")

    meta = asyncio.run(
        run_connection_routing_query(
            settings,
            "mach server healthcheck",
            preferred_kind="ssh",
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
        )
    )

    assert meta["status"] == "ok"
    assert meta["executed"] is False
    assert meta["deterministic"]["found"] is False
    assert meta["decision"]["source"] == "qdrant_routing"
    assert meta["decision"]["kind"] == "ssh"
    assert meta["decision"]["ref"] == "pihole1"
    assert meta["qdrant"]["accepted_count"] == 1


def test_routing_admin_testbench_keeps_exact_match_first_but_lists_qdrant_candidates() -> None:
    settings = _settings()
    collection = routing_connections_collection_name(settings)

    class FakeQdrant:
        async def collection_exists(self, collection_name: str) -> bool:
            return collection_name == collection

        async def get_collection(self, collection_name: str) -> object:
            return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=3))))

        async def query_points(self, *, collection_name: str, query: list[float], limit: int) -> list[object]:
            return [
                SimpleNamespace(
                    score=0.99,
                    payload={
                        "scope": "connection",
                        "kind": "discord",
                        "ref": "alerts",
                        "title": "Wrong target",
                    },
                )
            ]

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            return SimpleNamespace(vectors=[[0.1, 0.2, 0.3]], usage={}, model="openai/embed-small")

    meta = asyncio.run(
        run_connection_routing_query(
            settings,
            "Run uptime on pihole1",
            preferred_kind="ssh",
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
        )
    )

    assert meta["status"] == "ok"
    assert meta["decision"]["source"] == "exact_ref"
    assert meta["decision"]["ref"] == "pihole1"
    assert meta["qdrant"]["candidate_count"] == 1
    assert meta["qdrant"]["candidates"][0]["accepted"] is False
    assert "preferred kind ssh" in meta["qdrant"]["candidates"][0]["reject_reason"]


def test_routing_admin_testbench_auto_infers_ssh_and_rejects_sftp_candidate() -> None:
    settings = Settings.model_validate(
        {
            "aria": {"public_url": "http://aria.black.lan:8810"},
            "llm": {"model": "fake"},
            "embeddings": {"model": "embed-small", "api_base": "http://litellm:4000"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {"pihole1": {"host": "pihole1.lan", "user": "root", "description": "Pi-hole DNS"}},
                "sftp": {"pihole1": {"host": "pihole1.lan", "user": "root", "description": "Pi-hole files"}},
            },
        }
    )
    collection = routing_connections_collection_name(settings)

    class FakeQdrant:
        async def collection_exists(self, collection_name: str) -> bool:
            return collection_name == collection

        async def get_collection(self, collection_name: str) -> object:
            return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=3))))

        async def query_points(self, *, collection_name: str, query: list[float], limit: int) -> list[object]:
            assert collection_name == collection
            assert limit == 20
            return [
                SimpleNamespace(
                    score=0.91,
                    payload={
                        "scope": "connection",
                        "kind": "sftp",
                        "ref": "pihole1",
                        "title": "pihole1 files",
                    },
                ),
                SimpleNamespace(
                    score=0.82,
                    payload={
                        "scope": "connection",
                        "kind": "ssh",
                        "ref": "pihole1",
                        "title": "Pi-hole Primary DNS Server",
                    },
                ),
            ]

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            assert inputs == ["Zeig mir die Laufzeit vom primären DNS Server"]
            return SimpleNamespace(vectors=[[0.1, 0.2, 0.3]], usage={}, model="openai/embed-small")

    meta = asyncio.run(
        run_connection_routing_query(
            settings,
            "Zeig mir die Laufzeit vom primären DNS Server",
            preferred_kind="auto",
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
        )
    )

    assert meta["status"] == "ok"
    assert meta["preferred_kind"] == "ssh"
    assert meta["requested_preferred_kind"] == "auto"
    assert meta["inferred_preferred_kind"] == "ssh"
    assert meta["decision"]["kind"] == "ssh"
    assert meta["decision"]["ref"] == "pihole1"
    assert meta["qdrant"]["accepted_count"] == 1
    assert meta["qdrant"]["candidate_count"] == 2
    assert meta["qdrant"]["candidates"][0]["kind"] == "sftp"
    assert meta["qdrant"]["candidates"][0]["accepted"] is False
    assert "preferred kind ssh" in meta["qdrant"]["candidates"][0]["reject_reason"]
