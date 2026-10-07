"""Server-side pending state for native mutating tool confirmations."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any

_MAX_REQUEST_MESSAGE_CHARS = 1_500


def _sanitize_request_message(value: str) -> str:
    clean = "".join(
        character if character.isprintable() or character in "\n\t" else " "
        for character in str(value or "")
    ).strip()
    return clean[:_MAX_REQUEST_MESSAGE_CHARS]


@dataclass(frozen=True, slots=True)
class NativePendingAction:
    user_id: str
    token: str
    tool_name: str
    frozen_arguments: dict[str, Any]
    preview: str
    request_message: str
    created_at: float


class NativePendingStore:
    def __init__(self, db_path: Path, *, ttl_seconds: int = 15 * 60) -> None:
        self.db_path = Path(db_path)
        self.ttl_seconds = max(1, int(ttl_seconds or 15 * 60))
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS native_pending_actions (
                    user_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    frozen_arguments TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    request_message TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (user_id, token)
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(native_pending_actions)").fetchall()
            }
            if "request_message" not in columns:
                connection.execute(
                    "ALTER TABLE native_pending_actions ADD COLUMN request_message TEXT NOT NULL DEFAULT ''"
                )

    @staticmethod
    def _row(row: sqlite3.Row | None) -> NativePendingAction | None:
        if row is None:
            return None
        try:
            arguments = json.loads(str(row["frozen_arguments"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(arguments, dict):
            return None
        return NativePendingAction(
            user_id=str(row["user_id"]), token=str(row["token"]),
            tool_name=str(row["tool_name"]), frozen_arguments=arguments,
            preview=str(row["preview"]), request_message=str(row["request_message"]),
            created_at=float(row["created_at"]),
        )

    def put(
        self, *, user_id: str, token: str, tool_name: str,
        frozen_arguments: dict[str, Any], preview: str, request_message: str = "",
        now: float | None = None,
    ) -> NativePendingAction:
        created_at = float(time.time() if now is None else now)
        pending = NativePendingAction(
            user_id=str(user_id), token=str(token).lower(), tool_name=str(tool_name),
            frozen_arguments=json.loads(json.dumps(frozen_arguments, ensure_ascii=True)),
            preview=str(preview), request_message=_sanitize_request_message(request_message),
            created_at=created_at,
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO native_pending_actions
                (user_id, token, tool_name, frozen_arguments, preview, request_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pending.user_id, pending.token, pending.tool_name,
                 json.dumps(pending.frozen_arguments, ensure_ascii=True, sort_keys=True),
                 pending.preview, pending.request_message, pending.created_at),
            )
        return pending

    def peek(self, *, user_id: str, token: str, now: float | None = None) -> NativePendingAction | None:
        current = float(time.time() if now is None else now)
        with self._connect() as connection:
            connection.execute("DELETE FROM native_pending_actions WHERE created_at < ?", (current - self.ttl_seconds,))
            row = connection.execute(
                "SELECT * FROM native_pending_actions WHERE user_id = ? AND token = ?",
                (str(user_id), str(token).lower()),
            ).fetchone()
        return self._row(row)

    def consume(self, *, user_id: str, token: str, now: float | None = None) -> NativePendingAction | None:
        current = float(time.time() if now is None else now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM native_pending_actions WHERE created_at < ?", (current - self.ttl_seconds,))
            row = connection.execute(
                "SELECT * FROM native_pending_actions WHERE user_id = ? AND token = ?",
                (str(user_id), str(token).lower()),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "DELETE FROM native_pending_actions WHERE user_id = ? AND token = ?",
                    (str(user_id), str(token).lower()),
                )
        return self._row(row)

    def count(self, *, now: float | None = None) -> int:
        current = float(time.time() if now is None else now)
        with self._connect() as connection:
            connection.execute("DELETE FROM native_pending_actions WHERE created_at < ?", (current - self.ttl_seconds,))
            row = connection.execute("SELECT COUNT(*) AS count FROM native_pending_actions").fetchone()
        return int(row["count"] if row is not None else 0)
