from pathlib import Path
from aria.web.config_routes import (
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

import aria.web.config_routes as config_routes_mod
from aria.core.config import Settings
from aria.web.config_routes import ConfigRouteDeps, register_config_routes


def _write_profile_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


class _NoopStore:
    def get_secret(self, _key: str, default: str = "") -> str:
        return default

    def set_secret(self, _key: str, _value: str) -> None:
        return None

    def delete_secret(self, _key: str) -> None:
        return None

    def rename_secret(self, _src: str, _dst: str) -> None:
        return None

    def list_users(self) -> list[dict[str, object]]:
        return []


def _build_profile_config_app(tmp_path: Path, *, lang: str = 'en') -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
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
    pipeline = SimpleNamespace(usage_meter=None, memory_skill=None)

    async def _keyword_stub(*_args, **_kwargs) -> list[str]:
        return []

    @app.middleware('http')
    async def _inject_state(request: Request, call_next):
        request.state.can_access_advanced_config = True
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
        get_auth_session_from_request=lambda request: {'username': 'neo', 'role': 'admin'},
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
        reload_runtime=lambda: None,
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
        get_secure_store=lambda _raw=None: _NoopStore(),
        lang_flag=lambda code: code,
        lang_label=lambda code: code.upper(),
        available_languages=lambda: ['en', 'de'],
        resolve_lang=lambda code, default_lang='de': code or default_lang,
        clear_i18n_cache=lambda: None,
        load_custom_skill_manifests=lambda: ([], []),
        custom_skill_file=lambda skill_id: (tmp_path / 'data' / 'skills' / f'{skill_id}.json').resolve(),
        save_custom_skill_manifest=lambda manifest: manifest,
        refresh_skill_trigger_index=lambda: {},
        format_skill_routing_info=lambda ref, kind: f'{ref}:{kind}',
        suggest_skill_keywords_with_llm=_keyword_stub,
    )
    register_config_routes(app, deps)
    app.state.test_pipeline = pipeline
    return TestClient(app)


def test_llm_config_page_shows_active_profile_runtime_meta(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/llm?return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'Active profile' in response.text
    assert 'litellm-main' in response.text
    assert 'https://litellm.example/v1' in response.text
    assert 'openai/gpt-4.1-mini' in response.text
    assert 'action="/config/llm/test"' in response.text
    assert "const logical='/config';" in response.text


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
    assert 'LiteLLM Proxy' in response.text
    assert 'text-embedding-3-small' in response.text
    assert 'Anthropic' not in response.text


def test_routing_page_shows_qdrant_routing_index_status(monkeypatch, tmp_path: Path) -> None:
    async def fake_status(_settings: object) -> dict[str, object]:
        return {
            "status": "ok",
            "visual_status": "ok",
            "message": "Routing index ready: 3/3 profiles indexed.",
            "collection_name": "aria_routing_connections_test",
            "collection_names": ["aria_routing_connections_test"],
            "collection_count": 1,
            "document_count": 3,
            "indexed_count": 3,
            "detail": "",
        }

    monkeypatch.setattr(config_routes_mod, "build_connection_routing_index_status", fake_status)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/routing')

    assert response.status_code == 200
    assert 'Routing Index' in response.text
    assert 'Routing index ready: 3/3 profiles indexed.' in response.text
    assert 'aria_routing_connections_test' in response.text
    assert 'action="/config/routing-index/rebuild"' in response.text
    assert 'action="/config/routing/qdrant/save"' in response.text
    assert 'name="qdrant_connection_routing_enabled"' in response.text
    assert 'name="qdrant_score_threshold"' in response.text


def test_routing_index_rebuild_redirects_with_result(monkeypatch, tmp_path: Path) -> None:
    async def fake_status(_settings: object) -> dict[str, object]:
        return {
            "status": "warn",
            "visual_status": "warn",
            "message": "Routing index has not been built yet.",
            "collection_name": "aria_routing_connections_test",
            "collection_names": [],
            "collection_count": 0,
            "document_count": 3,
            "indexed_count": 0,
            "detail": "",
        }

    async def fake_rebuild(_settings: object) -> dict[str, object]:
        return {
            "status": "ok",
            "visual_status": "ok",
            "message": "Routing index rebuilt: 3/3 profiles indexed.",
            "document_count": 3,
            "indexed_count": 3,
        }

    monkeypatch.setattr(config_routes_mod, "build_connection_routing_index_status", fake_status)
    monkeypatch.setattr(config_routes_mod, "rebuild_connection_routing_index", fake_rebuild)
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        '/config/routing-index/rebuild',
        data={"scope": "default", "return_to": "/config"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert '/config/routing?' in response.headers['location']
    assert 'info=Routing+index+rebuilt' in response.headers['location']


def test_routing_qdrant_save_persists_live_settings(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        '/config/routing/qdrant/save',
        data={
            "scope": "default",
            "qdrant_connection_routing_enabled": "1",
            "qdrant_score_threshold": "0.45",
            "qdrant_candidate_limit": "7",
            "qdrant_ask_on_low_confidence": "1",
            "return_to": "/config",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert '/config/routing?' in response.headers['location']
    assert 'info=Live-Qdrant-Routing+gespeichert' in response.headers['location']
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    assert raw["routing"]["qdrant_connection_routing_enabled"] is True
    assert raw["routing"]["qdrant_score_threshold"] == 0.45
    assert raw["routing"]["qdrant_candidate_limit"] == 7
    assert raw["routing"]["qdrant_ask_on_low_confidence"] is True


def test_routing_qdrant_save_can_disable_live_routing(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        '/config/routing/qdrant/save',
        data={
            "scope": "default",
            "qdrant_score_threshold": "0.50",
            "qdrant_candidate_limit": "5",
            "return_to": "/config",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    raw = yaml.safe_load((tmp_path / 'config' / 'config.yaml').read_text(encoding='utf-8'))
    assert raw["routing"]["qdrant_connection_routing_enabled"] is False
    assert raw["routing"]["qdrant_ask_on_low_confidence"] is False


def test_routing_page_shows_testbench_result(monkeypatch, tmp_path: Path) -> None:
    async def fake_status(_settings: object) -> dict[str, object]:
        return {
            "status": "ok",
            "visual_status": "ok",
            "message": "Routing index ready.",
            "collection_name": "aria_routing_connections_test",
            "collection_names": [],
            "collection_count": 0,
            "document_count": 1,
            "indexed_count": 1,
            "detail": "",
        }

    async def fake_test(_settings: object, query: str, *, preferred_kind: str = "auto") -> dict[str, object]:
        assert query == "Run uptime on pihole1"
        assert preferred_kind == "ssh"
        return {
            "status": "ok",
            "visual_status": "ok",
            "message": "Deterministic routing matched ssh/pihole1 via exact_ref.",
            "query": query,
            "preferred_kind": preferred_kind,
            "available_counts": {"ssh": 1},
            "deterministic": {
                "found": True,
                "kind": "ssh",
                "ref": "pihole1",
                "source": "exact_ref",
                "score": 10007.0,
                "reason": "pihole1",
                "capability": "",
            },
            "qdrant": {
                "enabled": True,
                "message": "",
                "error": "",
                "candidate_count": 0,
                "accepted_count": 0,
                "candidates": [],
            },
            "decision": {
                "found": True,
                "kind": "ssh",
                "ref": "pihole1",
                "source": "exact_ref",
                "score": 10007.0,
                "reason": "pihole1",
                "capability": "",
            },
            "executed": False,
        }

    monkeypatch.setattr(config_routes_mod, "build_connection_routing_index_status", fake_status)
    monkeypatch.setattr(config_routes_mod, "test_connection_routing_query", fake_test)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/routing?routing_query=Run+uptime+on+pihole1&routing_kind=ssh')

    assert response.status_code == 200
    assert 'Routing Testbench' in response.text
    assert 'ssh/pihole1' in response.text
    assert 'Dry-run' in response.text


def test_routing_index_test_json_route(monkeypatch, tmp_path: Path) -> None:
    async def fake_test(_settings: object, query: str, *, preferred_kind: str = "auto") -> dict[str, object]:
        return {
            "status": "warn",
            "message": "No routing target matched.",
            "query": query,
            "preferred_kind": preferred_kind,
            "decision": {"found": False},
        }

    monkeypatch.setattr(config_routes_mod, "test_connection_routing_query", fake_test)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/routing-index/test?query=foo&preferred_kind=ssh')

    assert response.status_code == 200
    assert response.json()["query"] == "foo"
    assert response.json()["preferred_kind"] == "ssh"


def test_llm_test_route_reports_active_profile_result(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    async def _fake_probe(_llm, usage_meter=None):
        del usage_meter
        return {'id': 'llm', 'status': 'error', 'detail': 'connection refused'}

    monkeypatch.setattr(config_routes_mod, 'probe_llm', _fake_probe)

    response = client.post('/config/llm/test', follow_redirects=False)

    assert response.status_code == 303
    location = response.headers['location']
    assert location.startswith('/config/llm?test_status=error&error=')
    assert 'litellm-main' in location


def test_embeddings_test_route_reports_active_profile_result(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    async def _fake_probe(_embeddings, usage_meter=None):
        del usage_meter
        return {'id': 'embeddings', 'status': 'ok', 'detail': 'ok'}

    monkeypatch.setattr(config_routes_mod, 'probe_embeddings', _fake_probe)

    response = client.post('/config/embeddings/test', follow_redirects=False)

    assert response.status_code == 303
    location = response.headers['location']
    assert location.startswith('/config/embeddings?test_status=ok&info=')
    assert 'litellm-emb' in location


def test_llm_test_route_preserves_return_to_from_referer(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    async def _fake_probe(_llm, usage_meter=None):
        del usage_meter
        return {'id': 'llm', 'status': 'ok', 'detail': 'ok'}

    monkeypatch.setattr(config_routes_mod, 'probe_llm', _fake_probe)

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


def test_additional_config_pages_set_logical_back_url(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    for path in (
        '/config/appearance?return_to=%2Fconfig',
        '/config/language?return_to=%2Fconfig',
        '/config/routing?return_to=%2Fconfig',
        '/config/files?return_to=%2Fconfig',
        '/config/error-interpreter?return_to=%2Fconfig',
        '/config/users?return_to=%2Fconfig',
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "const logical='/config';" in response.text, path


def test_ssh_page_exposes_service_url_helper_and_matching_sftp_create(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/ssh?mode=create&return_to=%2Fconfig')
    nav_response = client.get('/config/connections/ssh?return_to=%2Fconfig')

    assert response.status_code == 200
    assert nav_response.status_code == 200
    assert 'name="service_url"' in response.text
    assert 'data-connection-meta-endpoint="/config/connections/ssh/suggest-metadata"' in response.text
    assert 'data-connection-meta-source-fields="service_url"' in response.text
    assert 'name="create_matching_sftp"' in response.text
    assert 'connection-create-link is-active' in nav_response.text


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

    monkeypatch.setattr(config_routes_mod, 'urlopen', lambda *_args, **_kwargs: _FakeResponse())
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
    assert 'German routing and trigger terms' in prompt_blob
    assert 'Preferred language: de' in prompt_blob


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

    monkeypatch.setattr(config_routes_mod, 'urlopen', lambda *_args, **_kwargs: _FakeResponse())
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

    monkeypatch.setattr(config_routes_mod, 'urlopen', lambda *_args, **_kwargs: _FakeResponse())
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


def test_ssh_save_can_create_matching_sftp_profile(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    monkeypatch.setattr(
        config_routes_mod,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )

    response = client.post(
        '/config/connections/save',
        data={
            'connection_ref': 'mgmt-ssh',
            'original_ref': '',
            'host': '10.0.1.5',
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
    assert sftp_row['host'] == '10.0.1.5'
    assert sftp_row['user'] == 'aria'
    assert sftp_row['key_path'] == 'data/ssh_keys/mgmt_ed25519'
    assert sftp_row['title'] == 'Management Server'
    assert sftp_row['aliases'] == ['grafana', 'ops']
    assert sftp_row['tags'] == ['monitoring', 'linux']


def test_sftp_save_persists_service_url(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    monkeypatch.setattr(
        config_routes_mod,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )

    response = client.post(
        '/config/connections/sftp/save',
        data={
            'connection_ref': 'files-sftp',
            'original_ref': '',
            'host': '10.0.1.9',
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
    assert sftp_row['host'] == '10.0.1.9'
    assert sftp_row['root_path'] == '/data'
