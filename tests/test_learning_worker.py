from __future__ import annotations

import asyncio

import pytest

import aria.core.learning_worker as learning_worker
from aria.core.learning_worker import classify_learning_worker_failure
from aria.core.learning_worker import enqueue_learning_job
from aria.core.learning_worker import flush_learning_worker_jobs
from aria.core.learning_worker import get_learning_worker_audit_summary
from aria.core.learning_worker import get_learning_worker_job
from aria.core.learning_worker import get_learning_worker_status
from aria.core.learning_worker import reset_learning_worker_state
from aria.core.learning_worker import retry_learning_job


@pytest.fixture(autouse=True)
def _isolated_worker_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(learning_worker, "_AUDIT_PATH", tmp_path / "learning_worker_audit.jsonl")


def test_learning_worker_records_completed_job() -> None:
    async def _run() -> dict[str, object]:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            return {"captured": True, "reason": "captured"}

        accepted = enqueue_learning_job(
            job_type="runtime_outcome",
            user_id="u1",
            source="test",
            artifact_type="procedure_candidate",
            request_id="req-1",
            factory=job,
        )
        await asyncio.sleep(0)
        return accepted

    accepted = asyncio.run(_run())
    status = get_learning_worker_status()

    assert accepted["accepted"] is True
    assert status["counts"]["completed"] == 1
    assert status["recent"][0]["captured"] is True
    assert status["recent"][0]["artifact_type"] == "procedure_candidate"
    assert status["budget"]["used_tokens"] == 0


def test_learning_worker_records_failed_job() -> None:
    async def _run() -> None:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            raise RuntimeError("qdrant unavailable")

        enqueue_learning_job(
            job_type="runtime_outcome",
            user_id="u1",
            source="test",
            factory=job,
        )
        await asyncio.sleep(0)

    asyncio.run(_run())
    status = get_learning_worker_status()

    assert status["counts"]["failed"] == 1
    assert "qdrant unavailable" in status["recent"][0]["error"]


def test_learning_worker_rejects_without_running_event_loop() -> None:
    reset_learning_worker_state()

    async def job() -> dict[str, object]:
        return {"captured": True}

    result = enqueue_learning_job(
        job_type="runtime_outcome",
        user_id="u1",
        source="test",
        factory=job,
    )
    status = get_learning_worker_status()

    assert result["accepted"] is False
    assert result["reason"] == "no_running_event_loop"
    assert status["counts"]["rejected"] == 1


def test_learning_worker_job_detail_marks_failed_job_retryable() -> None:
    async def _run() -> str:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            raise RuntimeError("temporary qdrant outage")

        result = enqueue_learning_job(
            job_type="runtime_outcome",
            user_id="u1",
            source="test",
            factory=job,
        )
        await asyncio.sleep(0)
        return str(result["job_id"])

    job_id = asyncio.run(_run())
    detail = get_learning_worker_job(job_id)

    assert detail is not None
    assert detail["status"] == "failed"
    assert detail["retryable"] is True
    assert detail["retry_after_seconds"] >= 2


def test_learning_worker_retry_respects_backoff_and_force_retries() -> None:
    async def _run() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        reset_learning_worker_state()
        attempts = {"count": 0}

        async def job() -> dict[str, object]:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("first attempt failed")
            return {"captured": True, "reason": "captured"}

        result = enqueue_learning_job(
            job_type="runtime_outcome",
            user_id="u1",
            source="test",
            factory=job,
        )
        await asyncio.sleep(0)
        blocked = retry_learning_job(job_id=str(result["job_id"]), force=False)
        forced = retry_learning_job(job_id=str(result["job_id"]), force=True)
        await asyncio.sleep(0)
        detail = get_learning_worker_job(str(result["job_id"])) or {}
        return blocked, forced, detail

    blocked, forced, detail = asyncio.run(_run())

    assert blocked["accepted"] is False
    assert blocked["reason"] == "retry_backoff_active"
    assert forced["accepted"] is True
    assert detail["status"] == "completed"
    assert detail["captured"] is True


def test_learning_worker_flush_removes_finished_jobs_only() -> None:
    async def _run() -> None:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            return {"captured": True}

        enqueue_learning_job(job_type="runtime_outcome", user_id="u1", source="test", factory=job)
        await asyncio.sleep(0)

    asyncio.run(_run())
    result = flush_learning_worker_jobs(scope="finished")
    status = get_learning_worker_status()

    assert result["removed_count"] == 1
    assert status["counts"]["completed"] == 0


def test_learning_worker_records_usage_budget_from_result_metadata() -> None:
    async def _run() -> None:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            return {
                "captured": True,
                "candidate": {"metadata": {"classification_usage": {"total_tokens": 7}}},
                "eval": {"metadata": {"validation_usage": {"total_tokens": 11, "cost_usd": 0.012}}},
            }

        enqueue_learning_job(job_type="runtime_outcome", user_id="u1", source="test", factory=job)
        await asyncio.sleep(0)

    asyncio.run(_run())
    status = get_learning_worker_status()
    detail = status["recent"][0]

    assert detail["consumed_tokens"] == 18
    assert detail["consumed_cost_usd"] == 0.012
    assert status["budget"]["used_tokens"] == 18
    assert status["budget"]["used_cost_usd"] == 0.012


def test_learning_worker_rejects_job_over_token_budget() -> None:
    reset_learning_worker_state()

    async def job() -> dict[str, object]:
        return {"captured": True}

    result = enqueue_learning_job(
        job_type="runtime_outcome",
        user_id="u1",
        source="test",
        factory=job,
        estimated_tokens=999_999,
    )
    status = get_learning_worker_status()

    assert result["accepted"] is False
    assert result["reason"] == "learning_budget_exhausted"
    assert status["counts"]["rejected"] == 1
    assert status["budget"]["rejected_count"] == 1


def test_learning_worker_retry_stops_after_max_attempts() -> None:
    async def _run() -> dict[str, object]:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            raise RuntimeError("still broken")

        result = enqueue_learning_job(job_type="runtime_outcome", user_id="u1", source="test", factory=job)
        await asyncio.sleep(0)
        first_retry = retry_learning_job(job_id=str(result["job_id"]), force=True)
        await asyncio.sleep(0)
        second_retry = retry_learning_job(job_id=str(result["job_id"]), force=True)
        await asyncio.sleep(0)
        blocked = retry_learning_job(job_id=str(result["job_id"]), force=True)
        return blocked

    blocked = asyncio.run(_run())

    assert blocked["accepted"] is False
    assert blocked["reason"] == "max_attempts_reached"


def test_learning_worker_writes_runtime_audit_summary() -> None:
    async def _run() -> None:
        reset_learning_worker_state(clear_audit=True)

        async def job() -> dict[str, object]:
            raise RuntimeError("qdrant unavailable")

        enqueue_learning_job(job_type="runtime_outcome", user_id="u1", source="test", factory=job)
        await asyncio.sleep(0)

    asyncio.run(_run())
    summary = get_learning_worker_audit_summary()

    assert summary["count"] == 1
    assert summary["by_status"]["failed"] == 1
    assert summary["by_failure_category"]["qdrant"] == 1
    assert summary["rows"][0]["event"] == "job_finished"


def test_learning_worker_failure_classifier_groups_operational_causes() -> None:
    assert classify_learning_worker_failure({"reason": "learning_budget_exhausted"}) == "budget"
    assert classify_learning_worker_failure({"error": "qdrant unavailable"}) == "qdrant"
    assert classify_learning_worker_failure({"error": "provider rate limit"}) == "provider"
    assert classify_learning_worker_failure({"source": "learning_validator"}) == "validator"
