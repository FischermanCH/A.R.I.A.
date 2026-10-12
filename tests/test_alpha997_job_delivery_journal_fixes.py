from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aria.modules.activity_journal.service import (
    build_turn_entry,
    list_legacy_rollups,
    migrate_legacy_rollups,
)
from aria.modules.activity_journal.store import ActivityJournalStore
from aria.modules.chat_history_storage.store import FileChatHistoryStore
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.config_ui.page_linter import lint_page_snapshots
from aria.modules.navigation_shell.ui_helpers import render_assistant_message_html


class _MemorySkill:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    async def list_memories_global(self, user_id: str, **_kwargs):  # noqa: ANN003, ANN202
        return [row for row in self.rows if row.get("user_id") == user_id]


def _terminal_store(path: Path) -> AgentJobStore:
    store = AgentJobStore(path)
    store.create(job_id="aj997", user_id="alice", goal="Check disks", status="detached")
    store.set_terminal("aj997", status="done", result="All systems checked")
    return store


def _notice_payload() -> dict[str, object]:
    return {
        "job_id": "aj997",
        "text": "✅ Fertig: **Alle Systeme geprüft.**",
        "badge_icon": "✅",
        "badge_intent": "agent_job_done",
        "badge_tokens": 12,
        "badge_cost_usd": "$0.001000",
        "badge_duration": "26.0",
        "badge_details": ["Routing Debug: agent_job status=done"],
        "request_id": "request-997",
        "event_key": "terminal",
    }


def test_terminal_notice_outbox_retries_before_write_and_after_write_before_ack(tmp_path: Path) -> None:
    store = _terminal_store(tmp_path / "jobs.sqlite3")
    pending = store.get_notice("aj997", "terminal")
    assert pending is not None and pending["delivery_state"] == "pending"
    assert pending["attempts"] == 0

    store.set_notice_payload("aj997", "terminal", _notice_payload())
    first = store.reserve_notice("aj997", "terminal", lease_seconds=0.01)
    assert first is not None and first["attempts"] == 1
    store.fail_notice("aj997", "terminal", "history unavailable")
    failed = store.get_notice("aj997", "terminal")
    assert failed is not None and failed["delivery_state"] == "pending"
    assert failed["last_error"] == "history unavailable"

    history = FileChatHistoryStore(tmp_path / "history")
    second = store.reserve_notice("aj997", "terminal", lease_seconds=0.01)
    assert second is not None and second["attempts"] == 2
    history.append_assistant_notice("alice", **_notice_payload())
    # Simulate a worker dying after the durable history write but before ACK.
    store.fail_notice("aj997", "terminal", "worker stopped before ack")
    third = store.reserve_notice("aj997", "terminal", lease_seconds=0.01)
    assert third is not None and third["attempts"] == 3
    history.append_assistant_notice("alice", **_notice_payload())
    assert history.has_notice("alice", job_id="aj997", event_key="terminal")
    store.mark_notice_delivered("aj997", "terminal")

    rows = [row for row in history.load_history("alice") if row.get("agent_job_event_key") == "terminal"]
    assert len(rows) == 1
    delivered = store.get_notice("aj997", "terminal")
    assert delivered is not None and delivered["delivery_state"] == "delivered"


def test_chat_history_cross_worker_notice_append_is_exactly_once(tmp_path: Path) -> None:
    base = tmp_path / "history"
    one = FileChatHistoryStore(base)
    two = FileChatHistoryStore(base)
    one.append_exchange(
        "alice", user_message="check", assistant_message="detached",
        badge_icon="⏳", badge_intent="agent_job_detached", badge_tokens=0,
        badge_cost_usd="n/a", badge_duration="25.0", agent_job_id="aj997",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(instance.append_assistant_notice, "alice", **_notice_payload())
            for instance in (one, two)
        ]
        for future in futures:
            future.result()
    rows = [row for row in one.load_history("alice") if row.get("agent_job_event_key") == "terminal"]
    assert len(rows) == 1
    assert not list(base.glob("*.tmp"))


def test_reload_reconciles_pending_terminal_notice_once(tmp_path: Path) -> None:
    history = FileChatHistoryStore(tmp_path / "history")
    pipeline = Pipeline.__new__(Pipeline)
    pipeline._project_root = tmp_path
    pipeline._agent_job_store = _terminal_store(tmp_path / "data" / "runtime" / "agent_jobs.sqlite3")
    pipeline._agent_job_store_path = tmp_path / "data" / "runtime" / "agent_jobs.sqlite3"
    pipeline.settings = type("Settings", (), {"ui": type("UI", (), {"language": "de"})()})()
    pipeline._activity_journal_job_finalizer = None

    async def notifier(user_id: str, **payload):  # noqa: ANN003, ANN202
        history.append_assistant_notice(user_id, **payload)
        return history.has_notice(
            user_id, job_id=str(payload.get("job_id") or ""),
            event_key=str(payload.get("event_key") or ""),
        )

    pipeline._agent_job_notifier = notifier
    assert asyncio.run(pipeline.reconcile_agent_job_notices("alice")) == 1
    assert asyncio.run(pipeline.reconcile_agent_job_notices("alice")) == 0
    terminal = [row for row in history.load_history("alice") if row.get("agent_job_event_key") == "terminal"]
    assert len(terminal) == 1


def test_activity_journal_ignores_read_only_self_turn_but_keeps_mixed_turn() -> None:
    common = dict(
        user_id="alice", turn_id="turn-1", started_at=1.0, finished_at=2.0,
        goal="Read my journal", outcome_status="ok", outcome_phrase="Done",
    )
    assert build_turn_entry(**common, used_tool_names=("activity_journal_read",)) is None
    mixed = build_turn_entry(
        **common, used_tool_names=("activity_journal_read", "ssh_read"),
    )
    assert mixed is not None and mixed["tools"] == {"activity_journal_read": 1, "ssh_read": 1}


def test_legacy_remigration_groups_weeks_keeps_only_unique_month_lines_and_updates_in_place(
    tmp_path: Path,
) -> None:
    rows = [
        {
            "id": "week-base", "user_id": "alice", "collection": "aria_context-mem_alice",
            "source": "compression", "rollup_level": "week", "rollup_bucket": "2026-W40",
            "rollup_period_start": "2026-09-28", "rollup_period_end": "2026-10-04",
            "text": "# Memory Compression Template\n- Blender geprüft.\n- Marketing-",
        },
        {
            "id": "week-dim", "user_id": "alice", "collection": "aria_context-mem_alice_dim_3",
            "source": "compression", "rollup_level": "week", "rollup_bucket": "2026-W40",
            "rollup_period_start": "2026-09-28", "rollup_period_end": "2026-10-04",
            "text": "Einträge:\n> - # Memory Compression Template\n- Blender geprüft.\n- Marketing-Kampagne geplant.",
        },
        {
            "id": "month", "user_id": "alice", "collection": "aria_context-mem_alice",
            "source": "compression", "rollup_level": "month", "rollup_bucket": "2026-10",
            "rollup_period_start": "2026-10-01", "rollup_period_end": "2026-10-31",
            "text": "# Memory Compression Template\n- Blender geprüft.\n- Marketing-Kampagne geplant.\n- Neue Monatsnotiz.",
        },
    ]
    skill = _MemorySkill(rows)
    grouped = asyncio.run(list_legacy_rollups(skill, user_id="alice"))
    assert len(grouped) == 2
    week = next(row for row in grouped if row["legacy_level"] == "week")
    month = next(row for row in grouped if row["legacy_level"] == "month")
    assert "Memory Compression Template" not in week["outcome_phrase"]
    assert week["outcome_phrase"].count("Blender geprüft.") == 1
    assert "Marketing-Kampagne geplant." in week["outcome_phrase"]
    assert not week["outcome_phrase"].rstrip().endswith("Marketing-")
    assert month["outcome_phrase"] == "Neue Monatsnotiz."
    assert len(week["legacy_sources"]) == 2

    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    old = dict(week)
    old["id"] = "legacy-old-week-id"
    old["outcome_phrase"] = "stale nested template"
    assert store.write(old)
    first = asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))
    second = asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))
    migrated = store.query("alice", source="legacy_context_rollup", limit=20)
    assert len(migrated) == 2
    assert any(row["id"] == "legacy-old-week-id" and "Blender geprüft." in row["outcome_phrase"] for row in migrated)
    assert first["updated"] >= 1
    assert second["created"] == 0 and second["updated"] == 0


def test_legacy_remigration_keeps_distinct_buckets_with_same_period(tmp_path: Path) -> None:
    rows = [
        {
            "id": f"point-{bucket}", "user_id": "alice",
            "collection": "aria_context-mem_alice",
            "source": "compression", "rollup_level": "week",
            "rollup_bucket": bucket,
            "rollup_period_start": "2020-01-01", "rollup_period_end": "2020-01-07",
            "text": f"Entry for {bucket}",
        }
        for bucket in ("2020-W01", "2020-W02")
    ]
    skill = _MemorySkill(rows)
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    assert asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))["created"] == 2

    second = asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))
    migrated = store.query("alice", source="legacy_context_rollup", limit=20)

    assert second == {"found": 2, "created": 0, "updated": 0, "existing": 2}
    assert {row["goal"] for row in migrated} == {"2020-W01", "2020-W02"}
    assert {
        (source["collection"], source["point_id"])
        for row in migrated
        for source in row["legacy_sources"]
    } == {
        ("aria_context-mem_alice", "point-2020-W01"),
        ("aria_context-mem_alice", "point-2020-W02"),
    }


def test_jobs_template_contract_uses_safe_result_and_compact_danger_action() -> None:
    source = (Path(__file__).resolve().parents[1] / "aria/templates/agent_jobs.html").read_text(encoding="utf-8")
    assert "data-agent-job-inventory-expected" in source
    assert "ui-danger-action ui-compact-action" in source
    assert "data-agent-job-technical" in source
    assert "render_assistant_message_html" in source
    assert "<pre class=\"stats-code\" data-agent-job-result-text>" not in source


def test_safe_assistant_renderer_supports_responsive_tables_without_raw_html() -> None:
    rendered = str(render_assistant_message_html(
        "| Name | Status |\n|---|---|\n| <script>alert(1)</script> | **done** |"
    ))
    assert '<div class="assistant-table-wrap"><table>' in rendered
    assert "<strong>done</strong>" in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


def test_journal_template_has_compact_associated_filters_and_conditional_details() -> None:
    source = (Path(__file__).resolve().parents[1] / "aria/templates/activity_journal.html").read_text(encoding="utf-8")
    for field in ("q", "outcome", "tool", "connection", "server", "since", "until"):
        assert f'for="journal-{field}"' in source
        assert f'id="journal-{field}"' in source
    assert 'class="activity-journal-day"' in source
    assert "{% if entry.detail_rows %}<details" in source
    assert "finished_relative" in source


def test_recipe_startup_warmup_only_uses_deterministic_loader() -> None:
    from aria.main import _schedule_recipe_startup_warmup

    class _Pipeline:
        def __init__(self) -> None:
            self.calls = 0

        def _load_stored_recipe_runtime(self):  # noqa: ANN202
            self.calls += 1
            return [{"id": "daily-check"}]

    async def run() -> _Pipeline:
        pipeline = _Pipeline()
        task = _schedule_recipe_startup_warmup(pipeline)
        assert task is not None
        await task
        return pipeline

    pipeline = asyncio.run(run())
    assert pipeline.calls == 2
    assert pipeline._native_recipe_warmup["loaded"] == 1
    assert pipeline._native_recipe_warmup["provider_calls"] == 0
    assert pipeline._native_recipe_warmup["embedding_calls"] == 0


def test_page_linter_r9_and_r28_to_r30_are_live_with_stats_only_allowlist() -> None:
    broken = {
        "path": "/example", "page_type": "tool", "inherits_page_base": True,
        "title_count": 1, "canonical_parent_section": "help", "rendered_parent_section": "help",
        "english_denied_terms": ["security"],
        "visible_raw_values": ["2026-10-10T08:30:00+02:00"],
        "bad_locale_values": ["$1.2345"],
        "form_geometry_issues": ["unlabelled:query"],
    }
    result = lint_page_snapshots([broken])
    assert {"R9", "R28", "R29", "R30"} <= {row.rule for row in result.blocking_findings}

    stats = dict(broken, path="/stats", bad_locale_values=[], form_geometry_issues=[])
    allowed = lint_page_snapshots([stats], allowlist={"entries": [
        {"path": "/stats", "rule": "R9", "reason": "redesign in alpha998"},
        {"path": "/stats", "rule": "R28", "reason": "redesign in alpha998"},
    ]})
    assert allowed.passed
    assert {row.reason for row in allowed.findings} == {"redesign in alpha998"}
