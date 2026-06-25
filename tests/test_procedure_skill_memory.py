from __future__ import annotations

import asyncio

from aria.core.learning_outcomes import connection_action_outcome_event
from aria.core.procedure_skill_memory import build_procedure_candidate_from_outcome
from aria.core.procedure_skill_memory import build_skill_candidate_from_outcome
from aria.core.procedure_skill_memory import capture_procedure_skill_memory_from_outcome
from aria.core.procedure_skill_memory import extract_procedure_skill_guidance
from aria.core.procedure_skill_memory import recall_procedure_skill_guidance


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
                "id": "procedure-1",
                "collection": "aria_learning_candidates_u1",
                "text": (
                    "Learning Candidate: Existing DNS procedure\n"
                    "Type: procedure_candidate\n"
                    "Summary: Similar DNS health procedure already reviewed."
                ),
                "score": 0.88,
            },
            {
                "id": "recipe-1",
                "collection": "aria_learning_candidates_u1",
                "text": "Learning Candidate: Existing recipe\nType: recipe_candidate\nSummary: not procedure guidance",
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


def test_extract_procedure_skill_guidance_filters_to_procedure_and_skill_candidates() -> None:
    rows = asyncio.run(_MemorySkill().search_memories(user_id="u1", query="x", type_filter="learning_candidate"))

    guidance = extract_procedure_skill_guidance(rows)

    assert len(guidance) == 1
    assert guidance[0]["candidate_type"] == "procedure_candidate"
    assert guidance[0]["effect"] == "generalize_or_refine"
    assert guidance[0]["promotion_allowed"] is False
    assert guidance[0]["runtime_activation_allowed"] is False


def test_build_procedure_candidate_from_successful_connection_outcome() -> None:
    candidate = build_procedure_candidate_from_outcome({**_event(), "event_id": "evt-1"}, guidance=[])

    assert candidate is not None
    assert candidate["artifact_type"] == "procedure_candidate"
    assert candidate["status"] == "proposed"
    assert candidate["risk"] == "medium"
    assert candidate["source"] == "procedure_skill_memory"
    assert candidate["proposed_change"]["connection_kind"] == "ssh"
    assert candidate["proposed_change"]["capability"] == "ssh_command"
    assert candidate["proposed_change"]["promotion_allowed"] is False
    assert candidate["proposed_change"]["runtime_activation_allowed"] is False


def test_build_skill_candidate_requires_repeated_guidance() -> None:
    assert build_skill_candidate_from_outcome({**_event(), "event_id": "evt-1"}, guidance=[]) is None

    candidate = build_skill_candidate_from_outcome(
        {**_event(), "event_id": "evt-1"},
        guidance=[
            {
                "candidate_type": "procedure_candidate",
                "summary": "Similar procedure",
                "collection": "aria_learning_candidates_u1",
                "point_id": "procedure-1",
                "score": 0.88,
            }
        ],
    )

    assert candidate is not None
    assert candidate["artifact_type"] == "skill_candidate"
    assert candidate["risk"] == "high"
    assert candidate["proposed_change"]["skill_kind"] == "workflow_skill_candidate"
    assert candidate["proposed_change"]["promotion_allowed"] is False
    assert candidate["proposed_change"]["runtime_activation_allowed"] is False


def test_recall_procedure_skill_guidance_uses_qdrant_learning_candidates() -> None:
    guidance = asyncio.run(
        recall_procedure_skill_guidance(
            memory_skill=_MemorySkill(),
            user_id="u1",
            event=_event(),
        )
    )

    assert len(guidance) == 1
    assert guidance[0]["collection"] == "aria_learning_candidates_u1"


def test_capture_procedure_skill_memory_writes_procedure_and_skill_when_repeated() -> None:
    memory = _MemorySkill()

    result = asyncio.run(
        capture_procedure_skill_memory_from_outcome(
            event={**_event(), "event_id": "evt-1"},
            user_id="u1",
            memory_skill=memory,
        )
    )

    assert result["captured"] is True
    assert result["procedure"]["candidate"]["artifact_type"] == "procedure_candidate"
    assert result["skill"]["candidate"]["artifact_type"] == "skill_candidate"
    assert [call["params"]["memory_type"] for call in memory.calls] == [
        "learning_candidate",
        "learning_eval",
        "learning_candidate",
        "learning_eval",
    ]
    assert [call["params"]["collection"] for call in memory.calls] == [
        "aria_learning_candidates_u1",
        "aria_learning_evals_u1",
        "aria_learning_candidates_u1",
        "aria_learning_evals_u1",
    ]
