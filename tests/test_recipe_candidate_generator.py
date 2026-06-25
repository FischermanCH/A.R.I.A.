from __future__ import annotations

import asyncio

from aria.core.learning_outcomes import connection_action_outcome_event
from aria.core.recipe_candidate_generator import build_recipe_candidate_from_outcome
from aria.core.recipe_candidate_generator import capture_recipe_candidate_from_outcome
from aria.core.recipe_candidate_generator import extract_recipe_candidate_guidance
from aria.core.recipe_candidate_generator import recall_recipe_candidate_guidance


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query, params):
        self.calls.append({"query": query, "params": dict(params)})
        return type("Result", (), {"success": True})()

    async def search_memories(self, **kwargs):
        assert kwargs["type_filter"] == "learning_candidate"
        return [
            {
                "id": "recipe-1",
                "collection": "aria_learning_candidates_u1",
                "text": (
                    "Learning Candidate: Existing health workflow\n"
                    "Type: recipe_candidate\n"
                    "Summary: Similar SSH health workflow already proposed."
                ),
                "score": 0.86,
            },
            {
                "id": "noise-1",
                "collection": "aria_learning_candidates_u1",
                "text": "Learning Candidate: Source rule\nType: source_rule_candidate\nSummary: not recipe",
                "score": 0.7,
            },
        ]


def _event() -> dict:
    return connection_action_outcome_event(
        message="prüfe ob der dns server gesund ist",
        user_id="u1",
        request_id="req-1",
        candidate_kind="template",
        candidate_id="ssh_dns_health",
        payload={
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "dns-node-01",
            "command": "systemctl is-active pihole-FTL",
        },
        safety_decision={"action": "allow"},
        execution_decision={"next_step": "execute"},
        result_intents=["capability:ssh_command"],
        skill_errors=[],
    )


def test_extract_recipe_candidate_guidance_filters_recipe_candidates() -> None:
    rows = asyncio.run(_MemorySkill().search_memories(user_id="u1", query="x", type_filter="learning_candidate"))

    guidance = extract_recipe_candidate_guidance(rows)

    assert len(guidance) == 1
    assert guidance[0]["candidate_type"] == "recipe_candidate"
    assert guidance[0]["effect"] == "dedupe_or_improve"
    assert guidance[0]["runtime_activation_allowed"] is False


def test_build_recipe_candidate_from_successful_connection_outcome_without_guidance() -> None:
    candidate = build_recipe_candidate_from_outcome({**_event(), "event_id": "evt-1"}, guidance=[])

    assert candidate is not None
    assert candidate["artifact_type"] == "recipe_candidate"
    assert candidate["status"] == "proposed"
    assert candidate["risk"] == "medium"
    assert candidate["source"] == "recipe_candidate_generator"
    assert candidate["proposed_change"]["connection_kind"] == "ssh"
    assert candidate["proposed_change"]["capability"] == "ssh_command"
    assert candidate["proposed_change"]["promotion_allowed"] is False
    assert candidate["proposed_change"]["runtime_activation_allowed"] is False
    assert candidate["metadata"]["similar_recipe_guidance_count"] == 0
    assert candidate["metadata"]["recipe_candidate_mode"] == "new_candidate"


def test_build_recipe_candidate_from_successful_connection_outcome_with_guidance_becomes_improvement() -> None:
    candidate = build_recipe_candidate_from_outcome(
        {**_event(), "event_id": "evt-1"},
        guidance=[
            {
                "candidate_type": "recipe_candidate",
                "summary": "Similar workflow",
                "collection": "aria_learning_candidates_u1",
                "point_id": "recipe-1",
                "score": 0.86,
            }
        ],
    )

    assert candidate is not None
    assert candidate["artifact_type"] == "recipe_improvement"
    assert candidate["status"] == "proposed"
    assert candidate["risk"] == "medium"
    assert candidate["source"] == "recipe_candidate_generator"
    assert candidate["proposed_change"]["connection_kind"] == "ssh"
    assert candidate["proposed_change"]["capability"] == "ssh_command"
    assert candidate["proposed_change"]["recipe_kind"] == "connection_workflow_recipe_improvement"
    assert candidate["proposed_change"]["improves_existing_candidates"] is True
    assert candidate["proposed_change"]["promotion_allowed"] is False
    assert candidate["proposed_change"]["runtime_activation_allowed"] is False
    assert candidate["metadata"]["similar_recipe_guidance_count"] == 1
    assert candidate["metadata"]["recipe_candidate_mode"] == "improvement"


def test_build_recipe_candidate_skips_failed_connection_outcome() -> None:
    event = connection_action_outcome_event(
        message="prüfe dns",
        user_id="u1",
        payload={"capability": "ssh_command", "connection_kind": "ssh"},
        skill_errors=["ssh timeout"],
    )

    assert build_recipe_candidate_from_outcome(event) is None


def test_recall_recipe_candidate_guidance_uses_qdrant_learning_candidates() -> None:
    guidance = asyncio.run(
        recall_recipe_candidate_guidance(
            memory_skill=_MemorySkill(),
            user_id="u1",
            event=_event(),
        )
    )

    assert len(guidance) == 1
    assert guidance[0]["collection"] == "aria_learning_candidates_u1"


def test_capture_recipe_candidate_from_outcome_writes_candidate_and_eval_to_qdrant() -> None:
    memory = _MemorySkill()

    result = asyncio.run(
        capture_recipe_candidate_from_outcome(
            event={**_event(), "event_id": "evt-1"},
            user_id="u1",
            memory_skill=memory,
        )
    )

    assert result["captured"] is True
    assert result["candidate"]["artifact_type"] == "recipe_improvement"
    assert [call["params"]["memory_type"] for call in memory.calls] == ["learning_candidate", "learning_eval"]
    assert [call["params"]["collection"] for call in memory.calls] == [
        "aria_learning_candidates_u1",
        "aria_learning_evals_u1",
    ]
