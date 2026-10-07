from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools


def _response(*, content: str = "", tool_name: str = "", arguments: dict | None = None):
    calls = []
    finish = "stop"
    if tool_name:
        calls = [SimpleNamespace(id=f"call-{tool_name}", function=SimpleNamespace(
            name=tool_name, arguments=json.dumps(arguments or {}),
        ))]
        finish = "tool_use"
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls), finish_reason=finish,
    )])


def _owner(*, recipes=(), capabilities=(), release=None):  # noqa: ANN001
    async def recipe_loader():
        return tuple(recipes)

    async def capability_loader():
        return tuple(capabilities)

    async def release_loader(_section):
        return release or {}

    return SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(),
        _native_agent_recipe_loader=recipe_loader,
        _native_agent_capability_loader=capability_loader,
        _native_agent_release_loader=release_loader,
    )


def _tools(owner):  # noqa: ANN001
    return assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )


def _recipe():
    return {
        "id": "backup-check", "name": "Backup Check", "description": "Check backups",
        "enabled": True, "connections": ["ssh"],
        "steps": [{
            "id": "s1", "name": "Inspect", "type": "ssh_run", "on_error": "stop",
            "params": {"connection_ref": "server-a", "command": "cat /safe", "token": "TOP-SECRET"},
        }],
    }


@pytest.mark.parametrize(("tool_name", "arguments", "needle"), (
    ("capabilities_inventory", {}, "file_read"),
    ("product_release_read", {"section": "all"}, "0.1.0-alpha836"),
    ("recipes_inventory", {}, "backup-check"),
    ("recipes_explain", {"recipe_id": "backup-check"}, "Inspect"),
    ("recipes_preview", {"recipe_id": "backup-check"}, "server-a"),
))
def test_p2_r3_tool_roundtrip_is_read_only_allowlisted(
    tmp_path, tool_name: str, arguments: dict, needle: str,
) -> None:
    owner = _owner(
        recipes=(_recipe(),),
        capabilities=({"capability": "file_read", "operation": "read", "executors": ["sftp"],
                       "confirmation_required": False, "password": "TOP-SECRET"},),
        release={"version": "0.1.0", "label": "0.1.0-alpha836", "changelog": "Read tools",
                 "upgrade": "Upgrade safely", "api_key": "TOP-SECRET"},
    )
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_name=tool_name, arguments=arguments)
        result = kwargs["messages"][-1]["content"]
        assert needle in result
        assert "TOP-SECRET" not in result
        assert '"effect": "read_only"' in result
        return _response(content=f"answer from {tool_name}")

    outcome = asyncio.run(run_native_agent_turn(
        message="read authority", user_id="u1", turn_id=tool_name,
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == (tool_name,)


def test_recipe_tools_are_exact_enabled_and_never_expose_free_params(tmp_path) -> None:
    disabled = {**_recipe(), "id": "disabled", "enabled": False}
    owner = _owner(recipes=(_recipe(), disabled))
    bindings = {tool.contract.name: tool for tool in _tools(owner)}

    inventory = asyncio.run(bindings["recipes_inventory"].handler(SimpleNamespace(user_id="u1"), {}))
    explain = asyncio.run(bindings["recipes_explain"].handler(
        SimpleNamespace(user_id="u1"), {"recipe_id": "backup-check"},
    ))
    missing = asyncio.run(bindings["recipes_preview"].handler(
        SimpleNamespace(user_id="u1"), {"recipe_id": "disabled"},
    ))
    assert "backup-check" in inventory.content and "disabled" not in inventory.content
    assert "connection_ref" in explain.content and "server-a" in explain.content
    assert "cat /safe" not in explain.content and "TOP-SECRET" not in explain.content
    assert "token" not in explain.content
    assert '"status": "recipe_not_found"' in missing.content


def test_p2_r3_empty_results_are_honest() -> None:
    bindings = {tool.contract.name: tool for tool in _tools(_owner())}
    expected = {
        "capabilities_inventory": "no_capabilities",
        "product_release_read": "release_information_unavailable",
        "recipes_inventory": "no_enabled_recipes",
        "recipes_explain": "recipe_not_found",
        "recipes_preview": "recipe_not_found",
    }
    for name, status in expected.items():
        args = {"recipe_id": "missing"} if name.startswith("recipes_e") or name.endswith("preview") else {}
        result = asyncio.run(bindings[name].handler(SimpleNamespace(user_id="u1"), args))
        assert f'"status": "{status}"' in result.content


@pytest.mark.parametrize(("tool_name", "arguments"), (
    ("capabilities_inventory", {"user_id": "u2"}),
    ("product_release_read", {"section": "secrets"}),
    ("recipes_inventory", {"include_disabled": True}),
    ("recipes_explain", {"recipe_id": "backup-check", "token": "x"}),
    ("recipes_preview", {"recipe_id": "backup-check", "execute": True}),
))
def test_p2_r3_tools_reject_unknown_or_unsafe_inputs(tool_name: str, arguments: dict) -> None:
    binding = {tool.contract.name: tool for tool in _tools(_owner(recipes=(_recipe(),)))}[tool_name]
    with pytest.raises(ValueError, match="arguments_invalid"):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))


def test_registry_has_twenty_read_only_tools_and_offers_all_without_selector() -> None:
    tools = _tools(_owner())
    assert len(tools) == 20
    assert {tool.contract.name for tool in tools} >= {
        "capabilities_inventory", "product_release_read", "recipes_inventory",
        "recipes_explain", "recipes_preview",
    }
    assert all(tool.contract.effect == "read_only" for tool in tools)
    assert all(not tool.contract.confirmation_required for tool in tools)

    async def selector(*_args):
        raise AssertionError("selector must not run at twenty tools")

    assert asyncio.run(select_relevant_native_tools("question", tools, selector=selector)) == tools
