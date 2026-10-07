from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.pipeline_bridge import native_agent_enabled
from aria.modules.native_agent.tool_registry import (
    assemble_native_tools,
    filter_tools_by_configured_connections,
    select_relevant_native_tools,
)
from aria.modules.recipe_runtime.native_tools import native_tool_contributions
from aria.modules.sdk import NativeToolContext


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _tool_call(name: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{name}",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeMessagingRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute_discord_send(self, ref: str, content: str) -> str:
        self.calls.append(("discord_send", (ref, content)))
        return f"Discord message sent via {ref}."

    def execute_webhook_send(self, ref: str, content: str) -> str:
        self.calls.append(("webhook_send", (ref, content)))
        return f"Webhook message sent via {ref}."

    def execute_email_send(self, ref: str, content: str) -> str:
        self.calls.append(("email_send", (ref, content)))
        return f"Email sent via {ref}."

    def execute_mqtt_publish(self, ref: str, topic: str, content: str) -> str:
        self.calls.append(("mqtt_publish", (ref, topic, content)))
        return f"MQTT message published via {ref} to {topic}."


def _owner(*, runtime: FakeMessagingRuntime | None = None, loader=None) -> SimpleNamespace:  # noqa: ANN001
    return SimpleNamespace(
        settings=SimpleNamespace(connections=SimpleNamespace(
            discord={"alerts": object()}, webhook={"deploy": object()},
            email={"ops": object()}, mqtt={"broker": object()},
        )),
        _skill_runtime=runtime or FakeMessagingRuntime(),
        _native_agent_connection_send_loader=loader,
    )


def _binding(owner: SimpleNamespace, name: str):  # noqa: ANN001
    return next(item for item in native_tool_contributions(owner) if item.contract.name == name)


def test_discord_send_is_confirmation_gated_and_executes_frozen_payload_once(tmp_path) -> None:
    runtime = FakeMessagingRuntime()
    binding = _binding(_owner(runtime=runtime), "discord_send")
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call("discord_send", {
                "connection_ref": "alerts", "content": "Maintenance starts now.",
            })], finish_reason="tool_use")
        if calls == 2:
            return _response(content="Send the maintenance message to alerts?")
        return _response(content="The maintenance message was sent to alerts.")

    preview = asyncio.run(run_native_agent_turn(
        message="Send the maintenance notice", user_id="alice", auth_role="admin", turn_id="preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))

    assert preview.kind == "pending_confirmation"
    assert runtime.calls == []
    pending = pending_store.peek(user_id="alice", token=preview.confirmation_token, now=1001)
    assert pending is not None
    assert pending.frozen_arguments == {
        "connection_ref": "alerts", "content": "Maintenance starts now.",
    }

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", auth_role="admin", turn_id="confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1001,
    ))
    assert confirmed.kind == "final_answer"
    assert runtime.calls == [("discord_send", ("alerts", "Maintenance starts now."))]


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("webhook_send", {"connection_ref": "deploy", "content": "done"},
         ("webhook_send", ("deploy", "done"))),
        ("mqtt_publish", {"connection_ref": "broker", "topic": "aria/status", "content": "ready"},
         ("mqtt_publish", ("broker", "aria/status", "ready"))),
    ],
)
def test_messaging_handlers_use_exact_runtime_primitive(name: str, arguments: dict[str, str], expected) -> None:  # noqa: ANN001
    runtime = FakeMessagingRuntime()
    result = asyncio.run(_binding(_owner(runtime=runtime), name).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), arguments,
    ))

    assert json.loads(result.content)["status"] == "ok"
    assert runtime.calls == [expected]


def test_unknown_connection_ref_is_honest_and_never_sends() -> None:
    runtime = FakeMessagingRuntime()
    result = asyncio.run(_binding(_owner(runtime=runtime), "email_send").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"connection_ref": "missing", "content": "hello"},
    ))
    payload = json.loads(result.content)

    assert payload["status"] == "connection_not_found"
    assert payload["connection_ref"] == "missing"
    assert runtime.calls == []


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        ({"source_authority": "wrong", "scope_user_id": "alice", "content": "sent"}, "authority_mismatch"),
        ({"source_authority": "discord:configured_profile", "scope_user_id": "bob", "content": "sent"}, "scope_mismatch"),
        ("not-a-row", "result_invalid"),
    ],
)
def test_injected_send_loader_remains_authority_and_scope_bound(row, reason: str) -> None:  # noqa: ANN001
    async def loader(*_args):
        return row

    with pytest.raises(ValueError, match=f"native_agent_connection_send_{reason}"):
        asyncio.run(_binding(_owner(loader=loader), "discord_send").handler(
            NativeToolContext(user_id="alice", auth_role="admin"),
            {"connection_ref": "alerts", "content": "hello"},
        ))


def test_registry_filter_flag_defaults_and_threshold_cover_four_messaging_tools() -> None:
    owner = _owner()
    base_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_write_notes_enabled", "native_agent_write_memory_enabled", "native_agent_ssh_enabled",
    }
    without_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=base_flags,
    )
    with_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={*base_flags, "native_agent_messaging_enabled"},
    )
    partly_configured = filter_tools_by_configured_connections(
        with_flag,
        SimpleNamespace(connections=SimpleNamespace(
            discord={"alerts": object()}, webhook={"deploy": object()}, email={}, mqtt={},
            rss={}, google_calendar={}, sftp={}, smb={}, imap={}, ssh={"server": object()},
        )),
    )
    messaging = {name: contract for name, contract in (
        (item.contract.name, item.contract) for item in with_flag
    ) if name in {"discord_send", "webhook_send", "email_send", "mqtt_publish"}}

    assert len(without_flag) == 28
    assert len(with_flag) == 32
    assert set(messaging) == {"discord_send", "webhook_send", "email_send", "mqtt_publish"}
    assert all(item.effect == "mutating" and item.confirmation_required for item in messaging.values())
    assert messaging["discord_send"].required_connection_kinds == ("discord",)
    assert messaging["webhook_send"].required_connection_kinds == ("webhook",)
    assert messaging["email_send"].required_connection_kinds == ("email",)
    assert messaging["mqtt_publish"].required_connection_kinds == ("mqtt",)
    filtered_names = {item.contract.name for item in partly_configured}
    assert {"discord_send", "webhook_send"} <= filtered_names
    assert not {"email_send", "mqtt_publish"} & filtered_names
    assert asyncio.run(select_relevant_native_tools("send", with_flag, selector=None)) == with_flag

    config = AgenticLoopFeatureConfig()
    assert config.native_agent_messaging_enabled is True
    assert native_agent_enabled(SimpleNamespace(agentic_loop=config)) is True
