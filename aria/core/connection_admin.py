from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aria.core.config import get_master_key
from aria.core.connection_catalog import connection_field_labels, connection_kind_label, sanitize_connection_payload
from aria.core.connection_health import delete_connection_health
from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key


CONNECTION_ADMIN_SPECS: dict[str, dict[str, Any]] = {
    "ssh": {
        "health_prefix": "ssh",
        "secret_keys": [],
        "success_message": "SSH-Profil gelöscht · lokale SSH-Keys bleiben erhalten",
    },
    "discord": {
        "health_prefix": "discord",
        "secret_keys": ["connections.discord.{ref}.webhook_url"],
        "success_message": "Discord-Profil gelöscht",
    },
    "sftp": {
        "health_prefix": "sftp",
        "secret_keys": ["connections.sftp.{ref}.password"],
        "success_message": "SFTP-Profil gelöscht",
    },
    "smb": {
        "health_prefix": "smb",
        "secret_keys": ["connections.smb.{ref}.password"],
        "success_message": "SMB-Profil gelöscht",
    },
    "webhook": {
        "health_prefix": "webhook",
        "secret_keys": ["connections.webhook.{ref}.url"],
        "success_message": "Webhook-Profil gelöscht",
    },
    "email": {
        "health_prefix": "email",
        "secret_keys": ["connections.email.{ref}.password"],
        "success_message": "SMTP-Profil gelöscht",
    },
    "imap": {
        "health_prefix": "imap",
        "secret_keys": ["connections.imap.{ref}.password"],
        "success_message": "IMAP-Profil gelöscht",
    },
    "http_api": {
        "health_prefix": "http_api",
        "secret_keys": ["connections.http_api.{ref}.auth_token"],
        "success_message": "HTTP-API-Profil gelöscht",
    },
    "rss": {
        "health_prefix": "rss",
        "secret_keys": [],
        "success_message": "RSS-Profil gelöscht",
    },
    "searxng": {
        "health_prefix": "searxng",
        "secret_keys": [],
        "success_message": "SearXNG-Profil gelöscht",
    },
    "mqtt": {
        "health_prefix": "mqtt",
        "secret_keys": ["connections.mqtt.{ref}.password"],
        "success_message": "MQTT-Profil gelöscht",
    },
}

CONNECTION_CREATE_SPECS: dict[str, dict[str, Any]] = {
    "ssh": {
        "section": "ssh",
        "required": ["host", "user"],
        "success_message": "SSH-Profil erstellt",
    },
    "sftp": {
        "section": "sftp",
        "required": ["host", "user"],
        "success_message": "SFTP-Profil erstellt",
    },
    "smb": {
        "section": "smb",
        "required": ["host", "share"],
        "success_message": "SMB-Profil erstellt",
    },
    "discord": {
        "section": "discord",
        "required": ["webhook_url"],
        "success_message": "Discord-Profil erstellt",
    },
    "rss": {
        "section": "rss",
        "required": ["feed_url"],
        "success_message": "RSS-Profil erstellt",
    },
    "webhook": {
        "section": "webhook",
        "required": ["url"],
        "success_message": "Webhook-Profil erstellt",
    },
    "http_api": {
        "section": "http_api",
        "required": ["base_url"],
        "success_message": "HTTP-API-Profil erstellt",
    },
    "searxng": {
        "section": "searxng",
        "required": ["base_url"],
        "success_message": "SearXNG-Profil erstellt",
    },
    "mqtt": {
        "section": "mqtt",
        "required": ["host"],
        "success_message": "MQTT-Profil erstellt",
    },
    "email": {
        "section": "email",
        "required": ["smtp_host"],
        "success_message": "SMTP-Profil erstellt",
    },
    "imap": {
        "section": "imap",
        "required": ["host"],
        "success_message": "IMAP-Profil erstellt",
    },
}

CONNECTION_UPDATE_SPECS: dict[str, dict[str, Any]] = {
    "ssh": {
        "section": "ssh",
        "success_message": "SSH-Profil aktualisiert",
    },
    "sftp": {
        "section": "sftp",
        "success_message": "SFTP-Profil aktualisiert",
    },
    "smb": {
        "section": "smb",
        "success_message": "SMB-Profil aktualisiert",
    },
    "discord": {
        "section": "discord",
        "success_message": "Discord-Profil aktualisiert",
    },
    "rss": {
        "section": "rss",
        "success_message": "RSS-Profil aktualisiert",
    },
    "webhook": {
        "section": "webhook",
        "success_message": "Webhook-Profil aktualisiert",
    },
    "http_api": {
        "section": "http_api",
        "success_message": "HTTP-API-Profil aktualisiert",
    },
    "searxng": {
        "section": "searxng",
        "success_message": "SearXNG-Profil aktualisiert",
    },
    "mqtt": {
        "section": "mqtt",
        "success_message": "MQTT-Profil aktualisiert",
    },
    "email": {
        "section": "email",
        "success_message": "SMTP-Profil aktualisiert",
    },
    "imap": {
        "section": "imap",
        "success_message": "IMAP-Profil aktualisiert",
    },
}


def friendly_connection_admin_error_text(exc: Exception, *, kind: str = "", action: str = "") -> str:
    raw = str(exc).strip() or "Unbekannter Fehler."
    clean_kind = str(kind or "").strip().lower().replace("-", "_")
    kind_label = connection_kind_label(clean_kind) if clean_kind else "Connection"
    field_labels = connection_field_labels(clean_kind)

    if raw.startswith("Pflichtfeld fehlt:"):
        field = raw.split(":", 1)[1].strip()
        return f"Pflichtfeld fehlt: {field_labels.get(field, field)}."
    if "Security Store ist für" in raw and "erforderlich" in raw:
        return f"{kind_label}-Profil kann nur gespeichert werden, wenn der Security Store aktiv ist."
    if raw == "Connection-Typ wird im Chat noch nicht für Create unterstützt.":
        return f"{kind_label}-Profile können aktuell noch nicht per Chat erstellt werden."
    if raw == "Connection-Typ wird im Chat noch nicht für Update unterstützt.":
        return f"{kind_label}-Profile können aktuell noch nicht per Chat aktualisiert werden."
    if raw == "Unbekannter Connection-Typ.":
        return "Unbekannter Connection-Typ."
    if raw == "Ungültige Connection-Konfiguration.":
        return "Die Connection-Konfiguration in `config.yaml` ist ungültig."
    if raw == "Ungültige Connection-Sektion.":
        return f"Die {kind_label}-Sektion in `config.yaml` ist ungültig."
    if raw == "Ungültige bestehende Connection-Daten.":
        return f"Die gespeicherten Daten des Profils sind für {kind_label} ungültig."
    if raw.startswith("Connection-Ref fehlt"):
        return "Connection-Ref fehlt oder ist ungültig."
    if raw.startswith("Connection-Profil '") and raw.endswith("' existiert bereits."):
        return raw
    if raw.startswith("Connection-Profil '") and raw.endswith("' nicht gefunden."):
        return raw
    if raw.startswith("Profil nicht gefunden."):
        return "Connection-Profil nicht gefunden."
    if raw.startswith("Konfigurationsdatei fehlt:"):
        return "config.yaml fehlt."
    if action == "delete" and "nicht eindeutig" in raw:
        return raw
    return raw


def sanitize_connection_ref(value: str | None) -> str:
    import re

    clean = re.sub(r"\s+", "-", str(value or "").strip().lower())
    clean = re.sub(r"[^a-z0-9._-]", "", clean)
    return clean[:64].strip(".-_")


def read_raw_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Konfigurationsdatei fehlt: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def write_raw_config(config_path: Path, raw: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(raw, handle, allow_unicode=True, sort_keys=False)


def get_secure_store_for_config(base_dir: Path, raw: dict[str, Any]) -> SecureConfigStore | None:
    security = raw.get("security", {})
    if not isinstance(security, dict) or not bool(security.get("enabled", True)):
        return None
    master = get_master_key(base_dir / "config" / "config.yaml")
    if not master:
        return None
    db_rel = str(security.get("db_path", "data/auth/aria_secure.sqlite")).strip() or "data/auth/aria_secure.sqlite"
    db_path = Path(db_rel)
    if not db_path.is_absolute():
        db_path = (base_dir / db_path).resolve()
    return SecureConfigStore(
        config=SecureStoreConfig(db_path=db_path, enabled=True),
        master_key=decode_master_key(master),
    )


def list_connection_refs(base_dir: Path) -> dict[str, list[str]]:
    raw = read_raw_config(base_dir / "config" / "config.yaml")
    rows = raw.get("connections", {})
    if not isinstance(rows, dict):
        return {}
    result: dict[str, list[str]] = {}
    for kind, values in rows.items():
        if isinstance(values, dict):
            refs = sorted(sanitize_connection_ref(ref) for ref in values.keys())
            result[str(kind).strip().lower()] = [ref for ref in refs if ref]
    return result


def resolve_connection_target(
    catalog: dict[str, list[str]],
    *,
    ref_hint: str,
    kind_hint: str = "",
) -> tuple[str, str]:
    clean_ref = sanitize_connection_ref(ref_hint)
    clean_kind = str(kind_hint or "").strip().lower().replace("-", "_")
    if not clean_ref:
        raise ValueError("Connection-Ref fehlt.")

    if clean_kind in {"smtp"}:
        clean_kind = "email"
    if clean_kind in {"http api"}:
        clean_kind = "http_api"

    if clean_kind:
        refs = catalog.get(clean_kind, [])
        if clean_ref not in refs:
            raise ValueError(f"{clean_kind.upper()}-Profil '{clean_ref}' nicht gefunden.")
        return clean_kind, clean_ref

    matches: list[tuple[str, str]] = []
    for kind, refs in catalog.items():
        if clean_ref in refs:
            matches.append((kind, clean_ref))
    if not matches:
        raise ValueError(f"Connection-Profil '{clean_ref}' nicht gefunden.")
    if len(matches) > 1:
        kinds = ", ".join(kind for kind, _ in matches)
        raise ValueError(f"Profil '{clean_ref}' ist nicht eindeutig. Bitte Typ angeben: {kinds}.")
    return matches[0]


def delete_connection_profile(base_dir: Path, kind: str, ref_raw: str) -> dict[str, Any]:
    clean_kind = str(kind or "").strip().lower()
    spec = CONNECTION_ADMIN_SPECS.get(clean_kind)
    if not spec:
        raise ValueError("Unbekannter Connection-Typ.")

    ref = sanitize_connection_ref(ref_raw)
    if not ref:
        raise ValueError("Profil-Ref fehlt.")

    config_path = base_dir / "config" / "config.yaml"
    raw = read_raw_config(config_path)
    connections = raw.setdefault("connections", {})
    if not isinstance(connections, dict):
        raise ValueError("Ungültige Connection-Konfiguration.")
    rows = connections.setdefault(clean_kind, {})
    if not isinstance(rows, dict) or ref not in rows:
        raise ValueError("Profil nicht gefunden.")

    rows.pop(ref, None)
    write_raw_config(config_path, raw)

    store = get_secure_store_for_config(base_dir, raw)
    if store:
        for key_template in spec.get("secret_keys", []):
            store.delete_secret(str(key_template).format(ref=ref))

    delete_connection_health(f"{spec['health_prefix']}:{ref}")
    return {
        "kind": clean_kind,
        "ref": ref,
        "success_message": spec["success_message"],
    }


def create_connection_profile(base_dir: Path, kind: str, ref_raw: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean_kind = str(kind or "").strip().lower().replace("-", "_")
    spec = CONNECTION_CREATE_SPECS.get(clean_kind)
    if not spec:
        raise ValueError("Connection-Typ wird im Chat noch nicht für Create unterstützt.")

    ref = sanitize_connection_ref(ref_raw)
    if not ref:
        raise ValueError("Connection-Ref fehlt oder ist ungültig.")

    config_path = base_dir / "config" / "config.yaml"
    raw = read_raw_config(config_path)
    connections = raw.setdefault("connections", {})
    if not isinstance(connections, dict):
        raise ValueError("Ungültige Connection-Konfiguration.")
    section = str(spec["section"])
    rows = connections.setdefault(section, {})
    if not isinstance(rows, dict):
        raise ValueError("Ungültige Connection-Sektion.")
    if ref in rows:
        raise ValueError(f"Connection-Profil '{ref}' existiert bereits.")

    row_value = sanitize_connection_payload(clean_kind, payload)
    for field in spec.get("required", []):
        if not str(row_value.get(field, "")).strip():
            raise ValueError(f"Pflichtfeld fehlt: {field}")

    store = get_secure_store_for_config(base_dir, raw)
    if clean_kind == "ssh":
        rows[ref] = {
            "host": str(row_value.get("host", "")).strip(),
            "port": int(row_value.get("port", 22) or 22),
            "user": str(row_value.get("user", "")).strip(),
            "key_path": str(row_value.get("key_path", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 20) or 20),
            "strict_host_key_checking": str(row_value.get("strict_host_key_checking", "accept-new")).strip() or "accept-new",
            "allow_commands": list(row_value.get("allow_commands", []) if isinstance(row_value.get("allow_commands", []), list) else []),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
    elif clean_kind == "sftp":
        rows[ref] = {
            "host": str(row_value.get("host", "")).strip(),
            "port": int(row_value.get("port", 22) or 22),
            "user": str(row_value.get("user", "")).strip(),
            "key_path": str(row_value.get("key_path", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "root_path": str(row_value.get("root_path", "")).strip(),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        password = str(row_value.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für SFTP-Passwörter erforderlich.")
            store.set_secret(f"connections.sftp.{ref}.password", password)
    elif clean_kind == "smb":
        rows[ref] = {
            "host": str(row_value.get("host", "")).strip(),
            "port": int(row_value.get("port", 445) or 445),
            "share": str(row_value.get("share", "")).strip(),
            "user": str(row_value.get("user", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "root_path": str(row_value.get("root_path", "")).strip(),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        password = str(row_value.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für SMB-Passwörter erforderlich.")
            store.set_secret(f"connections.smb.{ref}.password", password)
    elif clean_kind == "discord":
        if not store:
            raise ValueError("Security Store ist für Discord-Webhooks erforderlich.")
        rows[ref] = {
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "send_test_messages": bool(row_value.get("send_test_messages", True)),
            "allow_skill_messages": bool(row_value.get("allow_skill_messages", True)),
            "alert_skill_errors": bool(row_value.get("alert_skill_errors", False)),
            "alert_safe_fix": bool(row_value.get("alert_safe_fix", False)),
            "alert_connection_changes": bool(row_value.get("alert_connection_changes", False)),
            "alert_system_events": bool(row_value.get("alert_system_events", False)),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        store.set_secret(f"connections.discord.{ref}.webhook_url", str(row_value.get("webhook_url", "")).strip())
    elif clean_kind == "rss":
        rows[ref] = {
            "feed_url": str(row_value.get("feed_url", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
    elif clean_kind == "webhook":
        if not store:
            raise ValueError("Security Store ist für Webhook-URLs erforderlich.")
        rows[ref] = {
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "method": str(row_value.get("method", "POST")).strip().upper() or "POST",
            "content_type": str(row_value.get("content_type", "application/json")).strip() or "application/json",
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        store.set_secret(f"connections.webhook.{ref}.url", str(row_value.get("url", "")).strip())
    elif clean_kind == "http_api":
        rows[ref] = {
            "base_url": str(row_value.get("base_url", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "health_path": str(row_value.get("health_path", "/")).strip() or "/",
            "method": str(row_value.get("method", "GET")).strip().upper() or "GET",
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        auth_token = str(row_value.get("auth_token", "")).strip()
        if auth_token:
            if not store:
                raise ValueError("Security Store ist für HTTP-API-Tokens erforderlich.")
            store.set_secret(f"connections.http_api.{ref}.auth_token", auth_token)
    elif clean_kind == "mqtt":
        rows[ref] = {
            "host": str(row_value.get("host", "")).strip(),
            "port": int(row_value.get("port", 1883) or 1883),
            "user": str(row_value.get("user", "")).strip(),
            "topic": str(row_value.get("topic", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "use_tls": bool(row_value.get("use_tls", False)),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        password = str(row_value.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für MQTT-Passwörter erforderlich.")
            store.set_secret(f"connections.mqtt.{ref}.password", password)
    elif clean_kind == "email":
        rows[ref] = {
            "smtp_host": str(row_value.get("smtp_host", "")).strip(),
            "port": int(row_value.get("port", 587) or 587),
            "user": str(row_value.get("user", "")).strip(),
            "from_email": str(row_value.get("from_email", "")).strip(),
            "to_email": str(row_value.get("to_email", "")).strip(),
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "starttls": bool(row_value.get("starttls", True)),
            "use_ssl": bool(row_value.get("use_ssl", False)),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        password = str(row_value.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für SMTP-Passwörter erforderlich.")
            store.set_secret(f"connections.email.{ref}.password", password)
    elif clean_kind == "imap":
        rows[ref] = {
            "host": str(row_value.get("host", "")).strip(),
            "port": int(row_value.get("port", 993) or 993),
            "user": str(row_value.get("user", "")).strip(),
            "mailbox": str(row_value.get("mailbox", "INBOX")).strip() or "INBOX",
            "timeout_seconds": int(row_value.get("timeout_seconds", 10) or 10),
            "use_ssl": bool(row_value.get("use_ssl", True)),
            "title": str(row_value.get("title", "")).strip(),
            "description": str(row_value.get("description", "")).strip(),
            "aliases": list(row_value.get("aliases", []) if isinstance(row_value.get("aliases", []), list) else []),
            "tags": list(row_value.get("tags", []) if isinstance(row_value.get("tags", []), list) else []),
        }
        password = str(row_value.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für IMAP-Passwörter erforderlich.")
            store.set_secret(f"connections.imap.{ref}.password", password)
    else:
        raise ValueError("Connection-Typ wird im Chat noch nicht unterstützt.")

    write_raw_config(config_path, raw)
    return {"kind": clean_kind, "ref": ref, "success_message": spec["success_message"]}


def update_connection_profile(base_dir: Path, kind: str, ref_raw: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean_kind = str(kind or "").strip().lower().replace("-", "_")
    spec = CONNECTION_UPDATE_SPECS.get(clean_kind)
    if not spec:
        raise ValueError("Connection-Typ wird im Chat noch nicht für Update unterstützt.")

    ref = sanitize_connection_ref(ref_raw)
    if not ref:
        raise ValueError("Connection-Ref fehlt oder ist ungültig.")

    config_path = base_dir / "config" / "config.yaml"
    raw = read_raw_config(config_path)
    connections = raw.setdefault("connections", {})
    if not isinstance(connections, dict):
        raise ValueError("Ungültige Connection-Konfiguration.")
    section = str(spec["section"])
    rows = connections.setdefault(section, {})
    if not isinstance(rows, dict) or ref not in rows:
        raise ValueError(f"Connection-Profil '{ref}' nicht gefunden.")

    current = rows.get(ref, {})
    if not isinstance(current, dict):
        raise ValueError("Ungültige bestehende Connection-Daten.")
    row_value = dict(current)
    update_payload = sanitize_connection_payload(clean_kind, payload)
    store = get_secure_store_for_config(base_dir, raw)

    if clean_kind == "ssh":
        for field in ("host", "user", "key_path", "strict_host_key_checking"):
            value = update_payload.get(field, "")
            if field == "strict_host_key_checking":
                clean_value = str(value).strip()
                if clean_value:
                    row_value[field] = clean_value
                continue
            clean_value = str(value).strip()
            if clean_value:
                row_value[field] = clean_value
        if "port" in update_payload:
            row_value["port"] = int(update_payload.get("port", 22) or 22)
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 20) or 20)
        if "allow_commands" in update_payload and isinstance(update_payload.get("allow_commands"), list):
            row_value["allow_commands"] = list(update_payload.get("allow_commands"))
    elif clean_kind == "sftp":
        for field in ("host", "user", "key_path", "root_path"):
            value = str(update_payload.get(field, "")).strip()
            if value:
                row_value[field] = value
        if "port" in update_payload:
            row_value["port"] = int(update_payload.get("port", 22) or 22)
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
        password = str(update_payload.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für SFTP-Passwörter erforderlich.")
            store.set_secret(f"connections.sftp.{ref}.password", password)
    elif clean_kind == "smb":
        for field in ("host", "share", "user", "root_path"):
            value = str(update_payload.get(field, "")).strip()
            if value:
                row_value[field] = value
        if "port" in update_payload:
            row_value["port"] = int(update_payload.get("port", 445) or 445)
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
        password = str(update_payload.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für SMB-Passwörter erforderlich.")
            store.set_secret(f"connections.smb.{ref}.password", password)
    elif clean_kind == "discord":
        webhook_url = str(update_payload.get("webhook_url", "")).strip()
        if webhook_url:
            if not store:
                raise ValueError("Security Store ist für Discord-Webhooks erforderlich.")
            store.set_secret(f"connections.discord.{ref}.webhook_url", webhook_url)
        for field, default in (
            ("timeout_seconds", 10),
            ("send_test_messages", True),
            ("allow_skill_messages", True),
            ("alert_skill_errors", False),
            ("alert_safe_fix", False),
            ("alert_connection_changes", False),
            ("alert_system_events", False),
        ):
            if field in update_payload:
                value = update_payload.get(field, default)
                row_value[field] = int(value or default) if field == "timeout_seconds" else bool(value)
    elif clean_kind == "rss":
        feed_url = str(update_payload.get("feed_url", "")).strip()
        if feed_url:
            row_value["feed_url"] = feed_url
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
    elif clean_kind == "webhook":
        url = str(update_payload.get("url", "")).strip()
        if url:
            if not store:
                raise ValueError("Security Store ist für Webhook-URLs erforderlich.")
            store.set_secret(f"connections.webhook.{ref}.url", url)
        for field, default in (("timeout_seconds", 10), ("method", "POST"), ("content_type", "application/json")):
            if field in update_payload:
                value = update_payload.get(field, default)
                row_value[field] = int(value or default) if field == "timeout_seconds" else str(value).strip().upper() if field == "method" else str(value).strip() or default
    elif clean_kind == "http_api":
        base_url = str(update_payload.get("base_url", "")).strip()
        if base_url:
            row_value["base_url"] = base_url
        for field, default in (("timeout_seconds", 10), ("health_path", "/"), ("method", "GET")):
            if field in update_payload:
                value = update_payload.get(field, default)
                row_value[field] = int(value or default) if field == "timeout_seconds" else str(value).strip().upper() if field == "method" else str(value).strip() or default
        auth_token = str(update_payload.get("auth_token", "")).strip()
        if auth_token:
            if not store:
                raise ValueError("Security Store ist für HTTP-API-Tokens erforderlich.")
            store.set_secret(f"connections.http_api.{ref}.auth_token", auth_token)
    elif clean_kind == "mqtt":
        for field in ("host", "user", "topic"):
            value = str(update_payload.get(field, "")).strip()
            if value:
                row_value[field] = value
        if "port" in update_payload:
            row_value["port"] = int(update_payload.get("port", 1883) or 1883)
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
        if "use_tls" in update_payload:
            row_value["use_tls"] = bool(update_payload.get("use_tls"))
        password = str(update_payload.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für MQTT-Passwörter erforderlich.")
            store.set_secret(f"connections.mqtt.{ref}.password", password)
    elif clean_kind == "email":
        for field in ("smtp_host", "user", "from_email", "to_email"):
            value = str(update_payload.get(field, "")).strip()
            if value:
                row_value[field] = value
        if "port" in update_payload:
            row_value["port"] = int(update_payload.get("port", 587) or 587)
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
        if "starttls" in update_payload:
            row_value["starttls"] = bool(update_payload.get("starttls"))
        if "use_ssl" in update_payload:
            row_value["use_ssl"] = bool(update_payload.get("use_ssl"))
        password = str(update_payload.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für SMTP-Passwörter erforderlich.")
            store.set_secret(f"connections.email.{ref}.password", password)
    elif clean_kind == "imap":
        for field in ("host", "user", "mailbox"):
            value = str(update_payload.get(field, "")).strip()
            if value:
                row_value[field] = value
        if "port" in update_payload:
            row_value["port"] = int(update_payload.get("port", 993) or 993)
        if "timeout_seconds" in update_payload:
            row_value["timeout_seconds"] = int(update_payload.get("timeout_seconds", 10) or 10)
        if "use_ssl" in update_payload:
            row_value["use_ssl"] = bool(update_payload.get("use_ssl"))
        password = str(update_payload.get("password", "")).strip()
        if password:
            if not store:
                raise ValueError("Security Store ist für IMAP-Passwörter erforderlich.")
            store.set_secret(f"connections.imap.{ref}.password", password)
    else:
        raise ValueError("Connection-Typ wird im Chat noch nicht unterstützt.")

    for field in ("title", "description"):
        if field in update_payload:
            row_value[field] = str(update_payload.get(field, "")).strip()
    for field in ("aliases", "tags"):
        if field in update_payload and isinstance(update_payload.get(field), list):
            row_value[field] = list(update_payload.get(field))

    rows[ref] = row_value
    write_raw_config(config_path, raw)
    return {"kind": clean_kind, "ref": ref, "success_message": spec["success_message"]}
