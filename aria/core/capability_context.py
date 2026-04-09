from __future__ import annotations

import copy
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CapabilityContextStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_lock = threading.RLock()
        self._payload_cache: dict[str, Any] = {
            "mtime_ns": -1,
            "size": -1,
            "payload": {},
        }

    @staticmethod
    def _safe_user_id(user_id: str) -> str:
        raw = str(user_id or "").strip()
        if not raw:
            return "anonymous"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)

    def load_recent(self, user_id: str) -> dict[str, Any]:
        payload = self._load_payload()
        row = payload.get(self._safe_user_id(user_id), {})
        return row if isinstance(row, dict) else {}

    def remember_action(
        self,
        user_id: str,
        *,
        capability: str,
        connection_kind: str,
        connection_ref: str,
        path: str = "",
    ) -> None:
        payload = self._load_payload()
        payload[self._safe_user_id(user_id)] = {
            "capability": str(capability or "").strip(),
            "connection_kind": str(connection_kind or "").strip(),
            "connection_ref": str(connection_ref or "").strip(),
            "path": str(path or "").strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_payload(payload)

    def clear_user(self, user_id: str) -> None:
        payload = self._load_payload()
        payload.pop(self._safe_user_id(user_id), None)
        self._write_payload(payload)

    def _load_payload(self) -> dict[str, Any]:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            with self._cache_lock:
                self._payload_cache = {
                    "mtime_ns": -1,
                    "size": -1,
                    "payload": {},
                }
            return {}
        except OSError:
            return {}
        with self._cache_lock:
            if (
                int(self._payload_cache.get("mtime_ns", -1)) == int(stat.st_mtime_ns)
                and int(self._payload_cache.get("size", -1)) == int(stat.st_size)
            ):
                payload = self._payload_cache.get("payload", {})
                return copy.deepcopy(payload if isinstance(payload, dict) else {})
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        payload = raw if isinstance(raw, dict) else {}
        with self._cache_lock:
            self._payload_cache = {
                "mtime_ns": int(stat.st_mtime_ns),
                "size": int(stat.st_size),
                "payload": copy.deepcopy(payload),
            }
        return copy.deepcopy(payload)

    def _write_payload(self, payload: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
        try:
            stat = self.path.stat()
        except OSError:
            return
        with self._cache_lock:
            self._payload_cache = {
                "mtime_ns": int(stat.st_mtime_ns),
                "size": int(stat.st_size),
                "payload": copy.deepcopy(payload),
            }
