"""Read-only connection inventory projection from the authoritative configured profiles."""

from __future__ import annotations

from typing import Any

from aria.modules.connections_catalog.catalog import normalize_connection_kind, ordered_connection_kinds
from aria.modules.connections_runtime_status.runtime import build_settings_connection_status_rows

CONNECTION_PROFILE_SOURCE_AUTHORITY = "connections:profile_store"


async def load_connection_inventory(
    settings: Any, *, user_id: str, connection_kind: str = "",
) -> tuple[dict[str, str], ...]:
    scope_user_id = str(user_id or "").strip()
    if not scope_user_id:
        raise ValueError("connection_inventory_user_scope_missing")
    clean_kind = normalize_connection_kind(connection_kind) if str(connection_kind or "").strip() else ""
    if clean_kind and clean_kind not in set(ordered_connection_kinds()):
        raise ValueError("connection_inventory_kind_unknown")
    rows = build_settings_connection_status_rows(settings, page_probe=False, cached_only=True)
    result: list[dict[str, str]] = []
    for row in rows:
        kind = normalize_connection_kind(str(row.get("kind_key") or ""))
        ref = str(row.get("ref") or "").strip()
        if not kind or not ref or (clean_kind and kind != clean_kind):
            continue
        result.append({
            "kind": kind,
            "ref": ref,
            "display_name": str(row.get("display_name") or ref).strip() or ref,
            "target": str(row.get("target") or "").strip(),
            "source_authority": CONNECTION_PROFILE_SOURCE_AUTHORITY,
            "scope_user_id": scope_user_id,
        })
    return tuple(result)
