from __future__ import annotations

import base64
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decode_master_key(raw: str) -> bytes:
    value = (raw or "").strip()
    if not value:
        raise ValueError("ARIA_MASTER_KEY fehlt.")
    # Support urlsafe base64 (recommended), std base64 and hex as fallback.
    try:
        data = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception:
        data = b""
    if len(data) == 32:
        return data
    try:
        data = base64.b64decode(value + "=" * (-len(value) % 4))
    except Exception:
        data = b""
    if len(data) == 32:
        return data
    try:
        data = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("ARIA_MASTER_KEY ist ungültig (erwarte base64/hex).") from exc
    if len(data) != 32:
        raise ValueError("ARIA_MASTER_KEY muss 32 Byte (AES-256) sein.")
    return data


def generate_master_key_b64() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")


@dataclass
class SecureStoreConfig:
    db_path: Path
    enabled: bool = True


class SecureConfigStore:
    def __init__(self, config: SecureStoreConfig, master_key: bytes):
        self.config = config
        self._aesgcm = AESGCM(master_key)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.config.db_path)
        conn.row_factory = sqlite3.Row
        try:
            os.chmod(self.config.db_path, 0o600)
        except OSError:
            pass
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_secret (
                    key TEXT PRIMARY KEY,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def set_secret(self, key: str, value: str) -> None:
        clean_key = str(key).strip()
        if not clean_key:
            raise ValueError("Secret-Key darf nicht leer sein.")
        clear = str(value)
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, clear.encode("utf-8"), clean_key.encode("utf-8"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings_secret(key, nonce, ciphertext, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    nonce=excluded.nonce,
                    ciphertext=excluded.ciphertext,
                    updated_at=datetime('now')
                """,
                (clean_key, nonce, ciphertext),
            )
            conn.commit()

    def get_secret(self, key: str, default: str = "") -> str:
        clean_key = str(key).strip()
        if not clean_key:
            return default
        with self._connect() as conn:
            row = conn.execute(
                "SELECT nonce, ciphertext FROM settings_secret WHERE key = ?",
                (clean_key,),
            ).fetchone()
        if not row:
            return default
        nonce = bytes(row["nonce"])
        ciphertext = bytes(row["ciphertext"])
        try:
            clear = self._aesgcm.decrypt(nonce, ciphertext, clean_key.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Secret konnte nicht entschluesselt werden: {clean_key}") from exc
        return clear.decode("utf-8")

    def delete_secret(self, key: str) -> None:
        clean_key = str(key).strip()
        if not clean_key:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM settings_secret WHERE key = ?", (clean_key,))
            conn.commit()

    def list_secret_keys(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key FROM settings_secret ORDER BY key ASC").fetchall()
        return [str(row["key"]) for row in rows]

    def upsert_user(self, username: str, password_hash: str, role: str = "user") -> None:
        user = str(username).strip()
        if not user:
            raise ValueError("Username darf nicht leer sein.")
        if not password_hash:
            raise ValueError("Password-Hash fehlt.")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users(username, password_hash, role, active, created_at, updated_at)
                VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))
                ON CONFLICT(username) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    role=excluded.role,
                    active=1,
                    updated_at=datetime('now')
                """,
                (user, password_hash, role),
            )
            conn.commit()

    def get_user(self, username: str) -> dict[str, Any] | None:
        user = str(username).strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT username, password_hash, role, active FROM users WHERE username = ?",
                (user,),
            ).fetchone()
        if not row:
            return None
        return {
            "username": str(row["username"]),
            "password_hash": str(row["password_hash"]),
            "role": str(row["role"]),
            "active": bool(int(row["active"])),
        }

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT username, role, active FROM users ORDER BY username ASC").fetchall()
        return [
            {"username": str(row["username"]), "role": str(row["role"]), "active": bool(int(row["active"]))}
            for row in rows
        ]

    def set_user_role(self, username: str, role: str) -> None:
        user = str(username).strip()
        clean_role = str(role).strip().lower()
        if clean_role not in {"admin", "user"}:
            clean_role = "user"
        if not user:
            raise ValueError("Username darf nicht leer sein.")
        with self._connect() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = ?", (user,)).fetchone()
            if not row:
                raise ValueError("User nicht gefunden.")
            conn.execute(
                "UPDATE users SET role = ?, updated_at = datetime('now') WHERE username = ?",
                (clean_role, user),
            )
            conn.commit()

    def set_user_active(self, username: str, active: bool) -> None:
        user = str(username).strip()
        if not user:
            raise ValueError("Username darf nicht leer sein.")
        with self._connect() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = ?", (user,)).fetchone()
            if not row:
                raise ValueError("User nicht gefunden.")
            conn.execute(
                "UPDATE users SET active = ?, updated_at = datetime('now') WHERE username = ?",
                (1 if bool(active) else 0, user),
            )
            conn.commit()

    def rename_user(self, old_username: str, new_username: str) -> None:
        old_user = str(old_username).strip()
        new_user = str(new_username).strip()
        if not old_user or not new_user:
            raise ValueError("Username darf nicht leer sein.")
        with self._connect() as conn:
            old_row = conn.execute("SELECT username FROM users WHERE username = ?", (old_user,)).fetchone()
            if not old_row:
                raise ValueError("User nicht gefunden.")
            if old_user == new_user:
                return
            existing = conn.execute("SELECT username FROM users WHERE username = ?", (new_user,)).fetchone()
            if existing:
                raise ValueError("Ziel-Username existiert bereits.")
            conn.execute(
                "UPDATE users SET username = ?, updated_at = datetime('now') WHERE username = ?",
                (new_user, old_user),
            )
            conn.commit()
