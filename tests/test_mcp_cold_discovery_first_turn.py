from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import time
from types import SimpleNamespace

import aria.main as aria_main
from aria.modules.configuration_foundations.config import MCPServerConfig, Settings
from aria.modules.mcp.runtime import MCPClientManager
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.handler import NativeAgentOutcome
from aria.modules.pipeline_orchestrator.pipeline import Pipeline


def _server(**overrides) -> MCPServerConfig:  # noqa: ANN003
    payload = {
        "transport": "sse",
        "url": "https://mcp.invalid/events",
        "enabled": True,
    }
    payload.update(overrides)
    return MCPServerConfig.model_validate(payload)


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description="Test-only MCP Tool.",
        input_schema={"type": "object", "properties": {}},
        annotations=SimpleNamespace(read_only_hint=True),
    )


class _Session:
    def __init__(self, tools=()) -> None:  # noqa: ANN001
        self.tools = tuple(tools)
        self.list_calls = 0

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> SimpleNamespace:
        self.list_calls += 1
        return SimpleNamespace(tools=self.tools)


class _Factory:
    def __init__(self, session: _Session, *, fail: bool = False, delayed: bool = False) -> None:
        self.session = session
        self.fail = fail
        self.delayed = delayed
        self.opens = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @asynccontextmanager
    async def __call__(self, _server_name: str, _config: MCPServerConfig):
        self.opens += 1
        self.started.set()
        if self.delayed:
            await self.release.wait()
        if self.fail:
            raise ConnectionError("private endpoint detail")
        yield self.session


def _settings(*, enabled: bool = True) -> Settings:
    return Settings.model_validate({
        "llm": {"model": "fake"},
        "memory": {"enabled": False},
        "token_tracking": {"enabled": False},
        "agentic_loop": {"enabled": True, "native_agent_mcp_enabled": enabled},
        "mcp_servers": {"blender": _server().model_dump()},
    })


class _PromptLoader:
    def get_persona(self) -> str:
        return "ARIA"


class _LLM:
    usage_meter = None


class _Embedder:
    async def embed(self, inputs, **_kwargs):  # noqa: ANN001, ANN003
        return SimpleNamespace(vectors=[[1.0, float(index)] for index, _ in enumerate(inputs)])


def _pipeline(tmp_path) -> Pipeline:  # noqa: ANN001
    owner = Pipeline(
        settings=_settings(), prompt_loader=_PromptLoader(), llm_client=_LLM(),
        embedding_client=_Embedder(),
    )
    owner._project_root = tmp_path
    owner._stored_recipes_dir = tmp_path / "recipes"
    return owner


def test_cold_blocking_discovery_waits_once_and_returns_first_tools() -> None:
    async def scenario() -> None:
        factory = _Factory(_Session([_tool("execute_blender_code")]), delayed=True)
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)

        first = asyncio.create_task(manager.discover_all(block_cold=True))
        await asyncio.wait_for(factory.started.wait(), timeout=0.2)
        assert not first.done()
        factory.release.set()
        discovered = await asyncio.wait_for(first, timeout=0.2)

        assert [tool.remote_name for tool in discovered["blender"]] == ["execute_blender_code"]
        assert factory.opens == 1

    asyncio.run(scenario())


def test_multiple_cold_servers_share_one_parallel_bounded_wait() -> None:
    async def scenario() -> None:
        factory = _Factory(_Session([_tool("inspect")]), delayed=True)
        manager = MCPClientManager(
            {"alpha": _server(), "beta": _server()}, session_factory=factory,
        )

        discovery = asyncio.create_task(manager.discover_all(block_cold=True))
        for _ in range(20):
            if factory.opens == 2:
                break
            await asyncio.sleep(0)

        assert factory.opens == 2
        assert not discovery.done()
        factory.release.set()
        result = await asyncio.wait_for(discovery, timeout=0.2)
        assert set(result) == {"alpha", "beta"}

    asyncio.run(scenario())


def test_cold_failure_is_cached_and_second_turn_does_not_wait_or_reopen() -> None:
    async def scenario() -> None:
        factory = _Factory(_Session(), fail=True)
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)

        first = await manager.discover_all(block_cold=True)
        started = time.perf_counter()
        second = await manager.discover_all(block_cold=True)
        elapsed = time.perf_counter() - started

        assert first["blender"] == second["blender"] == ()
        assert factory.opens == 1
        assert elapsed < 0.05
        assert manager.statuses()[0].error == "ConnectionError"

    asyncio.run(scenario())


def test_warm_stale_server_returns_cached_tools_while_refresh_runs_in_background() -> None:
    async def scenario() -> None:
        now = [100.0]
        session = _Session([_tool("get_scene_info")])
        warm_factory = _Factory(session)
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=warm_factory, clock=lambda: now[0],
        )
        await manager.discover_all(refresh=True)

        now[0] += 301.0
        started = time.perf_counter()
        cached = await manager.discover_all(block_cold=True)
        elapsed = time.perf_counter() - started

        assert [tool.remote_name for tool in cached["blender"]] == ["get_scene_info"]
        assert elapsed < 0.05
        for _ in range(20):
            if session.list_calls >= 2:
                break
            await asyncio.sleep(0)
        assert session.list_calls == 2
        # The cached snapshot remains non-blocking while Alpha970 recycles the
        # idle persistent session before the background refresh.
        assert warm_factory.opens == 2

    asyncio.run(scenario())


def test_down_server_in_cooldown_is_immediate_and_makes_no_new_network_call() -> None:
    async def scenario() -> None:
        now = [100.0]
        factory = _Factory(_Session(), fail=True)
        manager = MCPClientManager(
            {"blender": _server()}, session_factory=factory, clock=lambda: now[0],
        )
        await manager.discover_all(refresh=True)

        started = time.perf_counter()
        discovered = await manager.discover_all(block_cold=True)
        elapsed = time.perf_counter() - started

        assert discovered["blender"] == ()
        assert elapsed < 0.05
        assert factory.opens == 1

    asyncio.run(scenario())


def test_pipeline_first_turn_blocks_for_cold_discovery_and_assembles_mcp_tool(
    monkeypatch, tmp_path,
) -> None:  # noqa: ANN001
    captured: dict[str, object] = {}

    async def fake_turn(**kwargs):  # noqa: ANN003, ANN202
        captured["names"] = tuple(binding.contract.name for binding in kwargs["tool_bindings"])
        return NativeAgentOutcome(
            "final_answer", "scene created", 1,
            used_tool_names=("mcp__blender__execute_blender_code",),
            successful_tool_names=("mcp__blender__execute_blender_code",),
        )

    factory = _Factory(_Session([_tool("execute_blender_code")]))
    owner = _pipeline(tmp_path)
    owner._native_mcp_client = MCPClientManager(
        {"blender": _server()}, session_factory=factory,
    )
    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="build the scene", user_id="alice", request_id="cold-first-turn",
        source="test", start=0.0,
    ))

    assert result is not None and result.text == "scene created"
    assert "mcp__blender__execute_blender_code" in captured["names"]
    assert factory.opens == 1
    assert any("server=blender status=connected tool_count=1" in line for line in result.detail_lines)


def test_startup_warmup_is_background_noop_when_off_and_swallows_down_server() -> None:
    async def scenario() -> None:
        factory = _Factory(_Session(), fail=True, delayed=True)
        manager = MCPClientManager({"blender": _server()}, session_factory=factory)
        pipeline = SimpleNamespace(_native_mcp_client=manager)
        schedule = getattr(aria_main, "_schedule_mcp_startup_warmup")

        assert schedule(pipeline, _settings(enabled=False)) is None
        disabled_manager = MCPClientManager({"disabled": _server(enabled=False)})
        assert schedule(
            SimpleNamespace(_native_mcp_client=disabled_manager), _settings(enabled=True),
        ) is None
        started = time.perf_counter()
        task = schedule(pipeline, _settings(enabled=True))
        elapsed = time.perf_counter() - started

        assert task is not None
        assert elapsed < 0.05
        await asyncio.wait_for(factory.started.wait(), timeout=0.2)
        factory.release.set()
        await asyncio.wait_for(task, timeout=0.2)
        assert manager.statuses()[0].connected is False
        assert manager.statuses()[0].error == "ConnectionError"

    asyncio.run(scenario())
