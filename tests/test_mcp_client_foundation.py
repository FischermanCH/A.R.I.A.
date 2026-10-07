from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import time
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import LLMConfig, MCPServerConfig, Settings
from aria.modules.mcp.runtime import (
    MCP_CALL_TIMEOUT_SECONDS,
    MCP_DISCOVERY_TIMEOUT_SECONDS,
    MCPClientManager,
)
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.handler import NativeAgentOutcome, run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.sdk import NativeToolContext


def _server(**overrides):  # noqa: ANN003, ANN202
    payload = {
        "transport": "sse",
        "url": "https://mcp.invalid/events",
        "headers": {"Authorization": "Bearer secret-value"},
        "enabled": True,
        "title": "Mock files",
        "description": "Test-only MCP server",
    }
    payload.update(overrides)
    return MCPServerConfig.model_validate(payload)


def _tool(
    name: str, *, read_only: bool | None = True, description: str = "Read mock data.",
    schema: dict | None = None,
):  # noqa: ANN202
    annotations = None if read_only is None else SimpleNamespace(read_only_hint=read_only)
    return SimpleNamespace(
        name=name,
        description=description,
        input_schema=schema or {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        annotations=annotations,
    )


def _completion_response(*, content: str = "", tool_name: str = "", arguments: dict | None = None):  # noqa: ANN202
    calls = []
    if tool_name:
        calls = [SimpleNamespace(
            id=f"call-{tool_name}",
            function=SimpleNamespace(name=tool_name, arguments=json.dumps(arguments or {})),
        )]
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls),
        finish_reason="tool_use" if calls else "stop",
    )])


class _Session:
    def __init__(self, tools, *, call_result=None, call_error: Exception | None = None) -> None:  # noqa: ANN001
        self.tools = tuple(tools)
        self.call_result = call_result or SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(type="text", text="fresh remote content")],
            structured_content={"status": "ok"},
        )
        self.call_error = call_error
        self.initialize_calls = 0
        self.list_calls = 0
        self.tool_calls: list[tuple[str, dict]] = []

    async def initialize(self) -> None:
        self.initialize_calls += 1

    async def list_tools(self):  # noqa: ANN202
        self.list_calls += 1
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict):  # noqa: ANN202
        self.tool_calls.append((name, arguments))
        if self.call_error is not None:
            raise self.call_error
        return self.call_result


class _SessionFactory:
    def __init__(self, sessions: dict[str, _Session], *, failures: set[str] | None = None) -> None:
        self.sessions = sessions
        self.failures = failures or set()
        self.opens: list[str] = []

    @asynccontextmanager
    async def __call__(self, server_name: str, _config: MCPServerConfig):
        self.opens.append(server_name)
        if server_name in self.failures:
            raise ConnectionError("secret-value must not escape")
        yield self.sessions[server_name]


class _DelayedSessionFactory(_SessionFactory):
    def __init__(self, sessions: dict[str, _Session]) -> None:
        super().__init__(sessions)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @asynccontextmanager
    async def __call__(self, server_name: str, _config: MCPServerConfig):
        self.opens.append(server_name)
        self.started.set()
        await self.release.wait()
        yield self.sessions[server_name]


def _settings(**payload) -> Settings:  # noqa: ANN003
    source = {
        "llm": {"model": "fake"},
        "memory": {"enabled": False},
        "token_tracking": {"enabled": False},
    }
    source.update(payload)
    return Settings.model_validate(source)


def test_mcp_config_is_backward_compatible_default_off_and_bad_transport_is_parseable() -> None:
    legacy = _settings()
    configured = _settings(mcp_servers={
        "docs": {"url": "https://mcp.invalid/sse"},
        "bad": {"url": "https://mcp.invalid/bad", "transport": "stdio", "enabled": True},
    })

    assert legacy.mcp_servers == {}
    assert legacy.agentic_loop.native_agent_mcp_enabled is False
    assert configured.mcp_servers["docs"].transport == "sse"
    assert configured.mcp_servers["docs"].enabled is False
    assert configured.mcp_servers["docs"].trusted is False
    assert configured.mcp_servers["bad"].transport == "stdio"


def test_discovery_is_cached_refreshable_and_failures_return_zero_tools(caplog) -> None:  # noqa: ANN001
    sessions = {
        "good": _Session([_tool("read_file")]),
        "down": _Session([]),
        "bad_transport": _Session([]),
    }
    factory = _SessionFactory(sessions, failures={"down"})
    manager = MCPClientManager({
        "good": _server(),
        "down": _server(),
        "bad_transport": _server(transport="stdio"),
        "disabled": _server(enabled=False),
    }, session_factory=factory)

    first = asyncio.run(manager.discover_all(refresh=True))
    second = asyncio.run(manager.discover_all())
    refreshed = asyncio.run(manager.discover_all(refresh=True))

    assert len(first["good"]) == len(second["good"]) == len(refreshed["good"]) == 1
    assert first["down"] == refreshed["down"] == ()
    assert first["bad_transport"] == ()
    assert factory.opens == ["down", "good", "good"]
    assert sessions["good"].list_calls == 2
    statuses = {row.server_name: row for row in manager.statuses()}
    assert statuses["good"].connected is True and statuses["good"].tool_count == 1
    assert statuses["down"].connected is False and statuses["down"].error == "ConnectionError"
    assert statuses["bad_transport"].error == "unsupported_transport"
    assert "secret-value" not in caplog.text
    assert "mcp.invalid" not in caplog.text


def test_failed_discovery_is_cached_until_cooldown_expires() -> None:
    now = [100.0]
    sessions = {"down": _Session([])}
    factory = _SessionFactory(sessions, failures={"down"})
    manager = MCPClientManager(
        {"down": _server()}, session_factory=factory, clock=lambda: now[0],
    )

    first = asyncio.run(manager.discover_all(refresh=True))
    second = asyncio.run(manager.discover_all(refresh=True))
    now[0] += 61.0
    third = asyncio.run(manager.discover_all(refresh=True))

    assert first["down"] == second["down"] == third["down"] == ()
    assert factory.opens == ["down", "down"]
    status = manager.statuses()[0]
    assert status.connected is False
    assert status.error == "ConnectionError"


def test_default_discovery_returns_snapshot_without_waiting_and_deduplicates_refresh() -> None:
    async def scenario() -> None:
        session = _Session([_tool("read_file")])
        factory = _DelayedSessionFactory({"docs": session})
        manager = MCPClientManager({"docs": _server()}, session_factory=factory)

        started = time.perf_counter()
        first = await manager.discover_all()
        elapsed = time.perf_counter() - started
        await asyncio.wait_for(factory.started.wait(), timeout=0.2)
        second = await manager.discover_all()

        assert elapsed < 0.05
        assert first == {}
        assert second == {}
        assert factory.opens == ["docs"]

        factory.release.set()
        for _ in range(20):
            await asyncio.sleep(0)
            cached = await manager.discover_all()
            if cached.get("docs"):
                break
        assert len(cached["docs"]) == 1
        assert factory.opens == ["docs"]

    asyncio.run(scenario())


def test_failed_server_recovers_in_background_after_cooldown() -> None:
    async def scenario() -> None:
        now = [100.0]
        session = _Session([_tool("read_file")])
        factory = _SessionFactory({"docs": session}, failures={"docs"})
        manager = MCPClientManager(
            {"docs": _server()}, session_factory=factory, clock=lambda: now[0],
        )

        failed = await manager.discover_all(refresh=True)
        factory.failures.clear()
        now[0] += 61.0
        immediate = await manager.discover_all()

        assert failed["docs"] == ()
        assert immediate["docs"] == ()
        assert factory.opens == ["docs"]
        for _ in range(20):
            await asyncio.sleep(0)
            recovered = await manager.discover_all()
            if recovered.get("docs"):
                break
        assert len(recovered["docs"]) == 1
        assert factory.opens == ["docs", "docs"]
        status = manager.statuses()[0]
        assert status.connected is True
        assert status.error == ""

    asyncio.run(scenario())


def test_discovery_timeout_is_shorter_without_changing_tool_call_timeout() -> None:
    assert MCP_DISCOVERY_TIMEOUT_SECONDS == 8.0
    assert MCP_CALL_TIMEOUT_SECONDS == 30.0


def test_all_tools_are_namespaced_and_effects_follow_annotations_for_untrusted_server() -> None:
    session = _Session([
        _tool("Read File", read_only=True),
        _tool("delete_file", read_only=False),
        _tool("mystery", read_only=None),
    ])
    manager = MCPClientManager({"Shared Docs": _server()}, session_factory=_SessionFactory({"Shared Docs": session}))
    discovered = asyncio.run(manager.discover_all(refresh=True))

    bindings = manager.native_tool_bindings()

    assert [row.contract.name for row in bindings] == [
        "mcp__shared_docs__read_file",
        "mcp__shared_docs__delete_file",
        "mcp__shared_docs__mystery",
    ]
    contracts = {row.contract.name: row.contract for row in bindings}
    assert contracts["mcp__shared_docs__read_file"].effect == "read_only"
    assert contracts["mcp__shared_docs__read_file"].confirmation_required is False
    assert contracts["mcp__shared_docs__delete_file"].effect == "mutating"
    assert contracts["mcp__shared_docs__delete_file"].confirmation_required is True
    assert contracts["mcp__shared_docs__mystery"].effect == "mutating"
    assert contracts["mcp__shared_docs__mystery"].confirmation_required is True
    assert all(contract.owner_module_id == "mcp" for contract in contracts.values())
    assert all(contract.rollout_flag == "native_agent_mcp_enabled" for contract in contracts.values())
    assert all(contract.input_schema["required"] == ["path"] for contract in contracts.values())
    assert discovered["Shared Docs"][0].annotations["read_only_hint"] is True
    assert manager.read_only_tool_count("Shared Docs") == 1
    assert manager.read_only_tool_count("missing") == 0


def test_trusted_server_projects_every_tool_as_direct_read_only() -> None:
    session = _Session([
        _tool("read_file", read_only=True),
        _tool("delete_file", read_only=False),
        _tool("execute_blender_code", read_only=None),
    ])
    manager = MCPClientManager(
        {"blender": _server(trusted=True)},
        session_factory=_SessionFactory({"blender": session}),
    )
    asyncio.run(manager.discover_all(refresh=True))

    bindings = manager.native_tool_bindings()

    assert len(bindings) == 3
    assert all(binding.contract.effect == "read_only" for binding in bindings)
    assert all(binding.contract.confirmation_required is False for binding in bindings)
    assert manager.read_only_tool_count("blender") == 3


def test_trusted_unannotated_tool_executes_directly_without_pending(tmp_path) -> None:  # noqa: ANN001
    session = _Session([_tool(
        "execute_blender_code",
        read_only=None,
        schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
    )])
    manager = MCPClientManager(
        {"blender": _server(trusted=True)},
        session_factory=_SessionFactory({"blender": session}),
    )
    asyncio.run(manager.discover_all(refresh=True))
    binding = manager.native_tool_bindings()[0]
    pending_store = NativePendingStore(tmp_path / "trusted-pending.sqlite3")
    responses = iter((
        _completion_response(tool_name=binding.contract.name, arguments={"code": "print('ok')"}),
        _completion_response(content="The MCP Tool returned fresh remote content."),
    ))

    async def completion(**_kwargs):  # noqa: ANN003
        return next(responses)

    outcome = asyncio.run(run_native_agent_turn(
        message="Run the trusted Blender Tool", user_id="alice", turn_id="trusted-mcp",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=completion, trace_root=tmp_path / "trusted-trace",
        pending_store=pending_store,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("mcp__blender__execute_blender_code",)
    assert session.tool_calls == [("execute_blender_code", {"code": "print('ok')"})]
    assert pending_store.count() == 0


def test_untrusted_mutating_mcp_tool_waits_for_confirmation_and_replays_frozen_code(tmp_path) -> None:  # noqa: ANN001
    code = "import bpy\nbpy.ops.mesh.primitive_cube_add(size=2)"
    session = _Session([_tool(
        "execute_blender_code",
        read_only=None,
        description="Execute Python in Blender.",
        schema={
            "type": "object",
            "properties": {"code": {"type": "string"}, "mode": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
    )])
    manager = MCPClientManager(
        {"blender": _server(trusted=False)},
        session_factory=_SessionFactory({"blender": session}),
    )
    asyncio.run(manager.discover_all(refresh=True))
    binding = manager.native_tool_bindings()[0]
    pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")

    async def preview_completion(**_kwargs):  # noqa: ANN003
        return _completion_response(
            tool_name=binding.contract.name,
            arguments={"code": code, "mode": "OBJECT"},
        )

    preview = asyncio.run(run_native_agent_turn(
        message="Fuehre diesen Blender-Code aus", user_id="alice", turn_id="mcp-preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=preview_completion, trace_root=tmp_path / "trace",
        pending_store=pending_store, confirmation_ledger=ledger, now=1000,
    ))

    assert binding.contract.effect == "mutating"
    assert binding.contract.confirmation_required is True
    assert preview.kind == "pending_confirmation"
    assert session.tool_calls == []
    pending = pending_store.peek(user_id="alice", token=preview.confirmation_token, now=1001)
    assert pending is not None
    assert pending.frozen_arguments == {"code": code, "mode": "OBJECT"}
    assert "server=blender" in pending.preview
    assert "tool=execute_blender_code" in pending.preview
    assert "bpy.ops.mesh.primitive_cube_add(size=2)" in pending.preview

    async def confirm_completion(**_kwargs):  # noqa: ANN003
        return _completion_response(content="Blender action completed from the Tool result.")

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", turn_id="mcp-confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=confirm_completion, pending_store=pending_store,
        confirmation_ledger=ledger, confirmation_token=preview.confirmation_token, now=1002,
    ))

    assert confirmed.kind == "final_answer"
    assert session.tool_calls == [(
        "execute_blender_code", {"code": code, "mode": "OBJECT"},
    )]


def test_confirmed_mutating_mcp_failure_relays_honest_error_without_success_phrasing(tmp_path) -> None:  # noqa: ANN001
    session = _Session(
        [_tool("delete_scene", read_only=False)],
        call_error=TimeoutError("remote timeout detail must not escape"),
    )
    manager = MCPClientManager(
        {"blender": _server(trusted=False)},
        session_factory=_SessionFactory({"blender": session}),
    )
    asyncio.run(manager.discover_all(refresh=True))
    binding = manager.native_tool_bindings()[0]
    pending_store = NativePendingStore(tmp_path / "failure-pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "failure-ledger.sqlite3")

    async def preview_completion(**_kwargs):  # noqa: ANN003
        return _completion_response(tool_name=binding.contract.name, arguments={"path": "/scene"})

    preview = asyncio.run(run_native_agent_turn(
        message="Delete the Blender scene", user_id="alice", turn_id="failure-preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=preview_completion, pending_store=pending_store,
        confirmation_ledger=ledger, now=1000,
    ))

    async def forbidden_success_phrasing(**_kwargs):  # noqa: ANN003
        raise AssertionError("confirmed MCP errors must be relayed, not phrased as success")

    confirmed = asyncio.run(run_native_agent_turn(
        message=preview.confirm_command, user_id="alice", turn_id="failure-confirm",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=forbidden_success_phrasing, pending_store=pending_store,
        confirmation_ledger=ledger, confirmation_token=preview.confirmation_token, now=1002,
    ))

    assert confirmed.kind == "final_answer"
    assert json.loads(confirmed.message) == {"error": "mcp_call_failed", "status": "error"}
    assert session.tool_calls == [
        ("delete_scene", {"path": "/scene"}),
    ]


def test_binding_validates_arguments_calls_remote_and_bounds_result() -> None:
    session = _Session([_tool("read_file")])
    manager = MCPClientManager({"docs": _server()}, session_factory=_SessionFactory({"docs": session}))
    asyncio.run(manager.discover_all(refresh=True))
    binding = manager.native_tool_bindings()[0]
    context = NativeToolContext(user_id="alice", request_id="mcp-turn")

    invalid = asyncio.run(binding.handler(context, {}))
    valid = asyncio.run(binding.handler(context, {"path": "/manual.txt"}))

    assert json.loads(invalid.content)["error"] == "mcp_arguments_invalid"
    assert session.tool_calls == [("read_file", {"path": "/manual.txt"})]
    payload = json.loads(valid.content)
    assert payload["status"] == "ok"
    assert payload["structured_content"] == {"status": "ok"}
    assert payload["content"][0]["text"] == "fresh remote content"
    assert valid.intent == "mcp__docs__read_file"
    assert len(valid.content) <= 12000


def test_binding_remote_error_is_honest_and_never_raises() -> None:
    result_error = SimpleNamespace(
        is_error=True,
        content=[SimpleNamespace(type="text", text="permission denied")],
        structured_content=None,
    )
    remote_error_session = _Session([_tool("read_file")], call_result=result_error)
    raised_session = _Session([_tool("read_file")], call_error=TimeoutError("remote timed out"))

    for session, expected in ((remote_error_session, "mcp_tool_error"), (raised_session, "mcp_call_failed")):
        manager = MCPClientManager({"docs": _server()}, session_factory=_SessionFactory({"docs": session}))
        asyncio.run(manager.discover_all(refresh=True))
        binding = manager.native_tool_bindings()[0]
        outcome = asyncio.run(binding.handler(NativeToolContext(user_id="alice"), {"path": "/x"}))
        payload = json.loads(outcome.content)
        assert payload["status"] == "error"
        assert payload["error"] == expected


def test_tool_names_and_remote_results_are_bounded() -> None:
    session = _Session(
        [_tool("read_" + ("very_long_name_" * 8))],
        call_result=SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(type="text", text="x" * 50000)],
            structured_content={"body": "y" * 50000},
        ),
    )
    manager = MCPClientManager(
        {"long_server_" + ("segment_" * 8): _server()},
        session_factory=_SessionFactory({"long_server_" + ("segment_" * 8): session}),
    )
    asyncio.run(manager.discover_all(refresh=True))
    binding = manager.native_tool_bindings()[0]
    outcome = asyncio.run(binding.handler(NativeToolContext(user_id="alice"), {"path": "/x"}))

    assert binding.contract.name.startswith("mcp__")
    assert len(binding.contract.name) <= 64
    assert len(outcome.content) <= 12000
    assert json.loads(outcome.content)["truncated"] is True


def test_called_mcp_binding_is_reported_in_native_used_tools(tmp_path) -> None:  # noqa: ANN001
    session = _Session([_tool("read_file")])
    manager = MCPClientManager({"docs": _server()}, session_factory=_SessionFactory({"docs": session}))
    asyncio.run(manager.discover_all(refresh=True))
    binding = manager.native_tool_bindings()[0]
    responses = iter((
        _completion_response(tool_name=binding.contract.name, arguments={"path": "/manual.txt"}),
        _completion_response(content="The current Tool result says fresh remote content."),
    ))

    async def completion(**_kwargs):  # noqa: ANN003
        return next(responses)

    outcome = asyncio.run(run_native_agent_turn(
        message="Read the remote manual", user_id="alice", turn_id="mcp-used-tool",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("mcp__docs__read_file",)


class _Embedder:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, inputs, **_kwargs):  # noqa: ANN001, ANN003
        self.calls += 1
        return SimpleNamespace(vectors=[[1.0, float(index)] for index, _text in enumerate(inputs)])


class _PromptLoader:
    def get_persona(self) -> str:
        return "ARIA"


class _LLM:
    usage_meter = None


def _pipeline(tmp_path, *, mcp_enabled: bool, embedder: _Embedder) -> Pipeline:  # noqa: ANN001
    owner = Pipeline(
        settings=_settings(
            agentic_loop={"enabled": True, "native_agent_mcp_enabled": mcp_enabled},
            token_tracking={"enabled": False, "log_file": str(tmp_path / "tokens.jsonl")},
        ),
        prompt_loader=_PromptLoader(), llm_client=_LLM(), embedding_client=embedder,
    )
    owner._project_root = tmp_path
    owner._stored_recipes_dir = tmp_path / "recipes"
    return owner


def test_flag_off_keeps_37_core_tools_and_flag_on_is_additive_and_selectable() -> None:
    session = _Session([_tool(f"remote_{index}", description=f"Remote reader {index}") for index in range(5)])
    manager = MCPClientManager({"docs": _server()}, session_factory=_SessionFactory({"docs": session}))
    asyncio.run(manager.discover_all(refresh=True))
    owner = SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(), _native_mcp_client=manager,
    )
    core_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_admin_write_enabled", "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
        "native_agent_ssh_enabled", "native_agent_messaging_enabled", "native_agent_infra_write_enabled",
        "native_agent_recipe_execute_enabled", "native_agent_recipe_learn_enabled", "native_agent_memory_learn_enabled",
    }

    core = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=core_flags)
    additive = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={*core_flags, "native_agent_mcp_enabled"},
    )

    assert len(core) == 37
    assert len(additive) == 42
    assert {row.contract.name for row in core}.isdisjoint({row.contract.name for row in additive[37:]})
    embedder = _Embedder()
    from aria.modules.native_agent.tool_registry import EmbeddingNativeToolRelevanceSelector

    selector = EmbeddingNativeToolRelevanceSelector(embedding_client=embedder, descriptor_cache={})
    selected = asyncio.run(select_relevant_native_tools("remote reader", additive, selector=selector))
    assert len(selected) == 42
    assert {row.contract.name for row in core}.issubset({row.contract.name for row in selected})
    assert embedder.calls == 1


def test_pipeline_flag_off_never_discovers_and_flag_on_emits_mcp_and_selector_details(
    monkeypatch, tmp_path,
) -> None:  # noqa: ANN001
    async def fake_turn(**_kwargs):  # noqa: ANN003
        return NativeAgentOutcome("final_answer", "Done", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    off_session = _Session([_tool(f"remote_{index}") for index in range(5)])
    off_factory = _SessionFactory({"docs": off_session})
    off_owner = _pipeline(tmp_path / "off", mcp_enabled=False, embedder=_Embedder())
    off_owner._native_mcp_client = MCPClientManager(
        {"docs": _server()}, session_factory=off_factory,
    )
    off_result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        off_owner, message="hello", user_id="alice", request_id="off", source="test", start=0.0,
    ))

    assert off_result is not None
    assert off_factory.opens == []
    assert not any("Routing Debug: mcp " in line for line in off_result.detail_lines)
    assert not any("tool_selector active=yes" in line for line in off_result.detail_lines)

    on_session = _Session([_tool(f"remote_{index}") for index in range(5)])
    on_factory = _SessionFactory({"docs": on_session})
    on_owner = _pipeline(tmp_path / "on", mcp_enabled=True, embedder=_Embedder())
    on_owner._native_mcp_client = MCPClientManager(
        {"docs": _server()}, session_factory=on_factory,
    )
    asyncio.run(on_owner._native_mcp_client.discover_all(refresh=True))
    on_result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        on_owner, message="read remote data", user_id="alice", request_id="on", source="test", start=0.0,
    ))

    assert on_result is not None
    assert on_factory.opens == ["docs"]
    assert any(
        line == "Routing Debug: mcp server=docs status=connected tool_count=5"
        for line in on_result.detail_lines
    )
    assert any(
        line.startswith("Routing Debug: tool_selector active=yes selected=42/42 ms=")
        for line in on_result.detail_lines
    )


def test_down_mcp_server_does_not_consume_async_job_budget_or_detach(
    monkeypatch, tmp_path,
) -> None:  # noqa: ANN001
    async def fake_turn(**_kwargs):  # noqa: ANN003
        return NativeAgentOutcome("final_answer", "Synchronous answer", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )
    real_bridge = pipeline_bridge.run_native_agent_first_stage

    async def scenario() -> tuple[object, float, tuple[object, ...]]:
        session = _Session([_tool("read_file")])
        factory = _SessionFactory({"docs": session}, failures={"docs"})
        owner = _pipeline(tmp_path / "down", mcp_enabled=True, embedder=_Embedder())
        owner.settings.agentic_loop.async_agent_job_sync_budget_seconds = 5.0
        owner._native_mcp_client = MCPClientManager(
            {"docs": _server()}, session_factory=factory,
        )
        await owner._native_mcp_client.discover_all(refresh=True)
        monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", real_bridge)

        started = time.perf_counter()
        result = await owner.process("was weisst du ueber mich", user_id="alice")
        elapsed = time.perf_counter() - started
        jobs = owner.get_agent_job_store().list_for_user("alice")
        return result, elapsed, jobs

    result, elapsed, jobs = asyncio.run(scenario())

    assert result.text == "Synchronous answer"
    assert elapsed < 5.0
    assert jobs == ()
