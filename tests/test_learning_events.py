from __future__ import annotations

import json

from aria.core.learning_events import load_learning_events
from aria.core.learning_events import normalize_learning_event
from aria.core.learning_events import record_learning_event


def test_record_learning_event_appends_redacted_jsonl(tmp_path) -> None:
    path = tmp_path / "learning_events.jsonl"

    event = record_learning_event(
        {
            "event_type": "reflection",
            "artifact_type": "memory_reflection",
            "user_id": "u1",
            "summary": "Learn source behavior",
            "evidence": {
                "message": "token=super-secret-value",
                "api_key": "sk-testsecret1234567890",
            },
            "metadata": {"auth": "Bearer abcdefghijklmnop"},
        },
        path=path,
    )

    assert event["status"] == "observed"
    assert path.exists()
    raw = path.read_text(encoding="utf-8")
    assert "super-secret-value" not in raw
    assert "sk-testsecret" not in raw
    assert "abcdefghijklmnop" not in raw
    stored = json.loads(raw)
    assert stored["evidence"]["api_key"] == "[REDACTED]"
    assert stored["evidence"]["message"] == "[REDACTED]"
    assert stored["metadata"]["auth"] == "[REDACTED]"


def test_load_learning_events_filters_and_limits(tmp_path) -> None:
    path = tmp_path / "learning_events.jsonl"
    record_learning_event({"event_type": "turn", "user_id": "u1", "summary": "one"}, path=path)
    record_learning_event({"event_type": "reflection", "user_id": "u2", "summary": "two"}, path=path)
    record_learning_event({"event_type": "reflection", "user_id": "u1", "summary": "three"}, path=path)

    events = load_learning_events(path=path, user_id="u1", limit=1)

    assert len(events) == 1
    assert events[0]["summary"] == "three"
    assert load_learning_events(path=path, event_type="reflection", limit=10)[0]["summary"] == "two"
    assert load_learning_events(path=path, status="promoted") == []


def test_normalize_learning_event_defaults_and_stable_fields() -> None:
    event = normalize_learning_event({"summary": "  learned something  "})

    assert event["event_id"]
    assert event["created_at"]
    assert event["event_type"] == "observation"
    assert event["artifact_type"] == "observation"
    assert event["status"] == "observed"
    assert event["risk"] == "low"
    assert event["summary"] == "learned something"
