from __future__ import annotations

import hmac
import json
import os
import re
import shlex
import socket
import subprocess
import xml.etree.ElementTree as ET
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlsplit, urlunsplit
from urllib.request import Request as URLRequest, urlopen

import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.connection_admin import CONNECTION_ADMIN_SPECS
from aria.core.connection_catalog import (
    connection_edit_page,
    connection_field_specs,
    connection_menu_rows,
    connection_menu_meta,
    connection_overview_meta,
    connection_ref_query_param,
    connection_status_meta,
    connection_template_name,
    connection_ui_sections,
    normalize_connection_kind,
)
from aria.core.config import (
    EmbeddingsConfig,
    UI_BACKGROUND_OPTIONS,
    UI_THEME_OPTIONS,
    normalize_ui_background,
    normalize_ui_theme,
    resolve_searxng_base_url,
)
from aria.core.config_backup import (
    backup_filename,
    build_config_backup_payload,
    parse_config_backup_payload,
    restore_config_backup_payload,
    summarize_config_backup_payload,
)
from aria.core.connection_health import delete_connection_health
from aria.core.connection_runtime import (
    build_connection_status_row,
    build_connection_status_rows,
    probe_searxng_stack_service,
)
from aria.core.guardrails import (
    guardrail_is_compatible,
    guardrail_kind_label,
    guardrail_kind_options,
    normalize_guardrail_kind,
)
from aria.core.pipeline import Pipeline
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.runtime_diagnostics import probe_embeddings, probe_llm
from aria.core.routing_admin import build_connection_routing_index_status
from aria.core.routing_admin import rebuild_connection_routing_index
from aria.core.routing_admin import test_connection_routing_query
from aria.core.rss_grouping import build_rss_status_groups
from aria.core.rss_grouping import load_cached_rss_status_groups, save_cached_rss_status_groups
from aria.core.rss_opml import build_opml_document, parse_opml_feeds
from aria.core.runtime_endpoint import cookie_should_be_secure, request_is_secure
from aria.core.embedding_client import EmbeddingClient


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Pipeline]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
StringSanitizer = Callable[[str | None], str]
RoleSanitizer = Callable[[str | None], str]
DefaultCollectionResolver = Callable[[str], str]
AuthEncoder = Callable[[str, str], str]
ActiveAdminCounter = Callable[[list[dict[str, Any]]], int]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
TextReader = Callable[[], str]
LinesParser = Callable[[str], list[str]]
ModelChecker = Callable[[str], bool]
PromptResolver = Callable[[str], Path]
PromptLister = Callable[[], list[dict[str, Any]]]
FileLister = Callable[[], list[str]]
FileResolver = Callable[[str], Path]
FileEditorEntryLister = Callable[[], list[dict[str, Any]]]
FileEditorFileResolver = Callable[[str], Path]
ModelLoader = Callable[[str, str], list[str]]
IntGetter = Callable[[], int]
ProfilesGetter = Callable[[dict[str, Any], str], dict[str, dict[str, Any]]]
ActiveProfileGetter = Callable[[dict[str, Any], str], str]
ActiveProfileSetter = Callable[[dict[str, Any], str, str], None]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]
LanguageRowsGetter = Callable[[], list[str]]
LanguageResolver = Callable[[str, str], str]
CacheClearer = Callable[[], None]
CustomSkillManifestLoader = Callable[[], tuple[list[dict[str, Any]], list[str]]]
CustomSkillFileResolver = Callable[[str], Path]
CustomSkillSaver = Callable[[dict[str, Any]], dict[str, Any]]
TriggerIndexBuilder = Callable[[], dict[str, Any]]
SkillRoutingInfoFormatter = Callable[[str, str], str]
KeywordSuggester = Callable[..., Awaitable[list[str]]]
_RSS_DEDUPE_IGNORED_QUERY_KEYS = {
    "wt_mc",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "mkt_tok",
}
_RSS_METADATA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 ARIA/1.0"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}
_WEB_METADATA_HEADERS = {
    **_RSS_METADATA_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}
_SAMPLE_CONNECTIONS_DIR = Path(__file__).resolve().parents[2] / "samples" / "connections"
_SAMPLE_GUARDRAILS_DIR = Path(__file__).resolve().parents[2] / "samples" / "security"
EMBEDDING_SWITCH_CONFIRM_PHRASE = "EMBEDDINGS WECHSELN"
_SEARXNG_CATEGORY_OPTIONS: list[tuple[str, str]] = [
    ("general", "General"),
    ("news", "News"),
    ("it", "IT"),
    ("science", "Science"),
    ("videos", "Videos"),
]
_SEARXNG_ENGINE_OPTIONS: list[tuple[str, str]] = [
    ("duckduckgo", "DuckDuckGo"),
    ("startpage", "Startpage"),
    ("brave", "Brave"),
    ("qwant", "Qwant"),
    ("wikipedia", "Wikipedia"),
    ("wikibooks", "WikiBooks"),
    ("youtube", "YouTube"),
    ("github", "GitHub"),
    ("stackoverflow", "Stack Overflow"),
    ("arxiv", "arXiv"),
]


def _sanitize_csrf_token_local(value: str | None) -> str:
    token = str(value or "").strip()
    token = re.sub(r"[^A-Za-z0-9_-]", "", token)
    return token[:256]


def _sanitize_reference_name_local(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_-]", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    return raw[:48]


def _is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    supplied = _sanitize_csrf_token_local(submitted_token)
    expected = _sanitize_csrf_token_local(expected_token)
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


class _DynamicProxy:
    def __init__(self, getter: Callable[[], Any]) -> None:
        self._getter = getter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._getter(), name)


@dataclass(slots=True)
class ConfigRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    error_interpreter_path: Path
    llm_provider_presets: dict[str, dict[str, str]]
    embedding_provider_presets: dict[str, dict[str, str]]
    auth_cookie: str
    lang_cookie: str
    username_cookie: str
    memory_collection_cookie: str
    get_auth_session_max_age_seconds: IntGetter
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_username_from_request: UsernameResolver
    get_auth_session_from_request: AuthSessionResolver
    sanitize_role: RoleSanitizer
    sanitize_username: StringSanitizer
    sanitize_connection_name: StringSanitizer
    sanitize_skill_id: StringSanitizer
    sanitize_profile_name: StringSanitizer
    default_memory_collection_for_user: DefaultCollectionResolver
    encode_auth_session: AuthEncoder
    get_auth_manager: Callable[[], Any | None]
    active_admin_count: ActiveAdminCounter
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    read_error_interpreter_raw: TextReader
    parse_lines: LinesParser
    is_ollama_model: ModelChecker
    resolve_prompt_file: PromptResolver
    list_prompt_files: PromptLister
    list_editable_files: FileLister
    resolve_edit_file: FileResolver
    list_file_editor_entries: FileEditorEntryLister
    resolve_file_editor_file: FileEditorFileResolver
    load_models_from_api_base: ModelLoader
    get_profiles: ProfilesGetter
    get_active_profile_name: ActiveProfileGetter
    set_active_profile: ActiveProfileSetter
    get_secure_store: SecureStoreGetter
    lang_flag: Callable[[str], str]
    lang_label: Callable[[str], str]
    available_languages: LanguageRowsGetter
    resolve_lang: LanguageResolver
    clear_i18n_cache: CacheClearer
    load_custom_skill_manifests: CustomSkillManifestLoader
    custom_skill_file: CustomSkillFileResolver
    save_custom_skill_manifest: CustomSkillSaver
    refresh_skill_trigger_index: TriggerIndexBuilder
    format_skill_routing_info: SkillRoutingInfoFormatter
    suggest_skill_keywords_with_llm: KeywordSuggester


def _size_human(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _format_session_timeout_label(total_minutes: int, lang: str = "de") -> str:
    minutes = max(1, int(total_minutes or 0))
    days, remainder = divmod(minutes, 60 * 24)
    hours, mins = divmod(remainder, 60)

    if str(lang or "de").lower().startswith("de"):
        units = {
            "day_singular": "Tag",
            "day_plural": "Tage",
            "hour_singular": "Stunde",
            "hour_plural": "Stunden",
            "minute_singular": "Minute",
            "minute_plural": "Minuten",
        }
    else:
        units = {
            "day_singular": "day",
            "day_plural": "days",
            "hour_singular": "hour",
            "hour_plural": "hours",
            "minute_singular": "minute",
            "minute_plural": "minutes",
        }

    parts: list[str] = []
    if days:
        parts.append(f"{days} {units['day_singular'] if days == 1 else units['day_plural']}")
    if hours:
        parts.append(f"{hours} {units['hour_singular'] if hours == 1 else units['hour_plural']}")
    if mins and not days:
        parts.append(f"{mins} {units['minute_singular'] if mins == 1 else units['minute_plural']}")
    if not parts:
        parts.append(f"{minutes} {units['minute_singular'] if minutes == 1 else units['minute_plural']}")
    return " ".join(parts)


def _resolve_embedding_model_label(model: str, api_base: str | None = None) -> str:
    config = EmbeddingsConfig(model=str(model or "").strip(), api_base=str(api_base or "").strip() or None)
    return EmbeddingClient(config)._resolve_model()


def _embedding_fingerprint_for_values(model: str, api_base: str | None = None) -> str:
    config = EmbeddingsConfig(model=str(model or "").strip(), api_base=str(api_base or "").strip() or None)
    return EmbeddingClient(config).fingerprint()


def _short_fingerprint(value: str, length: int = 12) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    return clean[: max(6, int(length))]


def _memory_point_totals(stats: list[dict[str, Any]] | None) -> tuple[int, int]:
    rows = list(stats or [])
    total_points = sum(int(row.get("points", 0) or 0) for row in rows)
    return total_points, len(rows)


def _embedding_switch_requires_confirmation(
    current_memory_fingerprint: str,
    new_fingerprint: str,
    memory_point_count: int,
) -> bool:
    return (
        int(memory_point_count or 0) > 0
        and str(current_memory_fingerprint or "").strip() != str(new_fingerprint or "").strip()
    )


def _build_editor_entries_from_paths(base_dir: Path, rel_paths: list[str], resolver: FileResolver) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel_path in rel_paths:
        try:
            path = resolver(rel_path)
            stat = path.stat()
            rows.append(
                {
                    "path": rel_path,
                    "name": path.name,
                    "size": int(stat.st_size),
                    "size_label": _size_human(int(stat.st_size)),
                    "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
        except (OSError, ValueError):
            continue
    return rows


def _wipe_directory_contents(path: Path) -> int:
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


def _apply_factory_reset_to_raw_config(raw: dict[str, Any]) -> dict[str, Any]:
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


async def _clear_qdrant_factory_data(memory_cfg: Any) -> int:
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


def _ssh_keys_dir_impl(base_dir: Path) -> Path:
    path = (base_dir / "data" / "ssh_keys").resolve()
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _ensure_ssh_keypair_impl(base_dir: Path, ref: str, overwrite: bool = False) -> Path:
    key_dir = _ssh_keys_dir_impl(base_dir)
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


def _read_ssh_connections_impl(read_raw_config: RawConfigReader, sanitize_connection_name: StringSanitizer) -> dict[str, dict[str, Any]]:
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
            **_read_connection_metadata(value),
        }
    return rows


def _normalize_connection_meta_list(raw: str) -> list[str]:
    items: list[str] = []
    for part in re.split(r"[\n,]+", str(raw or "")):
        clean = str(part).strip()
        if clean and clean not in items:
            items.append(clean)
    return items[:12]


def _friendly_ssh_setup_error_impl(lang: str, exc: Exception) -> str:
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


def _read_connection_metadata(value: dict[str, Any]) -> dict[str, Any]:
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


def _build_connection_metadata(
    title: str = "",
    description: str = "",
    aliases_text: str = "",
    tags_text: str = "",
) -> dict[str, Any]:
    return {
        "title": str(title).strip(),
        "description": str(description).strip(),
        "aliases": _normalize_connection_meta_list(aliases_text),
        "tags": _normalize_connection_meta_list(tags_text),
    }


def _derive_matching_sftp_ref(ssh_ref: str) -> str:
    clean_ref = str(ssh_ref or "").strip()
    if not clean_ref:
        return "sftp-profile"
    for suffix in ("-ssh", "_ssh"):
        if clean_ref.endswith(suffix):
            return f"{clean_ref[:-len(suffix)]}{suffix[0]}sftp"
    return f"{clean_ref}-sftp"


def _normalize_rss_feed_url_for_dedupe(value: str) -> str:
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
    if parts.port and not (
        (scheme == "http" and parts.port == 80)
        or (scheme == "https" and parts.port == 443)
    ):
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


def _split_guardrail_terms(value: str) -> list[str]:
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


def _build_connection_ref_options(rows: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for ref in sorted(rows.keys()):
        row = rows.get(ref, {})
        title = str(row.get("title", "")).strip() if isinstance(row, dict) else ""
        label = f"{title} · {ref}" if title and title != ref else ref
        options.append({"ref": ref, "label": label})
    return options


def _build_sample_connection_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not _SAMPLE_CONNECTIONS_DIR.exists():
        return rows
    for path in sorted(_SAMPLE_CONNECTIONS_DIR.glob("*.sample.yaml")):
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


def _build_sample_guardrail_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not _SAMPLE_GUARDRAILS_DIR.exists():
        return rows
    for path in sorted(_SAMPLE_GUARDRAILS_DIR.glob("*.sample.yaml")):
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
            ref = _sanitize_reference_name_local(str(raw_ref).strip())
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
        description = (
            str(payload.get("description", "")).strip()
            or f"{len(valid_refs)} sample guardrails for common ARIA connections."
        )
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


def _build_schema_form_fields(
    *,
    kind: str,
    values: dict[str, Any],
    prefix: str,
    ref_value: str,
    include_ref: bool = True,
    placeholders: dict[str, str] | None = None,
    required_fields: set[str] | None = None,
    select_options: dict[str, list[str]] | None = None,
    datalist_options: dict[str, list[str]] | None = None,
    boolean_defaults: dict[str, bool] | None = None,
    secrets_with_hints: dict[str, str] | None = None,
    field_hints: dict[str, str] | None = None,
    ordered_fields: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    hint_keys = {
        ("webhook", "url"): "config_conn.webhook_secret_hint",
        ("http_api", "auth_token"): "config_conn.http_api_token_hint",
        ("mqtt", "password"): "config_conn.mqtt_password_hint",
        ("email", "password"): "config_conn.email_password_hint",
        ("imap", "password"): "config_conn.imap_password_hint",
        ("smb", "password"): "config_conn.smb_password_store_hint",
        ("sftp", "password"): "config_conn.sftp_password_store_hint",
        ("sftp", "key_path"): "config_conn.sftp_key_path_hint",
        ("discord", "webhook_url"): "config_conn.discord_password_hint",
        ("ssh", "allow_commands"): "config_conn.allow_commands_hint",
        ("ssh", "service_url"): "config_conn.ssh_service_url_hint",
    }
    label_keys = {
        "connection_ref": "config_conn.profile_ref",
        "feed_url": "config_conn.rss_feed_url",
        "timeout_seconds": "config_conn.timeout",
        "method": "config_conn.webhook_method",
        "content_type": "config_conn.webhook_content_type",
        "base_url": "config_conn.http_api_base_url",
        "language": "config_conn.searxng_language",
        "safe_search": "config_conn.searxng_safe_search",
        "categories": "config_conn.searxng_categories",
        "engines": "config_conn.searxng_engines",
        "time_range": "config_conn.searxng_time_range",
        "max_results": "config_conn.searxng_max_results",
        "health_path": "config_conn.http_api_health_path",
        "auth_token": "config_conn.http_api_auth_token",
        "host": "config_conn.host",
        "port": "config_conn.port",
        "user": "config_conn.user",
        "service_url": "config_conn.ssh_service_url",
        "topic": "config_conn.mqtt_topic",
        "smtp_host": "config_conn.email_smtp_host",
        "from_email": "config_conn.email_from",
        "to_email": "config_conn.email_to",
        "mailbox": "config_conn.imap_mailbox",
    }
    label_keys_by_kind = {
        ("smb", "share"): "config_conn.smb_share",
        ("smb", "root_path"): "config_conn.smb_root_path",
        ("smb", "password"): "config_conn.smb_password",
        ("sftp", "root_path"): "config_conn.sftp_root_path",
        ("sftp", "key_path"): "config_conn.sftp_key_path",
        ("sftp", "password"): "config_conn.sftp_password",
        ("discord", "webhook_url"): "config_conn.discord_webhook_url",
        ("discord", "send_test_messages"): "config_conn.discord_send_test_messages_toggle",
        ("discord", "allow_skill_messages"): "config_conn.discord_allow_skill_messages_toggle",
        ("discord", "alert_skill_errors"): "config_conn.discord_alert_skill_errors_toggle",
        ("discord", "alert_safe_fix"): "config_conn.discord_alert_safe_fix_toggle",
        ("discord", "alert_connection_changes"): "config_conn.discord_alert_connection_changes_toggle",
        ("discord", "alert_system_events"): "config_conn.discord_alert_system_events_toggle",
        ("ssh", "strict_host_key_checking"): "config_conn.host_key_checking",
        ("ssh", "allow_commands"): "config_conn.allow_commands",
    }
    specs = connection_field_specs(kind)
    placeholders = dict(placeholders or {})
    required_fields = set(required_fields or set())
    select_options = dict(select_options or {})
    datalist_options = dict(datalist_options or {})
    boolean_defaults = dict(boolean_defaults or {})
    secrets_with_hints = dict(secrets_with_hints or {})
    field_hints = dict(field_hints or {})
    clean_kind = normalize_connection_kind(kind)

    field_order = [*(["connection_ref"] if include_ref else []), *(ordered_fields or [])]
    grid_fields: list[dict[str, Any]] = []
    inline_fields: list[dict[str, Any]] = []
    secret_fields: list[dict[str, Any]] = []

    for name in field_order:
        if name == "connection_ref":
            grid_fields.append(
                {
                    "id": f"{prefix}_connection_ref",
                    "name": "connection_ref",
                    "label_key": label_keys.get("connection_ref", ""),
                    "label": "Profile name (ref)",
                    "type": "text",
                    "value": ref_value,
                    "required": True,
                    "placeholder": placeholders.get(name, "z.B. connection-ref"),
                }
            )
            continue

        spec = specs.get(name, {})
        if not spec:
            continue
        raw_value = values.get(name)
        field_type = str(spec.get("type", "str")).strip().lower()
        input_type = "text"
        if field_type == "int":
            input_type = "number"
        elif field_type == "bool":
            input_type = "checkbox"
        elif field_type == "list" and name not in select_options:
            input_type = "textarea"
        elif name in {"feed_url", "base_url", "url", "webhook_url"}:
            input_type = "url"
        elif name in {"from_email", "to_email"}:
            input_type = "email"
        elif name in {"password", "auth_token"}:
            input_type = "password"
        elif name in select_options:
            input_type = "select"

        if field_type == "list" and isinstance(raw_value, list):
            display_value: Any = "\n".join(str(item).strip() for item in raw_value if str(item).strip())
        else:
            display_value = raw_value if raw_value not in (None, "") else spec.get("default", "")

        field = {
            "id": f"{prefix}_{name}",
            "name": name,
            "label_key": label_keys_by_kind.get((clean_kind, name), label_keys.get(name, "")),
            "label": str(spec.get("label", name)).strip(),
            "type": input_type,
            "value": display_value,
            "required": name in required_fields,
            "placeholder": placeholders.get(name, ""),
            "min": spec.get("min"),
            "options": list(select_options.get(name, [])),
            "datalist_id": f"{prefix}_{name}_options" if datalist_options.get(name) else "",
            "datalist_options": list(datalist_options.get(name, [])),
            "checked": bool(raw_value) if raw_value is not None else bool(boolean_defaults.get(name, False)),
            "hint": field_hints.get(name, secrets_with_hints.get(name, "")),
            "hint_key": hint_keys.get((normalize_connection_kind(kind), name), ""),
            "rows": int(spec.get("rows", 4) or 4),
        }
        if input_type == "checkbox":
            inline_fields.append(field)
        elif input_type == "password":
            secret_fields.append(field)
        else:
            grid_fields.append(field)

    return {
        "grid_fields": grid_fields,
        "inline_fields": inline_fields,
        "secret_fields": secret_fields,
    }


def _build_schema_toggle_sections(
    *,
    kind: str,
    values: dict[str, Any],
    prefix: str,
    section_names: list[str],
) -> list[dict[str, Any]]:
    clean_kind = normalize_connection_kind(kind)
    specs = connection_field_specs(clean_kind)
    sections = connection_ui_sections(clean_kind)
    rows: list[dict[str, Any]] = []
    for section_name in section_names:
        section_spec = sections.get(section_name, {})
        cards: list[dict[str, Any]] = []
        for field_name, spec in specs.items():
            if str(spec.get("type", "")).strip().lower() != "bool":
                continue
            if str(spec.get("section", "")).strip() != section_name:
                continue
            raw_value = values.get(field_name)
            checked = bool(raw_value) if raw_value is not None else False
            if field_name in {"send_test_messages", "allow_skill_messages"} and raw_value is None:
                checked = True
            cards.append(
                {
                    "id": f"{prefix}_{field_name}",
                    "name": field_name,
                    "checked": checked,
                    "title_key": str(spec.get("title_key", "")).strip(),
                    "title": str(spec.get("title", spec.get("label", field_name))).strip(),
                    "hint_key": str(spec.get("hint_key", "")).strip(),
                    "hint": str(spec.get("hint", "")).strip(),
                    "toggle_key": str(spec.get("toggle_key", "")).strip(),
                    "toggle": str(spec.get("toggle", spec.get("label", field_name))).strip(),
                }
            )
        if not cards:
            continue
        rows.append(
            {
                "name": section_name,
                "title_key": str(section_spec.get("title_key", "")).strip(),
                "title": str(section_spec.get("title", section_name)).strip(),
                "hint_key": str(section_spec.get("hint_key", "")).strip(),
                "hint": str(section_spec.get("hint", "")).strip(),
                "cards": cards,
            }
        )
    return rows


def _build_connection_intro(
    *,
    kind: str,
    summary_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    meta = connection_menu_meta(kind)
    return {
        "title_key": str(meta.get("title_key") or "").strip(),
        "title": str(meta.get("label") or kind).strip(),
        "subtitle_key": str(meta.get("desc_key") or "").strip(),
        "subtitle": "",
        "back_url": "/config",
        "back_label_key": "config_conn.back_to_hub",
        "back_label": "Back to connection overview",
        "summary_cards": summary_cards,
    }


def _build_connection_status_block(
    *,
    kind: str,
    rows: list[dict[str, Any]],
    collapse_threshold: int = 0,
) -> dict[str, Any]:
    meta = connection_status_meta(kind)
    should_collapse = collapse_threshold > 0 and len(rows) >= collapse_threshold
    return {
        "title_key": str(meta.get("title_key") or "").strip(),
        "title": str(meta.get("title") or "").strip(),
        "hint_key": str(meta.get("hint_key") or "").strip(),
        "hint": str(meta.get("hint") or "").strip(),
        "empty_key": str(meta.get("empty_key") or "").strip(),
        "empty_text": str(meta.get("empty_text") or "").strip(),
        "rows": rows,
        "collapsed": should_collapse,
        "total_count": len(rows),
        "ok_count": sum(1 for item in rows if str(item.get("status", "")).strip().lower() == "ok"),
        "warn_count": sum(1 for item in rows if str(item.get("status", "")).strip().lower() == "warn"),
        "error_count": sum(1 for item in rows if str(item.get("status", "")).strip().lower() == "error"),
    }


def _connection_edit_url(kind: str, ref: str) -> str:
    route = connection_edit_page(kind)
    param = connection_ref_query_param(kind)
    clean_ref = str(ref or "").strip()
    if normalize_connection_kind(kind) == "rss" and clean_ref == "RSS":
        return route
    if not route:
        return ""
    if not clean_ref or not param:
        return route
    return f"{route}?{param}={quote_plus(clean_ref)}"


def _attach_connection_edit_urls(kind: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["edit_url"] = _connection_edit_url(kind, str(payload.get("ref", "")).strip())
        enriched.append(payload)
    return enriched


def _build_connection_summary_cards(
    *,
    kind: str,
    profiles: int,
    healthy: int,
    issues: int,
    extra_cards: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    meta = connection_overview_meta(kind)
    cards = [
        {
            "label_key": str(meta["profiles"].get("label_key") or "").strip(),
            "label": str(meta["profiles"].get("label") or "Profiles").strip(),
            "value": profiles,
            "hint_key": str(meta["profiles"].get("hint_key") or "").strip(),
            "hint": str(meta["profiles"].get("hint") or "").strip(),
        },
        {
            "label_key": str(meta["healthy"].get("label_key") or "").strip(),
            "label": str(meta["healthy"].get("label") or "Healthy").strip(),
            "value": healthy,
            "hint_key": str(meta["healthy"].get("hint_key") or "").strip(),
            "hint": str(meta["healthy"].get("hint") or "").strip(),
        },
        {
            "label_key": str(meta["issues"].get("label_key") or "").strip(),
            "label": str(meta["issues"].get("label") or "Issues").strip(),
            "value": issues,
            "hint_key": str(meta["issues"].get("hint_key") or "").strip(),
            "hint": str(meta["issues"].get("hint") or "").strip(),
        },
    ]
    for card in extra_cards or []:
        cards.append(dict(card))
    return cards


def _perform_ssh_key_exchange_impl(
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

    key_path = _ensure_ssh_keypair_impl(base_dir, ref, overwrite=False)
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


def register_config_routes(app: FastAPI, deps: ConfigRouteDeps) -> None:
    TEMPLATES = deps.templates
    BASE_DIR = deps.base_dir
    ERROR_INTERPRETER_PATH = deps.error_interpreter_path
    LLM_PROVIDER_PRESETS = deps.llm_provider_presets
    EMBEDDING_PROVIDER_PRESETS = deps.embedding_provider_presets
    AUTH_COOKIE = deps.auth_cookie
    USERNAME_COOKIE = deps.username_cookie
    MEMORY_COLLECTION_COOKIE = deps.memory_collection_cookie
    get_auth_session_max_age_seconds = deps.get_auth_session_max_age_seconds

    settings = _DynamicProxy(deps.get_settings)
    pipeline = _DynamicProxy(deps.get_pipeline)

    _get_username_from_request = deps.get_username_from_request
    _get_auth_session_from_request = deps.get_auth_session_from_request
    _sanitize_role = deps.sanitize_role
    _sanitize_username = deps.sanitize_username
    _sanitize_connection_name = deps.sanitize_connection_name
    _sanitize_skill_id = deps.sanitize_skill_id
    _sanitize_profile_name = deps.sanitize_profile_name
    _default_memory_collection_for_user = deps.default_memory_collection_for_user
    _encode_auth_session = deps.encode_auth_session
    _get_auth_manager = deps.get_auth_manager
    _active_admin_count = deps.active_admin_count
    _read_raw_config = deps.read_raw_config
    _write_raw_config = deps.write_raw_config
    _reload_runtime = deps.reload_runtime
    _read_error_interpreter_raw = deps.read_error_interpreter_raw
    _parse_lines = deps.parse_lines
    _is_ollama_model = deps.is_ollama_model
    _resolve_prompt_file = deps.resolve_prompt_file
    _list_prompt_files = deps.list_prompt_files
    _list_editable_files = deps.list_editable_files
    _resolve_edit_file = deps.resolve_edit_file
    _list_file_editor_entries = deps.list_file_editor_entries
    _resolve_file_editor_file = deps.resolve_file_editor_file
    _load_models_from_api_base = deps.load_models_from_api_base
    _get_profiles = deps.get_profiles
    _get_active_profile_name = deps.get_active_profile_name
    _set_active_profile = deps.set_active_profile
    _get_secure_store = deps.get_secure_store
    _lang_flag = deps.lang_flag
    _lang_label = deps.lang_label
    _load_custom_skill_manifests = deps.load_custom_skill_manifests
    _custom_skill_file = deps.custom_skill_file
    _save_custom_skill_manifest = deps.save_custom_skill_manifest
    _refresh_skill_trigger_index = deps.refresh_skill_trigger_index
    _format_skill_routing_info = deps.format_skill_routing_info
    _suggest_skill_keywords_with_llm = deps.suggest_skill_keywords_with_llm

    def _cookie_name_for_request(request: Request, key: str, fallback: str) -> str:
        cookie_names = getattr(request.state, "cookie_names", {}) or {}
        if isinstance(cookie_names, dict):
            candidate = str(cookie_names.get(key, "") or "").strip()
            if candidate:
                return candidate
        return fallback

    def _cookie_scope_for_request(request: Request) -> str:
        return str(getattr(request.state, "cookie_scope_source", "") or "").strip()

    prompts_root = (BASE_DIR / "prompts").resolve()
    skills_root = (BASE_DIR / "aria" / "skills").resolve()

    class _I18NProxy:
        def available_languages(self) -> list[str]:
            return deps.available_languages()

        def resolve_lang(self, code: str, default_lang: str = "de") -> str:
            return deps.resolve_lang(code, default_lang)

        def clear_cache(self) -> None:
            deps.clear_i18n_cache()

    I18N = _I18NProxy()

    def _msg(lang: str, de: str, en: str) -> str:
        return de if str(lang or "de").strip().lower().startswith("de") else en

    def _sanitize_return_to(value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        parsed = urlsplit(raw)
        path = str(parsed.path or "").strip()
        if not path.startswith("/") or path.startswith("//"):
            return ""
        cleaned = path
        if parsed.query:
            cleaned = f"{cleaned}?{parsed.query}"
        return cleaned

    def _referer_return_to(request: Request) -> str:
        referer = str(request.headers.get("referer", "") or "").strip()
        if not referer:
            return ""
        parsed = urlsplit(referer)
        referer_query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        candidate = _sanitize_return_to(referer_query.get("return_to"))
        if candidate:
            return candidate
        path = str(parsed.path or "").strip()
        if not path.startswith("/") or path.startswith("//"):
            return ""
        return _sanitize_return_to(f"{path}?{parsed.query}" if parsed.query else path)

    def _resolve_return_to(request: Request, *, fallback: str) -> str:
        current_path = str(request.url.path or "").strip()
        candidate = _sanitize_return_to(request.query_params.get("return_to"))
        if candidate and urlsplit(candidate).path != current_path:
            return candidate
        referer_target = _referer_return_to(request)
        if referer_target and urlsplit(referer_target).path != current_path:
            return referer_target
        return _sanitize_return_to(fallback) or "/"

    def _attach_return_to(url: str, return_to: str) -> str:
        target = _sanitize_return_to(return_to)
        if not target:
            return url
        parsed = urlsplit(url)
        pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "return_to"]
        pairs.append(("return_to", target))
        query = urlencode(pairs)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))

    def _redirect_with_return_to(
        url: str,
        request: Request,
        *,
        fallback: str,
        return_to: str | None = None,
    ) -> RedirectResponse:
        target = _sanitize_return_to(return_to) or _resolve_return_to(request, fallback=fallback)
        return RedirectResponse(url=_attach_return_to(url, target), status_code=303)

    def _set_logical_back_url(request: Request, *, fallback: str) -> str:
        target = _resolve_return_to(request, fallback=fallback)
        request.state.logical_back_url = target
        return target

    def _friendly_route_error(lang: str, exc: Exception, de_default: str, en_default: str) -> str:
        if isinstance(exc, ValueError):
            detail = str(exc).strip()
            if detail:
                return detail
        return _msg(lang, de_default, en_default)

    def _friendly_ssh_setup_error(lang: str, exc: Exception) -> str:
        return _friendly_ssh_setup_error_impl(lang, exc)

    async def _embedding_memory_guard_context(username: str) -> dict[str, Any]:
        memory_stats: list[dict[str, Any]] = []
        if getattr(pipeline, "memory_skill", None):
            with suppress(Exception):
                memory_stats = list(await pipeline.memory_skill.get_user_collection_stats(username))
        memory_point_count, memory_collection_count = _memory_point_totals(memory_stats)
        current_fingerprint = _embedding_fingerprint_for_values(
            settings.embeddings.model,
            settings.embeddings.api_base,
        )
        memory_fingerprint = str(getattr(settings.memory, "embedding_fingerprint", "") or "").strip() or current_fingerprint
        memory_model = str(getattr(settings.memory, "embedding_model", "") or "").strip() or _resolve_embedding_model_label(
            settings.embeddings.model,
            settings.embeddings.api_base,
        )
        return {
            "memory_stats": memory_stats,
            "memory_point_count": memory_point_count,
            "memory_collection_count": memory_collection_count,
            "current_fingerprint": current_fingerprint,
            "current_fingerprint_short": _short_fingerprint(current_fingerprint),
            "memory_fingerprint": memory_fingerprint,
            "memory_fingerprint_short": _short_fingerprint(memory_fingerprint),
            "memory_model": memory_model,
            "requires_switch_confirmation": memory_point_count > 0,
            "confirm_phrase": EMBEDDING_SWITCH_CONFIRM_PHRASE,
            "export_url": "/memories/export?type=all&sort=updated_desc",
            "memory_fingerprint_tracked": bool(str(getattr(settings.memory, "embedding_fingerprint", "") or "").strip()),
        }

    async def _guard_embedding_switch(
        *,
        username: str,
        new_model: str,
        new_api_base: str,
        confirm_switch: str,
        confirm_phrase: str,
    ) -> tuple[str, str]:
        new_fingerprint = _embedding_fingerprint_for_values(new_model, new_api_base)
        resolved_model = _resolve_embedding_model_label(new_model, new_api_base)
        guard = await _embedding_memory_guard_context(username)
        if _embedding_switch_requires_confirmation(
            guard["memory_fingerprint"],
            new_fingerprint,
            guard["memory_point_count"],
        ):
            confirmed = str(confirm_switch or "").strip().lower() in {"1", "true", "yes", "on"}
            typed_phrase = str(confirm_phrase or "").strip().upper()
            if not confirmed or typed_phrase != EMBEDDING_SWITCH_CONFIRM_PHRASE:
                raise ValueError(
                    "Embedding-Wechsel blockiert: Vorhandenes Memory/RAG wurde mit einem anderen Embedding-Fingerprint erstellt. "
                    f"Bitte zuerst exportieren ({guard['export_url']}) und den Wechsel bewusst bestaetigen "
                    f"({EMBEDDING_SWITCH_CONFIRM_PHRASE})."
                )
        return new_fingerprint, resolved_model

    def _connection_saved_test_info(kind_label: str, lang: str, *, success: bool) -> str:
        if success:
            return _msg(
                lang,
                f"{kind_label}-Profil gespeichert · Verbindung erfolgreich getestet",
                f"{kind_label} profile saved · connection test succeeded",
            )
        return _msg(
            lang,
            f"{kind_label}-Profil gespeichert · Verbindungstest fehlgeschlagen",
                f"{kind_label} profile saved · connection test failed",
        )

    def _active_profile_runtime_meta(raw: dict[str, Any], kind: str) -> dict[str, str]:
        active_name = _get_active_profile_name(raw, kind) or "default"
        if kind == "llm":
            current = settings.llm
        else:
            current = settings.embeddings
        return {
            "active_name": active_name,
            "model": str(getattr(current, "model", "") or "").strip(),
            "api_base": str(getattr(current, "api_base", "") or "").strip(),
        }

    def _profile_test_redirect_url(page: str, *, ok: bool, message: str) -> str:
        key = "info" if ok else "error"
        return f"{page}?test_status={'ok' if ok else 'error'}&{key}={quote_plus(str(message))}"

    def _profile_test_result_message(kind: str, active_name: str, result: dict[str, Any], lang: str) -> str:
        label = _msg(lang, "LLM-Profil", "LLM profile") if kind == "llm" else _msg(lang, "Embedding-Profil", "Embedding profile")
        active = str(active_name or "default").strip() or "default"
        detail = str(result.get("detail", "") or "").strip()
        if str(result.get("status", "")).strip().lower() == "ok":
            return _msg(
                lang,
                f"{label} „{active}“ erfolgreich getestet.",
                f"{label} '{active}' tested successfully.",
            )
        return _msg(
            lang,
            f"{label} „{active}“ Test fehlgeschlagen: {detail or '-'}",
            f"{label} '{active}' test failed: {detail or '-'}",
        )

    def _format_config_info_message(lang: str, info: str) -> str:
        clean = str(info or "").strip()
        if not clean:
            return ""
        if clean.startswith("sample_imported:"):
            parts = clean.split(":")
            kind = str(parts[1] if len(parts) > 1 else "").strip().upper()
            imported_count = str(parts[2] if len(parts) > 2 else "").strip() or "0"
            skipped_count = str(parts[3] if len(parts) > 3 else "").strip() or "0"
            return _msg(
                lang,
                f"Sample-Connection importiert: {kind} · neu: {imported_count} · übersprungen: {skipped_count}",
                f"Sample connection imported: {kind} · new: {imported_count} · skipped: {skipped_count}",
            )
        if clean.startswith("guardrail_sample_imported:"):
            parts = clean.split(":")
            imported_count = str(parts[1] if len(parts) > 1 else "").strip() or "0"
            skipped_count = str(parts[2] if len(parts) > 2 else "").strip() or "0"
            return _msg(
                lang,
                f"Guardrail-Samples importiert: neu {imported_count} · übersprungen {skipped_count}",
                f"Guardrail samples imported: new {imported_count} · skipped {skipped_count}",
            )
        return clean

    def _import_sample_connection_manifest(sample_file: str) -> tuple[str, int, int]:
        clean_name = Path(str(sample_file or "").strip()).name
        if not clean_name or not clean_name.endswith(".sample.yaml"):
            raise ValueError("Unbekanntes Sample-Connection-Profil.")
        sample_path = _SAMPLE_CONNECTIONS_DIR / clean_name
        if not sample_path.exists() or not sample_path.is_file():
            raise ValueError("Sample-Connection nicht gefunden.")
        payload = yaml.safe_load(sample_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Sample-Import erwartet ein YAML-Objekt.")

        sample_connections = payload.get("connections")
        if not isinstance(sample_connections, dict) or not sample_connections:
            raise ValueError("Sample-Connection enthält keine Connections.")

        raw = _read_raw_config()
        raw.setdefault("connections", {})
        if not isinstance(raw["connections"], dict):
            raw["connections"] = {}

        imported_count = 0
        skipped_count = 0
        primary_kind = ""
        for raw_kind, profiles in sample_connections.items():
            kind = normalize_connection_kind(str(raw_kind).strip())
            if not kind or kind not in CONNECTION_ADMIN_SPECS or not isinstance(profiles, dict):
                continue
            primary_kind = primary_kind or kind
            raw["connections"].setdefault(kind, {})
            if not isinstance(raw["connections"][kind], dict):
                raw["connections"][kind] = {}
            for raw_ref, profile in profiles.items():
                ref = _sanitize_connection_name(str(raw_ref).strip())
                if not ref or not isinstance(profile, dict):
                    skipped_count += 1
                    continue
                if ref in raw["connections"][kind]:
                    skipped_count += 1
                    continue
                raw["connections"][kind][ref] = dict(profile)
                imported_count += 1

        if not primary_kind:
            raise ValueError("Sample-Connection-Typ ist nicht unterstützt.")
        if imported_count <= 0 and skipped_count <= 0:
            raise ValueError("Sample-Connection enthält keine importierbaren Profile.")
        _write_raw_config(raw)
        _reload_runtime()
        return primary_kind, imported_count, skipped_count

    def _import_sample_guardrail_manifest(sample_file: str) -> tuple[int, int]:
        clean_name = Path(str(sample_file or "").strip()).name
        if not clean_name or not clean_name.endswith(".sample.yaml"):
            raise ValueError("Unknown sample guardrail pack.")
        sample_path = _SAMPLE_GUARDRAILS_DIR / clean_name
        if not sample_path.exists() or not sample_path.is_file():
            raise ValueError("Sample guardrail pack not found.")
        payload = yaml.safe_load(sample_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Sample guardrail import expects a YAML object.")

        security = payload.get("security")
        if not isinstance(security, dict):
            raise ValueError("Sample guardrail file does not contain a security section.")
        sample_guardrails = security.get("guardrails")
        if not isinstance(sample_guardrails, dict) or not sample_guardrails:
            raise ValueError("Sample guardrail file does not contain guardrails.")

        raw = _read_raw_config()
        raw.setdefault("security", {})
        if not isinstance(raw["security"], dict):
            raw["security"] = {}
        raw["security"].setdefault("guardrails", {})
        if not isinstance(raw["security"]["guardrails"], dict):
            raw["security"]["guardrails"] = {}

        existing = raw["security"]["guardrails"]
        imported_count = 0
        skipped_count = 0
        for raw_ref, profile in sample_guardrails.items():
            ref = _sanitize_reference_name_local(str(raw_ref).strip())
            if not ref or not isinstance(profile, dict):
                skipped_count += 1
                continue
            if ref in existing:
                skipped_count += 1
                continue
            clean_kind = normalize_guardrail_kind(str(profile.get("kind", "")).strip() or "ssh_command")
            if clean_kind not in guardrail_kind_options():
                skipped_count += 1
                continue
            existing[ref] = {
                "kind": clean_kind,
                "title": str(profile.get("title", "")).strip(),
                "description": str(profile.get("description", "")).strip(),
                "allow_terms": [
                    str(item).strip()[:160]
                    for item in (profile.get("allow_terms", []) or [])
                    if str(item).strip()
                ][:40],
                "deny_terms": [
                    str(item).strip()[:160]
                    for item in (profile.get("deny_terms", []) or [])
                    if str(item).strip()
                ][:40],
            }
            imported_count += 1

        if imported_count <= 0 and skipped_count <= 0:
            raise ValueError("Sample guardrail file contains no importable profiles.")
        _write_raw_config(raw)
        _reload_runtime()
        return imported_count, skipped_count

    def _ssh_keys_dir() -> Path:
        return _ssh_keys_dir_impl(BASE_DIR)

    def _ensure_ssh_keypair(ref: str, overwrite: bool = False) -> Path:
        return _ensure_ssh_keypair_impl(BASE_DIR, ref, overwrite=overwrite)

    def _file_affects_runtime(target: Path) -> bool:
        resolved = target.resolve()
        return (
            resolved == prompts_root
            or prompts_root in resolved.parents
            or resolved == skills_root
            or skills_root in resolved.parents
        )

    def _save_text_file_and_maybe_reload(target: Path, content: str) -> tuple[bool, str]:
        target.write_text(content, encoding="utf-8")
        if not _file_affects_runtime(target):
            return True, ""
        try:
            _reload_runtime()
            return True, ""
        except (OSError, ValueError) as exc:
            return True, f"Datei gespeichert, aber Runtime-Neuladen fehlgeschlagen: {exc}"

    def _read_ssh_connections() -> dict[str, dict[str, Any]]:
        return _read_ssh_connections_impl(_read_raw_config, _sanitize_connection_name)

    def _perform_ssh_key_exchange(
        *,
        ref: str,
        host: str,
        port: int,
        profile_user: str,
        login_user: str,
        login_password: str,
    ) -> tuple[str, Path]:
        return _perform_ssh_key_exchange_impl(
            BASE_DIR,
            ref=ref,
            host=host,
            port=port,
            profile_user=profile_user,
            login_user=login_user,
            login_password=login_password,
        )

    def _read_guardrails() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        security = raw.get("security", {})
        if not isinstance(security, dict):
            return {}
        rows = security.get("guardrails", {})
        if not isinstance(rows, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for ref, value in rows.items():
            clean_ref = _sanitize_connection_name(ref)
            if not clean_ref or not isinstance(value, dict):
                continue
            kind = normalize_guardrail_kind(str(value.get("kind", "")).strip() or "ssh_command")
            result[clean_ref] = {
                "kind": kind,
                "kind_label": guardrail_kind_label(kind),
                "title": str(value.get("title", "")).strip(),
                "description": str(value.get("description", "")).strip(),
                "allow_terms": list(value.get("allow_terms", []) if isinstance(value.get("allow_terms", []), list) else []),
                "deny_terms": list(value.get("deny_terms", []) if isinstance(value.get("deny_terms", []), list) else []),
            }
        return result

    def _build_guardrail_ref_options(rows: dict[str, dict[str, Any]], *, connection_kind: str = "", lang: str = "de") -> list[dict[str, str]]:
        options = [{"ref": "", "label": _msg(lang, "Kein Guardrail-Profil", "No guardrail profile")}]
        for ref in sorted(rows.keys()):
            item = rows.get(ref, {})
            kind = str(item.get("kind", "")).strip()
            if connection_kind and kind and not guardrail_is_compatible(kind, connection_kind):
                continue
            title = str(item.get("title", "")).strip()
            kind_label = str(item.get("kind_label", "")).strip()
            label_core = f"{title} · {ref}" if title and title != ref else ref
            label = f"{label_core} · {kind_label}" if kind_label else label_core
            options.append({"ref": ref, "label": label})
        return options

    @app.get("/config", response_class=HTMLResponse)
    async def config_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        username = _get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        error_message = ""
        if error == "admin_mode_required":
            error_message = "Admin-Modus aktivieren, um diesen Bereich zu sehen." if lang.startswith("de") else "Enable admin mode to access this area."
        elif error == "no_admin":
            error_message = "Nur Admins dürfen diesen Bereich öffnen." if lang.startswith("de") else "Only admins can open this area."
        connection_rows = connection_menu_rows()
        searxng_stack = probe_searxng_stack_service(lang=lang)
        searxng_profiles = _read_searxng_connections()
        for row in connection_rows:
            if row.get("kind") != "searxng":
                continue
            row["availability_status"] = str(searxng_stack.get("status", "")).strip() or "ok"
            row["availability_message"] = (
                str(searxng_stack.get("message", "")).strip()
                if row["availability_status"] != "ok"
                else ""
            )
            row["disabled"] = not bool(searxng_stack.get("available")) and not bool(searxng_profiles)
            row["warning_badge"] = (
                _msg(lang, "Stack fehlt", "Stack missing")
                if row["disabled"]
                else (_msg(lang, "Prüfen", "Check") if row["availability_status"] == "warn" else "")
            )
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "info_message": _format_config_info_message(lang, info),
                "error_message": error_message,
                "connection_menu_rows": connection_rows,
                "sample_connection_rows": _build_sample_connection_rows(),
            },
        )

    @app.post("/config/connections/import-sample")
    async def config_connections_import_sample(
        request: Request,
        sample_file: str = Form(""),
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        try:
            kind, imported_count, skipped_count = _import_sample_connection_manifest(sample_file)
            info = quote_plus(f"sample_imported:{kind}:{imported_count}:{skipped_count}")
            return RedirectResponse(url=f"/config?saved=1&info={info}", status_code=303)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return RedirectResponse(url=f"/config?error={quote_plus(str(exc))}", status_code=303)

    @app.get("/config/backup", response_class=HTMLResponse)
    async def config_backup_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        raw = _read_raw_config()
        secure_store = _get_secure_store(raw)
        backup_payload = build_config_backup_payload(
            base_dir=BASE_DIR,
            raw_config=raw,
            secure_store=secure_store,
            error_interpreter_path=ERROR_INTERPRETER_PATH,
        )
        backup_summary = summarize_config_backup_payload(backup_payload)
        info_message = ""
        lang = str(getattr(request.state, "lang", "de") or "de")
        if info == "backup_imported":
            info_message = (
                "Konfigurations-Backup erfolgreich wiederhergestellt."
                if lang.startswith("de")
                else "Configuration backup restored successfully."
            )
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_backup.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": info_message,
                "backup_summary": backup_summary,
                "return_to": return_to,
            },
        )

    @app.get("/config/backup/export")
    async def config_backup_export(request: Request) -> Response:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        raw = _read_raw_config()
        payload = build_config_backup_payload(
            base_dir=BASE_DIR,
            raw_config=raw,
            secure_store=_get_secure_store(raw),
            error_interpreter_path=ERROR_INTERPRETER_PATH,
        )
        body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{backup_filename()}"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/config/backup/import")
    async def config_backup_import(
        request: Request,
        backup_file: UploadFile = File(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        previous_raw = _read_raw_config()
        previous_snapshot = build_config_backup_payload(
            base_dir=BASE_DIR,
            raw_config=previous_raw,
            secure_store=_get_secure_store(previous_raw),
            error_interpreter_path=ERROR_INTERPRETER_PATH,
        )
        rollback_restored = False
        try:
            data = await backup_file.read()
            if not data:
                raise ValueError("Backup-Datei ist leer.")
            payload = parse_config_backup_payload(data)
            restore_config_backup_payload(
                base_dir=BASE_DIR,
                payload=payload,
                write_raw_config=_write_raw_config,
                get_secure_store=_get_secure_store,
                error_interpreter_path=ERROR_INTERPRETER_PATH,
            )
            _refresh_skill_trigger_index()
            _reload_runtime()
            return _redirect_with_return_to("/config/backup?saved=1&info=backup_imported", request, fallback="/config")
        except Exception as exc:  # noqa: BLE001
            with suppress(Exception):
                restore_config_backup_payload(
                    base_dir=BASE_DIR,
                    payload=previous_snapshot,
                    write_raw_config=_write_raw_config,
                    get_secure_store=_get_secure_store,
                    error_interpreter_path=ERROR_INTERPRETER_PATH,
                )
                _refresh_skill_trigger_index()
                _reload_runtime()
                rollback_restored = True
            message = str(exc).strip() or "Backup-Import fehlgeschlagen."
            if rollback_restored:
                message = (
                    f"{message} Vorheriger Stand wurde wiederhergestellt."
                    if str(getattr(request.state, 'lang', 'de') or 'de').startswith("de")
                    else f"{message} Previous configuration was restored."
                )
            request.state.logical_back_url = _sanitize_return_to(return_to) or "/config"
            return _redirect_with_return_to(f"/config/backup?error={quote_plus(message)}", request, fallback="/config")

    @app.get("/config/appearance", response_class=HTMLResponse)
    async def config_appearance_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        raw = _read_raw_config()
        ui_cfg = raw.get("ui", {})
        if not isinstance(ui_cfg, dict):
            ui_cfg = {}
        current_theme = normalize_ui_theme(ui_cfg.get("theme") or getattr(settings.ui, "theme", "matrix"))
        current_background = normalize_ui_background(
            ui_cfg.get("background") or getattr(settings.ui, "background", "grid")
        )
        theme_rows = [
            {"value": "matrix", "label_key": "config_appearance.theme_matrix", "fallback": "Matrix Green"},
            {"value": "sunset", "label_key": "config_appearance.theme_sunset", "fallback": "Sunset Amber"},
            {"value": "harbor", "label_key": "config_appearance.theme_harbor", "fallback": "Harbor Blue"},
            {"value": "paper", "label_key": "config_appearance.theme_paper", "fallback": "Paper Ink"},
            {"value": "cyberpunk", "label_key": "config_appearance.theme_cyberpunk", "fallback": "CyberPunk Classic"},
            {"value": "cyberpunk-neo", "label_key": "config_appearance.theme_cyberpunk_neo", "fallback": "CyberPunk Neo"},
            {"value": "nyan-cat", "label_key": "config_appearance.theme_nyan_cat", "fallback": "Nyan Cat"},
            {"value": "puke-unicorn", "label_key": "config_appearance.theme_puke_unicorn", "fallback": "Puke Unicorn"},
            {"value": "pixel", "label_key": "config_appearance.theme_pixel", "fallback": "8-Bit Arcade"},
            {"value": "crt-amber", "label_key": "config_appearance.theme_crt_amber", "fallback": "Amber CRT"},
            {"value": "deep-space", "label_key": "config_appearance.theme_deep_space", "fallback": "Deep Space"},
        ]
        background_rows = [
            {"value": "grid", "label_key": "config_appearance.background_grid", "fallback": "Grid Signal"},
            {"value": "aurora", "label_key": "config_appearance.background_aurora", "fallback": "Aurora Glow"},
            {"value": "mesh", "label_key": "config_appearance.background_mesh", "fallback": "Mesh Weave"},
            {"value": "nodes", "label_key": "config_appearance.background_nodes", "fallback": "Nodes Field"},
        ]
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_appearance.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "theme_rows": [row for row in theme_rows if row["value"] in UI_THEME_OPTIONS],
                "background_rows": [row for row in background_rows if row["value"] in UI_BACKGROUND_OPTIONS],
                "current_theme": current_theme,
                "current_background": current_background,
                "return_to": return_to,
            },
        )

    @app.post("/config/appearance/save")
    async def config_appearance_save(
        request: Request,
        theme: str = Form("matrix"),
        background: str = Form("grid"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            raw = _read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["theme"] = normalize_ui_theme(theme)
            raw["ui"]["background"] = normalize_ui_background(background)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/appearance?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/appearance?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/language", response_class=HTMLResponse)
    async def config_language_page(request: Request, saved: int = 0, error: str = "", file: str = "") -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        raw = _read_raw_config()
        ui_cfg = raw.get("ui", {})
        if not isinstance(ui_cfg, dict):
            ui_cfg = {}
        default_language = str(ui_cfg.get("language", settings.ui.language or "de")).strip().lower() or "de"
        language_rows = []
        for code in I18N.available_languages():
            language_rows.append(
                {
                    "code": code,
                    "flag": _lang_flag(code),
                    "label": _lang_label(code),
                }
            )
        selected_file = str(file or "").strip().lower()
        if not selected_file:
            selected_file = f"{default_language}.json"
        if not selected_file.endswith(".json"):
            selected_file += ".json"
        target = BASE_DIR / "aria" / "i18n" / selected_file
        editor_content = ""
        if target.exists():
            try:
                editor_content = target.read_text(encoding="utf-8")
            except OSError:
                editor_content = ""
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_language.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "language_rows": language_rows,
                "default_language": default_language,
                "selected_file": selected_file,
                "editor_content": editor_content,
                "return_to": return_to,
            },
        )

    @app.post("/config/language/save")
    async def config_language_save(request: Request, default_language: str = Form(...), return_to: str = Form("")) -> RedirectResponse:
        try:
            code = I18N.resolve_lang(str(default_language).strip().lower(), default_lang=settings.ui.language)
            raw = _read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["language"] = code
            _write_raw_config(raw)
            _reload_runtime()
            request.state.lang = code
            response = _redirect_with_return_to("/config/language?saved=1", request, fallback="/config", return_to=return_to)
            response.set_cookie(
                key=_cookie_name_for_request(request, "lang", deps.lang_cookie),
                value=code,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=cookie_should_be_secure(request, public_url=str(settings.aria.public_url or "")),
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/language?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/language/file/save")
    async def config_language_file_save(
        request: Request,
        file_name: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            clean = str(file_name).strip().lower()
            if not re.fullmatch(r"[a-z0-9_-]+\.json", clean):
                raise ValueError("Ungültiger Dateiname.")
            target = BASE_DIR / "aria" / "i18n" / clean
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("Sprachdatei muss ein JSON-Objekt sein.")
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            I18N.clear_cache()
            return _redirect_with_return_to(
                f"/config/language?file={quote_plus(clean)}&saved=1",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _redirect_with_return_to(
                f"/config/language?file={quote_plus(str(file_name))}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/debug", response_class=HTMLResponse)
    async def config_debug_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        _ = request, saved, error
        return _redirect_with_return_to("/config/users", request, fallback="/config")

    @app.post("/config/debug/save")
    async def config_debug_save(request: Request, debug_mode: str = Form("0")) -> RedirectResponse:
        try:
            active = str(debug_mode).strip().lower() in {"1", "true", "on", "yes"}
            raw = _read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["debug_mode"] = active
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/users?saved=1&info=Admin-On%2FOff+aktualisiert", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/users?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.get("/config/security", response_class=HTMLResponse)
    async def config_security_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        guardrail_ref: str = "",
    ) -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        guardrail_rows = _read_guardrails()
        guardrail_refs = sorted(guardrail_rows.keys())
        selected_guardrail_ref = _sanitize_connection_name(guardrail_ref) or (guardrail_refs[0] if guardrail_refs else "")
        selected_guardrail = guardrail_rows.get(selected_guardrail_ref, {})
        timeout_minutes = max(
            5,
            int(getattr(settings.security, "session_max_age_seconds", 60 * 60 * 12) or 0) // 60,
        )
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_security.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": _format_config_info_message(lang, info),
                "security_cfg": settings.security,
                "security_session_timeout_minutes": timeout_minutes,
                "security_session_timeout_display": _format_session_timeout_label(timeout_minutes, lang=lang),
                "guardrail_refs": guardrail_refs,
                "guardrail_ref_options": _build_guardrail_ref_options(guardrail_rows, lang=lang)[1:],
                "selected_guardrail_ref": selected_guardrail_ref,
                "selected_guardrail": selected_guardrail,
                "guardrail_kind_options": [{"value": kind, "label": guardrail_kind_label(kind)} for kind in guardrail_kind_options()],
                "sample_guardrail_rows": _build_sample_guardrail_rows(),
                "return_to": return_to,
            },
        )

    @app.post("/config/security/save")
    async def config_security_save(
        request: Request,
        bootstrap_locked: str = Form("0"),
        session_timeout_minutes: int = Form(60 * 12 // 60),
    ) -> RedirectResponse:
        return await _save_user_security_settings(request, bootstrap_locked, session_timeout_minutes)

    @app.post("/config/security/guardrails/save")
    async def config_security_guardrail_save(
        request: Request,
        guardrail_ref: str = Form(...),
        original_ref: str = Form(""),
        kind: str = Form("ssh_command"),
        title: str = Form(""),
        description: str = Form(""),
        allow_terms: str = Form(""),
        deny_terms: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            raw = _read_raw_config()
            raw.setdefault("security", {})
            if not isinstance(raw["security"], dict):
                raw["security"] = {}
            raw["security"].setdefault("guardrails", {})
            if not isinstance(raw["security"]["guardrails"], dict):
                raw["security"]["guardrails"] = {}

            rows = raw["security"]["guardrails"]
            ref = _sanitize_connection_name(guardrail_ref)
            original_ref_clean = _sanitize_connection_name(original_ref)
            clean_kind = normalize_guardrail_kind(kind)
            if clean_kind not in guardrail_kind_options():
                raise ValueError("Unbekannter Guardrail-Typ.")
            if not ref:
                raise ValueError("Guardrail-Ref fehlt.")
            if ref != original_ref_clean and ref in rows:
                raise ValueError(f"Guardrail-Profil '{ref}' existiert bereits.")

            rows[ref] = {
                "kind": clean_kind,
                "title": str(title).strip(),
                "description": str(description).strip(),
                "allow_terms": _split_guardrail_terms(allow_terms),
                "deny_terms": _split_guardrail_terms(deny_terms),
            }
            if original_ref_clean and original_ref_clean != ref:
                rows.pop(original_ref_clean, None)

            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                f"/config/security?saved=1&guardrail_ref={quote_plus(ref)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_route_error(lang, exc, "Guardrail konnte nicht gespeichert werden.", "Could not save guardrail.")
            suffix = f"&guardrail_ref={quote_plus(_sanitize_connection_name(original_ref) or _sanitize_connection_name(guardrail_ref))}" if (original_ref or guardrail_ref) else ""
            return _redirect_with_return_to(
                f"/config/security?error={quote_plus(error)}{suffix}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/security/guardrails/delete")
    async def config_security_guardrail_delete(
        request: Request,
        guardrail_ref: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            ref = _sanitize_connection_name(guardrail_ref)
            if not ref:
                raise ValueError("Guardrail-Ref fehlt.")
            raw = _read_raw_config()
            raw.setdefault("security", {})
            if not isinstance(raw["security"], dict):
                raw["security"] = {}
            rows = raw["security"].get("guardrails", {})
            if not isinstance(rows, dict) or ref not in rows:
                raise ValueError("Guardrail-Profil nicht gefunden.")
            rows.pop(ref, None)
            connections = raw.get("connections", {})
            if isinstance(connections, dict):
                for connection_rows in connections.values():
                    if not isinstance(connection_rows, dict):
                        continue
                    for value in connection_rows.values():
                        if isinstance(value, dict) and str(value.get("guardrail_ref", "")).strip() == ref:
                            value["guardrail_ref"] = ""
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/security?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_route_error(lang, exc, "Guardrail konnte nicht gelöscht werden.", "Could not delete guardrail.")
            return _redirect_with_return_to(
                f"/config/security?error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/security/guardrails/import-sample")
    async def config_security_guardrail_import_sample(
        request: Request,
        sample_file: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        try:
            imported_count, skipped_count = _import_sample_guardrail_manifest(sample_file)
            info = quote_plus(f"guardrail_sample_imported:{imported_count}:{skipped_count}")
            return _redirect_with_return_to(
                f"/config/security?saved=1&info={info}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return _redirect_with_return_to(
                f"/config/security?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/logs", response_class=HTMLResponse)
    async def config_logs_page(
        request: Request,
        saved: int = 0,
        pruned: int | None = None,
        reset: int | None = None,
        factory_reset: int = 0,
        factory_qdrant: int | None = None,
        error: str = "",
    ) -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        health = await pipeline.token_tracker.get_log_health()
        size_bytes = int(health.get("size_bytes", 0) or 0)
        if size_bytes >= 1024 * 1024:
            size_human = f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes >= 1024:
            size_human = f"{size_bytes / 1024:.1f} KB"
        else:
            size_human = f"{size_bytes} B"
        health["size_human"] = size_human
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_logs.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "pruned": pruned,
                "reset": reset,
                "factory_reset": bool(factory_reset),
                "factory_qdrant": factory_qdrant,
                "error_message": error,
                "token_tracking": settings.token_tracking,
                "health": health,
                "return_to": return_to,
            },
        )

    @app.post("/config/logs/save")
    async def config_logs_save(
        request: Request,
        enabled: str = Form("0"),
        retention_days: int = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            if retention_days < 0:
                raise ValueError("retention_days muss >= 0 sein.")
            active = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
            raw = _read_raw_config()
            raw.setdefault("token_tracking", {})
            if not isinstance(raw["token_tracking"], dict):
                raw["token_tracking"] = {}
            raw["token_tracking"]["enabled"] = active
            raw["token_tracking"]["retention_days"] = int(retention_days)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/logs?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/logs?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/logs/cleanup")
    async def config_logs_cleanup(request: Request, return_to: str = Form("")) -> RedirectResponse:
        try:
            removed = await pipeline.token_tracker.prune_old_entries(
                int(getattr(settings.token_tracking, "retention_days", 0) or 0)
            )
            return _redirect_with_return_to(
                f"/config/logs?pruned={int(removed.get('removed', 0) or 0)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/logs?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/logs/reset")
    async def config_logs_reset(
        request: Request,
        confirm_text: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            expected = "RESET"
            if str(confirm_text or "").strip().upper() != expected:
                raise ValueError(
                    'Bitte zur Bestätigung genau "RESET" eingeben.'
                    if lang.startswith("de")
                    else 'Please type "RESET" exactly to confirm.'
                )
            removed = await pipeline.token_tracker.clear_log()
            runtime_dir = (BASE_DIR / "data" / "runtime").resolve()
            for cache_name in ("stats_connections_cache.json",):
                try:
                    (runtime_dir / cache_name).unlink(missing_ok=True)
                except OSError:
                    pass
            return _redirect_with_return_to(
                f"/config/logs?reset={int(removed.get('removed', 0) or 0)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_route_error(
                lang,
                exc,
                "Statistikdaten konnten nicht zurückgesetzt werden.",
                "Could not reset stats data.",
            )
            return _redirect_with_return_to(
                f"/config/logs?error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/logs/factory-reset")
    async def config_logs_factory_reset(request: Request, confirm_text: str = Form("")) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            expected = "FACTORY RESET"
            if str(confirm_text or "").strip().upper() != expected:
                raise ValueError(
                    'Bitte zur Bestätigung genau "FACTORY RESET" eingeben.'
                    if lang.startswith("de")
                    else 'Please type "FACTORY RESET" exactly to confirm.'
                )

            raw = _read_raw_config()
            cleaned = _apply_factory_reset_to_raw_config(raw)
            _write_raw_config(cleaned)

            removed_stats = await pipeline.token_tracker.clear_log()
            removed_qdrant = await _clear_qdrant_factory_data(settings.memory)

            removed_files = 0
            for rel_dir in (
                "data/auth",
                "data/chat_history",
                "data/runtime",
                "data/skills",
                "data/ssh_keys",
            ):
                removed_files += _wipe_directory_contents((BASE_DIR / rel_dir).resolve())

            logs_dir = (BASE_DIR / "data" / "logs").resolve()
            for file_name in ("tokens.jsonl", "tokens.jsonl.bak_unknown_cleanup"):
                with suppress(OSError):
                    (logs_dir / file_name).unlink()

            _reload_runtime()

            info = (
                "Factory Reset abgeschlossen. ARIA ist jetzt wieder im Erststart-Zustand."
                if lang.startswith("de")
                else "Factory reset completed. ARIA is back in first-start state."
            )
            response = RedirectResponse(
                url=(
                    f"/login?info={quote_plus(info)}"
                    f"&reset={int(removed_stats.get('removed', 0) or 0)}"
                    f"&qdrant={int(removed_qdrant)}"
                    f"&files={int(removed_files)}"
                ),
                status_code=303,
            )
            response.delete_cookie(_cookie_name_for_request(request, "auth", AUTH_COOKIE))
            response.delete_cookie(_cookie_name_for_request(request, "username", USERNAME_COOKIE))
            response.delete_cookie(_cookie_name_for_request(request, "memory_collection", MEMORY_COLLECTION_COOKIE))
            return response
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_route_error(
                lang,
                exc,
                "Factory Reset konnte nicht ausgeführt werden.",
                "Could not run factory reset.",
            )
            return RedirectResponse(url=f"/config/logs?error={quote_plus(error)}", status_code=303)

    def _ssh_keys_dir() -> Path:
        path = (BASE_DIR / "data" / "ssh_keys").resolve()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        return path

    def _ensure_ssh_keypair(ref: str, overwrite: bool = False) -> Path:
        key_dir = _ssh_keys_dir()
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
            [
                "ssh-keygen",
                "-t", "ed25519",
                "-N", "",
                "-f", str(key_path),
                "-C", comment,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return key_path

    def _read_ssh_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        ssh = connections.get("ssh", {})
        if not isinstance(ssh, dict):
            return {}
        rows: dict[str, dict[str, Any]] = {}
        for key, value in ssh.items():
            ref = _sanitize_connection_name(key)
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
                **_read_connection_metadata(value),
            }
        return rows

    def _read_discord_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        discord = connections.get("discord", {})
        if not isinstance(discord, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in discord.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            webhook = store.get_secret(f"connections.discord.{ref}.webhook_url", default="") if store else ""
            rows[ref] = {
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "send_test_messages": bool(value.get("send_test_messages", True)),
                "allow_skill_messages": bool(value.get("allow_skill_messages", True)),
                "alert_skill_errors": bool(value.get("alert_skill_errors", False)),
                "alert_safe_fix": bool(value.get("alert_safe_fix", False)),
                "alert_connection_changes": bool(value.get("alert_connection_changes", False)),
                "alert_system_events": bool(value.get("alert_system_events", False)),
                "webhook_url": webhook,
                "webhook_present": bool(webhook),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_sftp_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        sftp = connections.get("sftp", {})
        if not isinstance(sftp, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in sftp.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            password = store.get_secret(f"connections.sftp.{ref}.password", default="") if store else ""
            key_path = str(value.get("key_path", "")).strip()
            key_exists = False
            if key_path:
                candidate = Path(key_path)
                if not candidate.is_absolute():
                    candidate = (BASE_DIR / candidate).resolve()
                key_exists = candidate.exists()
            rows[ref] = {
                "host": str(value.get("host", "")).strip(),
                "port": int(value.get("port", 22) or 22),
                "user": str(value.get("user", "")).strip(),
                "service_url": str(value.get("service_url", "")).strip(),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "root_path": str(value.get("root_path", "")).strip(),
                "key_path": key_path,
                "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                "key_present": key_exists,
                "password": password,
                "password_present": bool(password),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_smb_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        smb = connections.get("smb", {})
        if not isinstance(smb, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in smb.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            password = store.get_secret(f"connections.smb.{ref}.password", default="") if store else ""
            rows[ref] = {
                "host": str(value.get("host", "")).strip(),
                "port": int(value.get("port", 445) or 445),
                "share": str(value.get("share", "")).strip(),
                "user": str(value.get("user", "")).strip(),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "root_path": str(value.get("root_path", "")).strip(),
                "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                "password": password,
                "password_present": bool(password),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_webhook_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        webhook = connections.get("webhook", {})
        if not isinstance(webhook, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in webhook.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            url = store.get_secret(f"connections.webhook.{ref}.url", default="") if store else ""
            rows[ref] = {
                "url": url,
                "url_present": bool(url),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "method": str(value.get("method", "POST")).strip().upper() or "POST",
                "content_type": str(value.get("content_type", "application/json")).strip() or "application/json",
                "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_email_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        email = connections.get("email", {})
        if not isinstance(email, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in email.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            password = store.get_secret(f"connections.email.{ref}.password", default="") if store else ""
            rows[ref] = {
                "smtp_host": str(value.get("smtp_host", "")).strip(),
                "port": int(value.get("port", 587) or 587),
                "user": str(value.get("user", "")).strip(),
                "from_email": str(value.get("from_email", "")).strip(),
                "to_email": str(value.get("to_email", "")).strip(),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "starttls": bool(value.get("starttls", True)),
                "use_ssl": bool(value.get("use_ssl", False)),
                "password": password,
                "password_present": bool(password),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_imap_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        imap = connections.get("imap", {})
        if not isinstance(imap, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in imap.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            password = store.get_secret(f"connections.imap.{ref}.password", default="") if store else ""
            rows[ref] = {
                "host": str(value.get("host", "")).strip(),
                "port": int(value.get("port", 993) or 993),
                "user": str(value.get("user", "")).strip(),
                "mailbox": str(value.get("mailbox", "INBOX")).strip() or "INBOX",
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "use_ssl": bool(value.get("use_ssl", True)),
                "password": password,
                "password_present": bool(password),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_http_api_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        http_api = connections.get("http_api", {})
        if not isinstance(http_api, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in http_api.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            auth_token = store.get_secret(f"connections.http_api.{ref}.auth_token", default="") if store else ""
            rows[ref] = {
                "base_url": str(value.get("base_url", "")).strip(),
                "health_path": str(value.get("health_path", "/")).strip() or "/",
                "method": str(value.get("method", "GET")).strip().upper() or "GET",
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "auth_token": auth_token,
                "auth_token_present": bool(auth_token),
                "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_rss_poll_interval_minutes(raw: dict[str, Any] | None = None) -> int:
        source = raw if isinstance(raw, dict) else _read_raw_config()
        rss_settings = source.get("rss", {}) if isinstance(source, dict) else {}
        if not isinstance(rss_settings, dict):
            rss_settings = {}
        try:
            poll_interval = int(rss_settings.get("poll_interval_minutes", 60) or 60)
        except (TypeError, ValueError):
            poll_interval = 60
        return max(1, min(poll_interval, 10080))

    def _extract_json_object_local(raw: str) -> dict[str, Any] | None:
        text = str(raw or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _extract_html_attribute_map(tag_html: str) -> dict[str, str]:
        attrs: dict[str, str] = {}
        for match in re.finditer(r'([a-zA-Z_:][\w:.-]*)\s*=\s*(["\'])(.*?)\2', str(tag_html or ""), flags=re.DOTALL):
            key = str(match.group(1) or "").strip().lower()
            if not key:
                continue
            attrs[key] = unescape(str(match.group(3) or "").strip())
        return attrs

    def _clean_html_text(value: str, max_length: int = 240) -> str:
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_length]

    def _extract_ssh_service_seed(service_url: str) -> dict[str, Any]:
        clean_url = str(service_url or "").strip()
        parsed = urlparse(clean_url)
        host = str(parsed.netloc or "").strip().lower()
        host_short = host[4:] if host.startswith("www.") else host
        fallback_aliases = [value for value in [host_short, host_short.split(".", 1)[0].replace("-", " ")] if value]
        seed = {
            "service_title": host_short or clean_url,
            "service_description": "",
            "keywords": [],
            "host": host_short,
            "aliases": fallback_aliases,
        }
        if not clean_url:
            return seed
        req = URLRequest(clean_url, headers=_WEB_METADATA_HEADERS, method="GET")
        try:
            with urlopen(req, timeout=10) as resp:  # noqa: S310
                payload = resp.read(256 * 1024)
        except Exception:
            return seed
        text = payload.decode("utf-8", errors="replace").strip()
        if not text:
            return seed

        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
        title = _clean_html_text(title_match.group(1), 120) if title_match else ""
        meta_description = ""
        keywords: list[str] = []
        og_title = ""
        h1_title = ""

        for match in re.finditer(r"<meta\b[^>]*>", text, flags=re.IGNORECASE):
            attrs = _extract_html_attribute_map(match.group(0))
            key = str(attrs.get("name") or attrs.get("property") or "").strip().lower()
            content = _clean_html_text(attrs.get("content", ""), 240)
            if not key or not content:
                continue
            if key in {"description", "og:description", "twitter:description"} and not meta_description:
                meta_description = content
            elif key in {"keywords", "news_keywords"} and not keywords:
                keywords = [item.strip()[:24] for item in re.split(r"[;,]", content) if item.strip()][:8]
            elif key in {"og:title", "twitter:title"} and not og_title:
                og_title = content[:120]

        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.IGNORECASE | re.DOTALL)
        if h1_match:
            h1_title = _clean_html_text(h1_match.group(1), 120)

        resolved_title = title or og_title or h1_title
        if resolved_title:
            seed["service_title"] = resolved_title
        if meta_description:
            seed["service_description"] = meta_description
        seed["keywords"] = keywords
        return seed

    def _extract_rss_feed_seed(feed_url: str) -> dict[str, Any]:
        clean_url = str(feed_url or "").strip()
        parsed = urlparse(clean_url)
        host = str(parsed.netloc or "").strip()
        host_short = host[4:] if host.startswith("www.") else host
        fallback_aliases = [value for value in [host_short, host_short.split(".", 1)[0].replace("-", " ")] if value]
        seed = {
            "feed_title": host_short or clean_url,
            "feed_description": "",
            "entry_titles": [],
            "host": host_short,
            "aliases": fallback_aliases,
        }
        if not clean_url:
            return seed
        req = URLRequest(clean_url, headers=_RSS_METADATA_HEADERS, method="GET")
        try:
            with urlopen(req, timeout=10) as resp:  # noqa: S310
                payload = resp.read(256 * 1024)
        except Exception:
            return seed
        text = payload.decode("utf-8", errors="replace").strip()
        if not text or text.startswith("{") or text.startswith("["):
            return seed
        try:
            root = ET.fromstring(text)
        except Exception:
            return seed
        root_title = ""
        root_description = ""
        entry_titles: list[str] = []
        for elem in root.iter():
            tag = str(elem.tag or "").split("}", 1)[-1].lower()
            value = str(elem.text or "").strip()
            if not value:
                continue
            if tag == "channel":
                continue
            if tag == "title" and not root_title:
                root_title = value[:120]
            elif tag in {"description", "subtitle", "summary"} and not root_description:
                root_description = value[:240]
            elif tag == "title" and root_title and len(entry_titles) < 8 and value != root_title:
                entry_titles.append(value[:120])
        if root_title:
            seed["feed_title"] = root_title
        if root_description:
            seed["feed_description"] = root_description
        seed["entry_titles"] = entry_titles
        return seed

    def _connection_metadata_language_instruction(lang: str) -> str:
        code = str(lang or "de").strip().lower() or "de"
        if code.startswith("de"):
            return (
                "Output language: German (Deutsch). "
                "Write title and description in natural German. "
                "Aliases and tags must prioritize German routing and trigger terms someone would type in German. "
                "Keep product names and proper nouns unchanged. "
                "If an English product term is common, it may appear once, but include German trigger words too. "
                "Do not switch to English only because the source page is in English."
            )
        if code.startswith("en"):
            return (
                "Output language: English. "
                "Write title and description in natural English. "
                "Aliases and tags must prioritize English routing and trigger terms someone would type in English. "
                "Keep product names and proper nouns unchanged."
            )
        return (
            f"Output language: {code}. "
            "Write title, description, aliases, and tags primarily in that language when natural. "
            "Keep product names and proper nouns unchanged. "
            "Prefer routing terms a user would type in that language."
        )

    async def _suggest_rss_metadata_with_llm(
        *,
        feed_url: str,
        connection_ref: str,
        current_title: str,
        current_description: str,
        current_aliases: str,
        current_tags: str,
        group_name: str,
        lang: str,
    ) -> dict[str, Any]:
        seed = _extract_rss_feed_seed(feed_url)
        llm_client = getattr(pipeline, "llm_client", None)
        if llm_client is None:
            return {
                "title": current_title.strip() or seed["feed_title"],
                "description": current_description.strip() or seed["feed_description"],
                "aliases": ", ".join(seed["aliases"]),
                "tags": current_tags.strip(),
            }

        system_prompt = (
            "You generate concise metadata for an RSS connection profile in ARIA. "
            "Respond with JSON only in the format "
            '{"title":"...","description":"...","aliases":["..."],"tags":["..."]}. '
            "Description max 120 characters. Aliases max 8 entries, each 2-40 chars. "
            "Tags max 8 entries, each 2-24 chars. No markdown. "
            + _connection_metadata_language_instruction(lang)
        )
        user_prompt = "\n".join(
            [
                f"Preferred language: {str(lang or 'de').strip() or 'de'}",
                f"Connection ref: {str(connection_ref or '').strip() or '-'}",
                f"Feed URL: {str(feed_url or '').strip() or '-'}",
                f"Detected feed title: {seed['feed_title'] or '-'}",
                f"Detected feed description: {seed['feed_description'] or '-'}",
                f"Example entries: {', '.join(seed['entry_titles']) or '-'}",
                f"Current group: {str(group_name or '').strip() or '-'}",
                f"Current title: {str(current_title or '').strip() or '-'}",
                f"Current description: {str(current_description or '').strip() or '-'}",
                f"Current aliases: {str(current_aliases or '').strip() or '-'}",
                f"Current tags: {str(current_tags or '').strip() or '-'}",
                "",
                "Goal: produce user-friendly metadata that helps ARIA route chat requests to this RSS connection. "
                "Aliases should contain the terms people would naturally use when referring to this feed in the preferred language.",
            ]
        )
        try:
            response = await llm_client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                source="rss_metadata",
                operation="suggest_metadata",
                user_id="system",
            )
        except Exception:
            response = None
        payload = _extract_json_object_local(str(getattr(response, "content", "") if response else "") or "") or {}
        title = str(payload.get("title", "") or "").strip()[:80]
        description = str(payload.get("description", "") or "").strip()[:120]
        aliases_raw = payload.get("aliases", [])
        aliases = [
            str(item).strip()[:40]
            for item in aliases_raw
            if str(item).strip()
        ][:8] if isinstance(aliases_raw, list) else []
        tags_raw = payload.get("tags", [])
        tags = [
            str(item).strip()[:24]
            for item in tags_raw
            if str(item).strip()
        ][:8] if isinstance(tags_raw, list) else []
        return {
            "title": title or current_title.strip() or seed["feed_title"],
            "description": description or current_description.strip() or seed["feed_description"],
            "aliases": ", ".join(aliases or seed["aliases"]),
            "tags": ", ".join(tags),
        }

    async def _suggest_ssh_metadata_with_llm(
        *,
        service_url: str,
        connection_ref: str,
        current_title: str,
        current_description: str,
        current_aliases: str,
        current_tags: str,
        lang: str,
    ) -> dict[str, Any]:
        seed = _extract_ssh_service_seed(service_url)
        llm_client = getattr(pipeline, "llm_client", None)
        fallback_tags = [item for item in seed["keywords"] if item][:8]
        if llm_client is None:
            return {
                "title": current_title.strip() or seed["service_title"],
                "description": current_description.strip() or seed["service_description"],
                "aliases": ", ".join(seed["aliases"]),
                "tags": ", ".join(fallback_tags),
            }

        system_prompt = (
            "You generate concise metadata for an SSH connection profile in ARIA. "
            "Respond with JSON only in the format "
            '{"title":"...","description":"...","aliases":["..."],"tags":["..."]}. '
            "Description max 120 characters. Aliases max 8 entries, each 2-40 chars. "
            "Tags max 8 entries, each 2-24 chars. No markdown. "
            + _connection_metadata_language_instruction(lang)
        )
        user_prompt = "\n".join(
            [
                f"Preferred language: {str(lang or 'de').strip() or 'de'}",
                f"Connection ref: {str(connection_ref or '').strip() or '-'}",
                f"Service URL: {str(service_url or '').strip() or '-'}",
                f"Detected page title: {seed['service_title'] or '-'}",
                f"Detected description: {seed['service_description'] or '-'}",
                f"Detected keywords: {', '.join(seed['keywords']) or '-'}",
                f"Current title: {str(current_title or '').strip() or '-'}",
                f"Current description: {str(current_description or '').strip() or '-'}",
                f"Current aliases: {str(current_aliases or '').strip() or '-'}",
                f"Current tags: {str(current_tags or '').strip() or '-'}",
                "",
                "Goal: produce user-friendly metadata that helps ARIA route chat requests to this SSH connection. "
                "Aliases should reflect how someone would naturally refer to the service behind this host.",
            ]
        )
        try:
            response = await llm_client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                source="ssh_metadata",
                operation="suggest_metadata",
                user_id="system",
            )
        except Exception:
            response = None
        payload = _extract_json_object_local(str(getattr(response, "content", "") if response else "") or "") or {}
        title = str(payload.get("title", "") or "").strip()[:80]
        description = str(payload.get("description", "") or "").strip()[:120]
        aliases_raw = payload.get("aliases", [])
        aliases = [
            str(item).strip()[:40]
            for item in aliases_raw
            if str(item).strip()
        ][:8] if isinstance(aliases_raw, list) else []
        tags_raw = payload.get("tags", [])
        tags = [
            str(item).strip()[:24]
            for item in tags_raw
            if str(item).strip()
        ][:8] if isinstance(tags_raw, list) else []
        return {
            "title": title or current_title.strip() or seed["service_title"],
            "description": description or current_description.strip() or seed["service_description"],
            "aliases": ", ".join(aliases or seed["aliases"]),
            "tags": ", ".join(tags or fallback_tags),
        }

    def _read_rss_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        rss = connections.get("rss", {})
        if not isinstance(rss, dict):
            return {}
        poll_interval_minutes = _read_rss_poll_interval_minutes(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in rss.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            rows[ref] = {
                "feed_url": str(value.get("feed_url", "")).strip(),
                "group_name": str(value.get("group_name", "")).strip(),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "poll_interval_minutes": poll_interval_minutes,
                **_read_connection_metadata(value),
            }
        return rows

    def _read_searxng_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        searxng = connections.get("searxng", {})
        if not isinstance(searxng, dict):
            return {}
        rows: dict[str, dict[str, Any]] = {}
        for key, value in searxng.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            safe_search = int(value.get("safe_search", 1) or 1)
            max_results = int(value.get("max_results", 5) or 5)
            rows[ref] = {
                "base_url": resolve_searxng_base_url(str(value.get("base_url", "")).strip()),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "language": str(value.get("language", "de-CH")).strip() or "de-CH",
                "safe_search": max(0, min(safe_search, 2)),
                "categories": [str(item).strip() for item in (value.get("categories", []) or []) if str(item).strip()],
                "engines": [str(item).strip() for item in (value.get("engines", []) or []) if str(item).strip()],
                "time_range": str(value.get("time_range", "")).strip(),
                "max_results": max(1, min(max_results, 20)),
                **_read_connection_metadata(value),
            }
        return rows

    def _read_mqtt_connections() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        connections = raw.get("connections", {})
        if not isinstance(connections, dict):
            return {}
        mqtt = connections.get("mqtt", {})
        if not isinstance(mqtt, dict):
            return {}
        store = _get_secure_store(raw)
        rows: dict[str, dict[str, Any]] = {}
        for key, value in mqtt.items():
            ref = _sanitize_connection_name(key)
            if not ref or not isinstance(value, dict):
                continue
            password = store.get_secret(f"connections.mqtt.{ref}.password", default="") if store else ""
            rows[ref] = {
                "host": str(value.get("host", "")).strip(),
                "port": int(value.get("port", 1883) or 1883),
                "user": str(value.get("user", "")).strip(),
                "topic": str(value.get("topic", "")).strip(),
                "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                "use_tls": bool(value.get("use_tls", False)),
                "password": password,
                "password_present": bool(password),
                **_read_connection_metadata(value),
            }
        return rows

    def _perform_ssh_key_exchange(
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

        key_path = _ensure_ssh_keypair(ref, overwrite=False)
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

    def _build_ssh_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        rows = _read_ssh_connections()
        guardrail_rows = _read_guardrails()
        guardrail_ref_options = _build_guardrail_ref_options(guardrail_rows, connection_kind="ssh", lang=lang)
        refs = sorted(rows.keys())
        selected_ref = _sanitize_connection_name(selected_ref_raw) or (refs[0] if refs else "")
        selected = rows.get(selected_ref, {})
        connection_status_rows = _attach_connection_edit_urls("ssh", build_connection_status_rows(
            "ssh",
            rows,
            selected_ref=selected_ref,
            cached_only=True,
            base_dir=BASE_DIR,
            lang=lang,
        ))
        healthy_count = sum(1 for item in connection_status_rows if item["status"] == "ok")
        issue_count = sum(1 for item in connection_status_rows if item["status"] == "error")
        public_key = ""
        private_key_exists = False
        public_key_exists = False
        key_path = str(selected.get("key_path", "")).strip()
        if key_path:
            expanded = Path(key_path).expanduser()
            private_key_exists = expanded.exists() and expanded.is_file()
            pub_path = expanded if expanded.suffix == ".pub" else expanded.with_suffix(expanded.suffix + ".pub")
            if pub_path.exists() and pub_path.is_file():
                public_key_exists = True
                try:
                    public_key = pub_path.read_text(encoding="utf-8").strip()
                except OSError:
                    public_key = ""
        return {
            "connection_intro": _build_connection_intro(
                kind="ssh",
                summary_cards=_build_connection_summary_cards(
                    kind="ssh",
                    profiles=len(refs),
                    healthy=healthy_count,
                    issues=issue_count,
                    extra_cards=[
                        {
                            "label_key": "config_conn.key_status",
                            "label": "Key status",
                            "value": "ready" if private_key_exists and public_key_exists else ("partial" if private_key_exists or public_key_exists else "missing"),
                            "value_key": "config_conn.ready" if private_key_exists and public_key_exists else ("config_conn.partial" if private_key_exists or public_key_exists else "config_conn.missing"),
                            "hint_key": "",
                            "hint": f"Private key: {'ok' if private_key_exists else 'missing'} · Public key: {'ok' if public_key_exists else 'missing'}",
                        },
                    ],
                ),
            ),
            "connection_status_block": _build_connection_status_block(
                kind="ssh",
                rows=connection_status_rows,
                collapse_threshold=5,
            ),
            "refs": refs,
            "ref_options": _build_connection_ref_options(rows),
            "selected_ref": selected_ref,
            "selected": selected,
            "ssh_edit_base_form_fields": _build_schema_form_fields(
                kind="ssh",
                values=dict(selected),
                prefix="ssh_edit",
                ref_value=selected_ref,
                placeholders={
                    "connection_ref": "z.B. main-ssh",
                    "host": "server.example.local",
                    "service_url": "https://service.example.local",
                    "user": "admin",
                },
                required_fields={"host", "user", "port", "timeout_seconds"},
                ordered_fields=["host", "service_url", "user", "port", "timeout_seconds"],
            ),
            "ssh_new_base_form_fields": _build_schema_form_fields(
                kind="ssh",
                values={"port": 22, "timeout_seconds": 20},
                prefix="ssh_new",
                ref_value="",
                placeholders={
                    "connection_ref": "z.B. main-ssh",
                    "host": "server.example.local",
                    "service_url": "https://service.example.local",
                    "user": "admin",
                },
                required_fields={"host", "user", "port", "timeout_seconds"},
                ordered_fields=["host", "service_url", "user", "port", "timeout_seconds"],
            ),
            "ssh_edit_advanced_form_fields": _build_schema_form_fields(
                kind="ssh",
                values=dict(selected),
                prefix="ssh_edit_adv",
                ref_value=selected_ref,
                include_ref=False,
                select_options={
                    "strict_host_key_checking": ["accept-new", "yes", "no"],
                },
                field_hints={
                    "allow_commands": "One line per command. Empty = no permission for ssh_command.",
                },
                ordered_fields=["strict_host_key_checking", "key_path", "allow_commands"],
            ),
            "ssh_new_advanced_form_fields": _build_schema_form_fields(
                kind="ssh",
                values={"strict_host_key_checking": "accept-new"},
                prefix="ssh_new_adv",
                ref_value="",
                include_ref=False,
                select_options={
                    "strict_host_key_checking": ["accept-new", "yes", "no"],
                },
                field_hints={
                    "allow_commands": "One line per command. Empty = no permission for ssh_command.",
                },
                ordered_fields=["strict_host_key_checking", "key_path", "allow_commands"],
            ),
            "connection_status_rows": connection_status_rows,
            "healthy_count": healthy_count,
            "issue_count": issue_count,
            "public_key": public_key,
            "private_key_exists": private_key_exists,
            "public_key_exists": public_key_exists,
            "guardrail_rows": guardrail_rows,
            "guardrail_ref_options": guardrail_ref_options,
            "test_status": str(test_status).strip().lower(),
        }

    def _build_generic_connections_context(
        kind: str,
        rows: dict[str, dict[str, Any]],
        *,
        lang: str = "de",
        selected_ref_raw: str = "",
        test_status: str = "",
        blank_selected: bool = False,
        ref_key: str,
        selected_ref_key: str,
        selected_key: str,
        rows_key: str,
        healthy_key: str,
        issue_key: str,
        test_status_key: str,
    ) -> dict[str, Any]:
        refs = sorted(rows.keys())
        selected_ref = "" if blank_selected else (_sanitize_connection_name(selected_ref_raw) or (refs[0] if refs else ""))
        selected = rows.get(selected_ref, {})
        status_rows = _attach_connection_edit_urls(kind, build_connection_status_rows(
            kind,
            rows,
            selected_ref=selected_ref,
            cached_only=True,
            base_dir=BASE_DIR,
            lang=lang,
        ))
        return {
            ref_key: refs,
            f"{ref_key[:-1]}_options" if ref_key.endswith("s") else f"{ref_key}_options": _build_connection_ref_options(rows),
            selected_ref_key: selected_ref,
            selected_key: selected,
            rows_key: status_rows,
            healthy_key: sum(1 for item in status_rows if item["status"] == "ok"),
            issue_key: sum(1 for item in status_rows if item["status"] == "error"),
            test_status_key: str(test_status).strip().lower(),
        }

    def _build_discord_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "discord",
            _read_discord_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="discord_refs",
            selected_ref_key="selected_discord_ref",
            selected_key="selected_discord",
            rows_key="discord_status_rows",
            healthy_key="discord_healthy_count",
            issue_key="discord_issue_count",
            test_status_key="discord_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="discord",
            summary_cards=_build_connection_summary_cards(
                kind="discord",
                profiles=len(context.get("discord_refs", [])),
                healthy=int(context.get("discord_healthy_count", 0) or 0),
                issues=int(context.get("discord_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.webhook_status",
                        "label": "Webhook status",
                        "value": "ready" if context.get("selected_discord", {}).get("webhook_present") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_discord", {}).get("webhook_present") else "config_conn.missing",
                        "hint_key": "config_conn.discord_webhook_hint",
                        "hint": "Webhook URL is stored in the secure store, not in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="discord",
            rows=list(context.get("discord_status_rows", [])),
        )
        context["discord_edit_form_fields"] = _build_schema_form_fields(
            kind="discord",
            values=dict(context.get("selected_discord", {})),
            prefix="discord_edit",
            ref_value=str(context.get("selected_discord_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. alerts"},
            required_fields={"timeout_seconds"},
            secrets_with_hints={"webhook_url": "The webhook URL is stored in the secure store and never written into config.yaml. Leave it empty to keep the existing secret."},
            ordered_fields=["timeout_seconds", "webhook_url"],
        )
        context["discord_new_form_fields"] = _build_schema_form_fields(
            kind="discord",
            values={"timeout_seconds": 10},
            prefix="discord_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. alerts"},
            required_fields={"timeout_seconds", "webhook_url"},
            secrets_with_hints={"webhook_url": "The webhook URL is stored in the secure store and never written into config.yaml. Leave it empty to keep the existing secret."},
            ordered_fields=["timeout_seconds", "webhook_url"],
        )
        context["discord_edit_toggle_sections"] = _build_schema_toggle_sections(
            kind="discord",
            values=dict(context.get("selected_discord", {})),
            prefix="discord_edit",
            section_names=["behaviour", "events"],
        )
        context["discord_new_toggle_sections"] = _build_schema_toggle_sections(
            kind="discord",
            values={"send_test_messages": True, "allow_skill_messages": True},
            prefix="discord_new",
            section_names=["behaviour", "events"],
        )
        return context

    def _build_sftp_connections_context(
        selected_ref_raw: str = "",
        test_status: str = "",
        copy_from_ssh_ref: str = "",
        lang: str = "de",
    ) -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        sftp_rows = _read_sftp_connections()
        ssh_rows = _read_ssh_connections()
        sftp_refs = sorted(sftp_rows.keys())
        selected_sftp_ref = _sanitize_connection_name(selected_ref_raw) or (sftp_refs[0] if sftp_refs else "")
        selected_sftp = dict(sftp_rows.get(selected_sftp_ref, {}))
        ssh_refs = sorted(ssh_rows.keys())
        selected_ssh_seed_ref = _sanitize_connection_name(copy_from_ssh_ref)
        selected_ssh_seed = ssh_rows.get(selected_ssh_seed_ref, {})
        if selected_ssh_seed:
            seed_key_path = str(selected_ssh_seed.get("key_path", "")).strip()
            seed_key_present = False
            if seed_key_path:
                seed_key_file = Path(seed_key_path)
                if not seed_key_file.is_absolute():
                    seed_key_file = (BASE_DIR / seed_key_file).resolve()
                seed_key_present = seed_key_file.exists()
            selected_sftp = {
                **selected_sftp,
                "host": str(selected_ssh_seed.get("host", "")).strip(),
                "port": int(selected_ssh_seed.get("port", 22) or 22),
                "user": str(selected_ssh_seed.get("user", "")).strip(),
                "key_path": seed_key_path,
                "key_present": seed_key_present,
                "timeout_seconds": int(selected_ssh_seed.get("timeout_seconds", 10) or 10),
            }
        sftp_status_rows = build_connection_status_rows(
            "sftp",
            sftp_rows,
            selected_ref=selected_sftp_ref,
            cached_only=True,
            base_dir=BASE_DIR,
            lang=lang,
        )
        sftp_healthy_count = sum(1 for item in sftp_status_rows if item["status"] == "ok")
        sftp_issue_count = sum(1 for item in sftp_status_rows if item["status"] == "error")
        return {
            "connection_intro": _build_connection_intro(
                kind="sftp",
                summary_cards=_build_connection_summary_cards(
                    kind="sftp",
                    profiles=len(sftp_refs),
                    healthy=sftp_healthy_count,
                    issues=sftp_issue_count,
                    extra_cards=[
                        {
                            "label_key": "config_conn.auth_status",
                            "label": "Auth status",
                            "value": "Key" if selected_sftp.get("key_path") else ("Password" if selected_sftp.get("password_present") else "missing"),
                            "value_key": "config_conn.sftp_key_mode" if selected_sftp.get("key_path") else ("config_conn.sftp_password_mode" if selected_sftp.get("password_present") else "config_conn.missing"),
                            "hint_key": "config_conn.sftp_key_hint" if selected_sftp.get("key_path") else "config_conn.sftp_password_hint",
                            "hint": "SFTP can use the configured SSH key directly." if selected_sftp.get("key_path") else "Password is stored in the secure store, not in config.yaml.",
                        },
                    ],
                ),
            ),
            "connection_status_block": _build_connection_status_block(
                kind="sftp",
                rows=sftp_status_rows,
                collapse_threshold=5,
            ),
            "sftp_refs": sftp_refs,
            "sftp_ref_options": _build_connection_ref_options(sftp_rows),
            "selected_sftp_ref": selected_sftp_ref,
            "selected_sftp": selected_sftp,
            "sftp_edit_form_fields": _build_schema_form_fields(
                kind="sftp",
                values=dict(selected_sftp),
                prefix="sftp_edit",
                ref_value=selected_sftp_ref,
                placeholders={"connection_ref": "z.B. files-sftp", "host": "files.example.local", "service_url": "https://files.example.local", "user": "backup", "root_path": "/data", "key_path": "/app/data/ssh_keys/files-sftp_ed25519"},
                required_fields={"host", "user", "port", "timeout_seconds"},
                field_hints={"key_path": "Wenn gesetzt, nutzt SFTP diesen Key statt Passwort. Ideal für Profile, die du aus SSH übernommen hast."},
                secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
                ordered_fields=["host", "service_url", "user", "port", "timeout_seconds", "root_path", "key_path", "password"],
            ),
            "sftp_new_form_fields": _build_schema_form_fields(
                kind="sftp",
                values={
                    "host": str(selected_ssh_seed.get("host", "")).strip(),
                    "service_url": str(selected_ssh_seed.get("service_url", "")).strip(),
                    "user": str(selected_ssh_seed.get("user", "")).strip(),
                    "port": int(selected_ssh_seed.get("port", 22) or 22),
                    "timeout_seconds": int(selected_ssh_seed.get("timeout_seconds", 10) or 10),
                    "key_path": str(selected_ssh_seed.get("key_path", "")).strip(),
                },
                prefix="sftp_new",
                ref_value=selected_ssh_seed_ref,
                placeholders={"connection_ref": "z.B. files-sftp", "host": "files.example.local", "service_url": "https://files.example.local", "user": "backup", "root_path": "/data", "key_path": "/app/data/ssh_keys/files-sftp_ed25519"},
                required_fields={"host", "user", "port", "timeout_seconds"},
                field_hints={"key_path": "Wenn gesetzt, nutzt SFTP diesen Key statt Passwort. Ideal für Profile, die du aus SSH übernommen hast."},
                secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
                ordered_fields=["host", "service_url", "user", "port", "timeout_seconds", "root_path", "key_path", "password"],
            ),
            "ssh_refs": ssh_refs,
            "ssh_ref_options": _build_connection_ref_options(ssh_rows),
            "selected_ssh_seed_ref": selected_ssh_seed_ref,
            "selected_ssh_seed": selected_ssh_seed,
            "sftp_status_rows": sftp_status_rows,
            "sftp_healthy_count": sftp_healthy_count,
            "sftp_issue_count": sftp_issue_count,
            "sftp_test_status": str(test_status).strip().lower(),
            "sftp_guardrail_ref_options": _build_guardrail_ref_options(guardrail_rows, connection_kind="sftp", lang=lang),
        }

    def _build_smb_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        context = _build_generic_connections_context(
            "smb",
            _read_smb_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="smb_refs",
            selected_ref_key="selected_smb_ref",
            selected_key="selected_smb",
            rows_key="smb_status_rows",
            healthy_key="smb_healthy_count",
            issue_key="smb_issue_count",
            test_status_key="smb_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="smb",
            summary_cards=_build_connection_summary_cards(
                kind="smb",
                profiles=len(context.get("smb_refs", [])),
                healthy=int(context.get("smb_healthy_count", 0) or 0),
                issues=int(context.get("smb_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.password_status",
                        "label": "Password status",
                        "value": "ready" if context.get("selected_smb", {}).get("password_present") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_smb", {}).get("password_present") else "config_conn.missing",
                        "hint_key": "config_conn.smb_password_hint",
                        "hint": "Password is stored in the secure store, not in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="smb",
            rows=list(context.get("smb_status_rows", [])),
        )
        context["smb_edit_form_fields"] = _build_schema_form_fields(
            kind="smb",
            values=dict(context.get("selected_smb", {})),
            prefix="smb_edit",
            ref_value=str(context.get("selected_smb_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. team-share", "host": "nas.example.local", "share": "documents", "user": "backup", "root_path": "/"},
            required_fields={"host", "share", "port", "user", "timeout_seconds"},
            secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
            ordered_fields=["host", "share", "port", "user", "timeout_seconds", "root_path", "password"],
        )
        context["smb_new_form_fields"] = _build_schema_form_fields(
            kind="smb",
            values={"port": 445, "timeout_seconds": 10},
            prefix="smb_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. team-share", "host": "nas.example.local", "share": "documents", "user": "backup", "root_path": "/"},
            required_fields={"host", "share", "port", "user", "timeout_seconds", "password"},
            secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
            ordered_fields=["host", "share", "port", "user", "timeout_seconds", "root_path", "password"],
        )
        context["smb_guardrail_ref_options"] = _build_guardrail_ref_options(guardrail_rows, connection_kind="smb", lang=lang)
        return context

    def _build_webhook_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        context = _build_generic_connections_context(
            "webhook",
            _read_webhook_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="webhook_refs",
            selected_ref_key="selected_webhook_ref",
            selected_key="selected_webhook",
            rows_key="webhook_status_rows",
            healthy_key="webhook_healthy_count",
            issue_key="webhook_issue_count",
            test_status_key="webhook_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="webhook",
            summary_cards=_build_connection_summary_cards(
                kind="webhook",
                profiles=len(context.get("webhook_refs", [])),
                healthy=int(context.get("webhook_healthy_count", 0) or 0),
                issues=int(context.get("webhook_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.webhook_status",
                        "label": "Webhook status",
                        "value": "ready" if context.get("selected_webhook", {}).get("url_present") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_webhook", {}).get("url_present") else "config_conn.missing",
                        "hint_key": "config_conn.webhook_secret_hint",
                        "hint": "The webhook URL is stored in the secure store, not in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="webhook",
            rows=list(context.get("webhook_status_rows", [])),
        )
        context["webhook_edit_form_fields"] = _build_schema_form_fields(
            kind="webhook",
            values=dict(context.get("selected_webhook", {})),
            prefix="webhook_edit",
            ref_value=str(context.get("selected_webhook_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. incident-hook", "url": "https://example.org/webhook", "content_type": "application/json"},
            required_fields={"timeout_seconds", "method", "content_type"},
            select_options={"method": ["POST", "PUT", "PATCH"]},
            secrets_with_hints={"url": "The webhook URL is stored in the secure store, not in config.yaml."},
            ordered_fields=["timeout_seconds", "method", "content_type", "url"],
        )
        context["webhook_new_form_fields"] = _build_schema_form_fields(
            kind="webhook",
            values={"timeout_seconds": 10, "method": "POST", "content_type": "application/json"},
            prefix="webhook_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. incident-hook", "url": "https://example.org/webhook", "content_type": "application/json"},
            required_fields={"timeout_seconds", "method", "content_type", "url"},
            select_options={"method": ["POST", "PUT", "PATCH"]},
            secrets_with_hints={"url": "The webhook URL is stored in the secure store, not in config.yaml."},
            ordered_fields=["timeout_seconds", "method", "content_type", "url"],
        )
        context["webhook_guardrail_ref_options"] = _build_guardrail_ref_options(guardrail_rows, connection_kind="webhook", lang=lang)
        return context

    def _build_email_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "email",
            _read_email_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="email_refs",
            selected_ref_key="selected_email_ref",
            selected_key="selected_email",
            rows_key="email_status_rows",
            healthy_key="email_healthy_count",
            issue_key="email_issue_count",
            test_status_key="email_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="email",
            summary_cards=_build_connection_summary_cards(
                kind="email",
                profiles=len(context.get("email_refs", [])),
                healthy=int(context.get("email_healthy_count", 0) or 0),
                issues=int(context.get("email_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.password_status",
                        "label": "Password status",
                        "value": "ready" if context.get("selected_email", {}).get("password_present") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_email", {}).get("password_present") else "config_conn.missing",
                        "hint_key": "config_conn.email_password_hint",
                        "hint": "Password is stored in the secure store, not in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="email",
            rows=list(context.get("email_status_rows", [])),
        )
        context["email_edit_form_fields"] = _build_schema_form_fields(
            kind="email",
            values=dict(context.get("selected_email", {})),
            prefix="email_edit",
            ref_value=str(context.get("selected_email_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. mail-alerts", "smtp_host": "smtp.example.org", "user": "alert@example.org"},
            required_fields={"smtp_host", "port", "user", "from_email", "timeout_seconds"},
            boolean_defaults={"starttls": True, "use_ssl": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["smtp_host", "port", "user", "from_email", "to_email", "timeout_seconds", "starttls", "use_ssl", "password"],
        )
        context["email_new_form_fields"] = _build_schema_form_fields(
            kind="email",
            values={"port": 587, "timeout_seconds": 10, "starttls": True},
            prefix="email_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. mail-alerts", "smtp_host": "smtp.example.org", "user": "alert@example.org"},
            required_fields={"smtp_host", "port", "user", "from_email", "timeout_seconds", "password"},
            boolean_defaults={"starttls": True, "use_ssl": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["smtp_host", "port", "user", "from_email", "to_email", "timeout_seconds", "starttls", "use_ssl", "password"],
        )
        return context

    def _build_imap_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "imap",
            _read_imap_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="imap_refs",
            selected_ref_key="selected_imap_ref",
            selected_key="selected_imap",
            rows_key="imap_status_rows",
            healthy_key="imap_healthy_count",
            issue_key="imap_issue_count",
            test_status_key="imap_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="imap",
            summary_cards=_build_connection_summary_cards(
                kind="imap",
                profiles=len(context.get("imap_refs", [])),
                healthy=int(context.get("imap_healthy_count", 0) or 0),
                issues=int(context.get("imap_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.password_status",
                        "label": "Password status",
                        "value": "ready" if context.get("selected_imap", {}).get("password_present") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_imap", {}).get("password_present") else "config_conn.missing",
                        "hint_key": "config_conn.imap_password_hint",
                        "hint": "Password is stored in the secure store, not in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="imap",
            rows=list(context.get("imap_status_rows", [])),
        )
        context["imap_edit_form_fields"] = _build_schema_form_fields(
            kind="imap",
            values=dict(context.get("selected_imap", {})),
            prefix="imap_edit",
            ref_value=str(context.get("selected_imap_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. mail-inbox", "host": "imap.example.org", "user": "imap-user@example.org"},
            required_fields={"host", "port", "user", "mailbox", "timeout_seconds"},
            boolean_defaults={"use_ssl": True},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "mailbox", "timeout_seconds", "use_ssl", "password"],
        )
        context["imap_new_form_fields"] = _build_schema_form_fields(
            kind="imap",
            values={"port": 993, "mailbox": "INBOX", "timeout_seconds": 10, "use_ssl": True},
            prefix="imap_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. mail-inbox", "host": "imap.example.org", "user": "imap-user@example.org"},
            required_fields={"host", "port", "user", "mailbox", "timeout_seconds", "password"},
            boolean_defaults={"use_ssl": True},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "mailbox", "timeout_seconds", "use_ssl", "password"],
        )
        return context

    def _build_http_api_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        context = _build_generic_connections_context(
            "http_api",
            _read_http_api_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="http_api_refs",
            selected_ref_key="selected_http_api_ref",
            selected_key="selected_http_api",
            rows_key="http_api_status_rows",
            healthy_key="http_api_healthy_count",
            issue_key="http_api_issue_count",
            test_status_key="http_api_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="http_api",
            summary_cards=_build_connection_summary_cards(
                kind="http_api",
                profiles=len(context.get("http_api_refs", [])),
                healthy=int(context.get("http_api_healthy_count", 0) or 0),
                issues=int(context.get("http_api_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.token_status",
                        "label": "Token status",
                        "value": "ready" if context.get("selected_http_api", {}).get("auth_token_present") else "partial",
                        "value_key": "config_conn.ready" if context.get("selected_http_api", {}).get("auth_token_present") else "config_conn.partial",
                        "hint_key": "config_conn.http_api_token_hint",
                        "hint": "Bearer token is stored in the secure store when provided.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="http_api",
            rows=list(context.get("http_api_status_rows", [])),
        )
        context["http_api_edit_form_fields"] = _build_schema_form_fields(
            kind="http_api",
            values=dict(context.get("selected_http_api", {})),
            prefix="http_api_edit",
            ref_value=str(context.get("selected_http_api_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. inventory-api", "base_url": "https://api.example.org"},
            required_fields={"base_url", "health_path", "method", "timeout_seconds"},
            select_options={"method": ["GET", "POST", "HEAD"]},
            secrets_with_hints={"auth_token": "Bearer token is stored in the secure store when provided."},
            ordered_fields=["base_url", "health_path", "method", "timeout_seconds", "auth_token"],
        )
        context["http_api_new_form_fields"] = _build_schema_form_fields(
            kind="http_api",
            values={"health_path": "/", "method": "GET", "timeout_seconds": 10},
            prefix="http_api_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. inventory-api", "base_url": "https://api.example.org"},
            required_fields={"base_url", "health_path", "method", "timeout_seconds"},
            select_options={"method": ["GET", "POST", "HEAD"]},
            secrets_with_hints={"auth_token": "Bearer token is stored in the secure store when provided."},
            ordered_fields=["base_url", "health_path", "method", "timeout_seconds", "auth_token"],
        )
        context["http_api_guardrail_ref_options"] = _build_guardrail_ref_options(guardrail_rows, connection_kind="http_api", lang=lang)
        return context

    def _build_searxng_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "searxng",
            _read_searxng_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="searxng_refs",
            selected_ref_key="selected_searxng_ref",
            selected_key="selected_searxng",
            rows_key="searxng_status_rows",
            healthy_key="searxng_healthy_count",
            issue_key="searxng_issue_count",
            test_status_key="searxng_test_status",
        )
        context["searxng_stack_status"] = probe_searxng_stack_service(lang=lang)
        selected_profile = dict(context.get("selected_searxng", {}))
        selected_categories = {
            str(item).strip()
            for item in (selected_profile.get("categories") or [])
            if str(item).strip()
        }
        selected_engines = {
            str(item).strip()
            for item in (selected_profile.get("engines") or [])
            if str(item).strip()
        }
        default_profile = {
            "timeout_seconds": 10,
            "language": "de-CH",
            "safe_search": 1,
            "categories": ["general"],
            "engines": [],
            "time_range": "",
            "max_results": 5,
        }
        context["searxng_default_base_url"] = resolve_searxng_base_url("")
        context["searxng_language_options"] = ["de-CH", "de-DE", "en-GB", "en-US", "fr-CH"]
        context["searxng_safe_search_options"] = [
            {"value": "0", "label": "0 - aus / off"},
            {"value": "1", "label": "1 - normal"},
            {"value": "2", "label": "2 - strikt / strict"},
        ]
        context["searxng_time_range_options"] = [
            {"value": "", "label": "kein Standard / none"},
            {"value": "day", "label": "day"},
            {"value": "month", "label": "month"},
            {"value": "year", "label": "year"},
        ]
        context["searxng_edit_profile"] = {
            **default_profile,
            **selected_profile,
        }
        context["searxng_new_profile"] = dict(default_profile)
        context["searxng_category_options"] = [
            {"value": value, "label": label, "checked": value in selected_categories}
            for value, label in _SEARXNG_CATEGORY_OPTIONS
        ]
        context["searxng_engine_options"] = [
            {"value": value, "label": label, "checked": value in selected_engines}
            for value, label in _SEARXNG_ENGINE_OPTIONS
        ]
        context["searxng_new_category_options"] = [
            {"value": value, "label": label, "checked": value in {"general"}}
            for value, label in _SEARXNG_CATEGORY_OPTIONS
        ]
        context["searxng_new_engine_options"] = [
            {"value": value, "label": label, "checked": False}
            for value, label in _SEARXNG_ENGINE_OPTIONS
        ]
        context["connection_intro"] = _build_connection_intro(
            kind="searxng",
            summary_cards=_build_connection_summary_cards(
                kind="searxng",
                profiles=len(context.get("searxng_refs", [])),
                healthy=int(context.get("searxng_healthy_count", 0) or 0),
                issues=int(context.get("searxng_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.endpoint",
                        "label": "Target",
                        "value": resolve_searxng_base_url(str(selected_profile.get("base_url", "")).strip()),
                        "hint_key": "config_conn.searxng_base_url_hint",
                        "hint": "ARIA uses the fixed in-stack SearXNG JSON API target.",
                    },
                    {
                        "label_key": "config_conn.searxng_max_results",
                        "label": "Max. Treffer",
                        "value": str(selected_profile.get("max_results", 5) or 5),
                        "hint_key": "config_conn.searxng_max_results_hint",
                        "hint": "How many hits ARIA should bring into the chat context by default.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="searxng",
            rows=list(context.get("searxng_status_rows", [])),
        )
        return context

    def _build_rss_connections_context(
        selected_ref_raw: str = "",
        test_status: str = "",
        create_new: bool = False,
        lang: str = "de",
    ) -> dict[str, Any]:
        selected_ref_requested = bool(_sanitize_connection_name(selected_ref_raw))
        context = _build_generic_connections_context(
            "rss",
            _read_rss_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            blank_selected=bool(create_new),
            ref_key="rss_refs",
            selected_ref_key="selected_rss_ref",
            selected_key="selected_rss",
            rows_key="rss_status_rows",
            healthy_key="rss_healthy_count",
            issue_key="rss_issue_count",
            test_status_key="rss_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="rss",
            summary_cards=_build_connection_summary_cards(
                kind="rss",
                profiles=len(context.get("rss_refs", [])),
                healthy=int(context.get("rss_healthy_count", 0) or 0),
                issues=int(context.get("rss_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.endpoint",
                        "label": "Target",
                        "value": "ready" if context.get("selected_rss", {}).get("feed_url") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_rss", {}).get("feed_url") else "config_conn.missing",
                        "hint_key": "config_conn.rss_feed_hint",
                        "hint": "Feed URL is stored directly in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_intro"]["back_url"] = "/config/connections/rss"
        context["connection_intro"]["back_label_key"] = "config_conn.back_to_rss_overview"
        context["connection_intro"]["back_label"] = "Back to RSS overview"
        context["connection_status_block"] = _build_connection_status_block(
            kind="rss",
            rows=list(context.get("rss_status_rows", [])),
        )
        context["rss_poll_interval_minutes"] = _read_rss_poll_interval_minutes()
        rss_group_options = sorted(
            {
                str(row.get("group_name", "")).strip()
                for row in context.get("rss_status_rows", [])
                if isinstance(row, dict) and str(row.get("group_name", "")).strip()
            },
            key=str.lower,
        )
        context["rss_create_new"] = bool(create_new)
        context["rss_selected_explicit"] = selected_ref_requested
        context["rss_edit_form_fields"] = _build_schema_form_fields(
            kind="rss",
            values=dict(context.get("selected_rss", {})),
            prefix="rss_edit",
            ref_value=str(context.get("selected_rss_ref", "")).strip(),
            placeholders={
                "connection_ref": "z.B. security-feed",
                "feed_url": "https://example.org/feed.xml",
                "group_name": "z.B. Security",
            },
            datalist_options={"group_name": rss_group_options},
            required_fields={"feed_url", "timeout_seconds"},
            ordered_fields=["feed_url", "group_name", "timeout_seconds"],
        )
        context["rss_new_form_fields"] = _build_schema_form_fields(
            kind="rss",
            values={"group_name": "", "timeout_seconds": 10},
            prefix="rss_new",
            ref_value="",
            placeholders={
                "connection_ref": "z.B. security-feed",
                "feed_url": "https://example.org/feed.xml",
                "group_name": "z.B. Security",
            },
            datalist_options={"group_name": rss_group_options},
            required_fields={"feed_url", "timeout_seconds"},
            ordered_fields=["feed_url", "group_name", "timeout_seconds"],
        )
        return context

    def _next_rss_import_ref(rows: dict[str, Any], title: str, feed_url: str) -> str:
        normalized_feed_url = _normalize_rss_feed_url_for_dedupe(feed_url) or feed_url
        parsed_host = urlparse(normalized_feed_url).netloc.replace("www.", "")
        seed = _sanitize_connection_name(title) or _sanitize_connection_name(parsed_host) or "rss-feed"
        if seed not in rows:
            return seed
        for idx in range(2, 1000):
            candidate = _sanitize_connection_name(f"{seed}-{idx}")
            if candidate and candidate not in rows:
                return candidate
        raise ValueError("Kein freier RSS-Ref mehr für OPML-Import gefunden.")

    def _build_mqtt_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "mqtt",
            _read_mqtt_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="mqtt_refs",
            selected_ref_key="selected_mqtt_ref",
            selected_key="selected_mqtt",
            rows_key="mqtt_status_rows",
            healthy_key="mqtt_healthy_count",
            issue_key="mqtt_issue_count",
            test_status_key="mqtt_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="mqtt",
            summary_cards=_build_connection_summary_cards(
                kind="mqtt",
                profiles=len(context.get("mqtt_refs", [])),
                healthy=int(context.get("mqtt_healthy_count", 0) or 0),
                issues=int(context.get("mqtt_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.password_status",
                        "label": "Password status",
                        "value": "ready" if context.get("selected_mqtt", {}).get("password_present") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_mqtt", {}).get("password_present") else "config_conn.missing",
                        "hint_key": "config_conn.mqtt_password_hint",
                        "hint": "Password is stored in the secure store, not in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="mqtt",
            rows=list(context.get("mqtt_status_rows", [])),
        )
        context["mqtt_edit_form_fields"] = _build_schema_form_fields(
            kind="mqtt",
            values=dict(context.get("selected_mqtt", {})),
            prefix="mqtt_edit",
            ref_value=str(context.get("selected_mqtt_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. event-bus", "host": "mqtt.example.local", "user": "mqtt-user", "topic": "aria/events"},
            required_fields={"host", "port", "user", "timeout_seconds"},
            boolean_defaults={"use_tls": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "topic", "timeout_seconds", "use_tls", "password"],
        )
        context["mqtt_new_form_fields"] = _build_schema_form_fields(
            kind="mqtt",
            values={"port": 1883, "timeout_seconds": 10, "use_tls": False},
            prefix="mqtt_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. event-bus", "host": "mqtt.example.local", "user": "mqtt-user", "topic": "aria/events"},
            required_fields={"host", "port", "user", "timeout_seconds", "password"},
            boolean_defaults={"use_tls": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "topic", "timeout_seconds", "use_tls", "password"],
        )
        return context

    def _build_connections_hub_cards() -> list[dict[str, Any]]:
        builder_map: dict[str, Callable[[], dict[str, Any]]] = {
            "ssh": lambda: _build_ssh_connections_context(),
            "discord": lambda: _build_discord_connections_context(),
            "sftp": lambda: _build_sftp_connections_context(),
            "smb": lambda: _build_smb_connections_context(),
            "webhook": lambda: _build_webhook_connections_context(),
            "email": lambda: _build_email_connections_context(),
            "imap": lambda: _build_imap_connections_context(),
            "http_api": lambda: _build_http_api_connections_context(),
            "searxng": lambda: _build_searxng_connections_context(),
            "rss": lambda: _build_rss_connections_context(),
            "mqtt": lambda: _build_mqtt_connections_context(),
        }
        rows: list[dict[str, Any]] = []
        for item in connection_menu_rows():
            kind = normalize_connection_kind(str(item.get("kind", "")).strip())
            builder = builder_map.get(kind)
            if not builder:
                continue
            context = builder()
            status_rows = list((context.get("connection_status_block") or {}).get("rows", []))
            rows.append(
                {
                    "id": kind,
                    "href": str(item.get("url") or connection_edit_page(kind)).strip(),
                    "title_key": str(item.get("title_key") or "").strip(),
                    "title_fallback": str(item.get("label") or kind).strip(),
                    "desc_key": str(item.get("desc_key") or "").strip(),
                    "desc_fallback": "",
                    "profiles": len(status_rows),
                    "healthy": sum(1 for row in status_rows if str(row.get("status", "")).strip().lower() == "ok"),
                    "issues": sum(1 for row in status_rows if str(row.get("status", "")).strip().lower() == "error"),
                    "icon": str(item.get("icon") or kind).strip(),
                    "alpha": bool(item.get("alpha", False)),
                }
            )
        return rows

    def _get_connection_delete_spec(kind: str) -> dict[str, Any]:
        clean_kind = normalize_connection_kind(kind)
        admin_spec = CONNECTION_ADMIN_SPECS.get(clean_kind)
        if not admin_spec:
            raise ValueError("Unbekannter Connection-Typ.")
        return {
            "section": clean_kind,
            "page": connection_edit_page(clean_kind),
            "ref_query": connection_ref_query_param(clean_kind),
            "secret_keys": list(admin_spec.get("secret_keys", [])),
            "health_prefix": str(admin_spec.get("health_prefix", clean_kind)),
            "success_message": str(admin_spec.get("success_message", "Connection-Profil gelöscht")),
        }

    def _delete_connection_profile(kind: str, ref_raw: str) -> dict[str, Any]:
        spec = _get_connection_delete_spec(kind)
        ref = _sanitize_connection_name(ref_raw)
        if not ref:
            raise ValueError("Connection-Ref ist ungültig.")
        raw = _read_raw_config()
        raw.setdefault("connections", {})
        if not isinstance(raw["connections"], dict):
            raw["connections"] = {}
        raw["connections"].setdefault(spec["section"], {})
        if not isinstance(raw["connections"][spec["section"]], dict):
            raw["connections"][spec["section"]] = {}
        rows = raw["connections"][spec["section"]]
        if ref not in rows:
            raise ValueError("Connection-Profil nicht gefunden.")
        rows.pop(ref, None)
        store = _get_secure_store(raw)
        if store:
            for key_tmpl in spec["secret_keys"]:
                store.delete_secret(str(key_tmpl).format(ref=ref))
        _write_raw_config(raw)
        delete_connection_health(f"{spec['health_prefix']}:{ref}")
        _reload_runtime()
        return spec

    def _prepare_connection_save(kind: str, connection_ref: str, original_ref: str = "") -> tuple[dict[str, Any], Any, dict[str, Any], str, str, bool]:
        spec = _get_connection_delete_spec(kind)
        ref = _sanitize_connection_name(connection_ref)
        original_ref_clean = _sanitize_connection_name(original_ref)
        is_create = not original_ref_clean
        if not ref:
            raise ValueError("Connection-Ref ist ungültig.")
        raw = _read_raw_config()
        raw.setdefault("connections", {})
        if not isinstance(raw["connections"], dict):
            raw["connections"] = {}
        raw["connections"].setdefault(spec["section"], {})
        if not isinstance(raw["connections"][spec["section"]], dict):
            raw["connections"][spec["section"]] = {}
        rows = raw["connections"][spec["section"]]
        if is_create:
            if ref in rows:
                raise ValueError("Connection-Profil existiert bereits.")
        else:
            if original_ref_clean not in rows:
                raise ValueError("Connection-Profil nicht gefunden.")
            if ref != original_ref_clean and ref in rows:
                raise ValueError("Connection-Ref existiert bereits.")
        store = _get_secure_store(raw)
        return raw, store, rows, ref, original_ref_clean, is_create

    def _rename_connection_secret(store: Any, key_from: str, key_to: str) -> None:
        if not store or key_from == key_to:
            return
        value = store.get_secret(key_from, default=None)
        if value in (None, ""):
            return
        store.set_secret(key_to, value)
        store.delete_secret(key_from)

    def _finalize_connection_save(
        kind: str,
        *,
        raw: dict[str, Any],
        rows: dict[str, Any],
        ref: str,
        original_ref: str,
        row_value: dict[str, Any],
        store: Any = None,
        secret_renames: list[tuple[str, str]] | None = None,
    ) -> None:
        spec = _get_connection_delete_spec(kind)
        rows[ref] = row_value
        if original_ref and original_ref != ref:
            rows.pop(original_ref, None)
            delete_connection_health(f"{spec['health_prefix']}:{original_ref}")
            if store:
                for src, dest in secret_renames or []:
                    _rename_connection_secret(store, src, dest)
        _write_raw_config(raw)
        _reload_runtime()

    def _normalize_connection_mode(mode: str | None) -> str:
        clean = str(mode or "edit").strip().lower()
        return "create" if clean in {"create", "new", "add"} else "edit"

    def _connection_mode_url(request: Request, mode: str) -> str:
        pairs = [(key, value) for key, value in parse_qsl(request.url.query, keep_blank_values=True) if key != "mode"]
        pairs.append(("mode", _normalize_connection_mode(mode)))
        query = urlencode(pairs)
        return f"{request.url.path}?{query}" if query else str(request.url.path)

    def _base_connections_page_context(
        request: Request,
        saved: int,
        info: str,
        error: str,
        *,
        mode: str = "edit",
    ) -> dict[str, Any]:
        connection_mode = _normalize_connection_mode(mode)
        return_to = _set_logical_back_url(request, fallback="/config")
        return {
            "title": settings.ui.title,
            "username": _get_username_from_request(request),
            "saved": bool(saved),
            "info_message": info,
            "error_message": error,
            "connection_mode": connection_mode,
            "connection_mode_edit_url": _connection_mode_url(request, "edit"),
            "connection_mode_create_url": _connection_mode_url(request, "create"),
            "return_to": return_to,
        }

    def _render_connection_page(
        request: Request,
        *,
        kind: str,
        saved: int,
        info: str,
        error: str,
        context_builder: Callable[..., dict[str, Any]],
        mode: str = "edit",
        **builder_kwargs: Any,
    ) -> HTMLResponse:
        context = _base_connections_page_context(request, saved, info, error, mode=mode)
        builder_kwargs.setdefault("lang", str(getattr(request.state, "lang", "de") or "de"))
        context.update(context_builder(**builder_kwargs))
        if isinstance(context.get("connection_intro"), dict):
            context["connection_intro"] = dict(context["connection_intro"])
            context["connection_intro"]["back_url"] = context.get("return_to") or "/config"
        return TEMPLATES.TemplateResponse(
            request=request,
            name=connection_template_name(kind),
            context=context,
        )

    @app.get("/config/connections/ssh", response_class=HTMLResponse)
    async def config_connections_ssh_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        ref: str = "",
        test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="ssh",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_ssh_connections_context,
            selected_ref_raw=ref,
            test_status=test_status,
            mode=mode,
        )

    @app.get("/config/connections/discord", response_class=HTMLResponse)
    async def config_connections_discord_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        discord_ref: str = "",
        discord_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="discord",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_discord_connections_context,
            selected_ref_raw=discord_ref,
            test_status=discord_test_status,
            mode=mode,
        )

    @app.get("/config/connections/sftp", response_class=HTMLResponse)
    async def config_connections_sftp_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        sftp_ref: str = "",
        sftp_test_status: str = "",
        copy_from_ssh_ref: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="sftp",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_sftp_connections_context,
            selected_ref_raw=sftp_ref,
            test_status=sftp_test_status,
            copy_from_ssh_ref=copy_from_ssh_ref,
            mode=mode,
        )

    @app.get("/config/connections/smb", response_class=HTMLResponse)
    async def config_connections_smb_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        smb_ref: str = "",
        smb_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="smb",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_smb_connections_context,
            selected_ref_raw=smb_ref,
            test_status=smb_test_status,
            mode=mode,
        )

    @app.get("/config/connections/webhook", response_class=HTMLResponse)
    async def config_connections_webhook_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        webhook_ref: str = "",
        webhook_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="webhook",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_webhook_connections_context,
            selected_ref_raw=webhook_ref,
            test_status=webhook_test_status,
            mode=mode,
        )

    @app.get("/config/connections/email")
    async def config_connections_email_legacy() -> RedirectResponse:
        return RedirectResponse(url="/config/connections/smtp", status_code=303)

    @app.get("/config/connections/smtp", response_class=HTMLResponse)
    async def config_connections_smtp_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        email_ref: str = "",
        email_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="email",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_email_connections_context,
            selected_ref_raw=email_ref,
            test_status=email_test_status,
            mode=mode,
        )

    @app.get("/config/connections/imap", response_class=HTMLResponse)
    async def config_connections_imap_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        imap_ref: str = "",
        imap_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="imap",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_imap_connections_context,
            selected_ref_raw=imap_ref,
            test_status=imap_test_status,
            mode=mode,
        )

    @app.get("/config/connections/http-api", response_class=HTMLResponse)
    async def config_connections_http_api_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        http_api_ref: str = "",
        http_api_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="http_api",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_http_api_connections_context,
            selected_ref_raw=http_api_ref,
            test_status=http_api_test_status,
            mode=mode,
        )

    @app.get("/config/connections/searxng", response_class=HTMLResponse)
    async def config_connections_searxng_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        searxng_ref: str = "",
        searxng_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="searxng",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_searxng_connections_context,
            selected_ref_raw=searxng_ref,
            test_status=searxng_test_status,
            mode=mode,
        )

    @app.get("/config/connections/rss", response_class=HTMLResponse)
    async def config_connections_rss_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        rss_ref: str = "",
        rss_test_status: str = "",
        create_new: int = 0,
        refresh_groups: int = 0,
        mode: str = "edit",
    ) -> HTMLResponse:
        effective_mode = "create" if create_new else mode
        context = _base_connections_page_context(request, saved, info, error, mode=effective_mode)
        context.update(_build_rss_connections_context(rss_ref, rss_test_status, bool(create_new)))
        rss_rows = context.get("rss_status_rows", [])
        cache_path = BASE_DIR / "data" / "runtime" / "rss_groups.json"
        use_refresh = bool(refresh_groups)
        rss_groups = None if use_refresh else load_cached_rss_status_groups(cache_path, rss_rows)
        if rss_groups is None:
            rss_groups = await build_rss_status_groups(
                rss_rows,
                getattr(pipeline, "llm_client", None) if use_refresh else None,
            )
            save_cached_rss_status_groups(cache_path, rss_rows, rss_groups)
        context["rss_status_groups"] = rss_groups
        context["rss_groups_refreshed"] = use_refresh
        if use_refresh and not info and not error:
            context["info_message"] = "RSS-Kategorien aktualisiert"
        return TEMPLATES.TemplateResponse(request=request, name=connection_template_name("rss"), context=context)

    @app.get("/config/connections/ssh/suggest-metadata")
    async def config_connections_ssh_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        service_url: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_service_url = str(service_url or "").strip()
        if not clean_service_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": _msg(lang, "Service-URL fehlt.", "Service URL is missing."),
                },
                status_code=400,
            )
        suggestion = await _suggest_ssh_metadata_with_llm(
            service_url=clean_service_url,
            connection_ref=_sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})

    @app.get("/config/connections/sftp/suggest-metadata")
    async def config_connections_sftp_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        service_url: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_service_url = str(service_url or "").strip()
        if not clean_service_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": _msg(lang, "Service-URL fehlt.", "Service URL is missing."),
                },
                status_code=400,
            )
        suggestion = await _suggest_ssh_metadata_with_llm(
            service_url=clean_service_url,
            connection_ref=_sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})

    @app.get("/config/connections/rss/suggest-metadata")
    async def config_connections_rss_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        feed_url: str = "",
        group_name: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_feed_url = _normalize_rss_feed_url_for_dedupe(feed_url)
        if not clean_feed_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": _msg(lang, "Feed-URL fehlt.", "Feed URL is missing."),
                },
                status_code=400,
            )
        suggestion = await _suggest_rss_metadata_with_llm(
            feed_url=clean_feed_url,
            connection_ref=_sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            group_name=str(group_name or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})

    @app.post("/config/connections/rss/poll-interval/save")
    async def config_connections_rss_poll_interval_save(
        request: Request,
        poll_interval_minutes: int = Form(60),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            poll_interval = max(1, min(int(poll_interval_minutes), 10080))
            raw = _read_raw_config()
            raw.setdefault("rss", {})
            if not isinstance(raw["rss"], dict):
                raw["rss"] = {}
            raw["rss"]["poll_interval_minutes"] = poll_interval
            connections = raw.setdefault("connections", {})
            if not isinstance(connections, dict):
                raw["connections"] = {}
                connections = raw["connections"]
            rss_rows = connections.setdefault("rss", {})
            if not isinstance(rss_rows, dict):
                connections["rss"] = {}
                rss_rows = connections["rss"]
            for row in rss_rows.values():
                if isinstance(row, dict):
                    row["poll_interval_minutes"] = poll_interval
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                "/config/connections/rss?saved=1&mode=edit"
                f"&info={quote_plus(_msg(lang, f'RSS-Ping-Intervall global auf {poll_interval} Minuten gesetzt.', f'Global RSS ping interval set to {poll_interval} minutes.'))}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/connections/rss?mode=edit&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
            )

    @app.get("/config/connections/mqtt", response_class=HTMLResponse)
    async def config_connections_mqtt_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        mqtt_ref: str = "",
        mqtt_test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return _render_connection_page(
            request,
            kind="mqtt",
            saved=saved,
            info=info,
            error=error,
            context_builder=_build_mqtt_connections_context,
            selected_ref_raw=mqtt_ref,
            test_status=mqtt_test_status,
            mode=mode,
        )

    @app.post("/config/connections/delete")
    async def config_connections_delete(
        request: Request,
        kind: str = Form(...),
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        try:
            spec = _delete_connection_profile(kind, connection_ref)
            return _redirect_with_return_to(
                f"{spec['page']}?saved=1&info={quote_plus(str(spec['success_message']))}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            try:
                spec = _get_connection_delete_spec(kind)
                ref_query = str(spec.get("ref_query", "")).strip()
                ref_suffix = f"&{ref_query}={quote_plus(connection_ref)}" if ref_query else ""
                target_page = str(spec.get("page", "/config"))
            except ValueError:
                target_page = "/config"
                ref_suffix = ""
            return _redirect_with_return_to(
                f"{target_page}?error={quote_plus(str(exc))}{ref_suffix}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/save")
    async def config_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        port: int = Form(22),
        user: str = Form(""),
        service_url: str = Form(""),
        login_user: str = Form(""),
        login_password: str = Form(""),
        run_key_exchange: str = Form("1"),
        create_matching_sftp: str = Form("0"),
        key_path: str = Form(""),
        timeout_seconds: int = Form(20),
        strict_host_key_checking: str = Form("accept-new"),
        guardrail_ref: str = Form(""),
        allow_commands: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("ssh", connection_ref, original_ref)
            allow_list = [line.strip() for line in re.split(r"[\n,]+", str(allow_commands)) if line.strip()]
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "ssh",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu SSH.")
            should_exchange = str(run_key_exchange).strip().lower() in {"1", "true", "on", "yes"}
            clean_host = str(host).strip()
            clean_user = str(user).strip()
            row_value = {
                "host": clean_host,
                "port": max(1, int(port)),
                "user": clean_user,
                "service_url": str(service_url).strip(),
                "key_path": str(key_path).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "strict_host_key_checking": str(strict_host_key_checking).strip() or "accept-new",
                "guardrail_ref": selected_guardrail_ref,
                "allow_commands": allow_list,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            info = _msg(lang, "Profil gespeichert", "Profile saved")
            if should_exchange and login_password.strip():
                exch_user, exch_key = _perform_ssh_key_exchange(
                    ref=ref,
                    host=clean_host,
                    port=max(1, int(port)),
                    profile_user=clean_user,
                    login_user=login_user,
                    login_password=login_password,
                )
                row_value["user"] = exch_user
                row_value["key_path"] = str(exch_key)
                info = _msg(lang, "Profil gespeichert + Key-Exchange erfolgreich", "Profile saved + key exchange successful")
            matching_sftp_note = ""
            if _is_create and str(create_matching_sftp).strip().lower() in {"1", "true", "on", "yes"}:
                connections = raw.setdefault("connections", {})
                if not isinstance(connections, dict):
                    raise ValueError("Ungültige Connection-Konfiguration.")
                sftp_rows = connections.setdefault("sftp", {})
                if not isinstance(sftp_rows, dict):
                    raise ValueError("Ungültige SFTP-Sektion.")
                sftp_ref = _derive_matching_sftp_ref(ref)
                key_path_for_sftp = str(row_value.get("key_path", "")).strip()
                if not key_path_for_sftp:
                    matching_sftp_note = _msg(
                        lang,
                        "Passendes SFTP-Profil nicht erzeugt: erst SSH-Key speichern oder Key-Exchange ausführen.",
                        "Matching SFTP profile not created: save an SSH key first or run key exchange.",
                    )
                elif sftp_ref in sftp_rows:
                    matching_sftp_note = _msg(
                        lang,
                        f"Passendes SFTP-Profil `{sftp_ref}` existiert bereits und blieb unverändert.",
                        f"Matching SFTP profile `{sftp_ref}` already exists and was left unchanged.",
                    )
                else:
                    sftp_rows[sftp_ref] = {
                        "host": clean_host,
                        "port": max(1, int(port)),
                        "user": str(row_value.get("user", "")).strip(),
                        "key_path": key_path_for_sftp,
                        "timeout_seconds": max(5, int(timeout_seconds)),
                        "root_path": "/",
                        **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
                    }
                    matching_sftp_note = _msg(
                        lang,
                        f"Passendes SFTP-Profil `{sftp_ref}` mitgespeichert",
                        f"Matching SFTP profile `{sftp_ref}` created",
                    )
            _finalize_connection_save(
                "ssh",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            if matching_sftp_note:
                info = f"{info} · {matching_sftp_note}"
            if should_exchange and not login_password.strip():
                info = _msg(lang, "Profil gespeichert (ohne Key-Exchange: Passwort fehlt)", "Profile saved (without key exchange: password missing)")
                if matching_sftp_note:
                    info = f"{info} · {matching_sftp_note}"
            test_result = build_connection_status_row(
                "ssh",
                ref,
                row_value,
                page_probe=False,
                base_dir=BASE_DIR,
                lang=lang,
            )
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/ssh?saved=1&info={quote_plus(info + ' · ' + _msg(lang, 'Verbindung erfolgreich getestet', 'connection test succeeded'))}"
                    f"&ref={quote_plus(ref)}&test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(info + ' · ' + _msg(lang, 'Verbindungstest fehlgeschlagen', 'connection test failed'))}"
                f"&error={quote_plus(test_result['message'])}&ref={quote_plus(ref)}&test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            suffix = f"&ref={quote_plus(ref_hint)}" if ref_hint else ""
            detail = _friendly_ssh_setup_error(lang, exc)
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(detail)}{suffix}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/discord/save")
    async def config_discord_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        webhook_url: str = Form(""),
        timeout_seconds: int = Form(10),
        send_test_messages: str = Form("0"),
        allow_skill_messages: str = Form("0"),
        alert_skill_errors: str = Form("0"),
        alert_safe_fix: str = Form("0"),
        alert_connection_changes: str = Form("0"),
        alert_system_events: str = Form("0"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("discord", connection_ref, original_ref)
            clean_webhook = str(webhook_url).strip()
            if not store:
                raise ValueError("Security Store ist für Discord-Webhooks erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_webhook = store.get_secret(f"connections.discord.{existing_secret_ref}.webhook_url", default="")
            if not clean_webhook:
                clean_webhook = existing_webhook
            if not clean_webhook:
                raise ValueError("Discord-Webhook-URL fehlt.")
            row_value = {
                "timeout_seconds": max(5, int(timeout_seconds)),
                "send_test_messages": str(send_test_messages).strip().lower() in {"1", "true", "on", "yes"},
                "allow_skill_messages": str(allow_skill_messages).strip().lower() in {"1", "true", "on", "yes"},
                "alert_skill_errors": str(alert_skill_errors).strip().lower() in {"1", "true", "on", "yes"},
                "alert_safe_fix": str(alert_safe_fix).strip().lower() in {"1", "true", "on", "yes"},
                "alert_connection_changes": str(alert_connection_changes).strip().lower() in {"1", "true", "on", "yes"},
                "alert_system_events": str(alert_system_events).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.discord.{ref}.webhook_url", clean_webhook)
            _finalize_connection_save(
                "discord",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.discord.{original_ref_clean}.webhook_url",
                        f"connections.discord.{ref}.webhook_url",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_discord_connections().get(ref, {})
            test_result = build_connection_status_row("discord", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/discord?saved=1&info={quote_plus(_connection_saved_test_info('Discord', lang, success=True))}"
                    f"&discord_ref={quote_plus(ref)}&discord_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/discord?saved=1&info={quote_plus(_connection_saved_test_info('Discord', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&discord_ref={quote_plus(ref)}&discord_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/discord?error={quote_plus(str(exc))}&discord_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/sftp/save")
    async def config_sftp_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        service_url: str = Form(""),
        port: int = Form(22),
        user: str = Form(""),
        password: str = Form(""),
        key_path: str = Form(""),
        timeout_seconds: int = Form(10),
        root_path: str = Form(""),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("sftp", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für SFTP-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.sftp.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            clean_key_path = str(key_path).strip()
            if not clean_password and not clean_key_path:
                raise ValueError("SFTP braucht Passwort oder Key-Pfad.")
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "sftp",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu SFTP.")
            row_value = {
                "host": str(host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "service_url": str(service_url).strip(),
                "key_path": clean_key_path,
                "timeout_seconds": max(5, int(timeout_seconds)),
                "root_path": str(root_path).strip(),
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.sftp.{ref}.password", clean_password if clean_password else "")
            _finalize_connection_save(
                "sftp",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.sftp.{original_ref_clean}.password",
                        f"connections.sftp.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_sftp_connections().get(ref, {})
            test_result = build_connection_status_row("sftp", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/sftp?saved=1&info={quote_plus(_connection_saved_test_info('SFTP', lang, success=True))}"
                    f"&sftp_ref={quote_plus(ref)}&sftp_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/sftp?saved=1&info={quote_plus(_connection_saved_test_info('SFTP', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&sftp_ref={quote_plus(ref)}&sftp_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/sftp?error={quote_plus(str(exc))}&sftp_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/smb/save")
    async def config_smb_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        share: str = Form(""),
        port: int = Form(445),
        user: str = Form(""),
        password: str = Form(""),
        timeout_seconds: int = Form(10),
        root_path: str = Form(""),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("smb", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für SMB-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.smb.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("SMB-Passwort fehlt.")
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "smb",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu SMB.")
            row_value = {
                "host": str(host).strip(),
                "share": str(share).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "root_path": str(root_path).strip(),
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.smb.{ref}.password", clean_password)
            _finalize_connection_save(
                "smb",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.smb.{original_ref_clean}.password",
                        f"connections.smb.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_smb_connections().get(ref, {})
            test_result = build_connection_status_row("smb", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/smb?saved=1&info={quote_plus(_connection_saved_test_info('SMB', lang, success=True))}&smb_ref={quote_plus(ref)}&smb_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/smb?saved=1&info={quote_plus(_connection_saved_test_info('SMB', lang, success=False))}&error={quote_plus(test_result['message'])}&smb_ref={quote_plus(ref)}&smb_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/smb?error={quote_plus(str(exc))}&smb_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/webhook/save")
    async def config_webhook_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        url: str = Form(""),
        timeout_seconds: int = Form(10),
        method: str = Form("POST"),
        content_type: str = Form("application/json"),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("webhook", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für Webhook-URLs erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_url = store.get_secret(f"connections.webhook.{existing_secret_ref}.url", default="")
            clean_url = str(url).strip() or existing_url
            if not clean_url:
                raise ValueError("Webhook-URL fehlt.")
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "webhook",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu Webhook.")
            row_value = {
                "timeout_seconds": max(5, int(timeout_seconds)),
                "method": str(method).strip().upper() or "POST",
                "content_type": str(content_type).strip() or "application/json",
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.webhook.{ref}.url", clean_url)
            _finalize_connection_save(
                "webhook",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.webhook.{original_ref_clean}.url",
                        f"connections.webhook.{ref}.url",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_webhook_connections().get(ref, {})
            test_result = build_connection_status_row("webhook", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/webhook?saved=1&info={quote_plus(_connection_saved_test_info('Webhook', lang, success=True))}&webhook_ref={quote_plus(ref)}&webhook_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/webhook?saved=1&info={quote_plus(_connection_saved_test_info('Webhook', lang, success=False))}&error={quote_plus(test_result['message'])}&webhook_ref={quote_plus(ref)}&webhook_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/webhook?error={quote_plus(str(exc))}&webhook_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/smtp/save")
    async def config_smtp_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        smtp_host: str = Form(""),
        port: int = Form(587),
        user: str = Form(""),
        password: str = Form(""),
        from_email: str = Form(""),
        to_email: str = Form(""),
        timeout_seconds: int = Form(10),
        starttls: str = Form("1"),
        use_ssl: str = Form("0"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("email", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für SMTP-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.email.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("SMTP-Passwort fehlt.")
            row_value = {
                "smtp_host": str(smtp_host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "from_email": str(from_email).strip(),
                "to_email": str(to_email).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "starttls": str(starttls).strip().lower() in {"1", "true", "on", "yes"},
                "use_ssl": str(use_ssl).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.email.{ref}.password", clean_password)
            _finalize_connection_save(
                "email",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.email.{original_ref_clean}.password",
                        f"connections.email.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_email_connections().get(ref, {})
            test_result = build_connection_status_row("email", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/smtp?saved=1&info={quote_plus(_connection_saved_test_info('SMTP', lang, success=True))}&email_ref={quote_plus(ref)}&email_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/smtp?saved=1&info={quote_plus(_connection_saved_test_info('SMTP', lang, success=False))}&error={quote_plus(test_result['message'])}&email_ref={quote_plus(ref)}&email_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/smtp?error={quote_plus(str(exc))}&email_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/imap/save")
    async def config_imap_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        port: int = Form(993),
        user: str = Form(""),
        password: str = Form(""),
        mailbox: str = Form("INBOX"),
        timeout_seconds: int = Form(10),
        use_ssl: str = Form("1"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("imap", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für IMAP-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.imap.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("IMAP-Passwort fehlt.")
            row_value = {
                "host": str(host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "mailbox": str(mailbox).strip() or "INBOX",
                "timeout_seconds": max(5, int(timeout_seconds)),
                "use_ssl": str(use_ssl).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.imap.{ref}.password", clean_password)
            _finalize_connection_save(
                "imap",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.imap.{original_ref_clean}.password",
                        f"connections.imap.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_imap_connections().get(ref, {})
            test_result = build_connection_status_row("imap", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/imap?saved=1&info={quote_plus(_connection_saved_test_info('IMAP', lang, success=True))}&imap_ref={quote_plus(ref)}&imap_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/imap?saved=1&info={quote_plus(_connection_saved_test_info('IMAP', lang, success=False))}&error={quote_plus(test_result['message'])}&imap_ref={quote_plus(ref)}&imap_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/imap?error={quote_plus(str(exc))}&imap_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/http-api/save")
    async def config_http_api_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        base_url: str = Form(""),
        auth_token: str = Form(""),
        timeout_seconds: int = Form(10),
        health_path: str = Form("/"),
        method: str = Form("GET"),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("http_api", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für HTTP-API-Tokens erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_token = store.get_secret(f"connections.http_api.{existing_secret_ref}.auth_token", default="")
            clean_token = str(auth_token).strip() or existing_token
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "http_api",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu HTTP API.")
            row_value = {
                "base_url": str(base_url).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "health_path": str(health_path).strip() or "/",
                "method": str(method).strip().upper() or "GET",
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.http_api.{ref}.auth_token", clean_token)
            _finalize_connection_save(
                "http_api",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.http_api.{original_ref_clean}.auth_token",
                        f"connections.http_api.{ref}.auth_token",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_http_api_connections().get(ref, {})
            test_result = build_connection_status_row("http_api", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/http-api?saved=1&info={quote_plus(_connection_saved_test_info('HTTP API', lang, success=True))}&http_api_ref={quote_plus(ref)}&http_api_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/http-api?saved=1&info={quote_plus(_connection_saved_test_info('HTTP API', lang, success=False))}&error={quote_plus(test_result['message'])}&http_api_ref={quote_plus(ref)}&http_api_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/http-api?error={quote_plus(str(exc))}&http_api_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/searxng/save")
    async def config_searxng_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        timeout_seconds: int = Form(10),
        language: str = Form("de-CH"),
        safe_search: int = Form(1),
        categories: list[str] = Form([]),
        engines: list[str] = Form([]),
        time_range: str = Form(""),
        max_results: int = Form(5),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("searxng", connection_ref, original_ref)
            existing_row = rows.get(original_ref_clean) if original_ref_clean else rows.get(ref)
            if not isinstance(existing_row, dict):
                existing_row = {}
            row_value = {
                "base_url": resolve_searxng_base_url(str(existing_row.get("base_url", "")).strip()),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "language": str(language).strip() or "de-CH",
                "safe_search": max(0, min(int(safe_search), 2)),
                "categories": [item.strip() for item in categories if item.strip()][:12] or ["general"],
                "engines": [item.strip() for item in engines if item.strip()][:20],
                "time_range": str(time_range).strip().lower(),
                "max_results": max(1, min(int(max_results), 20)),
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            _finalize_connection_save(
                "searxng",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            test_row = _read_searxng_connections().get(ref, {})
            test_result = build_connection_status_row("searxng", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/searxng?saved=1&info={quote_plus(_connection_saved_test_info('SearXNG', lang, success=True))}"
                    f"&searxng_ref={quote_plus(ref)}&searxng_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/searxng?saved=1&info={quote_plus(_connection_saved_test_info('SearXNG', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&searxng_ref={quote_plus(ref)}&searxng_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/searxng?error={quote_plus(str(exc))}&searxng_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/rss/save")
    async def config_rss_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        feed_url: str = Form(""),
        group_name: str = Form(""),
        timeout_seconds: int = Form(10),
        poll_interval_minutes: int = Form(60),
    ) -> RedirectResponse:
        try:
            del poll_interval_minutes
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, create_new_mode = _prepare_connection_save("rss", connection_ref, original_ref)
            clean_feed_url = _normalize_rss_feed_url_for_dedupe(feed_url)
            if not clean_feed_url:
                raise ValueError("Feed-URL fehlt.")
            for existing_ref, row in rows.items():
                if existing_ref == original_ref_clean:
                    continue
                existing_feed_url = _normalize_rss_feed_url_for_dedupe(str(row.get("feed_url", "")).strip())
                if existing_feed_url and existing_feed_url == clean_feed_url:
                    raise ValueError(f"RSS-Feed-URL ist bereits im Profil '{existing_ref}' erfasst.")
            row_value = {
                "feed_url": clean_feed_url,
                "group_name": str(group_name or "").strip()[:64],
                "timeout_seconds": max(5, int(timeout_seconds)),
                "poll_interval_minutes": _read_rss_poll_interval_minutes(raw),
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            _finalize_connection_save(
                "rss",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            test_row = _read_rss_connections().get(ref, {})
            test_result = build_connection_status_row("rss", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                target_url = (
                    f"/config/connections/rss?saved=1&info={quote_plus(_connection_saved_test_info('RSS', lang, success=True))}"
                    f"&rss_test_status=ok&rss_ref={quote_plus(ref)}&mode=edit"
                )
                return _redirect_with_return_to(target_url, request, fallback="/config")
            target_url = (
                f"/config/connections/rss?saved=1&info={quote_plus(_connection_saved_test_info('RSS', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&rss_test_status=error&rss_ref={quote_plus(ref)}&mode=edit"
            )
            return _redirect_with_return_to(target_url, request, fallback="/config")
        except (OSError, ValueError) as exc:
            original_ref_clean = _sanitize_connection_name(original_ref)
            target_url = f"/config/connections/rss?error={quote_plus(str(exc))}"
            if original_ref_clean:
                target_url += f"&rss_ref={quote_plus(original_ref_clean)}"
            else:
                target_url += "&create_new=1"
            return _redirect_with_return_to(target_url, request, fallback="/config")

    @app.get("/config/connections/rss/export-opml")
    async def config_rss_connections_export_opml() -> Response:
        rows = _read_rss_connections()
        xml_payload = build_opml_document(
            [{"ref": ref, **row} for ref, row in rows.items()],
            title="ARIA RSS Export",
        )
        return Response(
            content=xml_payload,
            media_type="application/xml",
            headers={"Content-Disposition": 'attachment; filename="aria-rss-feeds.opml"'},
        )

    @app.post("/config/connections/rss/import-opml")
    async def config_rss_connections_import_opml(
        request: Request,
        opml_file: UploadFile = File(...),
        poll_interval_minutes: int = Form(60),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(
                "/config/connections/rss?create_new=1&error=csrf_failed",
                request,
                fallback="/config",
            )
        try:
            del poll_interval_minutes
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw = _read_raw_config()
            raw.setdefault("connections", {})
            if not isinstance(raw["connections"], dict):
                raw["connections"] = {}
            raw["connections"].setdefault("rss", {})
            if not isinstance(raw["connections"]["rss"], dict):
                raw["connections"]["rss"] = {}
            rows = raw["connections"]["rss"]
            existing_urls = {
                _normalize_rss_feed_url_for_dedupe(str(value.get("feed_url", "")).strip())
                for value in rows.values()
                if isinstance(value, dict) and _normalize_rss_feed_url_for_dedupe(str(value.get("feed_url", "")).strip())
            }
            payload = (await opml_file.read()).decode("utf-8", errors="replace")
            entries = parse_opml_feeds(payload)
            imported_count = 0
            default_poll_interval = _read_rss_poll_interval_minutes(raw)
            for entry in entries:
                normalized_feed_url = _normalize_rss_feed_url_for_dedupe(entry.feed_url)
                if not normalized_feed_url or normalized_feed_url in existing_urls:
                    continue
                ref = _next_rss_import_ref(rows, entry.title, normalized_feed_url)
                group_name = str(entry.tags[0]).strip()[:64] if entry.tags else ""
                rows[ref] = {
                    "feed_url": normalized_feed_url,
                    "group_name": group_name,
                    "timeout_seconds": 10,
                    "poll_interval_minutes": default_poll_interval,
                    "title": entry.title,
                    "description": "",
                    "aliases": [],
                    "tags": list(entry.tags[1:] if group_name else entry.tags),
                }
                existing_urls.add(normalized_feed_url)
                imported_count += 1
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                "/config/connections/rss?saved=1&mode=edit"
                f"&info={quote_plus(_msg(lang, f'OPML-Import abgeschlossen · {imported_count} Feeds importiert', f'OPML import completed · {imported_count} feeds imported'))}",
                request,
                fallback="/config",
            )
        except Exception as exc:  # noqa: BLE001
            return _redirect_with_return_to(
                f"/config/connections/rss?create_new=1&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/rss/ping-now")
    async def config_rss_connections_ping_now(
        request: Request,
        rss_ref: str = Form(...),
    ) -> RedirectResponse:
        ref = _sanitize_connection_name(rss_ref)
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not ref:
            return _redirect_with_return_to(
                "/config/connections/rss?error=Connection-Ref+ist+ung%C3%BCltig.",
                request,
                fallback="/config",
            )
        try:
            test_row = _read_rss_connections().get(ref)
            if not isinstance(test_row, dict):
                raise ValueError("Connection-Profil nicht gefunden.")
            test_result = build_connection_status_row("rss", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    "/config/connections/rss?mode=edit"
                    f"&rss_ref={quote_plus(ref)}"
                    f"&rss_test_status=ok"
                    f"&info={quote_plus(str(test_result['message']))}",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                "/config/connections/rss?mode=edit"
                f"&rss_ref={quote_plus(ref)}"
                f"&rss_test_status=error"
                f"&error={quote_plus(str(test_result['message']))}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/connections/rss?mode=edit&rss_ref={quote_plus(ref)}&rss_test_status=error&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/mqtt/save")
    async def config_mqtt_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        port: int = Form(1883),
        user: str = Form(""),
        password: str = Form(""),
        topic: str = Form(""),
        timeout_seconds: int = Form(10),
        use_tls: str = Form("0"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("mqtt", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für MQTT-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.mqtt.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("MQTT-Passwort fehlt.")
            row_value = {
                "host": str(host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "topic": str(topic).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "use_tls": str(use_tls).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.mqtt.{ref}.password", clean_password)
            _finalize_connection_save(
                "mqtt",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.mqtt.{original_ref_clean}.password",
                        f"connections.mqtt.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_mqtt_connections().get(ref, {})
            test_result = build_connection_status_row("mqtt", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/mqtt?saved=1&info={quote_plus(_connection_saved_test_info('MQTT', lang, success=True))}&mqtt_ref={quote_plus(ref)}&mqtt_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/mqtt?saved=1&info={quote_plus(_connection_saved_test_info('MQTT', lang, success=False))}&error={quote_plus(test_result['message'])}&mqtt_ref={quote_plus(ref)}&mqtt_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/mqtt?error={quote_plus(str(exc))}&mqtt_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/keygen")
    async def config_connections_keygen(
        request: Request,
        connection_ref: str = Form(...),
        overwrite: str = Form("0"),
    ) -> RedirectResponse:
        try:
            ref = _sanitize_connection_name(connection_ref)
            if not ref:
                raise ValueError("Connection-Ref ist ungültig.")
            overwrite_enabled = str(overwrite).strip().lower() in {"1", "true", "on", "yes"}
            existing = _ssh_keys_dir() / f"{ref}_ed25519"
            if (existing.exists() or existing.with_suffix(".pub").exists()) and not overwrite_enabled:
                raise ValueError("Key existiert bereits. 'Overwrite' aktivieren zum Ersetzen.")
            key_path = _ensure_ssh_keypair(ref, overwrite=overwrite_enabled)

            raw = _read_raw_config()
            raw.setdefault("connections", {})
            if not isinstance(raw["connections"], dict):
                raw["connections"] = {}
            raw["connections"].setdefault("ssh", {})
            if not isinstance(raw["connections"]["ssh"], dict):
                raw["connections"]["ssh"] = {}
            raw["connections"]["ssh"].setdefault(ref, {})
            if not isinstance(raw["connections"]["ssh"][ref], dict):
                raw["connections"]["ssh"][ref] = {}
            raw["connections"]["ssh"][ref]["key_path"] = str(key_path)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(_msg(str(getattr(request.state, 'lang', 'de') or 'de'), 'SSH-Key erstellt', 'SSH key created'))}&ref={quote_plus(ref)}",
                request,
                fallback="/config",
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(detail)}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(_friendly_ssh_setup_error(lang, exc))}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/key-exchange")
    async def config_connections_key_exchange(
        request: Request,
        connection_ref: str = Form(...),
        login_user: str = Form(""),
        login_password: str = Form(""),
    ) -> RedirectResponse:
        try:
            ref = _sanitize_connection_name(connection_ref)
            if not ref:
                raise ValueError("Connection-Ref ist ungültig.")
            if not login_password.strip():
                raise ValueError("Passwort fehlt.")

            rows = _read_ssh_connections()
            row = rows.get(ref)
            if not row:
                raise ValueError("Connection-Profil nicht gefunden.")
            host = str(row.get("host", "")).strip()
            port = int(row.get("port", 22) or 22)
            profile_user = str(row.get("user", "")).strip()
            user, key_path = _perform_ssh_key_exchange(
                ref=ref,
                host=host,
                port=port,
                profile_user=profile_user,
                login_user=login_user,
                login_password=login_password,
            )

            raw = _read_raw_config()
            raw.setdefault("connections", {})
            if not isinstance(raw["connections"], dict):
                raw["connections"] = {}
            raw["connections"].setdefault("ssh", {})
            if not isinstance(raw["connections"]["ssh"], dict):
                raw["connections"]["ssh"] = {}
            raw["connections"]["ssh"].setdefault(ref, {})
            if not isinstance(raw["connections"]["ssh"][ref], dict):
                raw["connections"]["ssh"][ref] = {}
            raw["connections"]["ssh"][ref]["user"] = user
            raw["connections"]["ssh"][ref]["key_path"] = str(key_path)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(_msg(str(getattr(request.state, 'lang', 'de') or 'de'), 'Key-Exchange erfolgreich', 'Key exchange successful'))}&ref={quote_plus(ref)}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(_friendly_ssh_setup_error(lang, exc))}",
                request,
                fallback="/config",
            )

    @app.post("/config/connections/test")
    async def config_connections_test(
        request: Request,
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            ref = _sanitize_connection_name(connection_ref)
            if not ref:
                raise ValueError("Connection-Ref ist ungültig.")
            rows = _read_ssh_connections()
            row = rows.get(ref)
            if not row:
                raise ValueError("Connection-Profil nicht gefunden.")
            test_result = build_connection_status_row("ssh", ref, row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] != "ok":
                raise ValueError(test_result["message"])
            info = test_result["message"]
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(info)}&ref={quote_plus(ref)}&test_status=ok",
                request,
                fallback="/config",
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(str(exc))}&ref={quote_plus(connection_ref)}&test_status=error",
                request,
                fallback="/config",
            )

    @app.get("/config/users", response_class=HTMLResponse)
    async def config_users_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        manager = _get_auth_manager()
        users: list[dict[str, Any]] = []
        if manager:
            try:
                users = manager.store.list_users()
            except Exception as exc:
                error = error or str(exc)
        else:
            error = error or "Security Store nicht aktiv."
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_users.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": info,
                "users": users,
                "debug_mode": bool(settings.ui.debug_mode),
                "security_cfg": settings.security,
                "security_session_timeout_minutes": max(
                    5,
                    int(getattr(settings.security, "session_max_age_seconds", 60 * 60 * 12) or 0) // 60,
                ),
                "security_session_timeout_display": _format_session_timeout_label(
                    max(5, int(getattr(settings.security, "session_max_age_seconds", 60 * 60 * 12) or 0) // 60),
                    lang=str(getattr(request.state, "lang", "de") or "de"),
                ),
                "return_to": return_to,
            },
        )

    @app.post("/config/users/debug-save")
    async def config_users_debug_save(request: Request, debug_mode: str = Form("0"), return_to: str = Form("")) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            active = str(debug_mode).strip().lower() in {"1", "true", "on", "yes"}
            raw = _read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["debug_mode"] = active
            _write_raw_config(raw)
            _reload_runtime()
            info = (
                "Admin-Modus aktiviert. Erweiterte Systembereiche sind jetzt sichtbar."
                if active and lang.startswith("de")
                else "Admin mode enabled. Advanced system areas are now visible."
                if active
                else "Admin-Modus deaktiviert. Erweiterte Systembereiche sind jetzt ausgeblendet."
                if lang.startswith("de")
                else "Admin mode disabled. Advanced system areas are now hidden."
            )
            return _redirect_with_return_to(
                f"/config/users?saved=1&info={quote_plus(info)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/users?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    async def _save_user_security_settings(
        request: Request,
        bootstrap_locked: str,
        session_timeout_minutes: int,
        return_to: str = "",
    ) -> RedirectResponse:
        try:
            active = str(bootstrap_locked).strip().lower() in {"1", "true", "on", "yes"}
            timeout_minutes = max(5, min(int(session_timeout_minutes or 0), 60 * 24 * 30))
            raw = _read_raw_config()
            raw.setdefault("security", {})
            if not isinstance(raw["security"], dict):
                raw["security"] = {}
            raw["security"]["bootstrap_locked"] = active
            raw["security"]["session_max_age_seconds"] = int(timeout_minutes * 60)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/users?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error_msg = _friendly_route_error(
                lang,
                exc,
                "Benutzer- und Login-Einstellungen konnten nicht gespeichert werden.",
                "Could not save user and login settings.",
            )
            return _redirect_with_return_to(
                f"/config/users?error={quote_plus(error_msg)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/users/security-save")
    async def config_users_security_save(
        request: Request,
        bootstrap_locked: str = Form("0"),
        session_timeout_minutes: int = Form(60 * 60 * 12 // 60),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        return await _save_user_security_settings(request, bootstrap_locked, session_timeout_minutes, return_to=return_to)

    @app.post("/config/users/create")
    async def config_users_create(
        request: Request,
        create_username: str = Form(...),
        create_password: str = Form(...),
        create_role: str = Form("user"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        manager = _get_auth_manager()
        if not manager:
            return _redirect_with_return_to("/config/users?error=Security+Store+nicht+aktiv", request, fallback="/config", return_to=return_to)
        try:
            clean_username = _sanitize_username(create_username)
            clean_role = _sanitize_role(create_role)
            if not clean_username:
                raise ValueError("Username darf nicht leer sein.")
            if manager.store.get_user(clean_username):
                raise ValueError("User existiert bereits.")
            manager.upsert_user(clean_username, create_password, role=clean_role)
            return _redirect_with_return_to("/config/users?saved=1&info=User+erstellt", request, fallback="/config", return_to=return_to)
        except ValueError as exc:
            return _redirect_with_return_to(
                f"/config/users?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/users/update")
    async def config_users_update(
        request: Request,
        username_value: str = Form(...),
        new_username_value: str = Form(""),
        role_value: str = Form("user"),
        active_value: str = Form("0"),
        password_value: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        manager = _get_auth_manager()
        if not manager:
            return _redirect_with_return_to("/config/users?error=Security+Store+nicht+aktiv", request, fallback="/config", return_to=return_to)
        try:
            auth = _get_auth_session_from_request(request) or {}
            current_username = _sanitize_username(auth.get("username"))
            old_username = _sanitize_username(username_value)
            clean_username = _sanitize_username(new_username_value) or old_username
            clean_role = _sanitize_role(role_value)
            target_active = str(active_value).strip().lower() in {"1", "true", "on", "yes"}
            new_password = str(password_value).strip()

            if not old_username or not clean_username:
                raise ValueError("Username darf nicht leer sein.")

            before = manager.store.get_user(old_username)
            if not before:
                raise ValueError("User nicht gefunden.")
            if clean_username != old_username and manager.store.get_user(clean_username):
                raise ValueError("Ziel-Username existiert bereits.")

            before_role = _sanitize_role(before.get("role"))
            before_active = bool(before.get("active"))
            if old_username == current_username:
                if clean_role != "admin" or not target_active:
                    raise ValueError("Aktueller Admin darf sich nicht selbst deaktivieren oder degradieren.")

            users = manager.store.list_users()
            active_admins = _active_admin_count(users)
            removing_last_admin = (
                before_role == "admin"
                and before_active
                and active_admins <= 1
                and (clean_role != "admin" or not target_active)
            )
            if removing_last_admin:
                raise ValueError("Mindestens ein aktiver Admin muss erhalten bleiben.")

            if clean_username != old_username:
                manager.store.rename_user(old_username=old_username, new_username=clean_username)

            if new_password:
                manager.upsert_user(clean_username, new_password, role=clean_role)
            else:
                manager.store.set_user_role(clean_username, clean_role)

            manager.store.set_user_active(clean_username, target_active)
            response = _redirect_with_return_to("/config/users?saved=1&info=User+aktualisiert", request, fallback="/config", return_to=return_to)
            if old_username == current_username:
                secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
                response.set_cookie(
                    key=_cookie_name_for_request(request, "auth", AUTH_COOKIE),
                    value=_encode_auth_session(clean_username, clean_role, scope=_cookie_scope_for_request(request)),
                    max_age=get_auth_session_max_age_seconds(),
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=True,
                )
                response.set_cookie(
                    key=_cookie_name_for_request(request, "username", USERNAME_COOKIE),
                    value=clean_username,
                    max_age=60 * 60 * 24 * 365,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=False,
                )
                response.set_cookie(
                    key=_cookie_name_for_request(request, "memory_collection", MEMORY_COLLECTION_COOKIE),
                    value=_default_memory_collection_for_user(clean_username),
                    max_age=60 * 60 * 24 * 365,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=False,
                )
            return response
        except ValueError as exc:
            return _redirect_with_return_to(
                f"/config/users?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/prompts", response_class=HTMLResponse)
    async def config_prompts_page(
        request: Request,
        file: str | None = None,
        saved: int = 0,
        error: str = "",
    ) -> HTMLResponse:
        username = _get_username_from_request(request)
        rows = _list_prompt_files()
        selected = file or (rows[0]["path"] if rows else "")
        content = ""

        if selected:
            try:
                selected_path = _resolve_prompt_file(selected)
                if not selected_path.exists():
                    raise ValueError("Datei existiert nicht.")
                content = selected_path.read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                lang = str(getattr(request.state, "lang", "de") or "de")
                error = _friendly_route_error(lang, exc, "Prompt-Datei konnte nicht geladen werden.", "Could not load prompt file.")
                content = ""
        selected_row = next((row for row in rows if row.get("path") == selected), None)
        return_to = _set_logical_back_url(request, fallback="/config")

        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_prompts.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "rows": rows,
                "selected_file": selected,
                "selected_row": selected_row,
                "file_content": content,
                "saved": bool(saved),
                "error_message": error,
                "return_to": return_to,
            },
        )

    @app.post("/config/prompts/save")
    async def config_prompts_save(
        request: Request,
        file: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            target = _resolve_prompt_file(file)
            if not target.exists():
                raise ValueError("Datei existiert nicht.")
            _saved, reload_message = _save_text_file_and_maybe_reload(target, content)
            target_url = f"/config/prompts?file={quote_plus(file)}&saved=1"
            if reload_message:
                target_url += f"&error={quote_plus(reload_message)}"
            request.state.logical_back_url = _sanitize_return_to(return_to) or "/config"
            return _redirect_with_return_to(target_url, request, fallback="/config")
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_route_error(lang, exc, "Prompt-Datei konnte nicht gespeichert werden.", "Could not save prompt file.")
            request.state.logical_back_url = _sanitize_return_to(return_to) or "/config"
            return _redirect_with_return_to(
                f"/config/prompts?file={quote_plus(file)}&error={quote_plus(error)}",
                request,
                fallback="/config",
            )

    @app.get("/config/routing", response_class=HTMLResponse)
    async def config_routing_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        scope: str = "default",
        routing_query: str = "",
        routing_kind: str = "auto",
    ) -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        supported_languages = list(getattr(request.state, "supported_languages", []) or [])
        selected_scope = str(scope or "default").strip().lower() or "default"
        valid_scopes = {"default", *supported_languages}
        if selected_scope not in valid_scopes:
            selected_scope = "default"

        routing = settings.routing.for_language(None if selected_scope == "default" else selected_scope)
        routing_index_status = await build_connection_routing_index_status(settings)
        routing_qdrant_meta = {
            "enabled": bool(getattr(settings.routing, "qdrant_connection_routing_enabled", False)),
            "score_threshold": float(getattr(settings.routing, "qdrant_score_threshold", 0.72) or 0.0),
            "candidate_limit": int(getattr(settings.routing, "qdrant_candidate_limit", 5) or 5),
            "ask_on_low_confidence": bool(getattr(settings.routing, "qdrant_ask_on_low_confidence", True)),
        }
        routing_test_result = None
        if str(routing_query or "").strip():
            routing_test_result = await test_connection_routing_query(
                settings,
                routing_query,
                preferred_kind=routing_kind,
            )
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_routing.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": info,
                "routing_index_status": routing_index_status,
                "routing_qdrant_meta": routing_qdrant_meta,
                "routing_test_result": routing_test_result,
                "routing_test_query": str(routing_query or "").strip(),
                "routing_test_kind": str(routing_kind or "auto").strip().lower() or "auto",
                "routing_test_kind_options": ["auto", "ssh", "sftp", "rss", "discord", "http_api"],
                "scope_options": ["default", *supported_languages],
                "selected_scope": selected_scope,
                "store_keywords_text": "\n".join(routing.memory_store_keywords),
                "recall_keywords_text": "\n".join(routing.memory_recall_keywords),
                "forget_keywords_text": "\n".join(routing.memory_forget_keywords),
                "store_prefixes_text": "\n".join(routing.memory_store_prefixes),
                "recall_cleanup_text": "\n".join(routing.memory_recall_cleanup_keywords),
                "return_to": return_to,
            },
        )

    @app.get("/config/routing-index/status")
    async def config_routing_index_status(request: Request) -> JSONResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return JSONResponse({"status": "error", "message": "Admin access required."}, status_code=403)
        return JSONResponse(await build_connection_routing_index_status(settings))

    @app.get("/config/routing-index/test")
    async def config_routing_index_test(
        request: Request,
        query: str = "",
        preferred_kind: str = "auto",
    ) -> JSONResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return JSONResponse({"status": "error", "message": "Admin access required."}, status_code=403)
        return JSONResponse(
            await test_connection_routing_query(
                settings,
                query,
                preferred_kind=preferred_kind,
            )
        )

    @app.post("/config/routing-index/rebuild")
    async def config_routing_index_rebuild(
        request: Request,
        scope: str = Form("default"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return _redirect_with_return_to(
                "/config/routing?error=Admin+access+required.",
                request,
                fallback="/config",
                return_to=return_to,
            )
        selected_scope = str(scope or "default").strip().lower() or "default"
        try:
            result = await rebuild_connection_routing_index(settings)
        except Exception as exc:
            return _redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        message = str(result.get("message", "") or "").strip() or "Routing index rebuild finished."
        target_param = "info" if str(result.get("status", "") or "").lower() != "error" else "error"
        return _redirect_with_return_to(
            f"/config/routing?scope={quote_plus(selected_scope)}&{target_param}={quote_plus(message)}",
            request,
            fallback="/config",
            return_to=return_to,
        )

    @app.post("/config/routing/qdrant/save")
    async def config_routing_qdrant_save(
        request: Request,
        scope: str = Form("default"),
        qdrant_connection_routing_enabled: str = Form("0"),
        qdrant_score_threshold: str = Form("0.72"),
        qdrant_candidate_limit: str = Form("5"),
        qdrant_ask_on_low_confidence: str = Form("0"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = _get_auth_session_from_request(request) or {}
        selected_scope = str(scope or "default").strip().lower() or "default"
        if _sanitize_role(auth.get("role")) != "admin":
            return _redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&error=Admin+access+required.",
                request,
                fallback="/config",
                return_to=return_to,
            )
        try:
            threshold = float(str(qdrant_score_threshold or "0.72").strip().replace(",", "."))
            if threshold < 0.0 or threshold > 1.0:
                raise ValueError("Threshold muss zwischen 0.00 und 1.00 liegen.")
            candidate_limit = int(str(qdrant_candidate_limit or "5").strip())
            if candidate_limit < 1 or candidate_limit > 20:
                raise ValueError("Limit muss zwischen 1 und 20 liegen.")

            raw = _read_raw_config()
            raw.setdefault("routing", {})
            if not isinstance(raw["routing"], dict):
                raw["routing"] = {}
            routing_section = raw["routing"]
            routing_section["qdrant_connection_routing_enabled"] = str(qdrant_connection_routing_enabled or "") == "1"
            routing_section["qdrant_score_threshold"] = round(threshold, 4)
            routing_section["qdrant_candidate_limit"] = candidate_limit
            routing_section["qdrant_ask_on_low_confidence"] = str(qdrant_ask_on_low_confidence or "") == "1"
            _write_raw_config(raw)
            _reload_runtime()
            info = "Live-Qdrant-Routing gespeichert."
            return _redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&info={quote_plus(info)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/routing/save")
    async def config_routing_save(
        request: Request,
        scope: str = Form("default"),
        memory_store_keywords: str = Form(""),
        memory_recall_keywords: str = Form(""),
        memory_forget_keywords: str = Form(""),
        memory_store_prefixes: str = Form(""),
        memory_recall_cleanup_keywords: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            store_keywords = _parse_lines(memory_store_keywords)
            recall_keywords = _parse_lines(memory_recall_keywords)
            forget_keywords = _parse_lines(memory_forget_keywords)
            store_prefixes = _parse_lines(memory_store_prefixes)
            recall_cleanup = _parse_lines(memory_recall_cleanup_keywords)

            if not store_keywords:
                raise ValueError("memory_store_keywords darf nicht leer sein.")
            if not recall_keywords:
                raise ValueError("memory_recall_keywords darf nicht leer sein.")
            if not forget_keywords:
                raise ValueError("memory_forget_keywords darf nicht leer sein.")
            if not store_prefixes:
                raise ValueError("memory_store_prefixes darf nicht leer sein.")
            if not recall_cleanup:
                raise ValueError("memory_recall_cleanup_keywords darf nicht leer sein.")

            supported_languages = list(getattr(request.state, "supported_languages", []) or [])
            selected_scope = str(scope or "default").strip().lower() or "default"
            valid_scopes = {"default", *supported_languages}
            if selected_scope not in valid_scopes:
                raise ValueError("Ungültiger Routing-Scope.")

            raw = _read_raw_config()
            raw.setdefault("routing", {})
            if not isinstance(raw["routing"], dict):
                raw["routing"] = {}
            routing_section = raw["routing"]
            payload = {
                "memory_store_keywords": store_keywords,
                "memory_recall_keywords": recall_keywords,
                "memory_forget_keywords": forget_keywords,
                "memory_store_prefixes": store_prefixes,
                "memory_recall_cleanup_keywords": recall_cleanup,
            }

            if selected_scope == "default":
                routing_section["default"] = payload
                # Keep flat keys in sync as transitional compatibility.
                routing_section["memory_store_keywords"] = store_keywords
                routing_section["memory_recall_keywords"] = recall_keywords
                routing_section["memory_forget_keywords"] = forget_keywords
                routing_section["memory_store_prefixes"] = store_prefixes
                routing_section["memory_recall_cleanup_keywords"] = recall_cleanup
            else:
                routing_section.setdefault("languages", {})
                if not isinstance(routing_section["languages"], dict):
                    routing_section["languages"] = {}
                routing_section["languages"][selected_scope] = payload
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                f"/config/routing?saved=1&scope={quote_plus(selected_scope)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/routing?scope={quote_plus(str(scope or 'default'))}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/skill-routing", response_class=HTMLResponse)
    async def config_skill_routing_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        manifests, load_errors = _load_custom_skill_manifests()
        index = _refresh_skill_trigger_index()
        rows: list[dict[str, Any]] = []
        for row in manifests:
            skill_id = str(row.get("id", "")).strip()
            rows.append(
                {
                    "id": skill_id,
                    "name": str(row.get("name", skill_id)).strip() or skill_id,
                    "router_keywords_text": ", ".join(row.get("router_keywords", [])) if isinstance(row.get("router_keywords", []), list) else "",
                    "json_path": str(_custom_skill_file(skill_id).relative_to(BASE_DIR)),
                }
            )
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_skill_routing.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": _format_skill_routing_info(lang, info),
                "rows": rows,
                "index": index,
                "load_errors": load_errors,
                "return_to": return_to,
            },
        )

    @app.post("/config/skill-routing/save")
    async def config_skill_routing_save(
        request: Request,
        skill_id: str = Form(...),
        router_keywords: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            clean_id = _sanitize_skill_id(skill_id)
            if not clean_id:
                raise ValueError("Ungültige Skill-ID.")
            target = _custom_skill_file(clean_id)
            if not target.exists():
                raise ValueError("Skill-Datei nicht gefunden.")
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Skill-Datei ist kein JSON-Objekt.")
            keywords = [item.strip() for item in str(router_keywords).split(",") if item.strip()]
            raw["router_keywords"] = keywords
            clean = _save_custom_skill_manifest(raw)
            return _redirect_with_return_to(
                f"/config/skill-routing?saved=1&info={quote_plus(clean.get('id', clean_id))}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/skill-routing/suggest")
    async def config_skill_routing_suggest(
        request: Request,
        skill_id: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            clean_id = _sanitize_skill_id(skill_id)
            if not clean_id:
                raise ValueError("Ungültige Skill-ID.")
            target = _custom_skill_file(clean_id)
            if not target.exists():
                raise ValueError("Skill-Datei nicht gefunden.")
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Skill-Datei ist kein JSON-Objekt.")
            lang = str(getattr(request.state, "lang", "de") or "de")
            keywords = await _suggest_skill_keywords_with_llm(raw, language=lang)
            if not keywords:
                raise ValueError("Keine Trigger-Keywords erzeugt.")
            raw["router_keywords"] = keywords
            _save_custom_skill_manifest(raw)
            info = f"suggest:{clean_id}:{len(keywords)}"
            return _redirect_with_return_to(
                f"/config/skill-routing?saved=1&info={quote_plus(info)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/skill-routing/suggest-all")
    async def config_skill_routing_suggest_all(request: Request, return_to: str = Form("")) -> RedirectResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            manifests, _ = _load_custom_skill_manifests()
            lang = str(getattr(request.state, "lang", "de") or "de")
            updated = 0
            total_keywords = 0
            for manifest in manifests:
                skill_id = _sanitize_skill_id(manifest.get("id", ""))
                if not skill_id:
                    continue
                keywords = await _suggest_skill_keywords_with_llm(manifest, language=lang)
                if not keywords:
                    continue
                manifest["router_keywords"] = keywords
                _save_custom_skill_manifest(manifest)
                updated += 1
                total_keywords += len(keywords)
            info = f"suggest-all:{updated}:{total_keywords}"
            return _redirect_with_return_to(
                f"/config/skill-routing?saved=1&info={quote_plus(info)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/skill-routing/rebuild")
    async def config_skill_routing_rebuild(request: Request, return_to: str = Form("")) -> RedirectResponse:
        auth = _get_auth_session_from_request(request) or {}
        if _sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            _refresh_skill_trigger_index()
            return _redirect_with_return_to(
                "/config/skill-routing?saved=1&info=rebuild",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except OSError as exc:
            return _redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/llm", response_class=HTMLResponse)
    async def config_llm_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        test_status: str = "",
    ) -> HTMLResponse:
        _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        raw = _read_raw_config()
        llm_profiles = _get_profiles(raw, "llm")
        if not llm_profiles:
            llm_profiles = {
                "default": {
                    "model": settings.llm.model,
                    "api_base": settings.llm.api_base or "",
                    "api_key": settings.llm.api_key or "",
                    "temperature": settings.llm.temperature,
                    "max_tokens": settings.llm.max_tokens,
                    "timeout_seconds": settings.llm.timeout_seconds,
                }
            }
        active_llm_profile = _get_active_profile_name(raw, "llm") or "default"
        active_llm_meta = _active_profile_runtime_meta(raw, "llm")
        providers = [
            {
                "key": key,
                "label": data["label"],
                "default_model": data["default_model"],
                "default_api_base": data["default_api_base"],
            }
            for key, data in LLM_PROVIDER_PRESETS.items()
        ]
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_llm.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": _format_config_info_message(str(getattr(request.state, "lang", "de") or "de"), info),
                "test_status": str(test_status or "").strip().lower(),
                "llm": settings.llm,
                "providers": providers,
                "llm_profiles": sorted(llm_profiles.keys()),
                "active_llm_profile": active_llm_profile,
                "active_llm_meta": active_llm_meta,
            },
        )

    @app.post("/config/llm/profile/load")
    async def config_llm_profile_load(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        try:
            raw = _read_raw_config()
            name = _sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            llm_profiles = _get_profiles(raw, "llm")
            profile = llm_profiles.get(name)
            if not profile:
                raise ValueError("LLM-Profil nicht gefunden.")

            raw.setdefault("llm", {})
            raw["llm"]["model"] = str(profile.get("model", "")).strip()
            raw["llm"]["api_base"] = str(profile.get("api_base", "")).strip() or None
            store = _get_secure_store(raw)
            profile_api_key = str(profile.get("api_key", "")).strip()
            if store:
                profile_api_key = store.get_secret(f"profiles.llm.{name}.api_key", default=profile_api_key)
            raw["llm"]["api_key"] = profile_api_key
            raw["llm"]["temperature"] = float(profile.get("temperature", 0.4))
            raw["llm"]["max_tokens"] = int(profile.get("max_tokens", 4096))
            raw["llm"]["timeout_seconds"] = int(profile.get("timeout_seconds", 60))
            if store and profile_api_key:
                store.set_secret("llm.api_key", profile_api_key)
                raw["llm"]["api_key"] = ""
            _set_active_profile(raw, "llm", name)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/profile/save")
    async def config_llm_profile_save(
        request: Request,
        profile_name: str = Form(...),
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        temperature: float = Form(...),
        max_tokens: int = Form(...),
        timeout_seconds: int = Form(...),
    ) -> RedirectResponse:
        try:
            name = _sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")

            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Modell statt Placeholder eingeben.")
            if not _is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Modelle erforderlich.")
            if temperature < 0 or temperature > 2:
                raise ValueError("temperature muss zwischen 0 und 2 liegen.")
            if max_tokens <= 0:
                raise ValueError("max_tokens muss > 0 sein.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")

            raw = _read_raw_config()
            raw.setdefault("profiles", {})
            if not isinstance(raw["profiles"], dict):
                raw["profiles"] = {}
            raw["profiles"].setdefault("llm", {})
            if not isinstance(raw["profiles"]["llm"], dict):
                raw["profiles"]["llm"] = {}
            raw["profiles"]["llm"][name] = {
                "model": cleaned_model,
                "api_base": api_base.strip(),
                "api_key": "",
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
                "timeout_seconds": int(timeout_seconds),
            }
            _set_active_profile(raw, "llm", name)
            raw.setdefault("llm", {})
            raw["llm"].update(
                {
                    "model": cleaned_model,
                    "api_base": api_base.strip() or None,
                    "api_key": "",
                    "temperature": float(temperature),
                    "max_tokens": int(max_tokens),
                    "timeout_seconds": int(timeout_seconds),
                }
            )
            store = _get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("llm.api_key", cleaned_api_key)
                store.set_secret(f"profiles.llm.{name}.api_key", cleaned_api_key)
            elif not store:
                raw["profiles"]["llm"][name]["api_key"] = cleaned_api_key
                raw["llm"]["api_key"] = cleaned_api_key
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/profile/delete")
    async def config_llm_profile_delete(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        try:
            raw = _read_raw_config()
            name = _sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            active = _get_active_profile_name(raw, "llm")
            if name == active:
                raise ValueError("Aktives LLM-Profil kann nicht gelöscht werden.")
            llm_profiles = _get_profiles(raw, "llm")
            if name not in llm_profiles:
                raise ValueError("LLM-Profil nicht gefunden.")

            del raw["profiles"]["llm"][name]
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/models")
    async def config_llm_models(api_base: str = Form(...), api_key: str = Form("")) -> JSONResponse:
        try:
            # Accept only http(s) targets for safety.
            parsed = urlparse(api_base.strip())
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("API Base muss mit http:// oder https:// beginnen.")
            models = _load_models_from_api_base(api_base=api_base, api_key=api_key)
            return JSONResponse(content={"models": models})
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.post("/config/embeddings/models")
    async def config_embeddings_models(api_base: str = Form(...), api_key: str = Form("")) -> JSONResponse:
        try:
            parsed = urlparse(api_base.strip())
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("API Base muss mit http:// oder https:// beginnen.")
            models = _load_models_from_api_base(api_base=api_base, api_key=api_key)
            return JSONResponse(content={"models": models})
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.post("/config/llm/save")
    async def config_llm_save(
        request: Request,
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        temperature: float = Form(...),
        max_tokens: int = Form(...),
        timeout_seconds: int = Form(...),
        profile_name: str = Form(""),
    ) -> RedirectResponse:
        try:
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Modell statt Placeholder eingeben.")
            if not _is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Modelle erforderlich.")
            if temperature < 0 or temperature > 2:
                raise ValueError("temperature muss zwischen 0 und 2 liegen.")
            if max_tokens <= 0:
                raise ValueError("max_tokens muss > 0 sein.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")

            raw = _read_raw_config()
            raw.setdefault("llm", {})
            raw["llm"]["model"] = cleaned_model
            raw["llm"]["api_base"] = api_base.strip() or None
            raw["llm"]["api_key"] = ""
            raw["llm"]["temperature"] = float(temperature)
            raw["llm"]["max_tokens"] = int(max_tokens)
            raw["llm"]["timeout_seconds"] = int(timeout_seconds)
            active_name = _get_active_profile_name(raw, "llm")
            requested_name = _sanitize_profile_name(profile_name)
            target_name = requested_name or active_name
            if target_name:
                _set_active_profile(raw, "llm", target_name)
                raw.setdefault("profiles", {})
                raw["profiles"].setdefault("llm", {})
                if isinstance(raw["profiles"]["llm"], dict):
                    raw["profiles"]["llm"][target_name] = {
                        "model": cleaned_model,
                        "api_base": api_base.strip(),
                        "api_key": "",
                        "temperature": float(temperature),
                        "max_tokens": int(max_tokens),
                        "timeout_seconds": int(timeout_seconds),
                    }
            store = _get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("llm.api_key", cleaned_api_key)
                if target_name:
                    store.set_secret(f"profiles.llm.{target_name}.api_key", cleaned_api_key)
            elif not store:
                raw["llm"]["api_key"] = cleaned_api_key
                if target_name and isinstance(raw.get("profiles", {}).get("llm"), dict):
                    raw["profiles"]["llm"][target_name]["api_key"] = cleaned_api_key
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/test")
    async def config_llm_test(request: Request) -> RedirectResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = _read_raw_config()
        active_name = _get_active_profile_name(raw, "llm") or "default"
        result = await probe_llm(settings.llm, usage_meter=getattr(pipeline, "usage_meter", None))
        message = _profile_test_result_message("llm", active_name, result, lang)
        return _redirect_with_return_to(
            _profile_test_redirect_url("/config/llm", ok=str(result.get("status", "")).strip().lower() == "ok", message=message),
            request,
            fallback="/config",
        )

    @app.get("/config/embeddings", response_class=HTMLResponse)
    async def config_embeddings_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        test_status: str = "",
    ) -> HTMLResponse:
        _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        raw = _read_raw_config()
        embedding_profiles = _get_profiles(raw, "embeddings")
        if not embedding_profiles:
            embedding_profiles = {
                "default": {
                    "model": settings.embeddings.model,
                    "api_base": settings.embeddings.api_base or "",
                    "api_key": settings.embeddings.api_key or "",
                    "timeout_seconds": settings.embeddings.timeout_seconds,
                }
            }
        active_embedding_profile = _get_active_profile_name(raw, "embeddings") or "default"
        active_embedding_meta = _active_profile_runtime_meta(raw, "embeddings")
        providers = [
            {
                "key": key,
                "label": data["label"],
                "default_model": data["default_model"],
                "default_api_base": data["default_api_base"],
            }
            for key, data in EMBEDDING_PROVIDER_PRESETS.items()
        ]
        embedding_guard = await _embedding_memory_guard_context(username)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_embeddings.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": _format_config_info_message(str(getattr(request.state, "lang", "de") or "de"), info),
                "test_status": str(test_status or "").strip().lower(),
                "embeddings": settings.embeddings,
                "providers": providers,
                "embedding_profiles": sorted(embedding_profiles.keys()),
                "active_embedding_profile": active_embedding_profile,
                "active_embedding_meta": active_embedding_meta,
                "embedding_guard": embedding_guard,
            },
        )

    @app.post("/config/embeddings/profile/load")
    async def config_embeddings_profile_load(
        request: Request,
        profile_name: str = Form(...),
        confirm_embedding_switch: str = Form(""),
        confirm_embedding_phrase: str = Form(""),
    ) -> RedirectResponse:
        try:
            raw = _read_raw_config()
            name = _sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            profiles = _get_profiles(raw, "embeddings")
            profile = profiles.get(name)
            if not profile:
                raise ValueError("Embedding-Profil nicht gefunden.")
            username = _get_username_from_request(request) or "web"
            fingerprint, resolved_model = await _guard_embedding_switch(
                username=username,
                new_model=str(profile.get("model", "")).strip(),
                new_api_base=str(profile.get("api_base", "")).strip(),
                confirm_switch=confirm_embedding_switch,
                confirm_phrase=confirm_embedding_phrase,
            )

            raw.setdefault("embeddings", {})
            raw["embeddings"]["model"] = str(profile.get("model", "")).strip()
            raw["embeddings"]["api_base"] = str(profile.get("api_base", "")).strip() or None
            store = _get_secure_store(raw)
            profile_api_key = str(profile.get("api_key", "")).strip()
            if store:
                profile_api_key = store.get_secret(f"profiles.embeddings.{name}.api_key", default=profile_api_key)
            raw["embeddings"]["api_key"] = profile_api_key
            raw["embeddings"]["timeout_seconds"] = int(profile.get("timeout_seconds", 60))
            if store and profile_api_key:
                store.set_secret("embeddings.api_key", profile_api_key)
                raw["embeddings"]["api_key"] = ""
            _set_active_profile(raw, "embeddings", name)
            raw.setdefault("memory", {})
            raw["memory"]["embedding_fingerprint"] = fingerprint
            raw["memory"]["embedding_model"] = resolved_model
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/embeddings/profile/save")
    async def config_embeddings_profile_save(
        request: Request,
        profile_name: str = Form(...),
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        timeout_seconds: int = Form(...),
        confirm_embedding_switch: str = Form(""),
        confirm_embedding_phrase: str = Form(""),
    ) -> RedirectResponse:
        try:
            name = _sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Embedding-Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Embedding-Modell statt Placeholder eingeben.")
            if not _is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Embedding-Modelle erforderlich.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")
            username = _get_username_from_request(request) or "web"
            fingerprint, resolved_model = await _guard_embedding_switch(
                username=username,
                new_model=cleaned_model,
                new_api_base=api_base.strip(),
                confirm_switch=confirm_embedding_switch,
                confirm_phrase=confirm_embedding_phrase,
            )

            raw = _read_raw_config()
            raw.setdefault("profiles", {})
            if not isinstance(raw["profiles"], dict):
                raw["profiles"] = {}
            raw["profiles"].setdefault("embeddings", {})
            if not isinstance(raw["profiles"]["embeddings"], dict):
                raw["profiles"]["embeddings"] = {}
            raw["profiles"]["embeddings"][name] = {
                "model": cleaned_model,
                "api_base": api_base.strip(),
                "api_key": "",
                "timeout_seconds": int(timeout_seconds),
            }
            _set_active_profile(raw, "embeddings", name)
            raw.setdefault("embeddings", {})
            raw["embeddings"].update(
                {
                    "model": cleaned_model,
                    "api_base": api_base.strip() or None,
                    "api_key": "",
                    "timeout_seconds": int(timeout_seconds),
                }
            )
            raw.setdefault("memory", {})
            raw["memory"]["embedding_fingerprint"] = fingerprint
            raw["memory"]["embedding_model"] = resolved_model
            store = _get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("embeddings.api_key", cleaned_api_key)
                store.set_secret(f"profiles.embeddings.{name}.api_key", cleaned_api_key)
            elif not store:
                raw["profiles"]["embeddings"][name]["api_key"] = cleaned_api_key
                raw["embeddings"]["api_key"] = cleaned_api_key
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/embeddings/profile/delete")
    async def config_embeddings_profile_delete(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        try:
            raw = _read_raw_config()
            name = _sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            active = _get_active_profile_name(raw, "embeddings")
            if name == active:
                raise ValueError("Aktives Embedding-Profil kann nicht gelöscht werden.")
            profiles = _get_profiles(raw, "embeddings")
            if name not in profiles:
                raise ValueError("Embedding-Profil nicht gefunden.")

            del raw["profiles"]["embeddings"][name]
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/embeddings/save")
    async def config_embeddings_save(
        request: Request,
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        timeout_seconds: int = Form(...),
        profile_name: str = Form(""),
        confirm_embedding_switch: str = Form(""),
        confirm_embedding_phrase: str = Form(""),
    ) -> RedirectResponse:
        try:
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Embedding-Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Embedding-Modell statt Placeholder eingeben.")
            if not _is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Embedding-Modelle erforderlich.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")
            username = _get_username_from_request(request) or "web"
            fingerprint, resolved_model = await _guard_embedding_switch(
                username=username,
                new_model=cleaned_model,
                new_api_base=api_base.strip(),
                confirm_switch=confirm_embedding_switch,
                confirm_phrase=confirm_embedding_phrase,
            )

            raw = _read_raw_config()
            raw.setdefault("embeddings", {})
            raw["embeddings"]["model"] = cleaned_model
            raw["embeddings"]["api_base"] = api_base.strip() or None
            raw["embeddings"]["api_key"] = ""
            raw["embeddings"]["timeout_seconds"] = int(timeout_seconds)
            active_name = _get_active_profile_name(raw, "embeddings")
            requested_name = _sanitize_profile_name(profile_name)
            target_name = requested_name or active_name
            if target_name:
                _set_active_profile(raw, "embeddings", target_name)
                raw.setdefault("profiles", {})
                raw["profiles"].setdefault("embeddings", {})
                if isinstance(raw["profiles"]["embeddings"], dict):
                    raw["profiles"]["embeddings"][target_name] = {
                        "model": cleaned_model,
                        "api_base": api_base.strip(),
                        "api_key": "",
                        "timeout_seconds": int(timeout_seconds),
                    }
            raw.setdefault("memory", {})
            raw["memory"]["embedding_fingerprint"] = fingerprint
            raw["memory"]["embedding_model"] = resolved_model
            store = _get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("embeddings.api_key", cleaned_api_key)
                if target_name:
                    store.set_secret(f"profiles.embeddings.{target_name}.api_key", cleaned_api_key)
            elif not store:
                raw["embeddings"]["api_key"] = cleaned_api_key
                if target_name and isinstance(raw.get("profiles", {}).get("embeddings"), dict):
                    raw["profiles"]["embeddings"][target_name]["api_key"] = cleaned_api_key
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/embeddings/test")
    async def config_embeddings_test(request: Request) -> RedirectResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = _read_raw_config()
        active_name = _get_active_profile_name(raw, "embeddings") or "default"
        result = await probe_embeddings(settings.embeddings, usage_meter=getattr(pipeline, "usage_meter", None))
        message = _profile_test_result_message("embeddings", active_name, result, lang)
        return _redirect_with_return_to(
            _profile_test_redirect_url(
                "/config/embeddings",
                ok=str(result.get("status", "")).strip().lower() == "ok",
                message=message,
            ),
            request,
            fallback="/config",
        )

    @app.get("/config/files", response_class=HTMLResponse)
    async def config_files_page(request: Request, file: str | None = None, saved: int = 0, error: str = "") -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        entries = _list_file_editor_entries()
        rows = _build_editor_entries_from_paths(BASE_DIR, [row["path"] for row in entries], _resolve_file_editor_file)
        entry_map = {row["path"]: row for row in entries}
        for row in rows:
            meta = entry_map.get(row["path"], {})
            row["label"] = meta.get("label") or row["name"]
            row["group"] = meta.get("group") or "misc"
            row["mode"] = meta.get("mode") or "readonly"
        selected = file or (rows[0]["path"] if rows else "")
        content = ""

        if selected:
            try:
                selected_path = _resolve_file_editor_file(selected)
                if not selected_path.exists():
                    raise ValueError("Datei existiert nicht.")
                content = selected_path.read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                error = str(exc)
                content = ""
        selected_row = next((row for row in rows if row.get("path") == selected), None)

        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_files.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "rows": rows,
                "selected_file": selected,
                "selected_row": selected_row,
                "file_content": content,
                "saved": bool(saved),
                "error_message": error,
                "return_to": return_to,
            },
        )

    @app.get("/config/error-interpreter", response_class=HTMLResponse)
    async def config_error_interpreter_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        return_to = _set_logical_back_url(request, fallback="/config")
        username = _get_username_from_request(request)
        content = ""
        category_count = 0
        try:
            content = _read_error_interpreter_raw()
            parsed = yaml.safe_load(content) or {}
            rules = parsed.get("rules", []) if isinstance(parsed, dict) else []
            if isinstance(rules, list):
                category_count = len([row for row in rules if isinstance(row, dict) and str(row.get("id", "")).strip()])
        except (OSError, yaml.YAMLError, ValueError) as exc:
            error = error or str(exc)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="config_error_interpreter.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "file_content": content,
                "file_path": str(ERROR_INTERPRETER_PATH.relative_to(BASE_DIR)),
                "category_count": category_count,
                "return_to": return_to,
            },
        )

    @app.post("/config/error-interpreter/save")
    async def config_error_interpreter_save(
        request: Request,
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            parsed = yaml.safe_load(content) or {}
            if not isinstance(parsed, dict):
                raise ValueError("Die Regeldatei muss ein YAML-Objekt enthalten.")
            rules = parsed.get("rules", [])
            if not isinstance(rules, list):
                raise ValueError("`rules` muss eine Liste sein.")
            for idx, row in enumerate(rules, start=1):
                if not isinstance(row, dict):
                    raise ValueError(f"Regel {idx} ist kein Objekt.")
                if not str(row.get("id", "")).strip():
                    raise ValueError(f"Regel {idx} hat keine ID.")
                patterns = row.get("patterns", [])
                messages = row.get("messages", {})
                if not isinstance(patterns, list):
                    raise ValueError(f"Regel {idx}: `patterns` muss eine Liste sein.")
                if not isinstance(messages, dict):
                    raise ValueError(f"Regel {idx}: `messages` muss ein Objekt sein.")
            ERROR_INTERPRETER_PATH.write_text(content, encoding="utf-8")
            _reload_runtime()
            return _redirect_with_return_to(
                "/config/error-interpreter?saved=1",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return _redirect_with_return_to(
                f"/config/error-interpreter?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/files/save")
    async def config_files_save(
        request: Request,
        file: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            target = _resolve_edit_file(file)
            if not target.exists():
                raise ValueError("Datei existiert nicht.")
            _saved, reload_message = _save_text_file_and_maybe_reload(target, content)
            target_url = f"/config/files?file={quote_plus(file)}&saved=1"
            if reload_message:
                target_url += f"&error={quote_plus(reload_message)}"
            return _redirect_with_return_to(target_url, request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_route_error(lang, exc, "Datei konnte nicht gespeichert werden.", "Could not save file.")
            return _redirect_with_return_to(
                f"/config/files?file={quote_plus(file)}&error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
