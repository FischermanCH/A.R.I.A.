from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from aria.modules.platform_primitives.actionable_sequence import (
    CrossHostRecipeSuggestion,
    CrossHostRecipeSuggestionStore,
    LastActionableSequenceStore,
)
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.recipe_runtime.native_tools import native_tool_contributions
from aria.modules.recipe_store.manifests import validate_stored_recipe_manifest
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.sdk import NativeToolBinding, NativeToolContract, NativeToolContext, NativeToolResult


def _binding(owner, name="recipe_remember"):
    return next(item for item in native_tool_contributions(owner) if item.contract.name == name)


def test_recipe_remember_saves_inactive_exact_target_draft() -> None:
    store = LastActionableSequenceStore()
    store.append("alice", turn_id="turn-1", intent="check host", tool_name="ssh_read",
                 arguments={"command": "uptime", "targets": ["srv-a"]}, outcome="success")
    saved = []
    owner = SimpleNamespace(_native_actionable_sequence_store=store,
                            _native_agent_recipe_saver=lambda row: saved.append(row) or row)

    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"name": "Host check"},
    ))

    assert result.content == 'Recipe "Host check" saved as an inactive draft in My Recipes. Review and activate it and, for mutating commands, whitelist it before running.'
    assert saved[0]["enabled_default"] is False
    assert saved[0]["steps"][0]["type"] == "ssh_run"
    assert saved[0]["steps"][0]["params"] == {"connection_ref": "srv-a", "command": "uptime"}


def test_recipe_remember_keeps_blocked_attempt_as_inactive_draft() -> None:
    store = LastActionableSequenceStore()
    store.append("alice", turn_id="turn-1", intent="upgrade host", tool_name="ssh_command",
                 arguments={"command": "apt upgrade -y", "targets": ["srv-a"]}, outcome="blocked")
    saved = []
    owner = SimpleNamespace(_native_actionable_sequence_store=store,
                            _native_agent_recipe_saver=lambda row: saved.append(row) or row)

    asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"name": "Upgrade host"},
    ))

    assert saved[0]["enabled_default"] is False
    assert saved[0]["steps"][0]["params"]["command"] == "apt upgrade -y"


def test_recipe_remember_translates_all_declared_actionable_tool_shapes() -> None:
    store = LastActionableSequenceStore()
    calls = [
        ("file_read", {"connection_kind": "sftp", "connection_ref": "sftp-a", "path": "/a"}),
        ("file_write", {"connection_kind": "smb", "connection_ref": "smb-a", "path": "/b", "content": "x"}),
        ("file_list", {"connection_kind": "sftp", "connection_ref": "sftp-a", "path": "/"}),
        ("discord_send", {"connection_ref": "discord-a", "content": "hello"}),
        ("webhook_send", {"connection_ref": "hook-a", "content": "hello"}),
        ("email_send", {"connection_ref": "mail-a", "content": "hello"}),
        ("mqtt_publish", {"connection_ref": "mqtt-a", "topic": "a", "content": "hello"}),
        ("http_api_request", {"connection_ref": "api-a", "request_path": "/v1", "content": "{}"}),
        ("mail_read", {"connection_ref": "imap-a"}),
        ("mail_search", {"connection_ref": "imap-a", "query": "invoice"}),
        ("calendar_read", {"connection_ref": "cal-a", "range_hint": "week"}),
    ]
    for tool_name, arguments in calls:
        store.append("alice", turn_id="turn-1", intent="sequence", tool_name=tool_name,
                     arguments=arguments, outcome="success")
    saved = []
    owner = SimpleNamespace(_native_actionable_sequence_store=store,
                            _native_agent_recipe_saver=lambda row: saved.append(row) or row)

    asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"name": "Sequence"},
    ))

    assert [step["type"] for step in saved[0]["steps"]] == [
        "sftp_read", "smb_write", "sftp_list", "discord_send", "webhook_send",
        "email_send", "mqtt_publish", "http_api_request", "imap_read", "imap_search",
        "calendar_read",
    ]
    assert saved[0]["steps"][0]["params"]["remote_path"] == "/a"
    assert saved[0]["steps"][3]["params"]["message"] == "hello"
    assert len(validate_stored_recipe_manifest(saved[0])["steps"]) == len(calls)


def test_recipe_remember_empty_is_honest_and_non_actionable_does_not_overwrite() -> None:
    store = LastActionableSequenceStore()
    store.append("alice", turn_id="turn-1", intent="list", tool_name="file_list",
                 arguments={"connection_kind": "sftp", "connection_ref": "files", "path": "/tmp"},
                 outcome="success")
    assert store.get("alice").intent == "list"
    owner = SimpleNamespace(_native_actionable_sequence_store=store,
                            _native_agent_recipe_saver=lambda row: row)
    assert "inactive draft" in asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {},
    )).content
    empty = asyncio.run(_binding(SimpleNamespace(
        _native_actionable_sequence_store=LastActionableSequenceStore(),
    )).handler(NativeToolContext(user_id="bob", auth_role="admin"), {}))
    assert empty.content == "There is no recent actionable sequence to remember as a Recipe."


def test_recipe_remember_contract_and_preview_are_confirmation_gated() -> None:
    store = LastActionableSequenceStore()
    store.append("alice", turn_id="turn-1", intent="read file", tool_name="file_read",
                 arguments={"connection_kind": "sftp", "connection_ref": "files", "path": "/a"},
                 outcome="success")
    binding = _binding(SimpleNamespace(_native_actionable_sequence_store=store))
    preview = asyncio.run(binding.confirmation_preview(
        NativeToolContext(user_id="alice", auth_role="admin"), {"name": "Read A"},
    ))
    assert binding.contract.effect == "mutating"
    assert binding.contract.confirmation_required is True
    assert binding.contract.relay_result_content is True
    assert "inactive" in preview.lower() and "files" in preview and "/a" in preview


def test_recipe_remember_uses_server_side_cross_host_multistep_copy() -> None:
    store = LastActionableSequenceStore()
    store.append("alice", turn_id="turn-1", intent="same on srv-b", tool_name="ssh_read",
                 arguments={"command": "uptime", "targets": ["srv-b"]}, outcome="success")
    suggestions = CrossHostRecipeSuggestionStore()
    suggestions.put("alice", CrossHostRecipeSuggestion(
        recipe_id="health-srv-a", recipe_name="Health", source_host="srv-a", new_host="srv-b",
        steps=(
            {"id": "s1", "type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "uptime"}},
            {"id": "s2", "type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "df -h"}},
        ), similarity=0.94,
    ))
    saved = []
    owner = SimpleNamespace(
        _native_actionable_sequence_store=store,
        _native_cross_host_recipe_suggestions=suggestions,
        _native_agent_recipe_saver=lambda row: saved.append(row) or row,
    )

    asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {},
    ))

    assert saved[0]["name"] == "Health (srv-b)"
    assert saved[0]["enabled_default"] is False
    assert [step["params"]["connection_ref"] for step in saved[0]["steps"]] == ["srv-b", "srv-b"]
    assert suggestions.get("alice") is None


def test_suggestion_confirmation_saves_frozen_inactive_recipe_without_running_steps(tmp_path) -> None:
    saved = []
    owner = SimpleNamespace(
        _native_actionable_sequence_store=LastActionableSequenceStore(),
        _native_agent_recipe_saver=lambda row: saved.append(row) or row,
    )
    binding = _binding(owner)
    pending = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    frozen = {
        "name": "Frozen host check",
        "_frozen_recipe": {
            "name": "Frozen host check", "description": "Frozen suggestion",
            "steps": [{"id": "s1", "type": "ssh_run", "params": {
                "connection_ref": "srv-b", "command": "uptime",
            }, "on_error": "stop"}],
        },
    }
    pending.put(user_id="alice", token="na123456789abc", tool_name="recipe_remember",
                frozen_arguments=frozen, preview="Save inactive", request_message="yes", now=1000)

    outcome = asyncio.run(run_native_agent_turn(
        message="confirm action na123456789abc", user_id="alice", turn_id="confirm-frozen",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        pending_store=pending, confirmation_ledger=ledger,
        confirmation_token="na123456789abc", now=1001,
    ))

    assert outcome.kind == "final_answer"
    assert len(saved) == 1 and saved[0]["enabled_default"] is False
    assert saved[0]["steps"] == frozen["_frozen_recipe"]["steps"]


def test_handler_records_actionable_result_but_not_later_plain_turn(tmp_path) -> None:
    store = LastActionableSequenceStore()

    async def handler(_context, _arguments):  # noqa: ANN001
        return NativeToolResult('{"status":"blocked"}', "ssh_command")

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="ssh_runtime", name="ssh_command", description="test",
        input_schema={"type": "object", "properties": {"command": {"type": "string"},
                      "targets": {"type": "array"}}, "required": ["command", "targets"]},
        effect="read_only", confirmation_required=False, source_authority="test",
        user_scoped=True, rollout_flag="test", order=1,
    ), handler=handler)
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            function = SimpleNamespace(name="ssh_command", arguments=json.dumps({
                "command": "apt upgrade -y", "targets": ["srv-a"],
            }))
            tool_call = SimpleNamespace(id="c1", function=function)
            message = SimpleNamespace(content="", tool_calls=[tool_call])
            return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="tool_use")])
        message = SimpleNamespace(content="Blocked honestly", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])

    asyncio.run(run_native_agent_turn(
        message="upgrade srv-a", user_id="alice", turn_id="t1", llm_config=LLMConfig(model="fake"),
        tool_bindings=(binding,), completion=completion, trace_root=tmp_path,
        actionable_sequence_store=store,
    ))
    recorded = store.get("alice")
    assert recorded is not None and recorded.calls[0].outcome == "blocked"
    assert recorded.calls[0].arguments["command"] == "apt upgrade -y"
