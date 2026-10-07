from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote_plus

import pytest
from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient
from fastapi.templating import Jinja2Templates

from aria.modules import module_route_path
import aria.modules.auth_ui.routes as auth_surface_routes
from aria.modules.auth_ui.routes import (
    AuthSurfaceRouteDeps,
    LOGIN_RATE_LIMIT_MAX_FAILURES,
    register_auth_surface_routes,
)


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "aria" / "templates"


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


def _build_login_client(*, read_raw_config=None, write_raw_config=None, set_response_cookie=None) -> tuple[TestClient, _Manager]:
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
            set_response_cookie=set_response_cookie or (lambda *_args, **_kwargs: None),
            clear_auth_related_cookies=lambda *_args, **_kwargs: None,
            cookie_should_be_secure=lambda *_args, **_kwargs: False,
            read_raw_config=read_raw_config or (lambda: {}),
            write_raw_config=write_raw_config or (lambda _raw: None),
            enable_bootstrap_admin_mode_in_raw_config=lambda raw: raw,
            reload_runtime=lambda: None,
            default_memory_collection_for_user=lambda username: f"memory_{username}",
            encode_auth_session=lambda username, role, **_kwargs: f"{username}:{role}",
            auth_cookie="auth",
            username_cookie="username",
            memory_collection_cookie="memory",
            session_cookie="session",
            auth_session_max_age_seconds=3600,
            logger=logging.getLogger("test-auth-surface"),
        ),
    )
    return TestClient(app), manager


def _build_auth_render_client(
    monkeypatch,
    *,
    background_asset_url: str = "",
) -> tuple[TestClient, list[tuple[str, str]]]:
    app = FastAPI()
    manager = _Manager()
    settings = SimpleNamespace(
        aria=SimpleNamespace(public_url=""),
        security=SimpleNamespace(bootstrap_locked=True),
        ui=SimpleNamespace(title="ARIA"),
    )
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    templates.env.globals["tr"] = lambda _request, _key, fallback="": fallback
    templates.env.globals["agent_name"] = lambda _request, title="": title or "ARIA"
    templates.env.globals["lang_flag"] = lambda code: code
    templates.env.globals["lang_label"] = lambda code: code
    templates.env.globals["module_route_path"] = lambda module_id, route_path: module_route_path(module_id, route_path) or ""
    calls: list[tuple[str, str]] = []
    real_template_name = auth_surface_routes.module_template_name

    def tracking_template_name(module_id: str, template_name: str) -> str | None:
        calls.append((module_id, template_name))
        return real_template_name(module_id, template_name)

    monkeypatch.setattr(auth_surface_routes, "module_template_name", tracking_template_name)

    @app.middleware("http")
    async def inject_state(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.lang = "de"
        request.state.supported_languages = ["de", "en"]
        request.state.release_meta = SimpleNamespace(label="test")
        request.state.update_status = SimpleNamespace(update_available=False)
        request.state.authenticated = False
        request.state.auth_user = ""
        request.state.auth_role = ""
        request.state.can_access_advanced_config = False
        request.state.ui_theme = "matrix"
        request.state.ui_background = "grid"
        request.state.ui_background_asset_url = background_asset_url
        request.state.logical_back_url = ""
        return await call_next(request)

    register_auth_surface_routes(
        app,
        AuthSurfaceRouteDeps(
            templates=templates,
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
            auth_session_max_age_seconds=3600,
            logger=logging.getLogger("test-auth-surface"),
        ),
    )
    return TestClient(app), calls


def test_login_page_uses_auth_ui_template_readpoint(monkeypatch) -> None:
    client, calls = _build_auth_render_client(monkeypatch)

    response = client.get("/login?next=/stats")

    assert response.status_code == 200
    assert ("auth_ui", "login.html") in calls
    assert 'action="/login"' in response.text
    assert 'href="/login"' in response.text
    assert 'name="next_path" value="/stats"' in response.text


def test_base_keeps_active_background_style_without_preloading_it(monkeypatch) -> None:
    client, _calls = _build_auth_render_client(
        monkeypatch,
        background_asset_url="/static/background-space-station.webp",
    )

    response = client.get("/login")

    assert response.status_code == 200
    assert '<link rel="preload" as="image"' not in response.text
    assert "--background-art: url('/static/background-space-station.webp')" in response.text


def test_base_does_not_preload_a_background_when_none_is_active(monkeypatch) -> None:
    client, _calls = _build_auth_render_client(monkeypatch)

    response = client.get("/login")

    assert response.status_code == 200
    assert '<link rel="preload" as="image"' not in response.text


def test_session_expired_page_uses_auth_ui_template_readpoint(monkeypatch) -> None:
    client, calls = _build_auth_render_client(monkeypatch)

    response = client.get("/session-expired?next=/stats")

    assert response.status_code == 200
    assert ("auth_ui", "session_expired.html") in calls
    assert 'href="/login?next=%2Fstats"' in response.text
    assert 'window.location.href = "/login?next=%2Fstats";' in response.text


def test_login_error_redirects_use_auth_ui_route_readpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    real_route_path = auth_surface_routes.module_route_path

    def tracking_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(auth_surface_routes, "module_route_path", tracking_route_path)
    client, _manager = _build_login_client()

    failed = client.post(
        "/login",
        data={"username": "neo", "password": "wrong", "next_path": "/"},
        follow_redirects=False,
    )
    logout = client.post("/logout", follow_redirects=False)

    assert failed.status_code == 303
    assert failed.headers["location"] == "/login?error=Login+fehlgeschlagen"
    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"
    assert calls.count(("auth_ui", "/login")) >= 2


def test_login_error_redirect_fails_closed_without_auth_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_surface_routes,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "auth_ui" and route_path == "/login"
        else module_route_path(module_id, route_path),
    )
    client, _manager = _build_login_client()

    with pytest.raises(RuntimeError, match="auth_ui route is not registered: /login"):
        client.post(
            "/login",
            data={"username": "neo", "password": "wrong", "next_path": "/"},
            follow_redirects=False,
        )


def test_set_username_redirect_uses_chat_surface_route_readpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    cookie_names: list[str] = []
    real_route_path = auth_surface_routes.module_route_path

    def tracking_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    def tracking_cookie(_response, _request, cookie_name: str, *_args, **_kwargs) -> None:
        cookie_names.append(cookie_name)

    monkeypatch.setattr(auth_surface_routes, "module_route_path", tracking_route_path)
    client, _manager = _build_login_client(set_response_cookie=tracking_cookie)

    response = client.post("/set-username", data={"username": " trinity "}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert ("chat_surface", "/") in calls
    assert cookie_names == ["username", "memory", "session"]


def test_set_username_redirect_fails_closed_without_chat_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_surface_routes,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "chat_surface" and route_path == "/"
        else module_route_path(module_id, route_path),
    )
    client, _manager = _build_login_client()

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        client.post("/set-username", data={"username": "trinity"}, follow_redirects=False)


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
