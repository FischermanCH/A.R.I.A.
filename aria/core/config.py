from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import BaseModel, Field, ValidationError


class AriaRuntimeConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8800
    log_level: str = "info"
    public_url: str = ""


class LLMConfig(BaseModel):
    model: str
    api_base: str | None = None
    api_key: str = ""
    temperature: float = 0.4
    max_tokens: int = 4096
    timeout_seconds: int = 60


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
    top_k: int = 3
    compression_summary_prompt: str = "prompts/skills/memory_compress.md"
    collections: "MemoryCollectionsConfig" = Field(default_factory=lambda: MemoryCollectionsConfig())


class AutoMemoryConfig(BaseModel):
    enabled: bool = True
    session_recall_top_k: int = 4
    user_recall_top_k: int = 3
    max_facts_per_message: int = 3


class RoutingLanguageConfig(BaseModel):
    memory_store_keywords: list[str] = Field(default_factory=list)
    memory_recall_keywords: list[str] = Field(default_factory=list)
    memory_store_prefixes: list[str] = Field(default_factory=list)
    memory_recall_cleanup_keywords: list[str] = Field(default_factory=list)
    memory_forget_keywords: list[str] = Field(default_factory=list)


class RoutingConfig(BaseModel):
    memory_store_keywords: list[str] = Field(
        default_factory=lambda: ["merk", "speicher", "vergiss nicht", "notier"]
    )
    memory_recall_keywords: list[str] = Field(
        default_factory=lambda: [
            "erinnerst",
            "weisst du noch",
            "weisst du noch",
            "was weisst du",
            "was weisst du",
            "letztes mal",
            "gespeichert",
            "was weisst du über",
            "was weisst du über",
        ]
    )
    memory_store_prefixes: list[str] = Field(
        default_factory=lambda: [
            "merk dir, dass ",
            "merk dir dass ",
            "merk dir ",
            "speichere, dass ",
            "speichere dass ",
            "speichere ",
            "notier dir, dass ",
            "notier dir dass ",
            "notier dir ",
            "vergiss nicht, dass ",
            "vergiss nicht dass ",
            "vergiss nicht ",
        ]
    )
    memory_recall_cleanup_keywords: list[str] = Field(
        default_factory=lambda: [
            "erinnerst du dich",
            "weisst du noch",
            "weisst du noch",
            "gespeichert",
            "letztes mal",
        ]
    )
    memory_forget_keywords: list[str] = Field(
        default_factory=lambda: [
            "vergiss",
            "lösch",
            "lösch",
            "entfern",
            "delete",
            "remove",
        ]
    )
    default: RoutingLanguageConfig | None = None
    languages: dict[str, RoutingLanguageConfig] = Field(default_factory=dict)

    def _base_profile(self) -> RoutingLanguageConfig:
        if self.default is not None:
            return RoutingLanguageConfig(
                memory_store_keywords=list(self.default.memory_store_keywords),
                memory_recall_keywords=list(self.default.memory_recall_keywords),
                memory_store_prefixes=list(self.default.memory_store_prefixes),
                memory_recall_cleanup_keywords=list(self.default.memory_recall_cleanup_keywords),
                memory_forget_keywords=list(self.default.memory_forget_keywords),
            )
        return RoutingLanguageConfig(
            memory_store_keywords=list(self.memory_store_keywords),
            memory_recall_keywords=list(self.memory_recall_keywords),
            memory_store_prefixes=list(self.memory_store_prefixes),
            memory_recall_cleanup_keywords=list(self.memory_recall_cleanup_keywords),
            memory_forget_keywords=list(self.memory_forget_keywords),
        )

    def for_language(self, language: str | None) -> RoutingLanguageConfig:
        base = self._base_profile()
        lang_key = str(language or "").strip().lower()
        if not lang_key:
            return base

        override = self.languages.get(lang_key)
        if override is None:
            return base

        return RoutingLanguageConfig(
            memory_store_keywords=list(override.memory_store_keywords or base.memory_store_keywords),
            memory_recall_keywords=list(override.memory_recall_keywords or base.memory_recall_keywords),
            memory_store_prefixes=list(override.memory_store_prefixes or base.memory_store_prefixes),
            memory_recall_cleanup_keywords=list(
                override.memory_recall_cleanup_keywords or base.memory_recall_cleanup_keywords
            ),
            memory_forget_keywords=list(override.memory_forget_keywords or base.memory_forget_keywords),
        )


class PromptConfig(BaseModel):
    persona: str = "prompts/persona.md"
    skills_dir: str = "prompts/skills/"


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
UI_BACKGROUND_OPTIONS = ("grid", "aurora", "mesh", "nodes")


def normalize_ui_theme(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in UI_THEME_OPTIONS else "matrix"


def normalize_ui_background(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in UI_BACKGROUND_OPTIONS else "grid"


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
    allow_terms: list[str] = Field(default_factory=list)
    deny_terms: list[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    enabled: bool = True
    db_path: str = "data/auth/aria_secure.sqlite"
    bootstrap_locked: bool = True
    session_max_age_seconds: int = 60 * 60 * 12
    guardrails: dict[str, GuardrailConfig] = Field(default_factory=dict)


class TokenTrackingConfig(BaseModel):
    enabled: bool = True
    log_file: str = "data/logs/tokens.jsonl"
    retention_days: int = 30


class ChatPricingModelConfig(BaseModel):
    input_per_million: float = 0.0
    output_per_million: float = 0.0
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
    alert_safe_fix: bool = False
    alert_connection_changes: bool = False
    alert_system_events: bool = False


class SFTPConnectionConfig(ConnectionMetaConfig):
    host: str = ""
    port: int = 22
    user: str = ""
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


class RSSConnectionConfig(ConnectionMetaConfig):
    feed_url: str = ""
    group_name: str = ""
    timeout_seconds: int = 10
    poll_interval_minutes: int = 60


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
    email: dict[str, EmailConnectionConfig] = Field(default_factory=dict)
    imap: dict[str, IMAPConnectionConfig] = Field(default_factory=dict)
    http_api: dict[str, HTTPAPIConnectionConfig] = Field(default_factory=dict)
    rss: dict[str, RSSConnectionConfig] = Field(default_factory=dict)
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
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    auto_memory: AutoMemoryConfig = Field(default_factory=AutoMemoryConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)
    token_tracking: TokenTrackingConfig = Field(default_factory=TokenTrackingConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    connections: ConnectionsConfig = Field(default_factory=ConnectionsConfig)
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
        "ARIA_AUTO_MEMORY_ENABLED": ("auto_memory", "enabled"),
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
    for env_name, path in mapping.items():
        if env_name not in os.environ:
            continue

        cursor = merged
        for section in path[:-1]:
            cursor.setdefault(section, {})
            cursor = cursor[section]
        cursor[path[-1]] = _convert_env_value(os.environ[env_name])

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

    from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key

    store = SecureConfigStore(
        config=SecureStoreConfig(db_path=db_path, enabled=True),
        master_key=decode_master_key(master_key),
    )

    merged = dict(data)
    merged.setdefault("llm", {})
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
            active_embeddings = str(active.get("embeddings", "")).strip()
            if not merged["llm"].get("api_key") and active_llm:
                key = store.get_secret(f"profiles.llm.{active_llm}.api_key", default="")
                if key:
                    merged["llm"]["api_key"] = key
            if not merged["embeddings"].get("api_key") and active_embeddings:
                key = store.get_secret(f"profiles.embeddings.{active_embeddings}.api_key", default="")
                if key:
                    merged["embeddings"]["api_key"] = key

    return merged


def load_settings(config_path: str | Path = "config/config.yaml") -> Settings:
    path = Path(config_path)
    raw = _read_yaml(path)
    memory_section = raw.get("memory")
    if isinstance(memory_section, dict):
        nested_auto_memory = memory_section.get("auto_memory")
        if isinstance(nested_auto_memory, dict) and "auto_memory" not in raw:
            # Backward/forward compatibility for docs that place auto_memory under memory.
            raw["auto_memory"] = nested_auto_memory
    pricing_section = raw.get("pricing")
    if isinstance(pricing_section, dict):
        if pricing_section.get("chat_models") is None:
            pricing_section["chat_models"] = {}
        if pricing_section.get("embedding_models") is None:
            pricing_section["embedding_models"] = {}
    merged = _apply_env_overrides(raw)
    merged = _apply_secure_store_overrides(merged, path)
    merged.setdefault("ui", {})
    if not isinstance(merged["ui"], dict):
        merged["ui"] = {}
    merged["ui"]["theme"] = normalize_ui_theme(merged["ui"].get("theme"))
    merged["ui"]["background"] = normalize_ui_background(merged["ui"].get("background"))
    try:
        return Settings.model_validate(merged)
    except ValidationError as exc:
        raise ValueError(f"Ungültige Konfiguration in {path}: {exc}") from exc
