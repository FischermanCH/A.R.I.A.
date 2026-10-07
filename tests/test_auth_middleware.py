from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from aria.modules import module_public_path_prefix, module_route_path
import aria.modules.auth_ui.middleware as auth_middleware
from aria.modules.auth_ui.middleware import AuthMiddlewareDeps, _is_public_static_path, register_auth_middleware
from aria.modules.configuration_foundations.config import (
    discover_ui_background_files,
    normalize_ui_background,
    resolve_ui_background_asset_url,
)


def _build_auth_middleware_client(
    *,
    monkeypatch=None,
    role: str = "user",
    authenticated: bool = True,
    auth_reason: str = "",
    raw_auth_cookie: str = "",
    can_access_settings: bool = True,
    can_access_users: bool = True,
    can_access_advanced_config: bool = True,
    is_admin_only_path=None,
    is_advanced_config_path=None,
    background: str = "grid",
    background_normalizer=None,
    background_asset_resolver=None,
) -> TestClient:
    app = FastAPI()

    settings = SimpleNamespace(
        aria=SimpleNamespace(public_url="http://testserver"),
        ui=SimpleNamespace(language="de", title="ARIA", debug_mode=False, theme="matrix", background=background),
        security=SimpleNamespace(enabled=True),
    )
    if monkeypatch is not None:
        monkeypatch.setattr(auth_middleware, "module_route_path", auth_middleware.module_route_path)

    register_auth_middleware(
        app,
        AuthMiddlewareDeps(
            base_dir=Path("/tmp"),
            get_settings=lambda: settings,
            cookie_should_be_secure=lambda *_args, **_kwargs: False,
            cookie_scope_source=lambda *_args, **_kwargs: "test",
            cookie_names_for_request=lambda *_args, **_kwargs: {},
            request_cookie_value=lambda _request, cookie_name: raw_auth_cookie if cookie_name == "aria_auth_session" else "",
            translate=lambda _request, _key, default: default,
            read_release_meta=lambda _base_dir: {"label": "test"},
            get_update_status=lambda _current_label: {},
            get_auth_session_from_request_with_reason=lambda _request: (
                ({"username": "neo", "role": role}, auth_reason) if authenticated else (None, auth_reason)
            ),
            get_auth_manager=lambda: SimpleNamespace(
                store=SimpleNamespace(
                    get_user=lambda username: {"username": username, "role": role, "active": True},
                ),
            ),
            get_agent_name=lambda: "J.O.E.",
            sanitize_username=lambda value: str(value or "").strip(),
            sanitize_role=lambda value: str(value or "").strip(),
            sanitize_csrf_token=lambda value: str(value or "").strip(),
            new_csrf_token=lambda: "csrf-token",
            set_response_cookie=lambda *args, **kwargs: None,  # noqa: ARG005
            clear_auth_related_cookies=lambda *args, **kwargs: None,  # noqa: ARG005
            available_languages=lambda: ["de", "en"],
            resolve_lang=lambda code, default_lang: code or default_lang,
            normalize_ui_theme=lambda value: value,
            normalize_ui_background=background_normalizer or (lambda value: value),
            resolve_ui_background_asset_url=background_asset_resolver or (lambda _value: ""),
            can_access_settings=lambda _role: can_access_settings,
            can_access_users=lambda _role: can_access_users,
            can_access_advanced_config=lambda _role, _debug_mode: can_access_advanced_config,
            is_admin_only_path=is_admin_only_path or (lambda _path: False),
            is_advanced_config_path=is_advanced_config_path or (lambda _path: False),
            encode_auth_session=lambda username, role, scope: f"{username}:{role}:{scope}",
            auth_cookie="aria_auth_session",
            csrf_cookie="aria_csrf_token",
            username_cookie="aria_username",
            lang_cookie="aria_lang",
            auth_session_max_age_seconds=3600,
        ),
    )

    @app.get("/agent-name")
    def agent_name_probe(request: Request) -> JSONResponse:
        return JSONResponse({"agent_name": request.state.agent_name})

    @app.get("/appearance-probe")
    def appearance_probe(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "background": request.state.ui_background,
                "asset_url": request.state.ui_background_asset_url,
            }
        )

    @app.get("/config/admin/probe")
    def config_admin_probe() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/config/advanced/probe")
    def config_advanced_probe() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/config/probe")
    def config_probe() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/static/{asset_path:path}")
    def static_probe(asset_path: str) -> JSONResponse:
        return JSONResponse({"asset_path": asset_path})

    return TestClient(app)


def test_auth_middleware_prefers_persona_agent_name_over_ui_title() -> None:
    client = _build_auth_middleware_client()
    response = client.get("/agent-name")

    assert response.status_code == 200
    assert response.json()["agent_name"] == "J.O.E."


@pytest.mark.parametrize("background_row", discover_ui_background_files(), ids=lambda row: row["value"])
def test_auth_middleware_resolves_every_shipped_background(background_row: dict[str, str]) -> None:
    client = _build_auth_middleware_client(
        background=background_row["value"],
        background_normalizer=normalize_ui_background,
        background_asset_resolver=resolve_ui_background_asset_url,
    )

    response = client.get("/appearance-probe")

    assert response.status_code == 200
    assert response.json() == {
        "background": background_row["value"],
        "asset_url": background_row["asset_url"],
    }


def test_auth_public_static_path_uses_navigation_shell_prefix_readpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def tracking_public_prefix(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_public_path_prefix(module_id, route_path, **kwargs)

    monkeypatch.setattr(auth_middleware, "module_public_path_prefix", tracking_public_prefix)

    assert _is_public_static_path("/static/style.css") is True
    assert _is_public_static_path("/static/vendor/app.js") is True
    assert _is_public_static_path("/static") is False
    assert _is_public_static_path("/staticx/style.css") is False
    assert calls == [
        ("navigation_shell", "/static/style.css"),
        ("navigation_shell", "/static/vendor/app.js"),
    ]


def test_auth_public_static_path_fails_closed_without_navigation_shell_owner(monkeypatch) -> None:
    monkeypatch.setattr(auth_middleware, "module_public_path_prefix", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="navigation_shell public static prefix is not registered"):
        _is_public_static_path("/static/style.css")

    with pytest.raises(RuntimeError, match="navigation_shell public static prefix is not registered"):
        _is_public_static_path("/static/../config")


def test_auth_middleware_keeps_registered_static_get_public() -> None:
    client = _build_auth_middleware_client(authenticated=False)

    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert response.json() == {"asset_path": "style.css"}


def test_auth_middleware_config_guard_redirects_use_registry_route_readpoints(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(auth_middleware, "module_route_path", tracking_module_route_path)
    admin_client = _build_auth_middleware_client(
        can_access_users=False,
        is_admin_only_path=lambda path: path == "/config/admin/probe",
    )
    advanced_client = _build_auth_middleware_client(
        can_access_advanced_config=False,
        is_advanced_config_path=lambda path: path == "/config/advanced/probe",
    )

    admin = admin_client.get("/config/admin/probe", follow_redirects=False)
    advanced = advanced_client.get("/config/advanced/probe", follow_redirects=False)

    assert admin.status_code == 303
    assert admin.headers["location"] == "/config?error=no_admin"
    assert advanced.status_code == 303
    assert advanced.headers["location"] == "/config?error=admin_mode_required"
    assert calls.count(("config_ui", "/config")) >= 2


def test_auth_middleware_config_guard_redirect_fails_closed_without_config_owner(monkeypatch) -> None:
    monkeypatch.setattr(auth_middleware, "module_route_path", lambda *_args, **_kwargs: None)
    client = _build_auth_middleware_client(
        can_access_users=False,
        is_admin_only_path=lambda path: path == "/config/admin/probe",
    )

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.get("/config/admin/probe", follow_redirects=False)


def test_auth_middleware_home_guard_redirects_use_registry_route_readpoints(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(auth_middleware, "module_route_path", tracking_module_route_path)
    no_settings_client = _build_auth_middleware_client(role="user", can_access_settings=False)

    no_settings = no_settings_client.get("/config", follow_redirects=False)

    assert no_settings.status_code == 303
    assert no_settings.headers["location"] == "/?error=no_settings"
    assert calls.count(("chat_surface", "/")) >= 1


def test_auth_middleware_home_guard_redirect_fails_closed_without_chat_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_middleware,
        "module_route_path",
        lambda module_id, route_path, **_kwargs: None
        if module_id == "chat_surface" and route_path == "/"
        else module_route_path(module_id, route_path),
    )
    client = _build_auth_middleware_client(role="user", can_access_settings=False)

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        client.get("/config", follow_redirects=False)


def test_auth_middleware_login_redirects_use_registry_route_readpoints(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(auth_middleware, "module_route_path", tracking_module_route_path)
    login_required_client = _build_auth_middleware_client(authenticated=False)
    session_expired_client = _build_auth_middleware_client(
        authenticated=False,
        auth_reason="user_missing",
        raw_auth_cookie="stale",
    )

    login_required = login_required_client.get("/stats?tab=health", follow_redirects=False)
    session_expired = session_expired_client.get("/stats?tab=health", follow_redirects=False)
    json_required = login_required_client.get("/stats?tab=health", headers={"accept": "application/json"})

    assert login_required.status_code == 303
    assert login_required.headers["location"] == "/login?next=%2Fstats%3Ftab%3Dhealth"
    assert session_expired.status_code == 303
    assert session_expired.headers["location"] == "/session-expired?next=%2Fstats%3Ftab%3Dhealth"
    assert json_required.status_code == 401
    assert json_required.json()["login_url"] == "/login?next=%2Fstats%3Ftab%3Dhealth"
    assert ("auth_ui", "/login") in calls
    assert ("auth_ui", "/session-expired") in calls


def test_auth_middleware_login_redirect_fails_closed_without_auth_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_middleware,
        "module_route_path",
        lambda module_id, route_path, **_kwargs: None
        if module_id == "auth_ui" and route_path == "/login"
        else module_route_path(module_id, route_path),
    )
    client = _build_auth_middleware_client(authenticated=False)

    with pytest.raises(RuntimeError, match="auth_ui route is not registered: /login"):
        client.get("/stats", follow_redirects=False)
