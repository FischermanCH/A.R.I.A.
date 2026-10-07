from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import LLMConfig, load_settings
from aria.modules.memory.native_tools import native_tool_contributions as memory_native_tools
from aria.modules.model_gateway_clients.llm import LLMClient
from aria.modules.model_gateway_clients.parameter_compat import (
    call_with_model_parameter_compat,
    reset_model_parameter_compatibility,
    temperature_omitted_for_model,
)
from aria.modules.native_agent.handler import (
    _run_server_memory_learning,
    run_native_agent_turn,
)
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_toolcall_selftest.roundtrip import run_native_toolcall_selftest
from aria.modules.runtime_diagnostics import runtime as runtime_diagnostics


LIVE_TEMPERATURE_ERROR = "`temperature` is deprecated for this model."


class BadRequestError(Exception):
    status_code = 400


def _response(content: str = "ok", *, tool_calls: list[object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=list(tool_calls or ())),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


@pytest.fixture(autouse=True)
def _clear_model_parameter_compatibility() -> None:
    reset_model_parameter_compatibility()


def test_llm_temperature_is_optional_but_existing_default_is_unchanged() -> None:
    assert LLMConfig(model="claude-sonnet-4-5").temperature == 0.4
    assert LLMConfig.model_validate({"model": "claude-sonnet-5", "temperature": None}).temperature is None


def test_settings_yaml_loads_null_and_numeric_temperature(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.delenv("ARIA_LLM_TEMPERATURE", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm:\n  model: claude-sonnet-5\n  temperature: null\n",
        encoding="utf-8",
    )
    assert load_settings(config_path).llm.temperature is None
    config_path.write_text(
        "llm:\n  model: claude-sonnet-4-5\n  temperature: 0.7\n",
        encoding="utf-8",
    )
    assert load_settings(config_path).llm.temperature == 0.7


def test_exact_live_temperature_rejection_retries_once_and_remembers_model() -> None:
    calls: list[dict[str, object]] = []
    omitted: list[str] = []

    async def completion(**kwargs):
        calls.append(dict(kwargs))
        if kwargs.get("temperature") is not None:
            raise BadRequestError(LIVE_TEMPERATURE_ERROR)
        return "ok"

    result = asyncio.run(call_with_model_parameter_compat(
        completion,
        {"model": "claude-sonnet-5", "temperature": 0.4},
        on_temperature_omitted=omitted.append,
    ))
    assert result == "ok"
    assert [row["temperature"] for row in calls] == [0.4, None]
    assert omitted == ["claude-sonnet-5"]
    assert temperature_omitted_for_model("claude-sonnet-5") is True

    calls.clear()
    asyncio.run(call_with_model_parameter_compat(
        completion,
        {"model": "claude-sonnet-5", "temperature": 0.9},
        on_temperature_omitted=omitted.append,
    ))
    assert calls == [{"model": "claude-sonnet-5", "temperature": None}]
    assert omitted == ["claude-sonnet-5"]


def test_other_bad_request_is_not_retried_and_temperature_retry_never_loops() -> None:
    ordinary_calls = 0

    async def ordinary(**_kwargs):
        nonlocal ordinary_calls
        ordinary_calls += 1
        raise BadRequestError("invalid_request_error: another field is invalid")

    with pytest.raises(BadRequestError, match="another field"):
        asyncio.run(call_with_model_parameter_compat(
            ordinary, {"model": "claude-sonnet-5", "temperature": 0.4},
        ))
    assert ordinary_calls == 1

    rejected_calls = 0

    async def rejected(**_kwargs):
        nonlocal rejected_calls
        rejected_calls += 1
        raise BadRequestError(LIVE_TEMPERATURE_ERROR)

    with pytest.raises(BadRequestError, match="deprecated"):
        asyncio.run(call_with_model_parameter_compat(
            rejected, {"model": "claude-sonnet-5", "temperature": 0.4},
        ))
    assert rejected_calls == 2


def test_llm_client_and_memory_extraction_forward_none_without_crashing(monkeypatch) -> None:  # noqa: ANN001
    client_calls: list[dict[str, object]] = []

    async def client_completion(**kwargs):
        client_calls.append(dict(kwargs))
        return _response("client ok")

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", client_completion)
    response = asyncio.run(LLMClient(LLMConfig(model="temperature-free", temperature=None)).chat([
        {"role": "user", "content": "hello"},
    ]))
    assert response.content == "client ok"
    assert client_calls[0]["temperature"] is None

    extraction_calls: list[dict[str, object]] = []

    async def extraction_completion(**kwargs):
        extraction_calls.append(dict(kwargs))
        return _response("{}")

    result = asyncio.run(_run_server_memory_learning(
        message="ich mag gruener tee",
        user_id="alice",
        turn_id="temperature-none-memory",
        llm_config=LLMConfig(model="temperature-free", temperature=None),
        completion=extraction_completion,
        usage_meter=None,
        observed_claim_store=None,
        embedding_client=None,
        personal_claim_semantic_checker=None,
    ))
    assert result.claim is None
    assert extraction_calls[0]["temperature"] is None


def test_runtime_probe_does_not_reintroduce_temperature_when_unset(monkeypatch) -> None:  # noqa: ANN001
    captured: list[LLMConfig] = []

    class FakeClient:
        def __init__(self, config, usage_meter=None):  # noqa: ANN001
            del usage_meter
            captured.append(config)

        async def chat(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            return SimpleNamespace(content="OK")

    monkeypatch.setattr(runtime_diagnostics, "LLMClient", FakeClient)
    result = asyncio.run(runtime_diagnostics.probe_llm(
        LLMConfig(model="temperature-free", temperature=None),
    ))
    assert result["status"] == "ok"
    assert captured[0].temperature is None


def test_native_loop_and_selftest_forward_none_to_every_provider_call(tmp_path) -> None:  # noqa: ANN001
    owner = SimpleNamespace(
        memory_skill=object(),
        settings=SimpleNamespace(),
        _native_agent_claim_loader=lambda _user_id: (),
    )
    bindings = tuple(
        binding for binding in memory_native_tools(owner)
        if binding.contract.name == "recall_personal_memory"
    )
    native_calls: list[dict[str, object]] = []

    async def native_completion(**kwargs):
        native_calls.append(dict(kwargs))
        return _response("hello")

    outcome = asyncio.run(run_native_agent_turn(
        message="hello",
        user_id="alice",
        turn_id="temperature-none-loop",
        llm_config=LLMConfig(model="temperature-free", temperature=None),
        tool_bindings=bindings,
        completion=native_completion,
        trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert native_calls and all(call["temperature"] is None for call in native_calls)

    selftest_calls: list[dict[str, object]] = []

    async def selftest_completion(**kwargs):
        selftest_calls.append(dict(kwargs))
        if len(selftest_calls) == 1:
            return _response("", tool_calls=[SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(name="add_numbers", arguments='{"a":7,"b":5}'),
            )])
        return _response("12")

    diagnostics = asyncio.run(run_native_toolcall_selftest(
        LLMConfig(model="temperature-free", temperature=None),
        completion=selftest_completion,
    ))
    assert diagnostics.final_answer_correct is True
    assert len(selftest_calls) == 2
    assert all(call["temperature"] is None for call in selftest_calls)


def test_native_turn_retries_exact_rejection_once_and_reports_compat_detail_state(tmp_path) -> None:  # noqa: ANN001
    owner = SimpleNamespace(
        memory_skill=object(),
        settings=SimpleNamespace(),
        _native_agent_claim_loader=lambda _user_id: (),
    )
    bindings = tuple(
        binding for binding in memory_native_tools(owner)
        if binding.contract.name == "recall_personal_memory"
    )
    calls: list[dict[str, object]] = []

    async def completion(**kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise BadRequestError(LIVE_TEMPERATURE_ERROR)
        return _response("compatible")

    outcome = asyncio.run(run_native_agent_turn(
        message="hello",
        user_id="alice",
        turn_id="temperature-retry-loop",
        llm_config=LLMConfig(model="claude-sonnet-5", temperature=0.4),
        tool_bindings=bindings,
        completion=completion,
        trace_root=tmp_path,
        max_provider_calls=2,
    ))
    assert outcome.kind == "final_answer"
    assert outcome.message == "compatible"
    assert outcome.provider_calls == 1
    assert outcome.llm_param_compat_model == "claude-sonnet-5"
    assert [row["temperature"] for row in calls] == [0.4, None]


def test_pipeline_details_emit_temperature_compat_once(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    config = SimpleNamespace(
        enabled=True,
        native_agent_memory_enabled=True,
        native_agent_mcp_enabled=False,
        native_agent_memory_learn_enabled=False,
        native_web_debug_details=False,
        native_tool_selector_top_k=16,
        native_agent_max_steps=32,
        native_agent_max_provider_calls=32,
    )
    owner = SimpleNamespace(
        settings=SimpleNamespace(
            agentic_loop=config,
            llm=LLMConfig(model="claude-sonnet-5"),
            _aria_usage_meter=None,
        ),
        _project_root=tmp_path,
        _native_agent_completion=None,
        _load_stored_recipe_runtime=lambda: (),
        usage_meter=None,
        embedding_client=None,
    )
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    async def fake_turn(**_kwargs):
        from aria.modules.native_agent.handler import NativeAgentOutcome

        return NativeAgentOutcome(
            "final_answer", "compatible", 1,
            llm_param_compat_model="claude-sonnet-5",
        )

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner,
        message="hello",
        user_id="alice",
        request_id="temperature-compat-details",
        source="test",
        start=0.0,
        language="en",
    ))
    assert result is not None
    lines = [line for line in result.detail_lines if "llm_param_compat" in line]
    assert lines == [
        "Routing Debug: llm_param_compat model=claude-sonnet-5 omitted=temperature"
    ]
