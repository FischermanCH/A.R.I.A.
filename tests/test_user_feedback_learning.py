from __future__ import annotations

import asyncio
import json

from aria.core.user_feedback_learning import UserFeedbackLearningDetector
from aria.core.user_feedback_learning import capture_user_feedback_learning


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


class _FeedbackLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []

    async def chat(self, messages, **kwargs):
        _ = messages
        operation = str(kwargs.get("operation") or "")
        self.operations.append(operation)
        if operation == "user_feedback_learning_detection":
            return _Response(
                json.dumps(
                    {
                        "is_feedback": True,
                        "sentiment": "negative",
                        "summary": "Use official page excerpts instead of snippets.",
                        "artifact_hint": "source_rule_candidate",
                        "reason": "The user corrected source handling.",
                    }
                )
            )
        if operation == "learning_event_classification":
            return _Response(
                json.dumps(
                    {
                        "artifact_type": "source_rule_candidate",
                        "status": "proposed",
                        "risk": "low",
                        "title": "Official excerpts first",
                        "summary": "Prefer official page excerpts over snippets.",
                        "reason": "User feedback corrected source behavior.",
                        "eval_prompt": "was sind die themen der speaker an der area41 konferenz 2026",
                        "expected_behavior": "Fetch official page excerpts.",
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
                        "eval_prompt": "was sind die themen der speaker an der area41 konferenz 2026",
                        "expected_path": "web_search -> official page excerpt -> answer",
                        "expected_behavior": "Use official page excerpts.",
                        "negative_examples": ["answer from snippets only"],
                        "dry_run_steps": ["run prompt", "inspect sources"],
                        "review_notes": "review source handling",
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


def test_user_feedback_detector_uses_bounded_llm_for_durable_feedback() -> None:
    llm = _FeedbackLLM()

    event = asyncio.run(
        UserFeedbackLearningDetector(llm).detect(
            "Das war meh, bitte offizielle Page Excerpts statt Such-Snippets nutzen.",
            user_id="u1",
            history=[{"role": "assistant", "text": "Antwort aus Such-Snippets"}],
        )
    )

    assert event is not None
    assert event["event_type"] == "feedback"
    assert event["artifact_type"] == "user_feedback"
    assert event["metadata"]["detector"] == "bounded_llm"
    assert event["metadata"]["artifact_hint"] == "source_rule_candidate"
    assert llm.operations == ["user_feedback_learning_detection"]


def test_capture_user_feedback_learning_writes_event_candidate_and_eval_to_qdrant(monkeypatch) -> None:
    llm = _FeedbackLLM()
    memory = _MemorySkill()
    monkeypatch.setattr(
        "aria.core.user_feedback_learning.record_learning_event",
        lambda event: {**event, "event_id": "evt-feedback-1"},
    )

    result = asyncio.run(
        capture_user_feedback_learning(
            message="Das war meh, bitte offizielle Page Excerpts statt Such-Snippets nutzen.",
            user_id="u1",
            history=[{"role": "assistant", "text": "Antwort aus Such-Snippets"}],
            memory_skill=memory,
            llm_client=llm,
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


def test_user_feedback_detector_ignores_normal_task_request() -> None:
    class _NoFeedbackLLM(_FeedbackLLM):
        async def chat(self, messages, **kwargs):
            _ = messages
            self.operations.append(str(kwargs.get("operation") or ""))
            return _Response(json.dumps({"is_feedback": False}))

    event = asyncio.run(
        UserFeedbackLearningDetector(_NoFeedbackLLM()).detect(
            "wie ist das wetter morgen?",
            user_id="u1",
            history=[],
        )
    )

    assert event is None


def test_user_feedback_detector_fallback_captures_obvious_feedback_without_llm() -> None:
    event = asyncio.run(
        UserFeedbackLearningDetector(None).detect(
            "Das war falsch, du hast wieder nur Such-Snippets genommen.",
            user_id="u1",
            history=[{"role": "assistant", "text": "Vorherige Antwort"}],
        )
    )

    assert event is not None
    assert event["event_type"] == "feedback"
    assert event["metadata"]["detector"] == "fallback"
    assert event["metadata"]["feedback_sentiment"] == "negative"
