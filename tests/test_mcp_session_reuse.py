from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace

import aria.main as aria_main
from aria.modules.configuration_foundations.config import MCPServerConfig
from aria.modules.mcp.runtime import MCPClientManager


def _server() -> MCPServerConfig:
    return MCPServerConfig.model_validate({
        "transport": "sse",
        "url": "https://mcp.invalid/events",
        "enabled": True,
    })


def _tool(name: str = "inspect") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description="Test-only MCP Tool.",
        input_schema={"type": "object", "properties": {}},
        annotations=SimpleNamespace(read_only_hint=True),
    )


def _success(text: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        is_error=False,
        content=[SimpleNamespace(type="text", text=text)],
        structured_content={"status": "ok"},
    )


class _Activity:
    def __init__(self, *, wait_for_two: bool = False) -> None:
        self.active = 0
        self.maximum = 0
        self.wait_for_two = wait_for_two
        self.two_active = asyncio.Event()
        self.release = asyncio.Event()

    async def enter(self) -> None:
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        if self.active >= 2:
            self.two_active.set()
        if self.wait_for_two:
            await self.release.wait()
        else:
            await asyncio.sleep(0.01)

    def leave(self) -> None:
        self.active -= 1


class _Session:
    def __init__(
        self,
        label: str,
        *,
        tools: tuple[SimpleNamespace, ...] = (),
        call_error: Exception | None = None,
        list_error: Exception | None = None,
        activity: _Activity | None = None,
    ) -> None:
        self.label = label
        self.tools = tools
        self.call_error = call_error
        self.list_error = list_error
        self.activity = activity
        self.owner_task: asyncio.Task[object] | None = None
        self.initialize_calls = 0
        self.list_calls = 0
        self.tool_calls: list[tuple[str, dict]] = []

    async def initialize(self) -> None:
        assert asyncio.current_task() is self.owner_task
        self.initialize_calls += 1

    async def list_tools(self, *, cursor: str | None = None) -> SimpleNamespace:
        assert asyncio.current_task() is self.owner_task
        del cursor
        self.list_calls += 1
        if self.list_error is not None:
            raise self.list_error
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
        assert asyncio.current_task() is self.owner_task
        self.tool_calls.append((name, arguments))
        if self.activity is not None:
            await self.activity.enter()
        try:
            if self.call_error is not None:
                raise self.call_error
            return _success(self.label)
        finally:
            if self.activity is not None:
                self.activity.leave()


class _Factory:
    def __init__(self, sessions: dict[str, list[_Session | Exception]]) -> None:
        self.sessions = sessions
        self.opens: list[str] = []
        self.closes: list[str] = []

    @asynccontextmanager
    async def __call__(self, server_name: str, _config: MCPServerConfig):
        self.opens.append(server_name)
        rows = self.sessions[server_name]
        index = min(self.opens.count(server_name) - 1, len(rows) - 1)
        selected = rows[index]
        if isinstance(selected, Exception):
            raise selected
        selected.owner_task = asyncio.current_task()
        try:
            yield selected
        finally:
            assert asyncio.current_task() is selected.owner_task
            self.closes.append(selected.label)


def test_discovery_and_many_calls_reuse_one_server_session_until_shutdown() -> None:
    async def scenario() -> None:
        session = _Session("shared", tools=(_tool(),))
        factory = _Factory({"blender": [session]})
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)

        discovered = await manager.discover_all(refresh=True)
        refreshed = await manager.discover_all(refresh=True)
        outcomes = [
            await manager._call_remote("blender", "inspect", {"step": index}, intent="inspect")
            for index in range(3)
        ]

        assert len(discovered["blender"]) == 1
        assert len(refreshed["blender"]) == 1
        assert all(json.loads(row.content)["status"] == "ok" for row in outcomes)
        assert factory.opens == ["blender"]
        assert factory.closes == []
        assert session.initialize_calls == 1
        assert session.list_calls == 2
        assert len(session.tool_calls) == 3

        await manager.close()
        assert factory.closes == ["shared"]

    asyncio.run(scenario())


def test_same_server_concurrent_calls_are_serialized() -> None:
    async def scenario() -> None:
        activity = _Activity()
        session = _Session("shared", tools=(_tool(),), activity=activity)
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=_Factory({"blender": [session]}),
        )
        await manager.discover_all(refresh=True)

        first, second = await asyncio.gather(
            manager._call_remote("blender", "inspect", {"step": 1}, intent="inspect"),
            manager._call_remote("blender", "inspect", {"step": 2}, intent="inspect"),
        )

        assert json.loads(first.content)["status"] == "ok"
        assert json.loads(second.content)["status"] == "ok"
        assert activity.maximum == 1
        await manager.close()

    asyncio.run(scenario())


def test_transport_error_reconnects_once_and_retries_the_call() -> None:
    async def scenario() -> None:
        dropped = _Session(
            "dropped", tools=(_tool(),), call_error=ConnectionError("transport closed"),
        )
        recovered = _Session("recovered", tools=(_tool(),))
        factory = _Factory({"blender": [dropped, recovered]})
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)
        await manager.discover_all(refresh=True)

        outcome = await manager._call_remote(
            "blender", "inspect", {"step": 1}, intent="inspect",
        )

        assert json.loads(outcome.content)["status"] == "ok"
        assert factory.opens == ["blender", "blender"]
        assert factory.closes == ["dropped"]
        assert dropped.tool_calls == [("inspect", {"step": 1})]
        assert recovered.tool_calls == [("inspect", {"step": 1})]
        await manager.close()
        assert factory.closes == ["dropped", "recovered"]

    asyncio.run(scenario())


def test_failed_reconnect_returns_honest_call_error_without_looping() -> None:
    async def scenario() -> None:
        first = _Session(
            "first", tools=(_tool(),), call_error=BrokenPipeError("first drop"),
        )
        second = _Session(
            "second", tools=(_tool(),), call_error=ConnectionError("second drop"),
        )
        factory = _Factory({"blender": [first, second]})
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)
        await manager.discover_all(refresh=True)

        outcome = await manager._call_remote("blender", "inspect", {}, intent="inspect")

        assert json.loads(outcome.content) == {"error": "mcp_call_failed", "status": "error"}
        assert factory.opens == ["blender", "blender"]
        assert factory.closes == ["first", "second"]
        await manager.close()

    asyncio.run(scenario())


def test_different_servers_have_independent_sessions_and_locks() -> None:
    async def scenario() -> None:
        activity = _Activity(wait_for_two=True)
        alpha = _Session("alpha", tools=(_tool(),), activity=activity)
        beta = _Session("beta", tools=(_tool(),), activity=activity)
        factory = _Factory({"alpha": [alpha], "beta": [beta]})
        manager = MCPClientManager(
            {"alpha": _server(), "beta": _server()}, session_factory=factory,
        )
        await manager.discover_all(refresh=True)

        calls = asyncio.gather(
            manager._call_remote("alpha", "inspect", {}, intent="alpha"),
            manager._call_remote("beta", "inspect", {}, intent="beta"),
        )
        await asyncio.wait_for(activity.two_active.wait(), timeout=0.2)
        activity.release.set()
        outcomes = await asyncio.wait_for(calls, timeout=0.2)

        assert activity.maximum == 2
        assert all(json.loads(row.content)["status"] == "ok" for row in outcomes)
        assert sorted(factory.opens) == ["alpha", "beta"]
        await manager.close()

    asyncio.run(scenario())


def test_down_server_cooldown_snapshot_does_not_reopen_session() -> None:
    async def scenario() -> None:
        now = [100.0]
        factory = _Factory({"down": [ConnectionError("private endpoint")]} )
        manager = MCPClientManager(
            {"down": _server()}, session_factory=factory, clock=lambda: now[0],
        )

        first = await manager.discover_all(refresh=True)
        second = await manager.discover_all(block_cold=True)

        assert first["down"] == second["down"] == ()
        assert factory.opens == ["down"]
        assert manager.statuses()[0].error == "ConnectionError"
        await manager.close()

    asyncio.run(scenario())


def test_discovery_reconnect_failure_enters_cooldown_without_third_open() -> None:
    async def scenario() -> None:
        now = [100.0]
        first = _Session("first", list_error=ConnectionError("transport dropped"))
        second = _Session("second", list_error=BrokenPipeError("reconnect dropped"))
        factory = _Factory({"down": [first, second]})
        manager = MCPClientManager(
            {"down": _server()}, session_factory=factory, clock=lambda: now[0],
        )

        failed = await manager.discover_all(refresh=True)
        cached = await manager.discover_all(block_cold=True)

        assert failed["down"] == cached["down"] == ()
        assert factory.opens == ["down", "down"]
        assert factory.closes == ["first", "second"]
        assert manager.statuses()[0].error == "BrokenPipeError"
        await manager.close()

    asyncio.run(scenario())


def test_main_shutdown_helper_closes_mcp_manager() -> None:
    class _Manager:
        def __init__(self) -> None:
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1

    async def scenario() -> None:
        manager = _Manager()
        await aria_main._close_mcp_sessions(SimpleNamespace(_native_mcp_client=manager))
        assert manager.close_calls == 1

    asyncio.run(scenario())


def test_closing_session_during_inflight_call_returns_honest_error_not_cancellation() -> None:
    class _BlockingSession(_Session):
        def __init__(self) -> None:
            super().__init__("blocking", tools=(_tool(),))
            self.call_started = asyncio.Event()

        async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
            assert asyncio.current_task() is self.owner_task
            self.tool_calls.append((name, arguments))
            self.call_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def scenario() -> None:
        blocking = _BlockingSession()
        manager = MCPClientManager(
            {"blender": _server()},
            session_factory=_Factory({"blender": [blocking]}),
        )
        await manager.discover_all(refresh=True)

        caller = asyncio.create_task(
            manager._call_remote("blender", "inspect", {}, intent="inspect"),
        )
        await asyncio.wait_for(blocking.call_started.wait(), timeout=0.2)
        await manager._close_server_session("blender")
        outcome = await asyncio.wait_for(caller, timeout=0.2)

        assert caller.cancelled() is False
        assert json.loads(outcome.content) == {
            "error": "mcp_call_failed",
            "status": "error",
        }
        await manager.close()

    asyncio.run(scenario())


def test_explicit_reconnect_drops_session_and_replaces_cached_discovery() -> None:
    async def scenario() -> None:
        stale = _Session("stale", tools=(_tool("old_tool"),))
        recovered = _Session(
            "recovered", tools=(_tool("inspect"), _tool("render")),
        )
        factory = _Factory({"blender": [stale, recovered]})
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=factory, clock=lambda: 100.0,
        )
        await manager.discover_all(refresh=True)
        manager._failure_at["blender"] = 99.0

        status = await manager.reconnect("blender")

        assert status.server_name == "blender"
        assert status.connected is True
        assert status.tool_count == 2
        assert status.error == ""
        assert manager._failure_at.get("blender") is None
        assert [tool.remote_name for tool in manager._discovery["blender"]] == [
            "inspect", "render",
        ]
        assert factory.opens == ["blender", "blender"]
        assert factory.closes == ["stale"]
        await manager.close()
        assert factory.closes == ["stale", "recovered"]

    asyncio.run(scenario())


def test_explicit_reconnect_still_down_is_honest_and_leaves_no_worker() -> None:
    async def scenario() -> None:
        stale = _Session("stale", tools=(_tool(),))
        factory = _Factory({
            "blender": [stale, ConnectionError("private endpoint")],
        })
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=factory, clock=lambda: 100.0,
        )
        await manager.discover_all(refresh=True)

        status = await manager.reconnect("blender")

        assert status.server_name == "blender"
        assert status.connected is False
        assert status.tool_count == 0
        assert status.error == "ConnectionError"
        assert "blender" not in manager._session_workers
        assert "blender" not in manager._session_queues
        assert manager._discovery["blender"] == ()
        assert manager._failure_at["blender"] == 100.0
        assert factory.closes == ["stale"]
        await manager.close()

    asyncio.run(scenario())


def test_explicit_reconnect_bypasses_active_failure_cooldown() -> None:
    async def scenario() -> None:
        recovered = _Session("recovered", tools=(_tool(),))
        factory = _Factory({"blender": [recovered]})
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=factory, clock=lambda: 100.0,
        )
        manager._failure_at["blender"] = 99.0
        manager._discovery["blender"] = ()
        manager._discovered_at["blender"] = 99.0

        cached = await manager.discover_all(block_cold=True)
        assert cached["blender"] == ()
        assert factory.opens == []

        status = await manager.reconnect("blender")

        assert status.connected is True
        assert status.tool_count == 1
        assert factory.opens == ["blender"]
        assert "blender" not in manager._failure_at
        await manager.close()

    asyncio.run(scenario())


def test_explicit_reconnect_cancels_inflight_refresh_before_fresh_discovery() -> None:
    class _WedgedSession(_Session):
        def __init__(self) -> None:
            super().__init__("wedged")
            self.started = asyncio.Event()

        async def list_tools(self, *, cursor: str | None = None) -> SimpleNamespace:
            assert asyncio.current_task() is self.owner_task
            del cursor
            self.started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def scenario() -> None:
        wedged = _WedgedSession()
        recovered = _Session("recovered", tools=(_tool(),))
        factory = _Factory({"blender": [wedged, recovered]})
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=factory,
        )

        await manager.discover_all()
        await asyncio.wait_for(wedged.started.wait(), timeout=0.2)

        status = await manager.reconnect("blender")

        assert status.connected is True
        assert status.tool_count == 1
        assert factory.opens == ["blender", "blender"]
        assert factory.closes == ["wedged"]
        assert "blender" not in manager._refresh_tasks
        await manager.close()

    asyncio.run(scenario())


def test_explicit_reconnect_unknown_and_disabled_are_safe() -> None:
    async def scenario() -> None:
        disabled = MCPServerConfig.model_validate({
            "transport": "sse",
            "url": "https://mcp.invalid/events",
            "enabled": False,
        })
        factory = _Factory({"disabled": [_Session("unused")]})
        manager = MCPClientManager(
            {"disabled": disabled}, session_factory=factory,
        )

        missing = await manager.reconnect("missing")
        disabled_status = await manager.reconnect("disabled")

        assert missing.server_name == "missing"
        assert missing.connected is False
        assert missing.tool_count == 0
        assert missing.error == "not_found"
        assert disabled_status.server_name == "disabled"
        assert disabled_status.connected is False
        assert disabled_status.tool_count == 0
        assert disabled_status.error == "disabled"
        assert factory.opens == []
        await manager.close()

    asyncio.run(scenario())
