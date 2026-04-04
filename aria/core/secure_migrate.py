from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from aria.core.config import ensure_secret_value
from aria.core.secure_store import (
    SecureConfigStore,
    SecureStoreConfig,
    decode_master_key,
    generate_master_key_b64,
)


SECRET_KEYS = (
    ("llm", "api_key", "llm.api_key"),
    ("embeddings", "api_key", "embeddings.api_key"),
    ("memory", "qdrant_api_key", "memory.qdrant_api_key"),
    ("channels", "api", "auth_token", "channels.api.auth_token"),
)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config fehlt: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml muss ein Mapping sein.")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _get_nested(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part, "")
    return cur


def _set_nested(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cur = data
    for part in path[:-1]:
        cur.setdefault(part, {})
        if not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[path[-1]] = value


def _ensure_master_key(secrets_env_path: Path) -> str:
    config_path = secrets_env_path.with_name("config.yaml")
    ensured = ensure_secret_value("ARIA_MASTER_KEY", config_path, generator=generate_master_key_b64)
    decode_master_key(ensured)
    return ensured


def migrate(config_path: Path, strip: bool = True) -> dict[str, int]:
    raw = _read_yaml(config_path)
    root = config_path.parent.parent
    security = raw.get("security", {})
    if not isinstance(security, dict):
        security = {}
    db_rel = str(security.get("db_path", "data/auth/aria_secure.sqlite")).strip() or "data/auth/aria_secure.sqlite"
    db_path = Path(db_rel)
    if not db_path.is_absolute():
        db_path = (root / db_path).resolve()

    key_raw = _ensure_master_key(root / "config" / "secrets.env")
    store = SecureConfigStore(
        config=SecureStoreConfig(db_path=db_path, enabled=True),
        master_key=decode_master_key(key_raw),
    )

    migrated = 0
    for item in SECRET_KEYS:
        *path_parts, secret_key = item
        path = tuple(path_parts)
        value = str(_get_nested(raw, path)).strip()
        if value:
            store.set_secret(secret_key, value)
            migrated += 1
            if strip:
                _set_nested(raw, path, "")

    profiles = raw.get("profiles", {})
    if isinstance(profiles, dict):
        for section_name in ("llm", "embeddings"):
            section = profiles.get(section_name, {})
            if not isinstance(section, dict):
                continue
            for profile_name, payload in section.items():
                if not isinstance(payload, dict):
                    continue
                value = str(payload.get("api_key", "")).strip()
                if not value:
                    continue
                store.set_secret(f"profiles.{section_name}.{profile_name}.api_key", value)
                migrated += 1
                if strip:
                    payload["api_key"] = ""

    if strip:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = config_path.with_name(f"{config_path.name}.bak.{stamp}")
        backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
        _write_yaml(config_path, raw)

    return {"migrated": migrated}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migriert Secret-Konfig in verschlüsselte SQLite.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--no-strip", action="store_true", help="Secrets nicht aus config.yaml entfernen")
    args = parser.parse_args()

    stats = migrate(Path(args.config), strip=not args.no_strip)
    print(f"Secure migration abgeschlossen. Eintraege: {stats['migrated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
