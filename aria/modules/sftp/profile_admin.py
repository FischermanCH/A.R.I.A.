"""SFTP connection profile persistence authority."""

from __future__ import annotations

from typing import Any, Callable

CONNECTION_ADMIN_SPEC: dict[str, Any] = {
    "health_prefix": "sftp",
    "secret_keys": ["connections.sftp.{ref}.password"],
    "success_message_key": "connection_admin.success.sftp_deleted",
}

CONNECTION_CREATE_SPEC: dict[str, Any] = {
    "section": "sftp",
    "required": ["host", "user"],
    "success_message_key": "connection_admin.success.sftp_created",
}

CONNECTION_UPDATE_SPEC: dict[str, Any] = {
    "section": "sftp",
    "success_message_key": "connection_admin.success.sftp_updated",
}


def build_sftp_connection_profile(
    row_value: dict[str, Any],
    *,
    ref: str,
    store: Any,
    admin_error: Callable[..., Exception],
) -> dict[str, Any]:
    password = str(row_value.get("password", "")).strip()
    if password:
        if not store:
            raise admin_error("security_store_required")
        store.set_secret(f"connections.sftp.{ref}.password", password)
    return {
        "host": str(row_value.get("host", "")).strip(),
        "port": int(row_value.get("port", 22) or 22),
        "user": str(row_value.get("user", "")).strip(),
        "service_url": str(row_value.get("service_url", "")).strip(),
        "key_path": str(row_value.get("key_path", "")).strip(),
        "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
        "root_path": str(row_value.get("root_path", "")).strip(),
        "title": str(row_value.get("title", "")).strip(),
        "description": str(row_value.get("description", "")).strip(),
        "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
        "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
    }


def update_sftp_connection_profile(
    current: dict[str, Any],
    update_payload: dict[str, Any],
    *,
    ref: str,
    store: Any,
    admin_error: Callable[..., Exception],
) -> dict[str, Any]:
    row_value = dict(current)
    for field in ("host", "user", "key_path", "root_path"):
        value = str(update_payload.get(field, "")).strip()
        if value:
            row_value[field] = value
    if "port" in update_payload:
        row_value["port"] = int(update_payload.get("port", 22) or 22)
    if "timeout_seconds" in update_payload:
        row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
    password = str(update_payload.get("password", "")).strip()
    if password:
        if not store:
            raise admin_error("security_store_required")
        store.set_secret(f"connections.sftp.{ref}.password", password)
    return row_value
