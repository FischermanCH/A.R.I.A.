from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

LearningJobFactory = Callable[[], Awaitable[dict[str, Any] | None]]

_MAX_RUNNING_JOBS = 32
_HISTORY_LIMIT = 60
_MAX_ATTEMPTS = 3
_DEFAULT_ESTIMATED_TOKENS = 1500
_MAX_RUNTIME_TOKENS = 120_000
_MAX_RUNTIME_COST_USD = 2.0
_JOBS: dict[str, dict[str, Any]] = {}
_FACTORIES: dict[str, LearningJobFactory] = {}
_BUDGET = {"tokens": 0, "cost_usd": 0.0, "rejected": 0}
_AUDIT_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime" / "learning_worker_audit.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact(value: Any, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def classify_learning_worker_failure(job: dict[str, Any]) -> str:
    reason = str(job.get("reason", "") or "").strip().lower()
    error = str(job.get("error", "") or "").strip().lower()
    source = str(job.get("source", "") or "").strip().lower()
    text = f"{reason} {error} {source}"
    if "budget" in text or "token" in text or "cost" in text:
        return "budget"
    if "qdrant" in text or "memory" in text or "store" in text or "collection" in text:
        return "qdrant"
    if "llm" in text or "model" in text or "provider" in text or "rate limit" in text or "timeout" in text:
        return "provider"
    if "validator" in text or "eval" in text or "classification" in text:
        return "validator"
    if "event loop" in text or "worker" in text or "queue" in text:
        return "worker"
    if "route" in text or "http" in text or "form" in text:
        return "route"
    return "unknown"


def _running_count() -> int:
    return sum(1 for job in _JOBS.values() if str(job.get("status")) in {"queued", "running"})


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _retry_delay_seconds(attempts: int) -> int:
    return min(300, max(2, 2 ** max(1, int(attempts or 1))))


def _seconds_until(value: Any) -> int:
    parsed = _parse_iso(value)
    if parsed is None:
        return 0
    return max(0, int((parsed - datetime.now(timezone.utc)).total_seconds()))


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _usage_totals(value: Any) -> dict[str, float]:
    totals = {"tokens": 0.0, "cost_usd": 0.0}
    seen: set[int] = set()

    def visit(item: Any) -> None:
        marker = id(item)
        if marker in seen:
            return
        if isinstance(item, dict):
            seen.add(marker)
            if "total_tokens" in item:
                totals["tokens"] += _safe_int(item.get("total_tokens"))
            if "cost_usd" in item:
                totals["cost_usd"] += _safe_float(item.get("cost_usd"))
            elif "total_cost_usd" in item:
                totals["cost_usd"] += _safe_float(item.get("total_cost_usd"))
            for value in item.values():
                visit(value)
        elif isinstance(item, list):
            seen.add(marker)
            for value in item:
                visit(value)

    visit(value)
    return totals


def _budget_status(extra_estimated_tokens: int = 0) -> dict[str, Any]:
    used_tokens = int(_BUDGET["tokens"])
    used_cost = float(_BUDGET["cost_usd"])
    projected_tokens = used_tokens + max(0, int(extra_estimated_tokens or 0))
    token_remaining = max(0, _MAX_RUNTIME_TOKENS - used_tokens)
    cost_remaining = max(0.0, _MAX_RUNTIME_COST_USD - used_cost)
    return {
        "max_runtime_tokens": _MAX_RUNTIME_TOKENS,
        "max_runtime_cost_usd": _MAX_RUNTIME_COST_USD,
        "used_tokens": used_tokens,
        "used_cost_usd": round(used_cost, 8),
        "remaining_tokens": token_remaining,
        "remaining_cost_usd": round(cost_remaining, 8),
        "rejected_count": int(_BUDGET["rejected"]),
        "projected_tokens": projected_tokens,
        "tokens_exhausted": projected_tokens > _MAX_RUNTIME_TOKENS,
        "cost_exhausted": used_cost >= _MAX_RUNTIME_COST_USD,
    }


def _budget_allows(estimated_tokens: int) -> bool:
    status = _budget_status(extra_estimated_tokens=estimated_tokens)
    return not bool(status["tokens_exhausted"] or status["cost_exhausted"])


def _audit_payload(job: dict[str, Any], *, event: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "event": _compact(event, limit=80),
        "recorded_at": _now_iso(),
        "job_id": str(job.get("job_id", "") or ""),
        "job_type": _compact(job.get("job_type"), limit=80),
        "user_id": _compact(job.get("user_id"), limit=120),
        "source": _compact(job.get("source"), limit=120),
        "artifact_type": _compact(job.get("artifact_type"), limit=120),
        "status": _compact(job.get("status"), limit=80),
        "reason": _compact(job.get("reason"), limit=160),
        "failure_category": classify_learning_worker_failure(job),
        "attempts": _safe_int(job.get("attempts")),
        "estimated_tokens": _safe_int(job.get("estimated_tokens")),
        "consumed_tokens": _safe_int(job.get("consumed_tokens")),
        "consumed_cost_usd": round(_safe_float(job.get("consumed_cost_usd")), 8),
        "budget_state": _compact(job.get("budget_state"), limit=80),
        "created_at": _compact(job.get("created_at"), limit=80),
        "started_at": _compact(job.get("started_at"), limit=80),
        "finished_at": _compact(job.get("finished_at"), limit=80),
    }


def _record_audit(job: dict[str, Any], *, event: str) -> None:
    payload = _audit_payload(job, event=event)
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return


def load_learning_worker_audit(*, limit: int = 50) -> list[dict[str, Any]]:
    if not _AUDIT_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = _AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        if len(rows) >= max(1, min(int(limit or 50), 500)):
            break
    return rows


def get_learning_worker_audit_summary(*, limit: int = 100) -> dict[str, Any]:
    rows = load_learning_worker_audit(limit=limit)
    by_status: dict[str, int] = {}
    by_failure_category: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status", "") or "unknown")
        category = str(row.get("failure_category", "") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_failure_category[category] = by_failure_category.get(category, 0) + 1
    return {
        "path": str(_AUDIT_PATH),
        "count": len(rows),
        "rows": rows[:10],
        "by_status": by_status,
        "by_failure_category": by_failure_category,
    }


def _trim_history() -> None:
    finished = [
        job
        for job in _JOBS.values()
        if str(job.get("status")) in {"completed", "failed", "rejected"}
    ]
    if len(finished) <= _HISTORY_LIMIT:
        return
    finished.sort(key=lambda item: str(item.get("finished_at") or item.get("created_at") or ""))
    for job in finished[: len(finished) - _HISTORY_LIMIT]:
        job_id = str(job.get("job_id") or "")
        if job_id:
            _JOBS.pop(job_id, None)


async def _run_learning_job(job_id: str, factory: LearningJobFactory) -> None:
    job = _JOBS.get(job_id)
    if not job:
        return
    job["status"] = "running"
    job["started_at"] = _now_iso()
    try:
        result = await factory()
    except Exception as exc:  # noqa: BLE001
        attempts = int(job.get("attempts", 0) or 0)
        delay = _retry_delay_seconds(attempts + 1)
        job["status"] = "failed"
        job["error"] = _compact(exc)
        job["retry_after_seconds"] = delay
        job["next_retry_at"] = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
    else:
        job["status"] = "completed"
        if isinstance(result, dict):
            job["captured"] = bool(result.get("captured", False))
            job["reason"] = _compact(result.get("reason"), limit=120)
            usage = _usage_totals(result)
            consumed_tokens = int(usage["tokens"])
            consumed_cost = float(usage["cost_usd"])
            job["consumed_tokens"] = consumed_tokens
            job["consumed_cost_usd"] = round(consumed_cost, 8)
            _BUDGET["tokens"] += consumed_tokens
            _BUDGET["cost_usd"] += consumed_cost
            if "recipe_candidate" in result:
                job["recipe_candidate"] = dict(result.get("recipe_candidate") or {})
            if "procedure_skill" in result:
                job["procedure_skill"] = dict(result.get("procedure_skill") or {})
    finally:
        job["finished_at"] = _now_iso()
        job["failure_category"] = classify_learning_worker_failure(job)
        if str(job.get("status")) == "completed":
            _FACTORIES.pop(job_id, None)
        _record_audit(job, event="job_finished")
        _trim_history()


def enqueue_learning_job(
    *,
    job_type: str,
    user_id: str,
    source: str,
    factory: LearningJobFactory,
    artifact_type: str = "",
    request_id: str = "",
    session_id: str = "",
    summary: str = "",
    estimated_tokens: int = _DEFAULT_ESTIMATED_TOKENS,
) -> dict[str, Any]:
    job_id = uuid4().hex
    safe_estimated_tokens = max(0, int(estimated_tokens or 0))
    base = {
        "job_id": job_id,
        "job_type": _compact(job_type, limit=80) or "learning_outcome",
        "user_id": _compact(user_id, limit=120) or "web",
        "source": _compact(source, limit=120) or "learning_worker",
        "artifact_type": _compact(artifact_type, limit=120),
        "request_id": _compact(request_id, limit=160),
        "session_id": _compact(session_id, limit=160),
        "summary": _compact(summary, limit=260),
        "created_at": _now_iso(),
        "started_at": "",
        "finished_at": "",
        "status": "queued",
        "captured": False,
        "reason": "",
        "error": "",
        "attempts": 1,
        "max_attempts": _MAX_ATTEMPTS,
        "retryable": True,
        "retry_after_seconds": 0,
        "next_retry_at": "",
        "estimated_tokens": safe_estimated_tokens,
        "consumed_tokens": 0,
        "consumed_cost_usd": 0.0,
        "budget_state": "ok",
    }
    if not _budget_allows(safe_estimated_tokens):
        base["status"] = "rejected"
        base["reason"] = "learning_budget_exhausted"
        base["budget_state"] = "blocked"
        base["failure_category"] = classify_learning_worker_failure(base)
        base["finished_at"] = _now_iso()
        _JOBS[job_id] = base
        _BUDGET["rejected"] += 1
        _record_audit(base, event="job_rejected")
        _trim_history()
        return {"accepted": False, "job_id": job_id, "reason": "learning_budget_exhausted"}
    if _running_count() >= _MAX_RUNNING_JOBS:
        base["status"] = "rejected"
        base["reason"] = "learning_worker_busy"
        base["finished_at"] = _now_iso()
        base["failure_category"] = classify_learning_worker_failure(base)
        _JOBS[job_id] = base
        _FACTORIES[job_id] = factory
        _record_audit(base, event="job_rejected")
        _trim_history()
        return {"accepted": False, "job_id": job_id, "reason": "learning_worker_busy"}
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        base["status"] = "rejected"
        base["reason"] = "no_running_event_loop"
        base["finished_at"] = _now_iso()
        base["failure_category"] = classify_learning_worker_failure(base)
        _JOBS[job_id] = base
        _FACTORIES[job_id] = factory
        _record_audit(base, event="job_rejected")
        _trim_history()
        return {"accepted": False, "job_id": job_id, "reason": "no_running_event_loop"}
    _JOBS[job_id] = base
    _FACTORIES[job_id] = factory
    task = loop.create_task(_run_learning_job(job_id, factory))

    def _consume_result(done: asyncio.Task[None]) -> None:
        try:
            done.result()
        except Exception:
            pass

    task.add_done_callback(_consume_result)
    return {"accepted": True, "job_id": job_id, "reason": "queued"}


def retry_learning_job(*, job_id: str, force: bool = False) -> dict[str, Any]:
    clean_job_id = str(job_id or "").strip()
    job = _JOBS.get(clean_job_id)
    if not job:
        return {"accepted": False, "job_id": clean_job_id, "reason": "job_not_found"}
    if str(job.get("status")) in {"queued", "running"}:
        return {"accepted": False, "job_id": clean_job_id, "reason": "job_already_running"}
    attempts = int(job.get("attempts", 1) or 1)
    if attempts >= int(job.get("max_attempts", _MAX_ATTEMPTS) or _MAX_ATTEMPTS):
        return {"accepted": False, "job_id": clean_job_id, "reason": "max_attempts_reached"}
    factory = _FACTORIES.get(clean_job_id)
    if factory is None:
        return {"accepted": False, "job_id": clean_job_id, "reason": "job_not_retryable"}
    retry_wait = _seconds_until(job.get("next_retry_at"))
    if retry_wait > 0 and not force:
        return {
            "accepted": False,
            "job_id": clean_job_id,
            "reason": "retry_backoff_active",
            "retry_after_seconds": retry_wait,
        }
    if _running_count() >= _MAX_RUNNING_JOBS:
        return {"accepted": False, "job_id": clean_job_id, "reason": "learning_worker_busy"}
    estimated_tokens = int(job.get("estimated_tokens", _DEFAULT_ESTIMATED_TOKENS) or 0)
    if not _budget_allows(estimated_tokens):
        job["budget_state"] = "blocked"
        job["failure_category"] = classify_learning_worker_failure(job)
        _BUDGET["rejected"] += 1
        _record_audit(job, event="retry_rejected")
        return {"accepted": False, "job_id": clean_job_id, "reason": "learning_budget_exhausted"}
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {"accepted": False, "job_id": clean_job_id, "reason": "no_running_event_loop"}

    attempts = int(job.get("attempts", 1) or 1) + 1
    delay = _retry_delay_seconds(attempts)
    job.update(
        {
            "status": "queued",
            "started_at": "",
            "finished_at": "",
            "captured": False,
            "reason": "retry_queued",
            "error": "",
            "attempts": attempts,
            "retry_after_seconds": delay,
            "next_retry_at": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
            "budget_state": "ok",
        }
    )
    task = loop.create_task(_run_learning_job(clean_job_id, factory))

    def _consume_result(done: asyncio.Task[None]) -> None:
        try:
            done.result()
        except Exception:
            pass

    task.add_done_callback(_consume_result)
    _record_audit(job, event="job_retry_queued")
    return {"accepted": True, "job_id": clean_job_id, "reason": "retry_queued"}


def get_learning_worker_job(job_id: str) -> dict[str, Any] | None:
    clean_job_id = str(job_id or "").strip()
    job = _JOBS.get(clean_job_id)
    if not job:
        return None
    snapshot = dict(job)
    snapshot["retryable"] = clean_job_id in _FACTORIES and str(job.get("status")) in {"failed", "rejected"}
    snapshot["retry_wait_seconds"] = _seconds_until(job.get("next_retry_at"))
    snapshot["failure_category"] = classify_learning_worker_failure(snapshot)
    return snapshot


def flush_learning_worker_jobs(*, scope: str = "finished") -> dict[str, Any]:
    clean_scope = str(scope or "finished").strip().lower()
    if clean_scope not in {"finished", "failed", "all"}:
        clean_scope = "finished"
    removed: list[str] = []
    for job_id, job in list(_JOBS.items()):
        status = str(job.get("status") or "")
        if status in {"queued", "running"} and clean_scope != "all":
            continue
        if clean_scope == "failed" and status not in {"failed", "rejected"}:
            continue
        if clean_scope == "finished" and status not in {"completed", "failed", "rejected"}:
            continue
        removed.append(job_id)
        _JOBS.pop(job_id, None)
        _FACTORIES.pop(job_id, None)
    result = {"scope": clean_scope, "removed_count": len(removed), "removed_job_ids": removed[:20]}
    _record_audit(
        {
            "job_id": "flush",
            "job_type": "worker_maintenance",
            "status": "completed",
            "reason": f"flush_{clean_scope}_{len(removed)}",
            "budget_state": "ok",
        },
        event="history_flushed",
    )
    return result


def get_learning_worker_status(*, limit: int = 8) -> dict[str, Any]:
    jobs = sorted(_JOBS.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True)
    counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "rejected": 0}
    for job in jobs:
        status = str(job.get("status") or "queued")
        if status in counts:
            counts[status] += 1
    return {
        "enabled": True,
        "max_running": _MAX_RUNNING_JOBS,
        "max_attempts": _MAX_ATTEMPTS,
        "budget": _budget_status(),
        "audit": get_learning_worker_audit_summary(limit=60),
        "counts": counts,
        "running": counts["queued"] + counts["running"],
        "recent": [dict(job) for job in jobs[: max(1, min(int(limit or 8), 20))]],
    }


def reset_learning_worker_state(*, clear_audit: bool = False) -> None:
    _JOBS.clear()
    _FACTORIES.clear()
    _BUDGET["tokens"] = 0
    _BUDGET["cost_usd"] = 0.0
    _BUDGET["rejected"] = 0
    if clear_audit:
        try:
            _AUDIT_PATH.unlink(missing_ok=True)
        except OSError:
            pass
