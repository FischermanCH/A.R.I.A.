from __future__ import annotations

import json
from pathlib import Path

from aria.core import connection_health


def test_connection_health_cache_refreshes_after_external_change(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "connection_health.json"
    monkeypatch.setattr(connection_health, "_health_store_path", lambda: target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "connections": {
                    "searxng:web": {
                        "last_checked_at": "2026-04-09T08:00:00Z",
                        "last_status": "ok",
                        "last_target": "http://searxng:8080",
                        "last_message": "cached ok",
                        "last_success_at": "2026-04-09T08:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    first = connection_health.get_connection_health("searxng:web")
    assert first["last_message"] == "cached ok"

    target.write_text(
        json.dumps(
            {
                "connections": {
                    "searxng:web": {
                        "last_checked_at": "2026-04-09T08:05:00Z",
                        "last_status": "error",
                        "last_target": "http://searxng:8080",
                        "last_message": "cached error",
                        "last_success_at": "2026-04-09T08:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    second = connection_health.get_connection_health("searxng:web")
    assert second["last_status"] == "error"
    assert second["last_message"] == "cached error"


def test_connection_health_returns_copy(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "connection_health.json"
    monkeypatch.setattr(connection_health, "_health_store_path", lambda: target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "connections": {
                    "searxng:web": {
                        "last_checked_at": "2026-04-09T08:00:00Z",
                        "last_status": "ok",
                        "last_target": "http://searxng:8080",
                        "last_message": "cached ok",
                        "last_success_at": "2026-04-09T08:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = connection_health.get_connection_health("searxng:web")
    payload["last_message"] = "mutated"

    fresh = connection_health.get_connection_health("searxng:web")
    assert fresh["last_message"] == "cached ok"
