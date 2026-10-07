"""SSH read-only profile projection authority."""

from __future__ import annotations

from typing import Any, Callable


def read_ssh_connections(
    *,
    read_raw_config: Callable[[], dict[str, Any]],
    sanitize_connection_name: Callable[[str | None], str],
    read_connection_metadata: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw = read_raw_config()
    connections = raw.get("connections", {})
    if not isinstance(connections, dict):
        return {}
    ssh = connections.get("ssh", {})
    if not isinstance(ssh, dict):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for key, value in ssh.items():
        ref = sanitize_connection_name(key)
        if not ref or not isinstance(value, dict):
            continue
        rows[ref] = {
            "host": str(value.get("host", "")).strip(),
            "port": int(value.get("port", 22) or 22),
            "user": str(value.get("user", "")).strip(),
            "service_url": str(value.get("service_url", "")).strip(),
            "key_path": str(value.get("key_path", "")).strip(),
            "timeout_seconds": int(value.get("timeout_seconds", 20) or 20),
            "strict_host_key_checking": str(value.get("strict_host_key_checking", "accept-new")).strip() or "accept-new",
            "allow_commands": list(value.get("allow_commands", []) if isinstance(value.get("allow_commands", []), list) else []),
            "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
            **read_connection_metadata(value),
        }
    return rows
