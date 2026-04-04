from __future__ import annotations

from typing import Any, Callable

from aria.core.action_plan import ActionPlan


CapabilityLabelResolver = Callable[[str], str]


CAPABILITY_CATALOG: dict[str, dict[str, Any]] = {
    "file_read": {
        "icon": "📄",
        "badge": "file_read",
        "detail_attr": "path",
        "detail_label": "Pfad",
        "executors": ["sftp", "smb"],
    },
    "file_write": {
        "icon": "📝",
        "badge": "file_write",
        "detail_attr": "path",
        "detail_label": "Pfad",
        "executors": ["sftp", "smb"],
    },
    "file_list": {
        "icon": "🗂",
        "badge": "file_list",
        "detail_attr": "path",
        "detail_label": "Pfad",
        "executors": ["sftp", "smb"],
    },
    "feed_read": {"icon": "📰", "badge": "feed_read", "executors": ["rss"]},
    "webhook_send": {"icon": "📡", "badge": "webhook_send", "executors": ["webhook"]},
    "discord_send": {"icon": "💬", "badge": "discord_send", "executors": ["discord"]},
    "api_request": {
        "icon": "🌐",
        "badge": "api_request",
        "detail_attr": "path",
        "detail_label": "Pfad",
        "executors": ["http_api"],
    },
    "email_send": {"icon": "✉️", "badge": "email_send", "executors": ["email"]},
    "mail_read": {"icon": "📬", "badge": "mail_read", "executors": ["imap"]},
    "mail_search": {
        "icon": "🔎",
        "badge": "mail_search",
        "detail_attr": "content",
        "detail_label": "Suche",
        "executors": ["imap"],
    },
    "mqtt_publish": {
        "icon": "📟",
        "badge": "mqtt_publish",
        "detail_attr": "path",
        "detail_label": "Topic",
        "executors": ["mqtt"],
    },
}


def capability_badge(capability: str) -> tuple[str, str] | None:
    spec = CAPABILITY_CATALOG.get(str(capability or "").strip().lower())
    if not spec:
        return None
    return str(spec.get("icon", "💬")), str(spec.get("badge", capability)).strip()


def build_capability_detail_lines(plan: ActionPlan, connection_kind_label: CapabilityLabelResolver) -> list[str]:
    capability = str(plan.capability or "").strip().lower()
    details = [f"Ausgeführt via {connection_kind_label(plan.connection_kind)}-Profil `{plan.connection_ref}`"]
    spec = CAPABILITY_CATALOG.get(capability, {})
    detail_attr = str(spec.get("detail_attr") or "").strip()
    detail_label = str(spec.get("detail_label") or "").strip()
    if detail_attr and detail_label:
        value = str(getattr(plan, detail_attr, "") or "").strip()
        if value:
            details.append(f"{detail_label}: {value}")
    return details


def capability_executor_bindings() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for capability, spec in CAPABILITY_CATALOG.items():
        for connection_kind in spec.get("executors", []):
            clean_kind = str(connection_kind or "").strip().lower()
            if clean_kind:
                rows.append((clean_kind, capability))
    return rows
