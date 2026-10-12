from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules.activity_journal.service import build_job_entry, build_turn_entry
from aria.modules.activity_journal.store import ActivityJournalStore
from aria.modules.stats_ui import overview as stats_overview
from aria.modules.stats_ui.overview import (
    StatsActivityAggregation,
    StatsResourceSnapshot,
    StatsUsageAggregation,
    format_currency,
    format_integer,
    format_percent,
)


def _line(timestamp: str, *, request_id: str, cost: float, model: str = "example/chat-a") -> str:
    return json.dumps({
        "timestamp": timestamp,
        "request_id": request_id,
        "total_tokens": 100,
        "embedding_total_tokens": 10,
        "chat_model": model,
        "embedding_model": "example/embed",
        "chat_cost_usd": cost * 0.8,
        "embedding_cost_usd": cost * 0.2,
        "total_cost_usd": cost,
        "source": "chat",
    }) + "\n"


def test_usage_aggregation_includes_active_and_archived_calendar_month(tmp_path: Path) -> None:
    log = tmp_path / "tokens.jsonl"
    log.write_text(_line("2026-10-10T12:00:00Z", request_id="new", cost=2.0), encoding="utf-8")
    log.with_name("tokens-archive-20261009.jsonl").write_text(
        _line("2026-10-01T12:00:00Z", request_id="old", cost=1.0)
        + _line("2026-10-10T12:00:00Z", request_id="new", cost=2.0),
        encoding="utf-8",
    )
    now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc).timestamp()

    result = StatsUsageAggregation(log, "Europe/Zurich").build(language="de", now=now)

    assert result["periods"]["month"]["cost"] == 3.0
    assert result["periods"]["month"]["cost_label"] == "US$ 3,00"
    assert len(result["chart"]) == 30


def test_locale_helpers_are_symmetric() -> None:
    assert format_integer(11_772_562, "de") == "11.772.562"
    assert format_integer(11_772_562, "en") == "11,772,562"
    assert format_percent(3.2, "de") == "3,2 %"
    assert format_percent(3.2, "en") == "3.2%"
    assert format_currency(25.74, "de") == "US$ 25,74"
    assert format_currency(25.74, "en") == "US$25.74"


def test_activity_is_user_scoped_and_usage_fields_round_trip(tmp_path: Path) -> None:
    store = ActivityJournalStore(tmp_path / "activity.sqlite3")
    now = datetime.now(timezone.utc).timestamp()
    own = build_turn_entry(
        user_id="demo", turn_id="turn-1", started_at=now - 1, finished_at=now,
        goal="Read the report", used_tool_names=("document_content_read",),
        outcome_status="ok", outcome_phrase="Done", connection_refs=("docs",),
        usage={"input_tokens": 120, "output_tokens": 30, "embedding_tokens": 8, "cost_usd": 0.12},
    )
    other = build_turn_entry(
        user_id="other", turn_id="turn-2", started_at=now - 1, finished_at=now,
        goal="Private", used_tool_names=("ssh_read",), outcome_status="error", outcome_phrase="No",
    )
    assert own and other
    store.write(own)
    store.write(other)
    row = store.query("demo", limit=10)[0]
    assert (row["input_tokens"], row["output_tokens"], row["embedding_tokens"], row["cost_usd"]) == (120, 30, 8, 0.12)

    result = StatsActivityAggregation(store.path, SimpleNamespace(list_for_user=lambda *_a, **_k: ()), True).build(user_id="demo", language="en", now=now)
    assert result["turns"] == 1
    assert result["errors"] == 0
    assert result["top_tools"][0]["name"] == "document_content_read"


def test_job_projection_uses_persisted_meter_snapshot() -> None:
    record = SimpleNamespace(
        user_id="demo", job_id="job-1", goal="Build scene", result="Done", status="done",
        created_at=1.0, updated_at=2.0, step_log=(), usage={"input_tokens": 9, "output_tokens": 4, "cost_usd": 0.02},
        confirmation_asked=0, confirmation_approved=0, confirmation_rejected=0, corrected=False,
    )
    row = build_job_entry(record)
    assert row["input_tokens"] == 9
    assert row["output_tokens"] == 4
    assert row["cost_usd"] == 0.02


def test_resource_snapshot_is_cached_for_sixty_seconds(monkeypatch, tmp_path: Path) -> None:
    stats_overview._RESOURCE_CACHE.clear()
    snapshot = StatsResourceSnapshot(tmp_path, ttl_seconds=60)
    calls = 0
    real_size = snapshot._size

    def counted(path: Path) -> int:
        nonlocal calls
        calls += 1
        return real_size(path)

    monkeypatch.setattr(snapshot, "_size", counted)
    first = snapshot.build(language="en", now=1000)
    first_calls = calls
    second = snapshot.build(language="en", now=1059)
    assert first["cached"] is False
    assert second["cached"] is True
    assert calls == first_calls


def test_resource_snapshot_cache_never_leaks_locale_formatting(tmp_path: Path) -> None:
    stats_overview._RESOURCE_CACHE.clear()
    snapshot = StatsResourceSnapshot(tmp_path, ttl_seconds=60)

    german = snapshot.build(language="de", now=1000)
    english = snapshot.build(language="en", now=1001)

    assert "," in german["rss_percent_label"]
    assert "." in english["rss_percent_label"]
    assert english["cached"] is False


def test_stats_allowlist_has_no_timeboxed_exception() -> None:
    payload = json.loads(Path("tests/e2e/page_linter_allowlist.json").read_text(encoding="utf-8"))
    assert not [row for row in payload["entries"] if row.get("path") == "/stats"]
