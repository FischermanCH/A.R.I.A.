import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.modules import module_route_path, module_route_prefix_path
import aria.modules.recipe_store.manifests as recipe_manifests
import aria.modules.recipes_ui.routes as recipes_routes_module
import aria.modules.recipes_ui.route_support as recipes_route_support
import aria.modules.recipes_ui.surface_context as recipes_surface_context
from aria.modules.navigation_shell.navigation import admin_nav_groups, context_nav_context, context_nav_items, nav_section_items, settings_nav_groups
from aria.modules.recipes_ui.routes import register_recipe_routes


def _first_memory_subnav(html: str) -> str:
    start = html.find('<nav class="memory-subnav"')
    if start < 0:
        return ""
    end = html.find("</nav>", start)
    return html[start : end + len("</nav>")] if end >= 0 else html[start:]


def _build_recipes_app(
    *,
    language: str = "de",
    advanced_mode: bool = True,
    update_available: bool = False,
    module_route_path_resolver=None,
    auth_session=None,
) -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("agent_text", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("nav_section_items", nav_section_items)
    templates.env.globals.setdefault("context_nav_items", context_nav_items)
    templates.env.globals.setdefault("context_nav_context", context_nav_context)
    templates.env.globals.setdefault("admin_nav_groups", admin_nav_groups)
    templates.env.globals.setdefault("settings_nav_groups", settings_nav_groups)
    templates.env.globals.setdefault(
        "module_route_path",
        module_route_path_resolver or (lambda module_id, route_path: module_route_path(module_id, route_path) or ""),
    )

    raw_config: dict = {}

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.can_access_advanced_config = advanced_mode
        request.state.lang = language
        request.state.csrf_token = "test-csrf"
        request.state.release_meta = {"label": "test"}
        request.state.auth_role = "admin"
        request.state.authenticated = True
        request.state.auth_user = "neo"
        request.state.update_status = SimpleNamespace(update_available=update_available)
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
        get_auth_session_from_request=auth_session or (lambda request: {"username": "neo", "role": "admin"}),
        sanitize_role=lambda value: str(value or "").strip().lower(),
        read_raw_config=lambda: raw_config,
        write_raw_config=lambda data: raw_config.update(data),
        reload_runtime=lambda: None,
        translate=lambda _lang, _key, fallback="": fallback,
        localize_stored_recipe_description=lambda manifest, _lang: str(manifest.get("description", "")),
        format_recipe_routing_info=lambda _lang, info: info,
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    return TestClient(app)


def _seed_duplicate_recipe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Path]:
    recipes_dir = tmp_path / "data" / "recipes"
    recipes_dir.mkdir(parents=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", tmp_path)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "LEGACY_SKILLS_STORE_DIR", tmp_path / "data" / "skills")
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    monkeypatch.setattr(recipes_routes_module, "_load_stored_recipe_manifests", recipe_manifests._load_stored_recipe_manifests)
    monkeypatch.setattr(recipes_routes_module, "_save_stored_recipe_manifest", recipe_manifests._save_stored_recipe_manifest)
    recipe_manifests._invalidate_stored_recipe_manifest_cache()
    recipe_manifests._save_stored_recipe_manifest(
        {
            "id": "daily-check",
            "name": "Daily Check",
            "description": "Checks one target.",
            "enabled_default": True,
            "steps": [{"id": "s1", "type": "ssh_run", "params": {"connection_ref": "srv-1", "command": "uptime"}}],
        }
    )
    return _build_recipes_app(language="de"), recipes_dir


def test_duplicate_creates_inactive_copy_with_same_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, recipes_dir = _seed_duplicate_recipe(monkeypatch, tmp_path)

    response = client.post(
        "/recipes/duplicate",
        data={"recipe_id": "daily-check", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/recipes/mine?" in response.headers["location"]
    copied = json.loads((recipes_dir / "daily-check-copy.json").read_text(encoding="utf-8"))
    original = json.loads((recipes_dir / "daily-check.json").read_text(encoding="utf-8"))
    assert copied["id"] == "daily-check-copy"
    assert copied["name"] == "Daily Check (Kopie)"
    assert copied["enabled_default"] is False
    assert copied["steps"] == original["steps"]


def test_duplicate_allocates_unique_id_after_collision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, recipes_dir = _seed_duplicate_recipe(monkeypatch, tmp_path)

    for _ in range(2):
        response = client.post(
            "/recipes/duplicate",
            data={"recipe_id": "daily-check", "csrf_token": "test-csrf"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    assert (recipes_dir / "daily-check-copy.json").exists()
    second = json.loads((recipes_dir / "daily-check-copy-2.json").read_text(encoding="utf-8"))
    assert second["id"] == "daily-check-copy-2"
    assert second["enabled_default"] is False


def test_recipe_duplicate_button_is_rendered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, _recipes_dir = _seed_duplicate_recipe(monkeypatch, tmp_path)

    response = client.get("/recipes/mine")

    assert response.status_code == 200
    assert 'formaction="/recipes/duplicate"' in response.text
    assert 'name="recipe_id"' in response.text
    assert 'value="daily-check"' in response.text
    assert 'aria-label="Duplizieren"' in response.text


def test_recipes_return_to_invalid_fallback_uses_chat_surface_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    real_route_path = recipes_route_support.module_route_path

    def tracking_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(recipes_route_support, "module_route_path", tracking_route_path)
    request = SimpleNamespace(url=SimpleNamespace(path="/recipes"), query_params={}, headers={})

    assert recipes_route_support.resolve_return_to(request, fallback="") == "/"
    assert ("chat_surface", "/") in calls


def test_recipes_return_to_invalid_fallback_fails_closed_without_chat_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recipes_route_support,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "chat_surface" and route_path == "/"
        else module_route_path(module_id, route_path),
    )
    request = SimpleNamespace(url=SimpleNamespace(path="/recipes"), query_params={}, headers={})

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        recipes_route_support.resolve_return_to(request, fallback="")


def test_recipes_legacy_skills_return_to_uses_recipes_ui_readpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    route_calls: list[tuple[str, str]] = []
    prefix_calls: list[tuple[str, str]] = []

    def tracking_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    def tracking_route_prefix_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        prefix_calls.append((module_id, route_path))
        return module_route_prefix_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_route_support, "module_route_path", tracking_route_path)
    monkeypatch.setattr(recipes_route_support, "module_route_prefix_path", tracking_route_prefix_path)

    assert recipes_route_support.canonical_recipe_surface_return_to("/skills?tab=mine") == "/recipes?tab=mine"
    assert recipes_route_support.canonical_recipe_surface_return_to("/skills/mine?tab=own") == "/recipes/mine?tab=own"
    assert ("recipes_ui", "/recipes") in route_calls
    assert ("recipes_ui", "/recipes/mine") in prefix_calls


def test_recipes_legacy_skills_return_to_fails_closed_without_recipes_ui_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recipes_route_support,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "recipes_ui" and route_path == "/recipes"
        else module_route_path(module_id, route_path),
    )

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        recipes_route_support.canonical_recipe_surface_return_to("/skills")


def test_recipes_legacy_skills_return_to_fails_closed_without_recipes_ui_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recipes_route_support,
        "module_route_prefix_path",
        lambda module_id, route_path: None
        if module_id == "recipes_ui" and route_path == "/recipes/mine"
        else module_route_prefix_path(module_id, route_path),
    )

    with pytest.raises(RuntimeError, match="recipes_ui route prefix is not registered: /recipes/mine"):
        recipes_route_support.canonical_recipe_surface_return_to("/skills/mine")


def test_recipes_page_sets_logical_back_url() -> None:
    client = _build_recipes_app()

    response = client.get("/recipes?return_to=%2Fconfig")

    assert response.status_code == 200
    assert "const logical='/config';" in response.text
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
    assert "<h2>Rezepte</h2>" in response.text or "<h2>Recipes</h2>" in response.text
    assert "<h2>Meine Rezepte</h2>" not in response.text
    assert "<h2>My recipes</h2>" not in response.text
    assert 'form id="skills-toggles-form"' not in response.text
    assert 'id="skills-custom"' not in response.text
    assert "Einstellungen" in response.text or "Settings" in response.text
    assert "Meine Rezepte" in response.text or "My recipes" in response.text
    assert "Neu / Vorlagen" in response.text or "New / templates" in response.text
    assert "Zurück zu Einstellungen" not in response.text
    assert "Back to settings" not in response.text
    assert 'href="/config"' in response.text
    assert "Core / System" not in response.text
    assert "Vorlagen / Playbooks" not in response.text
    assert "Nächste Schritte" not in response.text
    assert "Erstes Rezept erstellen" not in response.text
    assert "Vorlage uebernehmen" not in response.text
    assert 'href="/recipes/start"' in response.text
    assert 'href="/recipes/mine"' in response.text
    assert 'href="/recipes"' in response.text
    assert 'href="/config"' in response.text
    assert 'memory-subnav-item' in response.text
    assert 'href="/recipes/system"' not in response.text
    assert 'href="/recipes/templates"' not in response.text


def test_global_menu_groups_admin_links_by_admin_mode() -> None:
    module_route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str) -> str:
        module_route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path) or ""

    admin_client = _build_recipes_app(
        advanced_mode=True,
        update_available=True,
        module_route_path_resolver=tracking_module_route_path,
    )
    user_client = _build_recipes_app(
        advanced_mode=False,
        update_available=True,
        module_route_path_resolver=tracking_module_route_path,
    )

    admin_response = admin_client.get("/recipes")
    user_response = user_client.get("/recipes")

    assert admin_response.status_code == 200
    assert user_response.status_code == 200
    assert 'href="/memories"' in admin_response.text
    assert 'href="/notes"' in admin_response.text
    assert 'href="/recipes" class="user-menu-link user-menu-link-icon' not in admin_response.text
    assert 'href="/config"' in admin_response.text
    assert 'href="/config"' in admin_response.text
    assert 'href="/stats"' in admin_response.text
    assert 'href="/help"' in admin_response.text
    assert 'href="/config/admin-mode"' in admin_response.text
    assert "Erweiterte Ansicht" in admin_response.text or "Extended view" in admin_response.text
    assert 'href="/config/users?return_to=/config/access#admin-mode"' not in admin_response.text
    assert 'class="user-menu-admin-details user-menu-settings-details"' not in admin_response.text
    assert 'class="user-menu-admin-links user-menu-settings-links"' not in admin_response.text
    assert 'href="/config/admin"' not in admin_response.text
    assert "Admin-Übersicht" not in admin_response.text
    assert "Admin overview" not in admin_response.text
    assert 'user-menu-section-label">Admin<' not in admin_response.text
    assert 'href="/config/intelligence"' not in admin_response.text
    assert 'href="/config/operations"' not in admin_response.text
    assert 'href="/config/workbench"' not in admin_response.text
    assert 'href="/memories/import"' not in admin_response.text
    assert 'href="/memories/maintenance"' not in admin_response.text
    assert 'href="/connections"' in admin_response.text
    assert 'href="/activities"' not in admin_response.text
    assert 'href="/updates"' in admin_response.text
    assert 'menu-update-chip' in admin_response.text
    assert 'class="admin-nav-group"' not in admin_response.text

    assert 'href="/memories"' in user_response.text
    assert 'href="/notes"' in user_response.text
    assert 'href="/recipes" class="user-menu-link user-menu-link-icon' not in user_response.text
    assert 'href="/config"' in user_response.text
    assert 'href="/stats"' in user_response.text
    assert 'href="/help"' in user_response.text
    assert 'href="/config/admin-mode"' in user_response.text
    assert "Erweiterte Ansicht" in user_response.text or "Extended view" in user_response.text
    assert 'href="/config/users?return_to=/config/access#admin-mode"' not in user_response.text
    assert 'class="user-menu-admin-details user-menu-settings-details"' not in user_response.text
    assert 'href="/config/admin"' not in user_response.text
    assert 'href="/updates"' in user_response.text
    assert 'menu-update-chip' in user_response.text
    assert 'class="user-menu-admin-details user-menu-settings-details"' not in user_response.text
    assert 'href="/config/intelligence"' not in user_response.text
    assert 'href="/config/access"' not in user_response.text
    assert 'href="/config/operations"' not in user_response.text
    assert 'href="/config/workbench"' not in user_response.text
    assert 'href="/recipes/system"' not in user_response.text
    assert 'href="/memories/import"' not in user_response.text
    assert 'href="/memories/maintenance"' not in user_response.text
    assert 'href="/connections"' in user_response.text
    assert ("notes", "/notes") in module_route_calls
    assert 'href="/activities"' not in user_response.text


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

    system_response = client.get("/recipes/system")
    assert system_response.status_code == 200
    system_nav = _first_memory_subnav(system_response.text)
    assert 'class="memory-subnav-item active" href="/config"' in system_nav
    assert 'href="/recipes/system"' not in system_nav
    assert 'href="/recipes/start"' not in system_response.text
    assert 'name="return_to" value="/recipes/system"' in system_response.text
    assert 'id="skills-system"' in system_response.text

    templates_response = client.get("/recipes/templates")
    assert templates_response.status_code == 200
    assert 'name="return_to" value="/recipes/start"' in templates_response.text
    assert 'class="config-group-card skill-card sample-skill-card"' in templates_response.text
    assert 'sample-skill-card" data-sample-skill open' not in templates_response.text
    assert "Schritte:" in templates_response.text
    assert "Verbindungen:" in templates_response.text or "Connections:" in templates_response.text
    assert "Trigger:" not in templates_response.text
    assert "Step-Typen:" in templates_response.text
    assert "Read-only / Chat" in templates_response.text
    assert "Side-Effect / Bestaetigung" not in templates_response.text
    assert "Beispielskill" not in templates_response.text
    assert "Demo-Skill" not in templates_response.text


def test_recipes_ui_surfaces_use_registry_template_readpoints(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []
    real_template_name = recipes_routes_module.module_template_name

    def tracking_template_name(module_id: str, template_name: str):
        seen.append((module_id, template_name))
        return real_template_name(module_id, template_name)

    monkeypatch.setattr(recipes_routes_module, "module_template_name", tracking_template_name)
    client = _build_recipes_app()

    for path in ("/recipes", "/recipes/start", "/recipes/mine", "/recipes/system"):
        response = client.get(path)
        assert response.status_code == 200

    assert ("recipes_ui", "recipes_overview.html") in seen
    assert ("recipes_ui", "recipes_start.html") in seen
    assert ("recipes_ui", "recipes_mine.html") in seen
    assert ("recipes_ui", "recipes_system.html") in seen


def test_recipes_ui_template_readpoint_fails_closed_for_unregistered_template(monkeypatch) -> None:
    monkeypatch.setattr(recipes_routes_module, "module_template_name", lambda *_args, **_kwargs: None)

    try:
        recipes_routes_module._recipes_ui_template_name("recipes_overview.html")
    except RuntimeError as exc:
        assert "recipes_ui template is not registered: recipes_overview.html" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("recipes_ui template helper must fail closed when the registry has no owner")


def test_recipes_ui_visible_urls_use_registry_route_readpoints(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str) -> str:
        seen.append((module_id, route_path))
        return module_route_path(module_id, route_path) or ""

    monkeypatch.setattr(recipes_routes_module, "module_route_path", tracking_module_route_path)
    monkeypatch.setattr(recipes_surface_context, "module_route_path", tracking_module_route_path)
    client = _build_recipes_app(module_route_path_resolver=tracking_module_route_path)

    overview_response = client.get("/recipes")
    start_response = client.get("/recipes/start")
    mine_response = client.get("/recipes/mine")
    system_response = client.get("/recipes/system")
    templates_response = client.get("/recipes/templates")
    wizard_response = client.get("/recipes/wizard?return_to=/recipes")

    assert overview_response.status_code == 200
    assert start_response.status_code == 200
    assert mine_response.status_code == 200
    assert system_response.status_code == 200
    assert templates_response.status_code == 200
    assert wizard_response.status_code == 200
    assert 'href="/recipes/wizard?return_to=/recipes/start"' in start_response.text
    assert 'action="/recipes/import"' in start_response.text
    assert 'action="/recipes/save"' in mine_response.text
    assert 'href="/recipes/start"' in mine_response.text
    assert 'href="/recipes/system"' in system_response.text
    assert 'href="/connections"' in wizard_response.text
    assert ("recipes_ui", "/recipes/wizard") in seen
    assert ("recipes_ui", "/recipes/import") in seen
    assert ("recipes_ui", "/recipes/save") in seen
    assert ("memory_admin_ui", "/memories") in seen
    assert ("recipes_ui", "/recipes/start") in seen
    assert ("recipes_ui", "/recipes/mine") in seen
    assert ("recipes_ui", "/recipes/system") in seen
    assert ("recipes_ui", "/recipes/templates") in seen
    assert seen.count(("recipes_ui", "/recipes")) >= 6
    assert ("chat_surface", "/") in seen
    assert ("config_ui", "/config") in seen
    assert ("connections_ui_readonly", "/connections") in seen


def test_recipes_surface_route_readpoints_fail_closed_without_owner(monkeypatch) -> None:
    def missing_recipes_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "recipes_ui":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_routes_module, "module_route_path", missing_recipes_route)
    client = _build_recipes_app()

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        client.get("/recipes")


def test_recipes_home_route_readpoint_fails_closed_without_owner(monkeypatch) -> None:
    monkeypatch.setattr(recipes_routes_module, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        recipes_routes_module._chat_surface_route_path("/")


def test_recipes_surface_context_path_fails_closed_without_route_owner(monkeypatch) -> None:
    monkeypatch.setattr(recipes_surface_context, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes/mine"):
        recipes_surface_context.build_recipes_overview_checks(
            lang="de",
            core_recipe_rows=[],
            custom_rows=[],
            sample_recipe_rows=[],
            advanced_mode=False,
            translate=lambda _lang, _key, fallback="": fallback,
        )


@pytest.mark.parametrize(
    ("method", "path"),
    (
        ("get", "/recipes/learned"),
        ("get", "/recipes/learned/maintenance"),
        ("get", "/recipes/learned/promote-preview?recipe_id=learned-example"),
        ("post", "/recipes/learned/promote"),
        ("post", "/recipes/learned/dismiss"),
        ("post", "/recipes/learned/delete"),
    ),
)
def test_learned_recipe_ui_routes_are_removed(method: str, path: str) -> None:
    client = _build_recipes_app()

    response = client.request(method, path, data={"recipe_id": "learned-example"})

    assert response.status_code == 404


def test_normal_recipe_surfaces_remain_without_learned_navigation() -> None:
    client = _build_recipes_app()

    overview = client.get("/recipes")
    mine = client.get("/recipes/mine")

    assert overview.status_code == 200
    assert mine.status_code == 200
    assert "/recipes/learned" not in overview.text
    assert "/recipes/learned" not in mine.text
    assert 'href="/recipes/mine"' in overview.text
    assert 'action="/recipes/duplicate"' in mine.text


def test_recipes_save_preserves_return_to() -> None:
    client = _build_recipes_app()

    response = client.post(
        "/recipes/save",
        data={
            "memory_enabled": "1",
            "return_to": "/recipes/system",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/recipes/system?saved=1&return_to=%2Frecipes%2Fsystem"


def test_recipes_post_redirect_fallbacks_use_registry_route_readpoints(monkeypatch) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_routes_module, "module_route_path", tracking_module_route_path)
    readonly_client = _build_recipes_app(
        advanced_mode=False,
        auth_session=lambda _request: {"username": "neo", "role": "user"},
    )
    admin_client = _build_recipes_app()

    save_readonly = readonly_client.post("/recipes/save", data={"return_to": ""}, follow_redirects=False)
    wizard_readonly = readonly_client.post(
        "/recipes/wizard/save",
        data={"skill_id": "demo", "skill_name": "Demo", "return_to": ""},
        follow_redirects=False,
    )
    import_sample_csrf = admin_client.post(
        "/recipes/import-sample",
        data={"sample_file": "missing.json", "csrf_token": "wrong", "return_to": ""},
        follow_redirects=False,
    )
    delete_csrf = admin_client.post(
        "/recipes/delete",
        data={"skill_id": "demo", "csrf_token": "wrong", "return_to": ""},
        follow_redirects=False,
    )

    assert save_readonly.status_code == 303
    assert save_readonly.headers["location"].startswith("/recipes?error=readonly")
    assert wizard_readonly.status_code == 303
    assert wizard_readonly.headers["location"].startswith("/recipes?error=readonly")
    assert import_sample_csrf.status_code == 303
    assert import_sample_csrf.headers["location"].startswith("/recipes?error=csrf_failed")
    assert delete_csrf.status_code == 303
    assert delete_csrf.headers["location"].startswith("/recipes?error=csrf_failed")
    assert ("recipes_ui", "/recipes") in route_calls
    assert ("chat_surface", "/") in route_calls


def test_recipes_post_redirect_fallbacks_fail_closed_without_recipes_owner(monkeypatch) -> None:
    def missing_recipes_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "recipes_ui" and route_path == "/recipes":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_routes_module, "module_route_path", missing_recipes_route)
    readonly_client = _build_recipes_app(
        advanced_mode=False,
        auth_session=lambda _request: {"username": "neo", "role": "user"},
    )

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        readonly_client.post("/recipes/save", data={"return_to": ""}, follow_redirects=False)


def test_recipes_post_redirect_fallbacks_fail_closed_without_home_owner(monkeypatch) -> None:
    def missing_home_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "chat_surface" and route_path == "/":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_routes_module, "module_route_path", missing_home_route)
    readonly_client = _build_recipes_app(
        advanced_mode=False,
        auth_session=lambda _request: {"username": "neo", "role": "user"},
    )

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        readonly_client.post("/recipes/save", data={"return_to": ""}, follow_redirects=False)


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
    templates.env.globals.setdefault("nav_section_items", nav_section_items)
    templates.env.globals.setdefault("context_nav_items", context_nav_items)
    templates.env.globals.setdefault("context_nav_context", context_nav_context)
    templates.env.globals.setdefault("admin_nav_groups", admin_nav_groups)
    templates.env.globals.setdefault("settings_nav_groups", settings_nav_groups)
    templates.env.globals.setdefault("module_route_path", lambda module_id, route_path: module_route_path(module_id, route_path) or "")

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
    templates.env.globals.setdefault("nav_section_items", nav_section_items)
    templates.env.globals.setdefault("context_nav_items", context_nav_items)
    templates.env.globals.setdefault("context_nav_context", context_nav_context)
    templates.env.globals.setdefault("admin_nav_groups", admin_nav_groups)
    templates.env.globals.setdefault("settings_nav_groups", settings_nav_groups)
    templates.env.globals.setdefault("module_route_path", lambda module_id, route_path: module_route_path(module_id, route_path) or "")

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
        daily_time_to_cron=lambda value: value,
        daily_time_from_cron=lambda value: value,
    )
    client = TestClient(app)

    response = client.post(
        "/recipes/save",
        data={
            "memory_enabled": "1",
            "return_to": "/recipes/system",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert target_raw["memory"]["enabled"] is True
    assert target_raw["auto_memory"]["enabled"] is False
    assert target_raw["skills"]["custom"]["linux-health"]["enabled"] is True


def test_recipes_wizard_page_sets_logical_back_url() -> None:
    client = _build_recipes_app()

    response = client.get("/recipes/wizard?return_to=%2Fskills")

    assert response.status_code == 200
    assert "const logical='/recipes';" in response.text
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
    assert "Create new recipe" in response.text
    assert 'const configUiOverviewPath = "/config";' in response.text
    assert 'link.href = "/config";' not in response.text


def test_recipes_wizard_get_defaults_use_registry_route_readpoints(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        seen.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_routes_module, "module_route_path", tracking_module_route_path)

    admin_client = _build_recipes_app()
    admin_response = admin_client.get("/recipes/wizard")
    readonly_client = _build_recipes_app(
        advanced_mode=False,
        auth_session=lambda _request: {"username": "neo", "role": "user"},
    )
    readonly_response = readonly_client.get("/recipes/wizard", follow_redirects=False)

    assert admin_response.status_code == 200
    assert readonly_response.status_code == 303
    assert readonly_response.headers["location"] == "/recipes?error=readonly&return_to=%2Frecipes"
    assert seen.count(("recipes_ui", "/recipes")) >= 2


def test_recipes_wizard_get_defaults_fail_closed_without_route_owner(monkeypatch) -> None:
    def missing_recipes_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "recipes_ui" and route_path == "/recipes":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_routes_module, "module_route_path", missing_recipes_route)

    admin_client = _build_recipes_app()
    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        admin_client.get("/recipes/wizard")

    readonly_client = _build_recipes_app(
        advanced_mode=False,
        auth_session=lambda _request: {"username": "neo", "role": "user"},
    )
    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        readonly_client.get("/recipes/wizard", follow_redirects=False)


def test_recipes_wizard_defaults_to_simple_mode() -> None:
    client = _build_recipes_app()

    response = client.get("/recipes/wizard")

    assert response.status_code == 200
    assert 'data-wizard-mode="simple"' in response.text
    assert "prompts/recipes/&lt;recipe-id&gt;.md" in response.text
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
            "step_1_connection_ref": "dns-node-01",
            "step_1_command": "uptime",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "mode=advanced" in response.headers["location"]


def _ssh_timeout_recipe_form(*, name: str, timeout: str) -> dict[str, str]:
    return {
        "skill_name": name,
        "skill_type": "health_check",
        "wizard_mode": "advanced",
        "schedule_enabled": "0",
        "enabled_default": "0",
        "step_1_enabled": "1",
        "step_1_id": "s1",
        "step_1_name": "Upgrade",
        "step_1_type": "ssh_run",
        "step_1_on_error": "stop",
        "step_1_connection_ref": "srv-1",
        "step_1_command": "apt update && apt upgrade -y",
        "step_1_timeout_seconds": timeout,
    }


def _prepare_ssh_timeout_recipe_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    recipes_dir = tmp_path / "data" / "recipes"
    recipes_dir.mkdir(parents=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", tmp_path)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "LEGACY_SKILLS_STORE_DIR", tmp_path / "data" / "skills")
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    recipe_manifests._invalidate_stored_recipe_manifest_cache()
    return recipes_dir


def test_recipes_wizard_renders_ssh_timeout_field_only_for_ssh() -> None:
    response = _build_recipes_app().get("/recipes/wizard")

    assert response.status_code == 200
    assert 'name="step_1_timeout_seconds"' in response.text
    timeout_control = response.text.split('name="step_1_timeout_seconds"', 1)[0].rsplit("<label", 1)[1]
    assert 'data-step-types="ssh_run"' in timeout_control
    assert 'type="number"' in response.text
    assert 'min="5"' in response.text
    assert "300" in response.text


def test_recipes_wizard_ssh_timeout_persists_and_reloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recipes_dir = _prepare_ssh_timeout_recipe_store(monkeypatch, tmp_path)
    client = _build_recipes_app()

    saved_response = client.post(
        "/recipes/wizard/save",
        data=_ssh_timeout_recipe_form(name="Long Upgrade", timeout="300"),
        follow_redirects=False,
    )

    assert saved_response.status_code == 303
    saved = json.loads((recipes_dir / "long-upgrade.json").read_text(encoding="utf-8"))
    assert saved["steps"][0]["params"]["timeout_seconds"] == 300
    reloaded = client.get("/recipes/wizard?skill_id=long-upgrade")
    assert reloaded.status_code == 200
    assert 'name="step_1_timeout_seconds"' in reloaded.text
    assert 'value="300"' in reloaded.text


@pytest.mark.parametrize("timeout", ["", "0", "-5", "invalid"])
def test_recipes_wizard_ssh_timeout_omits_non_positive_or_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    timeout: str,
) -> None:
    recipes_dir = _prepare_ssh_timeout_recipe_store(monkeypatch, tmp_path)
    client = _build_recipes_app()

    response = client.post(
        "/recipes/wizard/save",
        data=_ssh_timeout_recipe_form(name="Default Timeout", timeout=timeout),
        follow_redirects=False,
    )

    assert response.status_code == 303
    saved = json.loads((recipes_dir / "default-timeout.json").read_text(encoding="utf-8"))
    assert "timeout_seconds" not in saved["steps"][0]["params"]


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
            "step_1_connection_ref": "dns-node-01",
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
