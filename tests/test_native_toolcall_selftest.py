from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.templating import Jinja2Templates

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_toolcall_selftest.roundtrip import run_native_toolcall_selftest
from aria.modules.native_toolcall_selftest.routes import NativeToolcallRouteDeps, register_native_toolcall_selftest_routes


def _response(*, message, finish_reason: str = "stop"):  # noqa: ANN001
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def test_native_roundtrip_parses_object_tool_call_and_returns_exact_twelve() -> None:
    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(
                message=SimpleNamespace(
                    content="", tool_calls=[SimpleNamespace(
                        id="call-1", function=SimpleNamespace(name="add_numbers", arguments='{"a":7,"b":5}'),
                    )],
                ),
                finish_reason="tool_use",
            )
        return _response(message=SimpleNamespace(content="12", tool_calls=[]))

    result = asyncio.run(run_native_toolcall_selftest(LLMConfig(model="claude-sonnet-4-5"), completion=fake_completion))

    assert result.native_tool_call_emitted is True
    assert result.tool_name == "add_numbers"
    assert result.arguments == {"a": 7, "b": 5}
    assert result.tool_result == 12
    assert result.final_answer_correct is True
    assert result.response_source == "tool_calls"
    assert len(calls) == 2
    assert all(call["tool_choice"] == "auto" and "tools" in call for call in calls)
    assert all("response_format" not in call for call in calls)
    assert calls[0]["tools"] == [{
        "name": "add_numbers",
        "description": "Add two integers and return their sum.",
        "input_schema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
    }]
    assert calls[1]["messages"][-1] == {"role": "tool", "tool_call_id": "call-1", "content": "12"}


def test_native_roundtrip_parses_dict_tool_call_and_dict_arguments() -> None:
    responses = iter([
        {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call-2", "function": {"name": "add_numbers", "arguments": {"a": 7, "b": 5}}}]}, "finish_reason": "tool_use"}]},
        {"choices": [{"message": {"content": "12", "tool_calls": []}, "finish_reason": "stop"}]},
    ])

    async def fake_completion(**_kwargs):
        return next(responses)

    result = asyncio.run(run_native_toolcall_selftest(LLMConfig(model="claude-sonnet-4-5"), completion=fake_completion))

    assert result.arguments == {"a": 7, "b": 5}
    assert result.final_answer == "12"
    assert result.finish_reason == "tool_use"


def test_bad_request_diagnostics_include_raw_error_and_sent_tool_payload() -> None:
    class BadRequestError(Exception):
        pass

    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        raise BadRequestError("tools.0.custom.input_schema.type: Input should be 'object'")

    result = asyncio.run(run_native_toolcall_selftest(LLMConfig(model="claude-sonnet-4-5"), completion=fake_completion))

    assert result.native_tool_call_emitted is False
    assert result.provider_calls == 1
    assert result.provider_error == "tools.0.custom.input_schema.type: Input should be 'object'"
    assert result.tool_payload == calls[0]["tools"]
    assert result.tool_payload[0]["input_schema"]["type"] == "object"


def test_admin_route_is_inert_on_get_rejects_non_admin_and_runs_once_on_post(tmp_path) -> None:  # noqa: ANN001
    app = FastAPI()
    (tmp_path / "native_toolcall_selftest.html").write_text(
        "Run native Tool-Call selftest {{ diagnostics }} {{ error }}", encoding="utf-8",
    )
    templates = Jinja2Templates(directory=str(tmp_path))
    runs: list[int] = []

    @app.middleware("http")
    async def auth_state(request: Request, call_next):  # noqa: ANN001
        request.state.can_access_advanced_config = request.headers.get("x-advanced") == "1"
        request.state.auth_role = request.headers.get("x-role", "user")
        request.state.lang = "de"
        request.state.csrf_token = "test"
        return await call_next(request)

    async def runner(_config):  # noqa: ANN001
        runs.append(1)
        return SimpleNamespace(as_dict=lambda: {"native_tool_call_emitted": True, "tool_name": "add_numbers", "arguments": {"a": 7, "b": 5}, "tool_result": 12, "final_answer": "12", "final_answer_correct": True, "finish_reason": "tool_use", "response_source": "tool_calls", "provider_calls": 2})

    register_native_toolcall_selftest_routes(app, NativeToolcallRouteDeps(templates=templates, get_llm_config=lambda: LLMConfig(model="fake"), run_selftest=runner))
    client = TestClient(app)

    assert client.get("/config/native-toolcall-selftest").status_code == 403
    page = client.get("/config/native-toolcall-selftest", headers={"x-advanced": "1", "x-role": "admin"})
    assert page.status_code == 200 and "Run native Tool-Call selftest" in page.text
    assert runs == []
    result = client.post("/config/native-toolcall-selftest", headers={"x-advanced": "1", "x-role": "admin"})
    assert result.status_code == 200 and "add_numbers" in result.text and "12" in result.text
    assert runs == [1]
