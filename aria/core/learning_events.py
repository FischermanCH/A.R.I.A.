from __future__ import annotations

import json
import re
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


_LEARNING_EVENT_LOCK = threading.RLock()
_MAX_STRING_LENGTH = 2000
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]{4,}"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def default_learning_event_store_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path(__file__).resolve().parents[2]
    return root / "data" / "runtime" / "learning_events.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    if len(text) > _MAX_STRING_LENGTH:
        return text[:_MAX_STRING_LENGTH].rstrip() + "..."
    return text


def redact_learning_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = _clean_text(key)
            if re.search(r"(?i)(api[_-]?key|token|secret|password|private[_-]?key)", key_text):
                clean[key_text] = "[REDACTED]"
            else:
                clean[key_text] = redact_learning_payload(item)
        return clean
    if isinstance(value, list | tuple | set):
        return [redact_learning_payload(item) for item in value]
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, int | float | bool) or value is None:
        return value
    return _clean_text(value)


def normalize_learning_event(event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _clean_text(event.get("event_id") or uuid4().hex)
    created_at = _clean_text(event.get("created_at") or _utc_now())
    return {
        "event_id": event_id,
        "created_at": created_at,
        "event_type": _clean_text(event.get("event_type") or "observation"),
        "artifact_type": _clean_text(event.get("artifact_type") or "observation"),
        "status": _clean_text(event.get("status") or "observed"),
        "risk": _clean_text(event.get("risk") or "low"),
        "user_id": _clean_text(event.get("user_id") or ""),
        "source": _clean_text(event.get("source") or ""),
        "request_id": _clean_text(event.get("request_id") or ""),
        "session_id": _clean_text(event.get("session_id") or ""),
        "summary": _clean_text(event.get("summary") or ""),
        "evidence": redact_learning_payload(event.get("evidence") or {}),
        "metadata": redact_learning_payload(event.get("metadata") or {}),
    }


def record_learning_event(
    event: Mapping[str, Any],
    *,
    path: Path | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    normalized = normalize_learning_event(event)
    store_path = path or default_learning_event_store_path(base_dir)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(normalized, ensure_ascii=True, sort_keys=True)
    with _LEARNING_EVENT_LOCK:
        with store_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    return normalized


def load_learning_events(
    *,
    path: Path | None = None,
    base_dir: Path | None = None,
    limit: int = 100,
    user_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    store_path = path or default_learning_event_store_path(base_dir)
    try:
        lines = store_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    clean_user_id = str(user_id or "").strip()
    clean_event_type = str(event_type or "").strip()
    clean_status = str(status or "").strip()
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if clean_user_id and str(item.get("user_id", "")).strip() != clean_user_id:
            continue
        if clean_event_type and str(item.get("event_type", "")).strip() != clean_event_type:
            continue
        if clean_status and str(item.get("status", "")).strip() != clean_status:
            continue
        events.append(dict(item))

    clean_limit = max(0, int(limit or 0))
    if not clean_limit:
        return []
    return events[-clean_limit:]
