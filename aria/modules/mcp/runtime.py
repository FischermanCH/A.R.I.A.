"""Cached, fail-soft MCP discovery and confirmation-aware Native Tool bindings."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
import json
import logging
import re
import time
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from aria.modules.configuration_foundations.config import MCPServerConfig
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

LOGGER = logging.getLogger(__name__)
SUPPORTED_MCP_TRANSPORTS = frozenset({"sse", "http"})
MCP_DISCOVERY_TIMEOUT_SECONDS = 8.0
MCP_DISCOVERY_FAILURE_COOLDOWN_SECONDS = 30.0
MCP_DISCOVERY_REFRESH_INTERVAL_SECONDS = 300.0
MCP_SESSION_IDLE_RECYCLE_SECONDS = 120.0
MCP_TRANSPORT_CONNECT_TIMEOUT_SECONDS = 15.0
MCP_CALL_TIMEOUT_SECONDS = 30.0
MCP_RESULT_MAX_CHARS = 12000
MCP_PREVIEW_MAX_CHARS = 8000
MCP_RESULT_MAX_IMAGES = 2
MCP_IMAGE_MAX_BASE64_CHARS = 3_500_000
MCP_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


@dataclass(frozen=True, slots=True)
class MCPDiscoveredTool:
    server_name: str
    remote_name: str
    description: str
    input_schema: Mapping[str, Any]
    annotations: Mapping[str, Any]
    read_only: bool


@dataclass(frozen=True, slots=True)
class MCPServerStatus:
    server_name: str
    connected: bool
    tool_count: int
    error: str = ""


@dataclass(slots=True)
class _SessionRequest:
    operation: Callable[[Any], Awaitable[Any]]
    timeout: float
    future: asyncio.Future[Any]


class _InitializedClient:
    """Make the v2 SDK Client look like the injected low-level test session."""

    def __init__(self, client: Any) -> None:
        self.client = client

    async def initialize(self) -> None:
        return None

    async def list_tools(self, *, cursor: str | None = None) -> Any:
        if cursor:
            return await self.client.list_tools(cursor=cursor)
        return await self.client.list_tools()

    async def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        return await self.client.call_tool(name, dict(arguments))


@asynccontextmanager
async def official_mcp_session(
    _server_name: str, config: MCPServerConfig,
) -> AsyncIterator[Any]:
    """Open one official-SDK session without importing transport code while disabled."""

    from mcp import Client

    transport_name = str(config.transport or "sse").strip().lower()
    if transport_name == "sse":
        from mcp.client.sse import sse_client

        transport = sse_client(
            str(config.url), headers=dict(config.headers),
            timeout=MCP_TRANSPORT_CONNECT_TIMEOUT_SECONDS,
            sse_read_timeout=float(config.call_timeout_seconds),
        )
        async with Client(transport) as client:
            yield _InitializedClient(client)
        return

    if transport_name == "http":
        import httpx2
        from mcp.client.streamable_http import streamable_http_client

        http_client = httpx2.AsyncClient(
            headers=dict(config.headers),
            timeout=httpx2.Timeout(
                MCP_TRANSPORT_CONNECT_TIMEOUT_SECONDS,
                read=float(config.call_timeout_seconds),
            ),
        )
        async with http_client:
            transport = streamable_http_client(str(config.url), http_client=http_client)
            async with Client(transport) as client:
                yield _InitializedClient(client)
        return

    raise ValueError("unsupported_transport")


def _field(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _sanitize_segment(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return text[:64] or "unnamed"


def _transport_failure_code(exc: BaseException) -> str:
    detail = str(exc or "").strip()
    if detail == "mcp_session_closed":
        return detail
    names = {base.__name__.casefold() for base in type(exc).__mro__}
    transport_names = {
        "transporterror", "networkerror", "connecterror", "connecttimeouterror",
        "readerror", "writeerror", "remoteprotocolerror", "sseerror", "httperror",
    }
    if isinstance(exc, (OSError, asyncio.TimeoutError)) or names.intersection(transport_names):
        code = type(exc).__name__ or "transport_error"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", code)[:80] or "transport_error"
    return ""


def _native_tool_name(server_name: str, remote_name: str) -> str:
    name = f"mcp__{_sanitize_segment(server_name)}__{_sanitize_segment(remote_name)}"
    if len(name) <= 64:
        return name
    suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"{name[:54]}__{suffix}"


def _read_only_annotation(tool: Any) -> bool:
    annotations = _field(tool, "annotations")
    return _field(annotations, "read_only_hint", "readOnlyHint", default=False) is True


def _json_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[depth-limited]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:6000]
    if isinstance(value, Mapping):
        content_type = str(value.get("type") or "").strip().lower()
        if content_type in {"image", "audio"}:
            mime_type = str(
                value.get("mime_type") or value.get("mimeType") or "application/octet-stream"
            )[:160]
            label = "Image" if content_type == "image" else "Audio"
            return {
                "type": content_type,
                "mime_type": mime_type,
                "omitted": True,
                "note": f"{label} returned by the tool; it is NOT visible to you. Do not describe its contents.",
            }
        resource = value.get("resource")
        if (
            content_type == "resource"
            and isinstance(resource, Mapping)
            and resource.get("blob") is not None
        ):
            mime_type = str(
                resource.get("mime_type") or resource.get("mimeType") or "application/octet-stream"
            )[:160]
            return {
                "type": "resource",
                "mime_type": mime_type,
                "omitted": True,
                "note": "Binary resource returned by the tool; it is NOT visible to you. Do not describe its contents.",
            }
        return {
            str(key)[:120]: _json_value(item, depth=depth + 1)
            for key, item in list(value.items())[:80]
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item, depth=depth + 1) for item in value[:20]]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_value(model_dump(mode="json"), depth=depth + 1)
        except Exception:
            return {"type": type(value).__name__}
    if hasattr(value, "__dict__"):
        return _json_value(vars(value), depth=depth + 1)
    return {"type": type(value).__name__}


def _sniff_image_mime_type(data: str) -> str:
    """Return a supported image MIME from bounded leading base64 bytes only."""

    compact = "".join(str(data or "").split())[:64]
    if not compact:
        return ""
    padded = compact + ("=" * ((4 - len(compact) % 4) % 4))
    try:
        prefix = base64.b64decode(padded, validate=True)[:32]
    except Exception:
        return ""
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(prefix) >= 12 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _project_tool_content(content: Any) -> tuple[Any, tuple[tuple[str, str], ...]]:
    """Project MCP content to bounded JSON plus separately carried current-turn images."""

    images: list[tuple[str, str]] = []
    projected: list[Any] = []
    for item in tuple(content or ())[:20]:
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            try:
                value = model_dump(mode="json", exclude_none=True)
            except Exception:
                value = {"type": type(item).__name__}
        else:
            value = item
        if isinstance(value, Mapping) and str(value.get("type") or "").strip().lower() == "image":
            declared_mime_type = str(
                value.get("mime_type") or value.get("mimeType") or "application/octet-stream"
            )[:160].casefold()
            data = str(value.get("data") or "")
            sniffed_mime_type = ""
            if data and len(data) <= MCP_IMAGE_MAX_BASE64_CHARS:
                sniffed_mime_type = _sniff_image_mime_type(data)
            if sniffed_mime_type and len(images) < MCP_RESULT_MAX_IMAGES:
                images.append((sniffed_mime_type, data))
            projected_value = dict(value)
            if sniffed_mime_type:
                projected_value.pop("mimeType", None)
                projected_value["mime_type"] = sniffed_mime_type
            elif declared_mime_type:
                # Preserve the server declaration in the text-only placeholder;
                # unsupported bytes are never attached to a provider request.
                projected_value.pop("mimeType", None)
                projected_value["mime_type"] = declared_mime_type
            projected.append(_json_value(projected_value))
            continue
        projected.append(_json_value(value))
    return projected, tuple(images)


def _bounded_json(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(_json_value(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(rendered) <= MCP_RESULT_MAX_CHARS:
        return rendered
    preview = rendered[:4000]
    return json.dumps({
        "status": str(payload.get("status") or "ok"),
        "truncated": True,
        "preview": preview,
    }, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _ascii_preview_text(value: Any, *, limit: int) -> str:
    encoded = json.dumps(str(value or ""), ensure_ascii=True)[1:-1]
    return encoded[: max(0, int(limit))]


def _confirmation_preview(
    server_name: str, remote_name: str, arguments: Mapping[str, Any],
) -> str:
    rendered_arguments = json.dumps(
        _json_value(dict(arguments)), ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    )[:4000]
    preview = (
        f"server={_ascii_preview_text(server_name, limit=160)}; "
        f"tool={_ascii_preview_text(remote_name, limit=240)}; arguments={rendered_arguments}"
    )
    if str(remote_name).strip().lower() == "execute_blender_code":
        code = _ascii_preview_text(arguments.get("code", ""), limit=3500)
        if code:
            preview = f"{preview}\ncode:\n{code}"
    return preview[:MCP_PREVIEW_MAX_CHARS]


class MCPClientManager:
    """Own server config, cached discovery, projection and bounded calls."""

    def __init__(
        self,
        servers: Mapping[str, MCPServerConfig] | None,
        *,
        session_factory: Callable[[str, MCPServerConfig], Any] = official_mcp_session,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.servers = {
            str(name): config
            for name, config in dict(servers or {}).items()
        }
        self.session_factory = session_factory
        self._clock = clock
        self._discovery: dict[str, tuple[MCPDiscoveredTool, ...]] = {}
        self._statuses: dict[str, MCPServerStatus] = {}
        self._discovered_at: dict[str, float] = {}
        self._failure_at: dict[str, float] = {}
        self._refresh_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_locks: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Lock]] = {}
        self._session_queues: dict[str, asyncio.Queue[_SessionRequest]] = {}
        self._session_workers: dict[str, asyncio.Task[None]] = {}
        self._closed = False

    def _session_lock(self, server_name: str) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        current = self._session_locks.get(server_name)
        if current is None or current[0] is not loop:
            lock = asyncio.Lock()
            self._session_locks[server_name] = (loop, lock)
            return lock
        return current[1]

    async def _session_worker(
        self, server_name: str, config: MCPServerConfig,
        queue: asyncio.Queue[_SessionRequest],
    ) -> None:
        context: Any = None
        session: Any = None
        last_success_at: float | None = None

        async def close_session() -> None:
            nonlocal context, session
            current_context = context
            context = None
            session = None
            if current_context is None:
                return
            try:
                await current_context.__aexit__(None, None, None)
            except Exception as exc:
                LOGGER.warning(
                    "MCP session close failed for server %s (%s)",
                    _sanitize_segment(server_name), type(exc).__name__,
                )

        async def open_session() -> Any:
            nonlocal context, session
            candidate_context = self.session_factory(server_name, config)
            candidate_session = await candidate_context.__aenter__()
            try:
                await candidate_session.initialize()
            except BaseException as exc:
                try:
                    await candidate_context.__aexit__(type(exc), exc, exc.__traceback__)
                except Exception:
                    pass
                raise
            context = candidate_context
            session = candidate_session
            return session

        async def execute(request: _SessionRequest) -> Any:
            nonlocal last_success_at
            if (
                session is not None
                and last_success_at is not None
                and self._clock() - last_success_at >= MCP_SESSION_IDLE_RECYCLE_SECONDS
            ):
                await close_session()
            if session is None:
                await open_session()
            try:
                result = await request.operation(session)
                last_success_at = self._clock()
                return result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await close_session()
                if isinstance(exc, asyncio.TimeoutError):
                    raise
                await open_session()
                try:
                    result = await request.operation(session)
                    last_success_at = self._clock()
                    return result
                except asyncio.CancelledError:
                    await close_session()
                    raise
                except Exception:
                    await close_session()
                    raise

        try:
            while True:
                request = await queue.get()
                try:
                    try:
                        async with asyncio.timeout(max(0.001, float(request.timeout))):
                            result = await execute(request)
                    except asyncio.CancelledError:
                        await close_session()
                        if not request.future.done():
                            request.future.set_exception(RuntimeError("mcp_session_closed"))
                        raise
                    except Exception as exc:
                        if isinstance(exc, asyncio.TimeoutError):
                            await close_session()
                        if not request.future.done():
                            request.future.set_exception(exc)
                    else:
                        if not request.future.done():
                            request.future.set_result(result)
                finally:
                    queue.task_done()
        finally:
            await close_session()
            while not queue.empty():
                request = queue.get_nowait()
                if not request.future.done():
                    request.future.set_exception(RuntimeError("mcp_session_closed"))
                queue.task_done()

    def _ensure_session_worker(
        self, server_name: str, config: MCPServerConfig,
    ) -> asyncio.Queue[_SessionRequest]:
        loop = asyncio.get_running_loop()
        current = self._session_workers.get(server_name)
        if current is not None and not current.done() and current.get_loop() is loop:
            return self._session_queues[server_name]
        queue: asyncio.Queue[_SessionRequest] = asyncio.Queue()
        task = asyncio.create_task(
            self._session_worker(server_name, config, queue),
            name=f"mcp-session-{_sanitize_segment(server_name)}",
        )
        self._session_queues[server_name] = queue
        self._session_workers[server_name] = task

        def finish(completed: asyncio.Task[None]) -> None:
            if self._session_workers.get(server_name) is completed:
                self._session_workers.pop(server_name, None)
                self._session_queues.pop(server_name, None)
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finish)
        return queue

    async def _run_server_operation(
        self, server_name: str, config: MCPServerConfig,
        operation: Callable[[Any], Awaitable[Any]], *, timeout: float,
    ) -> Any:
        if self._closed:
            raise RuntimeError("mcp_client_closed")
        loop = asyncio.get_running_loop()
        started = loop.time()
        lock = self._session_lock(server_name)
        async with asyncio.timeout(max(0.001, float(timeout))):
            await lock.acquire()
            try:
                remaining = max(0.001, float(timeout) - (loop.time() - started))
                queue = self._ensure_session_worker(server_name, config)
                future: asyncio.Future[Any] = loop.create_future()
                queue.put_nowait(_SessionRequest(
                    operation=operation, timeout=remaining, future=future,
                ))
                return await future
            finally:
                lock.release()

    async def _cancel_server_refresh(self, server_name: str) -> None:
        task = self._refresh_tasks.get(server_name)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._refresh_tasks.get(server_name) is task:
            self._refresh_tasks.pop(server_name, None)

    async def _close_server_session(self, server_name: str) -> None:
        """Close one session through its task-affine worker cleanup path."""

        task = self._session_workers.get(server_name)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._session_workers.get(server_name) is task:
            self._session_workers.pop(server_name, None)
            self._session_queues.pop(server_name, None)

    async def close(self) -> None:
        """Cancel discovery work and close every live server session in its owner task."""

        self._closed = True
        refresh_names = tuple(self._refresh_tasks)
        if refresh_names:
            await asyncio.gather(*(
                self._cancel_server_refresh(server_name)
                for server_name in refresh_names
            ))
        self._refresh_tasks.clear()

        server_names = set(self._session_workers) | set(self._session_locks)
        if server_names:
            await asyncio.gather(*(
                self._close_server_session(server_name)
                for server_name in server_names
            ))
        self._session_workers.clear()
        self._session_queues.clear()
        self._session_locks.clear()

    async def reconnect(self, server_name: str) -> MCPServerStatus:
        """Force a clean, scoped reconnect and discovery for one enabled server."""

        name = str(server_name or "").strip()
        config = self.servers.get(name)
        if config is None:
            return MCPServerStatus(name, False, 0, "not_found")
        if not bool(config.enabled):
            return MCPServerStatus(name, False, 0, "disabled")
        if self._closed:
            return MCPServerStatus(name, False, 0, "client_closed")
        if str(config.transport or "sse").strip().lower() not in SUPPORTED_MCP_TRANSPORTS:
            self._set_unsupported_transport(name)
            return self._statuses[name]

        try:
            await self._cancel_server_refresh(name)
            await self._close_server_session(name)
            self._failure_at.pop(name, None)
            self._discovery.pop(name, None)
            self._discovered_at.pop(name, None)
            self._statuses.pop(name, None)
            await self._refresh_server(name, config)
            status = self._statuses.get(name)
            if status is None:
                status = MCPServerStatus(name, False, 0, "discovery_failed")
                self._statuses[name] = status
            if not status.connected:
                await self._close_server_session(name)
            return status
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive lifecycle boundary
            error = type(exc).__name__
            status = MCPServerStatus(name, False, 0, error)
            self._failure_at[name] = self._clock()
            self._discovery[name] = ()
            self._discovered_at[name] = self._clock()
            self._statuses[name] = status
            await self._close_server_session(name)
            LOGGER.warning(
                "MCP reconnect failed for server %s (%s)",
                _sanitize_segment(name), error,
            )
            return status

    async def _discover_server(self, server_name: str, config: MCPServerConfig) -> tuple[MCPDiscoveredTool, ...]:
        async def discover(session: Any) -> tuple[Any, ...]:
            remote_tools: list[Any] = []
            response = await session.list_tools()
            remote_tools.extend(tuple(_field(response, "tools", default=()) or ()))
            cursor = _field(response, "next_cursor", "nextCursor", default=None)
            while cursor:
                response = await session.list_tools(cursor=cursor)
                remote_tools.extend(tuple(_field(response, "tools", default=()) or ()))
                cursor = _field(response, "next_cursor", "nextCursor", default=None)
            return tuple(remote_tools)

        worker = self._session_workers.get(server_name)
        reused_session = worker is not None and not worker.done()
        timeout = max(0.001, float(MCP_DISCOVERY_TIMEOUT_SECONDS))
        started = asyncio.get_running_loop().time()
        try:
            remote_tools = await self._run_server_operation(
                server_name, config, discover,
                timeout=timeout * 0.5 if reused_session else timeout,
            )
        except asyncio.TimeoutError:
            if not reused_session:
                raise
            remaining = max(0.001, timeout - (asyncio.get_running_loop().time() - started))
            remote_tools = await self._run_server_operation(
                server_name, config, discover, timeout=remaining,
            )
        discovered: list[MCPDiscoveredTool] = []
        for tool in remote_tools:
            remote_name = str(_field(tool, "name", default="") or "").strip()
            input_schema = _field(tool, "input_schema", "inputSchema", default={})
            if not remote_name or not isinstance(input_schema, Mapping):
                continue
            annotations_value = _field(tool, "annotations", default={})
            annotations = _json_value(annotations_value) if annotations_value is not None else {}
            if not isinstance(annotations, Mapping):
                annotations = {}
            discovered.append(MCPDiscoveredTool(
                server_name=server_name,
                remote_name=remote_name,
                description=str(_field(tool, "description", default="") or "").strip(),
                input_schema=dict(input_schema),
                annotations=dict(annotations),
                read_only=_read_only_annotation(tool),
            ))
        return tuple(discovered)

    def _failure_cooldown_active(self, server_name: str, *, now: float) -> bool:
        failed_at = self._failure_at.get(server_name)
        return (
            failed_at is not None
            and now - failed_at < MCP_DISCOVERY_FAILURE_COOLDOWN_SECONDS
        )

    def _cache_is_stale(self, server_name: str, *, now: float) -> bool:
        updated_at = self._discovered_at.get(server_name)
        return (
            server_name not in self._discovery
            or updated_at is None
            or now - updated_at >= MCP_DISCOVERY_REFRESH_INTERVAL_SECONDS
        )

    def _set_unsupported_transport(self, server_name: str) -> None:
        if self._statuses.get(server_name) != MCPServerStatus(
            server_name=server_name, connected=False, tool_count=0,
            error="unsupported_transport",
        ):
            LOGGER.warning("MCP server %s ignored: unsupported transport", _sanitize_segment(server_name))
        self._discovery[server_name] = ()
        self._discovered_at[server_name] = self._clock()
        self._statuses[server_name] = MCPServerStatus(
            server_name=server_name, connected=False, tool_count=0,
            error="unsupported_transport",
        )

    async def _refresh_server(self, server_name: str, config: MCPServerConfig) -> None:
        try:
            tools = await asyncio.wait_for(
                self._discover_server(server_name, config),
                timeout=MCP_DISCOVERY_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            tools = ()
            error = type(exc).__name__
            now = self._clock()
            self._failure_at[server_name] = now
            self._statuses[server_name] = MCPServerStatus(
                server_name=server_name, connected=False, tool_count=0, error=error,
            )
            LOGGER.warning(
                "MCP discovery failed for server %s (%s)",
                _sanitize_segment(server_name), error,
            )
        else:
            now = self._clock()
            self._failure_at.pop(server_name, None)
            self._statuses[server_name] = MCPServerStatus(
                server_name=server_name, connected=True, tool_count=len(tools),
            )
        self._discovery[server_name] = tuple(tools)
        self._discovered_at[server_name] = now

    def _schedule_refresh(
        self, server_name: str, config: MCPServerConfig,
    ) -> asyncio.Task[None]:
        current = self._refresh_tasks.get(server_name)
        if current is not None and not current.done():
            return current
        task = asyncio.create_task(
            self._refresh_server(server_name, config),
            name=f"mcp-discovery-{_sanitize_segment(server_name)}",
        )
        self._refresh_tasks[server_name] = task

        def finish(completed: asyncio.Task[None]) -> None:
            if self._refresh_tasks.get(server_name) is completed:
                self._refresh_tasks.pop(server_name, None)
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finish)
        return task

    def _snapshot(self) -> dict[str, tuple[MCPDiscoveredTool, ...]]:
        enabled = {
            name for name, config in self.servers.items()
            if bool(config.enabled)
        }
        return {
            name: tuple(rows)
            for name, rows in sorted(self._discovery.items())
            if name in enabled
        }

    async def discover_all(
        self, *, refresh: bool = False, block_cold: bool = False,
    ) -> dict[str, tuple[MCPDiscoveredTool, ...]]:
        tasks: list[asyncio.Task[None]] = []
        cold_tasks: list[asyncio.Task[None]] = []
        now = self._clock()
        for server_name, config in sorted(self.servers.items()):
            if not bool(config.enabled):
                continue
            transport = str(config.transport or "sse").strip().lower()
            if transport not in SUPPORTED_MCP_TRANSPORTS:
                self._set_unsupported_transport(server_name)
                continue
            if self._failure_cooldown_active(server_name, now=now):
                continue
            if refresh or server_name in self._failure_at or self._cache_is_stale(server_name, now=now):
                is_cold = (
                    server_name not in self._discovery
                    or server_name in self._failure_at
                )
                if server_name not in self._statuses:
                    self._statuses[server_name] = MCPServerStatus(
                        server_name=server_name, connected=False, tool_count=0,
                        error="discovery_pending",
                    )
                task = self._schedule_refresh(server_name, config)
                tasks.append(task)
                if block_cold and is_cold:
                    cold_tasks.append(task)
        if refresh and tasks:
            await asyncio.gather(*(asyncio.shield(task) for task in tasks))
        elif cold_tasks:
            # Cold servers have no safe Tool snapshot yet. Wait for their one
            # already timeout-bounded discovery in parallel; warm/stale and
            # failure-cooldown paths remain snapshot-only and non-blocking.
            await asyncio.gather(*(asyncio.shield(task) for task in cold_tasks))
        return self._snapshot()

    def statuses(self) -> tuple[MCPServerStatus, ...]:
        return tuple(self._statuses[name] for name in sorted(self._statuses))

    def read_only_tool_count(self, server_name: str) -> int:
        """Return cached Tools projected as direct/read-only for one server."""

        config = self.servers.get(str(server_name))
        if config is not None and bool(config.trusted):
            return len(self._discovery.get(str(server_name), ()))
        return sum(
            1
            for tool in self._discovery.get(str(server_name), ())
            if tool.read_only
        )

    async def _call_remote(
        self, server_name: str, remote_name: str, arguments: Mapping[str, Any], *, intent: str,
    ) -> NativeToolResult:
        config = self.servers[server_name]
        if not bool(config.enabled):
            return NativeToolResult(
                _bounded_json({"status": "error", "error": "mcp_server_disabled"}), intent,
            )

        async def invoke(session: Any) -> Any:
            return await session.call_tool(remote_name, dict(arguments))

        try:
            result = await self._run_server_operation(
                server_name, config, invoke, timeout=float(config.call_timeout_seconds),
            )
        except Exception as exc:
            transport_error = _transport_failure_code(exc)
            if transport_error:
                failed_at = self._clock()
                self._failure_at[server_name] = failed_at
                self._discovery[server_name] = ()
                self._discovered_at[server_name] = failed_at
                self._statuses[server_name] = MCPServerStatus(
                    server_name=server_name, connected=False, tool_count=0,
                    error=transport_error,
                )
            LOGGER.warning(
                "MCP Tool call failed for server %s (%s)",
                _sanitize_segment(server_name), type(exc).__name__,
            )
            return NativeToolResult(
                _bounded_json({"status": "error", "error": "mcp_call_failed"}), intent,
            )
        content = _field(result, "content", default=()) or ()
        if bool(_field(result, "is_error", "isError", default=False)):
            return NativeToolResult(_bounded_json({
                "status": "error", "error": "mcp_tool_error", "content": content,
            }), intent)
        projected_content, images = _project_tool_content(content)
        return NativeToolResult(_bounded_json({
            "status": "ok",
            "content": projected_content,
            "structured_content": _field(result, "structured_content", "structuredContent"),
        }), intent, images=images)

    def native_tool_bindings(self) -> tuple[NativeToolBinding, ...]:
        bindings: list[NativeToolBinding] = []
        used_names: set[str] = set()
        for server_name, tools in sorted(self._discovery.items()):
            config = self.servers.get(server_name)
            if config is None or not bool(config.enabled):
                continue
            for tool in tools:
                base_name = _native_tool_name(server_name, tool.remote_name)
                native_name = base_name
                if native_name in used_names:
                    suffix = hashlib.sha256(
                        f"{server_name}\0{tool.remote_name}".encode("utf-8")
                    ).hexdigest()[:8]
                    native_name = f"{base_name[:54]}__{suffix}"
                if native_name in used_names:
                    LOGGER.warning("MCP Tool name collision ignored for server %s", _sanitize_segment(server_name))
                    continue
                try:
                    Draft202012Validator.check_schema(dict(tool.input_schema))
                except SchemaError:
                    LOGGER.warning("MCP Tool schema ignored for server %s", _sanitize_segment(server_name))
                    continue
                used_names.add(native_name)
                direct = bool(config.trusted) or bool(tool.read_only)

                async def handler(
                    _context: NativeToolContext, arguments: Mapping[str, Any],
                    *, _server: str = server_name, _tool: MCPDiscoveredTool = tool,
                    _intent: str = native_name,
                ) -> NativeToolResult:
                    try:
                        Draft202012Validator(dict(_tool.input_schema)).validate(dict(arguments))
                    except (ValidationError, SchemaError, TypeError, ValueError):
                        return NativeToolResult(_bounded_json({
                            "status": "error", "error": "mcp_arguments_invalid",
                        }), _intent)
                    return await self._call_remote(
                        _server, _tool.remote_name, arguments, intent=_intent,
                    )

                async def confirmation_preview(
                    _context: NativeToolContext, arguments: Mapping[str, Any],
                    *, _server: str = server_name, _tool: MCPDiscoveredTool = tool,
                ) -> str:
                    return _confirmation_preview(_server, _tool.remote_name, arguments)

                bindings.append(NativeToolBinding(contract=NativeToolContract(
                    owner_module_id="mcp",
                    name=native_name,
                    description=tool.description or f"MCP Tool {tool.remote_name}.",
                    input_schema=dict(tool.input_schema),
                    effect="read_only" if direct else "mutating",
                    confirmation_required=not direct,
                    source_authority=f"mcp:{_sanitize_segment(server_name)}:tools/call",
                    user_scoped=False,
                    rollout_flag="native_agent_mcp_enabled",
                    order=9000 + len(bindings),
                    relay_result_content=not direct,
                ), handler=handler, confirmation_preview=None if direct else confirmation_preview))
        return tuple(bindings)
