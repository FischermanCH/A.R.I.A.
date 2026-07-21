from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aria.core.config import Settings
from aria.core.aria_turn_arbitration import build_aria_turn_menu
from aria.core.aria_turn_arbitration import AriaTurnArbitration, AriaTurnPlan
from aria.core.agentic_context_runtime import AgenticContextRuntimeMixin
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.context_surfaces import ContextRequest
from aria.core.doc_meta_catalog import DocumentMetaCatalogStore, document_meta_collection_for_user
from aria.core.inventory_admin import rebuild_inventory_index
from aria.core.inventory_index import inventory_collection_name
from aria.core.meta_catalog import MetaCatalogStore, build_meta_catalog_documents, meta_catalog_collection_name, meta_catalog_documents_fingerprint
from aria.core.meta_catalog_routing import META_CATALOG_ROUTING_OPERATION
from aria.core.meta_catalog_routing import MetaCatalogRouter, MetaCatalogRoutingConfig, MetaCatalogRoutingInput
from aria.core.pipeline import Pipeline
from aria.skills.base import SkillResult


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
            server = 1.0 if any(token in lower for token in ("server", "ssh", "health", "updates")) else 0.0
            source = 1.0 if any(token in lower for token in ("rss", "source", "security")) else 0.0
            docs = 1.0 if any(token in lower for token in ("wireless", "heizung", "heizungen", "mill", "dokument", "document")) else 0.0
            vectors.append([server, source, docs])
        return FakeEmbeddingResponse(vectors)


class TrackingEmbeddingClient(FakeEmbeddingClient):
    def __init__(self) -> None:
        self.inputs: list[str] = []

    async def embed(self, inputs, **kwargs):  # noqa: ANN001
        self.inputs.extend(str(text or "") for text in inputs)
        return await super().embed(inputs, **kwargs)


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, object]] = {}

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    async def create_collection(self, collection_name: str, vectors_config) -> None:  # noqa: ANN001
        self.collections[collection_name] = {"size": int(vectors_config.size), "points": []}

    async def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)

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

    @staticmethod
    def _matches_filter(payload: dict[str, object], query_filter: object | None) -> bool:
        if not query_filter or not getattr(query_filter, "must", None):
            return True
        for condition in getattr(query_filter, "must", []) or []:
            key = str(getattr(condition, "key", "") or "")
            match = getattr(condition, "match", None)
            if key and match is not None and payload.get(key) != getattr(match, "value", None):
                return False
        return True

    async def query_points(self, collection_name: str, query: list[float], limit: int = 5, query_filter=None):  # noqa: ANN001
        rows = []
        for point in list(self.collections.get(collection_name, {}).get("points", []) or []):
            payload = getattr(point, "payload", {}) or {}
            if not self._matches_filter(payload, query_filter):
                continue
            vector = list(getattr(point, "vector", []) or [])
            score = sum(float(a) * float(b) for a, b in zip(vector, query, strict=False))
            rows.append(SimpleNamespace(id=getattr(point, "id", ""), payload=payload, score=score))
        rows.sort(key=lambda item: item.score, reverse=True)
        return SimpleNamespace(points=rows[:limit])

    async def delete(self, collection_name: str, points_selector=None, wait: bool = True):  # noqa: ANN001, ARG002
        ids = {str(point_id) for point_id in getattr(points_selector, "points", []) or []}
        current = list(self.collections.get(collection_name, {}).get("points", []) or [])
        self.collections.setdefault(collection_name, {"size": 0, "points": []})["points"] = [
            point for point in current if str(getattr(point, "id", "")) not in ids
        ]


class FakeChatResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}


class FakeRoutingLLM:
    def __init__(self, content: str | list[str]) -> None:
        self.contents = list(content) if isinstance(content, list) else [content]
        self.calls: list[dict[str, object]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.calls.append({"messages": messages, "kwargs": kwargs})
        index = min(len(self.calls) - 1, len(self.contents) - 1)
        return FakeChatResponse(self.contents[index])


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {
                    "mgmt-ssh": {
                        "host": "192.0.2.20",
                        "user": "admin",
                        "title": "Management Server",
                        "description": "Linux host for management and monitoring tasks at https://mgmt.example.invalid",
                        "aliases": ["management", "mgmt", "192.0.2.20"],
                        "tags": ["server", "monitoring", "192.0.2.20"],
                    }
                },
                "rss": {
                    "security-feed": {
                        "feed_url": "https://example.invalid/security.xml",
                        "title": "Security Feed",
                        "description": "Security advisories",
                        "tags": ["Security", "CVE"],
                    }
                },
            },
        }
    )


def test_meta_catalog_documents_describe_connections_without_secret_targets() -> None:
    docs = build_meta_catalog_documents(_settings())
    ssh = next(doc for doc in docs if doc.entity_type == "connection" and doc.kind == "ssh" and doc.ref == "mgmt-ssh")
    text = ssh.text

    assert ssh.surface_id == "connections"
    assert "server" in [item.lower() for item in ssh.knows]
    assert "health check" in ssh.can_do
    assert "ssh_run_command" in ssh.action_candidates
    assert ssh.confirmation_policy == "confirmation_required_for_commands_and_multi_target_checks"
    assert "192.0.2.20" not in text
    assert "mgmt.example.invalid" not in text
    assert "admin@" not in text
    assert "Management Server" in text


def test_meta_catalog_connections_surface_carries_german_inventory_signal() -> None:
    docs = build_meta_catalog_documents(_settings())
    surface = next(doc for doc in docs if doc.catalog_id == "surface|connections")

    assert surface.surface_id == "connections"
    assert "Verbindungen" in surface.text
    assert "bekannte Verbindungen" in surface.text


def test_connection_inventory_normalizer_requires_contract_signal() -> None:
    by_catalog_id = {
        "local|docs|document|wrong": {"surface_id": "docs", "kind": "document"},
        "connection|rss|security-feed": {"surface_id": "connections", "kind": "rss"},
    }
    message = "was habe ich für news feed für it security?"

    assert not MetaCatalogRouter._looks_like_connection_inventory_question(
        message,
        requested_surfaces=("docs",),
        selected_catalog_ids=("local|docs|document|wrong",),
        by_catalog_id=by_catalog_id,
        context_requests=(),
    )
    assert MetaCatalogRouter._looks_like_connection_inventory_question(
        message,
        requested_surfaces=("docs",),
        selected_catalog_ids=("connection|rss|security-feed",),
        by_catalog_id=by_catalog_id,
        context_requests=(),
    )
    assert MetaCatalogRouter._looks_like_connection_inventory_question(
        message,
        requested_surfaces=("docs",),
        selected_catalog_ids=("local|docs|document|wrong",),
        by_catalog_id=by_catalog_id,
        context_requests=(ContextRequest(surface_id="connections", mode="inventory", query=message),),
    )


def test_meta_catalog_documents_include_local_context_families() -> None:
    docs = build_meta_catalog_documents(_settings())
    catalog_ids = {doc.catalog_id for doc in docs}

    assert "local|memory|facts" in catalog_ids
    assert "local|memory|preferences" in catalog_ids
    assert "local|learning|reflections" in catalog_ids
    assert "local|notes|user_notes" in catalog_ids
    assert "local|docs|documents" in catalog_ids
    preferences = next(doc for doc in docs if doc.catalog_id == "local|memory|preferences")
    assert preferences.surface_id == "memory"
    assert "preferences" in [item.lower() for item in preferences.knows]
    assert preferences.loader_contract


def test_meta_catalog_rebuild_uses_own_collection_and_hash() -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))

    result = asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs), backup_collection_name=meta_catalog_collection_name(settings, backup=True)))

    assert result["documents"] == len(docs)
    assert result["collection"] == meta_catalog_collection_name(settings)
    assert result["meta_catalog_hash"]
    points = qdrant.collections[meta_catalog_collection_name(settings)]["points"]
    assert points
    payload = getattr(points[0], "payload", {})
    assert payload["meta_catalog_version"] == 1
    assert payload["meta_catalog_hash"] == result["meta_catalog_hash"]


def test_meta_catalog_store_can_query_catalog_hits() -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    hits = asyncio.run(store.query_catalog("server ssh health", limit=3))

    assert hits
    assert hits[0]["source"] == "qdrant_meta_catalog"
    assert hits[0]["payload"]["catalog_id"]


def test_document_meta_catalog_rebuild_keeps_active_and_previous_only() -> None:
    qdrant = FakeQdrant()
    store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    first = asyncio.run(
        store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "doc-1",
                    "document_name": "mill-heizung-handbuch.pdf",
                    "guide_summary": "Mill Heizung Wireless verbinden und WLAN einrichten.",
                    "guide_keywords": ["Mill", "Heizung", "Wireless", "WLAN"],
                    "target_collection": "aria_docs_example_user",
                    "source_type": "pdf",
                }
            ],
        )
    )
    second = asyncio.run(
        store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "doc-1",
                    "document_name": "mill-heizung-handbuch.pdf",
                    "guide_summary": "Mill Heizung Wireless verbinden und WLAN einrichten.",
                    "guide_keywords": ["Mill", "Heizung", "Wireless", "WLAN"],
                    "target_collection": "aria_docs_example_user",
                    "source_type": "pdf",
                }
            ],
        )
    )
    third = asyncio.run(
        store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "doc-1",
                    "document_name": "mill-heizung-handbuch.pdf",
                    "guide_summary": "Mill Heizung Wireless verbinden und WLAN einrichten.",
                    "guide_keywords": ["Mill", "Heizung", "Wireless", "WLAN"],
                    "target_collection": "aria_docs_example_user",
                    "source_type": "pdf",
                }
            ],
        )
    )

    assert first["status"] == "active"
    assert second["previous_build_id"] == first["active_build_id"]
    assert third["previous_build_id"] == second["active_build_id"]
    points = qdrant.collections[document_meta_collection_for_user("example_user")]["points"]
    build_ids = {
        str((getattr(point, "payload", {}) or {}).get("catalog_build_id", ""))
        for point in points
        if (getattr(point, "payload", {}) or {}).get("kind") == "document_meta"
    }
    assert build_ids == {second["active_build_id"], third["active_build_id"]}


def test_document_meta_catalog_query_returns_active_docs_only() -> None:
    qdrant = FakeQdrant()
    store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "doc-1",
                    "document_name": "mill-heizung-handbuch.pdf",
                    "guide_summary": "Mill Heizung Wireless verbinden.",
                    "guide_keywords": ["Mill", "Heizung", "Wireless"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    hits = asyncio.run(store.query_catalog("wie kriege ich meine heizungen ans wireless", user_id="example_user", limit=3))

    assert hits
    assert hits[0]["source"] == "qdrant_doc_meta_catalog"
    assert hits[0]["surface_id"] == "docs"
    assert hits[0]["payload"]["document_name"] == "mill-heizung-handbuch.pdf"

    empty = asyncio.run(store.rebuild_from_guides(user_id="example_user", guides=[]))
    empty_hits = asyncio.run(store.query_catalog("wie kriege ich meine heizungen ans wireless", user_id="example_user", limit=3))

    assert empty["status"] == "active"
    assert empty["documents"] == 0
    assert empty_hits == []


def test_document_meta_catalog_normalizes_user_id_for_collection_and_filter() -> None:
    qdrant = FakeQdrant()
    assert document_meta_collection_for_user("Example_User") == document_meta_collection_for_user("example_user")
    store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("Example_User"),
    )
    asyncio.run(
        store.rebuild_from_guides(
            user_id="Example_User",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "Example_User",
                    "document_id": "mill-manual",
                    "document_name": "Mill Gentle Air WiFi oil filled_Nordic_2025_print.pdf",
                    "guide_summary": "Mill heater WiFi setup instructions.",
                    "guide_keywords": ["Mill", "WiFi", "heater"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    hits = asyncio.run(
        store.query_catalog("wie kriege ich meine heizungen ans wireless", user_id="example_user", limit=3)
    )
    reverse_hits = asyncio.run(
        store.query_catalog("wie kriege ich meine heizungen ans wireless", user_id="Example_User", limit=3)
    )

    assert hits
    assert reverse_hits
    assert hits[0]["payload"]["user_id"] == "example_user"
    assert reverse_hits[0]["payload"]["document_id"] == "mill-manual"
    assert "heizung" in reverse_hits[0]["payload"]["knows"]
    assert "wlan" in reverse_hits[0]["payload"]["knows"]


def test_document_meta_catalog_query_keeps_legacy_cased_payload_user() -> None:
    qdrant = FakeQdrant()
    store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        store.rebuild_from_guides(
            user_id="Example_User",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "Example_User",
                    "document_id": "mill-manual",
                    "document_name": "Mill Gentle Air WiFi oil filled_Nordic_2025_print.pdf",
                    "guide_summary": "Mill heater WiFi setup instructions.",
                    "guide_keywords": ["Mill", "WiFi", "heater"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )
    points = qdrant.collections[document_meta_collection_for_user("example_user")]["points"]
    for point in points:
        payload = getattr(point, "payload", {}) or {}
        if payload.get("kind") == "document_meta":
            payload["user_id"] = "Example_User"

    hits = asyncio.run(
        store.query_catalog("wie kriege ich meine heizungen ans wireless", user_id="Example_User", limit=3)
    )

    assert hits
    assert hits[0]["payload"]["document_id"] == "mill-manual"


def test_meta_catalog_router_uses_catalog_before_legacy_turn_arbiter(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["connection|ssh|mgmt-ssh"],
          "context_requests": [{"catalog_id": "connection|ssh|mgmt-ssh", "surface_id": "connections", "mode": "action", "query": "server health"}],
          "intents": ["runtime_action"],
          "surfaces": ["connections"],
          "actions": ["ssh_run_command"],
          "target_scope_authority": "explicit_refs",
          "answer_mode": "plan_action",
          "context_depth": "shallow",
          "contract": {"mode": "action", "evidence_policy": "source_bound"},
          "risk": "medium",
          "needs_confirmation": true,
          "confidence": 0.91,
          "reason": "ssh server action"
        }
        """
    )
    menu = build_aria_turn_menu(connection_kinds=("ssh",))

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="wie geht es meinem management server",
                menu=menu,
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.context_requests
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "action"
    assert "ssh_run_command" in arbitration.plan.actions
    assert arbitration.plan.contract_mode == "action"
    assert arbitration.plan.evidence_policy == "source_bound"
    assert arbitration.plan.target_scope_authority == "explicit_refs"
    assert "contract_mode=action" in arbitration.debug_line
    assert arbitration.diagnostics["payload_bytes"] > 0
    assert arbitration.diagnostics["llm_input_contract_v1"] == 1
    assert arbitration.diagnostics["llm_input_world_meta_catalog"] >= 1
    assert "routing_payload_bytes=" in arbitration.debug_line
    assert "llm_input_contract=v1" in arbitration.debug_line
    assert arbitration.plan.needs_confirmation is True
    assert llm.calls[0]["kwargs"]["operation"] == META_CATALOG_ROUTING_OPERATION
    payload = llm.calls[0]["messages"][1]["content"]
    assert "llm_input_contract" in payload
    assert "llm_input_v1" in payload
    assert "canonical_input" in payload
    assert "meta_catalog_select_context_requests" in payload
    assert "normalizer_is_not_router" in payload
    assert "top_level_payload_fields_are_legacy_mirrors" in payload
    assert "top_level_payload_fields_removed" in payload
    assert "allowed_catalog_ids" in payload
    assert "connection|ssh|mgmt-ssh" in payload


def test_meta_catalog_router_uses_visible_chat_context_for_elliptic_action_followup(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    embedding = TrackingEmbeddingClient()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=embedding, collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))
    embedding.inputs.clear()

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["connection|ssh|mgmt-ssh"],
          "context_requests": [{"catalog_id": "connection|ssh|mgmt-ssh", "surface_id": "connections", "mode": "action", "query": "inspect /tmp on mgmt-ssh"}],
          "intents": ["runtime_action"],
          "surfaces": ["connections"],
          "actions": ["ssh_run_command"],
          "answer_mode": "plan_action",
          "context_depth": "shallow",
          "contract": {"mode": "action", "evidence_policy": "source_bound"},
          "risk": "medium",
          "needs_confirmation": true,
          "confidence": 0.94,
          "reason": "follow-up to visible ssh output"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(
            settings=settings,
            embedding_client=embedding,
            llm_client=llm,
            config=MetaCatalogRoutingConfig(candidate_limit=1),
        ).route(
            MetaCatalogRoutingInput(
                message="3.6G /tmp was liegt da alles rum",
                menu=build_aria_turn_menu(connection_kinds=("ssh",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
                turn_context={
                    "recent_visible_chat_context": {
                        "messages": [
                            {
                                "role": "assistant",
                                "text": "[Stored Recipe SSH] SSH Command\nConnection: mgmt-ssh\nSTDOUT:\n15G\t/\n3.6G\t/tmp",
                                "badge_intent": "ssh_command",
                            }
                        ]
                    }
                },
            )
        )
    )

    payload = str(llm.calls[0]["messages"][1]["content"])
    assert any("Connection: mgmt-ssh" in text for text in embedding.inputs)
    assert "recent_visible_chat_context" in payload
    assert "3.6G" in payload
    assert "connection|ssh|mgmt-ssh" in payload
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.priority == ("connection|ssh|mgmt-ssh",)
    assert arbitration.plan.actions == ("ssh_run_command",)
    assert arbitration.plan.contract_mode == "action"


def test_meta_catalog_router_includes_user_document_meta_without_explicit_docs(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "mill-manual",
                    "document_name": "mill-heizung-handbuch.pdf",
                    "guide_summary": "Bedienungsanleitung: Mill Heizung mit Wireless/WLAN verbinden.",
                    "guide_keywords": ["Mill", "Heizung", "Wireless", "WLAN"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["local|docs|document|mill-manual"],
          "context_requests": [{"catalog_id": "local|docs|document|mill-manual", "surface_id": "docs", "mode": "search", "query": "wie kriege ich meine heizungen ans wireless"}],
          "intents": ["local_retrieval"],
          "surfaces": ["docs"],
          "actions": [],
          "answer_mode": "direct_answer",
          "context_depth": "shallow",
          "contract": {"mode": "answer", "evidence_policy": "source_bound"},
          "risk": "low",
          "needs_confirmation": false,
          "confidence": 0.92,
          "reason": "user document meta matches wireless heating"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="wie kriege ich meine heizungen ans wireless",
                menu=build_aria_turn_menu(),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    payload = llm.calls[0]["messages"][1]["content"]
    assert "mill-heizung-handbuch.pdf" in str(payload)
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.context_requests[0].surface_id == "docs"
    assert arbitration.plan.priority == ("local|docs|document|mill-manual",)


def test_meta_catalog_router_keeps_llm_connection_plan_over_doc_meta_overlap(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                }
            },
        }
    )
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "arlo-manual",
                    "document_name": "Arlo Ultra_User_Manual_en.pdf",
                    "guide_summary": "Camera manual mentioning Syncthing only in unrelated local document text.",
                    "guide_keywords": ["camera", "syncthing", "manual"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["connection|sftp|sync-node-01"],
          "context_requests": [{"catalog_id": "connection|sftp|sync-node-01", "surface_id": "connections", "mode": "inventory", "query": "welche verbindungen kennst du für syncthing"}],
          "intents": ["chat"],
          "surfaces": ["connections"],
          "actions": [],
          "answer_mode": "direct_answer",
          "context_depth": "shallow",
          "contract": {"mode": "answer", "evidence_policy": "source_bound"},
          "risk": "low",
          "needs_confirmation": false,
          "confidence": 0.92,
          "reason": "User asks which Syncthing connections are known. Two connections match: SFTP and SSH"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="welche verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("ssh", "sftp")),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="Example_User",
                request_id="test",
            )
        )
    )

    payload = llm.calls[0]["messages"][1]["content"]
    assert "local|docs|document|arlo-manual" in str(payload)
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("connections",)
    assert arbitration.plan.context_directions == ("connections",)
    assert arbitration.plan.priority == ("connection|sftp|sync-node-01",)
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.context_requests[0].budget["catalog_hint_ids"] == ["connection|sftp|sync-node-01"]


def test_meta_catalog_surface_review_recovers_connection_inventory_from_wrong_docs_choice(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "arlo-manual",
                    "document_name": "Arlo Ultra_User_Manual_en.pdf",
                    "guide_summary": "Camera manual unrelated to configured server connections.",
                    "guide_keywords": ["camera", "manual"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|arlo-manual"],
              "context_requests": [{"catalog_id": "local|docs|document|arlo-manual", "surface_id": "docs", "mode": "search", "query": "welche verbindungen kennst du für syncthing"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "wrong document surface"
            }
            """,
            """
            {
              "use_connections_inventory": true,
              "catalog_ids": ["connection|sftp|sync-node-01"],
              "query": "welche verbindungen kennst du für syncthing",
              "confidence": 0.94,
              "reason": "configured connection profile question"
            }
            """,
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="welche verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("sftp",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    review_payload = llm.calls[1]["messages"][1]["content"]
    assert "wrong document surface" in review_payload
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("connections",)
    assert arbitration.plan.context_directions == ("connections",)
    assert arbitration.plan.priority == ("connection|sftp|sync-node-01",)
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.context_requests[0].budget["meta_contract_normalized"] == "surface_contract_review"
    assert arbitration.plan.context_requests[0].budget["surface_review_from"] == "docs"
    assert arbitration.plan.context_requests[0].budget["surface_review_to"] == "connections"


def test_meta_catalog_surface_review_uses_connections_surface_descriptor_when_specific_connection_not_in_candidates(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    meta_collection = meta_catalog_collection_name(settings)
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_collection,
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))
    qdrant.collections[meta_collection]["points"] = [
        point
        for point in list(qdrant.collections[meta_collection]["points"])
        if str((getattr(point, "payload", {}) or {}).get("catalog_id", "")) != "connection|sftp|sync-node-01"
    ]
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "arlo-manual",
                    "document_name": "Arlo Ultra_User_Manual_en.pdf",
                    "guide_summary": "Camera manual unrelated to configured server connections.",
                    "guide_keywords": ["camera", "manual"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|arlo-manual"],
              "context_requests": [{"catalog_id": "local|docs|document|arlo-manual", "surface_id": "docs", "mode": "search", "query": "welche verbindungen kennst du für syncthing"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "wrong document surface while the connections surface is relevant"
            }
            """,
            """
            {
              "use_connections_inventory": true,
              "catalog_ids": ["surface|connections"],
              "query": "welche verbindungen kennst du für syncthing",
              "confidence": 0.91,
              "reason": "user asks for configured connections, and only the connections surface descriptor is available"
            }
            """,
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="welche verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("sftp",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    assert "surface|connections" in llm.calls[1]["messages"][1]["content"]
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("connections",)
    assert arbitration.plan.context_directions == ("connections",)
    assert arbitration.plan.priority == ("surface|connections",)
    request = arbitration.plan.context_requests[0]
    assert request.surface_id == "connections"
    assert request.mode == "inventory"
    assert request.budget["meta_contract_normalized"] == "surface_contract_review"
    assert request.budget["catalog_hint_ids"] == ["surface|connections"]


def test_meta_catalog_surface_review_recovers_connection_hits_from_meta_collection(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|wrong"],
              "context_requests": [{"catalog_id": "local|docs|document|wrong", "surface_id": "docs", "mode": "search", "query": "welche verbindungen kennst du für syncthing"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "connection entries are acknowledged in prose but the structured plan still selected docs"
            }
            """,
            """
            {
              "use_connections_inventory": true,
              "catalog_ids": ["connection|sftp|sync-node-01"],
              "query": "welche verbindungen kennst du für syncthing",
              "confidence": 0.94,
              "reason": "the recovered meta-catalog connection entry is the correct surface evidence"
            }
            """,
        ]
    )
    router = MetaCatalogRouter(
        settings=settings,
        embedding_client=FakeEmbeddingClient(),
        llm_client=llm,
        config=MetaCatalogRoutingConfig(candidate_limit=1),
    )

    async def fake_initial_query(_query, *, user_id="", contextual_query=""):  # noqa: ANN001, ARG001
        return [
            {
                "catalog_id": "local|docs|document|wrong",
                "surface_id": "docs",
                "kind": "document",
                "ref": "wrong",
                "score": 1.0,
                "source": "qdrant_meta_catalog",
                "payload": {
                    "catalog_id": "local|docs|document|wrong",
                    "entity_type": "document",
                    "surface_id": "docs",
                    "kind": "document",
                    "ref": "wrong",
                    "title": "Wrong document",
                    "description": "Unrelated document candidate",
                    "document_id": "wrong",
                    "document_name": "Wrong.pdf",
                    "target_collection": "aria_docs_example_user",
                    "text": "Wrong document unrelated to connections.",
                },
            }
        ], ""

    router._query_meta_catalog = fake_initial_query  # type: ignore[method-assign]

    arbitration = asyncio.run(
        router.route(
            MetaCatalogRoutingInput(
                message="welche verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("sftp",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    review_payload = llm.calls[1]["messages"][1]["content"]
    assert "connection|sftp|sync-node-01" in review_payload
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("connections",)
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.priority == ("connection|sftp|sync-node-01",)
    assert arbitration.plan.context_requests[0].budget["catalog_hint_ids"] == ["connection|sftp|sync-node-01"]


def test_meta_catalog_surface_review_blocks_when_acknowledged_connection_evidence_is_not_recoverable(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["local|docs|document|wrong"],
          "context_requests": [{"catalog_id": "local|docs|document|wrong", "surface_id": "docs", "mode": "search", "query": "welche verbindungen kennst du für syncthing"}],
          "intents": ["local_retrieval"],
          "surfaces": ["docs"],
          "actions": [],
          "answer_mode": "direct_answer",
          "context_depth": "shallow",
          "contract": {"mode": "answer", "evidence_policy": "source_bound"},
          "risk": "low",
          "needs_confirmation": false,
          "confidence": 0.95,
          "reason": "User asks which connections ARIA knows for Syncthing. Two catalog entries match: SFTP and SSH"
        }
        """
    )
    router = MetaCatalogRouter(
        settings=settings,
        embedding_client=FakeEmbeddingClient(),
        llm_client=llm,
        config=MetaCatalogRoutingConfig(candidate_limit=1),
    )

    async def fake_initial_query(_query, *, user_id="", contextual_query=""):  # noqa: ANN001, ARG001
        return [
            {
                "catalog_id": "local|docs|document|wrong",
                "surface_id": "docs",
                "kind": "document",
                "ref": "wrong",
                "score": 1.0,
                "source": "qdrant_meta_catalog",
                "payload": {
                    "catalog_id": "local|docs|document|wrong",
                    "entity_type": "document",
                    "surface_id": "docs",
                    "kind": "document",
                    "ref": "wrong",
                    "title": "Wrong document",
                    "description": "Unrelated document candidate",
                    "document_id": "wrong",
                    "document_name": "Wrong.pdf",
                    "target_collection": "aria_docs_example_user",
                    "text": "Wrong document unrelated to connections.",
                },
            }
        ], ""

    router._query_meta_catalog = fake_initial_query  # type: ignore[method-assign]
    router._recover_connection_review_hits = AsyncMock(return_value=[])  # type: ignore[method-assign]

    arbitration = asyncio.run(
        router.route(
            MetaCatalogRoutingInput(
                message="welche verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("sftp",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == ["aria_meta_catalog_routing"]
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.needs_context is False
    assert arbitration.plan.context_directions == ()
    assert arbitration.plan.answer_mode == "ask_clarification"
    assert arbitration.plan.contract_mode == "clarify"
    assert arbitration.plan.context_requests[0].surface_id == "docs"
    assert arbitration.plan.context_requests[0].budget["surface_review_decision"] == "no_connection_evidence_recovered"
    assert "no_connection_evidence_recovered" in arbitration.plan.reason


def test_meta_catalog_surface_review_keeps_strong_specific_connection_candidate(monkeypatch) -> None:
    generic_servers = {
        f"aaa-generic-{index}": {
            "host": f"192.0.2.{index}",
            "user": "admin",
            "title": f"Generic Server {index}",
            "description": "Linux server inventory entry",
            "aliases": [f"generic server {index}"],
            "tags": ["server", "linux"],
        }
        for index in range(8)
    }
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {
                    **generic_servers,
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "sync-node-01",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "server", "file-sync"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|wrong"],
              "context_requests": [{"catalog_id": "local|docs|document|wrong", "surface_id": "docs", "mode": "search", "query": "welche server verbindungen kennst du für syncthing"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "wrong document surface"
            }
            """,
            """
            {
              "use_connections_inventory": true,
              "catalog_ids": ["connection|ssh|sync-node-01"],
              "query": "welche server verbindungen kennst du für syncthing",
              "confidence": 0.94,
              "reason": "specific configured syncthing connection candidate is present"
            }
            """,
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(
            settings=settings,
            embedding_client=FakeEmbeddingClient(),
            llm_client=llm,
            config=MetaCatalogRoutingConfig(candidate_limit=5),
        ).route(
            MetaCatalogRoutingInput(
                message="welche server verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("ssh",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    review_payload = llm.calls[1]["messages"][1]["content"]
    assert "connection|ssh|sync-node-01" in review_payload
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("connections",)
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.priority == ("connection|ssh|sync-node-01",)
    assert arbitration.plan.context_requests[0].budget["catalog_hint_ids"] == ["connection|ssh|sync-node-01"]


def test_meta_catalog_surface_review_keeps_real_document_question_on_docs(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "syncthing-manual",
                    "document_name": "Syncthing Manual.pdf",
                    "guide_summary": "Syncthing documentation and manual content.",
                    "guide_keywords": ["Syncthing", "Manual", "Dokumentation"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|syncthing-manual"],
              "context_requests": [{"catalog_id": "local|docs|document|syncthing-manual", "surface_id": "docs", "mode": "search", "query": "was steht im syncthing manual"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "document content question"
            }
            """,
            """
            {
              "use_connections_inventory": false,
              "catalog_ids": [],
              "query": "was steht im syncthing manual",
              "confidence": 0.90,
              "reason": "user asks for manual content"
            }
            """,
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="was steht im syncthing manual?",
                menu=build_aria_turn_menu(connection_kinds=("sftp",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("docs",)
    assert arbitration.plan.context_directions == ("docs",)
    assert arbitration.plan.priority == ("local|docs|document|syncthing-manual",)
    assert arbitration.plan.context_requests[0].surface_id == "docs"
    assert arbitration.plan.context_requests[0].budget["meta_contract_normalized"] == "surface_contract_review"
    assert arbitration.plan.context_requests[0].budget["surface_review_decision"] == "keep_local"
    assert arbitration.plan.context_requests[0].budget["surface_review_to"] == "local_context"


def test_meta_catalog_surface_review_blocks_unresolved_local_connection_conflict(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Syncthing file sync server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "arlo-manual",
                    "document_name": "Arlo Ultra_User_Manual_en.pdf",
                    "guide_summary": "Camera manual unrelated to configured server connections.",
                    "guide_keywords": ["camera", "manual"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|arlo-manual"],
              "context_requests": [{"catalog_id": "local|docs|document|arlo-manual", "surface_id": "docs", "mode": "search", "query": "welche verbindungen kennst du für syncthing"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "User asks which connections ARIA knows for Syncthing. Two Syncthing connections found"
            }
            """,
            "not json",
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="welche verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("sftp",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.needs_context is False
    assert arbitration.plan.context_directions == ()
    assert arbitration.plan.answer_mode == "ask_clarification"
    assert arbitration.plan.contract_mode == "clarify"
    assert arbitration.plan.context_requests[0].surface_id == "docs"
    assert arbitration.plan.context_requests[0].budget["surface_review_decision"] == "review_unavailable"
    assert "review_unavailable" in arbitration.plan.reason


def test_meta_catalog_surface_review_blocks_when_review_keeps_self_contradictory_local_plan(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "connections": {
                "ssh": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "sync-node-01",
                        "description": "Continuous file synchronization server",
                        "aliases": ["syncthing"],
                        "tags": ["syncthing", "file-sync"],
                    }
                },
                "sftp": {
                    "sync-node-01": {
                        "host": "192.0.2.40",
                        "user": "fischerman",
                        "title": "Syncthing Datei-Sync Server",
                        "description": "Dateisynchronisation",
                        "aliases": ["syncthing", "dateisync"],
                        "tags": ["syncthing", "file-sync"],
                    }
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = FakeQdrant()
    meta_store = MetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=meta_catalog_collection_name(settings),
    )
    asyncio.run(meta_store.rebuild_documents(build_meta_catalog_documents(settings), catalog_hash="catalog"))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "arlo-manual",
                    "document_name": "Arlo Ultra_User_Manual_en.pdf",
                    "guide_summary": "Camera manual unrelated to configured server connections.",
                    "guide_keywords": ["camera", "manual"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|arlo-manual"],
              "context_requests": [{"catalog_id": "local|docs|document|arlo-manual", "surface_id": "docs", "mode": "search", "query": "welche server verbindungen kennst du für syncthing"}],
              "intents": ["local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "low",
              "needs_confirmation": false,
              "confidence": 0.95,
              "reason": "User asks which server connections exist for Syncthing. Two catalog entries match: SFTP and SSH"
            }
            """,
            """
            {
              "use_connections_inventory": false,
              "catalog_ids": [],
              "query": "welche server verbindungen kennst du für syncthing",
              "confidence": 0.92,
              "reason": "kept local docs despite the router reason naming connection entries"
            }
            """,
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="welche server verbindungen kennst du für syncthing?",
                menu=build_aria_turn_menu(connection_kinds=("ssh", "sftp")),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.needs_context is False
    assert arbitration.plan.context_directions == ()
    assert arbitration.plan.answer_mode == "ask_clarification"
    assert arbitration.plan.contract_mode == "clarify"
    assert arbitration.plan.context_requests[0].surface_id == "docs"
    assert arbitration.plan.context_requests[0].budget["surface_review_decision"] == "self_contradictory_keep_local"
    assert "self_contradictory_keep_local" in arbitration.plan.reason


def test_meta_catalog_router_prefers_rss_inventory_over_wrong_docs_choice(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))
    doc_store = DocumentMetaCatalogStore(
        qdrant=qdrant,
        embedding_client=FakeEmbeddingClient(),
        collection_name=document_meta_collection_for_user("example_user"),
    )
    asyncio.run(
        doc_store.rebuild_from_guides(
            user_id="example_user",
            guides=[
                {
                    "source": "rag_document_guide",
                    "user_id": "example_user",
                    "document_id": "arlo-manual",
                    "document_name": "Arlo Ultra_User_Manual_en.pdf",
                    "guide_summary": "Security camera manual with camera feed settings.",
                    "guide_keywords": ["security", "camera", "feed"],
                    "target_collection": "aria_docs_example_user",
                }
            ],
        )
    )

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        [
            """
            {
              "needs_context": true,
              "catalog_ids": ["local|docs|document|arlo-manual"],
              "context_requests": [{"catalog_id": "local|docs|document|arlo-manual", "surface_id": "docs", "mode": "search", "query": "was habe ich für news feed für it security?"}],
              "intents": ["chat", "local_retrieval"],
              "surfaces": ["docs"],
              "actions": [],
              "answer_mode": "direct_answer",
              "context_depth": "shallow",
              "contract": {"mode": "answer", "evidence_policy": "source_bound"},
              "risk": "none",
              "needs_confirmation": false,
              "confidence": 0.92,
              "reason": "wrongly chose document mentioning security feed"
            }
            """,
            """
            {
              "use_connections_inventory": true,
              "catalog_ids": ["connection|rss|security-feed"],
              "query": "was habe ich für news feed für it security",
              "confidence": 0.93,
              "reason": "user asks which configured RSS/news feed connection exists for IT security"
            }
            """,
        ]
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="was habe ich für news feed für it security?",
                menu=build_aria_turn_menu(connection_kinds=("rss",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    payload = llm.calls[0]["messages"][1]["content"]
    assert "connection|rss|security-feed" in str(payload)
    assert [call["kwargs"]["operation"] for call in llm.calls] == [
        "aria_meta_catalog_routing",
        "meta_catalog_surface_contract_review",
    ]
    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("connections",)
    assert arbitration.plan.context_directions == ("connections",)
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.priority == ("connection|rss|security-feed",)
    assert arbitration.plan.context_requests[0].budget["catalog_hint_ids"] == ["connection|rss|security-feed"]


def test_meta_catalog_router_normalizes_explicit_rss_read_to_action(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["connection|rss|security-feed"],
          "context_requests": [{"catalog_id": "connection|rss|security-feed", "surface_id": "connections", "mode": "action", "query": "lies den feed security-feed"}],
          "intents": ["chat"],
          "surfaces": ["connections"],
          "actions": [],
          "answer_mode": "direct_answer",
          "context_depth": "shallow",
          "contract": {"mode": "action", "evidence_policy": "source_bound"},
          "risk": "low",
          "needs_confirmation": false,
          "confidence": 0.95,
          "reason": "explicit read-only rss feed request"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="lies den feed security-feed",
                menu=build_aria_turn_menu(connection_kinds=("rss",)),
                surface_registry=build_builtin_surface_registry(settings),
                user_id="example_user",
                request_id="test",
            )
        )
    )

    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.actions == ("rss_read_feed",)
    assert arbitration.plan.contract_mode == "action"
    assert arbitration.plan.needs_confirmation is False
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "action"
    assert arbitration.plan.context_requests[0].budget["kind"] == "rss"
    assert arbitration.plan.context_requests[0].budget["ref"] == "security-feed"


def test_meta_catalog_router_rejects_invalid_strict_action_contract(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": false,
          "catalog_ids": ["connection|ssh|mgmt-ssh"],
          "context_requests": [],
          "intents": ["chat"],
          "surfaces": ["chat"],
          "actions": [],
          "answer_mode": "direct_answer",
          "contract": {"mode": "action", "evidence_policy": "source_bound"},
          "confidence": 0.91,
          "reason": "broken action contract"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="wie fit ist mein server",
                menu=build_aria_turn_menu(connection_kinds=("ssh",)),
                surface_registry=build_builtin_surface_registry(settings),
            )
        )
    )

    assert arbitration.source == "fallback"
    assert arbitration.plan.reason == "meta_catalog_contract_invalid:action_without_action_candidate"


def test_meta_catalog_router_relaxed_contract_is_runtime_rollback(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": false,
          "catalog_ids": ["connection|ssh|mgmt-ssh"],
          "context_requests": [],
          "intents": ["chat"],
          "surfaces": ["chat"],
          "actions": [],
          "answer_mode": "direct_answer",
          "contract": {"mode": "action", "evidence_policy": "source_bound"},
          "confidence": 0.91,
          "reason": "broken but rollback mode allows old path"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(
            settings=settings,
            embedding_client=FakeEmbeddingClient(),
            llm_client=llm,
            config=MetaCatalogRoutingConfig(strict_contract_enabled=False),
        ).route(
            MetaCatalogRoutingInput(
                message="wie fit ist mein server",
                menu=build_aria_turn_menu(connection_kinds=("ssh",)),
                surface_registry=build_builtin_surface_registry(settings),
            )
        )
    )

    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.contract_mode == "action"


def test_meta_catalog_router_falls_back_when_catalog_is_empty(monkeypatch) -> None:
    settings = _settings()
    qdrant = FakeQdrant()

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM('{"needs_context": true, "confidence": 0.99}')

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="was weiss aria",
                menu=build_aria_turn_menu(),
                surface_registry=build_builtin_surface_registry(settings),
            )
        )
    )

    assert arbitration.source == "fallback"
    assert arbitration.plan.reason == "meta_catalog_empty"
    assert llm.calls == []


def test_meta_catalog_inventory_requests_stay_surface_level_with_catalog_hints(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": true,
          "catalog_ids": ["connection|rss|security-feed"],
          "context_requests": [
            {"catalog_id": "connection|rss|security-feed", "surface_id": "connections", "mode": "inventory", "query": "IT-Security"},
            {"catalog_id": "connection|rss|security-feed", "surface_id": "connections", "mode": "inventory", "query": "IT-Security"}
          ],
          "intents": ["chat", "context_inventory"],
          "surfaces": ["connections"],
          "actions": [],
          "answer_mode": "direct_answer",
          "contract": {"mode": "answer", "evidence_policy": "allow_general"},
          "confidence": 0.97,
          "reason": "broad inventory list"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="was für websites/rss habe ich unter beobachtung zum thema IT-Security?",
                menu=build_aria_turn_menu(connection_kinds=("rss",)),
                surface_registry=build_builtin_surface_registry(settings),
            )
        )
    )

    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.evidence_policy == "source_bound"
    assert len(arbitration.plan.context_requests) == 1
    request = arbitration.plan.context_requests[0]
    assert request.surface_id == "connections"
    assert request.mode == "inventory"
    assert "catalog_id" not in request.budget
    assert "ref" not in request.budget
    assert request.budget["catalog_hint_ids"] == ["connection|rss|security-feed"]


def test_meta_catalog_explicit_documents_surface_overrides_wrong_memory_choice(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": false,
          "catalog_ids": ["local|memory|facts"],
          "context_requests": [],
          "intents": ["chat"],
          "surfaces": ["memory"],
          "actions": [],
          "answer_mode": "direct_answer",
          "contract": {"mode": "answer", "evidence_policy": "allow_general"},
          "confidence": 0.95,
          "reason": "wrongly chose memory"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="was steht in meinen dokumenten zur UI-Regel?",
                menu=build_aria_turn_menu(),
                surface_registry=build_builtin_surface_registry(settings),
            )
        )
    )

    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.needs_context is True
    assert arbitration.plan.surfaces == ("docs",)
    assert arbitration.plan.context_directions == ("docs",)
    assert arbitration.plan.context_requests == (
        ContextRequest(
            surface_id="docs",
            mode="search",
            query="was steht in meinen dokumenten zur UI-Regel?",
            limit=12,
            budget={"explicit_source_surface": "docs"},
        ),
    )
    assert arbitration.plan.evidence_policy == "source_bound"


def test_meta_catalog_explicit_my_memory_surface_does_not_depend_on_catalog_choice(monkeypatch) -> None:
    settings = _settings()
    docs = build_meta_catalog_documents(settings)
    qdrant = FakeQdrant()
    store = MetaCatalogStore(qdrant=qdrant, embedding_client=FakeEmbeddingClient(), collection_name=meta_catalog_collection_name(settings))
    asyncio.run(store.rebuild_documents(docs, catalog_hash=meta_catalog_documents_fingerprint(docs)))

    async def fake_qdrant_factory(_settings, *, timeout=5):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr("aria.core.meta_catalog_routing.create_meta_catalog_qdrant_client", fake_qdrant_factory)
    llm = FakeRoutingLLM(
        """
        {
          "needs_context": false,
          "catalog_ids": ["connection|ssh|mgmt-ssh"],
          "context_requests": [],
          "intents": ["chat"],
          "surfaces": ["connections"],
          "actions": [],
          "answer_mode": "direct_answer",
          "contract": {"mode": "answer", "evidence_policy": "allow_general"},
          "confidence": 0.95,
          "reason": "wrongly chose connections"
        }
        """
    )

    arbitration = asyncio.run(
        MetaCatalogRouter(settings=settings, embedding_client=FakeEmbeddingClient(), llm_client=llm).route(
            MetaCatalogRoutingInput(
                message="habe ich informationen zu donald trump in meinem memory?",
                menu=build_aria_turn_menu(connection_kinds=("ssh",)),
                surface_registry=build_builtin_surface_registry(settings),
            )
        )
    )

    assert arbitration.source == META_CATALOG_ROUTING_OPERATION
    assert arbitration.plan.surfaces == ("memory",)
    assert arbitration.plan.context_directions == ("memory",)
    assert arbitration.plan.context_requests[0].surface_id == "memory"
    assert arbitration.plan.evidence_policy == "source_bound"


def test_inventory_result_merge_keeps_all_sources() -> None:
    first = SimpleNamespace(
        skill_name="context_inventory",
        success=True,
        content="Beobachtete Quellen:\nWebsite: one",
        metadata={
            "sources": [{"surface": "connections", "kind": "website", "refs": ["one"]}],
            "detail_lines": ["Routing Debug: inventory_index matches=1"],
        },
    )
    second = SimpleNamespace(
        skill_name="context_inventory",
        success=True,
        content="Beobachtete Quellen:\nRSS: two",
        metadata={
            "sources": [{"surface": "connections", "kind": "rss", "refs": ["two"]}],
            "detail_lines": ["Routing Debug: inventory_index matches=1"],
        },
    )

    merged = AgenticContextRuntimeMixin._aria_turn_merge_inventory_results([first, second])  # type: ignore[list-item]

    assert merged is not None
    assert "Website: one" in merged.content
    assert "RSS: two" in merged.content
    assert merged.metadata["sources"] == [
        {"surface": "connections", "kind": "website", "refs": ["one"]},
        {"surface": "connections", "kind": "rss", "refs": ["two"]},
    ]
    assert "Routing Debug: inventory_merge results=2 sources=2" in merged.metadata["detail_lines"]


def test_meta_catalog_action_selection_seeds_capability_draft() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("runtime_action",),
            surfaces=("connections",),
            actions=("ssh_run_command",),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="server health",
                    budget={
                        "catalog_id": "connection|ssh|mgmt-ssh",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "mgmt-ssh",
                    },
                ),
            ),
            priority=("connection|ssh|mgmt-ssh",),
            answer_mode="plan_action",
            risk="medium",
            needs_confirmation=True,
            confidence=0.91,
        ),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "mgmt-ssh"
    assert "capability_draft_source:meta_catalog" in draft.notes


def test_meta_catalog_action_contract_without_actions_still_seeds_capability_draft() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat", "context_inventory"),
            surfaces=("connections",),
            actions=(),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="server health",
                    budget={
                        "catalog_id": "connection|ssh|dev-node-02",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "dev-node-02",
                    },
                ),
            ),
            priority=("connection|ssh|dev-node-02",),
            answer_mode="direct_answer",
            contract_mode="action",
            risk="low",
            needs_confirmation=False,
            confidence=0.9,
        ),
    )
    runtime = AgenticContextRuntimeMixin()

    draft = runtime._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "dev-node-02"
    assert runtime._aria_turn_has_confident_local_context(arbitration) is False
    assert runtime._aria_turn_can_direct_inventory_fast_path(arbitration) is False
    contracts = Pipeline._process_turn_contracts(Pipeline.__new__(Pipeline), arbitration)
    assert contracts.action_contract_selected is True
    assert contracts.confident_local_context is False


def test_meta_catalog_ssh_priorities_seed_explicit_multi_target_contract() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat", "runtime_action"),
            surfaces=("connections",),
            actions=("ssh_run_command",),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="was fuer ip adressen haben meine dev-server",
                    budget={
                        "catalog_id": "connection|ssh|dev-node-01",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "dev-node-01",
                    },
                ),
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="was fuer ip adressen haben meine dev-server",
                    budget={
                        "catalog_id": "connection|ssh|dev-node-02",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "dev-node-02",
                    },
                ),
            ),
            priority=("connection|ssh|dev-node-01", "connection|ssh|dev-node-02"),
            target_scope_authority="semantic_group",
            answer_mode="plan_action",
            contract_mode="action",
            risk="medium",
            needs_confirmation=True,
            confidence=0.92,
            reason="candidate dev servers",
        ),
    )
    runtime = AgenticContextRuntimeMixin()

    draft = runtime._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == ""
    assert draft.connection_refs == ["dev-node-01", "dev-node-02"]
    assert "target_scope:multi_target" in draft.notes
    assert "turn_contract_target_refs:dev-node-01,dev-node-02" in draft.notes
    assert "turn_contract_priority:connection|ssh|dev-node-01,connection|ssh|dev-node-02" in draft.notes


def test_meta_catalog_ssh_priorities_without_scope_authority_are_hints_only() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("runtime_action",),
            surfaces=("connections",),
            actions=("ssh_run_command",),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="zeige mir den status meiner server",
                    budget={
                        "catalog_id": "connection|ssh|srv-a",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "srv-a",
                    },
                ),
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="zeige mir den status meiner server",
                    budget={
                        "catalog_id": "connection|ssh|srv-b",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "srv-b",
                    },
                ),
            ),
            priority=("connection|ssh|srv-a", "connection|ssh|srv-b"),
            answer_mode="plan_action",
            contract_mode="action",
            risk="medium",
            needs_confirmation=True,
            confidence=0.92,
        ),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.connection_refs == []
    assert "target_scope:multi_target" in draft.notes
    assert "target_scope_authority:priority_sample" in draft.notes
    assert "turn_contract_priority_refs_ignored:srv-a,srv-b" in draft.notes


def test_meta_catalog_multi_document_meta_requests_enable_document_inventory() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat", "local_retrieval"),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste die vorhandenen dokumente",
                    budget={
                        "catalog_id": "local|docs|document|doc-a",
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "ref": "doc-a",
                        "document_id": "doc-a",
                        "document_name": "Alpha Instructions.pdf",
                        "target_collection": "aria_docs_example_user",
                    },
                ),
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste die vorhandenen dokumente",
                    budget={
                        "catalog_id": "local|docs|document|doc-b",
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "ref": "doc-b",
                        "document_id": "doc-b",
                        "document_name": "Beta Instructions.pdf",
                        "target_collection": "aria_docs_example_user",
                    },
                ),
            ),
            priority=("local|docs|document|doc-a", "local|docs|document|doc-b"),
            answer_mode="direct_answer",
            risk="low",
            needs_confirmation=False,
            confidence=0.95,
        ),
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="example_user")

    assert overrides["document_inventory"] is True
    assert overrides["document_ids"] == ["doc-a", "doc-b"]
    assert overrides["document_names"] == ["Alpha Instructions.pdf", "Beta Instructions.pdf"]
    assert overrides["document_target_collections"] == ["aria_docs_example_user"]
    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True


def test_meta_catalog_mixed_rss_ssh_action_seed_prefers_ssh_targets() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("runtime_action",),
            surfaces=("connections",),
            actions=("rss_read_feed", "ssh_run_command"),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="server update status",
                    budget={
                        "catalog_id": "connection|rss|debian-security-advisories",
                        "entity_type": "connection",
                        "kind": "rss",
                        "ref": "debian-security-advisories",
                    },
                ),
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="server update status",
                    budget={
                        "catalog_id": "connection|ssh|srv-a",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "srv-a",
                    },
                ),
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="server update status",
                    budget={
                        "catalog_id": "connection|ssh|srv-b",
                        "entity_type": "connection",
                        "kind": "ssh",
                        "ref": "srv-b",
                    },
                ),
            ),
            priority=(
                "connection|rss|debian-security-advisories",
                "connection|ssh|srv-a",
                "connection|ssh|srv-b",
            ),
            target_scope_authority="semantic_group",
            answer_mode="direct_answer",
            contract_mode="action",
            evidence_policy="source_bound",
            risk="medium",
            needs_confirmation=True,
            confidence=0.92,
        ),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == ""
    assert draft.connection_refs == ["srv-a", "srv-b"]
    assert "target_scope:multi_target" in draft.notes
    assert "turn_contract_target_refs:srv-a,srv-b" in draft.notes
    assert "turn_contract_priority:connection|rss|debian-security-advisories,connection|ssh|srv-a,connection|ssh|srv-b" in draft.notes


def test_meta_catalog_rss_action_contract_without_action_array_seeds_feed_read() -> None:
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("runtime_action",),
            surfaces=("connections",),
            actions=(),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="lies den feed heise-security-alerts",
                    budget={
                        "catalog_id": "connection|rss|heise-security-alerts",
                        "entity_type": "connection",
                        "kind": "rss",
                        "ref": "heise-security-alerts",
                    },
                ),
            ),
            priority=("connection|rss|heise-security-alerts",),
            answer_mode="direct_answer",
            contract_mode="action",
            evidence_policy="source_bound",
            risk="low",
            needs_confirmation=False,
            confidence=0.95,
        ),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == "heise-security-alerts"
    assert draft.content == "lies den feed heise-security-alerts"


def test_meta_catalog_connection_actions_map_to_existing_capabilities() -> None:
    runtime = AgenticContextRuntimeMixin()
    cases = [
        ("connection_action_rss", "rss", "feed_read"),
        ("connection_action_website", "website", "website_list"),
        ("connection_action_sftp", "sftp", "file_list"),
        ("connection_action_smb", "smb", "file_list"),
        ("connection_action_http_api", "http_api", "api_request"),
        ("connection_action_imap", "imap", "mail_read"),
        ("connection_action_mqtt", "mqtt", "mqtt_publish"),
    ]
    for action, kind, expected in cases:
        arbitration = AriaTurnArbitration(
            source=META_CATALOG_ROUTING_OPERATION,
            plan=AriaTurnPlan(
                intents=("runtime_action",),
                surfaces=("connections",),
                actions=(action,),
                needs_context=True,
                context_directions=("connections",),
                context_requests=(
                    ContextRequest(
                        surface_id="connections",
                        mode="action",
                        query="topic",
                        budget={"entity_type": "connection", "kind": kind, "ref": "main"},
                    ),
                ),
                priority=(f"connection|{kind}|main",),
                risk="medium",
                confidence=0.91,
            ),
        )
        draft = runtime._aria_turn_seed_capability_draft(arbitration)
        assert draft is not None
        assert draft.capability == expected
        assert draft.connection_kind == kind
        assert draft.explicit_connection_ref == "main"


def test_meta_catalog_local_family_binds_memory_targets() -> None:
    runtime = AgenticContextRuntimeMixin()
    runtime.settings = _settings()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("memory",),
            needs_context=True,
            context_directions=("memory",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="memory",
                    mode="search",
                    query="UI-Regel",
                    budget={
                        "catalog_id": "local|memory|preferences",
                        "entity_type": "local_context",
                        "kind": "memory_family",
                        "ref": "preferences",
                    },
                ),
            ),
            priority=("local|memory|preferences",),
            confidence=0.91,
        ),
    )

    overrides = runtime._aria_turn_context_overrides(arbitration, user_id="example_user")

    assert overrides["memory_recall_enabled"] is True
    assert overrides["memory_target_collections"] == ["aria_preferences_example_user"]
    assert overrides["include_documents"] is False


def test_meta_catalog_docs_search_sets_docs_only_context_override() -> None:
    runtime = AgenticContextRuntimeMixin()
    runtime.settings = _settings()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),),
            confidence=0.91,
        ),
    )

    overrides = runtime._aria_turn_context_overrides(arbitration, user_id="example_user")

    assert overrides["memory_recall_enabled"] is True
    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert "memory_target_collections" not in overrides


def test_docs_search_evidence_rejects_non_document_memory_sources() -> None:
    runtime = AgenticContextRuntimeMixin()
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content="- [FAKT] Wenn ein sichtbarer Status eine Option darstellt, soll ein Klick direkt zu den Einstellungen führen.",
        metadata={
            "sources": [
                {
                    "type": "fact",
                    "label": "FAKT",
                    "collection": "aria_facts_example_user",
                    "detail": "Quelle: FAKT · aria_facts_example_user",
                }
            ],
            "detail_lines": [],
        },
    )

    matched = runtime._aria_turn_local_search_has_evidence(
        ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),
        result,
    )

    assert matched is False
    assert any("surface=docs mode=search matched=false" in line for line in result.metadata["detail_lines"])


def test_docs_search_evidence_accepts_matching_document_sources() -> None:
    runtime = AgenticContextRuntimeMixin()
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content="- [DOKUMENT: ui-rules.md] UI-Regel: sichtbarer Status führt per Klick zu Einstellungen.",
        metadata={
            "sources": [
                {
                    "type": "document",
                    "label": "DOKUMENT",
                    "collection": "aria_docs_example_user",
                    "document_name": "ui-rules.md",
                    "detail": "Quelle: ui-rules.md · aria_docs_example_user",
                }
            ],
            "detail_lines": [],
        },
    )

    matched = runtime._aria_turn_local_search_has_evidence(
        ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),
        result,
    )

    assert matched is True


def test_docs_fast_answer_accepts_compact_source_bound_document_content() -> None:
    runtime = AgenticContextRuntimeMixin()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content="- [DOKUMENT: ui-rules.md] UI-Regel: sichtbarer Status führt per Klick zu Einstellungen.",
        metadata={
            "sources": [
                {
                    "type": "document",
                    "collection": "aria_docs_example_user",
                    "document_name": "ui-rules.md",
                }
            ]
        },
    )

    text = runtime._aria_turn_fast_docs_search_answer(arbitration, result, language="de")

    assert text.startswith("Aus ui-rules.md:")
    assert "UI-Regel" in text


def test_docs_fast_answer_rejects_large_document_content_for_composer_fallback() -> None:
    runtime = AgenticContextRuntimeMixin()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content="\n".join(f"Zeile {index}" for index in range(20)),
        metadata={"sources": [{"type": "document", "collection": "aria_docs_example_user", "document_name": "ui-rules.md"}]},
    )

    assert runtime._aria_turn_fast_docs_search_answer(arbitration, result, language="de") == ""


def test_docs_composer_fallback_does_not_return_raw_multilingual_chunks() -> None:
    runtime = AgenticContextRuntimeMixin()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="wie kriege ich meine heizungen ans wireless?"),),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content=(
            "- [DOKUMENT: Mill Manual] Varmeapparatet har problemer med at forbinde til wi-fi.\n"
            "Tryk på «Tilføj varmeapparat» på startskærmen i Mill-appen.\n"
            "The heater has a problem connecting to or finding the WiFi signal.\n"
            "Please turn the heater OFF and ON. Restart the WiFi router. Check that 2.4 GHz is enabled.\n"
            "Delete WiFi settings: press the WiFi button and hold it for 5 seconds."
        ),
        metadata={
            "sources": [
                {
                    "type": "document",
                    "collection": "aria_docs_example_user",
                    "document_name": "Mill Gentle Air WiFi oil filled_Nordic_2025_print.pdf",
                }
            ]
        },
    )

    text = runtime._aria_turn_docs_search_fallback_answer(arbitration, result, language="de")

    assert "Öffne die Mill-App" in text
    assert "2,4 GHz" in text
    assert "WiFi-Taste 5 Sekunden" in text
    assert "Varmeapparatet" not in text
    assert "The heater has a problem" not in text


def test_docs_fallback_uses_source_bound_mill_metadata_for_compact_instruction() -> None:
    runtime = AgenticContextRuntimeMixin()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(
                ContextRequest(surface_id="docs", mode="search", query="wie kriege ich meine heizungen ans wireless?"),
            ),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content=(
            "- [DOKUMENT: Mill Manual] App pairing instructions.\n"
            "If it cannot connect, restart the router and make sure 2.4 GHz is enabled.\n"
            "Delete WiFi settings: press the WiFi button and hold it for 5 seconds."
        ),
        metadata={
            "sources": [
                {
                    "type": "document",
                    "collection": "aria_docs_example_user",
                    "document_name": "Mill Gentle Air WiFi oil filled_Nordic_2025_print.pdf",
                    "guide_summary": "Mill heater WiFi setup instructions.",
                    "guide_keywords": ["Mill", "WiFi", "heater"],
                }
            ]
        },
    )

    text = runtime._aria_turn_docs_search_fallback_answer(arbitration, result, language="de")

    assert text.startswith("Um die WLAN-Verbindung deiner Mill-Heizung einzurichten:")
    assert "Öffne die Mill-App" in text
    assert "2,4 GHz" in text
    assert "WiFi-Taste 5 Sekunden" in text
    assert "konnte sie aber nicht sicher genug" not in text


def test_docs_fallback_answers_exhaustive_corpus_scan_without_primary_term_match() -> None:
    runtime = AgenticContextRuntimeMixin()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="deep",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="Glucosamin Bestandteil Inhaltsstoff Zusammensetzung",
                ),
            ),
            priority=("local|docs|document|doc-a", "local|docs|documents"),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content=(
            "[Dokument-Corpus-Scan]\n"
            "Vollständig gescannt: 5 Dokumente, 296 Chunks.\n"
            "Suchbegriff-Abdeckung:\n"
            "- glucosamin: 0 Treffer-Chunks in 0 Dokumenten\n"
            "- bestandteil: 7 Treffer-Chunks in 3 Dokumenten\n"
        ),
        metadata={
            "document_corpus_scan": {
                "exhaustive": True,
                "terms": ["glucosamin", "bestandteil", "inhaltsstoff", "zusammensetzung"],
                "matched_terms": ["bestandteil", "inhaltsstoff", "zusammensetzung"],
                "unmatched_terms": ["glucosamin"],
                "term_stats": {
                    "glucosamin": {"chunks": 0, "documents": 0, "document_names": [], "matches": []},
                    "bestandteil": {"chunks": 7, "documents": 3, "document_names": ["Olumiant.pdf"], "matches": []},
                    "inhaltsstoff": {"chunks": 4, "documents": 2, "document_names": ["Cimzia.pdf"], "matches": []},
                    "zusammensetzung": {"chunks": 12, "documents": 4, "document_names": ["Simponi.pdf"], "matches": []},
                },
                "documents_scanned": 5,
                "chunks_scanned": 296,
                "match_chunks": 23,
            },
            "sources": [
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Olumiant.pdf"},
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Cimzia.pdf"},
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Simponi.pdf"},
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Zoledronat.pdf"},
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Certolizumab.pdf"},
            ],
        },
    )

    text = runtime._aria_turn_fast_docs_search_answer(arbitration, result, language="de")

    assert text.startswith("Ich habe den Dokument-Corpus vollständig gescannt: 5 Dokumente, 296 Chunks.")
    assert "Für `glucosamin` gab es 0 exakte Treffer" in text
    assert "keinen Beleg" in text
    assert "Die übrigen Treffer betreffen nur weitere Such-/Kontextbegriffe" in text
    assert "Geprüfte Dokumente: Olumiant.pdf, Cimzia.pdf, Simponi.pdf" in text
    assert "konnte sie aber nicht sicher genug" not in text


def test_docs_search_rejects_exhaustive_corpus_scan_without_match_chunks() -> None:
    runtime = AgenticContextRuntimeMixin()
    request = ContextRequest(
        surface_id="docs",
        mode="search",
        query="welche verbindungen kennst du fuer syncthing",
    )
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="deep",
            context_requests=(request,),
            priority=("local|docs|document|ffc2d1d6056e446221956170",),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content=(
            "[Dokument-Corpus-Scan]\n"
            "Vollständig gescannt: 2 Dokumente, 207 Chunks.\n"
            "Suchbegriff-Abdeckung:\n"
            "- welche: 0 Treffer-Chunks in 0 Dokumenten\n"
            "- verbindungen: 0 Treffer-Chunks in 0 Dokumenten\n"
            "- kennst: 0 Treffer-Chunks in 0 Dokumenten\n"
            "- syncthing: 0 Treffer-Chunks in 0 Dokumenten\n"
        ),
        metadata={
            "document_corpus_scan": {
                "exhaustive": True,
                "terms": ["welche", "verbindungen", "kennst", "syncthing"],
                "matched_terms": [],
                "unmatched_terms": ["welche", "verbindungen", "kennst", "syncthing"],
                "term_stats": {
                    "welche": {"chunks": 0, "documents": 0, "document_names": [], "matches": []},
                    "verbindungen": {"chunks": 0, "documents": 0, "document_names": [], "matches": []},
                    "kennst": {"chunks": 0, "documents": 0, "document_names": [], "matches": []},
                    "syncthing": {"chunks": 0, "documents": 0, "document_names": [], "matches": []},
                },
                "documents_scanned": 2,
                "chunks_scanned": 207,
                "match_chunks": 0,
            },
            "sources": [
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Beipackzettel A.pdf"},
                {"type": "document", "collection": "aria_docs_example_user", "document_name": "Beipackzettel B.pdf"},
            ],
        },
    )

    assert runtime._aria_turn_local_search_has_evidence(request, result) is False
    assert runtime._aria_turn_fast_docs_search_answer(arbitration, result, language="de") == ""
    assert runtime._aria_turn_docs_search_fallback_answer(arbitration, result, language="de") == ""
    assert any(
        "Routing Debug: evidence_filter surface=docs mode=search matched=false" in line
        and "reason=document_corpus_scan_no_matches" in line
        for line in result.metadata["detail_lines"]
    )


def test_docs_fast_answer_uses_bounded_mill_wifi_instruction_summary() -> None:
    runtime = AgenticContextRuntimeMixin()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            surfaces=("docs",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="wie kriege ich meine heizungen ans wireless?"),),
            answer_mode="direct_answer",
            evidence_policy="source_bound",
            confidence=0.91,
        ),
    )
    result = SkillResult(
        skill_name="memory_recall",
        success=True,
        content=(
            "- [DOKUMENT: Mill Manual] Varmeapparatet har problemer med at forbinde til wi-fi.\n"
            "Tryk på «Tilføj varmeapparat» på startskærmen i Mill-appen.\n"
            "The heater has a problem connecting to or finding the WiFi signal.\n"
            "Please turn the heater OFF and ON. Restart the WiFi router. Check that 2.4 GHz is enabled.\n"
            "Delete WiFi settings: press the WiFi button and hold it for 5 seconds."
        ),
        metadata={
            "sources": [
                {
                    "type": "document",
                    "collection": "aria_docs_example_user",
                    "document_name": "Mill Gentle Air WiFi oil filled_Nordic_2025_print.pdf",
                }
            ]
        },
    )

    text = runtime._aria_turn_fast_docs_search_answer(arbitration, result, language="de")

    assert text.startswith("Um die WLAN-Verbindung deiner Mill-Heizung einzurichten:")
    assert "Öffne die Mill-App" in text
    assert "Varmeapparatet" not in text


def test_rebuild_inventory_index_also_rebuilds_meta_catalog() -> None:
    settings = _settings()
    qdrant = FakeQdrant()

    result = asyncio.run(rebuild_inventory_index(settings, qdrant_client=qdrant, embedding_client=FakeEmbeddingClient()))

    assert result["status"] == "ok"
    assert result["indexed_count"] == result["document_count"]
    assert result["meta_indexed_count"] == result["meta_document_count"]
    assert inventory_collection_name(settings) in qdrant.collections
    assert meta_catalog_collection_name(settings) in qdrant.collections
    assert result["indexed_meta_catalog_hash"]
