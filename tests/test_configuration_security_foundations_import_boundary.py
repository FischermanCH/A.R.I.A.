from __future__ import annotations

import importlib
from pathlib import Path

import yaml


MODULE_PAIRS = (
    ("aria.modules.configuration_foundations.config", "aria.modules.configuration_foundations.config"),
    ("aria.modules.security_storage.secure_store", "aria.modules.security_storage.secure_store"),
    ("aria.modules.security_storage.migrate", "aria.modules.security_storage.migrate"),
    ("aria.modules.security_storage.user_admin", "aria.modules.security_storage.user_admin"),
)


def test_legacy_configuration_and_security_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_security_store_contract_uses_only_temporary_database(tmp_path: Path) -> None:
    secure_store = importlib.import_module("aria.modules.security_storage.secure_store")
    key = secure_store.generate_master_key_b64()
    assert len(secure_store.decode_master_key(key)) == 32

    store = secure_store.SecureConfigStore(
        secure_store.SecureStoreConfig(db_path=tmp_path / "auth" / "secure.sqlite"),
        secure_store.decode_master_key(key),
    )
    store.set_secret("llm.api_key", "secret-value")
    assert store.get_secret("llm.api_key") == "secret-value"
    assert store.list_secret_keys() == ["llm.api_key"]

    store.upsert_user("alice", "hash", role="admin")
    store.set_user_active("alice", False)
    store.rename_user("alice", "aria-admin")
    assert store.get_user("aria-admin") == {
        "username": "aria-admin",
        "password_hash": "hash",
        "role": "admin",
        "active": False,
    }


def test_secure_migration_contract_uses_only_temporary_tree(tmp_path: Path) -> None:
    migrate = importlib.import_module("aria.modules.security_storage.migrate")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "llm": {"model": "fake", "api_key": "llm-secret"},
            "embeddings": {"api_key": "embed-secret"},
            "memory": {"qdrant_api_key": "qdrant-secret"},
            "security": {"db_path": "data/auth/secure.sqlite"},
        }),
        encoding="utf-8",
    )

    result = migrate.migrate(config_path, strip=True)
    migrated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert result["migrated"] == 3
    assert migrated["llm"]["api_key"] == ""
    assert migrated["embeddings"]["api_key"] == ""
    assert migrated["memory"]["qdrant_api_key"] == ""
    assert (tmp_path / "data" / "auth" / "secure.sqlite").is_file()
    assert list(config_dir.glob("config.yaml.bak.*"))
