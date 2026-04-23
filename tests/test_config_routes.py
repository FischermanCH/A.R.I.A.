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
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
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
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Einstellungen Navigation"' in response.text
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
    assert '/config/workbench/routing?scope=default' in response.text
    assert 'Routing Testbench' not in response.text


def test_routing_page_redirects_legacy_testbench_queries_to_workbench(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get(
        '/config/routing?routing_query=Run+uptime+on+pihole1&routing_kind=ssh&routing_llm_qdrant_only=1',
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers['location'].startswith('/config/workbench/routing?')
    assert 'routing_query=Run+uptime+on+pihole1' in response.headers['location']
    assert 'routing_kind=ssh' in response.headers['location']
    assert 'routing_llm_qdrant_only=1' in response.headers['location']


def test_config_page_shows_routing_workbench_link(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config')

    assert response.status_code == 200
    assert 'aria-label="Settings navigation"' in response.text or 'aria-label="Settings Navigation"' in response.text
    assert 'href="/config/intelligence"' in response.text
    assert 'href="/config/persona"' in response.text
    assert 'href="/config/access"' in response.text
    assert 'href="/config/operations"' in response.text
    assert 'href="/config/workbench"' in response.text
    assert 'Routing Workbench' not in response.text
    assert 'litellm-main' in response.text
    assert 'litellm-emb' in response.text
    assert 'The currently active chat-brain profile for answers and tool decisions.' in response.text
    assert 'Memory Triggers & Routing' not in response.text
    assert 'Skill Triggers & Routing' not in response.text


def test_routing_workbench_page_renders_action_planner_dry_run(monkeypatch, tmp_path: Path) -> None:
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

    async def fake_test_query(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "status": "ok",
            "visual_status": "ok",
            "message": "Deterministic routing matched ssh/pihole1 via alias.",
            "query": "pruef mal den pi-hole",
            "preferred_kind": "ssh",
            "requested_preferred_kind": "auto",
            "inferred_preferred_kind": "ssh",
            "available_counts": {"ssh": 1},
            "llm_ignore_deterministic": False,
            "deterministic": {"found": True, "kind": "ssh", "ref": "pihole1", "source": "alias", "score": 1000.0, "reason": "pi-hole"},
            "qdrant": {"enabled": True, "message": "", "error": "", "candidate_count": 1, "accepted_count": 1, "candidates": []},
            "decision": {"found": True, "kind": "ssh", "ref": "pihole1", "source": "alias", "score": 1000.0, "reason": "pi-hole"},
            "llm_debug": {"available": True, "used": True, "status": "ok", "visual_status": "ok", "message": "LLM router debug selected ssh/pihole1.", "decision": {"found": True, "kind": "ssh", "ref": "pihole1", "reason": "fits"}, "confidence": "high", "ask_user": False},
            "action_debug": {
                "available": True,
                "used": True,
                "status": "ok",
                "visual_status": "ok",
                "message": "LLM action planner selected template/ssh_health_check.",
                "target_context": "ssh/pihole1",
                "target_reason": "pi-hole",
                "decision": {
                    "found": True,
                    "candidate_kind": "template",
                    "candidate_kind_label": "Template",
                    "candidate_id": "ssh_health_check",
                    "title": "SSH Health Check",
                    "intent": "health_check",
                    "intent_label": "Health check",
                    "capability": "ssh_command",
                    "capability_label": "SSH command",
                    "summary_line": "Template: Health check via SSH command on ssh/pihole1",
                    "inputs": {"command": "uptime"},
                    "input_items": [{"key": "command", "key_label": "Command", "value": "uptime"}],
                    "score": 0.98,
                    "execution_state": "ready",
                    "execution_state_label": "Ready",
                    "preview": "SSH command: uptime",
                    "reason": "health check fits",
                },
                "confidence": "high",
                "confidence_label": "High",
                "ask_user": False,
                "execution_state": "ready",
                "execution_state_label": "Ready",
                "planner_source": "llm",
                "planner_source_label": "LLM",
                "missing_input": "",
                "missing_input_label": "",
                "clarifying_question": "",
                "candidates": [
                    {
                        "candidate_kind": "template",
                        "candidate_kind_label": "Template",
                        "candidate_id": "ssh_health_check",
                        "title": "SSH Health Check",
                        "intent": "health_check",
                        "intent_label": "Health check",
                        "capability": "ssh_command",
                        "capability_label": "SSH command",
                        "summary_line": "Template: Health check via SSH command",
                        "inputs": {"command": "uptime"},
                        "input_items": [{"key": "command", "key_label": "Command", "value": "uptime"}],
                        "execution_state": "ready",
                        "execution_state_label": "Ready",
                        "missing_input": "",
                        "summary": "Runs a lightweight health or status check on the target host.",
                        "preview": "SSH command: uptime",
                        "score": 0.98,
                    },
                    {
                        "candidate_kind": "template",
                        "candidate_kind_label": "Template",
                        "candidate_id": "ssh_run_command",
                        "title": "SSH Run Command",
                        "intent": "run_command",
                        "intent_label": "Run command",
                        "capability": "ssh_command",
                        "capability_label": "SSH command",
                        "summary_line": "Template: Run command via SSH command",
                        "inputs": {},
                        "execution_state": "needs_input",
                        "execution_state_label": "Needs input",
                        "missing_input": "command",
                        "missing_input_label": "Command",
                        "clarifying_question": "Which command should ARIA run on this target?",
                        "summary": "Runs a direct command on the target host when the request names a concrete command.",
                        "preview": "SSH command from the user request",
                        "example_prompt": 'Run "df -h" on pihole1',
                        "input_items": [],
                        "score": 0.74,
                    }
                ],
            },
            "payload_debug": {
                "available": True,
                "used": True,
                "status": "ok",
                "visual_status": "ok",
                "message": "Payload dry-run built a concrete executor payload.",
                "payload": {
                    "found": True,
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "connection_ref": "pihole1",
                    "path": "",
                    "content": "uptime",
                    "missing_fields": [],
                    "preview": "SSH command: uptime",
                },
            },
            "safety_debug": {
                "available": True,
                "used": True,
                "status": "ok",
                "visual_status": "ok",
                "message": "Guardrail / confirm dry-run would allow execution.",
                "decision": {
                    "action": "allow",
                    "reason": "safe_health_check",
                    "guardrail_ref": "safe-ssh",
                },
            },
            "execution_debug": {
                "available": True,
                "used": True,
                "status": "ok",
                "visual_status": "ok",
                "message": "Would execute with the current dry-run plan.",
                "decision": {
                    "next_step": "allow",
                    "target": "ssh/pihole1",
                    "capability": "ssh_command",
                    "preview": "SSH command: uptime",
                },
            },
            "executed": False,
        }

    monkeypatch.setattr(config_routes_mod, "build_connection_routing_index_status", fake_status)
    monkeypatch.setattr(config_routes_mod, "test_connection_routing_query", fake_test_query)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/workbench/routing?routing_query=pruef+mal+den+pi-hole')

    assert response.status_code == 200
    assert 'Action / Skill' in response.text
    assert 'ssh/pihole1' in response.text
    assert 'pi-hole' in response.text
    assert 'SSH Health Check' in response.text
    assert 'ssh_health_check' in response.text
    assert 'SSH command' in response.text
    assert 'Template: Health check via SSH command on ssh/pihole1' in response.text
    assert 'Template: Run command via SSH command' in response.text
    assert 'Ready' in response.text
    assert 'Command=uptime' in response.text
    assert 'SSH command: uptime' in response.text
    assert 'Template' in response.text
    assert 'High' in response.text
    assert 'Health check' in response.text
    assert 'Run command' in response.text
    assert 'LLM' in response.text
    assert '0.980' in response.text
    assert '0.740' in response.text
    assert 'Needs input' in response.text
    assert 'Command' in response.text
    assert 'Which command should ARIA run on this target?' in response.text
    assert 'df -h' in response.text
    assert 'on pihole1' in response.text
    assert 'Decision identifier' in response.text
    assert 'Decision score' in response.text
    assert 'Decision reason' in response.text
    assert 'Payload dry-run' in response.text or 'Payload Dry-run' in response.text
    assert 'safe-ssh' in response.text
    assert 'Final execution preview' in response.text or 'Finale Ausfuehrungsvorschau' in response.text
    assert 'allow' in response.text


def test_routing_workbench_page_renders_action_planner_follow_up_question(monkeypatch, tmp_path: Path) -> None:
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

    async def fake_test_query(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "status": "warn",
            "visual_status": "warn",
            "message": "Qdrant routing candidate selected sftp/mgmt.",
            "query": "lies die datei vom management server",
            "preferred_kind": "sftp",
            "requested_preferred_kind": "auto",
            "inferred_preferred_kind": "sftp",
            "available_counts": {"sftp": 1},
            "llm_ignore_deterministic": False,
            "deterministic": {"found": True, "kind": "sftp", "ref": "mgmt", "source": "alias", "score": 1000.0, "reason": "management server"},
            "qdrant": {"enabled": True, "message": "", "error": "", "candidate_count": 1, "accepted_count": 1, "candidates": []},
            "decision": {"found": True, "kind": "sftp", "ref": "mgmt", "source": "alias", "score": 1000.0, "reason": "management server"},
            "llm_debug": {"available": True, "used": True, "status": "ok", "visual_status": "ok", "message": "LLM router debug selected sftp/mgmt.", "decision": {"found": True, "kind": "sftp", "ref": "mgmt", "reason": "fits"}, "confidence": "high", "ask_user": False},
            "action_debug": {
                "available": False,
                "used": False,
                "status": "warn",
                "visual_status": "warn",
                "message": "Action dry-run recommends asking the user before execution.",
                "target_context": "sftp/mgmt",
                "target_reason": "management server",
                "decision": {
                    "found": True,
                    "candidate_kind": "template",
                    "candidate_kind_label": "Template",
                    "candidate_id": "sftp_read_file",
                    "title": "SFTP Read File",
                    "intent": "read_file",
                    "intent_label": "Read file",
                    "capability": "file_read",
                    "capability_label": "Read file",
                    "summary_line": "Template: Read file on sftp/mgmt",
                    "inputs": {},
                    "input_items": [],
                    "score": 0.91,
                    "execution_state": "needs_input",
                    "execution_state_label": "Needs input",
                    "preview": "Read remote file via SFTP",
                    "reason": "Missing required remote_path.",
                },
                "confidence": "low",
                "confidence_label": "Low",
                "ask_user": True,
                "execution_state": "needs_input",
                "execution_state_label": "Needs input",
                "planner_source": "heuristic",
                "planner_source_label": "Heuristic",
                "missing_input": "remote_path",
                "missing_input_label": "Remote path",
                "clarifying_question": "Which remote path should ARIA read?",
                "example_prompt": "Read /etc/hosts from the management server",
                "candidates": [
                    {
                        "candidate_kind": "template",
                        "candidate_kind_label": "Template",
                        "candidate_id": "sftp_read_file",
                        "title": "SFTP Read File",
                        "intent": "read_file",
                        "intent_label": "Read file",
                        "capability": "file_read",
                        "capability_label": "Read file",
                        "summary_line": "Template: Read file",
                        "inputs": {},
                        "input_items": [],
                        "execution_state": "needs_input",
                        "execution_state_label": "Needs input",
                        "missing_input": "remote_path",
                        "missing_input_label": "Remote path",
                        "clarifying_question": "Which remote path should ARIA read?",
                        "summary": "Reads a remote file from the target system.",
                        "preview": "Read remote file via SFTP",
                        "example_prompt": "Read /etc/hosts from the management server",
                        "score": 0.91,
                    }
                ],
            },
            "payload_debug": {
                "available": True,
                "used": True,
                "status": "warn",
                "visual_status": "warn",
                "message": "Payload dry-run still needs one or more parameters.",
                "payload": {
                    "found": True,
                    "capability": "file_read",
                    "connection_kind": "sftp",
                    "connection_ref": "mgmt",
                    "path": "",
                    "content": "",
                    "missing_fields": ["path"],
                    "preview": "Remote file path still missing",
                },
            },
            "safety_debug": {
                "available": True,
                "used": True,
                "status": "warn",
                "visual_status": "warn",
                "message": "Guardrail / confirm dry-run would ask before execution.",
                "decision": {
                    "action": "ask_user",
                    "reason": "missing_parameters",
                    "guardrail_ref": "",
                },
            },
            "execution_debug": {
                "available": True,
                "used": True,
                "status": "warn",
                "visual_status": "warn",
                "message": "Would ask the user before executing this plan.",
                "decision": {
                    "next_step": "ask_user",
                    "target": "sftp/mgmt",
                    "capability": "file_read",
                    "preview": "Remote file path still missing",
                },
            },
            "executed": False,
        }

    monkeypatch.setattr(config_routes_mod, "build_connection_routing_index_status", fake_status)
    monkeypatch.setattr(config_routes_mod, "test_connection_routing_query", fake_test_query)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/workbench/routing?routing_query=lies+die+datei+vom+management+server')

    assert response.status_code == 200
    assert 'sftp/mgmt' in response.text
    assert 'management server' in response.text
    assert 'SFTP Read File' in response.text
    assert 'Template: Read file on sftp/mgmt' in response.text
    assert 'Template: Read file' in response.text
    assert 'Remote path' in response.text
    assert 'Read file' in response.text
    assert 'Needs input' in response.text
    assert 'Low' in response.text
    assert 'Read file' in response.text
    assert 'Which remote path should ARIA read?' in response.text
    assert 'Read /etc/hosts from the management server' in response.text
    assert 'Heuristic' in response.text
    assert '0.910' in response.text
    assert 'missing_parameters' in response.text
    assert 'ask_user' in response.text


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


def test_routing_workbench_page_shows_testbench_result(monkeypatch, tmp_path: Path) -> None:
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

    async def fake_test(
        _settings: object,
        query: str,
        *,
        preferred_kind: str = "auto",
        llm_ignore_deterministic: bool = False,
        llm_client: object | None = None,
        language: str = "",
    ) -> dict[str, object]:
        assert query == "Run uptime on pihole1"
        assert preferred_kind == "ssh"
        assert llm_ignore_deterministic is True
        assert llm_client is None
        assert language == "en"
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
            "llm_debug": {
                "available": True,
                "used": True,
                "status": "ok",
                "visual_status": "ok",
                "message": "LLM router debug selected ssh/pihole1.",
                "mode": "qdrant_only",
                "confidence": "high",
                "ask_user": False,
                "decision": {
                    "found": True,
                    "kind": "ssh",
                    "ref": "pihole1",
                    "source": "router_llm_debug",
                    "score": 0.0,
                    "reason": "exact match wins",
                    "capability": "ssh_command",
                },
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

    response = client.get('/config/workbench/routing?routing_query=Run+uptime+on+pihole1&routing_kind=ssh&routing_llm_qdrant_only=1')

    assert response.status_code == 200
    assert 'Routing Testbench' in response.text
    assert 'ssh/pihole1' in response.text
    assert 'Dry-run' in response.text
    assert 'LLM router dry-run' in response.text
    assert 'exact match wins' in response.text
    assert 'Qdrant + LLM only' in response.text


def test_routing_index_test_json_route(monkeypatch, tmp_path: Path) -> None:
    async def fake_test(
        _settings: object,
        query: str,
        *,
        preferred_kind: str = "auto",
        llm_ignore_deterministic: bool = False,
        llm_client: object | None = None,
        language: str = "",
    ) -> dict[str, object]:
        assert llm_ignore_deterministic is True
        assert llm_client is None
        assert language == "en"
        return {
            "status": "warn",
            "message": "No routing target matched.",
            "query": query,
            "preferred_kind": preferred_kind,
            "decision": {"found": False},
        }

    monkeypatch.setattr(config_routes_mod, "test_connection_routing_query", fake_test)
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/routing-index/test?query=foo&preferred_kind=ssh&llm_qdrant_only=1')

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


def test_config_appearance_lists_dynamic_background_files(tmp_path: Path) -> None:
    static_dir = tmp_path / "aria" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "background-8-bit-arcade.png").write_bytes(b"png")
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/appearance?return_to=%2Fconfig')

    assert response.status_code == 200
    assert 'value="8-bit-arcade"' in response.text
    assert '8-Bit Arcade' in response.text


def test_additional_config_pages_set_logical_back_url(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    for path in (
        '/config/appearance?return_to=%2Fconfig',
        '/config/language?return_to=%2Fconfig',
        '/config/routing?return_to=%2Fconfig',
        '/config/files?return_to=%2Fconfig',
        '/config/error-interpreter?return_to=%2Fconfig',
        '/config/users?return_to=%2Fconfig#admin-mode',
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "const logical='/config';" in response.text, path


def test_users_debug_save_route_is_available_from_users_surface(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.post(
        "/config/users/debug-save",
        data={"debug_mode": "1", "return_to": "/config/access"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/config/users?saved=1")
    assert "return_to=%2Fconfig%2Faccess" in response.headers["location"]


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

    monkeypatch.setattr(config_routes_mod, 'urlopen', lambda *_args, **_kwargs: _FakeResponse())
    monkeypatch.setattr(
        config_routes_mod,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )
    client.app.state.test_pipeline.llm_client = _FakeLLM()

    response = client.post(
        '/config/connections/save',
        data={
            'connection_ref': 'grafana-ssh',
            'original_ref': '',
            'host': '10.0.1.5',
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

    monkeypatch.setattr(config_routes_mod, 'urlopen', lambda *_args, **_kwargs: _FakeResponse())
    monkeypatch.setattr(
        config_routes_mod,
        'build_connection_status_row',
        lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'},
    )
    client.app.state.test_pipeline.llm_client = _FakeLLM()

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


def test_connections_overview_page_is_available_as_top_level_hub(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/connections')

    assert response.status_code == 200
    assert 'Connections' in response.text
    assert 'aria-label="Verbindungs-Navigation"' in response.text or 'aria-label="Connections navigation"' in response.text
    assert 'Next steps' not in response.text
    assert 'Nächste Schritte' not in response.text
    assert 'Create first connection' not in response.text
    assert 'Erste Verbindung anlegen' not in response.text
    assert 'href="/connections/status"' in response.text
    assert 'href="/connections/types"' in response.text
    assert 'href="/connections/templates"' in response.text
    assert 'href="/config/connections/searxng?return_to=%2Fconnections"' in response.text


def test_connections_subpages_render_with_surface_specific_targets(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    status_response = client.get('/connections/status')
    assert status_response.status_code == 200
    assert 'Live status of all configured connections' in status_response.text or 'Live-Status aller konfigurierten Verbindungen' in status_response.text

    types_response = client.get('/connections/types')
    assert types_response.status_code == 200
    assert '/config/connections/ssh?return_to=/connections/types' in types_response.text
    assert 'SearXNG' in types_response.text
    assert 'Beobachtete Webseiten' in types_response.text or 'Watched Websites' in types_response.text
    assert 'Google Calendar' in types_response.text
    assert types_response.text.index('Beobachtete Webseiten' if 'Beobachtete Webseiten' in types_response.text else 'Watched Websites') < types_response.text.index('Google Calendar')
    assert types_response.text.index('SearXNG') < types_response.text.index('Google Calendar')

    templates_response = client.get('/connections/templates')
    assert templates_response.status_code == 200
    assert 'name="return_to" value="/connections/templates"' in templates_response.text


def test_settings_page_groups_system_areas_without_connections_block(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config')

    assert response.status_code == 200
    assert '/config/intelligence' in response.text
    assert '/config/persona' in response.text
    assert '/config/access' in response.text
    assert '/config/operations' in response.text
    assert '/config/workbench' in response.text
    assert 'memory-health-grid' in response.text
    assert '/config/connections/ssh?return_to=%2Fconfig' not in response.text


def test_settings_subpages_link_to_existing_specialist_pages(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    intelligence = client.get('/config/intelligence')
    assert intelligence.status_code == 200
    assert '/config/llm?return_to=/config/intelligence' in intelligence.text
    assert '/config/embeddings?return_to=/config/intelligence' in intelligence.text

    persona = client.get('/config/persona')
    assert persona.status_code == 200
    assert '/config/prompts?return_to=/config/persona' in persona.text
    assert '/config/appearance?return_to=/config/persona' in persona.text
    assert '/config/language?return_to=/config/persona' in persona.text

    access = client.get('/config/access')
    assert access.status_code == 200
    assert '/config/users?return_to=/config/access#admin-mode' in access.text
    assert '/config/security?return_to=/config/access' in access.text

    operations = client.get('/config/operations')
    assert operations.status_code == 200
    assert '/updates?return_to=/config/operations' in operations.text
    assert '/config/logs?return_to=/config/operations' in operations.text
    assert '/config/backup?return_to=/config/operations' in operations.text

    workbench = client.get('/config/workbench')
    assert workbench.status_code == 200
    assert '/config/workbench/routing?return_to=/config/workbench' in workbench.text
    assert '/config/files?return_to=/config/workbench' in workbench.text
    assert '/config/error-interpreter?return_to=/config/workbench' in workbench.text


def test_config_operations_page_shows_service_restart_controls(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    monkeypatch.setattr(config_routes_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005
    monkeypatch.setattr(
        config_routes_mod,
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
    assert "SearXNG neu starten" in response.text or "Restart SearXNG" in response.text
    assert 'action="/config/operations/service-restart"' in response.text
    assert "kontrolliert neu starten" in response.text or "Restart Qdrant now?" in response.text


def test_config_operations_service_restart_triggers_helper(monkeypatch, tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)
    called: dict[str, str] = {}
    monkeypatch.setattr(config_routes_mod, "resolve_update_helper_config", lambda secure_store=None: SimpleNamespace(enabled=True))  # noqa: ARG005

    def _trigger(_config, service: str, timeout: float = 2.5) -> dict[str, object]:  # noqa: ARG001
        called["service"] = service
        return {"status": "accepted"}

    monkeypatch.setattr(config_routes_mod, "trigger_update_helper_service_restart", _trigger)

    response = client.post(
        '/config/operations/service-restart',
        data={"service": "qdrant", "csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert called["service"] == "qdrant"
    assert response.headers["location"].startswith("/config/operations?saved=1&info=")


def test_google_calendar_connection_page_renders(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get("/config/connections/google-calendar?mode=create&return_to=%2Fconnections%2Ftypes")

    assert response.status_code == 200
    assert "Google Calendar" in response.text
    assert "/config/connections/google-calendar/save" in response.text
    assert "OAuth Playground" in response.text
    assert "https://developers.google.com/oauthplayground/" in response.text
    assert "https://console.cloud.google.com/auth/clients" in response.text
    assert "https://www.googleapis.com/auth/calendar.readonly" in response.text
    assert "Recommended flow" not in response.text
    assert "Empfohlener Ablauf" not in response.text


def test_searxng_connection_page_prefills_local_stack_defaults(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    response = client.get('/config/connections/searxng?mode=create')

    assert response.status_code == 200
    assert 'value="web-search"' in response.text
    assert 'Standardprofil fuer allgemeine Websuche' in response.text or 'Default profile for general web search' in response.text
    assert 'websuche, internet, suche' in response.text or 'web search, internet, search' in response.text


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


def test_website_save_autofills_metadata_and_group(monkeypatch, tmp_path: Path) -> None:
    import aria.web.connection_reader_helpers as connection_reader_helpers_mod

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
    monkeypatch.setattr(config_routes_mod, 'build_connection_status_row', lambda *_args, **_kwargs: {'status': 'ok', 'message': 'ok'})

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
    assert row['group_name'] == 'Dokumentation'
