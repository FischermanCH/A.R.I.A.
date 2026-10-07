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
        id=f"call-{name}", function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeInfraRuntime:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.error = error

    def execute_sftp_write(self, ref: str, *, remote_path: str, content: str) -> str:
        self.calls.append(("sftp_write", (ref,), {"remote_path": remote_path, "content": content}))
        if self.error:
            raise self.error
        return f"Wrote {remote_path} via {ref}."

    def execute_smb_write(self, ref: str, *, remote_path: str, content: str) -> str:
        self.calls.append(("smb_write", (ref,), {"remote_path": remote_path, "content": content}))
        if self.error:
            raise self.error
        return f"Wrote {remote_path} via {ref}."

    def execute_http_api_request(
        self, ref: str, *, request_path: str, content: str, confirmed: bool,
    ) -> str:
        self.calls.append(("http_api_request", (ref,), {
            "request_path": request_path, "content": content, "confirmed": confirmed,
        }))
        if self.error:
            raise self.error
        return f"HTTP API request completed via {ref}."


def _owner(*, runtime: FakeInfraRuntime | None = None, loader=None) -> SimpleNamespace:  # noqa: ANN001
    return SimpleNamespace(
        settings=SimpleNamespace(connections=SimpleNamespace(
            sftp={"files": object()}, smb={"share": object()}, http_api={"service": object()},
        )),
        _skill_runtime=runtime or FakeInfraRuntime(),
        _native_agent_connection_send_loader=loader,
    )


def _binding(owner: SimpleNamespace, name: str):  # noqa: ANN001
    return next(item for item in native_tool_contributions(owner) if item.contract.name == name)


def test_file_write_waits_for_confirmation_and_executes_frozen_arguments_once(tmp_path) -> None:
    runtime = FakeInfraRuntime()
    binding = _binding(_owner(runtime=runtime), "file_write")
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call("file_write", {
                "connection_kind": "sftp", "connection_ref": "files",
                "path": "/upload/report.txt", "content": "ready",
            })], finish_reason="tool_use")
        if calls == 2:
            return _response(content="Write report.txt to files?")
        return _response(content="report.txt was written to files.")

    preview = asyncio.run(run_native_agent_turn(
        message="Write the report", user_id="alice", auth_role="admin", turn_id="preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))
    assert preview.kind == "pending_confirmation"
    assert runtime.calls == []
    pending = pending_store.peek(user_id="alice", token=preview.confirmation_token, now=1001)
    assert pending is not None
    assert pending.frozen_arguments == {
        "connection_kind": "sftp", "connection_ref": "files",
        "path": "/upload/report.txt", "content": "ready",
    }

    result = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", auth_role="admin", turn_id="confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1001,
    ))
    assert result.kind == "final_answer"
    assert runtime.calls == [(
        "sftp_write", ("files",), {"remote_path": "/upload/report.txt", "content": "ready"},
    )]


def test_http_api_request_passes_kernel_confirmation_to_runtime() -> None:
    runtime = FakeInfraRuntime()
    result = asyncio.run(_binding(_owner(runtime=runtime), "http_api_request").handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"connection_ref": "service", "request_path": "/deploy", "content": "{\"go\":true}"},
    ))

    assert json.loads(result.content)["status"] == "ok"
    assert runtime.calls == [(
        "http_api_request", ("service",),
        {"request_path": "/deploy", "content": '{"go":true}', "confirmed": True},
    )]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("file_write", {"connection_kind": "smb", "connection_ref": "missing", "path": "/x", "content": "x"}),
        ("http_api_request", {"connection_ref": "missing"}),
    ],
)
def test_unknown_ref_is_honest_and_never_writes(name: str, arguments: dict[str, str]) -> None:
    runtime = FakeInfraRuntime()
    payload = json.loads(asyncio.run(_binding(_owner(runtime=runtime), name).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), arguments,
    )).content)

    assert payload["status"] == "connection_not_found"
    assert runtime.calls == []


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("file_write", {"connection_kind": "sftp", "connection_ref": "files", "path": "/x", "content": "x"}),
        ("http_api_request", {"connection_ref": "service"}),
    ],
)
def test_runtime_failure_degrades_honestly_without_claiming_success(name: str, arguments: dict[str, str]) -> None:
    runtime = FakeInfraRuntime(error=FileNotFoundError("private runtime detail"))
    payload = json.loads(asyncio.run(_binding(_owner(runtime=runtime), name).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), arguments,
    )).content)

    assert payload["status"] in {"write_failed", "request_failed"}
    assert payload["error_class"] == "FileNotFoundError"
    assert "private runtime detail" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        ({"source_authority": "wrong", "scope_user_id": "alice", "content": "done"}, "authority_mismatch"),
        ({"source_authority": "sftp:configured_profile", "scope_user_id": "bob", "content": "done"}, "scope_mismatch"),
    ],
)
def test_injected_loader_keeps_authority_and_scope_guards(row, reason: str) -> None:  # noqa: ANN001
    async def loader(*_args):
        return row

    with pytest.raises(ValueError, match=f"native_agent_connection_send_{reason}"):
        asyncio.run(_binding(_owner(loader=loader), "file_write").handler(
            NativeToolContext(user_id="alice", auth_role="admin"),
            {"connection_kind": "sftp", "connection_ref": "files", "path": "/x", "content": "x"},
        ))


def test_registry_filter_flag_defaults_and_threshold_cover_infra_writes() -> None:
    owner = _owner()
    base_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_write_notes_enabled", "native_agent_write_memory_enabled", "native_agent_ssh_enabled",
        "native_agent_messaging_enabled",
    }
    without_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=base_flags,
    )
    with_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={*base_flags, "native_agent_infra_write_enabled"},
    )
    no_profiles = filter_tools_by_configured_connections(
        with_flag, SimpleNamespace(connections=SimpleNamespace(
            sftp={}, smb={}, http_api={}, rss={}, google_calendar={}, imap={}, ssh={},
            discord={}, webhook={}, email={}, mqtt={},
        )),
    )
    by_name = {item.contract.name: item.contract for item in with_flag}

    assert len(without_flag) == 32
    assert len(with_flag) == 34
    assert by_name["file_write"].effect == "mutating" and by_name["file_write"].confirmation_required
    assert by_name["http_api_request"].effect == "mutating" and by_name["http_api_request"].confirmation_required
    assert by_name["file_write"].required_connection_kinds == ("sftp", "smb")
    assert by_name["http_api_request"].required_connection_kinds == ("http_api",)
    assert not {"file_write", "http_api_request"} & {item.contract.name for item in no_profiles}
    assert asyncio.run(select_relevant_native_tools("write", with_flag, selector=None)) == with_flag

    config = AgenticLoopFeatureConfig()
    assert config.native_agent_infra_write_enabled is True
    assert native_agent_enabled(SimpleNamespace(agentic_loop=config)) is True
