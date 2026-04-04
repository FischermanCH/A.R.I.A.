from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Any

import yaml

from aria.core.auth import AuthManager
from aria.core.config import get_master_key
from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml muss Mapping sein.")
    return data


def _resolve_db_path(config_path: Path) -> Path:
    raw = _read_yaml(config_path)
    root = config_path.parent.parent
    security = raw.get("security", {})
    if not isinstance(security, dict):
        security = {}
    rel = str(security.get("db_path", "data/auth/aria_secure.sqlite")).strip() or "data/auth/aria_secure.sqlite"
    db = Path(rel)
    if not db.is_absolute():
        db = (root / db).resolve()
    return db


def main() -> int:
    parser = argparse.ArgumentParser(description="ARIA User Admin (Secure DB)")
    parser.add_argument("--config", default="config/config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="User anlegen/aktualisieren")
    add.add_argument("username")
    add.add_argument("--role", default="user")

    sub.add_parser("list", help="User auflisten")

    args = parser.parse_args()
    master_key = get_master_key(args.config)
    if not master_key:
        raise ValueError("ARIA_MASTER_KEY fehlt. Erst secure-migrate ausführen oder export setzen.")
    store = SecureConfigStore(
        config=SecureStoreConfig(db_path=_resolve_db_path(Path(args.config)), enabled=True),
        master_key=decode_master_key(master_key),
    )
    auth = AuthManager(store=store)

    if args.cmd == "list":
        for row in store.list_users():
            state = "active" if row.get("active") else "disabled"
            print(f"{row['username']} [{row['role']}] {state}")
        return 0

    if args.cmd == "add":
        pwd1 = getpass.getpass("Passwort: ")
        pwd2 = getpass.getpass("Passwort wiederholen: ")
        if pwd1 != pwd2:
            raise ValueError("Passwörter stimmen nicht überein.")
        auth.upsert_user(username=args.username, password=pwd1, role=args.role)
        print(f"User gespeichert: {args.username}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
