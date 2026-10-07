from __future__ import annotations

from threading import RLock
import time
from typing import Any, Callable


class RecipeProgressStore:
    def __init__(self, *, ttl_seconds: float = 120.0, clock: Callable[[], float] = time.time) -> None:
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._clock = clock
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    @staticmethod
    def _key(user_id: str) -> str:
        return str(user_id or "").strip().casefold()

    def update(self, user_id: str, **values: object) -> None:
        key = self._key(user_id)
        if not key:
            return
        now = float(self._clock())
        row = {
            "phase": str(values.get("phase") or "running")[:40],
            "step_index": max(0, int(values.get("step_index") or 0)),
            "step_total": max(0, int(values.get("step_total") or 0)),
            "step_type": str(values.get("step_type") or "")[:80],
            "host_index": max(0, int(values.get("host_index") or 0)),
            "host_total": max(0, int(values.get("host_total") or 0)),
            "host_ref": str(values.get("host_ref") or "")[:160],
            "ok_count": max(0, int(values.get("ok_count") or 0)),
            "error_count": max(0, int(values.get("error_count") or 0)),
            "updated_at": now,
        }
        with self._lock:
            self._rows[key] = row

    def get(self, user_id: str) -> dict[str, Any] | None:
        key = self._key(user_id)
        if not key:
            return None
        now = float(self._clock())
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                return None
            if now - float(row.get("updated_at") or 0.0) > self._ttl_seconds:
                self._rows.pop(key, None)
                return None
            return dict(row)

    def clear(self, user_id: str) -> None:
        key = self._key(user_id)
        if not key:
            return
        with self._lock:
            self._rows.pop(key, None)


RECIPE_PROGRESS_STORE = RecipeProgressStore()
