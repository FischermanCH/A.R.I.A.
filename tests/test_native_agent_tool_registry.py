from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from pathlib import Path

from aria.modules import MODULE_MANIFESTS
from aria.modules.native_agent.tool_registry import (
    assemble_native_tools,
    filter_tools_by_configured_connections,
    select_relevant_native_tools,
)


def _owner() -> SimpleNamespace:
    return SimpleNamespace(settings=SimpleNamespace(), memory_skill=object())


def test_registry_assembles_owner_declared_native_tools_with_independent_flags() -> None:
    both = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(),
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )
    memory = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(), enabled_rollout_flags={"native_agent_memory_enabled"},
    )
    connections = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(), enabled_rollout_flags={"native_agent_connections_enabled"},
    )

    assert [tool.contract.name for tool in both] == [
        "recall_personal_memory", "memory_context_read",
        "notes_read_search_inventory", "documents_read_search_inventory",
        "list_connections", "lookup_connection",
        "capabilities_inventory", "product_release_read", "recipes_inventory",
        "recipes_explain", "recipes_preview", "web_search_fetch", "website_list", "website_read",
        "rss_feed_read", "calendar_read", "file_list", "file_read", "mail_read", "mail_search",
    ]
    assert [tool.contract.name for tool in memory] == [
        "recall_personal_memory", "memory_context_read",
        "notes_read_search_inventory", "documents_read_search_inventory",
        "capabilities_inventory", "product_release_read", "recipes_inventory",
        "recipes_explain", "recipes_preview", "web_search_fetch", "website_list", "website_read",
    ]
    assert [tool.contract.name for tool in connections] == [
        "list_connections", "lookup_connection", "rss_feed_read", "calendar_read",
        "file_list", "file_read", "mail_read", "mail_search",
    ]
    assert all(tool.contract.effect == "read_only" for tool in both)
    assert all(tool.contract.confirmation_required is False for tool in both)
    assert all(tool.contract.input_schema["type"] == "object" for tool in both)
    assert {tool.contract.owner_module_id for tool in both} == {
        "memory", "notes", "document_memory", "connections_runtime_status",
        "action_contracts", "release_update", "recipe_store", "recipe_runtime",
        "native_web_llm", "website_runtime", "rss_runtime",
    }


def test_small_registry_offers_all_without_relevance_selector() -> None:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(),
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )
    selected = asyncio.run(select_relevant_native_tools("question", tools, selector=None))
    assert selected == tools


def test_large_core_only_registry_keeps_every_tool_without_selector() -> None:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(), enabled_rollout_flags={"native_agent_memory_enabled"},
    )
    expanded = tuple(tools[0] for _ in range(41))
    selected = asyncio.run(select_relevant_native_tools("question", expanded, selector=None))
    assert selected == expanded


def test_large_registry_uses_injected_meta_catalog_selector() -> None:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(),
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )
    mcp_tools = tuple(
        replace(
            tools[0],
            contract=replace(tools[0].contract, name=f"mcp__demo__tool_{index:02d}"),
        )
        for index in range(21)
    )
    expanded = (*tools, *mcp_tools)

    async def selector(message, offered, top_k):  # noqa: ANN001
        assert message == "question" and len(offered) == 21 and top_k == 16
        return ("mcp__demo__tool_05",)

    selected = asyncio.run(select_relevant_native_tools("question", expanded, selector=selector))
    assert [tool.contract.name for tool in selected] == [
        *(tool.contract.name for tool in tools),
        "mcp__demo__tool_05",
    ]


def test_native_agent_handler_and_bridge_do_not_import_tool_owner_implementations() -> None:
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in ("aria/modules/native_agent/handler.py", "aria/modules/native_agent/pipeline_bridge.py")
    )
    assert "aria.modules.memory" not in source
    assert "aria.modules.connections_runtime_status" not in source


def test_connection_tool_contracts_declare_required_kinds_and_assembly_stays_23() -> None:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(),
        enabled_rollout_flags={
            "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        },
    )
    by_name = {tool.contract.name: tool.contract.required_connection_kinds for tool in tools}

    assert len(tools) == 23
    assert by_name["rss_feed_read"] == ("rss",)
    assert by_name["calendar_read"] == ("google_calendar",)
    assert by_name["file_list"] == ("sftp", "smb")
    assert by_name["file_read"] == ("sftp", "smb")
    assert by_name["mail_read"] == ("imap",)
    assert by_name["mail_search"] == ("imap",)
    assert by_name["website_read"] == ()


def test_connection_tool_filter_uses_any_configured_required_kind_only() -> None:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(),
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )
    settings = SimpleNamespace(connections=SimpleNamespace(
        rss={}, google_calendar={}, sftp={"files": object()}, smb={}, imap={}, website={},
    ))

    filtered = filter_tools_by_configured_connections(tools, settings)
    names = {tool.contract.name for tool in filtered}

    assert "mail_read" not in names and "mail_search" not in names
    assert "rss_feed_read" not in names and "calendar_read" not in names
    assert "file_list" in names and "file_read" in names
    assert "website_list" in names and "website_read" in names
    assert "recall_personal_memory" in names


def test_connection_tool_filter_keeps_mail_when_imap_is_configured() -> None:
    tools = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=_owner(),
        enabled_rollout_flags={"native_agent_connections_enabled"},
    )
    settings = SimpleNamespace(connections=SimpleNamespace(
        rss={}, google_calendar={}, sftp={}, smb={}, imap={"inbox": object()},
    ))

    names = {tool.contract.name for tool in filter_tools_by_configured_connections(tools, settings)}

    assert "mail_read" in names and "mail_search" in names
