from __future__ import annotations

import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

import aria.main as main_mod


def _scoped_cookie(base_name: str) -> str:
    return main_mod._cookie_name(base_name, public_url="http://testserver")


def _admin_client(monkeypatch, *, advanced_mode: bool = False) -> TestClient:
    monkeypatch.setattr(main_mod.FileChatHistoryStore, "append_exchange", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(main_mod, "can_access_advanced_config", lambda role, debug_mode: advanced_mode)  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), main_mod._encode_auth_session("neo", "admin"))
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
