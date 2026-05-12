from __future__ import annotations

from dataclasses import replace
from typing import Any

from aria.core.connection_semantic_resolver import build_connection_aliases


def read_connection_field(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def with_capability_draft_updates(draft: Any | None, **updates: Any) -> Any | None:
    if draft is None:
        return None
    if hasattr(draft, "__dataclass_fields__"):
        return replace(draft, **updates)
    for key, value in updates.items():
        try:
            setattr(draft, key, value)
        except Exception:
            pass
    return draft


def build_ssh_target_dossier(
    connection_rows: dict[str, Any],
    connection_ref: str,
    *,
    recent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_ref = str(connection_ref or "").strip()
    row = dict(connection_rows or {}).get(clean_ref)
    if row is None:
        return {}
    recent = dict(recent_context or {})
    recent_summary: dict[str, Any] = {}
    if (
        str(recent.get("capability", "") or "").strip() == "ssh_command"
        and str(recent.get("connection_ref", "") or "").strip() == clean_ref
    ):
        if str(recent.get("content", "") or "").strip():
            recent_summary["last_command"] = str(recent.get("content", "") or "").strip()
        if str(recent.get("path", "") or "").strip():
            recent_summary["last_path"] = str(recent.get("path", "") or "").strip()

    def string_list(value: Any) -> list[str]:
        return [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]

    dossier = {
        "kind": "ssh",
        "ref": clean_ref,
        "title": str(read_connection_field(row, "title", "") or "").strip(),
        "description": str(read_connection_field(row, "description", "") or "").strip(),
        "host": str(read_connection_field(row, "host", "") or "").strip(),
        "port": str(read_connection_field(row, "port", "") or "").strip(),
        "user": str(read_connection_field(row, "user", "") or "").strip(),
        "service_url": str(read_connection_field(row, "service_url", "") or "").strip(),
        "aliases": build_connection_aliases("ssh", clean_ref, row),
        "tags": string_list(read_connection_field(row, "tags", [])),
        "allow_commands": string_list(read_connection_field(row, "allow_commands", [])),
        "guardrail_ref": str(read_connection_field(row, "guardrail_ref", "") or "").strip(),
        "strict_host_key_checking": str(read_connection_field(row, "strict_host_key_checking", "") or "").strip(),
        "recent_context": recent_summary,
    }
    return {
        key: value
        for key, value in dossier.items()
        if value is not None and value != "" and value != [] and value != {}
    }


def build_http_api_target_dossier(
    connection_rows: dict[str, Any],
    connection_ref: str,
    *,
    recent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_ref = str(connection_ref or "").strip()
    row = dict(connection_rows or {}).get(clean_ref)
    if row is None:
        return {}
    return {
        "connection_ref": clean_ref,
        "title": str(read_connection_field(row, "title", "") or "").strip(),
        "description": str(read_connection_field(row, "description", "") or "").strip(),
        "tags": list(read_connection_field(row, "tags", []) or []),
        "aliases": build_connection_aliases("http_api", clean_ref, row),
        "base_url": str(read_connection_field(row, "base_url", "") or "").strip(),
        "health_path": str(read_connection_field(row, "health_path", "/") or "/").strip() or "/",
        "configured_method": str(read_connection_field(row, "method", "GET") or "GET").strip().upper() or "GET",
        "guardrail_ref": str(read_connection_field(row, "guardrail_ref", "") or "").strip(),
        "recent_context": dict(recent_context or {}),
    }


def build_file_target_dossier(
    connection_rows: dict[str, Any],
    connection_ref: str,
    *,
    connection_kind: str,
    recent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_ref = str(connection_ref or "").strip()
    clean_kind = str(connection_kind or "").strip().lower()
    if clean_kind not in {"sftp", "smb"}:
        return {}
    row = dict(connection_rows or {}).get(clean_ref)
    if row is None:
        return {}

    def string_list(value: Any) -> list[str]:
        return [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]

    dossier = {
        "kind": clean_kind,
        "connection_ref": clean_ref,
        "title": str(read_connection_field(row, "title", "") or "").strip(),
        "description": str(read_connection_field(row, "description", "") or "").strip(),
        "host": str(read_connection_field(row, "host", "") or "").strip(),
        "share": str(read_connection_field(row, "share", "") or "").strip() if clean_kind == "smb" else "",
        "root_path": str(read_connection_field(row, "root_path", "") or "").strip(),
        "aliases": build_connection_aliases(clean_kind, clean_ref, row),
        "tags": string_list(read_connection_field(row, "tags", [])),
        "guardrail_ref": str(read_connection_field(row, "guardrail_ref", "") or "").strip(),
        "allowed_operations": ["list", "read", "write"],
        "recent_context": dict(recent_context or {}),
    }
    return {
        key: value
        for key, value in dossier.items()
        if value is not None and value != "" and value != [] and value != {}
    }


def build_message_target_dossier(
    connection_rows: dict[str, Any],
    connection_ref: str,
    *,
    connection_kind: str,
    recent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_ref = str(connection_ref or "").strip()
    clean_kind = str(connection_kind or "").strip().lower()
    if clean_kind not in {"discord", "webhook", "email", "mqtt"}:
        return {}
    row = dict(connection_rows or {}).get(clean_ref)
    if row is None:
        return {}

    def string_list(value: Any) -> list[str]:
        return [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]

    dossier = {
        "kind": clean_kind,
        "connection_ref": clean_ref,
        "title": str(read_connection_field(row, "title", "") or "").strip(),
        "description": str(read_connection_field(row, "description", "") or "").strip(),
        "aliases": build_connection_aliases(clean_kind, clean_ref, row),
        "tags": string_list(read_connection_field(row, "tags", [])),
        "guardrail_ref": str(read_connection_field(row, "guardrail_ref", "") or "").strip(),
        "default_topic": str(read_connection_field(row, "topic", "") or "").strip() if clean_kind == "mqtt" else "",
        "default_recipient": str(read_connection_field(row, "to_email", "") or "").strip() if clean_kind == "email" else "",
        "content_type": str(read_connection_field(row, "content_type", "") or "").strip() if clean_kind == "webhook" else "",
        "allowed_operations": ["publish"] if clean_kind == "mqtt" else ["send"],
        "recent_context": dict(recent_context or {}),
    }
    return {
        key: value
        for key, value in dossier.items()
        if value is not None and value != "" and value != [] and value != {}
    }


def build_read_target_dossier(
    connection_rows: dict[str, Any],
    connection_ref: str,
    *,
    connection_kind: str,
    recent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_ref = str(connection_ref or "").strip()
    clean_kind = str(connection_kind or "").strip().lower()
    if clean_kind not in {"rss", "google_calendar", "imap", "website"}:
        return {}
    row = dict(connection_rows or {}).get(clean_ref) if clean_ref else None
    if row is None and clean_kind != "website":
        return {}

    def string_list(value: Any) -> list[str]:
        return [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]

    row = row or {}
    dossier = {
        "kind": clean_kind,
        "connection_ref": clean_ref,
        "title": str(read_connection_field(row, "title", "") or "").strip(),
        "description": str(read_connection_field(row, "description", "") or "").strip(),
        "aliases": build_connection_aliases(clean_kind, clean_ref, row) if clean_ref else [],
        "tags": string_list(read_connection_field(row, "tags", [])),
        "group": str(read_connection_field(row, "group", "") or "").strip() if clean_kind == "website" else "",
        "calendar_id": str(read_connection_field(row, "calendar_id", "") or "").strip() if clean_kind == "google_calendar" else "",
        "mailbox": str(read_connection_field(row, "mailbox", "") or "").strip() if clean_kind == "imap" else "",
        "allowed_operations": ["read", "search"] if clean_kind == "imap" else ["read", "list"] if clean_kind == "website" else ["read"],
        "recent_context": dict(recent_context or {}),
    }
    return {
        key: value
        for key, value in dossier.items()
        if value is not None and value != "" and value != [] and value != {}
    }
