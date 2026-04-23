from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import aria.main as main_mod
import aria.web.stats_routes as stats_routes_mod
from aria.core.update_helper_client import resolve_update_helper_config


def _scoped_cookie(base_name: str) -> str:
    return main_mod._cookie_name(base_name, public_url="http://testserver")


def _scoped_auth(username: str, role: str) -> str:
    return main_mod._encode_auth_session(
        username,
        role,
        scope=main_mod._cookie_scope_source(public_url="http://testserver"),
    )


def test_login_page_shows_update_notice_when_newer_version_exists(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha26",
            "latest_label": "0.1.0-alpha27",
            "latest_tag": "v0.1.0-alpha.27",
            "update_available": True,
            "checked_at": "2026-04-05T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.27] - 2026-04-05",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )

    client = TestClient(main_mod.app)
    response = client.get("/login")

    assert response.status_code == 200
    assert "0.1.0-alpha27" in response.text
    assert "/updates" in response.text
    assert "hart neu laden" in response.text or "hard reload" in response.text


def test_updates_page_renders_release_notes(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha41",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha41",
            "latest_label": "0.1.0-alpha42",
            "latest_tag": "v0.1.0-alpha.42",
            "update_available": True,
            "checked_at": "2026-04-05T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.42] - 2026-04-05\n\n### Added\n- update hint",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [
                {
                    "label": "0.1.0-alpha41",
                    "tag": "v0.1.0-alpha.41",
                    "notes": "## [0.1.0-alpha.41] - 2026-04-05\n\n### Fixed\n- older fix",
                }
            ],
            "error": "",
        },
    )

    client = TestClient(main_mod.app)
    response = client.get("/updates")

    assert response.status_code == 200
    assert "0.1.0-alpha41" in response.text
    assert "0.1.0-alpha42" in response.text
    assert "CHANGELOG.md" in response.text
    assert "update hint" in response.text
    assert "0.1.0-alpha41" in response.text
    assert "older fix" in response.text
    assert "aria --version" in response.text
    assert "Sichere Update-Sequenz" in response.text or "Safe update sequence" in response.text
    assert "aria-pull" in response.text
    assert "memory-subnav-item" in response.text
    assert "/config/operations" in response.text


def test_updates_page_is_public_but_hides_managed_controls_for_anonymous(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha127",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha127",
            "latest_label": "0.1.0-alpha127",
            "latest_tag": "v0.1.0-alpha.127",
            "update_available": False,
            "checked_at": "2026-04-18T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.127] - 2026-04-19",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "fetch_update_helper_status", lambda _config: {"status": "idle", "running": False})  # noqa: ARG005

    client = TestClient(main_mod.app)
    response = client.get("/updates")

    assert response.status_code == 200
    assert "Updates" in response.text or "Update" in response.text
    assert "Einstellungen" in response.text or "Settings" in response.text
    assert "Kontrolliertes Update" not in response.text and "Controlled update" not in response.text
    assert "Update starten" not in response.text and "Start update" not in response.text


def test_updates_page_shows_managed_update_controls_for_admin(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha69",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha69",
            "latest_label": "0.1.0-alpha70",
            "latest_tag": "v0.1.0-alpha.70",
            "update_available": True,
            "checked_at": "2026-04-08T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.70] - 2026-04-08",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        main_mod,
        "fetch_update_helper_status",
        lambda _config: {
            "status": "idle",
            "running": False,
            "current_step": "",
            "last_started_at": "2026-04-08T10:10:00Z",
            "last_finished_at": "2026-04-08T10:11:00Z",
            "last_result": "Update completed successfully.",
            "last_error": "",
            "log_tail": ["[2026-04-08T10:10:00Z] ok"],
        },
    )

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    response = client.get("/updates")

    assert response.status_code == 200
    assert "Kontrolliertes Update" in response.text or "Controlled update" in response.text
    assert 'id="updates-primary"' in response.text
    assert "Update starten" in response.text or "Start update" in response.text
    assert "Update completed successfully." in response.text


def test_updates_page_shows_prominent_live_card_while_update_is_running(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha73",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha73",
            "latest_label": "0.1.0-alpha73",
            "latest_tag": "v0.1.0-alpha.73",
            "update_available": False,
            "checked_at": "2026-04-09T06:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.73] - 2026-04-09",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        main_mod,
        "fetch_update_helper_status",
        lambda _config: {
            "status": "running",
            "running": True,
            "current_step": "Run internal aria-pull/update-local flow",
            "last_started_at": "2026-04-09T06:31:58Z",
            "last_finished_at": "",
            "last_result": "",
            "last_error": "",
            "log_tail": ["[2026-04-09T06:31:58Z] running"],
        },
    )

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    response = client.get("/updates")

    assert response.status_code == 200
    assert "Update in progress" in response.text or "Update laeuft gerade" in response.text
    assert "update-live-card" in response.text
    assert "/updates/status" in response.text
    assert "Request sent to update helper" in response.text or "Anfrage an den Update-Helper gesendet" in response.text


def test_internal_local_helper_mode_is_treated_as_gui_update_capable() -> None:
    config = resolve_update_helper_config(
        env={
            "ARIA_UPDATE_MODE": "internal-local-helper",
            "ARIA_UPDATER_URL": "http://aria-updater:8094",
            "ARIA_UPDATER_TOKEN": "test-token",
        }
    )

    assert config.mode == "internal-local-helper"
    assert config.enabled is True


def test_updates_run_renders_running_wait_page_for_regular_form_posts(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "fetch_update_helper_status", lambda _config: {"status": "idle", "running": False})  # noqa: ARG005
    monkeypatch.setattr(main_mod, "trigger_update_helper_run", lambda _config: {"status": "accepted"})
    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha74",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha74",
            "latest_label": "0.1.0-alpha74",
            "latest_tag": "v0.1.0-alpha.74",
            "update_available": False,
            "checked_at": "2026-04-09T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.74] - 2026-04-09",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    client.get("/updates")
    csrf_token = client.cookies.get(_scoped_cookie(main_mod.CSRF_COOKIE), "")
    response = client.post("/updates/run", data={"csrf_token": csrf_token})

    assert response.status_code == 200
    assert "Update in progress" in response.text or "Update laeuft gerade" in response.text
    assert "/updates/status" in response.text
    assert "/health" in response.text


def test_updates_run_returns_json_for_ajax_requests(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "fetch_update_helper_status", lambda _config: {"status": "idle", "running": False})  # noqa: ARG005
    monkeypatch.setattr(main_mod, "trigger_update_helper_run", lambda _config: {"status": "accepted"})
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    client.get("/updates")
    csrf_token = client.cookies.get(_scoped_cookie(main_mod.CSRF_COOKIE), "")
    response = client.post(
        "/updates/run",
        data={"csrf_token": csrf_token},
        headers={"X-Requested-With": "ARIA-Update-UI", "Accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["status_url"] == "/updates/status"
    assert payload["reload_url"] == "/updates/relogin?next=%2Fupdates"


def test_updates_relogin_clears_current_instance_cookies() -> None:
    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("whity", "admin"))
    client.cookies.set(_scoped_cookie(main_mod.CSRF_COOKIE), "csrf-token")
    client.cookies.set(_scoped_cookie(main_mod.USERNAME_COOKIE), "whity")
    client.cookies.set(_scoped_cookie(main_mod.MEMORY_COLLECTION_COOKIE), "aria_facts_whity")
    client.cookies.set(_scoped_cookie(main_mod.SESSION_COOKIE), "session123")

    response = client.get("/updates/relogin?next=%2Fupdates", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fupdates"
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{_scoped_cookie(main_mod.AUTH_COOKIE)}=") for header in set_cookie_headers)
    assert any(header.startswith(f"{_scoped_cookie(main_mod.USERNAME_COOKIE)}=") for header in set_cookie_headers)
    assert any(header.startswith(f"{_scoped_cookie(main_mod.MEMORY_COLLECTION_COOKIE)}=") for header in set_cookie_headers)
    assert any(header.startswith(f"{_scoped_cookie(main_mod.SESSION_COOKIE)}=") for header in set_cookie_headers)


def test_updates_page_forces_relogin_when_helper_finished_after_session(monkeypatch) -> None:
    session_issued_at = int(time.time()) - 120
    helper_started_at = datetime.fromtimestamp(session_issued_at + 30, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    helper_finished_at = datetime.fromtimestamp(session_issued_at + 90, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha107",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha107",
            "latest_label": "0.1.0-alpha107",
            "latest_tag": "v0.1.0-alpha.107",
            "update_available": False,
            "checked_at": "2026-04-11T22:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.107] - 2026-04-11",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        main_mod,
        "fetch_update_helper_status",
        lambda _config: {
            "status": "ok",
            "running": False,
            "current_step": "",
            "last_started_at": helper_started_at,
            "last_finished_at": helper_finished_at,
            "last_result": "Update completed successfully.",
            "last_error": "",
            "log_tail": [],
        },
    )

    client = TestClient(main_mod.app)
    old_auth = main_mod._encode_auth_session(
        "whity",
        "admin",
        issued_at=session_issued_at,
        scope=main_mod._cookie_scope_source(public_url="http://testserver"),
    )
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), old_auth)
    response = client.get("/updates", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/updates/relogin?next=%2Fupdates"


def test_updates_run_rejects_non_admin(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "fetch_update_helper_status", lambda _config: {"status": "idle", "running": False})  # noqa: ARG005
    monkeypatch.setattr(main_mod, "trigger_update_helper_run", lambda _config: {"status": "accepted"})
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "user"))
    client.get("/updates")
    csrf_token = client.cookies.get(_scoped_cookie(main_mod.CSRF_COOKIE), "")
    response = client.post("/updates/run", data={"csrf_token": csrf_token}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/updates?error=no_admin"


def test_updates_run_rejects_anonymous_even_with_valid_csrf(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "fetch_update_helper_status", lambda _config: {"status": "idle", "running": False})  # noqa: ARG005
    monkeypatch.setattr(main_mod, "trigger_update_helper_run", lambda _config: {"status": "accepted"})

    client = TestClient(main_mod.app)
    client.get("/updates")
    csrf_token = client.cookies.get(_scoped_cookie(main_mod.CSRF_COOKIE), "")
    response = client.post("/updates/run", data={"csrf_token": csrf_token}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/updates?error=no_admin"


def test_updates_status_rejects_anonymous() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/updates/status")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin rights required."


def test_updates_status_returns_helper_payload_for_admin(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        main_mod,
        "fetch_update_helper_status",
        lambda _config: {
            "status": "running",
            "running": True,
            "current_step": "Recreating aria",
            "last_started_at": "2026-04-09T06:31:58Z",
            "last_finished_at": "",
            "last_result": "",
            "last_error": "",
            "log_tail": ["[2026-04-09T06:31:58Z] running"],
        },
    )

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    response = client.get("/updates/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["running"] is True
    assert payload["current_step"] == "Recreating aria"
    assert payload["visual_status"] == "warn"


def test_updates_running_page_renders_reconnect_shell(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        main_mod,
        "fetch_update_helper_status",
        lambda _config: {
            "status": "running",
            "visual_status": "warn",
            "running": True,
            "current_step": "Recreating aria",
            "last_started_at": "2026-04-09T06:31:58Z",
            "last_finished_at": "",
            "last_result": "",
            "last_error": "",
            "log_tail": ["[2026-04-09T06:31:58Z] running"],
        },
    )

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    response = client.get("/updates/running")

    assert response.status_code == 200
    assert "Update in progress" in response.text or "Update laeuft gerade" in response.text
    assert "/updates/status" in response.text
    assert "/health" in response.text


def test_stats_page_shows_update_card_and_uses_same_release_label(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_read_release_meta",
        lambda _base_dir: {
            "version": "0.1.0",
            "label": "0.1.0-alpha41",
        },
    )
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha41",
            "latest_label": "0.1.0-alpha42",
            "latest_tag": "v0.1.0-alpha.42",
            "update_available": True,
            "checked_at": "2026-04-05T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.42] - 2026-04-05",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    response = client.get("/stats")

    assert response.status_code == 200
    assert "0.1.0-alpha41" in response.text
    assert "0.1.0-alpha42" in response.text
    assert "/updates" in response.text
    assert "aria version-check" in response.text


def test_stats_page_includes_update_helper_health_row(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label, ttl_seconds=60 * 60 * 6: {
            "current_label": "0.1.0-alpha75",
            "latest_label": "0.1.0-alpha75",
            "latest_tag": "v0.1.0-alpha.75",
            "update_available": False,
            "checked_at": "2026-04-09T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.75] - 2026-04-09",
            "release_notes_source": "CHANGELOG.md",
            "recent_releases": [],
            "error": "",
        },
    )
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(stats_routes_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(
        stats_routes_mod,
        "fetch_update_helper_status",
        lambda _config, timeout=1.2: {  # noqa: ARG005
            "status": "idle",
            "visual_status": "ok",
            "running": False,
            "reachable": True,
            "current_step": "",
            "last_started_at": "",
            "last_finished_at": "",
            "last_result": "Update completed successfully.",
            "last_error": "",
            "log_tail": [],
        },
    )

    client = TestClient(main_mod.app)
    client.cookies.set(_scoped_cookie(main_mod.AUTH_COOKIE), _scoped_auth("neo", "admin"))
    response = client.get("/stats")

    assert response.status_code == 200
    assert "Update Helper" in response.text
    assert "GUI update helper reachable and ready." in response.text or "GUI-Update-Helper erreichbar und bereit." in response.text
