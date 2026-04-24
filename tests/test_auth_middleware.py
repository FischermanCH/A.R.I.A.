from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from aria.web.auth_middleware import AuthMiddlewareDeps, register_auth_middleware


def test_auth_middleware_prefers_persona_agent_name_over_ui_title() -> None:
    app = FastAPI()

    settings = SimpleNamespace(
        aria=SimpleNamespace(public_url="http://testserver"),
        ui=SimpleNamespace(language="de", title="ARIA", debug_mode=False, theme="matrix", background="grid"),
        security=SimpleNamespace(enabled=False),
    )

    register_auth_middleware(
        app,
        AuthMiddlewareDeps(
            base_dir=Path("/tmp"),
            get_settings=lambda: settings,
            cookie_should_be_secure=lambda *_args, **_kwargs: False,
            cookie_scope_source=lambda *_args, **_kwargs: "test",
            cookie_names_for_request=lambda *_args, **_kwargs: {},
            request_cookie_value=lambda *_args, **_kwargs: "",
            translate=lambda _request, _key, default: default,
            read_release_meta=lambda _base_dir: {"label": "test"},
            get_update_status=lambda _current_label: {},
            get_auth_session_from_request_with_reason=lambda _request: (None, ""),
            get_auth_manager=lambda: None,
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
            normalize_ui_background=lambda value: value,
            resolve_ui_background_asset_url=lambda _value: "",
            can_access_settings=lambda _role: False,
            can_access_users=lambda _role: False,
            can_access_advanced_config=lambda _role, _debug_mode: False,
            is_admin_only_path=lambda _path: False,
            is_advanced_config_path=lambda _path: False,
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

    client = TestClient(app)
    response = client.get("/agent-name")

    assert response.status_code == 200
    assert response.json()["agent_name"] == "J.O.E."
