from __future__ import annotations

from pathlib import Path

import yaml

from aria.core.config import load_settings


def _write_config(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_env_llm_overrides_do_not_clobber_active_saved_profiles(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.yaml"
    _write_config(
        config_path,
        {
            "aria": {"host": "0.0.0.0", "port": 8800},
            "llm": {
                "model": "anthropic/claude-sonnet-4-5",
                "api_base": "http://172.31.10.210:4000",
                "api_key": "",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout_seconds": 45,
            },
            "embeddings": {
                "model": "text-embedding-3-small",
                "api_base": "http://172.31.10.210:4000",
                "api_key": "",
                "timeout_seconds": 30,
            },
            "profiles": {
                "active": {"llm": "claude-sonnet-4-5", "embeddings": "litellm-emb"},
                "llm": {
                    "claude-sonnet-4-5": {
                        "model": "anthropic/claude-sonnet-4-5",
                        "api_base": "http://172.31.10.210:4000",
                        "api_key": "",
                        "temperature": 0.2,
                        "max_tokens": 2048,
                        "timeout_seconds": 45,
                    }
                },
                "embeddings": {
                    "litellm-emb": {
                        "model": "text-embedding-3-small",
                        "api_base": "http://172.31.10.210:4000",
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

    assert settings.llm.api_base == "http://172.31.10.210:4000"
    assert settings.llm.model == "anthropic/claude-sonnet-4-5"
    assert settings.embeddings.api_base == "http://172.31.10.210:4000"
    assert settings.embeddings.model == "text-embedding-3-small"


def test_env_llm_overrides_still_apply_without_active_profiles(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "config.yaml"
    _write_config(
        config_path,
        {
            "aria": {"host": "0.0.0.0", "port": 8800},
            "llm": {
                "model": "anthropic/claude-sonnet-4-5",
                "api_base": "http://172.31.10.210:4000",
                "api_key": "",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout_seconds": 45,
            },
            "embeddings": {
                "model": "text-embedding-3-small",
                "api_base": "http://172.31.10.210:4000",
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
                "api_base": "http://172.31.10.210:4000",
                "api_key": "",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout_seconds": 45,
            },
            "embeddings": {
                "model": "text-embedding-3-small",
                "api_base": "http://172.31.10.210:4000",
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

    assert settings.llm.api_base == "http://172.31.10.210:4000"
    assert settings.llm.model == "anthropic/claude-sonnet-4-5"
    assert settings.embeddings.api_base == "http://172.31.10.210:4000"
    assert settings.embeddings.model == "text-embedding-3-small"
