from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS"] = "True"

from litellm.llms.anthropic.chat.transformation import AnthropicConfig

import aria.main as main_mod
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent import handler as native_handler
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


_IMAGE = "aGVsbG8="


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _call(name: str, call_id: str = "call-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments="{}"),
    )


def _binding(*, with_image: bool = False) -> NativeToolBinding:
    async def execute(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        content = '{"status":"ok","object":"cube"}'
        if with_image:
            content = json.dumps({
                "status": "ok",
                "content": [{
                    "type": "image", "mime_type": "image/png", "omitted": True,
                    "note": "Image returned by the tool.",
                }],
            })
        return NativeToolResult(
            content,
            "mcp__demo__step",
            images=(("image/png", _IMAGE),) if with_image else (),
        )

    return NativeToolBinding(
        NativeToolContract(
            owner_module_id="mcp",
            name="mcp__demo__step",
            description="Perform one bounded test step.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="read_only",
            confirmation_required=False,
            source_authority="mcp:test",
            user_scoped=True,
            rollout_flag="native_agent_mcp_enabled",
        ),
        execute,
    )


def _pipeline(tmp_path: Path) -> Pipeline:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(
        agentic_loop=SimpleNamespace(enabled=True, async_agent_job_sync_budget_seconds=0.001),
    )
    pipeline._project_root = tmp_path
    pipeline._routing_debug_enabled = lambda: False
    pipeline._finalize_process_result = lambda result, **_kwargs: result
    pipeline._agent_job_tasks = set()
    pipeline._agent_job_store = None
    pipeline._agent_job_store_path = None
    pipeline._agent_job_notifier = None
    return pipeline


def _result(text: str = "finished") -> PipelineResult:
    return PipelineResult(
        request_id="resume-turn",
        text=text,
        usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        intents=["chat"],
        skill_errors=[],
        router_level=2,
        duration_ms=10,
        detail_lines=["Routing Debug: resumed result"],
    )


def test_store_pause_resume_migration_atomic_claim_cancel_and_restart_survival(tmp_path: Path) -> None:
    path = tmp_path / "agent_jobs.sqlite3"
    store = AgentJobStore(path)
    store.create(job_id="job", user_id="alice", goal="build", status="detached", now=10)

    assert store.request_pause("job", user_id="bob") == "not_found"
    assert store.request_pause("job", user_id="alice") == "requested"
    assert store.is_pause_requested("job", user_id="alice") is True
    snapshot = {"messages": [{"role": "user", "content": "build"}], "step_index": 2}
    store.set_paused("job", snapshot, now=20)

    paused = AgentJobStore(path).get("job")
    assert paused is not None
    assert paused.status == "paused"
    assert paused.pause_requested is False
    assert paused.resume_state == snapshot
    assert "resume_state" not in paused.as_dict()
    assert paused.paused_at == 20
    assert store.mark_stale_interrupted(stale_before=100, now=200) == 0
    assert store.claim_resume("job", user_id="bob") is None

    async def double_claim() -> list[dict | None]:
        return await asyncio.gather(
            asyncio.to_thread(store.claim_resume, "job", user_id="alice"),
            asyncio.to_thread(store.claim_resume, "job", user_id="alice"),
        )

    claims = asyncio.run(double_claim())
    assert sum(row is not None for row in claims) == 1
    assert next(row for row in claims if row is not None) == snapshot

    store.set_paused("job", snapshot, now=30)
    assert store.request_cancel("job", user_id="alice") == "requested"
    cancelled = store.get("job")
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled.result == "cancelled_by_user"
    assert cancelled.resume_state is None
    assert store.request_pause("job", user_id="alice") == "not_running"
    assert path.stat().st_mode & 0o777 == 0o600


def test_loop_pauses_only_at_clean_iteration_boundary_and_snapshot_is_private(tmp_path: Path) -> None:
    provider_messages: list[list[dict]] = []
    checkpoint_seen = asyncio.Event()

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        provider_messages.append(list(kwargs["messages"]))
        if len(provider_messages) == 1:
            return _response(tool_calls=[_call("mcp__demo__step")], finish_reason="tool_use")
        raise AssertionError("pause must happen before the second provider call")

    async def checkpoint(_step: int, _tools, _summary: str) -> None:  # noqa: ANN001
        checkpoint_seen.set()

    async def pause_check() -> bool:
        return checkpoint_seen.is_set()

    async def scenario() -> dict:
        try:
            await native_handler.run_native_agent_turn(
                message="build a cube", user_id="alice", turn_id="pause-turn",
                llm_config=LLMConfig(model="claude-sonnet-4-5"),
                tool_bindings=(_binding(with_image=True),), completion=completion,
                trace_root=tmp_path, step_callback=checkpoint, pause_check=pause_check,
                mcp_vision_enabled=True,
            )
        except native_handler.NativeAgentPaused as exc:
            return exc.snapshot
        raise AssertionError("loop did not pause")

    snapshot = asyncio.run(scenario())
    assert snapshot["step_index"] == 1
    assert snapshot["provider_calls"] == 1
    assert snapshot["used_tool_names"] == ["mcp__demo__step"]
    assert snapshot["original_message"] == "build a cube"
    assert snapshot["turn_id"] == "pause-turn"
    assert all(row.get("role") != "system" for row in snapshot["messages"])
    assistant = next(row for row in snapshot["messages"] if row.get("role") == "assistant")
    tool = next(row for row in snapshot["messages"] if row.get("role") == "tool")
    assert assistant["tool_calls"][0]["id"] == tool["tool_call_id"]
    serialized = json.dumps(snapshot)
    assert _IMAGE not in serialized
    assert "image from an earlier step was not retained after pause" in serialized
    assert len(serialized.encode("utf-8")) < native_handler.NATIVE_AGENT_RESUME_STATE_MAX_BYTES


def test_detached_budget_boundary_pauses_with_additive_reason(tmp_path: Path) -> None:
    calls = 0

    async def completion(**_kwargs):
        nonlocal calls
        calls += 1
        return _response(tool_calls=[_call("mcp__demo__step", f"call-{calls}")], finish_reason="tool_use")

    async def detached() -> bool:
        return True

    async def scenario() -> native_handler.NativeAgentPaused:
        try:
            await native_handler.run_native_agent_turn(
                message="build", user_id="alice", turn_id="budget-pause",
                llm_config=LLMConfig(model="fake"), tool_bindings=(_binding(),),
                completion=completion, trace_root=tmp_path, detached_check=detached,
                max_steps=2, max_provider_calls=3,
            )
        except native_handler.NativeAgentPaused as exc:
            return exc
        raise AssertionError("detached budget did not pause")

    paused = asyncio.run(scenario())
    assert paused.reason == "budget_reached"
    assert paused.snapshot["pause_reason"] == "budget_reached"
    assert paused.snapshot["budget_max_steps"] == 2
    assert paused.snapshot["budget_max_provider_calls"] == 3


def test_snapshot_over_cap_refuses_pause_and_final_answer_in_progress_finishes(tmp_path: Path) -> None:
    refusal: list[str] = []
    provider_calls = 0

    async def completion(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        if provider_calls == 1:
            return _response(tool_calls=[_call("mcp__demo__step")], finish_reason="tool_use")
        return _response(content="done")

    async def pause_check() -> bool:
        return True

    async def pause_refused(reason: str) -> None:
        refusal.append(reason)

    original_limit = native_handler.NATIVE_AGENT_RESUME_STATE_MAX_BYTES
    native_handler.NATIVE_AGENT_RESUME_STATE_MAX_BYTES = 32
    try:
        outcome = asyncio.run(native_handler.run_native_agent_turn(
            message="build", user_id="alice", turn_id="oversize",
            llm_config=LLMConfig(model="fake"), tool_bindings=(_binding(),),
            completion=completion, trace_root=tmp_path, pause_check=pause_check,
            pause_refused=pause_refused,
        ))
    finally:
        native_handler.NATIVE_AGENT_RESUME_STATE_MAX_BYTES = original_limit

    assert outcome.kind == "final_answer"
    assert outcome.message == "done"
    assert refusal == ["resume_state_too_large"]

    async def direct_final(**_kwargs):
        return _response(content="already complete")

    final = asyncio.run(native_handler.run_native_agent_turn(
        message="hello", user_id="alice", turn_id="final-in-progress",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_binding(),),
        completion=direct_final, trace_root=tmp_path, pause_check=pause_check,
    ))
    assert final.kind == "final_answer"
    assert final.message == "already complete"


def test_resume_restores_messages_counters_and_alpha973_cache_contract(tmp_path: Path) -> None:
    first_messages: list[dict] = []

    async def first_completion(**kwargs):  # noqa: ANN003, ANN202
        first_messages[:] = list(kwargs["messages"])
        return _response(content="resumed and done")

    resume_state = {
        "version": 1,
        "messages": [
            {"role": "user", "content": "build"},
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "mcp__demo__step", "arguments": "{}"},
            }]},
            {"role": "tool", "tool_call_id": "call-1", "content": '{"status":"ok"}'},
        ],
        "step_index": 2,
        "provider_calls": 2,
        "used_tool_names": ["mcp__demo__step"],
        "used_intents": ["mcp__demo__step"],
        "successful_effectful_observations": [["mcp__demo__step", '{"status":"ok"}']],
        "tool_step_error": False,
        "unsourced_resource_retry_used": False,
        "action_claim_retry_used": False,
        "mcp_vision_images": 0,
        "mcp_vision_bytes": 0,
        "llm_calls": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "original_message": "build",
        "language": "en",
        "auth_role": "user",
        "turn_id": "original-turn",
    }
    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="build", user_id="alice", auth_role="user", turn_id="original-turn",
        llm_config=LLMConfig(model="claude-sonnet-4-5"),
        tool_bindings=(_binding(),), completion=first_completion, trace_root=tmp_path,
        resume_state=resume_state, max_provider_calls=6,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.provider_calls == 3
    assert outcome.resumed is True
    assert first_messages[0]["role"] == "system"
    assert first_messages[1:-1] == resume_state["messages"][:-1]
    assert {key: value for key, value in first_messages[-1].items() if key != "cache_control"} == resume_state["messages"][-1]
    assert first_messages[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert isinstance(first_messages[-1]["content"], str)
    payload = AnthropicConfig().transform_request(
        model="claude-sonnet-4-5",
        messages=deepcopy(first_messages),
        optional_params={"max_tokens": 128, "tools": [{
            "name": "mcp__demo__step", "description": "Perform one bounded test step.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }]},
        litellm_params={}, headers={},
    )
    tool_results = [
        block
        for message in payload["messages"]
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    assert len(tool_results) == 1
    assert tool_results[0]["tool_use_id"] == "call-1"
    assert tool_results[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert tool_results[0]["content"] == '{"status":"ok"}'


def test_pipeline_resume_is_background_atomic_notifies_pause_and_terminal(monkeypatch, tmp_path: Path) -> None:
    notices: list[dict[str, object]] = []
    pipeline = _pipeline(tmp_path)
    pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})
    store = pipeline.get_agent_job_store()
    store.create(job_id="job", user_id="alice", goal="build", status="detached")
    store.set_paused("job", {
        "version": 1, "messages": [{"role": "user", "content": "build"}],
        "step_index": 2, "provider_calls": 2, "used_tool_names": [], "used_intents": [],
        "successful_effectful_observations": [], "tool_step_error": False,
        "unsourced_resource_retry_used": False, "action_claim_retry_used": False,
        "mcp_vision_images": 0, "mcp_vision_bytes": 0, "llm_calls": [], "usage": {},
        "original_message": "build", "language": "en", "auth_role": "user", "turn_id": "turn",
    })
    resumed_pipeline = _pipeline(tmp_path)
    resumed_pipeline._agent_job_notifier = pipeline._agent_job_notifier

    release = asyncio.Event()
    received: list[dict] = []

    async def resumed_native(*_args, **kwargs):  # noqa: ANN003
        received.append(kwargs)
        await release.wait()
        await kwargs["step_callback"](3, ("mcp__demo__step",), "done")
        return _result()

    monkeypatch.setattr("aria.modules.pipeline_orchestrator.pipeline.run_native_agent_first_stage", resumed_native)

    async def scenario() -> None:
        assert await resumed_pipeline.resume_agent_job("bob", "job") == "not_found"
        first, second = await asyncio.gather(
            resumed_pipeline.resume_agent_job("alice", "job"),
            resumed_pipeline.resume_agent_job("alice", "job"),
        )
        assert sorted((first, second)) == ["not_running", "started"]
        release.set()
        for _ in range(100):
            if store.get("job").status == "done":
                break
            await asyncio.sleep(0.01)

    asyncio.run(scenario())
    record = store.get("job")
    assert record is not None and record.status == "done"
    assert [row["step_index"] for row in record.step_log] == [3]
    assert received[0]["resume_state"]["step_index"] == 2
    assert any("agent_job resumed=yes steps=1" in row for row in notices[-1]["badge_details"])
    assert sum(str(row["badge_intent"]) == "agent_job_done" for row in notices) == 1


def test_detached_job_pause_notice_is_once_and_cancel_paused_is_terminal(monkeypatch, tmp_path: Path) -> None:
    notices: list[dict[str, object]] = []
    pipeline = _pipeline(tmp_path)
    pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})

    async def pausable_native(*_args, **kwargs):  # noqa: ANN003
        await kwargs["step_callback"](1, ("mcp__demo__step",), "first")
        while not await kwargs["pause_check"]():
            await asyncio.sleep(0.001)
        raise native_handler.NativeAgentPaused({
            "version": 1, "messages": [{"role": "user", "content": "build"}],
            "step_index": 1, "provider_calls": 1, "used_tool_names": ["mcp__demo__step"],
            "used_intents": ["mcp__demo__step"], "successful_effectful_observations": [],
            "tool_step_error": False, "unsourced_resource_retry_used": False,
            "action_claim_retry_used": False, "mcp_vision_images": 0, "mcp_vision_bytes": 0,
            "llm_calls": [], "usage": {}, "original_message": "build", "language": "de",
            "auth_role": "user", "turn_id": "pause-turn",
        })

    monkeypatch.setattr("aria.modules.pipeline_orchestrator.pipeline.run_native_agent_first_stage", pausable_native)

    async def scenario() -> tuple[object, object]:
        detached = await pipeline.process("build", user_id="alice", language="de", auth_role="user")
        job_id = str(detached.agent_job_id)
        assert pipeline.request_agent_job_pause("alice", job_id) == "requested"
        for _ in range(100):
            paused = pipeline.get_agent_job_store().get(job_id)
            if paused is not None and paused.status == "paused":
                break
            await asyncio.sleep(0.005)
        else:
            raise AssertionError("job did not pause")
        assert pipeline.request_agent_job_cancel("alice", job_id) == "requested"
        await asyncio.sleep(0.01)
        return paused, pipeline.get_agent_job_store().get(job_id)

    paused, cancelled = asyncio.run(scenario())
    assert paused.resume_state is not None
    assert cancelled.status == "cancelled"
    assert cancelled.resume_state is None
    pause_notices = [row for row in notices if row["badge_intent"] == "agent_job_paused"]
    terminal_notices = [row for row in notices if row["badge_intent"] == "agent_job_cancelled"]
    assert len(pause_notices) == len(terminal_notices) == 1
    assert str(pause_notices[0]["text"]).startswith("⏸ Hintergrund-Auftrag pausiert nach Schritt 1.")
    assert "Im Job-Panel fortsetzen" in str(pause_notices[0]["text"])


def _user_client(monkeypatch) -> TestClient:  # noqa: ANN001
    monkeypatch.setattr(main_mod.FileChatHistoryStore, "append_exchange", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(main_mod, "can_access_advanced_config", lambda role, debug_mode: False)
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    client = TestClient(main_mod.app)
    auth_name = main_mod._cookie_name(main_mod.AUTH_COOKIE, public_url="http://testserver")
    auth = main_mod._encode_auth_session(
        "neo", "user", scope=main_mod._cookie_scope_source(public_url="http://testserver"),
    )
    client.cookies.set(auth_name, auth)
    csrf = main_mod._new_csrf_token()
    client.cookies.set(main_mod._cookie_name(main_mod.CSRF_COOKIE, public_url="http://testserver"), csrf)
    client.headers.update({"x-csrf-token": csrf})
    return client


def test_pause_resume_routes_are_scoped_csrf_checked_and_panel_has_real_controls(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    def pause(_self: object, user_id: str, job_id: str) -> str:
        calls.append(("pause", user_id, job_id))
        return "requested"

    async def resume(_self: object, user_id: str, job_id: str) -> str:
        calls.append(("resume", user_id, job_id))
        return "started"

    def jobs(_self: object, _user_id: str, *, limit: int = 20):  # noqa: ANN202
        return [{
            "job_id": "job", "goal": "build", "status": "paused", "step_log": [],
            "result": "", "created_at": 1.0, "updated_at": 2.0,
            "cancel_requested": False, "pause_requested": False, "warning": "",
        }]

    monkeypatch.setattr(main_mod.Pipeline, "request_agent_job_pause", pause)
    monkeypatch.setattr(main_mod.Pipeline, "resume_agent_job", resume)
    monkeypatch.setattr(main_mod.Pipeline, "list_agent_jobs", jobs)
    client = _user_client(monkeypatch)

    paused = client.post("/jobs/job/pause", follow_redirects=False)
    resumed = client.post("/jobs/job/resume", follow_redirects=False)
    panel = client.get("/jobs/panel")

    assert paused.status_code == resumed.status_code == 303
    assert paused.headers["location"] == "/jobs/panel?notice=pause_requested#job-job"
    assert resumed.headers["location"] == "/jobs/panel?notice=resume_started#job-job"
    assert calls == [("pause", "neo", "job"), ("resume", "neo", "job")]
    assert "pausiert" in panel.text.lower()
    assert '/jobs/job/resume' in panel.text
    assert '/jobs/job/cancel' in panel.text
    assert "Korrigieren" in panel.text

    client.headers.pop("x-csrf-token")
    assert client.post("/jobs/job/pause").status_code == 403
    assert client.post("/jobs/job/resume").status_code == 403


def test_chat_polling_treats_paused_as_notice_state_and_keeps_polling_slowly() -> None:
    template = (Path(main_mod.BASE_DIR) / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")
    partial = (Path(main_mod.BASE_DIR) / "aria" / "templates" / "_chat_messages.html").read_text(encoding="utf-8")

    assert '"paused"' in template
    assert "15000" in template
    assert "data-agent-job-state" in template
    assert "data-agent-job-state" in partial
