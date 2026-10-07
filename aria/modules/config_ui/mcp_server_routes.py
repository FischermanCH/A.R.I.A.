"""Admin-only MCP server configuration surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hmac
from itertools import zip_longest
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote_plus, urlsplit

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules import module_route_path, module_template_name
from aria.modules.platform_primitives.i18n import I18NStore


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
StringSanitizer = Callable[[str | None], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]

_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")
_SUPPORTED_TRANSPORTS = frozenset({"sse", "http"})
_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,120}$")


@dataclass(frozen=True)
class MCPServerAdminRouteDeps:
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_username_from_request: UsernameResolver
    sanitize_server_name: StringSanitizer
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader


def _route_path(route_path: str) -> str:
    resolved = module_route_path("config_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"config_ui route is not registered: {route_path}")
    return resolved


def _connections_route_path(route_path: str) -> str:
    resolved = module_route_path("connections_ui_readonly", route_path)
    if resolved is None:
        raise RuntimeError(f"connections_ui_readonly route is not registered: {route_path}")
    return resolved


def _template_name() -> str:
    resolved = module_template_name("config_ui", "config_connections_mcp.html")
    if resolved is None:
        raise RuntimeError("config_ui template is not registered: config_connections_mcp.html")
    return resolved


def _is_admin(request: Request) -> bool:
    return bool(getattr(request.state, "can_access_advanced_config", False)) and str(
        getattr(request.state, "auth_role", "") or ""
    ).strip().lower() == "admin"


def _redirect(
    *, error: str = "", info: str = "", saved: bool = False,
    server: str = "", tool_count: int | None = None,
) -> RedirectResponse:
    parts: list[str] = []
    if saved:
        parts.append("saved=1")
    if error:
        parts.append(f"error={quote_plus(error)}")
    if info:
        parts.append(f"info={quote_plus(info)}")
    if server:
        parts.append(f"server={quote_plus(server)}")
    if tool_count is not None:
        parts.append(f"tool_count={max(0, int(tool_count))}")
    suffix = f"?{'&'.join(parts)}" if parts else ""
    return RedirectResponse(url=f"{_route_path('/config/connections/mcp')}{suffix}", status_code=303)


def _config_home_redirect() -> RedirectResponse:
    return RedirectResponse(
        url=f"{_route_path('/config')}?error=admin_mode_required",
        status_code=303,
    )


def _server_rows(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    source = raw.get("mcp_servers", {})
    if not isinstance(source, Mapping):
        return {}
    return {
        str(name): dict(value)
        for name, value in source.items()
        if str(name).strip() and isinstance(value, Mapping)
    }


def _mutable_server_rows(raw: dict[str, Any]) -> dict[str, Any]:
    rows = raw.get("mcp_servers")
    if not isinstance(rows, dict):
        rows = {}
        raw["mcp_servers"] = rows
    return rows


def _agentic_loop(raw: dict[str, Any]) -> dict[str, Any]:
    value = raw.get("agentic_loop")
    if not isinstance(value, dict):
        value = {}
        raw["agentic_loop"] = value
    return value


def _bool_value(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _masked_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
        host = str(parsed.hostname or "").strip()
        if not parsed.scheme or not host:
            return "***"
        port = f":{parsed.port}" if parsed.port is not None else ""
        path_marker = "/..." if parsed.path and parsed.path != "/" else ""
        return f"{parsed.scheme}://{host}{port}{path_marker}"
    except (TypeError, ValueError):
        return "***"


def _bounded_status_error(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", text):
        return "mcp_status_error"
    return text


def _message(lang: str, prefix: str, code: str) -> str:
    clean = str(code or "").strip()
    if not clean:
        return ""
    fallback = clean.replace("_", " ")
    return _I18N.t(lang, f"mcp_admin.{prefix}_{clean}", fallback)


def _headers_from_form(
    request_form: Any,
    *,
    existing: Mapping[str, Any],
) -> dict[str, str]:
    if _bool_value(request_form.get("clear_headers")):
        return {}
    names = list(request_form.getlist("header_name"))
    values = list(request_form.getlist("header_value"))
    submitted: dict[str, str] = {}
    any_submitted = False
    for raw_name, raw_value in zip_longest(names, values, fillvalue=""):
        name = str(raw_name or "").strip()
        value = str(raw_value or "").strip()
        if not name and not value:
            continue
        any_submitted = True
        if not name or not value or not _HEADER_NAME.fullmatch(name):
            raise ValueError("invalid_headers")
        submitted[name] = value[:4096]
    if any_submitted:
        return submitted
    return {
        str(name): str(value)
        for name, value in existing.items()
        if str(name).strip() and isinstance(value, str)
    }


async def _status_rows(
    raw: Mapping[str, Any],
    *,
    master_enabled: bool,
    pipeline: Any,
) -> list[dict[str, Any]]:
    servers = _server_rows(raw)
    enabled_names = {name for name, row in servers.items() if bool(row.get("enabled", False))}
    manager = getattr(pipeline, "_native_mcp_client", None)
    refresh_error = ""
    if master_enabled and enabled_names and manager is not None:
        discover = getattr(manager, "discover_all", None)
        if callable(discover):
            try:
                await discover(refresh=True)
            except Exception as exc:  # pragma: no cover - defensive around injected runtimes
                refresh_error = type(exc).__name__
    statuses_method = getattr(manager, "statuses", None)
    try:
        statuses = tuple(statuses_method()) if callable(statuses_method) else ()
    except Exception as exc:  # pragma: no cover - defensive around injected runtimes
        statuses = ()
        refresh_error = refresh_error or type(exc).__name__
    status_by_name = {str(getattr(row, "server_name", "")): row for row in statuses}
    read_only_counter = getattr(manager, "read_only_tool_count", None)

    rows: list[dict[str, Any]] = []
    for name, config in sorted(servers.items()):
        enabled = bool(config.get("enabled", False))
        connected = False
        tool_count = 0
        status_error = ""
        if not master_enabled:
            status_error = "feature_disabled"
        elif not enabled:
            status_error = "server_disabled"
        elif manager is None:
            status_error = "manager_unavailable"
        elif refresh_error:
            status_error = refresh_error
        else:
            status = status_by_name.get(name)
            if status is None:
                status_error = "status_unavailable"
            else:
                connected = bool(getattr(status, "connected", False))
                status_error = _bounded_status_error(getattr(status, "error", ""))
                if connected:
                    if callable(read_only_counter):
                        try:
                            tool_count = max(0, int(read_only_counter(name)))
                        except Exception:  # pragma: no cover - defensive around injected runtimes
                            tool_count = 0
                    else:
                        tool_count = max(0, int(getattr(status, "tool_count", 0) or 0))
        headers = config.get("headers", {})
        header_names = sorted(str(key) for key in headers) if isinstance(headers, Mapping) else []
        rows.append({
            "name": name,
            "title": str(config.get("title", "") or "").strip(),
            "transport": str(config.get("transport", "sse") or "sse").strip().lower(),
            "enabled": enabled,
            "trusted": bool(config.get("trusted", False)),
            "url_masked": _masked_url(config.get("url", "")),
            "header_names": header_names,
            "connected": connected,
            "tool_count": tool_count,
            "status_error": status_error,
        })
    return rows


def register_mcp_server_admin_routes(app: FastAPI, deps: MCPServerAdminRouteDeps) -> None:
    @app.get("/config/connections/mcp", response_class=HTMLResponse)
    async def config_connections_mcp_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        server: str = "",
        tool_count: int = 0,
    ) -> Response:
        if not _is_admin(request):
            return _config_home_redirect()
        raw = deps.read_raw_config()
        servers = _server_rows(raw)
        agentic = raw.get("agentic_loop", {})
        master_enabled = bool(
            isinstance(agentic, Mapping) and agentic.get("native_agent_mcp_enabled", False)
        )
        selected_name = deps.sanitize_server_name(server)
        selected = servers.get(selected_name, {})
        rows = await _status_rows(
            raw,
            master_enabled=master_enabled,
            pipeline=deps.get_pipeline(),
        )
        settings = deps.get_settings()
        lang = str(getattr(request.state, "lang", "de") or "de")
        for row in rows:
            status_error = str(row.get("status_error", "") or "")
            row["status_error_text"] = (
                _I18N.t(lang, f"mcp_admin.status_{status_error}", status_error)
                if status_error
                else ""
            )
        selected_headers = selected.get("headers", {}) if isinstance(selected, Mapping) else {}
        return deps.templates.TemplateResponse(
            request=request,
            name=_template_name(),
            context={
                "title": str(getattr(getattr(settings, "ui", None), "title", "ARIA") or "ARIA"),
                "username": deps.get_username_from_request(request) or "web",
                "connections_nav": "mcp",
                "connections_page_heading": _I18N.t(lang, "mcp_admin.title", "MCP servers"),
                "saved": int(saved or 0),
                "error_message": _message(lang, "error", error),
                "info_message": _message(lang, "info", info).format(
                    tool_count=max(0, int(tool_count or 0)),
                ),
                "mcp_master_enabled": master_enabled,
                "mcp_server_rows": rows,
                "selected_mcp_name": selected_name if selected else "",
                "selected_mcp": {
                    "name": selected_name if selected else "",
                    "title": str(selected.get("title", "") or "") if selected else "",
                    "transport": str(selected.get("transport", "sse") or "sse") if selected else "sse",
                    "enabled": bool(selected.get("enabled", False)) if selected else False,
                    "trusted": bool(selected.get("trusted", False)) if selected else False,
                    "call_timeout_seconds": float(selected.get("call_timeout_seconds", 30) or 30)
                    if selected else 30,
                    "url_masked": _masked_url(selected.get("url", "")) if selected else "",
                    "header_names": sorted(str(key) for key in selected_headers)
                    if isinstance(selected_headers, Mapping)
                    else [],
                },
                "page_return_to": _connections_route_path("/connections/types"),
            },
        )

    @app.post("/config/connections/mcp/save")
    async def config_connections_mcp_save(
        request: Request,
        server_name: str = Form(""),
        original_name: str = Form(""),
        url: str = Form(""),
        transport: str = Form("sse"),
        enabled: str = Form("0"),
        trusted: str = Form("0"),
        title: str = Form(""),
        call_timeout_seconds: str = Form("30"),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        if not _is_admin(request):
            return _config_home_redirect()
        clean_name = deps.sanitize_server_name(server_name)
        clean_original = deps.sanitize_server_name(original_name)
        clean_transport = str(transport or "sse").strip().lower()
        if not clean_name:
            return _redirect(error="invalid_name")
        if clean_transport not in _SUPPORTED_TRANSPORTS:
            return _redirect(error="invalid_transport", server=clean_original)

        raw = deps.read_raw_config()
        rows = _mutable_server_rows(raw)
        existing_name = clean_original if clean_original in rows else clean_name
        existing = rows.get(existing_name, {})
        existing = dict(existing) if isinstance(existing, Mapping) else {}
        clean_url = str(url or "").strip() or str(existing.get("url", "") or "").strip()
        if not clean_url:
            return _redirect(error="invalid_url", server=clean_original)
        if clean_name != existing_name and clean_name in rows:
            return _redirect(error="duplicate_name", server=clean_original)
        try:
            clean_call_timeout = float(call_timeout_seconds)
        except (TypeError, ValueError):
            return _redirect(error="invalid_call_timeout", server=clean_original)
        if clean_call_timeout < 5 or clean_call_timeout > 900:
            return _redirect(error="invalid_call_timeout", server=clean_original)
        form = await request.form()
        existing_headers = existing.get("headers", {})
        try:
            headers = _headers_from_form(
                form,
                existing=existing_headers if isinstance(existing_headers, Mapping) else {},
            )
        except ValueError:
            return _redirect(error="invalid_headers", server=clean_original)

        row = {
            "transport": clean_transport,
            "url": clean_url[:2048],
            "headers": headers,
            "enabled": _bool_value(enabled),
            "trusted": _bool_value(trusted),
            "title": str(title or "").strip()[:160],
            "call_timeout_seconds": clean_call_timeout,
        }
        if existing_name != clean_name:
            rows.pop(existing_name, None)
        rows[clean_name] = row
        _agentic_loop(raw)["native_agent_mcp_enabled"] = any(
            isinstance(value, Mapping) and bool(value.get("enabled", False))
            for value in rows.values()
        )
        try:
            deps.write_raw_config(raw)
            deps.reload_runtime()
        except (OSError, RuntimeError, ValueError):
            return _redirect(error="save_failed", server=clean_name)
        return _redirect(saved=True, info="saved", server=clean_name)

    @app.post("/config/connections/mcp/master")
    async def config_connections_mcp_master(
        request: Request,
        master_enabled: str = Form("0"),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        if not _is_admin(request):
            return _config_home_redirect()
        enabled_value = _bool_value(master_enabled)
        raw = deps.read_raw_config()
        _agentic_loop(raw)["native_agent_mcp_enabled"] = enabled_value
        try:
            deps.write_raw_config(raw)
            deps.reload_runtime()
        except (OSError, RuntimeError, ValueError):
            return _redirect(error="save_failed")
        return _redirect(info="master_on" if enabled_value else "master_off")

    @app.post("/config/connections/mcp/reconnect")
    async def config_connections_mcp_reconnect(
        request: Request,
        server_name: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin(request):
            return _config_home_redirect()
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        if not expected_csrf or not hmac.compare_digest(str(csrf_token or ""), expected_csrf):
            return _redirect(error="csrf_failed")
        clean_name = deps.sanitize_server_name(server_name)
        if not clean_name:
            return _redirect(error="unknown_server")
        manager = getattr(deps.get_pipeline(), "_native_mcp_client", None)
        reconnect = getattr(manager, "reconnect", None)
        if not callable(reconnect):
            return _redirect(error="manager_unavailable", server=clean_name)
        try:
            status = await reconnect(clean_name)
        except Exception:  # pragma: no cover - defensive around injected runtimes
            return _redirect(error="reconnect_failed", server=clean_name)
        if bool(getattr(status, "connected", False)):
            return _redirect(
                info="reconnected",
                server=clean_name,
                tool_count=max(0, int(getattr(status, "tool_count", 0) or 0)),
            )
        error = str(getattr(status, "error", "") or "")
        if error == "not_found":
            return _redirect(error="unknown_server", server=clean_name)
        if error == "disabled":
            return _redirect(error="server_disabled", server=clean_name)
        return _redirect(error="reconnect_failed", server=clean_name)

    @app.post("/config/connections/mcp/delete")
    async def config_connections_mcp_delete(
        request: Request,
        server_name: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        if not _is_admin(request):
            return _config_home_redirect()
        clean_name = deps.sanitize_server_name(server_name)
        raw = deps.read_raw_config()
        rows = _mutable_server_rows(raw)
        if not clean_name or clean_name not in rows:
            return _redirect(error="unknown_server")
        rows.pop(clean_name, None)
        if not any(
            isinstance(value, Mapping) and bool(value.get("enabled", False))
            for value in rows.values()
        ):
            _agentic_loop(raw)["native_agent_mcp_enabled"] = False
        try:
            deps.write_raw_config(raw)
            deps.reload_runtime()
        except (OSError, RuntimeError, ValueError):
            return _redirect(error="save_failed")
        return _redirect(info="deleted")
