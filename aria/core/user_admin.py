from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Any

import yaml

from aria.core.auth import AuthManager
from aria.core.config import get_master_key
from aria.core.i18n import I18NStore
from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key

_USER_ADMIN_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _user_admin_text(key: str, default: str = "", **values: object) -> str:
    template = _USER_ADMIN_I18N.t("de", f"user_admin.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(_user_admin_text("config_not_mapping", "config.yaml must be a mapping."))
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
    parser = argparse.ArgumentParser(description=_user_admin_text("parser_description", "ARIA User Admin (Secure DB)"))
    parser.add_argument("--config", default="config/config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help=_user_admin_text("add_help", "Add or update a user"))
    add.add_argument("username")
    add.add_argument("--role", default="user")

    sub.add_parser("list", help=_user_admin_text("list_help", "List users"))

    args = parser.parse_args()
    master_key = get_master_key(args.config)
    if not master_key:
        raise ValueError(
            _user_admin_text(
                "master_key_missing",
                "ARIA_MASTER_KEY is missing. Run secure-migrate first or set the export.",
            )
        )
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
        pwd1 = getpass.getpass(_user_admin_text("password_prompt", "Password: "))
        pwd2 = getpass.getpass(_user_admin_text("password_repeat_prompt", "Repeat password: "))
        if pwd1 != pwd2:
            raise ValueError(_user_admin_text("password_mismatch", "Passwords do not match."))
        auth.upsert_user(username=args.username, password=pwd1, role=args.role)
        print(_user_admin_text("user_saved", "User saved: {username}", username=args.username))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
