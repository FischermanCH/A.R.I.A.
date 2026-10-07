from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import aria.main as main_mod
import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.chat_execution_composition.routes import ChatExecutionRouteDeps
from aria.modules.chat_history_storage.store import FileChatHistoryStore
from aria.modules.native_agent.handler import _normalize_recent_history_messages
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline


def _result(
    text: str = "scene complete",
    *,
    warning: bool = False,
) -> PipelineResult:
    details = [
        "Routing Debug: native_agent_position=pre_arbitration outcome=final_answer "
        "provider_calls=3 used_tools=mcp__blender__execute_blender_code reason=-",
        "LLM usage: input_tokens=120 output_tokens=30 cache_read=80 cache_write=10 tools=1",
    ]
    if warning:
        details.append("Routing Debug: native_agent_summary_warning=yes")
    return PipelineResult(
        request_id="native-job",
        text=text,
        usage={"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        intents=["chat"],
        skill_errors=[],
        router_level=2,
        duration_ms=2500,
        total_cost_usd=0.012345,
        detail_lines=details,
    )


def _pipeline(tmp_path: Path, *, budget: float = 0.005) -> Pipeline:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(
        agentic_loop=SimpleNamespace(enabled=True, async_agent_job_sync_budget_seconds=budget),
    )
    pipeline._project_root = tmp_path
    pipeline._routing_debug_enabled = lambda: False
    pipeline._finalize_process_result = lambda result, **_kwargs: result
    pipeline._agent_job_tasks = set()
    pipeline._agent_job_store = None
    pipeline._agent_job_store_path = None
    pipeline._agent_job_notifier = None
    return pipeline


async def _wait_terminal(pipeline: Pipeline, job_id: str) -> object:
    for _ in range(200):
        record = pipeline.get_agent_job_store().get(job_id)
        if record is not None and record.status in {"done", "error", "cancelled"}:
            await asyncio.sleep(0)
            return record
        await asyncio.sleep(0.005)
    raise AssertionError("job did not reach a terminal state")


def _job_id(result: PipelineResult) -> str:
    assert result.agent_job_id
    return result.agent_job_id


def test_detached_message_has_machine_id_and_clickable_markdown_link(monkeypatch, tmp_path: Path) -> None:
    release = asyncio.Event()

    async def fake_native(*_args, **_kwargs):
        await release.wait()
        return _result()

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

    async def scenario() -> PipelineResult:
        pipeline = _pipeline(tmp_path)
        detached = await pipeline.process("build scene", user_id="alice", language="en")
        release.set()
        await _wait_terminal(pipeline, _job_id(detached))
        return detached

    detached = asyncio.run(scenario())
    job_id = _job_id(detached)

    assert f"[View job →](/jobs/panel#job-{job_id})" in detached.text
    rendered = str(main_mod._render_assistant_message_html(detached.text))
    assert f'href="/jobs/panel#job-{job_id}"' in rendered


def test_job_store_migrates_notified_and_claims_it_once(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "agent_jobs.sqlite3")
    store.create(job_id="job", user_id="alice", goal="goal", status="detached")
    store.set_terminal("job", status="done", result="ok")

    assert store.mark_notified("job") is True
    assert store.mark_notified("job") is False
    assert store.get("job").notified is True
    assert store.get("job").as_dict()["notified"] is True


def test_detached_done_and_warning_notices_are_assistant_only_and_exactly_once(
    monkeypatch, tmp_path: Path,
) -> None:
    for warning in (False, True):
        notices: list[dict[str, object]] = []

        async def fake_native(*_args, **_kwargs):
            await asyncio.sleep(0.02)
            return _result(warning=warning)

        monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fake_native)

        async def scenario() -> tuple[object, Pipeline]:
            pipeline = _pipeline(tmp_path / ("warning" if warning else "done"))
            pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})
            detached = await pipeline.process("build scene", user_id="alice", language="de")
            record = await _wait_terminal(pipeline, _job_id(detached))
            return record, pipeline

        record, pipeline = asyncio.run(scenario())

        assert record.status == "done"
        assert len(notices) == 1
        notice = notices[0]
        assert notice["user_id"] == "alice"
        expected_prefix = "⚠️ Hintergrund-Auftrag teilweise erledigt: scene complete" if warning else "✅ Hintergrund-Auftrag fertig: scene complete"
        assert str(notice["text"]).startswith(expected_prefix)
        assert f"/jobs/panel?job={record.job_id}#job-{record.job_id}" in str(notice["text"])
        assert "Best-Effort" not in str(notice["text"])
        details = list(notice["badge_details"])
        assert any("used_tools=mcp__blender__execute_blender_code" in row for row in details)
        assert any("cache_read=80" in row for row in details)
        assert any(f"job_id={record.job_id}" in row for row in details)
        assert notice["badge_tokens"] == 150
        assert notice["badge_cost_usd"] == "$0.012345"
        assert notice["badge_duration"] == "2.5"
        assert pipeline.get_agent_job_store().mark_notified(record.job_id) is False


def test_detached_error_and_cancelled_notices_are_honest(monkeypatch, tmp_path: Path) -> None:
    async def error_native(*_args, **_kwargs):
        await asyncio.sleep(0.02)
        raise RuntimeError("blender exploded")

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", error_native)

    async def error_scenario() -> tuple[object, list[dict[str, object]]]:
        notices: list[dict[str, object]] = []
        pipeline = _pipeline(tmp_path / "error")
        pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})
        detached = await pipeline.process("build scene", user_id="alice", language="en")
        record = await _wait_terminal(pipeline, _job_id(detached))
        return record, notices

    error_record, error_notices = asyncio.run(error_scenario())
    assert error_record.status == "error"
    assert len(error_notices) == 1
    assert str(error_notices[0]["text"]).startswith("⚠️ Background task failed: blender exploded")
    assert "scene complete" not in str(error_notices[0]["text"])

    release = asyncio.Event()

    async def cancellable_native(*_args, **kwargs):
        callback = kwargs["step_callback"]
        await callback(1, ("mcp__blender__step",), "created object")
        await release.wait()
        await callback(2, ("mcp__blender__step",), "second step")
        return _result()

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", cancellable_native)

    async def cancel_scenario() -> tuple[object, list[dict[str, object]]]:
        notices: list[dict[str, object]] = []
        pipeline = _pipeline(tmp_path / "cancel")
        pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})
        detached = await pipeline.process("build scene", user_id="alice", language="de")
        job_id = _job_id(detached)
        assert pipeline.request_agent_job_cancel("alice", job_id) == "requested"
        release.set()
        record = await _wait_terminal(pipeline, job_id)
        return record, notices

    cancelled_record, cancelled_notices = asyncio.run(cancel_scenario())
    assert cancelled_record.status == "cancelled"
    assert len(cancelled_notices) == 1
    assert str(cancelled_notices[0]["text"]).startswith(
        "⏹ Hintergrund-Auftrag abgebrochen. Bereits ausgeführte Schritte bleiben bestehen."
    )
    assert f"/jobs/panel?job={cancelled_record.job_id}#job-{cancelled_record.job_id}" in str(cancelled_notices[0]["text"])


def test_sync_turn_has_no_notice_and_notifier_failure_does_not_change_status(
    monkeypatch, tmp_path: Path,
) -> None:
    notices: list[dict[str, object]] = []

    async def fast_native(*_args, **_kwargs):
        return _result("fast")

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fast_native)

    async def sync_scenario() -> tuple[PipelineResult, Pipeline]:
        pipeline = _pipeline(tmp_path / "sync", budget=0.5)
        pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})
        return await pipeline.process("hello", user_id="alice"), pipeline

    result, pipeline = asyncio.run(sync_scenario())
    assert result.text == "fast"
    assert notices == []
    assert pipeline.get_agent_job_store().list_for_user("alice") == ()

    async def slow_native(*_args, **_kwargs):
        await asyncio.sleep(0.02)
        return _result()

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", slow_native)

    async def failure_scenario() -> object:
        failing = _pipeline(tmp_path / "notify-failure")

        def fail_notice(*_args, **_kwargs):
            raise OSError("history unavailable")

        failing._agent_job_notifier = fail_notice
        detached = await failing.process("build", user_id="alice")
        return await _wait_terminal(failing, _job_id(detached))

    record = asyncio.run(failure_scenario())
    assert record.status == "done"
    assert record.notified is True


def test_assistant_notice_history_is_bounded_and_provider_roles_are_normalized(tmp_path: Path) -> None:
    store = FileChatHistoryStore(tmp_path, max_messages=4)
    store.append_exchange(
        "alice", user_message="build", assistant_message="detached",
        badge_icon="⏳", badge_intent="agent_job_detached", badge_tokens=0,
        badge_cost_usd="n/a", badge_duration="0.1", agent_job_id="aj1",
    )
    store.append_assistant_notice(
        "alice", job_id="aj1", text="done", badge_icon="✅",
        badge_intent="agent_job_done", badge_tokens=12,
        badge_cost_usd="$0.01", badge_duration="2.0",
        badge_details=["cache_read=10"],
    )

    history = store.load_history("alice")
    assert [row["role"] for row in history] == ["user", "assistant", "assistant"]
    assert history[-1]["agent_job_id"] == "aj1"
    assert history[-1]["agent_job_notice"] is True

    messages = _normalize_recent_history_messages(history, current_message="what happened?")
    assert [row["role"] for row in messages] == ["user", "assistant", "user"]
    assert "detached\n\ndone" == messages[1]["content"]


def _auth_cookie(username: str) -> tuple[str, str]:
    name = main_mod._cookie_name(main_mod.AUTH_COOKIE, public_url="http://testserver")
    value = main_mod._encode_auth_session(
        username, "user", scope=main_mod._cookie_scope_source(public_url="http://testserver"),
    )
    return name, value


def test_notice_partial_is_authenticated_user_scoped_and_escaped(monkeypatch) -> None:
    def fake_list(_self: object, user_id: str, *, limit: int = 20):  # noqa: ANN202
        if user_id == "alice":
            return [{"job_id": "aj-safe", "status": "done", "goal": "x", "step_log": [], "result": "ok"}]
        return []

    def fake_history(_self: object, user_id: str):  # noqa: ANN202
        if user_id != "alice":
            return []
        return [{
            "role": "assistant",
            "text": "done <script>alert(1)</script> [Job ansehen →](/jobs/panel#job-aj-safe)",
            "badge_icon": "✅",
            "badge_intent": "agent_job_done",
            "badge_tokens": 1,
            "badge_cost_usd": "n/a",
            "badge_duration": "1.0",
            "badge_details": ["<img src=x onerror=alert(1)>"],
            "agent_job_id": "aj-safe",
            "agent_job_notice": True,
        }]

    monkeypatch.setattr(main_mod.Pipeline, "list_agent_jobs", fake_list)
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    notice_route = next(
        route for route in main_mod.app.routes
        if getattr(route, "path", "") == "/jobs/{job_id}/notice"
    )
    route_deps = next(
        cell.cell_contents for cell in (notice_route.endpoint.__closure__ or ())
        if isinstance(cell.cell_contents, ChatExecutionRouteDeps)
    )
    original_history_loader = route_deps.load_chat_history
    object.__setattr__(route_deps, "load_chat_history", lambda user_id: fake_history(None, user_id))

    try:
        anonymous = TestClient(main_mod.app)
        assert anonymous.get("/jobs/aj-safe/notice").status_code == 401

        alice = TestClient(main_mod.app)
        cookie_name, cookie_value = _auth_cookie("alice")
        alice.cookies.set(cookie_name, cookie_value)
        response = alice.get("/jobs/aj-safe/notice")
        assert response.status_code == 200
        assert 'data-agent-job-id="aj-safe"' in response.text
        assert 'data-agent-job-notice="true"' in response.text
        assert "<script>" not in response.text
        assert "&lt;script&gt;" in response.text
        assert "<img src=x" not in response.text

        bob = TestClient(main_mod.app)
        bob_name, bob_value = _auth_cookie("bob")
        bob.cookies.set(bob_name, bob_value)
        assert bob.get("/jobs/aj-safe/notice").status_code == 404
    finally:
        object.__setattr__(route_deps, "load_chat_history", original_history_loader)


def test_chat_template_polls_machine_identified_detached_jobs() -> None:
    template = (Path(main_mod.BASE_DIR) / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")
    partial = (Path(main_mod.BASE_DIR) / "aria" / "templates" / "_chat_messages.html").read_text(encoding="utf-8")

    assert "data-agent-job-id" in template
    assert "data-agent-job-notice" in template
    assert 'fetch("/jobs"' in template
    assert "/notice" in template
    assert "3000" in template
    assert "30 * 60 * 1000" in template
    assert "data-agent-job-id" in partial
    assert "assistant_only" in partial
