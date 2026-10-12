"""Worker-shared SQLite authority for compact user activity entries."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Mapping, Sequence


_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_.:@/-]+")
_ENTRY_LIMIT_PER_USER = 10_000


def _bounded(value: object, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 1)] + "…"


def _bounded_at_boundary(value: object, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    if len(clean) <= limit:
        return clean
    candidate = clean[: max(0, limit - 1)].rstrip()
    if " " in candidate:
        candidate = candidate.rsplit(" ", 1)[0].rstrip(" -–—,;:")
    return candidate + "…"


def _identifier(value: object, limit: int = 160) -> str:
    return _IDENTIFIER_RE.sub("_", str(value or "").strip())[:limit].strip("_")


def _json_dict(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _json_list(value: object) -> list[Any]:
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return list(parsed) if isinstance(parsed, list) else []


class ActivityJournalStore:
    """Bounded journal whose every read and mutation requires the owning user."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        needs_insert = False
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_journal (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL NOT NULL,
                    kind TEXT NOT NULL,
                    job_id TEXT NOT NULL DEFAULT '',
                    goal TEXT NOT NULL DEFAULT '',
                    tools TEXT NOT NULL DEFAULT '{}',
                    connection_kinds TEXT NOT NULL DEFAULT '[]',
                    connection_refs TEXT NOT NULL DEFAULT '[]',
                    mcp_servers TEXT NOT NULL DEFAULT '[]',
                    outcome_status TEXT NOT NULL,
                    confirmations TEXT NOT NULL DEFAULT '{}',
                    corrected INTEGER NOT NULL DEFAULT 0,
                    outcome_phrase TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'live',
                    keep INTEGER NOT NULL DEFAULT 0,
                    legacy_collection TEXT NOT NULL DEFAULT '',
                    legacy_point_id TEXT NOT NULL DEFAULT '',
                    legacy_sources TEXT NOT NULL DEFAULT '[]',
                    period_start TEXT NOT NULL DEFAULT '',
                    period_end TEXT NOT NULL DEFAULT '',
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    embedding_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL,
                    created_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_journal_user_finished "
                "ON activity_journal(user_id, finished_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_journal_user_source "
                "ON activity_journal(user_id, source)"
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(activity_journal)").fetchall()
            }
            if "legacy_sources" not in columns:
                connection.execute(
                    "ALTER TABLE activity_journal ADD COLUMN legacy_sources TEXT NOT NULL DEFAULT '[]'"
                )
            for name, definition in (
                ("input_tokens", "INTEGER NOT NULL DEFAULT 0"),
                ("output_tokens", "INTEGER NOT NULL DEFAULT 0"),
                ("embedding_tokens", "INTEGER NOT NULL DEFAULT 0"),
                ("cost_usd", "REAL"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE activity_journal ADD COLUMN {name} {definition}")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _normalized_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
        source = str(entry.get("source") or "live").strip().lower()
        if source not in {"live", "legacy_context_rollup"}:
            source = "live"
        phrase_limit = 1000 if source == "legacy_context_rollup" else 300
        tools_raw = entry.get("tools")
        tools = {
            _identifier(name, 160): max(1, int(count or 1))
            for name, count in dict(tools_raw or {}).items()
            if _identifier(name, 160)
        }
        confirmations_raw = dict(entry.get("confirmations") or {})
        confirmations = {
            key: max(0, int(confirmations_raw.get(key, 0) or 0))
            for key in ("asked", "approved", "rejected")
        }
        now = time.time()
        return {
            "id": _identifier(entry.get("id"), 160),
            "user_id": _bounded(entry.get("user_id"), 180),
            "started_at": float(entry.get("started_at") or now),
            "finished_at": float(entry.get("finished_at") or now),
            "kind": str(entry.get("kind") or "turn").strip().lower()
            if str(entry.get("kind") or "turn").strip().lower() in {"turn", "job", "legacy"}
            else "turn",
            "job_id": _identifier(entry.get("job_id"), 160),
            "goal": _bounded(entry.get("goal"), 300),
            "tools": tools,
            "connection_kinds": sorted({_identifier(value, 80) for value in entry.get("connection_kinds", ()) if _identifier(value, 80)}),
            "connection_refs": sorted({_identifier(value, 160) for value in entry.get("connection_refs", ()) if _identifier(value, 160)}),
            "mcp_servers": sorted({_identifier(value, 100) for value in entry.get("mcp_servers", ()) if _identifier(value, 100)}),
            "outcome_status": str(entry.get("outcome_status") or "error").strip().lower()
            if str(entry.get("outcome_status") or "error").strip().lower() in {
                "ok", "error", "cancelled", "needs_confirmation", "interrupted",
            } else "error",
            "confirmations": confirmations,
            "corrected": bool(entry.get("corrected")),
            "outcome_phrase": (
                _bounded_at_boundary(entry.get("outcome_phrase"), phrase_limit)
                if source == "legacy_context_rollup"
                else _bounded(entry.get("outcome_phrase"), phrase_limit)
            ),
            "source": source,
            "keep": bool(entry.get("keep")) or source == "legacy_context_rollup",
            "legacy_collection": _identifier(entry.get("legacy_collection"), 240),
            "legacy_point_id": _identifier(entry.get("legacy_point_id"), 240),
            "legacy_sources": sorted({
                f"{_identifier(source_row.get('collection'), 240)}:{_identifier(source_row.get('point_id'), 240)}"
                for source_row in entry.get("legacy_sources", ())
                if isinstance(source_row, Mapping)
                and _identifier(source_row.get("collection"), 240)
                and _identifier(source_row.get("point_id"), 240)
            }),
            "period_start": _bounded(entry.get("period_start"), 40),
            "period_end": _bounded(entry.get("period_end"), 40),
            "input_tokens": max(0, int(entry.get("input_tokens", 0) or 0)),
            "output_tokens": max(0, int(entry.get("output_tokens", 0) or 0)),
            "embedding_tokens": max(0, int(entry.get("embedding_tokens", 0) or 0)),
            "cost_usd": max(0.0, float(entry["cost_usd"])) if entry.get("cost_usd") is not None else None,
            "created_at": float(entry.get("created_at") or now),
        }

    def write(self, entry: Mapping[str, Any]) -> bool:
        row = self._normalized_entry(entry)
        if not row["id"] or not row["user_id"]:
            raise ValueError("activity_journal_identity_required")
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO activity_journal(
                    id,user_id,started_at,finished_at,kind,job_id,goal,tools,
                    connection_kinds,connection_refs,mcp_servers,outcome_status,
                    confirmations,corrected,outcome_phrase,source,keep,
                    legacy_collection,legacy_point_id,legacy_sources,period_start,period_end,
                    input_tokens,output_tokens,embedding_tokens,cost_usd,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"], row["user_id"], row["started_at"], row["finished_at"],
                    row["kind"], row["job_id"], row["goal"],
                    json.dumps(row["tools"], ensure_ascii=True, separators=(",", ":")),
                    json.dumps(row["connection_kinds"], ensure_ascii=True, separators=(",", ":")),
                    json.dumps(row["connection_refs"], ensure_ascii=True, separators=(",", ":")),
                    json.dumps(row["mcp_servers"], ensure_ascii=True, separators=(",", ":")),
                    row["outcome_status"],
                    json.dumps(row["confirmations"], ensure_ascii=True, separators=(",", ":")),
                    int(row["corrected"]), row["outcome_phrase"], row["source"],
                    int(row["keep"]), row["legacy_collection"], row["legacy_point_id"],
                    json.dumps(row["legacy_sources"], ensure_ascii=True, separators=(",", ":")),
                    row["period_start"], row["period_end"], row["input_tokens"],
                    row["output_tokens"], row["embedding_tokens"], row["cost_usd"], row["created_at"],
                ),
            )
            inserted = int(cursor.rowcount or 0) == 1
            if inserted:
                excess = connection.execute(
                    "SELECT id FROM activity_journal WHERE user_id=? AND keep=0 "
                    "ORDER BY finished_at DESC LIMIT -1 OFFSET ?",
                    (row["user_id"], _ENTRY_LIMIT_PER_USER),
                ).fetchall()
                if excess:
                    connection.executemany(
                        "DELETE FROM activity_journal WHERE id=? AND user_id=? AND keep=0",
                        [(str(item["id"]), row["user_id"]) for item in excess],
                    )
        return inserted

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]), "user_id": str(row["user_id"]),
            "started_at": float(row["started_at"]), "finished_at": float(row["finished_at"]),
            "kind": str(row["kind"]), "job_id": str(row["job_id"]),
            "goal": str(row["goal"]), "tools": {str(k): max(1, int(v or 1)) for k, v in _json_dict(row["tools"]).items()},
            "connection_kinds": [str(value) for value in _json_list(row["connection_kinds"])],
            "connection_refs": [str(value) for value in _json_list(row["connection_refs"])],
            "mcp_servers": [str(value) for value in _json_list(row["mcp_servers"])],
            "outcome_status": str(row["outcome_status"]),
            "confirmations": {key: max(0, int(_json_dict(row["confirmations"]).get(key, 0) or 0)) for key in ("asked", "approved", "rejected")},
            "corrected": bool(int(row["corrected"] or 0)),
            "outcome_phrase": str(row["outcome_phrase"]), "source": str(row["source"]),
            "keep": bool(int(row["keep"] or 0)),
            "legacy_collection": str(row["legacy_collection"]),
            "legacy_point_id": str(row["legacy_point_id"]),
            "legacy_sources": [
                {"collection": value.split(":", 1)[0], "point_id": value.split(":", 1)[1]}
                for value in _json_list(row["legacy_sources"])
                if isinstance(value, str) and ":" in value
            ],
            "period_start": str(row["period_start"]), "period_end": str(row["period_end"]),
            "input_tokens": max(0, int(row["input_tokens"] or 0)),
            "output_tokens": max(0, int(row["output_tokens"] or 0)),
            "embedding_tokens": max(0, int(row["embedding_tokens"] or 0)),
            "cost_usd": float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        }

    def get(self, user_id: str, entry_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM activity_journal WHERE id=? AND user_id=?",
                (str(entry_id), str(user_id)),
            ).fetchone()
        return self._record(row) if row is not None else None

    def upsert_legacy(self, entry: Mapping[str, Any], *, entry_id: str = "") -> str:
        """Insert or update one derived legacy row while preserving its established identity."""

        source = dict(entry)
        if entry_id:
            source["id"] = str(entry_id)
        row = self._normalized_entry(source)
        if row["source"] != "legacy_context_rollup" or not row["id"] or not row["user_id"]:
            raise ValueError("activity_journal_legacy_identity_required")
        encoded = {
            "tools": json.dumps(row["tools"], ensure_ascii=True, separators=(",", ":")),
            "connection_kinds": json.dumps(row["connection_kinds"], ensure_ascii=True, separators=(",", ":")),
            "connection_refs": json.dumps(row["connection_refs"], ensure_ascii=True, separators=(",", ":")),
            "mcp_servers": json.dumps(row["mcp_servers"], ensure_ascii=True, separators=(",", ":")),
            "confirmations": json.dumps(row["confirmations"], ensure_ascii=True, separators=(",", ":")),
            "legacy_sources": json.dumps(row["legacy_sources"], ensure_ascii=True, separators=(",", ":")),
        }
        needs_insert = False
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM activity_journal WHERE id=? AND user_id=?",
                (row["id"], row["user_id"]),
            ).fetchone()
            if existing is None:
                needs_insert = True
            else:
                current = self._record(existing)
                comparable = {
                    key: row[key]
                    for key in (
                        "started_at", "finished_at", "kind", "job_id", "goal", "tools",
                        "connection_kinds", "connection_refs", "mcp_servers", "outcome_status",
                        "confirmations", "corrected", "outcome_phrase", "source", "keep",
                        "legacy_collection", "legacy_point_id", "legacy_sources", "period_start", "period_end",
                    )
                }
                comparable["legacy_sources"] = [
                    {"collection": value.split(":", 1)[0], "point_id": value.split(":", 1)[1]}
                    for value in row["legacy_sources"] if ":" in value
                ]
                if all(current.get(key) == value for key, value in comparable.items()):
                    return "unchanged"
                connection.execute(
                    "UPDATE activity_journal SET started_at=?,finished_at=?,kind=?,job_id=?,goal=?,tools=?,"
                    "connection_kinds=?,connection_refs=?,mcp_servers=?,outcome_status=?,confirmations=?,"
                    "corrected=?,outcome_phrase=?,source=?,keep=1,legacy_collection=?,legacy_point_id=?,"
                    "legacy_sources=?,period_start=?,period_end=? WHERE id=? AND user_id=?",
                    (
                        row["started_at"], row["finished_at"], row["kind"], row["job_id"], row["goal"],
                        encoded["tools"], encoded["connection_kinds"], encoded["connection_refs"],
                        encoded["mcp_servers"], row["outcome_status"], encoded["confirmations"],
                        int(row["corrected"]), row["outcome_phrase"], row["source"],
                        row["legacy_collection"], row["legacy_point_id"], encoded["legacy_sources"],
                        row["period_start"], row["period_end"], row["id"], row["user_id"],
                    ),
                )
        if needs_insert:
            inserted = self.write(source)
            return "created" if inserted else "unchanged"
        return "updated"

    def delete_legacy_entries(self, user_id: str, entry_ids: Sequence[str]) -> int:
        ids = [str(value) for value in entry_ids if str(value)]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM activity_journal WHERE user_id=? AND source='legacy_context_rollup' "
                f"AND id IN ({placeholders})",
                (str(user_id), *ids),
            )
        return max(0, int(cursor.rowcount or 0))

    def query(
        self, user_id: str, *, query: str = "", since: float | None = None,
        until: float | None = None, tool: str = "", connection: str = "",
        server: str = "", outcome: str = "", source: str = "", limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses = ["user_id=?"]
        values: list[Any] = [str(user_id)]
        if since is not None:
            clauses.append("finished_at>=?")
            values.append(float(since))
        if until is not None:
            clauses.append("finished_at<=?")
            values.append(float(until))
        if outcome:
            clauses.append("outcome_status=?")
            values.append(str(outcome).strip().lower())
        if source:
            clauses.append("source=?")
            values.append(str(source).strip().lower())
        with self._lock, self._connect() as connection_db:
            rows = connection_db.execute(
                "SELECT * FROM activity_journal WHERE " + " AND ".join(clauses)
                + " ORDER BY finished_at DESC LIMIT ?",
                (*values, min(_ENTRY_LIMIT_PER_USER, max(1, int(limit or 20)) * 5)),
            ).fetchall()
        needle = " ".join(str(query or "").casefold().split())
        tool_needle = str(tool or "").casefold().strip()
        connection_needle = str(connection or "").casefold().strip()
        server_needle = str(server or "").casefold().strip()
        result: list[dict[str, Any]] = []
        for raw in rows:
            row = self._record(raw)
            searchable = " ".join((
                row["goal"], row["outcome_phrase"], " ".join(row["tools"]),
                " ".join(row["connection_kinds"]), " ".join(row["connection_refs"]),
                " ".join(row["mcp_servers"]), row["source"],
            )).casefold()
            if needle and needle not in searchable:
                continue
            if tool_needle and not any(tool_needle in name.casefold() for name in row["tools"]):
                continue
            if connection_needle and not any(connection_needle in value.casefold() for value in (*row["connection_kinds"], *row["connection_refs"])):
                continue
            if server_needle and not any(server_needle in value.casefold() for value in row["mcp_servers"]):
                continue
            result.append(row)
            if len(result) >= min(_ENTRY_LIMIT_PER_USER, max(1, int(limit or 20))):
                break
        return result

    def update_keep(self, user_id: str, entry_id: str, keep: bool) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE activity_journal SET keep=? WHERE id=? AND user_id=?",
                (int(bool(keep)), str(entry_id), str(user_id)),
            )
        return int(cursor.rowcount or 0) == 1

    def delete(self, user_id: str, entry_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM activity_journal WHERE id=? AND user_id=?",
                (str(entry_id), str(user_id)),
            )
        return int(cursor.rowcount or 0) == 1

    def delete_range(self, user_id: str, *, since: float, until: float) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM activity_journal WHERE user_id=? AND finished_at>=? AND finished_at<=?",
                (str(user_id), float(since), float(until)),
            )
        return max(0, int(cursor.rowcount or 0))

    def sweep(self, *, retention_days: int, now: float | None = None) -> int:
        days = min(365, max(7, int(retention_days or 90)))
        cutoff = float(time.time() if now is None else now) - days * 86400
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM activity_journal WHERE finished_at<? AND keep=0 AND source='live'",
                (cutoff,),
            )
        return max(0, int(cursor.rowcount or 0))

    def count(self, user_id: str) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM activity_journal WHERE user_id=?", (str(user_id),),
            ).fetchone()
        return int(row["count"] or 0) if row is not None else 0
