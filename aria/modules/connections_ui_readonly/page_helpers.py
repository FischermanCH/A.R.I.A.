from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aria.modules import module_route_path, module_template_name
from aria.modules.connections_ui_readonly.ia_routes import connection_canonical_url

GenericConnectionContextBuilder = Callable[..., dict[str, Any]]
UsernameResolver = Callable[[Request], str]
LogicalBackSetter = Callable[..., str]
Sanitizer = Callable[[str | None], str]
ConnectionRefOptionsBuilder = Callable[[dict[str, dict[str, Any]]], list[dict[str, str]]]
ConnectionStatusRowsBuilder = Callable[..., list[dict[str, Any]]]
ConnectionEditUrlAttacher = Callable[[str, list[dict[str, Any]]], list[dict[str, Any]]]
ConnectionTemplateNameResolver = Callable[[str], str]
SettingsGetter = Callable[[], Any]


@dataclass(frozen=True)
class ConnectionPageHelperDeps:
    base_dir: Path
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    set_logical_back_url: LogicalBackSetter
    sanitize_connection_name: Sanitizer
    build_connection_ref_options: ConnectionRefOptionsBuilder
    build_connection_status_rows: ConnectionStatusRowsBuilder
    attach_connection_edit_urls: ConnectionEditUrlAttacher
    connection_template_name: ConnectionTemplateNameResolver


@dataclass(frozen=True)
class ConnectionPageHelpers:
    build_generic_connections_context: GenericConnectionContextBuilder
    base_connections_page_context: Callable[..., dict[str, Any]]
    render_connection_page: Callable[..., HTMLResponse]


def build_connection_page_helpers(deps: ConnectionPageHelperDeps) -> ConnectionPageHelpers:
    BASE_DIR = deps.base_dir
    TEMPLATES = deps.templates
    _get_settings = deps.get_settings
    _get_username_from_request = deps.get_username_from_request
    _set_logical_back_url = deps.set_logical_back_url
    _sanitize_connection_name = deps.sanitize_connection_name
    _build_connection_ref_options = deps.build_connection_ref_options
    build_connection_status_rows = deps.build_connection_status_rows
    _attach_connection_edit_urls = deps.attach_connection_edit_urls
    connection_template_name = deps.connection_template_name

    def _normalize_connection_page_type(page_type: str | None) -> str:
        clean = str(page_type or "overview").strip().lower()
        if clean in {"create", "new", "add"}:
            return "create"
        if clean in {"detail", "edit"}:
            return "detail"
        return "overview"

    def _connection_ui_template_name(kind: str, template_name: str) -> str:
        module_id_by_kind = {
            "discord": "discord_ui",
            "email": "smtp_ui",
            "google_calendar": "google_calendar_ui",
            "http_api": "http_api_admin_ui",
            "imap": "imap_ui",
            "mqtt": "mqtt_ui",
            "sftp": "sftp_admin_ui",
            "smb": "smb_ui",
            "ssh": "ssh_admin_ui",
            "website": "website_ui",
            "webhook": "http_api_admin_ui",
        }
        module_id = module_id_by_kind.get(kind)
        if not module_id:
            raise RuntimeError(f"connection template kind is not registered: {kind}")
        resolved = module_template_name(module_id, template_name)
        if resolved is None:
            raise RuntimeError(f"{module_id} template is not registered: {template_name}")
        return resolved

    def _config_ui_path(route_path: str) -> str:
        resolved = module_route_path("config_ui", route_path)
        if resolved is None:
            raise RuntimeError(f"config_ui route is not registered: {route_path}")
        return resolved

    def _connections_surface_path(route_path: str) -> str:
        resolved = module_route_path("connections_ui_readonly", route_path)
        if resolved is None:
            raise RuntimeError(f"connections_ui_readonly route is not registered: {route_path}")
        return resolved

    def _connection_parent_url(request: Request) -> str:
        canonical = _connections_surface_path("/connections")
        allowed = {
            canonical,
            _connections_surface_path("/connections/status"),
            _connections_surface_path("/connections/types"),
            _connections_surface_path("/connections/templates"),
        }
        requested = str(request.query_params.get("return_to", "") or "").strip()
        parsed = urlsplit(requested)
        if (
            requested
            and not parsed.scheme
            and not parsed.netloc
            and parsed.path in allowed
            and parsed.path != str(request.url.path)
        ):
            return requested
        return canonical

    def build_generic_connections_context(
        kind: str,
        rows: dict[str, dict[str, Any]],
        *,
        lang: str = "de",
        selected_ref_raw: str = "",
        test_status: str = "",
        blank_selected: bool = False,
        ref_key: str,
        selected_ref_key: str,
        selected_key: str,
        rows_key: str,
        healthy_key: str,
        issue_key: str,
        test_status_key: str,
    ) -> dict[str, Any]:
        refs = sorted(rows.keys())
        selected_ref = "" if blank_selected else (_sanitize_connection_name(selected_ref_raw) or (refs[0] if refs else ""))
        selected = rows.get(selected_ref, {})
        status_rows = _attach_connection_edit_urls(kind, build_connection_status_rows(
            kind,
            rows,
            selected_ref=selected_ref,
            cached_only=True,
            base_dir=BASE_DIR,
            lang=lang,
        ))
        return {
            ref_key: refs,
            f"{ref_key[:-1]}_options" if ref_key.endswith("s") else f"{ref_key}_options": _build_connection_ref_options(rows),
            selected_ref_key: selected_ref,
            selected_key: selected,
            rows_key: status_rows,
            healthy_key: sum(1 for item in status_rows if item["status"] == "ok"),
            issue_key: sum(1 for item in status_rows if item["status"] == "error"),
            test_status_key: str(test_status).strip().lower(),
        }

    def base_connections_page_context(
        request: Request,
        saved: int,
        info: str,
        error: str,
        *,
        kind: str = "rss",
        page_type: str = "overview",
        connection_ref: str = "",
    ) -> dict[str, Any]:
        settings = _get_settings()
        normalized_page_type = _normalize_connection_page_type(page_type)
        return_to = _connection_parent_url(request)
        return {
            "title": settings.ui.title,
            "username": _get_username_from_request(request),
            "saved": bool(saved),
            "info_message": info,
            "error_message": error,
            "connection_page_type": normalized_page_type,
            "connection_mode": "create" if normalized_page_type == "create" else "edit",
            "connection_overview_url": connection_canonical_url(kind, "overview"),
            "connection_create_url": connection_canonical_url(kind, "create"),
            "connection_detail_url": (
                connection_canonical_url(kind, "detail", connection_ref=connection_ref)
                if connection_ref
                else ""
            ),
            "connection_mode_edit_url": (
                connection_canonical_url(kind, "detail", connection_ref=connection_ref)
                if connection_ref
                else connection_canonical_url(kind, "overview")
            ),
            "connection_mode_create_url": connection_canonical_url(kind, "create"),
            "return_to": return_to,
        }

    def render_connection_page(
        request: Request,
        *,
        kind: str,
        saved: int,
        info: str,
        error: str,
        context_builder: Callable[..., dict[str, Any]],
        page_type: str = "overview",
        connection_ref: str = "",
        **builder_kwargs: Any,
    ) -> HTMLResponse:
        selected_ref = str(connection_ref or builder_kwargs.get("selected_ref_raw", "") or "").strip()
        if selected_ref:
            builder_kwargs["selected_ref_raw"] = selected_ref
        context = base_connections_page_context(
            request,
            saved,
            info,
            error,
            kind=kind,
            page_type=page_type,
            connection_ref=selected_ref,
        )
        builder_kwargs.setdefault("lang", str(getattr(request.state, "lang", "de") or "de"))
        context.update(context_builder(**builder_kwargs))
        if isinstance(context.get("connection_intro"), dict):
            context["connection_intro"] = dict(context["connection_intro"])
            context["connection_intro"]["back_url"] = (
                context.get("connection_overview_url")
                if context.get("connection_page_type") in {"create", "detail"}
                else context.get("return_to") or _connections_surface_path("/connections")
            )
        return TEMPLATES.TemplateResponse(
            request=request,
            name=_connection_ui_template_name(kind, connection_template_name(kind)),
            context=context,
        )

    return ConnectionPageHelpers(
        build_generic_connections_context=build_generic_connections_context,
        base_connections_page_context=base_connections_page_context,
        render_connection_page=render_connection_page,
    )
