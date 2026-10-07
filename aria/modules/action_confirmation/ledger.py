from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


CLAIMED = "claimed"
REPLAYED = "replayed"
UNAVAILABLE = "unavailable"
INVALID = "invalid"
DEFAULT_RETENTION_SECONDS = 7 * 24 * 60 * 60


class ActionConfirmationLedger:
    """Atomically consumes signed action confirmations before side effects."""

    def __init__(self, db_path: Path, *, retention_seconds: int = DEFAULT_RETENTION_SECONDS) -> None:
        self.db_path = Path(db_path)
        self.retention_seconds = max(3600, int(retention_seconds or DEFAULT_RETENTION_SECONDS))
        self._available = self._init_db()

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

    def _init_db(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS action_confirmation_claims (
                        user_id TEXT NOT NULL,
                        token TEXT NOT NULL,
                        action_fingerprint TEXT NOT NULL,
                        consumed_at REAL NOT NULL,
                        PRIMARY KEY (user_id, token)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS ix_action_confirmation_consumed
                    ON action_confirmation_claims(consumed_at)
                    """
                )
            return True
        except (OSError, sqlite3.Error):
            return False

    @staticmethod
    def _fingerprint(pending_action: dict[str, Any]) -> str:
        material = json.dumps(
            pending_action,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def claim(
        self,
        *,
        user_id: str,
        token: str,
        pending_action: dict[str, Any],
        now: float | None = None,
    ) -> str:
        clean_user = str(user_id or "").strip()[:128]
        clean_token = str(token or "").strip().lower()[:64]
        if not clean_user or not clean_token or not isinstance(pending_action, dict) or not pending_action:
            return INVALID
        if not self._available:
            self._available = self._init_db()
        if not self._available:
            return UNAVAILABLE
        fingerprint = self._fingerprint(pending_action)
        consumed_at = float(time.time() if now is None else now)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM action_confirmation_claims WHERE consumed_at < ?",
                    (consumed_at - self.retention_seconds,),
                )
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO action_confirmation_claims(
                        user_id, token, action_fingerprint, consumed_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (clean_user, clean_token, fingerprint, consumed_at),
                )
                if int(cursor.rowcount or 0) == 1:
                    return CLAIMED
                return REPLAYED
        except (OSError, sqlite3.Error, TypeError, ValueError):
            return UNAVAILABLE
