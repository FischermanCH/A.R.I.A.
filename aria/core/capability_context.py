from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CapabilityContextStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

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
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_payload(self, payload: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
