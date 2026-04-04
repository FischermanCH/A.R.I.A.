from __future__ import annotations

from typing import Iterable


ADVANCED_CONFIG_PREFIXES: tuple[str, ...] = (
    "/config/llm",
    "/config/embeddings",
    "/config/routing",
    "/config/skill-routing",
    "/config/appearance",
    "/config/language",
    "/config/prompts",
    "/config/connections",
    "/config/language/file",
    "/config/security",
    "/config/files",
    "/config/logs",
    "/config/error-interpreter",
)

ADMIN_ONLY_PREFIXES: tuple[str, ...] = (
    "/config/users",
    "/config/debug",
)

ADVANCED_CONFIG_EXACT: tuple[str, ...] = tuple()
ADMIN_ONLY_EXACT: tuple[str, ...] = tuple()


def is_admin(role: str | None) -> bool:
    return str(role or "").strip().lower() == "admin"


def is_admin_mode(role: str | None, debug_mode: bool) -> bool:
    return is_admin(role) and bool(debug_mode)


def can_access_settings(role: str | None) -> bool:
    return is_admin(role)


def can_access_users(role: str | None) -> bool:
    return is_admin(role)


def can_access_advanced_config(role: str | None, debug_mode: bool) -> bool:
    return is_admin_mode(role, debug_mode)


def _matches(path: str, exact: Iterable[str], prefixes: Iterable[str]) -> bool:
    clean = str(path or "").strip() or "/"
    return clean in set(exact) or any(clean == prefix or clean.startswith(prefix + "/") for prefix in prefixes)


def is_admin_only_path(path: str) -> bool:
    return _matches(path, ADMIN_ONLY_EXACT, ADMIN_ONLY_PREFIXES)


def is_advanced_config_path(path: str) -> bool:
    return _matches(path, ADVANCED_CONFIG_EXACT, ADVANCED_CONFIG_PREFIXES)
