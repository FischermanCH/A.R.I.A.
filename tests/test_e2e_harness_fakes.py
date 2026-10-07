from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from e2e.fake_mcp import FakeMCPController, FakeMCPState, create_control_app
from e2e.strict_anthropic import (
    ALPHA972_CACHE_CONTROL_ERROR,
    ScriptedAnthropicState,
    create_app,
    validate_anthropic_request,
)


def _base() -> dict:
    return {
        "model": "claude-e2e",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
    }


def _valid_tool_pair() -> dict:
    payload = _base()
    payload["tools"] = [{"name": "look", "description": "Look", "input_schema": {"type": "object"}}]
    payload["messages"] = [
        {"role": "user", "content": [{"type": "text", "text": "Look"}]},
        {"role": "assistant", "content": [{
            "type": "tool_use", "id": "toolu-1", "name": "look", "input": {},
        }]},
        {"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": "toolu-1", "content": [
                {"type": "text", "text": "ok"},
            ],
        }]},
    ]
    return payload


@pytest.mark.parametrize(
    ("valid_payload", "invalid_payload", "expected"),
    [
        (
            _valid_tool_pair(),
            {
                **_valid_tool_pair(),
                "messages": [
                    *_valid_tool_pair()["messages"][:2],
                    {"role": "user", "content": [{
                        "type": "tool_result", "tool_use_id": "toolu-1",
                        "content": [{"type": "text", "text": "ok", "cache_control": {"type": "ephemeral"}}],
                    }]},
                ],
            },
            ALPHA972_CACHE_CONTROL_ERROR,
        ),
        (
            {**_base(), "system": [{"type": "text", "text": "s", "cache_control": {"type": "ephemeral"}}]},
            {
                **_base(),
                "system": [
                    {"type": "text", "text": str(index), "cache_control": {"type": "ephemeral"}}
                    for index in range(5)
                ],
            },
            "At most 4 cache_control blocks",
        ),
        (
            _valid_tool_pair(),
            {
                **_valid_tool_pair(),
                "messages": [
                    *_valid_tool_pair()["messages"][:2],
                    {"role": "user", "content": [{
                        "type": "tool_result", "tool_use_id": "wrong", "content": "no",
                    }]},
                ],
            },
            "tool_result must reference",
        ),
        (
            _valid_tool_pair(),
            {"model": "claude-e2e", "messages": _valid_tool_pair()["messages"]},
            "Tool blocks require",
        ),
        (
            _base(),
            {**_base(), "messages": [
                {"role": "assistant", "content": "bad"},
                {"role": "assistant", "content": "bad again"},
            ]},
            "strictly alternate",
        ),
        (
            {**_base(), "messages": [{"role": "user", "content": [{
                "type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": "aGVsbG8=",
                },
            }]}]},
            {**_base(), "messages": [{"role": "user", "content": [{
                "type": "image", "source": {
                    "type": "base64", "media_type": "image/tiff", "data": "not-base64",
                },
            }]}]},
            "invalid image",
        ),
        (
            _base(),
            {**_base(), "messages": [{"role": "user", "content": [{"type": "text", "text": "  "}]}]},
            "text blocks must not be empty",
        ),
    ],
)
def test_strict_anthropic_validator_accepts_valid_and_rejects_rule_violation(
    valid_payload: dict, invalid_payload: dict, expected: str,
) -> None:
    assert validate_anthropic_request(valid_payload) == ()
    assert expected in " | ".join(item.message for item in validate_anthropic_request(invalid_payload))


def test_strict_anthropic_rejects_exact_alpha972_nested_cache_control_shape() -> None:
    payload = _valid_tool_pair()
    payload["messages"][-1]["content"][0]["content"][0]["cache_control"] = {"type": "ephemeral"}
    client = TestClient(create_app(ScriptedAnthropicState()))
    response = client.post("/v1/messages", json=payload)
    assert response.status_code == 400
    assert response.json() == {
        "type": "error",
        "error": {"type": "invalid_request_error", "message": ALPHA972_CACHE_CONTROL_ERROR},
    }


def test_strict_anthropic_script_records_sanitized_image_and_realistic_usage() -> None:
    state = ScriptedAnthropicState()
    client = TestClient(create_app(state))
    client.post("/__control/reset", json={
        "scenario": "usage", "steps": [{"type": "text", "text": "ok", "cache_read_input_tokens": 11}],
    }).raise_for_status()
    payload = _base()
    payload["messages"][0]["content"] = [{
        "type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="},
    }]
    response = client.post("/v1/messages", json=payload)
    assert response.status_code == 200
    assert response.json()["usage"]["cache_read_input_tokens"] == 11
    assert "[base64 omitted;" in str(client.get("/__control/logs").json()["requests"])


def test_strict_fake_opt_in_reproduces_live_litellm_proxy_tool_choice_error() -> None:
    state = ScriptedAnthropicState()
    client = TestClient(create_app(state))
    client.post("/__control/reset", json={
        "scenario": "proxy", "steps": [], "litellm_proxy_compatibility": True,
    }).raise_for_status()
    payload = _base()
    payload["tool_choice"] = {"type": "none"}
    response = client.post("/v1/messages", json=payload)
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Incompatible tool choice param submitted - {'type': 'none'}"


def test_strict_fake_temperature_free_model_reproduces_exact_live_error_and_accepts_omission() -> None:
    state = ScriptedAnthropicState()
    client = TestClient(create_app(state))
    client.post("/__control/reset", json={
        "scenario": "temperature-free",
        "steps": [{"type": "text", "text": "ok"}],
        "temperature_free_models": ["claude-sonnet-5"],
    }).raise_for_status()
    rejected = client.post("/v1/messages", json={**_base(), "model": "claude-sonnet-5", "temperature": 0.4})
    assert rejected.status_code == 400
    assert rejected.json()["error"] == {
        "type": "invalid_request_error",
        "message": "`temperature` is deprecated for this model.",
    }

    accepted = client.post("/v1/messages", json={**_base(), "model": "claude-sonnet-5"})
    assert accepted.status_code == 200
    logs = client.get("/__control/logs").json()["requests"]
    assert [row["accepted"] for row in logs] == [False, True]


def test_strict_fake_embeddings_are_deterministic_and_openai_compatible() -> None:
    state = ScriptedAnthropicState()
    client = TestClient(create_app(state))
    payload = {"model": "text-embedding-3-small", "input": ["alpha", "beta", "alpha"]}

    response = client.post("/v1/embeddings", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert [row["index"] for row in body["data"]] == [0, 1, 2]
    assert len(body["data"][0]["embedding"]) == 32
    assert body["data"][0]["embedding"] == body["data"][2]["embedding"]
    assert body["data"][0]["embedding"] != body["data"][1]["embedding"]
    assert client.get("/__control/logs").json()["embedding_requests"] == [
        {"model": "text-embedding-3-small", "count": 3}
    ]


def test_fake_mcp_state_and_control_endpoint_are_idempotent() -> None:
    state = FakeMCPState()
    state.record("execute_blender_code", {"code": "name='Blue Cube'"})
    assert state.add_objects_from_code("name='Blue Cube'") == ["Blue Cube"]
    assert state.snapshot()["scene"] == ["Blue Cube"]
    state.reset()
    assert state.snapshot() == {"scene": [], "calls": [], "behavior": {"hang": False}}

    controller = FakeMCPController("127.0.0.1", 0, start_listener=False)
    client = TestClient(create_control_app(controller))
    assert client.post("/__control/start").json()["listener_running"] is True
    assert client.post("/__control/behavior", json={"hang": True}).json()["behavior"]["hang"] is True
    assert client.post("/__control/drop").json()["mode"] == "half_open_drop"
    assert client.get("/__control/logs").json()["listener_running"] is False
    assert client.post("/__control/stop").json()["listener_running"] is False
