from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient
from starlette.requests import Request

import aria.main as main_mod
import aria.web.chat_admin_actions as chat_admin_actions
import aria.web.chat_pending_flows as chat_pending_flows
from aria.web.chat_route_helpers import prepare_chat_route_state
from aria.core.pipeline import PipelineResult
from aria.skills.memory import MemorySkill


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
        safe_fix_pending_cookie=main_mod.SAFE_FIX_PENDING_COOKIE,
        connection_delete_pending_cookie=main_mod.CONNECTION_DELETE_PENDING_COOKIE,
        connection_create_pending_cookie=main_mod.CONNECTION_CREATE_PENDING_COOKIE,
        connection_update_pending_cookie=main_mod.CONNECTION_UPDATE_PENDING_COOKIE,
        update_pending_cookie=main_mod.UPDATE_PENDING_COOKIE,
        routed_action_pending_cookie=main_mod.ROUTED_ACTION_PENDING_COOKIE,
    )

    assert route_state.pending_state.forget_pending["token"] == "forget1"
    assert route_state.pending_state.routed_action_pending["token"] == "route1"


def test_render_assistant_message_html_supports_internal_links() -> None:
    rendered = str(main_mod._render_assistant_message_html("[Stats öffnen](/stats)"))

    assert 'href="/stats"' in rendered
    assert 'target="_blank"' in rendered


def test_chat_can_offer_config_backup_download_link(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "build_config_backup_payload", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        main_mod,
        "summarize_config_backup_payload",
        lambda _payload: {
            "secret_count": 4,
            "user_count": 2,
            "custom_skill_count": 3,
            "prompt_file_count": 5,
            "support_file_count": 1,
        },
    )

    client = _admin_client(monkeypatch, advanced_mode=True)
    response = client.post("/chat", data={"message": "exportiere config backup", "csrf_token": client.headers["x-csrf-token"]})

    assert response.status_code == 200
    assert "/config/backup/export" in response.text
    assert "Connections werden" in response.text or "Connections are included" in response.text


def test_chat_can_start_controlled_update_with_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "trigger_update_helper_run", lambda _config: {"status": "accepted"})

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "starte update", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    match = re.search(r"bestätige update ([a-z0-9]{8})", preview.text, re.IGNORECASE)
    assert match

    confirm = client.post("/chat", data={"message": f"bestätige update {match.group(1)}", "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "Kontrolliertes Update gestartet" in confirm.text or "Controlled update started" in confirm.text
    assert "/updates/running" in confirm.text


def test_chat_can_show_update_helper_status(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(
        main_mod,
        "fetch_update_helper_status",
        lambda _config: {
            "status": "running",
            "running": True,
            "current_step": "Run internal aria-pull/update-local flow",
            "last_result": "",
            "last_error": "",
        },
    )

    client = _admin_client(monkeypatch)
    response = client.post("/chat", data={"message": "zeige update status", "csrf_token": client.headers["x-csrf-token"]})

    assert response.status_code == 200
    assert "Update-Helper" in response.text
    assert "/updates" in response.text
    assert "/updates/running" in response.text


def test_chat_can_confirm_pending_routed_action(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r1",
            text="ARIA wuerde vor der Ausfuehrung auf discord/alerts noch nachfragen.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:discord_send"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            pending_action={
                "query": "schick eine testnachricht",
                "candidate_kind": "template",
                "candidate_id": "discord_send_message",
                "routing_decision": {"found": True, "kind": "discord", "ref": "alerts"},
                "action_decision": {"found": True, "candidate_kind": "template", "candidate_id": "discord_send_message"},
                "payload": {
                    "found": True,
                    "capability": "discord_send",
                    "connection_kind": "discord",
                    "connection_ref": "alerts",
                    "content": "ARIA Testnachricht",
                    "preview": 'Discord-Nachricht: "ARIA Testnachricht"',
                    "missing_fields": [],
                },
                "safety_decision": {"action": "ask_user", "reason_label": "Ausgehende Nachrichten sollten vor dem Senden kurz bestaetigt werden."},
                "execution_decision": {"next_step": "ask_user", "summary": "ARIA wuerde vor der Ausfuehrung auf discord/alerts noch nachfragen."},
            },
        )

    async def fake_execute_pending(*_args, **_kwargs):
        return PipelineResult(
            request_id="r2",
            text="Discord gesendet.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:discord_send"],
            skill_errors=[],
            router_level=1,
            duration_ms=12,
            detail_lines=['Discord-Nachricht: "ARIA Testnachricht"'],
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "execute_pending_routed_action", fake_execute_pending)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "schick eine testnachricht", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    assert "js-chat-send-message" in preview.text
    match = re.search(r'data-message="((?:bestätige aktion|bestaetige aktion|confirm action) [a-z0-9]{8})"', preview.text, re.IGNORECASE)
    assert match

    command = match.group(1)
    confirm = client.post("/chat", data={"message": command, "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "Discord gesendet." in confirm.text


def test_chat_confirm_button_can_post_signed_pending_payload_without_cookie(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r1",
            text="ARIA wuerde vor der Ausfuehrung auf discord/alerts noch nachfragen.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:discord_send"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            pending_action={
                "query": "schick eine testnachricht",
                "candidate_kind": "template",
                "candidate_id": "discord_send_message",
                "routing_decision": {"found": True, "kind": "discord", "ref": "alerts"},
                "action_decision": {"found": True, "candidate_kind": "template", "candidate_id": "discord_send_message"},
                "payload": {
                    "found": True,
                    "capability": "discord_send",
                    "connection_kind": "discord",
                    "connection_ref": "alerts",
                    "content": "ARIA Testnachricht",
                    "preview": 'Discord-Nachricht: "ARIA Testnachricht"',
                    "missing_fields": [],
                },
                "safety_decision": {"action": "ask_user", "reason_label": "Ausgehende Nachrichten sollten vor dem Senden kurz bestaetigt werden."},
                "execution_decision": {"next_step": "ask_user", "summary": "ARIA wuerde vor der Ausfuehrung auf discord/alerts noch nachfragen."},
            },
        )

    async def fake_execute_pending(*_args, **_kwargs):
        return PipelineResult(
            request_id="r2",
            text="Discord gesendet.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:discord_send"],
            skill_errors=[],
            router_level=1,
            duration_ms=12,
            detail_lines=['Discord-Nachricht: "ARIA Testnachricht"'],
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "execute_pending_routed_action", fake_execute_pending)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "schick eine testnachricht", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    command_match = re.search(r'data-message="((?:bestätige aktion|bestaetige aktion|confirm action) [a-z0-9]{8})"', preview.text, re.IGNORECASE)
    payload_match = re.search(r'data-routed-action-pending="([^"]+)"', preview.text)
    assert command_match
    assert payload_match

    fresh_client = _admin_client(monkeypatch)
    confirm = fresh_client.post(
        "/chat",
        data={
            "message": command_match.group(1),
            "routed_action_pending": payload_match.group(1),
            "csrf_token": fresh_client.headers["x-csrf-token"],
        },
    )

    assert confirm.status_code == 200
    assert "Discord gesendet." in confirm.text


def test_chat_rejects_unknown_routed_action_confirm_token(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        raise AssertionError("pipeline.process should not run for a bare confirm token")

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)

    client = _admin_client(monkeypatch)
    confirm = client.post("/chat", data={"message": "bestätige aktion ec891503", "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "ungültig oder abgelaufen" in confirm.text or "invalid or expired" in confirm.text


def test_chat_can_continue_pending_routed_action_missing_input(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-missing-preview",
            text="Welche Nachricht soll ARIA senden?",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:discord_send"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            pending_action={
                "query": "schick an alerts",
                "candidate_kind": "template",
                "candidate_id": "discord_send_message",
                "routing_decision": {"found": True, "kind": "discord", "ref": "alerts"},
                "action_decision": {
                    "found": True,
                    "candidate_kind": "template",
                    "candidate_id": "discord_send_message",
                    "missing_input": "message",
                    "clarifying_question": "Welche Nachricht soll ARIA senden?",
                },
                "payload": {
                    "found": True,
                    "capability": "discord_send",
                    "connection_kind": "discord",
                    "connection_ref": "alerts",
                    "content": "",
                    "preview": "Discord-Nachricht",
                    "missing_fields": [],
                },
                "safety_decision": {"action": "ask_user"},
                "execution_decision": {"next_step": "ask_user"},
            },
        )

    async def fake_continue(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-missing-continued",
            text="ARIA wuerde vor der Ausfuehrung auf discord/alerts noch nachfragen.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:discord_send"],
            skill_errors=[],
            router_level=1,
            duration_ms=12,
            detail_lines=['Discord-Nachricht: "TESTNACHRICHT"'],
            pending_action={
                "query": "schick an alerts",
                "candidate_kind": "template",
                "candidate_id": "discord_send_message",
                "routing_decision": {"found": True, "kind": "discord", "ref": "alerts"},
                "action_decision": {"found": True, "candidate_kind": "template", "candidate_id": "discord_send_message"},
                "payload": {
                    "found": True,
                    "capability": "discord_send",
                    "connection_kind": "discord",
                    "connection_ref": "alerts",
                    "content": "TESTNACHRICHT",
                    "preview": 'Discord-Nachricht: "TESTNACHRICHT"',
                    "missing_fields": [],
                },
                "safety_decision": {"action": "ask_user", "reason_label": "Ausgehende Nachrichten sollten vor dem Senden kurz bestaetigt werden."},
                "execution_decision": {"next_step": "ask_user", "summary": "ARIA wuerde vor der Ausfuehrung auf discord/alerts noch nachfragen."},
            },
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "continue_pending_routed_action_input", fake_continue)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "schick an alerts", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    assert "Welche Nachricht soll ARIA senden?" in preview.text
    assert "bestätige aktion" not in preview.text.lower()


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
                        "connection_ref": "ubnsrv-mgmt-master",
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
                        "connection_ref": "fischer_ronny",
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
                "recipe_smb_read_error:Failed to retrieve on Fischer_Ronny: Unable to open file\n"
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


def test_chat_does_not_offer_confirm_when_target_profile_is_still_missing(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-missing-target",
            text="Für `monitoring server` habe ich noch kein passendes SSH-Profil. Verfügbare SSH-Profile: ubnsrv-mgmt-master, ubnsrv-netalert. Antworte einfach mit dem passenden Profilnamen. Wenn es passt, kann ARIA sich die Zuordnung danach als Alias merken.",
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


def test_chat_does_not_consume_new_request_as_missing_connection_ref_followup(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_process(_self, message, *_args, **_kwargs):
        calls.append(str(message))
        if message == "backup server status":
            return PipelineResult(
                request_id="r-missing-target",
                text="Für `backup server` habe ich noch kein passendes SSH-Profil. Verfügbare SSH-Profile: ubnsrv-netalert. Antworte einfach mit dem passenden Profilnamen. Wenn es passt, kann ARIA sich die Zuordnung danach als Alias merken.",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                intents=["capability:ssh_command"],
                skill_errors=[],
                router_level=1,
                duration_ms=10,
                detail_lines=[],
                pending_action={
                    "query": "backup server status",
                    "candidate_kind": "template",
                    "candidate_id": "ssh_run_command",
                    "routing_decision": {"found": True, "kind": "ssh", "ref": ""},
                    "action_decision": {
                        "found": True,
                        "candidate_kind": "template",
                        "candidate_id": "ssh_run_command",
                        "missing_input": "connection_ref",
                    },
                    "payload": {
                        "found": True,
                        "capability": "ssh_command",
                        "connection_kind": "ssh",
                        "connection_ref": "",
                        "requested_connection_ref": "backup server",
                        "content": "uptime",
                        "preview": "SSH command: uptime",
                        "missing_fields": ["connection_ref"],
                    },
                    "safety_decision": {"action": "ask_user"},
                    "execution_decision": {"next_step": "ask_user"},
                },
            )
        return PipelineResult(
            request_id="r-monitoring",
            text="Monitoring wurde normal neu verarbeitet.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
        )

    async def fake_continue(*_args, **_kwargs):
        raise AssertionError("Pending connection_ref flow should not consume a fresh monitoring request.")

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "continue_pending_routed_action_input", fake_continue)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "backup server status", "csrf_token": client.headers["x-csrf-token"]})
    assert preview.status_code == 200
    assert calls == ["backup server status"]

    next_request = client.post("/chat", data={"message": "wie geht es dem monitoring server", "csrf_token": client.headers["x-csrf-token"]})
    assert next_request.status_code == 200
    assert "Monitoring wurde normal neu verarbeitet." in next_request.text
    assert calls == ["backup server status", "wie geht es dem monitoring server"]


def test_chat_suggests_manual_alias_followup_for_non_admin_connection_reply(monkeypatch) -> None:
    async def fake_process(_self, message, *_args, **_kwargs):
        return PipelineResult(
            request_id="r-missing-target",
            text="Für `backup server` habe ich noch kein passendes SSH-Profil.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=10,
            detail_lines=[],
            pending_action={
                "query": str(message),
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "routing_decision": {"found": True, "kind": "ssh", "ref": ""},
                "action_decision": {
                    "found": True,
                    "candidate_kind": "template",
                    "candidate_id": "ssh_run_command",
                    "missing_input": "connection_ref",
                },
                "payload": {
                    "found": True,
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "connection_ref": "",
                    "requested_connection_ref": "backup server",
                    "content": "uptime",
                    "preview": "SSH command: uptime",
                    "missing_fields": ["connection_ref"],
                },
                "safety_decision": {"action": "ask_user"},
                "execution_decision": {"next_step": "ask_user"},
            },
        )

    async def fake_continue(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-continued",
            text="Kurzcheck für `ubnsrv-netalert`: Erreichbar.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=12,
            detail_lines=["Ausgeführt via SSH-Profil `ubnsrv-netalert`", "Befehl: uptime"],
        )

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "continue_pending_routed_action_input", fake_continue)
    monkeypatch.setattr(
        chat_pending_flows,
        "_looks_like_connection_ref_reply",
        lambda pending_action, message, settings: str(message).strip() == "ubnsrv-netalert",
    )

    client = _user_client(monkeypatch)
    preview = client.post("/chat", data={"message": "backup server status", "csrf_token": client.headers["x-csrf-token"]})
    assert preview.status_code == 200

    follow_up = client.post("/chat", data={"message": "ubnsrv-netalert", "csrf_token": client.headers["x-csrf-token"]})
    assert follow_up.status_code == 200
    assert "kann ein Admin später `backup server` als Alias für `ubnsrv-netalert` speichern" in follow_up.text


def test_chat_offers_alias_learning_after_missing_connection_ref_is_filled(monkeypatch) -> None:
    async def fake_process(_self, message, *_args, **_kwargs):
        if message == "backup server status":
            return PipelineResult(
                request_id="r-missing-target",
                text="Für `backup server` habe ich noch kein passendes SSH-Profil. Verfügbare SSH-Profile: ubnsrv-netalert. Antworte einfach mit dem passenden Profilnamen. Wenn es passt, kann ARIA sich die Zuordnung danach als Alias merken.",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                intents=["capability:ssh_command"],
                skill_errors=[],
                router_level=1,
                duration_ms=10,
                detail_lines=[],
                pending_action={
                    "query": "backup server status",
                    "candidate_kind": "template",
                    "candidate_id": "ssh_run_command",
                    "routing_decision": {"found": True, "kind": "ssh", "ref": ""},
                    "action_decision": {
                        "found": True,
                        "candidate_kind": "template",
                        "candidate_id": "ssh_run_command",
                        "missing_input": "connection_ref",
                    },
                    "payload": {
                        "found": True,
                        "capability": "ssh_command",
                        "connection_kind": "ssh",
                        "connection_ref": "",
                        "requested_connection_ref": "backup server",
                        "content": "uptime",
                        "preview": "SSH command: uptime",
                        "missing_fields": ["connection_ref"],
                    },
                    "safety_decision": {"action": "ask_user"},
                    "execution_decision": {"next_step": "ask_user"},
                },
            )
        raise AssertionError(f"Unexpected process call: {message}")

    async def fake_continue(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-continued",
            text="SSH ok.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=12,
            detail_lines=["Ausgeführt via SSH-Profil `ubnsrv-netalert`", "Befehl: uptime"],
        )

    updates: list[tuple[str, str, dict[str, object]]] = []

    def fake_update_connection_profile(_base_dir, kind, ref, payload):
        updates.append((str(kind), str(ref), dict(payload)))
        return {"success_message": "SSH-Profil aktualisiert"}

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "continue_pending_routed_action_input", fake_continue)
    monkeypatch.setattr(main_mod, "update_connection_profile", fake_update_connection_profile)
    monkeypatch.setattr(
        chat_pending_flows,
        "_looks_like_connection_ref_reply",
        lambda pending_action, message, settings: str(message).strip() == "ubnsrv-netalert",
    )

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "backup server status", "csrf_token": client.headers["x-csrf-token"]})
    assert preview.status_code == 200

    follow_up = client.post("/chat", data={"message": "ubnsrv-netalert", "csrf_token": client.headers["x-csrf-token"]})
    assert follow_up.status_code == 200
    assert "kann ich mir `backup server` als Alias für `ubnsrv-netalert` merken" in follow_up.text
    match = re.search(r"bestätige verbindung aktualisieren ([a-z0-9]{8})", follow_up.text, re.IGNORECASE)
    assert match

    confirm = client.post(
        "/chat",
        data={"message": f"bestätige verbindung aktualisieren {match.group(1)}", "csrf_token": client.headers["x-csrf-token"]},
    )
    assert confirm.status_code == 200
    assert "SSH-Profil aktualisiert" in confirm.text
    assert updates == [("ssh", "ubnsrv-netalert", {"aliases": ["backup server"]})]


def test_chat_can_confirm_pending_safe_fix(monkeypatch) -> None:
    async def fake_process(*_args, **_kwargs):
        return PipelineResult(
            request_id="r-safe-fix-preview",
            text="Ich habe einen sicheren Fix vorbereitet.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["capability:ssh_command"],
            skill_errors=[],
            router_level=1,
            duration_ms=8,
            detail_lines=[],
            safe_fix_plan=[{"connection_ref": "pihole1", "packages": ["curl"]}],
        )

    async def fake_execute_safe_fix_plan(*_args, **_kwargs):
        return SimpleNamespace(content="Safe-Fix ausgeführt.", success=True, error="")

    monkeypatch.setattr(main_mod.Pipeline, "process", fake_process)
    monkeypatch.setattr(main_mod.Pipeline, "execute_safe_fix_plan", fake_execute_safe_fix_plan)
    monkeypatch.setattr(main_mod, "send_discord_alerts", lambda *_args, **_kwargs: None)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "repariere apt", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    match = re.search(r"bestätige fix ([a-z0-9]{8})", preview.text, re.IGNORECASE)
    assert match

    confirm = client.post("/chat", data={"message": f"bestätige fix {match.group(1)}", "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "Safe-Fix ausgeführt." in confirm.text


def test_chat_can_confirm_memory_forget(monkeypatch) -> None:
    async def fake_memory_execute(self, query="", params=None):  # noqa: ANN001
        action = dict(params or {}).get("action")
        if action == "forget_preview":
            return SimpleNamespace(
                success=True,
                content="Ich habe passende Memories gefunden.",
                metadata={"forget_candidates": [{"collection": "facts", "id": "m1"}]},
                error=None,
            )
        return SimpleNamespace(
            success=True,
            content="Memory gelöscht.",
            metadata={},
            error=None,
        )

    monkeypatch.setattr(main_mod.Pipeline, "classify_routing", lambda *_args, **_kwargs: SimpleNamespace(intents=["memory_forget"]))
    monkeypatch.setattr(MemorySkill, "execute", fake_memory_execute)

    client = _admin_client(monkeypatch)
    preview = client.post("/chat", data={"message": "vergiss meine notiz über dns", "csrf_token": client.headers["x-csrf-token"]})

    assert preview.status_code == 200
    match = re.search(r"bestätige ([a-z0-9]{8})", preview.text, re.IGNORECASE)
    assert match

    confirm = client.post("/chat", data={"message": f"bestätige {match.group(1)}", "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "Memory gelöscht." in confirm.text
