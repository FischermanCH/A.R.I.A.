from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from uuid import uuid4

import yaml

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aria.channels.api import register_api_routes
import aria.web.auth_session_helpers as auth_session_helpers
from aria.web.auth_middleware import AuthMiddlewareDeps, register_auth_middleware
from aria.web.auth_surface_routes import AuthSurfaceRouteDeps, register_auth_surface_routes
from aria.web.chat_execution_flow import ChatExecutionDeps, execute_chat_flow
from aria.web.chat_execution_routes import ChatExecutionRouteDeps, register_chat_execution_routes
from aria.web.chat_surface_routes import ChatSurfaceRouteDeps, register_chat_surface_routes
from aria.web.chat_route_helpers import (
    apply_chat_response_cookies,
    prepare_chat_route_state,
    render_missing_username_response,
)
from aria.web.docs_surface_routes import DocsSurfaceRouteDeps, register_docs_surface_routes
from aria.web.main_config_helpers import MainConfigHelperDeps, build_main_config_helpers
from aria.web.main_request_helpers import MainRequestHelperDeps, build_main_request_helpers
from aria.web.main_runtime_support_helpers import MainRuntimeSupportDeps, build_main_runtime_support_helpers
from aria.web.memory_runtime_helpers import MemoryRuntimeHelperDeps, build_memory_runtime_helpers
import aria.web.runtime_manager as runtime_manager
from aria.web.system_update_routes import SystemUpdateRouteDeps, register_system_update_routes
from aria.web.activities_routes import register_activities_routes
from aria.web.chat_catalog import build_chat_command_catalog
from aria.web.cookie_helpers import CookieHelper
from aria.web.config_routes import ConfigRouteDeps, register_config_routes
from aria.web.main_ui_helpers import (
    build_client_skill_progress_hints as _build_client_skill_progress_hints,
    current_memory_day as _current_memory_day,
    daily_time_from_cron as _daily_time_from_cron,
    daily_time_to_cron as _daily_time_to_cron,
    discord_alert_error_lines as _discord_alert_error_lines,
    exception_response as _exception_response,
    extract_keyword_candidates as _extract_keyword_candidates,
    friendly_error_text as _friendly_error_text,
    intent_badge as _intent_badge,
    lang_flag as _lang_flag,
    lang_label as _lang_label,
    localized_doc_path as _localized_doc_path,
    parse_collection_day_suffix as _parse_collection_day_suffix,
    read_doc_text as _read_doc_text,
    render_assistant_message_html as _render_assistant_message_html,
    render_markdown_doc as _render_markdown_doc,
    replace_agent_name as _replace_agent_name,
)
from aria.web.memories_routes import register_memories_routes
from aria.web.notes_routes import NotesRouteDeps, register_notes_routes
from aria.web.skills_routes import register_skills_routes
from aria.web.stats_routes import register_stats_routes
from aria.core.access import (
    can_access_advanced_config,
    can_access_settings,
    can_access_users,
    is_advanced_config_path,
    is_admin_only_path,
)
from aria.core.chat_history import FileChatHistoryStore
from aria.core.capability_context import CapabilityContextStore
from aria.core.connection_admin import (
    CONNECTION_ADMIN_SPECS,
    create_connection_profile,
    delete_connection_profile,
    list_connection_refs,
    resolve_connection_target,
    update_connection_profile,
)
from aria.core.config import (
    Settings,
    get_master_key,
    get_or_create_runtime_secret,
    load_settings,
    normalize_ui_background,
    normalize_ui_theme,
    resolve_ui_background_asset_url,
)
from aria.core.config_backup import build_config_backup_payload
from aria.core.config_backup import summarize_config_backup_payload
from aria.core.notes_index import NotesIndex
from aria.core.notes_store import NotesStore
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
from aria.core.pipeline import Pipeline
from aria.core.routing_admin import ensure_connection_routing_index_ready
from aria.core.routing_hints import suggest_skill_keywords_with_llm
from aria.core.runtime_diagnostics import build_runtime_diagnostics
from aria.core.runtime_endpoint import cookie_should_be_secure, request_is_secure
from aria.core.update_helper_client import fetch_update_helper_status
from aria.core.update_helper_client import helper_status_visual
from aria.core.update_helper_client import resolve_update_helper_config
from aria.core.update_helper_client import trigger_update_helper_run


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
ROUTED_ACTION_PENDING_COOKIE = "aria_routed_action_pending"
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
    "routed_action_pending": ROUTED_ACTION_PENDING_COOKIE,
    "auth": AUTH_COOKIE,
    "csrf": CSRF_COOKIE,
    "lang": LANG_COOKIE,
}
COOKIE_KEY_BY_BASE = {value: key for key, value in COOKIE_NAME_BASES.items()}
LEGACY_COOKIE_FALLBACK_BASES: set[str] = {
    LANG_COOKIE,
}
AUTH_RELATED_COOKIE_BASES: tuple[str, ...] = (
    AUTH_COOKIE,
    CSRF_COOKIE,
    USERNAME_COOKIE,
    MEMORY_COLLECTION_COOKIE,
    SESSION_COOKIE,
    FORGET_PENDING_COOKIE,
    SAFE_FIX_PENDING_COOKIE,
    CONNECTION_DELETE_PENDING_COOKIE,
    CONNECTION_CREATE_PENDING_COOKIE,
    CONNECTION_UPDATE_PENDING_COOKIE,
    UPDATE_PENDING_COOKIE,
    ROUTED_ACTION_PENDING_COOKIE,
)
PREFERENCE_COOKIE_BASES: tuple[str, ...] = (
    LANG_COOKIE,
    AUTO_MEMORY_COOKIE,
)
_COOKIE_HELPER = CookieHelper(
    cookie_name_bases=COOKIE_NAME_BASES,
    cookie_key_by_base=COOKIE_KEY_BY_BASE,
    legacy_cookie_fallback_bases=LEGACY_COOKIE_FALLBACK_BASES,
)
_cookie_scope_source = _COOKIE_HELPER.cookie_scope_source
_cookie_name = _COOKIE_HELPER.cookie_name
_cookie_names_for_request = _COOKIE_HELPER.cookie_names_for_request
_request_cookie_name = _COOKIE_HELPER.request_cookie_name
_request_cookie_value = _COOKIE_HELPER.request_cookie_value
_set_response_cookie = _COOKIE_HELPER.set_response_cookie
_delete_response_cookie = _COOKIE_HELPER.delete_response_cookie
_delete_response_cookie_variants = _COOKIE_HELPER.delete_response_cookie_variants
_clear_auth_related_cookies = partial(
    _COOKIE_HELPER.clear_auth_related_cookies,
    auth_related_cookie_bases=AUTH_RELATED_COOKIE_BASES,
    preference_cookie_bases=PREFERENCE_COOKIE_BASES,
)
_AUTH_SESSION_HELPER = auth_session_helpers.AuthSessionHelper(
    auth_cookie_name=AUTH_COOKIE,
    get_signing_secret=lambda: AUTH_SIGNING_SECRET,
    get_max_age_seconds=lambda: AUTH_SESSION_MAX_AGE_SECONDS,
    sanitize_username=lambda value: _sanitize_username(value),
    sanitize_role=lambda value: _sanitize_role(value),
    request_cookie_value=lambda request, base_name: _request_cookie_value(request, base_name),
    cookie_scope_source=lambda request=None, public_url="": _cookie_scope_source(request, public_url=public_url),
)
_encode_auth_session = _AUTH_SESSION_HELPER.encode_auth_session
_decode_auth_session = _AUTH_SESSION_HELPER.decode_auth_session
_decode_auth_session_with_reason = _AUTH_SESSION_HELPER.decode_auth_session_with_reason
_get_auth_session_from_request = _AUTH_SESSION_HELPER.get_auth_session_from_request
_get_auth_session_from_request_with_reason = _AUTH_SESSION_HELPER.get_auth_session_from_request_with_reason
_sanitize_auth_session_max_age_seconds = lambda value: auth_session_helpers.sanitize_auth_session_max_age_seconds(
    value,
    default_seconds=DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS,
)
_new_csrf_token = auth_session_helpers.new_csrf_token
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
        "id": "qdrant",
        "label_i18n": "help.doc_qdrant",
        "label_default": "Qdrant",
        "path": "docs/help/qdrant.md",
        "summary_i18n": "help.doc_qdrant_summary",
        "summary_default": "Wofuer ARIA Qdrant nutzt, was dort gespeichert wird und worauf man im Betrieb achten sollte.",
        "icon": "memories",
        "group": "reference",
    },
    {
        "id": "searxng",
        "label_i18n": "help.doc_searxng",
        "label_default": "SearXNG",
        "path": "docs/help/searxng.md",
        "summary_i18n": "help.doc_searxng_summary",
        "summary_default": "Wie ARIA die SearXNG-Websuche nutzt und warum der Dienst bewusst separat im Stack bleibt.",
        "icon": "searxng",
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
CUSTOM_SKILL_DESC_I18N_FALLBACKS: dict[str, dict[str, str]] = {
    "Fuehrt apt Update/Upgrade auf zwei konfigurierten Servern aus und fasst das Ergebnis zusammen.": {
        "en": "Runs apt update/upgrade on two configured servers and summarizes the result.",
    },
    "Führt apt Update/Upgrade auf zwei konfigurierten Servern aus und fasst das Ergebnis zusammen.": {
        "en": "Runs apt update/upgrade on two configured servers and summarizes the result.",
    },
}


class _DynamicProxy:
    def __init__(self, getter) -> None:  # type: ignore[no-untyped-def]
        self._getter = getter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._getter(), name)

    def __bool__(self) -> bool:
        return bool(self._getter())

    def __repr__(self) -> str:
        return repr(self._getter())

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

def _build_app() -> FastAPI:
    global AUTH_SIGNING_SECRET, FORGET_SIGNING_SECRET
    initial_settings: Settings = load_settings(CONFIG_PATH)
    global AUTH_SESSION_MAX_AGE_SECONDS
    AUTH_SESSION_MAX_AGE_SECONDS = _sanitize_auth_session_max_age_seconds(
        getattr(initial_settings.security, "session_max_age_seconds", DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS)
    )
    get_or_create_runtime_secret("ARIA_MASTER_KEY", CONFIG_PATH)
    AUTH_SIGNING_SECRET = get_or_create_runtime_secret("ARIA_AUTH_SIGNING_SECRET", CONFIG_PATH)
    FORGET_SIGNING_SECRET = get_or_create_runtime_secret("ARIA_FORGET_SIGNING_SECRET", CONFIG_PATH)
    capability_context_store = CapabilityContextStore(CAPABILITY_CONTEXT_PATH)
    runtime_manager_instance = runtime_manager.RuntimeManager(
        base_dir=BASE_DIR,
        config_path=CONFIG_PATH,
        initial_settings=initial_settings,
        capability_context_store=capability_context_store,
    )
    settings = _DynamicProxy(runtime_manager_instance.get_settings)
    prompt_loader = _DynamicProxy(runtime_manager_instance.get_prompt_loader)
    usage_meter = _DynamicProxy(runtime_manager_instance.get_usage_meter)
    llm_client = _DynamicProxy(runtime_manager_instance.get_llm_client)
    pipeline = _DynamicProxy(runtime_manager_instance.get_pipeline)
    chat_history_store = FileChatHistoryStore(CHAT_HISTORY_DIR, max_messages=80)

    def _get_runtime_settings() -> Settings:
        return runtime_manager_instance.get_settings()

    def _get_runtime_pipeline() -> Pipeline:
        return runtime_manager_instance.get_pipeline()

    def _reload_runtime() -> None:
        global AUTH_SESSION_MAX_AGE_SECONDS
        try:
            new_settings = runtime_manager_instance.reload_runtime()
            AUTH_SESSION_MAX_AGE_SECONDS = _sanitize_auth_session_max_age_seconds(
                getattr(new_settings.security, "session_max_age_seconds", DEFAULT_AUTH_SESSION_MAX_AGE_SECONDS)
            )
        except Exception as exc:
            LOGGER.exception("Runtime reload failed")
            raise ValueError(f"Runtime-Neuladen fehlgeschlagen: {exc}") from exc

    _main_request_helpers = build_main_request_helpers(
        MainRequestHelperDeps(
            translate=lambda lang, key, default: I18N.t(lang, key, default),
            custom_skill_desc_i18n_fallbacks=CUSTOM_SKILL_DESC_I18N_FALLBACKS,
            get_auth_session_from_request=lambda request: _get_auth_session_from_request(request),
            request_cookie_value=lambda request, base_name: _request_cookie_value(request, base_name),
            username_cookie=USERNAME_COOKIE,
        )
    )
    _format_skill_routing_info = _main_request_helpers.format_skill_routing_info
    _localize_custom_skill_description = _main_request_helpers.localize_custom_skill_description
    _sanitize_username = _main_request_helpers.sanitize_username
    _get_username_from_request = _main_request_helpers.get_username_from_request
    _sanitize_role = _main_request_helpers.sanitize_role
    _sanitize_collection_name = _main_request_helpers.sanitize_collection_name
    _sanitize_session_id = _main_request_helpers.sanitize_session_id
    _sanitize_csrf_token = _main_request_helpers.sanitize_csrf_token

    _memory_runtime_helpers = build_memory_runtime_helpers(
        MemoryRuntimeHelperDeps(
            base_dir=BASE_DIR,
            get_settings=_get_runtime_settings,
            sanitize_collection_name=_sanitize_collection_name,
            current_memory_day=_current_memory_day,
            request_cookie_value=_request_cookie_value,
            session_cookie=SESSION_COOKIE,
            memory_collection_cookie=MEMORY_COLLECTION_COOKIE,
        )
    )
    _default_memory_collection_for_user = _memory_runtime_helpers.default_memory_collection_for_user
    _ensure_session_id = _memory_runtime_helpers.ensure_session_id
    _get_effective_memory_collection = _memory_runtime_helpers.get_effective_memory_collection
    _session_memory_collection_for_user = _memory_runtime_helpers.session_memory_collection_for_user
    _is_auto_memory_enabled = _memory_runtime_helpers.is_auto_memory_enabled
    _qdrant_base_url = _memory_runtime_helpers.qdrant_base_url
    _qdrant_dashboard_url = _memory_runtime_helpers.qdrant_dashboard_url
    _list_qdrant_collections = _memory_runtime_helpers.list_qdrant_collections
    _qdrant_overview = _memory_runtime_helpers.qdrant_overview

    _main_config_helpers = build_main_config_helpers(
        MainConfigHelperDeps(
            get_base_dir=lambda: BASE_DIR,
            get_config_path=lambda: CONFIG_PATH,
            get_error_interpreter_path=lambda: ERROR_INTERPRETER_PATH,
            file_editor_catalog=FILE_EDITOR_CATALOG,
            raw_config_cache=_RAW_CONFIG_CACHE,
        )
    )
    _list_file_editor_entries = _main_config_helpers.list_file_editor_entries
    _resolve_file_editor_entry = _main_config_helpers.resolve_file_editor_entry
    _resolve_file_editor_file = _main_config_helpers.resolve_file_editor_file
    _is_allowed_edit_path = _main_config_helpers.is_allowed_edit_path
    _list_editable_files = _main_config_helpers.list_editable_files
    _resolve_edit_file = _main_config_helpers.resolve_edit_file
    _resolve_prompt_file = _main_config_helpers.resolve_prompt_file
    _clear_raw_config_cache = _main_config_helpers.clear_raw_config_cache
    _read_raw_config = _main_config_helpers.read_raw_config
    _write_raw_config = _main_config_helpers.write_raw_config
    _enable_bootstrap_admin_mode_in_raw_config = _main_config_helpers.enable_bootstrap_admin_mode_in_raw_config
    _read_error_interpreter_raw = _main_config_helpers.read_error_interpreter_raw
    _parse_lines = _main_config_helpers.parse_lines
    _is_ollama_model = _main_config_helpers.is_ollama_model
    _sanitize_profile_name = _main_config_helpers.sanitize_profile_name
    _normalize_model_key = _main_config_helpers.normalize_model_key
    _sanitize_connection_name = _main_config_helpers.sanitize_connection_name
    _resolve_pricing_entry = _main_config_helpers.resolve_pricing_entry
    _load_models_from_api_base = _main_config_helpers.load_models_from_api_base
    _read_release_meta = _main_config_helpers.read_release_meta
    _get_update_status = lambda current_label, ttl_seconds=60 * 60 * 6: _main_config_helpers.get_update_status(
        current_label,
        ttl_seconds,
    )
    globals().update(
        {
            "_format_skill_routing_info": _format_skill_routing_info,
            "_localize_custom_skill_description": _localize_custom_skill_description,
            "_sanitize_username": _sanitize_username,
            "_get_username_from_request": _get_username_from_request,
            "_sanitize_role": _sanitize_role,
            "_sanitize_collection_name": _sanitize_collection_name,
            "_sanitize_session_id": _sanitize_session_id,
            "_sanitize_csrf_token": _sanitize_csrf_token,
            "_list_file_editor_entries": _list_file_editor_entries,
            "_resolve_file_editor_entry": _resolve_file_editor_entry,
            "_resolve_file_editor_file": _resolve_file_editor_file,
            "_is_allowed_edit_path": _is_allowed_edit_path,
            "_list_editable_files": _list_editable_files,
            "_resolve_edit_file": _resolve_edit_file,
            "_resolve_prompt_file": _resolve_prompt_file,
            "_clear_raw_config_cache": _clear_raw_config_cache,
            "_read_raw_config": _read_raw_config,
            "_write_raw_config": _write_raw_config,
            "_enable_bootstrap_admin_mode_in_raw_config": _enable_bootstrap_admin_mode_in_raw_config,
            "_read_error_interpreter_raw": _read_error_interpreter_raw,
            "_parse_lines": _parse_lines,
            "_is_ollama_model": _is_ollama_model,
            "_sanitize_profile_name": _sanitize_profile_name,
            "_normalize_model_key": _normalize_model_key,
            "_sanitize_connection_name": _sanitize_connection_name,
            "_resolve_pricing_entry": _resolve_pricing_entry,
            "_load_models_from_api_base": _load_models_from_api_base,
            "_read_release_meta": _read_release_meta,
            "_get_update_status": _get_update_status,
        }
    )

    async def _suggest_skill_keywords_with_llm(
        manifest: dict[str, Any],
        language: str = "de",
        max_keywords: int = 12,
    ) -> list[str]:
        return await suggest_skill_keywords_with_llm(
            llm_client,
            manifest,
            language=language,
            max_keywords=max_keywords,
        )

    _main_runtime_support_helpers = build_main_runtime_support_helpers(
        MainRuntimeSupportDeps(
            base_dir=BASE_DIR,
            config_path=CONFIG_PATH,
            read_raw_config=lambda: _read_raw_config(),
            get_settings=_get_runtime_settings,
            get_master_key=lambda path: globals()["get_master_key"](path),
            sanitize_role=_sanitize_role,
            get_auth_session_from_request=lambda request: _get_auth_session_from_request(request),
            get_or_refresh_startup_diagnostics=runtime_manager_instance.get_or_refresh_startup_diagnostics,
            build_runtime_diagnostics=lambda: build_runtime_diagnostics(BASE_DIR, settings, usage_meter=usage_meter),
        )
    )
    _list_prompt_files = _main_runtime_support_helpers.list_prompt_files
    _get_profiles = _main_runtime_support_helpers.get_profiles
    _get_active_profile_name = _main_runtime_support_helpers.get_active_profile_name
    _set_active_profile = _main_runtime_support_helpers.set_active_profile
    _get_secure_store = _main_runtime_support_helpers.get_secure_store
    _get_auth_manager = _main_runtime_support_helpers.get_auth_manager
    _active_admin_count = _main_runtime_support_helpers.active_admin_count
    _get_runtime_preflight_data = _main_runtime_support_helpers.get_runtime_preflight_data
    _update_finished_after_session = _main_runtime_support_helpers.update_finished_after_session

    startup_maintenance_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):  # noqa: ANN202
        nonlocal startup_maintenance_task
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
                routing_refresh = await ensure_connection_routing_index_ready(
                    settings,
                    embedding_client=pipeline.embedding_client,
                    wait=True,
                )
                routing_status = dict(routing_refresh.get("status", {}) or {})
                if bool(routing_refresh.get("refresh_attempted")):
                    LOGGER.info(
                        "Startup routing index refresh status=%s :: %s",
                        routing_status.get("status", "warn"),
                        routing_status.get("message", ""),
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

    register_auth_middleware(
        app,
        AuthMiddlewareDeps(
            base_dir=BASE_DIR,
            get_settings=lambda: settings,
            cookie_should_be_secure=cookie_should_be_secure,
            cookie_scope_source=_cookie_scope_source,
            cookie_names_for_request=_cookie_names_for_request,
            request_cookie_value=_request_cookie_value,
            translate=_tr,
            read_release_meta=lambda base_dir: globals()["_read_release_meta"](base_dir),
            get_update_status=lambda current_label: globals()["_get_update_status"](current_label),
            get_auth_session_from_request_with_reason=_get_auth_session_from_request_with_reason,
            get_auth_manager=_get_auth_manager,
            sanitize_username=_sanitize_username,
            sanitize_role=_sanitize_role,
            sanitize_csrf_token=_sanitize_csrf_token,
            new_csrf_token=_new_csrf_token,
            set_response_cookie=_set_response_cookie,
            clear_auth_related_cookies=_clear_auth_related_cookies,
            available_languages=I18N.available_languages,
            resolve_lang=lambda code, default_lang: I18N.resolve_lang(code, default_lang=default_lang),
            normalize_ui_theme=normalize_ui_theme,
            normalize_ui_background=normalize_ui_background,
            resolve_ui_background_asset_url=resolve_ui_background_asset_url,
            can_access_settings=lambda role: globals()["can_access_settings"](role),
            can_access_users=lambda role: globals()["can_access_users"](role),
            can_access_advanced_config=lambda role, debug_mode: globals()["can_access_advanced_config"](role, debug_mode),
            is_admin_only_path=lambda path: globals()["is_admin_only_path"](path),
            is_advanced_config_path=lambda path: globals()["is_advanced_config_path"](path),
            encode_auth_session=_encode_auth_session,
            auth_cookie=AUTH_COOKIE,
            csrf_cookie=CSRF_COOKIE,
            username_cookie=USERNAME_COOKIE,
            lang_cookie=LANG_COOKIE,
            auth_session_max_age_seconds=AUTH_SESSION_MAX_AGE_SECONDS,
        ),
    )

    register_auth_surface_routes(
        app,
        AuthSurfaceRouteDeps(
            templates=TEMPLATES,
            get_settings=lambda: settings,
            get_auth_manager=_get_auth_manager,
            get_auth_session_from_request=_get_auth_session_from_request,
            sanitize_username=_sanitize_username,
            sanitize_role=_sanitize_role,
            set_response_cookie=_set_response_cookie,
            clear_auth_related_cookies=_clear_auth_related_cookies,
            cookie_should_be_secure=cookie_should_be_secure,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            enable_bootstrap_admin_mode_in_raw_config=_enable_bootstrap_admin_mode_in_raw_config,
            reload_runtime=_reload_runtime,
            default_memory_collection_for_user=_default_memory_collection_for_user,
            encode_auth_session=_encode_auth_session,
            auth_cookie=AUTH_COOKIE,
            username_cookie=USERNAME_COOKIE,
            memory_collection_cookie=MEMORY_COLLECTION_COOKIE,
            session_cookie=SESSION_COOKIE,
            auto_memory_cookie=AUTO_MEMORY_COOKIE,
            auth_session_max_age_seconds=AUTH_SESSION_MAX_AGE_SECONDS,
            logger=LOGGER,
        ),
    )

    register_chat_surface_routes(
        app,
        ChatSurfaceRouteDeps(
            templates=TEMPLATES,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            get_auth_session_from_request=_get_auth_session_from_request,
            ensure_session_id=_ensure_session_id,
            is_auto_memory_enabled=_is_auto_memory_enabled,
            get_effective_memory_collection=_get_effective_memory_collection,
            session_memory_collection_for_user=_session_memory_collection_for_user,
            load_custom_skill_manifests=_load_custom_skill_manifests,
            localize_custom_skill_description=_localize_custom_skill_description,
            sanitize_role=_sanitize_role,
            build_client_skill_progress_hints=_build_client_skill_progress_hints,
            get_connection_catalog=lambda: {
                kind: sorted(list(getattr(settings.connections, kind, {}).keys()))
                for kind in CONNECTION_ADMIN_SPECS.keys()
                if isinstance(getattr(settings.connections, kind, {}), dict)
            },
            build_chat_command_catalog=build_chat_command_catalog,
            load_chat_history=lambda username: chat_history_store.load_history(username),
            current_memory_day=_current_memory_day,
            cookie_should_be_secure=cookie_should_be_secure,
            request_cookie_value=_request_cookie_value,
            set_response_cookie=_set_response_cookie,
            session_cookie=SESSION_COOKIE,
            auto_memory_cookie=AUTO_MEMORY_COOKIE,
        ),
    )

    register_docs_surface_routes(
        app,
        DocsSurfaceRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            localized_doc_path=_localized_doc_path,
            read_doc_text=_read_doc_text,
            render_markdown_doc=_render_markdown_doc,
            translate=_tr,
            help_doc_catalog=HELP_DOC_CATALOG,
            help_doc_map=HELP_DOC_MAP,
            help_doc_groups=HELP_DOC_GROUPS,
            product_doc_catalog=PRODUCT_DOC_CATALOG,
            product_doc_map=PRODUCT_DOC_MAP,
            product_info_asset_map=PRODUCT_INFO_ASSET_MAP,
        ),
    )

    register_system_update_routes(
        app,
        SystemUpdateRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            get_auth_session_from_request=_get_auth_session_from_request,
            get_secure_store=_get_secure_store,
            clear_auth_related_cookies=_clear_auth_related_cookies,
            get_runtime_preflight=_get_runtime_preflight_data,
            update_finished_after_session=_update_finished_after_session,
            read_release_meta=lambda base_dir: globals()["_read_release_meta"](base_dir),
            get_update_status=lambda current_label: globals()["_get_update_status"](current_label, ttl_seconds=0),
            resolve_update_helper_config=lambda *, secure_store=None: resolve_update_helper_config(secure_store=secure_store),
            fetch_update_helper_status=lambda helper_config: fetch_update_helper_status(helper_config),
            trigger_update_helper_run=lambda helper_config: trigger_update_helper_run(helper_config),
            helper_status_visual=helper_status_visual,
        ),
    )

    register_stats_routes(
        app,
        templates=TEMPLATES,
        get_pipeline=_get_runtime_pipeline,
        get_settings=_get_runtime_settings,
        get_username_from_request=_get_username_from_request,
        resolve_pricing_entry=_resolve_pricing_entry,
        get_runtime_preflight=_get_runtime_preflight_data,
        get_secure_store=_get_secure_store,
    )
    register_activities_routes(
        app,
        templates=TEMPLATES,
        get_pipeline=_get_runtime_pipeline,
        get_settings=_get_runtime_settings,
        get_username_from_request=_get_username_from_request,
    )

    register_skills_routes(
        app,
        templates=TEMPLATES,
        get_settings=_get_runtime_settings,
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
        get_settings=_get_runtime_settings,
        get_pipeline=_get_runtime_pipeline,
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

    register_notes_routes(
        app,
        NotesRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            get_settings=_get_runtime_settings,
            get_username_from_request=_get_username_from_request,
            build_notes_store=lambda root_dir: NotesStore(root_dir),
            build_notes_index=lambda runtime_settings: NotesIndex(runtime_settings.memory, runtime_settings.embeddings),
        ),
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
            get_auth_session_max_age_seconds=lambda: AUTH_SESSION_MAX_AGE_SECONDS,
            get_settings=_get_runtime_settings,
            get_pipeline=_get_runtime_pipeline,
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

    register_chat_execution_routes(
        app,
        ChatExecutionRouteDeps(
            templates=TEMPLATES,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            ensure_session_id=_ensure_session_id,
            is_auto_memory_enabled=_is_auto_memory_enabled,
            get_effective_memory_collection=_get_effective_memory_collection,
            session_memory_collection_for_user=_session_memory_collection_for_user,
            cookie_should_be_secure=cookie_should_be_secure,
            request_cookie_value=_request_cookie_value,
            set_response_cookie=_set_response_cookie,
            delete_response_cookie=_delete_response_cookie,
            sanitize_username=_sanitize_username,
            sanitize_connection_name=_sanitize_connection_name,
            sanitize_role=_sanitize_role,
            intent_badge=_intent_badge,
            friendly_error_text=_friendly_error_text,
            execution_deps=ChatExecutionDeps(
                base_dir=BASE_DIR,
                pipeline=pipeline,
                settings=settings,
                intent_badge=_intent_badge,
                friendly_error_text=_friendly_error_text,
                alert_sender=lambda *args, **kwargs: send_discord_alerts(*args, **kwargs),
                signing_secret=FORGET_SIGNING_SECRET,
                sanitize_username=_sanitize_username,
                sanitize_connection_name=_sanitize_connection_name,
                sanitize_collection_name=_sanitize_collection_name,
                list_connection_refs=lambda base_dir: list_connection_refs(base_dir),
                resolve_connection_target=lambda *args, **kwargs: resolve_connection_target(*args, **kwargs),
                delete_connection_profile=lambda *args, **kwargs: delete_connection_profile(*args, **kwargs),
                create_connection_profile=lambda *args, **kwargs: create_connection_profile(*args, **kwargs),
                update_connection_profile=lambda *args, **kwargs: update_connection_profile(*args, **kwargs),
                reload_runtime=_reload_runtime,
                resolve_update_helper_config=lambda **kwargs: resolve_update_helper_config(**kwargs),
                trigger_update_helper_run=lambda helper_config: trigger_update_helper_run(helper_config),
                fetch_update_helper_status=lambda helper_config: fetch_update_helper_status(helper_config),
                helper_status_visual=lambda *args, **kwargs: helper_status_visual(*args, **kwargs),
                get_secure_store=_get_secure_store,
                build_config_backup_payload=lambda *args, **kwargs: globals()["build_config_backup_payload"](*args, **kwargs),
                summarize_config_backup_payload=lambda payload: globals()["summarize_config_backup_payload"](payload),
                read_raw_config=lambda: globals()["_read_raw_config"](),
            ),
            append_chat_history=chat_history_store.append_exchange,
            clear_chat_history=chat_history_store.clear_history,
            clear_capability_context=capability_context_store.clear_user,
            session_cookie=SESSION_COOKIE,
            forget_pending_cookie=FORGET_PENDING_COOKIE,
            safe_fix_pending_cookie=SAFE_FIX_PENDING_COOKIE,
            connection_delete_pending_cookie=CONNECTION_DELETE_PENDING_COOKIE,
            connection_create_pending_cookie=CONNECTION_CREATE_PENDING_COOKIE,
            connection_update_pending_cookie=CONNECTION_UPDATE_PENDING_COOKIE,
            update_pending_cookie=UPDATE_PENDING_COOKIE,
            routed_action_pending_cookie=ROUTED_ACTION_PENDING_COOKIE,
            connection_pending_max_age_seconds=CONNECTION_PENDING_MAX_AGE_SECONDS,
            forget_signing_secret=FORGET_SIGNING_SECRET,
        ),
    )

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
