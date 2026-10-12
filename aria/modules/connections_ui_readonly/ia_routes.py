"""Canonical UI route helpers for connection overview/create/detail pages."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from fastapi import Request
from fastapi.responses import RedirectResponse


CONNECTION_URL_SEGMENTS: dict[str, str] = {
    "discord": "discord",
    "email": "smtp",
    "google_calendar": "google-calendar",
    "http_api": "http-api",
    "imap": "imap",
    "mqtt": "mqtt",
    "rss": "rss",
    "sftp": "sftp",
    "smb": "smb",
    "ssh": "ssh",
    "website": "websites",
    "webhook": "webhook",
}

SEGMENT_CONNECTION_KINDS = {segment: kind for kind, segment in CONNECTION_URL_SEGMENTS.items()}

CONNECTION_REF_QUERY_KEYS: dict[str, str] = {
    "discord": "discord_ref",
    "email": "email_ref",
    "google_calendar": "google_calendar_ref",
    "http_api": "http_api_ref",
    "imap": "imap_ref",
    "mqtt": "mqtt_ref",
    "rss": "rss_ref",
    "sftp": "sftp_ref",
    "smb": "smb_ref",
    "ssh": "ref",
    "website": "website_ref",
    "webhook": "webhook_ref",
}

_ROUTING_QUERY_KEYS = {
    "mode",
    "create",
    "create_new",
    "new",
    "ref",
    *CONNECTION_REF_QUERY_KEYS.values(),
}


def connection_canonical_url(
    kind: str,
    page_type: str,
    *,
    connection_ref: str = "",
    query: Mapping[str, object] | None = None,
) -> str:
    """Return the single canonical presentation URL without reading config."""

    segment = CONNECTION_URL_SEGMENTS[str(kind)]
    base = f"/config/connections/{segment}"
    if page_type == "create":
        base = f"{base}/new"
    elif page_type == "detail":
        clean_ref = str(connection_ref or "").strip()
        if not clean_ref:
            raise ValueError("connection_ref is required for a detail URL")
        base = f"{base}/{quote(clean_ref, safe='')}"
    elif page_type != "overview":
        raise ValueError(f"unsupported connection page type: {page_type}")
    pairs = []
    for key, value in (query or {}).items():
        if key in _ROUTING_QUERY_KEYS or value in (None, "", 0, False):
            continue
        pairs.append((str(key), str(value)))
    return f"{base}?{urlencode(pairs)}" if pairs else base


def legacy_connection_redirect(
    request: Request,
    *,
    kind: str,
    selected_ref: str = "",
    create_requested: bool = False,
) -> RedirectResponse | None:
    """Redirect legacy query-driven views; plain collection GET stays overview."""

    mode = str(request.query_params.get("mode", "") or "").strip().lower()
    create = create_requested or mode in {"create", "new", "add"}
    create = create or str(request.query_params.get("create_new", "0")).lower() in {"1", "true", "yes"}
    create = create or str(request.query_params.get("new", "0")).lower() in {"1", "true", "yes"}
    ref_key = CONNECTION_REF_QUERY_KEYS[kind]
    ref = str(selected_ref or request.query_params.get(ref_key, "") or request.query_params.get("ref", "")).strip()
    preserved = dict(request.query_params)
    if create:
        target = connection_canonical_url(kind, "create", query=preserved)
    elif ref:
        target = connection_canonical_url(kind, "detail", connection_ref=ref, query=preserved)
    else:
        return None
    return RedirectResponse(url=target, status_code=307)


def canonicalize_connection_ui_redirect(url: str) -> str:
    """Translate a connection mutation's legacy query target to its canonical page."""

    parsed = urlsplit(str(url or ""))
    segment = parsed.path.removeprefix("/config/connections/").strip("/")
    kind = SEGMENT_CONNECTION_KINDS.get(segment)
    if not kind:
        return str(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ref = str(query.get(CONNECTION_REF_QUERY_KEYS[kind], "") or query.get("ref", "")).strip()
    create = str(query.get("mode", "")).lower() in {"create", "new", "add"}
    create = create or str(query.get("create_new", "")).lower() in {"1", "true", "yes"}
    if ref:
        return connection_canonical_url(kind, "detail", connection_ref=ref, query=query)
    if create:
        return connection_canonical_url(kind, "create", query=query)
    return connection_canonical_url(kind, "overview", query=query)
