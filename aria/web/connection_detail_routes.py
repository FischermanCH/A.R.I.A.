from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BaseConnectionsPageContextBuilder = Callable[..., dict[str, Any]]
ConnectionPageRenderer = Callable[..., HTMLResponse]
RssConnectionsContextBuilder = Callable[..., dict[str, Any]]
RssStatusGroupsBuilder = Callable[..., Awaitable[Any]]
RssStatusGroupsCacheLoader = Callable[[Path, list[dict[str, Any]]], Any]
RssStatusGroupsCacheSaver = Callable[[Path, list[dict[str, Any]], Any], None]
ConnectionTemplateNameResolver = Callable[[str], str]
LocalizedMessage = Callable[[str, str, str], str]


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
    build_searxng_connections_context: Callable[..., dict[str, Any]]
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
    @app.get("/config/connections/ssh", response_class=HTMLResponse)
    async def config_connections_ssh_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        ref: str = "",
        test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="ssh",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_ssh_connections_context,
            selected_ref_raw=ref,
            test_status=test_status,
            mode=mode,
        )

    @app.get("/config/connections/discord", response_class=HTMLResponse)
    async def config_connections_discord_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        discord_ref: str = "",
        discord_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="discord",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_discord_connections_context,
            selected_ref_raw=discord_ref,
            test_status=discord_test_status,
            mode=mode,
        )

    @app.get("/config/connections/sftp", response_class=HTMLResponse)
    async def config_connections_sftp_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        sftp_ref: str = "",
        sftp_test_status: str = "",
        copy_from_ssh_ref: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="sftp",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_sftp_connections_context,
            selected_ref_raw=sftp_ref,
            test_status=sftp_test_status,
            copy_from_ssh_ref=copy_from_ssh_ref,
            mode=mode,
        )

    @app.get("/config/connections/smb", response_class=HTMLResponse)
    async def config_connections_smb_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        smb_ref: str = "",
        smb_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="smb",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_smb_connections_context,
            selected_ref_raw=smb_ref,
            test_status=smb_test_status,
            mode=mode,
        )

    @app.get("/config/connections/webhook", response_class=HTMLResponse)
    async def config_connections_webhook_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        webhook_ref: str = "",
        webhook_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="webhook",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_webhook_connections_context,
            selected_ref_raw=webhook_ref,
            test_status=webhook_test_status,
            mode=mode,
        )

    @app.get("/config/connections/email")
    async def config_connections_email_legacy() -> RedirectResponse:
        return RedirectResponse(url="/config/connections/smtp", status_code=303)

    @app.get("/config/connections/smtp", response_class=HTMLResponse)
    async def config_connections_smtp_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        email_ref: str = "",
        email_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="email",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_email_connections_context,
            selected_ref_raw=email_ref,
            test_status=email_test_status,
            mode=mode,
        )

    @app.get("/config/connections/imap", response_class=HTMLResponse)
    async def config_connections_imap_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        imap_ref: str = "",
        imap_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="imap",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_imap_connections_context,
            selected_ref_raw=imap_ref,
            test_status=imap_test_status,
            mode=mode,
        )

    @app.get("/config/connections/http-api", response_class=HTMLResponse)
    async def config_connections_http_api_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        http_api_ref: str = "",
        http_api_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="http_api",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_http_api_connections_context,
            selected_ref_raw=http_api_ref,
            test_status=http_api_test_status,
            mode=mode,
        )

    @app.get("/config/connections/google-calendar", response_class=HTMLResponse)
    async def config_connections_google_calendar_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        google_calendar_ref: str = "",
        google_calendar_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="google_calendar",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_google_calendar_connections_context,
            selected_ref_raw=google_calendar_ref,
            test_status=google_calendar_test_status,
            mode=mode,
        )

    @app.get("/config/connections/searxng", response_class=HTMLResponse)
    async def config_connections_searxng_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        searxng_ref: str = "",
        searxng_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="searxng",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_searxng_connections_context,
            selected_ref_raw=searxng_ref,
            test_status=searxng_test_status,
            mode=mode,
        )

    @app.get("/config/connections/rss", response_class=HTMLResponse)
    async def config_connections_rss_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        rss_ref: str = "",
        rss_test_status: str = "",
        create_new: int = 0,
        refresh_groups: int = 0,
        mode: str = "edit",
    ) -> HTMLResponse:
        effective_mode = "create" if create_new else mode
        context = deps.base_connections_page_context(request, saved, info, error, mode=effective_mode)
        context.update(deps.build_rss_connections_context(rss_ref, rss_test_status, bool(create_new)))
        rss_rows = context.get("rss_status_rows", [])
        cache_path = deps.base_dir / "data" / "runtime" / "rss_groups.json"
        use_refresh = bool(refresh_groups)
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
            name=deps.connection_template_name("rss"),
            context=context,
        )

    @app.get("/config/connections/websites", response_class=HTMLResponse)
    async def config_connections_websites_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        website_ref: str = "",
        website_test_status: str = "",
        create_new: int = 0,
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="website",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_website_connections_context,
            selected_ref_raw=website_ref,
            test_status=website_test_status,
            create_new=bool(create_new),
            mode=mode,
        )

    @app.get("/config/connections/mqtt", response_class=HTMLResponse)
    async def config_connections_mqtt_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        mqtt_ref: str = "",
        mqtt_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return deps.render_connection_page(
            request,
            kind="mqtt",
            saved=saved,
            info=info,
            error=error,
            context_builder=deps.build_mqtt_connections_context,
            selected_ref_raw=mqtt_ref,
            test_status=mqtt_test_status,
            mode=mode,
        )
