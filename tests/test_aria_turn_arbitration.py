from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import aria.core.recipe_runtime as recipe_runtime_mod
import aria.core.pipeline as pipeline_mod
import aria.core.meta_catalog_routing as meta_catalog_routing_mod
from aria.core.aria_turn_arbitration import ARIA_TURN_ARBITRATION_OPERATION
from aria.core.aria_turn_arbitration import AriaTurnActionOption
from aria.core.aria_turn_arbitration import AriaTurnArbiter
from aria.core.aria_turn_arbitration import AriaTurnCollectionOption
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnMenu
from aria.core.aria_turn_arbitration import AriaTurnPlan
from aria.core.aria_turn_arbitration import AriaTurnSurfaceOption
from aria.core.aria_turn_arbitration import build_aria_turn_menu
from aria.core.action_plan import CapabilityDraft
from aria.core.config import Settings
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.inventory_index import InventoryIndexStore
from aria.core.inventory_index import build_inventory_documents
from aria.core.inventory_index import inventory_collection_name
from aria.core.meta_catalog import MetaCatalogStore
from aria.core.meta_catalog import build_meta_catalog_documents
from aria.core.meta_catalog import meta_catalog_collection_name
from aria.core.meta_catalog import meta_catalog_documents_fingerprint
from aria.core.meta_catalog_routing import META_CATALOG_ROUTING_OPERATION
from aria.core.pipeline import Pipeline
from aria.skills.base import SkillResult
from aria.web.chat_execution_flow import _pre_pipeline_aria_actions
from aria.web.chat_execution_flow import _pre_pipeline_aria_decision
from aria.web.chat_execution_flow import _selected_action_not_handled_outcome

LEGACY_FAST_CONTEXT_OPERATION = "aria_turn_fast_context_arbitration"


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}


class _ArbiterLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.operations: list[str] = []
        self.last_payload: dict | None = None

    async def chat(self, messages, **kwargs):
        self.operations.append(str(kwargs.get("operation", "") or ""))
        if kwargs.get("operation") == ARIA_TURN_ARBITRATION_OPERATION:
            self.last_payload = json.loads(messages[-1]["content"])
            return _Response(json.dumps(self.payload))
        return _Response("{}")


class _FastContextArbiterLLM:
    def __init__(self, fast_payload: dict, full_payload: dict | None = None) -> None:
        self.fast_payload = fast_payload
        self.full_payload = full_payload or {"intents": ["chat"], "needs_context": False, "confidence": "high", "reason": "fallback"}
        self.operations: list[str] = []
        self.last_payloads: dict[str, dict] = {}

    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        self.operations.append(operation)
        self.last_payloads[operation] = json.loads(messages[-1]["content"])
        if operation == LEGACY_FAST_CONTEXT_OPERATION:
            return _Response(json.dumps(self.fast_payload))
        if operation == ARIA_TURN_ARBITRATION_OPERATION:
            return _Response(json.dumps(self.full_payload))
        return _Response("{}")


class _PipelinePromptLoader:
    def get_persona(self) -> str:
        return "Du bist ARIA."


class _PipelineArbiterLLM:
    def __init__(self, aria_payload: dict | None = None) -> None:
        self.operations: list[str] = []
        self.last_messages = []
        self.aria_payloads_seen: list[dict] = []
        self.aria_payload = aria_payload or {
            "needs_context": True,
            "context_directions": ["memory", "learning"],
            "context_depth": "shallow",
            "intents": ["local_retrieval"],
            "surfaces": ["local_retrieval"],
            "collections": ["aria_facts_u1", "aria_learning_u1"],
            "queries": {
                "aria_facts_u1": "UI-Regel klickbare Optionen",
                "aria_learning_u1": "UI-Regel klickbare Optionen",
            },
            "priority": ["learning_reflections", "memory_facts"],
            "answer_mode": "answer_with_source_grouping",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks what ARIA has retained.",
        }

    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        self.operations.append(operation)
        if operation == LEGACY_FAST_CONTEXT_OPERATION:
            return _Response(json.dumps({"use_context": False, "confidence": "high", "reason": "needs full router"}))
        if operation == "turn_intent_arbitration":
            return _Response(json.dumps({"intents": ["chat"], "confidence": "high", "reason": "legacy arbiter stays chat"}))
        if operation == ARIA_TURN_ARBITRATION_OPERATION:
            self.aria_payloads_seen.append(json.loads(messages[-1]["content"]))
            return _Response(json.dumps(self.aria_payload))
        self.last_messages = messages
        return _Response("ok")


class _PipelineMetaCatalogLLM(_PipelineArbiterLLM):
    def __init__(self, meta_payload: dict) -> None:
        super().__init__()
        self.meta_payload = meta_payload

    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        self.operations.append(operation)
        if operation == META_CATALOG_ROUTING_OPERATION:
            return _Response(json.dumps(self.meta_payload))
        if operation == ARIA_TURN_ARBITRATION_OPERATION:
            self.aria_payloads_seen.append(json.loads(messages[-1]["content"]))
            return _Response(json.dumps(self.aria_payload))
        if operation == "turn_intent_arbitration":
            return _Response(json.dumps({"intents": ["chat"], "confidence": "high", "reason": "legacy should not run"}))
        self.last_messages = messages
        return _Response("ok")


class _PipelineMetaCatalogComposerLLM(_PipelineMetaCatalogLLM):
    def __init__(self, meta_payload: dict, *, composer_answer: str) -> None:
        super().__init__(meta_payload)
        self.composer_answer = composer_answer

    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        if operation == "aria_answer_composer":
            self.operations.append(operation)
            return _Response(
                json.dumps(
                    {
                        "answer": self.composer_answer,
                        "confidence": "high",
                        "reason": "composed from evidence packet",
                    }
                )
            )
        return await super().chat(messages, **kwargs)


class _PipelineMetaCatalogSshObjectiveLLM(_PipelineMetaCatalogLLM):
    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        if operation == "capability_draft_decision":
            self.operations.append(operation)
            return _Response(
                json.dumps(
                    {
                        "action": "action",
                        "capability": "ssh_command",
                        "connection_kind": "ssh",
                        "target_scope": "multi_target",
                        "target_intent": "package_update_check",
                        "content": "apt list --upgradable",
                        "confidence": "high",
                        "reason": "package update status question",
                    }
                )
            )
        if operation == "ssh_multi_target_summary":
            self.operations.append(operation)
            return _Response(
                json.dumps(
                    {
                        "summary": "Ich habe die Server auf verfügbare Paketupdates geprüft.",
                        "confidence": "high",
                        "reason": "summarized apt outputs",
                        "facts": {
                            "threshold_gib": None,
                            "threshold_label": "",
                            "below_threshold_refs": [],
                            "near_threshold_refs": [],
                            "ok_refs": [],
                        },
                    }
                )
            )
        return await super().chat(messages, **kwargs)


class _PipelineMetaCatalogCapacityObjectiveLLM(_PipelineMetaCatalogLLM):
    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        if operation == "capability_draft_decision":
            self.operations.append(operation)
            return _Response(
                json.dumps(
                    {
                        "action": "action",
                        "capability": "ssh_command",
                        "connection_kind": "ssh",
                        "target_scope": "single_target",
                        "target_intent": "capacity_check",
                        "content": "df -h",
                        "confidence": "high",
                        "reason": "disk capacity check",
                    }
                )
            )
        return await super().chat(messages, **kwargs)


class _PipelineMemory:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def _build_recall_targets(self, user_id: str, base_collection: str | None = None):
        _ = base_collection
        return [
            {"type": "fact", "label": "FAKT", "collection": f"aria_facts_{user_id}", "top_k": 5},
            {"type": "knowledge", "label": "WISSEN", "collection": f"aria_knowledge_{user_id}", "top_k": 5},
            {"type": "reflection", "label": "LERNEN", "collection": f"aria_learning_{user_id}", "top_k": 5},
        ]

    async def _build_document_targets(self, user_id: str):
        _ = user_id
        return []

    async def execute(self, query: str, params: dict):
        self.calls.append({"query": query, "params": dict(params)})
        targets = list(params.get("target_collections") or [])
        return SkillResult(
            skill_name="memory_recall",
            success=True,
            content="[FAKT] UI-Regel: Klickbare Optionen fuehren direkt zur Einstellung.",
            metadata={
                "detail_lines": [
                    f"Routing Debug: memory_recall_targets selected={len(targets)} collections={','.join(targets) or '-'}",
                    "Quelle: FAKT · aria_facts_u1",
                ]
            },
        )


class _PipelineQuestionWordMemory(_PipelineMemory):
    async def execute(self, query: str, params: dict):
        self.calls.append({"query": query, "params": dict(params)})
        targets = list(params.get("target_collections") or [])
        return SkillResult(
            skill_name="memory_recall",
            success=True,
            content="[WISSEN] und was ist mit dem management server\n[FAKT] habe ich auf meinen server genug speicherplatz",
            metadata={
                "detail_lines": [
                    f"Routing Debug: memory_recall_targets selected={len(targets)} collections={','.join(targets) or '-'}",
                    "Quelle: WISSEN · aria_knowledge_u1",
                ]
            },
        )


class _InventoryEmbeddingResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.usage = {"prompt_tokens": len(vectors), "completion_tokens": 0, "total_tokens": len(vectors)}
        self.model = "fake-embedding"


class _InventoryEmbeddingClient:
    async def embed(self, inputs, **kwargs):  # noqa: ANN001
        _ = kwargs
        rows: list[list[float]] = []
        for item in inputs:
            lower = str(item or "").lower()
            security = 1.0 if any(token in lower for token in ("security", "sicherheit", "pentest", "cve")) else 0.0
            sport = 1.0 if any(token in lower for token in ("sport", "sports", "football", "fussball")) else 0.0
            rows.append([security, sport])
        return _InventoryEmbeddingResponse(rows)


class _InventoryQdrant:
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
        self.collections.setdefault(collection_name, {"size": len(points[0].vector) if points else 0, "points": []})
        self.collections[collection_name]["points"] = list(points)

    async def scroll(self, collection_name: str, limit: int = 100, offset=None, with_payload: bool = True, with_vectors: bool = False):  # noqa: ANN001, ARG002
        rows = list(self.collections.get(collection_name, {}).get("points", []) or [])
        start = int(offset or 0)
        batch = rows[start : start + limit]
        next_offset = start + limit if start + limit < len(rows) else None
        return batch, next_offset

    async def query_points(self, collection_name: str, query: list[float], limit: int = 5):  # noqa: ANN001
        hits = []
        for point in list(self.collections.get(collection_name, {}).get("points", []) or []):
            vector = list(getattr(point, "vector", []) or [])
            score = sum(float(a) * float(b) for a, b in zip(vector, query, strict=False))
            hits.append(SimpleNamespace(id=getattr(point, "id", ""), payload=getattr(point, "payload", {}) or {}, score=score))
        hits.sort(key=lambda item: item.score, reverse=True)
        return SimpleNamespace(points=hits[:limit])


class _WebGatePipeline:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def _load_stored_recipe_runtime(self):
        return []

    async def _build_aria_turn_menu(self, *, user_id: str, runtime_recipes: list[dict]):
        _ = user_id, runtime_recipes
        return build_aria_turn_menu(notes_available=True, websites_available=True, learning_available=True)

    def _aria_turn_last_frame_payload(self, user_id: str):
        _ = user_id
        return {}


class _WebGatePipelineWithFrame(_WebGatePipeline):
    def _aria_turn_last_frame_payload(self, user_id: str):
        _ = user_id
        return {
            "surface_id": "connections",
            "mode": "inventory",
            "topic": "Sport",
            "source_scope": "registered_context_surface",
            "answer_contract": "answer_only_from_selected_loaded_context",
            "confidence": 0.95,
        }


def _menu() -> AriaTurnMenu:
    return AriaTurnMenu(
        surfaces=(
            AriaTurnSurfaceOption("chat", "chat", "normal answer"),
            AriaTurnSurfaceOption("local_retrieval", "retrieval", "memory, notes, docs, learning"),
            AriaTurnSurfaceOption("runtime", "runtime", "connection actions"),
            AriaTurnSurfaceOption("learning", "learning", "feedback and outcomes"),
        ),
        collections=(
            AriaTurnCollectionOption("aria_facts_u1", "memory_facts", "facts"),
            AriaTurnCollectionOption("aria_learning_u1", "learning_reflections", "learning"),
            AriaTurnCollectionOption("aria_notes_u1", "notes", "notes"),
            AriaTurnCollectionOption("aria_docs_manuals", "documents", "docs"),
        ),
        actions=(
            AriaTurnActionOption("ssh_package_update_check", "ssh", "read-only update status", risk="low"),
            AriaTurnActionOption("discord_send", "discord", "send a message", risk="medium", requires_confirmation=True),
        ),
        policy_notes=("side effects require confirmation",),
        budget={"max_collections": 4, "timeout_ms": 2500},
    )


def test_build_aria_turn_menu_unifies_surfaces_and_actions() -> None:
    menu = build_aria_turn_menu(
        collections=(
            AriaTurnCollectionOption("aria_facts_u1", "memory_facts"),
            AriaTurnCollectionOption("aria_notes_u1", "notes"),
        ),
        connection_kinds=("ssh", "discord", "ssh"),
        recipes_available=True,
        notes_available=True,
        docs_available=True,
        web_search_available=True,
        websites_available=True,
        pending_available=True,
        admin_available=True,
        learning_available=True,
        policy_notes=("side effects require confirmation",),
        budget={"timeout_ms": 2500},
    )

    assert [surface.name for surface in menu.surfaces] == [
        "chat",
        "local_retrieval",
        "web_research",
        "watched_websites",
        "recipes",
        "runtime_actions",
        "pending_flow",
        "admin_flow",
        "learning_feedback",
    ]
    assert [collection.name for collection in menu.collections] == ["aria_facts_u1", "aria_notes_u1"]
    assert [action.name for action in menu.actions] == [
        "notes_action",
        "watched_website_action",
        "connection_action_ssh",
        "connection_action_discord",
        "recipe_action",
        "pending_action",
        "admin_action",
        "learning_capture",
    ]
    assert menu.actions[0].requires_confirmation is False
    assert menu.actions[2].requires_confirmation is True
    assert menu.actions[-1].requires_confirmation is False
    assert menu.policy_notes == ("side effects require confirmation",)
    assert menu.budget == {"timeout_ms": 2500}


def test_aria_turn_arbiter_sends_compact_stage_one_payload() -> None:
    llm = _ArbiterLLM({"intents": ["chat"], "needs_context": False, "confidence": "high", "reason": "plain chat"})
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "website": {
                    "sports-watch": {
                        "url": "https://example.invalid/sports",
                        "title": "Sports Watch",
                        "description": "Observed sports website",
                        "group_name": "Sport",
                    }
                }
            },
        }
    )

    asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="hallo",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            user_id="u1",
            request_id="r1",
        )
    )

    assert llm.last_payload is not None
    assert "menu" not in llm.last_payload
    routing_meta = llm.last_payload["routing_meta_context"]
    assert "legacy_surfaces" not in routing_meta
    assert "collections" in routing_meta
    assert "actions" in routing_meta
    surface_meta = llm.last_payload["surface_meta_context"]
    connections = next(surface for surface in surface_meta["surfaces"] if surface["id"] == "connections")
    assert "metadata" not in connections
    assert "loader_contract" not in connections
    assert "what_it_knows" not in connections
    assert connections["routing"]["configured_kinds"] == ["website"]
    assert "Sports Watch" not in str(llm.last_payload)
    assert "https://example.invalid/sports" not in str(llm.last_payload)


def test_aria_turn_arbiter_sends_last_frame_to_full_turn_plan() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "IT-Security"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "query": "IT-Security",
            "depth": "shallow",
            "confidence": "high",
            "reason": "continues inventory frame",
        }
    )
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "rss": {
                    "security-feed": {
                        "title": "Security Feed",
                        "description": "Cybersecurity research",
                        "tags": ["security"],
                    }
                }
            },
        }
    )

    arbitration = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="und was ist mit IT-Security?",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            turn_context={
                "last_turn_frame": {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "topic": "Sport",
                    "confidence": 0.95,
                }
            },
            user_id="u1",
            request_id="r1",
        )
    )

    assert arbitration.source == ARIA_TURN_ARBITRATION_OPERATION
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert arbitration.plan.intents == ("context_inventory",)
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.context_requests[0].query == "IT-Security"
    assert llm.last_payload is not None
    assert llm.last_payload["last_turn_frame"]["surface_id"] == "connections"
    assert llm.last_payload["last_turn_frame"]["mode"] == "inventory"


def test_aria_turn_arbiter_does_not_let_old_frame_override_full_plan_surface() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "IT-Security"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "new topic fits inventory",
        }
    )
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "connections": {
                "rss": {
                    "security-feed": {
                        "title": "Security Feed",
                        "description": "Cybersecurity research",
                        "tags": ["security"],
                    }
                }
            },
        }
    )

    arbitration = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="und was ist mit IT-Security?",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            turn_context={
                "last_turn_frame": {
                    "surface_id": "memory",
                    "mode": "exists",
                    "topic": "Gongerot Maschrep",
                    "confidence": 0.95,
                }
            },
            user_id="u1",
            request_id="r1",
        )
    )

    assert arbitration.source == ARIA_TURN_ARBITRATION_OPERATION
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.context_requests[0].query == "IT-Security"


def test_aria_turn_arbiter_does_not_use_fast_context_as_semantic_truth() -> None:
    llm = _FastContextArbiterLLM(
        {
            "use_context": True,
            "surface_id": "notes",
            "mode": "search",
            "query": "UI-Regel",
            "depth": "shallow",
            "confidence": "high",
            "reason": "notes context",
        },
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["notes"],
            "surfaces": ["notes"],
            "context_requests": [{"surface_id": "notes", "mode": "search", "query": "UI-Regel"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "notes context",
        },
    )
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "notes": {"enabled": True},
        }
    )

    arbitration = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="was steht in meinen notizen zur UI-Regel?",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            language="de",
            user_id="u1",
            request_id="r1",
        )
    )

    assert arbitration.source == ARIA_TURN_ARBITRATION_OPERATION
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert arbitration.plan.intents == ("local_retrieval",)
    assert arbitration.plan.context_directions == ("notes",)
    assert arbitration.plan.context_requests[0].surface_id == "notes"
    assert arbitration.plan.context_requests[0].mode == "search"
    assert arbitration.plan.context_requests[0].query == "UI-Regel"
    assert LEGACY_FAST_CONTEXT_OPERATION not in llm.operations


def test_aria_turn_arbiter_uses_full_turn_plan_directly() -> None:
    llm = _FastContextArbiterLLM(
        {"use_context": False, "confidence": "high", "reason": "needs full router"},
        {"intents": ["chat"], "needs_context": False, "confidence": "high", "reason": "plain chat"},
    )
    settings = Settings.model_validate({"llm": {"model": "fake"}, "memory": {"enabled": False}})

    arbitration = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="hallo",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            user_id="u1",
            request_id="r1",
        )
    )

    assert arbitration.source == ARIA_TURN_ARBITRATION_OPERATION
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert arbitration.plan.intents == ("chat",)
    assert arbitration.plan.needs_context is False


def test_aria_turn_arbiter_full_plan_handles_resource_inventory_question() -> None:
    llm = _FastContextArbiterLLM(
        {
            "use_context": True,
            "surface_id": "memory",
            "mode": "exists",
            "query": "firewalls",
            "depth": "shallow",
            "confidence": "high",
            "reason": "wrong fast memory path",
        },
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "firewalls"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "resources inventory",
        },
    )
    settings = Settings.model_validate({"llm": {"model": "fake"}, "memory": {"enabled": True}, "connections": {}})

    arbitration = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="was habe ich fuer firewalls",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            language="de",
            user_id="u1",
            request_id="r1",
        )
    )

    assert arbitration.source == ARIA_TURN_ARBITRATION_OPERATION
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert arbitration.plan.intents == ("context_inventory",)
    assert arbitration.plan.context_directions == ("connections",)
    assert arbitration.plan.context_requests[0].surface_id == "connections"
    assert arbitration.plan.context_requests[0].mode == "inventory"
    assert arbitration.plan.context_requests[0].query == "firewalls"


def test_aria_turn_arbiter_does_not_let_fast_memory_block_server_operation_plan() -> None:
    llm = _FastContextArbiterLLM(
        {
            "use_context": True,
            "surface_id": "memory",
            "mode": "exists",
            "query": "server updates",
            "depth": "shallow",
            "confidence": "high",
            "reason": "wrong fast memory path",
        },
        {
            "intents": ["runtime_action"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["runtime"],
            "actions": ["ssh_package_update_check"],
            "answer_mode": "plan_action",
            "risk": "low",
            "needs_confirmation": False,
            "confidence": "high",
            "reason": "server update check",
        },
    )
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "connections": {"ssh": {"srv-a": {"host": "127.0.0.1", "user": "demo"}}},
        }
    )

    arbitration = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="brauchen meine server updates?",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            language="de",
            user_id="u1",
            request_id="r1",
        )
    )

    assert arbitration.source == ARIA_TURN_ARBITRATION_OPERATION
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert arbitration.plan.intents == ("runtime_action",)
    assert arbitration.plan.actions == ("ssh_package_update_check",)
    assert arbitration.plan.context_directions == ("connections",)


def test_aria_turn_arbiter_surface_meta_context_is_compact_but_registered() -> None:
    llm = _ArbiterLLM({"intents": ["chat"], "needs_context": False, "confidence": "high", "reason": "plain chat"})
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant"},
            "connections": {
                "rss": {
                    "security-feed": {
                        "title": "Security Feed",
                        "description": "Cybersecurity research",
                        "tags": ["security"],
                    }
                }
            },
        }
    )
    registry = build_builtin_surface_registry(settings)

    asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="hallo",
            menu=_menu(),
            surface_registry=registry,
            user_id="u1",
            request_id="r1",
        )
    )

    assert llm.last_payload is not None
    compact = llm.last_payload["surface_meta_context"]
    full = registry.as_routing_meta_context()
    assert {surface["id"] for surface in compact["surfaces"]} == set(registry.surface_ids())
    assert len(json.dumps(compact, sort_keys=True)) < len(json.dumps(full, sort_keys=True)) * 0.65
    assert compact["contract"]["select_registered_surface_ids_only"] is True
    assert "loader_contract" not in json.dumps(compact)


def test_aria_turn_arbiter_accepts_combined_local_retrieval_plan() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory", "learning", "notes"],
            "context_depth": "shallow",
            "surfaces": ["local_retrieval"],
            "collections": ["aria_facts_u1", "aria_learning_u1", "aria_notes_u1"],
            "queries": {
                "aria_facts_u1": "UI-Regel klickbare Optionen",
                "aria_learning_u1": "UI-Regel klickbare Optionen",
                "aria_notes_u1": "UI-Regel klickbare Optionen",
            },
            "priority": ["learning_reflections", "memory_facts", "notes"],
            "answer_mode": "answer_with_source_grouping",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": "high",
            "reason": "The user asks what ARIA knows across remembered and written context.",
        }
    )

    result = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="was weiss ARIA ueber meine UI-Regel, auch falls ich es in Notizen abgelegt habe?",
            menu=_menu(),
            user_id="u1",
            request_id="r1",
        )
    )

    assert result.source == ARIA_TURN_ARBITRATION_OPERATION
    assert result.plan.intents == ("local_retrieval",)
    assert result.plan.needs_context is True
    assert result.plan.context_directions == ("memory", "learning", "notes")
    assert result.plan.context_depth == "shallow"
    assert result.plan.collections == ("aria_facts_u1", "aria_learning_u1", "aria_notes_u1")
    assert result.plan.queries["aria_learning_u1"] == "UI-Regel klickbare Optionen"
    assert result.plan.answer_mode == "answer_with_source_grouping"
    assert "aria_turn_surface_action_arbitration" in result.debug_line
    assert "needs_context=true" in result.debug_line
    assert "context_directions=memory,learning,notes" in result.debug_line
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert llm.last_payload is not None
    assert llm.last_payload["routing_meta_context"]["collections"][0]["name"] == "aria_facts_u1"
    assert llm.last_payload["routing_meta_context"]["actions"][1]["name"] == "discord_send"


def test_aria_turn_arbiter_infers_context_directions_from_selected_collections() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "surfaces": ["local_retrieval"],
            "collections": ["aria_learning_u1"],
            "queries": {"aria_learning_u1": "dauerhafte UI Regel"},
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for learned durable behavior.",
        }
    )

    result = asyncio.run(AriaTurnArbiter(llm).arbitrate(message="was hast du ueber UI gelernt?", menu=_menu()))

    assert result.plan.needs_context is True
    assert result.plan.context_directions == ("learning",)
    assert result.plan.context_depth == "shallow"


def test_aria_turn_arbiter_rejects_invented_menu_entries() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["local_retrieval", "runtime_action"],
            "surfaces": ["local_retrieval", "hidden_admin_shell"],
            "collections": ["aria_facts_u1", "secret_collection"],
            "actions": ["ssh_package_update_check", "rm_everything"],
            "queries": {"aria_facts_u1": "status", "secret_collection": "secret"},
            "answer_mode": "plan_action",
            "risk": "low",
            "confidence": "high",
            "reason": "Try to use a mix of allowed and invented entries.",
        }
    )

    result = asyncio.run(AriaTurnArbiter(llm).arbitrate(message="check status", menu=_menu()))

    assert result.plan.surfaces == ("local_retrieval",)
    assert result.plan.collections == ("aria_facts_u1",)
    assert result.plan.actions == ("ssh_package_update_check",)
    assert result.plan.queries == {"aria_facts_u1": "status"}
    assert result.rejected["surfaces"] == ("hidden_admin_shell",)
    assert result.rejected["collections"] == ("secret_collection",)
    assert result.rejected["actions"] == ("rm_everything",)


def test_aria_turn_arbiter_forces_confirmation_for_risky_actions() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["runtime_action"],
            "surfaces": ["runtime"],
            "actions": ["discord_send"],
            "answer_mode": "plan_action",
            "risk": "medium",
            "needs_confirmation": False,
            "confidence": "high",
            "reason": "The user wants to send a message.",
        }
    )

    result = asyncio.run(AriaTurnArbiter(llm).arbitrate(message="schick eine Nachricht an Discord", menu=_menu()))

    assert result.plan.actions == ("discord_send",)
    assert result.plan.needs_confirmation is True
    assert result.plan.risk == "medium"


def test_aria_turn_arbiter_accepts_registered_surface_context_requests() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "website": {
                    "sports-watch": {
                        "url": "https://example.invalid/sports",
                        "title": "Sports Watch",
                        "group_name": "Sport",
                    }
                }
            },
        }
    )
    llm = _ArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "Sport",
                    "depth": "meta",
                    "limit": 5,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks what configured observed websites exist for a topic.",
        }
    )

    result = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message='was fuer websites habe ich unter beobachtung zum thema "Sport"?',
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            user_id="u1",
            request_id="r1",
        )
    )

    assert result.plan.intents == ("context_inventory",)
    assert result.plan.surfaces == ("connections",)
    assert result.plan.context_directions == ("connections",)
    assert len(result.plan.context_requests) == 1
    assert result.plan.context_requests[0].surface_id == "connections"
    assert result.plan.context_requests[0].mode == "inventory"
    assert result.plan.context_requests[0].query == "Sport"
    assert result.plan.queries["connections"] == "Sport"
    assert result.plan.needs_confirmation is False
    assert llm.last_payload is not None
    assert "surface_meta_context" in llm.last_payload
    assert llm.last_payload["surface_meta_context"]["contract"]["select_registered_surface_ids_only"] is True


def test_aria_turn_arbiter_does_not_override_full_plan_with_inventory_frame() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "rss": {
                    "sports-watch": {
                        "url": "https://example.invalid/sports.xml",
                        "title": "Sports Watch",
                        "group_name": "Sport",
                    }
                }
            },
        }
    )
    llm = _FastContextArbiterLLM(
        fast_payload={"use_context": False, "confidence": "low", "reason": "need_full"},
        full_payload={
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory", "notes", "docs"],
            "surfaces": ["memory", "notes", "docs"],
            "context_requests": [
                {"surface_id": "memory", "mode": "exists", "query": "Orchideenzucht"},
                {"surface_id": "notes", "mode": "search", "query": "Orchideenzucht"},
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "surface drift from follow-up",
        },
    )

    result = asyncio.run(
        AriaTurnArbiter(llm).arbitrate(
            message="und was ist mit Orchideenzucht?",
            menu=_menu(),
            surface_registry=build_builtin_surface_registry(settings),
            turn_context={
                "last_turn_frame": {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "topic": "Sport",
                    "confidence": 0.9,
                }
            },
            user_id="u1",
            request_id="r1",
        )
    )

    assert result.plan.intents == ("local_retrieval",)
    assert result.plan.context_directions == ("memory", "notes", "docs")
    assert len(result.plan.context_requests) == 2
    assert result.plan.context_requests[0].surface_id == "memory"
    assert result.plan.context_requests[0].mode == "exists"
    assert result.plan.context_requests[0].query == "Orchideenzucht"


def test_aria_turn_arbiter_falls_back_on_low_confidence() -> None:
    llm = _ArbiterLLM({"intents": ["runtime_action"], "actions": ["discord_send"], "confidence": "low", "reason": "unsure"})

    result = asyncio.run(AriaTurnArbiter(llm).arbitrate(message="vielleicht irgendwas machen", menu=_menu()))

    assert result.source == "fallback"
    assert result.plan.intents == ("chat",)
    assert result.plan.reason == "arbiter_low_confidence"


def test_web_pre_pipeline_gate_skips_llm_for_normal_free_text() -> None:
    llm = _ArbiterLLM({"intents": ["runtime_action"], "actions": ["watched_website_action"], "confidence": "high"})
    deps = SimpleNamespace(pipeline=_WebGatePipeline(llm))

    actions = asyncio.run(
        _pre_pipeline_aria_actions(
            clean_message="was weiss ARIA noch ueber meine UI-Regel?",
            username="u1",
            lang="de",
            deps=deps,
        )
    )

    assert actions == set()
    assert llm.operations == []


def test_web_pre_pipeline_gate_keeps_slash_shortcuts() -> None:
    llm = _ArbiterLLM({"intents": ["chat"], "confidence": "high"})
    deps = SimpleNamespace(pipeline=_WebGatePipeline(llm))

    actions = asyncio.run(
        _pre_pipeline_aria_actions(
            clean_message="/websites",
            username="u1",
            lang="de",
            deps=deps,
        )
    )

    assert actions == {"notes_action", "watched_website_action"}
    assert llm.operations == []


def test_web_pre_pipeline_gate_ignores_action_name_without_action_intent() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "actions": ["watched_website_action"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "Sport"}],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks what is configured, not to execute a website flow.",
        }
    )
    deps = SimpleNamespace(pipeline=_WebGatePipeline(llm))

    actions = asyncio.run(
        _pre_pipeline_aria_actions(
            clean_message='was fuer websites habe ich unter beobachtung zum thema "Sport"?',
            username="u1",
            lang="de",
            deps=deps,
        )
    )

    assert actions == set()
    assert llm.operations == []


def test_web_pre_pipeline_gate_does_not_consume_follow_up_frame() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "IT-Security"}],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The follow-up continues the previous inventory frame.",
        }
    )
    deps = SimpleNamespace(pipeline=_WebGatePipelineWithFrame(llm), settings=Settings.model_validate({"llm": {"model": "fake"}}))

    decision = asyncio.run(
        _pre_pipeline_aria_decision(
            clean_message="und was ist mit it-security?",
            username="u1",
            lang="de",
            deps=deps,
        )
    )

    assert decision.actions == set()
    assert decision.arbitration is None
    assert llm.operations == []


def test_selected_side_action_without_executor_result_does_not_fall_back_to_chat() -> None:
    outcome = _selected_action_not_handled_outcome({"watched_website_action"}, "de")

    assert "keinen passenden ausfuehrbaren Webseiten-Flow" in outcome.assistant_text
    assert "Ich fuehre nichts aus" in outcome.assistant_text
    assert outcome.intent_label == "action"


def test_pipeline_aria_turn_arbiter_can_drive_local_retrieval_query() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM()
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "was erinnert ARIA zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "ok"
    assert "memory_recall" in result.intents
    assert memory.calls
    recall_calls = [call for call in memory.calls if call["params"].get("action") == "recall" and call["params"].get("collection") != "aria_learning_active_hints_u1"]
    assert recall_calls[-1]["query"] == "UI-Regel klickbare Optionen"
    assert recall_calls[-1]["params"]["target_collections"] == ["aria_facts_u1", "aria_learning_u1"]
    assert recall_calls[-1]["params"]["include_documents"] is False
    assert ARIA_TURN_ARBITRATION_OPERATION in llm.operations
    assert "turn_intent_arbitration" not in llm.operations
    assert "pre_rag_action_arbitration" not in llm.operations
    assert "capability_draft_decision" not in llm.operations
    assert "recipe_execution_intent" not in llm.operations
    assert "chat_local_context_relevance" not in llm.operations
    assert any("Routing Debug: aria_turn_surface_action_arbitration" in line for line in result.detail_lines)
    assert any("Routing Debug: context_ledger phase=selection" in line for line in result.detail_lines)
    assert any("memory_targets=aria_facts_u1,aria_learning_u1" in line for line in result.detail_lines)
    assert any("Routing Debug: context_ledger phase=loaded" in line for line in result.detail_lines)
    assert any("Routing Debug: memory_recall_targets" in line for line in result.detail_lines)
    assert any("Routing Debug: chat_local_context_relevance skipped reason=turn_plan_selected_context" in line for line in result.detail_lines)
    assert "chat_freshness" not in llm.operations


def test_pipeline_memory_inventory_with_topic_uses_recall_context_not_inventory_only() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory", "local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory"],
            "context_depth": "shallow",
            "surfaces": ["memory"],
            "collections": ["aria_facts_u1", "aria_knowledge_u1"],
            "queries": {
                "aria_facts_u1": "Donald Trump",
                "aria_knowledge_u1": "Donald Trump",
            },
            "context_requests": [{"surface_id": "memory", "mode": "inventory", "query": "Donald Trump"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks whether topic-specific information exists in memory.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "habe ich informationen zu donald trump in meinem memory?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Nein, in den durchsuchten Memory-Quellen habe ich dazu nichts Passendes gefunden."
    assert "[FAKT] UI-Regel" not in result.text
    recall_calls = [call for call in memory.calls if call["params"].get("action") == "recall"]
    assert recall_calls
    assert recall_calls[-1]["query"] == "Donald Trump"
    assert any("memory_recall_targets" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_fast_path kind=memory_exists" in line for line in result.detail_lines)
    assert any("Routing Debug: stage_timing stage=memory_exists_loader" in line for line in result.detail_lines)
    assert any("Routing Debug: evidence_filter surface=memory mode=exists matched=false" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=memory_exists" in line for line in result.detail_lines)
    assert not any("filtered=memory_recall" in line for line in result.detail_lines)
    assert not any("context_inventory surface=memory" in line for line in result.detail_lines)
    assert "final_chat_response" not in llm.operations


def test_pipeline_memory_exists_ignores_question_words_as_evidence() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory"],
            "context_depth": "shallow",
            "surfaces": ["memory"],
            "collections": ["aria_facts_u1", "aria_knowledge_u1"],
            "context_requests": [{"surface_id": "memory", "mode": "exists", "query": "und was ist mit Orchideenzucht?"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user checks whether memory contains a topic.",
        }
    )
    memory = _PipelineQuestionWordMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "und was ist mit Orchideenzucht?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Nein, in den durchsuchten Memory-Quellen habe ich dazu nichts Passendes gefunden."
    assert "management server" not in result.text
    assert any("Routing Debug: evidence_filter surface=memory mode=exists matched=false terms=orchideenzucht" in line for line in result.detail_lines)
    assert not any("terms=und,was,ist,mit" in line for line in result.detail_lines)
    assert "final_chat_response" not in llm.operations


def test_pipeline_direct_memory_search_can_answer_without_final_llm() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory"],
            "context_depth": "shallow",
            "surfaces": ["memory"],
            "context_requests": [{"surface_id": "memory", "mode": "search", "query": "UI-Regel klickbare Optionen"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for a direct memory lookup.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "was steht im memory zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text.startswith("In deinem Memory habe ich dazu gefunden:")
    assert "[FAKT] UI-Regel" in result.text
    assert "final_chat_response" not in llm.operations
    assert any("Routing Debug: direct_context_answer kind=memory_search" in line for line in result.detail_lines)
    assert any("Routing Debug: evidence_filter surface=memory mode=search matched=true" in line for line in result.detail_lines)
    assert any("Routing Debug: stage_timing stage=pipeline_wall_time" in line for line in result.detail_lines)


def test_pipeline_memory_search_without_topic_evidence_stays_source_bound_empty() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory"],
            "context_depth": "shallow",
            "surfaces": ["memory"],
            "context_requests": [{"surface_id": "memory", "mode": "search", "query": "Donald Trump"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for a direct memory lookup.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "habe ich informationen zu donald trump in meinem memory?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "nichts Passendes gefunden" in result.text
    assert "[FAKT] UI-Regel" not in result.text
    assert "final_chat_response" not in llm.operations
    assert any("Routing Debug: evidence_filter surface=memory mode=search matched=false terms=donald,trump" in line for line in result.detail_lines)
    assert any("Routing Debug: local_context_empty directions=memory" in line and "reason=no_evidence_sources" in line for line in result.detail_lines)


def test_pipeline_memory_exists_does_not_pull_sessions_without_session_request() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["memory"],
            "context_depth": "shallow",
            "surfaces": ["memory"],
            "collections": ["aria_facts_u1", "aria_sessions_u1_260617", "aria_knowledge_u1"],
            "queries": {
                "aria_facts_u1": "Donald Trump",
                "aria_sessions_u1_260617": "Donald Trump",
                "aria_knowledge_u1": "Donald Trump",
            },
            "context_requests": [{"surface_id": "memory", "mode": "exists", "query": "Donald Trump"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks whether information exists in memory.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "habe ich informationen zu donald trump in meinem memory?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    recall_calls = [call for call in memory.calls if call["params"].get("action") == "recall"]
    assert recall_calls
    assert recall_calls[-1]["params"]["target_collections"] == ["aria_facts_u1", "aria_knowledge_u1"]
    assert any("memory_targets=aria_facts_u1,aria_knowledge_u1" in line for line in result.detail_lines)


def test_pipeline_aria_turn_arbiter_can_add_notes_retrieval(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "UI-Regel klickbare Optionen"
        return [
            SimpleNamespace(
                title="UI Regeln",
                folder="ARIA",
                note_id="n1",
                snippet="Klickbare Optionen gehen direkt zu Einstellungen.",
            )
        ]

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["notes"],
            "surfaces": ["local_retrieval"],
            "collections": ["aria_notes_u1"],
            "queries": {"aria_notes_u1": "UI-Regel klickbare Optionen"},
            "priority": ["notes"],
            "answer_mode": "answer_with_source_grouping",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for notes.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "was steht in meinen Notizen zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text.startswith("In deinen Notizen habe ich dazu gefunden:")
    assert "Klickbare Optionen gehen direkt zu Einstellungen" in result.text
    assert "notes_search" in result.intents
    assert "memory_recall" not in result.intents
    recall_calls = [call for call in memory.calls if call["params"].get("action") == "recall" and call["params"].get("collection") != "aria_learning_active_hints_u1"]
    assert recall_calls == []
    assert any("Routing Debug: notes_retrieval query=UI-Regel klickbare Optionen" in line for line in result.detail_lines)
    assert any("Routing Debug: context_ledger phase=selection" in line for line in result.detail_lines)
    assert any("memory_enabled=false" in line for line in result.detail_lines)
    assert not any("Routing Debug: pre_rag_action_gate" in line for line in result.detail_lines)
    assert not any("Routing Debug: memory_recall skipped" in line for line in result.detail_lines)
    assert any("Note context" in line or "Notiz-Kontext" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=notes_search" in line for line in result.detail_lines)
    assert "final_chat_response" not in llm.operations


def test_pipeline_notes_inventory_question_skips_answer_composer(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "area41"
        return [
            SimpleNamespace(
                title="AREA41/DC4131",
                folder="Area41",
                note_id="n1",
                snippet="Homepage: https://area41.io",
            ),
            SimpleNamespace(
                title="Aktive Projekt-Übersicht",
                folder="Fischerman Projekte",
                note_id="n2",
                snippet="AREA41 Wear-Aufgaben und Links.",
            ),
            SimpleNamespace(
                title="ARIA - Technische Architektur",
                folder="ARIA",
                note_id="n3",
                snippet="Meta-Katalog, Routing und Runtime-Contracts.",
            ),
            SimpleNamespace(
                title="Audima Sway",
                folder="Musik",
                note_id="n4",
                snippet="Arrangement-Ideen und Songstruktur.",
            ),
        ]

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["notes"],
            "surfaces": ["notes"],
            "context_requests": [{"surface_id": "notes", "mode": "search", "query": "area41"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks what notes exist for Area41.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)

    result = asyncio.run(
        pipeline.process(
            "was habe ich für notes über area41",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text.startswith("Ich habe 2 passende Notizen gefunden:")
    assert "AREA41/DC4131 (Area41)" in result.text
    assert "Aktive Projekt-Übersicht (Fischerman Projekte)" in result.text
    assert "ARIA - Technische Architektur" not in result.text
    assert "Audima Sway" not in result.text
    assert "aria_answer_composer" not in llm.operations
    assert any("Routing Debug: evidence_filter surface=notes mode=search matched=true terms=area41" in line for line in result.detail_lines)
    assert any("Routing Debug: fast_notes_inventory_filter kept=2 rejected=2 terms=area41" in line for line in result.detail_lines)
    assert any("answer_composer skipped reason=fast_notes_inventory_answer" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=notes_search" in line for line in result.detail_lines)


def test_pipeline_notes_only_turn_does_not_run_auto_memory_context(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "UI-Regel klickbare Optionen"
        return [
            SimpleNamespace(
                title="UI Regeln",
                folder="ARIA",
                note_id="n1",
                snippet="Klickbare Optionen gehen direkt zu Einstellungen.",
            )
        ]

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "auto_memory": {"agentic_extraction_enabled": True},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["notes"],
            "surfaces": ["notes"],
            "context_requests": [{"surface_id": "notes", "mode": "search", "query": "UI-Regel klickbare Optionen"}],
            "answer_mode": "answer_with_source_grouping",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for notes.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "was steht in meinen Notizen zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
            auto_memory_enabled=True,
        )
    )

    assert result.text.startswith("In deinen Notizen habe ich dazu gefunden:")
    assert "Klickbare Optionen gehen direkt zu Einstellungen" in result.text
    assert "auto_memory_extraction_decision" not in llm.operations
    assert "memory_session" not in "\n".join(result.detail_lines)
    assert "memory_user" not in "\n".join(result.detail_lines)
    assert "[FAKT]" not in result.text
    assert "final_chat_response" not in llm.operations


def test_pipeline_aria_turn_notes_only_empty_context_returns_guardrail_response(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "UI-Regel klickbare Optionen"
        return []

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["notes"],
            "surfaces": ["local_retrieval"],
            "collections": ["aria_notes_u1"],
            "queries": {"aria_notes_u1": "UI-Regel klickbare Optionen"},
            "priority": ["notes"],
            "answer_mode": "answer_with_source_grouping",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for notes.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "was steht in meinen Notizen zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe in deinen Notizen dazu nichts Passendes gefunden."
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION, "aria_answer_composer"]
    assert "notes_search" in result.intents
    assert "memory_recall" not in result.intents
    recall_calls = [call for call in memory.calls if call["params"].get("action") == "recall" and call["params"].get("collection") != "aria_learning_active_hints_u1"]
    assert recall_calls == []
    assert any("Routing Debug: context_ledger phase=loaded skills=- sources=0" in line for line in result.detail_lines)
    assert any("Routing Debug: local_context_empty directions=notes collections=aria_notes_u1" in line for line in result.detail_lines)
    assert not any("Routing Debug: pre_rag_action_gate" in line for line in result.detail_lines)
    assert not any("Routing Debug: memory_recall skipped" in line for line in result.detail_lines)


def test_pipeline_notes_only_irrelevant_hits_return_guardrail_response(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "UI-Regel interface guidelines"
        return [
            SimpleNamespace(
                title="Windmill",
                folder="AI - Stuff",
                note_id="n1",
                snippet="Orchestration platform notes and task scheduling.",
            ),
            SimpleNamespace(
                title="Otamatone",
                folder="Musik",
                note_id="n2",
                snippet="Japanese musical instrument and accessories.",
            ),
        ]

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["local_retrieval"],
            "needs_context": True,
            "context_directions": ["notes"],
            "surfaces": ["notes"],
            "collections": ["aria_notes_u1"],
            "context_requests": [{"surface_id": "notes", "mode": "search", "query": "UI-Regel interface guidelines"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "direct notes search",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)

    result = asyncio.run(
        pipeline.process(
            "was steht in meinen Notizen zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe in deinen Notizen dazu nichts Passendes gefunden."
    assert "final_chat_response" not in llm.operations
    assert any("Routing Debug: evidence_filter surface=notes mode=search matched=false" in line for line in result.detail_lines)
    assert any("reason=no_evidence_sources" in line for line in result.detail_lines)


def test_pipeline_aria_turn_connection_inventory_uses_context_not_action() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {
                "website": {
                    "sports-watch": {
                        "url": "https://example.invalid/sports",
                        "title": "Sports Watch",
                        "description": "Observed sports website",
                        "group_name": "Sport",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "meta",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "Sport",
                    "depth": "meta",
                    "limit": 5,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for configured observed websites about Sport, which is inventory context.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            'was fuer websites habe ich unter beobachtung zum thema "Sport"?',
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text.startswith("Ich habe passende konfigurierte Quellen gefunden:")
    assert "Sports Watch" in result.text
    assert "sports-watch" in result.text
    assert "https://example.invalid/sports" not in result.text
    assert "context_inventory" in result.intents
    assert "memory_recall" not in result.intents
    assert not any(call["params"].get("action") == "recall" for call in memory.calls)
    assert ARIA_TURN_ARBITRATION_OPERATION in llm.operations
    assert "final_chat_response" not in llm.operations
    assert "turn_intent_arbitration" not in llm.operations
    assert "pre_rag_action_arbitration" not in llm.operations
    assert "capability_draft_decision" not in llm.operations
    assert "recipe_execution_intent" not in llm.operations
    assert any("Routing Debug: context_inventory surface=connections mode=inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=inventory" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_uses_qdrant_inventory_index(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "infoguard-pentest": {
                        "feed_url": "https://labs.infoguard.ch/archive/category/Pentest/",
                        "title": "InfoGuard Labs Pentest Archiv",
                        "description": "Security Testing und Schwachstellen",
                        "group_name": "Security",
                        "tags": ["Pentest", "IT-Sicherheit", "CVE"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "IT-Security"}],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for observed sources about IT security.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "und was ist mit it-security?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "infoguard-pentest" in result.text
    assert "InfoGuard Labs Pentest Archiv" in result.text
    assert "https://labs.infoguard.ch" not in result.text
    assert "score=" not in result.text
    assert any("Routing Debug: inventory_index surface=connections matches=1 query=IT-Security" in line for line in result.detail_lines)
    assert any("Routing Debug: evidence_filter surface=connections kept=1" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: stage_timing stage=aria_turn_arbiter" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_fast_path_skips_broad_local_loader(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "heise-security": {
                        "title": "Heise Security News",
                        "description": "Aktuelle IT-Sicherheitsmeldungen, Schwachstellen und Cyberangriffe",
                        "group_name": "Security",
                        "tags": ["security", "cybersecurity", "it-security"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory", "local_retrieval"],
            "needs_context": True,
            "context_directions": ["connections", "memory", "notes", "docs"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "collections": ["aria_facts_u1", "aria_notes_u1", "aria_docs_u1"],
            "context_requests": [
                {"surface_id": "connections", "mode": "inventory", "query": "IT-Security"},
                {"surface_id": "memory", "mode": "search", "query": "IT-Security"},
                {"surface_id": "notes", "mode": "search", "query": "IT-Security"},
                {"surface_id": "docs", "mode": "search", "query": "IT-Security"},
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for observed configured sources; local surfaces are optional background context.",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "und was ist mit it-security?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "heise-security" in result.text
    assert not memory.calls
    assert "final_chat_response" not in llm.operations


def test_pipeline_meta_catalog_routing_is_first_semantic_contract(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "heise-security": {
                        "title": "Heise Security News",
                        "description": "Aktuelle IT-Sicherheitsmeldungen, Schwachstellen und Cyberangriffe",
                        "group_name": "Security",
                        "tags": ["security", "cybersecurity", "it-security"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    inventory_docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(inventory_docs, index_hash="test-index")
    )
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|rss|heise-security"],
            "context_requests": [
                {
                    "catalog_id": "connection|rss|heise-security",
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "IT-Security",
                }
            ],
            "intents": ["context_inventory"],
            "surfaces": ["connections"],
            "actions": [],
            "answer_mode": "answer_from_context",
            "context_depth": "shallow",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.91,
            "reason": "catalog source match",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "und was ist mit it-security?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "heise-security" in result.text
    assert META_CATALOG_ROUTING_OPERATION in llm.operations
    assert ARIA_TURN_ARBITRATION_OPERATION not in llm.operations
    assert "turn_intent_arbitration" not in llm.operations
    assert "pre_rag_action_arbitration" not in llm.operations
    assert "capability_draft_decision" not in llm.operations
    assert "recipe_execution_intent" not in llm.operations
    assert "chat_freshness" not in llm.operations
    assert "final_chat_response" not in llm.operations
    assert any("source=aria_meta_catalog_routing" in line for line in result.detail_lines)
    assert any("Routing Debug: meta_catalog_contract phase=context legacy_semantics=skipped" in line for line in result.detail_lines)
    assert any(
        "Routing Debug: inventory_index surface=connections matches=1 query=IT-Security" in line
        and "authoritative=true" in line
        for line in result.detail_lines
    )
    assert any("Routing Debug: direct_context_fast_path kind=inventory" in line for line in result.detail_lines)
    assert not any("filtered=memory_recall" in line for line in result.detail_lines)
    assert any("Routing Debug: stage_timing stage=context_inventory_loader" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_surface_context_without_requests_loads_inventory(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "sports-feed": {
                        "title": "Sports Watch",
                        "description": "Sport news and match coverage",
                        "group_name": "Sport",
                        "tags": ["Sport"],
                    },
                    "security-feed": {
                        "title": "SecurityWeek",
                        "description": "Cybersecurity news and vulnerability research",
                        "group_name": "Security",
                        "tags": ["Security", "CVE"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    inventory_docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(inventory_docs, index_hash="test-index")
    )
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": [],
            "context_requests": [],
            "intents": ["chat"],
            "surfaces": ["connections"],
            "actions": [],
            "answer_mode": "direct_answer",
            "context_depth": "shallow",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.95,
            "reason": "connections inventory topic",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was für websites/rss habe ich unter beobachtung zum thema Sport?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "sports-feed" in result.text
    assert "keinen Zugriff" not in result.text
    assert "final_chat_response" not in llm.operations
    assert any("source=aria_meta_catalog_routing" in line for line in result.detail_lines)
    assert any("requests=connections:inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: inventory_index surface=connections" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=inventory" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_feed_inventory_question_overrides_feed_read_action(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 8},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "alle-security-news": {
                        "title": "Alle Security News",
                        "description": "IT security news, vulnerabilities and CVE updates",
                        "group_name": "Security",
                        "tags": ["security", "it-security", "cve"],
                    },
                    "heise-security-alerts": {
                        "title": "Heise Security Alerts",
                        "description": "Security alerts and vulnerability warnings",
                        "group_name": "Security",
                        "tags": ["security", "alerts"],
                    },
                    "sports-feed": {
                        "title": "Sports Watch",
                        "description": "Sports reports and match coverage",
                        "group_name": "Sport",
                        "tags": ["sport"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    inventory_docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(inventory_docs, index_hash="test-index")
    )
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|rss|alle-security-news", "connection|rss|heise-security-alerts"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "IT security feeds",
                    "budget": {"entity_type": "connection", "kind": "rss", "ref": "alle-security-news"},
                }
            ],
            "intents": ["chat", "runtime_action"],
            "surfaces": ["connections"],
            "actions": ["rss_read_feed"],
            "answer_mode": "direct_answer",
            "contract": {"mode": "action", "evidence_policy": "source_bound"},
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.95,
            "reason": "incorrectly tries to read a feed for an inventory question",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was habe ich für news feed für it security",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["context_inventory"]
    assert "Alle Security News" in result.text
    assert "Heise Security Alerts" in result.text
    assert "Sports Watch" not in result.text
    assert "capability:feed_read" not in result.intents
    assert not any("agentic_runtime" in line and "capability=feed_read" in line for line in result.detail_lines)
    assert any("requests=connections:inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=inventory" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_selected_surface_forces_inventory_even_when_needs_context_false(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "security-feed": {
                        "title": "Security Feed",
                        "description": "Security updates",
                        "tags": ["security"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    inventory_docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(inventory_docs, index_hash="test-index")
    )
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": False,
            "catalog_ids": [],
            "context_requests": [],
            "intents": ["chat"],
            "surfaces": ["connections"],
            "actions": [],
            "answer_mode": "direct_answer",
            "context_depth": "none",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.98,
            "reason": "no catalog match, but connections surface selected",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was für websites/rss habe ich unter beobachtung zum thema rindfleisch grillieren?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "keinen Zugriff" not in result.text
    assert "final_chat_response" not in llm.operations
    assert any("requests=connections:inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=inventory" in line for line in result.detail_lines)


def test_pipeline_answer_composer_rewords_inventory_without_losing_evidence(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "sports-feed": {
                        "title": "Sports Watch",
                        "description": "Sport news and match coverage",
                        "tags": ["Sport"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    inventory_docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(inventory_docs, index_hash="test-index")
    )
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogComposerLLM(
        {
            "needs_context": True,
            "catalog_ids": [],
            "context_requests": [],
            "intents": ["chat"],
            "surfaces": ["connections"],
            "actions": [],
            "answer_mode": "direct_answer",
            "context_depth": "shallow",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.95,
            "reason": "connections inventory topic",
        },
        composer_answer="Ich habe eine passende beobachtete RSS-Quelle zu Sport gefunden: Sports Watch.",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was für websites/rss habe ich unter beobachtung zum thema Sport?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe eine passende beobachtete RSS-Quelle zu Sport gefunden: Sports Watch."
    assert "aria_answer_composer" in llm.operations
    assert any("Routing Debug: answer_composer source=llm" in line for line in result.detail_lines)


def test_pipeline_backup_action_contract_cannot_fall_back_to_chat(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {"host": "192.0.2.10", "user": "root"},
                    "srv-b": {"host": "192.0.2.11", "user": "root"},
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["runtime_action"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "actions": ["connection_action_ssh"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "sind alle server up2date",
                    "budget": {"entity_type": "connection", "kind": "ssh", "ref": "srv-a"},
                },
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "sind alle server up2date",
                    "budget": {"entity_type": "connection", "kind": "ssh", "ref": "srv-b"},
                },
            ],
            "answer_mode": "plan_action",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": "high",
            "reason": "Server update check requires SSH action.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=_InventoryEmbeddingClient())

    result = asyncio.run(
        pipeline.process(
            "sind alle server up2date ?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["capability:ssh_command"]
    assert "final_chat_response" not in llm.operations
    assert "direct_chat_response" not in llm.operations
    assert any("meta_catalog_contract phase=backup_fallback" in line for line in result.detail_lines)
    assert any("legacy_backup_action_contract phase=action_preflight chat_fallback=blocked" in line for line in result.detail_lines)
    assert any("pre_rag_action_gate action_path=unified_routing capability=ssh_command kind=ssh" in line for line in result.detail_lines)
    assert any("multi_target_ssh_preflight" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_ssh_action_refines_package_update_objective(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {"host": "192.0.2.10", "user": "root"},
                    "srv-b": {"host": "192.0.2.11", "user": "root"},
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogSshObjectiveLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh|srv-a", "connection|ssh|srv-b"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "sind meine server up2date?",
                    "budget": {"entity_type": "connection", "kind": "ssh", "ref": "srv-a"},
                },
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "sind meine server up2date?",
                    "budget": {"entity_type": "connection", "kind": "ssh", "ref": "srv-b"},
                },
            ],
            "intents": ["chat", "runtime_action"],
            "surfaces": ["connections"],
            "actions": ["connection_action_ssh"],
            "answer_mode": "plan_action",
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.95,
            "reason": "server package update status check",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "Listing... paket/example [upgradable from: 1.0]"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)

    result = asyncio.run(
        pipeline.process(
            "sind meine server up2date?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["capability:ssh_command"]
    assert ssh_calls == [("srv-a", "apt list --upgradable"), ("srv-b", "apt list --upgradable")]
    assert "capability_draft_decision" in llm.operations
    assert any("meta_catalog_contract phase=action_preflight legacy_semantics=skipped" in line for line in result.detail_lines)
    assert any("plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b command=apt list --upgradable" in line for line in result.detail_lines)


def test_pipeline_runtime_task_contract_overrides_wrong_security_rss_meta_answer(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {"host": "192.0.2.10", "user": "root", "tags": ["server"]},
                    "srv-b": {"host": "192.0.2.11", "user": "root", "tags": ["server"]},
                },
                "rss": {
                    "debian-security-advisories": {
                        "feed_url": "https://example.invalid/debian-security.xml",
                        "title": "Debian Security Advisories",
                        "description": "Security advisories and critical update news",
                        "tags": ["security", "updates"],
                    },
                    "heise-security-alerts": {
                        "feed_url": "https://example.invalid/heise-security.xml",
                        "title": "Heise Security Alerts",
                        "description": "Security alerts and vulnerabilities",
                        "tags": ["security", "updates"],
                    },
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogSshObjectiveLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|rss|debian-security-advisories", "connection|rss|heise-security-alerts"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "answer",
                    "query": "server updates security advisories",
                    "budget": {"entity_type": "connection", "kind": "rss", "ref": "debian-security-advisories"},
                },
                {
                    "surface_id": "connections",
                    "mode": "answer",
                    "query": "server updates security alerts",
                    "budget": {"entity_type": "connection", "kind": "rss", "ref": "heise-security-alerts"},
                },
            ],
            "intents": ["chat"],
            "surfaces": ["connections"],
            "actions": [],
            "answer_mode": "direct_answer",
            "contract": {"mode": "answer", "evidence_policy": "source_bound"},
            "context_depth": "shallow",
            "risk": "low",
            "needs_confirmation": False,
            "confidence": 0.95,
            "reason": "wrongly selected configured security RSS sources",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "Listing... openssl/stable-security 3.0 [upgradable from: 2.0]"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)

    result = asyncio.run(
        pipeline.process(
            "brauchen meine server updates und falls ja, welches sind die wichtigsten",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["capability:ssh_command"]
    assert ssh_calls == [("srv-a", "apt list --upgradable"), ("srv-b", "apt list --upgradable")]
    assert "capability_draft_decision" in llm.operations
    assert any("runtime_task_contract source=capability_draft_decision" in line for line in result.detail_lines)
    assert any("plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b command=apt list --upgradable" in line for line in result.detail_lines)


def test_pipeline_mixed_rss_ssh_update_action_contract_executes_ssh_not_feed(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {"host": "192.0.2.10", "user": "root", "tags": ["server"]},
                    "srv-b": {"host": "192.0.2.11", "user": "root", "tags": ["server"]},
                },
                "rss": {
                    "debian-security-advisories": {
                        "feed_url": "https://example.invalid/debian-security.xml",
                        "title": "Debian Security Advisories",
                        "description": "Security advisories and critical update news",
                        "tags": ["security", "updates"],
                    },
                    "heise-security-alerts": {
                        "feed_url": "https://example.invalid/heise-security.xml",
                        "title": "Heise Security Alerts",
                        "description": "Security alerts and vulnerabilities",
                        "tags": ["security", "updates"],
                    },
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogSshObjectiveLLM(
        {
            "needs_context": True,
            "catalog_ids": [
                "connection|rss|debian-security-advisories",
                "connection|rss|heise-security-alerts",
                "connection|ssh|srv-a",
                "connection|ssh|srv-b",
            ],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "server update security advisories",
                    "budget": {"entity_type": "connection", "kind": "rss", "ref": "debian-security-advisories"},
                },
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "server update security alerts",
                    "budget": {"entity_type": "connection", "kind": "rss", "ref": "heise-security-alerts"},
                },
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "server update status",
                    "budget": {"entity_type": "connection", "kind": "ssh", "ref": "srv-a"},
                },
                {
                    "surface_id": "connections",
                    "mode": "action",
                    "query": "server update status",
                    "budget": {"entity_type": "connection", "kind": "ssh", "ref": "srv-b"},
                },
            ],
            "intents": ["chat", "runtime_action"],
            "surfaces": ["connections"],
            "actions": ["rss_read_feed", "ssh_run_command"],
            "answer_mode": "direct_answer",
            "contract": {"mode": "action", "evidence_policy": "source_bound"},
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.92,
            "reason": "read advisories and inspect configured servers for updates",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "Listing... openssl/stable-security 3.0 [upgradable from: 2.0]"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)

    result = asyncio.run(
        pipeline.process(
            "brauchen meine server updates und falls ja, was wären die wichtigsten",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["capability:ssh_command"]
    assert ssh_calls == [("srv-a", "apt list --upgradable"), ("srv-b", "apt list --upgradable")]
    assert "capability:feed_read" not in result.intents
    assert any("pre_rag_action_gate action_path=unified_routing capability=ssh_command kind=ssh" in line for line in result.detail_lines)
    assert any("plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b command=apt list --upgradable" in line for line in result.detail_lines)
    assert not any("agentic_runtime ref=debian-security-advisories kind=rss capability=feed_read" in line for line in result.detail_lines)


def test_pipeline_meta_contract_ssh_targets_survive_plural_context_resolution(monkeypatch) -> None:
    _ = monkeypatch
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "debdev-srv01": {
                        "host": "192.0.2.20",
                        "user": "root",
                        "title": "Development server",
                        "aliases": ["und"],
                    },
                    "ubnsrv-gaming": {
                        "host": "192.0.2.21",
                        "user": "root",
                        "title": "Gaming server",
                        "tags": ["server"],
                    },
                    "ubnsrv-netalert": {
                        "host": "192.0.2.22",
                        "user": "root",
                        "title": "Netalert server",
                        "tags": ["server"],
                    },
                },
                "rss": {
                    "debian-security-advisories": {
                        "feed_url": "https://example.invalid/debian-security.xml",
                        "title": "Debian Security Advisories",
                        "description": "Security advisories and critical update news",
                        "tags": ["security", "updates"],
                    },
                    "heise-security-alerts": {
                        "feed_url": "https://example.invalid/heise-security.xml",
                        "title": "Heise Security Alerts",
                        "description": "Security alerts and vulnerabilities",
                        "tags": ["security", "updates"],
                    },
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=None, embedding_client=_InventoryEmbeddingClient())
    draft = CapabilityDraft(
        capability="ssh_command",
        connection_kind="ssh",
        content="apt list --upgradable",
        connection_refs=["ubnsrv-gaming", "ubnsrv-netalert"],
        notes=[
            "capability_draft_source:meta_catalog",
            "target_scope:multi_target",
            "turn_contract_target_refs:ubnsrv-gaming,ubnsrv-netalert",
        ],
    )

    resolved = asyncio.run(
        pipeline._resolve_unified_routed_action(
            "brauchen meine server updates und falls ja, welches sind die wichtigsten ?",
            user_id="u1",
            language="de",
            capability_draft=draft,
            llm_client=None,
        )
    )

    assert resolved is not None
    payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
    assert payload["connection_ref"] == ""
    assert payload["connection_refs"] == ["ubnsrv-gaming", "ubnsrv-netalert"]
    assert payload["content"] == "apt list --upgradable"
    detail_lines = list(resolved.get("detail_lines") or [])
    assert any(
        "plural_target_scope bound_by_turn_contract kind=ssh refs=ubnsrv-gaming, ubnsrv-netalert source=meta_catalog"
        in line
        for line in detail_lines
    )
    assert any(
        "plural_target_scope selected_multi_target kind=ssh refs=ubnsrv-gaming, ubnsrv-netalert command=apt list --upgradable"
        in line
        for line in detail_lines
    )


def test_pipeline_meta_contract_broad_server_health_expands_sampled_targets_to_ssh_fleet(monkeypatch) -> None:
    _ = monkeypatch
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "debdev-srv01": {
                        "host": "192.0.2.20",
                        "user": "root",
                        "title": "Development server",
                        "aliases": ["und"],
                    },
                    "srv-dev02": {
                        "host": "192.0.2.23",
                        "user": "root",
                        "title": "Dev server",
                        "tags": ["server"],
                    },
                    "ubnsrv-gaming": {
                        "host": "192.0.2.21",
                        "user": "root",
                        "title": "Gaming server",
                        "tags": ["server"],
                    },
                    "ubnsrv-netalert": {
                        "host": "192.0.2.22",
                        "user": "root",
                        "title": "Netalert server",
                        "tags": ["server"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=None, embedding_client=_InventoryEmbeddingClient())
    draft = CapabilityDraft(
        capability="ssh_command",
        connection_kind="ssh",
        content="uptime",
        connection_refs=["ubnsrv-gaming", "ubnsrv-netalert", "srv-dev02"],
        notes=[
            "capability_draft_source:meta_catalog",
            "target_scope:multi_target",
            "target_intent:health_check",
            "turn_contract_target_refs:ubnsrv-gaming,ubnsrv-netalert,srv-dev02",
        ],
    )

    resolved = asyncio.run(
        pipeline._resolve_unified_routed_action(
            "wie fit sind meine server?",
            user_id="u1",
            language="de",
            capability_draft=draft,
            llm_client=None,
        )
    )

    assert resolved is not None
    payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
    assert payload["connection_ref"] == ""
    assert payload["connection_refs"] == ["debdev-srv01", "srv-dev02", "ubnsrv-gaming", "ubnsrv-netalert"]
    assert payload["content"] == "uptime -p && df -h && free -h"
    detail_lines = list(resolved.get("detail_lines") or [])
    assert any("plural_target_scope expanded_by_fleet_contract kind=ssh" in line for line in detail_lines)
    assert any(
        "plural_target_scope selected_multi_target kind=ssh refs=debdev-srv01, srv-dev02, ubnsrv-gaming, ubnsrv-netalert"
        in line
        for line in detail_lines
    )


def test_pre_rag_action_seed_bypasses_context_inventory_intent_filter_for_meta_contract() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "ubnsrv-gaming": {
                        "host": "192.0.2.21",
                        "user": "root",
                        "title": "Gaming server",
                        "tags": ["server"],
                    },
                },
                "sftp": {
                    "pihole1": {"host": "192.0.2.31", "user": "root", "path": "/"},
                    "srv-dev02": {"host": "192.0.2.32", "user": "root", "path": "/"},
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineMetaCatalogCapacityObjectiveLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh|ubnsrv-gaming", "connection|sftp|pihole1", "connection|sftp|srv-dev02"],
            "context_requests": [],
            "intents": ["chat", "context_inventory"],
            "surfaces": ["connections"],
            "actions": [],
            "answer_mode": "direct_answer",
            "contract": {"mode": "action", "evidence_policy": "source_bound"},
            "risk": "low",
            "needs_confirmation": True,
            "confidence": 0.88,
            "reason": "disk space check across configured server connections",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=_InventoryEmbeddingClient())
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "Filesystem Size Used Avail Use% Mounted on\n/dev/sda1 50G 20G 30G 40% /"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)
    draft = CapabilityDraft(
        capability="ssh_command",
        connection_kind="ssh",
        explicit_connection_ref="ubnsrv-gaming",
        content="",
        confidence=0.88,
        notes=[
            "capability_draft_source:meta_catalog",
            "turn_contract_source:aria_meta_catalog_routing",
            "turn_contract_priority:connection|ssh|ubnsrv-gaming,connection|sftp|pihole1,connection|sftp|srv-dev02",
        ],
    )

    result = asyncio.run(
        pipeline._run_pre_rag_action_stage(
            message="haben die festplatten auf meinen server genug harddisk speicher",
            user_id="u1",
            request_id="r1",
            source="test",
            decision=SimpleNamespace(intents=["chat", "context_inventory"], level=2),
            start=0.0,
            runtime_recipes=[],
            language="de",
            seed_capability_draft=draft,
            semantic_source=META_CATALOG_ROUTING_OPERATION,
        )
    )

    assert result.direct_result is not None
    assert result.capability_draft is not None
    assert result.capability_draft.capability == "ssh_command"
    assert result.capability_draft.content == "df -h"
    assert ssh_calls == [("ubnsrv-gaming", "df -h")]
    assert any(
        "pre_rag_action_gate action_path=unified_routing capability=ssh_command kind=ssh explicit_ref=ubnsrv-gaming"
        in line
        for line in result.direct_result.detail_lines
    )


def test_pipeline_meta_catalog_local_family_binds_memory_collection(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    meta_docs = build_meta_catalog_documents(settings)
    asyncio.run(
        MetaCatalogStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=meta_catalog_collection_name(settings),
        ).rebuild_documents(meta_docs, catalog_hash=meta_catalog_documents_fingerprint(meta_docs))
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fake_qdrant_client)
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": ["local|memory|preferences"],
            "context_requests": [
                {
                    "catalog_id": "local|memory|preferences",
                    "surface_id": "memory",
                    "mode": "search",
                    "query": "UI-Regel",
                }
            ],
            "intents": ["local_retrieval"],
            "surfaces": ["memory"],
            "actions": [],
            "answer_mode": "answer_from_context",
            "context_depth": "shallow",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.91,
            "reason": "catalog preference memory",
        }
    )
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "was weiss aria zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    recall_calls = [call for call in memory.calls if call["params"].get("action") == "recall"]
    assert recall_calls
    assert recall_calls[-1]["params"]["target_collections"] == ["aria_preferences_u1"]
    assert recall_calls[-1]["params"]["include_documents"] is False
    assert META_CATALOG_ROUTING_OPERATION in llm.operations
    assert ARIA_TURN_ARBITRATION_OPERATION not in llm.operations
    assert "turn_intent_arbitration" not in llm.operations
    assert any("source=aria_meta_catalog_routing" in line for line in result.detail_lines)
    assert any("memory_targets=aria_preferences_u1" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_index_rejects_semantic_neighbors_without_topic_evidence(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "security-feed": {
                        "title": "SecurityWeek",
                        "description": "Cybersecurity news and vulnerability research",
                        "group_name": "Security",
                        "tags": ["Security", "CVE"],
                    },
                    "sports-feed": {
                        "title": "Sports Watch",
                        "description": "Sport news and match coverage",
                        "group_name": "Sport",
                        "tags": ["Sport"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "Sport RSS Webseiten"}],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for observed RSS/websites about sport.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            'was fuer websites/rss habe ich unter beobachtung zum thema "Sport"?',
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "sports-feed" in result.text
    assert "Sports Watch" in result.text
    assert "security-feed" not in result.text
    assert "SecurityWeek" not in result.text
    assert "score=" not in result.text
    assert any("Routing Debug: evidence_filter surface=connections kept=1" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_ignores_scope_terms_for_topic_evidence(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "netzwerk-tools-imonitor-internet-st-rungen": {
                        "title": "iMonitor Internetstörungen",
                        "description": "Aktuelle Meldungen zu Internetstörungen und Netzwerkproblemen vom heise Netze iMonitor",
                        "group_name": "Heise",
                        "tags": ["Störungen", "Internet", "Netzwerk", "Monitoring", "Ausfälle", "heise"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "RSS feeds websites monitoring trap shooting clay shooting Tontaubenschießen",
                }
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for observed sources about clay shooting.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was fuer websites/rss habe ich unter beobachtung zum thema Tontaubenschiessen?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe im ausgewählten Inventar keine passenden Einträge gefunden."
    assert "iMonitor Internetstörungen" not in result.text
    assert "netzwerk-tools-imonitor-internet-st-rungen" not in result.text
    assert any("Routing Debug: inventory_index surface=connections matches=0" in line for line in result.detail_lines)
    assert any("Routing Debug: evidence_filter surface=connections kept=0" in line for line in result.detail_lines)
    assert any("tontaubenschießen" in line for line in result.detail_lines if "evidence_filter" in line)
    assert not any("monitoring" in line for line in result.detail_lines if "evidence_filter" in line)


def test_pipeline_connection_inventory_ignores_filler_terms_for_unmatched_topic(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 8},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "gear-gadgets": {
                        "title": "Ars Technica Gadgets",
                        "description": "Tech news, reviews and analysis covering gadgets, hardware, processors and gaming",
                        "tags": ["technology", "gadgets", "hardware", "reviews", "gaming"],
                    },
                    "cars-technica": {
                        "title": "Ars Technica Cars",
                        "description": "Automotive tech news, EV reviews, racing coverage, and car industry analysis",
                        "tags": ["automotive", "electric-vehicles", "racing", "tech-news"],
                    },
                    "graham-cluley": {
                        "title": "Graham Cluley",
                        "description": "Cybersecurity news, scam alerts, malware analysis and hacking incidents",
                        "group_name": "Security",
                        "tags": ["cybersecurity", "malware", "scams", "hacking"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "RSS feeds and websites monitoring beef grilling topic",
                }
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for observed sources about beef grilling.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was fuer websites/rss habe ich unter beobachtung zum thema rindfleisch grillieren?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe im ausgewählten Inventar keine passenden Einträge gefunden."
    assert "gear-gadgets" not in result.text
    assert "cars-technica" not in result.text
    assert "graham-cluley" not in result.text
    evidence_lines = [line for line in result.detail_lines if "evidence_filter" in line]
    assert any("kept=0" in line for line in evidence_lines)
    assert any("beef" in line and "grilling" in line for line in evidence_lines)
    assert not any("and" in line or "the" in line for line in evidence_lines)


def test_pipeline_connection_inventory_allows_soft_scope_word_as_topic_without_feed_false_positive(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 10},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "netzwerk-tools-imonitor-internet-st-rungen": {
                        "title": "iMonitor Internetstörungen",
                        "description": "Aktuelle Meldungen zu Internetstörungen und Netzwerkproblemen",
                        "group_name": "Heise",
                        "tags": ["Störungen", "Internet", "Netzwerk", "Monitoring", "Ausfälle", "heise"],
                    },
                    "github-security-advisories": {
                        "title": "GitHub Security Advisories",
                        "description": "Vulnerability feeds and security advisories",
                        "group_name": "Security",
                        "tags": ["Security", "Vulnerability", "Feeds", "CVE"],
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "websites RSS feeds monitoring",
                }
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for observed sources about monitoring.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was fuer websites/rss habe ich unter beobachtung zum thema Monitoring?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "iMonitor Internetstörungen" in result.text
    assert "netzwerk-tools-imonitor-internet-st-rungen" in result.text
    assert "GitHub Security Advisories" not in result.text
    assert "github-security-advisories" not in result.text
    assert any("Routing Debug: evidence_filter surface=connections kept=1" in line for line in result.detail_lines)
    assert any("terms=monitoring" in line for line in result.detail_lines if "evidence_filter" in line)
    assert not any("feeds" in line for line in result.detail_lines if "evidence_filter" in line)
    assert not any("the" in line or "and" in line for line in result.detail_lines if "evidence_filter" in line)


def test_pipeline_connection_inventory_filters_by_item_topic_and_keeps_many_safe_matches() -> None:
    website_rows = {
        f"security-{index:02d}": {
            "url": f"https://example.invalid/security/{index}",
            "title": f"IT-Security Source {index}",
            "description": "IT-Security, incident response and vulnerability research",
            "group_name": "IT-Security",
        }
        for index in range(1, 22)
    }
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {"website": website_rows},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=_PipelineArbiterLLM())
    registry = build_builtin_surface_registry(settings)
    connections = registry.get("connections")
    assert connections is not None

    sport_message, sport_sources = pipeline._aria_turn_format_inventory_metadata(
        "connections",
        dict(connections.metadata or {}),
        "Sport websites",
        limit=50,
    )
    assert sport_sources == []
    assert "IT-Security Source" not in sport_message
    assert "No matching inventory metadata" in sport_message

    security_message, security_sources = pipeline._aria_turn_format_inventory_metadata(
        "connections",
        dict(connections.metadata or {}),
        "IT-Security",
        limit=50,
    )
    assert len(security_sources) == 1
    assert "21 matching of 21 configured" in security_message
    assert "security-01" in security_message
    assert "security-21" in security_message
    assert "https://example.invalid" not in security_message


def test_pipeline_website_list_capability_uses_inventory_index_without_action_fallback(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "website": {
                    "infoguard-pentest": {
                        "title": "InfoGuard Labs Pentest Archiv",
                        "description": "Penetrationstests und Security Research",
                        "group_name": "Security",
                        "tags": ["Security", "Pentest", "IT-Sicherheit"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["chat"],
            "needs_context": False,
            "context_directions": [],
            "surfaces": ["chat"],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "plain chat fallback",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was für websites/rss habe ich unter beobachtung zum thema Sport?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe im ausgewählten Inventar keine passenden Einträge gefunden."
    assert "InfoGuard" not in result.text
    assert "Security" not in result.text
    assert result.intents == ["context_inventory"]
    assert any("Routing Debug: action_to_context_inventory capability=website_list" in line for line in result.detail_lines)
    assert any("Routing Debug: inventory_index surface=connections matches=0" in line and "authoritative=true" in line for line in result.detail_lines)
    assert not any("Ausgeführt via beobachtete Webseiten" in line for line in result.detail_lines)


def test_pipeline_website_list_capability_uses_mixed_rss_and_website_inventory(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 8},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "sports-rss": {
                        "title": "Sports Desk RSS",
                        "description": "Sports news, football coverage and match analysis",
                        "group_name": "Sport",
                        "tags": ["sports", "football", "match-analysis"],
                    },
                    "security-rss": {
                        "title": "Security RSS",
                        "description": "IT-Security, CVE and threat intelligence",
                        "group_name": "Security",
                        "tags": ["security", "cve", "cybersecurity"],
                    },
                },
                "website": {
                    "sports-site": {
                        "title": "Sports Watch",
                        "description": "Observed sports website and football reports",
                        "group_name": "Sport",
                        "tags": ["sports", "football"],
                    },
                    "infoguard-pentest": {
                        "title": "InfoGuard Labs Pentest Archiv",
                        "description": "Penetrationstests und Security Research",
                        "group_name": "Security",
                        "tags": ["Security", "Pentest", "IT-Sicherheit"],
                    },
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["chat"],
            "needs_context": False,
            "context_directions": [],
            "surfaces": ["chat"],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "plain chat fallback",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was für websites/rss habe ich unter beobachtung zum thema Sport?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "sports-rss" in result.text
    assert "sports-site" in result.text
    assert "InfoGuard" not in result.text
    assert "security-rss" not in result.text
    assert result.intents == ["context_inventory"]
    assert any(
        "Routing Debug: action_to_context_inventory capability=website_list" in line and "authoritative=true" in line
        for line in result.detail_lines
    )
    assert any(
        "Routing Debug: inventory_index surface=connections matches=2" in line and "authoritative=true" in line
        for line in result.detail_lines
    )
    assert "RSS (rss): 1 Treffer" in result.text
    assert "Beobachtete Webseiten (website): 1 Treffer" in result.text
    assert not any("Ausgeführt via beobachtete Webseiten" in line for line in result.detail_lines)


def test_pipeline_capability_inventory_frame_preserves_followup_inventory_mode(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.1, "candidate_limit": 8},
            "ui": {"debug_mode": True},
            "connections": {
                "rss": {
                    "sports-rss": {
                        "title": "Sports Desk RSS",
                        "description": "Sports news, football coverage and match analysis",
                        "group_name": "Sport",
                        "tags": ["sports", "football", "match-analysis"],
                    },
                    "security-rss": {
                        "title": "Security RSS",
                        "description": "IT-Security, CVE and threat intelligence",
                        "group_name": "Security",
                        "tags": ["security", "cve", "cybersecurity"],
                    },
                },
                "website": {
                    "sports-site": {
                        "title": "Sports Watch",
                        "description": "Observed sports website and football reports",
                        "group_name": "Sport",
                        "tags": ["sports", "football"],
                    },
                    "infoguard-pentest": {
                        "title": "InfoGuard Labs Pentest Archiv",
                        "description": "Penetrationstests und Security Research",
                        "group_name": "Security",
                        "tags": ["Security", "Pentest", "IT-Sicherheit"],
                    },
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    docs = build_inventory_documents(settings)
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(docs, index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["chat"],
            "needs_context": False,
            "context_directions": [],
            "surfaces": ["chat"],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "plain chat fallback",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    sport_result = asyncio.run(
        pipeline.process(
            "was für websites/rss habe ich unter beobachtung zum thema Sport?",
            user_id="u1",
            source="test",
            language="de",
        )
    )
    assert "sports-rss" in sport_result.text
    assert any("Routing Debug: inventory_index surface=connections matches=2" in line for line in sport_result.detail_lines)

    llm.aria_payload = {
        "intents": ["context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "IT-Security"}],
        "answer_mode": "direct_answer",
        "contract": {"mode": "answer", "evidence_policy": "source_bound"},
        "risk": "none",
        "needs_confirmation": False,
        "confidence": "high",
        "reason": "Continuation inventory frame",
    }

    security_result = asyncio.run(
        pipeline.process(
            "und was ist mit IT-Security?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "security-rss" in security_result.text
    assert "infoguard-pentest" in security_result.text
    assert "sports-rss" not in security_result.text
    assert "context_inventory" in security_result.intents
    assert any(
        "Routing Debug: inventory_index surface=connections matches=2" in line and "authoritative=true" in line
        for line in security_result.detail_lines
    )
    assert any("Routing Debug: direct_context_fast_path kind=inventory" in line for line in security_result.detail_lines)
    assert not any("final_chat_response_stage" in line for line in security_result.detail_lines)
    assert len(llm.aria_payloads_seen) >= 2
    frame = llm.aria_payloads_seen[-1]["last_turn_frame"]
    assert frame["surface_id"] == "connections"
    assert frame["mode"] == "inventory"
    assert "Sport" in frame["topic"]
    assert frame["evidence_policy"] == "source_bound"
    assert frame["answer_mode"] == "direct_answer"


def test_pipeline_passes_last_turn_frame_to_next_arbitration() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {
                "website": {
                    "sports-watch": {
                        "url": "https://example.invalid/sports",
                        "title": "Sports Watch",
                        "description": "Observed sports website",
                        "group_name": "Sport",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "Sport"}],
            "answer_mode": "answer_from_context",
            "contract": {"mode": "answer", "evidence_policy": "source_bound"},
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for watched website inventory about Sport.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)

    asyncio.run(pipeline.process('was fuer websites habe ich unter beobachtung zum thema "Sport"?', user_id="u1", source="test", language="de"))

    llm.aria_payload = {
        "intents": ["context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "context_requests": [{"surface_id": "connections", "mode": "inventory", "query": "IT-Security"}],
        "answer_mode": "answer_from_context",
        "contract": {"mode": "answer", "evidence_policy": "source_bound"},
        "risk": "none",
        "confidence": "high",
        "reason": "The follow-up continues the previous inventory frame with a new topic.",
    }
    asyncio.run(pipeline.process("und was ist mit it-security?", user_id="u1", source="test", language="de"))

    assert len(llm.aria_payloads_seen) >= 2
    frame = llm.aria_payloads_seen[-1]["last_turn_frame"]
    assert frame["surface_id"] == "connections"
    assert frame["mode"] == "inventory"
    assert frame["topic"] == "Sport"
    assert frame["evidence_policy"] == "source_bound"
    assert frame["answer_mode"] == "answer_from_context"


def test_pipeline_empty_registered_context_stays_source_bound() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["chat"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [{"surface_id": "connections", "mode": "search", "query": "IT-Security"}],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "Connection context was selected.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)

    result = asyncio.run(pipeline.process("und was ist mit IT-Security?", user_id="u1", source="test", language="de"))

    assert "nichts Passendes gefunden" in result.text
    assert any("Routing Debug: local_context_empty directions=connections" in line for line in result.detail_lines)
    assert not any("final_chat_response_stage" in line for line in result.detail_lines)


def test_pipeline_notes_context_skips_turn_intent_even_when_arbiter_intent_is_chat(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "UI-Regel"
        return []

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM(
        {
            "intents": ["chat"],
            "needs_context": True,
            "context_directions": ["notes"],
            "context_depth": "shallow",
            "surfaces": ["notes"],
            "collections": ["aria_notes_u1"],
            "queries": {"notes": "UI-Regel", "aria_notes_u1": "UI-Regel"},
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "User requests note content.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)

    result = asyncio.run(
        pipeline.process(
            "was steht in meinen notizen zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe in deinen Notizen dazu nichts Passendes gefunden."
    assert "notes_search" in result.intents
    assert "turn_intent_arbitration" not in llm.operations
    assert not any("Routing Debug: stage_timing stage=turn_intent_arbiter" in line for line in result.detail_lines)
    assert any("Routing Debug: stage_timing stage=skill_runtime" in line for line in result.detail_lines)
    assert not any("final_chat_response_stage" in line for line in result.detail_lines)


def test_pipeline_reuses_precomputed_aria_turn_arbitration_for_empty_notes(monkeypatch) -> None:
    async def fake_search_note_hits(**kwargs):
        assert kwargs["query"] == "UI-Regel klickbare Optionen"
        return []

    monkeypatch.setattr(recipe_runtime_mod, "search_note_hits", fake_search_note_hits)
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineArbiterLLM()
    memory = _PipelineMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]
    arbitration = AriaTurnArbitration(
        source=ARIA_TURN_ARBITRATION_OPERATION,
        usage={"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("notes",),
            context_depth="shallow",
            surfaces=("local_retrieval",),
            collections=("aria_notes_u1",),
            queries={"aria_notes_u1": "UI-Regel klickbare Optionen"},
            priority=("notes",),
            answer_mode="direct_answer",
            risk="low",
            confidence=0.95,
            reason="precomputed web gate decision",
        ),
    )

    result = asyncio.run(
        pipeline.process(
            "was steht in meinen Notizen zur UI-Regel?",
            user_id="u1",
            source="test",
            language="de",
            aria_turn_arbitration=arbitration,
        )
    )

    assert result.text == "Ich habe in deinen Notizen dazu nichts Passendes gefunden."
    assert llm.operations == ["aria_answer_composer"]
    assert "notes_search" in result.intents
    assert "memory_recall" not in result.intents
    assert any("arbiter_tokens=9" in line for line in result.detail_lines)
