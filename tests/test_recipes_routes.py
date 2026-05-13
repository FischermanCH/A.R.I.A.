import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.core import recipe_manifests
import aria.core.learned_recipe_store as learned_store
import aria.web.recipes_routes as recipes_routes_module
from aria.web.recipes_routes import register_recipe_routes


def _build_recipes_app(*, language: str = "de") -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("agent_text", lambda _request, fallback="ARIA": fallback)

    raw_config: dict = {}

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.can_access_advanced_config = True
        request.state.lang = language
        request.state.csrf_token = "test-csrf"
        request.state.release_meta = {"label": "test"}
        request.state.auth_role = "admin"
        return await call_next(request)

    settings = SimpleNamespace(
        ui=SimpleNamespace(title="Recipes Test"),
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

    async def _suggest_recipe_keywords_with_llm(*args, **kwargs):
        return []

    register_recipe_routes(
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
        localize_stored_recipe_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_recipe_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=_suggest_recipe_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    return TestClient(app)


def test_recipes_page_sets_logical_back_url() -> None:
    client = _build_recipes_app()

    response = client.get("/recipes?return_to=%2Fconfig")

    assert response.status_code == 200
    assert "const logical='/config';" in response.text
    assert 'aria-label="Rezepte Navigation"' in response.text
    assert 'memory-health-grid' in response.text
    assert 'memory-health-card memory-health-card-link" href="/recipes/mine"' in response.text
    assert 'memory-health-card memory-health-card-link" href="/recipes/learned"' in response.text
    assert 'memory-health-card memory-health-card-link" href="/recipes/system"' in response.text
    assert 'memory-health-card memory-health-card-link" href="/recipes/templates"' in response.text
    assert "<h3>Eigene</h3>" in response.text
    assert "<h3>Gelernt</h3>" in response.text
    assert "<h3>Importierbar</h3>" in response.text
    assert "Meine Rezepte" in response.text
    assert "Gelernte Rezepte" in response.text
    assert "Rezept starten" in response.text
    assert "Core / System" in response.text
    assert "Vorlagen / Playbooks" in response.text
    assert "Nächste Schritte" not in response.text
    assert "Erstes Rezept erstellen" not in response.text
    assert "Vorlage uebernehmen" not in response.text
    assert 'href="/recipes/start"' in response.text
    assert 'href="/recipes/mine"' in response.text
    assert 'href="/recipes/learned"' in response.text
    assert 'href="/recipes/system"' in response.text
    assert 'href="/recipes/templates"' in response.text


def test_recipes_subpages_render_with_page_specific_actions() -> None:
    client = _build_recipes_app()

    start_response = client.get("/recipes/start")
    assert start_response.status_code == 200
    assert 'memory-subnav-item active' in start_response.text
    assert 'href="/recipes/wizard?return_to=/recipes/start"' in start_response.text
    assert 'name="return_to" value="/recipes/start"' in start_response.text
    assert "Rezept / Skill" not in start_response.text
    assert "Neuen Skill" not in start_response.text

    mine_response = client.get("/recipes/mine")
    assert mine_response.status_code == 200
    assert 'form id="skills-toggles-form"' in mine_response.text
    assert 'name="return_to" value="/recipes/mine"' in mine_response.text
    assert 'id="skills-custom"' in mine_response.text
    assert "Meine Rezepte / Skills" not in mine_response.text

    learned_response = client.get("/recipes/learned")
    assert learned_response.status_code == 200
    assert 'id="skills-learned"' in learned_response.text
    assert "Woher gelernt?" in learned_response.text
    assert "data/runtime/learned_recipes.json" in learned_response.text
    assert "Wie abgerufen?" in learned_response.text
    assert "Policy und Guardrails bleiben immer davor" in learned_response.text

    system_response = client.get("/recipes/system")
    assert system_response.status_code == 200
    assert 'name="return_to" value="/recipes/system"' in system_response.text
    assert 'id="skills-system"' in system_response.text

    templates_response = client.get("/recipes/templates")
    assert templates_response.status_code == 200
    assert 'name="return_to" value="/recipes/templates"' in templates_response.text
    assert 'class="config-group-card skill-card sample-skill-card"' in templates_response.text
    assert 'sample-skill-card" data-sample-skill open' not in templates_response.text
    assert "Schritte:" in templates_response.text
    assert "Connections:" in templates_response.text
    assert "Trigger:" in templates_response.text
    assert "Step-Typen:" in templates_response.text
    assert "Read-only / Chat" in templates_response.text
    assert "Side-Effect / Bestaetigung" in templates_response.text
    assert "Beispielskill" not in templates_response.text
    assert "Demo-Skill" not in templates_response.text


def test_recipes_learned_page_renders_store_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "title": "Monitoring Quick Check",
                "summary": "Kurzcheck fuer uptime und Speicher.",
                "preview": "uptime && df -h /",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "connection_ref": "ubnsrv-netalert",
                "capability": "ssh_command",
                "chosen_action": "uptime && df -h /",
                "user_message": "wie geht es dem monitoring server",
                "experience_count": 5,
                "last_success_at": "2026-05-03T11:00:00Z",
                "promotion_state": "eligible",
                "promotion_hint": "Repeated successful runs make this learned recipe eligible for promotion.",
                "router_keywords": ["monitoring server", "health"],
                "recipe_scope": {"learning_origin": "guardrail_healthcheck_fallback"},
                "confidence": 0.84,
                "risk_level": "low",
                "generalization_hint": "Useful for read-only Linux host health checks.",
                "suggested_triggers": ["ist mein monitoring server ok"],
                "promotion_reason": "Repeated successful bounded checks.",
                "limits": ["Do not use for restarts."],
                "curation_source": "llm_curator",
                "curation_policy": "context_only_not_executable",
            }
        ],
    )
    client = _build_recipes_app()

    response = client.get("/recipes/learned")

    assert response.status_code == 200
    assert "Monitoring Quick Check" in response.text
    assert "Promotion fällig" in response.text
    assert "Runs: 5" in response.text
    assert "ubnsrv-netalert" in response.text
    assert "User sagte" in response.text
    assert "wie geht es dem monitoring server" in response.text
    assert "ssh/ubnsrv-netalert" in response.text
    assert "Hat funktioniert" in response.text
    assert "uptime &amp;&amp; df -h /" in response.text
    assert "Nur Kontext: nicht direkt ausführbar" in response.text
    assert "Reviewen und promoten, wenn weiterhin korrekt" in response.text
    assert "Action Contract" in response.text
    assert "Contract: command · Policy ssh_readonly · Runtime run_command · read-only/bounded" in response.text
    assert "LLM-kuratiert" in response.text
    assert "Confidence: 0.84" in response.text
    assert "Generalisiert als" in response.text
    assert "Useful for read-only Linux host health checks." in response.text
    assert "Vorgeschlagene Trigger" in response.text
    assert "Do not use for restarts." in response.text
    assert "Review-Reife" in response.text
    assert "Starke Evidenz: 5 Runs, Ziel und Aktion sind bekannt." in response.text


def test_recipes_learned_page_localizes_review_row_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "title": "Monitoring Quick Check",
                "summary": "Short check.",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "connection_ref": "ubnsrv-netalert",
                "capability": "ssh_command",
                "chosen_action": "uptime && df -h /",
                "experience_count": 5,
                "promotion_state": "eligible",
            }
        ],
    )
    client = _build_recipes_app(language="en")

    response = client.get("/recipes/learned")

    assert response.status_code == 200
    assert "Promotion due" in response.text
    assert "Review and promote if still correct" in response.text
    assert "Context only: not directly executable" in response.text
    assert "Review-Reife" in response.text
    assert "Strong evidence: 5 runs, target and action are known." in response.text


def test_recipes_learned_page_links_to_promoted_stored_recipe(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "title": "Monitoring Quick Check",
                "summary": "Kurzcheck fuer uptime und Speicher.",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "connection_ref": "ubnsrv-netalert",
                "capability": "ssh_command",
                "experience_count": 7,
                "promotion_state": "promoted",
                "stored_recipe_id": "ssh-health-check",
            }
        ],
    )
    client = _build_recipes_app()

    response = client.get("/recipes/learned?state=promoted&kind=ssh")

    assert response.status_code == 200
    assert "Gespeichertes Rezept" in response.text
    assert "/recipes/wizard?skill_id=ssh-health-check" in response.text
    assert "return_to=/recipes/learned%3Fstate%3Dpromoted%26kind%3Dssh" in response.text


def test_recipes_learned_page_filters_by_promotion_state(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "title": "Review Candidate",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "capability": "ssh_command",
                "experience_count": 3,
                "promotion_state": "review_ready",
            },
            {
                "title": "Promoted Candidate",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "capability": "ssh_command",
                "experience_count": 8,
                "promotion_state": "promoted",
            },
        ],
    )
    client = _build_recipes_app()

    response = client.get("/recipes/learned?state=promoted")

    assert response.status_code == 200
    assert "Promoted Candidate" in response.text
    assert "Review Candidate" not in response.text
    assert "Alle: 2" in response.text
    assert "Promoted: 1" in response.text


def test_recipes_learned_page_filters_by_connection_kind(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "title": "SSH Candidate",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "capability": "ssh_command",
                "experience_count": 3,
                "promotion_state": "review_ready",
            },
            {
                "title": "RSS Candidate",
                "intent": "read_feed",
                "connection_kind": "rss",
                "capability": "feed_read",
                "experience_count": 4,
                "promotion_state": "eligible",
            },
        ],
    )
    client = _build_recipes_app()

    response = client.get("/recipes/learned?kind=rss")

    assert response.status_code == 200
    assert "RSS Candidate" in response.text
    assert "SSH Candidate" not in response.text
    assert "Alle Typen: 2" in response.text
    assert "rss: 1" in response.text


def test_recipes_learned_page_sorts_by_experience(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "title": "Lower Experience",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "capability": "ssh_command",
                "experience_count": 2,
                "promotion_state": "observed",
            },
            {
                "title": "Higher Experience",
                "intent": "server_health_check",
                "connection_kind": "ssh",
                "capability": "ssh_command",
                "experience_count": 9,
                "promotion_state": "eligible",
            },
        ],
    )
    client = _build_recipes_app()

    response = client.get("/recipes/learned?sort=experience")

    assert response.status_code == 200
    assert response.text.index("Higher Experience") < response.text.index("Lower Experience")
    assert "Sortierung" in response.text


def test_recipes_learned_admin_actions_update_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", tmp_path)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", tmp_path / "data" / "recipes")
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", tmp_path / "data" / "recipes" / "_trigger_index.json")
    (tmp_path / "data" / "recipes").mkdir(parents=True, exist_ok=True)
    learned_store.invalidate_learned_recipe_store_cache()
    recipe_manifests._invalidate_stored_recipe_manifest_cache()
    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 5,
            "connection_ref": "srv-a",
            "title": "Linux Health",
            "summary": "Checks a Linux host.",
            "router_keywords": ["linux health", "server check"],
        }
    )

    client = _build_recipes_app()

    promote = client.post(
        "/recipes/learned/promote",
        data={
            "recipe_id": "learned-ssh-health-check",
            "csrf_token": "test-csrf",
            "return_to": "/recipes/learned",
        },
        follow_redirects=False,
    )
    assert promote.status_code == 303
    rows = learned_store.load_learned_recipe_store_entries()
    assert rows[0]["promotion_state"] == "promoted"
    stored_recipe = json.loads((tmp_path / "data" / "recipes" / "ssh-health-check.json").read_text(encoding="utf-8"))
    assert stored_recipe["name"] == "Linux Health"
    assert stored_recipe["connections"] == ["ssh"]
    assert stored_recipe["steps"][0]["type"] == "ssh_run"
    assert stored_recipe["steps"][0]["params"]["command"] == "uptime"

    dismiss = client.post(
        "/recipes/learned/dismiss",
        data={
            "recipe_id": "learned-ssh-health-check",
            "csrf_token": "test-csrf",
            "return_to": "/recipes/learned",
        },
        follow_redirects=False,
    )
    assert dismiss.status_code == 303
    rows = learned_store.load_learned_recipe_store_entries()
    assert rows[0]["promotion_state"] == "observed"
    assert str(rows[0]["promotion_hint"]).startswith("admin:")

    delete = client.post(
        "/recipes/learned/delete",
        data={
            "recipe_id": "learned-ssh-health-check",
            "csrf_token": "test-csrf",
            "return_to": "/recipes/learned",
        },
        follow_redirects=False,
    )
    assert delete.status_code == 303
    assert learned_store.load_learned_recipe_store_entries() == []


def test_recipes_learned_admin_action_preserves_filtered_return_to(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()
    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 5,
            "promotion_state": "eligible",
        }
    )
    client = _build_recipes_app()

    response = client.post(
        "/recipes/learned/dismiss",
        data={
            "recipe_id": "learned-ssh-health-check",
            "csrf_token": "test-csrf",
            "return_to": "/recipes/learned?state=eligible&kind=ssh&sort=experience",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/recipes/learned?state=eligible&kind=ssh&sort=experience&saved=1&info=")
    assert location.count("?") == 1
    assert "return_to=%2Frecipes%2Flearned%3Fstate%3Deligible%26kind%3Dssh%26sort%3Dexperience" in location


def test_recipes_save_preserves_return_to() -> None:
    client = _build_recipes_app()

    response = client.post(
        "/recipes/save",
        data={
            "memory_enabled": "1",
            "auto_memory_enabled": "0",
            "return_to": "/recipes/system",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/recipes/system?saved=1&return_to=%2Frecipes%2Fsystem"


def test_recipes_save_custom_toggle_preserves_core_toggles(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    prompts_dir = base_dir / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "description": "Checks a Linux host.",
        "enabled_default": True,
        "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
    }
    (recipes_dir / "linux-health.json").write_text(json.dumps(manifest), encoding="utf-8")

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
        ui=SimpleNamespace(title="Recipes Test"),
        memory=SimpleNamespace(enabled=True),
        auto_memory=SimpleNamespace(enabled=False),
        connections=SimpleNamespace(ssh={}, sftp={}, smb={}, rss={}, discord={}),
    )

    async def _suggest_recipe_keywords_with_llm(*args, **kwargs):
        return []

    register_recipe_routes(
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
        localize_stored_recipe_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_recipe_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=_suggest_recipe_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    client = TestClient(app)

    response = client.post(
        "/recipes/save",
        data={
            "custom_toggle_ids": "linux-health",
            "custom_enabled__linux-health": "1",
            "return_to": "/recipes/mine",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert target_raw["memory"]["enabled"] is True
    assert target_raw["auto_memory"]["enabled"] is True
    assert target_raw["skills"]["custom"]["linux-health"]["enabled"] is True


def test_recipes_save_custom_toggle_can_disable_recipe(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    prompts_dir = base_dir / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    monkeypatch.setattr(recipes_routes_module, "_load_stored_recipe_manifests", recipe_manifests._load_stored_recipe_manifests)
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "description": "Checkt einen Host.",
        "category": "infrastructure",
        "prompt_file": "prompts/recipes/linux-health.md",
        "router_keywords": ["health"],
        "connections": ["ssh"],
        "enabled_default": True,
        "steps": [
            {
                "id": "s1",
                "type": "ssh_run",
                "name": "Check",
                "params": {"command": "uptime"},
            }
        ],
        "schedule": {"enabled": False, "cron": "", "timezone": "Europe/Zurich", "run_on_startup": False},
        "schema_version": "1.1",
        "ui": {"config_path": "", "hint": ""},
    }
    recipe_manifests._save_stored_recipe_manifest(manifest)

    target_raw: dict[str, Any] = {
        "memory": {"enabled": True},
        "auto_memory": {"enabled": True},
        "skills": {"custom": {"linux-health": {"enabled": True}}},
    }
    async def _suggest_recipe_keywords_with_llm(*args, **kwargs):
        return []

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

    register_recipe_routes(
        app,
        templates=templates,
        get_settings=lambda: SimpleNamespace(
            memory=SimpleNamespace(enabled=True),
            auto_memory=SimpleNamespace(enabled=False),
            ssh_connections=[],
            sftp_connections=[],
            smb_connections=[],
            rss_connections=[],
            discord_webhooks=[],
            llm=[],
            calendar_connections=[],
        ),
        get_username_from_request=lambda _request: "alice",
        get_auth_session_from_request=lambda _request: {"role": "admin", "admin_mode": True},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        read_raw_config=lambda: target_raw,
        write_raw_config=lambda data: target_raw.update(data),
        reload_runtime=lambda: None,
        translate=lambda _lang, _key, fallback="": fallback,
        localize_stored_recipe_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_recipe_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=_suggest_recipe_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    client = TestClient(app)

    response = client.post(
        "/recipes/save",
        data={
            "custom_toggle_ids": "linux-health",
            "return_to": "/recipes/mine",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert target_raw["skills"]["custom"]["linux-health"]["enabled"] is False


def test_recipes_save_core_toggle_preserves_custom_toggles(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    prompts_dir = base_dir / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "description": "Checks a Linux host.",
        "enabled_default": True,
        "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
    }
    (recipes_dir / "linux-health.json").write_text(json.dumps(manifest), encoding="utf-8")

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
        ui=SimpleNamespace(title="Recipes Test"),
        memory=SimpleNamespace(enabled=True),
        auto_memory=SimpleNamespace(enabled=False),
        connections=SimpleNamespace(ssh={}, sftp={}, smb={}, rss={}, discord={}),
    )

    async def _suggest_recipe_keywords_with_llm(*args, **kwargs):
        return []

    register_recipe_routes(
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
        localize_stored_recipe_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_recipe_routing_info=lambda _lang, info: info,
        suggest_skill_keywords_with_llm=_suggest_recipe_keywords_with_llm,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    client = TestClient(app)

    response = client.post(
        "/recipes/save",
        data={
            "memory_enabled": "1",
            "auto_memory_enabled": "1",
            "return_to": "/recipes/system",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert target_raw["memory"]["enabled"] is True
    assert target_raw["auto_memory"]["enabled"] is True
    assert target_raw["skills"]["custom"]["linux-health"]["enabled"] is True


def test_recipes_wizard_page_sets_logical_back_url() -> None:
    client = _build_recipes_app()

    response = client.get("/recipes/wizard?return_to=%2Fskills")

    assert response.status_code == 200
    assert "const logical='/recipes';" in response.text
    assert 'aria-label="Rezepte Navigation"' in response.text
    assert "Create new recipe" in response.text


def test_recipes_wizard_defaults_to_simple_mode() -> None:
    client = _build_recipes_app()

    response = client.get("/recipes/wizard")

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


def test_recipes_wizard_save_preserves_selected_mode(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    prompts_dir = base_dir / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    client = _build_recipes_app()

    response = client.post(
        "/recipes/wizard/save",
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
            "return_to": "/recipes",
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


def test_recipes_wizard_health_check_defaults_apply_in_simple_mode(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    prompts_dir = base_dir / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    client = _build_recipes_app()

    response = client.post(
        "/recipes/wizard/save",
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
            "return_to": "/recipes",
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
    saved = json.loads((recipes_dir / "server-check.json").read_text(encoding="utf-8"))
    assert saved["category"] == "monitoring"
    assert saved["description"] == "Prueft einen Host oder Dienst und liefert einen kurzen Status."
    assert saved["steps"][0]["type"] == "ssh_run"
    assert saved["steps"][0]["name"] == "Health Check"
    assert saved["steps"][0]["params"]["command"] == "uptime"


def test_recipes_learned_context_only_rows_do_not_show_stored_promote(monkeypatch) -> None:
    monkeypatch.setattr(
        recipes_routes_module,
        "load_learned_recipe_store_entries",
        lambda: [
            {
                "recipe_id": "learned-web-search-pricing",
                "title": "Pricing source",
                "summary": "Useful pricing context.",
                "intent": "research_context",
                "connection_kind": "web",
                "connection_ref": "web_search",
                "capability": "web_search",
                "chosen_action": "aria pricing",
                "experience_count": 1,
                "promotion_state": "review_ready",
                "promotion_hint": "admin:Promoted from web/search result into review; context only and not directly executable.",
            }
        ],
    )
    client = _build_recipes_app()

    response = client.get("/recipes/learned")

    assert response.status_code == 200
    assert "Pricing source" in response.text
    assert "Nur Kontext" in response.text
    assert 'action="/recipes/learned/promote"' not in response.text
    assert 'action="/recipes/learned/dismiss"' in response.text
