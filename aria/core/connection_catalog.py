from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore


_CONNECTION_CATALOG_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")
_CONNECTION_CATALOG_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "connection_catalog.json"


def _load_connection_catalog_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_CONNECTION_CATALOG_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load connection catalog lexicon: {_CONNECTION_CATALOG_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_CONNECTION_CATALOG_LEXICON = _load_connection_catalog_lexicon()


def _catalog_lexicon_list(key: str) -> list[str]:
    raw = _CONNECTION_CATALOG_LEXICON.get(key, [])
    if not isinstance(raw, list):
        return []
    return [str(value).strip() for value in raw if str(value).strip()]


def _catalog_text(key: str, default: str = "", *, language: str = "de") -> str:
    return _CONNECTION_CATALOG_I18N.t(language, key, default or key)


def _config_text(key: str, default: str = "", *, language: str = "de") -> str:
    return _catalog_text(f"config_conn.{key}", default, language=language)


def _field_text(key: str, default: str = "", *, language: str = "de") -> str:
    return _catalog_text(f"connection_catalog.field.{key}", default, language=language)


COMMON_METADATA_FIELD_SPECS: dict[str, dict[str, Any]] = {
    "title": {"type": "str", "max_length": 160, "label": _field_text("title", "Title")},
    "description": {"type": "str", "max_length": 512, "label": _field_text("description", "Description")},
    "aliases": {"type": "list", "max_items": 12, "item_max_length": 80, "label": _field_text("aliases", "Aliases")},
    "tags": {"type": "list", "max_items": 12, "item_max_length": 40, "label": _field_text("tags", "Tags")},
}


@dataclass(frozen=True, slots=True)
class ConnectionRoutingSpec:
    semantic_suffixes: list[str] = field(default_factory=list)
    requested_ref_suffixes: list[str] = field(default_factory=list)
    requested_ref_prefixes: list[str] = field(default_factory=list)
    supported_actions: list[str] = field(default_factory=list)
    language_hints: list[str] = field(default_factory=list)
    preferred_action_candidates: dict[str, list[str]] = field(default_factory=dict)
    follow_up_starter_terms: list[str] = field(default_factory=list)
    follow_up_same_target_terms: list[str] = field(default_factory=list)
    follow_up_time_terms: list[str] = field(default_factory=list)
    follow_up_rewrite_prefix: str = ""

CONNECTION_FIELD_CHAT_CATALOG: dict[str, dict[str, Any]] = {
    "host": {
        "patterns": [r"\bhost\s+(\S+)"],
    },
    "service_url": {
        "patterns": [r"\b(?:service(?:_url)?|service-url|homepage|home-page|website|webseite|url)\s+(https?://\S+)"],
        "show_in_summary": False,
    },
    "smtp_host": {
        "patterns": [r"\b(?:smtp[_-]?host|smtp-host|host)\s+(\S+)"],
    },
    "webhook_url": {
        "patterns": [r"\b(?:webhook(?:_url)?|url)\s+(https?://\S+)"],
    },
    "feed_url": {
        "patterns": [r"\b(?:feed(?:_url)?|url)\s+(https?://\S+)"],
    },
    "url": {
        "patterns": [r"\burl\s+(https?://\S+)"],
    },
    "base_url": {
        "patterns": [r"\b(?:base[_-]?url|base-url|url)\s+(https?://\S+)"],
    },
    "language": {
        "patterns": [r"\b(?:lang|language|sprache)\s+([a-zA-Z-]{2,12})"],
    },
    "safe_search": {
        "patterns": [r"\b(?:safesearch|safe-search|jugendschutz)\s+(\d+)"],
    },
    "time_range": {
        "patterns": [r"\b(?:time[_-]?range|zeitraum)\s+(\S+)"],
    },
    "max_results": {
        "patterns": [r"\b(?:max[_-]?results|results|max)\s+(\d+)"],
    },
    "categories": {
        "patterns": [r'\b(?:categories|category|kategorien|kategorie)\s+"([^"]+)"'],
        "split_pattern": r"[;,]",
    },
    "engines": {
        "patterns": [r'\b(?:engines|engine|suchmaschinen)\s+"([^"]+)"'],
        "split_pattern": r"[;,]",
    },
    "health_path": {
        "patterns": [r"\b(?:health(?:[_-]?path)?|path)\s+(\/\S+)"],
    },
    "user": {
        "patterns": [r"\buser\s+(\S+)"],
    },
    "key_path": {
        "patterns": [r"\b(?:key|key_path|schluesselpfad|keypfad)\s+(\S+)"],
    },
    "share": {
        "patterns": [r"(?:^|\s)share\s+(\S+)"],
    },
    "root_path": {
        "patterns": [r"\b(?:pfad|path|root(?:_path)?)\s+(\S+)"],
    },
    "from_email": {
        "patterns": [r"\bfrom\s+(\S+)"],
    },
    "to_email": {
        "patterns": [r"\bto\s+(\S+)"],
    },
    "mailbox": {
        "patterns": [r"\bmailbox\s+(\S+)"],
    },
    "topic": {
        "patterns": [r"\btopic\s+(\S+)"],
    },
    "strict_host_key_checking": {
        "patterns": [r"\b(?:host-key|strict|checking)\s+(\S+)"],
    },
    "allow_commands": {
        "patterns": [r'\b(?:allow|erlaube|commands?)\s+"([^"]+)"'],
        "split_pattern": r"[;,]",
    },
    "guardrail_ref": {
        "patterns": [r"\b(?:guardrail|guardrails|profil|profile)\s+([a-zA-Z0-9._-]+)"],
    },
    "method": {
        "patterns": [r"\b(?:method|methode)\s+(\S+)"],
    },
    "content_type": {
        "patterns": [r"\b(?:content-type|content_type|contenttype)\s+(\S+)"],
    },
    "password": {
        "patterns": [r"\b(?:passwort|password)\s+(\S+)"],
        "show_in_summary": False,
    },
    "auth_token": {
        "patterns": [r"\b(?:auth[-_ ]?token|token)\s+(\S+)"],
        "show_in_summary": False,
    },
    "port": {
        "patterns": [r"\bport\s+(\d+)"],
        "show_in_summary": False,
    },
    "timeout_seconds": {
        "patterns": [r"\b(?:timeout|zeitlimit)\s+(\d+)"],
        "show_in_summary": False,
    },
    "send_test_messages": {"show_in_summary": False},
    "allow_skill_messages": {"show_in_summary": False},
    "alert_skill_errors": {"show_in_summary": False},
    "alert_safe_fix": {"show_in_summary": False},
    "alert_connection_changes": {"show_in_summary": False},
    "alert_system_events": {"show_in_summary": False},
    "starttls": {"show_in_summary": False},
    "use_ssl": {"show_in_summary": False},
    "use_tls": {"show_in_summary": False},
}


def normalize_connection_kind(kind: str) -> str:
    value = str(kind or "").strip().lower().replace("-", "_")
    if value == "smtp":
        return "email"
    if value == "http api":
        return "http_api"
    return value


CONNECTION_CATALOG: dict[str, dict[str, Any]] = {
    "ssh": {
        "label": "SSH",
        "icon": "ssh",
        "template_name": "config_connections_ssh.html",
        "status_meta": {
            "title_key": "config_conn.live_status",
            "title": "Live status of all profiles",
            "hint_key": "config_conn.live_status_hint",
            "hint": "ARIA checks all SSH profiles when this page opens and also right after saving a profile.",
            "empty_key": "config_conn.no_profiles_status_hint",
            "empty_text": "No SSH profiles yet. Save a profile and ARIA will test it automatically.",
        },
        "chat_aliases": ["ssh"],
        "chat_primary_field": "host",
        "chat_defaults": {
            "port": 22,
            "timeout_seconds": 20,
            "strict_host_key_checking": "accept-new",
            "allow_commands": [],
        },
        "menu_title_key": "config.connections_ssh_title",
        "menu_desc_key": "config.connections_ssh_desc",
        "example_ref": "mgmt-ssh",
        "config_page": "/config/connections/ssh",
        "ref_query": "ref",
        "toolbox_keywords": ["ssh", "server", "remote shell", "shell", "host"],
        "semantic_suffixes": ["ssh", "server", "host"],
        "requested_ref_suffixes": ["server", "host", "system", "node"],
        "requested_ref_prefixes": ["auf", "bei", "beim", "via", "von", "vom", "on", "from"],
        "routing_supported_actions": [
            "run command",
            "execute shell command",
            "server status",
            "health check",
            "uptime",
            "logs",
            "linux host",
            "befehl ausfuehren",
            "server pruefen",
        ],
        "routing_language_hints": ["run", "execute", "status", "uptime", "health", "fuehre", "starte", "pruefe"],
        "routing_preferred_action_candidates": {
            "status_like": ["ssh_run_command"],
            "bounded_planner": ["ssh_run_command"],
        },
        "routing_follow_up_starter_terms": ["und", "dann", "jetzt", "nochmal", "erneut", "wieder", "ok", "okay", "ansonsten"],
        "routing_follow_up_same_target_terms": [
            "dort",
            "da",
            "darauf",
            "dabei",
            "denselben",
            "demselben",
            "gleichen",
            "wieder dort",
            "nochmal dort",
            "gleicher server",
            "gleichen server",
            "gleicher host",
            "gleichen host",
            "gleiches profil",
            "selbes profil",
        ],
        "routing_follow_up_rewrite_prefix": "ssh",
        "create_insert_key": "connection_catalog.insert.ssh.create",
        "create_insert": _catalog_text("connection_catalog.insert.ssh.create", 'create ssh {ref} server.example.local user admin key /app/data/ssh_keys/main-ssh_ed25519 title "SSH Server" '),
        "update_insert_key": "connection_catalog.insert.ssh.update",
        "update_insert": _catalog_text("connection_catalog.insert.ssh.update", 'update ssh {ref} server.example.local user admin key /app/data/ssh_keys/main-ssh_ed25519 title "SSH Server" '),
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": _config_text("host", "Host")},
            "port": {"type": "int", "min": 1, "max": 65535, "label": _config_text("port", "Port")},
            "user": {"type": "str", "max_length": 255, "label": _config_text("user", "User")},
            "service_url": {"type": "str", "max_length": 512, "label": _config_text("ssh_service_url", "Service URL")},
            "key_path": {"type": "str", "max_length": 512, "label": _field_text("key_path", "Key path")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "strict_host_key_checking": {"type": "str", "max_length": 32, "label": _config_text("host_key_checking", "Host key checking")},
            "allow_commands": {"type": "list", "max_items": 20, "item_max_length": 200, "label": _config_text("allow_commands", "Allowed commands")},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": _field_text("guardrail_ref", "Guardrail profile")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "sftp": {
        "label": "SFTP",
        "icon": "sftp",
        "template_name": "config_connections_sftp.html",
        "chat_aliases": ["sftp"],
        "chat_primary_field": "host",
        "chat_defaults": {
            "port": 22,
            "timeout_seconds": 10,
            "root_path": "/",
        },
        "menu_title_key": "config_conn.sftp_title",
        "menu_desc_key": "config_conn.sftp_subtitle",
        "example_ref": "mgmt-sftp",
        "config_page": "/config/connections/sftp",
        "ref_query": "sftp_ref",
        "toolbox_keywords": ["sftp", "ssh datei", "dateiserver", "remote file", "server datei"],
        "semantic_suffixes": ["server", "host", "sftp"],
        "routing_supported_actions": [
            "read file",
            "list directory",
            "write file",
            "remote files",
            "datei lesen",
            "dateien anzeigen",
            "server dateien",
        ],
        "routing_language_hints": ["read", "list", "file", "directory", "lies", "zeige", "datei", "ordner"],
        "routing_preferred_action_candidates": {
            "default": ["sftp_list_files"],
            "list_like": ["sftp_list_files"],
            "read_like": ["sftp_read_file"],
            "write_like": ["sftp_write_file"],
        },
        "create_insert_key": "connection_catalog.insert.sftp.create",
        "create_insert": _catalog_text("connection_catalog.insert.sftp.create", 'create sftp {ref} files.example.local user backup path /data title "SFTP Server" '),
        "update_insert_key": "connection_catalog.insert.sftp.update",
        "update_insert": _catalog_text("connection_catalog.insert.sftp.update", 'update sftp {ref} files.example.local user backup path /data title "SFTP Server" '),
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": _config_text("host", "Host")},
            "port": {"type": "int", "min": 1, "max": 65535, "label": _config_text("port", "Port")},
            "user": {"type": "str", "max_length": 255, "label": _config_text("user", "User")},
            "service_url": {"type": "str", "max_length": 512, "label": _config_text("ssh_service_url", "Service URL")},
            "password": {"type": "str", "max_length": 512, "label": _field_text("password", "Password")},
            "key_path": {"type": "str", "max_length": 512, "label": _field_text("key_path", "Key path")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "root_path": {"type": "str", "max_length": 512, "label": _field_text("path", "Path")},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": _field_text("guardrail_ref", "Guardrail profile")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "smb": {
        "label": "SMB",
        "icon": "smb",
        "template_name": "config_connections_smb.html",
        "chat_aliases": ["smb"],
        "chat_primary_field": "host",
        "chat_defaults": {
            "port": 445,
            "timeout_seconds": 10,
            "root_path": "/",
        },
        "menu_title_key": "config_conn.smb_title",
        "menu_desc_key": "config_conn.smb_subtitle",
        "example_ref": "nas-share",
        "config_page": "/config/connections/smb",
        "ref_query": "smb_ref",
        "toolbox_keywords": ["smb", "share", "freigabe", "nas", "netzlaufwerk", "synology"],
        "semantic_suffixes": ["share", "nas", "freigabe"],
        "routing_supported_actions": [
            "read file",
            "list directory",
            "write file",
            "remote files",
            "datei lesen",
            "dateien anzeigen",
            "server dateien",
        ],
        "routing_language_hints": ["read", "list", "file", "directory", "lies", "zeige", "datei", "ordner"],
        "routing_preferred_action_candidates": {
            "default": ["smb_list_files"],
            "list_like": ["smb_list_files"],
            "read_like": ["smb_read_file"],
            "write_like": ["smb_write_file"],
        },
        "create_insert_key": "connection_catalog.insert.smb.create",
        "create_insert": _catalog_text("connection_catalog.insert.smb.create", 'create smb {ref} nas.example.local share docs user aria path / title "NAS Share" '),
        "update_insert_key": "connection_catalog.insert.smb.update",
        "update_insert": _catalog_text("connection_catalog.insert.smb.update", 'update smb {ref} nas.example.local share docs path / title "NAS Share" '),
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": _config_text("host", "Host")},
            "port": {"type": "int", "min": 1, "max": 65535, "label": _config_text("port", "Port")},
            "share": {"type": "str", "max_length": 255, "label": _config_text("smb_share", "Share")},
            "user": {"type": "str", "max_length": 255, "label": _config_text("user", "User")},
            "password": {"type": "str", "max_length": 512, "label": _field_text("password", "Password")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "root_path": {"type": "str", "max_length": 512, "label": _field_text("path", "Path")},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": _field_text("guardrail_ref", "Guardrail profile")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "discord": {
        "label": "Discord",
        "icon": "discord",
        "template_name": "config_connections_discord.html",
        "chat_aliases": ["discord"],
        "chat_primary_field": "webhook_url",
        "chat_defaults": {
            "timeout_seconds": 10,
            "send_test_messages": True,
            "allow_skill_messages": True,
            "alert_skill_errors": False,
            "alert_safe_fix": False,
            "alert_connection_changes": False,
            "alert_system_events": False,
        },
        "menu_title_key": "config_conn.discord_title",
        "menu_desc_key": "config_conn.discord_subtitle",
        "example_ref": "alerts-bot",
        "config_page": "/config/connections/discord",
        "ref_query": "discord_ref",
        "toolbox_keywords": ["discord", "alert", "alerts", "nachricht", "webhook"],
        "semantic_suffixes": ["discord", "channel"],
        "requested_ref_suffixes": ["channel", "kanal", "profile", "profil", "server"],
        "requested_ref_prefixes": ["discord", "an", "nach", "zu", "in", "to"],
        "routing_supported_actions": [
            "send message",
            "notify",
            "alert channel",
            "discord nachricht",
            "alarmieren",
            "meldung senden",
        ],
        "routing_language_hints": ["send", "notify", "alert", "sende", "schicke", "melde", "alarmiere"],
        "routing_preferred_action_candidates": {
            "default": ["discord_send_message"],
            "send_like": ["discord_send_message"],
        },
        "create_insert_key": "connection_catalog.insert.discord.create",
        "create_insert": _catalog_text("connection_catalog.insert.discord.create", 'create discord {ref} https://discord.example/webhook title "Alerts Bot" '),
        "update_insert_key": "connection_catalog.insert.discord.update",
        "update_insert": _catalog_text("connection_catalog.insert.discord.update", 'update discord {ref} title "Alerts Bot" '),
        "ui_sections": {
            "behaviour": {
                "title_key": "config_conn.discord_alerting_title",
                "title": _config_text("discord_alerting_title", "Discord alerting and behavior"),
                "hint_key": "config_conn.discord_alerting_hint",
                "hint": _config_text("discord_alerting_hint", "Control whether ARIA may send visible test posts and whether recipes may use this profile as a Discord target."),
            },
            "events": {
                "title_key": "config_conn.discord_event_routing_title",
                "title": _config_text("discord_event_routing_title", "ARIA event routing to Discord"),
                "hint_key": "config_conn.discord_event_routing_hint",
                "hint": _config_text("discord_event_routing_hint", "These categories turn Discord into a compact alert and log hub for ARIA."),
            },
        },
        "fields": {
            "webhook_url": {"type": "str", "max_length": 512, "label": _config_text("discord_webhook_url", "Webhook URL")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "send_test_messages": {
                "type": "bool",
                "label": _field_text("test_messages", "Test messages"),
                "section": "behaviour",
                "title_key": "config_conn.discord_send_test_messages",
                "title": _config_text("discord_send_test_messages", "Send test message to Discord"),
                "hint_key": "config_conn.discord_send_test_messages_hint",
                "hint": _config_text("discord_send_test_messages_hint", "When enabled, ARIA sends a visible handshake message during connection tests."),
                "toggle_key": "config_conn.discord_send_test_messages_toggle",
                "toggle": _config_text("discord_send_test_messages_toggle", "Enable test posts"),
            },
            "allow_skill_messages": {
                "type": "bool",
                "label": _field_text("recipe_messages", "Recipe messages"),
                "section": "behaviour",
                "title_key": "config_conn.discord_allow_skill_messages",
                "title": _config_text("discord_allow_skill_messages", "Allow recipe messages via this profile"),
                "hint_key": "config_conn.discord_allow_skill_messages_hint",
                "hint": _config_text("discord_allow_skill_messages_hint", "When disabled, recipes cannot use this Discord profile as a target."),
                "toggle_key": "config_conn.discord_allow_skill_messages_toggle",
                "toggle": _config_text("discord_allow_skill_messages_toggle", "Allow recipe target"),
            },
            "alert_skill_errors": {
                "type": "bool",
                "label": _field_text("recipe_errors", "Recipe errors"),
                "section": "events",
                "title_key": "config_conn.discord_alert_skill_errors",
                "title": _config_text("discord_alert_skill_errors", "Report recipe errors"),
                "hint_key": "config_conn.discord_alert_skill_errors_hint",
                "hint": _config_text("discord_alert_skill_errors_hint", "Send a message to Discord when a recipe run fails."),
                "toggle_key": "config_conn.discord_alert_skill_errors_toggle",
                "toggle": _config_text("discord_alert_skill_errors_toggle", "Send recipe errors to Discord"),
            },
            "alert_safe_fix": {
                "type": "bool",
                "label": _field_text("safe_fix", "Safe-fix"),
                "section": "events",
                "title_key": "config_conn.discord_alert_safe_fix",
                "title": _config_text("discord_alert_safe_fix", "Safe-fix events"),
                "hint_key": "config_conn.discord_alert_safe_fix_hint",
                "hint": _config_text("discord_alert_safe_fix_hint", "Send messages when a safe-fix is ready or has been executed."),
                "toggle_key": "config_conn.discord_alert_safe_fix_toggle",
                "toggle": _config_text("discord_alert_safe_fix_toggle", "Send safe-fix events"),
            },
            "alert_connection_changes": {
                "type": "bool",
                "label": _field_text("status_changes", "Status changes"),
                "section": "events",
                "title_key": "config_conn.discord_alert_connection_changes",
                "title": _config_text("discord_alert_connection_changes", "Connection status changes"),
                "hint_key": "config_conn.discord_alert_connection_changes_hint",
                "hint": _config_text("discord_alert_connection_changes_hint", "Send a message when a configured connection changes status."),
                "toggle_key": "config_conn.discord_alert_connection_changes_toggle",
                "toggle": _config_text("discord_alert_connection_changes_toggle", "Send status changes"),
            },
            "alert_system_events": {
                "type": "bool",
                "label": _field_text("system_events", "System events"),
                "section": "events",
                "title_key": "config_conn.discord_alert_system_events",
                "title": _config_text("discord_alert_system_events", "System events"),
                "hint_key": "config_conn.discord_alert_system_events_hint",
                "hint": _config_text("discord_alert_system_events_hint", "Send compact messages on ARIA startup and similar system events."),
                "toggle_key": "config_conn.discord_alert_system_events_toggle",
                "toggle": _config_text("discord_alert_system_events_toggle", "Send system events"),
            },
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "rss": {
        "label": "RSS",
        "icon": "rss",
        "template_name": "config_connections_rss.html",
        "chat_aliases": ["rss"],
        "chat_primary_field": "feed_url",
        "chat_defaults": {
            "group_name": "",
            "timeout_seconds": 10,
            "poll_interval_minutes": 60,
        },
        "menu_title_key": "config_conn.rss_title",
        "menu_desc_key": "config_conn.rss_subtitle",
        "example_ref": "beispiel-feed",
        "config_page": "/config/connections/rss",
        "ref_query": "rss_ref",
        "toolbox_keywords": ["rss", "feed", "news", "feeds", "meldung"],
        "semantic_suffixes": ["feed", "rss", "news"],
        "routing_supported_actions": [
            "read feed",
            "latest news",
            "headlines",
            "feed lesen",
            "neueste meldungen",
            "nachrichten",
        ],
        "routing_language_hints": ["news", "latest", "feed", "headlines", "neu", "meldungen", "nachrichten"],
        "routing_preferred_action_candidates": {
            "default": ["rss_read_feed"],
            "read_like": ["rss_read_feed"],
        },
        "create_insert_key": "connection_catalog.insert.rss.create",
        "create_insert": _catalog_text("connection_catalog.insert.rss.create", 'create rss {ref} https://example.org/feed.xml title "Example Feed" '),
        "update_insert_key": "connection_catalog.insert.rss.update",
        "update_insert": _catalog_text("connection_catalog.insert.rss.update", 'update rss {ref} title "Example Feed" '),
        "fields": {
            "feed_url": {"type": "str", "max_length": 512, "label": _config_text("rss_feed_url", "Feed URL")},
            "group_name": {
                "type": "str",
                "max_length": 64,
                "label": _config_text("rss_group_name", "Group / category"),
                "label_key": "config_conn.rss_group_name",
                "hint_key": "config_conn.rss_group_name_hint",
                "hint": _config_text("rss_group_name_hint", "Manually assigned groups stay unchanged during LLM refresh."),
            },
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "poll_interval_minutes": {"type": "int", "min": 1, "max": 10080, "label": _field_text("poll_interval_minutes", "Ping interval (minutes)")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "website": {
        "label": _config_text("website_title", "Watched websites"),
        "icon": "http_api",
        "template_name": "config_connections_websites.html",
        "chat_aliases": ["website", "webseite", "webseiten", "web page", "webseiten quelle"],
        "chat_primary_field": "url",
        "chat_defaults": {
            "group_name": "",
            "timeout_seconds": 10,
        },
        "menu_title_key": "config_conn.website_title",
        "menu_desc_key": "config_conn.website_subtitle",
        "example_ref": "aria-docs",
        "config_page": "/config/connections/websites",
        "ref_query": "website_ref",
        "toolbox_keywords": ["website", "webseite", "seite", "quelle", "link", "url", "beobachten"],
        "semantic_suffixes": ["website", "webseite", "seite", "quelle", "link"],
        "routing_supported_actions": [
            "read website",
            "open website source",
            "list observed websites",
            "webseite lesen",
            "quelle oeffnen",
            "beobachtete webseiten",
        ],
        "routing_language_hints": [
            "website",
            "webseite",
            "seite",
            "quelle",
            "lesen",
            "oeffne",
            *_catalog_lexicon_list("website_routing_language_hints_extra"),
            "beobachtet",
        ],
        "routing_preferred_action_candidates": {
            "default": ["website_read"],
            "read_like": ["website_read"],
            "list_like": ["website_list"],
        },
        "create_insert_key": "connection_catalog.insert.website.create",
        "create_insert": _catalog_text("connection_catalog.insert.website.create", 'create website {ref} https://example.org title "Watched Source" '),
        "update_insert_key": "connection_catalog.insert.website.update",
        "update_insert": _catalog_text("connection_catalog.insert.website.update", 'update website {ref} https://example.org title "Watched Source" '),
        "fields": {
            "url": {"type": "str", "max_length": 512, "label": _field_text("url", "URL")},
            "group_name": {
                "type": "str",
                "max_length": 64,
                "label": _config_text("rss_group_name", "Group / category"),
                "label_key": "config_conn.rss_group_name",
                "hint_key": "config_conn.website_group_name_hint",
                "hint": _catalog_text("config_conn.website_group_name_hint", "Leave empty if ARIA should sort the source automatically."),
            },
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "webhook": {
        "label": "Webhook",
        "icon": "webhook",
        "template_name": "config_connections_webhook.html",
        "chat_aliases": ["webhook"],
        "chat_primary_field": "url",
        "chat_defaults": {
            "method": "POST",
            "content_type": "application/json",
            "timeout_seconds": 10,
        },
        "menu_title_key": "config_conn.webhook_title",
        "menu_desc_key": "config_conn.webhook_subtitle",
        "example_ref": "n8n-demo",
        "config_page": "/config/connections/webhook",
        "ref_query": "webhook_ref",
        "toolbox_keywords": ["webhook", "hook", "n8n", "automation"],
        "semantic_suffixes": ["webhook", "hook", "endpoint"],
        "requested_ref_suffixes": ["webhook", "hook"],
        "requested_ref_prefixes": ["per", "via", "an", "to"],
        "routing_supported_actions": [
            "send webhook",
            "post webhook",
            "callback",
            "event hook",
            "webhook senden",
            "webhook triggern",
        ],
        "routing_language_hints": ["webhook", "hook", "callback", "endpoint", "send", "poste", "sende"],
        "routing_preferred_action_candidates": {
            "default": ["webhook_send_message"],
            "send_like": ["webhook_send_message"],
        },
        "create_insert_key": "connection_catalog.insert.webhook.create",
        "create_insert": _catalog_text("connection_catalog.insert.webhook.create", 'create webhook {ref} https://example.org/webhook title "Webhook Demo" '),
        "update_insert_key": "connection_catalog.insert.webhook.update",
        "update_insert": _catalog_text("connection_catalog.insert.webhook.update", "update webhook {ref} https://example.org/new-webhook "),
        "fields": {
            "url": {"type": "str", "max_length": 512, "label": _field_text("url", "URL")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "method": {"type": "str", "max_length": 16, "label": _config_text("webhook_method", "Method")},
            "content_type": {"type": "str", "max_length": 120, "label": _config_text("webhook_content_type", "Content-Type")},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": _field_text("guardrail_ref", "Guardrail profile")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "http_api": {
        "label": "HTTP API",
        "icon": "http_api",
        "template_name": "config_connections_http_api.html",
        "chat_aliases": ["http api", "http-api", "api"],
        "chat_primary_field": "base_url",
        "chat_defaults": {
            "health_path": "/",
            "method": "GET",
            "timeout_seconds": 10,
        },
        "menu_title_key": "config_conn.http_api_title",
        "menu_desc_key": "config_conn.http_api_subtitle",
        "example_ref": "inventory-api",
        "config_page": "/config/connections/http-api",
        "ref_query": "http_api_ref",
        "toolbox_keywords": ["http api", "api", "endpoint", "health", "status"],
        "semantic_suffixes": ["api", "endpoint"],
        "requested_ref_suffixes": ["api", "endpoint", "service"],
        "requested_ref_prefixes": ["die", "der", "das", "the", "my", "mein", "meine", "meinen"],
        "routing_supported_actions": [
            "call api",
            "http request",
            "health endpoint",
            "api status",
            "api aufrufen",
            "endpoint pruefen",
        ],
        "routing_language_hints": ["api", "call", "endpoint", "health", "rufe", "hole", "status"],
        "routing_preferred_action_candidates": {
            "default": ["http_api_request"],
            "request_like": ["http_api_request"],
            "status_like": ["http_api_request"],
        },
        "create_insert_key": "connection_catalog.insert.http_api.create",
        "create_insert": _catalog_text("connection_catalog.insert.http_api.create", 'create http api {ref} https://example.org/api /health title "HTTP API" '),
        "update_insert_key": "connection_catalog.insert.http_api.update",
        "update_insert": _catalog_text("connection_catalog.insert.http_api.update", "update http api {ref} https://example.org/api /health "),
        "fields": {
            "base_url": {"type": "str", "max_length": 512, "label": _config_text("http_api_base_url", "Base URL")},
            "auth_token": {"type": "str", "max_length": 512, "label": _config_text("http_api_auth_token", "Auth token")},
            "health_path": {"type": "str", "max_length": 255, "label": _config_text("http_api_health_path", "Health path")},
            "method": {"type": "str", "max_length": 16, "label": _config_text("webhook_method", "Method")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": _field_text("guardrail_ref", "Guardrail profile")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "google_calendar": {
        "label": "Google Calendar",
        "icon": "calendar",
        "template_name": "config_connections_google_calendar.html",
        "chat_aliases": ["google calendar", "google kalender", "calendar", "kalender"],
        "chat_primary_field": "calendar_id",
        "chat_defaults": {
            "calendar_id": "primary",
            "timeout_seconds": 10,
        },
        "menu_title_key": "config_conn.google_calendar_title",
        "menu_desc_key": "config_conn.google_calendar_subtitle",
        "alpha": True,
        "example_ref": "primary-calendar",
        "config_page": "/config/connections/google-calendar",
        "ref_query": "google_calendar_ref",
        "toolbox_keywords": ["google calendar", "kalender", "termine", "events", "calendar"],
        "semantic_suffixes": ["calendar", "kalender", "termine"],
        "routing_supported_actions": [
            "read calendar",
            "today agenda",
            "tomorrow agenda",
            "next appointment",
            "kalender lesen",
            "heutige termine",
            "naechster termin",
        ],
        "routing_language_hints": ["calendar", "kalender", "termine", "meeting", "appointment", "today", "tomorrow", "heute", "morgen"],
        "routing_preferred_action_candidates": {
            "default": ["google_calendar_read_events"],
            "read_like": ["google_calendar_read_events"],
        },
        "routing_follow_up_starter_terms": ["und", "nur", "mit", "ohne", "was ist mit", "wie sieht es"],
        "routing_follow_up_time_terms": [
            "heute",
            "morgen",
            "diese woche",
            "naechste woche",
            "next week",
            "today",
            "tomorrow",
            "this week",
            "day after tomorrow",
            "naechster termin",
            "next appointment",
            "next meeting",
            *_catalog_lexicon_list("google_calendar_follow_up_time_terms_extra"),
        ],
        "routing_follow_up_rewrite_prefix": "Kalender",
        "create_insert_key": "connection_catalog.insert.google_calendar.create",
        "create_insert": _catalog_text("connection_catalog.insert.google_calendar.create", 'create google calendar {ref} primary title "Google Calendar" '),
        "update_insert_key": "connection_catalog.insert.google_calendar.update",
        "update_insert": _catalog_text("connection_catalog.insert.google_calendar.update", 'update google calendar {ref} primary title "Google Calendar" '),
        "fields": {
            "calendar_id": {"type": "str", "max_length": 255, "label": _config_text("calendar_target", "Calendar ID")},
            "client_id": {"type": "str", "max_length": 255, "label": _config_text("google_calendar_client_id", "OAuth client ID")},
            "client_secret": {"type": "str", "max_length": 512, "label": _config_text("google_calendar_client_secret", "OAuth client secret")},
            "refresh_token": {"type": "str", "max_length": 1024, "label": _config_text("google_calendar_refresh_token", "Refresh token")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "searxng": {
        "label": "SearXNG",
        "icon": "searxng",
        "alpha": True,
        "hide_alpha_badge": True,
        "template_name": "config_connections_searxng.html",
        "chat_aliases": ["searxng", "web search", "websearch", "search"],
        "chat_primary_field": "title",
        "chat_defaults": {
            "base_url": "http://searxng:8080",
            "timeout_seconds": 10,
            "language": "de-CH",
            "safe_search": 1,
            "categories": ["general"],
            "engines": [],
            "time_range": "",
            "max_results": 5,
        },
        "menu_title_key": "config_conn.searxng_title",
        "menu_desc_key": "config_conn.searxng_subtitle",
        "example_ref": "web-search",
        "config_page": "/config/connections/searxng",
        "ref_query": "searxng_ref",
        "toolbox_keywords": ["searxng", "websuche", "web search", "suche", "search", "internet"],
        "semantic_suffixes": ["searxng", "web", "search", "internet"],
        "routing_supported_actions": [
            "search web",
            "web search",
            "internet search",
            "websuche",
            "im internet suchen",
            "suchanfrage",
        ],
        "routing_language_hints": ["search", "suche", "web", "internet", "finde", "suchanfrage"],
        "routing_preferred_action_candidates": {
            "default": ["web_search"],
            "search_like": ["web_search"],
            "read_like": ["web_search"],
        },
        "create_insert_key": "connection_catalog.insert.searxng.create",
        "create_insert": _catalog_text("connection_catalog.insert.searxng.create", 'create searxng {ref} title "Web Search" '),
        "update_insert_key": "connection_catalog.insert.searxng.update",
        "update_insert": _catalog_text("connection_catalog.insert.searxng.update", 'update searxng {ref} title "Web Search" '),
        "fields": {
            "base_url": {"type": "str", "max_length": 512, "label": _config_text("http_api_base_url", "Base URL")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "language": {"type": "str", "max_length": 32, "label": _config_text("searxng_language", "Language")},
            "safe_search": {"type": "int", "min": 0, "max": 2, "label": _config_text("searxng_safe_search", "SafeSearch")},
            "categories": {"type": "list", "max_items": 12, "item_max_length": 40, "label": _config_text("searxng_categories", "Categories")},
            "engines": {"type": "list", "max_items": 20, "item_max_length": 40, "label": _config_text("searxng_engines", "Engines")},
            "time_range": {"type": "str", "max_length": 32, "label": _config_text("searxng_time_range", "Time range")},
            "max_results": {"type": "int", "min": 1, "max": 20, "label": _config_text("searxng_max_results", "Max results")},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "mqtt": {
        "label": "MQTT",
        "icon": "mqtt",
        "template_name": "config_connections_mqtt.html",
        "chat_aliases": ["mqtt"],
        "chat_primary_field": "host",
        "chat_defaults": {
            "port": 1883,
            "timeout_seconds": 10,
            "use_tls": False,
        },
        "menu_title_key": "config_conn.mqtt_title",
        "menu_desc_key": "config_conn.mqtt_subtitle",
        "alpha": True,
        "example_ref": "event-bus",
        "config_page": "/config/connections/mqtt",
        "ref_query": "mqtt_ref",
        "toolbox_keywords": ["mqtt", "topic", "broker", "publish", "event bus"],
        "semantic_suffixes": ["mqtt", "topic", "bus", "broker"],
        "requested_ref_suffixes": ["broker"],
        "requested_ref_prefixes": ["auf", "an", "to", "on"],
        "routing_supported_actions": [
            "publish topic",
            "mqtt publish",
            "event bus",
            "topic senden",
            "mqtt nachricht",
            "broker event",
        ],
        "routing_language_hints": ["mqtt", "broker", "topic", "publish", "sende", "schicke"],
        "routing_preferred_action_candidates": {
            "default": ["mqtt_publish_message"],
            "publish_like": ["mqtt_publish_message"],
        },
        "create_insert_key": "connection_catalog.insert.mqtt.create",
        "create_insert": _catalog_text("connection_catalog.insert.mqtt.create", 'create mqtt {ref} mqtt.example.local topic aria/events title "Event Bus" '),
        "update_insert_key": "connection_catalog.insert.mqtt.update",
        "update_insert": _catalog_text("connection_catalog.insert.mqtt.update", "update mqtt {ref} topic aria/events "),
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": _config_text("host", "Host")},
            "port": {"type": "int", "min": 1, "max": 65535, "label": _config_text("port", "Port")},
            "user": {"type": "str", "max_length": 255, "label": _config_text("user", "User")},
            "password": {"type": "str", "max_length": 512, "label": _field_text("password", "Password")},
            "topic": {"type": "str", "max_length": 255, "label": _config_text("mqtt_topic", "Topic")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "use_tls": {"type": "bool", "label": "TLS"},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "email": {
        "label": "SMTP",
        "icon": "smtp",
        "template_name": "config_connections_smtp.html",
        "chat_aliases": ["smtp", "email"],
        "chat_primary_field": "smtp_host",
        "chat_defaults": {
            "port": 587,
            "timeout_seconds": 10,
            "starttls": True,
            "use_ssl": False,
        },
        "menu_title_key": "config_conn.email_title",
        "menu_desc_key": "config_conn.email_subtitle",
        "alpha": True,
        "example_ref": "alerts-mail",
        "config_page": "/config/connections/smtp",
        "ref_query": "email_ref",
        "toolbox_keywords": ["smtp", "email", "mail", "mail senden", "alerts mail"],
        "semantic_suffixes": ["mail", "email", "smtp"],
        "routing_supported_actions": [
            "send email",
            "send mail",
            "alert mail",
            "mail senden",
            "email senden",
            "benachrichtigung per mail",
        ],
        "routing_language_hints": ["email", "mail", "smtp", "send", "sende", "schicke"],
        "routing_preferred_action_candidates": {
            "default": ["email_send_message"],
            "send_like": ["email_send_message"],
        },
        "create_insert_key": "connection_catalog.insert.email.create",
        "create_insert": _catalog_text("connection_catalog.insert.email.create", 'create smtp {ref} smtp.example.local user ops@example.local from ops@example.local to admin@example.local title "Alerts Mail" '),
        "update_insert_key": "connection_catalog.insert.email.update",
        "update_insert": _catalog_text("connection_catalog.insert.email.update", "update smtp {ref} from ops@example.local to admin@example.local "),
        "fields": {
            "smtp_host": {"type": "str", "max_length": 255, "label": _config_text("email_smtp_host", "SMTP host")},
            "port": {"type": "int", "min": 1, "max": 65535, "label": _config_text("port", "Port")},
            "user": {"type": "str", "max_length": 255, "label": _config_text("user", "User")},
            "password": {"type": "str", "max_length": 512, "label": _field_text("password", "Password")},
            "from_email": {"type": "str", "max_length": 255, "label": _config_text("email_from", "From")},
            "to_email": {"type": "str", "max_length": 255, "label": _config_text("email_to", "To")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "starttls": {"type": "bool", "label": "STARTTLS"},
            "use_ssl": {"type": "bool", "label": "SSL"},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "imap": {
        "label": "IMAP",
        "icon": "imap",
        "template_name": "config_connections_imap.html",
        "chat_aliases": ["imap"],
        "chat_primary_field": "host",
        "chat_defaults": {
            "mailbox": "INBOX",
            "port": 993,
            "timeout_seconds": 10,
            "use_ssl": True,
        },
        "menu_title_key": "config_conn.imap_title",
        "menu_desc_key": "config_conn.imap_subtitle",
        "alpha": True,
        "example_ref": "ops-inbox",
        "config_page": "/config/connections/imap",
        "ref_query": "imap_ref",
        "toolbox_keywords": ["imap", "inbox", "postfach", "mailbox", "mail lesen"],
        "semantic_suffixes": ["inbox", "mailbox", "postfach", "imap"],
        "requested_ref_suffixes": ["mailbox", "postfach", "inbox"],
        "requested_ref_prefixes": ["im", "in", "aus", "from"],
        "routing_supported_actions": [
            "read mailbox",
            "search mailbox",
            "inbox lesen",
            "emails lesen",
            "mailbox durchsuchen",
            "postfach durchsuchen",
        ],
        "routing_language_hints": ["imap", "mailbox", "postfach", "inbox", "lesen", "suche"],
        "routing_preferred_action_candidates": {
            "default": ["imap_read_mailbox"],
            "read_like": ["imap_read_mailbox"],
            "search_like": ["imap_search_mailbox"],
        },
        "create_insert_key": "connection_catalog.insert.imap.create",
        "create_insert": _catalog_text("connection_catalog.insert.imap.create", 'create imap {ref} imap.example.local user ops@example.local mailbox INBOX title "Ops Inbox" '),
        "update_insert_key": "connection_catalog.insert.imap.update",
        "update_insert": _catalog_text("connection_catalog.insert.imap.update", "update imap {ref} mailbox INBOX "),
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": _config_text("host", "Host")},
            "port": {"type": "int", "min": 1, "max": 65535, "label": _config_text("port", "Port")},
            "user": {"type": "str", "max_length": 255, "label": _config_text("user", "User")},
            "password": {"type": "str", "max_length": 512, "label": _field_text("password", "Password")},
            "mailbox": {"type": "str", "max_length": 255, "label": _config_text("imap_mailbox", "Mailbox")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
            "use_ssl": {"type": "bool", "label": "SSL"},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
}


def connection_kind_label(kind: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return str(spec.get("label") or str(kind or "").strip() or "Connection")


def connection_kind_labels() -> dict[str, str]:
    return {kind: connection_kind_label(kind) for kind in CONNECTION_CATALOG}


def ordered_connection_kinds() -> list[str]:
    return list(CONNECTION_CATALOG.keys())


def connection_example_ref(kind: str, connection_catalog: dict[str, list[str]] | None = None) -> str:
    clean_kind = normalize_connection_kind(kind)
    refs = (connection_catalog or {}).get(clean_kind, [])
    if refs:
        return str(refs[0]).strip()
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return str(spec.get("example_ref") or "beispiel-connection")


def connection_insert_template(kind: str, action: str, ref: str, *, language: str = "de") -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    key = "create_insert" if str(action).strip().lower() == "create" else "update_insert"
    template_key = str(spec.get(f"{key}_key") or "").strip()
    template = _catalog_text(template_key, str(spec.get(key) or ""), language=language).strip() if template_key else str(spec.get(key) or "").strip()
    if not template:
        verb_key = "create" if key == "create_insert" else "update"
        verb = _catalog_text(f"connection_catalog.insert_verb.{verb_key}", verb_key, language=language)
        template = f"{verb} {clean_kind} {{ref}} "
    return template.format(ref=ref)


def connection_toolbox_keywords(kind: str, refs: list[str]) -> list[str]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    keywords: list[str] = [clean_kind.replace("_", " "), clean_kind]
    keywords.extend(str(item).strip().lower() for item in spec.get("toolbox_keywords", []) if str(item).strip())
    keywords.extend(str(ref).strip().lower().replace("-", " ") for ref in refs if str(ref).strip())
    return [row for row in dict.fromkeys(keywords) if row]


def connection_semantic_suffixes(kind: str) -> list[str]:
    return list(connection_routing_spec(kind).semantic_suffixes)


def connection_requested_ref_suffixes(kind: str) -> list[str]:
    return list(connection_routing_spec(kind).requested_ref_suffixes)


def connection_requested_ref_prefixes(kind: str) -> list[str]:
    return list(connection_routing_spec(kind).requested_ref_prefixes)


def connection_routing_spec(kind: str) -> ConnectionRoutingSpec:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return ConnectionRoutingSpec(
        semantic_suffixes=[str(item).strip() for item in spec.get("semantic_suffixes", []) if str(item).strip()],
        requested_ref_suffixes=[str(item).strip() for item in spec.get("requested_ref_suffixes", []) if str(item).strip()],
        requested_ref_prefixes=[str(item).strip() for item in spec.get("requested_ref_prefixes", []) if str(item).strip()],
        supported_actions=[str(item).strip() for item in spec.get("routing_supported_actions", []) if str(item).strip()],
        language_hints=[str(item).strip() for item in spec.get("routing_language_hints", []) if str(item).strip()],
        preferred_action_candidates={
            str(key).strip(): [str(item).strip() for item in list(value or []) if str(item).strip()]
            for key, value in dict(spec.get("routing_preferred_action_candidates", {}) or {}).items()
            if str(key).strip()
        },
        follow_up_starter_terms=[str(item).strip() for item in spec.get("routing_follow_up_starter_terms", []) if str(item).strip()],
        follow_up_same_target_terms=[str(item).strip() for item in spec.get("routing_follow_up_same_target_terms", []) if str(item).strip()],
        follow_up_time_terms=[str(item).strip() for item in spec.get("routing_follow_up_time_terms", []) if str(item).strip()],
        follow_up_rewrite_prefix=str(spec.get("routing_follow_up_rewrite_prefix", "") or "").strip(),
    )


def connection_edit_page(kind: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return str(spec.get("config_page") or "/config")


def connection_ref_query_param(kind: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return str(spec.get("ref_query") or "ref")


def connection_template_name(kind: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    template_name = str(spec.get("template_name") or "").strip()
    if template_name:
        return template_name
    return f"config_connections_{clean_kind}.html"


def connection_field_specs(kind: str) -> dict[str, dict[str, Any]]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    fields = spec.get("fields", {})
    return dict(fields) if isinstance(fields, dict) else {}


def connection_ui_sections(kind: str) -> dict[str, dict[str, Any]]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    sections = spec.get("ui_sections", {})
    return dict(sections) if isinstance(sections, dict) else {}


def connection_chat_field_specs(kind: str) -> dict[str, dict[str, Any]]:
    fields = connection_field_specs(kind)
    specs: dict[str, dict[str, Any]] = {}
    for field in fields:
        spec = CONNECTION_FIELD_CHAT_CATALOG.get(field)
        if isinstance(spec, dict):
            specs[field] = dict(spec)
    return specs


def connection_summary_fields(kind: str) -> list[str]:
    fields = connection_field_specs(kind)
    summary_fields: list[str] = []
    for field, spec in fields.items():
        chat_spec = CONNECTION_FIELD_CHAT_CATALOG.get(field, {})
        if chat_spec.get("show_in_summary") is False:
            continue
        field_type = str(spec.get("type", "str")).strip().lower()
        if field_type == "bool":
            continue
        summary_fields.append(field)
    return summary_fields


def connection_icon_name(kind: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return str(spec.get("icon") or clean_kind)


def connection_is_alpha(kind: str) -> bool:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return bool(spec.get("alpha", False))


def connection_menu_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, spec in CONNECTION_CATALOG.items():
        rows.append(
            {
                "kind": kind,
                "label": str(spec.get("label") or kind).strip(),
                "icon": str(spec.get("icon") or kind).strip(),
                "title_key": str(spec.get("menu_title_key") or "").strip(),
                "desc_key": str(spec.get("menu_desc_key") or "").strip(),
                "alpha": bool(spec.get("alpha", False)),
                "hide_alpha_badge": bool(spec.get("hide_alpha_badge", False)),
                "url": str(spec.get("config_page") or "").strip(),
            }
        )
    return rows


def connection_menu_meta(kind: str) -> dict[str, Any]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return {
        "kind": clean_kind,
        "label": str(spec.get("label") or clean_kind).strip(),
        "icon": str(spec.get("icon") or clean_kind).strip(),
        "title_key": str(spec.get("menu_title_key") or "").strip(),
        "desc_key": str(spec.get("menu_desc_key") or "").strip(),
        "alpha": bool(spec.get("alpha", False)),
        "url": str(spec.get("config_page") or "").strip(),
    }


def connection_status_meta(kind: str) -> dict[str, str]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    raw = spec.get("status_meta", {})
    if isinstance(raw, dict) and raw:
        return {
            "title_key": str(raw.get("title_key") or "").strip(),
            "title": str(raw.get("title") or "").strip(),
            "hint_key": str(raw.get("hint_key") or "").strip(),
            "hint": str(raw.get("hint") or "").strip(),
            "empty_key": str(raw.get("empty_key") or "").strip(),
            "empty_text": str(raw.get("empty_text") or "").strip(),
        }
    label = str(spec.get("label") or clean_kind).strip()
    key_root = clean_kind
    return {
        "title_key": f"config_conn.{key_root}_live_status",
        "title": f"Live status of all {label} profiles",
        "hint_key": f"config_conn.{key_root}_live_status_hint",
        "hint": f"ARIA checks all {label} profiles when this page opens and right after saving a profile.",
        "empty_key": f"config_conn.{key_root}_no_profiles_hint",
        "empty_text": f"No {label} profiles yet. Save a profile and ARIA will test it automatically.",
    }


def connection_chat_emoji(kind: str) -> str:
    icon_name = connection_icon_name(kind)
    icon_map = {
        "ssh": "🔐",
        "discord": "💬",
        "sftp": "📁",
        "smb": "🗄",
        "webhook": "📡",
        "http_api": "🌐",
        "calendar": "📅",
        "searxng": "🔎",
        "rss": "📰",
        "website": "🔗",
        "smtp": "✉️",
        "email": "✉️",
        "imap": "📬",
        "mqtt": "📟",
    }
    return icon_map.get(icon_name, "🧩")


def connection_overview_meta(kind: str) -> dict[str, dict[str, str]]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    label = str(spec.get("label") or clean_kind).strip()
    raw = spec.get("overview_meta", {})
    raw = raw if isinstance(raw, dict) else {}

    profiles = raw.get("profiles", {}) if isinstance(raw.get("profiles", {}), dict) else {}
    healthy = raw.get("healthy", {}) if isinstance(raw.get("healthy", {}), dict) else {}
    issues = raw.get("issues", {}) if isinstance(raw.get("issues", {}), dict) else {}

    return {
        "profiles": {
            "label_key": str(profiles.get("label_key") or "config_conn.profiles").strip(),
            "label": str(profiles.get("label") or "Profiles").strip(),
            "hint_key": str(profiles.get("hint_key") or f"config_conn.{clean_kind}_profiles_hint").strip(),
            "hint": str(profiles.get("hint") or f"Available {label} profiles in ARIA.").strip(),
        },
        "healthy": {
            "label_key": str(healthy.get("label_key") or "config_conn.healthy").strip(),
            "label": str(healthy.get("label") or "Healthy").strip(),
            "hint_key": str(healthy.get("hint_key") or f"config_conn.{clean_kind}_healthy_hint").strip(),
            "hint": str(healthy.get("hint") or f"Profiles with successful {label} checks.").strip(),
        },
        "issues": {
            "label_key": str(issues.get("label_key") or "config_conn.issues").strip(),
            "label": str(issues.get("label") or "Issues").strip(),
            "hint_key": str(issues.get("hint_key") or f"config_conn.{clean_kind}_issue_hint").strip(),
            "hint": str(issues.get("hint") or f"Profiles that currently fail the {label} check.").strip(),
        },
    }


def connection_chat_aliases(kind: str) -> list[str]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    aliases = spec.get("chat_aliases", [])
    if isinstance(aliases, list):
        rows = [str(item).strip() for item in aliases if str(item).strip()]
        if rows:
            return rows
    return [clean_kind.replace("_", " "), clean_kind]


def connection_chat_primary_field(kind: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return str(spec.get("chat_primary_field") or "").strip()


def connection_chat_defaults(kind: str) -> dict[str, Any]:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    defaults = spec.get("chat_defaults", {})
    return dict(defaults) if isinstance(defaults, dict) else {}


def connection_field_labels(kind: str = "") -> dict[str, str]:
    labels: dict[str, str] = {}
    kinds = [normalize_connection_kind(kind)] if kind else list(CONNECTION_CATALOG.keys())
    for clean_kind in kinds:
        for field, spec in connection_field_specs(clean_kind).items():
            label = str(spec.get("label", "")).strip()
            if label and field not in labels:
                labels[field] = label
    return labels


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on", "ja"}


def sanitize_connection_payload(kind: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    clean_kind = normalize_connection_kind(kind)
    specs = connection_field_specs(clean_kind)
    raw = payload if isinstance(payload, dict) else {}
    clean: dict[str, Any] = {}
    for field, spec in specs.items():
        if field not in raw:
            continue
        value = raw.get(field)
        field_type = str(spec.get("type", "str")).strip().lower()
        if field_type == "int":
            try:
                int_value = int(value)
            except Exception:
                continue
            min_value = int(spec.get("min", int_value))
            max_value = int(spec.get("max", int_value))
            clean[field] = max(min_value, min(int_value, max_value))
            continue
        if field_type == "bool":
            clean[field] = _coerce_bool(value)
            continue
        if field_type == "list":
            if not isinstance(value, list):
                continue
            max_items = int(spec.get("max_items", 12) or 12)
            item_max = int(spec.get("item_max_length", 80) or 80)
            items = [str(item).strip()[:item_max] for item in value if str(item).strip()]
            if items:
                clean[field] = items[:max_items]
            continue
        text = str(value or "").strip()
        if not text:
            continue
        max_length = int(spec.get("max_length", 512) or 512)
        clean[field] = text[:max_length]
    return clean
