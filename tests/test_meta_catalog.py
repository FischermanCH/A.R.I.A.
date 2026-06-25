from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import Settings
from aria.core.aria_turn_arbitration import build_aria_turn_menu
from aria.core.aria_turn_arbitration import AriaTurnArbitration, AriaTurnPlan
from aria.core.agentic_context_runtime import AgenticContextRuntimeMixin
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.context_surfaces import ContextRequest
from aria.core.inventory_admin import rebuild_inventory_index
from aria.core.inventory_index import inventory_collection_name
from aria.core.meta_catalog import MetaCatalogStore, build_meta_catalog_documents, meta_catalog_collection_name, meta_catalog_documents_fingerprint
from aria.core.meta_catalog_routing import META_CATALOG_ROUTING_OPERATION
from aria.core.meta_catalog_routing import MetaCatalogRouter, MetaCatalogRoutingConfig, MetaCatalogRoutingInput
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
            vectors.append([server, source])
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


class FakeChatResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}


class FakeRoutingLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return FakeChatResponse(self.content)


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
                user_id="fischerman",
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
    assert "contract_mode=action" in arbitration.debug_line
    assert arbitration.plan.needs_confirmation is True
    assert llm.calls[0]["kwargs"]["operation"] == META_CATALOG_ROUTING_OPERATION


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

    overrides = runtime._aria_turn_context_overrides(arbitration, user_id="fischerman")

    assert overrides["memory_recall_enabled"] is True
    assert overrides["memory_target_collections"] == ["aria_preferences_fischerman"]
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

    overrides = runtime._aria_turn_context_overrides(arbitration, user_id="fischerman")

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
                    "collection": "aria_facts_fischerman",
                    "detail": "Quelle: FAKT · aria_facts_fischerman",
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
                    "collection": "aria_docs_fischerman",
                    "document_name": "ui-rules.md",
                    "detail": "Quelle: ui-rules.md · aria_docs_fischerman",
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
