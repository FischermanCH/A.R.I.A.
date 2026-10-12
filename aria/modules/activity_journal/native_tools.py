"""Native read surface for the user-owned activity journal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Mapping

from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult
from aria.modules.platform_primitives.display_time import (
    display_datetime,
    display_zone,
    local_date_bound,
    resolve_display_timezone,
)


def _date_bound(value: object, timezone_name: str, *, end: bool = False) -> float | None:
    clean = str(value or "").strip().casefold()
    if not clean:
        return None
    zone = display_zone(timezone_name)
    now = datetime.now(timezone.utc).astimezone(zone)
    relative = {
        "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "last_week": now - timedelta(days=7),
        "last_month": now - timedelta(days=30),
        "gestern": now - timedelta(days=1),
        "letzte_woche": now - timedelta(days=7),
        "letzten_monat": now - timedelta(days=30),
    }
    if clean in relative:
        return relative[clean].timestamp()
    try:
        return local_date_bound(clean, timezone_name, end=end)
    except ValueError:
        return None


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def read(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        store = getattr(runtime_owner, "_activity_journal_store", None)
        if store is None:
            return NativeToolResult(
                json.dumps({"status": "activity_journal_unavailable", "entries": []}, sort_keys=True),
                "activity_journal_read",
            )
        limit = min(50, max(1, int(arguments.get("limit", 20) or 20)))
        remembered_timezones = getattr(runtime_owner, "_display_timezones_by_user", {})
        remembered_timezone = (
            remembered_timezones.get(context.user_id, "")
            if isinstance(remembered_timezones, dict) else ""
        )
        timezone_name = (
            str(remembered_timezone)
            or resolve_display_timezone(getattr(runtime_owner, "settings", None))
        )
        rows = store.query(
            context.user_id,
            query=str(arguments.get("query") or ""),
            since=_date_bound(arguments.get("since"), timezone_name),
            until=_date_bound(arguments.get("until"), timezone_name, end=True),
            tool=str(arguments.get("tool") or ""),
            connection=str(arguments.get("connection") or ""),
            server=str(arguments.get("server") or ""),
            limit=limit,
        )
        compact = [{
            "user_id": row["user_id"],
            "date": display_datetime(row["finished_at"], timezone_name).isoformat(timespec="seconds"),
            "kind": row["kind"], "job_id": row["job_id"], "goal": row["goal"],
            "tools": row["tools"], "connections": row["connection_refs"],
            "mcp_servers": row["mcp_servers"], "outcome": row["outcome_status"],
            "outcome_phrase": row["outcome_phrase"], "source": row["source"],
        } for row in rows]
        payload = {"status": "ok", "entries": compact}
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        while len(encoded) > 4000 and compact:
            compact.pop()
            encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        return NativeToolResult(
            encoded,
            "activity_journal_read",
            detail_lines=(f"Routing Debug: activity_journal read entries={len(compact)}",),
        )

    return (NativeToolBinding(
        contract=NativeToolContract(
            owner_module_id="activity_journal", name="activity_journal_read",
            description=(
                "Read the current user's compact activity journal to answer what ARIA did, when it happened, "
                "which tools or connections were used, and how it ended. The journal is not automatic context."
            ),
            effect="read_only", confirmation_required=False, user_scoped=True,
            source_authority="activity_journal.sqlite3:user_id",
            rollout_flag="activity_journal_enabled", order=125,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 300},
                    "since": {"type": "string", "maxLength": 40},
                    "until": {"type": "string", "maxLength": 40},
                    "tool": {"type": "string", "maxLength": 160},
                    "connection": {"type": "string", "maxLength": 160},
                    "server": {"type": "string", "maxLength": 100},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                },
                "additionalProperties": False,
            },
        ),
        handler=read,
    ),)
