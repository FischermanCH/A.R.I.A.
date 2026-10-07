from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.pipeline_bridge import native_agent_enabled
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.recipe_runtime.native_tools import native_tool_contributions
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult
from aria.modules.ssh_runtime.native_tools import native_tool_contributions as ssh_tool_contributions
from aria.modules.skill_contracts.contracts import SkillResult


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _tool_call(name: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{name}", function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _recipe(
    recipe_id: str = "daily-health",
    *,
    name: str = "Daily health",
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "id": recipe_id, "name": name, "description": "Checks systems",
        "enabled": enabled, "steps": [{"id": "ssh", "type": "ssh", "params": {}}],
    }


def _bound_recipe() -> dict[str, object]:
    return {
        "id": "fleet", "name": "Fleet check", "description": "Checks every SSH profile",
        "enabled": True,
        "steps": [{
            "id": "check", "type": "ssh_run", "on_error": "stop",
            "params": {"connection_kind": "ssh", "binding": "all", "command": "uptime"},
        }],
    }


def _owner(*, recipes=None, result: SkillResult | None = None, error: Exception | None = None,
           ssh_refs=(), connection_refs=None) -> SimpleNamespace:  # noqa: ANN001
    rows = list(recipes if recipes is not None else [_recipe()])
    calls: list[dict[str, object]] = []

    async def execute(recipe_id: str, message: str, *, runtime_recipes, language: str, user_id: str):  # noqa: ANN001
        calls.append({
            "recipe_id": recipe_id, "message": message,
            "runtime_recipes": runtime_recipes, "language": language, "user_id": user_id,
        })
        if error:
            raise error
        return result or SkillResult(skill_name=f"recipe_{recipe_id}", content="Recipe completed.", success=True)

    refs_by_kind = {"ssh": tuple(ssh_refs), **dict(connection_refs or {})}
    return SimpleNamespace(
        settings=SimpleNamespace(connections=SimpleNamespace(**{
            kind: {ref: object() for ref in refs}
            for kind, refs in refs_by_kind.items()
        })), _load_stored_recipe_runtime=lambda: rows,
        _execute_recipe_by_id=execute, _test_recipe_calls=calls,
    )


def _binding(owner: SimpleNamespace, name: str = "recipes_execute"):
    return next(item for item in native_tool_contributions(owner) if item.contract.name == name)


def _execute_payload(owner: SimpleNamespace, identifier: str) -> dict[str, object]:
    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": identifier},
    ))
    try:
        return json.loads(result.content)
    except json.JSONDecodeError:
        if not owner._test_recipe_calls:
            return {"status": "recipe_not_found", "content": result.content}
        return {
            "status": "ok", "content": result.content,
            "recipe_id": owner._test_recipe_calls[-1]["recipe_id"],
        }


def _procedure_binding(
    name: str, *, effect: str, confirmation_required: bool, handler,
) -> NativeToolBinding:  # noqa: ANN001
    schema_properties = {
        "recipe_id": {"type": "string"},
    } if name == "recipes_execute" else {
        "command": {"type": "string"}, "targets": {"type": "array", "items": {"type": "string"}},
    } if name == "ssh_command" else {}
    required = ["recipe_id"] if name == "recipes_execute" else ["command", "targets"] if name == "ssh_command" else []
    return NativeToolBinding(NativeToolContract(
        owner_module_id="test", name=name, description=f"Test binding for {name}.",
        input_schema={"type": "object", "properties": schema_properties, "required": required},
        effect=effect, confirmation_required=confirmation_required,
        source_authority=f"test:{name}", user_scoped=True, rollout_flag="test_enabled",
    ), handler)


def test_mutating_maintenance_intent_discovers_recipe_before_execution(tmp_path) -> None:
    inventory_calls = 0

    async def inventory_handler(_context, _arguments):  # noqa: ANN001
        nonlocal inventory_calls
        inventory_calls += 1
        return NativeToolResult(
            '{"recipes":[{"id":"ssh-update-example-host-01","name":"SSH Update example-host-01"}]}',
            "recipes_inventory",
        )

    async def unused_handler(_context, _arguments):  # noqa: ANN001
        raise AssertionError("confirmation-required tools must not execute before confirmation")

    bindings = (
        _procedure_binding("recipes_inventory", effect="read_only", confirmation_required=False, handler=inventory_handler),
        _procedure_binding("recipes_execute", effect="mutating", confirmation_required=True, handler=unused_handler),
        _procedure_binding("ssh_command", effect="mutating", confirmation_required=True, handler=unused_handler),
    )
    calls = 0

    async def completion(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            prompt = str(kwargs["messages"][0]["content"])
            procedure_ready = (
                "MUST call recipes_inventory first" in prompt
                and "matching active Recipe" in prompt
                and "only as a last resort" in prompt
                and "does not literally dictate a concrete one-off command" in prompt
            )
            if procedure_ready:
                return _response(tool_calls=[_tool_call("recipes_inventory", {})], finish_reason="tool_use")
            return _response(tool_calls=[_tool_call("ssh_command", {
                "command": "sudo apt update && sudo apt upgrade -y", "targets": ["example-host-01"],
            })], finish_reason="tool_use")
        if calls == 2 and inventory_calls:
            return _response(tool_calls=[_tool_call(
                "recipes_execute", {"recipe_id": "ssh-update-example-host-01"},
            )], finish_reason="tool_use")
        return _response(content="Please confirm the matching stored Recipe.")

    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    outcome = asyncio.run(run_native_agent_turn(
        message="mach ein update auf example-host-01", user_id="alice", auth_role="admin",
        turn_id="mutating-intent-recipe-discovery", llm_config=LLMConfig(model="fake"),
        tool_bindings=bindings, completion=completion, pending_store=pending_store,
        confirmation_ledger=ActionConfirmationLedger(tmp_path / "ledger.sqlite3"),
        trace_root=tmp_path / "trace",
    ))

    pending = pending_store.peek(user_id="alice", token=outcome.confirmation_token)
    assert outcome.kind == "pending_confirmation"
    assert inventory_calls == 1
    assert pending is not None and pending.tool_name == "recipes_execute"


def test_mutating_maintenance_intent_allows_guarded_adhoc_fallback_after_empty_inventory(tmp_path) -> None:
    inventory_calls = 0

    async def inventory_handler(_context, _arguments):  # noqa: ANN001
        nonlocal inventory_calls
        inventory_calls += 1
        return NativeToolResult('{"recipes":[]}', "recipes_inventory")

    async def unused_handler(_context, _arguments):  # noqa: ANN001
        raise AssertionError("confirmation-required tools must not execute before confirmation")

    bindings = (
        _procedure_binding("recipes_inventory", effect="read_only", confirmation_required=False, handler=inventory_handler),
        _procedure_binding("ssh_command", effect="mutating", confirmation_required=True, handler=unused_handler),
    )
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call("recipes_inventory", {})], finish_reason="tool_use")
        if calls == 2:
            return _response(tool_calls=[_tool_call("ssh_command", {
                "command": "sudo apt update && sudo apt upgrade -y", "targets": ["example-host-01"],
            })], finish_reason="tool_use")
        return _response(content="No Recipe matched; confirm the guarded one-off command.")

    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    outcome = asyncio.run(run_native_agent_turn(
        message="mach ein update auf example-host-01", user_id="alice", auth_role="admin",
        turn_id="mutating-intent-adhoc-fallback", llm_config=LLMConfig(model="fake"),
        tool_bindings=bindings, completion=completion, pending_store=pending_store,
        confirmation_ledger=ActionConfirmationLedger(tmp_path / "ledger.sqlite3"),
        trace_root=tmp_path / "trace",
    ))

    pending = pending_store.peek(user_id="alice", token=outcome.confirmation_token)
    assert outcome.kind == "pending_confirmation"
    assert inventory_calls == 1
    assert pending is not None and pending.tool_name == "ssh_command"


def test_named_recipe_model_contract_prefers_recipe_execute_over_adhoc_ssh(tmp_path) -> None:
    recipe_owner = _owner(recipes=[_recipe(
        "ssh-update-example-host-01", name="SSH Update example-host-01",
    )], ssh_refs=("example-host-01",))
    ssh_owner = SimpleNamespace(
        settings=recipe_owner.settings,
        _ssh_runtime=SimpleNamespace(),
    )
    recipe_binding = _binding(recipe_owner)
    ssh_bindings = tuple(ssh_tool_contributions(ssh_owner))
    bindings = (recipe_binding, *ssh_bindings)
    calls = 0

    async def completion(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            prompt = str(kwargs["messages"][0]["content"])
            descriptions = {
                item["name"]: item["description"] for item in kwargs["tools"]
            }
            contract_ready = (
                "stored Recipe by name or intent" in prompt
                and "not reconstruct its actions" in prompt
                and "one-off ad-hoc commands" in descriptions["ssh_command"]
                and "stored Recipe" in descriptions["ssh_command"]
                and "stored Recipe" in descriptions["ssh_read"]
                and "stored recipe by name or intent" in descriptions["recipes_execute"]
            )
            if contract_ready:
                return _response(tool_calls=[_tool_call(
                    "recipes_execute", {"recipe_id": "SSH Update example-host-01"},
                )], finish_reason="tool_use")
            return _response(tool_calls=[_tool_call(
                "ssh_command", {
                    "command": "apt-get update && apt-get upgrade -y",
                    "targets": ["example-host-01"],
                },
            )], finish_reason="tool_use")
        return _response(content="Please confirm the stored Recipe execution.")

    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    outcome = asyncio.run(run_native_agent_turn(
        message="fuehre SSH Update example-host-01 aus",
        user_id="alice", auth_role="admin", turn_id="recipe-priority",
        llm_config=LLMConfig(model="fake"), tool_bindings=bindings,
        completion=completion,
        pending_store=pending_store,
        confirmation_ledger=ActionConfirmationLedger(tmp_path / "ledger.sqlite3"),
        trace_root=tmp_path / "trace",
    ))

    assert outcome.kind == "pending_confirmation"
    pending = pending_store.peek(
        user_id="alice", token=outcome.confirmation_token,
    )
    assert pending is not None
    assert pending.tool_name == "recipes_execute"


def test_recipe_execute_resolves_exact_name_to_canonical_id() -> None:
    item = _recipe("linux-updates-check-template", name="Linux Updates Check Template")
    owner = _owner(recipes=[item])

    payload = _execute_payload(owner, "Linux Updates Check Template")

    assert payload["status"] == "ok"
    assert payload["recipe_id"] == "linux-updates-check-template"
    assert owner._test_recipe_calls == [{
        "recipe_id": "linux-updates-check-template", "message": "",
        "runtime_recipes": [item], "language": "de", "user_id": "alice",
    }]


def test_recipe_execute_exact_id_is_unchanged() -> None:
    owner = _owner(recipes=[_recipe(
        "linux-updates-check-template", name="Linux Updates Check Template",
    )])

    payload = _execute_payload(owner, "linux-updates-check-template")

    assert payload["status"] == "ok"
    assert owner._test_recipe_calls[0]["recipe_id"] == "linux-updates-check-template"


def test_recipe_execute_relays_readable_direct_chat_text_without_json_envelope() -> None:
    readable = "System overview:\n- srv-a: healthy\n- srv-b: updates pending"
    owner = _owner(result=SkillResult(
        skill_name="recipe_daily-health",
        content="Technical execution dump",
        success=True,
        metadata={"direct_chat_text": readable},
    ))

    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "daily-health"},
    ))

    assert result.content == readable
    assert "\n" in result.content
    assert not result.content.lstrip().startswith("{")


def test_recipe_execute_exposes_safe_activity_name_and_resolved_targets() -> None:
    owner = _owner(recipes=[_bound_recipe()], ssh_refs=("srv-a", "srv-b"))

    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "fleet"},
    ))

    assert result.activity == {
        "title": "Fleet check", "target": "srv-a, srv-b", "success": True,
    }


def test_recipe_execute_name_match_is_case_insensitive() -> None:
    owner = _owner(recipes=[_recipe(
        "linux-updates-check-template", name="Linux Updates Check Template",
    )])

    payload = _execute_payload(owner, "lInUx UpDaTeS cHeCk TeMpLaTe")

    assert payload["status"] == "ok"
    assert owner._test_recipe_calls[0]["recipe_id"] == "linux-updates-check-template"


def test_recipe_execute_ambiguous_exact_name_does_not_execute() -> None:
    owner = _owner(recipes=[
        _recipe("linux-a", name="Linux Updates Check Template"),
        _recipe("linux-b", name="linux updates check template"),
    ])

    payload = _execute_payload(owner, "Linux Updates Check Template")

    assert payload["status"] == "recipe_not_found"
    assert owner._test_recipe_calls == []


def test_recipe_execute_disabled_exact_name_does_not_match() -> None:
    owner = _owner(recipes=[_recipe(
        "linux-updates-check-template", name="Linux Updates Check Template", enabled=False,
    )])

    payload = _execute_payload(owner, "Linux Updates Check Template")

    assert payload["status"] == "recipe_not_found"
    assert owner._test_recipe_calls == []


def test_recipe_execute_does_not_match_name_substrings() -> None:
    owner = _owner(recipes=[_recipe(
        "linux-updates-check-template", name="Linux Updates Check Template",
    )])

    payload = _execute_payload(owner, "Linux Updates")

    assert payload["status"] == "recipe_not_found"
    assert owner._test_recipe_calls == []


@pytest.mark.parametrize("tool_name,result_key", [
    ("recipes_explain", "recipe"),
    ("recipes_preview", "preview"),
])
def test_recipe_read_tools_share_exact_name_resolution(tool_name: str, result_key: str) -> None:
    owner = _owner(recipes=[_recipe(
        "linux-updates-check-template", name="Linux Updates Check Template",
    )])
    result = asyncio.run(_binding(owner, tool_name).handler(
        NativeToolContext(user_id="alice", auth_role="admin"),
        {"recipe_id": "linux updates check template"},
    ))

    payload = json.loads(result.content)
    assert payload["status"] == "ok"
    assert payload[result_key]["id"] == "linux-updates-check-template"


def test_recipe_execute_waits_for_confirmation_then_uses_legacy_engine(tmp_path) -> None:
    recipe_summary = "Host summary:\n- srv-a: healthy\n- srv-b: updates pending"
    owner = _owner(result=SkillResult(
        skill_name="recipe_daily-health", content=recipe_summary, success=True,
    ))
    binding = _binding(owner)
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=[_tool_call("recipes_execute", {
                "recipe_id": "daily-health",
            })], finish_reason="tool_use")
        if calls == 2:
            return _response(content="Run daily-health?")
        raise AssertionError("recipes_execute result must be relayed without a phrasing call")

    preview = asyncio.run(run_native_agent_turn(
        message="Run daily-health", user_id="alice", auth_role="admin", turn_id="preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))
    assert preview.kind == "pending_confirmation"
    assert owner._test_recipe_calls == []

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", auth_role="admin", turn_id="confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger,
        confirmation_token=preview.confirmation_token, now=1001,
    ))
    assert confirmed.kind == "final_answer"
    assert confirmed.message == recipe_summary
    assert confirmed.provider_calls == 0
    assert calls == 2
    assert owner._test_recipe_calls == [{
        "recipe_id": "daily-health", "message": "",
        "runtime_recipes": [_recipe()], "language": "de", "user_id": "alice",
    }]


def test_recipe_execute_confirmation_preview_lists_resolved_ssh_targets(tmp_path) -> None:
    recipe = _bound_recipe()
    owner = _owner(recipes=[recipe], ssh_refs=("srv-dev02", "backup-01", "db-01"))
    binding = _binding(owner)
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")

    async def completion(**kwargs):
        if kwargs.get("tools"):
            return _response(tool_calls=[_tool_call("recipes_execute", {"recipe_id": "fleet"})], finish_reason="tool_use")
        raise RuntimeError("force deterministic preview fallback")

    preview = asyncio.run(run_native_agent_turn(
        message="Run Fleet check", user_id="alice", auth_role="admin", turn_id="preview-targets",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))

    assert preview.kind == "pending_confirmation"
    assert "Fleet check" in preview.message
    assert "srv-dev02" in preview.message
    assert "backup-01" in preview.message
    assert "db-01" in preview.message
    assert owner._test_recipe_calls == []


def test_recipe_execute_confirmation_preview_lists_resolved_discord_target() -> None:
    recipe = {
        "id": "notify", "name": "Notify", "enabled": True,
        "steps": [{
            "id": "send", "type": "discord_send",
            "params": {"connection_kind": "discord", "binding": "one", "message": "done"},
        }],
    }
    owner = _owner(recipes=[recipe], connection_refs={"discord": ("alerts",)})

    preview = asyncio.run(_binding(owner).confirmation_preview(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "notify"},
    ))

    assert preview == "Confirm recipes_execute: recipe=Notify; runs on: alerts"
    assert owner._test_recipe_calls == []


def test_recipe_execute_confirmation_preview_maps_generalized_binding_error() -> None:
    recipe = {
        "id": "notify-all", "name": "Notify all", "enabled": True,
        "steps": [{
            "id": "send", "type": "discord_send",
            "params": {"connection_kind": "discord", "binding": "all", "message": "done"},
        }],
    }
    owner = _owner(recipes=[recipe], connection_refs={"discord": ("alerts", "ops")})

    preview = asyncio.run(_binding(owner).confirmation_preview(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "notify-all"},
    ))

    assert preview == (
        "Confirm recipes_execute: recipe=Notify all; target resolution failed "
        "(recipe_connection_binding_not_allowed_for_kind)"
    )
    assert owner._test_recipe_calls == []


@pytest.mark.parametrize("recipes", [[], [_recipe(enabled=False)]])
def test_unknown_or_disabled_recipe_returns_not_found_without_execution(recipes) -> None:  # noqa: ANN001
    owner = _owner(recipes=recipes)
    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "daily-health"},
    ))

    assert result.content == "Recipe 'daily-health' was not found or is not enabled."
    assert owner._test_recipe_calls == []


def test_step_guardrail_failure_is_preserved_as_honest_recipe_failure() -> None:
    owner = _owner(result=SkillResult(
        skill_name="recipe_daily-health", content="", success=False,
        error="recipe_ssh_policy_blocked",
    ))
    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "daily-health"},
    ))

    assert result.content == "Recipe 'daily-health' failed: recipe_ssh_policy_blocked"
    assert set(owner._test_recipe_calls[0]) == {"recipe_id", "message", "runtime_recipes", "language", "user_id"}


def test_runtime_exception_degrades_honestly_without_detail_leak() -> None:
    owner = _owner(error=RuntimeError("private step detail"))
    result = asyncio.run(_binding(owner).handler(
        NativeToolContext(user_id="alice", auth_role="admin"), {"recipe_id": "daily-health"},
    ))

    assert result.content == "Recipe 'daily-health' could not be executed (RuntimeError)."
    assert "private step detail" not in result.content


def test_registry_flag_defaults_and_threshold_cover_recipe_execute() -> None:
    owner = _owner()
    base_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_write_notes_enabled", "native_agent_write_memory_enabled", "native_agent_ssh_enabled",
        "native_agent_messaging_enabled", "native_agent_infra_write_enabled",
    }
    without_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=base_flags,
    )
    with_flag = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={*base_flags, "native_agent_recipe_execute_enabled"},
    )
    by_name = {item.contract.name: item.contract for item in with_flag}

    assert len(without_flag) == 34
    assert len(with_flag) == 35
    assert "recipes_execute" not in {item.contract.name for item in without_flag}
    assert by_name["recipes_execute"].effect == "mutating"
    assert by_name["recipes_execute"].confirmation_required is True
    assert by_name["recipes_execute"].relay_result_content is True
    assert [item.contract.name for item in with_flag if item.contract.relay_result_content] == [
        "recipes_execute",
    ]
    assert asyncio.run(select_relevant_native_tools("run recipe", with_flag, selector=None)) == with_flag

    config = AgenticLoopFeatureConfig()
    assert config.native_agent_recipe_execute_enabled is True
    assert native_agent_enabled(SimpleNamespace(agentic_loop=config)) is True
