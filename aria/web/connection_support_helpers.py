from __future__ import annotations

import os
import re
import shlex
import socket
import subprocess
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from aria.core.connection_admin import CONNECTION_ADMIN_SPECS
from aria.core.connection_catalog import connection_menu_meta, normalize_connection_kind
from aria.core.guardrails import (
    guardrail_kind_label,
    guardrail_kind_options,
    normalize_guardrail_kind,
)
from aria.core.qdrant_client import create_async_qdrant_client
from aria.web.config_misc_helpers import sanitize_reference_name_local


StringSanitizer = Callable[[str | None], str]
RawConfigReader = Callable[[], dict[str, Any]]

_RSS_DEDUPE_IGNORED_QUERY_KEYS = {
    "wt_mc",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "mkt_tok",
}
SAMPLE_CONNECTIONS_DIR = Path(__file__).resolve().parents[2] / "samples" / "connections"
SAMPLE_GUARDRAILS_DIR = Path(__file__).resolve().parents[2] / "samples" / "security"


def wipe_directory_contents(path: Path) -> int:
    removed = 0
    if not path.exists():
        return removed
    for item in path.iterdir():
        try:
            if item.is_dir():
                for child in item.rglob("*"):
                    with suppress(OSError):
                        if child.is_file() or child.is_symlink():
                            child.unlink()
                            removed += 1
                for child in sorted(item.rglob("*"), reverse=True):
                    with suppress(OSError):
                        if child.is_dir():
                            child.rmdir()
                with suppress(OSError):
                    item.rmdir()
            else:
                item.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def apply_factory_reset_to_raw_config(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw or {})

    connections = data.get("connections")
    if not isinstance(connections, dict):
        connections = {}
    for kind in CONNECTION_ADMIN_SPECS.keys():
        connections[kind] = {}
    data["connections"] = connections

    security = data.get("security")
    if not isinstance(security, dict):
        security = {}
    security["bootstrap_locked"] = False
    security["guardrails"] = {}
    data["security"] = security

    skills = data.get("skills")
    if not isinstance(skills, dict):
        skills = {}
    skills["custom"] = {}
    data["skills"] = skills

    channels = data.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    api = channels.get("api")
    if not isinstance(api, dict):
        api = {}
    api["auth_token"] = ""
    channels["api"] = api
    data["channels"] = channels

    ui = data.get("ui")
    if not isinstance(ui, dict):
        ui = {}
    ui["debug_mode"] = False
    data["ui"] = ui
    return data


async def clear_qdrant_factory_data(memory_cfg: Any) -> int:
    if not bool(getattr(memory_cfg, "enabled", False)):
        return 0
    if str(getattr(memory_cfg, "backend", "")).strip().lower() != "qdrant":
        return 0
    qdrant_url = str(getattr(memory_cfg, "qdrant_url", "")).strip()
    if not qdrant_url:
        return 0
    client = create_async_qdrant_client(
        url=qdrant_url,
        api_key=(str(getattr(memory_cfg, "qdrant_api_key", "")).strip() or None),
        timeout=10,
    )
    try:
        response = await client.get_collections()
        collections = list(getattr(response, "collections", []) or [])
        names = [str(getattr(row, "name", "")).strip() for row in collections if str(getattr(row, "name", "")).strip()]
        for name in names:
            await client.delete_collection(collection_name=name)
        return len(names)
    finally:
        with suppress(Exception):
            await client.close()


def ssh_keys_dir_impl(base_dir: Path) -> Path:
    path = (base_dir / "data" / "ssh_keys").resolve()
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def ensure_ssh_keypair_impl(base_dir: Path, ref: str, overwrite: bool = False) -> Path:
    key_dir = ssh_keys_dir_impl(base_dir)
    key_path = key_dir / f"{ref}_ed25519"
    pub_path = key_path.with_suffix(".pub")
    key_exists = key_path.exists() or pub_path.exists()
    if key_exists and not overwrite:
        return key_path
    if key_exists and overwrite:
        with suppress(OSError):
            key_path.unlink()
        with suppress(OSError):
            pub_path.unlink()
    comment = f"aria-{ref}@{socket.gethostname()}"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", comment],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key_path


def read_connection_metadata(value: dict[str, Any]) -> dict[str, Any]:
    title = str(value.get("title", "")).strip()
    description = str(value.get("description", "")).strip()
    aliases = [str(item).strip() for item in value.get("aliases", []) if str(item).strip()] if isinstance(value.get("aliases", []), list) else []
    tags = [str(item).strip() for item in value.get("tags", []) if str(item).strip()] if isinstance(value.get("tags", []), list) else []
    return {
        "title": title,
        "description": description,
        "aliases": aliases,
        "tags": tags,
        "aliases_text": ", ".join(aliases),
        "tags_text": ", ".join(tags),
        "meta_present": bool(title or description or aliases or tags),
    }


def read_ssh_connections_impl(read_raw_config: RawConfigReader, sanitize_connection_name: StringSanitizer) -> dict[str, dict[str, Any]]:
    raw = read_raw_config()
    connections = raw.get("connections", {})
    if not isinstance(connections, dict):
        return {}
    ssh = connections.get("ssh", {})
    if not isinstance(ssh, dict):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for key, value in ssh.items():
        ref = sanitize_connection_name(key)
        if not ref or not isinstance(value, dict):
            continue
        rows[ref] = {
            "host": str(value.get("host", "")).strip(),
            "port": int(value.get("port", 22) or 22),
            "user": str(value.get("user", "")).strip(),
            "service_url": str(value.get("service_url", "")).strip(),
            "key_path": str(value.get("key_path", "")).strip(),
            "timeout_seconds": int(value.get("timeout_seconds", 20) or 20),
            "strict_host_key_checking": str(value.get("strict_host_key_checking", "accept-new")).strip() or "accept-new",
            "allow_commands": list(value.get("allow_commands", []) if isinstance(value.get("allow_commands", []), list) else []),
            "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
            **read_connection_metadata(value),
        }
    return rows


def normalize_connection_meta_list(raw: str) -> list[str]:
    items: list[str] = []
    for part in re.split(r"[\n,]+", str(raw or "")):
        clean = str(part).strip()
        if clean and clean not in items:
            items.append(clean)
    return items[:12]


def friendly_ssh_setup_error_impl(lang: str, exc: Exception) -> str:
    is_de = str(lang or "de").strip().lower().startswith("de")
    if isinstance(exc, FileNotFoundError) and str(getattr(exc, "filename", "")).strip() == "ssh-keygen":
        if is_de:
            return (
                "ssh-keygen wurde auf diesem Host nicht gefunden. "
                "Bitte OpenSSH-Client/ssh-keygen installieren oder einen vorhandenen privaten Key manuell eintragen."
            )
        return (
            "ssh-keygen was not found on this host. "
            "Please install the OpenSSH client/ssh-keygen or enter an existing private key manually."
        )
    if isinstance(exc, ValueError):
        detail = str(exc).strip()
        if detail:
            return detail
    return "SSH-Key konnte nicht erzeugt werden." if is_de else "SSH key could not be generated."


def build_connection_metadata(
    title: str = "",
    description: str = "",
    aliases_text: str = "",
    tags_text: str = "",
) -> dict[str, Any]:
    return {
        "title": str(title).strip(),
        "description": str(description).strip(),
        "aliases": normalize_connection_meta_list(aliases_text),
        "tags": normalize_connection_meta_list(tags_text),
    }


def derive_matching_sftp_ref(ssh_ref: str) -> str:
    clean_ref = str(ssh_ref or "").strip()
    if not clean_ref:
        return "sftp-profile"
    for suffix in ("-ssh", "_ssh"):
        if clean_ref.endswith(suffix):
            return f"{clean_ref[:-len(suffix)]}{suffix[0]}sftp"
    return f"{clean_ref}-sftp"


def normalize_rss_feed_url_for_dedupe(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    scheme = str(parts.scheme or "").strip().lower()
    hostname = str(parts.hostname or "").strip().lower()
    if not scheme or not hostname:
        return raw
    netloc = hostname
    if parts.port and not ((scheme == "http" and parts.port == 80) or (scheme == "https" and parts.port == 443)):
        netloc = f"{hostname}:{parts.port}"
    path = str(parts.path or "").strip()
    if path == "/":
        path = ""
    elif path:
        path = path.rstrip("/")
    query_pairs: list[tuple[str, str]] = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        lower_key = str(key or "").strip().lower()
        if lower_key.startswith("utm_") or lower_key in _RSS_DEDUPE_IGNORED_QUERY_KEYS:
            continue
        query_pairs.append((str(key), str(item)))
    query_pairs.sort(key=lambda pair: (pair[0].strip().lower(), pair[1]))
    return urlunsplit((scheme, netloc, path, urlencode(query_pairs, doseq=True), ""))


def split_guardrail_terms(value: str) -> list[str]:
    rows = [item.strip() for item in re.split(r"[\n,;]+", str(value or "")) if item.strip()]
    seen: set[str] = set()
    clean: list[str] = []
    for row in rows:
        lowered = row.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        clean.append(row[:160])
    return clean[:40]


def build_connection_ref_options(rows: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for ref in sorted(rows.keys()):
        row = rows.get(ref, {})
        title = str(row.get("title", "")).strip() if isinstance(row, dict) else ""
        label = f"{title} · {ref}" if title and title != ref else ref
        options.append({"ref": ref, "label": label})
    return options


def build_sample_connection_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not SAMPLE_CONNECTIONS_DIR.exists():
        return rows
    for path in sorted(SAMPLE_CONNECTIONS_DIR.glob("*.sample.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(payload, dict):
            continue
        sample_connections = payload.get("connections")
        if not isinstance(sample_connections, dict) or not sample_connections:
            continue
        kind_key = str(next(iter(sample_connections.keys()), "")).strip()
        kind = normalize_connection_kind(kind_key)
        profiles = sample_connections.get(kind_key)
        if not kind or not isinstance(profiles, dict) or not profiles:
            continue
        ref = str(next(iter(profiles.keys()), "")).strip()
        profile = profiles.get(ref)
        if not isinstance(profile, dict):
            continue
        rows.append(
            {
                "file_name": path.name,
                "kind": kind,
                "label": str(connection_menu_meta(kind).get("label") or kind.upper()).strip(),
                "ref": ref,
                "title": str(profile.get("title", "")).strip() or ref or path.stem,
                "description": str(profile.get("description", "")).strip(),
            }
        )
    return rows


def build_sample_guardrail_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not SAMPLE_GUARDRAILS_DIR.exists():
        return rows
    for path in sorted(SAMPLE_GUARDRAILS_DIR.glob("*.sample.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(payload, dict):
            continue
        security = payload.get("security")
        if not isinstance(security, dict):
            continue
        guardrails = security.get("guardrails")
        if not isinstance(guardrails, dict) or not guardrails:
            continue
        valid_refs: list[str] = []
        kind_labels: list[str] = []
        for raw_ref, value in guardrails.items():
            ref = sanitize_reference_name_local(str(raw_ref).strip())
            if not ref or not isinstance(value, dict):
                continue
            clean_kind = normalize_guardrail_kind(str(value.get("kind", "")).strip() or "ssh_command")
            if clean_kind not in guardrail_kind_options():
                continue
            valid_refs.append(ref)
            kind_label = guardrail_kind_label(clean_kind)
            if kind_label not in kind_labels:
                kind_labels.append(kind_label)
        if not valid_refs:
            continue
        title = str(payload.get("title", "")).strip() or str(payload.get("name", "")).strip() or "Guardrail Starter Pack"
        description = str(payload.get("description", "")).strip() or f"{len(valid_refs)} sample guardrails for common ARIA connections."
        rows.append(
            {
                "file_name": path.name,
                "title": title,
                "description": description,
                "profile_count": str(len(valid_refs)),
                "profile_refs": ", ".join(valid_refs[:4]),
                "kind_labels": ", ".join(kind_labels),
            }
        )
    return rows


def perform_ssh_key_exchange_impl(
    base_dir: Path,
    *,
    ref: str,
    host: str,
    port: int,
    profile_user: str,
    login_user: str,
    login_password: str,
) -> tuple[str, Path]:
    if not login_password.strip():
        raise ValueError("Passwort fehlt.")
    clean_host = str(host).strip()
    if not clean_host:
        raise ValueError("Host/IP fehlt im Connection-Profil.")
    clean_user = str(login_user or profile_user).strip()
    if not clean_user:
        raise ValueError("SSH-User fehlt (im Profil oder Formular).")

    key_path = ensure_ssh_keypair_impl(base_dir, ref, overwrite=False)
    pub_path = key_path.with_suffix(".pub")
    if not pub_path.exists():
        raise ValueError("Public Key nicht gefunden.")
    pub_key = pub_path.read_text(encoding="utf-8").strip()
    if not pub_key:
        raise ValueError("Public Key ist leer.")

    try:
        import paramiko  # type: ignore[import-not-found]
    except Exception as exc:
        raise ValueError("Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=clean_host,
            port=max(1, int(port)),
            username=clean_user,
            password=login_password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
        key_q = shlex.quote(pub_key)
        remote_cmd = (
            "umask 077; "
            "mkdir -p ~/.ssh; "
            "touch ~/.ssh/authorized_keys; "
            "chmod 700 ~/.ssh; "
            "chmod 600 ~/.ssh/authorized_keys; "
            f"grep -qxF {key_q} ~/.ssh/authorized_keys || echo {key_q} >> ~/.ssh/authorized_keys"
        )
        _, stdout, stderr = client.exec_command(remote_cmd, timeout=15)
        exit_code = stdout.channel.recv_exit_status()
        err = (stderr.read() or b"").decode("utf-8", errors="replace").strip()
        if exit_code != 0:
            raise ValueError(err or "Remote-Fehler beim Schreiben von authorized_keys.")
    finally:
        with suppress(Exception):
            client.close()
    return clean_user, key_path
