"""SFTP read-only profile projection authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def read_sftp_connections(
    *,
    base_dir: Path,
    read_raw_config: Callable[[], dict[str, Any]],
    get_secure_store: Callable[[dict[str, Any] | None], Any],
    sanitize_connection_name: Callable[[str | None], str],
    read_connection_metadata: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw = read_raw_config()
    connections = raw.get("connections", {})
    if not isinstance(connections, dict):
        return {}
    sftp = connections.get("sftp", {})
    if not isinstance(sftp, dict):
        return {}
    store = get_secure_store(raw)
    rows: dict[str, dict[str, Any]] = {}
    for key, value in sftp.items():
        ref = sanitize_connection_name(key)
        if not ref or not isinstance(value, dict):
            continue
        password = store.get_secret(f"connections.sftp.{ref}.password", default="") if store else ""
        key_path = str(value.get("key_path", "")).strip()
        key_exists = False
        if key_path:
            candidate = Path(key_path)
            if not candidate.is_absolute():
                candidate = (base_dir / candidate).resolve()
            key_exists = candidate.exists()
        rows[ref] = {
            "host": str(value.get("host", "")).strip(),
            "port": int(value.get("port", 22) or 22),
            "user": str(value.get("user", "")).strip(),
            "service_url": str(value.get("service_url", "")).strip(),
            "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
            "root_path": str(value.get("root_path", "")).strip(),
            "key_path": key_path,
            "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
            "key_present": key_exists,
            "password": password,
            "password_present": bool(password),
            **read_connection_metadata(value),
        }
    return rows
