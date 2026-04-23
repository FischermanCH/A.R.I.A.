from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import Request

SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
LogicalBackSetter = Callable[..., str]
LocalizedMessage = Callable[[str, str, str], str]
InfoMessageFormatter = Callable[[str, str], str]
MixedEditUrlAttacher = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
ConnectionsSurfacePathResolver = Callable[..., str]
SearxngConnectionsReader = Callable[[], dict[str, dict[str, Any]]]
SampleConnectionRowsBuilder = Callable[[], list[dict[str, Any]]]
SettingsConnectionStatusRowsBuilder = Callable[..., list[dict[str, Any]]]
ConnectionMenuRowsBuilder = Callable[[], list[dict[str, Any]]]
SearxngProbe = Callable[..., dict[str, Any]]


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
    read_searxng_connections: SearxngConnectionsReader
    build_sample_connection_rows: SampleConnectionRowsBuilder
    build_settings_connection_status_rows: SettingsConnectionStatusRowsBuilder
    connection_menu_rows: ConnectionMenuRowsBuilder
    probe_searxng_stack_service: SearxngProbe


def build_connections_page_context_helper(deps: ConnectionsSurfaceHelperDeps) -> Callable[..., dict[str, Any]]:
    BASE_DIR = deps.base_dir
    _get_settings = deps.get_settings
    _get_username_from_request = deps.get_username_from_request
    _set_logical_back_url = deps.set_logical_back_url
    _msg = deps.msg
    _format_config_info_message = deps.format_config_info_message
    _attach_mixed_connection_edit_urls = deps.attach_mixed_connection_edit_urls
    _connections_surface_path = deps.connections_surface_path
    _read_searxng_connections = deps.read_searxng_connections
    _build_sample_connection_rows = deps.build_sample_connection_rows
    build_settings_connection_status_rows = deps.build_settings_connection_status_rows
    connection_menu_rows = deps.connection_menu_rows
    probe_searxng_stack_service = deps.probe_searxng_stack_service

    def build_connections_page_context(
        request: Request,
        *,
        error: str = "",
        info: str = "",
        logical_back_fallback: str = "/connections",
        page_return_to: str = "/connections",
        connections_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> dict[str, Any]:
        settings = _get_settings()
        username = _get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        _set_logical_back_url(request, fallback=logical_back_fallback)
        error_message = ""
        if error == "admin_mode_required":
            error_message = "Admin-Modus aktivieren, um diesen Bereich zu sehen." if lang.startswith("de") else "Enable admin mode to access this area."
        elif error == "no_admin":
            error_message = "Nur Admins dürfen diesen Bereich öffnen." if lang.startswith("de") else "Only admins can open this area."

        connection_rows = connection_menu_rows()
        searxng_stack = probe_searxng_stack_service(lang=lang)
        searxng_profiles = _read_searxng_connections()
        for row in connection_rows:
            if row.get("kind") != "searxng":
                continue
            row["availability_status"] = str(searxng_stack.get("status", "")).strip() or "ok"
            row["availability_message"] = (
                str(searxng_stack.get("message", "")).strip()
                if row["availability_status"] != "ok"
                else ""
            )
            row["disabled"] = not bool(searxng_stack.get("available")) and not bool(searxng_profiles)
            row["warning_badge"] = (
                _msg(lang, "Stack fehlt", "Stack missing")
                if row["disabled"]
                else (_msg(lang, "Prüfen", "Check") if row["availability_status"] == "warn" else "")
            )

        sample_rows = _build_sample_connection_rows()
        connection_status_rows = _attach_mixed_connection_edit_urls(
            build_settings_connection_status_rows(
                settings,
                page_probe=True,
                cached_only_threshold=4,
                base_dir=BASE_DIR,
                lang=lang,
            )
        )
        configured_count = sum(1 for row in connection_rows if not row.get("disabled"))
        warning_count = sum(1 for row in connection_rows if row.get("warning_badge"))
        ok_status_count = sum(1 for row in connection_status_rows if str(row.get("status", "")).strip() == "ok")
        configured_profile_count = len(connection_status_rows)
        overview_checks = [
            {
                "status": "ok" if connection_status_rows else "warn",
                "title": _msg(lang, "Live-Status", "Live status"),
                "summary": str(len(connection_status_rows)),
                "meta": _msg(
                    lang,
                    f"{ok_status_count} Verbindungen aktuell ok",
                    f"{ok_status_count} connections currently ok",
                ),
                "href": "/connections/status",
            },
            {
                "status": "ok" if configured_count else "warn",
                "title": _msg(lang, "Verbindungstypen", "Connection types"),
                "summary": str(configured_count),
                "meta": _msg(
                    lang,
                    f"von {len(connection_rows)} Typen direkt verfuegbar",
                    f"{configured_count} of {len(connection_rows)} types ready",
                ),
                "href": "/connections/types",
            },
            {
                "status": "ok" if sample_rows else "warn",
                "title": _msg(lang, "Samples", "Samples"),
                "summary": str(len(sample_rows)),
                "meta": _msg(lang, "importierbare Vorlagen", "importable samples"),
                "href": "/connections/templates",
            },
            {
                "status": "warn" if warning_count else "ok",
                "title": "SearXNG",
                "summary": _msg(lang, "Erreichbar", "Reachable") if searxng_stack.get("available") else _msg(lang, "Pruefen", "Check"),
                "meta": str(searxng_stack.get("message", "")).strip() or _msg(lang, "Stackdienst fuer Suche bereit", "Search stack is ready"),
                "href": (
                    f"/config/connections/searxng?return_to={quote_plus(_connections_surface_path(page_return_to, fallback='/connections'))}"
                    if request.state.can_access_advanced_config
                    else "/connections/types"
                ),
            },
        ]
        next_steps = [
            {
                "icon": "plus",
                "title": _msg(
                    lang,
                    "Erste Verbindung anlegen" if configured_profile_count <= 0 else "Weitere Verbindung anlegen",
                    "Create first connection" if configured_profile_count <= 0 else "Add connection",
                ),
                "desc": _msg(
                    lang,
                    "Starte mit SSH, SFTP, Discord oder RSS auf den jeweiligen Typseiten, statt direkt in Rohkonfigurationen zu fallen.",
                    "Start with SSH, SFTP, Discord, or RSS from the type pages instead of dropping straight into raw configuration.",
                ),
                "href": "/connections/types",
                "badge": f"{configured_count}/{len(connection_rows)}",
            },
            {
                "icon": "stats",
                "title": _msg(
                    lang,
                    "Live-Status pruefen" if configured_profile_count > 0 else "Status danach pruefen",
                    "Review live status" if configured_profile_count > 0 else "Check status afterwards",
                ),
                "desc": _msg(
                    lang,
                    "Hier siehst du direkt, welche bereits konfigurierten Verbindungen gesund, fraglich oder offline sind.",
                    "This shows which configured connections are currently healthy, uncertain, or offline.",
                ),
                "href": "/connections/status",
                "badge": str(configured_profile_count),
            },
            {
                "icon": "upload",
                "title": _msg(lang, "Vorlage importieren", "Import template"),
                "desc": _msg(
                    lang,
                    "Sample-Profile geben dir einen schnellen Startpunkt, wenn du nicht jede Verbindung von null aufsetzen willst.",
                    "Sample profiles give you a fast starting point when you do not want to build every connection from scratch.",
                ),
                "href": "/connections/templates",
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
            "overview_checks": overview_checks,
            "next_steps": next_steps,
            "configured_profile_count": configured_profile_count,
            "connections_nav": connections_nav,
            "connections_page_heading": page_heading,
            "page_return_to": _connections_surface_path(page_return_to, fallback="/connections"),
            "show_overview_checks": bool(show_overview_checks),
        }

    return build_connections_page_context
