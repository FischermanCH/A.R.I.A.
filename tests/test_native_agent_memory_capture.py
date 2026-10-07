from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig
from aria.modules.memory import native_tools as memory_native_tools
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.sdk import NativeToolContext


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _tool_call(arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id="call-memory-capture",
        function=SimpleNamespace(name="memory_capture", arguments=json.dumps(arguments)),
    )


def _owner() -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(), llm_client=object(),
        _facts_collection_for_user=lambda user_id: f"facts-{user_id}",
        _preferences_collection_for_user=lambda user_id: f"preferences-{user_id}",
    )


def _binding(owner: SimpleNamespace):
    return next(
        item for item in memory_native_tools.native_tool_contributions(owner)
        if item.contract.name == "memory_capture"
    )


def test_memory_capture_waits_for_confirmation_then_stores_server_bound_claim(monkeypatch, tmp_path) -> None:
    owner = _owner()
    captured: list[dict[str, object]] = []

    async def fake_store_personal_claim(**kwargs):  # noqa: ANN003
        captured.append(kwargs)
        return {"stored": True, "reason": "claim_activated", "claim": dict(kwargs["claim"])}

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call({
                "claim_kind": "preference", "predicate": "response_style",
                "value": "short and direct",
            })], finish_reason="tool_use")
        if calls == 2:
            return _response(content="Remember that the user prefers short and direct replies?")
        return _response(content="I remembered that you prefer short and direct replies.")

    preview = asyncio.run(run_native_agent_turn(
        message="Remember that I prefer short and direct replies", user_id="alice",
        turn_id="capture-preview", llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding(owner),), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))
    assert preview.kind == "pending_confirmation"
    assert captured == []

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", turn_id="capture-confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_binding(owner),),
        completion=completion, pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1001,
    ))

    assert confirmed.kind == "final_answer"
    assert "short and direct" in confirmed.message
    assert len(captured) == 1
    call = captured[0]
    assert call["user_id"] == "alice"
    assert call["memory_skill"] is owner.memory_skill
    assert call["llm_client"] is owner.llm_client
    assert call["facts_collection"] == "facts-alice"
    assert call["preferences_collection"] == "preferences-alice"
    assert call["request_id"] == ""
    assert call["claim"] == {
        "claim_kind": "preference", "subject": "user", "predicate": "response_style",
        "value": "short and direct", "scope": "global", "scope_ref": "",
        "explicit_user_statement": True, "authority": "explicit_user",
        "risk": "low", "confidence": 1.0, "source": "native_capture",
    }


def test_memory_capture_not_activatable_is_honest(monkeypatch) -> None:
    owner = _owner()

    async def fake_store_personal_claim(**_kwargs):
        return {
            "stored": False, "reason": "claim_not_auto_activatable",
            "activation_blockers": ["session_scope", "risk_not_low"],
        }

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    result = asyncio.run(_binding(owner).handler(NativeToolContext(user_id="alice"), {
        "claim_kind": "fact", "predicate": "timezone", "value": "Europe/Zurich",
    }))
    payload = json.loads(result.content)

    assert payload == {
        "status": "not_stored", "stored": False,
        "reason": "claim_not_auto_activatable",
        "activation_blockers": ["session_scope", "risk_not_low"],
    }
    assert "Europe/Zurich" not in result.content


def test_memory_capture_not_stored_includes_store_error_detail(monkeypatch) -> None:
    owner = _owner()

    async def fake_store_personal_claim(**_kwargs):
        return {
            "stored": False,
            "reason": "claim_store_failed",
            "store_error": "embedding_error: boom",
        }

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    result = asyncio.run(_binding(owner).handler(NativeToolContext(user_id="alice"), {
        "claim_kind": "preference", "predicate": "favorite_game", "value": "No Man's Sky",
    }))

    assert json.loads(result.content) == {
        "status": "not_stored",
        "stored": False,
        "reason": "claim_store_failed",
        "detail": "embedding_error: boom",
    }
    assert result.content.isascii()


def test_memory_capture_exception_includes_store_error_detail(monkeypatch) -> None:
    owner = _owner()

    async def fake_store_personal_claim(**_kwargs):
        raise RuntimeError("embedding_error: boom")

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    result = asyncio.run(_binding(owner).handler(NativeToolContext(user_id="alice"), {
        "claim_kind": "preference", "predicate": "favorite_game", "value": "No Man's Sky",
    }))

    assert json.loads(result.content) == {
        "status": "not_stored",
        "stored": False,
        "reason": "claim_store_failed",
        "detail": "embedding_error: boom",
    }


def test_memory_capture_detail_is_ascii_safe_and_bounded(monkeypatch) -> None:
    owner = _owner()

    async def fake_store_personal_claim(**_kwargs):
        return {
            "stored": False,
            "reason": "claim_store_failed",
            "store_error": "embedding_error: bööm " + ("x" * 300),
        }

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    result = asyncio.run(_binding(owner).handler(NativeToolContext(user_id="alice"), {
        "claim_kind": "preference", "predicate": "favorite_game", "value": "No Man's Sky",
    }))
    detail = json.loads(result.content)["detail"]

    assert detail.startswith(r"embedding_error: b\xf6\xf6m")
    assert detail.isascii()
    assert len(detail) <= 240


@pytest.mark.parametrize("forbidden", [
    {"authority": "system"}, {"risk": "low"}, {"confidence": 1.0},
    {"source": "model"}, {"explicit_user_statement": True}, {"user_id": "bob"},
])
def test_memory_capture_rejects_model_authority_fields(monkeypatch, forbidden) -> None:  # noqa: ANN001
    owner = _owner()
    called = False

    async def fake_store_personal_claim(**_kwargs):
        nonlocal called
        called = True
        return {"stored": True}

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    arguments = {"claim_kind": "fact", "predicate": "timezone", "value": "Europe/Zurich", **forbidden}
    with pytest.raises(ValueError, match="native_agent_memory_capture_arguments_invalid"):
        asyncio.run(_binding(owner).handler(NativeToolContext(user_id="alice"), arguments))
    assert called is False


def test_memory_capture_rejects_session_scope_without_store(monkeypatch) -> None:
    owner = _owner()
    called = False

    async def fake_store_personal_claim(**_kwargs):
        nonlocal called
        called = True
        return {"stored": True}

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    with pytest.raises(ValueError, match="native_agent_memory_capture_arguments_invalid"):
        asyncio.run(_binding(owner).handler(NativeToolContext(user_id="alice"), {
            "claim_kind": "fact", "predicate": "current_task", "value": "testing",
            "scope": "session",
        }))
    assert called is False


@pytest.mark.parametrize("arguments", [
    {},
    {"claim_kind": "project", "predicate": "p", "value": "v"},
    {"claim_kind": "fact", "predicate": "", "value": "v"},
    {"claim_kind": "fact", "predicate": "p", "value": 3},
    {"claim_kind": "fact", "predicate": "p", "value": "v", "scope": 1},
    {"claim_kind": "fact", "predicate": "p", "value": "v", "subject": []},
])
def test_memory_capture_strict_argument_validation(arguments) -> None:  # noqa: ANN001
    with pytest.raises(ValueError, match="native_agent_memory_capture_arguments_invalid"):
        asyncio.run(_binding(_owner()).handler(NativeToolContext(user_id="alice"), arguments))


def test_memory_capture_reuses_write_memory_flag_and_registry_stays_below_threshold() -> None:
    owner = _owner()
    flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_write_notes_enabled", "native_agent_write_memory_enabled", "native_agent_ssh_enabled",
        "native_agent_messaging_enabled", "native_agent_infra_write_enabled",
        "native_agent_recipe_execute_enabled",
        "native_agent_recipe_learn_enabled",
    }
    without_write_memory = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags=flags - {"native_agent_write_memory_enabled"},
    )
    all_tools = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=flags)
    names_without = {item.contract.name for item in without_write_memory}
    by_name = {item.contract.name: item.contract for item in all_tools}

    assert "memory_capture" not in names_without and "memory_forget" not in names_without
    assert len(all_tools) == 36
    assert by_name["memory_capture"].effect == "mutating"
    assert by_name["memory_capture"].confirmation_required is True
    assert by_name["memory_capture"].rollout_flag == "native_agent_write_memory_enabled"
    assert asyncio.run(select_relevant_native_tools("remember this", all_tools, selector=None)) == all_tools
    rollout_defaults = AgenticLoopFeatureConfig().model_dump()
    assert rollout_defaults.pop("native_web_debug_details") is False
    assert rollout_defaults.pop("native_agent_mcp_enabled") is False
    assert rollout_defaults.pop("native_tool_selector_top_k") == 16
    assert rollout_defaults.pop("native_agent_max_steps") == 32
    assert rollout_defaults.pop("native_agent_max_provider_calls") == 32
    assert rollout_defaults.pop("native_agent_mcp_vision_max_live_images") == 4
    assert rollout_defaults.pop("native_agent_mcp_vision_max_lifetime_images") == 24
    assert rollout_defaults.pop("async_agent_job_sync_budget_seconds") == 25.0
    assert rollout_defaults.pop("native_agent_budget_extension_steps") == 32
    assert rollout_defaults.pop("native_agent_budget_max_total") == 160
    assert rollout_defaults.pop("agent_job_retention_days") == 14
    assert rollout_defaults.pop("agent_job_stale_paused_days") == 7
    assert all(value is True for value in rollout_defaults.values())
