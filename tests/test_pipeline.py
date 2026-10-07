import asyncio
import inspect
from types import SimpleNamespace

import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.pipeline import Pipeline


def _pipeline() -> Pipeline:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(agentic_loop=SimpleNamespace(enabled=True))
    pipeline._routing_debug_enabled = lambda: False
    pipeline._finalize_process_result = lambda result, **_kwargs: result
    return pipeline


def test_process_returns_native_result_without_legacy_fallthrough(monkeypatch) -> None:
    expected = PipelineResult(
        request_id="native-1",
        text="native answer",
        usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        intents=["native_agent"],
        skill_errors=[],
        router_level=2,
        duration_ms=4,
    )

    async def fake_native(*_args, **kwargs):
        assert kwargs["auth_role"] == "admin"
        assert kwargs["confirmation_token"] == "na-token"
        return expected

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

    result = asyncio.run(
        _pipeline().process(
            "hello",
            user_id="u1",
            auth_role="admin",
            confirmation_token="na-token",
        )
    )

    assert result is expected


def test_process_returns_honest_degraded_result_when_native_is_disabled(monkeypatch) -> None:
    async def fake_native(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

    result = asyncio.run(_pipeline().process("hello", user_id="u1"))

    assert result.text == "The native agent is disabled for this turn."
    assert result.skill_errors == ["native_agent_disabled"]
    assert result.usage["total_tokens"] == 0


def test_legacy_process_flow_surface_is_absent() -> None:
    assert "aria_turn_arbitration" not in inspect.signature(Pipeline.process).parameters
    for name in (
        "_run_process_turn_routing_stage",
        "_run_terminal_module_response_stage",
        "_run_recipe_status_stage",
        "_run_process_action_recipe_stage",
        "_run_process_context_answer_stage",
        "_run_process_chat_response_stage",
        "_run_process_runtime_followup_stage",
    ):
        assert not hasattr(Pipeline, name)
