from __future__ import annotations

import asyncio
from html.parser import HTMLParser
from pathlib import Path
import subprocess
from types import SimpleNamespace

from fastapi.testclient import TestClient

import aria.main as main_mod
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
PANEL_TEMPLATE = ROOT / "aria" / "templates" / "agent_jobs.html"
CHAT_TEMPLATE = ROOT / "aria" / "templates" / "chat.html"
CHAT_PARTIAL = ROOT / "aria" / "templates" / "_chat_messages.html"
DEADLINE_SCRIPT = ROOT / "aria" / "static" / "chat-request-deadline.js"


class _InlineScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and not dict(attrs).get("src"):
            self._capture = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            self.scripts.append("".join(self._parts))
            self._capture = False


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


def _job(job_id: str, status: str, *, steps: int = 0) -> dict[str, object]:
    return {
        "job_id": job_id,
        "goal": f"goal {job_id}",
        "status": status,
        "step_log": [
            {
                "step_index": index,
                "tool_names": ["mcp__demo__execute"],
                "outcome_summary": f"step {index} ok",
            }
            for index in range(1, steps + 1)
        ],
        "result": "complete" if status == "done" else "",
        "created_at": 1.0,
        "updated_at": 2.0,
        "cancel_requested": False,
        "pause_requested": False,
        "warning": "",
    }


def test_panel_controls_are_in_header_and_long_steps_are_collapsed(monkeypatch) -> None:
    def jobs(_self: object, _user_id: str, *, limit: int = 20):  # noqa: ANN202
        return [_job("running", "detached", steps=12), _job("paused", "paused", steps=2), _job("done", "done", steps=1)]

    monkeypatch.setattr(main_mod.Pipeline, "list_agent_jobs", jobs)
    response = _user_client(monkeypatch).get("/jobs/panel")
    assert response.status_code == 200

    running = response.text.split('id="job-running"', 1)[1].split("</article>", 1)[0]
    paused = response.text.split('id="job-paused"', 1)[1].split("</article>", 1)[0]
    done = response.text.split('id="job-done"', 1)[1].split("</article>", 1)[0]
    for card in (running, paused, done):
        assert 'data-agent-job-header="true"' in card
        assert 'data-agent-job-steps="true"' in card
    assert running.index('/jobs/running/pause') < running.index('data-agent-job-steps="true"')
    assert running.index('/jobs/running/cancel') < running.index('data-agent-job-steps="true"')
    assert paused.index('/jobs/paused/resume') < paused.index('data-agent-job-steps="true"')
    assert paused.index('/jobs/paused/cancel') < paused.index('data-agent-job-steps="true"')
    assert "/jobs/done/pause" not in done and "/jobs/done/resume" not in done and "/jobs/done/cancel" not in done
    assert '<details class="agent-job-steps" data-agent-job-steps="true">' in running
    assert "Schritte: 12" in running and "mcp__demo__execute" in running


def test_panel_polling_updates_in_place_without_navigation_or_raw_html() -> None:
    template = PANEL_TEMPLATE.read_text(encoding="utf-8")
    assert "window.location.reload" not in template
    assert "location.assign" not in template
    assert "location.href =" not in template
    assert "updateAgentJobCard" in template
    assert "createAgentJobCard" in template
    assert ".textContent" in template
    assert "insertAdjacentHTML" not in template
    assert "innerHTML" not in template
    assert "details.open" in template
    assert "agentJobUserToggled" in template


def test_job_control_routes_support_json_fetch_and_form_redirect(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    def cancel(_self: object, user_id: str, job_id: str) -> str:
        calls.append(("cancel", user_id, job_id))
        return "requested"

    def pause(_self: object, user_id: str, job_id: str) -> str:
        calls.append(("pause", user_id, job_id))
        return "requested"

    async def resume(_self: object, user_id: str, job_id: str) -> str:
        calls.append(("resume", user_id, job_id))
        return "started"

    monkeypatch.setattr(main_mod.Pipeline, "request_agent_job_cancel", cancel)
    monkeypatch.setattr(main_mod.Pipeline, "request_agent_job_pause", pause)
    monkeypatch.setattr(main_mod.Pipeline, "resume_agent_job", resume)
    client = _user_client(monkeypatch)

    for action, expected in (("pause", "pause_requested"), ("resume", "resume_started"), ("cancel", "requested")):
        response = client.post(f"/jobs/job/{action}", headers={"accept": "application/json"})
        assert response.status_code == 200
        assert response.json() == {"job_id": "job", "notice": expected, "outcome": "requested" if action != "resume" else "started"}
    redirected = client.post("/jobs/job/pause", headers={"accept": "text/html"}, follow_redirects=False)
    assert redirected.status_code == 303
    assert redirected.headers["location"] == "/jobs/panel?notice=pause_requested#job-job"
    assert calls[:3] == [("pause", "neo", "job"), ("resume", "neo", "job"), ("cancel", "neo", "job")]

    client.headers.pop("x-csrf-token")
    denied = client.post(
        "/jobs/job/cancel",
        headers={"accept": "application/json", "x-requested-with": "XMLHttpRequest"},
    )
    assert denied.status_code == 403


def test_budget_and_cleanup_routes_are_scoped_csrf_and_refuse_active_delete(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def resume(_self, user_id: str, job_id: str, *, budget_action: str = "") -> str:  # noqa: ANN001
        assert user_id == "neo"
        calls.append((job_id, budget_action))
        return "started"

    def delete(_self, user_id: str, job_id: str) -> str:  # noqa: ANN001
        assert user_id == "neo"
        return "not_terminal" if job_id == "active" else "deleted"

    def clear(_self, user_id: str) -> int:  # noqa: ANN001
        assert user_id == "neo"
        return 2

    monkeypatch.setattr(main_mod.Pipeline, "resume_agent_job", resume)
    monkeypatch.setattr(main_mod.Pipeline, "delete_agent_job", delete)
    monkeypatch.setattr(main_mod.Pipeline, "clear_terminal_agent_jobs", clear)
    client = _user_client(monkeypatch)
    for action in ("extend", "finish"):
        response = client.post(f"/jobs/budget/{action}", headers={"accept": "application/json"})
        assert response.status_code == 200
        assert response.json()["outcome"] == "started"
    assert calls == [("budget", "extend"), ("budget", "finish")]
    assert client.post("/jobs/active/delete", headers={"accept": "application/json"}).json()["outcome"] == "not_terminal"
    assert client.post("/jobs/done/delete", headers={"accept": "application/json"}).json()["outcome"] == "deleted"
    assert client.post("/jobs/clear-completed", headers={"accept": "application/json"}).json()["count"] == 2
    client.headers.pop("x-csrf-token")
    assert client.post("/jobs/budget/extend").status_code == 403
    assert client.post("/jobs/done/delete").status_code == 403
    assert client.post("/jobs/clear-completed").status_code == 403


def test_chat_has_inline_job_controls_and_lost_response_fallback() -> None:
    template = CHAT_TEMPLATE.read_text(encoding="utf-8")
    partial = CHAT_PARTIAL.read_text(encoding="utf-8")
    for source in (template, partial):
        assert "data-agent-job-controls" in source
    assert "renderAgentJobControls" in template
    assert "postAgentJobAction" in template
    assert '"/pause"' in template and '"/resume"' in template and '"/cancel"' in template
    assert 'headers: { "X-CSRF-Token"' in template
    assert "recoverDetachedAgentJob" in template
    matcher = DEADLINE_SCRIPT.read_text(encoding="utf-8")
    assert "created_at" in matcher and "submittedAtSeconds" in template
    assert "matchRecentAgentJob" in template
    assert "data-agent-job-id" in template
    assert "Job ansehen" in template


def test_recent_job_matcher_uses_submit_time_and_normalized_goal_prefix() -> None:
    script = f"""
const api = require({str(DEADLINE_SCRIPT)!r});
const assert = require('node:assert/strict');
const rows = [
  {{job_id: 'old', created_at: 99, goal: 'Build a moon base'}},
  {{job_id: 'wrong', created_at: 101, goal: 'Unrelated request'}},
  {{job_id: 'match', created_at: 102, goal: '  BUILD   A MOON BASE with blue windows  '}},
];
assert.equal(api.matchRecentAgentJob(rows, 'build a moon base with blue windows and doors', 100).job_id, 'match');
assert.equal(api.matchRecentAgentJob(rows, 'not present', 100), null);
assert.equal(api.matchRecentAgentJob([rows[0]], 'build a moon base', 100), null);
"""
    subprocess.run(["node", "-e", script], cwd=ROOT, check=True)


def test_route_timing_detail_is_persisted_into_terminal_notice(tmp_path: Path) -> None:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace()
    pipeline._project_root = tmp_path
    pipeline._agent_job_store = None
    pipeline._agent_job_store_path = None
    notices: list[dict[str, object]] = []
    pipeline._agent_job_notifier = lambda user_id, **payload: notices.append({"user_id": user_id, **payload})
    store = pipeline.get_agent_job_store()
    store.create(job_id="job", user_id="alice", goal="work", status="detached")
    timing = "Routing Debug: web_route_timing history_append_ms=7 total_ms=25123"

    assert pipeline.append_agent_job_detail_line("alice", "job", timing) is True
    store.set_terminal("job", status="done", result="complete")
    asyncio.run(pipeline._notify_agent_job_terminal(
        store=store,
        job_id="job",
        user_id="alice",
        language="en",
        status="done",
        result="complete",
    ))
    assert timing in notices[0]["badge_details"]


def test_chat_route_records_post_pipeline_timing_for_detached_job() -> None:
    source = (ROOT / "aria" / "modules" / "chat_execution_composition" / "routes.py").read_text(encoding="utf-8")
    assert "append_agent_job_detail_line" in source
    assert "history_append_ms=" in source
    assert "total_ms=" in source


def test_detached_chat_route_persists_its_timing_line(monkeypatch) -> None:
    captured: list[tuple[str, str, str]] = []

    async def process(_self: object, *_args, **_kwargs) -> PipelineResult:
        return PipelineResult(
            request_id="request",
            text="The task continues.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["native_agent"],
            skill_errors=[],
            router_level=2,
            duration_ms=25_000,
            detail_lines=["Routing Debug: agent_job status=detached job_id=job"],
            agent_job_id="job",
        )

    def append_detail(_self: object, user_id: str, job_id: str, line: str) -> bool:
        captured.append((user_id, job_id, line))
        return True

    monkeypatch.setattr(main_mod.Pipeline, "process", process)
    monkeypatch.setattr(main_mod.Pipeline, "append_agent_job_detail_line", append_detail)
    client = _user_client(monkeypatch)
    response = client.post("/chat", data={"message": "build a scene"})

    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0][:2] == ("neo", "job")
    assert "history_append_ms=" in captured[0][2]
    assert "total_ms=" in captured[0][2]


def test_assistant_markdown_bold_is_strong_and_escaped() -> None:
    rendered = str(main_mod._render_assistant_message_html("**safe <tag>** [Job](/jobs/panel)"))
    assert "<strong>safe &lt;tag&gt;</strong>" in rendered
    assert "<tag>" not in rendered
    assert '<a href="/jobs/panel"' in rendered


def test_rendered_panel_and_chat_inline_javascript_parse(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod.Pipeline,
        "list_agent_jobs",
        lambda _self, _user_id, limit=20: [_job("running", "detached", steps=4)],
    )
    client = _user_client(monkeypatch)
    for path in ("/jobs/panel", "/"):
        response = client.get(path)
        assert response.status_code == 200
        parser = _InlineScriptParser()
        parser.feed(response.text)
        assert parser.scripts
        for script in parser.scripts:
            subprocess.run(
                ["node", "--check"], cwd=ROOT, input=script, text=True,
                capture_output=True, check=True,
            )
