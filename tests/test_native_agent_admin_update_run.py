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
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.release_update import native_tools as release_native_tools
from aria.modules.sdk import NativeToolContext


READ_FLAG = "native_agent_admin_enabled"
WRITE_FLAG = "native_agent_admin_write_enabled"


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _tool_call(arguments: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(
        id="call-admin-update-run",
        function=SimpleNamespace(name="admin_update_run", arguments=arguments),
    )


def _owner(**values) -> SimpleNamespace:  # noqa: ANN003
    return SimpleNamespace(settings=SimpleNamespace(), memory_skill=object(), **values)


def _binding(owner: SimpleNamespace):  # noqa: ANN202
    return next(
        item for item in release_native_tools.native_tool_contributions(owner)
        if item.contract.name == "admin_update_run"
    )


def test_admin_update_run_waits_for_confirmation_then_returns_honest_status(tmp_path) -> None:
    calls: list[str] = []

    async def trigger():
        calls.append("trigger")
        return {"status": "accepted", "requested": True, "secret": "omit-me"}

    owner = _owner(_native_agent_update_run_trigger=trigger)
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    responses = iter((
        _response(tool_calls=[_tool_call()], finish_reason="tool_use"),
        _response(content="Run the configured ARIA update now?"),
        _response(content="The update helper accepted the update request."),
    ))

    async def completion(**_kwargs):
        return next(responses)

    preview = asyncio.run(run_native_agent_turn(
        message="Run the ARIA update", user_id="alice", auth_role="admin",
        turn_id="update-preview", llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(owner),), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))
    assert preview.kind == "pending_confirmation"
    assert calls == []

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", auth_role="admin",
        turn_id="update-confirm", llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(owner),), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1001,
    ))
    assert confirmed.kind == "final_answer"
    assert calls == ["trigger"]


@pytest.mark.parametrize("auth_role", ("", "user"))
def test_admin_update_run_forbids_non_admin_before_resolution(auth_role: str) -> None:
    calls: list[str] = []
    owner = _owner(_native_agent_update_run_trigger=lambda: calls.append("trigger"))
    payload = json.loads(asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role=auth_role), {},
    )).content)
    assert payload == {
        "effect": "mutating", "message": "Administrator access is required.",
        "status": "forbidden_admin_only",
    }
    assert calls == []


def test_admin_update_run_rejects_all_model_arguments() -> None:
    with pytest.raises(ValueError, match="native_agent_admin_update_run_arguments_invalid"):
        asyncio.run(_binding(_owner()).handler(
            NativeToolContext(user_id="alice", auth_role="admin"), {"force": True},
        ))


def test_admin_update_run_direct_path_uses_secure_store_and_existing_helper(monkeypatch) -> None:
    secure_store = object()
    config = SimpleNamespace(enabled=True)
    seen: list[tuple[str, object]] = []
    owner = _owner(_native_agent_secure_store_getter=lambda _raw=None: secure_store)

    def resolve(*, secure_store=None):  # noqa: ANN001
        seen.append(("resolve", secure_store))
        return config

    def trigger(received):  # noqa: ANN001
        seen.append(("trigger", received))
        return {"status": "requested", "requested": True, "token": "omit-me"}

    monkeypatch.setattr(release_native_tools, "resolve_update_helper_config", resolve)
    monkeypatch.setattr(release_native_tools, "trigger_update_helper_run", trigger)
    payload = json.loads(asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {},
    )).content)
    assert payload == {
        "effect": "mutating", "status": "requested", "requested": True,
    }
    assert seen == [("resolve", secure_store), ("trigger", config)]


def test_admin_update_run_disabled_is_honest_without_trigger(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        release_native_tools, "resolve_update_helper_config",
        lambda **_kwargs: SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(release_native_tools, "trigger_update_helper_run", lambda _config: calls.append("trigger"))
    payload = json.loads(asyncio.run(_binding(_owner()).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {},
    )).content)
    assert payload["status"] == "update_helper_disabled"
    assert calls == []


@pytest.mark.parametrize(
    ("error", "status"),
    ((RuntimeError("update already running"), "already_running"),
     (ValueError("bad helper URL token=secret"), "update_trigger_failed")),
)
def test_admin_update_run_degrades_trigger_errors_honestly(error: Exception, status: str) -> None:
    def trigger():
        raise error

    payload = json.loads(asyncio.run(_binding(_owner(
        _native_agent_update_run_trigger=trigger,
    )).handler(NativeToolContext(user_id="alice", auth_role="admin"), {})).content)
    assert payload["status"] == status
    assert payload["error_class"] == type(error).__name__
    assert "secret" not in json.dumps(payload).lower()


def test_admin_update_run_flag_is_independent_and_registry_has_37_tools() -> None:
    owner = _owner()
    base_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", READ_FLAG,
        "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
        "native_agent_ssh_enabled", "native_agent_messaging_enabled",
        "native_agent_infra_write_enabled", "native_agent_recipe_execute_enabled",
        "native_agent_recipe_learn_enabled",
        "native_agent_memory_learn_enabled",
    }
    read_only = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=base_flags,
    )
    all_tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags={*base_flags, WRITE_FLAG},
    )
    read_names = {item.contract.name for item in read_only}
    by_name = {item.contract.name: item.contract for item in all_tools}

    assert "admin_update_status" in read_names
    assert "admin_update_run" not in read_names
    assert len(all_tools) == 37
    assert by_name["admin_update_run"].effect == "mutating"
    assert by_name["admin_update_run"].confirmation_required is True
    assert by_name["admin_update_run"].user_scoped is False
    assert by_name["admin_update_run"].rollout_flag == WRITE_FLAG
    assert asyncio.run(select_relevant_native_tools("run update", all_tools, selector=None)) == all_tools
    rollout_defaults = AgenticLoopFeatureConfig().model_dump()
    assert rollout_defaults.pop("native_web_debug_details") is False
    assert rollout_defaults.pop("native_agent_mcp_enabled") is False
    assert rollout_defaults.pop("native_tool_selector_top_k") == 16
    assert rollout_defaults.pop("native_agent_max_steps") == 32
    assert rollout_defaults.pop("native_agent_max_provider_calls") == 32
    assert rollout_defaults.pop("native_agent_mcp_vision_max_live_images") == 4
    assert rollout_defaults.pop("native_agent_mcp_vision_max_lifetime_images") == 24
    assert rollout_defaults.pop("async_agent_job_sync_budget_seconds") == 25.0
    assert rollout_defaults.pop("native_agent_budget_extension_steps") == 32
    assert rollout_defaults.pop("native_agent_budget_max_total") == 160
    assert rollout_defaults.pop("agent_job_retention_days") == 14
    assert rollout_defaults.pop("agent_job_stale_paused_days") == 7
    assert all(value is True for value in rollout_defaults.values())
