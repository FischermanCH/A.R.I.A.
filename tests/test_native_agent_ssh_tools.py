from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

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
from aria.modules.recipe_runtime.contracts import recipe_ssh_error
from aria.modules.sdk import NativeToolContext
from aria.modules.skill_contracts.contracts import SkillResult
from aria.modules.ssh_runtime.native_tools import MAX_SSH_TARGETS, native_tool_contributions


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


class FakeSSHRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.results: dict[str, SkillResult] = {}

    async def execute_custom_ssh_command(self, **kwargs) -> SkillResult:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        target = str(kwargs["connection_ref"])
        return self.results.get(target, SkillResult(
            skill_name="recipe_direct-ssh-command", content=f"output:{target}", success=True,
        ))


def _owner(runtime: FakeSSHRuntime | None = None, *, targets=("srv-a", "srv-b")) -> SimpleNamespace:
    ssh = {target: SimpleNamespace() for target in targets}
    return SimpleNamespace(
        settings=SimpleNamespace(connections=SimpleNamespace(ssh=ssh)),
        _ssh_runtime=runtime or FakeSSHRuntime(),
    )


def _binding(owner: SimpleNamespace, name: str):  # noqa: ANN001
    return next(item for item in native_tool_contributions(owner) if item.contract.name == name)


def test_ssh_read_readonly_runs_for_each_exact_target_with_bounded_output() -> None:
    runtime = FakeSSHRuntime()
    runtime.results["srv-a"] = SkillResult(
        skill_name="ssh", content="a" * 3_000, success=True,
    )
    result = asyncio.run(_binding(_owner(runtime), "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "uptime", "targets": ["srv-a", "srv-b"], "timeout": 30},
    ))
    payload = json.loads(result.content)

    assert payload["command"] == "uptime"
    assert [row["target"] for row in payload["results"]] == ["srv-a", "srv-b"]
    assert all(row["status"] == "ok" for row in payload["results"])
    assert len(payload["results"][0]["output"]) <= 2_000
    assert all(call["policy_confirmed"] is False for call in runtime.calls)
    assert all(call["command_template"] == "uptime" for call in runtime.calls)


def test_ssh_read_mutating_policy_result_requires_ssh_command_without_execution_success() -> None:
    runtime = FakeSSHRuntime()
    runtime.results["srv-a"] = SkillResult(
        skill_name="ssh", content="", success=False,
        error=recipe_ssh_error("policy_confirmation_required", "ssh_command_mutating_operation"),
    )
    result = asyncio.run(_binding(_owner(runtime), "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "apt upgrade -y", "targets": ["srv-a"]},
    ))

    assert json.loads(result.content)["results"] == [{
        "target": "srv-a", "status": "requires_ssh_command",
        "output": "This command requires the confirmed ssh_command tool.",
    }]
    assert runtime.calls[0]["policy_confirmed"] is False


def test_ssh_tools_reject_non_admin_before_runtime() -> None:
    for name in ("ssh_read", "ssh_command"):
        runtime = FakeSSHRuntime()
        result = asyncio.run(_binding(_owner(runtime), name).handler(
            NativeToolContext(user_id="alice", auth_role="user"),
            {"command": "uptime", "targets": ["srv-a"]},
        ))
        assert json.loads(result.content)["status"] == "forbidden_admin_only"
        assert runtime.calls == []


def test_ssh_tool_descriptions_reserve_ssh_for_literal_one_off_commands() -> None:
    descriptions = {
        name: _binding(_owner(), name).contract.description
        for name in ("ssh_read", "ssh_command")
    }

    assert "one-off ad-hoc commands" in descriptions["ssh_read"]
    assert "one-off ad-hoc commands" in descriptions["ssh_command"]
    assert "stored Recipe" in descriptions["ssh_read"]
    assert "stored Recipe" in descriptions["ssh_command"]
    assert "recipes_execute" in descriptions["ssh_read"]
    assert "recipes_execute" in descriptions["ssh_command"]


def test_ssh_command_preview_freezes_exact_command_and_all_targets_without_execution(tmp_path) -> None:
    runtime = FakeSSHRuntime()
    binding = _binding(_owner(runtime), "ssh_command")
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call("ssh_command", {
                "command": "apt upgrade -y", "targets": ["srv-a", "srv-b"], "timeout": 45,
            })], finish_reason="tool_use")
        return _response(content="Confirm apt upgrade -y on srv-a and srv-b.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Upgrade both", user_id="alice", auth_role="admin", turn_id="ssh-preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))
    pending = pending_store.peek(user_id="alice", token=outcome.confirmation_token, now=1001)

    assert outcome.kind == "pending_confirmation"
    assert outcome.message == "Confirm apt upgrade -y on srv-a and srv-b."
    assert runtime.calls == []
    assert pending is not None
    assert pending.frozen_arguments == {
        "command": "apt upgrade -y", "targets": ["srv-a", "srv-b"], "timeout": 45,
    }


def test_ssh_command_confirm_rechecks_admin_and_uses_policy_confirmation(tmp_path) -> None:
    runtime = FakeSSHRuntime()
    binding = _binding(_owner(runtime), "ssh_command")
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    step = 0

    async def completion(**_kwargs):
        nonlocal step
        step += 1
        if step == 1:
            return _response(tool_calls=[_tool_call("ssh_command", {
                "command": "systemctl restart app", "targets": ["srv-a", "srv-b"],
            })], finish_reason="tool_use")
        return _response(content="Please confirm the restart." if step == 2 else "Restart completed.")

    preview = asyncio.run(run_native_agent_turn(
        message="Restart", user_id="alice", auth_role="admin", turn_id="preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))
    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", auth_role="admin", turn_id="confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1001,
    ))

    assert confirmed.kind == "final_answer"
    assert [call["connection_ref"] for call in runtime.calls] == ["srv-a", "srv-b"]
    assert all(call["policy_confirmed"] is True for call in runtime.calls)


def test_ssh_command_confirmation_does_not_override_hard_block() -> None:
    runtime = FakeSSHRuntime()
    runtime.results["srv-a"] = SkillResult(
        skill_name="ssh", content="", success=False, error=recipe_ssh_error("not_allowed"),
    )
    result = asyncio.run(_binding(_owner(runtime), "ssh_command").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "blocked command", "targets": ["srv-a"]},
    ))

    assert json.loads(result.content)["results"][0]["status"] == "blocked"
    assert runtime.calls[0]["policy_confirmed"] is True


def test_ssh_command_confirm_as_non_admin_executes_nothing(tmp_path) -> None:
    runtime = FakeSSHRuntime()
    binding = _binding(_owner(runtime), "ssh_command")
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    pending_store.put(
        user_id="alice", token="natoken", tool_name="ssh_command",
        frozen_arguments={"command": "uptime", "targets": ["srv-a"]},
        preview="preview", now=1000,
    )

    async def completion(**_kwargs):
        return _response(content="Administrator access is required.")

    outcome = asyncio.run(run_native_agent_turn(
        message="confirm action natoken", user_id="alice", auth_role="user", turn_id="confirm-user",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token="natoken", now=1001,
    ))

    assert outcome.kind == "final_answer"
    assert runtime.calls == []


def test_multi_target_cap_returns_invalid_arguments_without_runtime() -> None:
    runtime = FakeSSHRuntime()
    result = asyncio.run(_binding(_owner(runtime), "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "uptime", "targets": [f"srv-{index}" for index in range(MAX_SSH_TARGETS + 1)]},
    ))

    assert json.loads(result.content)["status"] == "invalid_arguments"
    assert runtime.calls == []


def test_unknown_target_is_per_target_error_and_valid_target_still_runs() -> None:
    runtime = FakeSSHRuntime()
    result = asyncio.run(_binding(_owner(runtime, targets=("srv-a",)), "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "uptime", "targets": ["missing", "srv-a"]},
    ))
    rows = json.loads(result.content)["results"]

    assert rows[0] == {"target": "missing", "status": "unknown_target", "output": ""}
    assert rows[1]["status"] == "ok"
    assert [call["connection_ref"] for call in runtime.calls] == ["srv-a"]


def test_ssh_tool_resolves_display_name_to_canonical_ref_for_execution_and_recurrence() -> None:
    runtime = FakeSSHRuntime()
    owner = _owner(runtime, targets=())
    owner.settings.connections.ssh = {
        "srv-a": SimpleNamespace(title="Primary App", host="10.0.0.10"),
    }

    result = asyncio.run(_binding(owner, "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "uptime", "targets": [" primary app "]},
    ))

    assert runtime.calls[0]["connection_ref"] == "srv-a"
    assert json.loads(result.content)["results"][0]["target"] == "srv-a"
    assert result.actionable_arguments == {"command": "uptime", "targets": ["srv-a"]}
    assert result.actionable_outcome == "success"


def test_ssh_tool_does_not_execute_ambiguous_name_and_marks_observation_skipped() -> None:
    runtime = FakeSSHRuntime()
    owner = _owner(runtime, targets=())
    owner.settings.connections.ssh = {
        "srv-a": SimpleNamespace(title="Shared", host="10.0.0.10"),
        "srv-b": SimpleNamespace(title="shared", host="10.0.0.11"),
    }

    result = asyncio.run(_binding(owner, "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "uptime", "targets": ["shared"]},
    ))

    assert runtime.calls == []
    assert json.loads(result.content)["results"] == [{
        "target": "shared", "status": "unknown_target", "output": "",
    }]
    assert result.actionable_arguments is None
    assert result.actionable_outcome == "skip"


def test_ssh_tool_skips_transport_failure_but_keeps_policy_block_for_recurrence() -> None:
    runtime = FakeSSHRuntime()
    runtime.results["srv-a"] = SkillResult(
        skill_name="ssh", content="", success=False, error=recipe_ssh_error("exec_error", "offline"),
    )
    failed = asyncio.run(_binding(_owner(runtime, targets=("srv-a",)), "ssh_read").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "uptime", "targets": ["srv-a"]},
    ))
    assert failed.actionable_outcome == "skip"

    runtime.results["srv-a"] = SkillResult(
        skill_name="ssh", content="", success=False, error=recipe_ssh_error("guardrail_denied", "default"),
    )
    blocked = asyncio.run(_binding(_owner(runtime, targets=("srv-a",)), "ssh_command").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"command": "apt upgrade -y", "targets": ["srv-a"]},
    ))
    assert blocked.actionable_arguments == {"command": "apt upgrade -y", "targets": ["srv-a"]}
    assert blocked.actionable_outcome == "blocked"


def test_registry_and_rollout_defaults_gate_ssh_tools_on_flag_and_profile() -> None:
    owner = _owner()
    base_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
    }
    without_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=base_flags,
    )
    with_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags={*base_flags, "native_agent_ssh_enabled"},
    )
    without_profile = filter_tools_by_configured_connections(
        with_flag, SimpleNamespace(connections=SimpleNamespace(ssh={})),
    )
    names = {item.contract.name: item.contract for item in with_flag}

    assert "ssh_read" not in {item.contract.name for item in without_flag}
    assert len(with_flag) == 28
    assert names["ssh_read"].effect == "read_only" and not names["ssh_read"].confirmation_required
    assert names["ssh_command"].effect == "mutating" and names["ssh_command"].confirmation_required
    assert names["ssh_read"].required_connection_kinds == ("ssh",)
    assert not {"ssh_read", "ssh_command"} & {item.contract.name for item in without_profile}
    assert asyncio.run(select_relevant_native_tools("ssh", with_flag, selector=None)) == with_flag
    config = AgenticLoopFeatureConfig()
    assert config.native_agent_ssh_enabled is True
    assert native_agent_enabled(SimpleNamespace(agentic_loop=config)) is True


def test_native_ssh_tools_do_not_use_legacy_resolution_or_dossier() -> None:
    source = (Path(__file__).resolve().parents[1] / "aria/modules/ssh_runtime/native_tools.py").read_text(
        encoding="utf-8",
    )

    assert "ssh_resolution" not in source
    assert "dossier" not in source
