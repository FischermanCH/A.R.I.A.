from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aria.modules.platform_primitives.i18n import I18NStore


_CONNECTION_CATALOG_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")
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
    supported_actions: list[str] = field(default_factory=list)
    preferred_action_candidates: dict[str, list[str]] = field(default_factory=dict)

_CONNECTION_SUMMARY_HIDDEN_FIELDS = {
    "service_url", "password", "auth_token", "port", "timeout_seconds",
    "send_test_messages", "allow_skill_messages", "alert_skill_errors",
    "alert_connection_changes", "alert_system_events", "starttls", "use_ssl", "use_tls",
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
        "routing_preferred_action_candidates": {
            "status_like": ["ssh_run_command"],
            "bounded_planner": ["ssh_run_command"],
        },
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
        "routing_supported_actions": [
            "read file",
            "list directory",
            "write file",
            "remote files",
            "datei lesen",
            "dateien anzeigen",
            "server dateien",
        ],
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
        "routing_supported_actions": [
            "read file",
            "list directory",
            "write file",
            "remote files",
            "datei lesen",
            "dateien anzeigen",
            "server dateien",
        ],
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
            "alert_connection_changes": False,
            "alert_system_events": False,
        },
        "menu_title_key": "config_conn.discord_title",
        "menu_desc_key": "config_conn.discord_subtitle",
        "example_ref": "alerts-bot",
        "config_page": "/config/connections/discord",
        "ref_query": "discord_ref",
        "routing_supported_actions": [
            "send message",
            "notify",
            "alert channel",
            "discord nachricht",
            "alarmieren",
            "meldung senden",
        ],
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
        "routing_supported_actions": [
            "read feed",
            "latest news",
            "headlines",
            "feed lesen",
            "neueste meldungen",
            "nachrichten",
        ],
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
        "routing_supported_actions": [
            "read website",
            "open website source",
            "list observed websites",
            "webseite lesen",
            "quelle oeffnen",
            "beobachtete webseiten",
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
        "routing_supported_actions": [
            "send webhook",
            "post webhook",
            "callback",
            "event hook",
            "webhook senden",
            "webhook triggern",
        ],
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
        "routing_supported_actions": [
            "call api",
            "http request",
            "health endpoint",
            "api status",
            "api aufrufen",
            "endpoint pruefen",
        ],
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
        "routing_supported_actions": [
            "read calendar",
            "today agenda",
            "tomorrow agenda",
            "next appointment",
            "kalender lesen",
            "heutige termine",
            "naechster termin",
        ],
        "routing_preferred_action_candidates": {
            "default": ["google_calendar_read_events"],
            "read_like": ["google_calendar_read_events"],
        },
        "create_insert_key": "connection_catalog.insert.google_calendar.create",
        "create_insert": _catalog_text("connection_catalog.insert.google_calendar.create", 'create google calendar {ref} ical_url "https://..." title "Google Calendar" '),
        "update_insert_key": "connection_catalog.insert.google_calendar.update",
        "update_insert": _catalog_text("connection_catalog.insert.google_calendar.update", 'update google calendar {ref} ical_url "https://..." title "Google Calendar" '),
        "fields": {
            "ical_url": {"type": "str", "max_length": 4096, "label": _config_text("google_calendar_ical_url", "Secret iCal URL")},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": _config_text("timeout", "Timeout")},
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
        "routing_supported_actions": [
            "publish topic",
            "mqtt publish",
            "event bus",
            "topic senden",
            "mqtt nachricht",
            "broker event",
        ],
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
        "routing_supported_actions": [
            "send email",
            "send mail",
            "alert mail",
            "mail senden",
            "email senden",
            "benachrichtigung per mail",
        ],
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
        "routing_supported_actions": [
            "read mailbox",
            "search mailbox",
            "inbox lesen",
            "emails lesen",
            "mailbox durchsuchen",
            "postfach durchsuchen",
        ],
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
    "inbound_webhook": {
        "label": "Inbound Webhook",
        "icon": "webhook",
        "alpha": True,
        "routing_visible": False,
        "menu_visible": False,
        "chat_aliases": [],
        "chat_primary_field": "title",
        "chat_defaults": {
            "enabled": True,
            "provider_profile": "generic",
            "allowed_content_types": [
                "application/json",
                "application/x-www-form-urlencoded",
                "text/plain",
            ],
            "max_body_bytes": 65536,
            "routing_policy": "log_only",
            "store_raw_body": False,
            "max_events": 1000,
        },
        "example_ref": "senscap-watcher",
        "config_page": "",
        "fields": {
            "enabled": {"type": "bool", "label": "Enabled"},
            "provider_profile": {"type": "str", "max_length": 64, "label": "Provider profile"},
            "allowed_content_types": {
                "type": "list",
                "max_items": 8,
                "item_max_length": 120,
                "label": "Allowed content types",
            },
            "max_body_bytes": {
                "type": "int",
                "min": 1,
                "max": 10485760,
                "label": "Maximum body size",
            },
            "routing_policy": {"type": "str", "max_length": 32, "label": "Routing policy"},
            "store_raw_body": {"type": "bool", "label": "Store redacted body"},
            "max_events": {
                "type": "int",
                "min": 1,
                "max": 100000,
                "label": "Retained events",
            },
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
    return [
        kind
        for kind, spec in CONNECTION_CATALOG.items()
        if bool(spec.get("routing_visible", True))
    ]


def connection_manifest_kinds() -> list[str]:
    return list(CONNECTION_CATALOG.keys())


def routing_workbench_kind_options(*, include_auto: bool = True) -> list[str]:
    rows = ordered_connection_kinds()
    return ["auto", *rows] if include_auto else rows


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


def connection_routing_spec(kind: str) -> ConnectionRoutingSpec:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return ConnectionRoutingSpec(
        supported_actions=[str(item).strip() for item in spec.get("routing_supported_actions", []) if str(item).strip()],
        preferred_action_candidates={
            str(key).strip(): [str(item).strip() for item in list(value or []) if str(item).strip()]
            for key, value in dict(spec.get("routing_preferred_action_candidates", {}) or {}).items()
            if str(key).strip()
        },
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


def connection_summary_fields(kind: str) -> list[str]:
    fields = connection_field_specs(kind)
    summary_fields: list[str] = []
    for field_name, spec in fields.items():
        if field_name in _CONNECTION_SUMMARY_HIDDEN_FIELDS:
            continue
        field_type = str(spec.get("type", "str")).strip().lower()
        if field_type == "bool":
            continue
        summary_fields.append(field_name)
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
        if not bool(spec.get("menu_visible", True)):
            continue
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
        for field_name, spec in connection_field_specs(clean_kind).items():
            label = str(spec.get("label", "")).strip()
            if label and field_name not in labels:
                labels[field_name] = label
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
    for field_name, spec in specs.items():
        if field_name not in raw:
            continue
        value = raw.get(field_name)
        field_type = str(spec.get("type", "str")).strip().lower()
        if field_type == "int":
            try:
                int_value = int(value)
            except Exception:
                continue
            min_value = int(spec.get("min", int_value))
            max_value = int(spec.get("max", int_value))
            clean[field_name] = max(min_value, min(int_value, max_value))
            continue
        if field_type == "bool":
            clean[field_name] = _coerce_bool(value)
            continue
        if field_type == "list":
            if not isinstance(value, list):
                continue
            max_items = int(spec.get("max_items", 12) or 12)
            item_max = int(spec.get("item_max_length", 80) or 80)
            items = [str(item).strip()[:item_max] for item in value if str(item).strip()]
            if items:
                clean[field_name] = items[:max_items]
            continue
        text = str(value or "").strip()
        if not text:
            continue
        max_length = int(spec.get("max_length", 512) or 512)
        clean[field_name] = text[:max_length]
    return clean
