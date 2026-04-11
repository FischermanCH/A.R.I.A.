from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.web.skills_routes import register_skills_routes


def _build_skills_app() -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("agent_text", lambda _request, fallback="ARIA": fallback)

    raw_config: dict = {}

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.can_access_advanced_config = True
        request.state.lang = "en"
        request.state.csrf_token = "test-csrf"
        request.state.release_meta = {"label": "test"}
        request.state.auth_role = "admin"
        return await call_next(request)

    settings = SimpleNamespace(
        ui=SimpleNamespace(title="Skills Test"),
        memory=SimpleNamespace(enabled=True),
        auto_memory=SimpleNamespace(enabled=False),
        connections=SimpleNamespace(
            ssh={},
            sftp={},
            smb={},
            rss={},
            discord={},
        ),
    )

    register_skills_routes(
        app,
        templates=templates,
        get_settings=lambda: settings,
        get_username_from_request=lambda request: "neo",
        get_auth_session_from_request=lambda request: {"username": "neo", "role": "admin"},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        read_raw_config=lambda: raw_config,
        write_raw_config=lambda data: raw_config.update(data),
        reload_runtime=lambda: None,
        translate=lambda _lang, _key, fallback="": fallback,
        localize_custom_skill_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_skill_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=lambda *args, **kwargs: [],
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    return TestClient(app)


def test_skills_page_sets_logical_back_url() -> None:
    client = _build_skills_app()

    response = client.get("/skills?return_to=%2Fconfig")

    assert response.status_code == 200
    assert "const logical='/config';" in response.text


def test_skills_save_preserves_return_to() -> None:
    client = _build_skills_app()

    response = client.post(
        "/skills/save",
        data={
            "memory_enabled": "1",
            "auto_memory_enabled": "0",
            "return_to": "/config",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/skills?saved=1&return_to=%2Fconfig"


def test_skills_wizard_page_sets_logical_back_url() -> None:
    client = _build_skills_app()

    response = client.get("/skills/wizard?return_to=%2Fskills")

    assert response.status_code == 200
    assert "const logical='/skills';" in response.text
