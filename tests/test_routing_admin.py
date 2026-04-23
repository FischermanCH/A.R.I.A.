from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.routing_admin import (
    build_connection_routing_index_status,
    ensure_connection_routing_index_ready,
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


def test_routing_admin_ensure_refreshes_stale_index() -> None:
    settings = _settings()
    collection = routing_connections_collection_name(settings)
    current_hash = routing_documents_fingerprint(build_connection_routing_documents(settings))

    class FakeQdrant:
        def __init__(self) -> None:
            self.points_count = 1
            self.index_hash = "old-index-hash"

        async def get_collections(self) -> object:
            return SimpleNamespace(collections=[SimpleNamespace(name=collection)])

        async def get_collection(self, collection_name: str) -> object:
            assert collection_name == collection
            return SimpleNamespace(points_count=self.points_count)

        async def scroll(self, **_kwargs: object) -> tuple[list[object], None]:
            return [SimpleNamespace(payload={"routing_index_hash": self.index_hash})], None

        async def collection_exists(self, collection_name: str) -> bool:
            assert collection_name == collection
            return True

        async def upsert(self, *, collection_name: str, points: list[object]) -> None:
            assert collection_name == collection
            self.points_count = len(points)
            self.index_hash = str(points[0].payload["routing_index_hash"])

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            return SimpleNamespace(
                vectors=[[0.1, 0.2, 0.3] for _ in inputs],
                usage={"total_tokens": len(inputs)},
                model="openai/embed-small",
            )

    fake_qdrant = FakeQdrant()
    meta = asyncio.run(
        ensure_connection_routing_index_ready(
            settings,
            qdrant_client=fake_qdrant,
            embedding_client=FakeEmbedder(),
            wait=True,
        )
    )

    status = dict(meta["status"])
    assert meta["refresh_attempted"] is True
    assert status["status"] == "ok"
    assert status["current_config_hash"] == current_hash
    assert status["indexed_config_hash"] == current_hash
    assert status["stale"] is False


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
    assert meta["decision"]["source"] == "default_single_profile"
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


def test_routing_admin_testbench_includes_llm_router_dry_run() -> None:
    settings = Settings.model_validate(
        {
            "aria": {"public_url": "http://aria.black.lan:8810"},
            "llm": {"model": "fake"},
            "embeddings": {"model": "embed-small", "api_base": "http://litellm:4000"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {
                    "pihole1": {"host": "pihole1.lan", "user": "root", "description": "Primary DNS"},
                    "pihole2": {"host": "pihole2.lan", "user": "root", "description": "Secondary DNS"},
                }
            },
        }
    )
    collection = routing_connections_collection_name(settings)
    llm_messages: list[dict[str, str]] = []

    class FakeQdrant:
        async def collection_exists(self, collection_name: str) -> bool:
            return collection_name == collection

        async def get_collection(self, collection_name: str) -> object:
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
                        "title": "Primary DNS",
                        "description": "Pi-hole Primary DNS",
                        "aliases": ["primary dns"],
                        "tags": ["dns", "primary"],
                        "supported_actions": ["ssh_command"],
                    },
                ),
                SimpleNamespace(
                    score=0.81,
                    payload={
                        "scope": "connection",
                        "kind": "ssh",
                        "ref": "pihole2",
                        "title": "Secondary DNS",
                        "description": "Pi-hole Secondary DNS",
                        "aliases": ["secondary dns"],
                        "tags": ["dns", "secondary"],
                        "supported_actions": ["ssh_command"],
                    },
                ),
            ]

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            assert inputs == ["which dns server should handle uptime"]
            return SimpleNamespace(vectors=[[0.1, 0.2, 0.3]], usage={}, model="openai/embed-small")

    class FakeLLMClient:
        async def chat(self, messages: list[dict[str, str]], **_kwargs: object) -> object:
            llm_messages.extend(messages)
            return SimpleNamespace(
                content='{"kind":"ssh","ref":"pihole1","capability":"ssh_command","confidence":"high","ask_user":false,"reason":"primary dns alias matches best"}'
            )

    meta = asyncio.run(
        run_connection_routing_query(
            settings,
            "which dns server should handle uptime",
            preferred_kind="ssh",
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
            llm_client=FakeLLMClient(),
            language="en",
        )
    )

    assert meta["llm_debug"]["available"] is True
    assert meta["llm_debug"]["used"] is True
    assert meta["llm_debug"]["status"] == "ok"
    assert meta["llm_debug"]["decision"]["kind"] == "ssh"
    assert meta["llm_debug"]["decision"]["ref"] == "pihole1"
    assert meta["llm_debug"]["decision"]["capability"] == "ssh_command"
    assert meta["llm_debug"]["confidence"] == "high"
    assert "Bounded routing candidates:" in llm_messages[1]["content"]
    assert "ssh/pihole1" in llm_messages[1]["content"]
    assert "ssh/pihole2" in llm_messages[1]["content"]


def test_routing_admin_llm_dry_run_can_ignore_deterministic_hint() -> None:
    settings = Settings.model_validate(
        {
            "aria": {"public_url": "http://aria.black.lan:8810"},
            "llm": {"model": "fake"},
            "embeddings": {"model": "embed-small", "api_base": "http://litellm:4000"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {
                    "pihole1": {
                        "host": "pihole1.lan",
                        "user": "root",
                        "description": "Primary DNS",
                        "aliases": ["pihole1", "primary dns"],
                        "tags": ["dns", "primary"],
                    },
                    "pihole2": {
                        "host": "pihole2.lan",
                        "user": "root",
                        "description": "Secondary DNS",
                        "aliases": ["pihole2", "secondary dns"],
                        "tags": ["dns", "secondary"],
                    },
                }
            },
        }
    )
    collection = routing_connections_collection_name(settings)
    llm_messages: list[dict[str, str]] = []

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
                    score=0.92,
                    payload={
                        "scope": "connection",
                        "kind": "ssh",
                        "ref": "pihole1",
                        "title": "Primary DNS",
                        "description": "Pi-hole Primary DNS",
                        "aliases": ["primary dns"],
                        "tags": ["dns", "primary"],
                        "supported_actions": ["ssh_command"],
                    },
                ),
                SimpleNamespace(
                    score=0.81,
                    payload={
                        "scope": "connection",
                        "kind": "ssh",
                        "ref": "pihole2",
                        "title": "Secondary DNS",
                        "description": "Pi-hole Secondary DNS",
                        "aliases": ["secondary dns"],
                        "tags": ["dns", "secondary"],
                        "supported_actions": ["ssh_command"],
                    },
                ),
            ]

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            assert inputs == ["Run uptime on pihole1"]
            return SimpleNamespace(vectors=[[0.1, 0.2, 0.3]], usage={}, model="openai/embed-small")

    class FakeLLMClient:
        async def chat(self, messages: list[dict[str, str]], **_kwargs: object) -> object:
            llm_messages.extend(messages)
            return SimpleNamespace(
                content='{"kind":"ssh","ref":"pihole1","capability":"ssh_command","confidence":"high","ask_user":false,"reason":"qdrant candidate still matches best"}'
            )

    meta = asyncio.run(
        run_connection_routing_query(
            settings,
            "Run uptime on pihole1",
            preferred_kind="ssh",
            llm_ignore_deterministic=True,
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
            llm_client=FakeLLMClient(),
            language="en",
        )
    )

    assert meta["deterministic"]["found"] is True
    assert meta["decision"]["kind"] == "ssh"
    assert meta["decision"]["ref"] == "pihole1"
    assert meta["llm_ignore_deterministic"] is True
    assert meta["llm_debug"]["mode"] == "qdrant_only"
    assert meta["llm_debug"]["deterministic_hint_used"] is False
    assert "Deterministic hint: -" in llm_messages[1]["content"]
    assert "source=exact_ref" not in llm_messages[1]["content"]
    assert "source=qdrant_routing" in llm_messages[1]["content"]


def test_routing_admin_includes_action_planner_dry_run() -> None:
    settings = Settings.model_validate(
        {
            "aria": {"public_url": "http://aria.black.lan:8810"},
            "llm": {"model": "fake"},
            "embeddings": {"model": "embed-small", "api_base": "http://litellm:4000"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {
                    "pihole1": {
                        "host": "pihole1.lan",
                        "user": "root",
                        "description": "Primary DNS",
                        "aliases": ["pihole1", "primary dns"],
                        "tags": ["dns", "primary"],
                    }
                }
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
            assert query == [0.1, 0.2, 0.3]
            assert limit == 20
            return [
                SimpleNamespace(
                    score=0.87,
                    payload={
                        "scope": "connection",
                        "kind": "ssh",
                        "ref": "pihole1",
                        "title": "Primary DNS",
                        "description": "Pi-hole Primary DNS",
                        "aliases": ["primary dns"],
                        "tags": ["dns", "primary"],
                        "supported_actions": ["ssh_command"],
                    },
                )
            ]

    class FakeEmbedder:
        async def embed(self, inputs: list[str], **_kwargs: object) -> object:
            assert inputs == ["pruef mal den pi-hole"]
            return SimpleNamespace(vectors=[[0.1, 0.2, 0.3]], usage={}, model="openai/embed-small")

    class FakeLLMClient:
        async def chat(self, _messages: list[dict[str, str]], **kwargs: object) -> object:
            operation = str(kwargs.get("operation", "") or "")
            if operation == "routing_debug":
                return SimpleNamespace(
                    content='{"kind":"ssh","ref":"pihole1","capability":"ssh_command","confidence":"high","ask_user":false,"reason":"ssh target matches best"}'
                )
            if operation == "action_plan_debug":
                return SimpleNamespace(
                    content='{"candidate_kind":"template","candidate_id":"ssh_health_check","intent":"health_check","confidence":"high","ask_user":false,"reason":"health check fits this request"}'
                )
            raise AssertionError(f"unexpected operation: {operation}")

    meta = asyncio.run(
        run_connection_routing_query(
            settings,
            "pruef mal den pi-hole",
            preferred_kind="ssh",
            qdrant_client=FakeQdrant(),
            embedding_client=FakeEmbedder(),
            llm_client=FakeLLMClient(),
            language="de",
        )
    )

    assert meta["action_debug"]["available"] is True
    assert meta["action_debug"]["used"] is True
    assert meta["action_debug"]["status"] == "ok"
    assert meta["action_debug"]["decision"]["candidate_kind"] == "template"
    assert meta["action_debug"]["decision"]["candidate_kind_label"] == "Template"
    assert meta["action_debug"]["decision"]["candidate_id"] == "ssh_health_check"
    assert meta["action_debug"]["decision"]["intent_label"] == "Gesundheitscheck"
    assert meta["action_debug"]["decision"]["capability"] == "ssh_command"
    assert meta["action_debug"]["decision"]["capability_label"] == "SSH-Befehl"
    assert meta["action_debug"]["decision"]["summary_line"] == "Template: Gesundheitscheck via SSH-Befehl auf ssh/pihole1"
    assert meta["action_debug"]["decision"]["inputs"] == {"command": "uptime"}
    assert meta["action_debug"]["decision"]["input_items"] == [{"key": "command", "key_label": "Befehl", "value": "uptime"}]
    assert meta["action_debug"]["decision"]["execution_state"] == "ready"
    assert meta["action_debug"]["decision"]["execution_state_label"] == "Bereit"
    assert meta["action_debug"]["decision"]["preview"] == "SSH-Befehl: uptime"
    assert meta["action_debug"]["confidence_label"] == "Hoch"
    assert meta["action_debug"]["planner_source"] == "llm"
    assert meta["action_debug"]["planner_source_label"] == "LLM"
    assert meta["action_debug"]["execution_state"] == "ready"
    assert meta["action_debug"]["execution_state_label"] == "Bereit"
    assert meta["action_debug"]["target_context"] == "ssh/pihole1"
    assert meta["action_debug"]["target_reason"] == "single configured profile"
    assert meta["payload_debug"]["used"] is True
    assert meta["payload_debug"]["status"] == "ok"
    assert meta["payload_debug"]["payload"]["capability"] == "ssh_command"
    assert meta["payload_debug"]["payload"]["content"] == "uptime"
    assert meta["safety_debug"]["used"] is True
    assert meta["safety_debug"]["decision"]["action"] == "allow"
    assert meta["execution_debug"]["used"] is True
    assert meta["execution_debug"]["decision"]["next_step"] == "allow"
    assert meta["decision"]["ref"] == "pihole1"
