"""Bounded inbound event normalization and SQLite storage."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


INBOUND_EVENT_CONTRACT = "inbound_event_v1"
DEFAULT_MAX_BODY_BYTES = 64 * 1024
DEFAULT_MAX_EVENTS_PER_SOURCE = 1000
MAX_PREVIEW_CHARS = 2048

_SENSITIVE_KEY_RE = re.compile(
    r"(?:authorization|cookie|credential|password|passwd|secret|token|api[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)
_SAFE_HEADER_NAMES = ("content-type", "user-agent", "x-event-id")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    if depth >= 5:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {
            str(child_key)[:128]: _redact_value(child_value, key=str(child_key), depth=depth + 1)
            for child_key, child_value in list(value.items())[:100]
        }
    if isinstance(value, list):
        return [_redact_value(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:MAX_PREVIEW_CHARS]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:MAX_PREVIEW_CHARS]


def _safe_headers(headers: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in _SAFE_HEADER_NAMES:
        value = str(headers.get(name, "") or "").strip()
        if value:
            result[name] = value[:512]
    return result


def _parse_body(body: bytes, content_type: str) -> Any:
    text = body.decode("utf-8", errors="replace")
    if content_type == "application/json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"unparsed_text": text}
    if content_type == "application/x-www-form-urlencoded":
        from urllib.parse import parse_qs

        return {key: values[-1] if len(values) == 1 else values for key, values in parse_qs(text).items()}
    return text


def _find_first_scalar(payload: Any, names: tuple[str, ...]) -> Any:
    if not isinstance(payload, dict):
        return None
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        value = lowered.get(name)
        if isinstance(value, (str, int, float, bool)):
            return value
    for container_name in ("data", "event", "message", "payload", "sensor"):
        child = lowered.get(container_name)
        value = _find_first_scalar(child, names)
        if value is not None:
            return value
    return None


def _provider_fields(payload: Any, provider_profile: str) -> dict[str, Any]:
    if provider_profile != "senscap_watcher":
        return {}
    fields = {
        "device_id": _find_first_scalar(payload, ("device_id", "deviceid", "device_eui", "deveui")),
        "sensor_id": _find_first_scalar(payload, ("sensor_id", "sensorid", "channel")),
        "measurement": _find_first_scalar(payload, ("measurement", "measure_name", "name", "type")),
        "value": _find_first_scalar(payload, ("value", "measure_value")),
        "unit": _find_first_scalar(payload, ("unit", "measure_unit")),
        "severity": _find_first_scalar(payload, ("severity", "level", "priority")),
        "observed_at": _find_first_scalar(payload, ("observed_at", "timestamp", "time", "created_at")),
    }
    return {key: _redact_value(value, key=key) for key, value in fields.items() if value is not None}


@dataclass(frozen=True, slots=True)
class InboundEvent:
    contract: str
    event_id: str
    source_kind: str
    source_ref: str
    provider_profile: str
    received_at: str
    observed_at: str
    content_type: str
    headers: dict[str, str]
    remote_fingerprint: str
    body_digest: str
    preview: str
    technical_fields: dict[str, Any]
    routing_policy: str
    source_event_id: str
    raw_body: str


def normalize_inbound_event(
    *,
    source_ref: str,
    provider_profile: str,
    content_type: str,
    body: bytes,
    headers: Any,
    remote_host: str,
    routing_policy: str = "log_only",
    store_raw_body: bool = False,
) -> InboundEvent:
    parsed = _parse_body(body, content_type)
    redacted = _redact_value(parsed)
    safe_headers = _safe_headers(headers)
    source_event_id = safe_headers.get("x-event-id", "")
    technical_fields = _provider_fields(redacted, provider_profile)
    observed_at = str(technical_fields.get("observed_at", "") or "")[:128]
    serialized = (
        json.dumps(redacted, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        if not isinstance(redacted, str)
        else redacted
    )
    remote_material = f"{source_ref}\0{remote_host}".encode("utf-8", errors="ignore")
    return InboundEvent(
        contract=INBOUND_EVENT_CONTRACT,
        event_id=str(uuid4()),
        source_kind="inbound_webhook",
        source_ref=source_ref,
        provider_profile=provider_profile,
        received_at=utc_now_iso(),
        observed_at=observed_at,
        content_type=content_type,
        headers=safe_headers,
        remote_fingerprint=hashlib.sha256(remote_material).hexdigest()[:24] if remote_host else "",
        body_digest=hashlib.sha256(body).hexdigest(),
        preview=serialized[:MAX_PREVIEW_CHARS],
        technical_fields=technical_fields,
        routing_policy=routing_policy,
        source_event_id=source_event_id[:256],
        raw_body=serialized if store_raw_body else "",
    )


class InboundEventStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
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
                CREATE TABLE IF NOT EXISTS inbound_events (
                    event_id TEXT PRIMARY KEY,
                    contract TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    provider_profile TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    observed_at TEXT NOT NULL DEFAULT '',
                    content_type TEXT NOT NULL,
                    headers_json TEXT NOT NULL,
                    remote_fingerprint TEXT NOT NULL DEFAULT '',
                    body_digest TEXT NOT NULL,
                    preview TEXT NOT NULL DEFAULT '',
                    technical_fields_json TEXT NOT NULL DEFAULT '{}',
                    routing_policy TEXT NOT NULL DEFAULT 'log_only',
                    source_event_id TEXT NOT NULL DEFAULT '',
                    raw_body TEXT NOT NULL DEFAULT '',
                    activity_type TEXT NOT NULL DEFAULT 'inbound_event_received',
                    processing_state TEXT NOT NULL DEFAULT 'stored'
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(inbound_events)").fetchall()
            }
            if "processing_state" not in columns:
                connection.execute(
                    "ALTER TABLE inbound_events ADD COLUMN processing_state TEXT NOT NULL DEFAULT 'stored'"
                )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_inbound_events_source_event
                ON inbound_events(source_ref, source_event_id)
                WHERE source_event_id != ''
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_inbound_events_source_received
                ON inbound_events(source_ref, received_at DESC)
                """
            )

    def record(self, event: InboundEvent, *, max_events_per_source: int) -> tuple[str, bool]:
        limit = max(1, min(int(max_events_per_source or DEFAULT_MAX_EVENTS_PER_SOURCE), 100_000))
        values = asdict(event)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO inbound_events (
                        event_id, contract, source_kind, source_ref, provider_profile,
                        received_at, observed_at, content_type, headers_json,
                        remote_fingerprint, body_digest, preview, technical_fields_json,
                        routing_policy, source_event_id, raw_body
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["event_id"],
                        values["contract"],
                        values["source_kind"],
                        values["source_ref"],
                        values["provider_profile"],
                        values["received_at"],
                        values["observed_at"],
                        values["content_type"],
                        json.dumps(values["headers"], ensure_ascii=True, sort_keys=True),
                        values["remote_fingerprint"],
                        values["body_digest"],
                        values["preview"],
                        json.dumps(values["technical_fields"], ensure_ascii=True, sort_keys=True),
                        values["routing_policy"],
                        values["source_event_id"],
                        values["raw_body"],
                    ),
                )
                connection.execute(
                    """
                    DELETE FROM inbound_events
                    WHERE source_ref = ?
                      AND event_id NOT IN (
                          SELECT event_id
                          FROM inbound_events
                          WHERE source_ref = ?
                          ORDER BY received_at DESC, event_id DESC
                          LIMIT ?
                      )
                    """,
                    (event.source_ref, event.source_ref, limit),
                )
        except sqlite3.IntegrityError:
            if not event.source_event_id:
                raise
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT event_id FROM inbound_events
                    WHERE source_ref = ? AND source_event_id = ?
                    """,
                    (event.source_ref, event.source_event_id),
                ).fetchone()
            return (str(row["event_id"]) if row else event.event_id), True
        return event.event_id, False

    def list_recent(self, *, source_ref: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clean_limit = max(1, min(int(limit), 1000))
        query = "SELECT * FROM inbound_events"
        params: list[Any] = []
        if source_ref:
            query += " WHERE source_ref = ?"
            params.append(source_ref)
        query += " ORDER BY received_at DESC, event_id DESC LIMIT ?"
        params.append(clean_limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["headers"] = json.loads(item.pop("headers_json"))
            item["technical_fields"] = json.loads(item.pop("technical_fields_json"))
            result.append(item)
        return result
