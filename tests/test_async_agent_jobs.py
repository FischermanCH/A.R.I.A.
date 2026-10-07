from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from aria.modules.pipeline_contracts.result import PipelineResult
import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore


def _result(text: str = "done") -> PipelineResult:
    return PipelineResult(
        request_id="native-job", text=text,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        intents=["chat"], skill_errors=[], router_level=2, duration_ms=1,
    )


def _pipeline(tmp_path: Path, *, budget: float = 0.02) -> Pipeline:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(
        agentic_loop=SimpleNamespace(enabled=True, async_agent_job_sync_budget_seconds=budget),
    )
    pipeline._project_root = tmp_path
    pipeline._routing_debug_enabled = lambda: False
    pipeline._finalize_process_result = lambda result, **_kwargs: result
    return pipeline


def test_agent_job_store_is_worker_shared_bounded_and_user_scoped(tmp_path: Path) -> None:
    path = tmp_path / "data" / "runtime" / "agent_jobs.sqlite3"
    writer = AgentJobStore(path)
    writer.create(job_id="job-a", user_id="alice", goal="A" * 900, worker_id="worker-a", now=10)
    writer.append_step("job-a", step_index=1, tool_names=["file_read"], outcome_summary="x" * 2000, now=11)
    writer.set_terminal("job-a", status="done", result="result " * 3000, now=12)
    writer.create(job_id="job-b", user_id="bob", goal="private", now=13)

    reader = AgentJobStore(path)
    alice = reader.list_for_user("alice")

    assert [row.job_id for row in alice] == ["job-a"]
    assert len(alice[0].goal) <= 600
    assert len(alice[0].result) <= 12_000
    assert alice[0].step_log == ({
        "step_index": 1,
        "tool_names": ["file_read"],
        "outcome_summary": alice[0].step_log[0]["outcome_summary"],
    },)
    assert len(alice[0].step_log[0]["outcome_summary"]) <= 800


def test_agent_job_store_migrates_alpha961_schema_without_losing_rows(tmp_path: Path) -> None:
    path = tmp_path / "agent_jobs.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE agent_jobs (job_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,goal TEXT NOT NULL,"
            "status TEXT NOT NULL,step_log TEXT NOT NULL DEFAULT '[]',result TEXT NOT NULL DEFAULT '',"
            "created_at REAL NOT NULL,updated_at REAL NOT NULL,worker_id TEXT NOT NULL DEFAULT '')"
        )
        connection.execute(
            "INSERT INTO agent_jobs VALUES(?,?,?,?,?,?,?,?,?)",
            ("legacy", "alice", "goal", "done", "[]", "ok", 1.0, 2.0, "worker"),
        )

    store = AgentJobStore(path)
    record = store.get("legacy")

    assert record is not None
    assert record.result == "ok"
    assert record.cancel_requested is False
    assert record.warning == ""
    assert record.notified is False


def test_slow_turn_detaches_continues_and_finishes(monkeypatch, tmp_path: Path) -> None:
    finished = asyncio.Event()

    async def fake_native(*_args, **kwargs):
        callback = kwargs["step_callback"]
        await callback(1, ("mcp__demo__step",), "created object")
        await asyncio.sleep(0.06)
        await callback(2, ("mcp__demo__step",), "finished object")
        finished.set()
        return _result("real final result")

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

    async def scenario() -> tuple[PipelineResult, object]:
        pipeline = _pipeline(tmp_path)
        def finalize(result: PipelineResult, **_kwargs) -> PipelineResult:
            if result.text == "real final result":
                result.text = "guarded final result"
            return result
        pipeline._finalize_process_result = finalize
        immediate = await pipeline.process("build several objects", user_id="alice", language="en")
        assert "Job ID" in immediate.text
        job_id = immediate.text.split("Job ID: ", 1)[1].split()[0].rstrip(".")
        await asyncio.wait_for(finished.wait(), timeout=1)
        await asyncio.sleep(0)
        return immediate, pipeline.get_agent_job_store().get(job_id)

    immediate, record = asyncio.run(scenario())

    assert "status" in immediate.text.lower()
    assert record is not None
    assert record.status == "done"
    assert record.result == "guarded final result"
    assert [step["step_index"] for step in record.step_log] == [1, 2]


def test_fast_and_confirmation_turns_do_not_create_jobs(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def fake_native(*_args, **kwargs):
        calls.append(str(kwargs.get("confirmation_token") or ""))
        return _result("unchanged")

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

    async def scenario() -> tuple[PipelineResult, PipelineResult, Pipeline]:
        pipeline = _pipeline(tmp_path, budget=0.5)
        fast = await pipeline.process("hello", user_id="alice")
        confirmed = await pipeline.process("confirm", user_id="alice", confirmation_token="na-token")
        return fast, confirmed, pipeline

    fast, confirmed, pipeline = asyncio.run(scenario())

    assert fast.text == confirmed.text == "unchanged"
    assert calls == ["", "na-token"]
    assert pipeline.get_agent_job_store().list_for_user("alice") == ()


def test_startup_sweep_marks_only_stale_inflight_rows(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "agent_jobs.sqlite3")
    store.create(job_id="old", user_id="alice", goal="old", status="detached", now=10)
    store.create(job_id="fresh", user_id="alice", goal="fresh", status="running", now=90)
    store.create(job_id="done", user_id="alice", goal="done", status="done", now=5)

    assert store.mark_stale_interrupted(stale_before=50, now=100) == 1
    assert store.get("old").status == "error"
    assert store.get("old").result == "worker_restart"
    assert store.get("fresh").status == "running"
    assert store.get("done").status == "done"


def test_cancel_signal_is_user_scoped_and_finished_jobs_are_noop(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "agent_jobs.sqlite3")
    store.create(job_id="active", user_id="alice", goal="active", status="detached")
    store.create(job_id="done", user_id="alice", goal="done", status="done")

    assert store.request_cancel("active", user_id="bob") == "not_found"
    assert store.is_cancel_requested("active", user_id="alice") is False
    assert store.request_cancel("done", user_id="alice") == "not_running"
    assert store.request_cancel("active", user_id="alice") == "requested"
    assert store.is_cancel_requested("active", user_id="alice") is True


def test_detached_job_cancels_at_next_step_boundary(monkeypatch, tmp_path: Path) -> None:
    continue_current_tool = asyncio.Event()
    reached_next_tool = False

    async def fake_native(*_args, **kwargs):
        nonlocal reached_next_tool
        callback = kwargs["step_callback"]
        await callback(1, ("mcp__demo__first",), "first object created")
        await continue_current_tool.wait()
        await callback(2, ("mcp__demo__current",), "current object created")
        reached_next_tool = True
        await callback(3, ("mcp__demo__later",), "must not run")
        return _result("must not finish")

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

    async def scenario():  # noqa: ANN202
        pipeline = _pipeline(tmp_path, budget=0.01)
        immediate = await pipeline.process("build a scene", user_id="alice", language="en")
        job_id = immediate.text.split("Job ID: ", 1)[1].split()[0].rstrip(".")
        assert pipeline.request_agent_job_cancel("bob", job_id) == "not_found"
        assert pipeline.request_agent_job_cancel("alice", job_id) == "requested"
        continue_current_tool.set()
        for _ in range(100):
            record = pipeline.get_agent_job_store().get(job_id)
            if record is not None and record.status == "cancelled":
                return record
            await asyncio.sleep(0.01)
        raise AssertionError("detached job did not reach cancelled status")

    record = asyncio.run(scenario())

    assert reached_next_tool is False
    assert record.status == "cancelled"
    assert record.result == "cancelled_by_user"
    assert [step["step_index"] for step in record.step_log] == [1, 2]
