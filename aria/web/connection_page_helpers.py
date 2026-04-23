from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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

    def _normalize_connection_mode(mode: str | None) -> str:
        clean = str(mode or "edit").strip().lower()
        return "create" if clean in {"create", "new", "add"} else "edit"

    def _connection_mode_anchor(mode: str | None) -> str:
        return "#create-new" if _normalize_connection_mode(mode) == "create" else "#manage-existing"

    def _connection_mode_url(request: Request, mode: str) -> str:
        pairs = [(key, value) for key, value in parse_qsl(request.url.query, keep_blank_values=True) if key != "mode"]
        pairs.append(("mode", _normalize_connection_mode(mode)))
        query = urlencode(pairs)
        base = f"{request.url.path}?{query}" if query else str(request.url.path)
        return f"{base}{_connection_mode_anchor(mode)}"

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
        mode: str = "edit",
    ) -> dict[str, Any]:
        settings = _get_settings()
        connection_mode = _normalize_connection_mode(mode)
        return_to = _set_logical_back_url(request, fallback="/config")
        return {
            "title": settings.ui.title,
            "username": _get_username_from_request(request),
            "saved": bool(saved),
            "info_message": info,
            "error_message": error,
            "connection_mode": connection_mode,
            "connection_mode_edit_url": _connection_mode_url(request, "edit"),
            "connection_mode_create_url": _connection_mode_url(request, "create"),
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
        mode: str = "edit",
        **builder_kwargs: Any,
    ) -> HTMLResponse:
        context = base_connections_page_context(request, saved, info, error, mode=mode)
        builder_kwargs.setdefault("lang", str(getattr(request.state, "lang", "de") or "de"))
        context.update(context_builder(**builder_kwargs))
        if isinstance(context.get("connection_intro"), dict):
            context["connection_intro"] = dict(context["connection_intro"])
            context["connection_intro"]["back_url"] = context.get("return_to") or "/config"
        return TEMPLATES.TemplateResponse(
            request=request,
            name=connection_template_name(kind),
            context=context,
        )

    return ConnectionPageHelpers(
        build_generic_connections_context=build_generic_connections_context,
        base_connections_page_context=base_connections_page_context,
        render_connection_page=render_connection_page,
    )
