from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from aria.core.action_plan import ActionPlan
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.i18n import I18NStore


CapabilityLabelResolver = Callable[[str], str]
_CAPABILITY_CATALOG_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


CAPABILITY_CATALOG: dict[str, dict[str, Any]] = {
    "file_read": {
        "icon": "📄",
        "badge": "file_read",
        "detail_attr": "path",
        "detail_label_key": "detail_path",
        "executors": ["sftp", "smb"],
    },
    "file_write": {
        "icon": "📝",
        "badge": "file_write",
        "detail_attr": "path",
        "detail_label_key": "detail_path",
        "executors": ["sftp", "smb"],
    },
    "file_list": {
        "icon": "🗂",
        "badge": "file_list",
        "detail_attr": "path",
        "detail_label_key": "detail_path",
        "executors": ["sftp", "smb"],
    },
    "website_read": {"icon": "🔗", "badge": "website_read", "executors": ["website"]},
    "website_list": {"icon": "🗃", "badge": "website_list", "executors": ["website"]},
    "feed_read": {"icon": "📰", "badge": "feed_read", "executors": ["rss"]},
    "calendar_read": {
        "icon": "📅",
        "badge": "calendar_read",
        "detail_attr": "path",
        "detail_label_key": "detail_range",
        "executors": ["google_calendar"],
    },
    "webhook_send": {"icon": "📡", "badge": "webhook_send", "executors": ["webhook"]},
    "discord_send": {"icon": "💬", "badge": "discord_send", "executors": ["discord"]},
    "api_request": {
        "icon": "🌐",
        "badge": "api_request",
        "detail_attr": "path",
        "detail_label_key": "detail_path",
        "executors": ["http_api"],
    },
    "email_send": {"icon": "✉️", "badge": "email_send", "executors": ["email"]},
    "mail_read": {"icon": "📬", "badge": "mail_read", "executors": ["imap"]},
    "mail_search": {
        "icon": "🔎",
        "badge": "mail_search",
        "detail_attr": "content",
        "detail_label_key": "detail_search",
        "executors": ["imap"],
    },
    "mqtt_publish": {
        "icon": "📟",
        "badge": "mqtt_publish",
        "detail_attr": "path",
        "detail_label_key": "detail_topic",
        "executors": ["mqtt"],
    },
    "ssh_command": {
        "icon": "💻",
        "badge": "ssh_command",
        "detail_attr": "content",
        "detail_label_key": "detail_command",
        "executors": ["ssh"],
    },
}

CAPABILITY_ALIASES: dict[str, str] = {
    "rss_read": "feed_read",
    "http_api_request": "api_request",
}


def capability_badge(capability: str) -> tuple[str, str] | None:
    spec = CAPABILITY_CATALOG.get(normalize_capability(capability))
    if not spec:
        return None
    return str(spec.get("icon", "💬")), str(spec.get("badge", capability)).strip()


def normalize_capability(capability: str) -> str:
    clean = str(capability or "").strip().lower()
    if not clean:
        return ""
    return CAPABILITY_ALIASES.get(clean, clean)


def capability_executor_kinds(capability: str) -> list[str]:
    spec = CAPABILITY_CATALOG.get(normalize_capability(capability), {})
    rows: list[str] = []
    seen: set[str] = set()
    for connection_kind in spec.get("executors", []):
        clean_kind = normalize_connection_kind(connection_kind)
        if not clean_kind or clean_kind in seen:
            continue
        seen.add(clean_kind)
        rows.append(clean_kind)
    return rows


def capability_matches_connection_kind(capability: str, connection_kind: str) -> bool:
    clean_capability = normalize_capability(capability)
    clean_kind = normalize_connection_kind(connection_kind)
    if not clean_capability or not clean_kind:
        return True
    allowed_kinds = capability_executor_kinds(clean_capability)
    if not allowed_kinds:
        return True
    return clean_kind in set(allowed_kinds)


def _capability_detail_text(language: str | None, key: str, fallback: str, **values: object) -> str:
    template = _CAPABILITY_CATALOG_I18N.t(language or "de", f"capability_catalog.{key}", fallback or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def build_capability_detail_lines(
    plan: ActionPlan,
    connection_kind_label: CapabilityLabelResolver,
    *,
    language: str | None = None,
) -> list[str]:
    capability = normalize_capability(plan.capability)
    details = [
        _capability_detail_text(
            language,
            "executed_via",
            "Executed via {kind} profile `{ref}`",
            kind=connection_kind_label(plan.connection_kind),
            ref=plan.connection_ref,
        )
    ]
    spec = CAPABILITY_CATALOG.get(capability, {})
    detail_attr = str(spec.get("detail_attr") or "").strip()
    detail_label_key = str(spec.get("detail_label_key") or "").strip()
    detail_label = _capability_detail_text(language, detail_label_key, detail_label_key) if detail_label_key else ""
    if detail_attr and detail_label:
        value = str(getattr(plan, detail_attr, "") or "").strip()
        if value:
            details.append(f"{detail_label}: {value}")
    return details


def capability_executor_bindings() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for capability, spec in CAPABILITY_CATALOG.items():
        for connection_kind in spec.get("executors", []):
            clean_kind = normalize_connection_kind(connection_kind)
            if clean_kind:
                rows.append((clean_kind, capability))
    return rows
