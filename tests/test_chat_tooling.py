from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import aria.main as main_mod
import aria.modules.memory.native_tools as memory_native_tools
import aria.modules.chat_admin_composition.actions as chat_admin_actions
import aria.modules.action_pending_chat_boundary.flows as chat_pending_flows
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.chat_execution_composition.route_helpers import prepare_chat_route_state
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.pipeline_orchestrator.pipeline import PipelineResult


def _scoped_cookie(base_name: str) -> str:
    return main_mod._cookie_name(base_name, public_url="http://testserver")


def _scoped_auth(username: str, role: str) -> str:
    return main_mod._encode_auth_session(
        username,
        role,
        scope=main_mod._cookie_scope_source(public_url="http://testserver"),
    )


def _admin_client(monkeypatch, *, advanced_mode: bool = False) -> TestClient:
    monkeypatch.setattr(main_mod.FileChatHistoryStore, "append_exchange", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(main_mod, "can_access_advanced_config", lambda role, debug_mode: advanced_mode)  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    csrf_token = main_mod._new_csrf_token()
    client.cookies.set(_scoped_cookie(main_mod.CSRF_COOKIE), csrf_token)
    client.headers.update({"x-csrf-token": csrf_token})
    return client


def _user_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_mod.FileChatHistoryStore, "append_exchange", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(main_mod, "can_access_advanced_config", lambda role, debug_mode: False)  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "user"))
    csrf_token = main_mod._new_csrf_token()
    client.cookies.set(_scoped_cookie(main_mod.CSRF_COOKIE), csrf_token)
    client.headers.update({"x-csrf-token": csrf_token})
    return client


def test_chat_progress_is_user_scoped_and_idle_returns_no_content(monkeypatch) -> None:
    from aria.modules.platform_primitives.recipe_progress import RECIPE_PROGRESS_STORE

    client = _user_client(monkeypatch)
    RECIPE_PROGRESS_STORE.clear("neo")
    idle = client.get("/chat/progress")
    RECIPE_PROGRESS_STORE.update(
        "neo", phase="running", step_index=2, step_total=3, step_type="ssh_run",
        host_index=5, host_total=14, host_ref="srv-dev02", ok_count=4, error_count=1,
    )
    active = client.get("/chat/progress")
    RECIPE_PROGRESS_STORE.update("other", phase="running", step_index=1, step_total=1, step_type="ssh_run")
    isolated = client.get("/chat/progress")
    RECIPE_PROGRESS_STORE.clear("neo")

    assert idle.status_code == 204
    assert active.status_code == 200
    assert active.json() == {
        "phase": "running", "step_index": 2, "step_total": 3, "step_type": "ssh_run",
        "host_index": 5, "host_total": 14, "host_ref": "srv-dev02",
        "ok_count": 4, "error_count": 1, "updated_at": active.json()["updated_at"],
    }
    assert isolated.json()["host_ref"] == "srv-dev02"


def test_agent_job_status_route_is_authenticated_and_user_scoped(monkeypatch) -> None:
    seen: list[str] = []

    def fake_list(_self: object, user_id: str, *, limit: int = 20) -> list[dict[str, object]]:
        seen.append(user_id)
        return [{"job_id": "aj1", "goal": "goal", "status": "detached", "step_log": [], "result": ""}]

    monkeypatch.setattr(main_mod.Pipeline, "list_agent_jobs", fake_list)
    client = _user_client(monkeypatch)

    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json()["jobs"][0]["job_id"] == "aj1"
    assert seen == ["neo"]


def test_agent_jobs_panel_is_authenticated_user_scoped_and_renders_progress(monkeypatch) -> None:
    seen: list[str] = []

    def fake_list(_self: object, user_id: str, *, limit: int = 20) -> list[dict[str, object]]:
        seen.append(user_id)
        return [{
            "job_id": "aj-panel",
            "goal": "Build a detailed scene",
            "status": "done",
            "step_log": [{
                "step_index": 2,
                "tool_names": ["mcp__blender__execute_blender_code"],
                "outcome_summary": "snowman created",
            }],
            "result": "Scene complete",
            "created_at": 10.0,
            "updated_at": 20.0,
            "cancel_requested": False,
            "warning": "native_agent_summary_unavailable",
        }]

    monkeypatch.setattr(main_mod.Pipeline, "list_agent_jobs", fake_list)
    authenticated = _user_client(monkeypatch)
    response = authenticated.get("/jobs/panel")
    anonymous = TestClient(main_mod.app).get("/jobs/panel")

    assert response.status_code == 200
    assert "aj-panel" in response.text
    assert "Build a detailed scene" in response.text
    assert "mcp__blender__execute_blender_code" in response.text
    assert "snowman created" in response.text
    assert "Scene complete" in response.text
    assert "Teilweise erledigt" in response.text
    assert "aufgezeichnete Tool-Rückmeldungen" in response.text
    assert 'fetch("/jobs"' in response.text
    assert seen == ["neo"]
    assert anonymous.status_code == 401


def test_agent_job_cancel_route_passes_authenticated_owner_and_reports_noop(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_cancel(_self: object, user_id: str, job_id: str) -> str:
        calls.append((user_id, job_id))
        return "not_running"

    monkeypatch.setattr(main_mod.Pipeline, "request_agent_job_cancel", fake_cancel)
    client = _user_client(monkeypatch)

    response = client.post("/jobs/aj-finished/cancel", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/jobs/panel?notice=not_running#job-aj-finished"
    assert calls == [("neo", "aj-finished")]

    client.headers.pop("x-csrf-token")
    rejected = client.post("/jobs/aj-finished/cancel", follow_redirects=False)
    assert rejected.status_code == 403
    assert calls == [("neo", "aj-finished")]


def test_chat_wait_indicator_polls_server_progress_only_while_request_is_active() -> None:
    template = (Path(main_mod.BASE_DIR) / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "'/chat/progress'" in template or '"/chat/progress"' in template
    assert "1500" in template
    assert "step_index" in template
    assert "host_ref" in template
    assert "clearProgressPolling" in template


def test_pending_connection_ref_reply_requires_exact_configured_ref() -> None:
    pending_action = {
        "action_decision": {"missing_input": "connection_ref"},
        "payload": {
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "",
            "missing_fields": ["connection_ref"],
        },
    }
    settings = SimpleNamespace(
        connections=SimpleNamespace(ssh={"example-host-01": {"host": "192.0.2.15"}})
    )

    assert chat_pending_flows.pending_input_reply_matches_contract(
        pending_action,
        "example-host-01",
        settings,
    )
    assert not chat_pending_flows.pending_input_reply_matches_contract(
        pending_action,
        "wie fit ist example-host-01",
        settings,
    )


def test_prepare_chat_route_state_uses_separate_forget_and_pending_signing_secrets() -> None:
    forget_cookie = chat_admin_actions._encode_forget_pending(
        {
            "token": "forget1",
            "user_id": "neo",
            "candidates": [{"collection": "mem", "id": "point-1", "label": "Fact", "text": "old"}],
        },
        signing_secret="forget-secret",
        sanitize_username=lambda value: str(value or "").strip(),
        sanitize_collection_name=lambda value: str(value or "").strip(),
    )
    routed_cookie = chat_admin_actions._encode_routed_action_pending(
        {
            "token": "route1",
            "user_id": "neo",
            "query": "send alert",
            "candidate_kind": "template",
            "candidate_id": "discord_send_message",
            "payload": {"capability": "discord_send"},
        },
        signing_secret="pending-secret",
        sanitize_username=lambda value: str(value or "").strip(),
    )
    cookie_header = (
        f"{main_mod.FORGET_PENDING_COOKIE}={forget_cookie}; "
        f"{main_mod.ROUTED_ACTION_PENDING_COOKIE}={routed_cookie}"
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [(b"cookie", cookie_header.encode("utf-8"))],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
    )
    request.state.auth_role = "admin"
    request.state.can_access_advanced_config = True

    route_state = prepare_chat_route_state(
        request=request,
        clean_message="bestätige",
        username="neo",
        lang="de",
        pipeline=SimpleNamespace(classify_routing=lambda *_args, **_kwargs: SimpleNamespace(intents=[])),
        request_cookie_value=lambda req, name: req.cookies.get(name, ""),
        sanitize_username=lambda value: str(value or "").strip(),
        sanitize_connection_name=lambda value: str(value or "").strip(),
        sanitize_role=lambda value: str(value or "").strip() or "user",
        forget_signing_secret="forget-secret",
        pending_signing_secret="pending-secret",
        connection_pending_max_age_seconds=600,
        forget_pending_cookie=main_mod.FORGET_PENDING_COOKIE,
        connection_delete_pending_cookie=main_mod.CONNECTION_DELETE_PENDING_COOKIE,
        connection_create_pending_cookie=main_mod.CONNECTION_CREATE_PENDING_COOKIE,
        connection_update_pending_cookie=main_mod.CONNECTION_UPDATE_PENDING_COOKIE,
        update_pending_cookie=main_mod.UPDATE_PENDING_COOKIE,
        routed_action_pending_cookie=main_mod.ROUTED_ACTION_PENDING_COOKIE,
    )

    assert route_state.pending_state.forget_pending["token"] == "forget1"
    assert route_state.pending_state.routed_action_pending["token"] == "route1"


def test_prepare_chat_route_state_does_not_run_free_text_semantic_parsers(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("free-text semantic parser must not run in route preparation")

    removed_parsers = (
        "_parse_connection_delete_request",
        "_parse_connection_create_request",
        "_parse_connection_update_request",
        "_parse_update_run_request",
        "_parse_update_status_request",
        "_parse_backup_export_request",
        "_parse_backup_import_request",
        "_parse_stats_request",
        "_parse_activities_request",
    )
    assert all(not hasattr(chat_admin_actions, name) for name in removed_parsers)

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
    )
    request.state.auth_role = "admin"
    request.state.can_access_advanced_config = True
    route_state = prepare_chat_route_state(
        request=request,
        clean_message="starte update",
        username="neo",
        lang="de",
        pipeline=SimpleNamespace(classify_routing=forbidden),
        request_cookie_value=lambda _request, _name: "",
        sanitize_username=lambda value: str(value or "").strip(),
        sanitize_connection_name=lambda value: str(value or "").strip(),
        sanitize_role=lambda value: str(value or "").strip() or "user",
        forget_signing_secret="forget-secret",
        pending_signing_secret="pending-secret",
        connection_pending_max_age_seconds=600,
        forget_pending_cookie=main_mod.FORGET_PENDING_COOKIE,
        connection_delete_pending_cookie=main_mod.CONNECTION_DELETE_PENDING_COOKIE,
        connection_create_pending_cookie=main_mod.CONNECTION_CREATE_PENDING_COOKIE,
        connection_update_pending_cookie=main_mod.CONNECTION_UPDATE_PENDING_COOKIE,
        update_pending_cookie=main_mod.UPDATE_PENDING_COOKIE,
        routed_action_pending_cookie=main_mod.ROUTED_ACTION_PENDING_COOKIE,
    )

    assert route_state.admin_requests.update_run_request is False


def test_render_assistant_message_html_supports_internal_links() -> None:
    rendered = str(main_mod._render_assistant_message_html("[Stats öffnen](/stats)"))

    assert 'href="/stats"' in rendered
    assert 'target="_blank"' in rendered










@pytest.mark.parametrize("message", ("hallo", "/lernen start", "/lernen stop", "/lernen abbrechen"))
def test_former_chat_learn_commands_follow_normal_chat_flow(monkeypatch, message: str) -> None:
    calls: list[str] = []

    async def fake_process(_self, clean_message, **_kwargs):  # noqa: ANN001
        calls.append(str(clean_message))
        return PipelineResult(
            request_id="r-retired-learn-mode",
            text=f"normal-flow:{clean_message}",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["chat"],
            skill_errors=[],
            router_level=1,
            duration_ms=1,
            detail_lines=[],
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    client = _user_client(monkeypatch)

    response = client.post(
        "/chat",
        data={"message": message, "csrf_token": client.headers["x-csrf-token"]},
    )

    assert response.status_code == 200
    assert f"normal-flow:{message}" in response.text
    assert calls == [message]


def test_chat_can_save_current_history_as_note(monkeypatch, tmp_path) -> None:
    import aria.modules.chat_execution_composition.routes as chat_execution_routes

    saved: dict[str, object] = {}
    indexed: list[str] = []
    history = [
        {"role": "user", "text": "Wie geht es meinen Servern?", "timestamp": "2026-06-05T10:00:00Z"},
        {"role": "assistant", "text": "Alle Server sind erreichbar.", "timestamp": "2026-06-05T10:00:02Z"},
    ]

    class FakeNotesStore:
        def __init__(self, root):
            saved["root"] = str(root)

        def save_note(self, user_id, *, title, folder, tags, body):
            saved.update({"user_id": user_id, "title": title, "folder": folder, "tags": list(tags), "body": body})
            return SimpleNamespace(note_id="chat-note-1", title=title, folder=folder, tags=list(tags), body=body)

    class FakeNotesIndex:
        def __init__(self, *_args, **_kwargs):
            pass

        async def reindex_note(self, note):
            indexed.append(note.note_id)
            return {"chunk_count": 2}

        async def aclose(self):
            pass

    monkeypatch.setattr(chat_execution_routes, "NotesStore", FakeNotesStore)
    monkeypatch.setattr(chat_execution_routes, "NotesIndex", FakeNotesIndex)
    monkeypatch.setattr(chat_execution_routes, "notes_index_enabled", lambda _settings: True)

    state = asyncio.run(
        chat_execution_routes._save_chat_history_as_note(
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(), embeddings=SimpleNamespace()),
            username="neo",
            history=history,
            language="de",
        )
    )

    assert "Chat als Notiz gespeichert" in state.assistant_text
    assert saved["user_id"] == "neo"
    assert str(saved["folder"]).startswith("Chats/")
    assert saved["tags"] == ["chat", "archive", "aria"]
    assert "Wie geht es meinen Servern?" in str(saved["body"])
    assert "Alle Server sind erreichbar." in str(saved["body"])
    assert "/chat note" not in str(saved["body"])
    assert "`/notes?note=chat-note-1#note-editor`" in state.assistant_text
    assert indexed == ["chat-note-1"]






def test_chat_catalog_memory_import_path_fails_closed_without_memory_route(monkeypatch) -> None:
    import aria.modules.chat_surface.catalog as chat_catalog

    monkeypatch.setattr(chat_catalog, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/import"):
        chat_catalog.build_chat_command_catalog(
            lang="de",
            auth_role="user",
            advanced_mode=False,
            recall_templates=[],
            store_templates=[],
            recipe_trigger_hints=[],
        )




def test_chat_toolbox_contains_save_chat_as_note_command() -> None:
    from aria.modules.chat_surface.catalog import build_chat_command_catalog

    entries, _titles, groups = build_chat_command_catalog(
        lang="de",
        auth_role="user",
        advanced_mode=False,
        recall_templates=[],
        store_templates=[],
        recipe_trigger_hints=[],
    )

    matching = [entry for entry in entries if str(entry.get("insert", "")).strip() == "/chat note"]
    assert matching
    assert matching[0]["label"] == "Chat als Notiz speichern"
    assert any(item.get("insert") == "/chat note " for group in groups for item in group.get("items", []))


def test_chat_toolbox_links_to_document_import() -> None:
    from aria.modules.chat_surface.catalog import build_chat_command_catalog

    entries, _titles, groups = build_chat_command_catalog(
        lang="de",
        auth_role="user",
        advanced_mode=False,
        recall_templates=[],
        store_templates=[],
        recipe_trigger_hints=[],
    )

    matching = [entry for entry in entries if entry.get("href") == "/memories/import#document-import"]
    assert matching
    assert matching[0]["label"] == "Dokument importieren"
    document_groups = [group for group in groups if group.get("key") == "documents"]
    assert document_groups
    assert document_groups[0]["title"] == "Dokumente"
    assert any(item.get("href") == "/memories/import#document-import" for item in document_groups[0].get("items", []))


def test_chat_notes_flow_does_not_route_natural_question_without_llm_contract(monkeypatch, tmp_path) -> None:
    import aria.modules.notes.chat_flows as chat_notes_flows

    calls: list[str] = []

    async def fake_search_note_hits(*, base_dir, username, settings, query, limit):
        calls.append(query)
        return [
            SimpleNamespace(
                note_id="note-aria",
                title="ARIA",
                folder="ARIA",
                snippet="ARIA ist der lokale Agent.",
            )
        ]

    monkeypatch.setattr(chat_notes_flows, "search_note_hits", fake_search_note_hits)

    outcome = asyncio.run(
        chat_notes_flows.handle_chat_notes_flow(
            clean_message="was steht in meinen notizen zu ARIA?",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(),
        )
    )

    assert outcome is None
    assert calls == []


def test_web_chat_has_no_independent_followup_semantic_rewriter() -> None:
    import aria.modules.chat_execution_composition.routes as chat_execution_routes

    assert not hasattr(chat_execution_routes, "_resolve_pipeline_followup_message")
    assert not hasattr(chat_execution_routes, "_rewrite_vague_web_search_followup")
    assert not hasattr(chat_execution_routes, "_rewrite_vague_local_context_followup")


def test_web_chat_layer_has_no_independent_feedback_learning_scheduler() -> None:
    import aria.modules.chat_execution_composition.routes as chat_execution_routes

    assert not hasattr(chat_execution_routes, "_schedule_user_feedback_learning")
    assert not hasattr(chat_execution_routes, "_should_schedule_user_feedback_learning")


def test_missing_input_routed_action_sets_continuation_cookie_without_confirmation_payload() -> None:
    result = PipelineResult(
        request_id="r1",
        text="Ich brauche noch ein Ziel.",
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        intents=["capability:ssh_command"],
        skill_errors=[],
        router_level=1,
        duration_ms=10,
        detail_lines=[],
        pending_action={
            "query": "Führe uptime auf allen SSH Hosts aus.",
            "candidate_kind": "capability_draft",
            "candidate_id": "ssh_command",
            "routing_decision": {"found": True, "kind": "ssh"},
            "action_decision": {
                "found": True,
                "candidate_kind": "capability_draft",
                "candidate_id": "ssh_command",
                "missing_input": "connection_ref",
            },
            "payload": {
                "found": True,
                "capability": "ssh_command",
                "connection_kind": "ssh",
                "connection_ref": "",
                "content": "uptime",
                "missing_fields": ["connection_ref"],
            },
            "safety_decision": {"action": "ask_user", "reason": "missing_parameters"},
            "execution_decision": {"next_step": "ask_user"},
        },
    )

    outcome = asyncio.run(
        chat_pending_flows.apply_chat_result_pending_followups(
            result=result,
            assistant_text=result.text,
            icon="⚠",
            intent_label="action",
            username="neo",
            settings=SimpleNamespace(),
            is_english=False,
            language="de",
            signing_secret="pending-secret",
            sanitize_username=lambda value: str(value or "").strip(),
            sanitize_connection_name=lambda value: str(value or "").strip(),
            alert_sender=lambda *_args, **_kwargs: None,
        )
    )

    assert outcome.intent_label == "routed_action_needs_input"
    assert chat_pending_flows.COOKIE_ROUTED_ACTION in outcome.set_cookies
    assert chat_pending_flows.COOKIE_ROUTED_ACTION not in outcome.clear_cookies
    assert outcome.routed_action_confirm_command is None
    assert outcome.routed_action_confirm_payload is None


def test_complete_payload_with_non_confirmation_execution_step_is_not_confirmable() -> None:
    result = PipelineResult(
        request_id="r1",
        text="Geplante Aktion: file_list: smb/fischer_ronny; Pixel Axiom",
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        intents=["capability:file_list"],
        skill_errors=[],
        router_level=1,
        duration_ms=10,
        detail_lines=[
            "Routing Debug: action_contract_preflight status=held "
            "reason=confirmation_required_by_action_contract"
        ],
        pending_action={
            "query": "Was steht in meinen Notizen über Death Pays Overtime?",
            "candidate_kind": "capability_draft",
            "candidate_id": "file_list",
            "routing_decision": {"found": True, "kind": "smb", "ref": "fischer_ronny"},
            "action_decision": {"found": True, "candidate_kind": "capability_draft", "candidate_id": "file_list"},
            "payload": {
                "found": True,
                "capability": "file_list",
                "connection_kind": "smb",
                "connection_ref": "fischer_ronny",
                "path": "Pixel Axiom",
                "missing_fields": [],
            },
            "safety_decision": {"action": "allow", "reason": "No_extra_confirmation_needed."},
            "execution_decision": {"next_step": "allow"},
        },
    )

    outcome = asyncio.run(
        chat_pending_flows.apply_chat_result_pending_followups(
            result=result,
            assistant_text=result.text,
            icon="🟡",
            intent_label="routed_action_pending",
            username="neo",
            settings=SimpleNamespace(),
            is_english=False,
            language="de",
            signing_secret="pending-secret",
            sanitize_username=lambda value: str(value or "").strip(),
            sanitize_connection_name=lambda value: str(value or "").strip(),
            alert_sender=lambda *_args, **_kwargs: None,
        )
    )

    assert outcome.intent_label == "routed_action_invalid_token"
    assert chat_pending_flows.COOKIE_ROUTED_ACTION not in outcome.set_cookies
    assert chat_pending_flows.COOKIE_ROUTED_ACTION in outcome.clear_cookies
    assert outcome.routed_action_confirm_command is None
    assert outcome.routed_action_confirm_payload is None


def test_chat_template_does_not_restore_completed_routed_confirmation() -> None:
    template = (Path(main_mod.__file__).resolve().parent / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "(button) => !button.disabled &&" in template
    assert 'button.removeAttribute("data-routed-action-pending")' in template


def test_chat_template_keeps_cookie_bound_confirmation_buttons_single_use() -> None:
    template = (Path(main_mod.__file__).resolve().parent / "templates" / "chat.html").read_text(encoding="utf-8")

    assert 'button.getAttribute("data-single-use-confirmation") === "true"' in template
    assert "!routedActionPending && !singleUseConfirmation" in template


def test_chat_template_has_no_dead_response_mode_control() -> None:
    template = (Path(main_mod.__file__).resolve().parent / "templates" / "chat.html").read_text(encoding="utf-8")

    assert 'name="chat_mode"' not in template
    assert "chat-mode-control" not in template
    assert 'formData.set("chat_mode"' not in template


def test_chat_route_accepts_request_without_dead_mode_field(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-no-mode",
            text="ok",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["chat"],
            skill_errors=[],
            router_level=1,
            duration_ms=1,
            detail_lines=[],
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    client = _admin_client(monkeypatch)

    response = client.post(
        "/chat",
        data={"message": "hallo", "csrf_token": client.headers["x-csrf-token"]},
    )

    assert response.status_code == 200
    assert "ok" in response.text


def test_chat_does_not_offer_confirm_button_for_empty_ssh_command_contract(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r1",
            text="ARIA moechte diese Aktion vor der Ausfuehrung noch bestaetigen.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            pending_action={
                "query": "zeige mir den status vom monitoring server und nutze nur belegte kommandos",
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "routing_decision": {"found": True, "kind": "ssh", "ref": "ops-alert-01"},
                "action_decision": {"found": True, "candidate_kind": "template", "candidate_id": "ssh_run_command"},
                "payload": {
                    "found": True,
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "connection_ref": "ops-alert-01",
                    "content": "",
                    "preview": "SSH command",
                    "missing_fields": [],
                },
                "safety_decision": {"action": "ask_user"},
                "execution_decision": {"next_step": "ask_user"},
            },
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)

    client = _admin_client(monkeypatch)
    preview = client.post(
        "/chat",
        data={
            "message": "zeige mir den status vom monitoring server und nutze nur belegte kommandos",
            "csrf_token": client.headers["x-csrf-token"],
        },
    )

    assert preview.status_code == 200
    assert "chat-confirm-action" not in preview.text
    assert "Action-Contract fehlt" in preview.text or "action contract is missing" in preview.text


def test_chat_renders_native_learning_suggestion_as_nonblocking_action(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-learning-suggestion",
            text="Der aktuelle Befehl wurde ausgefuehrt.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["native_agent"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            suggestion_affordance={
                "kind": "recurrence",
                "label": "Save as Recipe",
                "caption": "Save this repeated action as an inactive Recipe.",
                "confirm_command": "confirm action na123456789abc",
                "token": "na123456789abc",
            },
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)

    client = _admin_client(monkeypatch)
    response = client.post(
        "/chat",
        data={"message": "wiederhole die Aktion", "csrf_token": client.headers["x-csrf-token"]},
    )

    assert response.status_code == 200
    assert "Der aktuelle Befehl wurde ausgefuehrt." in response.text
    assert 'data-message="confirm action na123456789abc"' in response.text
    assert "chat-queue-confirmation-action" in response.text
    assert "Als Rezept speichern" in response.text or "Save as Recipe" in response.text


@pytest.mark.parametrize(
    ("language", "suggestion", "expected_label", "expected_caption", "forbidden_words"),
    (
        (
            "de",
            {"kind": "memory"},
            "Als Erinnerung speichern",
            "Diese Präferenz als persönliche Erinnerung speichern.",
            ("Rezept", "Recipe"),
        ),
        (
            "en",
            {"kind": "memory"},
            "Save as memory",
            "Save this preference as a personal memory.",
            ("Rezept", "Recipe"),
        ),
        (
            "de",
            {"kind": "recurrence"},
            "Als Rezept speichern",
            "Diese wiederholte Aktion als inaktiven Rezeptentwurf speichern.",
            (),
        ),
        (
            "de",
            {"kind": "cross_host", "new_host": "srv-b"},
            "Kopie fuer srv-b anlegen",
            "Eine inaktive Kopie dieses Rezepts fuer srv-b anlegen.",
            (),
        ),
    ),
)
def test_chat_localizes_learning_suggestion_by_exact_kind(
    monkeypatch, language, suggestion, expected_label, expected_caption, forbidden_words,  # noqa: ANN001
) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id=f"r-{language}-{suggestion['kind']}",
            text="Verstanden.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["native_agent"],
            skill_errors=[],
            router_level=1,
            duration_ms=1,
            detail_lines=[],
            suggestion_affordance={
                **suggestion,
                "label": "upstream label",
                "caption": "upstream caption",
                "confirm_command": "confirm action na123456789abc",
                "token": "na123456789abc",
            },
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    client = _admin_client(monkeypatch)
    client.cookies.set(_scoped_cookie(main_mod.LANG_COOKIE), language)
    response = client.post(
        "/chat",
        data={"message": "zeige Vorschlag", "csrf_token": client.headers["x-csrf-token"]},
    )

    assert response.status_code == 200
    caption_match = re.search(r'class="chat-suggestion-caption">([^<]*)</p>', response.text)
    button_match = re.search(
        r'class="chat-confirm-action chat-queue-action chat-queue-confirmation-action js-chat-send-message"'
        r'.*?>\s*([^<]+?)\s*</button>',
        response.text,
        flags=re.DOTALL,
    )
    assert caption_match and button_match
    rendered_copy = f"{button_match.group(1).strip()}\n{caption_match.group(1).strip()}"
    assert button_match.group(1).strip() == expected_label
    assert caption_match.group(1).strip() == expected_caption
    assert all(word not in rendered_copy for word in forbidden_words)


def test_memory_suggestion_button_confirms_existing_memory_capture_pending(monkeypatch, tmp_path) -> None:
    token = "na123456789abc"
    claim = {
        "claim_kind": "preference",
        "subject": "user",
        "predicate": "preferred_tea",
        "value": "grüner tee",
    }
    pending_store = NativePendingStore(tmp_path / "memory-button-pending.sqlite3")
    ledger = ActionConfirmationLedger(tmp_path / "memory-button-ledger.sqlite3")
    pending_store.put(
        user_id="neo",
        token=token,
        tool_name="memory_capture",
        frozen_arguments=claim,
        preview="Save personal memory",
        request_message="Ich trinke am liebsten grünen Tee.",
    )
    stored: list[dict[str, object]] = []

    async def fake_store_personal_claim(**kwargs):  # noqa: ANN003
        stored.append(dict(kwargs["claim"]))
        return {"stored": True, "reason": "claim_activated"}

    monkeypatch.setattr(memory_native_tools, "store_personal_claim", fake_store_personal_claim)
    owner = SimpleNamespace(
        memory_skill=object(),
        llm_client=object(),
        facts_collection_for_user=lambda user_id: f"facts-{user_id}",
        preferences_collection_for_user=lambda user_id: f"preferences-{user_id}",
    )
    binding = next(
        item for item in memory_native_tools.native_tool_contributions(owner)
        if item.contract.name == "memory_capture"
    )
    confirmation_tokens: list[str] = []

    async def completion(**_request):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="Als persönliche Erinnerung gespeichert.", tool_calls=[]),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    async def fake_process(message, *_args, confirmation_token="", **kwargs):  # noqa: ANN001, ANN003
        if not confirmation_token:
            return PipelineResult(
                request_id="r-memory-button",
                text="Das klingt nach einer klaren Präferenz.",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                intents=["native_agent"],
                skill_errors=[],
                router_level=1,
                duration_ms=1,
                detail_lines=[],
                suggestion_affordance={
                    "kind": "memory",
                    "label": "upstream label",
                    "caption": "upstream caption",
                    "confirm_command": f"confirm action {token}",
                    "token": token,
                },
            )
        confirmation_tokens.append(confirmation_token)
        outcome = await run_native_agent_turn(
            message=message,
            user_id=kwargs["user_id"],
            auth_role=kwargs["auth_role"],
            turn_id="memory-button-confirm",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(binding,),
            completion=completion,
            pending_store=pending_store,
            confirmation_ledger=ledger,
            confirmation_token=confirmation_token,
        )
        return PipelineResult(
            request_id="r-memory-button-confirm",
            text=outcome.message,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["native_agent"],
            skill_errors=[],
            router_level=1,
            duration_ms=1,
            detail_lines=[],
            clear_routed_action_affordance=outcome.clear_confirmation_affordance,
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    client = _admin_client(monkeypatch)
    first = client.post(
        "/chat",
        data={"message": "zeige Vorschlag", "csrf_token": client.headers["x-csrf-token"]},
    )
    command_match = re.search(r'data-message="(confirm action na[0-9a-f]+)"', first.text)
    assert first.status_code == 200 and command_match

    confirmed = client.post(
        "/chat",
        data={"message": command_match.group(1), "csrf_token": client.headers["x-csrf-token"]},
    )

    assert confirmed.status_code == 200
    assert confirmation_tokens == [token]
    assert pending_store.peek(user_id="neo", token=token) is None
    assert stored == [{
        **claim,
        "scope": "global",
        "scope_ref": "",
        "explicit_user_statement": True,
        "authority": "explicit_user",
        "risk": "low",
        "confidence": 1.0,
        "source": "native_capture",
    }]


def test_chat_rejects_unknown_routed_action_confirm_token(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        raise AssertionError("pipeline.process should not run for a bare confirm token")

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)

    client = _admin_client(monkeypatch)
    confirm = client.post("/chat", data={"message": "bestätige aktion ec891503", "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "ungültig oder abgelaufen" in confirm.text or "invalid or expired" in confirm.text
    assert "Plane die Aktion bitte neu" in confirm.text or "Plan the action again" in confirm.text


def test_pending_input_flow_ignores_unrelated_new_capability_request() -> None:
    class FakePipeline:
        def _classify_capability_draft(self, message: str, *, language: str | None = None):
            del language
            if "rss" in message.lower():
                return SimpleNamespace(capability="feed_read", connection_kind="rss")
            return None

        async def continue_pending_routed_action_input(self, *_args, **_kwargs):
            raise AssertionError("pending input should not continue for an unrelated capability request")

    outcome = asyncio.run(
        chat_pending_flows.handle_chat_pending_input_flow(
            clean_message="gib mir aktuelle security news aus rss",
            state=chat_pending_flows.ChatPendingState(
                routed_action_pending={
                    "user_id": "neo",
                    "action_decision": {"missing_input": "command"},
                    "payload": {
                        "capability": "ssh_command",
                        "connection_kind": "ssh",
                        "connection_ref": "ops-mgmt-01",
                    },
                }
            ),
            username="neo",
            pipeline=FakePipeline(),
            settings=SimpleNamespace(connections=SimpleNamespace()),
            language="de",
            is_english=False,
            intent_badge=lambda intents, errors=None: ("💬", intents[0] if intents else "chat"),  # noqa: ARG005
            friendly_error_text=lambda errors=None: "",  # noqa: ARG005
            signing_secret="secret",
            sanitize_username=lambda value: str(value or ""),
            sanitize_connection_name=lambda value: str(value or ""),
            auth_role="admin",
            alert_sender=lambda *args, **kwargs: None,
        )
    )

    assert outcome is None


def test_pending_input_flow_ignores_discord_request_after_smb_path_prompt() -> None:
    class FakePipeline:
        def _classify_capability_draft(self, message: str, *, language: str | None = None):
            del language
            if "discord" in message.lower():
                return SimpleNamespace(capability="discord_send", connection_kind="discord")
            return None

        async def continue_pending_routed_action_input(self, *_args, **_kwargs):
            raise AssertionError("pending SMB path prompt must not consume a fresh Discord action")

    outcome = asyncio.run(
        chat_pending_flows.handle_chat_pending_input_flow(
            clean_message="schick eine testnachricht an discord: alpha238 läuft",
            state=chat_pending_flows.ChatPendingState(
                routed_action_pending={
                    "user_id": "neo",
                    "action_decision": {"missing_input": "path"},
                    "payload": {
                        "capability": "file_list",
                        "connection_kind": "smb",
                        "connection_ref": "example_share",
                    },
                }
            ),
            username="neo",
            pipeline=FakePipeline(),
            settings=SimpleNamespace(connections=SimpleNamespace()),
            language="de",
            is_english=False,
            intent_badge=lambda intents, errors=None: ("💬", intents[0] if intents else "chat"),  # noqa: ARG005
            friendly_error_text=lambda errors=None: "",  # noqa: ARG005
            signing_secret="secret",
            sanitize_username=lambda value: str(value or ""),
            sanitize_connection_name=lambda value: str(value or ""),
            auth_role="admin",
            alert_sender=lambda *args, **kwargs: None,
        )
    )

    assert outcome is None


def test_chat_handles_recipe_errors_without_crashing_and_sends_alert(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-recipe-error",
            text="RSS-Kategorie konnte nicht vollständig gelesen werden.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:feed_read"],
            skill_errors=[
                "recipe_smb_read_error:Failed to retrieve on Example_Share: Unable to open file\n"
                "==================== SMB Message 0 ====================\n"
                "SMB Header:\n"
                "-----------\n"
                "Command: 0x03 (SMB2_COM_TREE_CONNECT)",
            ],
            router_level=1,
            duration_ms=10,
            detail_lines=["Ausgeführt via RSS-Kategorie `Security`"],
        )

    alerts: list[dict[str, object]] = []

    def fake_send_discord_alerts(settings, **kwargs):  # noqa: ARG001
        alerts.append(dict(kwargs))
        return []

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod, "send_discord_alerts", fake_send_discord_alerts)

    client = _admin_client(monkeypatch)
    response = client.post("/chat", data={"message": "gib mir aktuelle security news aus rss", "csrf_token": client.headers["x-csrf-token"]})

    assert response.status_code == 200
    assert "RSS-Kategorie konnte nicht vollständig gelesen werden." in response.text
    assert alerts
    assert alerts[0]["category"] == "recipe_errors"
    assert "Unable to open file" in str(alerts[0]["lines"])
    assert "SMB2_COM_TREE_CONNECT" not in str(alerts[0]["lines"])


def test_chat_categorizes_native_agent_errors_separately(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-native-agent-error",
            text="Die gesammelten Ergebnisse konnten nicht abschließend zusammengefasst werden.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["native_agent"], skill_errors=["native_agent_budget_finalization_failed"],
            router_level=2, duration_ms=10, detail_lines=[],
        )

    alerts: list[dict[str, object]] = []

    def fake_send_discord_alerts(settings, **kwargs):  # noqa: ARG001
        alerts.append(dict(kwargs))
        return []

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod, "send_discord_alerts", fake_send_discord_alerts)

    client = _admin_client(monkeypatch)
    response = client.post(
        "/chat", data={"message": "komplexe Frage", "csrf_token": client.headers.get("x-csrf-token", "")},
    )

    assert response.status_code == 200
    assert alerts
    assert alerts[0]["category"] == "native_agent_errors"


def test_chat_routes_web_source_fail_closed_as_skill_alert(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-web-source-error",
            text="Ich habe die Websuche ausgeführt, aber keine belastbaren Quellen zum angefragten Thema gefunden.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["web_search"],
            skill_errors=["web_source_no_reliable_sources"],
            router_level=1,
            duration_ms=10,
            detail_lines=[
                "Routing Debug: web_source_acquisition_plan used=true planned_queries=3 required=rabbit.tech official website",
                "Routing Debug: web_source_queries count=4 queries=site:rabbit.tech Rabbit R1 update | Rabbit R1 update",
                "Routing Debug: web_source_contract required_domains=rabbit.tech missing_domains=rabbit.tech result_domains=hub.docker.com executed_queries=site:rabbit.tech Rabbit R1 update | Rabbit R1 update",
                "Routing Debug: web_source_curation sufficient=false reason=different entity",
            ],
        )

    alerts: list[dict[str, object]] = []

    def fake_send_discord_alerts(settings, **kwargs):  # noqa: ARG001
        alerts.append(dict(kwargs))
        return []

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod, "send_discord_alerts", fake_send_discord_alerts)

    client = _admin_client(monkeypatch)
    response = client.post("/chat", data={"message": "gibts vom rabbit r1 ein update?", "csrf_token": client.headers["x-csrf-token"]})

    assert response.status_code == 200
    assert "keine belastbaren Quellen" in response.text
    assert "memory_error" not in response.text
    assert alerts
    assert alerts[0]["category"] == "skill_errors"
    assert "Websuche" in str(alerts[0]["title"])
    assert "Web-Source-Diagnose" in str(alerts[0]["lines"])
    assert "missing_domains=rabbit.tech" in str(alerts[0]["lines"])


def test_chat_does_not_offer_confirm_when_target_profile_is_still_missing(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-missing-target",
            text="Für `monitoring server` habe ich noch kein passendes SSH-Profil. Verfügbare SSH-Profile: ops-mgmt-01, ops-monitor-01. Antworte einfach mit dem passenden Profilnamen. Wenn es passt, kann ARIA sich die Zuordnung danach als Alias merken.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            pending_action={
                "query": "wie geht es dem monitoring server",
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "routing_decision": {"found": True, "kind": "ssh", "ref": ""},
                "action_decision": {
                    "found": True,
                    "candidate_kind": "template",
                    "candidate_id": "ssh_run_command",
                },
                "payload": {
                    "found": True,
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "connection_ref": "",
                    "requested_connection_ref": "monitoring server",
                    "content": "uptime",
                    "preview": "SSH command: uptime",
                    "missing_fields": ["connection_ref"],
                },
                "safety_decision": {"action": "ask_user", "reason_label": "Es fehlen noch Pflichtangaben: Zielprofil."},
                "execution_decision": {"next_step": "ask_user"},
            },
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "wie geht es dem monitoring server", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    assert "passendes SSH-Profil" in preview.text
    assert "bestätige aktion" not in preview.text.lower()
    assert "confirm action" not in preview.text.lower()


def test_chat_badge_details_include_web_request_timing(monkeypatch) -> None:
    from html import unescape

    provider_detail = 'Routing Debug: web_search_provider query_index=1 {"engine_errors":[{"engine":"brave","class":"rate_limit","suspended":true}]}'

    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-web-timing",
            text="ok",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["chat"],
            skill_errors=[],
            router_level=1,
            duration_ms=7,
            detail_lines=["Routing Debug: fake_pipeline", provider_detail],
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    client = _admin_client(monkeypatch)

    response = client.post("/chat", data={"message": "hallo", "csrf_token": client.headers["x-csrf-token"]})

    assert response.status_code == 200
    assert "Routing Debug: fake_pipeline" in response.text
    assert provider_detail in unescape(response.text)
    assert "Routing Debug: web_request_timing" in response.text
    assert "Routing Debug: web_total_wall_time" in response.text
    assert "Routing Debug: web_post_pipeline_timing" in response.text
    assert "Routing Debug: web_route_timing" in response.text
    assert "history_load_ms=" in response.text
    assert "pre_template_total_ms=" in response.text
    assert response.headers["x-aria-web-template-ms"].isdigit()
    assert response.headers["x-aria-web-cookies-ms"].isdigit()
    assert "pipeline_ms=7" in response.text
