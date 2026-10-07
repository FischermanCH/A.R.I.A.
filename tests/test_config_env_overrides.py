from __future__ import annotations

from pathlib import Path

import yaml

from aria.modules.configuration_foundations.config import load_settings


def _write_config(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_web_llm_search_context_size_defaults_to_high(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, {"llm": {"model": "test/model"}, "security": {"enabled": False}})

    settings = load_settings(config_path)

    assert settings.web_llm.search_context_size == "high"


def test_web_llm_search_context_size_accepts_env_override(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, {"llm": {"model": "test/model"}, "security": {"enabled": False}})
    monkeypatch.setenv("ARIA_WEB_LLM_SEARCH_CONTEXT_SIZE", "medium")

    settings = load_settings(config_path)

    assert settings.web_llm.search_context_size == "medium"


def test_web_llm_search_context_size_invalid_env_uses_default(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, {"llm": {"model": "test/model"}, "security": {"enabled": False}})
    monkeypatch.setenv("ARIA_WEB_LLM_SEARCH_CONTEXT_SIZE", "unsupported")

    settings = load_settings(config_path)

    assert settings.web_llm.search_context_size == "high"


def test_env_llm_overrides_do_not_clobber_active_saved_profiles(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.yaml"
    _write_config(
        config_path,
        {
            "aria": {"host": "0.0.0.0", "port": 8800},
            "llm": {
                "model": "anthropic/claude-sonnet-4-5",
                "api_base": "http://192.0.2.30:4000",
                "api_key": "",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout_seconds": 45,
            },
            "embeddings": {
                "model": "text-embedding-3-small",
                "api_base": "http://192.0.2.30:4000",
                "api_key": "",
                "timeout_seconds": 30,
            },
            "profiles": {
                "active": {"llm": "claude-sonnet-4-5", "embeddings": "litellm-emb"},
                "llm": {
                    "claude-sonnet-4-5": {
                        "model": "anthropic/claude-sonnet-4-5",
                        "api_base": "http://192.0.2.30:4000",
                        "api_key": "",
                        "temperature": 0.2,
                        "max_tokens": 2048,
                        "timeout_seconds": 45,
                    }
                },
                "embeddings": {
                    "litellm-emb": {
                        "model": "text-embedding-3-small",
                        "api_base": "http://192.0.2.30:4000",
                        "api_key": "",
                        "timeout_seconds": 30,
                    }
                },
            },
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "security": {"enabled": False},
        },
    )
    monkeypatch.setenv("ARIA_LLM_API_BASE", "http://host.docker.internal:11434")
    monkeypatch.setenv("ARIA_LLM_MODEL", "ollama_chat/qwen3:8b")
    monkeypatch.setenv("ARIA_EMBEDDINGS_API_BASE", "http://host.docker.internal:11434")
    monkeypatch.setenv("ARIA_EMBEDDINGS_MODEL", "ollama/nomic-embed-text")

    settings = load_settings(config_path)

    assert settings.llm.api_base == "http://192.0.2.30:4000"
    assert settings.llm.model == "anthropic/claude-sonnet-4-5"
    assert settings.embeddings.api_base == "http://192.0.2.30:4000"
    assert settings.embeddings.model == "text-embedding-3-small"


def test_web_llm_role_resolves_existing_profile_without_changing_main(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.yaml"
    _write_config(
        config_path,
        {
            "llm": {"model": "stale/model", "api_base": "http://stale.example/v1"},
            "web_llm": {
                "enabled": True,
                "transport": "openai_responses",
                "max_search_uses": 3,
                "capability_verified_at": "2026-09-02T16:13:00Z",
            },
            "profiles": {
                "active": {"llm": "main", "web_llm": "web"},
                "llm": {
                    "main": {
                        "model": "main/model",
                        "api_base": "http://main.example/v1",
                        "api_key": "main-fixture-key",
                    },
                    "web": {
                        "model": "openai/gpt-5.6-luna",
                        "api_base": "https://gateway.example/v1",
                        "api_key": "fixture-key",
                        "max_tokens": 2048,
                        "timeout_seconds": 30,
                    },
                },
            },
            "security": {"enabled": False},
        },
    )

    settings = load_settings(config_path)

    assert settings.llm.model == "main/model"
    assert settings.llm.api_base == "http://main.example/v1"
    assert settings.llm.api_key == "main-fixture-key"
    assert settings.web_llm.enabled is True
    assert settings.web_llm.profile == "web"
    assert settings.web_llm.model == "openai/gpt-5.6-luna"
    assert settings.web_llm.api_key == "fixture-key"
    assert settings.web_llm.max_search_uses == 3


def test_legacy_auto_memory_config_is_ignored(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "llm": {"model": "test/model"},
            "auto_memory": {
                "learning_governor": {
                    "automatic_retention_delete": False,
                    "retention_target_per_source": 77,
                }
            }
        },
    )

    settings = load_settings(config_path)

    assert not hasattr(settings, "auto_memory")
    assert "auto_memory" not in settings.model_dump()


def test_load_settings_ignores_retired_connection_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "llm": {"model": "test/model"},
            "connections": {
                "retired_search_backend": [],
            },
        },
    )

    settings = load_settings(config_path)

    assert not hasattr(settings.connections, "retired_search_backend")


def test_env_llm_overrides_still_apply_without_active_profiles(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.yaml"
    _write_config(
        config_path,
        {
            "aria": {"host": "0.0.0.0", "port": 8800},
            "llm": {
                "model": "anthropic/claude-sonnet-4-5",
                "api_base": "http://192.0.2.30:4000",
                "api_key": "",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout_seconds": 45,
            },
            "embeddings": {
                "model": "text-embedding-3-small",
                "api_base": "http://192.0.2.30:4000",
                "api_key": "",
                "timeout_seconds": 30,
            },
            "profiles": {"active": {}, "llm": {}, "embeddings": {}},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "security": {"enabled": False},
        },
    )
    monkeypatch.setenv("ARIA_LLM_API_BASE", "http://override.example/v1")
    monkeypatch.setenv("ARIA_LLM_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("ARIA_EMBEDDINGS_API_BASE", "http://override.example/v1")
    monkeypatch.setenv("ARIA_EMBEDDINGS_MODEL", "openai/text-embedding-3-small")

    settings = load_settings(config_path)

    assert settings.llm.api_base == "http://override.example/v1"
    assert settings.llm.model == "openai/gpt-4.1-mini"
    assert settings.embeddings.api_base == "http://override.example/v1"
    assert settings.embeddings.model == "openai/text-embedding-3-small"


def test_blank_env_values_do_not_erase_existing_runtime_config(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.yaml"
    _write_config(
        config_path,
        {
            "aria": {"host": "0.0.0.0", "port": 8800},
            "llm": {
                "model": "anthropic/claude-sonnet-4-5",
                "api_base": "http://192.0.2.30:4000",
                "api_key": "",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout_seconds": 45,
            },
            "embeddings": {
                "model": "text-embedding-3-small",
                "api_base": "http://192.0.2.30:4000",
                "api_key": "",
                "timeout_seconds": 30,
            },
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
            "security": {"enabled": False},
        },
    )
    monkeypatch.setenv("ARIA_LLM_API_BASE", "")
    monkeypatch.setenv("ARIA_LLM_MODEL", "")
    monkeypatch.setenv("ARIA_EMBEDDINGS_API_BASE", "")
    monkeypatch.setenv("ARIA_EMBEDDINGS_MODEL", "")

    settings = load_settings(config_path)

    assert settings.llm.api_base == "http://192.0.2.30:4000"
    assert settings.llm.model == "anthropic/claude-sonnet-4-5"
    assert settings.embeddings.api_base == "http://192.0.2.30:4000"
    assert settings.embeddings.model == "text-embedding-3-small"
