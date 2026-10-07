from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules import module_route_path

SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
LogicalBackSetter = Callable[..., str]
LocalizedMessage = Callable[[str, str, str], str]
InfoMessageFormatter = Callable[[str, str], str]
MixedEditUrlAttacher = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
ConnectionsSurfacePathResolver = Callable[..., str]
SampleConnectionRowsBuilder = Callable[[], list[dict[str, Any]]]
SettingsConnectionStatusRowsBuilder = Callable[..., list[dict[str, Any]]]
ConnectionMenuRowsBuilder = Callable[[], list[dict[str, Any]]]
_CONNECTIONS_SURFACE_HELPERS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _connections_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CONNECTIONS_SURFACE_HELPERS_I18N.t(lang or "de", f"connections_surface_helpers.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _connections_route_path(route_path: str) -> str:
    resolved = module_route_path("connections_ui_readonly", route_path)
    if resolved is None:
        raise RuntimeError(f"connections_ui_readonly route is not registered: {route_path}")
    return resolved


def _web_search_route_path(route_path: str) -> str:
    resolved = module_route_path("web_search", route_path)
    if resolved is None:
        raise RuntimeError(f"web_search route is not registered: {route_path}")
    return resolved


@dataclass(frozen=True)
class ConnectionsSurfaceHelperDeps:
    base_dir: Path
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    set_logical_back_url: LogicalBackSetter
    msg: LocalizedMessage
    format_config_info_message: InfoMessageFormatter
    attach_mixed_connection_edit_urls: MixedEditUrlAttacher
    connections_surface_path: ConnectionsSurfacePathResolver
    build_sample_connection_rows: SampleConnectionRowsBuilder
    build_settings_connection_status_rows: SettingsConnectionStatusRowsBuilder
    connection_menu_rows: ConnectionMenuRowsBuilder


def build_connections_page_context_helper(deps: ConnectionsSurfaceHelperDeps) -> Callable[..., dict[str, Any]]:
    BASE_DIR = deps.base_dir
    _get_settings = deps.get_settings
    _get_username_from_request = deps.get_username_from_request
    _set_logical_back_url = deps.set_logical_back_url
    _format_config_info_message = deps.format_config_info_message
    _attach_mixed_connection_edit_urls = deps.attach_mixed_connection_edit_urls
    _connections_surface_path = deps.connections_surface_path
    _build_sample_connection_rows = deps.build_sample_connection_rows
    build_settings_connection_status_rows = deps.build_settings_connection_status_rows
    connection_menu_rows = deps.connection_menu_rows

    def build_connections_page_context(
        request: Request,
        *,
        error: str = "",
        info: str = "",
        logical_back_fallback: str | None = None,
        page_return_to: str | None = None,
        connections_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> dict[str, Any]:
        settings = _get_settings()
        username = _get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        default_connections_path = _connections_route_path("/connections")
        resolved_logical_back_fallback = logical_back_fallback or default_connections_path
        resolved_page_return_to = page_return_to or default_connections_path
        _set_logical_back_url(request, fallback=resolved_logical_back_fallback)
        error_message = ""
        if error == "admin_mode_required":
            error_message = _connections_text(lang, "admin_mode_required", "Enable Extended view to access this area.")
        elif error == "no_admin":
            error_message = _connections_text(lang, "no_admin", "Only admins can open this area.")

        live_status_refresh = str(request.query_params.get("refresh", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "live",
        }
        connection_rows = connection_menu_rows()

        sample_rows = _build_sample_connection_rows()
        connection_status_rows = _attach_mixed_connection_edit_urls(
            build_settings_connection_status_rows(
                settings,
                page_probe=live_status_refresh,
                cached_only=not live_status_refresh,
                cached_only_threshold=4 if live_status_refresh else None,
                base_dir=BASE_DIR,
                lang=lang,
            )
        )
        configured_count = sum(1 for row in connection_rows if not row.get("disabled"))
        ok_status_count = sum(1 for row in connection_status_rows if str(row.get("status", "")).strip() == "ok")
        configured_profile_count = len(connection_status_rows)
        connections_home_path = default_connections_path
        connections_status_path = _connections_route_path("/connections/status")
        connections_types_path = _connections_route_path("/connections/types")
        connections_templates_path = _connections_route_path("/connections/templates")
        overview_checks = [
            {
                "status": "ok" if connection_status_rows else "warn",
                "title": _connections_text(lang, "live_status", "Live status"),
                "summary": str(len(connection_status_rows)),
                "meta": _connections_text(lang, "connections_currently_ok", "{count} connections currently ok", count=ok_status_count),
                "href": connections_status_path,
            },
            {
                "status": "ok" if configured_count else "warn",
                "title": _connections_text(lang, "connection_types", "Connection types"),
                "summary": str(configured_count),
                "meta": _connections_text(lang, "connection_types_ready", "{configured_count} of {total_count} types ready", configured_count=configured_count, total_count=len(connection_rows)),
                "href": connections_types_path,
            },
            {
                "status": "ok" if sample_rows else "warn",
                "title": _connections_text(lang, "samples", "Samples"),
                "summary": str(len(sample_rows)),
                "meta": _connections_text(lang, "importable_samples", "importable samples"),
                "href": connections_templates_path,
            },
        ]
        next_steps = [
            {
                "icon": "plus",
                "title": _connections_text(lang, "create_first_connection" if configured_profile_count <= 0 else "add_connection", "Create first connection" if configured_profile_count <= 0 else "Add connection"),
                "desc": _connections_text(lang, "create_connection_desc", "Start with SSH, SFTP, Discord, or RSS from the type pages instead of dropping straight into raw configuration."),
                "href": connections_types_path,
                "badge": f"{configured_count}/{len(connection_rows)}",
            },
            {
                "icon": "stats",
                "title": _connections_text(lang, "review_live_status" if configured_profile_count > 0 else "check_status_afterwards", "Review live status" if configured_profile_count > 0 else "Check status afterwards"),
                "desc": _connections_text(lang, "live_status_desc", "This shows which configured connections are currently healthy, uncertain, or offline."),
                "href": connections_status_path,
                "badge": str(configured_profile_count),
            },
            {
                "icon": "upload",
                "title": _connections_text(lang, "import_template", "Import template"),
                "desc": _connections_text(lang, "import_template_desc", "Sample profiles give you a fast starting point when you do not want to build every connection from scratch."),
                "href": connections_templates_path,
                "badge": str(len(sample_rows)),
            },
        ]
        return {
            "title": settings.ui.title,
            "username": username,
            "info_message": _format_config_info_message(lang, info),
            "error_message": error_message,
            "connection_menu_rows": connection_rows,
            "sample_connection_rows": sample_rows,
            "connection_status_rows": connection_status_rows,
            "connection_status_live_refresh": live_status_refresh,
            "connection_status_cached_only": not live_status_refresh,
            "overview_checks": overview_checks,
            "next_steps": next_steps,
            "configured_profile_count": configured_profile_count,
            "connections_nav": connections_nav,
            "connections_page_heading": page_heading,
            "page_return_to": _connections_surface_path(resolved_page_return_to, fallback=connections_home_path),
            "show_overview_checks": bool(show_overview_checks),
        }

    return build_connections_page_context
