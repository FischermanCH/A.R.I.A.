from __future__ import annotations

import asyncio
import json

from aria.core.learning_outcomes import active_learning_hint_outcome_event
from aria.core.learning_outcomes import capture_web_search_learning_outcome
from aria.core.learning_outcomes import connection_action_outcome_event
from aria.core.learning_outcomes import recipe_catalog_outcome_event
from aria.core.learning_outcomes import web_search_outcome_event
from aria.skills.base import SkillResult


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


class _OutcomeLLM:
    async def chat(self, messages, **kwargs):
        _ = messages
        operation = str(kwargs.get("operation") or "")
        if operation == "learning_event_classification":
            return _Response(
                json.dumps(
                    {
                        "artifact_type": "source_rule_candidate",
                        "status": "proposed",
                        "risk": "low",
                        "title": "Explicit URLs need page excerpts",
                        "summary": "Concrete URL/source requests should use fetched page excerpts.",
                        "reason": "Runtime outcome observed source handling for an explicit URL.",
                        "eval_prompt": "Was steht auf https://area41.io/#speakers?",
                        "expected_behavior": "Fetch the official page excerpt before answering concrete page details.",
                        "review_criteria": ["visible in Qdrant"],
                        "confidence": "high",
                    }
                )
            )
        if operation == "learning_candidate_validation":
            return _Response(
                json.dumps(
                    {
                        "status": "dry_run",
                        "promotion_allowed": False,
                        "blockers": ["review_required"],
                        "eval_prompt": "Was steht auf https://area41.io/#speakers?",
                        "expected_path": "web_search -> official page excerpt -> answer",
                        "expected_behavior": "Use fetched official page excerpts.",
                        "negative_examples": ["answer concrete page details from snippets only"],
                        "dry_run_steps": ["run explicit URL prompt", "inspect source excerpts"],
                        "review_notes": "source outcome event",
                    }
                )
            )
        return _Response("{}")


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query, params):
        self.calls.append({"query": query, "params": dict(params)})
        return type("Result", (), {"success": True})()

    async def search_memories(self, **kwargs):
        _ = kwargs
        return []


def _web_result(*, page_excerpt_count: int, explicit_url_count: int = 1) -> SkillResult:
    return SkillResult(
        skill_name="web_search",
        content="[Web Search]",
        success=True,
        metadata={
            "sources": [
                {
                    "type": "web",
                    "title": "AREA41",
                    "url": "https://area41.io/#speakers",
                    "engine": "page_fetch",
                    "page_excerpt": bool(page_excerpt_count),
                }
            ],
            "connection_ref": "default",
            "connection_title": "SearXNG",
            "result_count": 1,
            "explicit_url_count": explicit_url_count,
            "fetch_attempt_count": 1,
            "page_excerpt_count": page_excerpt_count,
            "source_quality_outcome": (
                "explicit_url_with_page_excerpt" if page_excerpt_count else "explicit_url_without_page_excerpt"
            ),
        },
    )


def test_web_search_outcome_event_requires_explicit_url_signal() -> None:
    event = web_search_outcome_event(
        message="area41 speaker",
        user_id="u1",
        result=_web_result(page_excerpt_count=1, explicit_url_count=0),
    )

    assert event is None


def test_web_search_outcome_event_marks_missing_page_excerpt_gap() -> None:
    event = web_search_outcome_event(
        message="Was steht auf https://area41.io/#speakers?",
        user_id="u1",
        result=_web_result(page_excerpt_count=0),
    )

    assert event is not None
    assert event["event_type"] == "runtime_outcome"
    assert event["status"] == "observed_gap"
    assert event["evidence"]["outcome"] == "explicit_url_without_page_excerpt"


def test_recipe_catalog_outcome_event_marks_explicit_recipe_miss() -> None:
    event = recipe_catalog_outcome_event(
        message="gibt es ein rezept fuer dns health",
        user_id="u1",
        request_id="req-1",
        catalog_debug_line="Routing Debug: recipe_catalog_explanation source=stored_recipe_catalog matches=0 strong_matches=0",
        runtime_recipe_count=3,
        explicit_recipe_question=True,
    )

    assert event["source"] == "recipe_catalog_outcome"
    assert event["artifact_type"] == "recipe_candidate"
    assert event["status"] == "observed_gap"
    assert event["evidence"]["outcome"] == "explicit_recipe_catalog_miss"
    assert event["metadata"]["promotion_allowed"] is False


def test_connection_action_outcome_event_marks_confirmed_action_result() -> None:
    event = connection_action_outcome_event(
        message="schick eine testnachricht an discord",
        user_id="u1",
        request_id="req-1",
        candidate_kind="template",
        candidate_id="discord_send_message",
        payload={"capability": "discord_send", "connection_kind": "discord", "connection_ref": "alerts"},
        safety_decision={"action": "ask_user"},
        execution_decision={"next_step": "execute"},
        result_intents=["capability:discord_send"],
        skill_errors=[],
    )

    assert event["source"] == "connection_action_outcome"
    assert event["artifact_type"] == "procedure_candidate"
    assert event["status"] == "observed_success"
    assert event["evidence"]["outcome"] == "confirmed_connection_action_executed"
    assert event["evidence"]["connection_ref"] == "alerts"


def test_active_learning_hint_outcome_event_records_weak_signal_context() -> None:
    event = active_learning_hint_outcome_event(
        message="Was steht auf https://example.test/speakers?",
        user_id="u1",
        request_id="req-1",
        active_hints=[
            {
                "source": "qdrant_learning_active_hint",
                "collection": "aria_learning_active_hints_u1",
                "runtime_effect": "weak_signal_only",
                "text": "Active Learning Hint: concrete URLs should bias toward source lookup",
            }
        ],
        final_intents=["web_search"],
        router_level=2,
    )

    assert event is not None
    assert event["source"] == "active_learning_hint_outcome"
    assert event["artifact_type"] == "routing_hint"
    assert event["status"] == "observed_signal"
    assert event["risk"] == "low"
    assert event["evidence"]["outcome"] == "active_learning_hint_presented_to_arbiter"
    assert event["evidence"]["active_hint_collections"] == ["aria_learning_active_hints_u1"]
    assert event["evidence"]["final_intents"] == ["web_search"]
    assert event["metadata"]["runtime_effect"] == "weak_signal_only"
    assert event["metadata"]["promotion_allowed"] is False


def test_capture_web_search_learning_outcome_writes_event_candidate_and_eval_to_qdrant(monkeypatch) -> None:
    memory = _MemorySkill()
    monkeypatch.setattr(
        "aria.core.learning_outcomes.record_learning_event",
        lambda event: {**event, "event_id": "evt-web-1"},
    )

    result = asyncio.run(
        capture_web_search_learning_outcome(
            message="Was steht auf https://area41.io/#speakers?",
            user_id="u1",
            result=_web_result(page_excerpt_count=1),
            memory_skill=memory,
            llm_client=_OutcomeLLM(),
            request_id="req-1",
        )
    )

    collections = [call["params"]["collection"] for call in memory.calls]

    assert result["captured"] is True
    assert "aria_learning_events_u1" in collections
    assert "aria_learning_candidates_u1" in collections
    assert "aria_learning_evals_u1" in collections
    assert [call["params"]["memory_type"] for call in memory.calls] == [
        "learning_event",
        "learning_candidate",
        "learning_eval",
    ]


def test_capture_learning_outcome_adds_recipe_candidate_for_successful_connection_action(monkeypatch) -> None:
    from aria.core.learning_outcomes import capture_learning_outcome

    memory = _MemorySkill()
    monkeypatch.setattr(
        "aria.core.learning_outcomes.record_learning_event",
        lambda event: {**event, "event_id": "evt-conn-1"},
    )

    result = asyncio.run(
        capture_learning_outcome(
            event=connection_action_outcome_event(
                message="prüfe ob der dns server gesund ist",
                user_id="u1",
                payload={"capability": "ssh_command", "connection_kind": "ssh", "connection_ref": "dns-node-01"},
                safety_decision={"action": "allow"},
                execution_decision={"next_step": "execute"},
                skill_errors=[],
            ),
            user_id="u1",
            memory_skill=memory,
            llm_client=None,
        )
    )

    assert result["recipe_candidate"]["captured"] is True
    assert result["recipe_candidate"]["candidate"]["artifact_type"] == "recipe_candidate"
    assert result["procedure_skill"]["captured"] is True
    assert result["procedure_skill"]["procedure"]["candidate"]["artifact_type"] == "procedure_candidate"
    assert result["procedure_skill"]["skill"]["captured"] is False
    assert [call["params"]["memory_type"] for call in memory.calls] == [
        "learning_event",
        "learning_candidate",
        "learning_eval",
        "learning_candidate",
        "learning_eval",
        "learning_candidate",
        "learning_eval",
    ]
    assert "recipe_candidate" in memory.calls[-4]["query"]
    assert "procedure_candidate" in memory.calls[-2]["query"]
