from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.templating import Jinja2Templates

from aria.core.config_backup import (
    BACKUP_SCHEMA_VERSION,
    build_config_backup_payload,
    parse_config_backup_payload,
    restore_config_backup_payload,
)
from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, generate_master_key_b64
from aria.core.secure_store import decode_master_key
from aria.web.config_routes import ConfigRouteDeps, register_config_routes


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def _make_store(db_path: Path) -> SecureConfigStore:
    return SecureConfigStore(
        config=SecureStoreConfig(db_path=db_path, enabled=True),
        master_key=decode_master_key(generate_master_key_b64()),
    )


def _seed_source_tree(base_dir: Path) -> tuple[dict, SecureConfigStore]:
    raw = {
        "aria": {"host": "0.0.0.0", "port": 8800},
        "ui": {"title": "Source ARIA", "theme": "matrix"},
        "security": {"enabled": True, "db_path": "data/auth/aria_secure.sqlite"},
    }
    _write_yaml(base_dir / "config" / "config.yaml", raw)
    (base_dir / "prompts" / "skills").mkdir(parents=True, exist_ok=True)
    (base_dir / "prompts" / "persona.md").write_text("Source persona\n", encoding="utf-8")
    (base_dir / "prompts" / "skills" / "deploy.md").write_text("Deploy prompt\n", encoding="utf-8")
    (base_dir / "config" / "error_interpreter.yaml").write_text("rules: source\n", encoding="utf-8")
    skill_dir = base_dir / "data" / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "deploy.json").write_text(
        json.dumps(
            {
                "id": "deploy",
                "name": "Deploy",
                "description": "Deployment helper",
                "prompt_file": "prompts/skills/deploy.md",
                "router_keywords": ["deploy"],
                "steps": [
                    {
                        "id": "s1",
                        "name": "Send status",
                        "type": "chat_send",
                        "params": {"message": "Deployment started."},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    store = _make_store(base_dir / "data" / "auth" / "aria_secure.sqlite")
    store.set_secret("llm.api_key", "source-llm-key")
    store.set_secret("channels.api.auth_token", "source-api-token")
    store.upsert_user("neo", "hash-neo", role="admin")
    store.set_user_active("neo", True)
    return raw, store


def test_build_config_backup_payload_collects_expected_sections(tmp_path: Path) -> None:
    raw, store = _seed_source_tree(tmp_path)

    payload = build_config_backup_payload(
        base_dir=tmp_path,
        raw_config=raw,
        secure_store=store,
        error_interpreter_path=tmp_path / "config" / "error_interpreter.yaml",
    )

    assert payload["schema_version"] == BACKUP_SCHEMA_VERSION
    assert payload["config"]["ui"]["title"] == "Source ARIA"
    assert payload["secure_store"]["secrets"]["llm.api_key"] == "source-llm-key"
    assert payload["secure_store"]["users"][0]["username"] == "neo"
    assert payload["prompt_files"]["prompts/persona.md"] == "Source persona\n"
    assert payload["support_files"]["config/error_interpreter.yaml"] == "rules: source\n"
    assert payload["custom_skills"][0]["id"] == "deploy"


def test_restore_config_backup_payload_replaces_existing_config_snapshot(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_raw, source_store = _seed_source_tree(source_dir)
    payload = build_config_backup_payload(
        base_dir=source_dir,
        raw_config=source_raw,
        secure_store=source_store,
        error_interpreter_path=source_dir / "config" / "error_interpreter.yaml",
    )

    old_raw = {
        "aria": {"host": "127.0.0.1", "port": 8810},
        "ui": {"title": "Old Target"},
        "security": {"enabled": True, "db_path": "data/auth/aria_secure.sqlite"},
    }
    _write_yaml(target_dir / "config" / "config.yaml", old_raw)
    (target_dir / "prompts" / "skills").mkdir(parents=True, exist_ok=True)
    (target_dir / "prompts" / "persona.md").write_text("Old persona\n", encoding="utf-8")
    (target_dir / "config" / "error_interpreter.yaml").write_text("rules: old\n", encoding="utf-8")
    target_skill_dir = target_dir / "data" / "skills"
    target_skill_dir.mkdir(parents=True, exist_ok=True)
    (target_skill_dir / "old.json").write_text('{"id":"old","name":"Old"}\n', encoding="utf-8")
    target_store = _make_store(target_dir / "data" / "auth" / "aria_secure.sqlite")
    target_store.set_secret("llm.api_key", "old-key")
    target_store.upsert_user("legacy", "legacy-hash", role="user")

    def _write_target_raw(data: dict) -> None:
        _write_yaml(target_dir / "config" / "config.yaml", data)

    def _get_target_store(_raw: dict | None = None) -> SecureConfigStore:
        return target_store

    summary = restore_config_backup_payload(
        base_dir=target_dir,
        payload=payload,
        write_raw_config=_write_target_raw,
        get_secure_store=_get_target_store,
        error_interpreter_path=target_dir / "config" / "error_interpreter.yaml",
    )

    restored = yaml.safe_load((target_dir / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert restored["ui"]["title"] == "Source ARIA"
    assert target_store.get_secret("llm.api_key") == "source-llm-key"
    assert target_store.get_secret("channels.api.auth_token") == "source-api-token"
    assert target_store.get_user("neo") is not None
    assert target_store.get_user("legacy") is None
    assert (target_dir / "data" / "skills" / "deploy.json").exists()
    assert not (target_dir / "data" / "skills" / "old.json").exists()
    assert (target_dir / "prompts" / "persona.md").read_text(encoding="utf-8") == "Source persona\n"
    assert (target_dir / "config" / "error_interpreter.yaml").read_text(encoding="utf-8") == "rules: source\n"
    assert summary["custom_skill_count"] == 1


def test_parse_config_backup_payload_rejects_invalid_prompt_paths() -> None:
    bad_payload = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "config": {"ui": {"title": "Broken"}},
        "secure_store": {"secrets": {}, "users": []},
        "custom_skills": [],
        "prompt_files": {"../escape.md": "nope"},
        "support_files": {},
    }

    try:
        parse_config_backup_payload(json.dumps(bad_payload))
    except ValueError as exc:
        assert "allowed area" in str(exc)
    else:
        raise AssertionError("Invalid backup payload should be rejected")


def _build_test_config_app(base_dir: Path) -> FastAPI:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    store = _make_store(base_dir / "data" / "auth" / "aria_secure.sqlite")
    raw = {
        "aria": {"host": "0.0.0.0", "port": 8800},
        "ui": {"title": "Config Test"},
        "security": {"enabled": True, "db_path": "data/auth/aria_secure.sqlite"},
    }
    _write_yaml(base_dir / "config" / "config.yaml", raw)
    (base_dir / "config" / "error_interpreter.yaml").write_text("rules: test\n", encoding="utf-8")

    async def _keyword_stub(*_args, **_kwargs) -> list[str]:
        return []

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.can_access_advanced_config = True
        request.state.lang = "en"
        request.state.cookie_names = {}
        request.state.csrf_token = "test-csrf"
        return await call_next(request)

    def _read_raw() -> dict:
        return yaml.safe_load((base_dir / "config" / "config.yaml").read_text(encoding="utf-8"))

    def _write_raw(data: dict) -> None:
        _write_yaml(base_dir / "config" / "config.yaml", data)

    deps = ConfigRouteDeps(
        templates=templates,
        base_dir=base_dir,
        error_interpreter_path=base_dir / "config" / "error_interpreter.yaml",
        llm_provider_presets={},
        auth_cookie="auth",
        lang_cookie="lang",
        username_cookie="user",
        memory_collection_cookie="memory",
        auth_session_max_age_seconds=3600,
        get_settings=lambda: SimpleNamespace(ui=SimpleNamespace(title="ARIA Test")),
        get_pipeline=lambda: SimpleNamespace(),
        get_username_from_request=lambda request: "neo",
        get_auth_session_from_request=lambda request: {"username": "neo", "role": "admin"},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        sanitize_username=lambda value: str(value or "").strip(),
        sanitize_connection_name=lambda value: str(value or "").strip(),
        sanitize_skill_id=lambda value: str(value or "").strip(),
        sanitize_profile_name=lambda value: str(value or "").strip(),
        default_memory_collection_for_user=lambda _user: "default",
        encode_auth_session=lambda user, role: f"{user}:{role}",
        get_auth_manager=lambda: None,
        active_admin_count=lambda rows: len(rows),
        read_raw_config=_read_raw,
        write_raw_config=_write_raw,
        reload_runtime=lambda: None,
        read_error_interpreter_raw=lambda: (base_dir / "config" / "error_interpreter.yaml").read_text(encoding="utf-8"),
        parse_lines=lambda text: [line.strip() for line in text.splitlines() if line.strip()],
        is_ollama_model=lambda model: str(model or "").startswith("ollama"),
        resolve_prompt_file=lambda rel: (base_dir / rel).resolve(),
        list_prompt_files=lambda: [],
        list_editable_files=lambda: [],
        resolve_edit_file=lambda rel: (base_dir / rel).resolve(),
        list_file_editor_entries=lambda: [],
        resolve_file_editor_file=lambda rel: (base_dir / rel).resolve(),
        load_models_from_api_base=lambda *_args, **_kwargs: [],
        get_profiles=lambda _raw, _kind: {},
        get_active_profile_name=lambda _raw, _kind: "",
        set_active_profile=lambda _raw, _kind, _profile: None,
        get_secure_store=lambda _raw=None: store,
        lang_flag=lambda code: code,
        lang_label=lambda code: code.upper(),
        available_languages=lambda: ["en", "de"],
        resolve_lang=lambda code, default_lang="de": code or default_lang,
        clear_i18n_cache=lambda: None,
        load_custom_skill_manifests=lambda: ([], []),
        custom_skill_file=lambda skill_id: (base_dir / "data" / "skills" / f"{skill_id}.json").resolve(),
        save_custom_skill_manifest=lambda raw: raw,
        refresh_skill_trigger_index=lambda: {},
        format_skill_routing_info=lambda ref, kind: f"{ref}:{kind}",
        suggest_skill_keywords_with_llm=_keyword_stub,
    )
    register_config_routes(app, deps)
    return app


def test_config_backup_export_route_returns_attachment(tmp_path: Path) -> None:
    app = _build_test_config_app(tmp_path)
    client = TestClient(app)

    response = client.get("/config/backup/export")

    assert response.status_code == 200
    assert "attachment; filename=" in response.headers["content-disposition"]
    payload = response.json()
    assert payload["schema_version"] == BACKUP_SCHEMA_VERSION


def test_config_backup_import_route_restores_backup_and_redirects(tmp_path: Path) -> None:
    app = _build_test_config_app(tmp_path)
    client = TestClient(app)

    payload = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "exported_at": "2026-04-09T00:00:00Z",
        "aria": {"version": "0.1.0", "label": "0.1.0-alpha77"},
        "config": {
            "aria": {"host": "0.0.0.0", "port": 8801},
            "ui": {"title": "Imported Config"},
            "security": {"enabled": True, "db_path": "data/auth/aria_secure.sqlite"},
        },
        "secure_store": {
            "enabled": True,
            "secrets": {"llm.api_key": "imported-key"},
            "users": [{"username": "imported-admin", "password_hash": "hash", "role": "admin", "active": True}],
        },
        "custom_skills": [],
        "prompt_files": {"prompts/persona.md": "Imported persona\n"},
        "support_files": {"config/error_interpreter.yaml": "rules: imported\n"},
    }

    response = client.post(
        "/config/backup/import",
        files={"backup_file": ("aria-config-backup.json", json.dumps(payload).encode("utf-8"), "application/json")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/config/backup?saved=1&info=backup_imported"
    restored = yaml.safe_load((tmp_path / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert restored["ui"]["title"] == "Imported Config"
    assert (tmp_path / "prompts" / "persona.md").read_text(encoding="utf-8") == "Imported persona\n"
