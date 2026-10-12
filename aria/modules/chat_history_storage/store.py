"""Bounded per-user JSON chat-history storage."""

from __future__ import annotations

import copy
from contextlib import contextmanager
import fcntl
import json
import os
import re
import threading
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FileChatHistoryStore:
    def __init__(self, base_dir: Path, max_messages: int = 80) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages = max(2, int(max_messages))
        self._cache_lock = threading.RLock()
        self._history_cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _safe_user_id(user_id: str) -> str:
        raw = str(user_id or "").strip()
        if not raw:
            return "anonymous"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)

    def _history_file(self, user_id: str) -> Path:
        return self.base_dir / f"{self._safe_user_id(user_id)}.json"

    @contextmanager
    def _user_file_lock(self, user_id: str):  # type: ignore[no-untyped-def]
        lock_path = self.base_dir / f".{self._safe_user_id(user_id)}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_history_file(self, user_id: str) -> list[dict[str, Any]]:
        path = self._history_file(user_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
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
            rows.append({
                "role": role,
                "text": text,
                "badge_icon": str(item.get("badge_icon", "")).strip(),
                "badge_intent": str(item.get("badge_intent", "")).strip(),
                "badge_tokens": int(item.get("badge_tokens", 0) or 0),
                "badge_cost_usd": str(item.get("badge_cost_usd", "n/a")).strip() or "n/a",
                "badge_duration": str(item.get("badge_duration", "0.0")).strip() or "0.0",
                "badge_details": [str(row).strip() for row in (item.get("badge_details") or []) if str(row).strip()],
                "request_id": str(item.get("request_id", "")).strip(),
                "agent_job_id": str(item.get("agent_job_id", "")).strip(),
                "agent_job_notice": bool(item.get("agent_job_notice", False)),
                "agent_job_event_key": str(item.get("agent_job_event_key", "")).strip(),
                "timestamp": str(item.get("timestamp", "")).strip(),
            })
        return rows[-self.max_messages :]

    def _read_cached_history(self, user_id: str) -> list[dict[str, Any]]:
        path = self._history_file(user_id)
        cache_key = str(path)
        try:
            stat = path.stat()
        except FileNotFoundError:
            with self._cache_lock:
                self._history_cache.pop(cache_key, None)
            return []
        except OSError:
            with self._cache_lock:
                self._history_cache.pop(cache_key, None)
            return []

        with self._cache_lock:
            cached = self._history_cache.get(cache_key)
            if (
                cached
                and int(cached.get("mtime_ns", -1)) == int(stat.st_mtime_ns)
                and int(cached.get("size", -1)) == int(stat.st_size)
            ):
                return copy.deepcopy(cached.get("rows", []))

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
                    "request_id": str(item.get("request_id", "")).strip(),
                    "agent_job_id": str(item.get("agent_job_id", "")).strip(),
                    "agent_job_notice": bool(item.get("agent_job_notice", False)),
                    "agent_job_event_key": str(item.get("agent_job_event_key", "")).strip(),
                    "timestamp": str(item.get("timestamp", "")).strip(),
                }
            )
        rows = rows[-self.max_messages :]
        with self._cache_lock:
            self._history_cache[cache_key] = {
                "mtime_ns": int(stat.st_mtime_ns),
                "size": int(stat.st_size),
                "rows": copy.deepcopy(rows),
            }
        return copy.deepcopy(rows)

    def load_history(self, user_id: str) -> list[dict[str, Any]]:
        return self._read_cached_history(user_id)

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
        request_id: str = "",
        agent_job_id: str = "",
    ) -> list[dict[str, Any]]:
        with self._cache_lock, self._user_file_lock(user_id):
            history = self._read_history_file(user_id)
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
                        "request_id": str(request_id or "").strip(),
                        "agent_job_id": str(agent_job_id or "").strip(),
                        "agent_job_notice": False,
                        "timestamp": now,
                    },
                ]
            )
            history = history[-self.max_messages :]
            self._write_history(user_id, history)
            return history

    def append_assistant_notice(
        self,
        user_id: str,
        *,
        job_id: str,
        text: str,
        badge_icon: str,
        badge_intent: str,
        badge_tokens: int,
        badge_cost_usd: str,
        badge_duration: str,
        badge_details: list[str] | None = None,
        request_id: str = "",
        event_key: str = "",
    ) -> list[dict[str, Any]]:
        """Append an assistant-only event without inventing an empty user turn."""

        with self._cache_lock, self._user_file_lock(user_id):
            history = self._read_history_file(user_id)
            clean_job_id = str(job_id or "").strip()
            clean_event_key = str(event_key or "").strip()
            if clean_job_id and clean_event_key and any(
                str(row.get("agent_job_id") or "") == clean_job_id
                and str(row.get("agent_job_event_key") or "") == clean_event_key
                for row in history
            ):
                return history
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            history.append({
                "role": "assistant",
                "text": str(text or "").strip(),
                "badge_icon": str(badge_icon or "").strip(),
                "badge_intent": str(badge_intent or "").strip(),
                "badge_tokens": int(badge_tokens or 0),
                "badge_cost_usd": str(badge_cost_usd or "n/a").strip() or "n/a",
                "badge_duration": str(badge_duration or "0.0").strip() or "0.0",
                "badge_details": [str(row).strip() for row in (badge_details or []) if str(row).strip()],
                "request_id": str(request_id or "").strip(),
                "agent_job_id": clean_job_id,
                "agent_job_event_key": clean_event_key,
                "agent_job_notice": True,
                "timestamp": now,
            })
            history = history[-self.max_messages :]
            self._write_history(user_id, history)
            return history

    def has_notice(self, user_id: str, *, job_id: str, event_key: str) -> bool:
        clean_job_id = str(job_id or "").strip()
        clean_event_key = str(event_key or "").strip()
        return bool(clean_job_id and clean_event_key and any(
            str(row.get("agent_job_id") or "") == clean_job_id
            and str(row.get("agent_job_event_key") or "") == clean_event_key
            for row in self.load_history(user_id)
        ))

    def clear_history(self, user_id: str) -> None:
        path = self._history_file(user_id)
        with self._cache_lock, self._user_file_lock(user_id):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            self._history_cache.pop(str(path), None)

    def _write_history(self, user_id: str, history: list[dict[str, Any]]) -> None:
        path = self._history_file(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
        )
        tmp_path = Path(raw_tmp_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(history, ensure_ascii=False, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            tmp_path.replace(path)
        finally:
            tmp_path.unlink(missing_ok=True)
        try:
            stat = path.stat()
        except OSError:
            return
        with self._cache_lock:
            self._history_cache[str(path)] = {
                "mtime_ns": int(stat.st_mtime_ns),
                "size": int(stat.st_size),
                "rows": copy.deepcopy(history[-self.max_messages :]),
            }
