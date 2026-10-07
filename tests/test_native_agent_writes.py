from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig
from aria.modules.memory.native_tools import native_tool_contributions as memory_tools
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.pipeline_bridge import native_agent_enabled
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.platform_primitives.actionable_sequence import (
    LastActionableSequenceStore,
    ObservedSequenceStore,
)
from aria.modules.notes.native_tools import native_tool_contributions as notes_tools
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _response(*, content: str = "", tool_calls=None, finish_reason: str = "stop"):  # noqa: ANN001
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls or [])),
        finish_reason=finish_reason,
    )])


def _tool_call(name: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{name}",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeMemorySkill:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, *, query: str, params: dict[str, object]):
        self.calls.append((query, dict(params)))
        if params["action"] == "forget_preview":
            owned = {"claim-owned": {"collection": "alice-facts", "id": "point-1", "claim_id": "claim-owned"}}
            candidates = [owned[item] for item in params["personal_claim_ids"] if item in owned]
            return SimpleNamespace(success=True, error="", content="", metadata={"forget_candidates": candidates})
        candidates = list(params["candidates"])
        return SimpleNamespace(
            success=True, error="", content="", metadata={"deleted_count": len(candidates)},
        )


def _memory_binding(skill: FakeMemorySkill):
    owner = SimpleNamespace(memory_skill=skill)
    return next(binding for binding in memory_tools(owner) if binding.contract.name == "memory_forget")


def test_memory_forget_preview_confirm_owned_only_and_replay(tmp_path) -> None:
    skill = FakeMemorySkill()
    binding = _memory_binding(skill)
    store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    calls = 0

    async def preview_completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            system_prompt = _kwargs["messages"][0]["content"]
            assert "offered read-only tools" not in system_prompt
            assert "only after the appropriate tool returned success in this turn" in system_prompt
            return _response(tool_calls=[_tool_call("memory_forget", {
                "claim_ids": ["claim-owned", "claim-foreign"], "summary": "Forget the old preference",
            })], finish_reason="tool_use")
        return _response(content="I will forget the selected memory after confirmation.")

    preview = asyncio.run(run_native_agent_turn(
        message="forget that", user_id="alice", turn_id="forget-preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=preview_completion,
        pending_store=store, confirmation_ledger=ledger, trace_root=tmp_path / "trace", now=1000,
    ))
    assert preview.kind == "pending_confirmation"
    assert preview.message == "I will forget the selected memory after confirmation."
    assert skill.calls == []
    pending = store.peek(user_id="alice", token=preview.confirmation_token, now=1001)
    assert pending is not None
    assert pending.frozen_arguments["claim_ids"] == ["claim-owned", "claim-foreign"]

    async def result_completion(**_kwargs):
        return _response(content="I deleted one stored memory.")

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", turn_id="forget-confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=result_completion,
        pending_store=store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1002,
    ))
    replay = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", turn_id="forget-replay",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=result_completion,
        pending_store=store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1003,
    ))

    assert confirmed.kind == "final_answer" and confirmed.message == "I deleted one stored memory."
    assert replay.kind == "confirmation_refused"
    assert skill.calls[0][1] == {
        "action": "forget_preview", "user_id": "alice", "personal_claim_ids": ["claim-owned", "claim-foreign"],
        "max_hits": 2,
    }
    assert skill.calls[1][1] == {
        "action": "forget_apply", "user_id": "alice",
        "candidates": [{"collection": "alice-facts", "id": "point-1", "claim_id": "claim-owned"}],
    }


def test_main_prompt_allows_offered_writes_and_forbids_fabricated_actions(tmp_path) -> None:
    captured: dict[str, str] = {}

    async def completion(**kwargs):
        captured["system"] = kwargs["messages"][0]["content"]
        return _response(content="I cannot do that because no matching tool is available.")

    binding = next(item for item in memory_tools(SimpleNamespace(memory_skill=FakeMemorySkill()))
                   if item.contract.name == "recall_personal_memory")
    outcome = asyncio.run(run_native_agent_turn(
        message="Delete something", user_id="alice", turn_id="honest-unavailable",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        trace_root=tmp_path / "trace",
    ))

    assert outcome.kind == "final_answer"
    assert "read-only tools" not in captured["system"]
    assert "Use only the tools offered in this turn" in captured["system"]
    assert "remember, save, store, note, memorise or keep a fact or preference" in captured["system"]
    assert "only after the appropriate tool returned success in this turn" in captured["system"]
    assert "Answer directly only for general conversation that needs no data" in captured["system"]
    assert "For ANY question about the current state of a server, file, remote system, connection" in captured["system"]
    assert "you MUST call the appropriate tool and rely ONLY on what it returns in this turn" in captured["system"]
    assert "never invent, guess, recall or reuse command output, file contents, sizes, listings, statuses or results" in captured["system"]
    assert "instead of presenting any specific data as if you retrieved it" in captured["system"]


def test_repeated_live_read_requires_fresh_tool_call_and_reaches_recurrence_threshold(tmp_path) -> None:
    tool_calls = 0
    observed = ObservedSequenceStore(tmp_path / "observed.json")
    actionable = LastActionableSequenceStore()

    async def handler(_context: NativeToolContext, arguments) -> NativeToolResult:  # noqa: ANN001
        nonlocal tool_calls
        tool_calls += 1
        return NativeToolResult(
            f'{{"status":"ok","target":"{arguments["targets"][0]}","output":"fresh-{tool_calls}"}}',
            "ssh:read",
        )

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="test", name="ssh_read", description="Read current SSH state.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "targets": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["command", "targets"],
        },
        effect="read_only", confirmation_required=False, source_authority="ssh:test",
        user_scoped=True, rollout_flag="test_enabled",
    ), handler)

    async def completion(**kwargs):  # noqa: ANN003
        system = kwargs["messages"][0]["content"]
        if isinstance(system, list):
            system = system[0]["text"]
        tool_results = [row for row in kwargs["messages"] if row.get("role") == "tool"]
        if tool_results:
            return _response(content=f"Current disk state: {tool_results[-1]['content']}")
        fresh_rule = (
            "A repeated request for current state ALWAYS requires a fresh tool call in this turn"
            in str(system)
        )
        if fresh_rule:
            return _response(tool_calls=[_tool_call(
                "ssh_read", {"command": "df -h", "targets": ["srv-a"]},
            )], finish_reason="tool_use")
        return _response(content="Current disk state copied from prior conversation.")

    outcomes = [
        asyncio.run(run_native_agent_turn(
            message="show df -h on srv-a", user_id="alice", turn_id=f"repeat-{index}",
            llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
            actionable_sequence_store=actionable, observed_sequence_store=observed,
            trace_root=tmp_path / "trace",
        ))
        for index in range(1, 4)
    ]

    assert tool_calls == 3
    assert all(outcome.used_tool_names == ("ssh_read",) for outcome in outcomes)
    assert outcomes[-1].recurrence_count == 3


def test_main_prompt_routes_memory_mutations_and_fragments_without_fabricated_success(tmp_path) -> None:
    captured: dict[str, str] = {}

    async def completion(**kwargs):
        captured["system"] = kwargs["messages"][0]["content"]
        return _response(content="Please clarify what you want me to remember.")

    binding = next(item for item in memory_tools(SimpleNamespace(memory_skill=FakeMemorySkill()))
                   if item.contract.name == "recall_personal_memory")
    outcome = asyncio.run(run_native_agent_turn(
        message="dir, dass ich morgens keine Meetings mag", user_id="alice", turn_id="fragmented-memory",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        trace_root=tmp_path / "trace",
    ))

    assert outcome.kind == "final_answer"
    prompt = captured["system"]
    assert "remember, save, store, note, memorise or keep a fact or preference" in prompt
    assert "short, truncated, fragmented or ambiguous" in prompt
    assert "call the appropriate offered tool or ask what exactly should be done" in prompt
    assert "only after the appropriate tool returned success in this turn" in prompt


def test_main_prompt_requires_web_search_for_fast_changing_external_facts(tmp_path) -> None:
    captured: dict[str, str] = {}

    async def completion(**kwargs):
        captured["system"] = kwargs["messages"][0]["content"]
        return _response(content="I need current web evidence to answer that.")

    binding = next(item for item in memory_tools(SimpleNamespace(memory_skill=FakeMemorySkill()))
                   if item.contract.name == "recall_personal_memory")
    outcome = asyncio.run(run_native_agent_turn(
        message="welches ist die neuste apple watch", user_id="alice", turn_id="fresh-external-fact",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        trace_root=tmp_path / "trace",
    ))

    assert outcome.kind == "final_answer"
    prompt = captured["system"]
    assert "latest or current state of an external, fast-changing fact" in prompt
    assert "MUST call web_search_fetch" in prompt
    assert "Training knowledge is stale for these questions" in prompt
    assert "freshness-neutral" in prompt
    assert "latest or current" in prompt
    assert "NEVER hardcode a past year" in prompt
    assert "the tool knows the current date" in prompt
    assert "date or as-of state found" in prompt
    assert "latest state you found" in prompt


def test_plain_chat_remains_direct_and_tool_execution_records_used_tool(tmp_path) -> None:
    async def handler(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        return NativeToolResult('{"status":"ok","value":"source-bound"}', "test_read")

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="test", name="test_read", description="Read source-bound test data.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="test:source",
        user_scoped=True, rollout_flag="test_enabled",
    ), handler)

    async def chat_completion(**_kwargs):
        return _response(content="Hello!")

    chat = asyncio.run(run_native_agent_turn(
        message="Hello", user_id="alice", turn_id="plain-chat",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=chat_completion,
        trace_root=tmp_path / "chat-trace",
    ))

    calls = 0

    async def tool_completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call("test_read", {})], finish_reason="tool_use")
        return _response(content="The source-bound value is available.")

    tool = asyncio.run(run_native_agent_turn(
        message="Read the current value", user_id="alice", turn_id="tool-read",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=tool_completion,
        trace_root=tmp_path / "tool-trace",
    ))

    assert chat.kind == "final_answer" and chat.message == "Hello!"
    assert chat.provider_calls == 1 and chat.used_tool_names == ()
    assert tool.kind == "final_answer" and tool.message == "The source-bound value is available."
    assert tool.provider_calls == 2 and tool.used_tool_names == ("test_read",)


def test_memory_forget_handler_returns_fresh_deleted_count_and_ignores_summary() -> None:
    skill = FakeMemorySkill()
    result = asyncio.run(_memory_binding(skill).handler(
        NativeToolContext(user_id="alice"),
        {"claim_ids": ["claim-owned", "claim-foreign"], "summary": "not deletion authority"},
    ))

    assert json.loads(result.content) == {"deleted_count": 1}
    assert all("summary" not in params for _query, params in skill.calls)


class FakeNotesStore:
    def __init__(self) -> None:
        self.rows = {"note-1": SimpleNamespace(note_id="note-1", title="Old", body="Old body", folder="Work")}
        self.saved: list[dict[str, str]] = []

    def get_note(self, user_id: str, note_id: str):
        return self.rows.get(note_id) if user_id == "alice" else None

    @staticmethod
    def _normalize_title(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())[:140].strip()

    @staticmethod
    def _normalize_folder(value: str) -> str:
        return str(value or "").replace("\\", "/").strip().strip("/")

    def list_notes(self, user_id: str):
        return list(self.rows.values()) if user_id == "alice" else []

    def save_note(self, user_id: str, *, title: str, body: str, folder: str = "", note_id: str = ""):
        self.saved.append({"user_id": user_id, "title": title, "body": body, "folder": folder, "note_id": note_id})
        actual_id = note_id or "note-created"
        row = SimpleNamespace(note_id=actual_id, title=title, body=body, folder=folder)
        self.rows[actual_id] = row
        return row


def _notes_binding(store: FakeNotesStore):
    owner = SimpleNamespace(base_dir=".", settings=SimpleNamespace(), _native_agent_notes_store=store)
    return next(binding for binding in notes_tools(owner) if binding.contract.name == "notes_write")


def test_notes_update_existing_and_create_unchanged() -> None:
    store = FakeNotesStore()
    binding = _notes_binding(store)
    updated = asyncio.run(binding.handler(NativeToolContext(user_id="alice"), {
        "note_id": "note-1", "title": "New", "body": "New body", "folder": "Work",
    }))
    created = asyncio.run(binding.handler(NativeToolContext(user_id="alice"), {
        "title": "Created", "body": "Body", "folder": "Inbox",
    }))

    assert json.loads(updated.content) == {
        "status": "ok", "action": "updated", "note_id": "note-1", "title": "New", "folder": "Work",
    }
    assert json.loads(created.content) == {
        "status": "ok", "action": "created", "note_id": "note-created", "title": "Created", "folder": "Inbox",
    }
    assert store.saved[0]["note_id"] == "note-1"
    assert store.saved[1]["note_id"] == ""


def test_notes_update_missing_never_creates() -> None:
    store = FakeNotesStore()
    result = asyncio.run(_notes_binding(store).handler(NativeToolContext(user_id="alice"), {
        "note_id": "missing", "title": "No", "body": "No", "folder": "Work",
    }))

    assert json.loads(result.content) == {
        "status": "not_found", "action": "updated", "note_id": "missing", "title": "No", "folder": "Work",
    }
    assert store.saved == []


def test_notes_upsert_by_normalized_title_updates_without_duplicate() -> None:
    store = FakeNotesStore()
    store.rows["note-1"] = SimpleNamespace(
        note_id="note-1", title="Project Notes", body="Old", folder="Work",
    )
    result = asyncio.run(_notes_binding(store).handler(NativeToolContext(user_id="alice"), {
        "title": "  Project   Notes ", "body": "New body", "folder": "Work/",
    }))

    assert json.loads(result.content)["action"] == "updated"
    assert json.loads(result.content)["note_id"] == "note-1"
    assert store.saved == [{
        "user_id": "alice", "title": "Project Notes", "body": "New body",
        "folder": "Work", "note_id": "note-1",
    }]
    assert len(store.rows) == 1


def test_notes_upsert_creates_when_title_absent() -> None:
    store = FakeNotesStore()
    result = asyncio.run(_notes_binding(store).handler(NativeToolContext(user_id="alice"), {
        "title": "Fresh Note", "body": "Body", "folder": "Inbox",
    }))

    assert json.loads(result.content)["action"] == "created"
    assert store.saved[0]["note_id"] == ""


def test_notes_upsert_ambiguous_title_writes_nothing() -> None:
    store = FakeNotesStore()
    store.rows = {
        "note-1": SimpleNamespace(note_id="note-1", title="Same", body="One", folder="Work"),
        "note-2": SimpleNamespace(note_id="note-2", title="Same", body="Two", folder="Work"),
    }
    result = asyncio.run(_notes_binding(store).handler(NativeToolContext(user_id="alice"), {
        "title": "Same", "body": "Replacement", "folder": "Work",
    }))

    assert json.loads(result.content) == {
        "status": "ambiguous_title", "action": "ambiguous_title", "note_id": "",
        "title": "Same", "folder": "Work", "matches": ["note-1", "note-2"],
    }
    assert store.saved == []


def test_notes_upsert_title_match_is_folder_scoped() -> None:
    store = FakeNotesStore()
    store.rows = {
        "work-note": SimpleNamespace(note_id="work-note", title="Same", body="Work", folder="Work"),
        "home-note": SimpleNamespace(note_id="home-note", title="Same", body="Home", folder="Home"),
    }
    result = asyncio.run(_notes_binding(store).handler(NativeToolContext(user_id="alice"), {
        "title": "Same", "body": "Updated", "folder": "Home",
    }))

    assert json.loads(result.content)["note_id"] == "home-note"
    assert json.loads(result.content)["action"] == "updated"
    assert store.saved[0]["note_id"] == "home-note"


def test_notes_write_remains_confirmation_gated_and_reports_phrasing_action() -> None:
    binding = _notes_binding(FakeNotesStore())
    assert binding.contract.effect == "mutating"
    assert binding.contract.confirmation_required is True
    assert binding.contract.rollout_flag == "native_agent_write_notes_enabled"


def test_notes_confirmation_result_phrasing_receives_created_and_updated_action(tmp_path) -> None:
    async def run_case(*, store: FakeNotesStore, arguments: dict[str, object], expected_action: str):
        binding = _notes_binding(store)
        pending_store = NativePendingStore(tmp_path / f"{expected_action}-pending.sqlite3")
        ledger = ActionConfirmationLedger(tmp_path / f"{expected_action}-ledger.sqlite3")
        preview_calls = 0

        async def preview_completion(**_kwargs):
            nonlocal preview_calls
            preview_calls += 1
            if preview_calls == 1:
                return _response(tool_calls=[_tool_call("notes_write", arguments)], finish_reason="tool_use")
            return _response(content="Please confirm the note change.")

        preview = await run_native_agent_turn(
            message="Change the note", user_id="alice", turn_id=f"{expected_action}-preview",
            llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=preview_completion,
            pending_store=pending_store, confirmation_ledger=ledger, now=1000,
        )
        assert preview.kind == "pending_confirmation"

        async def result_completion(**kwargs):
            payload = json.loads(
                kwargs["messages"][2]["content"].removeprefix("Authoritative action payload: ")
            )
            assert payload["action"] == expected_action
            return _response(content=f"The note was {expected_action}.")

        return await run_native_agent_turn(
            message=preview.confirm_command, user_id="alice", turn_id=f"{expected_action}-confirm",
            llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=result_completion,
            pending_store=pending_store, confirmation_ledger=ledger,
            confirmation_token=preview.confirmation_token, now=1001,
        )

    created_store = FakeNotesStore()
    created = asyncio.run(run_case(
        store=created_store, arguments={"title": "Fresh", "body": "Body", "folder": "Inbox"},
        expected_action="created",
    ))
    updated_store = FakeNotesStore()
    updated_store.rows["note-1"] = SimpleNamespace(
        note_id="note-1", title="Existing", body="Old", folder="Work",
    )
    updated = asyncio.run(run_case(
        store=updated_store, arguments={"title": "Existing", "body": "New", "folder": "Work"},
        expected_action="updated",
    ))

    assert created.kind == "final_answer" and created.message == "The note was created."
    assert updated.kind == "final_answer" and updated.message == "The note was updated."


def test_write_flags_gate_tools_and_registry_defaults() -> None:
    owner = SimpleNamespace(settings=SimpleNamespace(), memory_skill=FakeMemorySkill())
    read_flags = {"native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled"}
    reads = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=read_flags)
    writes = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags={
        *read_flags, "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
    })

    assert len(reads) == 23
    assert all(item.contract.effect == "read_only" for item in reads)
    assert len(writes) == 26
    assert {item.contract.name for item in writes if item.contract.effect == "mutating"} == {
        "notes_write", "memory_forget", "memory_capture",
    }
    assert all(item.contract.confirmation_required for item in writes if item.contract.effect == "mutating")
    assert asyncio.run(select_relevant_native_tools("write", writes, selector=None)) == writes

    config = AgenticLoopFeatureConfig()
    assert config.native_agent_write_memory_enabled is True
    assert native_agent_enabled(SimpleNamespace(agentic_loop=config)) is True
