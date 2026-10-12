"""Config backup parsing, validation, snapshot, and restore contracts."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aria.modules.recipe_store.manifests import sanitize_recipe_id, validate_stored_recipe_manifest
from aria.modules.release_update.release_meta import read_release_meta

BACKUP_SCHEMA_VERSION = "aria-config-backup-v2"
LEGACY_BACKUP_SCHEMA_VERSION = "aria-config-backup-v1"
_SENSITIVE_CONFIG_KEYS = {
    "api_key", "qdrant_api_key", "password", "password_hash", "secret", "token",
    "auth_token", "access_token", "refresh_token", "private_key", "headers",
    "webhook_url", "client_secret", "authorization",
}
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1


def backup_filename(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"aria-config-backup-{stamp}.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_rel_path(base_dir: Path, path: Path) -> str:
    return str(path.resolve().relative_to(base_dir.resolve())).replace("\\", "/")


def _resolve_rel_path(base_dir: Path, rel_path: str) -> Path:
    clean = str(rel_path or "").strip().replace("\\", "/")
    if not clean or clean.startswith("/") or clean.startswith("../") or "/../" in clean or "\x00" in clean:
        raise ValueError(f"Invalid backup path: {rel_path}")
    target = (base_dir / clean).resolve()
    try:
        target.relative_to(base_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"Backup path escapes project root: {rel_path}") from exc
    return target


def _iter_prompt_files(base_dir: Path) -> list[Path]:
    prompts_root = (base_dir / "prompts").resolve()
    if not prompts_root.exists():
        return []
    return [path for path in sorted(prompts_root.rglob("*.md")) if path.is_file()]


def _iter_stored_recipe_files(base_dir: Path) -> list[Path]:
    recipes_root = (base_dir / "data" / "recipes").resolve()
    legacy_skills_root = (base_dir / "data" / "skills").resolve()
    recipes_root.mkdir(parents=True, exist_ok=True)
    rows: list[Path] = []
    seen_names: set[str] = set()
    for root in (recipes_root, legacy_skills_root):
        if root == recipes_root:
            paths = sorted(root.glob("*.json"))
        elif root.exists():
            paths = sorted(root.glob("*.json"))
        else:
            paths = []
        for path in paths:
            if not path.is_file() or path.name.startswith("_") or path.name in seen_names:
                continue
            seen_names.add(path.name)
            rows.append(path)
    return rows


def _read_text_files(base_dir: Path, paths: list[Path]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in paths:
        try:
            rows[_normalize_rel_path(base_dir, path)] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return rows


def _read_stored_recipe_manifests(base_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _iter_stored_recipe_files(base_dir):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            rows.append(copy.deepcopy(raw))
    return rows


def _read_secure_store_snapshot(secure_store: Any | None) -> dict[str, Any]:
    if not secure_store:
        return {"enabled": False, "secrets": {}, "users": []}

    secrets: dict[str, str] = {}
    for key in secure_store.list_secret_keys():
        clean_key = str(key).strip()
        if not clean_key:
            continue
        secrets[clean_key] = secure_store.get_secret(clean_key, default="")

    users: list[dict[str, Any]] = []
    for row in secure_store.list_users():
        username = str(row.get("username", "")).strip()
        if not username:
            continue
        detail = secure_store.get_user(username)
        if not detail:
            continue
        users.append(
            {
                "username": str(detail.get("username", "")).strip(),
                "password_hash": str(detail.get("password_hash", "")).strip(),
                "role": str(detail.get("role", "user")).strip() or "user",
                "active": bool(detail.get("active", True)),
            }
        )
    return {"enabled": True, "secrets": secrets, "users": users}


def _secret_free_config(value: Any, *, key: str = "") -> Any:
    """Preserve config shape while removing credentials from portable backups."""

    clean_key = str(key).strip().lower()
    is_sensitive = clean_key in _SENSITIVE_CONFIG_KEYS or clean_key.endswith(
        ("_password", "_secret", "_api_key", "_auth_token", "_access_token", "_refresh_token")
    )
    if is_sensitive:
        return {} if clean_key == "headers" else ""
    if isinstance(value, dict):
        return {str(child): _secret_free_config(item, key=str(child)) for child, item in value.items()}
    if isinstance(value, list):
        return [_secret_free_config(item) for item in value]
    return copy.deepcopy(value)


def _encrypted_secrets_bundle(
    *, raw_config: dict[str, Any], secure_store: Any | None, passphrase: str,
) -> dict[str, Any]:
    clean_passphrase = str(passphrase or "")
    if len(clean_passphrase) < 12:
        raise ValueError("Encrypted backups require a passphrase of at least 12 characters.")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = hashlib.scrypt(
        clean_passphrase.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=32, maxmem=128 * 1024 * 1024,
    )
    plaintext = json.dumps(
        {"config": copy.deepcopy(raw_config), "secure_store": _read_secure_store_snapshot(secure_store)},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, BACKUP_SCHEMA_VERSION.encode("ascii"))
    return {
        "algorithm": "AES-256-GCM",
        "kdf": "scrypt",
        "kdf_parameters": {"n": _SCRYPT_N, "r": _SCRYPT_R, "p": _SCRYPT_P, "length": 32},
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def _decrypt_secrets_bundle(bundle: Any, passphrase: str) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("Encrypted secrets bundle is invalid.")
    if not str(passphrase or ""):
        raise ValueError("This backup contains an encrypted secrets bundle; enter its passphrase.")
    try:
        params = dict(bundle.get("kdf_parameters") or {})
        salt = base64.b64decode(str(bundle["salt"]), validate=True)
        nonce = base64.b64decode(str(bundle["nonce"]), validate=True)
        ciphertext = base64.b64decode(str(bundle["ciphertext"]), validate=True)
        key = hashlib.scrypt(
            str(passphrase).encode("utf-8"), salt=salt,
            n=int(params.get("n", _SCRYPT_N)), r=int(params.get("r", _SCRYPT_R)),
            p=int(params.get("p", _SCRYPT_P)), dklen=int(params.get("length", 32)),
            maxmem=128 * 1024 * 1024,
        )
        decoded = AESGCM(key).decrypt(nonce, ciphertext, BACKUP_SCHEMA_VERSION.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Encrypted backup could not be decrypted; the passphrase is wrong or the file is damaged.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
        raise ValueError("Encrypted secrets bundle is invalid.")
    _validate_secure_store_payload(payload.get("secure_store", {}))
    return payload


def build_config_backup_payload(
    *,
    base_dir: Path,
    raw_config: dict[str, Any],
    secure_store: Any | None = None,
    error_interpreter_path: Path | None = None,
    include_secrets: bool = False,
    passphrase: str = "",
) -> dict[str, Any]:
    support_files: dict[str, str] = {}
    if error_interpreter_path and error_interpreter_path.exists() and error_interpreter_path.is_file():
        try:
            support_files[_normalize_rel_path(base_dir, error_interpreter_path)] = error_interpreter_path.read_text(
                encoding="utf-8"
            )
        except OSError:
            pass

    payload = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "exported_at": _iso_now(),
        "aria": read_release_meta(base_dir),
        "config": _secret_free_config(raw_config),
        "secure_store": {"included": False, "secrets": {}, "users": []},
        "stored_recipes": _read_stored_recipe_manifests(base_dir),
        "custom_skills": _read_stored_recipe_manifests(base_dir),
        "prompt_files": _read_text_files(base_dir, _iter_prompt_files(base_dir)),
        "support_files": support_files,
        "manifest": {
            "secrets": "encrypted" if include_secrets else "excluded",
            "scope_statement": (
                "Contains no memories, documents, notes, chats, jobs or Qdrant data; "
                "persistent volumes are not a backup."
            ),
            "included": ["secret-free config", "stored recipe manifests", "prompt markdown files", "support files"],
            "not_included": ["memories", "documents", "notes", "chats", "jobs", "qdrant_data"],
            "persistent_volumes_are_a_backup": False,
        },
        "notes": {
            "included": [
                "secret-free config.yaml",
                "stored recipe manifests",
                "prompt markdown files",
                "error interpreter file",
            ],
            "excluded": [
                "secrets and password hashes (unless explicitly encrypted)",
                "memories, documents, notes, chats, jobs and Qdrant data",
                "runtime logs and update state",
                "Docker or stack environment variables",
                "persistent volume contents",
            ],
        },
    }
    if include_secrets:
        payload["encrypted_secrets_bundle"] = _encrypted_secrets_bundle(
            raw_config=raw_config, secure_store=secure_store, passphrase=passphrase,
        )
    return payload


def summarize_config_backup_payload(payload: dict[str, Any]) -> dict[str, int]:
    secure_store = payload.get("secure_store", {})
    if not isinstance(secure_store, dict):
        secure_store = {}
    secrets = secure_store.get("secrets", {})
    users = secure_store.get("users", [])
    prompt_files = payload.get("prompt_files", {})
    support_files = payload.get("support_files", {})
    stored_recipes = payload.get("stored_recipes", payload.get("custom_skills", []))
    return {
        "secret_count": len(secrets) if isinstance(secrets, dict) else 0,
        "user_count": len(users) if isinstance(users, list) else 0,
        "stored_recipe_count": len(stored_recipes) if isinstance(stored_recipes, list) else 0,
        "custom_skill_count": len(stored_recipes) if isinstance(stored_recipes, list) else 0,
        "prompt_file_count": len(prompt_files) if isinstance(prompt_files, dict) else 0,
        "support_file_count": len(support_files) if isinstance(support_files, dict) else 0,
    }


def parse_config_backup_payload(data: bytes | str, *, passphrase: str = "") -> dict[str, Any]:
    raw = data.decode("utf-8") if isinstance(data, bytes) else str(data or "")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Backup file is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Backup file must contain a JSON object.")
    schema = str(payload.get("schema_version", "")).strip()
    if schema not in {BACKUP_SCHEMA_VERSION, LEGACY_BACKUP_SCHEMA_VERSION}:
        raise ValueError("Backup file schema is not supported.")
    config = payload.get("config")
    if not isinstance(config, dict):
        raise ValueError("Backup file does not contain a valid config object.")
    if schema == LEGACY_BACKUP_SCHEMA_VERSION:
        _validate_secure_store_payload(payload.get("secure_store", {}))
        payload["restore_warnings"] = ["legacy_plaintext_backup"]
    elif payload.get("encrypted_secrets_bundle") is not None:
        secret_payload = _decrypt_secrets_bundle(payload.get("encrypted_secrets_bundle"), passphrase)
        payload["config"] = secret_payload["config"]
        payload["secure_store"] = secret_payload.get("secure_store", {})
        payload["secrets_restored"] = True
    else:
        payload["secure_store"] = {"included": False, "secrets": {}, "users": []}
        payload["needs_secret_reentry"] = True
    _validate_text_file_map(payload.get("prompt_files", {}), required_prefix="prompts/", required_suffix=".md")
    _validate_support_files(payload.get("support_files", {}))
    _validate_stored_recipe_payload(payload.get("stored_recipes", payload.get("custom_skills", [])))
    return payload


def _validate_secure_store_payload(raw: Any) -> None:
    if raw is None or raw == "":
        return
    if not isinstance(raw, dict):
        raise ValueError("Backup secure_store payload must be an object.")
    secrets = raw.get("secrets", {})
    if secrets is not None and secrets != "" and not isinstance(secrets, dict):
        raise ValueError("Backup secrets must be a key/value object.")
    for key, value in (secrets.items() if isinstance(secrets, dict) else []):
        if not str(key).strip():
            raise ValueError("Backup contains an empty secret key.")
        if not isinstance(value, str):
            raise ValueError(f"Secret '{key}' must be a string.")
    users = raw.get("users", [])
    if users is not None and users != "" and not isinstance(users, list):
        raise ValueError("Backup users must be a list.")
    for entry in users if isinstance(users, list) else []:
        if not isinstance(entry, dict):
            raise ValueError("Every backup user entry must be an object.")
        username = str(entry.get("username", "")).strip()
        password_hash = str(entry.get("password_hash", "")).strip()
        if not username or not password_hash:
            raise ValueError("Backup user entries need username and password_hash.")


def _validate_text_file_map(raw: Any, *, required_prefix: str, required_suffix: str | None = None) -> None:
    if raw is None or raw == "":
        return
    if not isinstance(raw, dict):
        raise ValueError("Backup file section must be an object.")
    for path, content in raw.items():
        clean_path = str(path or "").strip().replace("\\", "/")
        if not clean_path.startswith(required_prefix):
            raise ValueError(f"Backup path is outside the allowed area: {path}")
        if required_suffix and not clean_path.endswith(required_suffix):
            raise ValueError(f"Backup path has the wrong file type: {path}")
        if not isinstance(content, str):
            raise ValueError(f"Backup file content must be text: {path}")


def _validate_support_files(raw: Any) -> None:
    if raw is None or raw == "":
        return
    if not isinstance(raw, dict):
        raise ValueError("Backup support_files must be an object.")
    for path, content in raw.items():
        clean_path = str(path or "").strip().replace("\\", "/")
        if not clean_path.startswith("config/"):
            raise ValueError(f"Support file path is outside config/: {path}")
        if not isinstance(content, str):
            raise ValueError(f"Support file content must be text: {path}")


def _validate_stored_recipe_payload(raw: Any) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError("Backup stored_recipes must be a list.")
    clean_rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Every stored recipe backup entry must be an object.")
        clean_rows.append(validate_stored_recipe_manifest(item))
    return clean_rows


def _sync_secure_store(secure_store: Any | None, payload: dict[str, Any]) -> None:
    if bool(payload.get("needs_secret_reentry")):
        return
    secure = payload.get("secure_store", {})
    if not isinstance(secure, dict):
        secure = {}
    secrets = secure.get("secrets", {})
    users = secure.get("users", [])
    if not secure and secure_store is None:
        return
    if not secure_store:
        if (isinstance(secrets, dict) and secrets) or (isinstance(users, list) and users):
            raise ValueError(
                "This ARIA installation has no active secure store, so secrets and users cannot be restored."
            )
        return

    target_secrets = {str(key).strip(): str(value) for key, value in secrets.items()} if isinstance(secrets, dict) else {}
    current_secret_keys = set(secure_store.list_secret_keys())
    for stale_key in sorted(current_secret_keys - set(target_secrets.keys())):
        secure_store.delete_secret(stale_key)
    for key, value in sorted(target_secrets.items()):
        secure_store.set_secret(key, value)

    target_users = _validate_custom_user_rows(users)
    current_users = {str(row.get("username", "")).strip() for row in secure_store.list_users()}
    for stale_user in sorted(user for user in current_users if user and user not in {row["username"] for row in target_users}):
        secure_store.delete_user(stale_user)
    for row in target_users:
        secure_store.upsert_user(row["username"], row["password_hash"], role=row["role"])
        secure_store.set_user_active(row["username"], bool(row["active"]))


def _validate_custom_user_rows(raw: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username", "")).strip()
        password_hash = str(item.get("password_hash", "")).strip()
        role = str(item.get("role", "user")).strip().lower() or "user"
        active = bool(item.get("active", True))
        if not username or not password_hash:
            raise ValueError("Backup user entries need username and password_hash.")
        rows.append(
            {
                "username": username,
                "password_hash": password_hash,
                "role": "admin" if role == "admin" else "user",
                "active": active,
            }
        )
    return rows


def restore_config_backup_payload(
    *,
    base_dir: Path,
    payload: dict[str, Any],
    write_raw_config: Callable[[dict[str, Any]], None],
    get_secure_store: Callable[[dict[str, Any] | None], Any | None],
    error_interpreter_path: Path | None = None,
    passphrase: str = "",
) -> dict[str, int]:
    clean_payload = parse_config_backup_payload(
        json.dumps(payload, ensure_ascii=False), passphrase=passphrase,
    )
    raw_config = copy.deepcopy(clean_payload.get("config", {}))
    write_raw_config(raw_config)

    secure_store = get_secure_store(raw_config)
    _sync_secure_store(secure_store, clean_payload)

    recipes_root = (base_dir / "data" / "recipes").resolve()
    recipes_root.mkdir(parents=True, exist_ok=True)
    existing_skill_files = _iter_stored_recipe_files(base_dir)
    for path in existing_skill_files:
        try:
            path.unlink()
        except OSError:
            continue

    validated_manifests = _validate_stored_recipe_payload(
        clean_payload.get("stored_recipes", clean_payload.get("custom_skills", []))
    )
    for manifest in validated_manifests:
        skill_id = sanitize_recipe_id(manifest.get("id"))
        if not skill_id:
            raise ValueError("Backup contains a stored recipe without a valid id.")
        target = recipes_root / f"{skill_id}.json"
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prompt_files = clean_payload.get("prompt_files", {})
    if isinstance(prompt_files, dict):
        for rel_path, content in prompt_files.items():
            target = _resolve_rel_path(base_dir, str(rel_path))
            if not str(rel_path).replace("\\", "/").startswith("prompts/") or target.suffix.lower() != ".md":
                raise ValueError(f"Backup prompt path is invalid: {rel_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")

    support_files = clean_payload.get("support_files", {})
    if isinstance(support_files, dict):
        for rel_path, content in support_files.items():
            target = _resolve_rel_path(base_dir, str(rel_path))
            if error_interpreter_path is not None and target != error_interpreter_path.resolve():
                raise ValueError(f"Unsupported support file in backup: {rel_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")

    summary = summarize_config_backup_payload(clean_payload)
    summary["needs_secret_reentry"] = int(bool(clean_payload.get("needs_secret_reentry")))
    summary["legacy_plaintext_warning"] = int(
        "legacy_plaintext_backup" in list(clean_payload.get("restore_warnings") or [])
    )
    return summary
