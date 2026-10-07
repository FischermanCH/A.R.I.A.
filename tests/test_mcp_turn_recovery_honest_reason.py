from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import aria.modules.mcp.runtime as mcp_runtime
from aria.modules.configuration_foundations.config import LLMConfig, MCPServerConfig
from aria.modules.mcp.runtime import MCPClientManager, MCPServerStatus, _json_value
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.handler import NativeAgentOutcome, run_native_agent_turn
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _server() -> MCPServerConfig:
    return MCPServerConfig.model_validate({
        "transport": "sse",
        "url": "https://private.invalid/events?token=secret",
        "headers": {"Authorization": "Bearer secret"},
        "enabled": True,
    })


def _tool(name: str = "inspect") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description="Test-only MCP Tool.",
        input_schema={"type": "object", "properties": {}},
        annotations=SimpleNamespace(read_only_hint=True),
    )


class _Session:
    def __init__(
        self,
        label: str,
        *,
        tools: tuple[SimpleNamespace, ...] = (),
        list_hangs_after: int | None = None,
        call_hangs: bool = False,
        result: object | None = None,
    ) -> None:
        self.label = label
        self.tools = tools
        self.list_hangs_after = list_hangs_after
        self.call_hangs = call_hangs
        self.result = result
        self.list_calls = 0
        self.call_calls = 0

    async def initialize(self) -> None:
        return None

    async def list_tools(self, *, cursor: str | None = None) -> SimpleNamespace:
        del cursor
        self.list_calls += 1
        if self.list_hangs_after is not None and self.list_calls > self.list_hangs_after:
            await asyncio.Event().wait()
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, _name: str, _arguments: dict) -> object:
        self.call_calls += 1
        if self.call_hangs:
            await asyncio.Event().wait()
        return self.result or SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(type="text", text="ok")],
            structured_content=None,
        )


class _Factory:
    def __init__(self, rows: list[_Session | Exception]) -> None:
        self.rows = rows
        self.opens: list[str] = []
        self.closes: list[str] = []

    @asynccontextmanager
    async def __call__(self, server_name: str, _config: MCPServerConfig):
        self.opens.append(server_name)
        row = self.rows[min(len(self.opens) - 1, len(self.rows) - 1)]
        if isinstance(row, Exception):
            raise row
        try:
            yield row
        finally:
            self.closes.append(row.label)


def test_expired_failed_discovery_blocks_once_and_recovers_same_turn(monkeypatch) -> None:
    now = [100.0]
    recovered = _Session("recovered", tools=(_tool("scene_info"),))
    factory = _Factory([ConnectionError("down"), recovered])

    async def scenario() -> None:
        manager = MCPClientManager(
            {"blender-mac-ronny": _server()}, session_factory=factory,
            clock=lambda: now[0],
        )
        first = await manager.discover_all(refresh=True)
        assert first["blender-mac-ronny"] == ()

        active = await manager.discover_all(block_cold=True)
        assert active["blender-mac-ronny"] == ()
        assert len(factory.opens) == 1

        now[0] += mcp_runtime.MCP_DISCOVERY_FAILURE_COOLDOWN_SECONDS + 1
        same_turn = await manager.discover_all(block_cold=True)
        assert [row.remote_name for row in same_turn["blender-mac-ronny"]] == ["scene_info"]
        assert len(factory.opens) == 2
        await manager.close()

    asyncio.run(scenario())


def test_idle_session_is_closed_before_fresh_session_opens(monkeypatch) -> None:
    now = [10.0]
    first = _Session("first", tools=(_tool("old"),))
    fresh = _Session("fresh", tools=(_tool("new"),))
    factory = _Factory([first, fresh])
    monkeypatch.setattr(mcp_runtime, "MCP_SESSION_IDLE_RECYCLE_SECONDS", 5.0)

    async def scenario() -> None:
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=factory, clock=lambda: now[0],
        )
        await manager.discover_all(refresh=True)
        now[0] += 6.0
        await manager.discover_all(refresh=True)
        assert factory.opens == ["blender", "blender"]
        assert factory.closes == ["first"]
        assert fresh.list_calls == 1
        await manager.close()

    asyncio.run(scenario())


def test_reused_discovery_timeout_retries_once_on_fresh_session(monkeypatch) -> None:
    stale = _Session("stale", tools=(_tool("old"),), list_hangs_after=1)
    fresh = _Session("fresh", tools=(_tool("new"),))
    factory = _Factory([stale, fresh])
    monkeypatch.setattr(mcp_runtime, "MCP_DISCOVERY_TIMEOUT_SECONDS", 0.08)

    async def scenario() -> None:
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)
        await manager.discover_all(refresh=True)
        recovered = await manager.discover_all(refresh=True)
        assert [row.remote_name for row in recovered["blender"]] == ["new"]
        assert factory.opens == ["blender", "blender"]
        assert factory.closes == ["stale"]
        await manager.close()

    asyncio.run(scenario())


def test_hanging_tool_call_is_not_retried(monkeypatch) -> None:
    hanging = _Session("hanging", tools=(_tool(),), call_hangs=True)
    replacement = _Session("replacement", tools=(_tool(),))
    factory = _Factory([hanging, replacement])
    server = _server().model_copy(update={"call_timeout_seconds": 0.03})

    async def scenario() -> None:
        manager = MCPClientManager({"blender": server}, session_factory=factory)
        await manager.discover_all(refresh=True)
        result = await manager._call_remote("blender", "inspect", {}, intent="inspect")
        assert json.loads(result.content) == {"error": "mcp_call_failed", "status": "error"}
        assert hanging.call_calls == 1
        assert replacement.call_calls == 0
        assert factory.opens == ["blender"]
        await manager.close()

    asyncio.run(scenario())


class _DownManager:
    async def discover_all(self, **_kwargs):  # noqa: ANN003, ANN202
        return {"blender-mac-ronny": ()}

    def statuses(self):  # noqa: ANN201
        return (MCPServerStatus("blender-mac-ronny", False, 0, "TimeoutError"),)


def _owner(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            agentic_loop=SimpleNamespace(
                enabled=True,
                native_agent_mcp_enabled=True,
                native_tool_selector_top_k=16,
                native_agent_max_steps=16,
                native_agent_max_provider_calls=16,
                native_agent_memory_learn_enabled=False,
                native_web_debug_details=False,
            ),
            llm=SimpleNamespace(model="fake"),
            _aria_usage_meter=None,
        ),
        _native_mcp_client=_DownManager(),
        _native_tool_relevance_selector=None,
        _native_agent_completion=None,
        _project_root=tmp_path,
        _load_stored_recipe_runtime=lambda: (),
        usage_meter=None,
        embedding_client=None,
    )


def test_unreachable_server_context_and_matching_footer_are_honest_and_secret_free(
    monkeypatch, tmp_path: Path,
) -> None:
    captured: list[tuple[str, ...]] = []

    async def fake_turn(**kwargs):  # noqa: ANN003, ANN202
        captured.append(tuple(kwargs["system_context_notes"]))
        used = ("mcp__blender_mac_ronny__inspect",) if kwargs["turn_id"] == "turn3" else ()
        return NativeAgentOutcome(
            "final_answer", "I cannot access Blender.", 1,
            used_tool_names=used, successful_tool_names=used,
        )

    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: rows)
    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        _owner(tmp_path), message="Bitte in Blender nachsehen", user_id="alice",
        request_id="turn", source="test", start=0.0, language="de",
    ))
    assert result is not None
    assert len(captured) == 1 and len(captured[0]) == 1
    assert "blender-mac-ronny" in captured[0][0]
    assert "temporarily unreachable" in captured[0][0]
    assert "TimeoutError" in captured[0][0]
    assert "secret" not in captured[0][0]
    assert result.text.count("⚠️ Der MCP-Server blender-mac-ronny") == 1
    assert "[Neu verbinden](/config/connections/mcp)" in result.text

    unrelated = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        _owner(tmp_path), message="Wie geht es dir?", user_id="alice",
        request_id="turn2", source="test", start=0.0, language="de",
    ))
    assert unrelated is not None
    assert "MCP-Server" not in unrelated.text

    used_mcp = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        _owner(tmp_path), message="Bitte in Blender nachsehen", user_id="alice",
        request_id="turn3", source="test", start=0.0, language="de",
    ))
    assert used_mcp is not None
    assert "⚠️ Der MCP-Server" not in used_mcp.text


def test_unreachable_context_note_is_injected_into_provider_system_message(tmp_path: Path) -> None:
    calls: list[dict] = []

    async def handler(_context: NativeToolContext, _arguments: dict) -> NativeToolResult:
        return NativeToolResult('{"status":"ok"}', "test")

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="test", name="read_test", description="Read test data.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False,
        source_authority="test:store", user_scoped=True, rollout_flag="test",
    ), handler)

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="temporarily unavailable", tool_calls=[]),
            finish_reason="stop",
        )])

    outcome = asyncio.run(run_native_agent_turn(
        message="use blender", user_id="alice", turn_id="context-note",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=completion, trace_root=tmp_path,
        system_context_notes=(
            "MCP server blender capability EXISTS but is temporarily unreachable (TimeoutError).",
        ),
    ))

    assert outcome.kind == "final_answer"
    system = str(calls[0]["messages"][0]["content"])
    assert "authoritative availability state" in system
    assert "temporarily unreachable (TimeoutError)" in system


def test_non_text_mcp_content_is_replaced_without_base64_and_text_is_kept() -> None:
    encoded = "aGVsbG8=" * 1000
    payload = [
        {"type": "text", "text": "visible text"},
        {"type": "image", "data": encoded, "mimeType": "image/png"},
        {"type": "audio", "data": encoded, "mimeType": "audio/wav"},
        {"type": "resource", "resource": {"blob": encoded, "mimeType": "application/octet-stream"}},
    ]

    serialized = _json_value(payload)
    rendered = json.dumps(serialized, sort_keys=True)
    assert serialized[0] == {"type": "text", "text": "visible text"}
    assert all(row["omitted"] is True for row in serialized[1:])
    assert "NOT visible" in rendered
    assert encoded[:100] not in rendered


def test_completion_notice_preserves_lines_bounds_text_and_does_not_split_markdown_link(
    tmp_path: Path,
) -> None:
    pipeline = Pipeline.__new__(Pipeline)
    notices: list[dict[str, object]] = []
    pipeline._agent_job_notifier = lambda _user_id, **payload: notices.append(payload)
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="aj-lines", user_id="alice", goal="goal", status="detached")
    store.set_terminal("aj-lines", status="done", result="done")
    result = "First   line\r\n- second    line\n\n\n" + ("x" * 1490) + " [details](/long/link) tail"

    asyncio.run(pipeline._notify_agent_job_terminal(
        store=store, job_id="aj-lines", user_id="alice", language="en",
        status="done", result=result,
    ))

    text = str(notices[0]["text"])
    assert "First line\n- second line\n\n" in text
    assert "\r" not in text
    assert len(text) < 1700
    assert "[details](/long/" not in text
    assert "[View job →](/jobs/panel?job=aj-lines#job-aj-lines)" in text
