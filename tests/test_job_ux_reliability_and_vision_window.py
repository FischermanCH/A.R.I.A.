from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules.config_ui.intelligence_workbench_routes import _optional_temperature
from aria.modules.chat_history_storage.store import FileChatHistoryStore
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent import handler as native_handler
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _call(call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name="mcp__test__look", arguments="{}"),
    )


def _look_binding(image: str) -> NativeToolBinding:
    async def execute(_context: NativeToolContext, _arguments: object) -> NativeToolResult:
        return NativeToolResult(json.dumps({
            "status": "ok",
            "content": [{"type": "image", "mime_type": "image/png", "omitted": True}],
        }), "look", images=(("image/png", image),))

    return NativeToolBinding(NativeToolContract(
        owner_module_id="mcp", name="mcp__test__look", description="Look.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False,
        source_authority="mcp:test", user_scoped=True,
        rollout_flag="native_agent_mcp_enabled",
    ), execute)


def test_budget_pause_event_key_is_stable_and_notice_claim_is_exactly_once(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="job", user_id="alice", goal="long", status="detached", now=1)
    assert store.set_paused("job", {"step_index": 32, "budget_max_steps": 32}, reason="budget_reached", now=2)
    first = store.get("job")
    assert first is not None
    assert first.event_key == "budget_paused#1"
    assert store.mark_event_notified("job", first.event_key) is True
    for _ in range(5):
        assert store.get("job").event_key == first.event_key  # type: ignore[union-attr]
        assert store.list_for_user("alice")[0].event_key == first.event_key
        assert store.mark_event_notified("job", first.event_key) is False
    assert store.set_paused("job", {"step_index": 32}, reason="budget_reached", now=3) is False
    assert store.get("job").pause_count == 1  # type: ignore[union-attr]


def test_pause_actions_are_atomically_idempotent_per_event(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    state = {"step_index": 32, "budget_max_steps": 32, "budget_max_provider_calls": 32}
    store.create(job_id="job", user_id="alice", goal="long", status="detached")
    assert store.set_paused("job", state, reason="budget_reached")
    event_key = store.get("job").event_key  # type: ignore[union-attr]
    first = store.claim_budget_action(
        "job", user_id="alice", event_key=event_key, action="extend", extension=32, hard_cap=160,
    )
    second = store.claim_budget_action(
        "job", user_id="alice", event_key=event_key, action="extend", extension=32, hard_cap=160,
    )
    third = store.claim_budget_action(
        "job", user_id="alice", event_key=event_key, action="finish", extension=32, hard_cap=160,
    )
    assert first.status == "claimed"
    assert first.state is not None and first.state["budget_max_steps"] == 64
    assert second.status == "already_handled"
    assert third.status == "already_handled"


def test_job_usage_round_trip_accumulates_all_token_classes(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="job", user_id="alice", goal="long")
    store.set_usage("job", {
        "input_tokens": 100, "cache_read_tokens": 80, "cache_write_tokens": 10,
        "output_tokens": 20, "cost_usd": 1.25,
    })
    row = store.get("job")
    assert row is not None
    assert row.usage == {
        "input_tokens": 100, "cache_read_tokens": 80, "cache_write_tokens": 10,
        "output_tokens": 20, "cost_usd": 1.25,
    }
    assert row.as_dict()["usage"]["total_tokens"] == 120


def test_persisted_notice_deduplicates_by_job_and_event_key(tmp_path: Path) -> None:
    history = FileChatHistoryStore(tmp_path / "history", max_messages=80)
    payload = {
        "job_id": "job", "text": "paused", "badge_icon": "⏸",
        "badge_intent": "agent_job_budget_reached", "badge_tokens": 12,
        "badge_cost_usd": "$0.01", "badge_duration": "1.0",
        "event_key": "budget_paused#1",
    }
    history.append_assistant_notice("alice", **payload)
    history.append_assistant_notice("alice", **payload)
    rows = history.load_history("alice")
    assert len(rows) == 1
    assert rows[0]["agent_job_event_key"] == "budget_paused#1"


def test_rolling_image_window_replaces_oldest_and_never_exceeds_four() -> None:
    messages: list[dict] = []
    for index in range(8):
        messages.append({
            "role": "tool", "tool_call_id": str(index), "content": [
                {"type": "text", "text": f"look {index}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{index}"}},
            ],
        })
        native_handler._trim_live_image_window(messages, max_live_images=4)
    rendered = str(messages)
    assert native_handler._live_image_count(messages) == 4
    assert rendered.count("[earlier image replaced to save context]") == 4
    assert all("image_url" not in str(row) for row in messages[:4])


def test_detached_job_can_attach_eight_looks_with_four_live(tmp_path: Path) -> None:
    requests: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        requests.append(copy.deepcopy(kwargs))
        if len(requests) <= 8:
            return _response(tool_calls=(_call(f"look-{len(requests)}"),), finish_reason="tool_use")
        return _response(content="done", finish_reason="stop")

    async def detached() -> bool:
        return True

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Look eight times", user_id="alice", turn_id="vision-window",
        llm_config=LLMConfig(model="claude-sonnet-4-5"),
        tool_bindings=(_look_binding("aA=="),), completion=completion,
        trace_root=tmp_path, detached_check=detached,
        mcp_vision_enabled=True, max_steps=12, max_provider_calls=12,
    ))
    assert outcome.mcp_vision_images == 8
    assert outcome.mcp_vision_live_images == 4
    assert outcome.mcp_vision_replaced_images == 4
    for request in requests[1:9]:
        tool_rows = [row for row in request["messages"] if row.get("role") == "tool"]
        assert any(native_handler._live_image_count([row]) > 0 for row in tool_rows[-1:])
        assert native_handler._live_image_count(request["messages"]) <= 4


def test_truncation_retries_once_then_reports_last_finish_reason(tmp_path: Path) -> None:
    calls: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(finish_reason="max_tokens")
        assert "smaller" in str(kwargs["messages"][-1]["content"]).lower()
        return _response(content="Completed in smaller steps.", finish_reason="stop")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Build it", user_id="alice", turn_id="truncated",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_look_binding("aA=="),), completion=completion,
        trace_root=tmp_path, max_steps=4, max_provider_calls=4, language="de",
    ))
    assert outcome.message == "Completed in smaller steps."
    assert outcome.finish_reason == "stop"
    assert len(calls) == 2


def test_second_truncation_is_honest_and_temperature_empty_is_preserved(tmp_path: Path) -> None:
    async def completion(**_kwargs):  # noqa: ANN202
        return _response(finish_reason="length")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Build it", user_id="alice", turn_id="truncated-twice",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_look_binding("aA=="),), completion=completion,
        trace_root=tmp_path, max_steps=4, max_provider_calls=4, language="de",
    ))
    assert outcome.finish_reason == "length"
    assert "Maximale Ausgabetokens" in outcome.message
    assert _optional_temperature("", default=None) is None
    assert _optional_temperature("0.0", default=None) == 0.0
    assert _optional_temperature(None) is None
