from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig
from aria.modules.memory import native_tools as memory_native_tools
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.handler import NativeAgentOutcome, run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.platform_primitives.observed_claims import ObservedClaimStore


CLAIM = {
    "claim_kind": "preference",
    "predicate": "meeting_time",
    "value": "no meetings in the morning",
    "subject": "user",
}


def _owner(tmp_path: Path, *, embedder=None) -> SimpleNamespace:  # noqa: ANN001
    return SimpleNamespace(
        settings=SimpleNamespace(),
        memory_skill=object(),
        llm_client=object(),
        embedding_client=embedder,
        _facts_collection_for_user=lambda user_id: f"facts-{user_id}",
        _preferences_collection_for_user=lambda user_id: f"preferences-{user_id}",
    )


def _binding(owner, name: str):  # noqa: ANN001
    return next(item for item in memory_native_tools.native_tool_contributions(owner) if item.contract.name == name)


def _response(*, content: str = "", tool_name: str = "", arguments=None):  # noqa: ANN001
    calls = []
    if tool_name:
        calls = [SimpleNamespace(
            id=f"call-{tool_name}",
            function=SimpleNamespace(name=tool_name, arguments=json.dumps(arguments or {})),
        )]
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=calls),
            finish_reason="tool_use" if calls else "stop",
        )],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


class _Embedder:
    model = "text-embedding-3-small"

    async def embed(self, *_args, **_kwargs):
        return SimpleNamespace(vectors=[(1.0, 0.0)])


async def _not_stored(_user_id: str, _embedding, _top_k: int) -> bool:  # noqa: ANN001
    return False


def test_observed_claim_store_semantic_merge_exact_fallback_and_user_bound(tmp_path: Path) -> None:
    store = ObservedClaimStore(tmp_path / "claims.json", clock=lambda: 1000.0)
    first = store.record("alice", CLAIM, turn_id="t1", embedding=(1.0, 0.0), already_stored=False)
    near = store.record(
        "alice",
        {**CLAIM, "value": "avoid morning meetings"},
        turn_id="t2",
        embedding=(0.99, 0.01),
        already_stored=False,
    )
    exact = store.record("alice", CLAIM, turn_id="t3", embedding=None, already_stored=False)
    store.record("bob", CLAIM, turn_id="t1", embedding=(1.0, 0.0), already_stored=False)

    assert first.count == 1 and first.offer is False
    assert near.signature == first.signature and near.count == 2 and near.offer is True
    assert exact.signature == first.signature and exact.count == 3 and exact.offer is False
    assert len(store.rows_for_user("alice")) == 1
    assert len(store.rows_for_user("bob")) == 1


def test_learning_failures_never_fail_close_native_turn(tmp_path: Path) -> None:
    store = ObservedClaimStore(tmp_path / "claims.json")
    store.record = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("record offline"))

    async def completion(**request):  # noqa: ANN003
        if "response_format" in request:
            return _response(content=json.dumps(CLAIM))
        return _response(content="Thanks for telling me.")

    outcome = asyncio.run(run_native_agent_turn(
        message="I always prefer meetings after lunch.",
        user_id="alice",
        turn_id="degraded-turn",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(_owner(tmp_path), "memory_capture"),),
        completion=completion,
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=store,
        embedding_client=_Embedder(),
        personal_claim_semantic_checker=_not_stored,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Thanks for telling me."
    assert outcome.used_tool_names == ()
    assert outcome.memory_learn_claim is True
    assert outcome.memory_recurrence_count == 0
    assert outcome.suggestion_affordance is None


def test_memory_suggestion_click_uses_frozen_memory_capture_arguments(monkeypatch, tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    captured = []

    async def fake_store_personal_claim(**kwargs):  # noqa: ANN003
        captured.append(kwargs)
        return {"stored": True, "reason": "claim_activated"}

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    pending = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    binding = _binding(owner, "memory_capture")
    store = ObservedClaimStore(tmp_path / "observed.json", clock=lambda: 1000.0)

    async def run_observation(turn: int):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                return _response(content=json.dumps({**CLAIM, "predicate": f"wording_{turn}"}))
            return _response(content="Thanks for telling me.")

        return await run_native_agent_turn(
            message=(
                "I always prefer meetings after lunch."
                if turn == 1
                else "I love having meetings after lunch, always."
            ),
            user_id="alice",
            turn_id=f"t{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(binding,),
            completion=completion,
            pending_store=pending,
            confirmation_ledger=ledger,
            trace_root=tmp_path,
            memory_learning_enabled=True,
            observed_claim_store=store,
            embedding_client=_Embedder(),
            personal_claim_semantic_checker=_not_stored,
        )

    first, second = asyncio.run(_run_two(run_observation))
    assert first.suggestion_affordance is None
    suggestion = second.suggestion_affordance
    assert suggestion and suggestion["kind"] == "memory"
    assert suggestion["label"] == "Als Erinnerung speichern"
    assert captured == []

    confirmed = asyncio.run(run_native_agent_turn(
        message=suggestion["confirm_command"],
        user_id="alice",
        turn_id="confirm",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(binding,),
        completion=lambda **_kwargs: asyncio.sleep(0, result=_response(content="Stored.")),
        pending_store=pending,
        confirmation_ledger=ledger,
        confirmation_token=suggestion["token"],
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=store,
    ))
    assert confirmed.kind == "final_answer"
    assert len(captured) == 1
    assert captured[0]["claim"]["value"] == CLAIM["value"]
    assert captured[0]["claim"]["predicate"] == "wording_2"


async def _run_two(run):  # noqa: ANN001, ANN202
    return await run(1), await run(2)


def test_explicit_remember_still_calls_memory_capture_directly(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    pending = NativePendingStore(tmp_path / "pending.sqlite3")

    async def completion(**request):  # noqa: ANN003
        assert "response_format" not in request
        return _response(tool_name="memory_capture", arguments=CLAIM)

    outcome = asyncio.run(run_native_agent_turn(
        message="Remember that I prefer no morning meetings",
        user_id="alice",
        turn_id="explicit",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(owner, "memory_capture"),),
        completion=completion,
        pending_store=pending,
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=ObservedClaimStore(tmp_path / "explicit.json"),
    ))
    assert outcome.kind == "pending_confirmation"
    stored = pending.consume(user_id="alice", token=outcome.confirmation_token, now=1000)
    assert stored and stored.tool_name == "memory_capture" and stored.frozen_arguments == CLAIM


def test_memory_learning_registry_and_defaults_are_server_owned(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_admin_write_enabled", "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
        "native_agent_ssh_enabled", "native_agent_messaging_enabled", "native_agent_infra_write_enabled",
        "native_agent_recipe_execute_enabled", "native_agent_recipe_learn_enabled", "native_agent_memory_learn_enabled",
    }
    tools = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=flags)
    by_name = {item.contract.name: item.contract for item in tools}

    assert len(tools) == 37
    assert sum(item.effect == "read_only" for item in by_name.values()) == 24
    assert sum(item.effect == "mutating" for item in by_name.values()) == 13
    assert sum(item.confirmation_required for item in by_name.values()) == 13
    assert "memory_note_candidate" not in by_name
    assert asyncio.run(select_relevant_native_tools("hello", tools, selector=None)) == tools
    defaults = AgenticLoopFeatureConfig().model_dump()
    assert defaults.pop("native_web_debug_details") is False
    assert defaults.pop("native_agent_mcp_enabled") is False
    assert defaults.pop("native_tool_selector_top_k") == 16
    assert defaults.pop("native_agent_max_steps") == 32
    assert defaults.pop("native_agent_max_provider_calls") == 32
    assert defaults.pop("async_agent_job_sync_budget_seconds") == 25.0
    assert defaults.pop("native_agent_budget_extension_steps") == 32
    assert defaults.pop("native_agent_budget_max_total") == 160
    assert defaults.pop("agent_job_retention_days") == 14
    assert defaults.pop("agent_job_stale_paused_days") == 7
    assert all(defaults.values())


def test_pipeline_bridge_wires_server_store_checker_and_extraction_details(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    async def fake_turn(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        embedding_used = kwargs["turn_id"] != "no-embedding"
        return NativeAgentOutcome(
            kind="final_answer",
            message="Thanks.",
            provider_calls=2,
            recurrence_signature_hash="fedcba654321",
            recurrence_count=1,
            recurrence_offered=False,
            recurrence_similarity=0.82 if embedding_used else 0.0,
            recurrence_embedding_used=embedding_used,
            memory_recurrence_signature_hash="abcdef123456",
            memory_recurrence_count=2,
            memory_recurrence_offered=True,
            memory_learn_pre_filter="pass",
            memory_learn_extraction_ms=17,
            memory_learn_claim=True,
            memory_learn_value="mate",
        )

    async def fake_select(_message, tools, **_kwargs):  # noqa: ANN001
        return tuple(tools)

    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(pipeline_bridge, "select_relevant_native_tools", fake_select)
    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)
    config = AgenticLoopFeatureConfig()
    owner = SimpleNamespace(
        settings=SimpleNamespace(agentic_loop=config, llm=LLMConfig(model="fake")),
        _project_root=tmp_path,
        embedding_client=None,
    )

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner,
        message="I prefer quiet mornings",
        user_id="alice",
        request_id="t1",
        source="web",
        start=0.0,
    ))

    assert isinstance(owner._native_observed_claim_store, ObservedClaimStore)
    assert captured["memory_learning_enabled"] is True
    assert captured["observed_claim_store"] is owner._native_observed_claim_store
    assert callable(captured["personal_claim_semantic_checker"])
    assert (
        "Routing Debug: recurrence sig=fedcba654321 count=1 offered=false near_sim=0.82 emb=yes"
        in result.detail_lines
    )
    assert any(
        line == (
            "Routing Debug: memory_learn_extraction pre_filter=pass extraction_ms=17 "
            "claim=yes value=mate sig=abcdef123456 count=2 offered=true"
        )
        for line in result.detail_lines
    )

    result_without_embedding = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner,
        message="I prefer quiet mornings",
        user_id="alice",
        request_id="no-embedding",
        source="web",
        start=0.0,
    ))
    assert (
        "Routing Debug: recurrence sig=fedcba654321 count=1 offered=false near_sim=0.00 emb=no"
        in result_without_embedding.detail_lines
    )
