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
