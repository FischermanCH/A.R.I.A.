"""Worker-shared persistence for detached native-agent turns."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Sequence


_GOAL_LIMIT = 600
_RESULT_LIMIT = 12_000
_OUTCOME_LIMIT = 800
_DETAIL_LIMIT = 800
_DETAIL_LINES_LIMIT = 24
_CORRECTION_LIMIT = 1_000
_CORRECTION_QUEUE_LIMIT = 12
_TOOL_LIMIT = 12
_STEP_LIMIT = 100
_JOB_STATUSES = {
    "running", "done", "error", "detached", "paused", "awaiting_confirmation", "cancelled",
}


def _bounded(value: object, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 1)] + "…"


@dataclass(frozen=True)
class AgentJobRecord:
    job_id: str
    user_id: str
    goal: str
    status: str
    step_log: tuple[dict[str, Any], ...]
    result: str
    created_at: float
    updated_at: float
    worker_id: str
    cancel_requested: bool = False
    warning: str = ""
    notified: bool = False
    pause_requested: bool = False
    resume_state: dict[str, Any] | None = None
    paused_at: float = 0.0
    pause_count: int = 0
    detail_lines: tuple[str, ...] = ()
    correction_queue: tuple[str, ...] = ()
    pause_reason: str = ""
    event_key: str = ""
    usage: dict[str, Any] | None = None

    def as_dict(self, *, recent_steps: int = 8) -> dict[str, Any]:
        usage = dict(self.usage or {})
        usage["total_tokens"] = max(
            0,
            int(usage.get("input_tokens", 0) or 0)
            + int(usage.get("output_tokens", 0) or 0),
        )
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "status": self.status,
            "step_log": [dict(row) for row in self.step_log[-max(1, int(recent_steps)):]],
            "step_count": len(self.step_log),
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cancel_requested": self.cancel_requested,
            "warning": self.warning,
            "notified": self.notified,
            "pause_requested": self.pause_requested,
            "paused_at": self.paused_at,
            "pause_count": self.pause_count,
            "correction_count": len(self.correction_queue),
            "awaiting_preview": str((self.resume_state or {}).get("pending_preview") or "")[:800],
            "pause_reason": self.pause_reason,
            "event_key": self.event_key,
            "usage": usage,
        }


@dataclass(frozen=True)
class AgentJobActionClaim:
    status: str
    state: dict[str, Any] | None = None


class AgentJobStore:
    """Small SQLite store safe for readers and writers in separate workers."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step_log TEXT NOT NULL DEFAULT '[]',
                    result TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    worker_id TEXT NOT NULL DEFAULT '',
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    warning TEXT NOT NULL DEFAULT '',
                    notified INTEGER NOT NULL DEFAULT 0,
                    pause_requested INTEGER NOT NULL DEFAULT 0,
                    resume_state TEXT,
                    paused_at REAL NOT NULL DEFAULT 0,
                    pause_count INTEGER NOT NULL DEFAULT 0,
                    detail_lines TEXT NOT NULL DEFAULT '[]',
                    correction_queue TEXT NOT NULL DEFAULT '[]',
                    pause_reason TEXT NOT NULL DEFAULT '',
                    pause_event_key TEXT NOT NULL DEFAULT '',
                    usage TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(agent_jobs)").fetchall()
            }
            if "cancel_requested" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0"
                )
            if "warning" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN warning TEXT NOT NULL DEFAULT ''"
                )
            if "notified" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN notified INTEGER NOT NULL DEFAULT 0"
                )
            if "pause_requested" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0"
                )
            if "resume_state" not in columns:
                connection.execute("ALTER TABLE agent_jobs ADD COLUMN resume_state TEXT")
            if "paused_at" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN paused_at REAL NOT NULL DEFAULT 0"
                )
            if "pause_count" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN pause_count INTEGER NOT NULL DEFAULT 0"
                )
            if "detail_lines" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN detail_lines TEXT NOT NULL DEFAULT '[]'"
                )
            if "correction_queue" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN correction_queue TEXT NOT NULL DEFAULT '[]'"
                )
            if "pause_reason" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN pause_reason TEXT NOT NULL DEFAULT ''"
                )
            if "pause_event_key" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN pause_event_key TEXT NOT NULL DEFAULT ''"
                )
            if "usage" not in columns:
                connection.execute(
                    "ALTER TABLE agent_jobs ADD COLUMN usage TEXT NOT NULL DEFAULT '{}'"
                )
            connection.execute(
                "UPDATE agent_jobs SET pause_event_key=(CASE WHEN pause_reason='budget_reached' "
                "THEN 'budget_paused#' ELSE 'paused#' END) || MAX(1,pause_count) "
                "WHERE status='paused' AND pause_event_key=''"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS agent_job_notices ("
                "job_id TEXT NOT NULL,event_key TEXT NOT NULL,created_at REAL NOT NULL,"
                "PRIMARY KEY(job_id,event_key))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS agent_job_pause_actions ("
                "job_id TEXT NOT NULL,event_key TEXT NOT NULL,action TEXT NOT NULL,created_at REAL NOT NULL,"
                "PRIMARY KEY(job_id,event_key))"
            )
            connection.execute(
                "INSERT OR IGNORE INTO agent_job_notices(job_id,event_key,created_at) "
                "SELECT job_id,'terminal',updated_at FROM agent_jobs WHERE notified=1"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_jobs_user_updated "
                "ON agent_jobs(user_id, updated_at DESC)"
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def create(
        self, *, job_id: str, user_id: str, goal: str, status: str = "detached",
        worker_id: str = "", now: float | None = None,
    ) -> AgentJobRecord:
        if status not in _JOB_STATUSES:
            raise ValueError("invalid_agent_job_status")
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (str(job_id), str(user_id), _bounded(goal, _GOAL_LIMIT), status, "[]", "", timestamp, timestamp, str(worker_id)),
            )
        record = self.get(job_id)
        if record is None:  # pragma: no cover - SQLite insert/read invariant
            raise RuntimeError("agent_job_create_failed")
        return record

    def append_step(
        self, job_id: str, *, step_index: int, tool_names: Sequence[str], outcome_summary: str,
        now: float | None = None,
    ) -> None:
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT step_log FROM agent_jobs WHERE job_id=?", (str(job_id),)).fetchone()
            if row is None:
                return
            try:
                entries = list(json.loads(str(row["step_log"] or "[]")))
            except (TypeError, ValueError, json.JSONDecodeError):
                entries = []
            if len(entries) < _STEP_LIMIT:
                entries.append({
                    "step_index": max(0, int(step_index)),
                    "tool_names": [_bounded(name, 120) for name in list(tool_names)[:_TOOL_LIMIT] if str(name).strip()],
                    "outcome_summary": _bounded(outcome_summary, _OUTCOME_LIMIT),
                })
            connection.execute(
                "UPDATE agent_jobs SET step_log=?, updated_at=? WHERE job_id=?",
                (json.dumps(entries, ensure_ascii=True, separators=(",", ":")), timestamp, str(job_id)),
            )

    def append_detail_line(
        self, job_id: str, *, user_id: str, detail_line: str,
        now: float | None = None,
    ) -> bool:
        """Persist one bounded owner-scoped diagnostic line for terminal notice Details."""

        clean_line = _bounded(detail_line, _DETAIL_LIMIT)
        if not clean_line:
            return False
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT detail_lines FROM agent_jobs WHERE job_id=? AND user_id=?",
                (str(job_id), str(user_id)),
            ).fetchone()
            if row is None:
                return False
            try:
                entries = [
                    str(item) for item in json.loads(str(row["detail_lines"] or "[]"))
                    if str(item).strip()
                ]
            except (TypeError, ValueError, json.JSONDecodeError):
                entries = []
            if clean_line not in entries:
                entries = [*entries[-(_DETAIL_LINES_LIMIT - 1):], clean_line]
            connection.execute(
                "UPDATE agent_jobs SET detail_lines=?, updated_at=? WHERE job_id=? AND user_id=?",
                (
                    json.dumps(entries, ensure_ascii=True, separators=(",", ":")),
                    timestamp,
                    str(job_id),
                    str(user_id),
                ),
            )
        return True

    def set_usage(self, job_id: str, usage: dict[str, Any], *, now: float | None = None) -> None:
        """Persist one bounded cumulative usage snapshot for live job surfaces."""

        normalized: dict[str, Any] = {
            key: max(0, int(usage.get(key, 0) or 0))
            for key in ("input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens")
        }
        raw_cost = usage.get("cost_usd")
        if raw_cost is not None:
            try:
                normalized["cost_usd"] = max(0.0, float(raw_cost))
            except (TypeError, ValueError):
                pass
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE agent_jobs SET usage=?,updated_at=? WHERE job_id=?",
                (json.dumps(normalized, separators=(",", ":")), timestamp, str(job_id)),
            )

    def set_terminal(
        self, job_id: str, *, status: str, result: str, warning: str = "",
        now: float | None = None,
    ) -> None:
        if status not in {"done", "error", "cancelled"}:
            raise ValueError("invalid_agent_job_terminal_status")
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE agent_jobs SET status=?, result=?, warning=?, updated_at=?, "
                "pause_requested=0, resume_state=NULL, correction_queue='[]', pause_reason='', paused_at=0 WHERE job_id=?",
                (status, _bounded(result, _RESULT_LIMIT), _bounded(warning, 120), timestamp, str(job_id)),
            )

    def request_pause(
        self, job_id: str, *, user_id: str, now: float | None = None,
    ) -> str:
        """Atomically request a clean-boundary pause for the user's live job."""

        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT user_id,status,cancel_requested FROM agent_jobs WHERE job_id=?",
                (str(job_id),),
            ).fetchone()
            if row is None or str(row["user_id"]) != str(user_id):
                return "not_found"
            if str(row["status"]) not in {"running", "detached"} or bool(int(row["cancel_requested"] or 0)):
                return "not_running"
            connection.execute(
                "UPDATE agent_jobs SET pause_requested=1, warning='', updated_at=? "
                "WHERE job_id=? AND user_id=?",
                (timestamp, str(job_id), str(user_id)),
            )
            return "requested"

    def queue_correction(
        self, job_id: str, *, user_id: str, text: str, now: float | None = None,
    ) -> str:
        """Append one bounded correction to a live owner-scoped job."""

        clean_text = str(text or "").strip()[:_CORRECTION_LIMIT]
        if not clean_text:
            return "invalid"
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT user_id,status,correction_queue FROM agent_jobs WHERE job_id=?",
                (str(job_id),),
            ).fetchone()
            if row is None or str(row["user_id"]) != str(user_id):
                return "not_found"
            if str(row["status"]) not in {
                "running", "detached", "paused", "awaiting_confirmation",
            }:
                return "not_running"
            try:
                queue = [str(item) for item in json.loads(str(row["correction_queue"] or "[]"))]
            except (TypeError, ValueError, json.JSONDecodeError):
                queue = []
            queue = [*queue[-(_CORRECTION_QUEUE_LIMIT - 1):], clean_text]
            connection.execute(
                "UPDATE agent_jobs SET correction_queue=?, updated_at=? WHERE job_id=? AND user_id=?",
                (
                    json.dumps(queue, ensure_ascii=True, separators=(",", ":")),
                    timestamp, str(job_id), str(user_id),
                ),
            )
        return "queued"

    def drain_corrections(self, job_id: str, *, user_id: str) -> tuple[str, ...]:
        """Atomically return and clear queued corrections for the job owner."""

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT correction_queue FROM agent_jobs WHERE job_id=? AND user_id=?",
                (str(job_id), str(user_id)),
            ).fetchone()
            if row is None:
                return ()
            try:
                queue = tuple(
                    str(item).strip()[:_CORRECTION_LIMIT]
                    for item in json.loads(str(row["correction_queue"] or "[]"))
                    if str(item).strip()
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                queue = ()
            connection.execute(
                "UPDATE agent_jobs SET correction_queue='[]' WHERE job_id=? AND user_id=?",
                (str(job_id), str(user_id)),
            )
        return queue

    def is_pause_requested(self, job_id: str, *, user_id: str) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT pause_requested FROM agent_jobs WHERE job_id=? AND user_id=?",
                (str(job_id), str(user_id)),
            ).fetchone()
        return bool(row and int(row["pause_requested"] or 0))

    def refuse_pause(
        self, job_id: str, *, user_id: str, reason: str, now: float | None = None,
    ) -> None:
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE agent_jobs SET pause_requested=0, warning=?, updated_at=? "
                "WHERE job_id=? AND user_id=? AND status IN ('running','detached')",
                (_bounded(reason, 120), timestamp, str(job_id), str(user_id)),
            )

    def set_paused(
        self, job_id: str, state_json: dict[str, Any], *, reason: str = "user_requested",
        now: float | None = None,
    ) -> bool:
        timestamp = float(time.time() if now is None else now)
        serialized = json.dumps(state_json, ensure_ascii=True, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status,pause_count,cancel_requested FROM agent_jobs WHERE job_id=?",
                (str(job_id),),
            ).fetchone()
            if (
                row is None or str(row["status"]) not in {"running", "detached"}
                or bool(int(row["cancel_requested"] or 0))
            ):
                return False
            next_pause_count = max(0, int(row["pause_count"] or 0)) + 1
            prefix = "budget_paused" if str(reason) == "budget_reached" else "paused"
            event_key = f"{prefix}#{next_pause_count}"
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='paused', pause_requested=0, resume_state=?, "
                "paused_at=?, pause_count=?, pause_reason=?, pause_event_key=?, updated_at=? "
                "WHERE job_id=? AND status IN ('running','detached') AND cancel_requested=0",
                (
                    serialized, timestamp, next_pause_count, _bounded(reason, 80),
                    event_key, timestamp, str(job_id),
                ),
            )
            return int(cursor.rowcount or 0) == 1

    def set_awaiting_confirmation(
        self, job_id: str, state_json: dict[str, Any], *, now: float | None = None,
    ) -> bool:
        """Persist a resumable confirmation boundary without executing the action."""

        timestamp = float(time.time() if now is None else now)
        serialized = json.dumps(state_json, ensure_ascii=True, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='awaiting_confirmation', pause_requested=0, "
                "resume_state=?, paused_at=?, updated_at=? "
                "WHERE job_id=? AND status IN ('running','detached') AND cancel_requested=0",
                (serialized, timestamp, timestamp, str(job_id)),
            )
            return int(cursor.rowcount or 0) == 1

    def claim_confirmation_resume(
        self, job_id: str, *, user_id: str,
    ) -> dict[str, Any] | None:
        """Claim an awaiting snapshot exactly once before confirm/decline continuation."""

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT resume_state,correction_queue FROM agent_jobs "
                "WHERE job_id=? AND user_id=? AND status='awaiting_confirmation'",
                (str(job_id), str(user_id)),
            ).fetchone()
            if row is None:
                return None
            try:
                state = json.loads(str(row["resume_state"] or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
            if not isinstance(state, dict):
                return None
            try:
                queued = [
                    str(item).strip()[:_CORRECTION_LIMIT]
                    for item in json.loads(str(row["correction_queue"] or "[]"))
                    if str(item).strip()
                ]
            except (TypeError, ValueError, json.JSONDecodeError):
                queued = []
            if queued:
                state["queued_corrections"] = queued[-_CORRECTION_QUEUE_LIMIT:]
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='detached', paused_at=0, correction_queue='[]', updated_at=? "
                "WHERE job_id=? AND user_id=? AND status='awaiting_confirmation'",
                (time.time(), str(job_id), str(user_id)),
            )
            return state if int(cursor.rowcount or 0) == 1 else None

    def claim_resume(self, job_id: str, *, user_id: str) -> dict[str, Any] | None:
        """Claim one paused snapshot without allowing concurrent duplicate resumes."""

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT resume_state,correction_queue FROM agent_jobs "
                "WHERE job_id=? AND user_id=? AND status='paused'",
                (str(job_id), str(user_id)),
            ).fetchone()
            if row is None:
                return None
            try:
                state = json.loads(str(row["resume_state"] or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
            if not isinstance(state, dict):
                return None
            try:
                queued = [
                    str(item).strip()[:_CORRECTION_LIMIT]
                    for item in json.loads(str(row["correction_queue"] or "[]"))
                    if str(item).strip()
                ]
            except (TypeError, ValueError, json.JSONDecodeError):
                queued = []
            if queued:
                state["queued_corrections"] = queued[-_CORRECTION_QUEUE_LIMIT:]
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='detached', pause_requested=0, paused_at=0, pause_reason='', "
                "warning='', correction_queue='[]', updated_at=? "
                "WHERE job_id=? AND user_id=? AND status='paused'",
                (time.time(), str(job_id), str(user_id)),
            )
            return state if int(cursor.rowcount or 0) == 1 else None

    def clear_resume_state(self, job_id: str, *, user_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE agent_jobs SET resume_state=NULL WHERE job_id=? AND user_id=?",
                (str(job_id), str(user_id)),
            )

    def claim_budget_resume(
        self, job_id: str, *, user_id: str, extension: int, hard_cap: int,
        finish: bool = False,
    ) -> dict[str, Any] | None:
        """Backward-compatible wrapper for claiming the current budget pause."""
        record = self.get(job_id)
        if record is None:
            return None
        claimed = self.claim_budget_action(
            job_id,
            user_id=user_id,
            event_key=record.event_key,
            action="finish" if finish else "extend",
            extension=extension,
            hard_cap=hard_cap,
        )
        return claimed.state if claimed.status == "claimed" else None

    def claim_budget_action(
        self, job_id: str, *, user_id: str, event_key: str, action: str,
        extension: int, hard_cap: int,
    ) -> AgentJobActionClaim:
        """Atomically apply at most one control action to one stable pause event."""

        clean_action = str(action or "").strip().lower()
        if clean_action not in {"extend", "finish", "cancel"}:
            return AgentJobActionClaim("invalid")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            handled = connection.execute(
                "SELECT action FROM agent_job_pause_actions WHERE job_id=? AND event_key=?",
                (str(job_id), str(event_key)),
            ).fetchone()
            if handled is not None:
                return AgentJobActionClaim("already_handled")
            row = connection.execute(
                "SELECT resume_state,pause_reason,pause_event_key FROM agent_jobs "
                "WHERE job_id=? AND user_id=? AND status='paused'",
                (str(job_id), str(user_id)),
            ).fetchone()
            if row is None:
                return AgentJobActionClaim("not_running")
            if (
                str(row["pause_reason"] or "") != "budget_reached"
                or str(row["pause_event_key"] or "") != str(event_key)
            ):
                return AgentJobActionClaim("event_mismatch")
            try:
                state = json.loads(str(row["resume_state"] or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                return AgentJobActionClaim("invalid_state")
            if not isinstance(state, dict):
                return AgentJobActionClaim("invalid_state")
            if clean_action == "finish":
                state["budget_finish_requested"] = True
            elif clean_action == "extend":
                cap = max(1, int(hard_cap))
                current_steps = max(0, int(state.get("budget_max_steps") or state.get("step_index") or 0))
                current_calls = max(0, int(state.get("budget_max_provider_calls") or state.get("provider_calls") or 0))
                if current_steps >= cap and current_calls >= cap:
                    return AgentJobActionClaim("hard_cap")
                amount = max(1, int(extension))
                state["budget_max_steps"] = min(cap, current_steps + amount)
                state["budget_max_provider_calls"] = min(cap, current_calls + amount)
            inserted = connection.execute(
                "INSERT OR IGNORE INTO agent_job_pause_actions(job_id,event_key,action,created_at) VALUES(?,?,?,?)",
                (str(job_id), str(event_key), clean_action, time.time()),
            )
            if int(inserted.rowcount or 0) != 1:
                return AgentJobActionClaim("already_handled")
            if clean_action == "cancel":
                cursor = connection.execute(
                    "UPDATE agent_jobs SET status='cancelled',result='cancelled_by_user',cancel_requested=0,"
                    "pause_requested=0,resume_state=NULL,paused_at=0,updated_at=? "
                    "WHERE job_id=? AND user_id=? AND status='paused' AND pause_event_key=?",
                    (time.time(), str(job_id), str(user_id), str(event_key)),
                )
                return AgentJobActionClaim("claimed") if int(cursor.rowcount or 0) == 1 else AgentJobActionClaim("not_running")
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='detached',paused_at=0,pause_reason='',resume_state=?,updated_at=? "
                "WHERE job_id=? AND user_id=? AND status='paused' AND pause_event_key=?",
                (
                    json.dumps(state, ensure_ascii=True, separators=(",", ":")), time.time(),
                    str(job_id), str(user_id), str(event_key),
                ),
            )
            return AgentJobActionClaim("claimed", state) if int(cursor.rowcount or 0) == 1 else AgentJobActionClaim("not_running")

    def stage_resume_state(
        self, job_id: str, state_json: dict[str, Any], *, user_id: str,
    ) -> bool:
        """Stage an internal continuation for the existing pause/resume runner."""

        serialized = json.dumps(state_json, ensure_ascii=True, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='paused', resume_state=?, paused_at=?, updated_at=? "
                "WHERE job_id=? AND user_id=? AND status='detached' AND cancel_requested=0",
                (serialized, time.time(), time.time(), str(job_id), str(user_id)),
            )
            return int(cursor.rowcount or 0) == 1

    def request_cancel(
        self, job_id: str, *, user_id: str, now: float | None = None,
    ) -> str:
        """Atomically request cancellation without revealing another user's job."""

        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT user_id,status FROM agent_jobs WHERE job_id=?",
                (str(job_id),),
            ).fetchone()
            if row is None or str(row["user_id"]) != str(user_id):
                return "not_found"
            status = str(row["status"])
            if status not in {"running", "detached", "paused", "awaiting_confirmation"}:
                return "not_running"
            if status in {"paused", "awaiting_confirmation"}:
                connection.execute(
                    "UPDATE agent_jobs SET status='cancelled', result='cancelled_by_user', "
                    "cancel_requested=0, pause_requested=0, resume_state=NULL, paused_at=0, updated_at=? "
                    "WHERE job_id=? AND user_id=? AND status=?",
                    (timestamp, str(job_id), str(user_id), status),
                )
            else:
                connection.execute(
                    "UPDATE agent_jobs SET cancel_requested=1, updated_at=? WHERE job_id=? AND user_id=?",
                    (timestamp, str(job_id), str(user_id)),
                )
            return "requested"

    def is_cancel_requested(self, job_id: str, *, user_id: str) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM agent_jobs WHERE job_id=? AND user_id=?",
                (str(job_id), str(user_id)),
            ).fetchone()
        return bool(row and int(row["cancel_requested"] or 0))

    def mark_notified(self, job_id: str) -> bool:
        """Atomically claim the one completion notice for a terminal job."""

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            inserted = connection.execute(
                "INSERT OR IGNORE INTO agent_job_notices(job_id,event_key,created_at) "
                "SELECT job_id,'terminal',? FROM agent_jobs "
                "WHERE job_id=? AND status IN ('done','error','cancelled')",
                (time.time(), str(job_id)),
            )
            if int(inserted.rowcount or 0) != 1:
                return False
            cursor = connection.execute(
                "UPDATE agent_jobs SET notified=1 "
                "WHERE job_id=? AND status IN ('done','error','cancelled')",
                (str(job_id),),
            )
            return int(cursor.rowcount or 0) == 1

    def mark_event_notified(self, job_id: str, event_key: str) -> bool:
        clean_event = _bounded(event_key, 120)
        if not clean_event:
            return False
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO agent_job_notices(job_id,event_key,created_at) "
                "SELECT job_id,?,? FROM agent_jobs WHERE job_id=?",
                (clean_event, time.time(), str(job_id)),
            )
            return int(cursor.rowcount or 0) == 1

    def get(self, job_id: str) -> AgentJobRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM agent_jobs WHERE job_id=?", (str(job_id),)).fetchone()
        return self._record(row)

    def list_for_user(self, user_id: str, *, limit: int = 20) -> tuple[AgentJobRecord, ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_jobs WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (str(user_id), max(1, min(100, int(limit)))),
            ).fetchall()
        return tuple(record for row in rows if (record := self._record(row)) is not None)

    def mark_stale_interrupted(self, *, stale_before: float, now: float | None = None) -> int:
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='error', result='worker_restart', pause_requested=0, "
                "resume_state=NULL, paused_at=0, updated_at=? "
                "WHERE status IN ('running','detached') AND updated_at < ?",
                (timestamp, float(stale_before)),
            )
            return max(0, int(cursor.rowcount or 0))

    def stale_paused(self, *, stale_before: float) -> tuple[AgentJobRecord, ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_jobs WHERE status IN ('paused','awaiting_confirmation') AND updated_at < ?",
                (float(stale_before),),
            ).fetchall()
        return tuple(record for row in rows if (record := self._record(row)) is not None)

    def cancel_stale_paused(self, job_id: str, *, now: float | None = None) -> bool:
        timestamp = float(time.time() if now is None else now)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE agent_jobs SET status='cancelled',result='stale_paused_timeout',resume_state=NULL,"
                "correction_queue='[]',pause_reason='',paused_at=0,updated_at=? "
                "WHERE job_id=? AND status IN ('paused','awaiting_confirmation')",
                (timestamp, str(job_id)),
            )
        return int(cursor.rowcount or 0) == 1

    def delete_terminal(self, job_id: str, *, user_id: str) -> str:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM agent_jobs WHERE job_id=? AND user_id=?", (str(job_id), str(user_id)),
            ).fetchone()
            if row is None:
                return "not_found"
            if str(row["status"]) not in {"done", "error", "cancelled"}:
                return "not_terminal"
            connection.execute("DELETE FROM agent_job_notices WHERE job_id=?", (str(job_id),))
            connection.execute("DELETE FROM agent_job_pause_actions WHERE job_id=?", (str(job_id),))
            connection.execute("DELETE FROM agent_jobs WHERE job_id=? AND user_id=?", (str(job_id), str(user_id)))
        return "deleted"

    def delete_terminal_for_user(self, user_id: str) -> int:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            ids = [str(row[0]) for row in connection.execute(
                "SELECT job_id FROM agent_jobs WHERE user_id=? AND status IN ('done','error','cancelled')",
                (str(user_id),),
            ).fetchall()]
            for job_id in ids:
                connection.execute("DELETE FROM agent_job_notices WHERE job_id=?", (job_id,))
                connection.execute("DELETE FROM agent_job_pause_actions WHERE job_id=?", (job_id,))
            connection.execute(
                "DELETE FROM agent_jobs WHERE user_id=? AND status IN ('done','error','cancelled')", (str(user_id),),
            )
        return len(ids)

    def purge_terminal_before(self, *, stale_before: float) -> int:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            ids = [str(row[0]) for row in connection.execute(
                "SELECT job_id FROM agent_jobs WHERE status IN ('done','error','cancelled') AND updated_at < ?",
                (float(stale_before),),
            ).fetchall()]
            for job_id in ids:
                connection.execute("DELETE FROM agent_job_notices WHERE job_id=?", (job_id,))
                connection.execute("DELETE FROM agent_job_pause_actions WHERE job_id=?", (job_id,))
            connection.execute(
                "DELETE FROM agent_jobs WHERE status IN ('done','error','cancelled') AND updated_at < ?",
                (float(stale_before),),
            )
        return len(ids)

    @staticmethod
    def _record(row: sqlite3.Row | None) -> AgentJobRecord | None:
        if row is None:
            return None
        try:
            steps = tuple(item for item in json.loads(str(row["step_log"] or "[]")) if isinstance(item, dict))
        except (TypeError, ValueError, json.JSONDecodeError):
            steps = ()
        try:
            resume_state = json.loads(str(row["resume_state"] or "")) if "resume_state" in row.keys() and row["resume_state"] else None
        except (TypeError, ValueError, json.JSONDecodeError):
            resume_state = None
        if not isinstance(resume_state, dict):
            resume_state = None
        try:
            detail_lines = tuple(
                _bounded(item, _DETAIL_LIMIT)
                for item in json.loads(str(row["detail_lines"] or "[]"))
                if str(item).strip()
            ) if "detail_lines" in row.keys() else ()
        except (TypeError, ValueError, json.JSONDecodeError):
            detail_lines = ()
        try:
            correction_queue = tuple(
                str(item).strip()[:_CORRECTION_LIMIT]
                for item in json.loads(str(row["correction_queue"] or "[]"))
                if str(item).strip()
            ) if "correction_queue" in row.keys() else ()
        except (TypeError, ValueError, json.JSONDecodeError):
            correction_queue = ()
        try:
            usage = json.loads(str(row["usage"] or "{}")) if "usage" in row.keys() else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            usage = {}
        if not isinstance(usage, dict):
            usage = {}
        status = str(row["status"])
        if status == "paused":
            event_key = str(row["pause_event_key"] or "") if "pause_event_key" in row.keys() else ""
        elif status == "awaiting_confirmation":
            event_key = "confirmation#" + str((resume_state or {}).get("pending_token") or "")
        elif status in {"done", "error", "cancelled"}:
            event_key = "terminal"
        else:
            event_key = ""
        return AgentJobRecord(
            job_id=str(row["job_id"]), user_id=str(row["user_id"]), goal=str(row["goal"]),
            status=status, step_log=steps, result=str(row["result"] or ""),
            created_at=float(row["created_at"]), updated_at=float(row["updated_at"]),
            worker_id=str(row["worker_id"] or ""),
            cancel_requested=bool(int(row["cancel_requested"] or 0)),
            warning=str(row["warning"] or "") if "warning" in row.keys() else "",
            notified=bool(int(row["notified"] or 0)) if "notified" in row.keys() else False,
            pause_requested=bool(int(row["pause_requested"] or 0)) if "pause_requested" in row.keys() else False,
            resume_state=resume_state,
            paused_at=float(row["paused_at"] or 0) if "paused_at" in row.keys() else 0.0,
            pause_count=max(0, int(row["pause_count"] or 0)) if "pause_count" in row.keys() else 0,
            detail_lines=detail_lines[-_DETAIL_LINES_LIMIT:],
            correction_queue=correction_queue[-_CORRECTION_QUEUE_LIMIT:],
            pause_reason=str(row["pause_reason"] or "") if "pause_reason" in row.keys() else "",
            event_key=event_key,
            usage=usage,
        )
