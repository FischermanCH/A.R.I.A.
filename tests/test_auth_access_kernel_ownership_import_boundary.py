from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from aria.modules import MODULE_MANIFESTS


MODULE_PAIRS = (
    ("aria.modules.security_storage.auth_manager", "aria.modules.security_storage.auth_manager"),
    ("aria.modules.auth_policy.access_policy", "aria.modules.auth_policy.access_policy"),
)


class FakeUserStore:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, object]] = {}

    def upsert_user(self, username: str, password_hash: str, role: str) -> None:
        self.users[username] = {
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "active": True,
        }

    def get_user(self, username: str) -> dict[str, object] | None:
        return self.users.get(username)


def test_auth_access_legacy_modules_are_identity_aliases() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_production_code_uses_canonical_auth_access_imports() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_auth_manager_contract_with_in_memory_store() -> None:
    auth_module = importlib.import_module("aria.modules.security_storage.auth_manager")
    store = FakeUserStore()
    manager = auth_module.AuthManager(store)

    with pytest.raises(ValueError, match="mindestens 8 Zeichen"):
        manager.upsert_user("short", "1234567")

    manager.upsert_user("alice", "correct-horse", role="admin")
    assert manager.verify("alice", "correct-horse") is True
    assert manager.verify("alice", "wrong-password") is False
    assert manager.verify("missing", "correct-horse") is False
    store.users["alice"]["active"] = False
    assert manager.verify("alice", "correct-horse") is False


def test_auth_policy_contract_remains_bounded() -> None:
    policy = importlib.import_module("aria.modules.auth_policy.access_policy")

    assert policy.can_access_settings("admin") is True
    assert policy.can_access_settings("user") is False
    assert policy.can_access_advanced_config("admin", True) is True
    assert policy.can_access_advanced_config("admin", False) is False
    assert policy.is_admin_only_path("/config/users/aria") is True
    assert policy.is_admin_only_path("/config/userland") is False
    assert policy.is_advanced_config_path("/config/connections/ssh") is True
    assert policy.is_advanced_config_path("/config") is False


def test_auth_access_manifests_own_canonical_implementations() -> None:
    assert "aria/modules/security_storage/auth_manager.py" in MODULE_MANIFESTS["security_storage"]["python"]
    assert "aria/modules/auth_policy/access_policy.py" in MODULE_MANIFESTS["auth_policy"]["python"]
