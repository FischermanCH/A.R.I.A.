from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from aria.core.connection_catalog import (
    connection_edit_page,
    connection_field_specs,
    connection_menu_meta,
    connection_overview_meta,
    connection_ref_query_param,
    connection_status_meta,
    connection_ui_sections,
    normalize_connection_kind,
)

_SEARXNG_CATEGORY_OPTIONS: list[tuple[str, str]] = [
    ("general", "General"),
    ("news", "News"),
    ("it", "IT"),
    ("science", "Science"),
    ("videos", "Videos"),
]
_SEARXNG_ENGINE_OPTIONS: list[tuple[str, str]] = [
    ("duckduckgo", "DuckDuckGo"),
    ("startpage", "Startpage"),
    ("brave", "Brave"),
    ("qwant", "Qwant"),
    ("wikipedia", "Wikipedia"),
    ("wikibooks", "WikiBooks"),
    ("youtube", "YouTube"),
    ("github", "GitHub"),
    ("stackoverflow", "Stack Overflow"),
    ("arxiv", "arXiv"),
]


def build_schema_form_fields(
    *,
    kind: str,
    values: dict[str, Any],
    prefix: str,
    ref_value: str,
    include_ref: bool = True,
    placeholders: dict[str, str] | None = None,
    required_fields: set[str] | None = None,
    select_options: dict[str, list[str]] | None = None,
    datalist_options: dict[str, list[str]] | None = None,
    boolean_defaults: dict[str, bool] | None = None,
    secrets_with_hints: dict[str, str] | None = None,
    field_hints: dict[str, str] | None = None,
    ordered_fields: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    hint_keys = {
        ("webhook", "url"): "config_conn.webhook_secret_hint",
        ("http_api", "auth_token"): "config_conn.http_api_token_hint",
        ("mqtt", "password"): "config_conn.mqtt_password_hint",
        ("email", "password"): "config_conn.email_password_hint",
        ("imap", "password"): "config_conn.imap_password_hint",
        ("smb", "password"): "config_conn.smb_password_store_hint",
        ("sftp", "password"): "config_conn.sftp_password_store_hint",
        ("sftp", "key_path"): "config_conn.sftp_key_path_hint",
        ("discord", "webhook_url"): "config_conn.discord_password_hint",
        ("google_calendar", "client_secret"): "config_conn.google_calendar_auth_hint",
        ("google_calendar", "refresh_token"): "config_conn.google_calendar_auth_hint",
        ("ssh", "allow_commands"): "config_conn.allow_commands_hint",
        ("ssh", "service_url"): "config_conn.ssh_service_url_hint",
    }
    label_keys = {
        "connection_ref": "config_conn.profile_ref",
        "feed_url": "config_conn.rss_feed_url",
        "timeout_seconds": "config_conn.timeout",
        "method": "config_conn.webhook_method",
        "content_type": "config_conn.webhook_content_type",
        "base_url": "config_conn.http_api_base_url",
        "language": "config_conn.searxng_language",
        "safe_search": "config_conn.searxng_safe_search",
        "categories": "config_conn.searxng_categories",
        "engines": "config_conn.searxng_engines",
        "time_range": "config_conn.searxng_time_range",
        "max_results": "config_conn.searxng_max_results",
        "health_path": "config_conn.http_api_health_path",
        "auth_token": "config_conn.http_api_auth_token",
        "host": "config_conn.host",
        "port": "config_conn.port",
        "user": "config_conn.user",
        "service_url": "config_conn.ssh_service_url",
        "topic": "config_conn.mqtt_topic",
        "smtp_host": "config_conn.email_smtp_host",
        "from_email": "config_conn.email_from",
        "to_email": "config_conn.email_to",
        "mailbox": "config_conn.imap_mailbox",
        "calendar_id": "config_conn.calendar_target",
        "client_id": "config_conn.google_calendar_client_id",
        "client_secret": "config_conn.google_calendar_client_secret",
        "refresh_token": "config_conn.google_calendar_refresh_token",
    }
    label_keys_by_kind = {
        ("smb", "share"): "config_conn.smb_share",
        ("smb", "root_path"): "config_conn.smb_root_path",
        ("smb", "password"): "config_conn.smb_password",
        ("sftp", "root_path"): "config_conn.sftp_root_path",
        ("sftp", "key_path"): "config_conn.sftp_key_path",
        ("sftp", "password"): "config_conn.sftp_password",
        ("discord", "webhook_url"): "config_conn.discord_webhook_url",
        ("discord", "send_test_messages"): "config_conn.discord_send_test_messages_toggle",
        ("discord", "allow_skill_messages"): "config_conn.discord_allow_skill_messages_toggle",
        ("discord", "alert_skill_errors"): "config_conn.discord_alert_skill_errors_toggle",
        ("discord", "alert_safe_fix"): "config_conn.discord_alert_safe_fix_toggle",
        ("discord", "alert_connection_changes"): "config_conn.discord_alert_connection_changes_toggle",
        ("discord", "alert_system_events"): "config_conn.discord_alert_system_events_toggle",
        ("ssh", "strict_host_key_checking"): "config_conn.host_key_checking",
        ("ssh", "allow_commands"): "config_conn.allow_commands",
    }
    specs = connection_field_specs(kind)
    placeholders = dict(placeholders or {})
    required_fields = set(required_fields or set())
    select_options = dict(select_options or {})
    datalist_options = dict(datalist_options or {})
    boolean_defaults = dict(boolean_defaults or {})
    secrets_with_hints = dict(secrets_with_hints or {})
    field_hints = dict(field_hints or {})
    clean_kind = normalize_connection_kind(kind)

    field_order = [*( ["connection_ref"] if include_ref else []), *(ordered_fields or [])]
    grid_fields: list[dict[str, Any]] = []
    inline_fields: list[dict[str, Any]] = []
    secret_fields: list[dict[str, Any]] = []

    for name in field_order:
        if name == "connection_ref":
            grid_fields.append(
                {
                    "id": f"{prefix}_connection_ref",
                    "name": "connection_ref",
                    "label_key": label_keys.get("connection_ref", ""),
                    "label": "Profile name (ref)",
                    "type": "text",
                    "value": ref_value,
                    "required": True,
                    "placeholder": placeholders.get(name, "z.B. connection-ref"),
                }
            )
            continue

        spec = specs.get(name, {})
        if not spec:
            continue
        raw_value = values.get(name)
        field_type = str(spec.get("type", "str")).strip().lower()
        input_type = "text"
        if field_type == "int":
            input_type = "number"
        elif field_type == "bool":
            input_type = "checkbox"
        elif field_type == "list" and name not in select_options:
            input_type = "textarea"
        elif name in {"feed_url", "base_url", "url", "webhook_url"}:
            input_type = "url"
        elif name in {"from_email", "to_email"}:
            input_type = "email"
        elif name in {"password", "auth_token", "client_secret", "refresh_token"}:
            input_type = "password"
        elif name in select_options:
            input_type = "select"

        if field_type == "list" and isinstance(raw_value, list):
            display_value: Any = "\n".join(str(item).strip() for item in raw_value if str(item).strip())
        else:
            display_value = raw_value if raw_value not in (None, "") else spec.get("default", "")

        field = {
            "id": f"{prefix}_{name}",
            "name": name,
            "label_key": label_keys_by_kind.get((clean_kind, name), label_keys.get(name, "")),
            "label": str(spec.get("label", name)).strip(),
            "type": input_type,
            "value": display_value,
            "required": name in required_fields,
            "placeholder": placeholders.get(name, ""),
            "min": spec.get("min"),
            "options": list(select_options.get(name, [])),
            "datalist_id": f"{prefix}_{name}_options" if datalist_options.get(name) else "",
            "datalist_options": list(datalist_options.get(name, [])),
            "checked": bool(raw_value) if raw_value is not None else bool(boolean_defaults.get(name, False)),
            "hint": field_hints.get(name, secrets_with_hints.get(name, "")),
            "hint_key": hint_keys.get((normalize_connection_kind(kind), name), ""),
            "rows": int(spec.get("rows", 4) or 4),
        }
        if input_type == "checkbox":
            inline_fields.append(field)
        elif input_type == "password":
            secret_fields.append(field)
        else:
            grid_fields.append(field)

    return {"grid_fields": grid_fields, "inline_fields": inline_fields, "secret_fields": secret_fields}


def build_schema_toggle_sections(*, kind: str, values: dict[str, Any], prefix: str, section_names: list[str]) -> list[dict[str, Any]]:
    clean_kind = normalize_connection_kind(kind)
    specs = connection_field_specs(clean_kind)
    sections = connection_ui_sections(clean_kind)
    rows: list[dict[str, Any]] = []
    for section_name in section_names:
        section_spec = sections.get(section_name, {})
        cards: list[dict[str, Any]] = []
        for field_name, spec in specs.items():
            if str(spec.get("type", "")).strip().lower() != "bool":
                continue
            if str(spec.get("section", "")).strip() != section_name:
                continue
            raw_value = values.get(field_name)
            checked = bool(raw_value) if raw_value is not None else False
            if field_name in {"send_test_messages", "allow_skill_messages"} and raw_value is None:
                checked = True
            cards.append(
                {
                    "id": f"{prefix}_{field_name}",
                    "name": field_name,
                    "checked": checked,
                    "title_key": str(spec.get("title_key", "")).strip(),
                    "title": str(spec.get("title", spec.get("label", field_name))).strip(),
                    "hint_key": str(spec.get("hint_key", "")).strip(),
                    "hint": str(spec.get("hint", "")).strip(),
                    "toggle_key": str(spec.get("toggle_key", "")).strip(),
                    "toggle": str(spec.get("toggle", spec.get("label", field_name))).strip(),
                }
            )
        if not cards:
            continue
        rows.append(
            {
                "name": section_name,
                "title_key": str(section_spec.get("title_key", "")).strip(),
                "title": str(section_spec.get("title", section_name)).strip(),
                "hint_key": str(section_spec.get("hint_key", "")).strip(),
                "hint": str(section_spec.get("hint", "")).strip(),
                "cards": cards,
            }
        )
    return rows


def build_connection_intro(*, kind: str, summary_cards: list[dict[str, Any]]) -> dict[str, Any]:
    meta = connection_menu_meta(kind)
    return {
        "title_key": str(meta.get("title_key") or "").strip(),
        "title": str(meta.get("label") or kind).strip(),
        "subtitle_key": str(meta.get("desc_key") or "").strip(),
        "subtitle": "",
        "back_url": "/config",
        "back_label_key": "config_conn.back_to_hub",
        "back_label": "Back to connection overview",
        "summary_cards": summary_cards,
    }


def build_connection_status_block(*, kind: str, rows: list[dict[str, Any]], collapse_threshold: int = 0) -> dict[str, Any]:
    meta = connection_status_meta(kind)
    should_collapse = collapse_threshold > 0 and len(rows) >= collapse_threshold
    return {
        "title_key": str(meta.get("title_key") or "").strip(),
        "title": str(meta.get("title") or "").strip(),
        "hint_key": str(meta.get("hint_key") or "").strip(),
        "hint": str(meta.get("hint") or "").strip(),
        "empty_key": str(meta.get("empty_key") or "").strip(),
        "empty_text": str(meta.get("empty_text") or "").strip(),
        "rows": rows,
        "collapsed": should_collapse,
        "total_count": len(rows),
        "ok_count": sum(1 for item in rows if str(item.get("status", "")).strip().lower() == "ok"),
        "warn_count": sum(1 for item in rows if str(item.get("status", "")).strip().lower() == "warn"),
        "error_count": sum(1 for item in rows if str(item.get("status", "")).strip().lower() == "error"),
    }


def connection_edit_url(kind: str, ref: str) -> str:
    route = connection_edit_page(kind)
    param = connection_ref_query_param(kind)
    clean_ref = str(ref or "").strip()
    if normalize_connection_kind(kind) == "rss" and clean_ref == "RSS":
        return f"{route}#manage-existing"
    if not route:
        return ""
    if not clean_ref or not param:
        return f"{route}#manage-existing"
    return f"{route}?{param}={quote_plus(clean_ref)}#manage-existing"


def attach_connection_edit_urls(kind: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["edit_url"] = connection_edit_url(kind, str(payload.get("ref", "")).strip())
        enriched.append(payload)
    return enriched


def attach_mixed_connection_edit_urls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        kind = normalize_connection_kind(str(payload.get("kind_key", "") or payload.get("kind", "")).strip().replace(" ", "_"))
        ref = str(payload.get("ref", "")).strip()
        route = connection_edit_page(kind)
        param = connection_ref_query_param(kind)
        if kind == "rss" and ref == "RSS":
            payload["edit_url"] = f"{route}#manage-existing"
        elif not route:
            payload["edit_url"] = ""
        elif not ref or not param:
            payload["edit_url"] = f"{route}#manage-existing"
        else:
            payload["edit_url"] = f"{route}?{param}={quote_plus(ref)}#manage-existing"
        enriched.append(payload)
    return enriched


def build_connection_summary_cards(*, kind: str, profiles: int, healthy: int, issues: int, extra_cards: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    meta = connection_overview_meta(kind)
    cards = [
        {
            "label_key": str(meta["profiles"].get("label_key") or "").strip(),
            "label": str(meta["profiles"].get("label") or "Profiles").strip(),
            "value": profiles,
            "hint_key": str(meta["profiles"].get("hint_key") or "").strip(),
            "hint": str(meta["profiles"].get("hint") or "").strip(),
        },
        {
            "label_key": str(meta["healthy"].get("label_key") or "").strip(),
            "label": str(meta["healthy"].get("label") or "Healthy").strip(),
            "value": healthy,
            "hint_key": str(meta["healthy"].get("hint_key") or "").strip(),
            "hint": str(meta["healthy"].get("hint") or "").strip(),
        },
        {
            "label_key": str(meta["issues"].get("label_key") or "").strip(),
            "label": str(meta["issues"].get("label") or "Issues").strip(),
            "value": issues,
            "hint_key": str(meta["issues"].get("hint_key") or "").strip(),
            "hint": str(meta["issues"].get("hint") or "").strip(),
        },
    ]
    for card in extra_cards or []:
        cards.append(dict(card))
    return cards
