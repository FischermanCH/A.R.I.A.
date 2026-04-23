import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.core import custom_skills
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

    async def _suggest_skill_keywords_with_llm(*args, **kwargs):
        return []

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
        suggest_skill_keywords_with_llm=_suggest_skill_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    return TestClient(app)


def test_skills_page_sets_logical_back_url() -> None:
    client = _build_skills_app()

    response = client.get("/skills?return_to=%2Fconfig")

    assert response.status_code == 200
    assert "const logical='/config';" in response.text
    assert 'aria-label="Fähigkeiten Navigation"' in response.text
    assert 'memory-health-grid' in response.text
    assert "Meine Skills" in response.text
    assert "Skill starten" in response.text
    assert "Core / System" in response.text
    assert "Vorlagen" in response.text
    assert "Nächste Schritte" not in response.text
    assert "Ersten Skill erstellen" not in response.text
    assert "Vorlage uebernehmen" not in response.text
    assert 'href="/skills/start"' in response.text
    assert 'href="/skills/mine"' in response.text
    assert 'href="/skills/system"' in response.text
    assert 'href="/skills/templates"' in response.text


def test_skills_subpages_render_with_page_specific_actions() -> None:
    client = _build_skills_app()

    start_response = client.get("/skills/start")
    assert start_response.status_code == 200
    assert 'memory-subnav-item active' in start_response.text
    assert 'href="/skills/wizard?return_to=/skills/start"' in start_response.text
    assert 'name="return_to" value="/skills/start"' in start_response.text

    mine_response = client.get("/skills/mine")
    assert mine_response.status_code == 200
    assert 'form id="skills-toggles-form"' in mine_response.text
    assert 'name="return_to" value="/skills/mine"' in mine_response.text
    assert 'id="skills-custom"' in mine_response.text

    system_response = client.get("/skills/system")
    assert system_response.status_code == 200
    assert 'name="return_to" value="/skills/system"' in system_response.text
    assert 'id="skills-system"' in system_response.text

    templates_response = client.get("/skills/templates")
    assert templates_response.status_code == 200
    assert 'name="return_to" value="/skills/templates"' in templates_response.text
    assert 'class="config-group-card skill-card sample-skill-card"' in templates_response.text
    assert 'sample-skill-card" data-sample-skill open' not in templates_response.text


def test_skills_save_preserves_return_to() -> None:
    client = _build_skills_app()

    response = client.post(
        "/skills/save",
        data={
            "memory_enabled": "1",
            "auto_memory_enabled": "0",
            "return_to": "/skills/system",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/skills/system?saved=1&return_to=%2Fskills%2Fsystem"


def test_skills_save_custom_toggle_preserves_core_toggles(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    prompts_dir = base_dir / "prompts" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")
    custom_skills._invalidate_custom_skill_manifest_cache()

    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "description": "Checks a Linux host.",
        "enabled_default": True,
        "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
    }
    (skills_dir / "linux-health.json").write_text(json.dumps(manifest), encoding="utf-8")

    raw = {
        "memory": {"enabled": True},
        "auto_memory": {"enabled": True},
        "skills": {"custom": {"linux-health": {"enabled": False}}},
    }
    target_raw = raw

    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("agent_text", lambda _request, fallback="ARIA": fallback)

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
        connections=SimpleNamespace(ssh={}, sftp={}, smb={}, rss={}, discord={}),
    )

    async def _suggest_skill_keywords_with_llm(*args, **kwargs):
        return []

    register_skills_routes(
        app,
        templates=templates,
        get_settings=lambda: settings,
        get_username_from_request=lambda request: "neo",
        get_auth_session_from_request=lambda request: {"username": "neo", "role": "admin"},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        read_raw_config=lambda: target_raw,
        write_raw_config=lambda data: target_raw.update(data),
        reload_runtime=lambda: None,
        translate=lambda _lang, _key, fallback="": fallback,
        localize_custom_skill_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_skill_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=_suggest_skill_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    client = TestClient(app)

    response = client.post(
        "/skills/save",
        data={
            "custom_enabled__linux-health": "1",
            "return_to": "/skills/mine",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert target_raw["memory"]["enabled"] is True
    assert target_raw["auto_memory"]["enabled"] is True
    assert target_raw["skills"]["custom"]["linux-health"]["enabled"] is True


def test_skills_save_core_toggle_preserves_custom_toggles(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    prompts_dir = base_dir / "prompts" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")
    custom_skills._invalidate_custom_skill_manifest_cache()

    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "description": "Checks a Linux host.",
        "enabled_default": True,
        "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
    }
    (skills_dir / "linux-health.json").write_text(json.dumps(manifest), encoding="utf-8")

    target_raw = {
        "memory": {"enabled": False},
        "auto_memory": {"enabled": False},
        "skills": {"custom": {"linux-health": {"enabled": True}}},
    }

    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("agent_text", lambda _request, fallback="ARIA": fallback)

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
        connections=SimpleNamespace(ssh={}, sftp={}, smb={}, rss={}, discord={}),
    )

    async def _suggest_skill_keywords_with_llm(*args, **kwargs):
        return []

    register_skills_routes(
        app,
        templates=templates,
        get_settings=lambda: settings,
        get_username_from_request=lambda request: "neo",
        get_auth_session_from_request=lambda request: {"username": "neo", "role": "admin"},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        read_raw_config=lambda: target_raw,
        write_raw_config=lambda data: target_raw.update(data),
        reload_runtime=lambda: None,
        translate=lambda _lang, _key, fallback="": fallback,
        localize_custom_skill_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_skill_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=_suggest_skill_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    client = TestClient(app)

    response = client.post(
        "/skills/save",
        data={
            "memory_enabled": "1",
            "auto_memory_enabled": "1",
            "return_to": "/skills/system",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert target_raw["memory"]["enabled"] is True
    assert target_raw["auto_memory"]["enabled"] is True
    assert target_raw["skills"]["custom"]["linux-health"]["enabled"] is True


def test_skills_wizard_page_sets_logical_back_url() -> None:
    client = _build_skills_app()

    response = client.get("/skills/wizard?return_to=%2Fskills")

    assert response.status_code == 200
    assert "const logical='/skills';" in response.text
    assert 'aria-label="Fähigkeiten Navigation"' in response.text
    assert "Neuen Skill erstellen" in response.text


def test_skills_wizard_defaults_to_simple_mode() -> None:
    client = _build_skills_app()

    response = client.get("/skills/wizard")

    assert response.status_code == 200
    assert 'data-wizard-mode="simple"' in response.text
    assert 'name="wizard_mode" id="wizard-mode-input" value="simple"' in response.text
    assert 'name="skill_type" id="skill-type-select"' in response.text
    assert '<option value="health_check" selected>Health Check</option>' in response.text
    assert 'const skillTypeAllowedSteps =' in response.text
    assert '"health_check": ["ssh_run", "llm_transform", "discord_send", "chat_send"]' in response.text
    assert 'const skillTypeFollowupSteps =' in response.text
    assert '"label": "An Discord senden"' in response.text
    assert 'Sinnvolle n' in response.text
    assert 'const skillTypeConnectionChoices =' in response.text
    assert '"health_check"' in response.text
    assert '"kind":"ssh"' in response.text or '"kind": "ssh"' in response.text
    assert 'Hauptverbindung wählen' in response.text
    assert 'class="skill-icon-button js-move-step-up"' in response.text
    assert 'aria-label="Move step up"' in response.text
    assert 'class="skill-action-button skill-add-step-button"' in response.text


def test_skills_wizard_save_preserves_selected_mode(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    prompts_dir = base_dir / "prompts" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")
    custom_skills._invalidate_custom_skill_manifest_cache()

    client = _build_skills_app()

    response = client.post(
        "/skills/wizard/save",
        data={
            "skill_name": "Health Check",
            "skill_description": "Checkt den Server",
            "skill_category": "monitoring",
            "skill_version": "0.1.0",
            "skill_router_keywords": "",
            "skill_connections": "",
            "skill_prompt_file": "",
            "skill_schema_version": "1.1",
            "auto_generate_keywords": "1",
            "schedule_enabled": "0",
            "schedule_time": "",
            "schedule_timezone": "Europe/Zurich",
            "schedule_run_on_startup": "0",
            "skill_ui_config_path": "",
            "skill_ui_hint": "",
            "enabled_default": "1",
            "wizard_mode": "advanced",
            "return_to": "/skills",
            "step_1_enabled": "1",
            "step_1_id": "s1",
            "step_1_name": "Check uptime",
            "step_1_type": "ssh_run",
            "step_1_on_error": "stop",
            "step_1_connection_ref": "pihole1",
            "step_1_command": "uptime",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "mode=advanced" in response.headers["location"]


def test_skills_wizard_health_check_defaults_apply_in_simple_mode(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    prompts_dir = base_dir / "prompts" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")
    custom_skills._invalidate_custom_skill_manifest_cache()

    client = _build_skills_app()

    response = client.post(
        "/skills/wizard/save",
        data={
            "skill_name": "Server Check",
            "skill_description": "",
            "skill_category": "custom",
            "skill_type": "health_check",
            "skill_version": "0.1.0",
            "skill_router_keywords": "",
            "skill_connections": "",
            "skill_prompt_file": "",
            "skill_schema_version": "1.1",
            "auto_generate_keywords": "0",
            "schedule_enabled": "0",
            "schedule_time": "",
            "schedule_timezone": "Europe/Zurich",
            "schedule_run_on_startup": "0",
            "skill_ui_config_path": "",
            "skill_ui_hint": "",
            "enabled_default": "1",
            "wizard_mode": "simple",
            "return_to": "/skills",
            "step_1_enabled": "1",
            "step_1_id": "s1",
            "step_1_name": "",
            "step_1_type": "ssh_run",
            "step_1_on_error": "stop",
            "step_1_connection_ref": "pihole1",
            "step_1_command": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    saved = json.loads((skills_dir / "server-check.json").read_text(encoding="utf-8"))
    assert saved["category"] == "monitoring"
    assert saved["description"] == "Prueft einen Host oder Dienst und liefert einen kurzen Status."
    assert saved["steps"][0]["type"] == "ssh_run"
    assert saved["steps"][0]["name"] == "Health Check"
    assert saved["steps"][0]["params"]["command"] == "uptime"
