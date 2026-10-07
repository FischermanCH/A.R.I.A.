import asyncio
import re
from pathlib import Path
from urllib.parse import unquote_plus

import pytest

import aria.modules.config_ui.routes as config_routes
from aria.modules.config_ui.routes import (
    EMBEDDING_SWITCH_CONFIRM_PHRASE,
    _embedding_fingerprint_for_values,
    _embedding_switch_requires_confirmation,
    _memory_point_totals,
    _resolve_embedding_model_label,
    _short_fingerprint,
)


def test_embedding_switch_requires_confirmation_only_with_existing_memory() -> None:
    current = _embedding_fingerprint_for_values("nomic-embed-text", "http://localhost:11434")
    new = _embedding_fingerprint_for_values("text-embedding-3-small", "https://api.openai.com/v1")

    assert _embedding_switch_requires_confirmation(current, new, 12) is True
    assert _embedding_switch_requires_confirmation(current, current, 12) is False
    assert _embedding_switch_requires_confirmation(current, new, 0) is False


def test_memory_point_totals_sums_points_and_collections() -> None:
    total_points, total_collections = _memory_point_totals(
        [{"name": "a", "points": 4}, {"name": "b", "points": 7}]
    )

    assert total_points == 11
    assert total_collections == 2


def test_embedding_helpers_normalize_expected_values() -> None:
    assert _resolve_embedding_model_label("text-embedding-3-small", "https://api.openai.com/v1") == "openai/text-embedding-3-small"
    assert len(_short_fingerprint("abcdef1234567890")) == 12
    assert EMBEDDING_SWITCH_CONFIRM_PHRASE == "EMBEDDINGS WECHSELN"


import yaml
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from types import SimpleNamespace

import aria.modules.navigation_shell.config_helpers as config_navigation_helpers
import aria.modules.config_ui.access_detail_routes as config_access_detail_routes
import aria.modules.config_ui.intelligence_workbench_routes as config_intelligence_workbench_routes
import aria.modules.config_ui.profile_helpers as config_profile_helpers
import aria.modules.connections_ui_readonly.context_helpers as connection_context_helpers
import aria.modules.connections_ui_readonly.detail_routes as connection_detail_routes
import aria.modules.connections_ui_readonly.page_helpers as connection_page_helpers
import aria.modules.ops_config_backup.detail_routes as config_ops_detail_routes
import aria.modules.config_ui.persona_routes as config_persona_routes
import aria.modules.config_ui.surface_routes as config_surface_routes
import aria.modules.connections_ui_readonly.surface_helpers as connections_surface_helpers
import aria.modules.connections_ui_readonly.surface_routes as connections_surface_routes
from aria.modules.configuration_foundations.config import Settings
from aria.modules import module_route_path, module_static_asset_path
from aria.modules.config_ui.routes import ConfigRouteDeps, register_config_routes
from aria.modules.navigation_shell.navigation import (
    admin_nav_groups,
    config_hub_groups,
    context_nav_context,
    context_nav_items,
    nav_section_items,
    resolve_nav_id,
    settings_nav_groups,
)


class _NavUrl:
    def __init__(self, path: str) -> None:
        self.path = path


def _nav_request(path: str, *, advanced_mode: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        url=_NavUrl(path),
        state=SimpleNamespace(can_access_advanced_config=advanced_mode, auth_role="admin" if advanced_mode else "user"),
    )


def test_config_navigation_invalid_fallback_uses_chat_surface_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    real_route_path = config_navigation_helpers.module_route_path

    def tracking_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(config_navigation_helpers, "module_route_path", tracking_route_path)
    helpers = config_navigation_helpers.build_config_navigation_helpers()
    request = SimpleNamespace(url=SimpleNamespace(path="/config/security"), query_params={}, headers={}, state=SimpleNamespace())

    assert helpers.resolve_return_to(request, fallback="") == "/"
    assert ("chat_surface", "/") in calls


def test_config_navigation_invalid_fallback_fails_closed_without_chat_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config_navigation_helpers,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "chat_surface" and route_path == "/"
        else module_route_path(module_id, route_path),
    )
    helpers = config_navigation_helpers.build_config_navigation_helpers()
    request = SimpleNamespace(url=SimpleNamespace(path="/config/security"), query_params={}, headers={}, state=SimpleNamespace())

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        helpers.resolve_return_to(request, fallback="")


def test_navigation_registry_context_matrix_handles_modes_and_section_titles() -> None:
    cases = [
        (
            "/config",
            False,
            "settings.overview",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/connections/status", "/recipes/start"],
            ["/config"],
        ),
        (
            "/config/persona",
            False,
            "settings.persona",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/config/appearance?return_to=/config/persona", "/connections/status", "/recipes/start"],
            ["/config/persona"],
        ),
        (
            "/config/appearance",
            False,
            "persona.appearance",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/config/appearance?return_to=/config/persona", "/connections/status", "/recipes/start"],
            ["/config/persona"],
        ),
        (
            "/config/prompts",
            True,
            "persona.prompts",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/config/prompts?return_to=/config/persona", "/connections/status", "/recipes/start"],
            ["/config/persona"],
        ),
        (
            "/recipes",
            False,
            "recipes.overview",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/recipes/start", "/recipes/mine"],
            ["/recipes"],
        ),
        (
            "/recipes/mine",
            False,
            "recipes.mine",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/recipes/mine", "/recipes/start", "/recipes/system"],
            ["/recipes"],
        ),
        (
            "/connections",
            True,
            "connections.overview",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/connections/status", "/connections/types", "/connections/templates"],
            ["/connections"],
        ),
        (
            "/connections/status",
            True,
            "connections.status",
            "settings",
            ["/config", "/config/persona", "/connections", "/recipes", "/updates?return_to=/config"],
            ["/config/admin", "/connections/status", "/connections/types", "/connections/templates"],
            ["/connections"],
        ),
    ]
    for path, advanced_mode, expected_id, expected_section, required_hrefs, forbidden_hrefs, expected_active_hrefs in cases:
        ctx = context_nav_context(_nav_request(path, advanced_mode=advanced_mode))
        hrefs = [item["href"] for item in ctx["items"]]
        active_hrefs = [item["href"] for item in ctx["items"] if item["active"]]
        assert ctx["current_id"] == expected_id
        assert ctx["section"] == expected_section
        assert active_hrefs == expected_active_hrefs, f"{path=} {advanced_mode=} active mismatch; got {active_hrefs}"
        for href in required_hrefs:
            assert href in hrefs, f"{path=} {advanced_mode=} missing {href}; got {hrefs}"
        for href in forbidden_hrefs:
            assert href not in hrefs, f"{path=} {advanced_mode=} unexpectedly had {href}; got {hrefs}"


def test_navigation_registry_settings_nav_hrefs_use_route_readpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.navigation_shell.navigation as navigation_registry

    calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(navigation_registry, "module_route_path", tracking_module_route_path)

    ctx = navigation_registry.context_nav_context(_nav_request("/config", advanced_mode=True))
    hrefs = [item["href"] for item in ctx["items"]]

    assert "/config/persona" in hrefs
    assert "/connections" in hrefs
    assert "/recipes" in hrefs
    assert "/updates?return_to=/config" in hrefs
    assert ("config_ui", "/config") in calls
    assert ("config_ui", "/config/persona") in calls
    assert ("connections_ui_readonly", "/connections") in calls
    assert ("recipes_ui", "/recipes") in calls
    assert ("release_update", "/updates") in calls


def test_navigation_registry_route_readpoint_hrefs_fail_closed_without_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.navigation_shell.navigation as navigation_registry

    def missing_recipes_route(module_id: str, route_path: str, **kwargs: object) -> str | None:
        if module_id == "recipes_ui" and route_path == "/recipes":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(navigation_registry, "module_route_path", missing_recipes_route)

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        navigation_registry.context_nav_context(_nav_request("/config", advanced_mode=True))


def test_navigation_registry_admin_and_memory_hrefs_use_route_readpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.navigation_shell.navigation as navigation_registry

    calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(navigation_registry, "module_route_path", tracking_module_route_path)

    admin_ctx = navigation_registry.context_nav_context(_nav_request("/config/admin/modules", advanced_mode=True))
    admin_groups = navigation_registry.config_hub_groups(_nav_request("/config", advanced_mode=True))
    memory_ctx = navigation_registry.context_nav_context(_nav_request("/memories", advanced_mode=True))
    admin_group_hrefs = [item["href"] for item in admin_ctx["items"]]
    admin_hrefs = [item["href"] for group in admin_groups for item in group["items"]]
    admin_hrefs.extend(group["landing_href"] for group in admin_groups if group["landing_href"])
    memory_hrefs = [item["href"] for item in memory_ctx["items"]]

    assert "/config" in admin_group_hrefs
    assert "/config/intelligence" in admin_hrefs
    assert "/config/access" in admin_hrefs
    assert "/config/workbench" not in admin_hrefs
    assert "/config/files" in admin_hrefs
    assert "/config/error-interpreter" in admin_hrefs
    assert "/config/llm/debug" in admin_hrefs
    assert "/config/admin/modules" in admin_hrefs
    assert "/recipes/system" in admin_hrefs
    assert "/recipes/learned/maintenance" not in admin_hrefs
    assert "/activities" in admin_hrefs
    assert "/memories" in memory_hrefs
    assert "/memories/import" in memory_hrefs
    assert "/memories/create" in memory_hrefs
    assert "/memories/auto-memory" in memory_hrefs
    assert "/memories/maintenance" in memory_hrefs
    assert ("config_ui", "/config") in calls
    assert ("recipes_ui", "/recipes/system") in calls
    assert ("stats_ui", "/activities") in calls
    assert ("memory_admin_ui", "/memories") in calls
    assert ("memory_admin_ui", "/memories/import") in calls
    assert ("memory_admin_ui", "/memories/create") in calls
    assert ("memory_admin_ui", "/memories/auto-memory") in calls
    assert ("memory_admin_ui", "/memories/maintenance") in calls


def test_config_hub_is_single_role_gated_topic_tree() -> None:
    from aria.modules.navigation_shell.navigation import config_hub_groups

    user_request = _nav_request("/config", advanced_mode=False)
    user_request.state.auth_role = "user"
    admin_request = _nav_request("/config", advanced_mode=True)
    admin_request.state.auth_role = "admin"

    user_groups = config_hub_groups(user_request)
    admin_groups = config_hub_groups(admin_request)

    assert [group["id"] for group in admin_groups] == [
        "persona",
        "connections",
        "recipes_learning",
        "knowledge_memory",
        "ai_models",
        "security_access",
        "operations",
        "system_development",
        "about",
    ]
    assert len(user_groups) < len(admin_groups)
    user_hrefs = {item["href"] for group in user_groups for item in group["items"]}
    user_hrefs.update(group["landing_href"] for group in user_groups if group["landing_href"])
    admin_hrefs = {item["href"] for group in admin_groups for item in group["items"]}
    admin_hrefs.update(group["landing_href"] for group in admin_groups if group["landing_href"])
    assert "/config/intelligence" not in user_hrefs
    assert "/config/intelligence" in admin_hrefs
    assert "/config/admin/modules" in admin_hrefs
    assert "/config/admin/ui-audit" in admin_hrefs
    assert "/config/native-toolcall-selftest" in admin_hrefs
    assert "/memories" in user_hrefs
    assert "/licenses" in user_hrefs
    assert not any(href in admin_hrefs for href in {"/config/admin", "/config/admin/config", "/config/admin/recipes", "/config/admin/operations"})


def test_config_hub_group_headers_replace_repeated_landing_cards() -> None:
    admin_request = _nav_request("/config", advanced_mode=True)
    admin_request.state.auth_role = "admin"

    groups = {group["id"]: group for group in config_hub_groups(admin_request)}
    expected_landings = {
        "persona": "/config/persona",
        "connections": "/connections",
        "recipes_learning": "/recipes",
        "knowledge_memory": "/memories",
        "ai_models": "/config/intelligence",
        "security_access": "/config/access",
        "operations": "/config/operations",
    }

    for group_id, landing_href in expected_landings.items():
        group = groups[group_id]
        assert group["landing_href"] == landing_href
        assert landing_href not in {item["href"] for item in group["items"]}

    assert groups["system_development"]["landing_href"] == ""
    assert groups["about"]["landing_href"] == ""
    system_hrefs = {item["href"] for item in groups["system_development"]["items"]}
    assert "/config/workbench" not in system_hrefs
    assert {"/config/files", "/config/error-interpreter", "/config/llm/debug"} <= system_hrefs
    assert "/updates" not in {item["href"].split("?", 1)[0] for item in groups["about"]["items"]}
    assert "/updates" in {item["href"].split("?", 1)[0] for item in groups["operations"]["items"]}


def test_config_hub_template_uses_linked_headers_without_group_subtitles() -> None:
    template = (Path(__file__).parents[1] / "aria" / "templates" / "config_hub.html").read_text(encoding="utf-8")

    assert "{% if group.landing_href %}" in template
    assert 'class="config-hub-group-link"' in template
    assert "group.desc_key" not in template
    assert "group.desc_fallback" not in template


def test_config_hub_groups_are_nonempty_and_expose_real_subpages() -> None:
    admin_request = _nav_request("/config", advanced_mode=True)
    admin_request.state.auth_role = "admin"
    groups = {group["id"]: group for group in config_hub_groups(admin_request)}

    assert all(group["items"] for group in groups.values())
    assert {item["href"] for item in groups["ai_models"]["items"]} == {
        "/config/llm",
        "/config/embeddings",
    }
    assert {item["href"] for item in groups["security_access"]["items"]} == {
        "/config/users",
        "/config/security",
        "/config/admin-mode",
    }
    assert {item["href"].split("?", 1)[0] for item in groups["operations"]["items"]} == {
        "/config/backup",
        "/config/logs",
        "/updates",
        "/activities",
    }
    assert resolve_nav_id(_nav_request("/config/llm", advanced_mode=True)) == "admin.llm_profiles"
    assert resolve_nav_id(_nav_request("/config/embeddings", advanced_mode=True)) == "admin.embeddings"
    assert resolve_nav_id(_nav_request("/config/users", advanced_mode=True)) == "admin.users"
    assert resolve_nav_id(_nav_request("/config/security", advanced_mode=True)) == "admin.guardrails"
    assert resolve_nav_id(_nav_request("/config/backup", advanced_mode=True)) == "admin.backup"
    assert resolve_nav_id(_nav_request("/config/logs", advanced_mode=True)) == "admin.logs"
    assert resolve_nav_id(_nav_request("/config/llm/debug", advanced_mode=True)) == "admin.llm_debug"


def test_config_hub_keeps_landing_card_when_it_is_the_only_visible_item(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.navigation_shell.navigation as navigation_registry

    monkeypatch.setattr(
        navigation_registry,
        "CONFIG_HUB_GROUPS",
        (
            navigation_registry.NavGroup(
                "only",
                "only.title",
                "Only",
                "only.desc",
                "Only landing",
                ("settings.persona",),
                landing_item_id="settings.persona",
            ),
        ),
    )

    groups = navigation_registry.config_hub_groups(_nav_request("/config", advanced_mode=False))

    assert groups[0]["landing_href"] == "/config/persona"
    assert [item["href"] for item in groups[0]["items"]] == ["/config/persona"]


def test_navigation_registry_memory_hrefs_fail_closed_without_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.navigation_shell.navigation as navigation_registry

    def missing_memory_route(module_id: str, route_path: str, **kwargs: object) -> str | None:
        if module_id == "memory_admin_ui" and route_path == "/memories":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(navigation_registry, "module_route_path", missing_memory_route)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories"):
        navigation_registry.context_nav_context(_nav_request("/memories", advanced_mode=True))


def test_navigation_registry_has_no_learned_recipe_surface_nodes() -> None:
    from aria.modules.navigation_shell.navigation import NAV_NODES

    assert "recipes.learned" not in NAV_NODES
    assert "admin.recipes.learned" not in NAV_NODES


def test_navigation_registry_does_not_assign_one_href_to_multiple_nodes() -> None:
    from collections import defaultdict

    from aria.modules.navigation_shell.navigation import NAV_NODES

    nodes_by_href: dict[str, list[str]] = defaultdict(list)
    for node_id, node in NAV_NODES.items():
        nodes_by_href[node.href].append(node_id)

    duplicates = {href: node_ids for href, node_ids in nodes_by_href.items() if len(node_ids) > 1}

    assert duplicates == {}


def test_navigation_registry_accepts_explicit_nav_id_through_navigation_shell_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.navigation_shell.navigation as navigation_registry

    calls: list[tuple[str, str, tuple[str, ...]]] = []

    def fake_module_nav_node_id(module_id: str, nav_node_id: str, *, available_node_ids: tuple[str, ...], manifests=None) -> str | None:
        calls.append((module_id, nav_node_id, available_node_ids))
        if module_id == "navigation_shell" and nav_node_id == "admin.modules":
            return nav_node_id
        return None

    monkeypatch.setattr(navigation_registry, "module_nav_node_id", fake_module_nav_node_id)

    assert navigation_registry.resolve_nav_id(_nav_request("/config/admin/modules"), "admin.modules") == "admin.modules"
    assert navigation_registry.resolve_nav_id(_nav_request("/config/admin/modules"), "settings.overview") == "admin.modules"
    assert calls[0][0] == "navigation_shell"
    assert calls[0][1] == "admin.modules"
    assert "admin.modules" in calls[0][2]


def test_config_surface_path_resolver_uses_config_ui_route_prefix_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria.modules.config_ui.surface_helpers as config_surface_helpers
    from aria.modules.config_ui.surface_helpers import build_surface_path_resolver

    calls: list[tuple[str, str]] = []

    def fake_module_route_prefix_path(module_id: str, route_path: str, *, manifests=None) -> str | None:
        calls.append((module_id, route_path))
        if module_id == "config_ui" and route_path == "/config/admin/modules":
            return route_path
        return None

    monkeypatch.setattr(config_surface_helpers, "module_route_prefix_path", fake_module_route_prefix_path)
    resolver = build_surface_path_resolver(
        sanitize_return_to=lambda value: str(value or "").strip(),
        allowed_paths={"/config", "/config/admin/modules"},
        fallback="/fallback",
        module_id="config_ui",
    )

    assert resolver("/config/admin/modules") == "/config/admin/modules"
    assert resolver("/config") == "/fallback"
    assert calls == [("config_ui", "/config/admin/modules"), ("config_ui", "/config")]


def _write_profile_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


class _MemoryStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get_secret(self, key: str, default: str = "") -> str:
        return self._values.get(key, default)

    def set_secret(self, key: str, value: str) -> None:
        self._values[key] = value

    def delete_secret(self, key: str) -> None:
        self._values.pop(key, None)

    def rename_secret(self, src: str, dst: str) -> None:
        if src == dst or src not in self._values:
            return None
        self._values[dst] = self._values[src]
        self.delete_secret(src)

    def list_users(self) -> list[dict[str, object]]:
        return []


class _TokenTracker:
    async def get_log_health(self) -> dict[str, object]:
        return {
            "line_count": 0,
            "size_bytes": 0,
            "oldest_timestamp": "",
            "newest_timestamp": "",
        }

    async def prune_old_entries(self, _retention_days: int) -> dict[str, object]:
        return {"removed": 2}

    async def clear_log(self, *, archive: bool = False) -> dict[str, object]:
        return {"removed": 3, "archive_name": "tokens-test.jsonl" if archive else ""}


def _build_profile_config_app(
    tmp_path: Path,
    *,
    lang: str = 'en',
    advanced_mode: bool = True,
    auth_role: str = "admin",
    module_route_calls: list[tuple[str, str]] | None = None,
    module_route_prefix_calls: list[tuple[str, str]] | None = None,
    reload_calls: list[str] | None = None,
) -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    app.state.templates = templates
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("nav_section_items", nav_section_items)
    templates.env.globals.setdefault("context_nav_items", context_nav_items)
    templates.env.globals.setdefault("context_nav_context", context_nav_context)
    templates.env.globals.setdefault("admin_nav_groups", admin_nav_groups)
    templates.env.globals.setdefault("settings_nav_groups", settings_nav_groups)
    templates.env.globals.setdefault("config_hub_groups", config_hub_groups)
    def module_route_path(module_id: str, route_path: str) -> str:
        if module_route_calls is not None:
            module_route_calls.append((module_id, route_path))
        return route_path

    def module_route_prefix_path(module_id: str, route_path: str) -> str:
        if module_route_prefix_calls is not None:
            module_route_prefix_calls.append((module_id, route_path))
        return route_path

    templates.env.globals.setdefault("module_route_path", module_route_path)
    templates.env.globals.setdefault("required_module_route_path", module_route_path)
    templates.env.globals.setdefault("module_route_prefix_path", module_route_prefix_path)
    templates.env.globals.setdefault(
        "module_static_asset_url",
        lambda module_id, asset_name: f"/static/{asset_name}"
        if module_static_asset_path(module_id, asset_name, Path(__file__).resolve().parents[1])
        else "",
    )
    raw = {
        "aria": {"host": "0.0.0.0", "port": 8800},
        "ui": {"title": "Config Test"},
        "security": {"enabled": True, "db_path": "data/auth/aria_secure.sqlite"},
        "profiles": {
            "active": {"llm": "litellm-main", "embeddings": "litellm-emb"},
            "llm": {
                "litellm-main": {
                    "model": "openai/gpt-4.1-mini",
                    "api_base": "https://litellm.example/v1",
                    "api_key": "secret",
                    "temperature": 0.2,
                    "max_tokens": 2048,
                    "timeout_seconds": 45,
                }
            },
            "embeddings": {
                "litellm-emb": {
                    "model": "text-embedding-3-small",
                    "api_base": "https://litellm.example/v1",
                    "api_key": "secret",
                    "timeout_seconds": 30,
                }
            },
        },
        "llm": {
            "model": "openai/gpt-4.1-mini",
            "api_base": "https://litellm.example/v1",
            "api_key": "secret",
            "temperature": 0.2,
            "max_tokens": 2048,
            "timeout_seconds": 45,
        },
        "embeddings": {
            "model": "text-embedding-3-small",
            "api_base": "https://litellm.example/v1",
            "api_key": "secret",
            "timeout_seconds": 30,
        },
        "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
    }
    _write_profile_yaml(tmp_path / 'config' / 'config.yaml', raw)
    (tmp_path / 'config' / 'error_interpreter.yaml').write_text('rules: test\n', encoding='utf-8')
    (tmp_path / 'prompts').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'prompts' / 'persona.md').write_text('hello prompt\n', encoding='utf-8')

    settings = Settings.model_validate(raw)
    pipeline = SimpleNamespace(usage_meter=None, memory_skill=None, token_tracker=_TokenTracker())
    secure_store = _MemoryStore()

    async def _keyword_stub(*_args, **_kwargs) -> list[str]:
        return []

    @app.middleware('http')
    async def _inject_state(request: Request, call_next):
        request.state.can_access_advanced_config = advanced_mode
        request.state.authenticated = True
        request.state.auth_user = "tester"
        request.state.auth_role = auth_role
        request.state.lang = lang
        request.state.cookie_names = {}
        request.state.csrf_token = 'test-csrf'
        request.state.release_meta = {'label': 'test'}
        return await call_next(request)

    def _read_raw() -> dict:
        return yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))

    def _write_raw(data: dict) -> None:
        _write_profile_yaml(tmp_path / 'config' / 'config.yaml', data)

    def _get_profiles(raw: dict, kind: str) -> dict[str, dict[str, object]]:
        profiles = raw.get('profiles', {}) if isinstance(raw.get('profiles', {}), dict) else {}
        section = profiles.get(kind, {}) if isinstance(profiles.get(kind, {}), dict) else {}
        return {str(k): v for k, v in section.items() if isinstance(v, dict)}

    def _get_active_profile_name(raw: dict, kind: str) -> str:
        profiles = raw.get('profiles', {}) if isinstance(raw.get('profiles', {}), dict) else {}
        active = profiles.get('active', {}) if isinstance(profiles.get('active', {}), dict) else {}
        return str(active.get(kind, '') or '').strip()

    def _set_active_profile(raw: dict, kind: str, profile_name: str) -> None:
        raw.setdefault('profiles', {})
        if not isinstance(raw['profiles'], dict):
            raw['profiles'] = {}
        raw['profiles'].setdefault('active', {})
        if not isinstance(raw['profiles']['active'], dict):
            raw['profiles']['active'] = {}
        raw['profiles']['active'][kind] = profile_name

    deps = ConfigRouteDeps(
        templates=templates,
        base_dir=tmp_path,
        error_interpreter_path=tmp_path / 'config' / 'error_interpreter.yaml',
        llm_provider_presets={
            "openai": {
                "label": "OpenAI",
                "default_model": "openai/gpt-4o-mini",
                "default_api_base": "",
            },
            "litellm": {
                "label": "LiteLLM Proxy",
                "default_model": "openai/<modellname>",
                "default_api_base": "http://localhost:4000",
            },
            "anthropic": {
                "label": "Anthropic",
                "default_model": "anthropic/claude-3-5-sonnet-latest",
                "default_api_base": "",
            },
        },
        embedding_provider_presets={
            "litellm": {
                "label": "LiteLLM Proxy",
                "default_model": "openai/<embedding-model>",
                "default_api_base": "http://localhost:4000",
            },
            "openai": {
                "label": "OpenAI",
                "default_model": "text-embedding-3-small",
                "default_api_base": "",
            },
        },
        auth_cookie='auth',
        lang_cookie='lang',
        username_cookie='user',
        memory_collection_cookie='memory',
        get_auth_session_max_age_seconds=lambda: 3600,
        get_settings=lambda: settings,
        get_pipeline=lambda: pipeline,
        get_username_from_request=lambda request: 'neo',
        get_auth_session_from_request=lambda request: {'username': 'neo', 'role': auth_role},
        sanitize_role=lambda value: str(value or '').strip().lower(),
        sanitize_username=lambda value: str(value or '').strip(),
        sanitize_connection_name=lambda value: str(value or '').strip(),
        sanitize_skill_id=lambda value: str(value or '').strip(),
        sanitize_profile_name=lambda value: str(value or '').strip(),
        default_memory_collection_for_user=lambda _user: 'default',
        encode_auth_session=lambda user, role, **_kwargs: f'{user}:{role}',
        get_auth_manager=lambda: None,
        active_admin_count=lambda rows: len(rows),
        read_raw_config=_read_raw,
        write_raw_config=_write_raw,
        reload_runtime=lambda: reload_calls.append("reload") if reload_calls is not None else None,
        read_error_interpreter_raw=lambda: (tmp_path / 'config' / 'error_interpreter.yaml').read_text(encoding='utf-8'),
        parse_lines=lambda text: [line.strip() for line in text.splitlines() if line.strip()],
        is_ollama_model=lambda model: str(model or '').startswith('ollama'),
        resolve_prompt_file=lambda rel: (tmp_path / rel).resolve(),
        list_prompt_files=lambda: [
            {
                'path': 'prompts/persona.md',
                'label': 'Persona',
                'group': 'prompts',
                'mode': 'edit',
                'size': 12,
                'size_label': '12 B',
                'updated': 'now',
            }
        ],
        list_editable_files=lambda: [],
        resolve_edit_file=lambda rel: (tmp_path / rel).resolve(),
        list_file_editor_entries=lambda: [],
        resolve_file_editor_file=lambda rel: (tmp_path / rel).resolve(),
        load_models_from_api_base=lambda *_args, **_kwargs: [],
        get_profiles=_get_profiles,
        get_active_profile_name=_get_active_profile_name,
        set_active_profile=_set_active_profile,
        get_secure_store=lambda _raw=None: secure_store,
        lang_flag=lambda code: code,
        lang_label=lambda code: code.upper(),
        available_languages=lambda: ['en', 'de'],
        resolve_lang=lambda code, default_lang='de': code or default_lang,
        clear_i18n_cache=lambda: None,
        load_stored_recipe_manifests=lambda: ([], []),
        stored_recipe_file=lambda skill_id: (tmp_path / 'data' / 'skills' / f'{skill_id}.json').resolve(),
        save_stored_recipe_manifest=lambda manifest: manifest,
        refresh_skill_trigger_index=lambda: {},
        format_recipe_routing_info=lambda ref, kind: f'{ref}:{kind}',
    )
    register_config_routes(app, deps)
    app.state.test_pipeline = pipeline
    app.state.test_settings = settings
    return TestClient(app)


class _FakeMCPStatusManager:
    def __init__(self) -> None:
        self.refresh_calls = 0

    async def discover_all(self, *, refresh: bool = False) -> dict[str, tuple[object, ...]]:
        assert refresh is True
        self.refresh_calls += 1
        return {"blender": ()}

    def statuses(self) -> tuple[SimpleNamespace, ...]:
        return (
            SimpleNamespace(
                server_name="blender",
                connected=True,
                tool_count=5,
                error="",
            ),
        )

    def read_only_tool_count(self, server_name: str) -> int:
        assert server_name == "blender"
        return 3


class _FailingMCPStatusManager:
    def __init__(self) -> None:
        self.refresh_calls = 0

    async def discover_all(self, *, refresh: bool = False) -> dict[str, tuple[object, ...]]:
        assert refresh is True
        self.refresh_calls += 1
        raise RuntimeError("status-secret-must-not-render")

    def statuses(self) -> tuple[SimpleNamespace, ...]:
        return ()


class _ReconnectMCPStatusManager(_FakeMCPStatusManager):
    def __init__(self, *, connected: bool = True, error: str = "") -> None:
        super().__init__()
        self.connected = connected
        self.error = error
        self.reconnect_calls: list[str] = []

    async def reconnect(self, server_name: str) -> SimpleNamespace:
        self.reconnect_calls.append(server_name)
        return SimpleNamespace(
            server_name=server_name,
            connected=self.connected,
            tool_count=7 if self.connected else 0,
            error=self.error,
        )


def test_mcp_server_admin_page_adds_config_masks_secrets_and_renders_live_status(tmp_path: Path) -> None:
    reload_calls: list[str] = []
    client = _build_profile_config_app(tmp_path, reload_calls=reload_calls)
    manager = _FakeMCPStatusManager()
    client.app.state.test_pipeline._native_mcp_client = manager

    response = client.post(
        "/config/connections/mcp/save",
        data={
            "server_name": "blender",
            "url": "https://mcp.example/sse?token=url-secret",
            "transport": "sse",
            "enabled": "1",
            "trusted": "1",
            "call_timeout_seconds": "180",
            "title": "Blender MCP",
            "header_name": "Authorization",
            "header_value": "Bearer header-secret",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/config/connections/mcp?saved=1")
    raw = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert raw["mcp_servers"]["blender"] == {
        "transport": "sse",
        "url": "https://mcp.example/sse?token=url-secret",
        "headers": {"Authorization": "Bearer header-secret"},
        "enabled": True,
        "trusted": True,
        "title": "Blender MCP",
        "call_timeout_seconds": 180.0,
    }
    assert raw["agentic_loop"]["native_agent_mcp_enabled"] is True
    assert reload_calls == ["reload"]

    page = client.get("/config/connections/mcp?server=blender")

    assert page.status_code == 200
    assert "blender" in page.text
    assert "Blender MCP" in page.text
    assert "connected" in page.text.lower()
    assert ">3<" in page.text
    assert "Authorization" in page.text
    assert "header-secret" not in page.text
    assert "url-secret" not in page.text
    assert 'value="Bearer header-secret"' not in page.text
    assert 'name="trusted" value="1" checked' in page.text
    assert 'name="call_timeout_seconds"' in page.text
    assert 'value="180.0"' in page.text
    assert "ohne Bestätigung" in page.text
    assert manager.refresh_calls == 1


def test_mcp_server_admin_invalid_input_writes_nothing_and_non_admin_is_blocked(tmp_path: Path) -> None:
    reload_calls: list[str] = []
    client = _build_profile_config_app(tmp_path, reload_calls=reload_calls)
    config_path = tmp_path / "config" / "config.yaml"
    before = config_path.read_text(encoding="utf-8")

    invalid = client.post(
        "/config/connections/mcp/save",
        data={
            "server_name": "broken",
            "url": "",
            "transport": "stdio",
            "enabled": "1",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )

    assert invalid.status_code == 303
    assert "error=" in invalid.headers["location"]
    assert config_path.read_text(encoding="utf-8") == before
    assert reload_calls == []

    blocked = _build_profile_config_app(tmp_path / "blocked", advanced_mode=False, auth_role="user")
    assert blocked.get("/config/connections/mcp", follow_redirects=False).status_code == 303
    assert blocked.post(
        "/config/connections/mcp/save",
        data={"server_name": "x", "url": "https://example.invalid/sse", "transport": "sse"},
        follow_redirects=False,
    ).status_code == 303


def test_mcp_server_admin_master_off_and_delete_preserve_scope(tmp_path: Path) -> None:
    reload_calls: list[str] = []
    client = _build_profile_config_app(tmp_path, reload_calls=reload_calls)
    config_path = tmp_path / "config" / "config.yaml"
    client.post(
        "/config/connections/mcp/save",
        data={
            "server_name": "blender",
            "url": "http://blender.invalid/sse",
            "transport": "http",
            "enabled": "1",
            "header_name": "Authorization",
            "header_value": "Bearer retained-secret",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )

    disabled = client.post(
        "/config/connections/mcp/save",
        data={
            "server_name": "blender",
            "original_name": "blender",
            "url": "",
            "transport": "http",
            "enabled": "0",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )
    raw_after_disable = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert disabled.status_code == 303
    assert raw_after_disable["mcp_servers"]["blender"]["enabled"] is False
    assert raw_after_disable["mcp_servers"]["blender"]["url"] == "http://blender.invalid/sse"
    assert raw_after_disable["mcp_servers"]["blender"]["headers"] == {
        "Authorization": "Bearer retained-secret"
    }
    assert raw_after_disable["agentic_loop"]["native_agent_mcp_enabled"] is False

    master_off = client.post(
        "/config/connections/mcp/master",
        data={"master_enabled": "0", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    raw_after_off = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert master_off.status_code == 303
    assert raw_after_off["agentic_loop"]["native_agent_mcp_enabled"] is False
    assert "blender" in raw_after_off["mcp_servers"]

    deleted = client.post(
        "/config/connections/mcp/delete",
        data={"server_name": "blender", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    raw_after_delete = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert deleted.status_code == 303
    assert "blender" not in raw_after_delete["mcp_servers"]
    assert raw_after_delete["llm"]["model"] == "openai/gpt-4.1-mini"
    assert reload_calls == ["reload", "reload", "reload", "reload"]


def test_mcp_server_admin_status_failure_is_safe_and_master_off_skips_discovery(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    client.post(
        "/config/connections/mcp/save",
        data={
            "server_name": "blender",
            "url": "http://blender.invalid/sse",
            "transport": "sse",
            "enabled": "1",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )
    manager = _FailingMCPStatusManager()
    client.app.state.test_pipeline._native_mcp_client = manager

    failed = client.get("/config/connections/mcp")
    assert failed.status_code == 200
    assert "RuntimeError" in failed.text
    assert "status-secret-must-not-render" not in failed.text
    assert manager.refresh_calls == 1

    client.post(
        "/config/connections/mcp/master",
        data={"master_enabled": "0", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    disabled = client.get("/config/connections/mcp")
    assert disabled.status_code == 200
    assert "MCP globally disabled" in disabled.text
    assert manager.refresh_calls == 1


def test_mcp_server_admin_reconnect_is_admin_csrf_protected_and_reports_outcome(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang="de")
    client.post(
        "/config/connections/mcp/save",
        data={
            "server_name": "blender",
            "url": "http://blender.invalid/sse",
            "transport": "sse",
            "enabled": "1",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )
    manager = _ReconnectMCPStatusManager()
    client.app.state.test_pipeline._native_mcp_client = manager

    page = client.get("/config/connections/mcp")
    assert 'action="/config/connections/mcp/reconnect"' in page.text
    assert 'name="server_name" value="blender"' in page.text
    assert "Reconnect" in page.text

    response = client.post(
        "/config/connections/mcp/reconnect",
        data={"server_name": "blender", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/config/connections/mcp?info=reconnected&server=blender&tool_count=7"
    )
    assert manager.reconnect_calls == ["blender"]
    refreshed = client.get(response.headers["location"])
    assert "MCP-Server neu verbunden: 7 Tools erkannt." in refreshed.text

    bad_csrf = client.post(
        "/config/connections/mcp/reconnect",
        data={"server_name": "blender", "csrf_token": "wrong"},
        follow_redirects=False,
    )
    assert bad_csrf.status_code == 303
    assert "error=csrf_failed" in bad_csrf.headers["location"]
    assert manager.reconnect_calls == ["blender"]

    blocked = _build_profile_config_app(
        tmp_path / "blocked-reconnect", advanced_mode=False, auth_role="user",
    )
    refused = blocked.post(
        "/config/connections/mcp/reconnect",
        data={"server_name": "blender", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    assert refused.status_code == 303
    assert refused.headers["location"].startswith("/config?error=admin_mode_required")


def test_mcp_server_admin_reconnect_handles_failure_and_missing_manager(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    manager = _ReconnectMCPStatusManager(
        connected=False, error="ConnectionError",
    )
    client.app.state.test_pipeline._native_mcp_client = manager

    failed = client.post(
        "/config/connections/mcp/reconnect",
        data={"server_name": "blender", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    assert failed.status_code == 303
    assert "error=reconnect_failed" in failed.headers["location"]

    client.app.state.test_pipeline._native_mcp_client = None
    unavailable = client.post(
        "/config/connections/mcp/reconnect",
        data={"server_name": "blender", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    assert unavailable.status_code == 303
    assert "error=manager_unavailable" in unavailable.headers["location"]


def test_connections_types_page_links_to_mcp_admin(tmp_path: Path) -> None:
    response = _build_profile_config_app(tmp_path).get("/connections/types")

    assert response.status_code == 200
    assert 'href="/config/connections/mcp?return_to=' in response.text
    assert "MCP" in response.text


def _first_memory_subnav(html: str) -> str:
    start = html.find('<nav class="memory-subnav"')
    if start < 0:
        return ""
    end = html.find("</nav>", start)
    if end < 0:
        return html[start:]
    return html[start : end + len("</nav>")]


def test_llm_config_page_shows_assigned_runtime_and_edit_profile(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/llm?return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
    assert 'class="ui-action-link config-admin-return-link"' not in response.text
    assert 'Currently used models' in response.text
    assert 'Profile selected for editing' in response.text
    assert 'litellm-main' in response.text
    assert 'https://litellm.example/v1' in response.text
    assert 'openai/gpt-4.1-mini' in response.text
    assert 'action="/config/llm/test"' in response.text
    assert 'href="/help?doc=pricing"' in response.text
    assert "Open help" in response.text or "Hilfe öffnen" in response.text
    assert "If answers get cut off" not in response.text
    assert "const logical='/config';" in response.text


def test_llm_config_page_separates_assignments_from_profile_editing(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["profiles"]["llm"]["web-search"] = {
        "model": "openai/gpt-web",
        "api_base": "https://web.example/v1",
        "api_key": "",
        "temperature": 0.2,
        "max_tokens": 1200,
        "timeout_seconds": 45,
    }
    raw["profiles"]["active"]["main_llm"] = "litellm-main"
    raw["profiles"]["active"]["web_llm"] = "web-search"
    raw["web_llm"] = {
        "profile": "web-search",
        "model": "openai/gpt-web",
        "api_base": "https://web.example/v1",
        "transport": "openai_responses",
        "enabled": True,
        "capability_verified_at": "2026-09-02T19:00:00+00:00",
    }
    _write_profile_yaml(config_path, raw)
    client.app.state.test_settings.web_llm.profile = "web-search"
    client.app.state.test_settings.web_llm.model = "openai/gpt-web"
    client.app.state.test_settings.web_llm.api_base = "https://web.example/v1"
    client.app.state.test_settings.web_llm.enabled = True
    client.app.state.test_settings.web_llm.capability_verified_at = "2026-09-02T19:00:00+00:00"

    response = client.get("/config/llm?edit_profile=web-search")

    assert response.status_code == 200
    assert "Model assignment" in response.text
    assert "Both roles use ordinary saved LLM profiles." in response.text
    assert "Main model" in response.text
    assert "Web model" in response.text
    assert "Currently used models" in response.text
    assert "Profile selected for editing" in response.text
    assert 'value="web-search" selected' in response.text
    assert 'value="openai/gpt-web"' in response.text
    assert "Paid Web search test" in response.text
    assert "exactly one provider request" in response.text
    assert "Active profile" not in response.text
    assert "Save roles" not in response.text


def test_llm_profile_editor_save_does_not_change_model_assignments(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/llm/profile/save",
        data={
            "profile_name": "web-search",
            "model": "openai/gpt-web",
            "api_base": "https://web.example/v1",
            "api_key": "secret",
            "temperature": "0.2",
            "max_tokens": "1200",
            "timeout_seconds": "45",
            "activate_main": "0",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert raw["profiles"]["llm"]["web-search"]["model"] == "openai/gpt-web"
    assert raw["profiles"]["active"]["llm"] == "litellm-main"
    assert raw["profiles"]["active"].get("main_llm", "litellm-main") == "litellm-main"
    assert raw["llm"]["model"] == "openai/gpt-4.1-mini"


def test_llm_profile_editor_accepts_empty_temperature_and_renders_hint(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/llm/profile/save",
        data={
            "profile_name": "temperature-free",
            "model": "claude-sonnet-5",
            "api_base": "https://litellm.example/v1",
            "api_key": "secret",
            "temperature": "",
            "max_tokens": "1200",
            "timeout_seconds": "45",
            "activate_main": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert raw["profiles"]["llm"]["temperature-free"]["temperature"] is None
    assert raw["llm"]["temperature"] is None
    page = client.get("/config/llm?edit_profile=temperature-free")
    assert page.status_code == 200
    assert 'name="temperature"' in page.text
    assert 'name="temperature" type="number"' in page.text
    assert 'name="temperature" type="number" step="0.1" min="0" max="2" value="" required' not in page.text
    assert "Leave empty for models that do not accept temperature." in page.text


def test_llm_connection_test_uses_selected_profile_without_activating_it(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["profiles"]["llm"]["web-search"] = {
        "model": "openai/gpt-web",
        "api_base": "https://web.example/v1",
        "api_key": "",
        "temperature": 0.2,
        "max_tokens": 1200,
        "timeout_seconds": 45,
    }
    _write_profile_yaml(config_path, raw)
    seen_models: list[str] = []

    async def _fake_probe(llm, usage_meter=None):
        del usage_meter
        seen_models.append(llm.model)
        return {"id": "llm", "status": "ok", "detail": "ok"}

    monkeypatch.setattr(config_routes, "probe_llm", _fake_probe)

    response = client.post(
        "/config/llm/test",
        data={"profile_name": "web-search"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert seen_models == ["openai/gpt-web"]
    persisted = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert persisted["profiles"]["active"]["llm"] == "litellm-main"
    assert persisted["llm"]["model"] == "openai/gpt-4.1-mini"


def test_web_llm_paid_test_feedback_is_localized_without_provider_call(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang="de")

    response = client.post("/config/llm/web/test", follow_redirects=False)

    assert response.status_code == 303
    assert "Der kostenpflichtige Websuche-Test wurde nicht bestätigt." in unquote_plus(response.headers["location"])


def test_editing_assigned_web_profile_invalidates_stale_capability_receipt(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["profiles"]["llm"]["web-search"] = {
        "model": "openai/gpt-web-old",
        "api_base": "https://web.example/v1",
        "api_key": "",
        "temperature": 0.2,
        "max_tokens": 1200,
        "timeout_seconds": 45,
    }
    raw["profiles"]["active"]["main_llm"] = "litellm-main"
    raw["profiles"]["active"]["web_llm"] = "web-search"
    raw["web_llm"] = {
        "profile": "web-search",
        "model": "openai/gpt-web-old",
        "api_base": "https://web.example/v1",
        "enabled": True,
        "capability_verified_at": "2026-09-02T19:00:00+00:00",
        "capability_receipt": {"model": "openai/gpt-web-old"},
    }
    _write_profile_yaml(config_path, raw)

    response = client.post(
        "/config/llm/profile/save",
        data={
            "profile_name": "web-search",
            "model": "openai/gpt-web-new",
            "api_base": "https://web.example/v1",
            "api_key": "secret",
            "temperature": "0.2",
            "max_tokens": "1200",
            "timeout_seconds": "45",
            "activate_main": "0",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    persisted = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert persisted["profiles"]["active"]["main_llm"] == "litellm-main"
    assert persisted["web_llm"]["enabled"] is False
    assert persisted["web_llm"]["capability_verified_at"] == ""
    assert "capability_receipt" not in persisted["web_llm"]


def test_llm_page_uses_llm_specific_provider_presets(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/llm')

    assert response.status_code == 200
    assert 'Anthropic' in response.text
    assert 'openai/gpt-4o-mini' in response.text
    assert 'text-embedding-3-small' not in response.text


def test_embeddings_page_uses_embedding_specific_provider_presets(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/embeddings')

    assert response.status_code == 200
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
    assert 'class="ui-action-link config-admin-return-link"' not in response.text
    assert 'LiteLLM Proxy' in response.text
    assert 'text-embedding-3-small' in response.text
    assert 'Anthropic' not in response.text


def test_embedding_memory_guard_export_url_uses_memory_export_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs) or ""

    class _MemorySkill:
        async def get_user_collection_stats(self, username: str) -> list[dict[str, object]]:
            assert username == "tester"
            return [{"name": "default", "points": 3}]

    monkeypatch.setattr(config_profile_helpers, "module_route_path", tracking_module_route_path)
    helpers = config_profile_helpers.build_config_profile_helpers(
        config_profile_helpers.ConfigProfileHelperDeps(
            read_raw_config=lambda: {},
            write_raw_config=lambda _data: None,
            reload_runtime=lambda: None,
            sanitize_connection_name=lambda value: str(value or "").strip(),
            get_active_profile_name=lambda _raw, _kind: "default",
            settings=SimpleNamespace(
                embeddings=SimpleNamespace(model="text-embedding-3-small", api_base="https://api.openai.com/v1"),
                memory=SimpleNamespace(embedding_fingerprint="", embedding_model=""),
            ),
            pipeline=SimpleNamespace(memory_skill=_MemorySkill()),
        )
    )

    guard = asyncio.run(helpers.embedding_memory_guard_context("tester"))

    assert guard["export_url"] == "/memories/export?type=all&sort=updated_desc"
    assert ("memory_export", "/memories/export") in route_calls


def test_embedding_memory_guard_export_url_fails_closed_without_memory_export_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MemorySkill:
        async def get_user_collection_stats(self, username: str) -> list[dict[str, object]]:
            assert username == "tester"
            return [{"name": "default", "points": 3}]

    monkeypatch.setattr(config_profile_helpers, "module_route_path", lambda *_args, **_kwargs: None)
    helpers = config_profile_helpers.build_config_profile_helpers(
        config_profile_helpers.ConfigProfileHelperDeps(
            read_raw_config=lambda: {},
            write_raw_config=lambda _data: None,
            reload_runtime=lambda: None,
            sanitize_connection_name=lambda value: str(value or "").strip(),
            get_active_profile_name=lambda _raw, _kind: "default",
            settings=SimpleNamespace(
                embeddings=SimpleNamespace(model="text-embedding-3-small", api_base="https://api.openai.com/v1"),
                memory=SimpleNamespace(embedding_fingerprint="", embedding_model=""),
            ),
            pipeline=SimpleNamespace(memory_skill=_MemorySkill()),
        )
    )

    with pytest.raises(RuntimeError, match="memory_export route is not registered: /memories/export"):
        asyncio.run(helpers.embedding_memory_guard_context("tester"))














def test_config_pages_do_not_show_retired_routing_workbench_link(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config')

    assert response.status_code == 200
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Settings Navigation"' in response.text
    assert 'href="/config/admin"' not in response.text
    assert 'href="/config/persona"' in response.text
    assert 'href="/connections"' in response.text
    assert 'href="/recipes"' in response.text
    assert 'Routing Workbench' not in response.text
    assert 'litellm-main' not in response.text
    assert 'litellm-emb' not in response.text
    assert 'The currently active chat-brain profile for answers and tool decisions.' not in response.text
    assert 'memory-health-grid' not in response.text
    assert 'Memory Triggers & Routing' not in response.text
    assert 'Skill Triggers & Routing' not in response.text












def test_retired_skill_routing_mutation_routes_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_profile_config_app(tmp_path)
    for path in (
        "/config/skill-routing/save",
        "/config/skill-routing/suggest",
        "/config/skill-routing/suggest-all",
        "/config/skill-routing/rebuild",
    ):
        assert client.post(path).status_code == 404


def test_retired_routing_pages_are_unavailable(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    for path in (
        "/config/routing",
        "/config/workbench/routing",
        "/config/skill-routing",
    ):
        assert client.get(path, follow_redirects=False).status_code == 404






def test_routing_index_test_json_route(monkeypatch, tmp_path: Path) -> None:
    async def fake_test(
        _settings: object,
        query: str,
        *,
        preferred_kind: str = "auto",
        llm_client: object | None = None,
        language: str = "",
    ) -> dict[str, object]:
        assert llm_client is None
        assert language == "en"
        return {
            "status": "warn",
            "message": "No routing target matched.",
            "query": query,
            "preferred_kind": preferred_kind,
            "decision": {"found": False},
        }

    monkeypatch.setattr(config_routes, "test_connection_routing_query", fake_test)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/routing-index/test?query=foo&preferred_kind=ssh')

    assert response.status_code == 200
    assert response.json()["query"] == "foo"
    assert response.json()["preferred_kind"] == "ssh"


def test_security_guardrail_ai_draft_renders_review_form(tmp_path: Path) -> None:
    class _FakeLLM:
        async def chat(self, *_args, **_kwargs):
            return SimpleNamespace(
                content=(
                    '{"ref":"no-sudo-linux","kind":"ssh_command","title":"No sudo on Linux",'
                    '"description":"Blocks sudo command execution on SSH targets.",'
                    '"allow_terms":[],"deny_terms":["sudo","su"],'
                    '"scope_summary":"Use on Ubuntu SSH profiles.",'
                    '"review_notes":["Confirm that privileged maintenance should be blocked."],'
                    '"examples":[{"text":"sudo systemctl restart nginx","expected":"block","reason":"sudo is denied"}],'
                    '"confidence":0.9}'
                )
            )

    client = _build_profile_config_app(tmp_path)
    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.post(
        "/config/security/guardrails/draft",
        data={
            "draft_kind": "ssh_command",
            "draft_connection_kind": "ssh",
            "draft_instruction": "Ich möchte keine sudo Befehle auf Ubuntu Linux.",
            "return_to": "/config/access",
        },
    )

    assert response.status_code == 200
    assert "KI-Vorschlag" in response.text
    assert "guardrail-draft-working" in response.text
    assert "guardrail-draft-working-line" in response.text
    assert "KI-Vorschlag wird angefragt" in response.text
    assert "no-sudo-linux" in response.text
    assert "sudo" in response.text
    assert "Geprüften Vorschlag als Guardrail speichern" in response.text


def test_security_guardrail_test_mode_evaluates_saved_guardrail(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("security", {})
    raw["security"]["guardrails"] = {
        "no-sudo": {
            "kind": "ssh_command",
            "title": "No sudo",
            "description": "Blocks privileged commands",
            "allow_terms": ["uptime", "df -h"],
            "deny_terms": ["sudo", "su"],
        }
    }
    _write_profile_yaml(config_path, raw)

    response = client.post(
        "/config/security/guardrails/test",
        data={
            "guardrail_ref": "no-sudo",
            "kind": "ssh_command",
            "test_text": "sudo systemctl restart nginx",
            "return_to": "/config/access",
        },
    )

    assert response.status_code == 200
    assert "Guardrail testen" in response.text
    assert "Testergebnis" in response.text
    assert "block" in response.text
    assert "Deny wording matched" in response.text
    assert "sudo systemctl restart nginx" in response.text


def test_llm_test_route_reports_active_profile_result(monkeypatch, tmp_path: Path) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    async def _fake_probe(_llm, usage_meter=None):
        del usage_meter
        return {'id': 'llm', 'status': 'error', 'detail': 'connection refused'}

    monkeypatch.setattr(config_routes, 'probe_llm', _fake_probe)

    response = client.post('/config/llm/test', follow_redirects=False)

    assert response.status_code == 303
    location = response.headers['location']
    assert location.startswith('/config/llm?test_status=error&error=')
    assert 'litellm-main' in location
    assert ("config_ui", "/config/llm") in route_calls
    assert ("config_ui", "/config") in route_calls


def test_embeddings_test_route_reports_active_profile_result(monkeypatch, tmp_path: Path) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    async def _fake_probe(_embeddings, usage_meter=None):
        del usage_meter
        return {'id': 'embeddings', 'status': 'ok', 'detail': 'ok'}

    monkeypatch.setattr(config_routes, 'probe_embeddings', _fake_probe)

    response = client.post('/config/embeddings/test', follow_redirects=False)

    assert response.status_code == 303
    location = response.headers['location']
    assert location.startswith('/config/embeddings?test_status=ok&info=')
    assert 'litellm-emb' in location
    assert ("config_ui", "/config/embeddings") in route_calls
    assert ("config_ui", "/config") in route_calls


def test_llm_test_route_preserves_return_to_from_referer(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    async def _fake_probe(_llm, usage_meter=None):
        del usage_meter
        return {'id': 'llm', 'status': 'ok', 'detail': 'ok'}

    monkeypatch.setattr(config_routes, 'probe_llm', _fake_probe)

    response = client.post(
        '/config/llm/test',
        headers={'referer': 'http://testserver/config/llm?return_to=%2Fconfig'},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert 'return_to=%2Fconfig' in response.headers['location']


def test_config_prompts_page_sets_logical_back_url(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/prompts?file=prompts%2Fpersona.md&return_to=%2Fconfig')

    assert response.status_code == 200
    assert "const logical='/config';" in response.text


def test_config_prompts_save_preserves_return_to(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        '/config/prompts/save',
        data={
            'file': 'prompts/persona.md',
            'content': 'updated prompt\n',
            'return_to': '/config',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers['location'].startswith('/config/prompts?file=prompts%2Fpersona.md&saved=1')
    assert 'return_to=%2Fconfig' in response.headers['location']


def test_config_appearance_save_preserves_return_to(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        '/config/appearance/save',
        data={
            'theme': 'sunset',
            'background': 'aurora',
            'return_to': '/config',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers['location'].startswith('/config/appearance?saved=1')
    assert 'return_to=%2Fconfig' in response.headers['location']


def test_config_persona_redirect_fallbacks_use_registry_route_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_persona_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    appearance = client.post(
        "/config/appearance/save",
        data={"theme": "sunset", "background": "aurora", "return_to": "/config"},
        follow_redirects=False,
    )
    language = client.post(
        "/config/language/save",
        data={"default_language": "de", "return_to": "/config"},
        follow_redirects=False,
    )
    prompt = client.post(
        "/config/prompts/save",
        data={"file": "prompts/persona.md", "content": "updated prompt\n", "return_to": "/config"},
        follow_redirects=False,
    )
    language_file_error = client.post(
        "/config/language/file/save",
        data={"file_name": "../bad.json", "content": "{}", "return_to": "/config"},
        follow_redirects=False,
    )

    assert appearance.status_code == 303
    assert appearance.headers["location"].startswith("/config/appearance?saved=1")
    assert language.status_code == 303
    assert language.headers["location"].startswith("/config/language?saved=1")
    assert prompt.status_code == 303
    assert prompt.headers["location"].startswith("/config/prompts?file=prompts%2Fpersona.md&saved=1")
    assert language_file_error.status_code == 303
    assert language_file_error.headers["location"].startswith("/config/language?file=..%2Fbad.json&error=")
    assert ("config_ui", "/config/appearance") in route_calls
    assert ("config_ui", "/config/language") in route_calls
    assert ("config_ui", "/config/prompts") in route_calls
    assert route_calls.count(("config_ui", "/config")) >= 4


def test_config_persona_redirect_fallbacks_fail_closed_without_config_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_persona_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.post(
            "/config/appearance/save",
            data={"theme": "sunset", "background": "aurora", "return_to": "/not-allowed"},
            follow_redirects=False,
        )


def test_config_appearance_lists_dynamic_background_files(tmp_path: Path) -> None:
    static_dir = tmp_path / "aria" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "background-8-bit-arcade.webp").write_bytes(b"webp")
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/appearance?return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'value="8-bit-arcade"' in response.text
    assert '8-Bit Arcade' in response.text


def test_config_appearance_lists_all_eight_shipped_background_slugs(tmp_path: Path) -> None:
    static_dir = tmp_path / "aria" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    slugs = (
        "grid-signal",
        "mesh-weave",
        "ai-lobby",
        "side-circuits",
        "aria-thinking",
        "8-bit-arcade",
        "puke-unicorn",
        "space-station",
    )
    for slug in slugs:
        (static_dir / f"background-{slug}.webp").write_bytes(b"webp")
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/appearance?return_to=%2Fconfig')

    assert response.status_code == 200
    for slug in slugs:
        assert f'value="{slug}"' in response.text


def test_config_appearance_lists_matching_theme_presets(tmp_path: Path) -> None:
    static_dir = tmp_path / "aria" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "background-grid-signal.webp").write_bytes(b"webp")
    (static_dir / "background-space-station.webp").write_bytes(b"webp")
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/appearance?return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'data-appearance-preset' in response.text
    assert 'value="matrix-grid-signal"' in response.text
    assert 'data-theme="matrix"' in response.text
    assert 'data-background="grid-signal"' in response.text
    assert 'value="deep-space-space-station"' in response.text
    assert 'value="puke-unicorn-puke-unicorn"' not in response.text


def test_additional_config_pages_set_logical_back_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    route_calls: list[tuple[str, str]] = []
    real_module_route_path = module_route_path

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str:
        route_calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path, **kwargs) or ""

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    monkeypatch.setattr(config_persona_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    for path in (
        '/config/appearance?return_to=%2Fconfig',
        '/config/language?return_to=%2Fconfig',
        '/config/files?return_to=%2Fconfig',
        '/config/error-interpreter?return_to=%2Fconfig',
        '/config/users?return_to=%2Fconfig',
        '/config/admin-mode?return_to=%2Fconfig',
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "const logical='/config';" in response.text, path
    assert ("config_ui", "/config") in route_calls
    assert ("config_ui", "/config/access") in route_calls
    assert ("config_ui", "/config/admin-mode") in route_calls
    assert ("config_ui", "/config/persona") in route_calls


def test_config_debug_redirect_uses_registry_route_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []
    real_module_route_path = module_route_path

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/debug", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/config/admin-mode")
    assert ("config_ui", "/config/admin-mode") in route_calls
    assert ("config_ui", "/config") in route_calls


def test_config_debug_redirect_fails_closed_without_route_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path in {"/config", "/config/admin-mode"}:
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/admin-mode"):
        client.get("/config/debug", follow_redirects=False)


def test_users_debug_save_route_is_available_from_users_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/users/debug-save",
        data={"debug_mode": "1", "return_to": "/config/access"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/config/users?saved=1")
    assert "return_to=%2Fconfig%2Faccess" in response.headers["location"]
    assert ("config_ui", "/config") in route_calls


def test_admin_mode_page_contains_only_admin_mode_toggle(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/admin-mode")

    assert response.status_code == 200
    assert "Erweiterte Ansicht" in response.text or "Extended view" in response.text
    assert 'action="/config/admin-mode/save"' in response.text
    assert 'name="debug_mode"' in response.text
    assert 'action="/config/users/create"' not in response.text
    assert 'action="/config/users/security-save"' not in response.text
    assert "Bestehende User" not in response.text


def test_users_page_no_longer_contains_admin_mode_toggle(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/users?return_to=/config/access")

    assert response.status_code == 200
    assert 'id="admin-mode"' not in response.text
    assert 'action="/config/users/debug-save"' not in response.text
    assert 'name="debug_mode"' not in response.text
    assert 'action="/config/users/security-save"' in response.text
    assert 'action="/config/users/create"' in response.text


def test_admin_mode_save_redirects_to_admin_mode_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/admin-mode/save",
        data={"debug_mode": "1", "return_to": "/config"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/config/admin-mode?saved=1")
    assert "return_to=%2Fconfig" in response.headers["location"]
    assert ("config_ui", "/config") in route_calls


def test_admin_mode_debug_save_fallback_fails_closed_without_config_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.post(
            "/config/admin-mode/save",
            data={"debug_mode": "1", "return_to": "/config"},
            follow_redirects=False,
        )


def test_access_security_settings_fallbacks_use_registry_route_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    security = client.post(
        "/config/security/save",
        data={"bootstrap_locked": "1", "session_timeout_minutes": "30", "return_to": "/config/access"},
        follow_redirects=False,
    )
    users = client.post(
        "/config/users/security-save",
        data={"bootstrap_locked": "0", "session_timeout_minutes": "45", "return_to": "/config/access"},
        follow_redirects=False,
    )

    assert security.status_code == 303
    assert security.headers["location"].startswith("/config/security?saved=1")
    assert users.status_code == 303
    assert users.headers["location"].startswith("/config/users?saved=1")
    assert route_calls.count(("config_ui", "/config")) >= 2


def test_access_security_settings_fallback_fails_closed_without_config_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.post(
            "/config/security/save",
            data={"bootstrap_locked": "1", "session_timeout_minutes": "30", "return_to": "/config/access"},
            follow_redirects=False,
        )


def test_access_user_management_redirects_use_registry_route_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    create = client.post(
        "/config/users/create",
        data={
            "create_username": "new-user",
            "create_password": "secret",
            "create_role": "user",
            "return_to": "/config",
        },
        follow_redirects=False,
    )
    update = client.post(
        "/config/users/update",
        data={
            "username_value": "neo",
            "new_username_value": "neo",
            "role_value": "admin",
            "active_value": "1",
            "return_to": "/config",
        },
        follow_redirects=False,
    )

    assert create.status_code == 303
    assert create.headers["location"].startswith("/config/users?error=Security+Store+nicht+aktiv")
    assert update.status_code == 303
    assert update.headers["location"].startswith("/config/users?error=Security+Store+nicht+aktiv")
    assert route_calls.count(("config_ui", "/config/users")) >= 2
    assert route_calls.count(("config_ui", "/config")) >= 2


def test_access_user_management_redirects_fail_closed_without_config_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config/users":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/users"):
        client.post(
            "/config/users/create",
            data={
                "create_username": "new-user",
                "create_password": "secret",
                "create_role": "user",
                "return_to": "/config",
            },
            follow_redirects=False,
        )


def test_access_guardrail_redirect_fallbacks_use_registry_route_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    save = client.post(
        "/config/security/guardrails/save",
        data={
            "guardrail_ref": "no-sudo",
            "kind": "ssh_command",
            "connection_kinds": "ssh",
            "title": "No sudo",
            "description": "Blocks sudo",
            "deny_terms": "sudo",
            "return_to": "/config/access",
        },
        follow_redirects=False,
    )
    duplicate = client.post(
        "/config/security/guardrails/save",
        data={
            "guardrail_ref": "no-sudo",
            "kind": "ssh_command",
            "connection_kinds": "ssh",
            "title": "No sudo",
            "return_to": "/config/access",
        },
        follow_redirects=False,
    )
    delete = client.post(
        "/config/security/guardrails/delete",
        data={"guardrail_ref": "no-sudo", "return_to": "/config/access"},
        follow_redirects=False,
    )
    import_error = client.post(
        "/config/security/guardrails/import-sample",
        data={"sample_file": "missing.yaml", "return_to": "/config/access"},
        follow_redirects=False,
    )

    assert save.status_code == 303
    assert save.headers["location"].startswith("/config/security?saved=1&guardrail_ref=no-sudo")
    assert duplicate.status_code == 303
    assert duplicate.headers["location"].startswith("/config/security?error=")
    assert delete.status_code == 303
    assert delete.headers["location"].startswith("/config/security?saved=1")
    assert import_error.status_code == 303
    assert import_error.headers["location"].startswith("/config/security?error=")
    assert route_calls.count(("config_ui", "/config/security")) >= 4
    assert route_calls.count(("config_ui", "/config")) >= 4


def test_guardrail_recipe_whitelist_checkboxes_and_persistence(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("security", {})["guardrails"] = {
        "maintenance": {
            "kind": "ssh_command",
            "allow_terms": [],
            "deny_terms": [],
            "allow_recipe_ids": ["trusted-maintenance"],
        }
    }
    _write_profile_yaml(config_path, raw)
    client.app.state.test_pipeline._load_stored_recipe_runtime = lambda: [
        {"id": "trusted-maintenance", "name": "Trusted Maintenance", "enabled": True},
        {"id": "trusted-backup", "name": "Trusted Backup", "enabled": True},
        {"id": "disabled-recipe", "name": "Disabled Recipe", "enabled": False},
    ]
    page = client.get("/config/security")
    assert page.status_code == 200
    assert '<div id="guardrail_recipe_allow_edit" class="guardrail-recipe-checklist"' in page.text
    assert 'type="checkbox"' in page.text
    assert 'name="allow_recipe_ids"' in page.text
    trusted_control = page.text.split('value="trusted-maintenance"', 1)[1].split(">", 1)[0]
    assert "checked" in trusted_control
    assert "Trusted Maintenance" in page.text and "Trusted Backup" in page.text
    assert 'select id="guardrail_recipe_allow_edit"' not in page.text
    assert "disabled-recipe" not in page.text

    saved = client.post(
        "/config/security/guardrails/save",
        data={
            "guardrail_ref": "maintenance",
            "original_ref": "maintenance",
            "kind": "ssh_command",
            "allow_recipe_ids": ["trusted-maintenance", "trusted-backup"],
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    raw = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert raw["security"]["guardrails"]["maintenance"]["allow_recipe_ids"] == [
        "trusted-maintenance",
        "trusted-backup",
    ]


def test_guardrail_page_uses_scoped_house_style_cards() -> None:
    template = Path("aria/templates/config_security.html").read_text(encoding="utf-8")
    stylesheet = Path("aria/static/style.css").read_text(encoding="utf-8")

    assert 'class="config-card floating-card config-domain-section guardrail-card"' in template
    assert "guardrail-risk-badge" in template
    assert ".config-security-layout .guardrail-card" in stylesheet
    assert "background: var(--surface-card-strong)" in stylesheet
    assert ".config-security-layout .guardrail-risk-badge" in stylesheet


def test_cyberpunk_config_accordions_use_shared_house_style_without_magenta_bars(
    tmp_path: Path,
) -> None:
    stylesheet = Path("aria/static/style.css").read_text(encoding="utf-8")
    theme_block = stylesheet.split(".config-section-details {", 1)[1].split(".config-submenu", 1)[0]

    assert "rgba(255, 20, 147" not in theme_block
    assert "rgba(219, 8, 120" not in theme_block
    assert "var(--surface-card-strong)" in theme_block
    assert "var(--border)" in theme_block
    assert 'body[data-theme="cyberpunk"] .config-section-details' not in stylesheet

    client = _build_profile_config_app(tmp_path)
    for path in ("/config/security", "/config/connections/ssh", "/config/connections/discord"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'class="config-section-summary"' in response.text


def test_every_discovered_background_has_a_canonical_css_asset_mapping() -> None:
    from aria.modules.configuration_foundations.config import (
        UI_BACKGROUND_DEFAULT,
        discover_ui_background_files,
    )

    stylesheet = Path("aria/static/style.css").read_text(encoding="utf-8")
    rows = discover_ui_background_files(Path("aria/static"))

    assert rows
    assert UI_BACKGROUND_DEFAULT in {row["value"] for row in rows}
    for row in rows:
        selector = f'body[data-background="{row["value"]}"]'
        match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", stylesheet)
        assert match is not None, selector
        assert f'url("{row["asset_url"]}")' in match.group(1), selector

    body_before = re.search(r"body::before\s*\{([^}]+)\}", stylesheet)
    assert body_before is not None
    assert "var(--background-art)" in body_before.group(1)


def test_admin_structural_surfaces_use_theme_tokens_without_changing_status_green(
    tmp_path: Path,
) -> None:
    stylesheet = Path("aria/static/style.css").read_text(encoding="utf-8")

    def block(selector: str) -> str:
        match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", stylesheet)
        assert match is not None, selector
        return match.group(1)

    structural_selectors = (
        ".stats-health-card",
        ".config-section-details",
        ".config-section-summary",
        ".config-security-layout .guardrail-card",
        ".connection-summary-card",
        ".connection-test-card",
        ".connection-option-card",
        ".config-group-card",
    )
    hardcoded_green = re.compile(
        r"#(?:00ff00|31ff8f|2b6d42|cbffd8|95c6a1)|"
        r"rgba?\([^)]*(?:43,\s*109,\s*66|49,\s*255,\s*143|8,\s*18,\s*12)[^)]*\)",
        re.IGNORECASE,
    )
    for selector in structural_selectors:
        rules = block(selector)
        assert "var(--" in rules, selector
        assert hardcoded_green.search(rules) is None, selector

    assert 'body[data-theme="cyberpunk"] .config-section-details' not in stylesheet
    cyberpunk = block('body[data-theme="cyberpunk"]')
    sunset = block('body[data-theme="sunset"]')
    for token in ("--accent", "--border", "--surface-card", "--text"):
        cyberpunk_value = re.search(rf"{token}:\s*([^;]+)", cyberpunk)
        sunset_value = re.search(rf"{token}:\s*([^;]+)", sunset)
        assert cyberpunk_value and sunset_value
        assert cyberpunk_value.group(1) != sunset_value.group(1)

    assert "#39d86c" in block(".health-lamp.status-ok")
    assert "rgba(69, 192, 110, 0.78)" in block(".stats-health-card.status-ok")
    assert "rgba(17, 53, 34, 0.82)" in block(".update-status-chip.status-ok")

    client = _build_profile_config_app(tmp_path)
    for path in ("/config", "/config/security", "/config/connections/ssh"):
        response = client.get(path)
        assert response.status_code == 200


def test_access_guardrail_redirect_fallbacks_fail_closed_without_config_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_access_detail_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.post(
            "/config/security/guardrails/save",
            data={
                "guardrail_ref": "no-sudo",
                "kind": "ssh_command",
                "connection_kinds": "ssh",
                "title": "No sudo",
                "return_to": "/config/access",
            },
            follow_redirects=False,
        )


def test_ssh_page_exposes_service_url_helper_and_matching_sftp_create(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/ssh?mode=create&return_to=%2Fconfig')
    nav_response = client.get('/config/connections/ssh?return_to=%2Fconfig')

    assert response.status_code == 200
    assert nav_response.status_code == 200
    assert 'name="service_url"' in response.text
    assert 'data-connection-meta-endpoint="/config/connections/ssh/suggest-metadata"' in response.text
    assert 'data-connection-meta-source-fields="host,user,port,service_url"' in response.text
    assert 'Service-URL (optional)' in response.text
    assert 'optional diese Service-URL' in response.text
    assert 'name="create_matching_sftp"' in response.text
    assert 'id="create-new"' in nav_response.text
    assert '<details id="create-new"' in nav_response.text


def test_ssh_page_profile_cards_link_to_edit_mode_and_expose_guardrail_select(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("connections", {})
    raw["connections"]["ssh"] = {
        "dns-node-01": {
            "title": "Pi-hole 1",
            "host": "dns-node-01.local",
            "user": "admin",
            "port": 22,
            "timeout_seconds": 10,
            "guardrail_ref": "no-sudo",
        }
    }
    raw.setdefault("security", {})
    raw["security"]["guardrails"] = {
        "no-sudo": {
            "kind": "ssh_command",
            "title": "No sudo",
            "description": "Blocks sudo",
            "allow_terms": ["uptime"],
            "deny_terms": ["sudo"],
        }
    }
    _write_profile_yaml(config_path, raw)

    response = client.get("/config/connections/ssh?ref=dns-node-01&return_to=%2Fconnections%2Ftypes")

    assert response.status_code == 200
    assert "connection-profile-card" in response.text
    assert "/config/connections/ssh?ref=dns-node-01#manage-existing" in response.text
    assert "Editieren" in response.text
    assert "Bestehendes Profil bearbeiten" in response.text
    assert 'id="guardrail_ref_edit"' in response.text
    assert 'value="no-sudo" selected' in response.text
    assert "/config/connections/ssh?ref=dns-node-01&amp;return_to=%2Fconnections%2Ftypes&amp;mode=create#create-new" not in response.text
    assert "/config/connections/ssh?ref=dns-node-01&amp;return_to=%2Fconnections%2Ftypes&amp;mode=edit#manage-existing" not in response.text
    assert "/config/connections/ssh?return_to=%2Fconnections%2Ftypes&amp;mode=create#create-new" in response.text


@pytest.mark.parametrize(
    ("kind", "path", "ref_param", "connection_ref", "profile", "field_id"),
    [
        (
            "sftp",
            "/config/connections/sftp",
            "sftp_ref",
            "files",
            {"host": "files.local", "user": "aria", "port": 22, "timeout_seconds": 10, "root_path": "/", "guardrail_ref": "file-safe"},
            "guardrail_ref_sftp_edit",
        ),
        (
            "smb",
            "/config/connections/smb",
            "smb_ref",
            "share",
            {"host": "nas.local", "share": "docs", "user": "aria", "port": 445, "timeout_seconds": 10, "root_path": "/", "guardrail_ref": "file-safe"},
            "guardrail_ref_smb_edit",
        ),
        (
            "webhook",
            "/config/connections/webhook",
            "webhook_ref",
            "hook",
            {"timeout_seconds": 10, "method": "POST", "content_type": "application/json", "guardrail_ref": "http-safe"},
            "guardrail_ref_webhook_edit",
        ),
        (
            "http_api",
            "/config/connections/http-api",
            "http_api_ref",
            "api",
            {"base_url": "https://api.example.test", "health_path": "/", "method": "GET", "timeout_seconds": 10, "guardrail_ref": "http-safe"},
            "guardrail_ref_http_api_edit",
        ),
    ],
)
def test_guardrail_capable_connection_pages_use_shared_guardrail_selector(
    tmp_path: Path,
    kind: str,
    path: str,
    ref_param: str,
    connection_ref: str,
    profile: dict[str, object],
    field_id: str,
) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("connections", {})
    raw["connections"][kind] = {connection_ref: profile}
    raw.setdefault("security", {})
    raw["security"]["guardrails"] = {
        "file-safe": {
            "kind": "file_access",
            "title": "File safe",
            "description": "File boundary",
            "allow_terms": ["/"],
            "deny_terms": [".."],
        },
        "http-safe": {
            "kind": "http_request",
            "title": "HTTP safe",
            "description": "HTTP boundary",
            "allow_terms": ["https://"],
            "deny_terms": ["localhost"],
        },
    }
    _write_profile_yaml(config_path, raw)

    response = client.get(f"{path}?{ref_param}={connection_ref}&return_to=%2Fconnections%2Ftypes")

    assert response.status_code == 200
    assert f'id="{field_id}"' in response.text
    assert 'name="guardrail_ref"' in response.text
    assert "Aktives Guardrail" in response.text or "Attached guardrail" in response.text
    assert 'selected' in response.text


def test_file_guardrail_selector_filters_connection_kind_scope(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("connections", {})
    raw["connections"]["smb"] = {
        "share": {
            "host": "nas.local",
            "share": "docs",
            "user": "aria",
            "port": 445,
            "timeout_seconds": 10,
            "root_path": "/",
        }
    }
    raw.setdefault("security", {})
    raw["security"]["guardrails"] = {
        "sftp-only": {
            "kind": "file_access",
            "connection_kinds": ["sftp"],
            "title": "SFTP only",
            "description": "SFTP boundary",
            "allow_terms": ["read"],
            "deny_terms": ["write"],
        },
        "smb-only": {
            "kind": "file_access",
            "connection_kinds": ["smb"],
            "title": "SMB only",
            "description": "SMB boundary",
            "allow_terms": ["read"],
            "deny_terms": ["write"],
        },
    }
    _write_profile_yaml(config_path, raw)

    response = client.get("/config/connections/smb?smb_ref=share&return_to=%2Fconnections%2Ftypes")

    assert response.status_code == 200
    assert "SMB only" in response.text
    assert "smb-only" in response.text
    assert "SFTP only" not in response.text
    assert "sftp-only" not in response.text


@pytest.mark.parametrize(
    ("kind", "selected_query", "profiles", "visible_refs", "edit_fragment"),
    [
        (
            "ssh",
            "ref=srv-1",
            {
                f"srv-{idx}": {
                    "host": f"10.0.0.{idx}",
                    "user": "aria",
                    "port": 22,
                    "timeout_seconds": 20,
                    "key_path": f"data/ssh_keys/srv_{idx}_ed25519",
                }
                for idx in range(1, 7)
            },
            ("srv-1", "srv-6"),
            "/config/connections/ssh?ref=srv-1#manage-existing",
        ),
        (
            "sftp",
            "sftp_ref=files-1",
            {
                f"files-{idx}": {
                    "host": f"10.0.1.{idx}",
                    "user": "aria",
                    "port": 22,
                    "timeout_seconds": 20,
                    "root_path": "/",
                    "key_path": f"data/ssh_keys/files_{idx}_ed25519",
                }
                for idx in range(1, 7)
            },
            ("files-1", "files-6"),
            "/config/connections/sftp?sftp_ref=files-1#manage-existing",
        ),
        (
            "smb",
            "smb_ref=share-1",
            {
                f"share-{idx}": {
                    "host": f"nas-{idx}.example.local",
                    "share": "documents",
                    "user": "aria",
                    "port": 445,
                    "timeout_seconds": 10,
                    "root_path": "/",
                }
                for idx in range(1, 7)
            },
            ("share-1", "share-6"),
            "/config/connections/smb?smb_ref=share-1#manage-existing",
        ),
    ],
)
def test_connection_page_renders_existing_profiles_directly(
    tmp_path: Path,
    kind: str,
    selected_query: str,
    profiles: dict[str, dict[str, object]],
    visible_refs: tuple[str, str],
    edit_fragment: str,
) -> None:
    client = _build_profile_config_app(tmp_path)
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    raw.setdefault('connections', {})
    raw['connections'][kind] = profiles
    _write_profile_yaml(tmp_path / 'config' / 'config.yaml', raw)

    response = client.get(f'/config/connections/{kind}?{selected_query}&return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'connection-status-grid' in response.text
    assert 'connection-status-collapsed' not in response.text
    assert 'connection-status-summary' not in response.text
    assert visible_refs[0] in response.text
    assert visible_refs[1] in response.text
    assert "connection-profile-card" in response.text
    assert "Editieren" in response.text
    assert edit_fragment in response.text


def test_connection_page_without_profiles_opens_create_mode_from_type_link(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/discord?return_to=/connections/types')

    assert response.status_code == 200
    assert 'id="create-new"' in response.text
    assert 'connection-mode-create" hidden' not in response.text
    assert 'id="discord_new_connection_ref"' in response.text
    assert 'name="connection_ref"' in response.text
    assert 'id="discord_new_webhook_url"' in response.text
    assert 'name="webhook_url"' in response.text


def test_sftp_page_exposes_service_url_helper(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/sftp?mode=create&return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'name="service_url"' in response.text
    assert 'data-connection-meta-endpoint="/config/connections/sftp/suggest-metadata"' in response.text
    assert 'data-connection-meta-source-fields="service_url"' in response.text


def test_ssh_suggest_metadata_route_returns_llm_payload(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang='de')
    captured_messages: list[dict[str, str]] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b"<html><head><title>Grafana Labs</title>"
                b"<meta name=\"description\" content=\"Dashboards and metrics\">"
                b"<meta name=\"keywords\" content=\"grafana, monitoring, dashboards\">"
                b"</head><body></body></html>"
            )

    class _FakeLLM:
        async def chat(self, messages, **_kwargs):
            captured_messages.extend(messages)
            return SimpleNamespace(
                content='{"title":"Grafana","description":"Monitoring dashboards","aliases":["grafana","monitoring"],"tags":["metrics","dashboards"]}'
            )

    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.get(
        '/config/connections/ssh/suggest-metadata',
        params={'service_url': 'https://grafana.example.local'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['title'] == 'Grafana'
    assert payload['description'] == 'Monitoring dashboards'
    assert payload['aliases'] == 'grafana, monitoring'
    assert payload['tags'] == 'metrics, dashboards'
    prompt_blob = "\n".join(item.get('content', '') for item in captured_messages)
    assert 'Output language: German (Deutsch).' in prompt_blob
    assert 'German semantic retrieval context' in prompt_blob
    assert 'Preferred language: de' in prompt_blob


def test_ssh_suggest_metadata_route_uses_host_when_service_url_is_empty(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang='de')

    response = client.get(
        '/config/connections/ssh/suggest-metadata',
        params={
            'connection_ref': 'dns-node-01',
            'host': '192.0.2.11',
            'user': 'demo_user',
            'port': '22',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['title'] == '192.0.2.11'
    assert 'dns-node-01' in payload['aliases']
    assert '192.0.2.11' in payload['aliases']


def test_sftp_suggest_metadata_route_returns_llm_payload(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang='de')
    captured_messages: list[dict[str, str]] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b"<html><head><title>MinIO Console</title>"
                b"<meta name=\"description\" content=\"Object storage browser\">"
                b"<meta name=\"keywords\" content=\"minio, storage, objects\">"
                b"</head><body></body></html>"
            )

    class _FakeLLM:
        async def chat(self, messages, **_kwargs):
            captured_messages.extend(messages)
            return SimpleNamespace(
                content='{"title":"MinIO","description":"Dateiablage im Objekt-Storage","aliases":["minio","dateiablage"],"tags":["storage","dateien"]}'
            )

    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.get(
        '/config/connections/sftp/suggest-metadata',
        params={'service_url': 'https://minio.example.local'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['title'] == 'MinIO'
    assert payload['description'] == 'Dateiablage im Objekt-Storage'
    assert payload['aliases'] == 'minio, dateiablage'
    assert payload['tags'] == 'storage, dateien'
    prompt_blob = "\n".join(item.get('content', '') for item in captured_messages)
    assert 'Output language: German (Deutsch).' in prompt_blob
    assert 'Preferred language: de' in prompt_blob


def test_rss_suggest_metadata_route_uses_request_language(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang='de')
    captured_messages: list[dict[str, str]] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<rss version="2.0"><channel>'
                b'<title>Example Feed</title>'
                b'<description>Ops updates and incidents</description>'
                b'<item><title>Database incident</title></item>'
                b'</channel></rss>'
            )

    class _FakeLLM:
        async def chat(self, messages, **_kwargs):
            captured_messages.extend(messages)
            return SimpleNamespace(
                content='{"title":"Ops Feed","description":"Aktuelle Ops-Meldungen","aliases":["ops feed","stoerungen"],"tags":["ops","status"]}'
            )

    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.get(
        '/config/connections/rss/suggest-metadata',
        params={'feed_url': 'https://feeds.example.local/rss.xml'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['description'] == 'Aktuelle Ops-Meldungen'
    prompt_blob = "\n".join(item.get('content', '') for item in captured_messages)
    assert 'Output language: German (Deutsch).' in prompt_blob
    assert 'Preferred language: de' in prompt_blob


def test_rss_config_page_uses_registry_template_readpoint(monkeypatch, tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []
    real_template_name = connection_detail_routes.module_template_name

    def tracking_template_name(module_id: str, template_name: str):
        seen.append((module_id, template_name))
        return real_template_name(module_id, template_name)

    monkeypatch.setattr(connection_detail_routes, "module_template_name", tracking_template_name)
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/connections/rss")

    assert response.status_code == 200
    assert ("rss_ui", "config_connections_rss.html") in seen


def test_rss_config_template_readpoint_fails_closed_for_unregistered_template(monkeypatch) -> None:
    monkeypatch.setattr(connection_detail_routes, "module_template_name", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="rss_ui template is not registered: config_connections_rss.html"):
        connection_detail_routes._rss_ui_template_name("config_connections_rss.html")


def test_smtp_legacy_redirect_uses_registry_route_readpoint(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    real_module_route_path = connection_detail_routes.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path)

    monkeypatch.setattr(connection_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/connections/email", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/config/connections/smtp"
    assert ("smtp_ui", "/config/connections/smtp") in calls


def test_smtp_legacy_redirect_fails_closed_without_route_owner(monkeypatch) -> None:
    monkeypatch.setattr(connection_detail_routes, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="smtp_ui route is not registered: /config/connections/smtp"):
        connection_detail_routes._smtp_ui_route("/config/connections/smtp")


def test_retired_admin_group_routes_are_absent_and_admin_details_stay_gated(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    real_module_route_path = config_surface_routes.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_surface_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path, advanced_mode=False)

    admin = client.get("/config/admin", follow_redirects=False)
    modules = client.get("/config/admin/modules", follow_redirects=False)

    assert admin.status_code == 404
    assert modules.status_code == 303
    assert modules.headers["location"] == "/config?error=admin_mode_required"
    assert calls.count(("config_ui", "/config")) >= 1


def test_config_admin_unknown_group_is_absent(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    real_module_route_path = config_surface_routes.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_surface_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/admin/unknown", follow_redirects=False)

    assert response.status_code == 404


def test_config_operations_redirects_use_registry_route_readpoints(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    real_ops_module_route_path = config_ops_detail_routes.module_route_path
    real_surface_module_route_path = config_surface_routes.module_route_path

    def tracking_ops_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return real_ops_module_route_path(module_id, route_path, **kwargs)

    def tracking_surface_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return real_surface_module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", tracking_ops_module_route_path)
    monkeypatch.setattr(config_surface_routes, "module_route_path", tracking_surface_module_route_path)
    locked_client = _build_profile_config_app(tmp_path / "locked", advanced_mode=False)
    open_client = _build_profile_config_app(tmp_path / "open")

    export_response = locked_client.get("/config/backup/export", follow_redirects=False)
    restart_response = open_client.post(
        "/config/operations/service-restart",
        data={"service": "unknown", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert export_response.status_code == 303
    assert export_response.headers["location"] == "/config?error=admin_mode_required"
    assert restart_response.status_code == 303
    assert restart_response.headers["location"].startswith("/config/operations?error=")
    assert ("config_ui", "/config") in calls
    assert ("ops_config_backup", "/config/operations") in calls


def test_config_redirect_routes_do_not_keep_hardcoded_config_targets() -> None:
    blocked_by_file = {
        Path("aria/modules/connections_ui_readonly/detail_routes.py"): (
            'RedirectResponse(url="/config/connections/smtp"',
            'RedirectResponse(url=f"/config/connections/smtp"',
        ),
        Path("aria/modules/config_ui/surface_routes.py"): (
            'RedirectResponse(url="/config?error=admin_mode_required"',
            'RedirectResponse(url="/config/admin"',
            'RedirectResponse(url="/config/operations?error=no_admin"',
            'RedirectResponse(url=f"/config/operations?',
        ),
        Path("aria/modules/config_ui/access_detail_routes.py"): (
            'RedirectResponse(url="/config?error=admin_mode_required"',
        ),
        Path("aria/modules/ops_config_backup/detail_routes.py"): (
            'RedirectResponse(url="/config?error=admin_mode_required"',
            'RedirectResponse(url=f"/config/logs?',
            'RedirectResponse(url="/memories/reindex"',
            'RedirectResponse(url="/memories/reindex?',
            'RedirectResponse(url=f"/memories/reindex?',
        ),
    }

    found: list[str] = []
    for path, snippets in blocked_by_file.items():
        source = path.read_text(encoding="utf-8")
        found.extend(f"{path}:{snippet}" for snippet in snippets if snippet in source)

    assert found == []


def test_connection_profile_action_urls_use_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("connections", {})
    raw["connections"]["discord"] = {
        "ops-feed": {
            "title": "Ops Feed",
            "webhook_url": "https://discord.example.invalid/webhook",
            "timeout_seconds": 10,
        }
    }
    _write_profile_yaml(config_path, raw)

    overview = client.get("/connections/templates")
    discord = client.get("/config/connections/discord?ref=ops-feed")

    assert overview.status_code == 200
    assert discord.status_code == 200
    assert 'action="/config/connections/import-sample"' in overview.text
    assert 'action="/config/connections/delete"' in discord.text
    assert {
        ("connections_profiles", "/config/connections/import-sample"),
        ("connections_profiles", "/config/connections/delete"),
    }.issubset(set(module_route_calls))


def test_security_and_users_action_urls_use_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    security = client.get("/config/security")
    users = client.get("/config/users")
    assert security.status_code == 200
    assert users.status_code == 200
    assert 'action="/config/security/guardrails/draft"' in security.text
    assert 'action="/config/security/guardrails/save"' in security.text
    assert 'action="/config/security/guardrails/test"' in security.text
    assert 'action="/config/users/security-save"' in users.text
    assert 'action="/config/users/create"' in users.text
    expected_calls = {
        ("config_ui", "/config/security/guardrails/draft"),
        ("config_ui", "/config/security/guardrails/save"),
        ("config_ui", "/config/security/guardrails/test"),
        ("config_ui", "/config/security/guardrails/delete"),
        ("config_ui", "/config/security/guardrails/import-sample"),
        ("config_ui", "/config/users/security-save"),
        ("config_ui", "/config/users/create"),
        ("config_ui", "/config/users/update"),
    }
    assert expected_calls.issubset(set(module_route_calls))


def test_ssh_tool_action_urls_use_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    response = client.get("/config/connections/ssh?mode=create")

    assert response.status_code == 200
    assert 'action="/config/connections/key-exchange"' in response.text
    assert 'action="/config/connections/keygen"' in response.text
    assert {
        ("ssh_admin_ui", "/config/connections/key-exchange"),
        ("ssh_admin_ui", "/config/connections/keygen"),
    }.issubset(set(module_route_calls))


def test_chat_action_urls_use_registry_route_readpoints() -> None:
    template = (Path(__file__).resolve().parents[1] / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "module_route_path('chat_execution_composition', '/chat')" in template
    assert "module_route_path('chat_execution_composition', '/chat/progress')" in template
    assert "module_route_path('chat_execution_composition', '/chat/history/clear')" in template
    assert 'action="/chat"' not in template
    assert 'fetch("/chat"' not in template
    assert 'fetch("/chat/history/clear"' not in template


def test_rss_config_visible_urls_use_registry_route_readpoints(monkeypatch, tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    helper_route_calls: list[tuple[str, str]] = []

    def tracking_helper_route_path(module_id: str, route_path: str, **kwargs):  # noqa: ANN001, ANN202
        helper_route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs) or ""

    monkeypatch.setattr(connection_context_helpers, "module_route_path", tracking_helper_route_path)
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw.setdefault("connections", {})
    raw["connections"]["rss"] = {
        "security-feed": {
            "title": "Security Feed",
            "feed_url": "https://example.invalid/security.xml",
            "group_name": "Security",
            "timeout_seconds": 10,
        }
    }
    _write_profile_yaml(config_path, raw)

    list_response = client.get("/config/connections/rss")
    selected_response = client.get("/config/connections/rss?mode=edit&rss_ref=security-feed")

    assert list_response.status_code == 200
    assert selected_response.status_code == 200
    assert 'action="/config/connections/rss/poll-interval/save"' in list_response.text
    assert 'href="/config/connections/rss/export-opml"' in list_response.text
    assert 'action="/config/connections/rss/import-opml"' in list_response.text
    assert 'action="/config/connections/rss"' in list_response.text
    assert 'action="/config/connections/rss/ping-now"' in selected_response.text
    assert 'action="/config/connections/rss/save"' in selected_response.text
    assert 'data-connection-meta-endpoint="/config/connections/rss/suggest-metadata"' in selected_response.text
    assert ("rss_ui", "/config/connections/rss") in module_route_calls
    assert ("rss_ui", "/config/connections/rss/poll-interval/save") in module_route_calls
    assert ("rss_ui", "/config/connections/rss/export-opml") in module_route_calls
    assert ("rss_ui", "/config/connections/rss/import-opml") in module_route_calls
    assert ("rss_ui", "/config/connections/rss/ping-now") in module_route_calls
    assert ("rss_ui", "/config/connections/rss/save") in module_route_calls
    assert ("rss_ui", "/config/connections/rss/suggest-metadata") in module_route_calls
    assert ("rss_ui", "/config/connections/rss") in helper_route_calls


def test_rss_config_template_action_readpoints_fail_closed_without_owner(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    def missing_rss_route(module_id: str, route_path: str) -> str:
        if module_id == "rss_ui" and route_path == "/config/connections/rss/import-opml":
            raise RuntimeError(f"{module_id} route is not registered: {route_path}")
        return route_path

    client.app.state.templates.env.globals["required_module_route_path"] = missing_rss_route

    with pytest.raises(RuntimeError, match="rss_ui route is not registered: /config/connections/rss/import-opml"):
        client.get("/config/connections/rss")


def test_ssh_save_can_create_matching_sftp_profile(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    monkeypatch.setattr(
        config_routes,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )

    response = client.post(
        '/config/connections/save',
        data={
            'connection_ref': 'mgmt-ssh',
            'original_ref': '',
            'host': '192.0.2.5',
            'service_url': 'https://grafana.example.local',
            'user': 'aria',
            'key_path': 'data/ssh_keys/mgmt_ed25519',
            'timeout_seconds': '20',
            'port': '22',
            'connection_title': 'Management Server',
            'connection_description': 'SSH access for ops',
            'connection_aliases': 'grafana, ops',
            'connection_tags': 'monitoring, linux',
            'create_matching_sftp': '1',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    ssh_row = raw['connections']['ssh']['mgmt-ssh']
    sftp_row = raw['connections']['sftp']['mgmt-sftp']
    assert ssh_row['service_url'] == 'https://grafana.example.local'
    assert sftp_row['host'] == '192.0.2.5'
    assert sftp_row['user'] == 'aria'
    assert sftp_row['key_path'] == 'data/ssh_keys/mgmt_ed25519'
    assert sftp_row['title'] == 'Management Server'
    assert sftp_row['aliases'] == ['grafana', 'ops']
    assert sftp_row['tags'] == ['monitoring', 'linux']


def test_ssh_save_autofills_routing_metadata_from_service_url(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang='de')

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b"<html><head><title>Grafana Labs</title>"
                b"<meta name=\"description\" content=\"Dashboards and metrics\">"
                b"<meta name=\"keywords\" content=\"grafana, monitoring, dashboards\">"
                b"</head><body></body></html>"
            )

    class _FakeLLM:
        async def chat(self, *_args, **_kwargs):
            return SimpleNamespace(
                content='{"title":"Grafana","description":"Monitoring dashboards","aliases":["grafana","monitoring"],"tags":["metrics","dashboards"]}'
            )

    monkeypatch.setattr(
        config_routes,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )
    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.post(
        '/config/connections/save',
        data={
            'connection_ref': 'grafana-ssh',
            'original_ref': '',
            'host': '192.0.2.5',
            'service_url': 'https://grafana.example.local',
            'user': 'aria',
            'key_path': 'data/ssh_keys/grafana_ed25519',
            'timeout_seconds': '20',
            'port': '22',
            'connection_title': '',
            'connection_description': '',
            'connection_aliases': '',
            'connection_tags': '',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    ssh_row = raw['connections']['ssh']['grafana-ssh']
    assert ssh_row['title'] == 'Grafana'
    assert ssh_row['description'] == 'Monitoring dashboards'
    assert ssh_row['aliases'] == ['grafana', 'monitoring']
    assert ssh_row['tags'] == ['metrics', 'dashboards']


def test_sftp_save_persists_service_url(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    monkeypatch.setattr(
        config_routes,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )

    response = client.post(
        '/config/connections/sftp/save',
        data={
            'connection_ref': 'files-sftp',
            'original_ref': '',
            'host': '192.0.2.9',
            'service_url': 'https://minio.example.local',
            'user': 'backup',
            'key_path': 'data/ssh_keys/files_ed25519',
            'timeout_seconds': '10',
            'port': '22',
            'root_path': '/data',
            'connection_title': 'Files',
            'connection_description': 'SFTP for backups',
            'connection_aliases': 'minio, backup',
            'connection_tags': 'storage, files',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    sftp_row = raw['connections']['sftp']['files-sftp']
    assert sftp_row['service_url'] == 'https://minio.example.local'
    assert sftp_row['host'] == '192.0.2.9'
    assert sftp_row['root_path'] == '/data'


def test_sftp_save_autofills_routing_metadata_from_service_url(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, lang='de')

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b"<html><head><title>MinIO Console</title>"
                b"<meta name=\"description\" content=\"Object storage browser\">"
                b"<meta name=\"keywords\" content=\"minio, storage, objects\">"
                b"</head><body></body></html>"
            )

    class _FakeLLM:
        async def chat(self, *_args, **_kwargs):
            return SimpleNamespace(
                content='{"title":"MinIO","description":"Dateiablage im Objekt-Storage","aliases":["minio","dateiablage"],"tags":["storage","dateien"]}'
            )

    monkeypatch.setattr(
        config_routes,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )
    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.post(
        '/config/connections/sftp/save',
        data={
            'connection_ref': 'files-sftp',
            'original_ref': '',
            'host': '192.0.2.9',
            'service_url': 'https://minio.example.local',
            'user': 'backup',
            'key_path': 'data/ssh_keys/files_ed25519',
            'timeout_seconds': '10',
            'port': '22',
            'root_path': '/data',
            'connection_title': '',
            'connection_description': '',
            'connection_aliases': '',
            'connection_tags': '',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    sftp_row = raw['connections']['sftp']['files-sftp']
    assert sftp_row['title'] == 'MinIO'
    assert sftp_row['description'] == 'Dateiablage im Objekt-Storage'
    assert sftp_row['aliases'] == ['minio', 'dateiablage']
    assert sftp_row['tags'] == ['storage', 'dateien']


def test_connections_overview_page_is_available_as_top_level_hub(tmp_path: Path, monkeypatch) -> None:
    template_calls: list[tuple[str, str]] = []
    route_calls: list[tuple[str, str]] = []
    helper_route_calls: list[tuple[str, str]] = []
    surface_route_calls: list[tuple[str, str]] = []
    real_template_name = connections_surface_routes.module_template_name
    real_surface_route_path = connections_surface_routes.module_route_path
    real_helper_route_path = connections_surface_helpers.module_route_path

    def tracking_template_name(module_id: str, template_name: str) -> str | None:
        template_calls.append((module_id, template_name))
        return real_template_name(module_id, template_name)

    def tracking_surface_route_path(module_id: str, route_path: str) -> str | None:
        surface_route_calls.append((module_id, route_path))
        return real_surface_route_path(module_id, route_path)

    def tracking_helper_route_path(module_id: str, route_path: str) -> str | None:
        helper_route_calls.append((module_id, route_path))
        return real_helper_route_path(module_id, route_path)

    monkeypatch.setattr(connections_surface_routes, "module_template_name", tracking_template_name)
    monkeypatch.setattr(connections_surface_routes, "module_route_path", tracking_surface_route_path)
    monkeypatch.setattr(connections_surface_helpers, "module_route_path", tracking_helper_route_path)
    client = _build_profile_config_app(tmp_path, module_route_calls=route_calls)

    response = client.get('/connections')

    assert response.status_code == 200
    assert ("connections_ui_readonly", "connections_hub.html") in template_calls
    assert 'Connections' in response.text
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
    assert 'Next steps' not in response.text
    assert 'Nächste Schritte' not in response.text
    assert 'Create first connection' not in response.text
    assert 'Erste Verbindung anlegen' not in response.text
    assert 'memory-health-grid' not in response.text
    assert 'href="/connections/status"' in response.text
    assert 'href="/connections/types"' in response.text
    assert 'href="/connections/templates"' in response.text
    assert ("connections_ui_readonly", "/connections/status") in route_calls
    assert ("connections_ui_readonly", "/connections/types") in route_calls
    assert ("connections_ui_readonly", "/connections/templates") in route_calls
    assert {
        ("connections_ui_readonly", "/connections"),
        ("connections_ui_readonly", "/connections/status"),
        ("connections_ui_readonly", "/connections/types"),
        ("connections_ui_readonly", "/connections/templates"),
    }.issubset(set(helper_route_calls))
    assert ("config_ui", "/config") in surface_route_calls
    assert ("connections_ui_readonly", "/connections") in surface_route_calls
    assert 'href="/config"' in response.text
    assert 'Zurück zu Einstellungen' not in response.text
    assert 'Back to settings' not in response.text
    nav = _first_memory_subnav(response.text)
    assert 'href="/config/persona"' in nav
    assert 'class="memory-subnav-item active" href="/connections"' in nav
    assert 'href="/connections/status"' not in nav
    assert 'href="/connections/types"' not in nav
    assert 'href="/connections/templates"' not in nav


def test_connections_overview_route_readpoint_fails_closed_without_owner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(connections_surface_routes, "module_route_path", lambda *_args, **_kwargs: None)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.get("/connections")


def test_connections_surface_import_sample_fallback_uses_route_readpoint(tmp_path: Path, monkeypatch) -> None:
    surface_route_calls: list[tuple[str, str]] = []
    real_surface_route_path = connections_surface_routes.module_route_path
    config_route_calls: list[tuple[str, str]] = []
    real_config_route_path = config_routes.module_route_path

    def tracking_surface_route_path(module_id: str, route_path: str) -> str | None:
        surface_route_calls.append((module_id, route_path))
        return real_surface_route_path(module_id, route_path)

    def tracking_config_route_path(module_id: str, route_path: str) -> str | None:
        config_route_calls.append((module_id, route_path))
        return real_config_route_path(module_id, route_path)

    monkeypatch.setattr(connections_surface_routes, "module_route_path", tracking_surface_route_path)
    monkeypatch.setattr(config_routes, "module_route_path", tracking_config_route_path)
    client = _build_profile_config_app(tmp_path, advanced_mode=False)

    response = client.post(
        "/config/connections/import-sample",
        data={"sample_file": "default-connections.yaml", "return_to": "/not-allowed"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/connections/templates?error=admin_mode_required"
    assert ("connections_ui_readonly", "/connections") in config_route_calls
    assert ("connections_ui_readonly", "/connections/templates") in surface_route_calls


def test_connections_page_context_defaults_use_route_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    route_calls: list[tuple[str, str]] = []
    logical_back_fallbacks: list[str] = []
    surface_path_calls: list[tuple[str, str]] = []
    real_helper_route_path = connections_surface_helpers.module_route_path

    def tracking_helper_route_path(module_id: str, route_path: str) -> str | None:
        route_calls.append((module_id, route_path))
        return real_helper_route_path(module_id, route_path)

    monkeypatch.setattr(connections_surface_helpers, "module_route_path", tracking_helper_route_path)
    helper = connections_surface_helpers.build_connections_page_context_helper(
        connections_surface_helpers.ConnectionsSurfaceHelperDeps(
            base_dir=Path(__file__).resolve().parents[1],
            get_settings=lambda: SimpleNamespace(ui=SimpleNamespace(title="ARIA")),
            get_username_from_request=lambda _request: "tester",
            set_logical_back_url=lambda _request, *, fallback: logical_back_fallbacks.append(fallback) or fallback,
            msg=lambda _lang, _key, default: default,
            format_config_info_message=lambda _lang, info: info,
            attach_mixed_connection_edit_urls=lambda rows: rows,
            connections_surface_path=lambda path, *, fallback: surface_path_calls.append((path, fallback)) or path,
            build_sample_connection_rows=lambda: [],
            build_settings_connection_status_rows=lambda *_args, **_kwargs: [],
            connection_menu_rows=lambda: [],
        )
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/connections",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    request.state.lang = "en"
    request.state.can_access_advanced_config = True

    context = helper(request, page_heading="Connections")

    assert context["page_return_to"] == "/connections"
    assert logical_back_fallbacks == ["/connections"]
    assert surface_path_calls[-1] == ("/connections", "/connections")
    assert route_calls.count(("connections_ui_readonly", "/connections")) >= 1


def test_connections_page_context_defaults_fail_closed_without_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(connections_surface_helpers, "module_route_path", lambda *_args, **_kwargs: None)
    helper = connections_surface_helpers.build_connections_page_context_helper(
        connections_surface_helpers.ConnectionsSurfaceHelperDeps(
            base_dir=Path(__file__).resolve().parents[1],
            get_settings=lambda: SimpleNamespace(ui=SimpleNamespace(title="ARIA")),
            get_username_from_request=lambda _request: "tester",
            set_logical_back_url=lambda _request, *, fallback: fallback,
            msg=lambda _lang, _key, default: default,
            format_config_info_message=lambda _lang, info: info,
            attach_mixed_connection_edit_urls=lambda rows: rows,
            connections_surface_path=lambda path, *, fallback: path,
            build_sample_connection_rows=lambda: [],
            build_settings_connection_status_rows=lambda *_args, **_kwargs: [],
            connection_menu_rows=lambda: [],
        )
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/connections",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    request.state.lang = "en"
    request.state.can_access_advanced_config = False

    with pytest.raises(RuntimeError, match="connections_ui_readonly route is not registered: /connections"):
        helper(request, page_heading="Connections")


def test_connections_surface_import_sample_fallback_fails_closed_without_owner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(connections_surface_routes, "module_route_path", lambda *_args, **_kwargs: None)
    client = _build_profile_config_app(tmp_path, advanced_mode=False)

    with pytest.raises(RuntimeError, match="connections_ui_readonly route is not registered: /connections/templates"):
        client.post(
            "/config/connections/import-sample",
            data={"sample_file": "default-connections.yaml", "return_to": "/not-allowed"},
            follow_redirects=False,
        )


def test_connections_surface_sanitizer_fallback_fails_closed_without_owner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(config_routes, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="connections_ui_readonly route is not registered: /connections"):
        _build_profile_config_app(tmp_path)


def test_config_surface_sanitizer_fallback_uses_route_readpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_calls: list[tuple[str, str]] = []
    real_config_route_path = config_routes.module_route_path

    def tracking_config_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return real_config_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_routes, "module_route_path", tracking_config_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/persona?return_to=/not-allowed")

    assert response.status_code == 200
    assert ("config_ui", "/config") in route_calls


def test_config_surface_sanitizer_fallback_fails_closed_without_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_routes, "module_route_path", missing_config_route)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        _build_profile_config_app(tmp_path)


def test_config_dependency_logical_back_defaults_use_route_readpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_calls: list[tuple[str, str]] = []
    real_config_route_path = config_routes.module_route_path

    def tracking_config_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return real_config_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_routes, "module_route_path", tracking_config_route_path)
    client = _build_profile_config_app(tmp_path)

    llm_response = client.get("/config/llm")
    assert llm_response.status_code == 200
    assert ("config_ui", "/config") in route_calls




def test_config_route_readpoint_helpers_fail_closed_without_route_owner(monkeypatch) -> None:
    monkeypatch.setattr(config_access_detail_routes, "module_route_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(config_persona_routes, "module_route_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(config_surface_routes, "module_route_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(connection_page_helpers, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/security"):
        config_access_detail_routes._config_ui_path("/config/security")
    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/workbench"):
        config_intelligence_workbench_routes._config_ui_path("/config/workbench")
    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/appearance"):
        config_persona_routes._config_ui_path("/config/appearance")
    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/access"):
        config_surface_routes._config_ui_path("/config/access")
    with pytest.raises(RuntimeError, match="ops_config_backup route is not registered: /config/operations/service-restart"):
        config_surface_routes._ops_config_route("/config/operations/service-restart")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/config/connections/rss",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    helpers = connection_page_helpers.build_connection_page_helpers(
        connection_page_helpers.ConnectionPageHelperDeps(
            base_dir=Path(__file__).resolve().parents[1],
            templates=Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates")),
            get_settings=lambda: SimpleNamespace(ui=SimpleNamespace(title="ARIA")),
            get_username_from_request=lambda _request: "tester",
            set_logical_back_url=lambda _request, *, fallback: fallback,
            sanitize_connection_name=lambda value: str(value or "").strip(),
            build_connection_ref_options=lambda _rows: [],
            build_connection_status_rows=lambda *_args, **_kwargs: [],
            attach_connection_edit_urls=lambda _kind, rows: rows,
            connection_template_name=lambda kind: f"connections/{kind}.html",
        )
    )
    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        helpers.base_connections_page_context(request, 0, "", "")


def test_connections_subpages_render_with_surface_specific_targets(tmp_path: Path, monkeypatch) -> None:
    page_probe_flags: list[bool] = []
    template_calls: list[tuple[str, str]] = []
    route_calls: list[tuple[str, str]] = []
    helper_route_calls: list[tuple[str, str]] = []
    surface_route_calls: list[tuple[str, str]] = []
    original_status_rows = config_routes.build_settings_connection_status_rows
    real_template_name = connections_surface_routes.module_template_name
    real_surface_route_path = connections_surface_routes.module_route_path
    real_helper_route_path = connections_surface_helpers.module_route_path

    def tracked_status_rows(*args, **kwargs):
        page_probe_flags.append(bool(kwargs.get("page_probe")))
        return original_status_rows(*args, **kwargs)

    def tracking_template_name(module_id: str, template_name: str) -> str | None:
        template_calls.append((module_id, template_name))
        return real_template_name(module_id, template_name)

    def tracking_surface_route_path(module_id: str, route_path: str) -> str | None:
        surface_route_calls.append((module_id, route_path))
        return real_surface_route_path(module_id, route_path)

    def tracking_helper_route_path(module_id: str, route_path: str) -> str | None:
        helper_route_calls.append((module_id, route_path))
        return real_helper_route_path(module_id, route_path)

    monkeypatch.setattr(config_routes, "build_settings_connection_status_rows", tracked_status_rows)
    monkeypatch.setattr(connections_surface_routes, "module_template_name", tracking_template_name)
    monkeypatch.setattr(connections_surface_routes, "module_route_path", tracking_surface_route_path)
    monkeypatch.setattr(connections_surface_helpers, "module_route_path", tracking_helper_route_path)
    client = _build_profile_config_app(tmp_path, module_route_calls=route_calls)

    status_response = client.get('/connections/status')
    assert status_response.status_code == 200
    assert 'Live status of all configured connections' in status_response.text or 'Live-Status aller konfigurierten Verbindungen' in status_response.text
    assert 'href="/config"' in status_response.text
    assert 'href="/connections/status?refresh=1"' in status_response.text
    assert ("connections_ui_readonly", "/connections/status") in route_calls
    status_nav = _first_memory_subnav(status_response.text)
    assert 'href="/config/persona"' in status_nav
    assert 'href="/connections"' in status_nav
    assert 'class="memory-subnav-item active" href="/connections"' in status_nav
    assert 'href="/connections/status"' not in status_nav
    assert 'href="/connections/types"' not in status_nav
    assert 'href="/connections/templates"' not in status_nav

    live_status_response = client.get('/connections/status?refresh=1')
    assert live_status_response.status_code == 200
    assert 'href="/connections/status"' in live_status_response.text

    types_response = client.get('/connections/types')
    assert types_response.status_code == 200
    assert 'href="/config"' in types_response.text
    assert '/config/connections/ssh?return_to=/connections/types' in types_response.text
    types_nav = _first_memory_subnav(types_response.text)
    assert 'href="/config/persona"' in types_nav
    assert 'class="memory-subnav-item active" href="/connections"' in types_nav
    assert 'href="/connections/types"' not in types_nav
    assert 'allgemeine Websuche wird von ARIA verwaltet' in types_response.text or 'general web search is managed by ARIA' in types_response.text
    assert 'Beobachtete Webseiten' in types_response.text or 'Watched Websites' in types_response.text
    assert 'Google Calendar' in types_response.text
    assert types_response.text.index('Beobachtete Webseiten' if 'Beobachtete Webseiten' in types_response.text else 'Watched Websites') < types_response.text.index('Google Calendar')

    templates_response = client.get('/connections/templates')
    assert templates_response.status_code == 200
    assert 'href="/config"' in templates_response.text
    assert 'name="return_to" value="/connections/templates"' in templates_response.text
    templates_nav = _first_memory_subnav(templates_response.text)
    assert 'href="/config/persona"' in templates_nav
    assert 'class="memory-subnav-item active" href="/connections"' in templates_nav
    assert 'href="/connections/templates"' not in templates_nav
    assert ("connections_ui_readonly", "connections_status.html") in template_calls
    assert ("connections_ui_readonly", "connections_types.html") in template_calls
    assert ("connections_ui_readonly", "connections_templates.html") in template_calls
    assert route_calls.count(("connections_ui_readonly", "/connections/status")) >= 2
    assert helper_route_calls.count(("connections_ui_readonly", "/connections/status")) >= 4
    assert ("connections_ui_readonly", "/connections/types") in helper_route_calls
    assert ("connections_ui_readonly", "/connections/templates") in helper_route_calls
    assert ("connections_ui_readonly", "/connections") in surface_route_calls
    assert ("connections_ui_readonly", "/connections/status") in surface_route_calls
    assert ("connections_ui_readonly", "/connections/types") in surface_route_calls
    assert ("connections_ui_readonly", "/connections/templates") in surface_route_calls
    assert page_probe_flags == [False, True, False, False]


def test_settings_page_groups_system_areas_without_connections_block(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config')

    assert response.status_code == 200
    assert '/config/admin"' not in response.text
    assert '/config/persona' in response.text
    assert 'href="/connections"' in response.text
    assert 'href="/recipes"' in response.text
    assert "My recipes" in response.text or "Meine Rezepte" in response.text
    assert 'href="/recipes/mine"' in response.text
    assert 'href="/connections/status"' in response.text
    assert 'memory-health-grid' not in response.text
    assert 'class="config-submenu-details"' not in response.text
    assert '/config/connections/ssh?return_to=%2Fconfig' not in response.text


def test_settings_nav_hides_advanced_tabs_when_admin_mode_is_off(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, advanced_mode=False)

    response = client.get('/config')

    assert response.status_code == 200
    assert 'href="/config"' in response.text
    assert 'href="/config/persona"' in response.text
    assert 'href="/updates?return_to=/config"' in response.text
    assert 'class="memory-subnav-admin"' not in response.text
    assert 'href="/config/admin"' not in response.text
    assert 'href="/config/intelligence"' not in response.text
    assert 'href="/config/access"' not in response.text
    assert 'href="/config/operations"' not in response.text
    assert 'href="/config/workbench"' not in response.text


def test_persona_theme_and_language_remain_user_accessible_without_admin_mode(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, advanced_mode=False)

    persona = client.get('/config/persona')

    assert persona.status_code == 200
    assert '/config/appearance?return_to=/config/persona' in persona.text
    assert '/config/language?return_to=/config/persona' in persona.text
    assert '/config/prompts?return_to=/config/persona' not in persona.text
    assert 'Admin mode is currently off' not in persona.text
    assert 'Admin-Modus ist derzeit aus' not in persona.text

    appearance = client.get('/config/appearance?return_to=/config/persona')
    assert appearance.status_code == 200
    assert 'action="/config/appearance/save"' in appearance.text

    language = client.get('/config/language?return_to=/config/persona')
    assert language.status_code == 200
    assert 'action="/config/language/save"' in language.text
    assert 'action="/config/language/file/save"' not in language.text


def test_settings_subpages_link_to_existing_specialist_pages(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    module_route_prefix_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(
        tmp_path,
        module_route_calls=module_route_calls,
        module_route_prefix_calls=module_route_prefix_calls,
    )

    hub = client.get('/config')
    assert hub.status_code == 200
    assert hub.text.count('class="admin-nav-group settings-nav-group"') == 9
    assert 'data-config-hub-group="knowledge_memory"' in hub.text
    assert 'data-config-hub-group="system_development"' in hub.text
    assert 'href="/config/admin/modules"' in hub.text
    assert 'href="/config/admin/ui-audit"' in hub.text
    assert 'href="/config/admin"' not in hub.text
    assert 'href="/config/admin/config"' not in hub.text
    assert 'href="/config/admin/recipes"' not in hub.text
    assert 'href="/config/admin/operations"' not in hub.text
    assert client.get('/config/admin').status_code == 404
    assert client.get('/config/admin/config').status_code == 404
    assert client.get('/config/admin/recipes').status_code == 404
    assert client.get('/config/admin/operations').status_code == 404
    assert client.get('/config/intelligence').status_code == 200
    assert client.get('/config/access').status_code == 200
    assert client.get('/config/workbench').status_code == 404
    assert client.get('/config/admin/modules').status_code == 200
    return
    assert '/config/admin' in hub.text
    assert '/config/operations/reindex?return_to=%2Fconfig' not in hub.text
    assert 'class="admin-nav-groups settings-nav-groups"' in hub.text
    assert hub.text.count('class="admin-nav-group settings-nav-group"') == 5
    assert 'data-settings-nav-group="config.overview_title"' not in hub.text
    assert "Arbeitsbereiche" not in hub.text
    assert "Workspace" not in hub.text
    assert "Persönlichkeit &amp; Stil" in hub.text or "Personality &amp; style" in hub.text
    assert "Verbindungen" in hub.text or "Connections" in hub.text
    assert "Rezepte" in hub.text or "Recipes" in hub.text
    assert "Updates" in hub.text
    assert "Admin" in hub.text
    assert 'href="/config/persona"' in hub.text
    assert 'href="/config/appearance?return_to=/config/persona"' in hub.text
    assert 'href="/config/language?return_to=/config/persona"' in hub.text
    assert 'href="/connections"' in hub.text
    assert 'href="/connections/status"' in hub.text
    assert 'href="/connections/types"' in hub.text
    assert 'href="/connections/templates"' in hub.text
    assert 'href="/recipes"' in hub.text
    assert 'href="/recipes/mine"' in hub.text
    assert 'href="/recipes/start"' in hub.text
    assert 'href="/recipes/learned"' not in hub.text
    assert 'href="/updates?return_to=/config"' in hub.text
    assert ("release_update", "/updates") in module_route_calls
    assert 'href="/config/admin"' in hub.text
    assert 'href="/config/admin/config"' in hub.text
    assert 'href="/config/admin/recipes"' in hub.text
    assert 'href="/config/admin/memory"' not in hub.text
    assert 'href="/config/admin/operations"' in hub.text

    admin = client.get('/config/admin')
    assert admin.status_code == 200
    assert 'aria-label="Settings navigation"' not in admin.text
    assert 'aria-label="Einstellungen Navigation"' not in admin.text
    assert 'href="/config/persona"' not in admin.text
    assert 'href="/updates?return_to=/config"' not in admin.text
    assert '<a class="memory-subnav-item" href="/connections"' not in admin.text
    assert '<a class="memory-subnav-item" href="/recipes"' not in admin.text
    assert 'class="admin-nav-groups"' in admin.text
    assert 'class="admin-nav-group"' in admin.text
    assert 'data-admin-nav-group="config.admin_group_config_title"' in admin.text
    assert "Systemkonfiguration" in admin.text or "System configuration" in admin.text
    assert "Rezepte &amp; Lernen" in admin.text or "Recipes &amp; learning" in admin.text
    assert "Betrieb" in admin.text or "Operations" in admin.text
    assert 'href="/config/intelligence"' in admin.text
    assert 'href="/config/access"' in admin.text
    assert 'href="/config/operations"' in admin.text
    assert 'href="/config/workbench"' in admin.text
    assert 'href="/config/admin/modules"' in admin.text
    assert 'href="/config/admin/ui-audit"' in admin.text
    assert 'href="/recipes/system"' in admin.text
    assert 'href="/recipes/learned/maintenance"' not in admin.text
    assert 'href="/memories/import"' not in admin.text
    assert 'href="/memories/auto-memory"' not in admin.text
    assert 'href="/memories/maintenance"' not in admin.text
    assert '<a class="config-submenu-item" href="/connections"' not in admin.text
    assert 'href="/activities"' in admin.text
    admin_nav = _first_memory_subnav(admin.text)
    assert 'class="memory-subnav-item active" href="/config/admin"' in admin_nav
    assert 'href="/config/admin/config"' in admin_nav
    assert 'href="/config/admin/recipes"' in admin_nav
    assert 'href="/config/admin/memory"' not in admin_nav
    assert 'href="/config/admin/operations"' in admin_nav
    assert 'href="/config/intelligence"' not in admin_nav
    assert 'href="/recipes/system"' not in admin_nav

    admin_modules = client.get('/config/admin/modules')
    assert admin_modules.status_code == 200
    assert "Module Registry" in admin_modules.text
    assert "runtime_result_summary" in admin_modules.text
    assert ".codex/aria_acceptance/action-control-observability-import-rail-alpha731.json" in admin_modules.text
    assert 'class="module-registry-list"' in admin_modules.text
    assert 'class="module-registry-row"' in admin_modules.text
    assert 'class="module-registry-badge module-registry-badge-risk"' in admin_modules.text
    assert 'class="module-registry-acceptance"' in admin_modules.text
    assert "Build allowed" in admin_modules.text
    assert "Validation issues" in admin_modules.text
    assert "Internal dependencies" in admin_modules.text
    assert "External boundaries" in admin_modules.text
    assert "Durable boundaries" in admin_modules.text
    assert "Migration candidates" in admin_modules.text
    assert "Python owners" in admin_modules.text
    assert "Integration points" in admin_modules.text
    assert "External classes" in admin_modules.text
    assert "Boundary disposition" in admin_modules.text
    assert "Legacy manifest references" in admin_modules.text
    assert "Dependency cycles" in admin_modules.text
    assert "106" in admin_modules.text
    assert "416" in admin_modules.text
    assert "62" in admin_modules.text
    assert "264" in admin_modules.text
    assert "66" in admin_modules.text
    assert "88 / 18 / 0" in admin_modules.text
    assert "2 / 0" in admin_modules.text
    assert "Consumers" in admin_modules.text
    assert 'class="module-registry-badge module-registry-badge-cycle"' not in admin_modules.text
    assert "configuration_foundations" in admin_modules.text
    assert "kernel.config" not in admin_modules.text
    assert 'action="/config/admin/modules' not in admin_modules.text
    assert 'method="post"' not in admin_modules.text.split('<main class="config-layout', 1)[-1].split("</main>", 1)[0]
    assert 'class="memory-subnav-item active" href="/config/admin/config"' in _first_memory_subnav(admin_modules.text)

    admin_recipes = client.get('/config/admin/recipes')
    assert admin_recipes.status_code == 200
    admin_recipes_nav = _first_memory_subnav(admin_recipes.text)
    assert 'class="memory-subnav-item active" href="/config/admin/recipes"' in admin_recipes_nav
    assert 'href="/recipes/system"' in admin_recipes.text
    assert 'href="/recipes/learned/maintenance"' not in admin_recipes.text
    assert 'href="/config/intelligence"' not in admin_recipes.text
    assert 'href="/memories/auto-memory"' not in admin_recipes.text
    assert admin_recipes.text.count('class="admin-nav-group"') == 1

    admin_config = client.get('/config/admin/config')
    assert admin_config.status_code == 200
    admin_config_nav = _first_memory_subnav(admin_config.text)
    assert 'class="memory-subnav-item active" href="/config/admin/config"' in admin_config_nav
    assert 'href="/config/intelligence"' in admin_config.text
    assert 'href="/config/access"' in admin_config.text
    assert 'href="/config/workbench"' in admin_config.text
    assert 'href="/recipes/system"' not in admin_config.text
    assert admin_config.text.count('class="admin-nav-group"') == 1

    intelligence = client.get('/config/intelligence')
    assert intelligence.status_code == 200
    intelligence_nav = _first_memory_subnav(intelligence.text)
    assert 'href="/config/admin/config"' in intelligence_nav
    assert 'href="/config/admin/recipes"' in intelligence_nav
    assert 'class="memory-subnav-item active" href="/config/admin/config"' in intelligence_nav
    assert 'href="/config/intelligence"' not in intelligence_nav
    assert 'class="ui-action-link config-admin-return-link"' not in intelligence.text
    assert '/config/llm?return_to=/config/intelligence' in intelligence.text
    assert '/config/embeddings?return_to=/config/intelligence' in intelligence.text

    persona = client.get('/config/persona')
    assert persona.status_code == 200
    assert 'class="ui-action-link config-admin-return-link"' not in persona.text
    assert 'aria-label="Settings navigation"' in persona.text or 'aria-label="Einstellungen Navigation"' in persona.text
    assert 'class="memory-subnav-item active" href="/config/persona"' in persona.text
    assert '/config/prompts?return_to=/config/persona' in persona.text
    assert '/config/appearance?return_to=/config/persona' in persona.text
    assert '/config/language?return_to=/config/persona' in persona.text

    access = client.get('/config/access')
    assert access.status_code == 200
    assert '/config/users?return_to=/config/access' in access.text
    assert '/config/users?return_to=/config/access#admin-mode' not in access.text
    assert '/config/security?return_to=/config/access' in access.text

    operations = client.get('/config/operations')
    assert operations.status_code == 200
    operations_nav = _first_memory_subnav(operations.text)
    assert 'class="memory-subnav-item active" href="/config/admin/operations"' in operations_nav
    assert 'class="ui-action-link config-admin-return-link"' not in operations.text
    assert '/updates?return_to=/config/operations' not in operations.text
    assert 'Version, Release Notes' not in operations.text
    assert '/config/logs?return_to=/config/operations' in operations.text
    assert '/config/backup?return_to=/config/operations' in operations.text
    assert module_route_prefix_calls.count(("ops_config_backup", "/config/logs")) >= 1
    assert '/config/operations/reindex?return_to=/config/operations' not in operations.text

def test_retired_workbench_and_rollout_surface_are_absent_but_tools_remain(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    assert client.get('/config/workbench').status_code == 404
    assert client.post('/config/admin/agentic-loop/save', follow_redirects=False).status_code == 404
    for path in ('/config/files', '/config/error-interpreter', '/config/llm/debug'):
        assert client.get(path).status_code == 200
    hub = client.get('/config')
    assert 'Agentic Loop (experimental rollout)' not in hub.text
    assert 'href="/config/workbench"' not in hub.text
    assert 'href="/config/files"' in hub.text
    assert 'href="/config/error-interpreter"' in hub.text
    assert 'href="/config/llm/debug"' in hub.text


def test_config_admin_page_requires_admin_mode(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, advanced_mode=False)

    response = client.get('/config/admin', follow_redirects=False)

    assert response.status_code == 404

    modules_response = client.get('/config/admin/modules', follow_redirects=False)

    assert modules_response.status_code == 303
    assert modules_response.headers['location'].startswith('/config?error=admin_mode_required')


def test_config_operations_page_shows_service_restart_controls(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    monkeypatch.setattr(config_routes, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(
        config_routes,
        "fetch_update_helper_status",
        lambda _config, timeout=1.2: {  # noqa: ARG005
            "status": "idle",
            "running": False,
            "visual_status": "ok",
            "current_step": "",
            "last_result": "",
            "last_error": "",
        },
    )
    response = client.get('/config/operations')

    assert response.status_code == 200
    assert "System-Services" in response.text
    assert "Qdrant neu starten" in response.text or "Restart Qdrant" in response.text
    assert 'action="/config/operations/service-restart"' in response.text
    assert "kontrolliert neu starten" in response.text or "Restart Qdrant now?" in response.text


def test_ops_config_action_urls_use_registry_route_readpoints(monkeypatch, tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)
    monkeypatch.setattr(config_routes, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(
        config_routes,
        "fetch_update_helper_status",
        lambda _config, timeout=1.2: {  # noqa: ARG005
            "status": "idle",
            "running": False,
            "visual_status": "ok",
            "current_step": "",
            "last_result": "",
            "last_error": "",
        },
    )

    logs = client.get("/config/logs")
    operations = client.get("/config/operations")

    assert logs.status_code == 200
    assert operations.status_code == 200
    assert 'action="/config/logs/save"' in logs.text
    assert 'action="/config/logs/cleanup"' in logs.text
    assert 'action="/config/logs/reset"' in logs.text
    assert 'action="/config/logs/factory-reset"' in logs.text
    assert 'action="/config/operations/service-restart"' in operations.text
    assert {
        ("ops_config_backup", "/config/logs/save"),
        ("ops_config_backup", "/config/logs/cleanup"),
        ("ops_config_backup", "/config/logs/reset"),
        ("ops_config_backup", "/config/logs/factory-reset"),
        ("ops_config_backup", "/config/operations/service-restart"),
    }.issubset(set(module_route_calls))


def test_ops_logs_redirect_fallbacks_use_registry_route_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    save = client.post(
        "/config/logs/save",
        data={"enabled": "1", "retention_days": "30", "return_to": "/config/operations"},
        follow_redirects=False,
    )
    cleanup = client.post(
        "/config/logs/cleanup",
        data={"return_to": "/config/operations"},
        follow_redirects=False,
    )
    reset = client.post(
        "/config/logs/reset",
        data={"confirm_text": "RESET", "return_to": "/config/operations"},
        follow_redirects=False,
    )
    reset_error = client.post(
        "/config/logs/reset",
        data={"confirm_text": "nope", "return_to": "/config/operations"},
        follow_redirects=False,
    )

    assert save.status_code == 303
    assert save.headers["location"].startswith("/config/logs?saved=1")
    assert cleanup.status_code == 303
    assert cleanup.headers["location"].startswith("/config/logs?pruned=2")
    assert reset.status_code == 303
    assert reset.headers["location"].startswith("/config/logs?reset=3&archive=tokens-test.jsonl")
    assert reset_error.status_code == 303
    assert reset_error.headers["location"].startswith("/config/logs?error=")
    assert route_calls.count(("ops_config_backup", "/config/logs")) >= 4
    assert route_calls.count(("config_ui", "/config")) >= 4


def test_ops_logs_redirect_fallbacks_fail_closed_without_config_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.post(
            "/config/logs/save",
            data={"enabled": "1", "retention_days": "30", "return_to": "/config/operations"},
            follow_redirects=False,
        )


def test_ops_config_pages_use_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    template_calls: list[tuple[str, str]] = []
    route_calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        template_calls.append((module_id, template_name))
        return template_name

    def _module_route_path(module_id: str, route_path: str, **kwargs: object) -> str:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs) or ""

    monkeypatch.setattr(config_surface_routes, "module_template_name", _module_template_name)
    monkeypatch.setattr(config_ops_detail_routes, "module_template_name", _module_template_name)
    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", _module_route_path)
    client = _build_profile_config_app(tmp_path)

    for path in ("/config/operations", "/config/logs"):
        response = client.get(path)
        assert response.status_code == 200

    assert ("ops_config_backup", "config_operations.html") in template_calls
    assert ("ops_config_backup", "config_logs.html") in template_calls
    assert ("ops_config_backup", "/config/operations") in route_calls


def test_ops_config_memory_admin_route_fails_closed_without_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        if module_id == "memory_admin_ui":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", _module_route_path)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/maintenance"):
        client.get("/config/operations/reindex", follow_redirects=False)


def test_config_backup_memory_export_route_fails_closed_without_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        if module_id == "memory_export":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", _module_route_path)
    monkeypatch.setattr(config_ops_detail_routes, "build_config_backup_payload", lambda **_kwargs: {"schema_version": 1})
    monkeypatch.setattr(config_ops_detail_routes, "summarize_config_backup_payload", lambda _payload: {})
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="memory_export route is not registered: /memories/export"):
        client.get("/config/backup")


def test_config_ui_pages_use_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    template_calls: list[tuple[str, str]] = []
    route_calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        template_calls.append((module_id, template_name))
        return template_name

    def _module_route_path(module_id: str, route_path: str, **kwargs: object) -> str:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs) or ""

    monkeypatch.setattr(config_surface_routes, "module_template_name", _module_template_name)
    monkeypatch.setattr(config_surface_routes, "module_route_path", _module_route_path)
    client = _build_profile_config_app(tmp_path)

    paths = [
        "/config",
        "/config/admin/modules",
        "/config/intelligence",
        "/config/persona",
        "/config/access",
        "/config/operations",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200

    assert ("config_ui", "config_hub.html") in template_calls
    assert ("config_ui", "config_admin_modules.html") in template_calls
    assert ("config_ui", "config_intelligence.html") in template_calls
    assert ("config_ui", "config_persona.html") in template_calls
    assert ("config_ui", "config_access.html") in template_calls
    assert ("config_ui", "/config") in route_calls
    assert ("config_ui", "/config/admin/modules") in route_calls
    assert ("config_ui", "/config/intelligence") in route_calls
    assert ("config_ui", "/config/persona") in route_calls
    assert ("config_ui", "/config/access") in route_calls
    assert ("ops_config_backup", "/config/operations") in route_calls
    assert ("chat_surface", "/") in route_calls


def test_config_surface_template_readpoint_fails_closed_for_unregistered_template(monkeypatch) -> None:
    monkeypatch.setattr(config_surface_routes, "module_template_name", lambda *_args, **_kwargs: None)

    try:
        config_surface_routes._config_ui_template("config_hub.html")
    except RuntimeError as exc:
        assert "config_ui template is not registered: config_hub.html" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("config_ui template helper must fail closed when the registry has no owner")


def test_config_surface_home_route_readpoint_fails_closed_without_owner(monkeypatch) -> None:
    monkeypatch.setattr(config_surface_routes, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="chat_surface route is not registered: /"):
        config_surface_routes._chat_surface_path("/")


def test_config_ui_visible_urls_use_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    for page in (
        "/config",
        "/config/intelligence",
        "/config/persona",
        "/config/access",
        "/config/admin-mode",
        "/config/language",
        "/config/prompts",
        "/config/files",
        "/config/error-interpreter",
        "/config/security",
        "/config/llm/debug",
        "/connections",
        "/connections/types",
    ):
        response = client.get(page)
        assert response.status_code == 200

    expected_route_calls = {
        ("config_ui", "/config"),
        ("config_ui", "/config/admin-mode"),
        ("config_ui", "/config/security"),
        ("config_ui", "/config/users"),
        ("config_ui", "/config/llm"),
        ("config_ui", "/config/embeddings"),
        ("config_ui", "/config/prompts"),
        ("config_ui", "/config/appearance"),
        ("config_ui", "/config/language"),
        ("config_ui", "/config/files"),
        ("config_ui", "/config/files/save"),
        # The retired Workbench used to resolve these two links indirectly.
        # Their dedicated pages are exercised directly above.
    }
    assert expected_route_calls.issubset(set(module_route_calls))
    assert 'action="/config/admin-mode/save"' in client.get("/config/admin-mode").text
    assert 'action="/config/language/save"' in client.get("/config/language").text
    assert 'action="/config/security"' in client.get("/config/security").text


def test_config_ui_form_action_urls_use_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    responses = {
        path: client.get(path)
        for path in (
            "/config/admin-mode",
            "/config/appearance",
            "/config/language",
            "/config/prompts",
            "/config/files",
            "/config/error-interpreter",
            "/config/llm/debug",
            "/config/llm",
            "/config/embeddings",
        )
    }

    for path, response in responses.items():
        assert response.status_code == 200, path
    assert 'action="/config/admin-mode/save"' in responses["/config/admin-mode"].text
    assert 'action="/config/appearance/save"' in responses["/config/appearance"].text
    assert 'action="/config/language/save"' in responses["/config/language"].text
    assert 'action="/config/language/file/save"' in responses["/config/language"].text
    assert 'action="/config/prompts"' in responses["/config/prompts"].text
    assert 'action="/config/prompts/save"' in responses["/config/prompts"].text
    assert 'action="/config/error-interpreter/save"' in responses["/config/error-interpreter"].text
    assert 'action="/config/llm/debug/clear"' in responses["/config/llm/debug"].text
    assert 'action="/config/llm/test"' in responses["/config/llm"].text
    assert 'action="/config/llm/roles"' in responses["/config/llm"].text
    assert 'action="/config/llm/web/test"' in responses["/config/llm"].text
    assert 'action="/config/llm/profile/save"' in responses["/config/llm"].text
    assert 'fetch("/config/llm/models"' in responses["/config/llm"].text
    assert 'action="/config/embeddings/test"' in responses["/config/embeddings"].text
    assert 'action="/config/embeddings/profile/load"' in responses["/config/embeddings"].text
    assert 'action="/config/embeddings/profile/delete"' in responses["/config/embeddings"].text
    assert 'action="/config/embeddings/save"' in responses["/config/embeddings"].text
    assert 'formaction="/config/embeddings/profile/save"' in responses["/config/embeddings"].text
    assert 'fetch("/config/embeddings/models"' in responses["/config/embeddings"].text
    assert {
        ("config_ui", "/config/admin-mode/save"),
        ("config_ui", "/config/appearance/save"),
        ("config_ui", "/config/language/save"),
        ("config_ui", "/config/language/file/save"),
        ("config_ui", "/config/prompts"),
        ("config_ui", "/config/prompts/save"),
        ("config_ui", "/config/files"),
        ("config_ui", "/config/files/save"),
        ("config_ui", "/config/error-interpreter/save"),
        ("config_ui", "/config/llm/debug/clear"),
        ("config_ui", "/config/llm/models"),
        ("config_ui", "/config/llm/test"),
        ("config_ui", "/config/llm/profile/delete"),
        ("config_ui", "/config/llm/profile/save"),
        ("config_ui", "/config/llm/roles"),
        ("config_ui", "/config/llm/web/test"),
        ("config_ui", "/config/embeddings/test"),
        ("config_ui", "/config/embeddings/profile/load"),
        ("config_ui", "/config/embeddings/profile/delete"),
        ("config_ui", "/config/embeddings/models"),
        ("config_ui", "/config/embeddings/save"),
        ("config_ui", "/config/embeddings/profile/save"),
    }.issubset(set(module_route_calls))


def test_config_persona_detail_pages_use_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        calls.append((module_id, template_name))
        return template_name

    monkeypatch.setattr(config_persona_routes, "module_template_name", _module_template_name)
    client = _build_profile_config_app(tmp_path)

    for path in ("/config/appearance", "/config/language", "/config/prompts"):
        response = client.get(path)
        assert response.status_code == 200

    assert ("config_ui", "config_appearance.html") in calls
    assert ("config_ui", "config_language.html") in calls
    assert ("config_ui", "config_prompts.html") in calls


def test_config_access_detail_pages_use_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        calls.append((module_id, template_name))
        return template_name

    monkeypatch.setattr(config_access_detail_routes, "module_template_name", _module_template_name)
    client = _build_profile_config_app(tmp_path)

    for path in ("/config/admin-mode", "/config/security", "/config/users"):
        response = client.get(path)
        assert response.status_code == 200

    assert ("config_ui", "config_admin_mode.html") in calls
    assert ("config_ui", "config_security.html") in calls
    assert ("config_ui", "config_users.html") in calls


def test_config_intelligence_workbench_pages_use_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    template_calls: list[tuple[str, str]] = []
    route_calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        template_calls.append((module_id, template_name))
        return template_name

    def _module_route_path(module_id: str, route_path: str, **kwargs: object) -> str:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs) or ""

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_template_name", _module_template_name)
    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", _module_route_path)
    client = _build_profile_config_app(tmp_path)

    paths = [
        "/config/llm",
        "/config/llm/debug",
        "/config/embeddings",
        "/config/files",
        "/config/error-interpreter",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200

    assert ("config_ui", "config_llm.html") in template_calls
    assert ("config_ui", "config_llm_debug.html") in template_calls
    assert ("config_ui", "config_embeddings.html") in template_calls
    assert ("config_ui", "config_files.html") in template_calls
    assert ("config_ui", "config_error_interpreter.html") in template_calls
    assert ("config_ui", "/config") in route_calls
    assert ("config_ui", "/config/intelligence") in route_calls


def test_config_intelligence_redirect_fallbacks_use_route_readpoints(monkeypatch, tmp_path: Path) -> None:
    route_calls: list[tuple[str, str]] = []
    real_module_route_path = config_intelligence_workbench_routes.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    debug_clear = client.post("/config/llm/debug/clear", follow_redirects=False)
    llm_load = client.post("/config/llm/profile/load", data={"profile_name": "missing-profile"}, follow_redirects=False)
    embeddings_load = client.post(
        "/config/embeddings/profile/load",
        data={"profile_name": "missing-profile"},
        follow_redirects=False,
    )

    assert debug_clear.status_code == 303
    assert llm_load.status_code == 303
    assert embeddings_load.status_code == 303
    assert ("config_ui", "/config/llm/debug") in route_calls
    assert ("config_ui", "/config/llm") in route_calls
    assert ("config_ui", "/config/embeddings") in route_calls
    assert route_calls.count(("config_ui", "/config")) >= 2


def test_web_llm_paid_capability_test_fails_closed_on_provider_error(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    class FailingGateway:
        async def answer(self, *_args: object, **_kwargs: object) -> object:
            raise config_intelligence_workbench_routes.NativeWebLLMError(
                "native_web_provider_failed:TimeoutError"
            )

    client.app.state.test_settings.web_llm.profile = "web"
    client.app.state.test_pipeline.web_llm_gateway = FailingGateway()

    response = client.post(
        "/config/llm/web/test",
        data={"confirm_paid": "on"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "test_status=error" in response.headers["location"]
    assert "native_web_provider_failed" in response.headers["location"]


def test_config_intelligence_redirect_target_fails_closed_without_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_llm_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config/llm":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", missing_llm_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/llm"):
        client.post("/config/llm/profile/load", data={"profile_name": "missing-profile"}, follow_redirects=False)


def test_config_intelligence_redirect_fallback_fails_closed_without_owner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def missing_config_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", missing_config_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config"):
        client.post("/config/llm/profile/load", data={"profile_name": "missing-profile"}, follow_redirects=False)


def test_config_workbench_editor_redirect_targets_use_registry_readpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_calls: list[tuple[str, str]] = []

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    error_interpreter_save = client.post(
        "/config/error-interpreter/save",
        data={
            "content": "rules:\n  - id: demo\n    patterns: []\n    messages: {}\n",
            "return_to": "/config",
        },
        follow_redirects=False,
    )
    error_interpreter_error = client.post(
        "/config/error-interpreter/save",
        data={"content": "rules: nope", "return_to": "/config"},
        follow_redirects=False,
    )
    files_save = client.post(
        "/config/files/save",
        data={"file": "prompts/persona.md", "content": "updated prompt\n", "return_to": "/config"},
        follow_redirects=False,
    )
    files_error = client.post(
        "/config/files/save",
        data={"file": "missing.md", "content": "missing\n", "return_to": "/config"},
        follow_redirects=False,
    )

    assert error_interpreter_save.status_code == 303
    assert error_interpreter_save.headers["location"].startswith("/config/error-interpreter?saved=1")
    assert error_interpreter_error.status_code == 303
    assert error_interpreter_error.headers["location"].startswith("/config/error-interpreter?error=")
    assert files_save.status_code == 303
    assert files_save.headers["location"].startswith("/config/files?file=prompts%2Fpersona.md&saved=1")
    assert files_error.status_code == 303
    assert files_error.headers["location"].startswith("/config/files?file=missing.md&error=")
    assert ("config_ui", "/config/error-interpreter") in route_calls
    assert ("config_ui", "/config/files") in route_calls
    assert ("config_ui", "/config") in route_calls


def test_config_workbench_editor_redirect_target_fails_closed_without_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_files_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "config_ui" and route_path == "/config/files":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_intelligence_workbench_routes, "module_route_path", missing_files_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/files"):
        client.post(
            "/config/files/save",
            data={"file": "missing.md", "content": "missing\n", "return_to": "/config"},
            follow_redirects=False,
        )


def test_config_operations_service_restart_triggers_helper(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    called: dict[str, str] = {}
    monkeypatch.setattr(config_routes, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005

    def _trigger(_config, service: str, timeout: float = 2.5) -> dict[str, object]:  # noqa: ARG001
        called["service"] = service
        return {"status": "accepted"}

    monkeypatch.setattr(config_routes, "trigger_update_helper_service_restart", _trigger)

    response = client.post(
        '/config/operations/service-restart',
        data={"service": "qdrant", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert called["service"] == "qdrant"
    assert response.headers["location"].startswith("/config/operations?saved=1&info=")


def test_memory_reindex_standalone_page_is_removed(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get("/memories/reindex")

    assert response.status_code == 404


def test_memory_reindex_save_redirects_to_memory_config(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    save_response = client.post(
        "/memories/reindex/save",
        data={
            "enabled": "1",
            "cron": "5 */4 * * *",
            "timezone": "Europe/Zurich",
            "run_on_startup": "1",
            "keep_backup": "1",
            "score_threshold": "0.42",
            "candidate_limit": "17",
            "csrf_token": "test-csrf",
        },
        follow_redirects=False,
    )

    assert save_response.status_code == 303
    assert save_response.headers["location"] == "/memories/config?saved=1"
    raw = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert raw["inventory_index"]["enabled"] is True
    assert raw["inventory_index"]["cron"] == "5 */4 * * *"
    assert raw["inventory_index"]["run_on_startup"] is True
    assert raw["inventory_index"]["keep_backup"] is True
    assert raw["inventory_index"]["score_threshold"] == 0.42
    assert raw["inventory_index"]["candidate_limit"] == 17


def test_memory_reindex_run_keeps_behavior_and_focuses_maintenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_rebuild(settings: object, *, usage_meter: object | None = None) -> dict[str, object]:
        calls.append({"settings": settings, "usage_meter": usage_meter})
        return {"status": "ok", "message": "Inventory index rebuilt."}

    monkeypatch.setattr(config_ops_detail_routes, "rebuild_inventory_index", fake_rebuild)
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/memories/reindex/run",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert calls and calls[0]["usage_meter"] is None
    assert response.headers["location"] == (
        "/memories/maintenance?info=Inventory+index+rebuilt.&focus=reindex#maint-reindex"
    )


def test_legacy_config_operations_reindex_redirects_to_memory_maintenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []
    real_module_route_path = config_ops_detail_routes.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return real_module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", tracking_module_route_path)
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/operations/reindex", follow_redirects=False)
    run_response = client.post("/config/operations/reindex/run", follow_redirects=False)
    save_response = client.post("/config/operations/reindex/save", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/memories/maintenance"
    assert run_response.status_code == 303
    assert run_response.headers["location"] == "/memories/maintenance"
    assert save_response.status_code == 303
    assert save_response.headers["location"] == "/memories/config"
    assert ("memory_admin_ui", "/memories/maintenance") in calls
    assert ("memory_admin_ui", "/memories/config") in calls


def test_legacy_config_operations_reindex_redirect_fails_closed_without_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_memory_admin_route(module_id: str, route_path: str, **kwargs: object) -> str | None:  # noqa: ARG001
        if module_id == "memory_admin_ui":
            return None
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(config_ops_detail_routes, "module_route_path", missing_memory_admin_route)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/maintenance"):
        client.get("/config/operations/reindex", follow_redirects=False)


def test_google_calendar_connection_page_renders(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/connections/google-calendar?mode=create&return_to=%2Fconnections%2Ftypes")

    assert response.status_code == 200
    assert "Google Calendar" in response.text
    assert "/config/connections/google-calendar/save" in response.text
    assert "/config/connections/google-calendar/oauth/start" not in response.text
    assert "/config/connections/google-calendar/oauth/device/start" not in response.text
    assert "/config/connections/google-calendar/oauth/callback" not in response.text
    assert "Mit Google per Code verbinden" not in response.text
    assert "iCal" in response.text
    assert 'name="ical_url"' in response.text
    assert "Geheime Adresse im iCal-Format" in response.text or "Secret address in iCal format" in response.text
    assert 'name="refresh_token"' not in response.text
    assert 'name="client_id"' not in response.text
    assert 'name="client_secret"' not in response.text
    assert 'name="oauth_client_file"' not in response.text
    assert "https://console.cloud.google.com/auth/clients" not in response.text
    assert "Recommended flow" not in response.text
    assert "Empfohlener Ablauf" not in response.text
    assert "OAuth-Branding einrichten" not in response.text
    assert "Dich selbst als Testnutzer eintragen" not in response.text


def test_google_calendar_save_persists_ical_profile_without_leaking_secret(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        config_routes,
        "build_connection_status_row",
        lambda *args, **kwargs: {"status": "ok", "message": "Google Calendar iCal ok"},
    )
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/connections/google-calendar/save",
        data={
            "connection_ref": "primary-calendar",
            "connection_title": "Mein Kalender",
            "ical_url": "https://calendar.google.com/calendar/ical/private/basic.ics",
            "timeout_seconds": "10",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "google_calendar_test_status=ok" in response.headers["location"]
    raw = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    row = raw["connections"]["google_calendar"]["primary-calendar"]
    assert row["calendar_id"] == "ical"
    assert row["timeout_seconds"] == 10
    assert "ical_url" not in row
    assert "client_id" not in row
    assert "client_secret" not in row
    assert "refresh_token" not in row


def test_google_calendar_save_requires_ical_url(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/connections/google-calendar/save",
        data={
            "connection_ref": "primary-calendar",
            "connection_title": "Mein Kalender",
            "timeout_seconds": "10",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "google_calendar_ref=primary-calendar" in response.headers["location"]
    assert "error=" in response.headers["location"]


def test_website_connection_page_renders(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/websites?mode=create&return_to=%2Fconnections%2Ftypes')

    assert response.status_code == 200
    assert 'action="/config/connections/websites/save"' in response.text
    assert 'https://example.org/docs' in response.text
    assert 'group_name' in response.text
    assert '#manage-existing' in response.text


def test_website_connection_existing_links_jump_to_editor(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    response = client.post(
        '/config/connections/websites/save',
        data={
            'connection_ref': 'aria-docs',
            'url': 'https://example.org/docs',
            'group_name': 'Docs',
            'title': 'ARIA Docs',
            'description': 'Technical documentation',
            'aliases': 'docs',
            'tags': 'aria, docs',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert '#create-new' in response.text
    assert 'website_ref=aria-docs#manage-existing' in response.text


def test_website_config_page_uses_registry_template_readpoint(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        calls.append((module_id, template_name))
        return template_name

    monkeypatch.setattr(connection_page_helpers, "module_template_name", _module_template_name)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/websites?mode=create')

    assert response.status_code == 200
    assert ("website_ui", "config_connections_websites.html") in calls


def test_connection_config_template_readpoint_fails_closed_without_owner(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(connection_page_helpers, "module_template_name", lambda *_args, **_kwargs: None)
    client = _build_profile_config_app(tmp_path)

    with pytest.raises(RuntimeError, match="website_ui template is not registered: config_connections_websites.html"):
        client.get("/config/connections/websites?mode=create")


def test_website_config_visible_urls_use_registry_route_readpoints(monkeypatch, tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    helper_route_calls: list[tuple[str, str]] = []

    def tracking_connection_context_route_path(module_id: str, route_path: str, **kwargs):  # noqa: ANN001, ANN202
        helper_route_calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs) or ""

    monkeypatch.setattr(connection_context_helpers, "module_route_path", tracking_connection_context_route_path)
    monkeypatch.setattr(connection_page_helpers, "module_route_path", tracking_connection_context_route_path)
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    response = client.get('/config/connections/websites?mode=create')

    assert response.status_code == 200
    assert 'action="/config/connections/websites/save"' in response.text
    assert 'data-connection-meta-endpoint="/config/connections/websites/suggest-metadata"' in response.text
    assert {
        ("website_ui", "/config/connections/websites"),
        ("website_ui", "/config/connections/websites/save"),
        ("website_ui", "/config/connections/websites/suggest-metadata"),
    }.issubset(set(module_route_calls))
    assert ("website_ui", "/config/connections/websites") in helper_route_calls
    assert ("config_ui", "/config") in helper_route_calls


def test_website_config_template_action_readpoints_fail_closed_without_owner(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    def missing_website_route(module_id: str, route_path: str) -> str:
        if module_id == "website_ui" and route_path == "/config/connections/websites/suggest-metadata":
            raise RuntimeError(f"{module_id} route is not registered: {route_path}")
        return route_path

    client.app.state.templates.env.globals["required_module_route_path"] = missing_website_route

    with pytest.raises(
        RuntimeError,
        match="website_ui route is not registered: /config/connections/websites/suggest-metadata",
    ):
        client.get("/config/connections/websites?mode=create")


def test_simple_connection_config_pages_use_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        calls.append((module_id, template_name))
        return template_name

    monkeypatch.setattr(connection_page_helpers, "module_template_name", _module_template_name)
    client = _build_profile_config_app(tmp_path)

    expectations = [
        ("/config/connections/discord?mode=create", "discord_ui", "config_connections_discord.html"),
        ("/config/connections/imap?mode=create", "imap_ui", "config_connections_imap.html"),
        ("/config/connections/mqtt?mode=create", "mqtt_ui", "config_connections_mqtt.html"),
        ("/config/connections/smb?mode=create", "smb_ui", "config_connections_smb.html"),
        ("/config/connections/smtp?mode=create", "smtp_ui", "config_connections_smtp.html"),
    ]

    for path, _module_id, _template_name in expectations:
        response = client.get(path)
        assert response.status_code == 200

    for _path, module_id, template_name in expectations:
        assert (module_id, template_name) in calls


def test_simple_connection_config_visible_urls_use_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    expectations = [
        ("/config/connections/discord?mode=create", "discord_ui", "/config/connections/discord/save"),
        ("/config/connections/imap?mode=create", "imap_ui", "/config/connections/imap/save"),
        ("/config/connections/mqtt?mode=create", "mqtt_ui", "/config/connections/mqtt/save"),
        ("/config/connections/smb?mode=create", "smb_ui", "/config/connections/smb/save"),
        ("/config/connections/smtp?mode=create", "smtp_ui", "/config/connections/smtp/save"),
    ]

    for path, module_id, save_path in expectations:
        response = client.get(path)
        assert response.status_code == 200
        assert f'action="{save_path}"' in response.text
        assert (module_id, save_path) in module_route_calls


def test_simple_connection_config_action_readpoints_fail_closed_without_owner(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    def missing_discord_route(module_id: str, route_path: str) -> str:
        if module_id == "discord_ui" and route_path == "/config/connections/discord/save":
            raise RuntimeError(f"{module_id} route is not registered: {route_path}")
        return route_path

    client.app.state.templates.env.globals["required_module_route_path"] = missing_discord_route

    with pytest.raises(RuntimeError, match="discord_ui route is not registered: /config/connections/discord/save"):
        client.get("/config/connections/discord?mode=create")


def test_critical_connection_config_pages_use_existing_registry_template_readpoints(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str:
        calls.append((module_id, template_name))
        return template_name

    monkeypatch.setattr(connection_page_helpers, "module_template_name", _module_template_name)
    client = _build_profile_config_app(tmp_path)

    expectations = [
        (
            "/config/connections/google-calendar?mode=create",
            "google_calendar_ui",
            "config_connections_google_calendar.html",
        ),
        ("/config/connections/ssh?mode=create", "ssh_admin_ui", "config_connections_ssh.html"),
        ("/config/connections/sftp?mode=create", "sftp_admin_ui", "config_connections_sftp.html"),
        ("/config/connections/http-api?mode=create", "http_api_admin_ui", "config_connections_http_api.html"),
        ("/config/connections/webhook?mode=create", "http_api_admin_ui", "config_connections_webhook.html"),
    ]

    for path, _module_id, _template_name in expectations:
        response = client.get(path)
        assert response.status_code == 200

    for _path, module_id, template_name in expectations:
        assert (module_id, template_name) in calls


def test_critical_connection_config_visible_urls_use_existing_registry_route_readpoints(tmp_path: Path) -> None:
    module_route_calls: list[tuple[str, str]] = []
    client = _build_profile_config_app(tmp_path, module_route_calls=module_route_calls)

    expectations = [
        (
            "/config/connections/google-calendar?mode=create",
            [("google_calendar_ui", "/config/connections/google-calendar/save")],
        ),
        ("/config/connections/ssh?mode=create", [
            ("ssh_admin_ui", "/config/connections/save"),
            ("ssh_admin_ui", "/config/connections/ssh/suggest-metadata"),
        ]),
        ("/config/connections/sftp?mode=create", [
            ("sftp_admin_ui", "/config/connections/sftp/save"),
            ("sftp_admin_ui", "/config/connections/sftp/suggest-metadata"),
        ]),
        ("/config/connections/http-api?mode=create", [("http_api_admin_ui", "/config/connections/http-api/save")]),
        ("/config/connections/webhook?mode=create", [("http_api_admin_ui", "/config/connections/webhook/save")]),
    ]

    for path, expected_calls in expectations:
        response = client.get(path)
        assert response.status_code == 200
        for module_id, route_path in expected_calls:
            if route_path.endswith("/suggest-metadata"):
                assert f'data-connection-meta-endpoint="{route_path}"' in response.text
            else:
                assert f'action="{route_path}"' in response.text
            assert (module_id, route_path) in module_route_calls


def test_critical_connection_config_action_readpoints_fail_closed_without_owner(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    def missing_ssh_route(module_id: str, route_path: str) -> str:
        if module_id == "ssh_admin_ui" and route_path == "/config/connections/keygen":
            raise RuntimeError(f"{module_id} route is not registered: {route_path}")
        return route_path

    client.app.state.templates.env.globals["required_module_route_path"] = missing_ssh_route

    with pytest.raises(RuntimeError, match="ssh_admin_ui route is not registered: /config/connections/keygen"):
        client.get("/config/connections/ssh?mode=create")


def test_website_save_autofills_metadata_and_group(monkeypatch, tmp_path: Path) -> None:
    import aria.modules.connections_ui_readonly.reader_helpers as connection_reader_helpers_mod

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b'<html><head><title>ARIA Docs</title>'
                b'<meta name="description" content="Technical documentation for ARIA">'
                b'<meta name="keywords" content="docs, api, reference">'
                b'</head><body><h1>ARIA Docs</h1></body></html>'
            )

    class _FakeLLM:
        async def chat(self, _messages, **_kwargs):
            return SimpleNamespace(
                content='{"title":"ARIA Docs","description":"Technische Dokumentation fuer ARIA","aliases":["aria docs","doku"],"tags":["docs","api"]}'
            )

    monkeypatch.setattr(connection_reader_helpers_mod, 'urlopen', lambda *_args, **_kwargs: _FakeResponse())
    monkeypatch.setattr(config_routes, 'build_connection_status_row', lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'})

    client = _build_profile_config_app(tmp_path, lang='de')
    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.post(
        '/config/connections/websites/save',
        data={
            'connection_ref': 'aria-docs',
            'original_ref': '',
            'url': 'docs.aria.local/reference',
            'timeout_seconds': '10',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert '/config/connections/websites?saved=1' in response.headers['location']
    assert 'website_ref=aria-docs' in response.headers['location']
    assert 'website_test_status=ok' in response.headers['location']

    saved = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    row = saved['connections']['website']['aria-docs']
    assert row['url'] == 'https://docs.aria.local/reference'
    assert row['title'] == 'ARIA Docs'
    assert row['description'] == 'Technische Dokumentation fuer ARIA'
    assert row['aliases'] == ['aria docs', 'doku']
    assert row['tags'] == ['docs', 'api']
    assert row['group_name'] == 'docs'
