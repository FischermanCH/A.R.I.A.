from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent.handler import _cacheable_request, run_native_agent_turn
from aria.modules.native_agent.pipeline_bridge import _native_llm_timing_detail_line
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _binding(name: str = "read_test", *, mutating: bool = False) -> NativeToolBinding:
    async def handler(_context: NativeToolContext, _arguments):  # noqa: ANN001
        return NativeToolResult('{"status":"ok"}', "test.read")

    return NativeToolBinding(NativeToolContract(
        owner_module_id="test", name=name, description="Read test data.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="mutating" if mutating else "read_only", confirmation_required=mutating,
        source_authority="test:store", user_scoped=True, rollout_flag="test_enabled",
    ), handler)


def _response(*, content: str = "ok", usage=None):  # noqa: ANN001
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=[]), finish_reason="stop",
        )],
        usage=usage,
    )


def _cache_breakpoint_count(value) -> int:  # noqa: ANN001
    if isinstance(value, dict):
        return int("cache_control" in value) + sum(
            _cache_breakpoint_count(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return sum(_cache_breakpoint_count(item) for item in value)
    return 0


def test_anthropic_request_caches_system_tool_and_incremental_message_prefix(tmp_path: Path) -> None:
    calls: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003
        calls.append(kwargs)
        return _response()

    outcome = asyncio.run(run_native_agent_turn(
        message="Current question", user_id="u1", turn_id="cache-anthropic",
        llm_config=LLMConfig(model="claude-sonnet-4-5"),
        tool_bindings=(_binding("first"), _binding("last")), completion=completion,
        recent_history=[
            {"role": "user", "text": "Earlier question"},
            {"role": "assistant", "text": "Earlier answer"},
        ],
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    request = calls[0]
    assert request["messages"][0]["content"][0]["type"] == "text"
    assert request["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert request["messages"][1] == {"role": "user", "content": "Earlier question"}
    assert request["messages"][2] == {"role": "assistant", "content": "Earlier answer"}
    assert request["messages"][-1]["role"] == "user"
    assert request["messages"][-1]["content"] == [{
        "type": "text", "text": "Current question",
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }]
    assert "cache_control" not in request["tools"][0]
    assert request["tools"][-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert _cache_breakpoint_count(request["messages"]) + _cache_breakpoint_count(request["tools"]) == 3


def test_non_anthropic_request_is_cache_metadata_noop(tmp_path: Path) -> None:
    calls: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003
        calls.append(kwargs)
        return _response()

    asyncio.run(run_native_agent_turn(
        message="Hello", user_id="u1", turn_id="cache-noop",
        llm_config=LLMConfig(model="gpt-test"), tool_bindings=(_binding(),),
        completion=completion, trace_root=tmp_path,
    ))

    assert isinstance(calls[0]["messages"][0]["content"], str)
    assert "cache_control" not in calls[0]["tools"][-1]
    assert _cache_breakpoint_count(calls[0]["messages"]) == 0
    assert _cache_breakpoint_count(calls[0]["tools"]) == 0


def test_anthropic_system_only_does_not_gain_duplicate_message_breakpoint() -> None:
    messages, tools = _cacheable_request(
        model="anthropic/claude-sonnet-4-5",
        messages=({"role": "system", "content": "System contract"},),
        tools=None,
    )

    assert tools is None
    assert messages == [{
        "role": "system",
        "content": [{
            "type": "text", "text": "System contract",
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
    }]
    assert _cache_breakpoint_count(messages) == 1


def test_anthropic_structured_last_message_preserves_blocks_and_annotates_only_last() -> None:
    original_messages = (
        {"role": "system", "content": "System contract"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "First block"},
            {"type": "text", "text": "Last block"},
        ]},
    )
    messages, _tools = _cacheable_request(
        model="claude-sonnet-4-5", messages=original_messages, tools=(),
    )

    assert messages[-1]["content"][0] == {"type": "text", "text": "First block"}
    assert messages[-1]["content"][1] == {
        "type": "text", "text": "Last block",
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }
    assert original_messages[-1]["content"][-1] == {"type": "text", "text": "Last block"}
    assert _cache_breakpoint_count(messages) == 2


def test_anthropic_second_loop_call_caches_prior_tool_result_prefix(tmp_path: Path) -> None:
    calls: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003
        calls.append(kwargs)
        if len(calls) == 1:
            tool_call = SimpleNamespace(
                id="call-read", function=SimpleNamespace(name="read_test", arguments="{}"),
            )
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[tool_call]), finish_reason="tool_use",
            )])
        return _response(
            content="Done from the Tool observation.",
            usage=SimpleNamespace(
                prompt_tokens=32, completion_tokens=4,
                cache_read_input_tokens=24, cache_creation_input_tokens=0,
            ),
        )

    outcome = asyncio.run(run_native_agent_turn(
        message="Read it", user_id="u1", turn_id="cache-second-loop",
        llm_config=LLMConfig(model="anthropic/claude-sonnet-4-5"),
        tool_bindings=(_binding(),), completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "tool"
    assert calls[1]["messages"][-1]["content"] == '{"status":"ok"}'
    assert calls[1]["messages"][-1]["cache_control"] == {
        "type": "ephemeral", "ttl": "1h",
    }
    assert _cache_breakpoint_count(calls[1]["messages"]) == 2
    assert _cache_breakpoint_count(calls[1]["tools"]) == 1
    assert outcome.llm_calls[-1].cache_read_input_tokens == 24


def test_native_llm_timing_details_include_cache_usage_without_secrets(tmp_path: Path) -> None:
    usage = SimpleNamespace(
        prompt_tokens=15000, completion_tokens=12, total_tokens=15012,
        cache_read_input_tokens=14000, cache_creation_input_tokens=900,
        prompt_tokens_details=SimpleNamespace(cached_tokens=14000),
    )

    async def completion(**_kwargs):
        return _response(usage=usage)

    outcome = asyncio.run(run_native_agent_turn(
        message="Hello", user_id="u1", turn_id="cache-metrics",
        llm_config=LLMConfig(model="claude-sonnet-4-5", api_key="never-log-this"),
        tool_bindings=(_binding(),), completion=completion, trace_root=tmp_path,
    ))
    line = _native_llm_timing_detail_line(outcome)

    assert "calls=1" in line
    assert "per_call_ms=[" in line
    assert "cache_read=14000" in line
    assert "cache_write=900" in line
    assert "tools=1" in line
    assert "input_tokens=15000" in line
    assert "never-log-this" not in line


def test_anthropic_preview_phrasing_caches_its_static_system_text(tmp_path: Path) -> None:
    from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
    from aria.modules.native_agent.pending_store import NativePendingStore

    calls: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003
        calls.append(kwargs)
        if len(calls) == 1:
            tool_call = SimpleNamespace(
                id="call-write",
                function=SimpleNamespace(name="write_test", arguments=json.dumps({})),
            )
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[tool_call]), finish_reason="tool_use",
            )])
        return _response(content="Please confirm the write.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Write it", user_id="u1", turn_id="cache-preview",
        llm_config=LLMConfig(model="anthropic/claude-sonnet-4-5"),
        tool_bindings=(_binding("write_test", mutating=True),), completion=completion,
        pending_store=NativePendingStore(tmp_path / "pending.sqlite3"),
        confirmation_ledger=ActionConfirmationLedger(tmp_path / "ledger.sqlite3"),
        trace_root=tmp_path,
    ))

    assert outcome.kind == "pending_confirmation"
    assert calls[1]["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert calls[1]["messages"][-1]["content"][-1]["cache_control"] == {
        "type": "ephemeral", "ttl": "1h",
    }
    assert _cache_breakpoint_count(calls[1]["messages"]) == 2
    assert [metric.operation for metric in outcome.llm_calls] == ["loop", "preview"]
