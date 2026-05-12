from __future__ import annotations

import logging
from types import SimpleNamespace
from urllib.parse import unquote_plus

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aria.web.auth_surface_routes import (
    AuthSurfaceRouteDeps,
    LOGIN_RATE_LIMIT_MAX_FAILURES,
    register_auth_surface_routes,
)


class _Store:
    def list_users(self) -> list[dict[str, object]]:
        return [{"username": "neo", "role": "admin", "active": True}]

    def get_user(self, username: str) -> dict[str, object]:
        return {"username": username, "role": "admin", "active": True}


class _Manager:
    def __init__(self) -> None:
        self.store = _Store()
        self.verify_calls = 0

    def verify(self, _username: str, password: str) -> bool:
        self.verify_calls += 1
        return password == "correct-password"

    def upsert_user(self, *_args, **_kwargs) -> None:
        raise AssertionError("bootstrap user creation should not run in these tests")


def _build_login_client() -> tuple[TestClient, _Manager]:
    app = FastAPI()
    manager = _Manager()
    settings = SimpleNamespace(
        aria=SimpleNamespace(public_url=""),
        security=SimpleNamespace(bootstrap_locked=True),
        ui=SimpleNamespace(title="ARIA"),
    )
    register_auth_surface_routes(
        app,
        AuthSurfaceRouteDeps(
            templates=SimpleNamespace(),
            get_settings=lambda: settings,
            get_auth_manager=lambda: manager,
            get_auth_session_from_request=lambda _request: None,
            sanitize_username=lambda value: str(value or "").strip(),
            sanitize_role=lambda value: str(value or "user").strip() or "user",
            set_response_cookie=lambda *_args, **_kwargs: None,
            clear_auth_related_cookies=lambda *_args, **_kwargs: None,
            cookie_should_be_secure=lambda *_args, **_kwargs: False,
            read_raw_config=lambda: {},
            write_raw_config=lambda _raw: None,
            enable_bootstrap_admin_mode_in_raw_config=lambda raw: raw,
            reload_runtime=lambda: None,
            default_memory_collection_for_user=lambda username: f"memory_{username}",
            encode_auth_session=lambda username, role, **_kwargs: f"{username}:{role}",
            auth_cookie="auth",
            username_cookie="username",
            memory_collection_cookie="memory",
            session_cookie="session",
            auto_memory_cookie="auto_memory",
            auth_session_max_age_seconds=3600,
            logger=logging.getLogger("test-auth-surface"),
        ),
    )
    return TestClient(app), manager


def test_login_rate_limit_blocks_repeated_failed_passwords() -> None:
    client, manager = _build_login_client()

    for _ in range(LOGIN_RATE_LIMIT_MAX_FAILURES):
        response = client.post(
            "/login",
            data={"username": "neo", "password": "wrong", "next_path": "/"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "Login+fehlgeschlagen" in response.headers["location"]

    response = client.post(
        "/login",
        data={"username": "neo", "password": "wrong", "next_path": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Zu viele Login-Versuche" in unquote_plus(response.headers["location"])
    assert manager.verify_calls == LOGIN_RATE_LIMIT_MAX_FAILURES


def test_successful_login_clears_rate_limit_attempts() -> None:
    client, manager = _build_login_client()

    for _ in range(LOGIN_RATE_LIMIT_MAX_FAILURES - 1):
        client.post(
            "/login",
            data={"username": "neo", "password": "wrong", "next_path": "/"},
            follow_redirects=False,
        )

    success = client.post(
        "/login",
        data={"username": "neo", "password": "correct-password", "next_path": "/"},
        follow_redirects=False,
    )
    assert success.status_code == 303
    assert success.headers["location"] == "/"

    for _ in range(LOGIN_RATE_LIMIT_MAX_FAILURES - 1):
        response = client.post(
            "/login",
            data={"username": "neo", "password": "wrong", "next_path": "/"},
            follow_redirects=False,
        )
        assert "Login+fehlgeschlagen" in response.headers["location"]

    assert manager.verify_calls == (LOGIN_RATE_LIMIT_MAX_FAILURES - 1) * 2 + 1
