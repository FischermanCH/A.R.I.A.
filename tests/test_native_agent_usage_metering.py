from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import LLMConfig, Settings
from aria.modules.model_usage_observability.usage_meter import UsageMeter
from aria.modules.native_agent.handler import NativeAgentOutcome, run_native_agent_turn
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _response(*, content: str = "", tool_calls=(), usage=None, finish_reason: str = "stop"):  # noqa: ANN001
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
            finish_reason=finish_reason,
        )],
        usage=usage,
    )


def _usage(prompt: int, completion: int, total: int) -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)


def _tool_call(name: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{name}",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _binding(*, mutating: bool = False, executed: list[dict[str, object]] | None = None) -> NativeToolBinding:
    name = "write_test" if mutating else "read_test"

    async def handler(context: NativeToolContext, arguments):  # noqa: ANN001
        if executed is not None:
            executed.append({"user_id": context.user_id, **dict(arguments)})
        return NativeToolResult(json.dumps({"status": "ok", "value": arguments.get("value", "done")}), name)

    return NativeToolBinding(NativeToolContract(
        owner_module_id="test", name=name, description="Test tool.",
        input_schema={
            "type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"],
        },
        effect="mutating" if mutating else "read_only",
        confirmation_required=mutating, source_authority="test:store", user_scoped=True,
        rollout_flag="test_enabled",
    ), handler)


class FakeUsageMeter:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self.fail = fail

    async def record_llm_call(self, **kwargs):  # noqa: ANN003
        self.calls.append(dict(kwargs))
        if self.fail:
            raise RuntimeError("meter unavailable")
        return 0.01


class FakeFlushMeter(FakeUsageMeter):
    def __init__(
        self, *, flush_error: bool = False, snapshot_error: bool = False,
        snapshot_usage: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self.flush_error = flush_error
        self.snapshot_error = snapshot_error
        self.snapshot_usage = snapshot_usage
        self.flush_calls: list[dict[str, object]] = []

    def snapshot_scope(self, _scope):  # noqa: ANN001
        if self.snapshot_error:
            raise RuntimeError("snapshot unavailable")
        if self.snapshot_usage is None:
            return None
        return {"usage": dict(self.snapshot_usage)}

    async def flush_current_scope(self, **kwargs):  # noqa: ANN003
        self.flush_calls.append(dict(kwargs))
        if self.flush_error:
            raise RuntimeError("flush unavailable")
        return True


def _meter_settings(tmp_path: Path) -> Settings:
    return Settings.model_validate({
        "llm": {"model": "fake"},
        "token_tracking": {"enabled": True, "log_file": str(tmp_path / "tokens.jsonl")},
        "pricing": {"enabled": False, "chat_models": {}, "embedding_models": {}},
    })


def _token_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_native_agent_meters_main_loop_with_exact_response_usage(tmp_path) -> None:
    meter = FakeUsageMeter()

    async def completion(**_kwargs):
        return _response(content="Direct answer", usage=_usage(11, 7, 18))

    outcome = asyncio.run(run_native_agent_turn(
        message="Hello", user_id="alice", turn_id="turn-loop", llm_config=LLMConfig(model="fake-model"),
        tool_bindings=(_binding(),), completion=completion, usage_meter=meter, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer" and outcome.message == "Direct answer"
    assert len(meter.calls) == 1
    assert meter.calls[0] == {
        "model": "fake-model",
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        "source": "native_agent", "operation": "loop", "user_id": "alice",
        "request_id": "turn-loop", "duration_ms": meter.calls[0]["duration_ms"],
    }
    assert isinstance(meter.calls[0]["duration_ms"], int) and meter.calls[0]["duration_ms"] >= 0


def test_native_agent_meters_budget_finalizer(tmp_path) -> None:
    meter = FakeUsageMeter()
    calls = 0

    async def completion(**kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if "tool_choice" not in kwargs:
            return _response(content="Best effort", usage=_usage(30, 5, 35))
        return _response(
            tool_calls=[_tool_call("read_test", {"value": "observed"})],
            usage=_usage(10 + calls, 2, 12 + calls), finish_reason="tool_use",
        )

    outcome = asyncio.run(run_native_agent_turn(
        message="Read repeatedly", user_id="alice", turn_id="turn-finalizer",
        llm_config=LLMConfig(model="fake-model"), tool_bindings=(_binding(),),
        completion=completion, usage_meter=meter, trace_root=tmp_path,
        max_steps=3, max_provider_calls=3,
    ))

    assert outcome.kind == "final_answer" and outcome.reason == "native_agent_budget_best_effort"
    assert [call["operation"] for call in meter.calls] == ["loop", "loop", "finalizer"]
    assert meter.calls[-1]["usage"] == {"prompt_tokens": 30, "completion_tokens": 5, "total_tokens": 35}


def test_native_agent_meters_preview_and_result_without_changing_confirmation(tmp_path) -> None:
    meter = FakeUsageMeter()
    executed: list[dict[str, object]] = []
    binding = _binding(mutating=True, executed=executed)
    store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    preview_calls = 0

    async def preview_completion(**_kwargs):
        nonlocal preview_calls
        preview_calls += 1
        if preview_calls == 1:
            return _response(
                tool_calls=[_tool_call("write_test", {"value": "frozen"})],
                usage=_usage(20, 4, 24), finish_reason="tool_use",
            )
        return _response(content="Please confirm.", usage=_usage(8, 3, 11))

    preview = asyncio.run(run_native_agent_turn(
        message="Write frozen", user_id="alice", turn_id="turn-preview",
        llm_config=LLMConfig(model="fake-model"), tool_bindings=(binding,),
        completion=preview_completion, usage_meter=meter, pending_store=store,
        confirmation_ledger=ledger, trace_root=tmp_path, now=1000,
    ))

    async def result_completion(**_kwargs):
        return _response(content="Written.", usage=_usage(9, 2, 11))

    result = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", turn_id="turn-result",
        llm_config=LLMConfig(model="fake-model"), tool_bindings=(binding,),
        completion=result_completion, usage_meter=meter, pending_store=store,
        confirmation_ledger=ledger, confirmation_token=preview.confirmation_token, now=1001,
    ))

    assert preview.kind == "pending_confirmation" and result.kind == "final_answer"
    assert executed == [{"user_id": "alice", "value": "frozen"}]
    assert [call["operation"] for call in meter.calls] == ["loop", "preview", "result"]
    assert [call["request_id"] for call in meter.calls] == ["turn-preview", "turn-preview", "turn-result"]


def test_missing_meter_or_usage_is_safe_and_record_failure_never_breaks_turn(tmp_path) -> None:
    async def no_usage_completion(**_kwargs):
        return _response(content="No usage")

    meter = FakeUsageMeter()
    without_usage = asyncio.run(run_native_agent_turn(
        message="Hello", user_id="alice", turn_id="no-usage", llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(),), completion=no_usage_completion, usage_meter=meter, trace_root=tmp_path,
    ))
    without_meter = asyncio.run(run_native_agent_turn(
        message="Hello", user_id="alice", turn_id="no-meter", llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(),), completion=no_usage_completion, usage_meter=None, trace_root=tmp_path,
    ))

    failing_meter = FakeUsageMeter(fail=True)

    async def metered_completion(**_kwargs):
        return _response(content="Still works", usage=_usage(1, 2, 3))

    failed_record = asyncio.run(run_native_agent_turn(
        message="Hello", user_id="alice", turn_id="meter-fails", llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(),), completion=metered_completion,
        usage_meter=failing_meter, trace_root=tmp_path,
    ))

    assert without_usage.kind == without_meter.kind == failed_record.kind == "final_answer"
    assert meter.calls == []
    assert failed_record.message == "Still works"
    assert len(failing_meter.calls) == 1


def _bridge_owner(tmp_path, *, owner_meter=None, settings_meter=None, completion=None):  # noqa: ANN001
    config = SimpleNamespace(
        enabled=True, native_agent_memory_enabled=True,
        native_agent_connections_enabled=False, native_agent_admin_enabled=False,
        native_agent_write_notes_enabled=False, native_agent_write_memory_enabled=False,
        native_agent_ssh_enabled=False,
    )
    settings = SimpleNamespace(
        agentic_loop=config, llm=LLMConfig(model="fake"), _aria_usage_meter=settings_meter,
        connections=SimpleNamespace(),
    )
    payload = {"settings": settings, "_project_root": tmp_path}
    if owner_meter is not None:
        payload["usage_meter"] = owner_meter
    if completion is not None:
        payload["_native_agent_completion"] = completion
    return SimpleNamespace(**payload)


def _patch_bridge_tools(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: (_binding(),))
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections",
        lambda tools, _settings: tuple(tools),
    )

    async def select(tools_message, tools, **_kwargs):  # noqa: ANN001
        assert tools_message == "Hello"
        return tuple(tools)

    monkeypatch.setattr(pipeline_bridge, "select_relevant_native_tools", select)


def test_pipeline_bridge_prefers_owner_usage_meter_and_records_native_turn(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    meter = FakeUsageMeter()

    async def completion(**_kwargs):
        return _response(content="Hello", usage=_usage(13, 5, 18))

    owner = _bridge_owner(tmp_path, owner_meter=meter, settings_meter=None, completion=completion)
    _patch_bridge_tools(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="owner-meter-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None and result.text == "Hello"
    assert len(meter.calls) == 1
    assert meter.calls[0]["request_id"] == "owner-meter-turn"
    assert meter.calls[0]["usage"] == {"prompt_tokens": 13, "completion_tokens": 5, "total_tokens": 18}


def test_pipeline_bridge_uses_settings_usage_meter_fallback(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    meter = FakeUsageMeter()
    captured: dict[str, object] = {}
    owner = _bridge_owner(tmp_path, settings_meter=meter)

    _patch_bridge_tools(monkeypatch)

    async def fake_run(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return NativeAgentOutcome("final_answer", "Hello", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="bridge-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None and result.text == "Hello"
    assert captured["usage_meter"] is meter


def test_pipeline_bridge_without_usage_meter_is_safe(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    captured: dict[str, object] = {}
    owner = _bridge_owner(tmp_path)
    _patch_bridge_tools(monkeypatch)

    async def fake_run(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return NativeAgentOutcome("final_answer", "Hello", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="no-meter-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None and result.text == "Hello"
    assert captured["usage_meter"] is None


def test_pipeline_bridge_web_debug_details_are_toggle_gated_and_bounded(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    owner = _bridge_owner(tmp_path)
    owner.settings.agentic_loop.native_web_debug_details = True
    owner._native_web_debug_details = {"request_input": "stale"}
    _patch_bridge_tools(monkeypatch)

    async def fake_run(**_kwargs):  # noqa: ANN003
        owner._native_web_debug_details = {
            "request_input": 'actual query "from Luna"\nsecond line',
            "model": "openai/gpt-5.6-luna",
            "search_context_size": "high",
            "reasoning_effort": "low",
            "max_output_tokens": 1200,
            "source_urls": [f"https://example.test/{index}" for index in range(10)],
            "web_uses": 2,
        }
        return NativeAgentOutcome("final_answer", "Web answer", 1, used_tool_names=("web_search_fetch",))

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="web-debug-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None
    assert result.detail_lines[1:] == [
        "Routing Debug: native_llm_timing calls=0 total_ms=0 per_call_ms=[] "
        "cache_read=0 cache_write=0 tools=0 input_tokens=0",
        "Routing Debug: native_finish_reason=-",
        "Routing Debug: memory_learn_extraction pre_filter=skip extraction_ms=0 claim=no",
        "Routing Debug: semantic match_recipe=- sim=0.00",
        'Routing Debug: web_llm_query="actual query \\"from Luna\\"\\nsecond line"',
        "Routing Debug: web_llm_params model=openai/gpt-5.6-luna ctx=high effort=low max_out=1200",
        "Routing Debug: web_llm_sources="
        + ",".join(f"https://example.test/{index}" for index in range(8))
        + " web_uses=2",
    ]
    assert not any(" value=" in line for line in result.detail_lines if "memory_learn_extraction" in line)
    assert "stale" not in "\n".join(result.detail_lines)

    owner.settings.agentic_loop.native_web_debug_details = False
    result_off = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="web-debug-off-turn",
        source="web", start=time.perf_counter(),
    ))
    assert result_off is not None
    assert len(result_off.detail_lines) == 5
    assert "native_llm_timing" in result_off.detail_lines[1]


def test_native_scope_requires_bridge_flush_and_logs_exactly_once(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    async def completion(**_kwargs):
        return _response(content="Hello", usage=_usage(13, 5, 18))

    unflushed_dir = tmp_path / "unflushed"
    unflushed_meter = UsageMeter(_meter_settings(unflushed_dir))

    async def run_without_flush() -> None:
        with unflushed_meter.scope(
            request_id="unflushed-turn", user_id="alice", source="web", router_level=2,
        ):
            outcome = await run_native_agent_turn(
                message="Hello", user_id="alice", turn_id="unflushed-turn",
                llm_config=LLMConfig(model="fake"), tool_bindings=(_binding(),),
                completion=completion, usage_meter=unflushed_meter, trace_root=unflushed_dir,
            )
            assert outcome.kind == "final_answer"

    asyncio.run(run_without_flush())
    assert _token_rows(unflushed_dir / "tokens.jsonl") == []

    flushed_dir = tmp_path / "flushed"
    flushed_dir.mkdir()
    flushed_meter = UsageMeter(_meter_settings(flushed_dir))
    owner = _bridge_owner(flushed_dir, owner_meter=flushed_meter, completion=completion)
    _patch_bridge_tools(monkeypatch)
    monkeypatch.chdir(flushed_dir)

    async def run_with_flush() -> bool:
        with flushed_meter.scope(
            request_id="flushed-turn", user_id="alice", source="web", router_level=2,
        ):
            result = await pipeline_bridge.run_native_agent_first_stage(
                owner, message="Hello", user_id="alice", request_id="flushed-turn",
                source="web", start=time.perf_counter(),
            )
            assert result is not None and result.text == "Hello"
            assert result.usage == {"prompt_tokens": 13, "completion_tokens": 5, "total_tokens": 18}
            return await flushed_meter.flush_current_scope(
                intents=["native_agent"], duration_ms=1, skill_errors=[],
            )

    second_flush = asyncio.run(run_with_flush())
    rows = _token_rows(flushed_dir / "tokens.jsonl")
    assert second_flush is False
    assert len(rows) == 1
    assert rows[0]["request_id"] == "flushed-turn"
    assert rows[0]["total_tokens"] == 18
    assert rows[0]["intents"] == ["native_agent"]


@pytest.mark.parametrize("kind", [
    "pending_confirmation", "confirmation_refused", "final_answer", "fail_closed",
])
def test_pipeline_bridge_flushes_before_every_outcome_branch(monkeypatch, tmp_path, kind) -> None:  # noqa: ANN001
    expected_usage = {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29}
    meter = FakeFlushMeter(snapshot_usage=expected_usage)
    owner = _bridge_owner(tmp_path, owner_meter=meter)
    _patch_bridge_tools(monkeypatch)

    async def fake_run(**_kwargs):
        return NativeAgentOutcome(
            kind, "Outcome", 1, reason="test_reason",
            confirmation_token="token", confirm_command="confirm token",
        )

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id=f"{kind}-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None
    assert result.usage == expected_usage
    assert len(meter.flush_calls) == 1
    assert meter.flush_calls[0]["intents"] == ["native_agent"]
    assert meter.flush_calls[0]["skill_errors"] == (["test_reason"] if kind == "fail_closed" else [])
    assert isinstance(meter.flush_calls[0]["duration_ms"], int)


def test_pipeline_bridge_flush_failure_never_changes_outcome(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    meter = FakeFlushMeter(flush_error=True)
    owner = _bridge_owner(tmp_path, owner_meter=meter)
    _patch_bridge_tools(monkeypatch)

    async def fake_run(**_kwargs):
        return NativeAgentOutcome("final_answer", "Still works", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="flush-error-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None and result.text == "Still works"
    assert len(meter.flush_calls) == 1


def test_pipeline_bridge_flushes_native_tool_intents_for_activity_projection(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    meter = FakeFlushMeter()
    owner = _bridge_owner(tmp_path, owner_meter=meter)
    _patch_bridge_tools(monkeypatch)

    async def fake_run(**_kwargs):
        return NativeAgentOutcome(
            "final_answer", "Recipe completed", 1,
            used_tool_names=("recipes_execute",), used_intents=("recipes_execute",),
            activity={"title": "SSH Update", "target": "srv-dev02", "success": True},
        )

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id="native-activity-turn",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None and result.text == "Recipe completed"
    assert meter.flush_calls[0]["intents"] == ["native_agent", "recipes_execute"]
    assert meter.flush_calls[0]["activity"] == {
        "title": "SSH Update", "target": "srv-dev02", "success": True,
    }


@pytest.mark.parametrize("snapshot_mode", ["missing", "none", "raises"])
def test_pipeline_bridge_snapshot_unavailable_keeps_zero_badge_and_outcome(
    monkeypatch, tmp_path, snapshot_mode,
) -> None:  # noqa: ANN001
    if snapshot_mode == "missing":
        meter = FakeUsageMeter()
    else:
        meter = FakeFlushMeter(snapshot_error=snapshot_mode == "raises")
    owner = _bridge_owner(tmp_path, owner_meter=meter)
    _patch_bridge_tools(monkeypatch)

    async def fake_run(**_kwargs):
        return NativeAgentOutcome("final_answer", "Still works", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Hello", user_id="alice", request_id=f"snapshot-{snapshot_mode}",
        source="web", start=time.perf_counter(),
    ))

    assert result is not None and result.text == "Still works"
    assert result.usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
