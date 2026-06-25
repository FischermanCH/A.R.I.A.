from __future__ import annotations

import asyncio

from aria.core.artifact_review_patterns import artifact_review_pattern_query
from aria.core.artifact_review_patterns import extract_artifact_review_patterns
from aria.core.artifact_review_patterns import recall_artifact_review_patterns


class _MemorySkill:
    async def search_memories(self, **kwargs):
        assert kwargs["type_filter"] == "learning_candidate"
        assert kwargs["user_id"] == "u1"
        return [
            {
                "id": "pattern-1",
                "collection": "aria_learning_candidates_u1",
                "type": "learning_candidate",
                "text": (
                    "Learning Candidate: Accepted prepared artifact pattern\n"
                    "Type: artifact_pattern_candidate\n"
                    "Summary: pytest_skeleton_write review: accepted; target=tests/test_app_plan_generated.py\n"
                    "Expected behavior: Use this accepted proposal shape as review-only guidance."
                ),
                "score": 0.91,
            },
            {
                "id": "noise-1",
                "collection": "aria_learning_candidates_u1",
                "type": "learning_candidate",
                "text": "Learning Candidate: Other\nType: source_rule_candidate\nSummary: not a pattern",
                "score": 0.5,
            },
            {
                "id": "negative-1",
                "collection": "aria_learning_candidates_u1",
                "type": "learning_candidate",
                "text": (
                    "Learning Candidate: Rejected prepared artifact pattern\n"
                    "Type: negative_pattern_candidate\n"
                    "Summary: pytest_skeleton_write review: rejected; target=aria/test_bad.py"
                ),
                "score": 0.42,
            },
        ]


def test_artifact_review_pattern_query_includes_app_and_regression_context() -> None:
    query = artifact_review_pattern_query(
        app_identity={"runtime_kind": "docker_compose", "app_root": "/srv/aria"},
        regression_drafts=[{"name": "test_plan_preview"}],
        plan_validation={"validation_state": "review_required"},
    )

    assert "pytest skeleton prepared artifact review pattern" in query
    assert "docker_compose" in query
    assert "test_plan_preview" in query


def test_extract_artifact_review_patterns_filters_to_review_pattern_types() -> None:
    rows = asyncio.run(_MemorySkill().search_memories(user_id="u1", query="x", type_filter="learning_candidate", top_k=12))

    patterns = extract_artifact_review_patterns(rows)

    assert [item["pattern_type"] for item in patterns] == ["artifact_pattern_candidate", "negative_pattern_candidate"]
    assert patterns[0]["effect"] == "encourage"
    assert patterns[1]["effect"] == "avoid"
    assert patterns[0]["write_allowed"] is False
    assert patterns[0]["runtime_activation_allowed"] is False


def test_recall_artifact_review_patterns_uses_qdrant_learning_candidates() -> None:
    patterns = asyncio.run(
        recall_artifact_review_patterns(
            memory_skill=_MemorySkill(),
            user_id="u1",
            query="docker compose pytest skeleton",
        )
    )

    assert len(patterns) == 2
    assert patterns[0]["collection"] == "aria_learning_candidates_u1"
