from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.agentic_context_runtime import AgenticContextRuntimeMixin
from aria.core.agentic_context_runtime import SurfaceLoaderRuntime
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnPlan
from aria.core.context_surfaces import ContextRequest
from aria.skills.base import SkillResult


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query: str, params: dict):
        self.calls.append({"query": query, "params": dict(params)})
        return SkillResult(skill_name="memory_recall", success=True, content="")


class _Owner:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            memory=SimpleNamespace(
                top_k=5,
                collections=SimpleNamespace(facts=SimpleNamespace(prefix="aria_facts")),
            )
        )
        self.memory_skill = _MemorySkill()

    def _aria_turn_memory_exists_evidence_query(self, arbitration: AriaTurnArbitration) -> str:
        for request in arbitration.plan.context_requests:
            if request.surface_id == "memory":
                return request.query
        return ""


def test_surface_loader_runtime_loads_memory_exists_without_pipeline_loader_method() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("memory",),
            context_requests=(ContextRequest(surface_id="memory", mode="exists", query="Donald Trump"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "memory_target_collections": ["aria_facts_u1"],
                "include_documents": False,
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls == [
        {
            "query": "Donald Trump",
            "params": {
                "action": "recall",
                "top_k": 2,
                "user_id": "u1",
                "collection": "aria_facts_u1",
                "target_collections": ["aria_facts_u1"],
                "include_documents": False,
                "docs_only": False,
            },
        }
    ]


def test_surface_loader_runtime_passes_docs_only_to_memory_recall() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "include_documents": True,
                "docs_only": True,
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls[-1]["params"]["include_documents"] is True
    assert owner.memory_skill.calls[-1]["params"]["docs_only"] is True


def test_deep_docs_context_requests_document_corpus_scan() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="deep",
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True


def test_docs_corpus_priority_requests_document_corpus_scan_even_when_shallow() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
            priority=("local|docs|document|doc-a", "local|docs|documents"),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True


def test_docs_substance_question_requests_corpus_scan_even_when_meta_is_shallow() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="Ist Glucosamin Bestandteil eines der Medikamente deren Beipackzettel wir haben",
                ),
            ),
            priority=("local|docs|document|doc-a",),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True


def test_docs_substance_question_keeps_corpus_scope_from_original_prompt_when_meta_query_is_narrowed() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="Glucosamin Bestandteil Olumiant",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "olumiant-doc",
                        "document_name": "at_olumiant_gebrauchsinformation.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
            ),
            priority=("local|docs|document|olumiant-doc",),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(
        arbitration,
        user_id="u1",
        message="Ist Glucosamin Bestandteil eines der Medikamente deren Beipackzettel wir haben",
    )

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True
    assert overrides["document_target_collections"] == ["aria_docs_sample_medications"]


def test_broad_docs_inventory_keeps_collection_scope_instead_of_selected_ids() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-a",
                        "document_name": "Olumiant.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
            ),
            priority=("local|docs|document|doc-a", "local|docs|documents"),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["document_inventory"] is True
    assert overrides["document_ids"] == []
    assert overrides["document_names"] == []
    assert overrides["document_target_collections"] == ["aria_docs_sample_medications"]


def test_broad_medication_inventory_keeps_collection_scope_even_without_documents_priority() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-a",
                        "document_name": "Olumiant.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-b",
                        "document_name": "Humira.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-c",
                        "document_name": "Simponi.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
            ),
            priority=("local|docs|document|doc-a", "local|docs|document|doc-b", "local|docs|document|doc-c"),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["document_inventory"] is True
    assert overrides["document_ids"] == []
    assert overrides["document_names"] == []
    assert overrides["document_target_collections"] == ["aria_docs_sample_medications"]


def test_surface_loader_runtime_passes_document_corpus_scan_to_memory_recall() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "include_documents": True,
                "docs_only": True,
                "document_corpus_scan": True,
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls[-1]["params"]["document_corpus_scan"] is True


def test_surface_loader_runtime_passes_document_target_collections_for_corpus_scan() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "include_documents": True,
                "docs_only": True,
                "document_corpus_scan": True,
                "document_target_collections": ["aria_docs_sample_medications"],
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls[-1]["params"]["document_corpus_scan"] is True
    assert owner.memory_skill.calls[-1]["params"]["document_target_collections"] == ["aria_docs_sample_medications"]
