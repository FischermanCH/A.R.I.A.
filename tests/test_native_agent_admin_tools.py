from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.configuration_foundations.config import LLMConfig, Settings
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.sdk import NativeToolBinding, NativeToolContract, NativeToolResult


ADMIN_FLAG = "native_agent_admin_enabled"
ADMIN_TOOL_NAMES = {"admin_update_status", "admin_stats", "admin_activities"}


def _owner() -> SimpleNamespace:
    calls: list[tuple] = []

    async def update_loader():
        calls.append(("update",))
        return {
            "status": "ok", "current_label": "0.1.0-alpha846",
            "latest_label": "0.1.0-alpha846", "update_available": False,
            "checked_at": "2026-09-21T02:00:00+00:00", "token": "UPDATE-SECRET",
        }

    async def stats_loader():
        calls.append(("stats",))
        return {
            "days": 7, "request_count": 12, "model_total_tokens": 345,
            "total_cost_usd": 0.42, "validation_issue_count": 0,
            "dependency_cycle_count": 0, "password": "STATS-SECRET",
        }

    async def activities_loader(kind: str, status: str, limit: int):
        calls.append(("activities", kind, status, limit))
        return {
            "rows": [{
                "timestamp": "2026-09-21T01:00:00+00:00", "kind": "system",
                "status": "ok", "title": "Native read", "intent": "native_agent",
                "duration_ms": 18, "success": True, "token": "ACTIVITY-SECRET",
            }],
            "summary": {"count": 1, "success": 1, "errors": 0, "avg_duration_ms": 18},
            "config": "NEVER-RETURN",
        }

    return SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(), _test_admin_calls=calls,
        _native_agent_update_status_loader=update_loader,
        _native_agent_stats_loader=stats_loader,
        _native_agent_activities_loader=activities_loader,
    )


def _admin_tools(owner: SimpleNamespace) -> dict[str, NativeToolBinding]:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags={ADMIN_FLAG},
    )
    return {tool.contract.name: tool for tool in tools}


@pytest.mark.parametrize("auth_role", ("", "user"))
def test_admin_tools_forbid_non_admin_without_reading_data(auth_role: str) -> None:
    owner = _owner()
    tools = _admin_tools(owner)
    assert set(tools) == ADMIN_TOOL_NAMES
    for name, arguments in (
        ("admin_update_status", {}),
        ("admin_stats", {}),
        ("admin_activities", {"kind": "all", "status": "all", "limit": 10}),
    ):
        result = asyncio.run(tools[name].handler(SimpleNamespace(user_id="u1", auth_role=auth_role), arguments))
        payload = json.loads(result.content)
        assert payload == {
            "effect": "read_only", "message": "Administrator access is required.",
            "status": "forbidden_admin_only",
        }
    assert owner._test_admin_calls == []


def test_admin_tools_return_only_fresh_allowlisted_fields() -> None:
    owner = _owner()
    tools = _admin_tools(owner)
    context = SimpleNamespace(user_id="u1", auth_role="admin")

    update = json.loads(asyncio.run(tools["admin_update_status"].handler(context, {})).content)
    stats = json.loads(asyncio.run(tools["admin_stats"].handler(context, {})).content)
    activities = json.loads(asyncio.run(tools["admin_activities"].handler(
        context, {"kind": "system", "status": "ok", "limit": 10},
    )).content)

    assert update == {"status": "ok", "effect": "read_only", "update": {
        "current_label": "0.1.0-alpha846", "available_label": "0.1.0-alpha846",
        "update_available": False, "checked_at": "2026-09-21T02:00:00+00:00",
    }}
    assert stats == {"status": "ok", "effect": "read_only", "stats": {
        "days": 7, "request_count": 12, "model_total_tokens": 345,
        "total_cost_usd": 0.42, "validation_issue_count": 0,
        "dependency_cycle_count": 0,
    }}
    assert activities == {"status": "ok", "effect": "read_only", "activities": {
        "rows": [{
            "timestamp": "2026-09-21T01:00:00+00:00", "kind": "system", "status": "ok",
            "title": "Native read", "intent": "native_agent", "duration_ms": 18,
            "success": True,
        }],
        "summary": {"count": 1, "success": 1, "errors": 0, "avg_duration_ms": 18},
        "returned_count": 1, "limit": 10, "truncated": False,
    }}
    combined = json.dumps((update, stats, activities))
    assert "UPDATE-SECRET" not in combined and "STATS-SECRET" not in combined
    assert "ACTIVITY-SECRET" not in combined and '"password"' not in combined and '"token"' not in combined
    assert owner._test_admin_calls == [("update",), ("stats",), ("activities", "system", "ok", 10)]


@pytest.mark.parametrize("tool_name", ADMIN_TOOL_NAMES)
@pytest.mark.parametrize("field", ("role", "auth_role", "admin"))
def test_admin_role_is_not_model_controllable(tool_name: str, field: str) -> None:
    owner = _owner()
    tool = _admin_tools(owner)[tool_name]
    with pytest.raises(ValueError, match="arguments_invalid"):
        asyncio.run(tool.handler(SimpleNamespace(user_id="u1", auth_role=""), {field: "admin"}))
    assert owner._test_admin_calls == []


def test_admin_rollout_flag_is_independent_and_registry_has_23_read_only_tools() -> None:
    owner = _owner()
    without_admin = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )
    with_admin = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={
            "native_agent_memory_enabled", "native_agent_connections_enabled", ADMIN_FLAG,
        },
    )
    assert not ADMIN_TOOL_NAMES.intersection(tool.contract.name for tool in without_admin)
    assert len(with_admin) == 23
    assert ADMIN_TOOL_NAMES.issubset(tool.contract.name for tool in with_admin)
    assert all(tool.contract.effect == "read_only" for tool in with_admin)
    assert all(tool.contract.confirmation_required is False for tool in with_admin)
    assert asyncio.run(select_relevant_native_tools("diagnostic", with_admin, selector=None)) == with_admin


def test_native_agent_binds_auth_role_into_tool_context(tmp_path) -> None:  # noqa: ANN001
    seen: list[tuple[str, str]] = []

    async def handler(context, arguments):  # noqa: ANN001
        assert arguments == {}
        seen.append((context.user_id, context.auth_role))
        return NativeToolResult('{"status":"ok"}', "admin_stats")

    binding = NativeToolBinding(contract=NativeToolContract(
        owner_module_id="stats_ui", name="admin_stats", description="test",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="stats:usage_readmodel",
        user_scoped=False, rollout_flag=ADMIN_FLAG,
    ), handler=handler)
    responses = iter((
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=[SimpleNamespace(
                id="call-1", function=SimpleNamespace(name="admin_stats", arguments="{}"),
            )],
        ), finish_reason="tool_use")]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="Admin stats ready.", tool_calls=[],
        ), finish_reason="stop")]),
    ))

    async def completion(**_kwargs):
        return next(responses)

    outcome = asyncio.run(run_native_agent_turn(
        message="show diagnostics", user_id="u1", auth_role="admin", turn_id="admin-role",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert seen == [("u1", "admin")]


def test_pipeline_and_bridge_thread_admin_role_to_owner_tool(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    settings = Settings.model_validate({
        "llm": {"model": "fake"}, "memory": {"enabled": False},
        "agentic_loop": {"enabled": True, "native_agent_admin_enabled": True},
        "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
    })
    pipeline = Pipeline(
        settings=settings, prompt_loader=SimpleNamespace(get_persona=lambda: "ARIA"),
        llm_client=SimpleNamespace(),
    )
    calls: list[str] = []

    async def stats_loader():
        calls.append("stats")
        return {
            "days": 7, "request_count": 1, "model_total_tokens": 2,
            "total_cost_usd": 0.0, "validation_issue_count": 0,
            "dependency_cycle_count": 0,
        }

    pipeline._native_agent_stats_loader = stats_loader
    responses = iter((
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=[SimpleNamespace(
                id="call-1", function=SimpleNamespace(name="admin_stats", arguments="{}"),
            )],
        ), finish_reason="tool_use")]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="Admin stats ready.", tool_calls=[],
        ), finish_reason="stop")]),
    ))

    async def completion(**_kwargs):
        return next(responses)

    pipeline._native_agent_completion = completion
    result = asyncio.run(pipeline.process(
        "show diagnostics", user_id="u1", auth_role="admin", source="test",
    ))
    assert result is not None and result.text == "Admin stats ready."
    assert calls == ["stats"]
