from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from aria.modules.connections_profiles.admin import CONNECTION_ADMIN_SPECS
from aria.modules.connections_catalog.catalog import connection_menu_meta, normalize_connection_kind
from aria.modules.runtime_guardrails.guardrails import (
    guardrail_kind_label,
    guardrail_kind_options,
    normalize_guardrail_kind,
)
from aria.modules.ssh_admin_ui.support import derive_matching_sftp_ref as provider_derive_matching_sftp_ref
from aria.modules.ssh_admin_ui.support import ensure_ssh_keypair as provider_ensure_ssh_keypair
from aria.modules.ssh_admin_ui.support import friendly_ssh_setup_error as provider_friendly_ssh_setup_error
from aria.modules.ssh_admin_ui.support import perform_ssh_key_exchange as provider_perform_ssh_key_exchange
from aria.modules.ssh_admin_ui.support import read_ssh_connection_profiles
from aria.modules.ssh_admin_ui.support import ssh_keys_dir as provider_ssh_keys_dir
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.qdrant_gateway.client import create_async_qdrant_client
from aria.modules.config_ui.misc_helpers import sanitize_reference_name_local


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
SAMPLE_CONNECTIONS_DIR = Path(__file__).resolve().parents[3] / "samples" / "connections"
SAMPLE_GUARDRAILS_DIR = Path(__file__).resolve().parents[3] / "samples" / "security"
_CONNECTION_SUPPORT_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _connection_support_text(key: str, default: str = "", **values: object) -> str:
    template = _CONNECTION_SUPPORT_I18N.t("de", f"connection_support_helpers.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


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
    return provider_ssh_keys_dir(base_dir)


def ensure_ssh_keypair_impl(base_dir: Path, ref: str, overwrite: bool = False) -> Path:
    return provider_ensure_ssh_keypair(base_dir, ref, overwrite=overwrite)


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
    return read_ssh_connection_profiles(read_raw_config, sanitize_connection_name, read_connection_metadata)


def normalize_connection_meta_list(raw: str) -> list[str]:
    items: list[str] = []
    for part in re.split(r"[\n,]+", str(raw or "")):
        clean = str(part).strip()
        if clean and clean not in items:
            items.append(clean)
    return items[:12]


def friendly_ssh_setup_error_impl(lang: str, exc: Exception) -> str:
    return provider_friendly_ssh_setup_error(lang, exc)


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
    return provider_derive_matching_sftp_ref(ssh_ref)


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
    return provider_perform_ssh_key_exchange(
        base_dir,
        ref=ref,
        host=host,
        port=port,
        profile_user=profile_user,
        login_user=login_user,
        login_password=login_password,
        connection_support_text=_connection_support_text,
    )
