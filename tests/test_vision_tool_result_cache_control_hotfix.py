from __future__ import annotations

from copy import deepcopy
import os

import pytest

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS"] = "True"

from litellm.llms.anthropic.chat.transformation import AnthropicConfig

from aria.modules.native_agent.handler import _cacheable_request
from aria.modules.navigation_shell.ui_helpers import intent_badge


_CACHE_CONTROL = {"type": "ephemeral", "ttl": "1h"}
_TOOL = {
    "name": "mcp__blender__look",
    "description": "Return the current Blender viewport.",
    "input_schema": {"type": "object", "properties": {}},
}


def _count_cache_control(value: object) -> int:
    if isinstance(value, dict):
        return int("cache_control" in value) + sum(
            _count_cache_control(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return sum(_count_cache_control(item) for item in value)
    return 0


def _tool_results(value: object) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        if value.get("type") == "tool_result":
            found.append(value)
        for item in value.values():
            found.extend(_tool_results(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_tool_results(item))
    return found


def _anthropic_payload(messages: list[dict], tools: list[dict] | None) -> dict:
    return AnthropicConfig().transform_request(
        model="claude-sonnet-4-5",
        messages=deepcopy(messages),
        optional_params={"max_tokens": 128, **({"tools": deepcopy(tools)} if tools else {})},
        litellm_params={},
        headers={},
    )


@pytest.mark.parametrize(
    "tool_content, expected_content_type",
    [
        ('{"status":"ok"}', str),
        (
            [
                {"type": "text", "text": '{"status":"ok"}'},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,aA=="},
                },
            ],
            list,
        ),
    ],
)
def test_litellm_anthropic_tool_result_breakpoint_is_on_result_not_content(
    tool_content: object,
    expected_content_type: type,
) -> None:
    request_messages, request_tools = _cacheable_request(
        model="claude-sonnet-4-5",
        messages=(
            {"role": "system", "content": "System contract."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call-look",
                    "type": "function",
                    "function": {"name": "mcp__blender__look", "arguments": "{}"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call-look",
                "name": "mcp__blender__look",
                "content": tool_content,
            },
        ),
        tools=(_TOOL,),
    )

    tool_message = request_messages[-1]
    assert tool_message["cache_control"] == _CACHE_CONTROL
    assert isinstance(tool_message["content"], expected_content_type)
    assert _count_cache_control(tool_message["content"]) == 0
    assert _count_cache_control(request_messages) + _count_cache_control(request_tools) == 3

    payload = _anthropic_payload(request_messages, request_tools)
    tool_results = _tool_results(payload["messages"])
    assert len(tool_results) == 1
    tool_result = tool_results[0]
    assert tool_result["cache_control"] == _CACHE_CONTROL
    assert _count_cache_control(tool_result["content"]) == 0
    if isinstance(tool_content, list):
        assert any(block.get("type") == "image" for block in tool_result["content"])
    assert _count_cache_control(payload) <= 4


def test_litellm_anthropic_user_message_keeps_content_block_breakpoint() -> None:
    request_messages, request_tools = _cacheable_request(
        model="claude-sonnet-4-5",
        messages=(
            {"role": "system", "content": "System contract."},
            {"role": "user", "content": "What is visible?"},
        ),
        tools=(_TOOL,),
    )

    assert "cache_control" not in request_messages[-1]
    assert request_messages[-1]["content"][-1]["cache_control"] == _CACHE_CONTROL
    assert _count_cache_control(request_messages) + _count_cache_control(request_tools) == 3

    payload = _anthropic_payload(request_messages, request_tools)
    assert _tool_results(payload["messages"]) == []
    assert _count_cache_control(payload) <= 4


def test_unmatched_native_error_uses_generic_agent_error_badge() -> None:
    assert intent_badge(["chat"], ["litellm.BadRequestError: invalid payload"]) == (
        "⚠",
        "agent_error",
    )


@pytest.mark.parametrize("error", ["memory_unavailable", "embedding_failed", "memory_error"])
def test_memory_errors_keep_memory_specific_badges(error: str) -> None:
    assert intent_badge(["memory_recall"], [error]) == ("⚠", error)
