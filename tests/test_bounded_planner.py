from __future__ import annotations

import asyncio
from types import SimpleNamespace

import aria.core.action_planner as action_planner_mod
from aria.core.action_candidate_taxonomy import LEARNED_EXPERIENCE_ORIGIN
from aria.core.action_candidate_taxonomy import LEARNED_RECIPE_CANDIDATE_ROLE
from aria.core.bounded_planner import debug_bounded_planner_decision
from aria.core.action_planner import build_action_planner_input_set
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.planner_candidates import build_connection_planner_input_set, merge_planner_input_sets


def test_bounded_planner_selects_bounded_ssh_run_command_pair() -> None:
    connection_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            ),
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="backup-host",
                source="semantic_alias",
                note="alias:backup host",
                alias="backup host",
                score=150,
            ),
        ],
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )
    planner_input = merge_planner_input_sets(connection_input, action_input)

    class FakeLLMClient:
        async def chat(self, _messages, **_kwargs):
            return SimpleNamespace(
                content='{"target_kind":"ssh","target_ref":"mgmt-server","action_candidate_type":"template","action_candidate_id":"ssh_run_command","confidence":"high","ask_user":false,"reason":"management server plus health intent","steps":["ssh_run_command"]}'
            )

    result = asyncio.run(debug_bounded_planner_decision(planner_input, llm_client=FakeLLMClient(), language="de"))

    assert result["status"] == "ok"
    assert result["decision"]["target_kind"] == "ssh"
    assert result["decision"]["target_ref"] == "mgmt-server"
    assert result["decision"]["action_candidate_type"] == "template"
    assert result["decision"]["action_candidate_id"] == "ssh_run_command"
    assert result["decision"]["steps"] == ["ssh_run_command"]
    assert result["planner_source"] == "llm"
    assert result["agentic_flow"]["phases"] == [
        "context_enrichment",
        "llm_action_proposal",
        "policy_guardrail_decision",
        "runtime_execution",
    ]
    assert "connection_candidates" in result["agentic_flow"]["context_sources"]
    assert "action_candidates" in result["agentic_flow"]["context_sources"]


def test_bounded_planner_prompt_makes_context_proposal_policy_contract_explicit() -> None:
    connection_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            )
        ],
        session_context={"recipe_experience": "Linux Health | worked_action=uptime -p"},
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )
    action_input.action_candidates = [item for item in action_input.action_candidates if item.candidate_id == "ssh_run_command"]
    planner_input = merge_planner_input_sets(connection_input, action_input)

    class FakeLLMClient:
        def __init__(self) -> None:
            self.messages = []

        async def chat(self, messages, **_kwargs):
            self.messages = messages
            return SimpleNamespace(
                content='{"target_kind":"ssh","target_ref":"mgmt-server","action_candidate_type":"template","action_candidate_id":"ssh_run_command","confidence":"high","ask_user":false,"reason":"bounded health action","steps":["ssh_run_command"]}'
            )

    client = FakeLLMClient()
    result = asyncio.run(debug_bounded_planner_decision(planner_input, llm_client=client, language="de"))

    prompt = "\n".join(str(message["content"]) for message in client.messages)
    assert "Agentic execution contract:" in prompt
    assert "Deterministic context enrichment" in prompt
    assert "The LLM proposes" in prompt
    assert "policy and guardrails decide allow, ask_user, or block" in prompt
    assert "experience_memory" in result["agentic_flow"]["context_sources"]


def test_bounded_planner_rejects_out_of_bounds_target_choice() -> None:
    connection_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            ),
        ],
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )
    planner_input = merge_planner_input_sets(connection_input, action_input)

    class FakeLLMClient:
        async def chat(self, _messages, **_kwargs):
            return SimpleNamespace(
                content='{"target_kind":"ssh","target_ref":"evil-host","action_candidate_type":"template","action_candidate_id":"ssh_run_command","confidence":"high","ask_user":false,"reason":"wrong target"}'
            )

    result = asyncio.run(debug_bounded_planner_decision(planner_input, llm_client=FakeLLMClient(), language="de"))

    assert result["status"] == "warn"
    assert result["decision"] == {}
    assert "outside the bounded set" in result["message"]


def test_bounded_planner_uses_single_pair_without_llm() -> None:
    connection_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            ),
        ],
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )
    # keep only one action candidate to exercise the fallback path directly
    action_input.action_candidates = [item for item in action_input.action_candidates if item.candidate_id == "ssh_run_command"]
    planner_input = merge_planner_input_sets(connection_input, action_input)

    result = asyncio.run(debug_bounded_planner_decision(planner_input, llm_client=None, language="de"))

    assert result["status"] == "ok"
    assert result["used"] is False
    assert result["decision"]["target_ref"] == "mgmt-server"
    assert result["decision"]["action_candidate_id"] == "ssh_run_command"
    assert result["planner_source"] == "heuristic"


def test_bounded_planner_decision_exposes_recipe_candidate_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        action_planner_mod,
        "_load_stored_recipe_manifests",
        lambda: (
            [
                {
                    "id": "linux-health",
                    "name": "Linux Health",
                    "description": "Prueft Linux Hosts.",
                    "connections": ["ssh"],
                    "router_keywords": ["linux health", "server check"],
                    "enabled_default": True,
                    "steps": [
                        {
                            "type": "ssh_run",
                            "params": {"command": "uptime"},
                        }
                    ],
                }
            ],
            [],
        ),
    )
    connection_input = build_connection_planner_input_set(
        query="mach bitte einen linux health check",
        preferred_connection_kind="ssh",
        connection_ref="srv-a",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="srv-a",
                source="semantic_alias",
                note="alias:srv-a",
                alias="srv-a",
                score=171,
            ),
        ],
    )
    action_input = build_action_planner_input_set(
        "mach bitte einen linux health check",
        connection_kind="ssh",
        connection_ref="srv-a",
        language="de",
    )
    action_input.action_candidates = [
        item
        for item in action_input.action_candidates
        if item.metadata.get("candidate_role") == "stored_recipe_candidate"
    ]
    planner_input = merge_planner_input_sets(connection_input, action_input)

    class FakeLLMClient:
        async def chat(self, _messages, **_kwargs):
            return SimpleNamespace(
                content='{"target_kind":"ssh","target_ref":"srv-a","action_candidate_type":"recipe","action_candidate_id":"linux-health","confidence":"high","ask_user":false,"reason":"stored recipe matches the host health request","steps":["linux-health"]}'
            )

    result = asyncio.run(debug_bounded_planner_decision(planner_input, llm_client=FakeLLMClient(), language="de"))

    assert result["status"] == "ok"
    assert result["decision"]["action_candidate_type"] == "recipe"
    assert result["decision"]["action_candidate_id"] == "linux-health"
    assert result["decision"]["action_candidate_role"] == "stored_recipe_candidate"
    assert result["decision"]["action_recipe_origin"] == "stored_recipe_manifest"
    assert result["decision"]["action_recipe_scope"] == {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]}
    assert result["decision"]["action_experience_count"] == 0
    assert result["decision"]["action_last_success_at"] == ""
    assert result["decision"]["action_promotion_state"] == ""
    assert result["decision"]["action_promotion_hint"] == ""


def test_debug_bounded_planner_decision_exposes_learned_recipe_experience_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        action_planner_mod,
        "_load_stored_recipe_manifests",
        lambda: (
            [
                {
                    "id": "linux-health",
                    "name": "Linux Health",
                    "description": "Prueft Linux Hosts.",
                    "connections": ["ssh"],
                    "router_keywords": ["linux health", "server check"],
                    "enabled_default": True,
                    "steps": [
                        {
                            "type": "ssh_run",
                            "params": {"command": "uptime"},
                        }
                    ],
                }
            ],
            [],
        ),
    )
    connection_input = build_connection_planner_input_set(
        query="mach bitte den gelernten linux health check",
        preferred_connection_kind="ssh",
        connection_ref="srv-a",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="srv-a",
                source="semantic_alias",
                note="alias:srv-a",
                alias="srv-a",
                score=171,
            ),
        ],
    )
    action_input = build_action_planner_input_set(
        "mach bitte den gelernten linux health check",
        connection_kind="ssh",
        connection_ref="srv-a",
        language="de",
    )
    action_input.action_candidates = [
        item
        for item in action_input.action_candidates
        if item.metadata.get("candidate_role") == "stored_recipe_candidate"
    ]
    learned_recipe = action_input.action_candidates[0]
    learned_recipe.candidate_id = "learned-linux-health"
    learned_recipe.metadata.update(
        {
            "candidate_role": LEARNED_RECIPE_CANDIDATE_ROLE,
            "recipe_origin": LEARNED_EXPERIENCE_ORIGIN,
            "experience_count": 7,
            "last_success_at": "2026-05-01T10:15:00Z",
            "promotion_state": "eligible",
            "promotion_hint": "Observed repeated successful Linux health checks.",
        }
    )
    planner_input = merge_planner_input_sets(connection_input, action_input)

    class FakeLLMClient:
        async def chat(self, _messages, **_kwargs):
            return SimpleNamespace(
                content='{"target_kind":"ssh","target_ref":"srv-a","action_candidate_type":"recipe","action_candidate_id":"learned-linux-health","confidence":"high","ask_user":false,"reason":"learned recipe matches the repeated host health request","steps":["learned-linux-health"]}'
            )

    result = asyncio.run(debug_bounded_planner_decision(planner_input, llm_client=FakeLLMClient(), language="de"))

    assert result["status"] == "ok"
    assert result["decision"]["action_candidate_id"] == "learned-linux-health"
    assert result["decision"]["action_candidate_role"] == LEARNED_RECIPE_CANDIDATE_ROLE
    assert result["decision"]["action_recipe_origin"] == LEARNED_EXPERIENCE_ORIGIN
    assert result["decision"]["action_experience_count"] == 7
    assert result["decision"]["action_last_success_at"] == "2026-05-01T10:15:00Z"
    assert result["decision"]["action_promotion_state"] == "eligible"
    assert result["decision"]["action_promotion_hint"] == "Observed repeated successful Linux health checks."
