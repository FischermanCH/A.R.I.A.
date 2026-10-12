from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules import module_route_path, module_template_name
from aria.modules.connections_ui_readonly.ia_routes import (
    CONNECTION_REF_QUERY_KEYS,
    CONNECTION_URL_SEGMENTS,
    legacy_connection_redirect,
)
from aria.modules.sftp_admin_ui.context import register_sftp_connections_detail_route
from aria.modules.ssh_admin_ui.context import register_ssh_connections_detail_route

BaseConnectionsPageContextBuilder = Callable[..., dict[str, Any]]
ConnectionPageRenderer = Callable[..., HTMLResponse]
RssConnectionsContextBuilder = Callable[..., dict[str, Any]]
RssStatusGroupsBuilder = Callable[..., Awaitable[Any]]
RssStatusGroupsCacheLoader = Callable[[Path, list[dict[str, Any]]], Any]
RssStatusGroupsCacheSaver = Callable[[Path, list[dict[str, Any]], Any], None]
ConnectionTemplateNameResolver = Callable[[str], str]
LocalizedMessage = Callable[[str, str, str], str]


def _rss_ui_template_name(template_name: str) -> str:
    resolved = module_template_name("rss_ui", template_name)
    if resolved is None:
        raise RuntimeError(f"rss_ui template is not registered: {template_name}")
    return resolved


def _smtp_ui_route(route_path: str) -> str:
    resolved = module_route_path("smtp_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"smtp_ui route is not registered: {route_path}")
    return resolved


@dataclass(frozen=True)
class ConnectionDetailRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    render_connection_page: ConnectionPageRenderer
    base_connections_page_context: BaseConnectionsPageContextBuilder
    build_ssh_connections_context: Callable[..., dict[str, Any]]
    build_discord_connections_context: Callable[..., dict[str, Any]]
    build_sftp_connections_context: Callable[..., dict[str, Any]]
    build_smb_connections_context: Callable[..., dict[str, Any]]
    build_webhook_connections_context: Callable[..., dict[str, Any]]
    build_email_connections_context: Callable[..., dict[str, Any]]
    build_imap_connections_context: Callable[..., dict[str, Any]]
    build_http_api_connections_context: Callable[..., dict[str, Any]]
    build_google_calendar_connections_context: Callable[..., dict[str, Any]]
    build_rss_connections_context: RssConnectionsContextBuilder
    build_website_connections_context: Callable[..., dict[str, Any]]
    build_mqtt_connections_context: Callable[..., dict[str, Any]]
    build_rss_status_groups: RssStatusGroupsBuilder
    load_cached_rss_status_groups: RssStatusGroupsCacheLoader
    save_cached_rss_status_groups: RssStatusGroupsCacheSaver
    connection_template_name: ConnectionTemplateNameResolver
    pipeline: Any
    msg: LocalizedMessage


def register_connection_detail_routes(app: FastAPI, deps: ConnectionDetailRouteDeps) -> None:
    @app.get("/config/connections/email")
    async def config_connections_email_legacy() -> RedirectResponse:
        return RedirectResponse(url=_smtp_ui_route("/config/connections/smtp"), status_code=303)

    builders: dict[str, Callable[..., dict[str, Any]]] = {
        "discord": deps.build_discord_connections_context,
        "email": deps.build_email_connections_context,
        "google_calendar": deps.build_google_calendar_connections_context,
        "http_api": deps.build_http_api_connections_context,
        "imap": deps.build_imap_connections_context,
        "mqtt": deps.build_mqtt_connections_context,
        "sftp": deps.build_sftp_connections_context,
        "smb": deps.build_smb_connections_context,
        "ssh": deps.build_ssh_connections_context,
        "website": deps.build_website_connections_context,
        "webhook": deps.build_webhook_connections_context,
    }
    test_status_keys = {
        "discord": "discord_test_status",
        "email": "email_test_status",
        "google_calendar": "google_calendar_test_status",
        "http_api": "http_api_test_status",
        "imap": "imap_test_status",
        "mqtt": "mqtt_test_status",
        "sftp": "sftp_test_status",
        "smb": "smb_test_status",
        "ssh": "test_status",
        "website": "website_test_status",
        "webhook": "webhook_test_status",
    }

    def _query_int(request: Request, key: str) -> int:
        try:
            return int(request.query_params.get(key, "0") or 0)
        except (TypeError, ValueError):
            return 0

    async def _render_rss(
        request: Request,
        *,
        page_type: str,
        connection_ref: str = "",
    ) -> HTMLResponse:
        saved = _query_int(request, "saved")
        info = str(request.query_params.get("info", "") or "")
        error = str(request.query_params.get("error", "") or "")
        status = str(request.query_params.get("rss_test_status", "") or "")
        context = deps.base_connections_page_context(
            request,
            saved,
            info,
            error,
            kind="rss",
            page_type=page_type,
            connection_ref=connection_ref,
        )
        context.update(
            deps.build_rss_connections_context(
                connection_ref,
                status,
                page_type == "create",
                str(getattr(request.state, "lang", "de") or "de"),
            )
        )
        if isinstance(context.get("connection_intro"), dict):
            context["connection_intro"] = dict(context["connection_intro"])
            context["connection_intro"]["back_url"] = (
                context.get("connection_overview_url")
                if page_type in {"create", "detail"}
                else context.get("return_to") or module_route_path("connections_ui_readonly", "/connections")
            )
        rss_rows = context.get("rss_status_rows", [])
        cache_path = deps.base_dir / "data" / "runtime" / "rss_groups.json"
        use_refresh = bool(_query_int(request, "refresh_groups"))
        rss_groups = None if use_refresh else deps.load_cached_rss_status_groups(cache_path, rss_rows)
        if rss_groups is None:
            rss_groups = await deps.build_rss_status_groups(
                rss_rows,
                getattr(deps.pipeline, "llm_client", None) if use_refresh else None,
            )
            deps.save_cached_rss_status_groups(cache_path, rss_rows, rss_groups)
        context["rss_status_groups"] = rss_groups
        context["rss_groups_refreshed"] = use_refresh
        if use_refresh and not info and not error:
            lang = str(getattr(request.state, "lang", "de") or "de")
            context["info_message"] = deps.msg(lang, "RSS-Kategorien aktualisiert", "RSS categories refreshed")
        return deps.templates.TemplateResponse(
            request=request,
            name=_rss_ui_template_name(deps.connection_template_name("rss")),
            context=context,
        )

    async def _render(
        request: Request,
        *,
        kind: str,
        page_type: str,
        connection_ref: str = "",
    ) -> HTMLResponse:
        if kind == "rss":
            return await _render_rss(request, page_type=page_type, connection_ref=connection_ref)
        kwargs: dict[str, Any] = {}
        if kind == "sftp":
            kwargs["copy_from_ssh_ref"] = str(request.query_params.get("copy_from_ssh_ref", "") or "")
        if kind == "website":
            kwargs["create_new"] = page_type == "create"
        return deps.render_connection_page(
            request,
            kind=kind,
            saved=_query_int(request, "saved"),
            info=str(request.query_params.get("info", "") or ""),
            error=str(request.query_params.get("error", "") or ""),
            context_builder=builders[kind],
            page_type=page_type,
            connection_ref=connection_ref,
            selected_ref_raw=connection_ref,
            test_status=str(request.query_params.get(test_status_keys[kind], "") or ""),
            **kwargs,
        )

    def _register_kind(kind: str, segment: str) -> None:
        base = f"/config/connections/{segment}"

        async def overview(request: Request) -> Response:
            ref_key = CONNECTION_REF_QUERY_KEYS[kind]
            selected_ref = str(request.query_params.get(ref_key, "") or request.query_params.get("ref", "") or "")
            redirect = legacy_connection_redirect(
                request,
                kind=kind,
                selected_ref=selected_ref,
                create_requested=bool(_query_int(request, "create_new")),
            )
            return redirect or await _render(request, kind=kind, page_type="overview")

        async def create(request: Request) -> HTMLResponse:
            return await _render(request, kind=kind, page_type="create")

        async def detail(request: Request, connection_ref: str) -> HTMLResponse:
            return await _render(request, kind=kind, page_type="detail", connection_ref=connection_ref)

        app.add_api_route(base, overview, methods=["GET"], response_class=HTMLResponse, name=f"config_connections_{kind}_overview")
        app.add_api_route(f"{base}/new", create, methods=["GET"], response_class=HTMLResponse, name=f"config_connections_{kind}_create")
        app.add_api_route(f"{base}/{{connection_ref}}", detail, methods=["GET"], response_class=HTMLResponse, name=f"config_connections_{kind}_detail")

    for connection_kind, url_segment in CONNECTION_URL_SEGMENTS.items():
        _register_kind(connection_kind, url_segment)
