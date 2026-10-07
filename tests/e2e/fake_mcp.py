"""Controllable Blender-like MCP SSE fake for isolated browser E2E tests."""

from __future__ import annotations

import argparse
import asyncio
import base64
from multiprocessing import Manager, Process
import re
import signal
from typing import Any, MutableMapping, MutableSequence

from fastapi import FastAPI, Request
from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent, TextContent, ToolAnnotations
import uvicorn


_ONE_PIXEL_PNG = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)).decode("ascii")
_MISLABELED_WEBP = base64.b64encode(
    b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"aria-e2e-webp"
).decode("ascii")


class FakeMCPState:
    def __init__(
        self,
        *,
        scene: MutableSequence[str] | None = None,
        calls: MutableSequence[dict[str, Any]] | None = None,
        behavior: MutableMapping[str, Any] | None = None,
    ) -> None:
        self.scene = scene if scene is not None else []
        self.calls = calls if calls is not None else []
        self.behavior = behavior if behavior is not None else {"hang": False}

    def reset(self) -> None:
        self.scene[:] = []
        self.calls[:] = []
        self.behavior["hang"] = False

    def record(self, tool: str, arguments: dict[str, Any]) -> None:
        self.calls.append({"tool": str(tool), "arguments": dict(arguments)})

    def add_objects_from_code(self, code: str) -> list[str]:
        candidates: list[str] = []
        patterns = (
            r"\bname\s*=\s*['\"]([^'\"]{1,80})['\"]",
            r"objects\.new\(\s*['\"]([^'\"]{1,80})['\"]",
            r"primitive_[a-z_]+_add\([^\n]*?['\"]([^'\"]{1,80})['\"]",
        )
        for pattern in patterns:
            candidates.extend(re.findall(pattern, str(code), flags=re.IGNORECASE))
        for name in candidates:
            if name not in self.scene:
                self.scene.append(name)
        return candidates

    def snapshot(self) -> dict[str, Any]:
        return {
            "scene": list(self.scene),
            "calls": list(self.calls),
            "behavior": dict(self.behavior),
        }


def create_mcp_server(state: FakeMCPState) -> MCPServer:
    server = MCPServer("ARIA E2E Blender", version="1.0")

    async def maybe_hang() -> None:
        if bool(state.behavior.get("hang")):
            await asyncio.sleep(120)

    @server.tool(
        description="Return the in-memory Blender scene listing.",
        annotations=ToolAnnotations(readOnlyHint=True),
        structured_output=False,
    )
    async def get_scene_info() -> str:
        state.record("get_scene_info", {})
        await maybe_hang()
        objects = list(state.scene)
        return "Scene objects: " + (", ".join(objects) if objects else "(empty)")

    @server.tool(
        description="Execute Blender Python code in the isolated in-memory fake.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True),
        structured_output=False,
    )
    async def execute_blender_code(code: str) -> str:
        state.record("execute_blender_code", {"code": str(code)})
        await maybe_hang()
        state.add_objects_from_code(str(code))
        return "Code executed successfully"

    @server.tool(
        description="Return a tiny valid PNG view of the fake scene.",
        annotations=ToolAnnotations(readOnlyHint=True),
        structured_output=False,
    )
    async def look() -> list[TextContent | ImageContent]:
        state.record("look", {})
        await maybe_hang()
        return [
            TextContent(type="text", text="Rendered fake Blender scene."),
            ImageContent(type="image", data=_ONE_PIXEL_PNG, mimeType="image/png"),
        ]

    @server.tool(
        description="Return a search result image whose server declaration is intentionally wrong.",
        annotations=ToolAnnotations(readOnlyHint=True),
        structured_output=False,
    )
    async def search_assets() -> list[TextContent | ImageContent]:
        state.record("search_assets", {})
        await maybe_hang()
        return [
            TextContent(type="text", text="Found one fake Poly Haven asset."),
            ImageContent(type="image", data=_MISLABELED_WEBP, mimeType="image/png"),
        ]

    return server


def _run_listener(
    host: str,
    port: int,
    scene: MutableSequence[str],
    calls: MutableSequence[dict[str, Any]],
    behavior: MutableMapping[str, Any],
) -> None:
    state = FakeMCPState(scene=scene, calls=calls, behavior=behavior)
    asyncio.run(create_mcp_server(state).run_sse_async(
        host=host,
        port=port,
        sse_path="/sse",
        message_path="/messages/",
    ))


class FakeMCPController:
    def __init__(self, host: str, port: int, *, start_listener: bool = True) -> None:
        self.host = host
        self.port = int(port)
        self._manager = Manager() if start_listener else None
        if self._manager is None:
            self.state = FakeMCPState()
        else:
            self.state = FakeMCPState(
                scene=self._manager.list(),
                calls=self._manager.list(),
                behavior=self._manager.dict({"hang": False}),
            )
        self.process: Process | None = None
        self.simulated_running = False
        self.start_listener = start_listener

    @property
    def running(self) -> bool:
        if not self.start_listener:
            return self.simulated_running
        return bool(self.process and self.process.is_alive())

    def start(self) -> None:
        if self.running:
            return
        if not self.start_listener:
            self.simulated_running = True
            return
        self.process = Process(
            target=_run_listener,
            args=(self.host, self.port, self.state.scene, self.state.calls, self.state.behavior),
            daemon=True,
            name="aria-e2e-fake-mcp-listener",
        )
        self.process.start()

    def stop(self) -> None:
        if not self.start_listener:
            self.simulated_running = False
            return
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=2)
        self.process = None

    def close(self) -> None:
        self.stop()
        if self._manager is not None:
            self._manager.shutdown()


def create_control_app(controller: FakeMCPController) -> FastAPI:
    app = FastAPI(title="ARIA fake MCP control")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "listener_running": controller.running}

    @app.get("/__control/logs")
    async def logs() -> dict[str, Any]:
        return {**controller.state.snapshot(), "listener_running": controller.running}

    @app.post("/__control/reset")
    async def reset() -> dict[str, Any]:
        controller.state.reset()
        return {"ok": True, **controller.state.snapshot(), "listener_running": controller.running}

    @app.post("/__control/behavior")
    async def behavior(request: Request) -> dict[str, Any]:
        payload = await request.json()
        controller.state.behavior["hang"] = bool(payload.get("hang"))
        return {"ok": True, "behavior": dict(controller.state.behavior)}

    @app.post("/__control/stop")
    async def stop() -> dict[str, Any]:
        controller.stop()
        return {"ok": True, "listener_running": controller.running}

    @app.post("/__control/start")
    async def start() -> dict[str, Any]:
        controller.start()
        return {"ok": True, "listener_running": controller.running}

    @app.post("/__control/drop")
    async def drop() -> dict[str, Any]:
        controller.stop()
        return {"ok": True, "listener_running": controller.running, "mode": "half_open_drop"}

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mcp-port", type=int, default=9000)
    parser.add_argument("--control-port", type=int, default=9001)
    args = parser.parse_args()
    controller = FakeMCPController(args.host, args.mcp_port)
    controller.start()

    def shutdown(*_args: Any) -> None:
        controller.close()

    signal.signal(signal.SIGTERM, shutdown)
    try:
        uvicorn.run(create_control_app(controller), host=args.host, port=args.control_port, log_level="warning")
    finally:
        controller.close()


if __name__ == "__main__":
    main()
