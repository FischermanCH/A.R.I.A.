"""Optional finalize-hook wiring for the activity journal."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import time
from typing import Any

from .service import build_job_entry, build_turn_entry
from .store import ActivityJournalStore


LOGGER = logging.getLogger(__name__)


def _enabled(owner: Any) -> bool:
    config = getattr(getattr(owner, "settings", None), "agentic_loop", None)
    return bool(getattr(config, "activity_journal_enabled", True))


def _retention_days(owner: Any) -> int:
    config = getattr(getattr(owner, "settings", None), "agentic_loop", None)
    return min(365, max(7, int(getattr(config, "activity_journal_retention_days", 90) or 90)))


def activity_journal_store_for(owner: Any) -> ActivityJournalStore:
    path = Path(getattr(owner, "_project_root", Path.cwd())) / "data" / "runtime" / "activity_journal.sqlite3"
    store = getattr(owner, "_activity_journal_store", None)
    if store is None or Path(getattr(store, "path", "")) != path:
        store = ActivityJournalStore(path)
        owner._activity_journal_store = store
    return store


def _track(owner: Any, task: asyncio.Task[Any]) -> None:
    tasks = getattr(owner, "_activity_journal_tasks", None)
    if tasks is None:
        tasks = set()
        owner._activity_journal_tasks = tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def _write(owner: Any, entry: dict[str, Any]) -> None:
    try:
        inserted = await asyncio.to_thread(activity_journal_store_for(owner).write, entry)
        state = getattr(owner, "_activity_journal_counters", None)
        if not isinstance(state, dict):
            state = {"written": 0, "skipped": 0, "redacted": 0}
            owner._activity_journal_counters = state
        state["written" if inserted else "skipped"] += 1
        state["redacted"] += max(0, int(entry.get("_redaction_count", 0) or 0))
        LOGGER.info(
            "Activity journal finalize written=%d skipped=%d redacted=%d",
            int(state["written"]), int(state["skipped"]), int(state["redacted"]),
        )
    except Exception as exc:
        LOGGER.warning("Activity journal finalize failed (%s)", type(exc).__name__)


async def _sweep(owner: Any) -> None:
    try:
        removed = await asyncio.to_thread(
            activity_journal_store_for(owner).sweep,
            retention_days=_retention_days(owner),
        )
        LOGGER.info("Activity journal retention removed=%d", int(removed))
    except Exception as exc:
        LOGGER.warning("Activity journal retention failed (%s)", type(exc).__name__)


def _schedule(owner: Any, entry: dict[str, Any] | None) -> str:
    if not _enabled(owner) or entry is None:
        return ""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        LOGGER.warning("Activity journal finalize skipped (no event loop)")
        return ""
    task = loop.create_task(_write(owner, entry), name="aria-activity-journal-write")
    _track(owner, task)
    now = time.time()
    if now - float(getattr(owner, "_activity_journal_last_sweep", 0.0) or 0.0) >= 86400:
        owner._activity_journal_last_sweep = now
        _track(owner, loop.create_task(_sweep(owner), name="aria-activity-journal-retention"))
    return str(entry.get("id") or "")


def wire_activity_journal(owner: Any) -> None:
    """Attach optional callbacks without making the pipeline import this module."""

    activity_journal_store_for(owner)

    def finalize_turn(**values: Any) -> str:
        return _schedule(owner, build_turn_entry(**values))

    def finalize_job(record: Any) -> str:
        return _schedule(owner, build_job_entry(record))

    owner._activity_journal_turn_finalizer = finalize_turn
    owner._activity_journal_job_finalizer = finalize_job
