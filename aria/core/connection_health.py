from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _health_store_path() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "runtime" / "connection_health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_health_store() -> dict[str, Any]:
    path = _health_store_path()
    if not path.exists():
        return {"connections": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"connections": {}}
    if not isinstance(data, dict):
        return {"connections": {}}
    connections = data.get("connections", {})
    if not isinstance(connections, dict):
        data["connections"] = {}
    return data


def record_connection_health(ref: str, *, status: str, target: str, message: str) -> dict[str, str]:
    now = datetime.now(timezone.utc).isoformat()
    data = _read_health_store()
    rows = data.setdefault("connections", {})
    existing = rows.get(ref, {}) if isinstance(rows, dict) else {}
    if not isinstance(existing, dict):
        existing = {}
    entry = {
        "last_checked_at": now,
        "last_status": str(status).strip().lower() or "error",
        "last_target": str(target or "").strip(),
        "last_message": str(message or "").strip(),
        "last_success_at": str(existing.get("last_success_at", "")).strip(),
    }
    if entry["last_status"] == "ok":
        entry["last_success_at"] = now
    rows[ref] = entry
    path = _health_store_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    previous_status = str(existing.get("last_status", "")).strip().lower()
    status_changed = bool(previous_status) and previous_status != entry["last_status"]
    entry["previous_status"] = previous_status
    entry["status_changed"] = "1" if status_changed else ""
    if status_changed:
        try:
            from aria.core.config import load_settings
            from aria.core.discord_alerts import send_discord_alerts

            settings = load_settings()
            send_discord_alerts(
                settings,
                category="connection_changes",
                title="Verbindungsstatus geändert",
                lines=[
                    f"Ref: {ref}",
                    f"Ziel: {entry['last_target']}",
                    f"Status: {previous_status or '-'} -> {entry['last_status']}",
                    f"Detail: {entry['last_message']}",
                ],
                level="warn" if entry["last_status"] == "error" else "info",
            )
        except Exception:
            pass
    return entry


def get_connection_health(ref: str) -> dict[str, str]:
    clean_ref = str(ref or "").strip()
    if not clean_ref:
        return {}
    data = _read_health_store()
    rows = data.get("connections", {})
    if not isinstance(rows, dict):
        return {}
    entry = rows.get(clean_ref, {})
    if not isinstance(entry, dict):
        return {}
    return {
        "last_checked_at": str(entry.get("last_checked_at", "")).strip(),
        "last_status": str(entry.get("last_status", "")).strip().lower(),
        "last_target": str(entry.get("last_target", "")).strip(),
        "last_message": str(entry.get("last_message", "")).strip(),
        "last_success_at": str(entry.get("last_success_at", "")).strip(),
    }


def delete_connection_health(ref: str) -> None:
    clean_ref = str(ref or "").strip()
    if not clean_ref:
        return
    data = _read_health_store()
    rows = data.setdefault("connections", {})
    if not isinstance(rows, dict) or clean_ref not in rows:
        return
    rows.pop(clean_ref, None)
    path = _health_store_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
