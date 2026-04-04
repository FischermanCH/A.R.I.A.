from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FileChatHistoryStore:
    def __init__(self, base_dir: Path, max_messages: int = 80) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages = max(2, int(max_messages))

    @staticmethod
    def _safe_user_id(user_id: str) -> str:
        raw = str(user_id or "").strip()
        if not raw:
            return "anonymous"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)

    def _history_file(self, user_id: str) -> Path:
        return self.base_dir / f"{self._safe_user_id(user_id)}.json"

    def load_history(self, user_id: str) -> list[dict[str, Any]]:
        path = self._history_file(user_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            text = str(item.get("text", "")).strip()
            if role not in {"user", "assistant"} or not text:
                continue
            rows.append(
                {
                    "role": role,
                    "text": text,
                    "badge_icon": str(item.get("badge_icon", "")).strip(),
                    "badge_intent": str(item.get("badge_intent", "")).strip(),
                    "badge_tokens": int(item.get("badge_tokens", 0) or 0),
                    "badge_cost_usd": str(item.get("badge_cost_usd", "n/a")).strip() or "n/a",
                    "badge_duration": str(item.get("badge_duration", "0.0")).strip() or "0.0",
                    "badge_details": [str(row).strip() for row in (item.get("badge_details") or []) if str(row).strip()],
                    "timestamp": str(item.get("timestamp", "")).strip(),
                }
            )
        return rows[-self.max_messages :]

    def append_exchange(
        self,
        user_id: str,
        *,
        user_message: str,
        assistant_message: str,
        badge_icon: str,
        badge_intent: str,
        badge_tokens: int,
        badge_cost_usd: str,
        badge_duration: str,
        badge_details: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        history = self.load_history(user_id)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        history.extend(
            [
                {
                    "role": "user",
                    "text": str(user_message or "").strip(),
                    "timestamp": now,
                },
                {
                    "role": "assistant",
                    "text": str(assistant_message or "").strip(),
                    "badge_icon": str(badge_icon or "").strip(),
                    "badge_intent": str(badge_intent or "").strip(),
                    "badge_tokens": int(badge_tokens or 0),
                    "badge_cost_usd": str(badge_cost_usd or "n/a").strip() or "n/a",
                    "badge_duration": str(badge_duration or "0.0").strip() or "0.0",
                    "badge_details": [str(row).strip() for row in (badge_details or []) if str(row).strip()],
                    "timestamp": now,
                },
            ]
        )
        history = history[-self.max_messages :]
        self._write_history(user_id, history)
        return history

    def clear_history(self, user_id: str) -> None:
        path = self._history_file(user_id)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _write_history(self, user_id: str, history: list[dict[str, Any]]) -> None:
        path = self._history_file(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)
