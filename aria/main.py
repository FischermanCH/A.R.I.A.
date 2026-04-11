from __future__ import annotations

import copy
import html
import json
import re
import base64
import hmac
import hashlib
import logging
import os
import time
import asyncio
import secrets
import socket
import subprocess
import shlex
import tomllib
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request as URLRequest, urlopen
from uuid import uuid4

import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
try:
    import markdown as markdown_lib
except ModuleNotFoundError:  # pragma: no cover - runtime dependency fallback
    markdown_lib = None

from aria.channels.api import register_api_routes
import aria.web.chat_admin_actions as chat_admin_actions
from aria.web.activities_routes import register_activities_routes
from aria.web.chat_catalog import build_chat_command_catalog
from aria.web.config_routes import ConfigRouteDeps, register_config_routes
from aria.web.memories_routes import register_memories_routes
from aria.web.skills_routes import register_skills_routes
from aria.web.stats_routes import register_stats_routes
from aria.core.access import (
    can_access_advanced_config,
    can_access_settings,
    can_access_users,
    is_advanced_config_path,
    is_admin_only_path,
)
from aria.core.auth import AuthManager
from aria.core.chat_history import FileChatHistoryStore
from aria.core.capability_context import CapabilityContextStore
from aria.core.capability_catalog import capability_badge
from aria.core.connection_admin import (
    CONNECTION_ADMIN_SPECS,
    create_connection_profile,
    delete_connection_profile,
    friendly_connection_admin_error_text,
    list_connection_refs,
    resolve_connection_target,
    sanitize_connection_ref,
    update_connection_profile,
)
from aria.core.connection_catalog import (
    sanitize_connection_payload,
)
from aria.core.config import (
    Settings,
    get_master_key,
    get_or_create_runtime_secret,
    load_settings,
    normalize_ui_background,
    normalize_ui_theme,
)
from aria.core.config_backup import build_config_backup_payload
from aria.core.config_backup import summarize_config_backup_payload
from aria.core.custom_skills import (
    SKILL_TRIGGER_INDEX_FILE,
    _collect_skill_categories,
    _custom_skill_file,
    _load_custom_skill_manifests,
    _normalize_skill_schedule_manifest,
    _normalize_skill_steps_manifest,
    _refresh_skill_trigger_index,
    _sanitize_skill_id,
    _save_custom_skill_manifest,
    _validate_custom_skill_manifest,
)
from aria.core.discord_alerts import runtime_host_line, send_discord_alerts
from aria.core.i18n import I18NStore
from aria.core.llm_client import LLMClient, LLMClientError
from aria.core.pipeline import Pipeline
from aria.core.pricing_catalog import resolve_litellm_pricing_entry
from aria.core.prompt_loader import PromptLoader, PromptLoadError
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.qdrant_storage_diagnostics import build_qdrant_storage_warning
from aria.core.qdrant_storage_diagnostics import list_local_qdrant_collection_names
from aria.core.qdrant_storage_diagnostics import resolve_qdrant_storage_path
from aria.core.release_meta import read_release_meta
from aria.core.runtime_diagnostics import build_runtime_diagnostics
from aria.core.runtime_endpoint import cookie_should_be_secure, request_is_secure
from aria.core.update_check import get_update_status
from aria.core.update_helper_client import fetch_update_helper_status
from aria.core.update_helper_client import helper_status_visual
from aria.core.update_helper_client import resolve_update_helper_config
from aria.core.update_helper_client import trigger_update_helper_run
from aria.core.usage_meter import UsageMeter


BASE_DIR = Path(__file__).resolve().parent.parent
CHAT_HISTORY_DIR = BASE_DIR / "data" / "chat_history"
CAPABILITY_CONTEXT_PATH = BASE_DIR / "data" / "runtime" / "capability_context.json"
_RAW_CONFIG_CACHE: dict[str, Any] = {
    "path": "",
    "mtime_ns": -1,
    "size": -1,
    "data": None,
}
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "aria" / "templates"))
USERNAME_COOKIE = "aria_username"
MEMORY_COLLECTION_COOKIE = "aria_memory_collection"
SESSION_COOKIE = "aria_session_id"
AUTO_MEMORY_COOKIE = "aria_auto_memory"
FORGET_PENDING_COOKIE = "aria_forget_pending"
SAFE_FIX_PENDING_COOKIE = "aria_safe_fix_pending"
CONNECTION_DELETE_PENDING_COOKIE = "aria_connection_delete_pending"
CONNECTION_CREATE_PENDING_COOKIE = "aria_connection_create_pending"
CONNECTION_UPDATE_PENDING_COOKIE = "aria_connection_update_pending"
UPDATE_PENDING_COOKIE = "aria_update_pending"
AUTH_COOKIE = "aria_auth_session"
CSRF_COOKIE = "aria_csrf_token"
LANG_COOKIE = "aria_lang"
COOKIE_NAME_BASES: dict[str, str] = {
    "username": USERNAME_COOKIE,
    "memory_collection": MEMORY_COLLECTION_COOKIE,
    "session": SESSION_COOKIE,
    "auto_memory": AUTO_MEMORY_COOKIE,
    "forget_pending": FORGET_PENDING_COOKIE,
    "safe_fix_pending": SAFE_FIX_PENDING_COOKIE,
    "connection_delete_pending": CONNECTION_DELETE_PENDING_COOKIE,
    "connection_create_pending": CONNECTION_CREATE_PENDING_COOKIE,
    "connection_update_pending": CONNECTION_UPDATE_PENDING_COOKIE,
    "update_pending": UPDATE_PENDING_COOKIE,
    "auth": AUTH_COOKIE,
    "csrf": CSRF_COOKIE,
    "lang": LANG_COOKIE,
}
COOKIE_KEY_BY_BASE = {value: key for key, value in COOKIE_NAME_BASES.items()}
LEGACY_COOKIE_FALLBACK_BASES: set[str] = {
    LANG_COOKIE,
}
FILE_EDITOR_CATALOG: tuple[dict[str, str], ...] = (
    {
        "path": "prompts/persona.md",
        "label": "Persona",
        "group": "prompts",
        "mode": "edit",
    },
    {
        "path": "prompts/skills/memory.md",
        "label": "Memory Prompt",
        "group": "prompts",
        "mode": "edit",
    },
    {
        "path": "prompts/skills/memory_compress.md",
        "label": "Memory Compress Prompt",
        "group": "prompts",
        "mode": "edit",
    },
    {
        "path": "docs/help/memory.md",
        "label": "Memory Help",
        "group": "help",
        "mode": "readonly",
    },
    {
        "path": "docs/help/pricing.md",
        "label": "Pricing Help",
        "group": "help",
        "mode": "readonly",
    },
    {
        "path": "docs/help/security.md",
        "label": "Security Help",
        "group": "help",
        "mode": "readonly",
    },
)
PRODUCT_DOC_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "overview",
        "label_i18n": "product_info.doc_overview",
        "label_default": "Produktüberblick",
        "path": "docs/product/overview.md",
        "summary_i18n": "product_info.doc_overview_summary",
        "summary_default": "Was ARIA ist, für wen ARIA gedacht ist und wo die aktuelle ALPHA-Grenze liegt.",
        "icon": "product",
        "assets": (),
    },
    {
        "id": "feature-list",
        "label_i18n": "product_info.doc_feature_list",
        "label_default": "Feature-Liste",
        "path": "docs/product/feature-list.md",
        "summary_i18n": "product_info.doc_feature_list_summary",
        "summary_default": "Technischer Feature-Snapshot für Chat, Memory, Skills, Connections, UI und Deployment.",
        "icon": "skills",
        "assets": (),
    },
    {
        "id": "architecture",
        "label_i18n": "product_info.doc_architecture",
        "label_default": "Architektur",
        "path": "docs/product/architecture-summary.md",
        "summary_i18n": "product_info.doc_architecture_summary",
        "summary_default": "Schichtenmodell, Routing, Custom Skills, Persistenz, Security und Update-Strategie.",
        "icon": "routing",
        "assets": (
            {
                "src": "/product-info/assets/aria_schichten_architektur.svg",
                "caption_i18n": "product_info.diagram_layers",
                "caption_default": "Schichtenarchitektur",
            },
            {
                "src": "/product-info/assets/aria_intelligentes_routing.svg",
                "caption_i18n": "product_info.diagram_routing",
                "caption_default": "Routing-Fluss",
            },
            {
                "src": "/product-info/assets/aria_modularitaet_persistenz.svg",
                "caption_i18n": "product_info.diagram_persistence",
                "caption_default": "Modularität und Persistenz",
            },
        ),
    },
)
PRODUCT_DOC_MAP = {entry["id"]: entry for entry in PRODUCT_DOC_CATALOG}
HELP_DOC_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "home",
        "label_i18n": "help.doc_home",
        "label_default": "Wiki Home",
        "path": "docs/wiki/Home.md",
        "summary_i18n": "help.doc_home_summary",
        "summary_default": "Startpunkt fuer Orientierung, Doku-Pfade und empfohlene erste Schritte.",
        "icon": "help",
        "group": "wiki",
    },
    {
        "id": "quick-start",
        "label_i18n": "help.doc_quick_start",
        "label_default": "Quick Start",
        "path": "docs/wiki/Quick-Start.md",
        "summary_i18n": "help.doc_quick_start_summary",
        "summary_default": "Schneller Weg von Docker oder Portainer bis zur ersten nutzbaren ARIA-Instanz.",
        "icon": "updates",
        "group": "wiki",
    },
    {
        "id": "memory",
        "label_i18n": "help.doc_memory",
        "label_default": "Memory",
        "path": "docs/wiki/Memory.md",
        "summary_i18n": "help.doc_memory_summary",
        "summary_default": "Memory, RAG-Dokumente, Memory Map und Recall-Verhalten kompakt erklaert.",
        "icon": "memories",
        "group": "wiki",
    },
    {
        "id": "skills",
        "label_i18n": "help.doc_skills",
        "label_default": "Skills",
        "path": "docs/wiki/Skills.md",
        "summary_i18n": "help.doc_skills_summary",
        "summary_default": "Wie Skills aufgebaut sind, wie Trigger funktionieren und wie ARIA sie ausfuehrt.",
        "icon": "skills",
        "group": "wiki",
    },
    {
        "id": "connections",
        "label_i18n": "help.doc_connections",
        "label_default": "Connections",
        "path": "docs/wiki/Connections.md",
        "summary_i18n": "help.doc_connections_summary",
        "summary_default": "Uebersicht ueber Connection-Typen, Konfiguration und Routing-Nutzen.",
        "icon": "settings",
        "group": "wiki",
    },
    {
        "id": "releases",
        "label_i18n": "help.doc_releases",
        "label_default": "Releases & Upgrades",
        "path": "docs/wiki/Releases-and-Upgrades.md",
        "summary_i18n": "help.doc_releases_summary",
        "summary_default": "Wie Releases, lokale TAR-Updates und Upgrade-Flows zusammenhaengen.",
        "icon": "updates",
        "group": "wiki",
    },
    {
        "id": "pricing",
        "label_i18n": "help.doc_pricing",
        "label_default": "Pricing",
        "path": "docs/help/pricing.md",
        "summary_i18n": "help.doc_pricing_summary",
        "summary_default": "Wie ARIA Preise fuer LLM- und Embedding-Modelle aufloest und Kosten berechnet.",
        "icon": "stats",
        "group": "reference",
    },
    {
        "id": "security",
        "label_i18n": "help.doc_security",
        "label_default": "Security",
        "path": "docs/help/security.md",
        "summary_i18n": "help.doc_security_summary",
        "summary_default": "Session-, Guardrail- und Sicherheitsprinzipien der aktuellen ALPHA-Linie.",
        "icon": "security",
        "group": "reference",
    },
)
HELP_DOC_MAP = {entry["id"]: entry for entry in HELP_DOC_CATALOG}
HELP_DOC_GROUPS: tuple[dict[str, str], ...] = (
    {
        "id": "wiki",
        "label_i18n": "help.group_wiki",
        "label_default": "Wiki & Guides",
    },
    {
        "id": "reference",
        "label_i18n": "help.group_reference",
        "label_default": "Technische Referenz",
    },
)
PRODUCT_INFO_ASSET_MAP = {
    "aria_schichten_architektur.svg": BASE_DIR / "docs" / "product" / "aria_schichten_architektur.svg",
    "aria_intelligentes_routing.svg": BASE_DIR / "docs" / "product" / "aria_intelligentes_routing.svg",
    "aria_modularitaet_persistenz.svg": BASE_DIR / "docs" / "product" / "aria_modularitaet_persistenz.svg",
}
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
ERROR_INTERPRETER_PATH = BASE_DIR / "config" / "error_interpreter.yaml"
FORGET_SIGNING_SECRET = ""
AUTH_SIGNING_SECRET = ""
DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
AUTH_SESSION_MAX_AGE_SECONDS = DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS
CONNECTION_PENDING_MAX_AGE_SECONDS = 60 * 10
LOGGER = logging.getLogger(__name__)
I18N = I18NStore(BASE_DIR / "aria" / "i18n")
LANGUAGE_LABELS = {
    "de": "Deutsch",
    "en": "English",
}
CUSTOM_SKILL_DESC_I18N_FALLBACKS: dict[str, dict[str, str]] = {
    "Fuehrt apt Update/Upgrade auf zwei konfigurierten Servern aus und fasst das Ergebnis zusammen.": {
        "en": "Runs apt update/upgrade on two configured servers and summarizes the result.",
    },
    "Führt apt Update/Upgrade auf zwei konfigurierten Servern aus und fasst das Ergebnis zusammen.": {
        "en": "Runs apt update/upgrade on two configured servers and summarizes the result.",
    },
}


def _replace_agent_name(text: str, agent_name: str) -> str:
    raw = str(text or "")
    clean_name = str(agent_name or "").strip() or "ARIA"
    return re.sub(r"\b(?:ARIA|Aria)\b", clean_name, raw)


def _cookie_scope_source(request: Request | None = None, *, public_url: str = "") -> str:
    explicit_namespace = str(os.getenv("ARIA_COOKIE_NAMESPACE", "") or "").strip()
    if explicit_namespace:
        return explicit_namespace

    if request is not None:
        headers = getattr(request, "headers", {}) or {}
        forwarded_host = str(headers.get("x-forwarded-host", "") or "").strip()
        host_header = str(headers.get("host", "") or "").strip()
        host = (forwarded_host or host_header).lower()
        if not host:
            try:
                req_url = getattr(request, "url", object())
                hostname = str(getattr(req_url, "hostname", "") or "").strip().lower()
                port = getattr(req_url, "port", None)
                if hostname:
                    host = f"{hostname}:{int(port)}" if port else hostname
            except Exception:
                host = ""
        root_path = str(getattr(request, "scope", {}).get("root_path", "") or "").strip().rstrip("/")
        if host:
            return f"{host}{root_path}"

    configured_public_url = str(public_url or "").strip()
    if configured_public_url:
        parsed = urlparse(configured_public_url)
        host = str(parsed.netloc or "").strip().lower()
        path = str(parsed.path or "").strip().rstrip("/")
        if host:
            return f"{host}{path}"

    return "default"


def _cookie_name(base_name: str, request: Request | None = None, *, public_url: str = "") -> str:
    scope_source = _cookie_scope_source(request, public_url=public_url)
    scope_hash = hashlib.sha1(scope_source.encode("utf-8")).hexdigest()[:10]
    return f"{base_name}_{scope_hash}"


def _cookie_names_for_request(request: Request | None = None, *, public_url: str = "") -> dict[str, str]:
    return {
        key: _cookie_name(base_name, request, public_url=public_url)
        for key, base_name in COOKIE_NAME_BASES.items()
    }


def _request_cookie_name(request: Request | None, base_name: str, *, public_url: str = "") -> str:
    if request is not None:
        cookie_names = getattr(getattr(request, "state", object()), "cookie_names", None)
        key = COOKIE_KEY_BY_BASE.get(base_name)
        if key and isinstance(cookie_names, dict) and cookie_names.get(key):
            return str(cookie_names[key])
        state_public_url = str(getattr(getattr(request, "state", object()), "cookie_public_url", "") or "").strip()
        if state_public_url:
            public_url = state_public_url
    return _cookie_name(base_name, request, public_url=public_url)


def _request_cookie_value(
    request: Request,
    base_name: str,
    *,
    allow_legacy: bool | None = None,
    public_url: str = "",
) -> str:
    current_name = _request_cookie_name(request, base_name, public_url=public_url)
    current_value = request.cookies.get(current_name)
    if current_value not in {None, ""}:
        return str(current_value)
    if allow_legacy is None:
        allow_legacy = base_name in LEGACY_COOKIE_FALLBACK_BASES
    if allow_legacy and current_name != base_name:
        legacy_value = request.cookies.get(base_name)
        if legacy_value not in {None, ""}:
            return str(legacy_value)
    return ""


def _set_response_cookie(
    response: Response,
    request: Request,
    base_name: str,
    value: str,
    *,
    max_age: int,
    secure: bool,
    httponly: bool,
    samesite: str = "lax",
) -> None:
    response.set_cookie(
        key=_request_cookie_name(request, base_name),
        value=value,
        max_age=max_age,
        samesite=samesite,
        secure=secure,
        httponly=httponly,
    )


def _delete_response_cookie(response: Response, request: Request | None, base_name: str) -> None:
    response.delete_cookie(_request_cookie_name(request, base_name))


def _delete_response_cookie_variants(response: Response, request: Request | None, base_name: str) -> None:
    current_name = _request_cookie_name(request, base_name)
    response.delete_cookie(current_name)
    if current_name != base_name:
        response.delete_cookie(base_name)


def _build_client_skill_progress_hints(custom_manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in custom_manifests:
        skill_id = str(manifest.get("id", "")).strip()
        skill_name = str(manifest.get("name", "")).strip() or skill_id
        if not skill_id:
            continue
        keywords = manifest.get("router_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        triggers: list[str] = []
        seen: set[str] = set()
        for raw in [
            skill_name.lower(),
            skill_id.replace("-", " ").lower(),
            *[str(item).strip().lower() for item in keywords],
        ]:
            if not raw or len(raw) < 3 or raw in seen:
                continue
            seen.add(raw)
            triggers.append(raw)
        steps = manifest.get("steps", [])
        step_names: list[str] = []
        if isinstance(steps, list):
            for item in steps[:8]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if name:
                    step_names.append(name)
        rows.append(
            {
                "id": skill_id,
                "name": skill_name,
                "triggers": triggers,
                "steps": step_names,
            }
        )
    return rows

LLM_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "ollama": {
        "label": "Ollama",
        "default_model": "ollama_chat/qwen3:8b",
        "default_api_base": "http://localhost:11434",
    },
    "litellm": {
        "label": "LiteLLM Proxy",
        "default_model": "openai/<modellname>",
        "default_api_base": "http://localhost:4000",
    },
    "openai": {
        "label": "OpenAI",
        "default_model": "openai/gpt-4o-mini",
        "default_api_base": "",
    },
    "anthropic": {
        "label": "Anthropic",
        "default_model": "anthropic/claude-3-5-sonnet-latest",
        "default_api_base": "",
    },
    "google": {
        "label": "Google",
        "default_model": "gemini/gemini-2.0-flash",
        "default_api_base": "",
    },
    "mistral": {
        "label": "Mistral",
        "default_model": "mistral/mistral-large-latest",
        "default_api_base": "",
    },
    "groq": {
        "label": "Groq",
        "default_model": "groq/llama-3.3-70b-versatile",
        "default_api_base": "",
    },
    "openrouter": {
        "label": "OpenRouter",
        "default_model": "openrouter/openai/gpt-4o-mini",
        "default_api_base": "https://openrouter.ai/api/v1",
    },
}

EMBEDDING_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "ollama": {
        "label": "Ollama",
        "default_model": "ollama/nomic-embed-text",
        "default_api_base": "http://localhost:11434",
    },
    "litellm": {
        "label": "LiteLLM Proxy",
        "default_model": "openai/<embedding-model>",
        "default_api_base": "http://localhost:4000",
    },
    "openai": {
        "label": "OpenAI",
        "default_model": "text-embedding-3-small",
        "default_api_base": "",
    },
    "openrouter": {
        "label": "OpenRouter",
        "default_model": "openai/<embedding-model>",
        "default_api_base": "https://openrouter.ai/api/v1",
    },
}

def _daily_time_to_cron(value: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        raise ValueError("Zeit muss im Format HH:MM sein.")
    hour = int(text[:2])
    minute = int(text[3:5])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Zeit ausserhalb gültiger Grenzen.")
    return f"{minute} {hour} * * *"


def _daily_time_from_cron(value: str) -> str:
    raw = str(value or "").strip()
    match = re.fullmatch(r"(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*", raw)
    if not match:
        return ""
    minute = int(match.group(1))
    hour = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def _normalize_keyword_list(values: list[str], max_items: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip().lower()
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)
        text = text.strip(" \"'`;,")
        text = re.sub(r"\s+", " ", text)
        if not text or len(text) < 2:
            continue
        if text in seen:
            continue
        seen.add(text)
        rows.append(text[:80])
        if len(rows) >= max_items:
            break
    return rows


def _extract_keyword_candidates(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []

    parsed: list[str] = []
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            values = payload.get("keywords", [])
            if isinstance(values, list):
                parsed = [str(item) for item in values]
        elif isinstance(payload, list):
            parsed = [str(item) for item in payload]
    except json.JSONDecodeError:
        pass

    if parsed:
        return _normalize_keyword_list(parsed)

    lines: list[str] = []
    for row in raw.splitlines():
        parts = [piece.strip() for piece in row.split(",")]
        for part in parts:
            if part:
                lines.append(part)
    return _normalize_keyword_list(lines)


def _format_skill_routing_info(lang: str, raw_info: str) -> str:
    value = str(raw_info or "").strip()
    if not value:
        return ""
    if value == "rebuild":
        return I18N.t(lang, "config_skill_routing.info_rebuild", "Trigger index rebuilt.")
    if value.startswith("suggest-all:"):
        parts = value.split(":")
        if len(parts) == 3:
            updated = parts[1]
            total = parts[2]
            text = I18N.t(
                lang,
                "config_skill_routing.info_suggest_all",
                "LLM suggestion applied: {updated} skills updated, {total} keywords generated.",
            )
            return text.format(updated=updated, total=total)
    if value.startswith("suggest:"):
        parts = value.split(":")
        if len(parts) == 3:
            skill_id = parts[1]
            total = parts[2]
            text = I18N.t(
                lang,
                "config_skill_routing.info_suggest_one",
                "LLM suggestion applied for {skill}: {total} keywords generated.",
            )
            return text.format(skill=skill_id, total=total)
    if value.startswith("keywords:auto:"):
        total = value.split(":")[-1]
        text = I18N.t(
            lang,
            "config_skill_routing.info_auto_keywords",
            "Auto-generated {total} trigger keywords via LLM.",
        )
        return text.format(total=total)
    if value.startswith("deleted:"):
        skill_id = value.split(":", 1)[1]
        text = I18N.t(
            lang,
            "skills.deleted_info",
            "Skill deleted: {skill}.",
        )
        return text.format(skill=skill_id)
    if value.startswith("imported:"):
        skill_id = value.split(":", 1)[1]
        text = I18N.t(
            lang,
            "skills.imported_info",
            "Skill imported: {skill}.",
        )
        return text.format(skill=skill_id)
    return value


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(((?:https?://|/)[^\s)]+)\)")


def _render_assistant_message_html(text: str) -> Markup:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        escaped_line = html.escape(str(raw_line or ""))

        def _replace_link(match: re.Match[str]) -> str:
            label = html.escape(match.group(1))
            url = html.escape(match.group(2), quote=True)
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'

        rendered_line = _MARKDOWN_LINK_RE.sub(_replace_link, escaped_line)
        lines.append(rendered_line)
    return Markup("<br>".join(lines))


def _intent_badge(intents: list[str], skill_errors: list[str] | None = None) -> tuple[str, str]:
    if skill_errors:
        text = " ".join(skill_errors).lower()
        if "memory_unavailable" in text:
            return "⚠", "memory_unavailable"
        if "embedding_failed" in text:
            return "⚠", "embedding_failed"
        return "⚠", "memory_error"
    if "memory_recall" in intents:
        return "🧠", "memory_recall"
    if "memory_store" in intents:
        return "💾", "memory_store"
    if "skill_status" in intents:
        return "🧩", "skill_status"
    for intent in intents:
        if not str(intent).startswith("capability:"):
            continue
        badge = capability_badge(str(intent).split(":", 1)[1])
        if badge:
            return badge
    if "connection_delete" in intents:
        return "🗑", "connection_delete"
    if "connection_create" in intents:
        return "🧩", "connection_create"
    if "connection_update" in intents:
        return "🛠", "connection_update"
    return "💬", "chat"


def _friendly_error_text(skill_errors: list[str] | None) -> str:
    text = " ".join(skill_errors or []).lower()
    if "memory_unavailable" in text:
        return "Memory-Dienst nicht verfügbar. Ich antworte ohne gespeichertes Wissen."
    if "embedding_failed" in text:
        return "Textverarbeitung fehlgeschlagen. Bitte Modell/API-Key für Embeddings prüfen."
    if "memory_error" in text:
        return "Memory-Verarbeitung fehlgeschlagen. Ich antworte ohne Memory-Kontext."
    if "capability_" in text:
        return "Die Aktion konnte nicht vollständig ausgeführt werden. Bitte Profil, Ziel und Zugriffsrechte prüfen."
    return ""


def _discord_alert_error_lines(skill_errors: list[str] | None, *, limit: int = 4) -> str:
    cleaned_rows: list[str] = []
    for raw in list(skill_errors or [])[: max(1, int(limit or 4))]:
        text = str(raw or "").strip()
        if not text:
            continue
        first_line = ""
        for line in text.splitlines():
            candidate = str(line or "").strip()
            if not candidate:
                continue
            if candidate.startswith("====================") or candidate.startswith("SMB Header:") or candidate.startswith("SMB Data Packet"):
                break
            first_line = candidate
            break
        if not first_line:
            first_line = text.splitlines()[0].strip() if text.splitlines() else text
        first_line = re.sub(r"\s+", " ", first_line).strip()
        if len(first_line) > 220:
            first_line = first_line[:220].rstrip() + "…"
        cleaned_rows.append(first_line)
    return " | ".join(cleaned_rows)


def _exception_response(request: Request, *, detail: str, status_code: int = 500) -> Response:
    clean_detail = str(detail or "").strip() or "Unerwarteter Fehler."
    path = str(request.url.path or "").strip()
    accept = str(request.headers.get("accept", "") or "").lower()
    agent_name = str(getattr(request.state, "agent_name", "") or "ARIA").strip() or "ARIA"
    if path == "/chat":
        return JSONResponse(status_code=status_code, content={"detail": clean_detail})
    if "text/html" in accept:
        html_body = (
            "<!DOCTYPE html><html lang='de'><head><meta charset='UTF-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            f"<title>{html.escape(agent_name)} Fehler</title><link rel='stylesheet' href='/static/style.css'></head>"
            "<body><main class='config-layout'><section class='config-card'>"
            f"<h2>{html.escape(agent_name)} konnte die Seite nicht sauber laden</h2>"
            f"<p>{html.escape(clean_detail)}</p>"
            "<p><a class='nav-link' href='/'>Zurück zum Chat</a></p>"
            "</section></main></body></html>"
        )
        return HTMLResponse(status_code=status_code, content=html_body)
    return JSONResponse(status_code=status_code, content={"detail": clean_detail})


def _sanitize_username(value: str | None) -> str:
    if not value:
        return ""
    clean = re.sub(r"\s+", " ", value).strip()
    clean = re.sub(r"[^\w .-]", "", clean, flags=re.UNICODE)
    return clean[:40].strip()


def _lang_flag(code: str) -> str:
    lang = str(code or "").strip().lower()
    if lang.startswith("de"):
        return "🇩🇪"
    if lang.startswith("en"):
        return "🇬🇧"
    if len(lang) >= 2 and lang[:2].isalpha():
        pair = lang[:2].upper()
        return chr(ord(pair[0]) + 127397) + chr(ord(pair[1]) + 127397)
    return "🏳️"


def _lang_label(code: str) -> str:
    lang = str(code or "").strip().lower()
    return LANGUAGE_LABELS.get(lang, lang.upper() or "LANG")


def _localize_custom_skill_description(manifest: dict[str, Any], lang: str) -> str:
    lang_code = str(lang or "de").strip().lower() or "de"
    i18n_map = manifest.get("description_i18n", {})
    if isinstance(i18n_map, dict):
        value = str(i18n_map.get(lang_code, "")).strip()
        if value:
            return value
    fallback = str(manifest.get("description", "")).strip()
    if lang_code == "de":
        return fallback
    mapped = CUSTOM_SKILL_DESC_I18N_FALLBACKS.get(fallback, {}).get(lang_code, "")
    return str(mapped or fallback)


def _get_username_from_request(request: Request) -> str:
    auth_session = _get_auth_session_from_request(request)
    if auth_session:
        return _sanitize_username(auth_session.get("username"))
    return _sanitize_username(_request_cookie_value(request, USERNAME_COOKIE))


def _sanitize_role(value: str | None) -> str:
    role = str(value or "").strip().lower()
    if role not in {"admin", "user"}:
        return "user"
    return role


def _encode_auth_session(
    username: str,
    role: str,
    issued_at: int | None = None,
    *,
    scope: str = "",
) -> str:
    payload = {
        "username": _sanitize_username(username),
        "role": _sanitize_role(role),
        "iat": int(issued_at if issued_at is not None else time.time()),
        "scope": str(scope or "").strip(),
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(AUTH_SIGNING_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_auth_session(raw: str | None, *, expected_scope: str = "") -> dict[str, Any] | None:
    payload, _ = _decode_auth_session_with_reason(raw, expected_scope=expected_scope)
    return payload


def _decode_auth_session_with_reason(
    raw: str | None,
    *,
    expected_scope: str = "",
) -> tuple[dict[str, Any] | None, str]:
    if not raw:
        return None, "no_cookie"
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(AUTH_SIGNING_SECRET.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None, "signature_invalid"
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            return None, "payload_invalid"
        username = _sanitize_username(str(payload.get("username", "")))
        role = _sanitize_role(payload.get("role"))
        issued_at = int(payload.get("iat", 0) or 0)
        scope = str(payload.get("scope", "") or "").strip()
        if not username or issued_at <= 0:
            return None, "payload_invalid"
        if expected_scope:
            if not scope:
                return None, "scope_missing"
            if not hmac.compare_digest(scope, expected_scope):
                return None, "scope_mismatch"
        if int(time.time()) - issued_at > AUTH_SESSION_MAX_AGE_SECONDS:
            return None, "expired"
        return {"username": username, "role": role, "iat": issued_at, "scope": scope}, "ok"
    except Exception:
        return None, "decode_failed"


def _get_auth_session_from_request(request: Request) -> dict[str, Any] | None:
    raw = _request_cookie_value(request, AUTH_COOKIE)
    expected_scope = _cookie_scope_source(
        request,
        public_url=str(getattr(getattr(request, "state", object()), "cookie_public_url", "") or ""),
    )
    return _decode_auth_session(raw, expected_scope=expected_scope)


def _get_auth_session_from_request_with_reason(request: Request) -> tuple[dict[str, Any] | None, str]:
    raw = _request_cookie_value(request, AUTH_COOKIE)
    expected_scope = _cookie_scope_source(
        request,
        public_url=str(getattr(getattr(request, "state", object()), "cookie_public_url", "") or ""),
    )
    return _decode_auth_session_with_reason(raw, expected_scope=expected_scope)


def _clear_auth_related_cookies(response: Response, request: Request | None = None, *, clear_preferences: bool = False) -> None:
    _delete_response_cookie_variants(response, request, AUTH_COOKIE)
    _delete_response_cookie_variants(response, request, CSRF_COOKIE)
    _delete_response_cookie_variants(response, request, USERNAME_COOKIE)
    _delete_response_cookie_variants(response, request, MEMORY_COLLECTION_COOKIE)
    _delete_response_cookie_variants(response, request, SESSION_COOKIE)
    _delete_response_cookie_variants(response, request, FORGET_PENDING_COOKIE)
    _delete_response_cookie_variants(response, request, SAFE_FIX_PENDING_COOKIE)
    _delete_response_cookie_variants(response, request, CONNECTION_DELETE_PENDING_COOKIE)
    _delete_response_cookie_variants(response, request, CONNECTION_CREATE_PENDING_COOKIE)
    _delete_response_cookie_variants(response, request, CONNECTION_UPDATE_PENDING_COOKIE)
    _delete_response_cookie_variants(response, request, UPDATE_PENDING_COOKIE)
    if clear_preferences:
        _delete_response_cookie_variants(response, request, LANG_COOKIE)
        _delete_response_cookie_variants(response, request, AUTO_MEMORY_COOKIE)


def _sanitize_collection_name(value: str | None) -> str:
    if not value:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
    clean = re.sub(r"_+", "_", clean)
    return clean[:64]


def _sanitize_session_id(value: str | None) -> str:
    if not value:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", value)
    return clean[:32]


def _sanitize_auth_session_max_age_seconds(value: Any) -> int:
    try:
        seconds = int(value or 0)
    except (TypeError, ValueError):
        return DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS
    return max(60 * 5, min(seconds, 60 * 60 * 24 * 30))


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _sanitize_csrf_token(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_\-]{20,128}", raw):
        return ""
    return raw


def _current_memory_day() -> str:
    return datetime.now().strftime("%y%m%d")


def _parse_collection_day_suffix(name: str) -> datetime | None:
    raw = str(name).strip()
    if len(raw) < 6:
        return None
    suffix = raw[-6:]
    if not suffix.isdigit():
        return None
    try:
        return datetime.strptime(suffix, "%y%m%d")
    except ValueError:
        return None




def _list_file_editor_entries() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in FILE_EDITOR_CATALOG:
        rel_path = str(raw.get("path", "")).strip().replace("\\", "/")
        if not rel_path or "\x00" in rel_path:
            continue
        candidate = (BASE_DIR / rel_path).resolve()
        try:
            candidate.relative_to(BASE_DIR.resolve())
        except ValueError:
            continue
        if not candidate.exists() or not candidate.is_file():
            continue
        rows.append(
            {
                "path": rel_path,
                "label": str(raw.get("label", candidate.name)).strip() or candidate.name,
                "group": str(raw.get("group", "misc")).strip() or "misc",
                "mode": str(raw.get("mode", "readonly")).strip() or "readonly",
            }
        )
    return rows


def _resolve_file_editor_entry(rel_path: str) -> dict[str, str]:
    clean = str(rel_path or "").strip().replace("\\", "/")
    if not clean or "\x00" in clean:
        raise ValueError("Ungültiger Dateipfad.")
    for row in _list_file_editor_entries():
        if row.get("path") == clean:
            return row
    raise ValueError("Datei ist nicht für den Editor freigegeben.")


def _resolve_file_editor_file(rel_path: str) -> Path:
    entry = _resolve_file_editor_entry(rel_path)
    return (BASE_DIR / entry["path"]).resolve()


def _is_allowed_edit_path(path: Path) -> bool:
    resolved = path.resolve()
    for row in _list_file_editor_entries():
        if row.get("mode") != "edit":
            continue
        if resolved == (BASE_DIR / row["path"]).resolve():
            return True
    return False


def _list_editable_files() -> list[str]:
    return [row["path"] for row in _list_file_editor_entries() if row.get("mode") == "edit"]


def _resolve_edit_file(rel_path: str) -> Path:
    entry = _resolve_file_editor_entry(rel_path)
    if entry.get("mode") != "edit":
        raise ValueError("Datei ist im Editor nur lesbar.")
    return _resolve_file_editor_file(rel_path)


def _resolve_prompt_file(rel_path: str) -> Path:
    if not rel_path or "\x00" in rel_path:
        raise ValueError("Ungültiger Dateipfad.")
    candidate = (BASE_DIR / rel_path).resolve()
    prompts_root = (BASE_DIR / "prompts").resolve()
    if prompts_root not in candidate.parents and candidate != prompts_root:
        raise ValueError("Nur Dateien unter prompts/ sind erlaubt.")
    if candidate.suffix.lower() != ".md":
        raise ValueError("Nur Markdown-Prompt-Dateien sind erlaubt.")
    return candidate


def _clear_raw_config_cache() -> None:
    _RAW_CONFIG_CACHE["path"] = ""
    _RAW_CONFIG_CACHE["mtime_ns"] = -1
    _RAW_CONFIG_CACHE["size"] = -1
    _RAW_CONFIG_CACHE["data"] = None


def _read_raw_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise ValueError(f"Konfigurationsdatei fehlt: {CONFIG_PATH}")
    try:
        stat = CONFIG_PATH.stat()
    except OSError as exc:
        raise ValueError(f"Konfigurationsdatei fehlt: {CONFIG_PATH}") from exc
    resolved_path = str(CONFIG_PATH.resolve())
    if (
        _RAW_CONFIG_CACHE.get("data") is not None
        and _RAW_CONFIG_CACHE.get("path") == resolved_path
        and int(_RAW_CONFIG_CACHE.get("mtime_ns", -1)) == int(stat.st_mtime_ns)
        and int(_RAW_CONFIG_CACHE.get("size", -1)) == int(stat.st_size)
    ):
        return copy.deepcopy(_RAW_CONFIG_CACHE["data"])
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml muss ein Mapping/Objekt enthalten.")
    _RAW_CONFIG_CACHE["path"] = resolved_path
    _RAW_CONFIG_CACHE["mtime_ns"] = int(stat.st_mtime_ns)
    _RAW_CONFIG_CACHE["size"] = int(stat.st_size)
    _RAW_CONFIG_CACHE["data"] = copy.deepcopy(data)
    return copy.deepcopy(data)


def _write_raw_config(data: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
    try:
        stat = CONFIG_PATH.stat()
    except OSError:
        _clear_raw_config_cache()
        return
    _RAW_CONFIG_CACHE["path"] = str(CONFIG_PATH.resolve())
    _RAW_CONFIG_CACHE["mtime_ns"] = int(stat.st_mtime_ns)
    _RAW_CONFIG_CACHE["size"] = int(stat.st_size)
    _RAW_CONFIG_CACHE["data"] = copy.deepcopy(data)


def _enable_bootstrap_admin_mode_in_raw_config(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw or {})
    ui = data.get("ui")
    if not isinstance(ui, dict):
        ui = {}
    ui["debug_mode"] = True
    data["ui"] = ui
    return data


def _read_error_interpreter_raw() -> str:
    if not ERROR_INTERPRETER_PATH.exists():
        return ""
    return ERROR_INTERPRETER_PATH.read_text(encoding="utf-8")


def _parse_lines(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _is_ollama_model(model: str) -> bool:
    return model.strip().lower().startswith("ollama")


def _sanitize_profile_name(value: str | None) -> str:
    if not value:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
    clean = re.sub(r"_+", "_", clean)
    return clean[:48]


def _normalize_model_key(value: str) -> str:
    return value.strip().lower()


def _sanitize_connection_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_-]", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    return raw[:48]


def _resolve_pricing_entry(entries: dict[str, Any], model_name: str) -> Any | None:
    clean = str(model_name or "").strip()
    if not clean:
        return None
    if entries:
        if clean in entries:
            return entries[clean]
        lowered = {_normalize_model_key(k): v for k, v in entries.items()}
        entry = lowered.get(_normalize_model_key(clean))
        if entry is not None:
            return entry
    return resolve_litellm_pricing_entry(clean)


def _load_models_from_api_base(api_base: str, api_key: str = "", timeout_seconds: int = 8) -> list[str]:
    base = api_base.strip().rstrip("/")
    if not base:
        raise ValueError("API Base fehlt.")

    def _fetch_json(url: str) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        request = URLRequest(url=url, headers=headers)
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Ungültige API-Antwort.")
        return data

    models: list[str] = []
    errors: list[str] = []

    try:
        data = _fetch_json(f"{base}/v1/models")
        entries = data.get("data", [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    model_id = str(entry.get("id", "")).strip()
                    if model_id:
                        models.append(model_id)
    except (ValueError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    if not models:
        try:
            data = _fetch_json(f"{base}/api/tags")
            entries = data.get("models", [])
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        name = str(entry.get("name", "")).strip()
                        if name:
                            models.append(f"ollama_chat/{name}")
        except (ValueError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

    models = sorted(set(models))
    if models:
        return models
    if errors:
        raise ValueError(f"Modelle konnten nicht geladen werden: {errors[-1]}")
    raise ValueError("Modelle konnten nicht geladen werden.")


def _read_release_meta(base_dir: Path) -> dict[str, str]:
    return read_release_meta(base_dir)


def _read_doc_text(base_dir: Path, relative_path: str) -> str:
    doc_path = base_dir / relative_path
    if not doc_path.exists():
        return ""
    try:
        return doc_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _localized_doc_path(base_dir: Path, relative_path: str, lang: str) -> str:
    clean_lang = str(lang or "").strip().lower()
    if not clean_lang:
        return relative_path
    doc_path = Path(relative_path)
    if doc_path.suffix.lower() != ".md":
        return relative_path
    lang_code = clean_lang[:2]
    if lang_code not in {"de", "en"}:
        return relative_path
    localized_name = f"{doc_path.stem}.{lang_code}{doc_path.suffix}"
    localized_path = doc_path.with_name(localized_name)
    if (base_dir / localized_path).exists():
        return localized_path.as_posix()
    return relative_path


def _render_markdown_doc(text: str) -> Markup:
    if not text.strip():
        return Markup("")
    if markdown_lib is None:
        return Markup(f"<pre>{html.escape(text)}</pre>")
    rendered = markdown_lib.markdown(
        text,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    return Markup(rendered)


def _get_update_status(current_label: str, *, ttl_seconds: int = 60 * 60 * 6) -> dict[str, Any]:
    return get_update_status(BASE_DIR, current_label=current_label, ttl_seconds=ttl_seconds)


def _build_app() -> FastAPI:
    global AUTH_SIGNING_SECRET, FORGET_SIGNING_SECRET
    settings: Settings = load_settings(CONFIG_PATH)
    global AUTH_SESSION_MAX_AGE_SECONDS
    AUTH_SESSION_MAX_AGE_SECONDS = _sanitize_auth_session_max_age_seconds(
        getattr(settings.security, "session_max_age_seconds", DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS)
    )
    get_or_create_runtime_secret("ARIA_MASTER_KEY", CONFIG_PATH)
    AUTH_SIGNING_SECRET = get_or_create_runtime_secret("ARIA_AUTH_SIGNING_SECRET", CONFIG_PATH)
    FORGET_SIGNING_SECRET = get_or_create_runtime_secret("ARIA_FORGET_SIGNING_SECRET", CONFIG_PATH)
    prompt_loader = PromptLoader(BASE_DIR / settings.prompts.persona)
    usage_meter = UsageMeter(settings)
    llm_client = LLMClient(settings.llm, usage_meter=usage_meter)
    capability_context_store = CapabilityContextStore(CAPABILITY_CONTEXT_PATH)
    pipeline = Pipeline(
        settings=settings,
        prompt_loader=prompt_loader,
        llm_client=llm_client,
        capability_context_store=capability_context_store,
        usage_meter=usage_meter,
    )
    chat_history_store = FileChatHistoryStore(CHAT_HISTORY_DIR, max_messages=80)

    def _reload_runtime() -> None:
        nonlocal settings, prompt_loader, llm_client, pipeline, startup_diagnostics, usage_meter
        global AUTH_SESSION_MAX_AGE_SECONDS
        try:
            new_settings = load_settings(CONFIG_PATH)
            new_prompt_loader = PromptLoader(BASE_DIR / new_settings.prompts.persona)
            new_usage_meter = UsageMeter(new_settings)
            new_llm_client = LLMClient(new_settings.llm, usage_meter=new_usage_meter)
            new_pipeline = Pipeline(
                settings=new_settings,
                prompt_loader=new_prompt_loader,
                llm_client=new_llm_client,
                capability_context_store=capability_context_store,
                usage_meter=new_usage_meter,
            )
        except Exception as exc:
            LOGGER.exception("Runtime reload failed")
            raise ValueError(f"Runtime-Neuladen fehlgeschlagen: {exc}") from exc

        settings = new_settings
        AUTH_SESSION_MAX_AGE_SECONDS = _sanitize_auth_session_max_age_seconds(
            getattr(new_settings.security, "session_max_age_seconds", DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS)
        )
        prompt_loader = new_prompt_loader
        llm_client = new_llm_client
        usage_meter = new_usage_meter
        pipeline = new_pipeline
        startup_diagnostics = {
            "status": "warn",
            "checked_at": "",
            "checks": [],
        }

    async def _suggest_skill_keywords_with_llm(
        manifest: dict[str, Any],
        language: str = "de",
        max_keywords: int = 12,
    ) -> list[str]:
        clean = _validate_custom_skill_manifest(manifest)
        lang = str(language or "de").strip().lower()
        lang_name = "German" if lang.startswith("de") else "English"
        steps = clean.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        step_lines: list[str] = []
        for step in steps[:8]:
            if not isinstance(step, dict):
                continue
            step_type = str(step.get("type", "")).strip()
            step_name = str(step.get("name", "")).strip()
            params = step.get("params", {})
            if not isinstance(params, dict):
                params = {}
            param_hint = ""
            if step_type == "ssh_run":
                param_hint = str(params.get("command", "")).strip()
            elif step_type == "llm_transform":
                param_hint = str(params.get("prompt", "")).strip()
            elif step_type == "discord_send":
                param_hint = str(params.get("message", "")).strip()
            elif step_type == "chat_send":
                param_hint = str(params.get("chat_message", "")).strip()
            row = f"- {step_type}"
            if step_name:
                row += f" | {step_name}"
            if param_hint:
                row += f" | {param_hint[:120]}"
            step_lines.append(row)

        prompt_payload = {
            "skill_id": clean.get("id", ""),
            "skill_name": clean.get("name", ""),
            "category": clean.get("category", ""),
            "description": clean.get("description", ""),
            "connections": clean.get("connections", []),
            "steps": step_lines,
            "max_keywords": max(6, min(int(max_keywords), 20)),
            "language": lang_name,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate routing trigger keywords for one automation skill. "
                    "Return ONLY compact JSON object: {\"keywords\": [\"...\", \"...\"]}. "
                    "Keywords must be short user phrases, no explanations, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate useful trigger keywords in {lang_name}.\n"
                    "Use intent phrases users would actually type.\n"
                    "Avoid duplicates.\n"
                    f"Input:\n{json.dumps(prompt_payload, ensure_ascii=False)}"
                ),
            },
        ]
        candidates: list[str] = []
        try:
            response = await llm_client.chat(
                messages,
                source="skill_keywords",
                operation="generate_keywords",
                user_id="system",
            )
            candidates = _extract_keyword_candidates(response.content)
        except LLMClientError:
            candidates = []

        if not candidates:
            fallback: list[str] = []
            skill_name = str(clean.get("name", "")).strip().lower()
            if skill_name:
                fallback.append(skill_name)
                fallback.append(f"{skill_name} ausführen")
            clean_id = str(clean.get("id", "")).strip().lower()
            if clean_id:
                fallback.append(clean_id.replace("-", " "))
            desc = str(clean.get("description", "")).strip().lower()
            if desc:
                pieces = re.split(r"[,.!?:;/]", desc)
                for piece in pieces[:3]:
                    if piece.strip():
                        fallback.append(piece.strip()[:80])
            candidates = _normalize_keyword_list(fallback, max_items=max_keywords)
        return _normalize_keyword_list(candidates, max_items=max_keywords)

    def _default_memory_collection_for_user(user_id: str) -> str:
        slug = _sanitize_collection_name(user_id.lower())
        if not slug:
            slug = "web"
        prefix = settings.memory.collections.facts.prefix.strip() or "aria_facts"
        return f"{prefix}_{slug}"

    def _ensure_session_id(request: Request) -> str:
        current = _sanitize_session_id(_request_cookie_value(request, SESSION_COOKIE))
        if current:
            return current
        return uuid4().hex[:12]

    def _get_effective_memory_collection(request: Request, user_id: str) -> str:
        selected = _sanitize_collection_name(_request_cookie_value(request, MEMORY_COLLECTION_COOKIE))
        if selected:
            return selected
        return _default_memory_collection_for_user(user_id)

    def _session_memory_collection_for_user(user_id: str, session_id: str) -> str:
        slug = _sanitize_collection_name(user_id.lower())
        if not slug:
            slug = "web"
        session_prefix = settings.memory.collections.sessions.prefix.strip() or "aria_sessions"
        _ = session_id
        return f"{session_prefix}_{slug}_{_current_memory_day()}"

    def _is_auto_memory_enabled(request: Request) -> bool:
        _ = request
        return bool(settings.auto_memory.enabled)

    def _qdrant_base_url(request: Request) -> str:
        base = (settings.memory.qdrant_url or "").strip()
        parsed = urlparse(base)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            host = (parsed.hostname or "").strip()
            # if Qdrant läuft als interner Service (hostname=qdrant), für UI einen von außen erreichbaren Host bauen
            if host.lower() == "qdrant":
                req_host = (request.url.hostname or "").strip() or "localhost"
                if ":" in req_host and not req_host.startswith("["):
                    req_host = f"[{req_host}]"
                port = parsed.port or 6333
                return f"{parsed.scheme}://{req_host}:{port}"
            if host in {"localhost", "127.0.0.1", "::1"}:
                req_host = (request.url.hostname or "").strip()
                if req_host:
                    host = req_host
            if not host:
                host = parsed.hostname or "localhost"
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            port = parsed.port
            port_part = f":{port}" if port else ""
            return f"{parsed.scheme}://{host}{port_part}"
        return base

    def _qdrant_dashboard_url(request: Request) -> str:
        base = _qdrant_base_url(request).rstrip("/")
        if not base:
            return ""
        return f"{base}/dashboard#/collections"

    async def _list_qdrant_collections() -> list[str]:
        if not settings.memory.enabled or settings.memory.backend.lower() != "qdrant":
            return []
        client = create_async_qdrant_client(
            url=settings.memory.qdrant_url,
            api_key=(settings.memory.qdrant_api_key or None),
            timeout=10,
        )
        try:
            resp = await client.get_collections()
            names = [c.name for c in getattr(resp, "collections", []) if getattr(c, "name", "")]
            names.sort()
            return names
        except Exception:
            return []

    async def _qdrant_overview(request: Request) -> dict[str, Any]:
        storage_path = resolve_qdrant_storage_path(BASE_DIR, settings.memory.qdrant_url)
        local_collection_names = list_local_qdrant_collection_names(storage_path)
        empty = {
            "enabled": settings.memory.enabled and settings.memory.backend.lower() == "qdrant",
            "qdrant_url": _qdrant_base_url(request),
            "dashboard_url": _qdrant_dashboard_url(request),
            "collections": [],
            "collection_count": 0,
            "total_points": 0,
            "max_points": 0,
            "reachable": False,
            "error": "",
            "storage_path": str(storage_path) if storage_path else "",
            "storage_collection_count": len(local_collection_names),
            "storage_warning": "",
            "storage_warning_missing": [],
        }
        if not empty["enabled"]:
            return empty

        client = create_async_qdrant_client(
            url=settings.memory.qdrant_url,
            api_key=(settings.memory.qdrant_api_key or None),
            timeout=10,
        )
        try:
            resp = await client.get_collections()
            names = [c.name for c in getattr(resp, "collections", []) if getattr(c, "name", "")]
            names = sorted(set(names))
            rows: list[dict[str, Any]] = []
            max_points = 0
            for name in names:
                points = 0
                vectors = 0
                indexed_vectors = 0
                status = "ok"
                try:
                    info = await client.get_collection(collection_name=name)
                    points = int(getattr(info, "points_count", 0) or 0)
                    vectors = int(getattr(info, "vectors_count", 0) or 0)
                    indexed_vectors = int(getattr(info, "indexed_vectors_count", 0) or 0)
                    raw_status = getattr(info, "status", None)
                    if raw_status is not None:
                        status = str(raw_status)
                except Exception:
                    status = "error"
                max_points = max(max_points, points)
                rows.append(
                    {
                        "name": name,
                        "points": points,
                        "vectors": vectors,
                        "indexed_vectors": indexed_vectors,
                        "status": status,
                    }
                )

            for row in rows:
                row["points_bar_pct"] = int((row["points"] / max_points) * 100) if max_points > 0 else 0

            storage_warning = build_qdrant_storage_warning(
                storage_path=storage_path,
                local_collection_names=local_collection_names,
                api_collection_names=names,
            )
            return {
                "enabled": True,
                "qdrant_url": _qdrant_base_url(request),
                "dashboard_url": _qdrant_dashboard_url(request),
                "collections": rows,
                "collection_count": len(rows),
                "total_points": int(sum(r["points"] for r in rows)),
                "max_points": max_points,
                "reachable": True,
                "error": "",
                "storage_path": str(storage_path) if storage_path else "",
                "storage_collection_count": len(local_collection_names),
                "storage_warning": str(storage_warning.get("message", "") or ""),
                "storage_warning_missing": list(storage_warning.get("missing_from_api", []) or []),
            }
        except Exception as exc:
            empty["error"] = str(exc)
            storage_warning = build_qdrant_storage_warning(
                storage_path=storage_path,
                local_collection_names=local_collection_names,
                api_collection_names=[],
            )
            empty["storage_warning"] = str(storage_warning.get("message", "") or "")
            empty["storage_warning_missing"] = list(storage_warning.get("missing_from_api", []) or [])
            return empty

    def _list_prompt_files() -> list[dict[str, Any]]:
        prompt_paths: set[Path] = set()
        prompts_root = (BASE_DIR / "prompts").resolve()

        persona_path = (BASE_DIR / settings.prompts.persona).resolve()
        if persona_path.exists() and persona_path.suffix.lower() == ".md":
            prompt_paths.add(persona_path)

        skills_dir = (BASE_DIR / settings.prompts.skills_dir).resolve()
        if skills_dir.exists() and skills_dir.is_dir():
            for path in skills_dir.rglob("*.md"):
                if path.is_file():
                    prompt_paths.add(path.resolve())

        # Include other prompt markdown files under prompts/ (e.g. examples), no code files.
        if prompts_root.exists():
            for path in prompts_root.rglob("*.md"):
                if path.is_file():
                    prompt_paths.add(path.resolve())

        rows: list[dict[str, Any]] = []
        for path in sorted(prompt_paths):
            try:
                rel = str(path.relative_to(BASE_DIR)).replace("\\", "/")
                stat = path.stat()
                rows.append(
                    {
                        "path": rel,
                        "name": path.name,
                        "group": "prompts",
                        "mode": "edit",
                        "size": int(stat.st_size),
                        "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    }
                )
            except (OSError, ValueError):
                continue
        return rows

    def _get_profiles(raw: dict[str, Any], kind: str) -> dict[str, dict[str, Any]]:
        profiles = raw.get("profiles", {})
        if not isinstance(profiles, dict):
            return {}
        section = profiles.get(kind, {})
        if not isinstance(section, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for name, payload in section.items():
            if isinstance(payload, dict):
                result[str(name)] = payload
        return result

    def _get_active_profile_name(raw: dict[str, Any], kind: str) -> str:
        profiles = raw.get("profiles", {})
        if not isinstance(profiles, dict):
            return ""
        active = profiles.get("active", {})
        if not isinstance(active, dict):
            return ""
        return str(active.get(kind, "")).strip()

    def _set_active_profile(raw: dict[str, Any], kind: str, profile_name: str) -> None:
        raw.setdefault("profiles", {})
        if not isinstance(raw["profiles"], dict):
            raw["profiles"] = {}
        raw["profiles"].setdefault("active", {})
        if not isinstance(raw["profiles"]["active"], dict):
            raw["profiles"]["active"] = {}
        raw["profiles"]["active"][kind] = profile_name

    def _get_secure_store(raw: dict[str, Any] | None = None):
        cfg = raw if isinstance(raw, dict) else _read_raw_config()
        security = cfg.get("security", {})
        if not isinstance(security, dict):
            security = {}
        if not bool(security.get("enabled", True)):
            return None
        master = get_master_key(CONFIG_PATH)
        if not master:
            return None
        db_rel = str(security.get("db_path", "data/auth/aria_secure.sqlite")).strip() or "data/auth/aria_secure.sqlite"
        db_path = Path(db_rel)
        if not db_path.is_absolute():
            db_path = (BASE_DIR / db_path).resolve()
        from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key

        return SecureConfigStore(
            config=SecureStoreConfig(db_path=db_path, enabled=True),
            master_key=decode_master_key(master),
        )

    def _get_auth_manager() -> AuthManager | None:
        store = _get_secure_store()
        if not store:
            return None
        return AuthManager(store=store)

    def _active_admin_count(users: list[dict[str, Any]]) -> int:
        count = 0
        for row in users:
            role = _sanitize_role(row.get("role"))
            active = bool(row.get("active"))
            if role == "admin" and active:
                count += 1
        return count

    startup_maintenance_task: asyncio.Task[None] | None = None
    startup_diagnostics: dict[str, Any] = {
        "status": "warn",
        "checked_at": "",
        "checks": [],
    }

    async def _get_runtime_preflight_data(force_refresh: bool = False) -> dict[str, Any]:
        nonlocal startup_diagnostics
        if force_refresh or not startup_diagnostics.get("checked_at"):
            startup_diagnostics = await build_runtime_diagnostics(BASE_DIR, settings, usage_meter=usage_meter)
        return startup_diagnostics

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):  # noqa: ANN202
        nonlocal startup_maintenance_task, startup_diagnostics
        async def _run_startup_maintenance() -> None:
            try:
                startup_diagnostics = await _get_runtime_preflight_data(force_refresh=True)
                diag_lines = [
                    f"{row.get('id')}: {row.get('status')} - {row.get('summary')}"
                    for row in startup_diagnostics.get("checks", [])
                ]
                LOGGER.info(
                    "Startup diagnostics status=%s :: %s",
                    startup_diagnostics.get("status", "warn"),
                    " | ".join(diag_lines),
                )
                memory_ops = 0
                if pipeline.memory_skill:
                    session_cfg = settings.memory.collections.sessions
                    compress_after = int(getattr(session_cfg, "compress_after_days", 7) or 7)
                    monthly_after = int(getattr(session_cfg, "monthly_after_days", 30) or 30)
                    stats = await pipeline.memory_skill.compress_all_users(
                        compress_after_days=compress_after,
                        monthly_after_days=monthly_after,
                    )
                    removed_empty = await pipeline.memory_skill.cleanup_empty_collections_global()
                    memory_ops = (
                        int(stats.get("compressed_week", 0))
                        + int(stats.get("compressed_month", 0))
                        + len(removed_empty)
                    )

                await pipeline.token_tracker.prune_old_entries(
                    int(getattr(settings.token_tracking, "retention_days", 0) or 0)
                )
                await pipeline.token_tracker.log(
                    request_id=str(uuid4()),
                    user_id="system",
                    intents=["memory_compress_startup"],
                    router_level=0,
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    chat_model=settings.llm.model,
                    embedding_model=settings.embeddings.model,
                    embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                    chat_cost_usd=None,
                    embedding_cost_usd=None,
                    total_cost_usd=None,
                    duration_ms=0,
                    source="startup",
                    skill_errors=[],
                    extraction_model="compression",
                    extraction_usage={
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "calls": memory_ops,
                    },
                )
                await asyncio.to_thread(
                    send_discord_alerts,
                    settings,
                    category="system_events",
                    title=f"{_agent_name_value()} gestartet",
                    lines=[
                        runtime_host_line(settings),
                        f"Version: {_read_release_meta(BASE_DIR).get('label', 'unknown')}",
                        f"Memory-Operationen beim Start: {memory_ops}",
                        f"LLM: {settings.llm.model}",
                        f"Embeddings: {settings.embeddings.model}",
                        f"Memory: {settings.memory.backend}",
                        f"Preflight: {startup_diagnostics.get('status', 'warn')}",
                    ],
                    level="info",
                )
            except Exception as exc:
                LOGGER.warning("Startup maintenance failed: %s", exc)

        startup_maintenance_task = asyncio.create_task(_run_startup_maintenance())
        try:
            yield
        finally:
            if startup_maintenance_task and not startup_maintenance_task.done():
                startup_maintenance_task.cancel()
                with suppress(asyncio.CancelledError):
                    await startup_maintenance_task

    app = FastAPI(title=prompt_loader.get_persona_name(default=settings.ui.title or "ARIA"), lifespan=_lifespan)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "aria" / "static")), name="static")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(
            BASE_DIR / "aria" / "static" / "logo-aria-v01.png",
            media_type="image/png",
        )
    if settings.channels.api.enabled:
        register_api_routes(app, pipeline=pipeline, auth_token=settings.channels.api.auth_token)

    def _agent_name_value() -> str:
        try:
            return prompt_loader.get_persona_name(default=settings.ui.title or "ARIA")
        except Exception:
            fallback = str(settings.ui.title or "ARIA").strip()
            return fallback or "ARIA"

    def _tr(request: Request, key: str, default: str = "") -> str:
        lang = "de"
        agent_name = _agent_name_value()
        if request is not None and hasattr(request, "state"):
            lang = str(getattr(request.state, "lang", "") or "de")
            agent_name = str(getattr(request.state, "agent_name", "") or agent_name)
        return _replace_agent_name(I18N.t(lang, key, default), agent_name)

    def _agent_name(request: Request | None = None, fallback: str = "") -> str:
        if request is not None and hasattr(request, "state"):
            value = str(getattr(request.state, "agent_name", "") or "").strip()
            if value:
                return value
        return _agent_name_value() or (str(fallback or "").strip() or "ARIA")

    def _agent_text(request: Request | None, text: str, fallback: str = "") -> str:
        base = str(text or fallback or "")
        return _replace_agent_name(base, _agent_name(request, fallback))

    TEMPLATES.env.globals["tr"] = _tr
    TEMPLATES.env.globals["agent_name"] = _agent_name
    TEMPLATES.env.globals["agent_text"] = _agent_text
    TEMPLATES.env.globals["lang_flag"] = _lang_flag
    TEMPLATES.env.globals["lang_label"] = _lang_label
    TEMPLATES.env.globals["render_assistant_message_html"] = _render_assistant_message_html

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path or "/"
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        cookie_public_url = str(settings.aria.public_url or "")
        request.state.cookie_public_url = cookie_public_url
        request.state.cookie_scope_source = _cookie_scope_source(request, public_url=cookie_public_url)
        request.state.cookie_names = _cookie_names_for_request(request, public_url=cookie_public_url)
        accept_header = str(request.headers.get("accept", "") or "").lower()
        requested_with = str(request.headers.get("x-requested-with", "") or "").lower()
        expects_json = "application/json" in accept_header or requested_with in {"fetch", "xmlhttprequest"}
        requested_lang = (
            str(request.query_params.get("lang", "")).strip().lower()
            or str(_request_cookie_value(request, LANG_COOKIE)).strip().lower()
            or str(settings.ui.language or "de").strip().lower()
        )
        resolved_lang = I18N.resolve_lang(requested_lang, default_lang=str(settings.ui.language or "de"))
        request.state.lang = resolved_lang
        request.state.supported_languages = I18N.available_languages()
        request.state.agent_name = _agent_name_value()
        request.state.release_meta = _read_release_meta(BASE_DIR)
        request.state.update_status = _get_update_status(request.state.release_meta["label"])
        raw_auth_cookie = str(_request_cookie_value(request, AUTH_COOKIE) or "").strip()
        auth, auth_reason = _get_auth_session_from_request_with_reason(request)
        auth_degraded = False
        csrf_cookie_token = _sanitize_csrf_token(_request_cookie_value(request, CSRF_COOKIE))
        if not csrf_cookie_token:
            csrf_cookie_token = _new_csrf_token()
        request.state.csrf_token = csrf_cookie_token
        if auth:
            manager = _get_auth_manager()
            if manager:
                try:
                    user = manager.store.get_user(auth["username"])
                except Exception:
                    LOGGER.exception("Auth store lookup failed; keeping signed session for this request")
                    auth_degraded = True
                    auth_reason = "store_error"
                else:
                    if not user:
                        auth = None
                        auth_reason = "user_missing"
                    elif not bool(user.get("active")):
                        auth = None
                        auth_reason = "user_inactive"
                    else:
                        # Canonical username comes from trusted store (lowercase in current store schema).
                        auth["username"] = _sanitize_username(user.get("username"))
                        # Role comes from trusted store, not only from cookie payload.
                        auth["role"] = _sanitize_role(user.get("role"))
            else:
                if bool(settings.security.enabled):
                    auth_degraded = True
                    auth_reason = "store_unavailable"
                else:
                    auth = None
                    auth_reason = "security_disabled"
        request.state.authenticated = bool(auth)
        request.state.auth_user = auth.get("username") if auth else ""
        request.state.auth_role = auth.get("role") if auth else ""
        request.state.auth_debug_reason = auth_reason
        request.state.auth_degraded = auth_degraded
        request.state.debug_mode = bool(settings.ui.debug_mode)
        request.state.ui_theme = normalize_ui_theme(getattr(settings.ui, "theme", "matrix"))
        request.state.ui_background = normalize_ui_background(getattr(settings.ui, "background", "grid"))
        request.state.can_access_settings = bool(auth) and can_access_settings(request.state.auth_role)
        request.state.can_access_users = bool(auth) and can_access_users(request.state.auth_role)
        request.state.can_access_advanced_config = bool(auth) and can_access_advanced_config(
            request.state.auth_role,
            request.state.debug_mode,
        )

        public_paths = {"/health", "/login", "/session-expired"}
        is_public_or_api = (
            path in public_paths
            or path.startswith("/static/")
            or path.startswith("/v1/")
            or path.startswith("/api/")
        )

        needs_login = (
            path in {"/", "/chat", "/stats", "/activities", "/memories", "/skills", "/set-username", "/set-auto-memory"}
            or path.startswith("/memories/")
            or path.startswith("/skills/")
            or path.startswith("/stats/")
            or path.startswith("/activities/")
            or path.startswith("/config/")
            or path == "/config"
        )
        if not is_public_or_api and needs_login and not auth:
            target_path = path
            if request.url.query:
                target_path = f"{path}?{request.url.query}"
            next_path = quote_plus(target_path)
            login_url = f"/login?next={next_path}"
            if raw_auth_cookie:
                if expects_json:
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "code": "session_expired",
                            "detail": _tr(request, "auth.session_expired", "Sitzung abgelaufen. Bitte erneut anmelden."),
                            "login_url": login_url,
                        },
                    )
                    if auth_reason not in {"store_unavailable", "store_error"}:
                        _clear_auth_related_cookies(response, request)
                    return response
                response = RedirectResponse(url=f"/session-expired?next={next_path}", status_code=303)
                if auth_reason not in {"store_unavailable", "store_error"}:
                    _clear_auth_related_cookies(response, request)
                return response
            if expects_json:
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": "login_required",
                        "detail": _tr(request, "auth.login_required", "Bitte zuerst anmelden."),
                        "login_url": login_url,
                    },
                )
            return RedirectResponse(url=login_url, status_code=303)

        if not is_public_or_api and path == "/set-auto-memory" and auth:
            if _sanitize_role(auth.get("role")) != "admin":
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_admin",
                            "detail": _tr(request, "auth.no_admin", "Admin-Rechte erforderlich."),
                        },
                    )
                return RedirectResponse(url="/?error=no_admin", status_code=303)

        if not is_public_or_api and path == "/config" and auth:
            if not request.state.can_access_settings:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_settings",
                            "detail": _tr(request, "auth.no_settings", "Keine Berechtigung für Einstellungen."),
                        },
                    )
                return RedirectResponse(url="/?error=no_settings", status_code=303)

        if not is_public_or_api and path.startswith("/config/") and auth:
            if not request.state.can_access_settings:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_settings",
                            "detail": _tr(request, "auth.no_settings", "Keine Berechtigung für Einstellungen."),
                        },
                    )
                return RedirectResponse(url="/?error=no_settings", status_code=303)
            if is_admin_only_path(path) and not request.state.can_access_users:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_admin",
                            "detail": _tr(request, "auth.no_admin", "Admin-Rechte erforderlich."),
                        },
                    )
                return RedirectResponse(url="/config?error=no_admin", status_code=303)
            if is_advanced_config_path(path) and not request.state.can_access_advanced_config:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "admin_mode_required",
                            "detail": _tr(
                                request,
                                "auth.admin_mode_required",
                                "Admin-Modus erforderlich. Bitte unter Benutzer aktivieren.",
                            ),
                        },
                    )
                return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)

        protected_methods = {"POST", "PUT", "PATCH", "DELETE"}
        csrf_exempt_prefixes = ("/v1/", "/api/")
        csrf_exempt_paths = {"/health", "/skills/import", "/config/connections/rss/import-opml", "/memories/upload"}
        if (
            request.method.upper() in protected_methods
            and path not in csrf_exempt_paths
            and not path.startswith(csrf_exempt_prefixes)
        ):
            header_token = _sanitize_csrf_token(request.headers.get("x-csrf-token"))
            form_token = ""
            content_type = (request.headers.get("content-type") or "").lower()
            if not header_token and (
                "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type
            ):
                try:
                    if "multipart/form-data" in content_type:
                        form = await request.form()
                        raw_token = str(form.get("csrf_token", "") or "")
                    else:
                        body = await request.body()
                        parsed = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=False)
                        raw_token = parsed.get("csrf_token", [""])[0]
                    form_token = _sanitize_csrf_token(raw_token)
                except Exception:
                    form_token = ""
            supplied = header_token or form_token
            if not supplied or not hmac.compare_digest(supplied, csrf_cookie_token):
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "csrf_failed",
                            "detail": _tr(
                                request,
                                "auth.csrf_failed",
                                "CSRF-Prüfung fehlgeschlagen. Bitte Seite neu laden.",
                            ),
                        },
                    )
                return HTMLResponse(
                    content="<h3>CSRF validation failed. Bitte Seite neu laden.</h3>",
                    status_code=403,
                )

        response = await call_next(request)
        if isinstance(response, Response):
            response_lang = I18N.resolve_lang(
                str(getattr(request.state, "lang", resolved_lang) or resolved_lang),
                default_lang=str(settings.ui.language or "de"),
            )
            if bool(request.state.debug_mode):
                response.headers.setdefault("X-ARIA-Auth-Reason", str(auth_reason or "unknown"))
                response.headers.setdefault("X-ARIA-Auth-Degraded", "1" if auth_degraded else "0")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            response.headers.setdefault(
                "Content-Security-Policy",
                (
                    "default-src 'self'; "
                    "img-src 'self' data:; "
                    "style-src 'self' 'unsafe-inline'; "
                    "script-src 'self' https://unpkg.com 'unsafe-inline'; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                ),
            )
            if auth and path != "/logout":
                refreshed = _encode_auth_session(
                    auth["username"],
                    auth["role"],
                    scope=str(getattr(request.state, "cookie_scope_source", "") or ""),
                )
                _set_response_cookie(
                    response,
                    request,
                    AUTH_COOKIE,
                    refreshed,
                    max_age=AUTH_SESSION_MAX_AGE_SECONDS,
                    secure=secure_cookie,
                    httponly=True,
                )
                _set_response_cookie(
                    response,
                    request,
                    USERNAME_COOKIE,
                    auth["username"],
                    max_age=60 * 60 * 24 * 365,
                    secure=secure_cookie,
                    httponly=False,
                )
            _set_response_cookie(
                response,
                request,
                CSRF_COOKIE,
                csrf_cookie_token,
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
            _set_response_cookie(
                response,
                request,
                LANG_COOKIE,
                response_lang,
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/system/preflight")
    async def system_preflight() -> dict[str, Any]:
        return await _get_runtime_preflight_data()

    @app.get("/api/auto-memory/status")
    async def auto_memory_status() -> dict[str, bool]:
        return {"enabled": bool(settings.auto_memory.enabled)}

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, next: str = "/", error: str = "", info: str = "") -> HTMLResponse:  # noqa: A002
        auth = _get_auth_session_from_request(request)
        if auth:
            target = str(next or "/")
            if not target.startswith("/"):
                target = "/"
            return RedirectResponse(url=target, status_code=303)
        bootstrap_mode = False
        login_users: list[str] = []
        bootstrap_locked = bool(settings.security.bootstrap_locked)
        manager = _get_auth_manager()
        if manager:
            try:
                rows = manager.store.list_users()
                bootstrap_mode = len(rows) == 0
                login_users = sorted(
                    [str(row.get("username", "")).strip() for row in rows if bool(row.get("active")) and str(row.get("username", "")).strip()]
                )
                lower_error = str(error or "").strip().lower()
                if lower_error and (
                    "security store" in lower_error
                    or "bootstrap gesperrt" in lower_error
                    or "bootstrap is currently locked" in lower_error
                ):
                    error = ""
            except Exception:
                bootstrap_mode = False
                login_users = []
        return TEMPLATES.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": settings.ui.title,
                "next_path": next if str(next).startswith("/") else "/",
                "error_message": error,
                "info_message": info,
                "username": "",
                "bootstrap_mode": bootstrap_mode,
                "bootstrap_locked": bootstrap_locked,
                "login_users": login_users,
            },
        )

    @app.post("/login")
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        password_confirm: str = Form(""),
        next_path: str = Form("/"),
    ) -> RedirectResponse:
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        clean_username = _sanitize_username(username)
        target = str(next_path or "/")
        if not target.startswith("/"):
            target = "/"

        manager = _get_auth_manager()
        if not manager:
            return RedirectResponse(
                url="/login?error=Security+Store+nicht+aktiv.+Bitte+secrets.env+und+Security+prüfen.",
                status_code=303,
            )
        try:
            store = manager.store
            users = store.list_users()
            lang = str(getattr(request.state, "lang", "de") or "de")
            if not users:
                if bool(settings.security.bootstrap_locked):
                    return RedirectResponse(
                        url="/login?error=Bootstrap+gesperrt.+Bitte+Admin+im+Config+Store+anlegen+oder+bootstrap_locked+deaktivieren.",
                        status_code=303,
                    )
                if not clean_username:
                    return RedirectResponse(url="/login?error=Bitte+Benutzernamen+eingeben", status_code=303)
                if str(password or "") != str(password_confirm or ""):
                    msg = (
                        "Passwörter stimmen nicht überein. Bitte beide Felder identisch eingeben."
                        if lang.startswith("de")
                        else "Passwords do not match. Please enter the same password in both fields."
                    )
                    return RedirectResponse(url=f"/login?error={quote_plus(msg)}", status_code=303)
                try:
                    manager.upsert_user(clean_username, password, role="admin")
                except ValueError as exc:
                    return RedirectResponse(url=f"/login?error={quote_plus(str(exc))}", status_code=303)
                try:
                    raw = _read_raw_config()
                    raw = _enable_bootstrap_admin_mode_in_raw_config(raw)
                    _write_raw_config(raw)
                    settings.ui.debug_mode = True
                except Exception:
                    LOGGER.exception("Failed to auto-enable admin mode for first bootstrap user")
                users = store.list_users()
            if not clean_username or not manager.verify(clean_username, password):
                return RedirectResponse(url=f"/login?error={quote_plus('Login fehlgeschlagen')}", status_code=303)
            user = store.get_user(clean_username)
            canonical_username = _sanitize_username((user or {}).get("username")) or clean_username
            role = _sanitize_role((user or {}).get("role"))
            response = RedirectResponse(url=target, status_code=303)
            _set_response_cookie(
                response,
                request,
                AUTH_COOKIE,
                _encode_auth_session(
                    canonical_username,
                    role,
                    scope=str(getattr(request.state, "cookie_scope_source", "") or ""),
                ),
                max_age=AUTH_SESSION_MAX_AGE_SECONDS,
                secure=secure_cookie,
                httponly=True,
            )
            _set_response_cookie(
                response,
                request,
                USERNAME_COOKIE,
                canonical_username,
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            _set_response_cookie(
                response,
                request,
                MEMORY_COLLECTION_COOKIE,
                _default_memory_collection_for_user(canonical_username),
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            _set_response_cookie(
                response,
                request,
                SESSION_COOKIE,
                uuid4().hex[:12],
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except Exception:
            return RedirectResponse(url=f"/login?error={quote_plus('Login fehlgeschlagen')}", status_code=303)

    @app.post("/logout")
    async def logout(request: Request) -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        _clear_auth_related_cookies(response, request, clear_preferences=True)
        return response

    @app.get("/session-expired", response_class=HTMLResponse)
    async def session_expired_page(request: Request, next: str = "/") -> HTMLResponse:  # noqa: A002
        target = str(next or "/")
        if not target.startswith("/"):
            target = "/"
        response = TEMPLATES.TemplateResponse(
            request=request,
            name="session_expired.html",
            context={
                "title": settings.ui.title,
                "next_path": target,
                "next_query": quote_plus(target),
            },
        )
        _clear_auth_related_cookies(response, request)
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        username = _get_username_from_request(request)
        session_id = _ensure_session_id(request)
        auth = _get_auth_session_from_request(request) or {}
        auto_memory_enabled = _is_auto_memory_enabled(request)
        recall_templates = settings.routing.memory_recall_keywords
        store_templates = settings.routing.memory_store_prefixes
        custom_manifests, _ = _load_custom_skill_manifests()
        skill_trigger_hints: list[str] = []
        skill_toolbox_rows: list[dict[str, Any]] = []
        seen_hints: set[str] = set()
        lang = str(getattr(request.state, "lang", "de") or "de")
        for manifest in custom_manifests:
            skill_name = str(manifest.get("name", "") or "").strip()
            skill_id = str(manifest.get("id", "") or "").strip()
            names = [
                skill_name.lower(),
                skill_id.replace("-", " ").lower(),
            ]
            keywords = manifest.get("router_keywords", [])
            if not isinstance(keywords, list):
                keywords = []
            trigger_values = [str(val).strip() for val in keywords if str(val).strip()]
            first_trigger = next((item for item in trigger_values if len(item.strip()) >= 3), "")
            description = _localize_custom_skill_description(manifest, lang).strip()
            for item in names + [value.lower() for value in trigger_values]:
                if not item or len(item) < 3:
                    continue
                if item in seen_hints:
                    continue
                seen_hints.add(item)
                skill_trigger_hints.append(item)
            if skill_name or first_trigger or skill_id:
                skill_toolbox_rows.append(
                    {
                        "label": skill_name or first_trigger or skill_id,
                        "insert": first_trigger or skill_name or skill_id.replace("-", " "),
                        "hint": description or first_trigger or skill_id,
                        "keywords": list(
                            dict.fromkeys(
                                [
                                    skill_name.lower(),
                                    skill_id.lower(),
                                    skill_id.replace("-", " ").lower(),
                                    description.lower(),
                                    *[item.lower() for item in trigger_values],
                                ]
                            )
                        ),
                    }
                )
        active_collection = _get_effective_memory_collection(request, username or "web")
        session_collection = _session_memory_collection_for_user(username or "web", session_id)
        chat_history = chat_history_store.load_history(username) if username else []
        auth_role = _sanitize_role(auth.get("role"))
        client_skill_progress_hints = _build_client_skill_progress_hints(custom_manifests)
        connection_catalog = {
            kind: sorted(list(getattr(settings.connections, kind, {}).keys()))
            for kind in CONNECTION_ADMIN_SPECS.keys()
            if isinstance(getattr(settings.connections, kind, {}), dict)
        }
        chat_command_entries, chat_command_group_titles, chat_toolbox_groups = build_chat_command_catalog(
            lang=lang,
            auth_role=auth_role,
            advanced_mode=bool(getattr(request.state, "can_access_advanced_config", False)),
            recall_templates=list(recall_templates),
            store_templates=list(store_templates),
            skill_trigger_hints=sorted(skill_trigger_hints, key=len, reverse=True),
            skill_toolbox_rows=sorted(
                skill_toolbox_rows,
                key=lambda row: (
                    str(row.get("label", "") or "").lower(),
                    str(row.get("insert", "") or "").lower(),
                ),
            ),
            connection_catalog=connection_catalog,
            recent_messages=[
                str(item.get("text", "")).strip()
                for item in chat_history[-8:]
                if isinstance(item, dict) and str(item.get("text", "")).strip()
            ],
        )
        response = TEMPLATES.TemplateResponse(
            request=request,
            name="chat.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "recall_templates": recall_templates,
                "store_templates": store_templates,
                "skill_trigger_hints": sorted(skill_trigger_hints, key=len, reverse=True),
                "skill_progress_hints": client_skill_progress_hints,
                "chat_command_entries": chat_command_entries,
                "chat_command_group_titles": chat_command_group_titles,
                "chat_toolbox_groups": chat_toolbox_groups,
                "active_memory_collection": active_collection,
                "active_session_collection": session_collection,
                "auto_memory_enabled": auto_memory_enabled,
                "active_memory_day": _current_memory_day(),
                "debug_mode": bool(settings.ui.debug_mode),
                "active_session_id": session_id,
                "auth_role": auth_role,
                "chat_history": chat_history,
            },
        )
        if not _request_cookie_value(request, SESSION_COOKIE):
            _set_response_cookie(
                response,
                request,
                SESSION_COOKIE,
                session_id,
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
        _set_response_cookie(
            response,
            request,
            AUTO_MEMORY_COOKIE,
            "1" if auto_memory_enabled else "0",
            max_age=60 * 60 * 24 * 365,
            secure=secure_cookie,
            httponly=False,
        )
        return response

    @app.get("/help", response_class=HTMLResponse)
    async def help_page(request: Request, doc: str = "home") -> HTMLResponse:
        username = _get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de").strip().lower()
        selected_doc = HELP_DOC_MAP.get(doc) or HELP_DOC_CATALOG[0]
        localized_help_path = _localized_doc_path(BASE_DIR, selected_doc["path"], lang)
        help_text = _read_doc_text(BASE_DIR, localized_help_path)
        help_sections = [
            {
                **group,
                "docs": [entry for entry in HELP_DOC_CATALOG if entry.get("group") == group["id"]],
            }
            for group in HELP_DOC_GROUPS
        ]
        return TEMPLATES.TemplateResponse(
            request=request,
            name="help.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "help_docs": HELP_DOC_CATALOG,
                "help_sections": help_sections,
                "selected_doc": selected_doc,
                "help_path": localized_help_path,
                "help_text": help_text,
                "help_html": _render_markdown_doc(help_text),
            },
        )

    def _build_update_control_payload(request: Request) -> dict[str, Any]:
        update_notice = str(request.query_params.get("notice", "") or "").strip().lower()
        update_control = {
            "visible": str(getattr(request.state, "auth_role", "") or "").strip().lower() == "admin",
            "configured": False,
            "reachable": False,
            "running": False,
            "status": "disabled",
            "status_visual": "warn",
            "last_result": "",
            "last_error": "",
            "current_step": "",
            "log_tail": [],
            "helper_error": "",
        }
        if update_control["visible"]:
            store = _get_secure_store()
            helper_config = resolve_update_helper_config(secure_store=store)
            update_control["configured"] = helper_config.enabled
            if helper_config.enabled:
                try:
                    helper_status = fetch_update_helper_status(helper_config)
                    update_control.update(helper_status)
                except RuntimeError as exc:
                    update_control["helper_error"] = str(exc)
                    update_control["status"] = "error"
                    update_control["status_visual"] = "error"
            update_control["status_visual"] = helper_status_visual(
                str(update_control.get("status", "") or ""),
                running=bool(update_control.get("running", False)),
                configured=bool(update_control.get("configured", False)),
                reachable=not bool(update_control.get("helper_error", "")),
                last_error=str(update_control.get("last_error", "") or update_control.get("helper_error", "") or ""),
            )
        if update_notice == "update_started" and not update_control["running"]:
            update_control["running"] = True
            update_control["status"] = "requested"
            update_control["status_visual"] = "warn"
        return update_control

    def _render_updates_running_page(
        request: Request,
        *,
        release_meta: dict[str, Any] | None = None,
        update_status: dict[str, Any] | None = None,
        update_control: dict[str, Any] | None = None,
    ) -> HTMLResponse:
        username = _get_username_from_request(request)
        release_payload = dict(release_meta or getattr(request.state, "release_meta", {}) or _read_release_meta(BASE_DIR))
        update_payload = dict(update_status or _get_update_status(str(release_payload.get("label", "") or ""), ttl_seconds=0))
        control_payload = dict(update_control or _build_update_control_payload(request))
        return TEMPLATES.TemplateResponse(
            request=request,
            name="updates_running.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "release_meta": release_payload,
                "update_status": update_payload,
                "update_control": control_payload,
            },
        )

    @app.get("/updates", response_class=HTMLResponse)
    async def updates_page(request: Request) -> HTMLResponse:
        username = _get_username_from_request(request)
        release_meta = dict(getattr(request.state, "release_meta", {}) or _read_release_meta(BASE_DIR))
        update_status = _get_update_status(str(release_meta.get("label", "") or ""), ttl_seconds=0)
        update_notice = str(request.query_params.get("notice", "") or "").strip().lower()
        update_error = str(request.query_params.get("error", "") or "").strip().lower()
        update_control = _build_update_control_payload(request)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="updates.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "release_meta": release_meta,
                "update_status": update_status,
                "update_control": update_control,
                "update_notice": update_notice,
                "update_error": update_error,
            },
        )

    @app.get("/updates/running", response_class=HTMLResponse)
    async def updates_running_page(request: Request) -> HTMLResponse:
        auth_role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
        if auth_role != "admin":
            return RedirectResponse(url="/updates", status_code=303)
        return _render_updates_running_page(request)

    @app.post("/updates/run")
    async def run_updates_from_ui(request: Request, csrf_token: str = Form("")) -> Response:  # noqa: ARG001
        wants_json = str(request.headers.get("x-requested-with", "") or "").strip() == "ARIA-Update-UI"
        auth_role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
        if auth_role != "admin":
            if wants_json:
                return JSONResponse(status_code=403, content={"detail": "Admin rights required."})
            return RedirectResponse(url="/updates?error=no_admin", status_code=303)
        store = _get_secure_store()
        helper_config = resolve_update_helper_config(secure_store=store)
        if not helper_config.enabled:
            if wants_json:
                return JSONResponse(status_code=409, content={"detail": "GUI update helper is not enabled."})
            return RedirectResponse(url="/updates?error=update_helper_disabled", status_code=303)
        try:
            result = trigger_update_helper_run(helper_config)
        except RuntimeError as exc:
            error_text = str(exc).strip().lower()
            if "already running" in error_text:
                if wants_json:
                    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "already_running"})
                return RedirectResponse(url="/updates?error=update_running", status_code=303)
            if wants_json:
                return JSONResponse(status_code=502, content={"detail": str(exc)})
            return RedirectResponse(url=f"/updates?error={quote_plus(str(exc))}", status_code=303)
        status = str(result.get("status", "") or "").strip().lower()
        if wants_json:
            return JSONResponse(
                content={
                    "status": status or "accepted",
                    "message": "Update helper accepted the run." if status == "accepted" else "Update request forwarded.",
                    "reload_url": "/updates",
                    "status_url": "/updates/status",
                    "running_url": "/updates/running",
                }
            )
        if status == "accepted":
            release_meta = dict(getattr(request.state, "release_meta", {}) or _read_release_meta(BASE_DIR))
            update_status = _get_update_status(str(release_meta.get("label", "") or ""), ttl_seconds=0)
            update_control = _build_update_control_payload(request)
            update_control["running"] = True
            update_control["status"] = "requested"
            update_control["status_visual"] = "warn"
            return _render_updates_running_page(
                request,
                release_meta=release_meta,
                update_status=update_status,
                update_control=update_control,
            )
        return RedirectResponse(url="/updates?notice=update_requested", status_code=303)

    @app.get("/updates/status")
    async def updates_status_api(request: Request) -> JSONResponse:
        auth_role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
        if auth_role != "admin":
            return JSONResponse(status_code=403, content={"detail": "Admin rights required."})
        store = _get_secure_store()
        helper_config = resolve_update_helper_config(secure_store=store)
        if not helper_config.enabled:
            return JSONResponse(
                content={
                    "configured": False,
                    "reachable": False,
                    "running": False,
                    "status": "disabled",
                    "visual_status": "warn",
                    "current_step": "",
                    "last_started_at": "",
                    "last_finished_at": "",
                    "last_result": "",
                    "last_error": "",
                    "log_tail": [],
                }
            )
        try:
            payload = fetch_update_helper_status(helper_config)
        except RuntimeError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "configured": True,
                    "reachable": False,
                    "running": False,
                    "status": "error",
                    "visual_status": "error",
                    "current_step": "",
                    "last_started_at": "",
                    "last_finished_at": "",
                    "last_result": "",
                    "last_error": str(exc),
                    "helper_error": str(exc),
                    "log_tail": [],
                },
            )
        payload["configured"] = True
        payload["visual_status"] = helper_status_visual(
            str(payload.get("status", "") or ""),
            running=bool(payload.get("running", False)),
            configured=True,
            reachable=True,
            last_error=str(payload.get("last_error", "") or payload.get("helper_error", "") or ""),
        )
        return JSONResponse(content=payload)

    @app.get("/product-info", response_class=HTMLResponse)
    async def product_info_page(request: Request, doc: str = "overview") -> HTMLResponse:
        username = _get_username_from_request(request)
        selected_doc = PRODUCT_DOC_MAP.get(doc) or PRODUCT_DOC_CATALOG[0]
        doc_path = BASE_DIR / selected_doc["path"]
        doc_text = ""
        if doc_path.exists():
            try:
                doc_text = doc_path.read_text(encoding="utf-8")
            except OSError:
                doc_text = ""
        return TEMPLATES.TemplateResponse(
            request=request,
            name="product_info.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "product_docs": PRODUCT_DOC_CATALOG,
                "selected_doc": selected_doc,
                "doc_path": selected_doc["path"],
                "doc_text": doc_text,
            },
        )

    @app.get("/product-info/assets/{asset_name}")
    async def product_info_asset(asset_name: str) -> Response:
        asset_path = PRODUCT_INFO_ASSET_MAP.get(asset_name)
        if not asset_path or not asset_path.exists():
            return Response(status_code=404)
        try:
            return Response(
                content=asset_path.read_text(encoding="utf-8"),
                media_type="image/svg+xml; charset=utf-8",
            )
        except OSError:
            return Response(status_code=404)

    register_stats_routes(
        app,
        templates=TEMPLATES,
        get_pipeline=lambda: pipeline,
        get_settings=lambda: settings,
        get_username_from_request=_get_username_from_request,
        resolve_pricing_entry=_resolve_pricing_entry,
        get_runtime_preflight=_get_runtime_preflight_data,
        get_secure_store=_get_secure_store,
    )
    register_activities_routes(
        app,
        templates=TEMPLATES,
        get_pipeline=lambda: pipeline,
        get_settings=lambda: settings,
        get_username_from_request=_get_username_from_request,
    )

    register_skills_routes(
        app,
        templates=TEMPLATES,
        get_settings=lambda: settings,
        get_username_from_request=_get_username_from_request,
        get_auth_session_from_request=_get_auth_session_from_request,
        sanitize_role=_sanitize_role,
        read_raw_config=_read_raw_config,
        write_raw_config=_write_raw_config,
        reload_runtime=_reload_runtime,
        translate=lambda lang, key, default: I18N.t(lang, key, default),
        localize_custom_skill_description=_localize_custom_skill_description,
        format_skill_routing_info=_format_skill_routing_info,
        suggest_skill_keywords_with_llm=_suggest_skill_keywords_with_llm,
        daily_time_to_cron=_daily_time_to_cron,
        daily_time_from_cron=_daily_time_from_cron,
    )

    register_memories_routes(
        app,
        templates=TEMPLATES,
        get_settings=lambda: settings,
        get_pipeline=lambda: pipeline,
        get_username_from_request=_get_username_from_request,
        get_auth_session_from_request=_get_auth_session_from_request,
        sanitize_role=_sanitize_role,
        qdrant_overview=_qdrant_overview,
        qdrant_dashboard_url=_qdrant_dashboard_url,
        parse_collection_day_suffix=_parse_collection_day_suffix,
        sanitize_collection_name=_sanitize_collection_name,
        default_memory_collection_for_user=_default_memory_collection_for_user,
        get_effective_memory_collection=_get_effective_memory_collection,
        is_auto_memory_enabled=_is_auto_memory_enabled,
        read_raw_config=_read_raw_config,
        write_raw_config=_write_raw_config,
        reload_runtime=_reload_runtime,
        resolve_prompt_file=_resolve_prompt_file,
        get_secure_store=_get_secure_store,
        memory_collection_cookie=MEMORY_COLLECTION_COOKIE,
        auto_memory_cookie=AUTO_MEMORY_COOKIE,
    )

    register_config_routes(
        app,
        ConfigRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            error_interpreter_path=ERROR_INTERPRETER_PATH,
            llm_provider_presets=LLM_PROVIDER_PRESETS,
            embedding_provider_presets=EMBEDDING_PROVIDER_PRESETS,
            auth_cookie=AUTH_COOKIE,
            lang_cookie=LANG_COOKIE,
            username_cookie=USERNAME_COOKIE,
            memory_collection_cookie=MEMORY_COLLECTION_COOKIE,
            auth_session_max_age_seconds=AUTH_SESSION_MAX_AGE_SECONDS,
            get_settings=lambda: settings,
            get_pipeline=lambda: pipeline,
            get_username_from_request=_get_username_from_request,
            get_auth_session_from_request=_get_auth_session_from_request,
            sanitize_role=_sanitize_role,
            sanitize_username=_sanitize_username,
            sanitize_connection_name=_sanitize_connection_name,
            sanitize_skill_id=_sanitize_skill_id,
            sanitize_profile_name=_sanitize_profile_name,
            default_memory_collection_for_user=_default_memory_collection_for_user,
            encode_auth_session=_encode_auth_session,
            get_auth_manager=_get_auth_manager,
            active_admin_count=_active_admin_count,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            read_error_interpreter_raw=_read_error_interpreter_raw,
            parse_lines=_parse_lines,
            is_ollama_model=_is_ollama_model,
            resolve_prompt_file=_resolve_prompt_file,
            list_prompt_files=_list_prompt_files,
            list_editable_files=_list_editable_files,
            resolve_edit_file=_resolve_edit_file,
            list_file_editor_entries=_list_file_editor_entries,
            resolve_file_editor_file=_resolve_file_editor_file,
            load_models_from_api_base=_load_models_from_api_base,
            get_profiles=_get_profiles,
            get_active_profile_name=_get_active_profile_name,
            set_active_profile=_set_active_profile,
            get_secure_store=_get_secure_store,
            lang_flag=_lang_flag,
            lang_label=_lang_label,
            available_languages=I18N.available_languages,
            resolve_lang=lambda code, default_lang: I18N.resolve_lang(code, default_lang=default_lang),
            clear_i18n_cache=I18N.clear_cache,
            load_custom_skill_manifests=_load_custom_skill_manifests,
            custom_skill_file=_custom_skill_file,
            save_custom_skill_manifest=_save_custom_skill_manifest,
            refresh_skill_trigger_index=_refresh_skill_trigger_index,
            format_skill_routing_info=_format_skill_routing_info,
            suggest_skill_keywords_with_llm=_suggest_skill_keywords_with_llm,
        ),
    )

    @app.post("/set-username")
    async def set_username(request: Request, username: str = Form(...)) -> RedirectResponse:
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        auth = _get_auth_session_from_request(request)
        clean_username = _sanitize_username(username)
        if auth:
            clean_username = _sanitize_username(auth.get("username"))
        response = RedirectResponse(url="/", status_code=303)
        session_id = uuid4().hex[:12]
        if clean_username:
            _set_response_cookie(
                response,
                request,
                USERNAME_COOKIE,
                clean_username,
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            _set_response_cookie(
                response,
                request,
                MEMORY_COLLECTION_COOKIE,
                _default_memory_collection_for_user(clean_username),
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            _set_response_cookie(
                response,
                request,
                SESSION_COOKIE,
                session_id,
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
        return response

    @app.post("/set-auto-memory")
    async def set_auto_memory(request: Request, enabled: str = Form("0"), next_path: str = Form("/")) -> RedirectResponse:
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        target = "/" if not str(next_path).startswith("/") else str(next_path)
        try:
            active = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
            raw = _read_raw_config()
            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            raw["auto_memory"]["enabled"] = active
            _write_raw_config(raw)
            _reload_runtime()
            response = RedirectResponse(url=target, status_code=303)
            _set_response_cookie(
                response,
                request,
                AUTO_MEMORY_COOKIE,
                "1" if active else "0",
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/memories/config?error={quote_plus(str(exc))}", status_code=303)

    @app.post("/chat", response_class=HTMLResponse)
    async def chat(request: Request, message: str = Form(...)) -> HTMLResponse:
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        clean_message = message.strip()
        if not clean_message:
            return HTMLResponse("", status_code=204)
        username = _get_username_from_request(request)
        session_id = _ensure_session_id(request)
        auto_memory_enabled = _is_auto_memory_enabled(request)
        memory_collection = _get_effective_memory_collection(request, username or "web")
        session_collection = _session_memory_collection_for_user(username or "web", session_id)
        if not username:
            response = TEMPLATES.TemplateResponse(
                request=request,
                name="_chat_messages.html",
                context={
                    "user_message": clean_message,
                    "assistant_message": "Bitte gib zuerst deinen Namen ein, damit ich dein Memory korrekt zuordnen kann.",
                    "badge_icon": "⚠",
                    "badge_intent": "missing_username",
                    "badge_tokens": 0,
                    "badge_cost_usd": "n/a",
                    "badge_duration": "0.0",
                    "badge_details": [],
                },
            )
            if not _request_cookie_value(request, SESSION_COOKIE):
                _set_response_cookie(
                    response,
                    request,
                    SESSION_COOKIE,
                    session_id,
                    max_age=60 * 60 * 24 * 7,
                    secure=secure_cookie,
                    httponly=False,
                )
            return response

        icon = "⚠"
        intent_label = "error"
        total_tokens = 0
        cost_usd = "n/a"
        duration_s = "0.0"
        badge_details: list[str] = []
        forget_cookie_value = _request_cookie_value(request, FORGET_PENDING_COOKIE)
        forget_pending = chat_admin_actions._decode_forget_pending(
            forget_cookie_value,
            signing_secret=FORGET_SIGNING_SECRET,
            sanitize_username=_sanitize_username,
        )
        safe_fix_cookie_value = _request_cookie_value(request, SAFE_FIX_PENDING_COOKIE)
        safe_fix_pending = chat_admin_actions._decode_safe_fix_pending(
            safe_fix_cookie_value,
            signing_secret=FORGET_SIGNING_SECRET,
            sanitize_username=_sanitize_username,
        )
        connection_delete_cookie_value = _request_cookie_value(request, CONNECTION_DELETE_PENDING_COOKIE)
        connection_delete_pending = chat_admin_actions._decode_connection_delete_pending(
            connection_delete_cookie_value,
            signing_secret=FORGET_SIGNING_SECRET,
            sanitize_username=_sanitize_username,
            sanitize_connection_name=_sanitize_connection_name,
            max_age_seconds=CONNECTION_PENDING_MAX_AGE_SECONDS,
        )
        connection_create_cookie_value = _request_cookie_value(request, CONNECTION_CREATE_PENDING_COOKIE)
        connection_create_pending = chat_admin_actions._decode_connection_create_pending(
            connection_create_cookie_value,
            signing_secret=FORGET_SIGNING_SECRET,
            sanitize_username=_sanitize_username,
            max_age_seconds=CONNECTION_PENDING_MAX_AGE_SECONDS,
        )
        connection_update_cookie_value = _request_cookie_value(request, CONNECTION_UPDATE_PENDING_COOKIE)
        connection_update_pending = chat_admin_actions._decode_connection_update_pending(
            connection_update_cookie_value,
            signing_secret=FORGET_SIGNING_SECRET,
            sanitize_username=_sanitize_username,
            max_age_seconds=CONNECTION_PENDING_MAX_AGE_SECONDS,
        )
        update_cookie_value = _request_cookie_value(request, UPDATE_PENDING_COOKIE)
        update_pending = chat_admin_actions._decode_update_pending(
            update_cookie_value,
            signing_secret=FORGET_SIGNING_SECRET,
            sanitize_username=_sanitize_username,
            max_age_seconds=CONNECTION_PENDING_MAX_AGE_SECONDS,
        )
        forget_decision = pipeline.classify_routing(
            clean_message,
            language=str(getattr(request.state, "lang", "de") or "de"),
        )
        safe_fix_confirm_token = chat_admin_actions._parse_safe_fix_confirm_token(clean_message)
        connection_delete_confirm_token = chat_admin_actions._parse_connection_delete_confirm_token(clean_message)
        connection_delete_request = chat_admin_actions._parse_connection_delete_request(clean_message)
        connection_create_confirm_token = chat_admin_actions._parse_connection_create_confirm_token(clean_message)
        connection_create_request = chat_admin_actions._parse_connection_create_request(clean_message)
        connection_update_confirm_token = chat_admin_actions._parse_connection_update_confirm_token(clean_message)
        connection_update_request = chat_admin_actions._parse_connection_update_request(clean_message)
        update_confirm_token = chat_admin_actions._parse_update_confirm_token(clean_message)
        update_run_request = chat_admin_actions._parse_update_run_request(clean_message)
        update_status_request = chat_admin_actions._parse_update_status_request(clean_message)
        backup_export_request = chat_admin_actions._parse_backup_export_request(clean_message)
        backup_import_request = chat_admin_actions._parse_backup_import_request(clean_message)
        stats_request = chat_admin_actions._parse_stats_request(clean_message)
        activities_request = chat_admin_actions._parse_activities_request(clean_message)
        auth_role = _sanitize_role(getattr(request.state, "auth_role", ""))
        advanced_mode = bool(getattr(request.state, "can_access_advanced_config", False))

        assistant_text = ""
        set_forget_cookie: str | None = None
        clear_forget_cookie = False
        set_safe_fix_cookie: str | None = None
        clear_safe_fix_cookie = False
        set_connection_delete_cookie: str | None = None
        clear_connection_delete_cookie = False
        set_connection_create_cookie: str | None = None
        clear_connection_create_cookie = False
        set_connection_update_cookie: str | None = None
        clear_connection_update_cookie = False
        set_update_cookie: str | None = None
        clear_update_cookie = False

        if safe_fix_confirm_token and safe_fix_pending:
            pending_user = str(safe_fix_pending.get("user_id", "")).strip()
            pending_token = str(safe_fix_pending.get("token", "")).strip().lower()
            pending_fixes = safe_fix_pending.get("fixes", [])
            if (
                pending_user == username
                and pending_token
                and pending_token == safe_fix_confirm_token.lower()
                and isinstance(pending_fixes, list)
                and pending_fixes
            ):
                fix_result = await pipeline.execute_safe_fix_plan(
                    pending_fixes,
                    language=str(getattr(request.state, "lang", "de") or "de"),
                )
                assistant_text = fix_result.content or "Safe-Fix abgeschlossen."
                icon = "🛠"
                intent_label = "safe_fix_apply"
                if not fix_result.success:
                    icon = "⚠"
                    warning = _friendly_error_text([fix_result.error]) if fix_result.error else ""
                    if warning:
                        assistant_text = f"{assistant_text}\n\nHinweis: {warning}"
                await asyncio.to_thread(
                    send_discord_alerts,
                    settings,
                    category="safe_fix",
                    title="Safe-Fix ausgeführt",
                    lines=[
                        f"User: {username}",
                        f"Ergebnis: {'ok' if fix_result.success else 'fehler'}",
                        f"Text: {assistant_text[:300]}",
                    ],
                    level="info" if fix_result.success else "warn",
                )
                clear_safe_fix_cookie = True
            else:
                assistant_text = "Der Safe-Fix Bestätigungscode ist ungültig oder abgelaufen."
                icon = "⚠"
                intent_label = "safe_fix_invalid_token"
                clear_safe_fix_cookie = True
        elif connection_delete_confirm_token and connection_delete_pending:
            pending_user = str(connection_delete_pending.get("user_id", "")).strip()
            pending_token = str(connection_delete_pending.get("token", "")).strip().lower()
            pending_kind = str(connection_delete_pending.get("kind", "")).strip().lower()
            pending_ref = str(connection_delete_pending.get("ref", "")).strip()
            if auth_role != "admin":
                assistant_text = "Connections im Chat verwalten ist aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "connection_delete_denied"
                clear_connection_delete_cookie = True
            elif (
                pending_user == username
                and pending_token
                and pending_token == connection_delete_confirm_token.lower()
                and pending_kind
                and pending_ref
            ):
                try:
                    delete_result = delete_connection_profile(BASE_DIR, pending_kind, pending_ref)
                    _reload_runtime()
                    assistant_text = delete_result.get("success_message") or f"Connection-Profil `{pending_ref}` gelöscht."
                    assistant_text += f"\n\nGelöscht: `{pending_kind}` / `{pending_ref}`"
                    icon = "🗑"
                    intent_label = "connection_delete"
                    clear_connection_delete_cookie = True
                except Exception as exc:
                    detail = friendly_connection_admin_error_text(exc, kind=pending_kind, action="delete")
                    assistant_text = f"Connection-Löschen fehlgeschlagen: {detail}"
                    icon = "⚠"
                    intent_label = "connection_delete_error"
            else:
                assistant_text = "Der Bestätigungscode für das Connection-Löschen ist ungültig oder abgelaufen."
                icon = "⚠"
                intent_label = "connection_delete_invalid_token"
                clear_connection_delete_cookie = True
        elif connection_delete_request:
            if auth_role != "admin":
                assistant_text = "Connections im Chat verwalten ist aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "connection_delete_denied"
                clear_connection_delete_cookie = True
            else:
                try:
                    kind_hint, ref_hint = connection_delete_request
                    catalog = list_connection_refs(BASE_DIR)
                    resolved_kind, resolved_ref = resolve_connection_target(catalog, ref_hint=ref_hint, kind_hint=kind_hint)
                    token = uuid4().hex[:8].lower()
                    set_connection_delete_cookie = chat_admin_actions._encode_connection_delete_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "kind": resolved_kind,
                            "ref": resolved_ref,
                        },
                        signing_secret=FORGET_SIGNING_SECRET,
                        sanitize_username=_sanitize_username,
                        sanitize_connection_name=_sanitize_connection_name,
                    )
                    assistant_text = (
                        f"Ich lösche das Profil `{resolved_ref}` vom Typ `{resolved_kind}` nicht blind.\n\n"
                        f"Zum Bestätigen sende: `bestätige verbindung löschen {token}`"
                    )
                    icon = "🗑"
                    intent_label = "connection_delete_pending"
                except Exception as exc:
                    detail = friendly_connection_admin_error_text(exc, kind=kind_hint, action="delete")
                    assistant_text = f"Connection-Löschen nicht vorbereitet: {detail}"
                    icon = "⚠"
                    intent_label = "connection_delete_error"
        elif connection_create_confirm_token and connection_create_pending:
            pending_user = str(connection_create_pending.get("user_id", "")).strip()
            pending_token = str(connection_create_pending.get("token", "")).strip().lower()
            pending_kind = str(connection_create_pending.get("kind", "")).strip().lower()
            pending_ref = str(connection_create_pending.get("ref", "")).strip()
            pending_payload = connection_create_pending.get("payload", {})
            if auth_role != "admin":
                assistant_text = "Connections im Chat verwalten ist aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "connection_create_denied"
                clear_connection_create_cookie = True
            elif (
                pending_user == username
                and pending_token
                and pending_token == connection_create_confirm_token.lower()
                and pending_kind
                and pending_ref
                and isinstance(pending_payload, dict)
            ):
                try:
                    create_result = create_connection_profile(BASE_DIR, pending_kind, pending_ref, pending_payload)
                    _reload_runtime()
                    assistant_text = create_result.get("success_message") or f"Connection-Profil `{pending_ref}` erstellt."
                    assistant_text += f"\n\nErstellt: `{pending_kind}` / `{pending_ref}`"
                    icon = "🧩"
                    intent_label = "connection_create"
                    clear_connection_create_cookie = True
                except Exception as exc:
                    detail = friendly_connection_admin_error_text(exc, kind=pending_kind, action="create")
                    assistant_text = f"Connection-Erstellen fehlgeschlagen: {detail}"
                    icon = "⚠"
                    intent_label = "connection_create_error"
            else:
                assistant_text = "Der Bestätigungscode für das Connection-Erstellen ist ungültig oder abgelaufen."
                icon = "⚠"
                intent_label = "connection_create_invalid_token"
                clear_connection_create_cookie = True
        elif connection_create_request:
            if auth_role != "admin":
                assistant_text = "Connections im Chat verwalten ist aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "connection_create_denied"
                clear_connection_create_cookie = True
            else:
                try:
                    kind = str(connection_create_request.get("kind", "")).strip().lower().replace("-", "_")
                    ref = sanitize_connection_ref(str(connection_create_request.get("ref", "")).strip())
                    payload = sanitize_connection_payload(kind, connection_create_request.get("payload", {}))
                    if not kind or not ref or not isinstance(payload, dict):
                        raise ValueError("Connection-Daten unvollständig.")
                    token = uuid4().hex[:8].lower()
                    set_connection_create_cookie = chat_admin_actions._encode_connection_create_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "kind": kind,
                            "ref": ref,
                            "payload": payload,
                        },
                        signing_secret=FORGET_SIGNING_SECRET,
                        sanitize_username=_sanitize_username,
                    )
                    summary_lines = [
                        f"Typ: `{kind}`",
                        f"Ref: `{ref}`",
                        *chat_admin_actions._format_connection_payload_summary(kind, payload),
                    ]
                    assistant_text = (
                        "Ich habe die neue Connection vorbereitet:\n\n- "
                        + "\n- ".join(summary_lines)
                        + f"\n\nZum Bestätigen sende: `bestätige verbindung erstellen {token}`"
                    )
                    icon = "🧩"
                    intent_label = "connection_create_pending"
                except Exception as exc:
                    detail = friendly_connection_admin_error_text(exc, kind=kind, action="create")
                    assistant_text = f"Connection-Erstellen nicht vorbereitet: {detail}"
                    icon = "⚠"
                    intent_label = "connection_create_error"
        elif connection_update_confirm_token and connection_update_pending:
            pending_user = str(connection_update_pending.get("user_id", "")).strip()
            pending_token = str(connection_update_pending.get("token", "")).strip().lower()
            pending_kind = str(connection_update_pending.get("kind", "")).strip().lower()
            pending_ref = str(connection_update_pending.get("ref", "")).strip()
            pending_payload = connection_update_pending.get("payload", {})
            if auth_role != "admin":
                assistant_text = "Connections im Chat verwalten ist aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "connection_update_denied"
                clear_connection_update_cookie = True
            elif (
                pending_user == username
                and pending_token
                and pending_token == connection_update_confirm_token.lower()
                and pending_kind
                and pending_ref
                and isinstance(pending_payload, dict)
            ):
                try:
                    update_result = update_connection_profile(BASE_DIR, pending_kind, pending_ref, pending_payload)
                    _reload_runtime()
                    assistant_text = update_result.get("success_message") or f"Connection-Profil `{pending_ref}` aktualisiert."
                    assistant_text += f"\n\nAktualisiert: `{pending_kind}` / `{pending_ref}`"
                    icon = "🛠"
                    intent_label = "connection_update"
                    clear_connection_update_cookie = True
                except Exception as exc:
                    detail = friendly_connection_admin_error_text(exc, kind=pending_kind, action="update")
                    assistant_text = f"Connection-Aktualisieren fehlgeschlagen: {detail}"
                    icon = "⚠"
                    intent_label = "connection_update_error"
            else:
                assistant_text = "Der Bestätigungscode für das Connection-Aktualisieren ist ungültig oder abgelaufen."
                icon = "⚠"
                intent_label = "connection_update_invalid_token"
                clear_connection_update_cookie = True
        elif connection_update_request:
            if auth_role != "admin":
                assistant_text = "Connections im Chat verwalten ist aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "connection_update_denied"
                clear_connection_update_cookie = True
            else:
                try:
                    kind = str(connection_update_request.get("kind", "")).strip().lower().replace("-", "_")
                    ref = sanitize_connection_ref(str(connection_update_request.get("ref", "")).strip())
                    payload = sanitize_connection_payload(kind, connection_update_request.get("payload", {}))
                    if not kind or not ref or not isinstance(payload, dict) or not payload:
                        raise ValueError("Connection-Daten unvollständig.")
                    token = uuid4().hex[:8].lower()
                    set_connection_update_cookie = chat_admin_actions._encode_connection_update_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "kind": kind,
                            "ref": ref,
                            "payload": payload,
                        },
                        signing_secret=FORGET_SIGNING_SECRET,
                        sanitize_username=_sanitize_username,
                    )
                    summary_lines = [
                        f"Typ: `{kind}`",
                        f"Ref: `{ref}`",
                        *chat_admin_actions._format_connection_payload_summary(kind, payload),
                    ]
                    assistant_text = (
                        "Ich habe die Connection-Aktualisierung vorbereitet:\n\n- "
                        + "\n- ".join(summary_lines)
                        + f"\n\nZum Bestätigen sende: `bestätige verbindung aktualisieren {token}`"
                    )
                    icon = "🛠"
                    intent_label = "connection_update_pending"
                except Exception as exc:
                    detail = friendly_connection_admin_error_text(exc, kind=kind, action="update")
                    assistant_text = f"Connection-Aktualisieren nicht vorbereitet: {detail}"
                    icon = "⚠"
                    intent_label = "connection_update_error"
        elif update_confirm_token and update_pending:
            pending_user = str(update_pending.get("user_id", "")).strip()
            pending_token = str(update_pending.get("token", "")).strip().lower()
            if auth_role != "admin":
                assistant_text = "Kontrollierte Updates per Chat sind aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "update_denied"
                clear_update_cookie = True
            elif pending_user == username and pending_token and pending_token == update_confirm_token.lower():
                helper_config = resolve_update_helper_config(secure_store=_get_secure_store())
                if not helper_config.enabled:
                    assistant_text = (
                        "Der GUI-Update-Helper ist für diese Instanz nicht aktiviert.\n\n"
                        "[Update-Seite öffnen](/updates)"
                    )
                    icon = "⚠"
                    intent_label = "update_disabled"
                else:
                    try:
                        result = trigger_update_helper_run(helper_config)
                        status = str(result.get("status", "")).strip().lower() or "accepted"
                        assistant_text = (
                            "Kontrolliertes Update gestartet.\n\n"
                            f"Status: `{status}`\n"
                            "[Live-Status öffnen](/updates/running)\n"
                            "[Update-Seite öffnen](/updates)"
                        )
                        icon = "🚀"
                        intent_label = "update_started"
                    except RuntimeError as exc:
                        assistant_text = (
                            f"Update konnte nicht gestartet werden: {exc}\n\n"
                            "[Update-Seite öffnen](/updates)"
                        )
                        icon = "⚠"
                        intent_label = "update_error"
                clear_update_cookie = True
            else:
                assistant_text = "Der Bestätigungscode für das Update ist ungültig oder abgelaufen."
                icon = "⚠"
                intent_label = "update_invalid_token"
                clear_update_cookie = True
        elif update_run_request:
            if auth_role != "admin":
                assistant_text = "Kontrollierte Updates per Chat sind aktuell nur für Admins erlaubt."
                icon = "⚠"
                intent_label = "update_denied"
                clear_update_cookie = True
            else:
                token = uuid4().hex[:8].lower()
                set_update_cookie = chat_admin_actions._encode_update_pending(
                    {"token": token, "user_id": username},
                    signing_secret=FORGET_SIGNING_SECRET,
                    sanitize_username=_sanitize_username,
                )
                assistant_text = (
                    "Ich starte das Update nicht blind.\n\n"
                    f"Zum Bestätigen sende: `bestätige update {token}`\n\n"
                    "[Update-Seite öffnen](/updates)"
                )
                icon = "🚀"
                intent_label = "update_pending"
        elif update_status_request:
            if auth_role != "admin":
                assistant_text = "[Update-Seite öffnen](/updates)"
                icon = "🩺"
                intent_label = "update_page"
            else:
                helper_config = resolve_update_helper_config(secure_store=_get_secure_store())
                if not helper_config.enabled:
                    assistant_text = (
                        "Der GUI-Update-Helper ist aktuell nicht aktiviert.\n\n"
                        "[Update-Seite öffnen](/updates)"
                    )
                    icon = "⚠"
                    intent_label = "update_disabled"
                else:
                    try:
                        helper_status = fetch_update_helper_status(helper_config)
                        visual = helper_status_visual(
                            str(helper_status.get("status", "") or ""),
                            running=bool(helper_status.get("running", False)),
                            configured=True,
                            reachable=True,
                            last_error=str(helper_status.get("last_error", "") or helper_status.get("helper_error", "") or ""),
                        )
                        lamp = {"ok": "🟢", "warn": "🟡", "error": "🔴"}.get(visual, "🟡")
                        lines = [
                            f"Update-Helper: {lamp} `{str(helper_status.get('status', 'unknown') or 'unknown')}`",
                        ]
                        if str(helper_status.get("current_step", "")).strip():
                            lines.append(f"Aktueller Schritt: {helper_status['current_step']}")
                        if str(helper_status.get("last_result", "")).strip():
                            lines.append(f"Letztes Ergebnis: {helper_status['last_result']}")
                        if str(helper_status.get("last_error", "")).strip():
                            lines.append(f"Letzter Fehler: {helper_status['last_error']}")
                        lines.append("[Update-Seite öffnen](/updates)")
                        if bool(helper_status.get("running", False)):
                            lines.append("[Live-Status öffnen](/updates/running)")
                        assistant_text = "\n".join(lines)
                        icon = "🩺"
                        intent_label = "update_status"
                    except RuntimeError as exc:
                        assistant_text = (
                            f"Update-Helper nicht erreichbar: {exc}\n\n"
                            "[Update-Seite öffnen](/updates)"
                        )
                        icon = "⚠"
                        intent_label = "update_error"
        elif backup_export_request:
            if not advanced_mode:
                assistant_text = "Config-Backups per Chat brauchen aktuell Admin Mode.\n\n[Backup-Seite öffnen](/config/backup)"
                icon = "⚠"
                intent_label = "backup_denied"
            else:
                raw = _read_raw_config()
                payload = build_config_backup_payload(
                    base_dir=BASE_DIR,
                    raw_config=raw,
                    secure_store=_get_secure_store(raw),
                    error_interpreter_path=BASE_DIR / "config" / "error_interpreter.yaml",
                )
                summary = summarize_config_backup_payload(payload)
                assistant_text = (
                    "Config-Backup ist bereit.\n\n"
                    f"- Secrets: `{summary.get('secret_count', 0)}`\n"
                    f"- Benutzer: `{summary.get('user_count', 0)}`\n"
                    f"- Custom Skills: `{summary.get('custom_skill_count', 0)}`\n"
                    f"- Prompt-Dateien: `{summary.get('prompt_file_count', 0)}`\n\n"
                    "Connections werden über `config.yaml` plus Secure-Store-Secrets mitgesichert. "
                    "Lokale SSH-Key-Dateien bleiben bewusst außerhalb des Backups.\n\n"
                    "[Config-Backup herunterladen](/config/backup/export)\n"
                    "[Backup-Seite öffnen](/config/backup)"
                )
                icon = "📦"
                intent_label = "backup_export"
        elif backup_import_request:
            if not advanced_mode:
                assistant_text = "Config-Backups wiederherstellen braucht aktuell Admin Mode.\n\n[Backup-Seite öffnen](/config/backup)"
                icon = "⚠"
                intent_label = "backup_denied"
            else:
                assistant_text = (
                    "Den Config-Backup-Import führe ich aktuell nicht blind im Chat aus, weil dafür eine Datei hochgeladen werden muss.\n\n"
                    "[Backup-Seite öffnen](/config/backup)"
                )
                icon = "♻️"
                intent_label = "backup_import"
        elif stats_request:
            assistant_text = "Hier sind die Stats.\n\n[Stats öffnen](/stats)"
            icon = "📊"
            intent_label = "stats"
        elif activities_request:
            assistant_text = "Hier sind Aktivitäten & Runs.\n\n[Aktivitäten öffnen](/activities)"
            icon = "🧾"
            intent_label = "activities"
        elif "memory_forget" in forget_decision.intents and pipeline.memory_skill:
            confirm_token = chat_admin_actions._parse_forget_confirm_token(clean_message)
            if confirm_token and forget_pending:
                pending_user = str(forget_pending.get("user_id", "")).strip()
                pending_token = str(forget_pending.get("token", "")).strip().lower()
                pending_candidates = forget_pending.get("candidates", [])
                if (
                    pending_user == username
                    and pending_token
                    and pending_token == confirm_token.lower()
                    and isinstance(pending_candidates, list)
                    and pending_candidates
                ):
                    forget_result = await pipeline.memory_skill.execute(
                        query="",
                        params={
                            "action": "forget_apply",
                            "user_id": username,
                            "candidates": pending_candidates,
                        },
                    )
                    assistant_text = forget_result.content or "Löschen abgeschlossen."
                    if forget_result.success:
                        icon = "🧹"
                        intent_label = "memory_forget"
                    else:
                        friendly = _friendly_error_text([forget_result.error])
                        assistant_text = friendly or "Löschen fehlgeschlagen."
                        icon = "⚠"
                        intent_label = "memory_error"
                    clear_forget_cookie = True
                else:
                    assistant_text = "Der Bestätigungscode ist ungültig oder abgelaufen. Bitte 'Vergiss ...' erneut senden."
                    icon = "⚠"
                    intent_label = "memory_forget"
                    clear_forget_cookie = True
            else:
                forget_query = chat_admin_actions._parse_forget_query(clean_message)
                forget_preview = await pipeline.memory_skill.execute(
                    query=forget_query,
                    params={
                        "action": "forget_preview",
                        "user_id": username,
                        "threshold": 0.75,
                        "max_hits": 5,
                    },
                )
                candidates = (forget_preview.metadata or {}).get("forget_candidates", [])
                if not forget_preview.success:
                    assistant_text = _friendly_error_text([forget_preview.error]) or "Memory-Vorschau fehlgeschlagen."
                    icon = "⚠"
                    intent_label = "memory_error"
                    clear_forget_cookie = True
                elif isinstance(candidates, list) and candidates:
                    token = uuid4().hex[:8].lower()
                    assistant_text = (
                        f"{forget_preview.content}\n\n"
                        f"Zum Löschen bestätige mit: 'bestätige {token}'"
                    )
                    set_forget_cookie = chat_admin_actions._encode_forget_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "candidates": candidates,
                        },
                        signing_secret=FORGET_SIGNING_SECRET,
                        sanitize_username=_sanitize_username,
                        sanitize_collection_name=_sanitize_collection_name,
                    )
                    icon = "🧹"
                    intent_label = "memory_forget_pending"
                else:
                    assistant_text = forget_preview.content or "Ich habe nichts Passendes zum Vergessen gefunden."
                    icon = "🧹"
                    intent_label = "memory_forget"
                    clear_forget_cookie = True
        else:
            result = None
            badge_details: list[str] = []
            try:
                result = await pipeline.process(
                    clean_message,
                    user_id=username,
                    source="web",
                    language=str(getattr(request.state, "lang", "") or ""),
                    memory_collection=memory_collection,
                    session_collection=session_collection,
                    auto_memory_enabled=auto_memory_enabled,
                )
                assistant_text = result.text or "Ich habe gerade keine Antwort erzeugt."
                icon, intent_label = _intent_badge(result.intents, result.skill_errors)
                total_tokens = int(result.usage.get("total_tokens", 0) or 0)
                if result.total_cost_usd is not None:
                    cost_usd = f"${result.total_cost_usd:.6f}"
                duration_s = f"{result.duration_ms / 1000:.1f}"
                badge_details = list(result.detail_lines)
                warning = _friendly_error_text(result.skill_errors)
                if warning:
                    assistant_text = f"{assistant_text}\n\nHinweis: {warning}"
                if result.skill_errors:
                    discord_error_text = _discord_alert_error_lines(result.skill_errors)
                    await asyncio.to_thread(
                        send_discord_alerts,
                        settings,
                        category="skill_errors",
                        title="Skill-Fehler erkannt",
                        lines=[
                            f"User: {username}",
                            f"Intents: {', '.join(result.intents) or '-'}",
                            f"Fehler: {discord_error_text or '-'}",
                        ],
                        level="warn",
                    )
                if isinstance(result.safe_fix_plan, list) and result.safe_fix_plan:
                    token = uuid4().hex[:8].lower()
                    set_safe_fix_cookie = chat_admin_actions._encode_safe_fix_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "fixes": result.safe_fix_plan,
                        },
                        signing_secret=FORGET_SIGNING_SECRET,
                        sanitize_username=_sanitize_username,
                        sanitize_connection_name=_sanitize_connection_name,
                    )
                    assistant_text = (
                        f"{assistant_text}\n\n"
                        f"Safe-Fix bereit. Bestätige mit: 'bestätige fix {token}'"
                    )
                    await asyncio.to_thread(
                        send_discord_alerts,
                        settings,
                        category="safe_fix",
                        title="Safe-Fix bereit",
                        lines=[
                            f"User: {username}",
                            f"Token: {token}",
                            f"Intents: {', '.join(result.intents) or '-'}",
                            f"Text: {assistant_text[:300]}",
                        ],
                        level="warn",
                    )
                    intent_label = "safe_fix_pending"
                    icon = "🛠"
            except (PromptLoadError, LLMClientError, ValueError) as exc:
                assistant_text = f"Fehler: {exc}"
                badge_details = []

        response = TEMPLATES.TemplateResponse(
            request=request,
            name="_chat_messages.html",
            context={
                "user_message": clean_message,
                "assistant_message": assistant_text,
                "badge_icon": icon,
                "badge_intent": intent_label,
                "badge_tokens": total_tokens,
                "badge_cost_usd": cost_usd,
                "badge_duration": duration_s,
                "badge_details": badge_details,
            },
        )
        if username and assistant_text:
            chat_history_store.append_exchange(
                username,
                user_message=clean_message,
                assistant_message=assistant_text,
                badge_icon=icon,
                badge_intent=intent_label,
                badge_tokens=total_tokens,
                badge_cost_usd=cost_usd,
                badge_duration=duration_s,
                badge_details=badge_details,
            )
        if not _request_cookie_value(request, SESSION_COOKIE):
            _set_response_cookie(
                response,
                request,
                SESSION_COOKIE,
                session_id,
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
        if clear_forget_cookie:
            _delete_response_cookie(response, request, FORGET_PENDING_COOKIE)
        elif set_forget_cookie:
            _set_response_cookie(
                response,
                request,
                FORGET_PENDING_COOKIE,
                set_forget_cookie,
                max_age=60 * 10,
                secure=secure_cookie,
                httponly=False,
            )
        if clear_safe_fix_cookie:
            _delete_response_cookie(response, request, SAFE_FIX_PENDING_COOKIE)
        elif set_safe_fix_cookie:
            _set_response_cookie(
                response,
                request,
                SAFE_FIX_PENDING_COOKIE,
                set_safe_fix_cookie,
                max_age=60 * 15,
                secure=secure_cookie,
                httponly=False,
            )
        if clear_connection_delete_cookie:
            _delete_response_cookie(response, request, CONNECTION_DELETE_PENDING_COOKIE)
        elif set_connection_delete_cookie:
            _set_response_cookie(
                response,
                request,
                CONNECTION_DELETE_PENDING_COOKIE,
                set_connection_delete_cookie,
                max_age=60 * 10,
                secure=secure_cookie,
                httponly=False,
            )
        if clear_connection_create_cookie:
            _delete_response_cookie(response, request, CONNECTION_CREATE_PENDING_COOKIE)
        elif set_connection_create_cookie:
            _set_response_cookie(
                response,
                request,
                CONNECTION_CREATE_PENDING_COOKIE,
                set_connection_create_cookie,
                max_age=60 * 10,
                secure=secure_cookie,
                httponly=False,
            )
        if clear_connection_update_cookie:
            _delete_response_cookie(response, request, CONNECTION_UPDATE_PENDING_COOKIE)
        elif set_connection_update_cookie:
            _set_response_cookie(
                response,
                request,
                CONNECTION_UPDATE_PENDING_COOKIE,
                set_connection_update_cookie,
                max_age=60 * 10,
                secure=secure_cookie,
                httponly=False,
            )
        if clear_update_cookie:
            _delete_response_cookie(response, request, UPDATE_PENDING_COOKIE)
        elif set_update_cookie:
            _set_response_cookie(
                response,
                request,
                UPDATE_PENDING_COOKIE,
                set_update_cookie,
                max_age=60 * 10,
                secure=secure_cookie,
                httponly=False,
            )
        return response

    @app.post("/chat/history/clear")
    async def clear_chat_history(request: Request) -> Response:
        username = _get_username_from_request(request)
        if username:
            chat_history_store.clear_history(username)
            capability_context_store.clear_user(username)
        return Response(status_code=204)

    @app.exception_handler(ValueError)
    async def handle_config_error(request: Request, exc: ValueError) -> Response:
        return _exception_response(request, detail=str(exc), status_code=500)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> Response:
        LOGGER.exception("Unhandled request error on %s", request.url.path, exc_info=exc)
        return _exception_response(
            request,
            detail="Unerwarteter Fehler. Bitte erneut versuchen oder Logs prüfen.",
            status_code=500,
        )

    return app


app = _build_app()
