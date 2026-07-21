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
from aria.core.answer_composer import AnswerComposer
from aria.core.answer_composer import AnswerComposerInput
from aria.core.config import Settings
from aria.core.context_surfaces import ContextRequest
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
from aria.core.surface_loader_runtime import SurfaceLoaderRuntime
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


class _PipelineComposerLLM(_PipelineArbiterLLM):
    def __init__(
        self,
        aria_payload: dict | None = None,
        *,
        composer_answer: str,
        semantic_review_payload: dict | None = None,
        scope_review_payload: dict | None = None,
    ) -> None:
        super().__init__(aria_payload)
        self.composer_answer = composer_answer
        self.semantic_review_payload = semantic_review_payload
        self.scope_review_payload = scope_review_payload
        self.last_composer_payload: dict | None = None
        self.last_semantic_review_payload: dict | None = None
        self.last_scope_review_payload: dict | None = None

    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation", "") or "")
        if operation == "connection_evidence_scope_review":
            self.operations.append(operation)
            try:
                self.last_scope_review_payload = json.loads(messages[-1]["content"])
            except Exception:
                self.last_scope_review_payload = None
            return _Response(json.dumps(self.scope_review_payload or {}))
        if operation == "inventory_semantic_scope_review":
            self.operations.append(operation)
            try:
                self.last_semantic_review_payload = json.loads(messages[-1]["content"])
            except Exception:
                self.last_semantic_review_payload = None
            return _Response(json.dumps(self.semantic_review_payload or {}))
        if operation == "aria_answer_composer":
            self.operations.append(operation)
            try:
                self.last_composer_payload = json.loads(messages[-1]["content"])
            except Exception:
                self.last_composer_payload = None
            return _Response(
                json.dumps(
                    {
                        "answer": self.composer_answer,
                        "confidence": "high",
                        "reason": "composed from inventory candidates",
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
                        "target_scope_authority": "full_kind",
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


class _PipelineMetaCatalogFullKindSshRuntimeLLM(_PipelineMetaCatalogLLM):
    def __init__(self, meta_payload: dict, *, target_intent: str, content: str) -> None:
        super().__init__(meta_payload)
        self.target_intent = target_intent
        self.content = content

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
                        "target_scope_authority": "full_kind",
                        "target_intent": self.target_intent,
                        "content": self.content,
                        "confidence": "high",
                        "reason": "safe read-only full-kind SSH runtime task",
                    }
                )
            )
        if operation == "ssh_multi_target_summary":
            self.operations.append(operation)
            return _Response(
                json.dumps(
                    {
                        "summary": "Ich habe die SSH-Ziele mit dem gebundenen Runtime-Profil geprueft.",
                        "confidence": "high",
                        "reason": "summarized bounded SSH runtime records",
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
            dev = 1.0 if any(token in lower for token in ("dev", "development", "entwickl", "vscode")) else 0.0
            rows.append([security, sport, dev])
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


def test_builtin_registry_exposes_capabilities_and_recipes_surfaces() -> None:
    settings = Settings.model_validate({"llm": {"model": "fake"}, "memory": {"enabled": False}})
    registry = build_builtin_surface_registry(settings)

    assert registry.get("capabilities") is not None
    assert registry.get("recipes") is not None
    assert registry.validate_requests(
        [
            ContextRequest(surface_id="capabilities", mode="inventory", query="aktive Skills"),
            ContextRequest(surface_id="recipes", mode="inventory", query="Rezeptvorlagen"),
        ]
    )


def test_surface_loader_uses_system_inventory_for_capabilities_and_recipes() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {"ssh": {"srv-01": {"host": "192.0.2.1", "title": "srv-01"}}},
        }
    )

    class _Owner:
        def __init__(self) -> None:
            self.settings = settings

        def _aria_turn_context_request_query(self, arbitration, surface_id):  # noqa: ANN001
            _ = arbitration, surface_id
            return ""

        def _aria_turn_format_inventory_metadata(self, surface_id, metadata, query, limit=None):  # noqa: ANN001
            _ = surface_id, metadata, query, limit
            return "", []

        def _load_stored_recipe_runtime(self):
            return [
                {
                    "id": "server-status",
                    "name": "Server Status",
                    "description": "Status der Server pruefen",
                    "enabled": True,
                    "connections": ["ssh"],
                    "keywords": ["server", "status"],
                    "steps": [{"type": "ssh_run"}],
                }
            ]

    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("context_inventory",),
            surfaces=("capabilities", "recipes"),
            needs_context=True,
            context_directions=("capabilities", "recipes"),
            context_requests=(
                ContextRequest(surface_id="capabilities", mode="inventory", query="aktive Skills"),
                ContextRequest(surface_id="recipes", mode="inventory", query="Rezeptvorlagen"),
            ),
            answer_mode="answer_from_context",
            confidence=0.9,
        )
    )

    results = asyncio.run(SurfaceLoaderRuntime(_Owner()).load_inventory(arbitration))

    capability_result = next(result for result in results if "ssh_command" in result.content)
    recipe_result = next(result for result in results if "server-status" in result.content)
    assert "Aktive ARIA-Faehigkeiten" in capability_result.content
    assert "Gespeicherte Rezeptvorlagen" in recipe_result.content
    assert any("surface=capabilities" in line for line in capability_result.metadata["detail_lines"])
    assert any("surface=recipes" in line for line in recipe_result.metadata["detail_lines"])


def test_explicit_internet_search_normalizes_meta_chat_contract_to_web_research() -> None:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.web_search_skill = object()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat",),
            surfaces=(),
            actions=(),
            needs_context=False,
            context_directions=(),
            context_depth="none",
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="allow_general",
            risk="none",
            confidence=0.95,
            reason="User requests internet search",
        ),
    )

    normalized = pipeline._normalize_explicit_web_research_contract(
        arbitration,
        message="suche im internet nach der neusten apple watch ultra und dem neusten iphone",
        user_id="u1",
        request_id="r1",
    )

    assert normalized is not None
    assert normalized.source == META_CATALOG_ROUTING_OPERATION
    assert "web_research" in normalized.plan.intents
    assert normalized.plan.surfaces == ("web",)
    assert normalized.plan.needs_context is True
    assert normalized.plan.context_directions == ("web",)
    assert normalized.plan.context_requests
    assert normalized.plan.context_requests[0].surface_id == "web"
    assert normalized.plan.context_requests[0].mode == "search"
    assert normalized.plan.contract_mode == "answer"
    assert normalized.plan.evidence_policy == "source_bound"
    assert pipeline._merge_aria_turn_intents(["chat"], normalized) == ["web_search"]


def test_current_product_question_overrides_accidental_local_docs_contract() -> None:
    class FreshnessLLM:
        async def chat(self, messages, **kwargs):  # noqa: ANN001
            if kwargs.get("operation") == "chat_freshness_arbitration":
                return _Response(
                    json.dumps(
                        {
                            "needs_fresh_context": True,
                            "query": "Apple Watch Ultra latest model official Apple comparison",
                            "confidence": "high",
                            "reason": "current product comparison needs fresh external sources",
                        }
                    )
                )
            return _Response("{}")

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.web_search_skill = object()
    pipeline.llm_client = FreshnessLLM()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat", "local_retrieval"),
            surfaces=("docs",),
            actions=(),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="welches ist die neuste apple watch ultra und was kann sie mehr als die alte version",
                ),
            ),
            priority=("local|docs|document|arlo-ultra",),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="low",
            confidence=0.88,
            reason="The prompt matched a local Ultra document.",
        ),
    )

    normalized = asyncio.run(
        pipeline._normalize_fresh_web_context_contract(
            arbitration,
            message="welches ist die neuste apple watch ultra und was kann sie mehr als die alte version",
            user_id="u1",
            request_id="r1",
            language="de",
            source="test",
        )
    )

    assert normalized is not None
    assert normalized.plan.surfaces == ("web",)
    assert normalized.plan.context_directions == ("web",)
    assert normalized.plan.context_requests
    assert normalized.plan.context_requests[0].surface_id == "web"
    assert normalized.plan.context_requests[0].query == "Apple Watch Ultra latest model official Apple comparison"
    assert normalized.plan.context_requests[0].budget["freshness_contract"] is True
    assert normalized.plan.context_requests[0].budget["previous_surfaces"] == ["docs"]
    assert "web_research" in normalized.plan.intents
    assert "local_retrieval" not in normalized.plan.intents
    assert pipeline._merge_aria_turn_intents(["chat"], normalized) == ["web_search"]


def test_meta_catalog_web_context_request_runs_web_search_even_without_web_research_intent() -> None:
    pipeline = Pipeline.__new__(Pipeline)
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat",),
            surfaces=("web",),
            actions=(),
            needs_context=True,
            context_directions=("web",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(surface_id="web", mode="search", query="newest Google Pixel phone"),
            ),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="none",
            confidence=0.91,
            reason="User asks for a current product answer.",
        ),
    )

    assert pipeline._merge_aria_turn_intents(["chat"], arbitration) == ["web_search"]


def test_meta_catalog_existing_web_context_gets_freshness_query() -> None:
    class FreshnessLLM:
        async def chat(self, _messages, **kwargs):
            if kwargs.get("operation") == "chat_freshness_arbitration":
                return _Response(
                    json.dumps(
                        {
                            "needs_fresh_context": True,
                            "query": "Apple Watch Ultra latest model official Apple comparison",
                            "confidence": "high",
                            "reason": "current product answer needs current official source context",
                        }
                    )
                )
            return _Response("{}")

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.web_search_skill = object()
    pipeline.llm_client = FreshnessLLM()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat", "web_research"),
            surfaces=("web",),
            actions=(),
            needs_context=True,
            context_directions=("web",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="web",
                    mode="search",
                    query="welches ist die neuste apple watch ultra",
                    budget={"from_meta_catalog": True},
                ),
            ),
            priority=("web",),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="low",
            confidence=0.9,
            reason="The user asks for latest product information.",
        ),
    )

    normalized = asyncio.run(
        pipeline._normalize_fresh_web_context_contract(
            arbitration,
            message="welches ist die neuste apple watch ultra",
            user_id="u1",
            request_id="r1",
            language="de",
            source="test",
        )
    )

    assert normalized is not None
    request = normalized.plan.context_requests[0]
    assert request.surface_id == "web"
    assert request.query == "Apple Watch Ultra latest model official Apple comparison"
    assert request.budget["freshness_contract"] is True
    assert request.budget["previous_query"] == "welches ist die neuste apple watch ultra"
    assert request.budget["from_meta_catalog"] is True
    assert normalized.plan.queries["web"] == "Apple Watch Ultra latest model official Apple comparison"
    assert pipeline._merge_aria_turn_intents(["chat"], normalized) == ["web_search"]


def test_meta_catalog_freshness_timeout_keeps_existing_web_context() -> None:
    class TimeoutFreshnessLLM:
        async def chat(self, _messages, **kwargs):
            if kwargs.get("operation") == "chat_freshness_arbitration":
                raise asyncio.TimeoutError()
            return _Response("{}")

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.web_search_skill = object()
    pipeline.llm_client = TimeoutFreshnessLLM()
    arbitration = AriaTurnArbitration(
        source=META_CATALOG_ROUTING_OPERATION,
        plan=AriaTurnPlan(
            intents=("chat", "web_research"),
            surfaces=("web",),
            actions=(),
            needs_context=True,
            context_directions=("web",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="web",
                    mode="search",
                    query="welches ist die neuste apple watch ultra",
                    budget={"from_meta_catalog": True},
                ),
            ),
            priority=("web",),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="low",
            confidence=0.9,
            reason="The user asks for latest product information.",
        ),
    )

    normalized = asyncio.run(
        pipeline._normalize_fresh_web_context_contract(
            arbitration,
            message="welches ist die neuste apple watch ultra",
            user_id="u1",
            request_id="r1",
            language="de",
            source="test",
        )
    )

    assert normalized is arbitration
    assert normalized.plan.context_requests[0].query == "welches ist die neuste apple watch ultra"
    assert pipeline._merge_aria_turn_intents(["chat"], normalized) == ["web_search"]


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
        },
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
    contract = llm.last_payload["llm_input_contract"]
    assert contract["contract_version"] == "llm_input_v1"
    assert contract["canonical_input"] is True
    assert contract["decision_task"] == "aria_turn_select_context_action_or_chat"
    assert contract["user_prompt"] == "hallo"
    assert contract["global_rules"]["normalizer_is_not_router"] is True
    assert contract["global_rules"]["top_level_payload_fields_are_legacy_mirrors"] is False
    assert contract["global_rules"]["top_level_payload_fields_removed"] is True
    assert contract["global_rules"]["llm_selects_context"] is True
    assert "connections" in contract["requested_output_schema"]["allowed_surface_ids"]
    assert "aria_facts_u1" in contract["requested_output_schema"]["allowed_collection_names"]
    assert set(llm.last_payload) == {"llm_input_contract"}
    routing_meta = contract["world_map"]["routing_meta"]
    assert "legacy_surfaces" not in routing_meta
    assert "collections" in routing_meta
    assert "actions" in routing_meta
    surface_meta = contract["world_map"]["surface_meta"]
    connections = next(surface for surface in surface_meta["surfaces"] if surface["id"] == "connections")
    assert "metadata" not in connections
    assert "loader_contract" not in connections
    assert "what_it_knows" not in connections
    assert connections["routing"]["configured_kinds"] == ["website"]
    world_connections = next(surface for surface in contract["world_map"]["surfaces"] if surface["id"] == "connections")
    assert world_connections["routing"]["configured_kinds"] == ["website"]
    assert contract["world_map"]["collections"] == routing_meta["collections"]
    assert "Sports Watch" not in str(llm.last_payload)
    assert "https://example.invalid/sports" not in str(llm.last_payload)


def test_aria_turn_arbiter_preserves_runtime_target_scope_authority() -> None:
    llm = _ArbiterLLM(
        {
            "intents": ["runtime_action"],
            "needs_context": True,
            "context_directions": ["connections"],
            "actions": ["ssh_package_update_check"],
            "priority": ["connection|ssh|srv-a", "connection|ssh|srv-b"],
            "target_scope_authority": "full_kind",
            "answer_mode": "plan_action",
            "risk": "low",
            "confidence": "high",
            "reason": "whole configured kind",
        }
    )

    result = asyncio.run(AriaTurnArbiter(llm).arbitrate(message="status meiner server", menu=_menu()))

    assert result.plan.target_scope_authority == "full_kind"
    assert "target_scope_authority=full_kind" in result.debug_line


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
    frame = llm.last_payload["llm_input_contract"]["conversation_context"]["last_turn_frame"]
    assert frame["surface_id"] == "connections"
    assert frame["mode"] == "inventory"


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
    compact = llm.last_payload["llm_input_contract"]["world_map"]["surface_meta"]
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
    assert "llm_input_contract=v1" in result.debug_line
    assert "needs_context=true" in result.debug_line
    assert "context_directions=memory,learning,notes" in result.debug_line
    assert result.diagnostics["payload_bytes"] > 0
    assert result.diagnostics["system_chars"] > 0
    assert "routing_payload_bytes=" in result.debug_line
    assert "routing_system_chars=" in result.debug_line
    assert llm.operations == [ARIA_TURN_ARBITRATION_OPERATION]
    assert llm.last_payload is not None
    routing_meta = llm.last_payload["llm_input_contract"]["world_map"]["routing_meta"]
    assert routing_meta["collections"][0]["name"] == "aria_facts_u1"
    assert routing_meta["actions"][1]["name"] == "discord_send"


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
    surface_meta = llm.last_payload["llm_input_contract"]["world_map"]["surface_meta"]
    assert surface_meta["contract"]["select_registered_surface_ids_only"] is True


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


def test_pipeline_aria_turn_web_context_request_executes_web_search(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )

    async def fail_meta_qdrant(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        raise RuntimeError("qdrant unavailable")

    class WebSkill:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def execute(self, query: str, params: dict[str, object]) -> SkillResult:
            self.calls.append({"query": query, "params": dict(params or {})})
            return SkillResult(
                skill_name="web_search",
                success=True,
                content=(
                    "[Web Search via web-search]\n"
                    "Suche: newest Google Pixel phone\n"
                    "- [1] Google Pixel 10 phones\n"
                    "  URL: https://store.google.com/category/phones\n"
                    "  Snippet: Pixel 10, Pixel 10 Pro, Pixel 10 Pro XL, and Pixel 10 Pro Fold."
                ),
                metadata={
                    "sources": [
                        {
                            "title": "Google Pixel 10 phones",
                            "url": "https://store.google.com/category/phones",
                            "engine": "web",
                        }
                    ],
                    "detail_lines": [
                        "Quelle: Google Pixel 10 phones · https://store.google.com/category/phones · web"
                    ]
                },
            )

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fail_meta_qdrant)
    llm = _PipelineArbiterLLM(
        {
            "intents": ["chat"],
            "needs_context": True,
            "context_directions": ["web"],
            "context_depth": "shallow",
            "surfaces": ["web"],
            "context_requests": [
                {"surface_id": "web", "mode": "search", "query": "newest Google Pixel phone"},
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for current product information.",
        }
    )
    web_skill = WebSkill()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.web_search_skill = web_skill  # type: ignore[assignment]

    result = asyncio.run(
        pipeline.process(
            "welches ist das aktuell neuste google phone?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "ok"
    assert result.intents == ["web_search"]
    assert web_skill.calls
    assert web_skill.calls[-1]["query"] == "newest Google Pixel phone"
    assert "Google Pixel 10 phones" in str(llm.last_messages[1]["content"])
    assert any("context_ledger phase=loaded skills=web_search sources=1" in line for line in result.detail_lines)
    assert any(
        "Routing Debug: context_packet" in line and "requests=web:search" in line and "loaded=web:1" in line
        for line in result.detail_lines
    )
    assert any(
        line == "Quelle: Google Pixel 10 phones · https://store.google.com/category/phones · web"
        for line in result.detail_lines
    )


def test_pipeline_docs_inventory_uses_document_sources_as_evidence() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    query = "was für medizinische beipackzettel sind im dokumente speicher abgelegt?"
    llm = _PipelineArbiterLLM(
        {
            "needs_context": True,
            "context_directions": ["docs"],
            "context_depth": "shallow",
            "intents": ["chat", "local_retrieval"],
            "surfaces": ["docs"],
            "context_requests": [{"surface_id": "docs", "mode": "search", "query": query}],
            "answer_mode": "direct_answer",
            "contract": {"mode": "answer", "evidence_policy": "source_bound"},
            "risk": "low",
            "confidence": "high",
            "reason": "document inventory question",
        }
    )

    class DocumentInventoryMemory:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def _build_recall_targets(self, user_id: str, base_collection: str | None = None):  # noqa: ANN001
            _ = user_id, base_collection
            return []

        async def _build_document_targets(self, user_id: str):  # noqa: ANN001
            _ = user_id
            return []

        async def execute(self, query: str, params: dict):  # noqa: ANN001
            self.calls.append({"query": query, "params": dict(params or {})})
            sources = [
                {"type": "document", "document_name": "Arlo Ultra_User_Manual_en.pdf", "collection": "aria_docs_fischerman"},
                {
                    "type": "document",
                    "document_name": "Mill Gentle Air WiFi oil filled_Nordic_2025_print.pdf",
                    "collection": "aria_docs_fischerman",
                },
                {
                    "type": "document",
                    "document_name": "at_olumiant_gebrauchsinformation.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {
                    "type": "document",
                    "document_name": "Certolizumab Pegol anx_63451_de.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {
                    "type": "document",
                    "document_name": "cimzia-r-200-mg-injektionsloesung-in-einer-fertigspritze.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {
                    "type": "document",
                    "document_name": "Humira 40 mg Injektionsloesung in einer Fertigspritze.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {"type": "document", "document_name": "Simpoini50mg.pdf", "collection": "aria_docs_whity_medikamente"},
                {
                    "type": "document",
                    "document_name": "Zoledronic acid Clonmel 4mg 5ml Concentrate for.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {"type": "recipe", "title": "Discord Send Message", "collection": "aria_recipe_experience_fischerman"},
            ]
            return SkillResult(
                skill_name="memory_recall",
                success=True,
                content="\n".join(
                    f"- [Dokument: {source.get('document_name')}] Collection: {source.get('collection')}"
                    for source in sources
                    if source.get("type") == "document"
                ),
                metadata={
                    "document_inventory": True,
                    "sources": sources,
                    "detail_lines": [
                        "Routing Debug: document_inventory selected=9 collections=aria_docs_fischerman,aria_docs_whity_medikamente,aria_recipe_experience_fischerman requested_ids=0",
                    ],
                },
            )

    memory = DocumentInventoryMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(pipeline.process(query, user_id="u1", source="test", language="de"))

    assert memory.calls
    assert memory.calls[-1]["params"]["document_inventory"] is True
    assert result.text.startswith("Ich habe 6 passende Dokumente gefunden:")
    assert "at_olumiant_gebrauchsinformation.pdf" in result.text
    assert "Humira 40 mg Injektionsloesung in einer Fertigspritze.pdf" in result.text
    assert "Zoledronic acid Clonmel 4mg 5ml Concentrate for.pdf" in result.text
    assert "Arlo Ultra_User_Manual_en.pdf" not in result.text
    assert "Mill Gentle Air WiFi" not in result.text
    assert "Discord Send Message" not in result.text
    assert "aria_answer_composer" not in llm.operations
    assert any("Routing Debug: evidence_filter surface=docs mode=search matched=true" in line for line in result.detail_lines)
    assert any(
        "Routing Debug: context_packet" in line and "requests=docs:search" in line and "loaded=docs:9" in line
        for line in result.detail_lines
    )
    assert any(
        "Routing Debug: answer_contract kind=docs_search status=found mode=answer evidence_policy=source_bound" in line
        for line in result.detail_lines
    )
    assert any("Routing Debug: fast_docs_inventory_filter kept=6 rejected=2" in line for line in result.detail_lines)
    assert not any("Routing Debug: local_context_empty" in line for line in result.detail_lines)


def test_pipeline_memory_surface_document_inventory_uses_document_sources_as_evidence() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    query = "Von welchen Medikamenten haben wir Beipackzettel im Memory"
    llm = _PipelineArbiterLLM(
        {
            "needs_context": True,
            "context_directions": ["memory"],
            "context_depth": "shallow",
            "intents": ["chat", "local_retrieval"],
            "surfaces": ["memory"],
            "context_requests": [{"surface_id": "memory", "mode": "search", "query": query}],
            "answer_mode": "answer_from_context",
            "contract": {"mode": "answer", "evidence_policy": "source_bound"},
            "risk": "low",
            "confidence": "high",
            "reason": "document inventory question worded as memory",
        }
    )

    class DocumentInventoryMemory:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def _build_recall_targets(self, user_id: str, base_collection: str | None = None):  # noqa: ANN001
            _ = user_id, base_collection
            return []

        async def _build_document_targets(self, user_id: str):  # noqa: ANN001
            _ = user_id
            return []

        async def execute(self, query: str, params: dict):  # noqa: ANN001
            self.calls.append({"query": query, "params": dict(params or {})})
            sources = [
                {"type": "document", "document_name": "Arlo Ultra_User_Manual_en.pdf", "collection": "aria_docs_fischerman"},
                {
                    "type": "document",
                    "document_name": "at_olumiant_gebrauchsinformation.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {
                    "type": "document",
                    "document_name": "Certolizumab Pegol anx_63451_de.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {
                    "type": "document",
                    "document_name": "cimzia-r-200-mg-injektionsloesung-in-einer-fertigspritze.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {
                    "type": "document",
                    "document_name": "Humira 40 mg Injektionsloesung in einer Fertigspritze.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {"type": "document", "document_name": "Simpoini50mg.pdf", "collection": "aria_docs_whity_medikamente"},
                {
                    "type": "document",
                    "document_name": "Zoledronic acid Clonmel 4mg 5ml Concentrate for.pdf",
                    "collection": "aria_docs_whity_medikamente",
                },
                {"type": "recipe", "title": "RSS Read Feed", "collection": "aria_recipe_experience_fischerman"},
            ]
            return SkillResult(
                skill_name="memory_recall",
                success=True,
                content="\n".join(
                    f"- [Dokument: {source.get('document_name')}] Collection: {source.get('collection')}"
                    for source in sources
                    if source.get("type") == "document"
                ),
                metadata={
                    "document_inventory": True,
                    "sources": sources,
                    "detail_lines": [
                        "Routing Debug: document_inventory selected=8 collections=aria_docs_fischerman,aria_docs_whity_medikamente,aria_recipe_experience_fischerman requested_ids=0",
                    ],
                },
            )

    memory = DocumentInventoryMemory()
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm)
    pipeline.memory_skill = memory  # type: ignore[assignment]

    result = asyncio.run(pipeline.process(query, user_id="u1", source="test", language="de"))

    assert memory.calls
    assert memory.calls[-1]["params"]["document_inventory"] is True
    assert result.text.startswith("Ich habe 6 passende Dokumente gefunden:")
    assert "at_olumiant_gebrauchsinformation.pdf" in result.text
    assert "Humira 40 mg Injektionsloesung in einer Fertigspritze.pdf" in result.text
    assert "Arlo Ultra_User_Manual_en.pdf" not in result.text
    assert "RSS Read Feed" not in result.text
    assert "aria_answer_composer" not in llm.operations
    assert any("Routing Debug: evidence_filter surface=memory mode=search matched=true" in line for line in result.detail_lines)
    assert any("Routing Debug: fast_docs_inventory_filter kept=6 rejected=1" in line for line in result.detail_lines)
    assert any(
        "Routing Debug: answer_contract kind=docs_search status=found mode=answer evidence_policy=source_bound" in line
        for line in result.detail_lines
    )
    assert not any("Routing Debug: local_context_empty" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_unavailable_backup_chat_stays_local_retrieval(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )

    async def fail_meta_qdrant(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(meta_catalog_routing_mod, "create_meta_catalog_qdrant_client", fail_meta_qdrant)
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
    assert META_CATALOG_ROUTING_OPERATION not in llm.operations
    assert ARIA_TURN_ARBITRATION_OPERATION in llm.operations
    assert "pre_rag_action_arbitration" not in llm.operations
    assert not any("agentic_runtime" in line for line in result.detail_lines)
    assert any(
        "meta_catalog_contract phase=backup_fallback" in line and "meta_catalog_unavailable" in line
        for line in result.detail_lines
    )


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
    assert any("Routing Debug: answer_contract kind=empty_source_bound status=empty" in line for line in result.detail_lines)
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
                folder="Example Projects",
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
    assert "Aktive Projekt-Übersicht (Example Projects)" in result.text
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

    assert result.text == "Ich habe im ausgewählten Inventar keine passenden Einträge gefunden."
    assert "Sports Watch" not in result.text
    assert "sports-watch" not in result.text
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
    llm = _PipelineComposerLLM(
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
        },
        composer_answer="Ich habe eine passende beobachtete Quelle gefunden: infoguard-pentest - InfoGuard Labs Pentest Archiv.",
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
    assert "aria_answer_composer" in llm.operations
    assert any("Routing Debug: inventory_index surface=connections matches=1 query=IT-Security" in line for line in result.detail_lines)
    assert any("Routing Debug: inventory_candidate_context surface=connections" in line for line in result.detail_lines)
    assert any("deterministic_filter=disabled" in line for line in result.detail_lines)
    assert any("Routing Debug: direct_context_answer kind=inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: stage_timing stage=aria_turn_arbiter" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_server_ip_question_does_not_bind_partial_priority_refs(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {
                        "host": "192.0.2.10",
                        "title": "Server A",
                        "description": "Primary server",
                        "tags": ["server"],
                    },
                    "srv-b": {
                        "host": "192.0.2.11",
                        "title": "Server B",
                        "description": "Secondary server",
                        "tags": ["server"],
                    },
                    "srv-c": {
                        "host": "192.0.2.12",
                        "title": "Server C",
                        "description": "Tertiary server",
                        "tags": ["server"],
                    },
                },
                "rss": {
                    "security-feed": {
                        "title": "Security Feed",
                        "description": "Security advisories",
                        "tags": ["security"],
                    }
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "SSH server connections IP addresses hostnames",
                }
            ],
            "priority": ["connection|ssh|srv-a", "connection|ssh|srv-b"],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for server hostnames and IP addresses.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Welche IP/Hostnamen haben meine Server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "srv-a" in result.text
    assert "srv-b" in result.text
    assert "srv-c" in result.text
    assert "192.0.2.10" in result.text
    assert "192.0.2.11" in result.text
    assert "192.0.2.12" in result.text
    assert "security-feed" not in result.text
    assert any("ref_authority=kind_only" in line for line in result.detail_lines)
    assert any("selected_refs_hint=srv-a,srv-b selected_kinds=ssh kept=3" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_kind_only_not_truncated_to_candidate_limit(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    f"srv-{idx:02d}": {
                        "host": f"192.0.2.{idx}",
                        "title": f"Server {idx:02d}",
                        "description": "SSH server host",
                        "tags": ["server", "ssh"],
                    }
                    for idx in range(1, 15)
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "SSH servers hostname IP address",
                    "limit": 5,
                }
            ],
            "priority": [f"connection|ssh|srv-{idx:02d}" for idx in range(1, 7)],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for SSH server hostnames and IP addresses.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "srv-01" in result.text
    assert "srv-14" in result.text
    assert "192.0.2.1" in result.text
    assert "192.0.2.14" in result.text
    assert any("ref_authority=kind_only" in line and "kept=14" in line for line in result.detail_lines)
    assert any("context_packet" in line and "loaded=connections:14" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_followup_reuses_last_evidence_bundle_for_dev_hosts(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {
                        "host": "192.0.2.101",
                        "title": "dev-node-01",
                        "description": "Development server",
                        "tags": ["dev-server", "ssh"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.102",
                        "title": "dev-node-02",
                        "description": "Development server",
                        "tags": ["dev-server", "ssh"],
                    },
                    "prod-srv01": {
                        "host": "198.51.100.101",
                        "title": "prod-srv01",
                        "description": "Production server",
                        "tags": ["prod-server", "ssh"],
                    },
                },
                "sftp": {
                    "dns-node-01": {
                        "host": "192.0.2.10",
                        "description": "Primary DNS server",
                        "tags": ["pihole", "dns"],
                    },
                    "dns-node-02": {
                        "host": "192.0.2.20",
                        "description": "Secondary DNS server",
                        "tags": ["pihole", "dns"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.110",
                        "description": "Code server SFTP profile",
                        "tags": ["development"],
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "SSH server connections hostname IP address",
                    "limit": 5,
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for SSH server inventory with hostname and IP information.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    first = asyncio.run(
        pipeline.process(
            "Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )
    llm.aria_payload = {
        "intents": ["chat", "context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "context_depth": "shallow",
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "dev-server SSH connections hostname IP address",
                "limit": 5,
                "budget": {
                    "bind_selected_refs": True,
                    "selected_refs": ["dev-node-01", "dev-node-02"],
                    "selected_kinds": ["ssh"],
                },
            }
        ],
        "priority": ["connection|ssh|dev-node-01", "connection|ssh|dev-node-02"],
        "target_scope_authority": "semantic_group",
        "scope_operation": "narrow_subset",
        "answer_mode": "answer_from_context",
        "risk": "none",
        "confidence": "high",
        "reason": "The user asks for the dev server subset.",
    }
    operation_count = len(llm.operations)
    followup = asyncio.run(
        pipeline.process(
            "Welche IP/Hostnamen haben meine dev-server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "dev-node-01" in first.text
    assert "prod-srv01" in first.text
    assert "dev-node-01" in followup.text
    assert "dev-node-02" in followup.text
    assert "192.0.2.101" in followup.text
    assert "192.0.2.102" in followup.text
    assert "prod-srv01" not in followup.text
    assert len(llm.operations) == operation_count + 1
    assert any("evidence_bundle stored surface=connections authority=config completeness=full_kind rows=3" in line for line in first.detail_lines)
    assert any("evidence_bundle reused surface=connections authority=config completeness=full_kind" in line for line in followup.detail_lines)
    assert any("answerability surface=connections completeness=full_kind authority=config field=host" in line for line in followup.detail_lines)
    assert not any("final_chat_response_stage" in line for line in followup.detail_lines)


def test_pipeline_connection_inventory_scope_history_reviews_bad_reuse_then_empty_exclusion(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {
                        "host": "192.0.2.101",
                        "title": "dev-node-01",
                        "description": "Remote development environment",
                        "tags": ["dev-server", "development", "ssh"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.102",
                        "title": "dev-node-02",
                        "description": "Web-based development environment",
                        "tags": ["dev-server", "development", "ssh"],
                    },
                    "prod-srv01": {
                        "host": "198.51.100.101",
                        "title": "prod-srv01",
                        "description": "Production server",
                        "tags": ["prod-server", "ssh"],
                    },
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(build_inventory_documents(settings), index_hash="test-index")
    )

    async def fake_qdrant_client(_settings, *, timeout: int = 10):  # noqa: ANN001, ARG001
        return qdrant

    monkeypatch.setattr(pipeline_mod, "create_inventory_qdrant_client", fake_qdrant_client)
    llm = _PipelineComposerLLM(
        {
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "all SSH server connections hostname IP address",
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "target_scope_authority": "full_kind",
            "scope_operation": "expand_to_kind",
            "answer_mode": "answer_from_context",
            "confidence": "high",
            "reason": "all ssh inventory",
        },
        composer_answer=(
            "Ich habe passende konfigurierte Quellen gefunden:\n"
            "- dev-node-01: 192.0.2.101\n"
            "- dev-node-02: 192.0.2.102\n"
            "- prod-srv01: 198.51.100.101"
        ),
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    first = asyncio.run(
        pipeline.process(
            "Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )
    llm.aria_payload = {
        "intents": ["chat"],
        "needs_context": False,
        "context_directions": [],
        "surfaces": [],
        "context_requests": [],
        "target_scope_authority": "last_turn_scope",
        "scope_operation": "reuse_same_set",
        "answer_mode": "direct_answer",
        "confidence": "high",
        "reason": "same visible servers",
    }
    same_set = asyncio.run(
        pipeline.process(
            "Welche IPs und Hostnamen haben diese Server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    llm.aria_payload = {
        "intents": ["chat", "context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "Welche IP/Hostnamen haben meine dev-server?",
            }
        ],
        "target_scope_authority": "last_turn_scope",
        "scope_operation": "reuse_same_set",
        "answer_mode": "answer_from_context",
        "confidence": "high",
        "reason": "bad live contract said same set",
    }
    llm.scope_review_payload = {
        "operation": "narrow_subset",
        "selected_refs": ["dev-node-01", "dev-node-02"],
        "excluded_refs": [],
        "empty_result_allowed": False,
        "confidence": "high",
        "reason": "dev metadata matches two development hosts",
    }
    dev_subset = asyncio.run(
        pipeline.process(
            "Welche IP/Hostnamen haben meine dev-server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    llm.aria_payload = {
        "intents": ["chat", "context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "SFTP connections: dns-node-01, dns-node-02, dev-node-02 - filter dev vs non-dev by tags",
                "budget": {"selected_refs": ["dns-node-01", "dns-node-02", "dev-node-02"], "selected_kinds": ["sftp"]},
            }
        ],
        "priority": ["connection|sftp|dns-node-01", "connection|sftp|dns-node-02", "connection|sftp|dev-node-02"],
        "target_scope_authority": "last_turn_scope",
        "scope_operation": "surface_change",
        "answer_mode": "answer_from_context",
        "confidence": "high",
        "reason": "bad live contract contradicted last turn scope with surface change",
    }
    llm.scope_review_payload = {
        "operation": "exclude_subset",
        "selected_refs": [],
        "excluded_refs": ["dev-node-01", "dev-node-02"],
        "empty_result_allowed": True,
        "confidence": "high",
        "reason": "current scoped set contains only dev hosts",
    }
    non_dev = asyncio.run(
        pipeline.process(
            "Welche davon gehören nicht zu dev?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    llm.aria_payload = {
        "intents": ["chat", "context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "context_depth": "shallow",
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "all SSH server connections hostname IP address",
                "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
            }
        ],
        "target_scope_authority": "full_kind",
        "scope_operation": "expand_to_kind",
        "answer_mode": "answer_from_context",
        "confidence": "high",
        "reason": "reset to all ssh inventory",
    }
    reset_all = asyncio.run(
        pipeline.process(
            "Und jetzt wieder alle SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    llm.aria_payload = {
        "intents": ["chat", "context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "Welche davon sind keine dev-server?",
            }
        ],
        "target_scope_authority": "last_turn_scope",
        "scope_operation": "exclude_subset",
        "answer_mode": "answer_from_context",
        "confidence": "high",
        "reason": "exclude dev hosts from the previous full ssh inventory",
    }
    llm.scope_review_payload = {
        "operation": "exclude_subset",
        "selected_refs": [],
        "excluded_refs": ["dev-node-01", "dev-node-02"],
        "empty_result_allowed": False,
        "confidence": "high",
        "reason": "dev metadata matches two development hosts",
    }
    non_dev_after_reset = asyncio.run(
        pipeline.process(
            "Welche davon sind keine dev-server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "prod-srv01" in first.text
    assert "prod-srv01" in same_set.text
    assert "dev-node-01" in dev_subset.text
    assert "dev-node-02" in dev_subset.text
    assert "192.0.2.101" in dev_subset.text
    assert "192.0.2.102" in dev_subset.text
    assert "prod-srv01" not in dev_subset.text
    assert "Keine" in non_dev.text
    assert "prod-srv01" not in non_dev.text
    assert "dns-node-01" not in non_dev.text
    assert "dns-node-02" not in non_dev.text
    assert "prod-srv01" in reset_all.text
    assert "prod-srv01" in non_dev_after_reset.text
    assert "dev-node-01" not in non_dev_after_reset.text
    assert "dev-node-02" not in non_dev_after_reset.text
    assert "nach dem Ausschluss" in non_dev_after_reset.text
    assert "connection_evidence_scope_review" in llm.operations
    assert llm.last_scope_review_payload is not None
    assert any("connection_evidence_scope_review operation=narrow_subset" in line for line in dev_subset.detail_lines)
    assert any("evidence_bundle stored surface=connections authority=config completeness=semantic_subset rows=2" in line for line in dev_subset.detail_lines)
    assert any("connection_evidence_scope_review operation=exclude_subset" in line for line in non_dev.detail_lines)
    assert any("status=scope_review_exclude_subset_empty" in line for line in non_dev.detail_lines)
    assert not any("inventory_metadata_authority surface=connections" in line and "selected_kinds=sftp" in line for line in non_dev.detail_lines)
    assert not any("evidence_bundle_followup rejected" in line and "reason=surface_change" in line for line in non_dev.detail_lines)
    assert any("connection_evidence_scope_review operation=exclude_subset" in line for line in non_dev_after_reset.detail_lines)
    assert any("status=scope_review_exclude_subset" in line for line in non_dev_after_reset.detail_lines)
    assert any(
        "answerability surface=connections" in line
        and "field=ref" in line
        and "decision=answer_from_last_evidence_bundle_subset" in line
        for line in non_dev_after_reset.detail_lines
    )
    assert not any("query_not_host_ip" in line for line in non_dev_after_reset.detail_lines)
    assert not any("inventory_candidate_context" in line for line in non_dev_after_reset.detail_lines)
    assert not any("final_chat_response_stage" in line for line in non_dev_after_reset.detail_lines)
    assert not any("inventory_candidate_context" in line for line in dev_subset.detail_lines)
    assert not any("final_chat_response_stage" in line for line in dev_subset.detail_lines)


def test_pipeline_connection_inventory_followup_reuses_same_set_without_legacy_memory(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {"host": "192.0.2.101", "title": "dev-node-01", "tags": ["dev-server", "ssh"]},
                    "dev-node-02": {"host": "192.0.2.102", "title": "dev-node-02", "tags": ["dev-server", "ssh"]},
                    "prod-srv01": {"host": "198.51.100.101", "title": "prod-srv01", "tags": ["prod-server", "ssh"]},
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(build_inventory_documents(settings), index_hash="test-index")
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
                    "query": "all SSH server connections hostname IP address",
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "target_scope_authority": "full_kind",
            "scope_operation": "expand_to_kind",
            "answer_mode": "answer_from_context",
            "confidence": "high",
            "reason": "all ssh inventory",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    first = asyncio.run(pipeline.process("Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.", user_id="u1", source="test", language="de"))
    llm.aria_payload = {
        "intents": ["chat"],
        "needs_context": False,
        "context_directions": [],
        "surfaces": [],
        "context_requests": [],
        "target_scope_authority": "last_turn_scope",
        "scope_operation": "reuse_same_set",
        "answer_mode": "direct_answer",
        "confidence": "high",
        "reason": "same visible servers",
    }
    followup = asyncio.run(pipeline.process("Welche IPs und Hostnamen haben diese Server?", user_id="u1", source="test", language="de"))

    assert "dev-node-01" in first.text
    assert "prod-srv01" in followup.text
    assert "198.51.100.101" in followup.text
    assert any("status=reused_same_set" in line for line in followup.detail_lines)
    assert not any("memory_recall" in line for line in followup.detail_lines)
    assert not any("final_chat_response_stage" in line for line in followup.detail_lines)


def test_pipeline_connection_inventory_followup_missing_scope_operation_fails_closed(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {"ssh": {"srv-01": {"host": "192.0.2.1", "title": "srv-01", "tags": ["ssh"]}}},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(build_inventory_documents(settings), index_hash="test-index")
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
                    "query": "all SSH server connections hostname IP address",
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "target_scope_authority": "full_kind",
            "scope_operation": "expand_to_kind",
            "answer_mode": "answer_from_context",
            "confidence": "high",
            "reason": "all ssh inventory",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    asyncio.run(pipeline.process("Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.", user_id="u1", source="test", language="de"))
    llm.aria_payload = {
        "intents": ["chat"],
        "needs_context": False,
        "context_directions": [],
        "surfaces": [],
        "context_requests": [],
        "target_scope_authority": "last_turn_scope",
        "answer_mode": "direct_answer",
        "confidence": "high",
        "reason": "same visible servers",
    }
    followup = asyncio.run(pipeline.process("Welche IPs und Hostnamen haben diese Server?", user_id="u1", source="test", language="de"))

    assert "Scope-Vertrag fehlt" in followup.text
    assert any("evidence_bundle_followup blocked" in line and "reason=missing_scope_operation" in line for line in followup.detail_lines)
    assert not any("memory_recall" in line for line in followup.detail_lines)
    assert not any("final_chat_response_stage" in line for line in followup.detail_lines)


def test_pipeline_connection_inventory_followup_excludes_selected_subset(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {"host": "192.0.2.101", "title": "dev-node-01", "tags": ["dev-server", "ssh"]},
                    "dev-node-02": {"host": "192.0.2.102", "title": "dev-node-02", "tags": ["dev-server", "ssh"]},
                    "prod-srv01": {"host": "198.51.100.101", "title": "prod-srv01", "tags": ["prod-server", "ssh"]},
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    qdrant = _InventoryQdrant()
    embedder = _InventoryEmbeddingClient()
    asyncio.run(
        InventoryIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=inventory_collection_name(settings),
        ).rebuild_documents(build_inventory_documents(settings), index_hash="test-index")
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
                    "query": "all SSH server connections hostname IP address",
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "target_scope_authority": "full_kind",
            "scope_operation": "expand_to_kind",
            "answer_mode": "answer_from_context",
            "confidence": "high",
            "reason": "all ssh inventory",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    asyncio.run(pipeline.process("Und jetzt alle SSH-Server mit Hostname und IP.", user_id="u1", source="test", language="de"))
    llm.aria_payload = {
        "intents": ["context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "SSH server not dev subset",
                "budget": {
                    "bind_selected_refs": True,
                    "selected_refs": ["dev-node-01", "dev-node-02"],
                    "selected_kinds": ["ssh"],
                },
            }
        ],
        "priority": ["connection|ssh|dev-node-01", "connection|ssh|dev-node-02"],
        "target_scope_authority": "last_turn_scope",
        "scope_operation": "exclude_subset",
        "answer_mode": "answer_from_context",
        "confidence": "high",
        "reason": "exclude dev subset",
    }
    followup = asyncio.run(pipeline.process("Welche davon gehören nicht zu dev?", user_id="u1", source="test", language="de"))

    assert "prod-srv01" in followup.text
    assert "198.51.100.101" in followup.text
    assert "dev-node-01" not in followup.text
    assert "dev-node-02" not in followup.text
    assert any("status=reused_exclude_subset" in line for line in followup.detail_lines)
    assert not any("final_chat_response_stage" in line for line in followup.detail_lines)


def test_pipeline_connection_inventory_followup_expands_scope_via_loader_not_last_subset(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {
                        "host": "192.0.2.101",
                        "title": "dev-node-01",
                        "description": "Development server",
                        "tags": ["dev-server", "ssh"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.102",
                        "title": "dev-node-02",
                        "description": "Development server",
                        "tags": ["dev-server", "ssh"],
                    },
                    "prod-srv01": {
                        "host": "198.51.100.101",
                        "title": "prod-srv01",
                        "description": "Production server",
                        "tags": ["prod-server", "ssh"],
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "dev-server SSH connections hostname IP address",
                    "limit": 5,
                    "budget": {
                        "bind_selected_refs": True,
                        "selected_refs": ["dev-node-01", "dev-node-02"],
                        "selected_kinds": ["ssh"],
                    },
                }
        ],
        "priority": ["connection|ssh|dev-node-01", "connection|ssh|dev-node-02"],
        "target_scope_authority": "semantic_group",
        "scope_operation": "narrow_subset",
        "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for the dev server subset.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    first = asyncio.run(
        pipeline.process(
            "Welche IP/Hostnamen haben meine dev-server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )
    llm.aria_payload = {
        "intents": ["chat", "context_inventory"],
        "needs_context": True,
        "context_directions": ["connections"],
        "context_depth": "shallow",
        "surfaces": ["connections"],
        "context_requests": [
            {
                "surface_id": "connections",
                "mode": "inventory",
                "query": "all SSH server connections hostname IP address",
                "limit": 5,
                "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
            }
        ],
        "priority": ["connection|ssh|dev-node-01", "connection|ssh|dev-node-02", "connection|ssh|prod-srv01"],
        "target_scope_authority": "full_kind",
        "scope_operation": "expand_to_kind",
        "answer_mode": "answer_from_context",
        "risk": "none",
        "confidence": "high",
        "reason": "The user expands from dev servers to all SSH servers.",
    }
    expanded = asyncio.run(
        pipeline.process(
            "Und jetzt alle SSH-Server mit Hostname und IP",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "dev-node-01" in first.text
    assert "prod-srv01" not in first.text
    assert "prod-srv01" in expanded.text
    assert "198.51.100.101" in expanded.text
    assert any("evidence_bundle_followup rejected" in line and "reason=scope_expand_requires_loader" in line for line in expanded.detail_lines)
    assert any("context_packet" in line and "loaded=connections:3" in line for line in expanded.detail_lines)


def test_pipeline_last_connection_evidence_does_not_capture_docs_memory_surface_change(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-01": {
                        "host": "192.0.2.1",
                        "title": "srv-01",
                        "description": "SSH server",
                        "tags": ["server", "ssh"],
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "SSH server connections hostname IP address",
                    "limit": 5,
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "target_scope_authority": "full_kind",
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for SSH server inventory.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    first = asyncio.run(
        pipeline.process(
            "Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )
    llm.aria_payload = {
        "intents": ["chat", "local_retrieval"],
        "needs_context": True,
        "context_directions": ["memory", "docs"],
        "context_depth": "shallow",
        "surfaces": ["memory", "docs"],
        "context_requests": [
            {"surface_id": "memory", "mode": "search", "query": "Medikamente Beipackzettel", "limit": 5},
            {"surface_id": "docs", "mode": "search", "query": "Medikamente Beipackzettel", "limit": 5},
        ],
        "answer_mode": "answer_from_context",
        "risk": "none",
        "confidence": "high",
        "reason": "The user changes surface to medicine leaflets in memory.",
    }
    result = asyncio.run(
        pipeline.process(
            "über welche medikamente haben wir beipackzettel im memory",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "srv-01" in first.text
    assert "Host/IP" not in result.text
    assert "srv-01" not in result.text
    assert any("evidence_bundle_followup rejected" in line and "reason=surface_change" in line for line in result.detail_lines)
    assert not any("direct_context_answer kind=evidence_bundle_followup" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_llm_kind_scope_without_priority_uses_kind_authority(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    f"ssh-srv-{idx:02d}": {
                        "host": f"192.0.2.{idx}",
                        "title": f"SSH Server {idx:02d}",
                        "description": "SSH server host",
                        "tags": ["server", "ssh"],
                    }
                    for idx in range(1, 15)
                },
                "sftp": {
                    f"sftp-srv-{idx:02d}": {
                        "host": f"198.51.100.{idx}",
                        "title": f"SFTP Server {idx:02d}",
                        "description": "SFTP server host",
                        "tags": ["server", "sftp"],
                    }
                    for idx in range(1, 11)
                },
                "smb": {
                    "share-01": {
                        "host": "203.0.113.50",
                        "title": "SMB Share",
                        "description": "SMB file share",
                        "tags": ["share", "smb"],
                    }
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "SSH server connections hostname IP address",
                    "limit": 5,
                    "budget": {"bind_selected_kinds": True, "selected_kinds": ["ssh"]},
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for SSH server hostnames and IP addresses.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "ssh-srv-01" in result.text
    assert "ssh-srv-14" in result.text
    assert "192.0.2.14" in result.text
    assert "sftp-srv-01" not in result.text
    assert "share-01" not in result.text
    assert any(
        "inventory_metadata_authority" in line
        and "selected_kinds=ssh" in line
        and "kept=14" in line
        and "kind_authority=context_request" in line
        for line in result.detail_lines
    )
    assert any("context_packet" in line and "loaded=connections:14" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_llm_query_kind_contract_without_budget_uses_config_authority(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    f"ssh-srv-{idx:02d}": {
                        "host": f"192.0.2.{idx}",
                        "title": f"SSH Server {idx:02d}",
                        "description": "SSH server host",
                        "tags": ["server", "ssh"],
                    }
                    for idx in range(1, 15)
                },
                "sftp": {
                    f"sftp-srv-{idx:02d}": {
                        "host": f"198.51.100.{idx}",
                        "title": f"SFTP Server {idx:02d}",
                        "description": "SFTP server host",
                        "tags": ["server", "sftp"],
                    }
                    for idx in range(1, 4)
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "SSH server connections hostname IP overview",
                    "limit": 5,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for SSH server inventory with hostname and IP information.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Liste mir bitte die Hostnamen und IP-Adressen meiner Server auf.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "ssh-srv-01" in result.text
    assert "ssh-srv-14" in result.text
    assert "192.0.2.14" in result.text
    assert "sftp-srv-01" not in result.text
    assert not any("inventory_candidate_context surface=connections" in line for line in result.detail_lines)
    assert any(
        "inventory_metadata_authority" in line
        and "selected_kinds=ssh" in line
        and "kept=14" in line
        and "kind_authority=query_contract" in line
        for line in result.detail_lines
    )
    assert any("context_packet" in line and "loaded=connections:14" in line for line in result.detail_lines)


def test_pipeline_connection_answer_request_with_priority_refs_loads_inventory(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-02": {
                        "host": "192.0.2.32",
                        "title": "Development Server",
                        "description": "VS Code remote development host",
                        "tags": ["dev-server"],
                    }
                },
                "sftp": {
                    "dev-node-02": {
                        "host": "192.0.2.32",
                        "title": "Development Files",
                        "description": "SFTP access for the development server",
                        "tags": ["dev-server"],
                    }
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
    llm = _PipelineComposerLLM(
        {
            "intents": ["chat"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "answer",
                    "query": "Welche IP hat dev-node-02?",
                }
            ],
            "priority": ["connection|ssh|dev-node-02", "connection|sftp|dev-node-02"],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for the configured IP address.",
        },
        composer_answer="dev-node-02 hat die belegte IP-Adresse 192.0.2.32.",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Welche IP hat dev-node-02?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "dev-node-02" in result.text
    assert "192.0.2.32" in result.text
    assert "Ich habe in den ausgewaehlten lokalen Quellen dazu nichts Passendes gefunden" not in result.text
    assert any("selected_refs=dev-node-02" in line and "kept=2" in line for line in result.detail_lines)
    assert any("context_packet" in line and "loaded=connections:2" in line for line in result.detail_lines)


def test_pipeline_broad_server_ip_inventory_uses_connection_metadata_authority(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    f"srv-{idx:02d}": {
                        "host": f"192.0.2.{idx}",
                        "title": f"Server {idx:02d}",
                        "description": "SSH server host",
                        "tags": ["server", "ssh"],
                    }
                    for idx in range(1, 12)
                },
                "sftp": {
                    "files-01": {
                        "host": "192.0.2.201",
                        "title": "Files Server",
                        "description": "SFTP server host",
                        "tags": ["server", "sftp"],
                    }
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
            "intents": ["chat", "context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "all servers hostnames IP addresses",
                    "limit": 5,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for all server hostnames and IP addresses.",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Liste mir bitte die Hostnamen und IP-Adressen meiner Server auf.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "srv-01" in result.text
    assert "srv-11" in result.text
    assert "files-01" in result.text
    assert "192.0.2.201" in result.text
    assert any("inventory_metadata_authority" in line and "scope=all_host_ip" in line for line in result.detail_lines)
    assert any("context_packet" in line and "loaded=connections:12" in line for line in result.detail_lines)


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
    llm = _PipelineComposerLLM(
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
        },
        composer_answer="Ich habe eine passende konfigurierte Quelle gefunden: heise-security.",
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
    assert "aria_answer_composer" in llm.operations
    assert "final_chat_response" not in llm.operations


def test_pipeline_connection_inventory_ip_question_includes_host_evidence(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-02": {
                        "host": "192.0.2.32",
                        "user": "root",
                        "title": "Development Server",
                        "description": "VS Code remote development host",
                        "tags": ["dev-server", "development"],
                    },
                    "dns-node-01": {
                        "host": "192.0.2.53",
                        "user": "root",
                        "title": "Pi-hole DNS",
                        "description": "Network-wide ad blocking DNS server for devices.",
                        "tags": ["dns", "dhcp"],
                    },
                    "app-proxy-01": {
                        "host": "192.0.2.210",
                        "user": "root",
                        "title": "LiteLLM Proxy",
                        "description": "Gateway for developers to call LLM providers from applications.",
                        "tags": ["ai", "proxy"],
                    }
                },
                "sftp": {
                    "dev-node-02": {
                        "host": "192.0.2.32",
                        "user": "root",
                        "title": "Development Files",
                        "description": "SFTP access for the development server",
                        "tags": ["dev-server"],
                    }
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
    llm = _PipelineComposerLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {"surface_id": "connections", "mode": "inventory", "query": "was fuer ip adressen haben meine dev-server"}
            ],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for configured dev server addresses.",
        },
        composer_answer="dev-node-02 hat die belegte IP-Adresse 192.0.2.32.",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was fuer ip adressen haben meine dev-server",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["context_inventory"]
    assert "dev-node-02" in result.text
    assert "192.0.2.32" in result.text
    assert "dns-node-01" not in result.text
    assert "app-proxy-01" not in result.text
    assert "aria_answer_composer" in llm.operations
    assert any("Routing Debug: answer_composer source=llm" in line for line in result.detail_lines)
    assert not any("fast_inventory_list_answer" in line for line in result.detail_lines)


def test_pipeline_connection_inventory_semantic_group_review_filters_wrong_ref(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {
                        "host": "192.0.2.100",
                        "title": "dev-node-01",
                        "description": "Remote development environment for browser coding",
                        "tags": ["entwicklung", "vscode", "remote-coding"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.110",
                        "title": "dev-node-02",
                        "description": "Web-based development environment",
                        "tags": ["development", "vscode", "coding", "remote"],
                    },
                    "ops-alert-01": {
                        "host": "192.0.2.160",
                        "title": "ops-alert-01",
                        "description": "Network monitoring with realtime device discovery",
                        "tags": ["netalert", "monitoring", "network", "alerts"],
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
    llm = _PipelineComposerLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "context_depth": "shallow",
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "dev-server SSH connections hostname IP address",
                }
            ],
            "priority": [
                "connection|ssh|dev-node-02",
                "connection|ssh|dev-node-01",
                "connection|ssh|ops-alert-01",
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for dev-server hostnames and IP addresses.",
        },
        semantic_review_payload={
            "accepted_refs": ["dev-node-02", "dev-node-01"],
            "rejected_refs": ["ops-alert-01"],
            "confidence": "high",
            "reason": "Development metadata matches only the two dev hosts.",
        },
        composer_answer=(
            "Ich habe passende konfigurierte Quellen gefunden:\n"
            "- dev-node-01: 192.0.2.100\n"
            "- dev-node-02: 192.0.2.110"
        ),
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Welche IP/Hostnamen haben meine dev-server?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "dev-node-01" in result.text
    assert "dev-node-02" in result.text
    assert "ops-alert-01" not in result.text
    assert "inventory_semantic_scope_review" in llm.operations
    assert llm.last_semantic_review_payload is not None
    assert "ops-alert-01" in str(llm.last_semantic_review_payload)
    assert any(
        "inventory_semantic_scope_review" in line
        and "authority=reviewed" in line
        and "rejected=ops-alert-01" in line
        for line in result.detail_lines
    )
    assert any("semantic_scope_authority=reviewed" in line and "kept=2" in line for line in result.detail_lines)
    assert any("context_packet" in line and "loaded=connections:2" in line for line in result.detail_lines)


def test_pipeline_bound_connection_inventory_counts_each_selected_ref(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 5},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-node-01": {
                        "host": "192.0.2.31",
                        "user": "root",
                        "title": "Debian development server",
                        "description": "Development host for Debian testing",
                        "tags": ["dev-server", "development"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.32",
                        "user": "root",
                        "title": "Development Server",
                        "description": "VS Code remote development host",
                        "tags": ["dev-server", "development"],
                    },
                    "dns-node-01": {
                        "host": "192.0.2.53",
                        "user": "root",
                        "title": "Pi-hole DNS",
                        "description": "Network-wide ad blocking DNS server.",
                        "tags": ["dns", "dhcp"],
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
    llm = _PipelineComposerLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "was fuer ip adressen haben meine dev-server",
                }
            ],
            "priority": ["connection|ssh|dev-node-01", "connection|ssh|dev-node-02"],
            "answer_mode": "direct_answer",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for configured dev server addresses.",
        },
        composer_answer="dev-node-01 hat 192.0.2.31, dev-node-02.",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "was fuer ip adressen haben meine dev-server",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    if llm.last_composer_payload is not None:
        contract = dict(llm.last_composer_payload.get("llm_input_contract") or {})
        world_map = dict(contract.get("world_map") or {})
        answer_request = dict(world_map.get("answer_request") or {})
        outcome = dict(answer_request.get("outcome") or {})
        assert outcome.get("source_count") == 2
        assert "dev-node-01" in str(outcome)
        assert "dev-node-02" in str(outcome)
        assert "dns-node-01" not in str(outcome)
    assert "dev-node-01" in result.text
    assert "dev-node-02" in result.text
    assert "192.0.2.31" in result.text
    assert "192.0.2.32" in result.text
    assert "dns-node-01" not in result.text
    assert "aria_answer_composer" in llm.operations
    assert any("answer_composer skipped reason=invalid_or_guardrail_blocked" in line for line in result.detail_lines)
    assert any("selected_refs=dev-node-01,dev-node-02" in line and "kept=2" in line for line in result.detail_lines)
    assert any("context_packet" in line and "loaded=connections:2" in line for line in result.detail_lines)
    assert any("answer_contract kind=inventory" in line and "source_count=2" in line for line in result.detail_lines)


def test_pipeline_web_search_zero_sources_stops_before_final_chat_response() -> None:
    pipeline = Pipeline(
        settings=Settings.model_validate(
            {
                "llm": {"model": "fake"},
                "memory": {"enabled": False},
                "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
            }
        ),
        prompt_loader=_PipelinePromptLoader(),
        llm_client=_ArbiterLLM({}),
    )

    result = asyncio.run(
        pipeline._run_web_search_precheck_stage(
            skill_results=[
                SkillResult(
                    skill_name="web_search",
                    success=True,
                    content="Websuche via Internet Search · 0 Treffer",
                    metadata={"sources": [], "detail_lines": ["Websuche via Internet Search · 0 Treffer"]},
                )
            ],
            intents=["web_search"],
            decision=SimpleNamespace(level="llm"),
            safe_fix_plan=[],
            start=0.0,
            request_id="r1",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result is not None
    assert result.text == "Ich habe keine belastbaren Quellen fuer diese Frage gefunden."
    assert result.intents == ["web_search"]
    assert result.detail_lines == ["Websuche via Internet Search · 0 Treffer"]


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


def test_pipeline_meta_catalog_surface_context_without_requests_stays_unbound_inventory(monkeypatch) -> None:
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

    assert "keine vertraglich gebundene Quelle" in result.text
    assert "sports-feed" not in result.text
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
    llm = _PipelineMetaCatalogComposerLLM(
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
        },
        composer_answer=(
            "Ich habe 2 passende RSS-Profile gefunden:\n"
            "- **alle-security-news** - Alle Security News\n"
            "- **heise-security-alerts** - Heise Security Alerts"
        ),
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
    assert result.text.startswith("Ich habe 2 passende RSS-Profile gefunden:")
    assert "\n- **alle-security-news**" in result.text
    assert "\n- **heise-security-alerts**" in result.text
    assert " • " not in result.text
    assert "Alle Security News" in result.text
    assert "Heise Security Alerts" in result.text
    assert "Sports Watch" not in result.text
    assert "capability:feed_read" not in result.intents
    assert "aria_answer_composer" in llm.operations
    assert not any("agentic_runtime" in line and "capability=feed_read" in line for line in result.detail_lines)
    assert any("requests=connections:inventory" in line for line in result.detail_lines)
    assert any("Routing Debug: answer_composer source=llm" in line for line in result.detail_lines)
    assert not any("fast_inventory_list_answer" in line for line in result.detail_lines)
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


def test_pipeline_meta_catalog_full_kind_contract_binds_ssh_inventory_without_candidate_fallback(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 12},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {"host": "192.0.2.10", "title": "Server A", "tags": ["ssh"]},
                    "srv-b": {"host": "192.0.2.11", "title": "Server B", "tags": ["ssh"]},
                    "srv-c": {"host": "192.0.2.12", "title": "Server C", "tags": ["ssh"]},
                },
                "sftp": {
                    "backup-sftp": {"host": "192.0.2.50", "title": "Backup SFTP", "tags": ["sftp"]},
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
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": [],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "all SSH servers with hostname and IP address",
                    "limit": 12,
                }
            ],
            "intents": ["chat", "context_inventory"],
            "surfaces": ["connections"],
            "actions": [],
            "target_scope_authority": "full_kind",
            "scope_operation": "expand_to_kind",
            "answer_mode": "answer_from_context",
            "context_depth": "shallow",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.95,
            "reason": "all ssh server inventory",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Und jetzt alle SSH-Server mit Hostname und IP.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "srv-a" in result.text
    assert "srv-b" in result.text
    assert "srv-c" in result.text
    assert "backup-sftp" not in result.text
    assert any("scope_operation=expand_to_kind" in line for line in result.detail_lines)
    assert any(
        "inventory_metadata_authority surface=connections" in line
        and "selected_kinds=ssh" in line
        and "kept=3" in line
        and "authority=config" in line
        for line in result.detail_lines
    )
    assert any("evidence_bundle stored surface=connections authority=config completeness=full_kind rows=3" in line for line in result.detail_lines)
    assert not any("inventory_candidate_context" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_capabilities_search_loads_system_inventory(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {"ssh": {"srv-a": {"host": "192.0.2.10", "title": "Server A"}}},
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
            "catalog_ids": [],
            "context_requests": [
                {
                    "surface_id": "capabilities",
                    "mode": "search",
                    "query": "aktive Skills in ARIA",
                    "limit": 20,
                }
            ],
            "intents": ["chat"],
            "surfaces": ["capabilities"],
            "actions": [],
            "answer_mode": "answer_from_context",
            "context_depth": "shallow",
            "risk": "none",
            "needs_confirmation": False,
            "confidence": 0.95,
            "reason": "active capability inventory",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Was sind aktive Skills in ARIA?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert "ssh_command" in result.text
    assert "keine passenden Einträge" not in result.text
    assert any("requests=capabilities:inventory" in line for line in result.detail_lines)
    assert any("inventory_system surface=capabilities" in line and "authoritative=true" in line for line in result.detail_lines)
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


def test_answer_composer_preserves_multiline_inventory_rows() -> None:
    class ComposerLLM:
        def __init__(self) -> None:
            self.last_payload: dict | None = None

        async def chat(self, messages, **kwargs):  # noqa: ANN001, ARG002
            assert kwargs.get("operation") == "aria_answer_composer"
            self.last_payload = json.loads(messages[-1]["content"])
            return _Response(
                json.dumps(
                    {
                        "answer": "Du hast 2 Feeds:\n- feed-a\n- feed-b",
                        "confidence": "high",
                        "reason": "list answer",
                    }
                )
            )

    llm = ComposerLLM()
    result = asyncio.run(
        AnswerComposer(llm).compose(
            AnswerComposerInput(
                answer_mode="inventory_list",
                user_prompt="feeds",
                fallback_text="fallback",
                outcome={"status": "found"},
                evidence={"local_store_checked": True},
            )
        )
    )

    assert result.text == "Du hast 2 Feeds:\n- feed-a\n- feed-b"
    assert llm.last_payload is not None
    assert set(llm.last_payload) == {"llm_input_contract"}
    contract = llm.last_payload["llm_input_contract"]
    assert contract["contract_version"] == "llm_input_v1"
    assert contract["decision_task"] == "compose_source_bound_answer"
    assert contract["world_map"]["answer_request"]["answer_mode"] == "inventory_list"
    assert contract["world_map"]["answer_request"]["outcome"]["status"] == "found"
    assert contract["world_map"]["answer_request"]["evidence"]["local_store_checked"] is True
    assert "llm_input_contract=v1" in result.debug_line


def test_answer_composer_rejects_unbound_host_inventory_answer() -> None:
    class ComposerLLM:
        async def chat(self, messages, **kwargs):  # noqa: ANN001, ARG002
            assert kwargs.get("operation") == "aria_answer_composer"
            return _Response(
                json.dumps(
                    {
                        "answer": "Vollständige Übersicht: srv-a hat 192.0.2.10.",
                        "confidence": "high",
                        "reason": "candidate rows",
                    }
                )
            )

    result = asyncio.run(
        AnswerComposer(ComposerLLM()).compose(
            AnswerComposerInput(
                answer_mode="inventory_list",
                user_prompt="Liste Hostnamen und IP-Adressen meiner Maschinen auf.",
                fallback_text="needs narrowing",
                outcome={
                    "kind": "inventory_list",
                    "status": "found",
                    "scope_contract": "candidate_context",
                    "requires_llm_narrowing": True,
                    "sources": [
                        {
                            "surface": "connections",
                            "kind": "ssh",
                            "refs": ["srv-a"],
                            "items": [{"ref": "srv-a", "host": "192.0.2.10"}],
                        }
                    ],
                },
                evidence={"local_store_checked": True},
            )
        )
    )

    assert result.text == "needs narrowing"
    assert "answer_composer skipped" in result.debug_line


def test_answer_composer_rejects_uncautious_candidate_host_inventory_count() -> None:
    class ComposerLLM:
        async def chat(self, messages, **kwargs):  # noqa: ANN001, ARG002
            assert kwargs.get("operation") == "aria_answer_composer"
            return _Response(
                json.dumps(
                    {
                        "answer": "Ich habe **12 SSH/SFTP-Verbindungen** mit Hostname und IP-Adresse gefunden.",
                        "confidence": "high",
                        "reason": "candidate rows",
                    }
                )
            )

    result = asyncio.run(
        AnswerComposer(ComposerLLM()).compose(
            AnswerComposerInput(
                answer_mode="inventory_list",
                user_prompt="Gib mir eine Übersicht meiner SSH-Server mit Hostname und IP.",
                fallback_text="needs narrowing",
                outcome={
                    "kind": "inventory_list",
                    "status": "found",
                    "scope_contract": "candidate_context",
                    "requires_llm_narrowing": True,
                    "sources": [
                        {
                            "surface": "connections",
                            "kind": "ssh",
                            "refs": ["srv-a"],
                            "items": [{"ref": "srv-a", "host": "192.0.2.10"}],
                        }
                    ],
                },
                evidence={"local_store_checked": True},
            )
        )
    )

    assert result.text == "needs narrowing"
    assert "answer_composer skipped" in result.debug_line


def test_pipeline_unbound_host_inventory_candidate_context_cannot_claim_complete_list(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "inventory_index": {"enabled": True, "score_threshold": 0.0, "candidate_limit": 2},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "srv-a": {"host": "192.0.2.10", "title": "Server A", "tags": ["machine"]},
                    "srv-b": {"host": "192.0.2.11", "title": "Server B", "tags": ["machine"]},
                    "srv-c": {"host": "192.0.2.12", "title": "Server C", "tags": ["machine"]},
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
    llm = _PipelineComposerLLM(
        {
            "intents": ["context_inventory"],
            "needs_context": True,
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "context_requests": [
                {
                    "surface_id": "connections",
                    "mode": "inventory",
                    "query": "machine hostnames IP addresses",
                    "limit": 2,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "The user asks for machine hostnames and IP addresses.",
        },
        composer_answer="Vollständige Übersicht meiner Maschinen: srv-a hat 192.0.2.10, srv-b hat 192.0.2.11.",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "Liste Hostnamen und IP-Adressen meiner Maschinen auf.",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.text == "Ich habe Inventory-Kandidaten geladen, aber keine vertraglich gebundene Quelle ausgewählt. Ich mache daraus keine breite deterministische Trefferliste."
    assert "Vollständige Übersicht" not in result.text
    assert "aria_answer_composer" in llm.operations
    assert any("Routing Debug: inventory_candidate_context surface=connections" in line for line in result.detail_lines)
    assert any("answer_composer skipped reason=invalid_or_guardrail_blocked" in line for line in result.detail_lines)


def test_pipeline_backup_action_contract_cannot_execute_without_meta_catalog_contract(monkeypatch) -> None:
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
            "target_scope_authority": "full_kind",
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
            auto_memory_enabled=False,
        )
    )

    assert result.intents == ["blocked"]
    assert "Meta-Katalog konnte keinen belastbaren Action-Contract liefern" in result.text
    assert "final_chat_response" not in llm.operations
    assert "direct_chat_response" not in llm.operations
    assert "pre_rag_action_arbitration" not in llm.operations
    assert any("meta_catalog_contract phase=backup_fallback" in line for line in result.detail_lines)
    assert any(
        "meta_catalog_backup_fallback phase=action_preflight" in line and "legacy_semantics=blocked" in line
        for line in result.detail_lines
    )
    assert not any("pre_rag_action_gate action_path=unified_routing" in line for line in result.detail_lines)
    assert not any("multi_target_ssh_preflight" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_low_confidence_backup_action_contract_is_blocked(monkeypatch) -> None:
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
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh|srv-a", "connection|ssh|srv-b"],
            "context_requests": [],
            "intents": ["runtime_action"],
            "surfaces": ["connections"],
            "actions": ["connection_action_ssh"],
            "target_scope_authority": "full_kind",
            "answer_mode": "plan_action",
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.3,
            "reason": "uncertain meta routing must fall back visibly",
        }
    )
    llm.aria_payload = {
        "intents": ["runtime_action"],
        "needs_context": True,
        "context_directions": ["connections"],
        "surfaces": ["connections"],
        "actions": ["connection_action_ssh"],
        "target_scope_authority": "full_kind",
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
        "reason": "Backup arbiter keeps the action in preflight.",
    }
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)

    result = asyncio.run(
        pipeline.process(
            "sind alle server up2date ?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["blocked"]
    assert "Meta-Katalog konnte keinen belastbaren Action-Contract liefern" in result.text
    assert META_CATALOG_ROUTING_OPERATION in llm.operations
    assert ARIA_TURN_ARBITRATION_OPERATION in llm.operations
    assert "final_chat_response" not in llm.operations
    assert "direct_chat_response" not in llm.operations
    assert "pre_rag_action_arbitration" not in llm.operations
    assert any("meta_catalog_contract phase=backup_fallback" in line and "meta_catalog_low_confidence" in line for line in result.detail_lines)
    assert any(
        "meta_catalog_backup_fallback phase=action_preflight" in line and "legacy_semantics=blocked" in line
        for line in result.detail_lines
    )
    assert not any("multi_target_ssh_preflight" in line for line in result.detail_lines)


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
            "target_scope_authority": "full_kind",
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


def test_pipeline_meta_catalog_full_kind_ssh_update_runs_without_action_refs(monkeypatch) -> None:
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
    llm = _PipelineMetaCatalogFullKindSshRuntimeLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh"],
            "context_requests": [],
            "intents": ["chat", "runtime_action"],
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "actions": ["connection_action_ssh"],
            "target_scope_authority": "full_kind",
            "answer_mode": "answer_from_context",
            "contract_mode": "action",
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.92,
            "reason": "all configured SSH servers package update status",
        },
        target_intent="package_update_check",
        content="apt list --upgradable",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "Listing... paket/example [upgradable from: 1.0]"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)

    result = asyncio.run(
        pipeline.process(
            "sind alle server up2date ?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents == ["capability:ssh_command"]
    assert ssh_calls == [("srv-a", "apt list --upgradable"), ("srv-b", "apt list --upgradable")]
    assert "empty_action_preflight_surface_review" not in llm.operations
    assert any("meta_catalog_contract phase=action_preflight legacy_semantics=skipped" in line for line in result.detail_lines)
    assert any("plural_target_scope bound_by_turn_contract kind=ssh refs=srv-a, srv-b" in line for line in result.detail_lines)
    assert any("multi_target_ssh_preflight refs=2" in line for line in result.detail_lines)
    assert any("multi_target_ssh_preflight_result allowed=2 blocked=0" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_full_kind_ssh_capacity_runs_without_action_refs(monkeypatch) -> None:
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
    llm = _PipelineMetaCatalogFullKindSshRuntimeLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh"],
            "context_requests": [],
            "intents": ["chat", "runtime_action"],
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "actions": ["connection_action_ssh"],
            "target_scope_authority": "full_kind",
            "answer_mode": "answer_from_context",
            "contract_mode": "action",
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.92,
            "reason": "all configured SSH servers disk capacity status",
        },
        target_intent="capacity_check",
        content="df -h",
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "Filesystem Size Used Avail Use% Mounted on\n/dev/root 50G 10G 40G 20% /"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)

    result = asyncio.run(
        pipeline.process(
            "haben die festplatten auf meinen server genug harddisk speicher?",
            user_id="u1",
            source="test",
            language="de",
            auto_memory_enabled=False,
        )
    )

    assert result.intents == ["capability:ssh_command"]
    assert ssh_calls == [("srv-a", "df -h"), ("srv-b", "df -h")]
    assert "empty_action_preflight_surface_review" not in llm.operations
    assert any("meta_catalog_contract phase=action_preflight legacy_semantics=skipped" in line for line in result.detail_lines)
    assert any("plural_target_scope bound_by_turn_contract kind=ssh refs=srv-a, srv-b" in line for line in result.detail_lines)
    assert any("multi_target_ssh_preflight refs=2" in line for line in result.detail_lines)
    assert any("multi_target_ssh_preflight_result allowed=2 blocked=0" in line for line in result.detail_lines)


def test_pipeline_meta_catalog_full_kind_ssh_without_runtime_profile_does_not_reframe_to_inventory(monkeypatch) -> None:
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
    llm = _PipelineMetaCatalogLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh"],
            "context_requests": [],
            "intents": ["chat", "runtime_action"],
            "context_directions": ["connections"],
            "surfaces": ["connections"],
            "actions": ["connection_action_ssh"],
            "target_scope_authority": "full_kind",
            "answer_mode": "answer_from_context",
            "contract_mode": "action",
            "context_depth": "shallow",
            "risk": "medium",
            "needs_confirmation": True,
            "confidence": 0.92,
            "reason": "all configured SSH servers need an action but no safe runtime profile is available",
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=llm, embedding_client=embedder)
    ssh_calls: list[tuple[str, str]] = []

    async def fake_ssh(plan, *, language="de"):  # noqa: ANN001, ARG001
        ssh_calls.append((plan.connection_ref, plan.content))
        return "should not run"

    pipeline._executor_registry.register("ssh", "ssh_command", fake_ssh)

    result = asyncio.run(
        pipeline.process(
            "mach irgendwas diagnostisches mit allen ssh servern",
            user_id="u1",
            source="test",
            language="de",
            auto_memory_enabled=False,
        )
    )

    assert ssh_calls == []
    assert "empty_action_preflight_surface_review" not in llm.operations
    assert "capability_draft_decision" in llm.operations
    assert "brauche aber noch" in result.text or "Action-Contract fehlt" in result.text
    assert result.pending_action is not None
    assert any("multi_target_ssh_preflight status=blocked reason=missing_or_unsafe_command" in line for line in result.detail_lines)
    assert not any("inventory_candidate_context surface=connections" in line for line in result.detail_lines)


def test_pipeline_keeps_meta_answer_contract_instead_of_runtime_task_override(monkeypatch) -> None:
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

    assert result.intents != ["capability:ssh_command"]
    assert ssh_calls == []
    assert "capability_draft_decision" not in llm.operations
    assert not any("runtime_task_contract source=capability_draft_decision" in line for line in result.detail_lines)
    assert not any("plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b" in line for line in result.detail_lines)


def test_pipeline_mixed_rss_ssh_action_without_command_does_not_invent_update_command(monkeypatch) -> None:
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

    assert result.intents != ["capability:ssh_command"]
    assert ssh_calls == []
    assert not any("plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b command=apt list --upgradable" in line for line in result.detail_lines)
    assert not any("agentic_runtime ref=debian-security-advisories kind=rss capability=feed_read" in line for line in result.detail_lines)


def test_pipeline_rss_only_meta_action_does_not_become_ssh_update_contract(monkeypatch) -> None:
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
            "actions": ["rss_read_feed"],
            "answer_mode": "direct_answer",
            "contract": {"mode": "action", "evidence_policy": "source_bound"},
            "context_depth": "shallow",
            "risk": "low",
            "needs_confirmation": False,
            "confidence": 0.92,
            "reason": "wrongly narrowed to RSS even though selected catalog targets include SSH servers",
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
            "brauchen meine server updates und falls ja, welches sind die wichtigsten?",
            user_id="u1",
            source="test",
            language="de",
        )
    )

    assert result.intents != ["capability:ssh_command"]
    assert ssh_calls == []
    assert "capability_draft_decision" not in llm.operations
    assert not any("runtime_task_contract source=capability_draft_decision" in line for line in result.detail_lines)
    assert not any("plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b" in line for line in result.detail_lines)


def test_pipeline_meta_contract_ssh_targets_survive_plural_context_resolution(monkeypatch) -> None:
    _ = monkeypatch
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-server-01": {
                        "host": "192.0.2.20",
                        "user": "root",
                        "title": "Development server",
                        "aliases": ["und"],
                    },
                    "app-node-02": {
                        "host": "192.0.2.21",
                        "user": "root",
                        "title": "Gaming server",
                        "tags": ["server"],
                    },
                    "ops-alert-01": {
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
        connection_refs=["app-node-02", "ops-alert-01"],
        notes=[
            "capability_draft_source:meta_catalog",
            "target_scope:multi_target",
            "turn_contract_target_refs:app-node-02,ops-alert-01",
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
    assert payload["connection_refs"] == ["app-node-02", "ops-alert-01"]
    assert payload["content"] == "apt list --upgradable"
    detail_lines = list(resolved.get("detail_lines") or [])
    assert any(
        "plural_target_scope bound_by_turn_contract kind=ssh refs=app-node-02, ops-alert-01 source=meta_catalog"
        in line
        for line in detail_lines
    )
    assert any(
        "plural_target_scope selected_multi_target kind=ssh refs=app-node-02, ops-alert-01 command=apt list --upgradable"
        in line
        for line in detail_lines
    )


def test_pipeline_meta_contract_broad_server_health_keeps_contract_target_refs(monkeypatch) -> None:
    _ = monkeypatch
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "dev-server-01": {
                        "host": "192.0.2.20",
                        "user": "root",
                        "title": "Development server",
                        "aliases": ["und"],
                    },
                    "dev-node-02": {
                        "host": "192.0.2.23",
                        "user": "root",
                        "title": "Dev server",
                        "tags": ["server"],
                    },
                    "app-node-02": {
                        "host": "192.0.2.21",
                        "user": "root",
                        "title": "Gaming server",
                        "tags": ["server"],
                    },
                    "ops-alert-01": {
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
        connection_refs=["app-node-02", "ops-alert-01", "dev-node-02"],
        notes=[
            "capability_draft_source:meta_catalog",
            "target_scope:multi_target",
            "target_intent:health_check",
            "turn_contract_target_refs:app-node-02,ops-alert-01,dev-node-02",
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
    assert payload["connection_refs"] == ["app-node-02", "dev-node-02", "ops-alert-01"]
    assert payload["content"] == "uptime -p && df -h && free -h"
    detail_lines = list(resolved.get("detail_lines") or [])
    assert any(
        "plural_target_scope selected_multi_target kind=ssh refs=app-node-02, dev-node-02, ops-alert-01"
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
                    "app-node-02": {
                        "host": "192.0.2.21",
                        "user": "root",
                        "title": "Gaming server",
                        "tags": ["server"],
                    },
                },
                "sftp": {
                    "dns-node-01": {"host": "192.0.2.31", "user": "root", "path": "/"},
                    "dev-node-02": {"host": "192.0.2.32", "user": "root", "path": "/"},
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = _PipelineMetaCatalogCapacityObjectiveLLM(
        {
            "needs_context": True,
            "catalog_ids": ["connection|ssh|app-node-02", "connection|sftp|dns-node-01", "connection|sftp|dev-node-02"],
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
        explicit_connection_ref="app-node-02",
        content="",
        confidence=0.88,
        notes=[
            "capability_draft_source:meta_catalog",
            "turn_contract_source:aria_meta_catalog_routing",
            "turn_contract_priority:connection|ssh|app-node-02,connection|sftp|dns-node-01,connection|sftp|dev-node-02",
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
    assert ssh_calls == []
    assert result.direct_result.pending_action is not None
    assert any(
        "pre_rag_action_gate action_path=unified_routing capability=ssh_command kind=ssh explicit_ref=app-node-02"
        in line
        for line in result.direct_result.detail_lines
    )


def test_pre_rag_seeded_meta_catalog_contract_uses_contract_without_legacy_fallback(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "auto_memory": {"enabled": True},
            "ui": {"debug_mode": True},
            "connections": {
                "ssh": {
                    "ops-mgmt-01": {
                        "host": "192.0.2.10",
                        "user": "root",
                        "title": "Management Server",
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=_PipelinePromptLoader(), llm_client=None)
    draft = CapabilityDraft(
        capability="ssh_command",
        connection_kind="ssh",
        explicit_connection_ref="ops-mgmt-01",
        content="df -h",
        confidence=0.95,
        notes=[
            "capability_draft_source:meta_catalog",
            "turn_contract_source:aria_meta_catalog_routing",
        ],
    )
    def unexpected_local_classification(*_args, **_kwargs):  # noqa: ANN001
        raise AssertionError("seeded runtime task contract must not use local capability fallback")

    async def fake_unified_action(message, user_id, **kwargs):  # noqa: ANN001
        return pipeline._build_routed_action_result(
            request_id=str(kwargs["request_id"]),
            decision=kwargs["decision"],
            duration_ms=0,
            intents=["capability:ssh_command"],
            text="ok",
            detail_lines=["Routing Debug: fake_unified_action"],
            skill_errors=[],
        )

    monkeypatch.setattr(pipeline, "_classify_capability_draft", unexpected_local_classification)
    monkeypatch.setattr(pipeline, "_try_unified_routed_action", fake_unified_action)

    result = asyncio.run(
        pipeline._run_pre_rag_action_stage(
            message="brauchen meine server updates und falls ja, welches sind die wichtigsten?",
            user_id="u1",
            request_id="r1",
            source="test",
            decision=SimpleNamespace(intents=["runtime_action"], level=2),
            start=0.0,
            runtime_recipes=[],
            auto_memory_enabled=True,
            language="de",
            seed_capability_draft=draft,
            semantic_source=META_CATALOG_ROUTING_OPERATION,
        )
    )

    assert result.direct_result is not None
    assert result.direct_result.intents == ["capability:ssh_command"]
    assert result.capability_draft is draft
    assert result.direct_result.detail_lines[0].startswith(
        "Routing Debug: pre_rag_action_gate action_path=unified_routing capability=ssh_command kind=ssh"
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
    llm = _PipelineComposerLLM(
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
        },
        composer_answer="Ich habe eine passende beobachtete RSS-/Website-Quelle zu Sport gefunden: Sports Watch.",
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

    assert "Sports Watch" in result.text
    assert "security-feed" not in result.text
    assert "SecurityWeek" not in result.text
    assert "score=" not in result.text
    assert "aria_answer_composer" in llm.operations
    assert any("Routing Debug: inventory_candidate_context surface=connections" in line for line in result.detail_lines)
    assert any("deterministic_filter=disabled" in line for line in result.detail_lines)


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

    assert result.text == "Ich habe Inventory-Kandidaten geladen, aber keine vertraglich gebundene Quelle ausgewählt. Ich mache daraus keine breite deterministische Trefferliste."
    assert "iMonitor Internetstörungen" not in result.text
    assert "netzwerk-tools-imonitor-internet-st-rungen" not in result.text
    assert any("Routing Debug: inventory_index surface=connections matches=" in line for line in result.detail_lines)
    assert any("Routing Debug: inventory_candidate_context surface=connections" in line for line in result.detail_lines)
    assert any("deterministic_filter=disabled" in line for line in result.detail_lines)


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

    assert result.text == "Ich habe Inventory-Kandidaten geladen, aber keine vertraglich gebundene Quelle ausgewählt. Ich mache daraus keine breite deterministische Trefferliste."
    assert "gear-gadgets" not in result.text
    assert "cars-technica" not in result.text
    assert "graham-cluley" not in result.text
    candidate_lines = [line for line in result.detail_lines if "inventory_candidate_context" in line]
    assert any("deterministic_filter=disabled" in line for line in candidate_lines)


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
    llm = _PipelineComposerLLM(
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
        },
        composer_answer="Ich habe eine passende beobachtete Quelle zu Monitoring gefunden: iMonitor Internetstörungen.",
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
    assert "GitHub Security Advisories" not in result.text
    assert "github-security-advisories" not in result.text
    assert "aria_answer_composer" in llm.operations
    assert any("Routing Debug: inventory_candidate_context surface=connections" in line for line in result.detail_lines)
    assert any("deterministic_filter=disabled" in line for line in result.detail_lines)


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
    assert "no indexed or contract-bound inventory context" in sport_message

    security_message, security_sources = pipeline._aria_turn_format_inventory_metadata(
        "connections",
        dict(connections.metadata or {}),
        "IT-Security",
        limit=50,
    )
    assert security_sources == []
    assert "no indexed or contract-bound inventory context" in security_message
    assert "security-01" not in security_message
    assert "security-21" not in security_message
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
    llm = _PipelineComposerLLM(
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
            "reason": "inventory contract",
        },
        composer_answer=(
            "Ich habe passende beobachtete Quellen zu Sport gefunden:\n"
            "- sports-rss - Sports Desk RSS\n"
            "- sports-site - Sports Watch"
        ),
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
    assert not any("Routing Debug: action_to_context_inventory capability=website_list" in line for line in result.detail_lines)
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
    llm = _PipelineComposerLLM(
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
                    "limit": 8,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "inventory contract",
        },
        composer_answer=(
            "Ich habe passende beobachtete Quellen zu Sport gefunden:\n"
            "- sports-rss - Sports Desk RSS\n"
            "- sports-site - Sports Watch"
        ),
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
    assert not any("Routing Debug: action_to_context_inventory capability=website_list" in line for line in result.detail_lines)
    assert any(
        "Routing Debug: inventory_index surface=connections matches=2" in line and "authoritative=true" in line
        for line in result.detail_lines
    )
    assert "aria_answer_composer" in llm.operations
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
    llm = _PipelineComposerLLM(
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
                    "limit": 8,
                }
            ],
            "answer_mode": "answer_from_context",
            "risk": "none",
            "confidence": "high",
            "reason": "inventory contract",
        },
        composer_answer=(
            "Ich habe passende beobachtete Quellen zu Sport gefunden:\n"
            "- sports-rss - Sports Desk RSS\n"
            "- sports-site - Sports Watch"
        ),
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
    llm.composer_answer = (
        "Ich habe passende beobachtete Quellen zu IT-Security gefunden:\n"
        "- security-rss - Security RSS\n"
        "- infoguard-pentest - InfoGuard Labs Pentest Archiv"
    )

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
    frame = llm.aria_payloads_seen[-1]["llm_input_contract"]["conversation_context"]["last_turn_frame"]
    assert frame["surface_id"] == "connections"
    assert frame["mode"] == "inventory"
    assert "Sport" in frame["topic"]
    assert frame["evidence_policy"] == "source_bound"
    assert frame["answer_mode"] == "answer_from_context"


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
    frame = llm.aria_payloads_seen[-1]["llm_input_contract"]["conversation_context"]["last_turn_frame"]
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
        diagnostics={"payload_bytes": 1234, "system_chars": 567, "payload_keys": 5},
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
    assert any("arbiter_prompt_tokens=7" in line for line in result.detail_lines)
    assert any("arbiter_completion_tokens=2" in line for line in result.detail_lines)
    assert any("routing_payload_bytes=1234" in line for line in result.detail_lines)
