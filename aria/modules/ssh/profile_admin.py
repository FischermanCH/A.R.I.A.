"""SSH connection profile persistence authority."""

from __future__ import annotations

from typing import Any

CONNECTION_ADMIN_SPEC: dict[str, Any] = {
    "health_prefix": "ssh",
    "secret_keys": [],
    "success_message_key": "connection_admin.success.ssh_deleted",
}

CONNECTION_CREATE_SPEC: dict[str, Any] = {
    "section": "ssh",
    "required": ["host", "user"],
    "success_message_key": "connection_admin.success.ssh_created",
}

CONNECTION_UPDATE_SPEC: dict[str, Any] = {
    "section": "ssh",
    "success_message_key": "connection_admin.success.ssh_updated",
}


def build_ssh_connection_profile(
    row_value: dict[str, Any],
    *,
    ref: str,
    store: Any,
    admin_error: Any = None,
) -> dict[str, Any]:
    del ref, store, admin_error
    return {
        "host": str(row_value.get("host", "")).strip(),
        "port": int(row_value.get("port", 22) or 22),
        "user": str(row_value.get("user", "")).strip(),
        "service_url": str(row_value.get("service_url", "")).strip(),
        "key_path": str(row_value.get("key_path", "")).strip(),
        "timeout_seconds": int(row_value.get("timeout_seconds", 20) or 20),
        "strict_host_key_checking": str(row_value.get("strict_host_key_checking", "accept-new")).strip() or "accept-new",
        "allow_commands": list(row_value.get("allow_commands", []) if isinstance(row_value.get("allow_commands", []), list) else []),
        "title": str(row_value.get("title", "")).strip(),
        "description": str(row_value.get("description", "")).strip(),
        "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
        "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
    }


def update_ssh_connection_profile(
    current: dict[str, Any],
    update_payload: dict[str, Any],
    *,
    ref: str,
    store: Any,
    admin_error: Any = None,
) -> dict[str, Any]:
    del ref, store, admin_error
    row_value = dict(current)
    for field in ("host", "user", "service_url", "key_path", "strict_host_key_checking"):
        value = update_payload.get(field, "")
        if field == "strict_host_key_checking":
            clean_value = str(value).strip()
            if clean_value:
                row_value[field] = clean_value
            continue
        clean_value = str(value).strip()
        if clean_value:
            row_value[field] = clean_value
    if "port" in update_payload:
        row_value["port"] = int(update_payload.get("port", 22) or 22)
    if "timeout_seconds" in update_payload:
        row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 20) or 20)
    if "allow_commands" in update_payload and isinstance(update_payload.get("allow_commands"), list):
        row_value["allow_commands"] = list(update_payload.get("allow_commands"))
    return row_value
