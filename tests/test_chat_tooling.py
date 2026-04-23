from __future__ import annotations

import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

import aria.main as main_mod
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
    match = re.search(r"(?:bestätige aktion|bestaetige aktion|confirm action) ([a-z0-9]{8})", preview.text, re.IGNORECASE)
    assert match

    command = (
        f"confirm action {match.group(1)}"
        if "confirm action" in preview.text.lower()
        else f"bestätige aktion {match.group(1)}"
    )
    confirm = client.post("/chat", data={"message": command, "csrf_token": client.headers["x-csrf-token"]})

    assert confirm.status_code == 200
    assert "Discord gesendet." in confirm.text


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

    follow_up = client.post("/chat", data={"message": "TESTNACHRICHT", "csrf_token": client.headers["x-csrf-token"]})

    assert follow_up.status_code == 200
    assert "vor der Ausfuehrung" in follow_up.text
    assert (
        "bestätige aktion" in follow_up.text.lower()
        or "bestaetige aktion" in follow_up.text.lower()
        or "confirm action" in follow_up.text.lower()
    )


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
