from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.handler import (
    NativeAgentOutcome,
    _is_transient_provider_error,
    _looks_like_unsourced_resource_claim,
    run_native_agent_turn,
)
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


class InternalServerError(RuntimeError):
    status_code = 500


class InvalidRequestError(RuntimeError):
    status_code = 400


def _response(*, content: str = "", tool_calls: list[object] | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=list(tool_calls or []))
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _tool_call() -> SimpleNamespace:
    return SimpleNamespace(
        id="call-build-1",
        function=SimpleNamespace(name="scene_mutation", arguments="{}"),
    )


def _mutating_binding(
    *, status: str = "ok", effect: str = "mutating", owner_module_id: str = "test",
) -> NativeToolBinding:
    async def handler(_context: NativeToolContext, _arguments: object) -> NativeToolResult:
        return NativeToolResult(
            json.dumps({"status": status, "observation": "snowman body created"}),
            "scene_mutation",
        )

    return NativeToolBinding(
        NativeToolContract(
            owner_module_id=owner_module_id,
            name="scene_mutation",
            description="Mutate the test scene.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect=effect,
            confirmation_required=False,
            source_authority="test:scene",
            user_scoped=True,
            rollout_flag="native_agent_mcp_enabled",
        ),
        handler,
    )


def _run_with_finalizer(completion, tmp_path, *, status: str = "ok"):  # noqa: ANN001, ANN202
    return asyncio.run(run_native_agent_turn(
        message="Build the scene",
        user_id="alice",
        turn_id="budget-resilience",
        language="en",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mutating_binding(status=status),),
        completion=completion,
        trace_root=tmp_path,
        max_steps=1,
        max_provider_calls=2,
    ))


def test_agent_budget_defaults_and_bridge_wiring(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    defaults = AgenticLoopFeatureConfig()
    assert defaults.native_agent_max_steps == 32
    assert defaults.native_agent_max_provider_calls == 32

    config = SimpleNamespace(
        enabled=True,
        native_agent_memory_enabled=True,
        native_agent_max_steps=12,
        native_agent_max_provider_calls=14,
        native_tool_selector_top_k=16,
        native_agent_memory_learn_enabled=False,
        native_web_debug_details=False,
    )
    owner = SimpleNamespace(
        settings=SimpleNamespace(agentic_loop=config, llm=LLMConfig(model="fake")),
        _project_root=tmp_path,
        embedding_client=None,
        usage_meter=None,
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    async def fake_turn(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return NativeAgentOutcome("final_answer", "done", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner,
        message="hello",
        user_id="alice",
        request_id="budget-wiring",
        source="test",
        start=0.0,
        language="en",
    ))

    assert result is not None and result.text == "done"
    assert captured["max_steps"] == 12
    assert captured["max_provider_calls"] == 14


def test_default_budget_keeps_seven_tool_steps_on_normal_final_answer_path(tmp_path) -> None:  # noqa: ANN001
    calls = 0

    async def completion(**kwargs):
        nonlocal calls
        calls += 1
        if calls <= 7:
            assert kwargs["tool_choice"] == "auto"
            return _response(tool_calls=[_tool_call()])
        return _response(content="The seven recorded steps are complete.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Build a snowman",
        user_id="alice",
        turn_id="seven-step-normal-path",
        language="en",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mutating_binding(),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.reason == ""
    assert outcome.warning == ""
    assert outcome.provider_calls == 8
    assert calls == 8


def test_transient_finalizer_retries_twice_then_returns_real_answer(tmp_path) -> None:  # noqa: ANN001
    finalizer_calls = 0

    async def completion(**kwargs):
        nonlocal finalizer_calls
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        finalizer_calls += 1
        if finalizer_calls < 3:
            raise InternalServerError("upstream 500")
        return _response(content="The recorded scene step completed.")

    outcome = _run_with_finalizer(completion, tmp_path)

    assert outcome.kind == "final_answer"
    assert outcome.message == "The recorded scene step completed."
    assert outcome.reason == "native_agent_budget_best_effort"
    assert outcome.warning == "native_agent_budget_exhausted"
    assert finalizer_calls == 3
    assert outcome.provider_calls == 4


def test_exhausted_transient_finalizer_degrades_from_successful_mutation_only(tmp_path) -> None:  # noqa: ANN001
    finalizer_calls = 0

    async def completion(**kwargs):
        nonlocal finalizer_calls
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        finalizer_calls += 1
        raise InternalServerError("litellm.InternalServerError: upstream secret detail")

    outcome = _run_with_finalizer(completion, tmp_path)

    assert outcome.kind == "final_answer"
    assert outcome.reason == "native_agent_budget_finalization_degraded"
    assert outcome.warning == "native_agent_summary_unavailable"
    assert "snowman body created" in outcome.message
    assert "Warning:" in outcome.message
    assert "InternalServerError" not in outcome.message
    assert "secret detail" not in outcome.message
    assert not _looks_like_unsourced_resource_claim(outcome.message)
    assert finalizer_calls == 3


def test_trusted_mcp_observation_can_degrade_without_changing_trust_binding_effect(tmp_path) -> None:  # noqa: ANN001
    async def completion(**kwargs):
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        raise InternalServerError("upstream 500")

    outcome = asyncio.run(run_native_agent_turn(
        message="Build the scene",
        user_id="alice",
        turn_id="trusted-mcp-finalizer",
        language="en",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mutating_binding(effect="read_only", owner_module_id="mcp"),),
        completion=completion,
        trace_root=tmp_path,
        max_steps=1,
        max_provider_calls=2,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.warning == "native_agent_summary_unavailable"
    assert "snowman body created" in outcome.message


def test_transient_provider_failure_without_successful_tool_is_still_infra_error(tmp_path) -> None:  # noqa: ANN001
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        raise InternalServerError("upstream 529 overloaded_error")

    outcome = asyncio.run(run_native_agent_turn(
        message="hello",
        user_id="alice",
        turn_id="no-observations",
        language="en",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mutating_binding(),),
        completion=completion,
        trace_root=tmp_path,
        max_provider_calls=3,
    ))

    assert outcome.kind == "infra_error"
    assert outcome.warning == ""
    assert calls == 3


def test_non_transient_4xx_is_not_retried(tmp_path) -> None:  # noqa: ANN001
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        raise InvalidRequestError("invalid request")

    outcome = asyncio.run(run_native_agent_turn(
        message="hello",
        user_id="alice",
        turn_id="non-transient",
        language="en",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mutating_binding(),),
        completion=completion,
        trace_root=tmp_path,
        max_provider_calls=4,
    ))

    assert outcome.kind == "infra_error"
    assert calls == 1


def test_non_transient_finalizer_4xx_degrades_without_retry(tmp_path) -> None:  # noqa: ANN001
    finalizer_calls = 0

    async def completion(**kwargs):
        nonlocal finalizer_calls
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        finalizer_calls += 1
        raise InvalidRequestError("invalid request")

    outcome = _run_with_finalizer(completion, tmp_path)

    assert outcome.kind == "final_answer"
    assert outcome.warning == "native_agent_summary_unavailable"
    assert finalizer_calls == 1


def test_finalizer_keeps_tools_omits_none_and_does_not_execute_returned_tool_call(tmp_path) -> None:  # noqa: ANN001
    executed = 0

    async def handler(_context, _arguments):  # noqa: ANN001
        nonlocal executed
        executed += 1
        return NativeToolResult('{"status":"ok","observation":"created"}', "scene_mutation")

    binding = _mutating_binding()
    binding = NativeToolBinding(binding.contract, handler)
    requests: list[dict] = []

    async def completion(**kwargs):
        requests.append(kwargs)
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        return _response(content="Scripted final summary.", tool_calls=[_tool_call()])

    outcome = asyncio.run(run_native_agent_turn(
        message="Build", user_id="alice", turn_id="alpha978-finalizer",
        language="en", llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=completion, trace_root=tmp_path, max_steps=1, max_provider_calls=2,
    ))
    assert outcome.message == "Scripted final summary."
    assert executed == 1
    assert requests[-1].get("tool_choice") is None
    assert requests[-1]["tools"]


def test_live_proxy_parameter_error_is_non_transient_even_with_status_500() -> None:
    error = InternalServerError("Incompatible tool choice param submitted - {'type': 'none'}")
    assert _is_transient_provider_error(error) is False
    assert _is_transient_provider_error(InternalServerError("upstream 500")) is True
    assert _is_transient_provider_error(InternalServerError("529 overloaded_error")) is True


def test_live_proxy_parameter_error_finalizer_is_not_retried(tmp_path) -> None:  # noqa: ANN001
    finalizer_calls = 0

    async def completion(**kwargs):
        nonlocal finalizer_calls
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        finalizer_calls += 1
        raise InternalServerError("Incompatible tool choice param submitted - {'type': 'none'}")

    outcome = _run_with_finalizer(completion, tmp_path)
    assert finalizer_calls == 1
    assert outcome.kind == "final_answer"
    assert outcome.reason == "native_agent_budget_finalization_degraded"


def test_budget_extension_math_hard_cap_and_retention(tmp_path) -> None:  # noqa: ANN001
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="budget", user_id="alice", goal="build", status="detached", now=10)
    state = {"messages": [], "step_index": 32, "provider_calls": 31,
             "budget_max_steps": 32, "budget_max_provider_calls": 32}
    assert store.set_paused("budget", state, reason="budget_reached", now=20)
    resumed = store.claim_budget_resume("budget", user_id="alice", extension=32, hard_cap=64)
    assert resumed is not None
    assert resumed["budget_max_steps"] == 64
    assert resumed["budget_max_provider_calls"] == 64
    assert store.set_paused("budget", resumed, reason="budget_reached", now=30)
    assert store.claim_budget_resume("budget", user_id="alice", extension=32, hard_cap=64) is None
    finishing = store.claim_budget_resume("budget", user_id="alice", extension=32, hard_cap=64, finish=True)
    assert finishing is not None and finishing["budget_finish_requested"] is True

    store.create(job_id="old", user_id="alice", goal="old", status="detached", now=1)
    store.set_terminal("old", status="done", result="ok", now=2)
    store.create(job_id="active", user_id="alice", goal="active", status="running", now=1)
    assert store.purge_terminal_before(stale_before=3) == 1
    assert store.get("old") is None and store.get("active") is not None
    assert store.delete_terminal("active", user_id="alice") == "not_terminal"
    assert store.delete_terminal("active", user_id="mallory") == "not_found"

    store.create(job_id="stale-pause", user_id="alice", goal="pause", status="detached", now=1)
    assert store.set_paused(
        "stale-pause", {"pending_token": "secret", "messages": []},
        reason="budget_reached", now=2,
    )
    assert [row.job_id for row in store.stale_paused(stale_before=3)] == ["stale-pause"]
    assert store.cancel_stale_paused("stale-pause", now=4)
    stale = store.get("stale-pause")
    assert stale is not None and stale.status == "cancelled" and stale.resume_state is None


def test_failed_tool_result_does_not_enable_finalizer_degradation(tmp_path) -> None:  # noqa: ANN001
    async def completion(**kwargs):
        if kwargs.get("tool_choice") == "auto":
            return _response(tool_calls=[_tool_call()])
        raise InternalServerError("upstream 500")

    outcome = _run_with_finalizer(completion, tmp_path, status="error")

    assert outcome.kind == "infra_error"
    assert outcome.warning == ""


def test_detached_degraded_result_is_done_with_warning_but_error_stays_error(
    monkeypatch, tmp_path,
) -> None:  # noqa: ANN001
    outcomes = iter([
        PipelineResult(
            request_id="degraded",
            text="Observed step.\n\nWarning: Natural-language summary unavailable.",
            usage={},
            intents=["scene_mutation"],
            skill_errors=[],
            router_level=2,
            duration_ms=1,
            detail_lines=["Routing Debug: native_agent_summary_warning=yes"],
        ),
        PipelineResult(
            request_id="error",
            text="Could not complete.",
            usage={},
            intents=["native_agent"],
            skill_errors=["native_agent_provider_failed"],
            router_level=2,
            duration_ms=1,
        ),
    ])

    async def fake_native(*_args, **kwargs):
        await kwargs["step_callback"](1, ("scene_mutation",), "snowman body created")
        await asyncio.sleep(0.03)
        return next(outcomes)

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(
        agentic_loop=SimpleNamespace(enabled=True, async_agent_job_sync_budget_seconds=0.01),
    )
    pipeline._project_root = tmp_path
    pipeline._routing_debug_enabled = lambda: False
    pipeline._finalize_process_result = lambda result, **_kwargs: result

    async def scenario():  # noqa: ANN202
        await pipeline.process("first", user_id="alice", language="en")
        await pipeline.process("second", user_id="alice", language="en")
        for _ in range(100):
            records = pipeline.get_agent_job_store().list_for_user("alice")
            if len(records) == 2 and all(row.status in {"done", "error"} for row in records):
                return records
            await asyncio.sleep(0.01)
        raise AssertionError("jobs did not finish")

    records = asyncio.run(scenario())
    by_goal = {record.goal: record for record in records}

    assert by_goal["first"].status == "done"
    assert by_goal["first"].warning == "native_agent_summary_unavailable"
    assert "Warning:" in by_goal["first"].result
    assert by_goal["second"].status == "error"
    assert by_goal["second"].warning == ""
