from __future__ import annotations

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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from aria.channels.api import register_api_routes
from aria.web.activities_routes import register_activities_routes
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
    CONNECTION_CREATE_SPECS,
    CONNECTION_UPDATE_SPECS,
    create_connection_profile,
    delete_connection_profile,
    friendly_connection_admin_error_text,
    list_connection_refs,
    resolve_connection_target,
    sanitize_connection_ref,
    update_connection_profile,
)
from aria.core.connection_catalog import (
    connection_chat_aliases,
    connection_chat_defaults,
    connection_chat_field_specs,
    connection_chat_primary_field,
    connection_example_ref,
    connection_field_labels,
    connection_field_specs,
    connection_chat_emoji,
    connection_icon_name,
    connection_insert_template,
    connection_kind_label,
    connection_summary_fields,
    connection_toolbox_keywords,
    sanitize_connection_payload,
    normalize_connection_kind,
)
from aria.core.config import (
    Settings,
    get_master_key,
    get_or_create_runtime_secret,
    load_settings,
    normalize_ui_background,
    normalize_ui_theme,
)
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
from aria.core.runtime_diagnostics import build_runtime_diagnostics
from aria.core.runtime_endpoint import request_is_secure


BASE_DIR = Path(__file__).resolve().parent.parent
CHAT_HISTORY_DIR = BASE_DIR / "data" / "chat_history"
CAPABILITY_CONTEXT_PATH = BASE_DIR / "data" / "runtime" / "capability_context.json"
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
AUTH_COOKIE = "aria_auth_session"
CSRF_COOKIE = "aria_csrf_token"
LANG_COOKIE = "aria_lang"
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
PRODUCT_INFO_ASSET_MAP = {
    "aria_schichten_architektur.svg": BASE_DIR / "docs" / "product" / "aria_schichten_architektur.svg",
    "aria_intelligentes_routing.svg": BASE_DIR / "docs" / "product" / "aria_intelligentes_routing.svg",
    "aria_modularitaet_persistenz.svg": BASE_DIR / "docs" / "product" / "aria_modularitaet_persistenz.svg",
}
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
ERROR_INTERPRETER_PATH = BASE_DIR / "config" / "error_interpreter.yaml"
FORGET_SIGNING_SECRET = ""
AUTH_SIGNING_SECRET = ""
AUTH_SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
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


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


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


def _toolbox_label(lang: str, key: str, default: str) -> str:
    return I18N.t(lang, f"chat.{key}", default)


def _chat_connection_kind_label(kind: str) -> str:
    return connection_kind_label(kind)


def _chat_connection_example_ref(kind: str, connection_catalog: dict[str, list[str]]) -> str:
    return connection_example_ref(kind, connection_catalog)


def _chat_connection_create_insert(kind: str, ref: str) -> str:
    return connection_insert_template(kind, "create", ref)


def _chat_connection_update_insert(kind: str, ref: str) -> str:
    return connection_insert_template(kind, "update", ref)


def _connection_toolbox_keywords(kind: str, refs: list[str]) -> list[str]:
    return connection_toolbox_keywords(kind, refs)


def _chat_connection_kind_icon(kind: str) -> str:
    return connection_chat_emoji(kind)


def _score_chat_command_entry(
    entry: dict[str, Any],
    *,
    recent_text: str,
) -> int:
    haystack = str(recent_text or "").strip().lower()
    if not haystack:
        return 0
    score = 0
    for keyword in entry.get("keywords", []):
        value = str(keyword or "").strip().lower()
        if not value or len(value) < 2:
            continue
        if value in haystack:
            score += 3 if len(value) >= 6 else 2
    label = str(entry.get("label", "")).strip().lower()
    hint = str(entry.get("hint", "")).strip().lower()
    if label and label in haystack:
        score += 2
    elif hint and hint in haystack:
        score += 1
    return score


def _build_suggested_toolbox_group(
    lang: str,
    entries: list[dict[str, Any]],
    recent_messages: list[str] | None,
) -> dict[str, Any] | None:
    recent_text = " \n".join(str(row or "").strip().lower() for row in (recent_messages or [])[-8:] if str(row or "").strip())
    if not recent_text:
        return None
    scored: list[tuple[int, dict[str, Any]]] = []
    seen_inserts: set[str] = set()
    for entry in entries:
        insert = str(entry.get("insert", "")).strip()
        if not insert:
            continue
        score = _score_chat_command_entry(entry, recent_text=recent_text)
        if score <= 0:
            continue
        if insert in seen_inserts:
            continue
        seen_inserts.add(insert)
        scored.append((score, entry))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], str(item[1].get("group", "")), str(item[1].get("label", ""))))
    return {
        "key": "suggested",
        "title": _toolbox_label(lang, "slash_suggested", "Passend jetzt"),
        "items": [row for _, row in scored[:5]],
    }


def _build_admin_chat_command_entries(lang: str, connection_catalog: dict[str, list[str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for kind in sorted(CONNECTION_CREATE_SPECS.keys()):
        label_kind = _chat_connection_kind_label(kind)
        example_ref = _chat_connection_example_ref(kind, connection_catalog)
        refs = connection_catalog.get(normalize_connection_kind(kind), [])
        entries.append(
            {
                "group": "admin",
                "kind": kind,
                "icon": _chat_connection_kind_icon(kind),
                "label": f"{_toolbox_label(lang, 'tool_create_connection', 'Verbindung erstellen')} · {label_kind}",
                "insert": _chat_connection_create_insert(kind, example_ref),
                "hint": _toolbox_label(
                    lang,
                    "tool_create_connection_hint",
                    "Erstellt eine einfache Connection per Chat mit Confirm-Step.",
                ),
                "keywords": _connection_toolbox_keywords(kind, refs),
            }
        )

    for kind in sorted(CONNECTION_UPDATE_SPECS.keys()):
        label_kind = _chat_connection_kind_label(kind)
        example_ref = _chat_connection_example_ref(kind, connection_catalog)
        refs = connection_catalog.get(normalize_connection_kind(kind), [])
        entries.append(
            {
                "group": "admin",
                "kind": kind,
                "icon": _chat_connection_kind_icon(kind),
                "label": f"{_toolbox_label(lang, 'tool_update_connection', 'Verbindung aktualisieren')} · {label_kind}",
                "insert": _chat_connection_update_insert(kind, example_ref),
                "hint": _toolbox_label(
                    lang,
                    "tool_update_connection_hint",
                    "Aktualisiert einfache Connections oder nur Metadaten per Chat.",
                ),
                "keywords": _connection_toolbox_keywords(kind, refs),
            }
        )

    delete_kind = ""
    delete_ref = ""
    for kind in sorted(connection_catalog.keys()):
        refs = connection_catalog.get(kind, [])
        if refs:
            delete_kind = kind
            delete_ref = refs[0]
            break
    if not delete_kind:
        delete_kind = "rss"
        delete_ref = _chat_connection_example_ref(delete_kind, connection_catalog)
    entries.append(
        {
            "group": "admin",
            "icon": _chat_connection_kind_icon(delete_kind),
            "kind": delete_kind,
            "label": f"{_toolbox_label(lang, 'tool_delete_connection', 'Verbindung löschen')} · {_chat_connection_kind_label(delete_kind)}",
            "insert": f"lösche {delete_kind} {delete_ref} ",
            "hint": _toolbox_label(
                lang,
                "tool_delete_connection_hint",
                "Löscht ein Connection-Profil mit Confirm-Step.",
            ),
            "keywords": _connection_toolbox_keywords(delete_kind, [delete_ref]),
        }
    )
    return entries


def _build_chat_command_catalog(
    *,
    lang: str,
    auth_role: str,
    recall_templates: list[str],
    store_templates: list[str],
    skill_trigger_hints: list[str],
    skill_toolbox_rows: list[dict[str, Any]] | None = None,
    connection_catalog: dict[str, list[str]] | None = None,
    recent_messages: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = [
        {
            "group": "commands",
            "icon": "⌨",
            "label": "/cls",
            "insert": "/cls",
            "hint": _toolbox_label(lang, "slash_cls_hint", "Lokalen Chatverlauf löschen"),
            "keywords": ["clear", "cls", "chat löschen", "verlauf löschen", "chat reset"],
        },
        {
            "group": "commands",
            "icon": "⌨",
            "label": "/clear",
            "insert": "/clear",
            "hint": _toolbox_label(lang, "slash_cls_hint", "Lokalen Chatverlauf löschen"),
            "keywords": ["clear", "cls", "chat löschen", "verlauf löschen", "chat reset"],
        },
    ]

    for item in recall_templates:
        value = str(item or "").strip()
        if not value:
            continue
        entries.append(
            {
                "group": "read",
                "icon": "📖",
                "label": _toolbox_label(lang, "slash_read_cmd", "/lesen"),
                "insert": value if value.endswith(" ") else value + " ",
                "hint": value,
                "keywords": [value, "lesen", "erinnern", "memory", "wissen"],
            }
        )
    for item in store_templates:
        value = str(item or "").strip()
        if not value:
            continue
        entries.append(
            {
                "group": "store",
                "icon": "💾",
                "label": _toolbox_label(lang, "slash_store_cmd", "/merken"),
                "insert": value if value.endswith(" ") else value + " ",
                "hint": value,
                "keywords": [value, "merken", "speichern", "memory", "wissen"],
            }
        )
    if skill_toolbox_rows:
        for row in skill_toolbox_rows[:40]:
            insert_text = str(row.get("insert", "") or "").strip()
            label = str(row.get("label", "") or "").strip()
            hint = str(row.get("hint", "") or "").strip()
            keywords = [str(item or "").strip().lower() for item in row.get("keywords", []) if str(item or "").strip()]
            if not insert_text:
                insert_text = label or hint
            if not label:
                label = insert_text or _toolbox_label(lang, "slash_skill_cmd", "/skill")
            if not hint:
                hint = insert_text or label
            if not insert_text:
                continue
            entries.append(
                {
                    "group": "skills",
                    "icon": "🧩",
                    "label": label,
                    "badge": _toolbox_label(lang, "slash_skill_cmd", "/skill"),
                    "insert": insert_text if insert_text.endswith(" ") else insert_text + " ",
                    "hint": hint,
                    "keywords": list(dict.fromkeys(keywords + [label.lower(), hint.lower(), insert_text.lower(), "skill", "automation", "aktion"])),
                }
            )
    else:
        for value in skill_trigger_hints[:40]:
            hint = str(value or "").strip()
            if not hint:
                continue
            entries.append(
                {
                    "group": "skills",
                    "icon": "🧩",
                    "label": hint,
                    "badge": _toolbox_label(lang, "slash_skill_cmd", "/skill"),
                    "insert": hint if hint.endswith(" ") else hint + " ",
                    "hint": _toolbox_label(lang, "slash_skill_cmd", "/skill"),
                    "keywords": [hint, "skill", "automation", "aktion"],
                }
            )

    if auth_role == "admin":
        entries.extend(_build_admin_chat_command_entries(lang, connection_catalog or {}))

    group_titles = {
        "suggested": _toolbox_label(lang, "slash_suggested", "Passend jetzt"),
        "commands": _toolbox_label(lang, "slash_commands", "Commands"),
        "read": _toolbox_label(lang, "slash_read", "Memory lesen"),
        "store": _toolbox_label(lang, "slash_store", "Memory speichern"),
        "skills": _toolbox_label(lang, "slash_skills", "Skills"),
        "admin": _toolbox_label(lang, "slash_admin", "Admin"),
    }
    group_icons = {
        "suggested": "✨",
        "commands": "⌨",
        "read": "📖",
        "store": "💾",
        "skills": "🧩",
        "admin": "🛠",
    }

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in group_titles.keys()}
    for row in entries:
        grouped.setdefault(str(row.get("group", "commands")), []).append(row)

    order = ["commands", "read", "store", "skills", "admin"]
    toolbox_groups: list[dict[str, Any]] = []
    suggested_group = _build_suggested_toolbox_group(lang, entries, recent_messages)
    if suggested_group:
        suggested_group["icon"] = group_icons["suggested"]
        toolbox_groups.append(suggested_group)
    for group_key in order:
        rows = grouped.get(group_key, [])
        if not rows:
            continue
        limit = 6 if group_key in {"skills", "read", "store"} else 12
        toolbox_groups.append(
            {
                "key": group_key,
                "title": group_titles.get(group_key, group_key),
                "icon": group_icons.get(group_key, "•"),
                "items": rows[:limit],
            }
        )
    return entries, group_titles, toolbox_groups


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
    return _sanitize_username(request.cookies.get(USERNAME_COOKIE))


def _sanitize_role(value: str | None) -> str:
    role = str(value or "").strip().lower()
    if role not in {"admin", "user"}:
        return "user"
    return role


def _encode_auth_session(username: str, role: str, issued_at: int | None = None) -> str:
    payload = {
        "username": _sanitize_username(username),
        "role": _sanitize_role(role),
        "iat": int(issued_at if issued_at is not None else time.time()),
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(AUTH_SIGNING_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_auth_session(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(AUTH_SIGNING_SECRET.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        username = _sanitize_username(str(payload.get("username", "")))
        role = _sanitize_role(payload.get("role"))
        issued_at = int(payload.get("iat", 0) or 0)
        if not username or issued_at <= 0:
            return None
        if int(time.time()) - issued_at > AUTH_SESSION_MAX_AGE_SECONDS:
            return None
        return {"username": username, "role": role, "iat": issued_at}
    except Exception:
        return None


def _get_auth_session_from_request(request: Request) -> dict[str, Any] | None:
    raw = request.cookies.get(AUTH_COOKIE)
    return _decode_auth_session(raw)


def _clear_auth_related_cookies(response: Response, *, clear_preferences: bool = False) -> None:
    response.delete_cookie(AUTH_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    response.delete_cookie(USERNAME_COOKIE)
    response.delete_cookie(MEMORY_COLLECTION_COOKIE)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(FORGET_PENDING_COOKIE)
    response.delete_cookie(SAFE_FIX_PENDING_COOKIE)
    response.delete_cookie(CONNECTION_DELETE_PENDING_COOKIE)
    response.delete_cookie(CONNECTION_CREATE_PENDING_COOKIE)
    response.delete_cookie(CONNECTION_UPDATE_PENDING_COOKIE)
    if clear_preferences:
        response.delete_cookie(LANG_COOKIE)
        response.delete_cookie(AUTO_MEMORY_COOKIE)


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


def _parse_forget_query(message: str) -> str:
    text = re.sub(r"\s+", " ", message).strip()
    pattern = re.compile(r"^(vergiss|lösch|lösch|entfern|delete|remove)\s+", re.IGNORECASE)
    return pattern.sub("", text).strip(" .,:;!?") or text


def _parse_forget_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    # Examples:
    # "bestätige 1a2b3c"
    # "lösche jetzt 1a2b3c"
    match = re.search(
        r"(?:bestätige|bestätige|lösche|lösche|delete)\s+(?:jetzt\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_safe_fix_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestätige|confirm)\s+(?:safe-?fix\s+|fix\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_connection_delete_request(message: str) -> tuple[str, str] | None:
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    match = re.search(
        r"(?:lösche|loesche|entferne|delete|remove)\s+(?:die\s+|das\s+|den\s+)?(?:(ssh|discord|sftp|smb|webhook|smtp|email|imap|http api|http-api|rss|mqtt)\s+)?(?:verbindung|profil)?\s*([a-z0-9._-]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    kind = str(match.group(1) or "").strip().lower()
    ref = str(match.group(2) or "").strip()
    return kind, ref


def _parse_connection_delete_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:verbindung\s+)?(?:(?:löschen|loeschen|delete)\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _extract_connection_create_metadata(text: str) -> dict[str, Any]:
    def _extract(pattern: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE)
        return str(match.group(1)).strip() if match else ""

    title = _extract(r'(?:titel|title)\s+"([^"]+)"')
    description = _extract(r'(?:beschreibung|description)\s+"([^"]+)"')
    tags_raw = _extract(r'(?:tags|tag)\s+"([^"]+)"')
    aliases_raw = _extract(r'(?:aliase|aliases|alias)\s+"([^"]+)"')

    payload: dict[str, Any] = {}
    if title:
        payload["title"] = title[:120]
    if description:
        payload["description"] = description[:280]
    if tags_raw:
        payload["tags"] = [item.strip() for item in re.split(r"[;,]", tags_raw) if item.strip()][:12]
    if aliases_raw:
        payload["aliases"] = [item.strip() for item in re.split(r"[;,]", aliases_raw) if item.strip()][:12]
    return payload


def _extract_connection_field(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    return str(match.group(1)).strip() if match else ""


_CONNECTION_ACTION_VERBS: dict[str, str] = {
    "create": r"(?:erstelle|erzeuge|lege an|erfasse|create)",
    "update": r"(?:aktualisiere|update|ändere|aendere|bearbeite)",
}

_CONNECTION_URL_FIELDS = {"webhook_url", "feed_url", "url", "base_url"}
_CONNECTION_LEADING_VALUE_KEYWORDS = {
    "host",
    "user",
    "key",
    "key_path",
    "schluesselpfad",
    "keypfad",
    "share",
    "pfad",
    "path",
    "root",
    "root_path",
    "from",
    "to",
    "mailbox",
    "topic",
    "port",
    "timeout",
    "passwort",
    "password",
    "token",
    "auth_token",
    "auth-token",
    "method",
    "methode",
    "strict",
    "checking",
    "host-key",
    "allow",
    "commands",
    "titel",
    "title",
    "beschreibung",
    "description",
    "tags",
    "tag",
    "aliase",
    "aliases",
    "alias",
}

def _build_connection_chat_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for kind in CONNECTION_ADMIN_SPECS:
        clean_kind = normalize_connection_kind(kind)
        for alias in connection_chat_aliases(clean_kind):
            token = str(alias).strip().lower()
            if token:
                alias_map[token] = clean_kind
    return alias_map


def _match_connection_request_header(text: str, action: str) -> tuple[str, str, str] | None:
    alias_map = _build_connection_chat_alias_map()
    alias_pattern = "|".join(sorted((re.escape(alias) for alias in alias_map), key=len, reverse=True))
    if not alias_pattern:
        return None
    verbs = _CONNECTION_ACTION_VERBS.get(action, "")
    if not verbs:
        return None
    match = re.search(
        rf"^{verbs}\s+(?:eine\s+|ein\s+)?(?P<alias>{alias_pattern})(?:\s+verbindung|\s+profil)?\s+(?P<ref>[a-z0-9._-]+)(?P<rest>.*)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    alias = str(match.group("alias") or "").strip().lower()
    ref = str(match.group("ref") or "").strip()
    rest = str(match.group("rest") or "").strip()
    kind = alias_map.get(alias, "")
    if not kind or not ref:
        return None
    return kind, ref, rest


def _extract_connection_primary_value(kind: str, rest: str) -> tuple[str, str]:
    primary_field = connection_chat_primary_field(kind)
    clean_rest = str(rest or "").strip()
    if not primary_field or not clean_rest:
        return "", clean_rest
    if primary_field in _CONNECTION_URL_FIELDS:
        match = re.match(r"(https?://\S+)(?:\s+(.*))?$", clean_rest, re.IGNORECASE)
        if not match:
            return "", clean_rest
        primary_value = str(match.group(1) or "").strip()
        remaining = str(match.group(2) or "").strip()
        if primary_field == "base_url":
            primary_value = primary_value.rstrip("/")
        return primary_value, remaining
    token, _, remaining = clean_rest.partition(" ")
    lowered = token.strip().lower()
    if not token or lowered in _CONNECTION_LEADING_VALUE_KEYWORDS or token.startswith('"'):
        return "", clean_rest
    return token.strip(), remaining.strip()


def _extract_connection_field_value(text: str, kind: str, field: str) -> Any:
    chat_spec = connection_chat_field_specs(kind).get(field, {})
    patterns = chat_spec.get("patterns", [])
    if not isinstance(patterns, list) or not patterns:
        return None
    value = ""
    for pattern in patterns:
        value = _extract_connection_field(text, str(pattern))
        if value:
            break
    if not value:
        return None
    field_spec = connection_field_specs(kind).get(field, {})
    field_type = str(field_spec.get("type", "str")).strip().lower()
    if field_type == "list":
        split_pattern = str(chat_spec.get("split_pattern") or r"[;,]")
        return [item.strip() for item in re.split(split_pattern, value) if item.strip()]
    if field_type == "int":
        try:
            return int(value)
        except ValueError:
            return None
    if field == "base_url":
        return value.rstrip("/")
    return value


def _parse_catalog_connection_request(message: str, action: str) -> dict[str, Any] | None:
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    if not text:
        return None
    header = _match_connection_request_header(text, action)
    if not header:
        return None
    kind, ref, rest = header
    payload: dict[str, Any] = connection_chat_defaults(kind) if action == "create" else {}
    payload.update(_extract_connection_create_metadata(text))

    primary_field = connection_chat_primary_field(kind)
    primary_value, remaining = _extract_connection_primary_value(kind, rest)
    if primary_field and primary_value:
        payload[primary_field] = primary_value

    if kind == "http_api" and remaining.startswith("/"):
        inline_path, _, remaining = remaining.partition(" ")
        if inline_path.strip():
            payload["health_path"] = inline_path.strip()

    for field in connection_field_specs(kind):
        if field in {"title", "description", "tags", "aliases"}:
            continue
        if field == primary_field and field in payload:
            continue
        extracted = _extract_connection_field_value(text, kind, field)
        if extracted in (None, "", []):
            continue
        payload[field] = extracted

    clean_payload = sanitize_connection_payload(kind, payload)
    if action == "create" and primary_field and primary_field not in clean_payload:
        return None
    if action == "update" and not clean_payload:
        return None
    return {"kind": kind, "ref": ref, "payload": clean_payload}


def _parse_connection_create_request(message: str) -> dict[str, Any] | None:
    return _parse_catalog_connection_request(message, "create")


def _format_connection_payload_summary(kind: str, payload: dict[str, Any]) -> list[str]:
    labels = connection_field_labels(kind)
    lines: list[str] = []
    specs = connection_field_specs(kind)
    for key in connection_summary_fields(kind):
        spec = specs.get(key, {})
        value = payload.get(key)
        field_type = str(spec.get("type", "str")).strip().lower()
        if field_type == "list":
            if isinstance(value, list) and value:
                joined = ", ".join(str(item).strip() for item in value if str(item).strip())
                if joined:
                    lines.append(f"{labels.get(key, key)}: `{joined}`")
            continue
        if field_type == "bool":
            continue
        text = str(value or "").strip()
        if text:
            lines.append(f"{labels.get(key, key)}: `{text}`")
    return lines


def _parse_connection_create_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:verbindung\s+)?(?:(?:erstellen|erfassen|create)\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_connection_update_request(message: str) -> dict[str, Any] | None:
    return _parse_catalog_connection_request(message, "update")


def _parse_connection_update_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:verbindung\s+)?(?:(?:aktualisieren|update|aendern|ändern)\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _encode_forget_pending(data: dict[str, Any]) -> str:
    candidates = data.get("candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    cleaned_candidates: list[dict[str, Any]] = []
    for row in candidates[:10]:
        if not isinstance(row, dict):
            continue
        collection = _sanitize_collection_name(str(row.get("collection", "")).strip())
        point_id = str(row.get("id", "")).strip()[:128]
        label = str(row.get("label", "")).strip()[:64]
        text = str(row.get("text", "")).strip()[:240]
        if not collection or not point_id:
            continue
        cleaned_candidates.append(
            {
                "collection": collection,
                "id": point_id,
                "label": label,
                "text": text,
            }
        )

    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": _sanitize_username(str(data.get("user_id", ""))),
        "candidates": cleaned_candidates,
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_forget_pending(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        token = str(payload.get("token", "")).strip().lower()
        user_id = _sanitize_username(str(payload.get("user_id", "")))
        candidates = payload.get("candidates", [])
        if not token or not user_id or not isinstance(candidates, list):
            return None
        return {
            "token": token,
            "user_id": user_id,
            "candidates": candidates,
        }
    except Exception:
        return None
    return None


def _encode_safe_fix_pending(data: dict[str, Any]) -> str:
    fixes = data.get("fixes", [])
    if not isinstance(fixes, list):
        fixes = []
    clean_fixes: list[dict[str, Any]] = []
    for row in fixes[:20]:
        if not isinstance(row, dict):
            continue
        conn_ref = _sanitize_connection_name(str(row.get("connection_ref", "")))
        packages = row.get("packages", [])
        if not conn_ref or not isinstance(packages, list):
            continue
        clean_packages: list[str] = []
        for pkg in packages:
            name = str(pkg).strip().lower()
            if re.fullmatch(r"[a-z0-9][a-z0-9+_.-]*", name):
                clean_packages.append(name)
        clean_packages = sorted(set(clean_packages))[:30]
        if not clean_packages:
            continue
        clean_fixes.append({"connection_ref": conn_ref, "packages": clean_packages})

    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": _sanitize_username(str(data.get("user_id", ""))),
        "fixes": clean_fixes,
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_safe_fix_pending(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        token = str(payload.get("token", "")).strip().lower()
        user_id = _sanitize_username(str(payload.get("user_id", "")))
        fixes = payload.get("fixes", [])
        if not token or not user_id or not isinstance(fixes, list):
            return None
        return {"token": token, "user_id": user_id, "fixes": fixes}
    except Exception:
        return None
    return None


def _encode_connection_delete_pending(data: dict[str, Any]) -> str:
    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": _sanitize_username(str(data.get("user_id", ""))),
        "kind": str(data.get("kind", "")).strip().lower().replace("-", "_")[:32],
        "ref": _sanitize_connection_name(str(data.get("ref", "")))[:64],
        "issued_at": int(time.time()),
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_connection_delete_pending(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        token = str(payload.get("token", "")).strip().lower()
        user_id = _sanitize_username(str(payload.get("user_id", "")))
        kind = str(payload.get("kind", "")).strip().lower().replace("-", "_")
        ref = _sanitize_connection_name(str(payload.get("ref", "")))
        issued_at = int(payload.get("issued_at", 0) or 0)
        if not token or not user_id or not kind or not ref or issued_at <= 0:
            return None
        if int(time.time()) - issued_at > CONNECTION_PENDING_MAX_AGE_SECONDS:
            return None
        return {"token": token, "user_id": user_id, "kind": kind, "ref": ref, "issued_at": issued_at}
    except Exception:
        return None
    return None


def _encode_connection_create_pending(data: dict[str, Any]) -> str:
    kind = normalize_connection_kind(str(data.get("kind", "")))
    payload = sanitize_connection_payload(kind, data.get("payload", {}))
    packed = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": _sanitize_username(str(data.get("user_id", ""))),
        "kind": kind[:32],
        "ref": sanitize_connection_ref(str(data.get("ref", "")))[:64],
        "issued_at": int(time.time()),
        "payload": payload,
    }
    raw = json.dumps(packed, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_connection_create_pending(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(FORGET_SIGNING_SECRET.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        token = str(payload.get("token", "")).strip().lower()
        user_id = _sanitize_username(str(payload.get("user_id", "")))
        kind = str(payload.get("kind", "")).strip().lower().replace("-", "_")
        ref = sanitize_connection_ref(str(payload.get("ref", "")))
        issued_at = int(payload.get("issued_at", 0) or 0)
        create_payload = sanitize_connection_payload(kind, payload.get("payload", {}))
        if not token or not user_id or not kind or not ref or issued_at <= 0:
            return None
        if int(time.time()) - issued_at > CONNECTION_PENDING_MAX_AGE_SECONDS:
            return None
        return {"token": token, "user_id": user_id, "kind": kind, "ref": ref, "payload": create_payload, "issued_at": issued_at}
    except Exception:
        return None
    return None


def _encode_connection_update_pending(data: dict[str, Any]) -> str:
    return _encode_connection_create_pending(data)


def _decode_connection_update_pending(raw: str | None) -> dict[str, Any] | None:
    return _decode_connection_create_pending(raw)


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


def _read_raw_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise ValueError(f"Konfigurationsdatei fehlt: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml muss ein Mapping/Objekt enthalten.")
    return data


def _write_raw_config(data: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)


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


def _build_app() -> FastAPI:
    global AUTH_SIGNING_SECRET, FORGET_SIGNING_SECRET
    settings: Settings = load_settings(CONFIG_PATH)
    get_or_create_runtime_secret("ARIA_MASTER_KEY", CONFIG_PATH)
    AUTH_SIGNING_SECRET = get_or_create_runtime_secret("ARIA_AUTH_SIGNING_SECRET", CONFIG_PATH)
    FORGET_SIGNING_SECRET = get_or_create_runtime_secret("ARIA_FORGET_SIGNING_SECRET", CONFIG_PATH)
    prompt_loader = PromptLoader(BASE_DIR / settings.prompts.persona)
    llm_client = LLMClient(settings.llm)
    capability_context_store = CapabilityContextStore(CAPABILITY_CONTEXT_PATH)
    pipeline = Pipeline(
        settings=settings,
        prompt_loader=prompt_loader,
        llm_client=llm_client,
        capability_context_store=capability_context_store,
    )
    chat_history_store = FileChatHistoryStore(CHAT_HISTORY_DIR, max_messages=80)

    def _reload_runtime() -> None:
        nonlocal settings, prompt_loader, llm_client, pipeline, startup_diagnostics
        try:
            new_settings = load_settings(CONFIG_PATH)
            new_prompt_loader = PromptLoader(BASE_DIR / new_settings.prompts.persona)
            new_llm_client = LLMClient(new_settings.llm)
            new_pipeline = Pipeline(
                settings=new_settings,
                prompt_loader=new_prompt_loader,
                llm_client=new_llm_client,
                capability_context_store=capability_context_store,
            )
        except Exception as exc:
            LOGGER.exception("Runtime reload failed")
            raise ValueError(f"Runtime-Neuladen fehlgeschlagen: {exc}") from exc

        settings = new_settings
        prompt_loader = new_prompt_loader
        llm_client = new_llm_client
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
            response = await llm_client.chat(messages)
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
        current = _sanitize_session_id(request.cookies.get(SESSION_COOKIE))
        if current:
            return current
        return uuid4().hex[:12]

    def _get_effective_memory_collection(request: Request, user_id: str) -> str:
        selected = _sanitize_collection_name(request.cookies.get(MEMORY_COLLECTION_COOKIE))
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
            }
        except Exception as exc:
            empty["error"] = str(exc)
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
            startup_diagnostics = await build_runtime_diagnostics(BASE_DIR, settings)
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
                        f"Memory-Operationen beim Start: {memory_ops}",
                        f"Model: {settings.llm.model}",
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
        secure_cookie = request_is_secure(request)
        requested_lang = (
            str(request.query_params.get("lang", "")).strip().lower()
            or str(request.cookies.get(LANG_COOKIE, "")).strip().lower()
            or str(settings.ui.language or "de").strip().lower()
        )
        resolved_lang = I18N.resolve_lang(requested_lang, default_lang=str(settings.ui.language or "de"))
        request.state.lang = resolved_lang
        request.state.supported_languages = I18N.available_languages()
        request.state.agent_name = _agent_name_value()
        auth = _get_auth_session_from_request(request)
        csrf_cookie_token = _sanitize_csrf_token(request.cookies.get(CSRF_COOKIE))
        if not csrf_cookie_token:
            csrf_cookie_token = _new_csrf_token()
        request.state.csrf_token = csrf_cookie_token
        if auth:
            manager = _get_auth_manager()
            if manager:
                user = manager.store.get_user(auth["username"])
                if not user or not bool(user.get("active")):
                    auth = None
                else:
                    # Canonical username comes from trusted store (lowercase in current store schema).
                    auth["username"] = _sanitize_username(user.get("username"))
                    # Role comes from trusted store, not only from cookie payload.
                    auth["role"] = _sanitize_role(user.get("role"))
            else:
                auth = None
        request.state.authenticated = bool(auth)
        request.state.auth_user = auth.get("username") if auth else ""
        request.state.auth_role = auth.get("role") if auth else ""
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
            if request.cookies.get(AUTH_COOKIE):
                response = RedirectResponse(url=f"/session-expired?next={next_path}", status_code=303)
                _clear_auth_related_cookies(response)
                return response
            return RedirectResponse(url=f"/login?next={next_path}", status_code=303)

        if not is_public_or_api and path == "/set-auto-memory" and auth:
            if _sanitize_role(auth.get("role")) != "admin":
                return RedirectResponse(url="/?error=no_admin", status_code=303)

        if not is_public_or_api and path == "/config" and auth:
            if not request.state.can_access_settings:
                return RedirectResponse(url="/?error=no_settings", status_code=303)

        if not is_public_or_api and path.startswith("/config/") and auth:
            if not request.state.can_access_settings:
                return RedirectResponse(url="/?error=no_settings", status_code=303)
            if is_admin_only_path(path) and not request.state.can_access_users:
                return RedirectResponse(url="/config?error=no_admin", status_code=303)
            if is_advanced_config_path(path) and not request.state.can_access_advanced_config:
                return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)

        protected_methods = {"POST", "PUT", "PATCH", "DELETE"}
        csrf_exempt_prefixes = ("/v1/", "/api/")
        csrf_exempt_paths = {"/health", "/skills/import", "/config/connections/rss/import-opml"}
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
                refreshed = _encode_auth_session(auth["username"], auth["role"])
                response.set_cookie(
                    key=AUTH_COOKIE,
                    value=refreshed,
                    max_age=AUTH_SESSION_MAX_AGE_SECONDS,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=True,
                )
                response.set_cookie(
                    key=USERNAME_COOKIE,
                    value=auth["username"],
                    max_age=60 * 60 * 24 * 365,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=False,
                )
            elif request.cookies.get(AUTH_COOKIE):
                response.delete_cookie(AUTH_COOKIE)
            response.set_cookie(
                key=CSRF_COOKIE,
                value=csrf_cookie_token,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            response.set_cookie(
                key=LANG_COOKIE,
                value=response_lang,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
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
        secure_cookie = request_is_secure(request)
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
            response.set_cookie(
                key=AUTH_COOKIE,
                value=_encode_auth_session(canonical_username, role),
                max_age=AUTH_SESSION_MAX_AGE_SECONDS,
                samesite="lax",
                secure=secure_cookie,
                httponly=True,
            )
            response.set_cookie(
                key=USERNAME_COOKIE,
                value=canonical_username,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            response.set_cookie(
                key=MEMORY_COLLECTION_COOKIE,
                value=_default_memory_collection_for_user(canonical_username),
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            response.set_cookie(
                key=SESSION_COOKIE,
                value=uuid4().hex[:12],
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except Exception:
            return RedirectResponse(url=f"/login?error={quote_plus('Login fehlgeschlagen')}", status_code=303)

    @app.post("/logout")
    async def logout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        _clear_auth_related_cookies(response, clear_preferences=True)
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
        _clear_auth_related_cookies(response)
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        secure_cookie = request_is_secure(request)
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
        chat_command_entries, chat_command_group_titles, chat_toolbox_groups = _build_chat_command_catalog(
            lang=lang,
            auth_role=auth_role,
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
        if not request.cookies.get(SESSION_COOKIE):
            response.set_cookie(
                key=SESSION_COOKIE,
                value=session_id,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        response.set_cookie(
            key=AUTO_MEMORY_COOKIE,
            value="1" if auto_memory_enabled else "0",
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=secure_cookie,
            httponly=False,
        )
        return response

    @app.get("/help", response_class=HTMLResponse)
    async def help_page(request: Request) -> HTMLResponse:
        username = _get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de").strip().lower()
        help_file = "alpha-help-system.de.md" if lang.startswith("de") else "alpha-help-system.en.md"
        help_path = BASE_DIR / "docs" / "help" / help_file
        help_text = ""
        if help_path.exists():
            try:
                help_text = help_path.read_text(encoding="utf-8")
            except OSError:
                help_text = ""
        return TEMPLATES.TemplateResponse(
            request=request,
            name="help.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "help_path": f"docs/help/{help_file}",
                "help_text": help_text,
            },
        )

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
        secure_cookie = request_is_secure(request)
        auth = _get_auth_session_from_request(request)
        clean_username = _sanitize_username(username)
        if auth:
            clean_username = _sanitize_username(auth.get("username"))
        response = RedirectResponse(url="/", status_code=303)
        session_id = uuid4().hex[:12]
        if clean_username:
            response.set_cookie(
                key=USERNAME_COOKIE,
                value=clean_username,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            response.set_cookie(
                key=MEMORY_COLLECTION_COOKIE,
                value=_default_memory_collection_for_user(clean_username),
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            response.set_cookie(
                key=SESSION_COOKIE,
                value=session_id,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        return response

    @app.post("/set-auto-memory")
    async def set_auto_memory(request: Request, enabled: str = Form("0"), next_path: str = Form("/")) -> RedirectResponse:
        secure_cookie = request_is_secure(request)
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
            response.set_cookie(
                key=AUTO_MEMORY_COOKIE,
                value="1" if active else "0",
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/memories/config?error={quote_plus(str(exc))}", status_code=303)

    @app.post("/chat", response_class=HTMLResponse)
    async def chat(request: Request, message: str = Form(...)) -> HTMLResponse:
        secure_cookie = request_is_secure(request)
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
            if not request.cookies.get(SESSION_COOKIE):
                response.set_cookie(
                    key=SESSION_COOKIE,
                    value=session_id,
                    max_age=60 * 60 * 24 * 7,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=False,
                )
            return response

        icon = "⚠"
        intent_label = "error"
        total_tokens = 0
        cost_usd = "n/a"
        duration_s = "0.0"
        forget_cookie_value = request.cookies.get(FORGET_PENDING_COOKIE)
        forget_pending = _decode_forget_pending(forget_cookie_value)
        safe_fix_cookie_value = request.cookies.get(SAFE_FIX_PENDING_COOKIE)
        safe_fix_pending = _decode_safe_fix_pending(safe_fix_cookie_value)
        connection_delete_cookie_value = request.cookies.get(CONNECTION_DELETE_PENDING_COOKIE)
        connection_delete_pending = _decode_connection_delete_pending(connection_delete_cookie_value)
        connection_create_cookie_value = request.cookies.get(CONNECTION_CREATE_PENDING_COOKIE)
        connection_create_pending = _decode_connection_create_pending(connection_create_cookie_value)
        connection_update_cookie_value = request.cookies.get(CONNECTION_UPDATE_PENDING_COOKIE)
        connection_update_pending = _decode_connection_update_pending(connection_update_cookie_value)
        forget_decision = pipeline.router.classify(clean_message)
        safe_fix_confirm_token = _parse_safe_fix_confirm_token(clean_message)
        connection_delete_confirm_token = _parse_connection_delete_confirm_token(clean_message)
        connection_delete_request = _parse_connection_delete_request(clean_message)
        connection_create_confirm_token = _parse_connection_create_confirm_token(clean_message)
        connection_create_request = _parse_connection_create_request(clean_message)
        connection_update_confirm_token = _parse_connection_update_confirm_token(clean_message)
        connection_update_request = _parse_connection_update_request(clean_message)
        auth_role = _sanitize_role(getattr(request.state, "auth_role", ""))

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
                    set_connection_delete_cookie = _encode_connection_delete_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "kind": resolved_kind,
                            "ref": resolved_ref,
                        }
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
                    set_connection_create_cookie = _encode_connection_create_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "kind": kind,
                            "ref": ref,
                            "payload": payload,
                        }
                    )
                    summary_lines = [f"Typ: `{kind}`", f"Ref: `{ref}`", *_format_connection_payload_summary(kind, payload)]
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
                    set_connection_update_cookie = _encode_connection_update_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "kind": kind,
                            "ref": ref,
                            "payload": payload,
                        }
                    )
                    summary_lines = [f"Typ: `{kind}`", f"Ref: `{ref}`", *_format_connection_payload_summary(kind, payload)]
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
        elif "memory_forget" in forget_decision.intents and pipeline.memory_skill:
            confirm_token = _parse_forget_confirm_token(clean_message)
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
                forget_query = _parse_forget_query(clean_message)
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
                    set_forget_cookie = _encode_forget_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "candidates": candidates,
                        }
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
                    set_safe_fix_cookie = _encode_safe_fix_pending(
                        {
                            "token": token,
                            "user_id": username,
                            "fixes": result.safe_fix_plan,
                        }
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
        if not request.cookies.get(SESSION_COOKIE):
            response.set_cookie(
                key=SESSION_COOKIE,
                value=session_id,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        if clear_forget_cookie:
            response.delete_cookie(FORGET_PENDING_COOKIE)
        elif set_forget_cookie:
            response.set_cookie(
                key=FORGET_PENDING_COOKIE,
                value=set_forget_cookie,
                max_age=60 * 10,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        if clear_safe_fix_cookie:
            response.delete_cookie(SAFE_FIX_PENDING_COOKIE)
        elif set_safe_fix_cookie:
            response.set_cookie(
                key=SAFE_FIX_PENDING_COOKIE,
                value=set_safe_fix_cookie,
                max_age=60 * 15,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        if clear_connection_delete_cookie:
            response.delete_cookie(CONNECTION_DELETE_PENDING_COOKIE)
        elif set_connection_delete_cookie:
            response.set_cookie(
                key=CONNECTION_DELETE_PENDING_COOKIE,
                value=set_connection_delete_cookie,
                max_age=60 * 10,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        if clear_connection_create_cookie:
            response.delete_cookie(CONNECTION_CREATE_PENDING_COOKIE)
        elif set_connection_create_cookie:
            response.set_cookie(
                key=CONNECTION_CREATE_PENDING_COOKIE,
                value=set_connection_create_cookie,
                max_age=60 * 10,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        if clear_connection_update_cookie:
            response.delete_cookie(CONNECTION_UPDATE_PENDING_COOKIE)
        elif set_connection_update_cookie:
            response.set_cookie(
                key=CONNECTION_UPDATE_PENDING_COOKIE,
                value=set_connection_update_cookie,
                max_age=60 * 10,
                samesite="lax",
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
