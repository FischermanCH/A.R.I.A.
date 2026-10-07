from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules import module_route_path, module_template_name


ConnectionsPageContextBuilder = Callable[..., dict[str, Any]]
ConnectionsSurfacePathResolver = Callable[..., str]
SampleConnectionImporter = Callable[[str], tuple[str, int, int]]
LocalizedMessage = Callable[[str, str, str], str]
_CONNECTIONS_SURFACE_ROUTES_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _connections_route_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CONNECTIONS_SURFACE_ROUTES_I18N.t(lang or "de", f"connections_surface_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class ConnectionsSurfaceRouteDeps:
    templates: Jinja2Templates
    build_connections_page_context: ConnectionsPageContextBuilder
    connections_surface_path: ConnectionsSurfacePathResolver
    import_sample_connection_manifest: SampleConnectionImporter
    msg: LocalizedMessage


def register_connections_surface_routes(app: FastAPI, deps: ConnectionsSurfaceRouteDeps) -> None:
    def _connections_route_path(route_path: str) -> str:
        resolved = module_route_path("connections_ui_readonly", route_path)
        if resolved is None:
            raise RuntimeError(f"connections_ui_readonly route is not registered: {route_path}")
        return resolved

    def _config_ui_path(route_path: str) -> str:
        resolved = module_route_path("config_ui", route_path)
        if resolved is None:
            raise RuntimeError(f"config_ui route is not registered: {route_path}")
        return resolved

    def _connections_ui_readonly_template(template_name: str) -> str:
        resolved = module_template_name("connections_ui_readonly", template_name)
        if resolved is None:
            raise RuntimeError(f"connections_ui_readonly template is not registered: {template_name}")
        return resolved

    def _render_connections_surface(
        request: Request,
        *,
        template_name: str,
        error: str = "",
        info: str = "",
        logical_back_fallback: str | None = None,
        page_return_to: str | None = None,
        connections_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> HTMLResponse:
        resolved_default_path = _connections_route_path("/connections")
        context = deps.build_connections_page_context(
            request,
            error=error,
            info=info,
            logical_back_fallback=logical_back_fallback or resolved_default_path,
            page_return_to=page_return_to or resolved_default_path,
            connections_nav=connections_nav,
            page_heading=page_heading,
            show_overview_checks=show_overview_checks,
        )
        return deps.templates.TemplateResponse(
            request=request,
            name=_connections_ui_readonly_template(template_name),
            context=context,
        )

    @app.get("/connections", response_class=HTMLResponse)
    async def connections_overview_page(
        request: Request,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_connections_surface(
            request,
            template_name="connections_hub.html",
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_connections_route_path("/connections"),
            connections_nav="overview",
            page_heading=_connections_route_text(lang, "heading_connections", "Connections"),
        )

    @app.get("/connections/status", response_class=HTMLResponse)
    async def connections_status_page(
        request: Request,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_connections_surface(
            request,
            template_name="connections_status.html",
            error=error,
            info=info,
            logical_back_fallback=_connections_route_path("/connections"),
            page_return_to=_connections_route_path("/connections/status"),
            connections_nav="status",
            page_heading=_connections_route_text(lang, "heading_live_status", "Live status"),
        )

    @app.get("/connections/types", response_class=HTMLResponse)
    async def connections_types_page(
        request: Request,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_connections_surface(
            request,
            template_name="connections_types.html",
            error=error,
            info=info,
            logical_back_fallback=_connections_route_path("/connections"),
            page_return_to=_connections_route_path("/connections/types"),
            connections_nav="types",
            page_heading=_connections_route_text(lang, "heading_connection_types", "Connection types"),
        )

    @app.get("/connections/templates", response_class=HTMLResponse)
    async def connections_templates_page(
        request: Request,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_connections_surface(
            request,
            template_name="connections_templates.html",
            error=error,
            info=info,
            logical_back_fallback=_connections_route_path("/connections"),
            page_return_to=_connections_route_path("/connections/templates"),
            connections_nav="templates",
            page_heading=_connections_route_text(lang, "heading_templates", "Templates"),
        )

    @app.post("/config/connections/import-sample")
    async def config_connections_import_sample(
        request: Request,
        sample_file: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = deps.connections_surface_path(return_to, fallback=_connections_route_path("/connections/templates"))
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url=f"{surface_path}?error=admin_mode_required", status_code=303)
        try:
            kind, imported_count, skipped_count = deps.import_sample_connection_manifest(sample_file)
            info = quote_plus(f"sample_imported:{kind}:{imported_count}:{skipped_count}")
            return RedirectResponse(url=f"{surface_path}?info={info}", status_code=303)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return RedirectResponse(url=f"{surface_path}?error={quote_plus(str(exc))}", status_code=303)
