"""Canonical ARIA configuration models and loading foundations."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules import module_static_asset_prefix_path

_CONFIG_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _config_text(key: str, default: str = "", **values: object) -> str:
    template = _CONFIG_I18N.t("de", f"config.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


class AriaRuntimeConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8800
    log_level: str = "info"
    public_url: str = ""


class LLMConfig(BaseModel):
    model: str
    api_base: str | None = None
    api_key: str = ""
    temperature: float | None = 0.4
    max_tokens: int = 4096
    timeout_seconds: int = 60


class WebLLMConfig(LLMConfig):
    model: str = ""
    enabled: bool = False
    profile: str = ""
    transport: Literal["openai_responses", "anthropic_native", "openai_web_search_options"] = "openai_responses"
    search_context_size: Literal["low", "medium", "high"] = "high"
    max_search_uses: int = Field(default=3, ge=1, le=3)
    max_output_tokens: int = Field(default=1200, ge=1, le=8192)
    allowed_domains: list[str] = Field(default_factory=list)
    required_url_prefixes: list[str] = Field(default_factory=list)
    capability_verified_at: str = ""


class WebEvidenceConfig(BaseModel):
    enabled: bool = True
    collection: str = "aria_web_evidence"
    read_timeout_ms: int = Field(default=200, ge=10, le=2000)
    ttl_hours: int = Field(default=24, ge=1, le=720)


class EmbeddingsConfig(BaseModel):
    model: str = "nomic-embed-text"
    api_base: str | None = None
    api_key: str = ""
    timeout_seconds: int = 60


class MemoryConfig(BaseModel):
    enabled: bool = True
    backend: str = "qdrant"
    qdrant_url: str = "http://localhost:6334"
    qdrant_api_key: str = ""
    collection: str = "aria_memory"
    embedding_fingerprint: str = ""
    embedding_model: str = ""
    top_k: int = 3
    compression_summary_prompt: str = "prompts/recipes/memory_compress.md"
    collections: "MemoryCollectionsConfig" = Field(default_factory=lambda: MemoryCollectionsConfig())


class InventoryIndexConfig(BaseModel):
    enabled: bool = True
    cron: str = "17 */6 * * *"
    timezone: str = "Europe/Zurich"
    run_on_startup: bool = False
    keep_backup: bool = True
    score_threshold: float = 0.35
    candidate_limit: int = 12


class RoutingLanguageConfig(BaseModel):
    pass


class RoutingConfig(BaseModel):
    qdrant_connection_routing_enabled: bool = False
    qdrant_score_threshold: float = 0.72
    qdrant_candidate_limit: int = 5
    qdrant_ask_on_low_confidence: bool = True
    meta_catalog_strict_contract_enabled: bool = False

    def for_language(self, language: str | None) -> RoutingLanguageConfig:
        _ = language
        return RoutingLanguageConfig()


class AgenticLoopFeatureConfig(BaseModel):
    enabled: bool = True
    connection_inventory_enabled: bool = True
    personal_memory_recall_enabled: bool = True
    native_agent_memory_enabled: bool = True
    native_agent_connections_enabled: bool = True
    native_agent_admin_enabled: bool = True
    native_agent_admin_write_enabled: bool = True
    native_agent_write_notes_enabled: bool = True
    native_agent_write_memory_enabled: bool = True
    native_agent_ssh_enabled: bool = True
    native_agent_messaging_enabled: bool = True
    native_agent_infra_write_enabled: bool = True
    native_agent_recipe_execute_enabled: bool = True
    native_agent_recipe_learn_enabled: bool = True
    native_agent_memory_learn_enabled: bool = True
    native_agent_mcp_enabled: bool = False
    native_agent_mcp_vision_enabled: bool = True
    native_agent_mcp_vision_max_live_images: int = Field(default=4, ge=1, le=12)
    native_agent_mcp_vision_max_lifetime_images: int = Field(default=24, ge=1, le=96)
    native_tool_selector_top_k: int = Field(default=16, ge=1, le=128)
    native_agent_max_steps: int = Field(default=32, ge=1, le=64)
    native_agent_max_provider_calls: int = Field(default=32, ge=1, le=64)
    async_agent_job_sync_budget_seconds: float = Field(default=25.0, gt=0.0, lt=90.0)
    native_agent_budget_extension_steps: int = Field(default=32, ge=1, le=160)
    native_agent_budget_max_total: int = Field(default=160, ge=32, le=512)
    agent_job_retention_days: int = Field(default=14, ge=1, le=3650)
    agent_job_stale_paused_days: int = Field(default=7, ge=1, le=3650)
    native_web_debug_details: bool = False


class MCPServerConfig(BaseModel):
    transport: str = "sse"
    url: str = Field(repr=False)
    headers: dict[str, str] = Field(default_factory=dict, repr=False)
    enabled: bool = False
    trusted: bool = False
    title: str = ""
    description: str = ""
    call_timeout_seconds: float = Field(default=30.0, ge=5.0, le=900.0)


class PromptConfig(BaseModel):
    persona: str = "prompts/persona.md"
    skills_dir: str = "prompts/recipes/"


UI_THEME_OPTIONS = (
    "matrix",
    "sunset",
    "harbor",
    "paper",
    "cyberpunk",
    "cyberpunk-neo",
    "nyan-cat",
    "puke-unicorn",
    "pixel",
    "crt-amber",
    "deep-space",
)
UI_BACKGROUND_FILE_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg", ".svg", ".avif")
UI_BACKGROUND_DEFAULT = "grid-signal"
UI_BACKGROUND_LEGACY_ALIASES = {
    "grid": "grid-signal",
    "aurora": "aurora-glow",
    "mesh": "mesh-weave",
    "nodes": "nodes-field",
}


def _ui_static_dir(static_dir: Path | None = None) -> Path:
    if static_dir is not None:
        return static_dir
    return Path(__file__).resolve().parents[2] / "static"


def _ui_static_base_dir(static_dir: Path) -> Path:
    try:
        return static_dir.resolve().parents[1]
    except IndexError:
        return Path(__file__).resolve().parents[2]


def _background_file_slug(path: Path) -> str:
    stem = path.stem
    if stem.startswith("background-"):
        return stem[len("background-") :].strip().lower()
    return ""


def _background_label_from_slug(slug: str) -> str:
    clean = str(slug or "").strip().replace("_", "-")
    raw_parts = [part for part in clean.split("-") if part]
    if not raw_parts:
        return "Custom Background"
    acronyms = {
        "ai": "AI",
        "api": "API",
        "aria": "ARIA",
        "crt": "CRT",
        "css": "CSS",
        "html": "HTML",
        "json": "JSON",
        "lcars": "LCARS",
        "llm": "LLM",
        "pdf": "PDF",
        "png": "PNG",
        "qdrant": "Qdrant",
        "rss": "RSS",
        "sftp": "SFTP",
        "smb": "SMB",
        "ssh": "SSH",
        "svg": "SVG",
        "ui": "UI",
        "webp": "WebP",
    }
    parts: list[str] = []
    idx = 0
    while idx < len(raw_parts):
        part = raw_parts[idx]
        if part.isdigit() and idx + 1 < len(raw_parts) and raw_parts[idx + 1] == "bit":
            parts.append(f"{part}-Bit")
            idx += 2
            continue
        parts.append(acronyms.get(part, part.capitalize() if not part.isdigit() else part))
        idx += 1
    return " ".join(parts)


def _canonical_ui_background_slug(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    return UI_BACKGROUND_LEGACY_ALIASES.get(clean, clean)


def discover_ui_background_files(static_dir: Path | None = None) -> list[dict[str, str]]:
    root = _ui_static_dir(static_dir)
    base_dir = _ui_static_base_dir(root)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for ext in UI_BACKGROUND_FILE_EXTENSIONS:
        for path in sorted(root.glob(f"background-*{ext}")):
            slug = _background_file_slug(path)
            if not slug or slug in seen:
                continue
            owned_path = module_static_asset_prefix_path("navigation_shell", path.name, base_dir)
            if owned_path is None:
                raise RuntimeError(f"navigation_shell static asset prefix is not registered: {path.name}")
            seen.add(slug)
            rows.append(
                {
                    "value": slug,
                    "label_key": "",
                    "fallback": _background_label_from_slug(slug),
                    "asset_url": f"/static/{path.name}",
                }
            )
    return rows


def resolve_ui_background_asset_url(value: str | None, static_dir: Path | None = None) -> str | None:
    clean = _canonical_ui_background_slug(value)
    if not clean:
        return None
    for row in discover_ui_background_files(static_dir):
        if row["value"] == clean:
            return row["asset_url"]
    return None


def ui_background_values(static_dir: Path | None = None) -> tuple[str, ...]:
    return tuple(row["value"] for row in discover_ui_background_files(static_dir))


def normalize_ui_theme(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in UI_THEME_OPTIONS else "matrix"


def normalize_ui_background(value: str | None, static_dir: Path | None = None) -> str:
    clean = _canonical_ui_background_slug(value)
    options = ui_background_values(static_dir)
    if clean and clean in options:
        return clean
    if UI_BACKGROUND_DEFAULT in options:
        return UI_BACKGROUND_DEFAULT
    if options:
        return options[0]
    return UI_BACKGROUND_DEFAULT


class UIConfig(BaseModel):
    title: str = "ARIA"
    debug_mode: bool = False
    language: str = "de"
    theme: str = "matrix"
    background: str = "grid"


class GuardrailConfig(BaseModel):
    kind: str = "ssh_command"
    title: str = ""
    description: str = ""
    connection_kinds: list[str] = Field(default_factory=list)
    allow_terms: list[str] = Field(default_factory=list)
    deny_terms: list[str] = Field(default_factory=list)
    allow_recipe_ids: list[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    enabled: bool = True
    db_path: str = "data/auth/aria_secure.sqlite"
    bootstrap_locked: bool = True
    session_max_age_seconds: int = 60 * 60 * 12
    guardrails: dict[str, GuardrailConfig] = Field(default_factory=dict)


class TokenTrackingConfig(BaseModel):
    enabled: bool = True
    log_file: str = "data/logs/tokens.jsonl"
    retention_days: int = 90


class ChatPricingModelConfig(BaseModel):
    input_per_million: float = 0.0
    output_per_million: float = 0.0
    native_web_search_per_call: float | None = None
    source_name: str = ""
    source_url: str = ""
    verified_at: str = ""
    notes: str = ""


class EmbeddingPricingModelConfig(BaseModel):
    input_per_million: float = 0.0
    source_name: str = ""
    source_url: str = ""
    verified_at: str = ""
    notes: str = ""


class PricingConfig(BaseModel):
    enabled: bool = False
    currency: str = "USD"
    last_updated: str = ""
    default_source_name: str = ""
    default_source_url: str = ""
    source: str = "litellm_github"
    litellm_cache_file: str = "data/pricing/litellm_model_prices.json"
    refresh_interval_days: int = 7
    model_aliases: dict[str, str] = Field(default_factory=dict)
    chat_models: dict[str, ChatPricingModelConfig] = Field(default_factory=dict)
    embedding_models: dict[str, EmbeddingPricingModelConfig] = Field(default_factory=dict)


class APIChannelConfig(BaseModel):
    enabled: bool = True
    auth_token: str = ""


class ChannelsConfig(BaseModel):
    api: APIChannelConfig = Field(default_factory=APIChannelConfig)


class ConnectionMetaConfig(BaseModel):
    title: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SSHConnectionConfig(ConnectionMetaConfig):
    host: str = ""
    port: int = 22
    user: str = ""
    service_url: str = ""
    key_path: str = ""
    timeout_seconds: int = 20
    strict_host_key_checking: str = "accept-new"
    allow_commands: list[str] = Field(default_factory=list)
    guardrail_ref: str = ""


class DiscordConnectionConfig(ConnectionMetaConfig):
    webhook_url: str = ""
    timeout_seconds: int = 10
    send_test_messages: bool = True
    allow_skill_messages: bool = True
    alert_skill_errors: bool = False
    alert_connection_changes: bool = False
    alert_system_events: bool = False


class SFTPConnectionConfig(ConnectionMetaConfig):
    host: str = ""
    port: int = 22
    user: str = ""
    service_url: str = ""
    password: str = ""
    key_path: str = ""
    timeout_seconds: int = 10
    root_path: str = ""
    guardrail_ref: str = ""


class SMBConnectionConfig(ConnectionMetaConfig):
    host: str = ""
    port: int = 445
    share: str = ""
    user: str = ""
    password: str = ""
    timeout_seconds: int = 10
    root_path: str = ""
    guardrail_ref: str = ""


class WebhookConnectionConfig(ConnectionMetaConfig):
    url: str = ""
    timeout_seconds: int = 10
    method: str = "POST"
    content_type: str = "application/json"
    guardrail_ref: str = ""


class InboundWebhookConnectionConfig(ConnectionMetaConfig):
    enabled: bool = True
    provider_profile: str = "generic"
    allowed_content_types: list[str] = Field(
        default_factory=lambda: [
            "application/json",
            "application/x-www-form-urlencoded",
            "text/plain",
        ]
    )
    max_body_bytes: int = Field(default=65536, ge=1, le=10 * 1024 * 1024)
    routing_policy: Literal["log_only"] = "log_only"
    store_raw_body: bool = False
    max_events: int = Field(default=1000, ge=1, le=100_000)


class EmailConnectionConfig(ConnectionMetaConfig):
    smtp_host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    from_email: str = ""
    to_email: str = ""
    timeout_seconds: int = 10
    starttls: bool = True
    use_ssl: bool = False


class IMAPConnectionConfig(ConnectionMetaConfig):
    host: str = ""
    port: int = 993
    user: str = ""
    password: str = ""
    mailbox: str = "INBOX"
    timeout_seconds: int = 10
    use_ssl: bool = True


class HTTPAPIConnectionConfig(ConnectionMetaConfig):
    base_url: str = ""
    auth_token: str = ""
    timeout_seconds: int = 10
    health_path: str = "/"
    method: str = "GET"
    guardrail_ref: str = ""


class GoogleCalendarConnectionConfig(ConnectionMetaConfig):
    calendar_id: str = "primary"
    ical_url: str = ""
    timeout_seconds: int = 10


class RSSConnectionConfig(ConnectionMetaConfig):
    feed_url: str = ""
    group_name: str = ""
    timeout_seconds: int = 10
    poll_interval_minutes: int = 60


class WebsiteConnectionConfig(ConnectionMetaConfig):
    url: str = ""
    group_name: str = ""
    timeout_seconds: int = 10


class RSSRuntimeConfig(BaseModel):
    poll_interval_minutes: int = 60


class MQTTConnectionConfig(ConnectionMetaConfig):
    host: str = ""
    port: int = 1883
    user: str = ""
    password: str = ""
    topic: str = ""
    timeout_seconds: int = 10
    use_tls: bool = False


class ConnectionsConfig(BaseModel):
    ssh: dict[str, SSHConnectionConfig] = Field(default_factory=dict)
    discord: dict[str, DiscordConnectionConfig] = Field(default_factory=dict)
    sftp: dict[str, SFTPConnectionConfig] = Field(default_factory=dict)
    smb: dict[str, SMBConnectionConfig] = Field(default_factory=dict)
    webhook: dict[str, WebhookConnectionConfig] = Field(default_factory=dict)
    inbound_webhook: dict[str, InboundWebhookConnectionConfig] = Field(default_factory=dict)
    email: dict[str, EmailConnectionConfig] = Field(default_factory=dict)
    imap: dict[str, IMAPConnectionConfig] = Field(default_factory=dict)
    http_api: dict[str, HTTPAPIConnectionConfig] = Field(default_factory=dict)
    google_calendar: dict[str, GoogleCalendarConnectionConfig] = Field(default_factory=dict)
    rss: dict[str, RSSConnectionConfig] = Field(default_factory=dict)
    website: dict[str, WebsiteConnectionConfig] = Field(default_factory=dict)
    mqtt: dict[str, MQTTConnectionConfig] = Field(default_factory=dict)


class MemoryCollectionTypeConfig(BaseModel):
    prefix: str
    weight: float
    top_k: int
    dedup_threshold: float | None = None
    time_decay: bool = False
    compress_after_days: int | None = None
    archive_after_days: int | None = None
    monthly_after_days: int = 30


class MemoryCollectionsConfig(BaseModel):
    facts: MemoryCollectionTypeConfig = Field(
        default_factory=lambda: MemoryCollectionTypeConfig(
            prefix="aria_facts",
            weight=1.0,
            top_k=2,
            dedup_threshold=0.85,
        )
    )
    preferences: MemoryCollectionTypeConfig = Field(
        default_factory=lambda: MemoryCollectionTypeConfig(
            prefix="aria_preferences",
            weight=0.8,
            top_k=1,
            dedup_threshold=0.80,
        )
    )
    sessions: MemoryCollectionTypeConfig = Field(
        default_factory=lambda: MemoryCollectionTypeConfig(
            prefix="aria_sessions",
            weight=0.5,
            top_k=2,
            time_decay=True,
            compress_after_days=7,
            archive_after_days=90,
        )
    )
    knowledge: MemoryCollectionTypeConfig = Field(
        default_factory=lambda: MemoryCollectionTypeConfig(
            prefix="aria_knowledge",
            weight=0.7,
            top_k=2,
            dedup_threshold=0.90,
        )
    )


class Settings(BaseModel):
    aria: AriaRuntimeConfig = Field(default_factory=AriaRuntimeConfig)
    llm: LLMConfig
    web_llm: WebLLMConfig = Field(default_factory=WebLLMConfig)
    web_evidence: WebEvidenceConfig = Field(default_factory=WebEvidenceConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    inventory_index: InventoryIndexConfig = Field(default_factory=InventoryIndexConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    agentic_loop: AgenticLoopFeatureConfig = Field(default_factory=AgenticLoopFeatureConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)
    token_tracking: TokenTrackingConfig = Field(default_factory=TokenTrackingConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    connections: ConnectionsConfig = Field(default_factory=ConnectionsConfig)
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    rss: RSSRuntimeConfig = Field(default_factory=RSSRuntimeConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


def _resolve_config_path(config_path: str | Path = "config/config.yaml") -> Path:
    path = Path(config_path)
    if not path.is_absolute():
        path = path.resolve()
    return path


def _resolve_project_root(config_path: str | Path = "config/config.yaml") -> Path:
    return _resolve_config_path(config_path).parent.parent


def resolve_secrets_env_path(config_path: str | Path = "config/config.yaml") -> Path:
    return _resolve_config_path(config_path).parent / "secrets.env"


def read_secrets_env(config_path: str | Path = "config/config.yaml") -> dict[str, str]:
    path = resolve_secrets_env_path(config_path)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if raw.startswith("export "):
                raw = raw[len("export ") :].strip()
            if "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            if not key:
                continue
            values[key] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def get_env_value(name: str) -> str:
    return str(os.environ.get(name, "")).strip()


def get_secret_value(name: str, config_path: str | Path = "config/config.yaml") -> str:
    value = get_env_value(name)
    if value:
        return value
    return read_secrets_env(config_path).get(name, "").strip()


def write_secrets_env_value(name: str, value: str, config_path: str | Path = "config/config.yaml") -> None:
    path = resolve_secrets_env_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"export {name}={value}"
    existing_lines: list[str] = []
    if path.exists():
        try:
            existing_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            existing_lines = []
    updated = False
    new_lines: list[str] = []
    for current in existing_lines:
        raw = current.strip()
        normalized = raw[len("export ") :].strip() if raw.startswith("export ") else raw
        if normalized.startswith(f"{name}="):
            new_lines.append(line)
            updated = True
        else:
            new_lines.append(current)
    if not updated:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(line)
    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def ensure_secret_value(
    name: str,
    config_path: str | Path = "config/config.yaml",
    *,
    generator: Callable[[], str] | None = None,
) -> str:
    existing = get_secret_value(name, config_path)
    if existing:
        return existing
    generate = generator or (lambda: secrets.token_hex(32))
    created = str(generate()).strip()
    if not created:
        raise ValueError(f"Secret konnte nicht erzeugt werden: {name}")
    write_secrets_env_value(name, created, config_path)
    return created


def get_master_key(config_path: str | Path = "config/config.yaml") -> str:
    return get_secret_value("ARIA_MASTER_KEY", config_path)


def get_or_create_runtime_secret(name: str, config_path: str | Path = "config/config.yaml") -> str:
    return ensure_secret_value(name, config_path)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Konfigurationsdatei fehlt: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml muss ein Mapping/Objekt enthalten.")
    return data


def _convert_env_value(raw: str) -> Any:
    lower = raw.strip().lower()
    if lower in {"true", "false"}:
        return lower == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _has_active_profile_config(data: dict[str, Any], kind: str) -> bool:
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        return False
    active = profiles.get("active", {})
    if not isinstance(active, dict):
        return False
    active_name = str(active.get(kind, "") or "").strip()
    if not active_name:
        return False
    section = profiles.get(kind, {})
    if not isinstance(section, dict):
        return False
    return isinstance(section.get(active_name), dict)


def _apply_llm_role_profiles(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)
    profiles = merged.get("profiles", {})
    if not isinstance(profiles, dict):
        return merged
    active = profiles.get("active", {})
    llm_profiles = profiles.get("llm", {})
    if not isinstance(active, dict) or not isinstance(llm_profiles, dict):
        return merged

    main_ref = str(active.get("main_llm") or active.get("llm") or "").strip()
    if main_ref:
        active["main_llm"] = main_ref
        main_profile = llm_profiles.get(main_ref)
        if isinstance(main_profile, dict):
            resolved_main = dict(merged.get("llm", {}))
            for key in ("model", "api_base", "api_key", "temperature", "max_tokens", "timeout_seconds"):
                if key in main_profile:
                    resolved_main[key] = main_profile[key]
            merged["llm"] = resolved_main

    web_section = merged.get("web_llm", {})
    if not isinstance(web_section, dict):
        web_section = {}
    web_ref = str(active.get("web_llm") or web_section.get("profile") or "").strip()
    web_profile = llm_profiles.get(web_ref)
    if web_ref and isinstance(web_profile, dict):
        resolved = dict(web_section)
        for key in ("model", "api_base", "api_key", "temperature", "max_tokens", "timeout_seconds"):
            if key in web_profile:
                resolved[key] = web_profile[key]
        resolved["profile"] = web_ref
        merged["web_llm"] = resolved
    return merged


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "ARIA_ARIA_HOST": ("aria", "host"),
        "ARIA_ARIA_PORT": ("aria", "port"),
        "ARIA_ARIA_LOG_LEVEL": ("aria", "log_level"),
        "ARIA_PUBLIC_URL": ("aria", "public_url"),
        "ARIA_LLM_MODEL": ("llm", "model"),
        "ARIA_LLM_API_BASE": ("llm", "api_base"),
        "ARIA_LLM_API_KEY": ("llm", "api_key"),
        "ARIA_LLM_TEMPERATURE": ("llm", "temperature"),
        "ARIA_LLM_MAX_TOKENS": ("llm", "max_tokens"),
        "ARIA_LLM_TIMEOUT_SECONDS": ("llm", "timeout_seconds"),
        "ARIA_WEB_LLM_ENABLED": ("web_llm", "enabled"),
        "ARIA_WEB_LLM_MODEL": ("web_llm", "model"),
        "ARIA_WEB_LLM_API_BASE": ("web_llm", "api_base"),
        "ARIA_WEB_LLM_API_KEY": ("web_llm", "api_key"),
        "ARIA_WEB_LLM_TRANSPORT": ("web_llm", "transport"),
        "ARIA_WEB_LLM_SEARCH_CONTEXT_SIZE": ("web_llm", "search_context_size"),
        "ARIA_WEB_LLM_MAX_SEARCH_USES": ("web_llm", "max_search_uses"),
        "ARIA_EMBEDDINGS_MODEL": ("embeddings", "model"),
        "ARIA_EMBEDDINGS_API_BASE": ("embeddings", "api_base"),
        "ARIA_EMBEDDINGS_API_KEY": ("embeddings", "api_key"),
        "ARIA_EMBEDDINGS_TIMEOUT_SECONDS": ("embeddings", "timeout_seconds"),
        "ARIA_MEMORY_ENABLED": ("memory", "enabled"),
        "ARIA_MEMORY_BACKEND": ("memory", "backend"),
        "ARIA_QDRANT_URL": ("memory", "qdrant_url"),
        "ARIA_QDRANT_API_KEY": ("memory", "qdrant_api_key"),
        "ARIA_MEMORY_COLLECTION": ("memory", "collection"),
        "ARIA_MEMORY_TOP_K": ("memory", "top_k"),
        "ARIA_MEMORY_COMPRESSION_SUMMARY_PROMPT": ("memory", "compression_summary_prompt"),
        "ARIA_PROMPTS_PERSONA": ("prompts", "persona"),
        "ARIA_PROMPTS_SKILLS_DIR": ("prompts", "skills_dir"),
        "ARIA_TOKEN_TRACKING_ENABLED": ("token_tracking", "enabled"),
        "ARIA_TOKEN_LOG_FILE": ("token_tracking", "log_file"),
        "ARIA_TOKEN_RETENTION_DAYS": ("token_tracking", "retention_days"),
        "ARIA_PRICING_ENABLED": ("pricing", "enabled"),
        "ARIA_API_AUTH_TOKEN": ("channels", "api", "auth_token"),
        "ARIA_UI_TITLE": ("ui", "title"),
        "ARIA_UI_DEBUG_MODE": ("ui", "debug_mode"),
        "ARIA_UI_LANGUAGE": ("ui", "language"),
        "ARIA_UI_THEME": ("ui", "theme"),
        "ARIA_UI_BACKGROUND": ("ui", "background"),
        "ARIA_SECURITY_ENABLED": ("security", "enabled"),
        "ARIA_SECURITY_DB_PATH": ("security", "db_path"),
        "ARIA_SECURITY_BOOTSTRAP_LOCKED": ("security", "bootstrap_locked"),
        "ARIA_SECURITY_SESSION_MAX_AGE_SECONDS": ("security", "session_max_age_seconds"),
    }

    merged = dict(data)
    llm_profile_active = _has_active_profile_config(data, "llm")
    embeddings_profile_active = _has_active_profile_config(data, "embeddings")
    for env_name, path in mapping.items():
        if env_name not in os.environ:
            continue
        raw_value = str(os.environ[env_name])
        if not raw_value.strip():
            continue
        if env_name == "ARIA_WEB_LLM_SEARCH_CONTEXT_SIZE":
            normalized = raw_value.strip().lower()
            raw_value = (
                normalized
                if normalized in {"low", "medium", "high"}
                else WebLLMConfig().search_context_size
            )
        top_level = path[0]
        if top_level == "llm" and llm_profile_active:
            continue
        if top_level == "embeddings" and embeddings_profile_active:
            continue

        cursor = merged
        for section in path[:-1]:
            cursor.setdefault(section, {})
            cursor = cursor[section]
        cursor[path[-1]] = _convert_env_value(raw_value)

    return merged


def _apply_secure_store_overrides(data: dict[str, Any], config_path: Path) -> dict[str, Any]:
    security = data.get("security", {})
    if not isinstance(security, dict):
        security = {}
    enabled = bool(security.get("enabled", True))
    if not enabled:
        return data

    master_key = get_master_key(config_path)
    if not master_key:
        return data

    db_rel = str(security.get("db_path", "data/auth/aria_secure.sqlite")).strip() or "data/auth/aria_secure.sqlite"
    db_path = Path(db_rel)
    root = _resolve_project_root(config_path)
    if not db_path.is_absolute():
        db_path = (root / db_path).resolve()
    if not db_path.exists():
        return data

    from aria.modules.security_storage.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key

    store = SecureConfigStore(
        config=SecureStoreConfig(db_path=db_path, enabled=True),
        master_key=decode_master_key(master_key),
    )

    merged = dict(data)
    merged.setdefault("llm", {})
    merged.setdefault("web_llm", {})
    merged.setdefault("embeddings", {})
    merged.setdefault("channels", {})
    if not isinstance(merged["channels"], dict):
        merged["channels"] = {}
    merged["channels"].setdefault("api", {})
    if not isinstance(merged["channels"]["api"], dict):
        merged["channels"]["api"] = {}

    llm_key = store.get_secret("llm.api_key", default="")
    embeddings_key = store.get_secret("embeddings.api_key", default="")
    api_auth = store.get_secret("channels.api.auth_token", default="")
    qdrant_api_key = store.get_secret("memory.qdrant_api_key", default="")

    if llm_key:
        merged["llm"]["api_key"] = llm_key
    if embeddings_key:
        merged["embeddings"]["api_key"] = embeddings_key
    if api_auth:
        merged["channels"]["api"]["auth_token"] = api_auth
    if qdrant_api_key:
        merged.setdefault("memory", {})
        if not isinstance(merged["memory"], dict):
            merged["memory"] = {}
        merged["memory"]["qdrant_api_key"] = qdrant_api_key

    merged.setdefault("connections", {})
    if not isinstance(merged["connections"], dict):
        merged["connections"] = {}
    merged["connections"].setdefault("discord", {})
    if not isinstance(merged["connections"]["discord"], dict):
        merged["connections"]["discord"] = {}
    merged["connections"].setdefault("sftp", {})
    if not isinstance(merged["connections"]["sftp"], dict):
        merged["connections"]["sftp"] = {}
    merged["connections"].setdefault("smb", {})
    if not isinstance(merged["connections"]["smb"], dict):
        merged["connections"]["smb"] = {}
    merged["connections"].setdefault("webhook", {})
    if not isinstance(merged["connections"]["webhook"], dict):
        merged["connections"]["webhook"] = {}
    merged["connections"].setdefault("email", {})
    if not isinstance(merged["connections"]["email"], dict):
        merged["connections"]["email"] = {}
    merged["connections"].setdefault("imap", {})
    if not isinstance(merged["connections"]["imap"], dict):
        merged["connections"]["imap"] = {}
    merged["connections"].setdefault("http_api", {})
    if not isinstance(merged["connections"]["http_api"], dict):
        merged["connections"]["http_api"] = {}
    merged["connections"].setdefault("google_calendar", {})
    if not isinstance(merged["connections"]["google_calendar"], dict):
        merged["connections"]["google_calendar"] = {}
    merged["connections"].setdefault("rss", {})
    if not isinstance(merged["connections"]["rss"], dict):
        merged["connections"]["rss"] = {}
    merged["connections"].setdefault("mqtt", {})
    if not isinstance(merged["connections"]["mqtt"], dict):
        merged["connections"]["mqtt"] = {}
    for ref, row in list(merged["connections"]["discord"].items()):
        if not isinstance(row, dict):
            continue
        webhook = store.get_secret(f"connections.discord.{ref}.webhook_url", default="")
        if webhook:
            row["webhook_url"] = webhook
    for ref, row in list(merged["connections"]["sftp"].items()):
        if not isinstance(row, dict):
            continue
        password = store.get_secret(f"connections.sftp.{ref}.password", default="")
        if password:
            row["password"] = password
    for ref, row in list(merged["connections"]["smb"].items()):
        if not isinstance(row, dict):
            continue
        password = store.get_secret(f"connections.smb.{ref}.password", default="")
        if password:
            row["password"] = password
    for ref, row in list(merged["connections"]["webhook"].items()):
        if not isinstance(row, dict):
            continue
        secret_url = store.get_secret(f"connections.webhook.{ref}.url", default="")
        if secret_url:
            row["url"] = secret_url
    for ref, row in list(merged["connections"]["email"].items()):
        if not isinstance(row, dict):
            continue
        password = store.get_secret(f"connections.email.{ref}.password", default="")
        if password:
            row["password"] = password
    for ref, row in list(merged["connections"]["imap"].items()):
        if not isinstance(row, dict):
            continue
        password = store.get_secret(f"connections.imap.{ref}.password", default="")
        if password:
            row["password"] = password
    for ref, row in list(merged["connections"]["http_api"].items()):
        if not isinstance(row, dict):
            continue
        auth_token = store.get_secret(f"connections.http_api.{ref}.auth_token", default="")
        if auth_token:
            row["auth_token"] = auth_token
    for ref, row in list(merged["connections"]["google_calendar"].items()):
        if not isinstance(row, dict):
            continue
        ical_url = store.get_secret(f"connections.google_calendar.{ref}.ical_url", default="")
        if ical_url:
            row["ical_url"] = ical_url
    for ref, row in list(merged["connections"]["mqtt"].items()):
        if not isinstance(row, dict):
            continue
        password = store.get_secret(f"connections.mqtt.{ref}.password", default="")
        if password:
            row["password"] = password

    # Fallback from active profile secrets if base key not set.
    profiles = merged.get("profiles", {})
    if isinstance(profiles, dict):
        active = profiles.get("active", {})
        if isinstance(active, dict):
            active_llm = str(active.get("llm", "")).strip()
            active_web_llm = str(active.get("web_llm", "")).strip()
            active_embeddings = str(active.get("embeddings", "")).strip()
            if not merged["llm"].get("api_key") and active_llm:
                key = store.get_secret(f"profiles.llm.{active_llm}.api_key", default="")
                if key:
                    merged["llm"]["api_key"] = key
            if not merged["web_llm"].get("api_key") and active_web_llm:
                key = store.get_secret(f"profiles.llm.{active_web_llm}.api_key", default="")
                if key:
                    merged["web_llm"]["api_key"] = key
            if not merged["embeddings"].get("api_key") and active_embeddings:
                key = store.get_secret(f"profiles.embeddings.{active_embeddings}.api_key", default="")
                if key:
                    merged["embeddings"]["api_key"] = key

    return merged


def load_settings(config_path: str | Path = "config/config.yaml") -> Settings:
    path = Path(config_path)
    raw = _read_yaml(path)
    pricing_section = raw.get("pricing")
    if isinstance(pricing_section, dict):
        if pricing_section.get("model_aliases") is None:
            pricing_section["model_aliases"] = {}
        if pricing_section.get("chat_models") is None:
            pricing_section["chat_models"] = {}
        if pricing_section.get("embedding_models") is None:
            pricing_section["embedding_models"] = {}
    merged = _apply_llm_role_profiles(raw)
    merged = _apply_env_overrides(merged)
    merged = _apply_secure_store_overrides(merged, path)
    merged.setdefault("connections", {})
    if not isinstance(merged["connections"], dict):
        merged["connections"] = {}
    merged.setdefault("ui", {})
    if not isinstance(merged["ui"], dict):
        merged["ui"] = {}
    merged["ui"]["theme"] = normalize_ui_theme(merged["ui"].get("theme"))
    merged["ui"]["background"] = normalize_ui_background(merged["ui"].get("background"))
    try:
        return Settings.model_validate(merged)
    except ValidationError as exc:
        raise ValueError(_config_text("invalid_configuration", "Invalid configuration in {path}: {error}", path=path, error=exc)) from exc
