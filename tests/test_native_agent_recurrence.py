from __future__ import annotations

from pathlib import Path
import asyncio
import json
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.platform_primitives import actionable_sequence as actionable_sequence_module
from aria.modules.platform_primitives.actionable_sequence import (
    ActionableCall,
    ActionableSequence,
    LastActionableSequenceStore,
    ObservedSequenceStore,
    actionable_sequence_signature,
    actionable_sequence_to_recipe_steps,
    SIMILARITY_THRESHOLD,
    CrossHostRecipeSuggestionStore,
)
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _sequence(*, turn_id: str, outcome: str = "success") -> ActionableSequence:
    return ActionableSequence(
        turn_id=turn_id,
        intent="upgrade srv-a",
        calls=(ActionableCall(
            tool_name="ssh_command",
            arguments={"targets": ["srv-a"], "command": "apt   update && apt upgrade -y"},
            outcome=outcome,
        ),),
    )


def _recipe_remember_contract_binding() -> NativeToolBinding:
    async def handler(_context, _arguments):  # noqa: ANN001
        return NativeToolResult("saved", "recipe_remember")
    return NativeToolBinding(NativeToolContract(
        owner_module_id="recipe_runtime", name="recipe_remember", description="Remember Recipe.",
        input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
        effect="mutating", confirmation_required=True, source_authority="recipes:test",
        user_scoped=True, rollout_flag="test", order=2, relay_result_content=True,
    ), handler)


def test_observed_sequence_counts_exact_signature_once_per_turn_and_offers_at_three(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    first = store.record("alice", _sequence(turn_id="t1"), existing_recipes=())
    duplicate_same_turn = store.record("alice", _sequence(turn_id="t1"), existing_recipes=())
    second = store.record("alice", _sequence(turn_id="t2", outcome="blocked"), existing_recipes=())
    third = store.record("alice", _sequence(turn_id="t3"), existing_recipes=())
    fourth = store.record("alice", _sequence(turn_id="t4"), existing_recipes=())

    assert [first.count, duplicate_same_turn.count, second.count, third.count, fourth.count] == [1, 1, 2, 3, 4]
    assert first.offer is False and second.offer is False
    assert third.offer is True and third.offered is True
    assert fourth.offer is False and fourth.offered is True
    assert third.last_outcome == "success"
    persisted = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1001.0).get(
        "alice", third.signature,
    )
    assert persisted is not None and persisted.count == 4 and persisted.offered is True


def test_observed_sequence_clear_user_removes_rows_and_cross_host_offers_only_for_user(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "clear-sequences.json", clock=lambda: 1000.0)
    store.record(" alice ", _sequence(turn_id="a1"), existing_recipes=())
    second_sequence = ActionableSequence(
        turn_id="a2",
        intent="check srv-b",
        calls=(ActionableCall("ssh_command", {"targets": ["srv-b"], "command": "uptime"}, "success"),),
    )
    store.record(" alice ", second_sequence, existing_recipes=())
    store.record("bob", _sequence(turn_id="b1"), existing_recipes=())
    assert store.claim_cross_host_offer(" alice ", recipe_id="upgrade", new_host="srv-b") is True
    assert store.claim_cross_host_offer("bob", recipe_id="upgrade", new_host="srv-c") is True

    assert store.clear_user(" alice ") == 2
    assert store.rows_for_user("alice") == ()
    assert len(store.rows_for_user("bob")) == 1
    assert store.claim_cross_host_offer("alice", recipe_id="upgrade", new_host="srv-b") is True
    assert store.claim_cross_host_offer("bob", recipe_id="upgrade", new_host="srv-c") is False
    assert store.clear_user("unknown") == 0
    assert store.clear_user(" alice ") == 0


def test_existing_recipe_exact_signature_suppresses_offer(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    sequence = _sequence(turn_id="t1")
    steps = actionable_sequence_to_recipe_steps(sequence)
    recipe = {"id": "upgrade", "steps": steps}

    store.record("alice", sequence, existing_recipes=(recipe,))
    store.record("alice", _sequence(turn_id="t2"), existing_recipes=(recipe,))
    third = store.record("alice", _sequence(turn_id="t3"), existing_recipes=(recipe,))

    assert third.count == 3
    assert third.offer is False
    assert third.offered is False


def test_signature_is_deterministic_whitespace_normalized_and_recipe_shaped() -> None:
    sequence = _sequence(turn_id="t1")
    steps = actionable_sequence_to_recipe_steps(sequence)
    assert steps[0]["params"] == {"connection_ref": "srv-a", "command": "apt   update && apt upgrade -y"}
    assert actionable_sequence_signature(sequence) == "ssh_run:srv-a:apt update && apt upgrade -y"


def test_primary_action_recurrence_key_uses_signature_parameter_order() -> None:
    extractor = getattr(actionable_sequence_module, "primary_action_recurrence_key", None)
    assert callable(extractor)

    cases = (
        ({"type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "uptime"}},
         ("ssh_run", "srv-a", "uptime")),
        ({"type": "sftp_read", "params": {"connection_ref": "files", "remote_path": "/logs/app.log"}},
         ("sftp_read", "files", "/logs/app.log")),
        ({"type": "http_api_request", "params": {"connection_ref": "api", "request_path": "/v1/health"}},
         ("http_api_request", "api", "/v1/health")),
        ({"type": "mqtt_publish", "params": {"connection_ref": "broker", "topic": "sensors/room"}},
         ("mqtt_publish", "broker", "sensors/room")),
        ({"type": "sftp_list", "params": {"connection_ref": "files"}},
         ("sftp_list", "files", "")),
    )
    for step, expected in cases:
        assert extractor((step,)) == expected

    assert extractor((
        {"type": "sftp_list", "params": {"connection_ref": "files"}},
        {"type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "must-not-win"}},
    )) == ("sftp_list", "files", "")


def test_store_is_user_scoped_and_recipes_execute_is_not_actionable(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    sequence = ActionableSequence(
        turn_id="t1", intent="run recipe",
        calls=(ActionableCall("recipes_execute", {"recipe_id": "upgrade"}, "success"),),
    )
    assert actionable_sequence_signature(sequence) == ""
    assert store.record("alice", sequence, existing_recipes=()).count == 0
    assert store.rows_for_user("bob") == ()


def test_handler_emits_one_recurrence_affordance_without_model_text_on_third_turn(tmp_path: Path) -> None:
    actionable_store = LastActionableSequenceStore()
    observed_store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)

    async def handler(_context: NativeToolContext, _arguments):  # noqa: ANN001
        return NativeToolResult('{"status":"ok","output":"done"}', "ssh_command")

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="ssh_runtime", name="ssh_command", description="Run command.",
        input_schema={
            "type": "object",
            "properties": {"command": {"type": "string"}, "targets": {"type": "array"}},
            "required": ["command", "targets"],
        },
        effect="read_only", confirmation_required=False, source_authority="ssh:test",
        user_scoped=True, rollout_flag="test", order=1,
    ), handler)
    notes_seen: list[list[str]] = []

    async def run(turn: int):
        call_index = 0

        async def completion(**kwargs):  # noqa: ANN003
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                function = SimpleNamespace(name="ssh_command", arguments=json.dumps({
                    "command": "uptime", "targets": ["srv-a"],
                }))
                tool_call = SimpleNamespace(id=f"call-{turn}", function=function)
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content="", tool_calls=[tool_call]), finish_reason="tool_use",
                )])
            notes_seen.append([
                str(row.get("content") or "") for row in kwargs["messages"]
                if row.get("role") == "system"
                and isinstance(row.get("content"), str)
                and str(row.get("content") or "").startswith("RECURRENCE-NOTE")
            ])
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="Done.", tool_calls=[]), finish_reason="stop",
            )])

        return await run_native_agent_turn(
            message="uptime srv-a", user_id="alice", turn_id=f"t{turn}",
            llm_config=LLMConfig(model="claude-sonnet-4-5"), tool_bindings=(binding, _recipe_remember_contract_binding()),
            completion=completion, trace_root=tmp_path, actionable_sequence_store=actionable_store,
            observed_sequence_store=observed_store, existing_recipes=(),
            pending_store=NativePendingStore(tmp_path / "pending.sqlite3"),
        )

    outcomes = [asyncio.run(run(turn)) for turn in (1, 2, 3)]
    assert notes_seen[0] == [] and notes_seen[1] == []
    assert notes_seen[2] == []
    assert outcomes[0].suggestion_affordance is None and outcomes[1].suggestion_affordance is None
    assert outcomes[2].suggestion_affordance["kind"] == "recurrence"
    assert outcomes[2].suggestion_affordance["confirm_command"].startswith("confirm action na")
    assert outcomes[2].recurrence_count == 3
    assert outcomes[2].recurrence_offered is True
    assert len(outcomes[2].recurrence_signature_hash) == 12
    assert [outcome.recurrence_embedding_used for outcome in outcomes] == [False, False, False]
    assert [outcome.recurrence_similarity for outcome in outcomes] == [0.0, 1.0, 1.0]


def test_handler_skips_failed_actionable_result_from_recurrence(tmp_path: Path) -> None:
    actionable_store = LastActionableSequenceStore()
    observed_store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)

    async def handler(_context: NativeToolContext, _arguments):  # noqa: ANN001
        return NativeToolResult(
            '{"status":"ok","results":[{"target":"missing","status":"unknown_target","output":""}]}',
            "ssh_command", actionable_arguments=None, actionable_outcome="skip",
        )

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="ssh_runtime", name="ssh_command", description="Run command.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="ssh:test",
        user_scoped=True, rollout_flag="test", order=1,
    ), handler)
    calls = 0

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            function = SimpleNamespace(name="ssh_command", arguments='{"command":"uptime","targets":["missing"]}')
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[SimpleNamespace(id="c1", function=function)]),
                finish_reason="tool_use",
            )])
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Not found.", tool_calls=[]), finish_reason="stop",
        )])

    outcome = asyncio.run(run_native_agent_turn(
        message="uptime missing", user_id="alice", turn_id="t1",
        llm_config=LLMConfig(model="claude-sonnet-4-5"), tool_bindings=(binding,),
        completion=completion, trace_root=tmp_path, actionable_sequence_store=actionable_store,
        observed_sequence_store=observed_store, existing_recipes=(),
    ))

    assert outcome.kind == "final_answer"
    assert actionable_store.get("alice") is None
    assert observed_store.rows_for_user("alice") == ()


def test_handler_collapses_resolved_name_and_ref_into_one_signature(tmp_path: Path) -> None:
    actionable_store = LastActionableSequenceStore()
    observed_store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)

    async def handler(_context: NativeToolContext, arguments):  # noqa: ANN001
        return NativeToolResult(
            '{"status":"ok","results":[{"target":"srv-a","status":"ok","output":"up"}]}',
            "ssh_command",
            actionable_arguments={"command": arguments["command"], "targets": ["srv-a"]},
            actionable_outcome="success",
        )

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="ssh_runtime", name="ssh_command", description="Run command.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="ssh:test",
        user_scoped=True, rollout_flag="test", order=1,
    ), handler)

    async def run(turn: int, target: str):
        calls = 0
        async def completion(**_kwargs):  # noqa: ANN003
            nonlocal calls
            calls += 1
            if calls == 1:
                function = SimpleNamespace(name="ssh_command", arguments=json.dumps({
                    "command": "uptime", "targets": [target],
                }))
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content="", tool_calls=[SimpleNamespace(id=f"c{turn}", function=function)]),
                    finish_reason="tool_use",
                )])
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="Done.", tool_calls=[]), finish_reason="stop",
            )])
        return await run_native_agent_turn(
            message=f"uptime {target}", user_id="alice", turn_id=f"t{turn}",
            llm_config=LLMConfig(model="claude-sonnet-4-5"), tool_bindings=(binding,),
            completion=completion, trace_root=tmp_path, actionable_sequence_store=actionable_store,
            observed_sequence_store=observed_store, existing_recipes=(),
        )

    outcomes = [
        asyncio.run(run(1, "Primary App")), asyncio.run(run(2, "srv-a")), asyncio.run(run(3, "10.0.0.10")),
    ]
    rows = observed_store.rows_for_user("alice")
    assert len(rows) == 1 and rows[0].count == 3
    assert rows[0].signature == "ssh_run:srv-a:uptime"
    assert outcomes[2].recurrence_offered is True


def test_semantic_near_duplicates_merge_only_in_same_tool_host_bucket(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    first = _sequence(turn_id="t1")
    near = ActionableSequence("t2", "upgrade srv-a", (
        ActionableCall("ssh_command", {"targets": ["srv-a"], "command": "apt update; apt upgrade -y"}, "success"),
    ))
    other_host = ActionableSequence("t3", "upgrade srv-b", (
        ActionableCall("ssh_command", {"targets": ["srv-b"], "command": "apt update; apt upgrade -y"}, "success"),
    ))

    one = store.record("alice", first, existing_recipes=(), embedding=(1.0, 0.0))
    two = store.record("alice", near, existing_recipes=(), embedding=(0.99, 0.01))
    store.record("alice", other_host, existing_recipes=(), embedding=(0.99, 0.01))

    assert SIMILARITY_THRESHOLD == 0.88
    assert two.signature == one.signature and two.count == 2
    assert one.similarity == 0.0
    assert two.similarity > SIMILARITY_THRESHOLD
    assert len(store.rows_for_user("alice")) == 2


def test_semantic_near_miss_reports_best_similarity_without_clustering(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "near-miss.json", clock=lambda: 1000.0)
    first = store.record("alice", _sequence(turn_id="t1"), existing_recipes=(), embedding=(1.0, 0.0))
    near_miss_sequence = ActionableSequence("t2", "near miss", (
        ActionableCall(
            "ssh_command", {"targets": ["srv-a"], "command": "apt update --list"}, "success",
        ),
    ))
    near_miss = store.record(
        "alice", near_miss_sequence, existing_recipes=(), embedding=(0.8, 0.6),
    )

    assert first.similarity == 0.0
    assert round(near_miss.similarity, 2) == 0.80
    assert near_miss.similarity < SIMILARITY_THRESHOLD
    assert near_miss.signature != first.signature
    assert near_miss.count == 1
    assert len(store.rows_for_user("alice")) == 2


def test_semantic_dissimilar_action_stays_separate_and_exact_fallback_works(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    first = store.record("alice", _sequence(turn_id="t1"), existing_recipes=(), embedding=(1.0, 0.0))
    different = ActionableSequence("t2", "restart", (
        ActionableCall("ssh_command", {"targets": ["srv-a"], "command": "systemctl restart nginx"}, "success"),
    ))
    second = store.record("alice", different, existing_recipes=(), embedding=(0.0, 1.0))
    exact = store.record("alice", _sequence(turn_id="t3"), existing_recipes=(), embedding=None)

    assert first.signature != second.signature
    assert exact.signature == first.signature and exact.count == 2
    assert len(store.rows_for_user("alice")) == 2


def test_cross_host_offer_pair_is_persistently_one_shot(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    assert store.claim_cross_host_offer("alice", recipe_id="upgrade", new_host="srv-b") is True
    assert store.claim_cross_host_offer("alice", recipe_id="upgrade", new_host="srv-b") is False
    assert store.claim_cross_host_offer("alice", recipe_id="upgrade", new_host="srv-a") is True


def test_handler_batches_semantic_embedding_and_injects_cross_host_suggestion(tmp_path: Path) -> None:
    actionable_store = LastActionableSequenceStore()
    observed_store = ObservedSequenceStore(tmp_path / "observed.json")
    suggestions = CrossHostRecipeSuggestionStore()
    embed_calls = []

    class Embedder:
        model = "text-embedding-3-small"
        async def embed(self, inputs, **kwargs):  # noqa: ANN001, ANN003
            embed_calls.append((inputs, kwargs))
            return SimpleNamespace(vectors=[[1.0, 0.0], [0.99, 0.01]])

    async def handler(_context, arguments):  # noqa: ANN001
        return NativeToolResult(
            '{"status":"ok"}', "ssh_read",
            actionable_arguments={"command": arguments["command"], "targets": ["srv-b"]},
            actionable_outcome="success",
        )

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="ssh_runtime", name="ssh_read", description="Read.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="ssh:test",
        user_scoped=True, rollout_flag="test", order=1,
    ), handler)
    seen_notes = []
    calls = 0
    async def completion(**kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            function = SimpleNamespace(name="ssh_read", arguments='{"command":"apt update","targets":["friendly"]}')
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[SimpleNamespace(id="c1", function=function)]),
                finish_reason="tool_use",
            )])
        seen_notes.extend(str(row.get("content")) for row in kwargs["messages"] if str(row.get("content", "")).startswith("SUGGESTION-NOTE"))
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Done.", tool_calls=[]), finish_reason="stop",
        )])

    outcome = asyncio.run(run_native_agent_turn(
        message="update friendly", user_id="alice", turn_id="t1",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding, _recipe_remember_contract_binding()), completion=completion,
        actionable_sequence_store=actionable_store, observed_sequence_store=observed_store,
        embedding_client=Embedder(), recipe_embedding_cache={},
        cross_host_suggestion_store=suggestions, trace_root=tmp_path,
        pending_store=NativePendingStore(tmp_path / "pending.sqlite3"),
        existing_recipes=({"id": "update-a", "name": "Update A", "enabled": True, "steps": [
            {"id": "s1", "type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "apt upgrade"}},
            {"id": "s2", "type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "reboot-if-needed"}},
        ]},),
    ))

    assert len(embed_calls) == 1 and embed_calls[0][0] == ["apt update", "apt upgrade"]
    assert seen_notes == []
    assert outcome.semantic_match_recipe == "Update A" and outcome.semantic_similarity > 0.88
    assert outcome.suggestion_affordance["kind"] == "cross_host"
    assert outcome.suggestion_affordance["new_host"] == "srv-b"
    assert suggestions.get("alice").new_host == "srv-b"


def test_handler_embeds_and_clusters_non_ssh_primary_actions_without_cross_host_offer(tmp_path: Path) -> None:
    actionable_store = LastActionableSequenceStore()
    observed_store = ObservedSequenceStore(tmp_path / "observed-sftp.json")
    suggestions = CrossHostRecipeSuggestionStore()
    embed_calls: list[list[str]] = []

    class Embedder:
        model = "text-embedding-3-small"

        async def embed(self, inputs, **_kwargs):  # noqa: ANN001, ANN003
            embed_calls.append(list(inputs))
            return SimpleNamespace(vectors=[[1.0, 0.01 * len(embed_calls)]])

    async def handler(_context, arguments):  # noqa: ANN001
        return NativeToolResult(
            '{"status":"ok"}', "file_read",
            actionable_arguments=dict(arguments), actionable_outcome="success",
        )

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="sftp", name="file_read", description="Read remote file.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="sftp:test",
        user_scoped=True, rollout_flag="test", order=1,
    ), handler)
    paths = ("/logs/app.log", "/logs/application.log", "/logs/app-current.log")

    async def run(turn: int, path: str):
        calls = 0

        async def completion(**_kwargs):  # noqa: ANN003
            nonlocal calls
            calls += 1
            if calls == 1:
                function = SimpleNamespace(name="file_read", arguments=json.dumps({
                    "connection_kind": "sftp", "connection_ref": "files-a", "path": path,
                }))
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(
                        content="", tool_calls=[SimpleNamespace(id=f"sftp-{turn}", function=function)],
                    ),
                    finish_reason="tool_use",
                )])
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="Done.", tool_calls=[]), finish_reason="stop",
            )])

        return await run_native_agent_turn(
            message=f"read {path}", user_id="alice", turn_id=f"sftp-t{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(binding, _recipe_remember_contract_binding()), completion=completion,
            actionable_sequence_store=actionable_store, observed_sequence_store=observed_store,
            embedding_client=Embedder(), recipe_embedding_cache={},
            cross_host_suggestion_store=suggestions, trace_root=tmp_path,
            pending_store=NativePendingStore(tmp_path / "sftp-pending.sqlite3"),
            existing_recipes=({
                "id": "ssh-only", "name": "SSH only", "enabled": True,
                "steps": [{
                    "id": "s1", "type": "ssh_run",
                    "params": {"connection_ref": "srv-a", "command": "cat /logs/app.log"},
                }],
            },),
        )

    outcomes = [asyncio.run(run(index, path)) for index, path in enumerate(paths, 1)]

    assert embed_calls == [[path] for path in paths]
    assert [outcome.recurrence_count for outcome in outcomes] == [1, 2, 3]
    assert outcomes[0].recurrence_offered is False and outcomes[1].recurrence_offered is False
    assert outcomes[2].recurrence_offered is True
    assert outcomes[2].suggestion_affordance["kind"] == "recurrence"
    assert all(outcome.semantic_match_recipe == "" for outcome in outcomes)
    assert all(outcome.recurrence_embedding_used for outcome in outcomes)
    assert outcomes[0].recurrence_similarity == 0.0
    assert outcomes[1].recurrence_similarity > SIMILARITY_THRESHOLD
    assert outcomes[2].recurrence_similarity > SIMILARITY_THRESHOLD
    assert suggestions.get("alice") is None
    assert len(observed_store.rows_for_user("alice")) == 1


def test_embedding_failure_preserves_exact_recurrence_path(tmp_path: Path) -> None:
    store = ObservedSequenceStore(tmp_path / "observed.json")
    first = store.record("alice", _sequence(turn_id="t1"), existing_recipes=())
    second = store.record("alice", _sequence(turn_id="t2"), existing_recipes=(), embedding=None)
    assert first.signature == second.signature and second.count == 2
