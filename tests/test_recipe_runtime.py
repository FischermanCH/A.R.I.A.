from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import RoutingLanguageConfig
from aria.core.recipe_runtime import RecipeRuntime
from aria.skills.base import SkillResult


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query: str, params: dict) -> SkillResult:
        self.calls.append({"query": query, "params": dict(params)})
        return SkillResult(skill_name="memory_recall", success=True, content="")


def _runtime(memory_skill: _MemorySkill) -> RecipeRuntime:
    settings = SimpleNamespace(
        memory=SimpleNamespace(top_k=5),
        auto_memory=SimpleNamespace(session_recall_top_k=2, user_recall_top_k=2),
    )
    return RecipeRuntime(
        settings=settings,
        llm_client=None,
        memory_skill_getter=lambda: memory_skill,
        web_search_skill_getter=lambda: None,
        execute_custom_ssh_command=lambda *args, **kwargs: None,
        extract_memory_store_text=lambda *args, **kwargs: "",
        extract_memory_recall_query=lambda message, *_args, **_kwargs: str(message),
        extract_web_search_query=lambda *args, **kwargs: "",
        facts_collection_for_user=lambda user_id: f"aria_facts_{user_id}",
        preferences_collection_for_user=lambda user_id: f"aria_preferences_{user_id}",
        normalize_spaces=lambda text: text,
        truncate_text=lambda text, _limit: text,
    )


def test_run_skills_passes_docs_only_to_memory_recall() -> None:
    memory_skill = _MemorySkill()
    runtime = _runtime(memory_skill)

    results = asyncio.run(
        runtime.run_skills(
            intents=["memory_recall"],
            message="was steht in meinen dokumenten zur UI-Regel?",
            user_id="fischerman",
            routing_profile=RoutingLanguageConfig(),
            query_overrides={"memory_recall": "UI-Regel"},
            context_overrides={
                "memory_recall_enabled": True,
                "include_documents": True,
                "docs_only": True,
                "memory_top_k": 2,
            },
        )
    )

    assert [result.skill_name for result in results] == ["memory_recall"]
    assert memory_skill.calls == [
        {
            "query": "UI-Regel",
            "params": {
                "action": "recall",
                "top_k": 2,
                "user_id": "fischerman",
                "collection": "aria_facts_fischerman",
                "target_collections": [],
                "include_documents": True,
                "docs_only": True,
            },
        }
    ]
