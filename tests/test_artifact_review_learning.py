from __future__ import annotations

import asyncio

from aria.core.artifact_review_learning import capture_prepared_artifact_review_learning
from aria.core.artifact_review_learning import prepared_artifact_review_candidate
from aria.core.artifact_review_learning import prepared_artifact_review_event


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query, params):
        self.calls.append({"query": query, "params": dict(params)})
        return type("Result", (), {"success": True})()


def _review_payload(decision: str = "accepted") -> dict:
    return {
        "prepared_artifact_review_state": "reviewed",
        "prepared_artifact_review_decision": decision,
        "prepared_artifact_review_notes": "Useful skeleton.",
        "prepared_artifact_target_file": "tests/test_app_plan_generated.py",
        "prepared_artifact_code_preview_sha256": "abcdef1234567890",
        "pytest_write_allowed": False,
        "runtime_activation_allowed": False,
    }


def test_prepared_artifact_review_event_requires_reviewed_decision() -> None:
    event = prepared_artifact_review_event(
        user_id="u1",
        candidate_collection="aria_learning_candidates_u1",
        candidate_point_id="point-1",
        candidate_text="Learning Candidate: test",
        artifact_kind="pytest_skeleton_write",
        review_payload={**_review_payload(), "prepared_artifact_review_state": "blocked"},
    )

    assert event is None


def test_prepared_artifact_review_candidate_maps_accepted_to_pattern_candidate() -> None:
    event = prepared_artifact_review_event(
        user_id="u1",
        candidate_collection="aria_learning_candidates_u1",
        candidate_point_id="point-1",
        candidate_text="Learning Candidate: test",
        artifact_kind="pytest_skeleton_write",
        review_payload=_review_payload("accepted"),
    )

    assert event is not None
    candidate = prepared_artifact_review_candidate({**event, "event_id": "evt-1"})

    assert candidate["artifact_type"] == "artifact_pattern_candidate"
    assert candidate["status"] == "proposed"
    assert candidate["risk"] == "low"
    assert candidate["proposed_change"]["write_allowed"] is False
    assert candidate["metadata"]["promotion_allowed"] is False


def test_prepared_artifact_review_candidate_maps_needs_changes_to_improvement_candidate() -> None:
    event = prepared_artifact_review_event(
        user_id="u1",
        candidate_collection="aria_learning_candidates_u1",
        candidate_point_id="point-1",
        candidate_text="Learning Candidate: test",
        artifact_kind="pytest_skeleton_write",
        review_payload=_review_payload("needs_changes"),
    )

    assert event is not None
    candidate = prepared_artifact_review_candidate({**event, "event_id": "evt-1"})

    assert candidate["artifact_type"] == "artifact_improvement_candidate"
    assert "needs_changes" in candidate["summary"]


def test_prepared_artifact_review_candidate_maps_rejected_to_negative_pattern_candidate() -> None:
    event = prepared_artifact_review_event(
        user_id="u1",
        candidate_collection="aria_learning_candidates_u1",
        candidate_point_id="point-1",
        candidate_text="Learning Candidate: test",
        artifact_kind="pytest_skeleton_write",
        review_payload=_review_payload("rejected"),
    )

    assert event is not None
    candidate = prepared_artifact_review_candidate({**event, "event_id": "evt-1"})

    assert candidate["artifact_type"] == "negative_pattern_candidate"
    assert "Avoid repeating" in candidate["expected_behavior"]


def test_capture_prepared_artifact_review_learning_writes_event_candidate_and_eval_to_qdrant(monkeypatch) -> None:
    memory = _MemorySkill()
    monkeypatch.setattr(
        "aria.core.artifact_review_learning.record_learning_event",
        lambda event: {**event, "event_id": "evt-review-1"},
    )

    result = asyncio.run(
        capture_prepared_artifact_review_learning(
            user_id="u1",
            memory_skill=memory,
            candidate_collection="aria_learning_candidates_u1",
            candidate_point_id="point-1",
            candidate_text="Learning Candidate: Compose install plan",
            artifact_kind="pytest_skeleton_write",
            review_payload=_review_payload("accepted"),
        )
    )

    assert result["captured"] is True
    assert result["candidate"]["artifact_type"] == "artifact_pattern_candidate"
    assert [call["params"]["memory_type"] for call in memory.calls] == [
        "learning_event",
        "learning_candidate",
        "learning_eval",
    ]
    assert [call["params"]["collection"] for call in memory.calls] == [
        "aria_learning_events_u1",
        "aria_learning_candidates_u1",
        "aria_learning_evals_u1",
    ]
