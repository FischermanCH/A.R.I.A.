from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any
from uuid import uuid4


_MAX_TEXT_LENGTH = 12000
_MAX_FILE_ENTRIES = 200
_DEFAULT_AUDIT_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime" / "llm_audit.jsonl"
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|token|secret|password|passwd|webhook_url)(['\"]?\s*[:=]\s*['\"]?)[^'\"\s,}]+"
)
_DISCORD_WEBHOOK_PATTERN = re.compile(r"(?i)(https://discord(?:app)?\.com/api/webhooks/)[^\s'\",}]+")
_OPENAI_KEY_PATTERN = re.compile(r"(?i)sk-[A-Za-z0-9_-]{12,}")


def _redact_text(value: Any) -> str:
    text = str(value or "")
    text = _KEY_VALUE_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
    text = _DISCORD_WEBHOOK_PATTERN.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
    text = _OPENAI_KEY_PATTERN.sub("[REDACTED]", text)
    if len(text) > _MAX_TEXT_LENGTH:
        text = text[:_MAX_TEXT_LENGTH] + "\n...[truncated]"
    return text


def _redact_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    redacted: list[dict[str, str]] = []
    for message in list(messages or []):
        redacted.append(
            {
                "role": str((message or {}).get("role", "") or "").strip(),
                "content": _redact_text((message or {}).get("content", "")),
            }
        )
    return redacted


@dataclass(slots=True)
class LLMAuditEntry:
    id: str
    created_at: str
    model: str = ""
    source: str = ""
    operation: str = ""
    user_id: str = ""
    request_id: str = ""
    duration_ms: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    messages: list[dict[str, str]] = field(default_factory=list)
    response: str = ""
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "model": self.model,
            "source": self.source,
            "operation": self.operation,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "duration_ms": self.duration_ms,
            "usage": dict(self.usage or {}),
            "messages": list(self.messages or []),
            "response": self.response,
            "error": self.error,
        }


class LLMAuditLog:
    def __init__(self, max_entries: int = 60, path: Path | None = None) -> None:
        self._entries: deque[LLMAuditEntry] = deque(maxlen=max(1, int(max_entries or 60)))
        self._lock = Lock()
        self._path = path or _DEFAULT_AUDIT_PATH

    def record(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        source: str = "",
        operation: str = "",
        user_id: str = "",
        request_id: str = "",
        duration_ms: int = 0,
        usage: dict[str, int] | None = None,
        response: str = "",
        error: str = "",
    ) -> None:
        entry = LLMAuditEntry(
            id=uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            model=str(model or "").strip(),
            source=str(source or "").strip(),
            operation=str(operation or "").strip(),
            user_id=_redact_text(user_id),
            request_id=str(request_id or "").strip(),
            duration_ms=max(0, int(duration_ms or 0)),
            usage={str(key): int(value or 0) for key, value in dict(usage or {}).items()},
            messages=_redact_messages(messages),
            response=_redact_text(response),
            error=_redact_text(error),
        )
        with self._lock:
            self._entries.appendleft(entry)
            self._append_file(entry)

    def entries(self, limit: int = 30) -> list[dict[str, Any]]:
        clean_limit = max(1, int(limit or 30))
        with self._lock:
            file_entries = self._read_file_entries(clean_limit)
            if file_entries:
                return file_entries
            return [entry.as_dict() for entry in list(self._entries)[:clean_limit]]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            try:
                self._path.unlink(missing_ok=True)
            except Exception:
                pass

    def _append_file(self, entry: LLMAuditEntry) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            self._trim_file()
        except Exception:
            pass

    def _read_file_entries(self, limit: int) -> list[dict[str, Any]]:
        try:
            if not self._path.exists():
                return []
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []

        entries: list[dict[str, Any]] = []
        for line in reversed(lines[-_MAX_FILE_ENTRIES:]):
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
            if len(entries) >= limit:
                break
        return entries

    def _trim_file(self) -> None:
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            if len(lines) <= _MAX_FILE_ENTRIES:
                return
            self._path.write_text("\n".join(lines[-_MAX_FILE_ENTRIES:]) + "\n", encoding="utf-8")
        except Exception:
            pass


GLOBAL_LLM_AUDIT_LOG = LLMAuditLog()
