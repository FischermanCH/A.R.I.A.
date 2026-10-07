from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig, MCPServerConfig
from aria.modules.native_agent.handler import NativeAgentAwaitingConfirmation, run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.pipeline_bridge import _mcp_unreachable_footer
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def test_job_correction_queue_is_owner_scoped_bounded_and_drained_once(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="job-1", user_id="alice", goal="build", status="detached")

    assert store.queue_correction("job-1", user_id="mallory", text="wrong") == "not_found"
    assert store.queue_correction("job-1", user_id="alice", text="x" * 1200) == "queued"
    assert store.drain_corrections("job-1", user_id="mallory") == ()
    corrections = store.drain_corrections("job-1", user_id="alice")
    assert len(corrections) == 1
    assert 0 < len(corrections[0]) <= 1000
    assert store.drain_corrections("job-1", user_id="alice") == ()


def test_terminal_job_refuses_correction(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="job-1", user_id="alice", goal="build", status="detached")
    store.set_terminal("job-1", status="done", result="ok")
    assert store.queue_correction("job-1", user_id="alice", text="change it") == "not_running"


def test_awaiting_confirmation_snapshot_round_trip_and_cancel(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="job-1", user_id="alice", goal="build", status="detached")
    state = {"pending_token": "tok", "pending_call_id": "call-1", "messages": []}
    assert store.set_awaiting_confirmation("job-1", state)
    record = store.get("job-1")
    assert record is not None and record.status == "awaiting_confirmation"
    assert record.resume_state == state
    assert store.request_cancel("job-1", user_id="alice") == "requested"
    assert store.get("job-1").status == "cancelled"  # type: ignore[union-attr]


def test_default_native_agent_budget_is_32() -> None:
    config = AgenticLoopFeatureConfig()
    assert config.native_agent_max_steps == 32
    assert config.native_agent_max_provider_calls == 32


def test_mcp_call_timeout_is_per_server_and_bounded() -> None:
    assert MCPServerConfig(url="http://example.invalid/sse").call_timeout_seconds == 30
    assert MCPServerConfig(url="http://example.invalid/sse", call_timeout_seconds=180).call_timeout_seconds == 180
    with pytest.raises(ValidationError):
        MCPServerConfig(url="http://example.invalid/sse", call_timeout_seconds=4)
    with pytest.raises(ValidationError):
        MCPServerConfig(url="http://example.invalid/sse", call_timeout_seconds=901)


def test_jobs_ui_contains_stage2_controls_and_scroll_compensation() -> None:
    panel = Path("aria/templates/agent_jobs.html").read_text(encoding="utf-8")
    chat = Path("aria/templates/chat.html").read_text(encoding="utf-8")
    base = Path("aria/templates/base.html").read_text(encoding="utf-8")
    assert "/correct" in panel and "agent-job-correction" in panel
    assert "awaiting_confirmation" in panel
    assert "scroll-compensation" in panel
    assert "data-agent-job-action=\"correct\"" in chat
    assert "global-agent-job-indicator" in base
    assert "window.location.reload" not in panel


def test_failed_mcp_call_overrides_stale_connected_status_for_footer() -> None:
    status = SimpleNamespace(
        server_name="blender", connected=True, tool_count=3, error="",
    )
    footer = _mcp_unreachable_footer(
        message="Zeige den Status vom Blender MCP Server.",
        language="de",
        statuses=(status,),
        failed_servers=frozenset({"blender"}),
    )
    assert "MCP-Server blender ist gerade nicht erreichbar" in footer


def _response(*, content: str = "", tool_calls: tuple[object, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason="tool_use" if tool_calls else "stop",
    )])


def _call(name: str, call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments="{}"),
    )


def _binding(name: str, *, confirmation: bool) -> NativeToolBinding:
    async def handler(_context: NativeToolContext, _arguments: object) -> NativeToolResult:
        return NativeToolResult(json.dumps({"status": "ok", "tool": name}), name)

    return NativeToolBinding(
        NativeToolContract(
            owner_module_id="mcp",
            name=name,
            description=name,
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="mutating" if confirmation else "read_only",
            confirmation_required=confirmation,
            source_authority="test",
            user_scoped=True,
            rollout_flag="native_agent_mcp_enabled",
            relay_result_content=True,
        ),
        handler,
    )


def test_correction_is_injected_after_tool_result_at_next_boundary(tmp_path: Path) -> None:
    requests: list[list[dict]] = []
    corrections = [[], ["change the color to blue"]]

    async def completion(**kwargs):  # noqa: ANN003
        requests.append(list(kwargs["messages"]))
        if len(requests) == 1:
            return _response(tool_calls=(_call("read_step", "call-1"),))
        return _response(content="done")

    async def drain() -> tuple[str, ...]:
        return tuple(corrections.pop(0)) if corrections else ()

    outcome = asyncio.run(run_native_agent_turn(
        message="build", user_id="alice", turn_id="correction",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_binding("read_step", confirmation=False),),
        completion=completion, trace_root=tmp_path, correction_drain=drain,
    ))
    assert outcome.message == "done"
    second = requests[1]
    tool_index = next(index for index, row in enumerate(second) if row.get("role") == "tool")
    correction_index = next(
        index for index, row in enumerate(second)
        if row.get("role") == "user" and "CORRECTION FROM THE USER" in str(row.get("content"))
    )
    assert correction_index > tool_index


def test_detached_confirmation_raises_snapshot_with_deferred_calls(tmp_path: Path) -> None:
    pending = NativePendingStore(tmp_path / "pending.sqlite3")

    async def completion(**kwargs):  # noqa: ANN003
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=(
                _call("mutate_step", "call-1"),
                _call("read_step", "call-2"),
            ))
        return _response(content="Run the mutation?")

    async def detached() -> bool:
        return True

    async def scenario() -> dict:
        try:
            await run_native_agent_turn(
                message="build", user_id="alice", turn_id="await",
                llm_config=LLMConfig(model="fake"),
                tool_bindings=(
                    _binding("mutate_step", confirmation=True),
                    _binding("read_step", confirmation=False),
                ),
                completion=completion, trace_root=tmp_path,
                pending_store=pending, detached_check=detached,
            )
        except NativeAgentAwaitingConfirmation as exc:
            return exc.snapshot
        raise AssertionError("confirmation boundary was not raised")

    snapshot = asyncio.run(scenario())
    assert snapshot["pending_call_id"] == "call-1"
    assert snapshot["pending_tool_name"] == "mutate_step"
    assert snapshot["pending_deferred_calls"] == [
        {"call_id": "call-2", "tool_name": "read_step"},
    ]
    assert pending.peek(user_id="alice", token=snapshot["pending_token"]) is not None


def test_job_confirmation_reuses_confirmation_turn_then_resumes_with_paired_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(
        agentic_loop=SimpleNamespace(async_agent_job_sync_budget_seconds=0.01),
    )
    pipeline._project_root = tmp_path
    pipeline._routing_debug_enabled = lambda: False
    pipeline._finalize_process_result = lambda result, **_kwargs: result
    pipeline._agent_job_tasks = set()
    pipeline._agent_job_store = None
    pipeline._agent_job_store_path = None
    pipeline._agent_job_notifier = None
    store = pipeline.get_agent_job_store()
    store.create(job_id="job-confirm", user_id="alice", goal="build", status="detached")
    store.set_awaiting_confirmation("job-confirm", {
        "messages": [{
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call-1", "type": "function", "function": {"name": "mutate", "arguments": "{}"}},
                {"id": "call-2", "type": "function", "function": {"name": "read", "arguments": "{}"}},
            ],
        }],
        "step_index": 1,
        "provider_calls": 1,
        "pending_token": "na-token",
        "pending_call_id": "call-1",
        "pending_tool_name": "mutate",
        "pending_preview": "preview",
        "pending_deferred_calls": [{"call_id": "call-2", "tool_name": "read"}],
        "original_message": "build",
        "language": "en",
        "auth_role": "admin",
        "turn_id": "turn-confirm",
    })
    confirmation_calls: list[str] = []
    resumed_states: list[dict] = []

    async def fake_first_stage(_owner, **kwargs):  # noqa: ANN001, ANN003
        token = str(kwargs.get("confirmation_token") or "")
        if token:
            confirmation_calls.append(token)
            return PipelineResult(
                request_id="confirm", text='{"status":"ok"}', usage={}, intents=["mutate"],
                skill_errors=[], router_level=2, duration_ms=1, detail_lines=[],
            )
        resumed_states.append(dict(kwargs.get("resume_state") or {}))
        return PipelineResult(
            request_id="resume", text="finished", usage={}, intents=["chat"],
            skill_errors=[], router_level=2, duration_ms=1, detail_lines=[],
        )

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_first_stage)

    async def scenario() -> None:
        assert await pipeline.resolve_agent_job_confirmation("alice", "job-confirm", approve=True) == "started"
        for _index in range(20):
            tasks = list(pipeline._agent_job_tasks)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if not pipeline._agent_job_tasks:
                break
            await asyncio.sleep(0)

    asyncio.run(scenario())
    assert confirmation_calls == ["na-token"]
    assert resumed_states
    tool_rows = [row for row in resumed_states[0]["messages"] if row.get("role") == "tool"]
    assert [row["tool_call_id"] for row in tool_rows] == ["call-1", "call-2"]
    assert json.loads(tool_rows[1]["content"]) == {
        "status": "not_executed", "reason": "deferred_by_confirmation",
    }
    assert store.get("job-confirm").status == "done"  # type: ignore[union-attr]
