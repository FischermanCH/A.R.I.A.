from __future__ import annotations

from typing import Any


COMMON_METADATA_FIELD_SPECS: dict[str, dict[str, Any]] = {
    "title": {"type": "str", "max_length": 160, "label": "Titel"},
    "description": {"type": "str", "max_length": 512, "label": "Beschreibung"},
    "aliases": {"type": "list", "max_items": 12, "item_max_length": 80, "label": "Aliase"},
    "tags": {"type": "list", "max_items": 12, "item_max_length": 40, "label": "Tags"},
}

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
        "create_insert": 'erstelle ssh {ref} server.example.local user admin key /app/data/ssh_keys/main-ssh_ed25519 titel "SSH Server" ',
        "update_insert": 'aktualisiere ssh {ref} server.example.local user admin key /app/data/ssh_keys/main-ssh_ed25519 titel "SSH Server" ',
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": "Host"},
            "port": {"type": "int", "min": 1, "max": 65535, "label": "Port"},
            "user": {"type": "str", "max_length": 255, "label": "User"},
            "service_url": {"type": "str", "max_length": 512, "label": "Service-URL"},
            "key_path": {"type": "str", "max_length": 512, "label": "Key-Pfad"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "strict_host_key_checking": {"type": "str", "max_length": 32, "label": "Host-Key-Prüfung"},
            "allow_commands": {"type": "list", "max_items": 20, "item_max_length": 200, "label": "Allow-Commands"},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": "Guardrail-Profil"},
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
        "create_insert": 'erstelle sftp {ref} files.example.local user backup pfad /data titel "SFTP Server" ',
        "update_insert": 'aktualisiere sftp {ref} files.example.local user backup pfad /data titel "SFTP Server" ',
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": "Host"},
            "port": {"type": "int", "min": 1, "max": 65535, "label": "Port"},
            "user": {"type": "str", "max_length": 255, "label": "User"},
            "service_url": {"type": "str", "max_length": 512, "label": "Service-URL"},
            "password": {"type": "str", "max_length": 512, "label": "Passwort"},
            "key_path": {"type": "str", "max_length": 512, "label": "Key-Pfad"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "root_path": {"type": "str", "max_length": 512, "label": "Pfad"},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": "Guardrail-Profil"},
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
        "create_insert": 'erstelle smb {ref} nas.example.local share docs user aria pfad / titel "NAS Share" ',
        "update_insert": 'aktualisiere smb {ref} nas.example.local share docs pfad / titel "NAS Share" ',
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": "Host"},
            "port": {"type": "int", "min": 1, "max": 65535, "label": "Port"},
            "share": {"type": "str", "max_length": 255, "label": "Share"},
            "user": {"type": "str", "max_length": 255, "label": "User"},
            "password": {"type": "str", "max_length": 512, "label": "Passwort"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "root_path": {"type": "str", "max_length": 512, "label": "Pfad"},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": "Guardrail-Profil"},
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
        "create_insert": 'erstelle discord {ref} https://discord.example/webhook titel "Alerts Bot" ',
        "update_insert": 'aktualisiere discord {ref} titel "Alerts Bot" ',
        "ui_sections": {
            "behaviour": {
                "title_key": "config_conn.discord_alerting_title",
                "title": "Discord Alerting & Verhalten",
                "hint_key": "config_conn.discord_alerting_hint",
                "hint": "Hier steuerst du, ob ARIA sichtbare Testposts senden darf und ob Skills dieses Profil aktiv als Discord-Ziel verwenden dürfen.",
            },
            "events": {
                "title_key": "config_conn.discord_event_routing_title",
                "title": "ARIA Event-Routing nach Discord",
                "hint_key": "config_conn.discord_event_routing_hint",
                "hint": "Diese Kategorien machen Discord zu einer kleinen Alarm- und Log-Zentrale für ARIA. Aktiviert werden nur wichtige Ereignisse, keine kompletten Rohlogs.",
            },
        },
        "fields": {
            "webhook_url": {"type": "str", "max_length": 512, "label": "Webhook-URL"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "send_test_messages": {
                "type": "bool",
                "label": "Testnachrichten",
                "section": "behaviour",
                "title_key": "config_conn.discord_send_test_messages",
                "title": "Nerdige Testnachricht nach Discord senden",
                "hint_key": "config_conn.discord_send_test_messages_hint",
                "hint": "Wenn aktiv, sendet ARIA bei einem Verbindungstest eine sichtbare A.R.I.A-Handshake-Nachricht. Wenn aus, prüft ARIA den Webhook still ohne Testpost.",
                "toggle_key": "config_conn.discord_send_test_messages_toggle",
                "toggle": "Testposts aktivieren",
            },
            "allow_skill_messages": {
                "type": "bool",
                "label": "Skill-Nachrichten",
                "section": "behaviour",
                "title_key": "config_conn.discord_allow_skill_messages",
                "title": "Skill-Nachrichten über dieses Profil erlauben",
                "hint_key": "config_conn.discord_allow_skill_messages_hint",
                "hint": "Wenn deaktiviert, können Skills dieses Discord-Profil nicht als Ziel für `discord_send` verwenden.",
                "toggle_key": "config_conn.discord_allow_skill_messages_toggle",
                "toggle": "Skill-Ziel erlauben",
            },
            "alert_skill_errors": {
                "type": "bool",
                "label": "Skill-Fehler",
                "section": "events",
                "title_key": "config_conn.discord_alert_skill_errors",
                "title": "Skill-Fehler melden",
                "hint_key": "config_conn.discord_alert_skill_errors_hint",
                "hint": "Sendet eine Meldung nach Discord, wenn ein Skill im Lauf fehlschlägt.",
                "toggle_key": "config_conn.discord_alert_skill_errors_toggle",
                "toggle": "Skill-Fehler an Discord senden",
            },
            "alert_safe_fix": {
                "type": "bool",
                "label": "Safe-Fix",
                "section": "events",
                "title_key": "config_conn.discord_alert_safe_fix",
                "title": "Safe-Fix Meldungen",
                "hint_key": "config_conn.discord_alert_safe_fix_hint",
                "hint": "Sendet Meldungen, wenn ein Safe-Fix bereitsteht oder ausgeführt wurde.",
                "toggle_key": "config_conn.discord_alert_safe_fix_toggle",
                "toggle": "Safe-Fix Events senden",
            },
            "alert_connection_changes": {
                "type": "bool",
                "label": "Statuswechsel",
                "section": "events",
                "title_key": "config_conn.discord_alert_connection_changes",
                "title": "Verbindungsstatus-Änderungen",
                "hint_key": "config_conn.discord_alert_connection_changes_hint",
                "hint": "Sendet eine Meldung, wenn eine konfigurierte Verbindung von grün auf rot oder zurück wechselt.",
                "toggle_key": "config_conn.discord_alert_connection_changes_toggle",
                "toggle": "Statuswechsel senden",
            },
            "alert_system_events": {
                "type": "bool",
                "label": "System-Events",
                "section": "events",
                "title_key": "config_conn.discord_alert_system_events",
                "title": "System-Events",
                "hint_key": "config_conn.discord_alert_system_events_hint",
                "hint": "Sendet kompakte Meldungen bei ARIA-Start und ähnlichen Systemereignissen.",
                "toggle_key": "config_conn.discord_alert_system_events_toggle",
                "toggle": "System-Events senden",
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
        "create_insert": 'erstelle rss {ref} https://example.org/feed.xml titel "Beispiel Feed" ',
        "update_insert": 'aktualisiere rss {ref} titel "Beispiel Feed" ',
        "fields": {
            "feed_url": {"type": "str", "max_length": 512, "label": "Feed-URL"},
            "group_name": {
                "type": "str",
                "max_length": 64,
                "label": "Gruppe / Kategorie",
                "label_key": "config_conn.rss_group_name",
                "hint_key": "config_conn.rss_group_name_hint",
                "hint": "Manuell gesetzte Gruppen bleiben beim LLM-Refresh unverändert. Leer lassen, wenn ARIA den Feed frei einsortieren darf.",
            },
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "poll_interval_minutes": {"type": "int", "min": 1, "max": 10080, "label": "Ping-Intervall (Minuten)"},
            **COMMON_METADATA_FIELD_SPECS,
        },
    },
    "website": {
        "label": "Beobachtete Webseiten",
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
        "create_insert": 'erstelle website {ref} https://example.org titel "Beobachtete Quelle" ',
        "update_insert": 'aktualisiere website {ref} https://example.org titel "Beobachtete Quelle" ',
        "fields": {
            "url": {"type": "str", "max_length": 512, "label": "URL"},
            "group_name": {
                "type": "str",
                "max_length": 64,
                "label": "Gruppe / Kategorie",
                "label_key": "config_conn.rss_group_name",
                "hint_key": "config_conn.website_group_name_hint",
                "hint": "Leer lassen, wenn ARIA die Quelle automatisch einsortieren soll.",
            },
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
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
        "create_insert": 'erstelle webhook {ref} https://example.org/webhook titel "Webhook Demo" ',
        "update_insert": "update webhook {ref} https://example.org/new-webhook ",
        "fields": {
            "url": {"type": "str", "max_length": 512, "label": "URL"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "method": {"type": "str", "max_length": 16, "label": "Methode"},
            "content_type": {"type": "str", "max_length": 120, "label": "Content-Type"},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": "Guardrail-Profil"},
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
        "create_insert": 'erstelle http api {ref} https://example.org/api /health titel "HTTP API" ',
        "update_insert": "ändere http api {ref} https://example.org/api /health ",
        "fields": {
            "base_url": {"type": "str", "max_length": 512, "label": "Base-URL"},
            "auth_token": {"type": "str", "max_length": 512, "label": "Auth-Token"},
            "health_path": {"type": "str", "max_length": 255, "label": "Health-Pfad"},
            "method": {"type": "str", "max_length": 16, "label": "Methode"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "guardrail_ref": {"type": "str", "max_length": 64, "label": "Guardrail-Profil"},
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
        "create_insert": 'erstelle google calendar {ref} primary titel "Google Kalender" ',
        "update_insert": 'aktualisiere google calendar {ref} primary titel "Google Kalender" ',
        "fields": {
            "calendar_id": {"type": "str", "max_length": 255, "label": "Calendar-ID"},
            "client_id": {"type": "str", "max_length": 255, "label": "OAuth Client-ID"},
            "client_secret": {"type": "str", "max_length": 512, "label": "OAuth Client Secret"},
            "refresh_token": {"type": "str", "max_length": 1024, "label": "Refresh-Token"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
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
        "create_insert": 'erstelle searxng {ref} titel "Web Search" ',
        "update_insert": 'aktualisiere searxng {ref} titel "Web Search" ',
        "fields": {
            "base_url": {"type": "str", "max_length": 512, "label": "Base-URL"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
            "language": {"type": "str", "max_length": 32, "label": "Sprache"},
            "safe_search": {"type": "int", "min": 0, "max": 2, "label": "SafeSearch"},
            "categories": {"type": "list", "max_items": 12, "item_max_length": 40, "label": "Kategorien"},
            "engines": {"type": "list", "max_items": 20, "item_max_length": 40, "label": "Suchmaschinen"},
            "time_range": {"type": "str", "max_length": 32, "label": "Zeitraum"},
            "max_results": {"type": "int", "min": 1, "max": 20, "label": "Max. Treffer"},
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
        "create_insert": 'erstelle mqtt {ref} mqtt.example.local topic aria/events titel "Event Bus" ',
        "update_insert": "aktualisiere mqtt {ref} topic aria/events ",
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": "Host"},
            "port": {"type": "int", "min": 1, "max": 65535, "label": "Port"},
            "user": {"type": "str", "max_length": 255, "label": "User"},
            "password": {"type": "str", "max_length": 512, "label": "Passwort"},
            "topic": {"type": "str", "max_length": 255, "label": "Topic"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
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
        "create_insert": 'erstelle smtp {ref} smtp.example.local user ops@example.local from ops@example.local to admin@example.local titel "Alerts Mail" ',
        "update_insert": "aktualisiere smtp {ref} from ops@example.local to admin@example.local ",
        "fields": {
            "smtp_host": {"type": "str", "max_length": 255, "label": "SMTP-Host"},
            "port": {"type": "int", "min": 1, "max": 65535, "label": "Port"},
            "user": {"type": "str", "max_length": 255, "label": "User"},
            "password": {"type": "str", "max_length": 512, "label": "Passwort"},
            "from_email": {"type": "str", "max_length": 255, "label": "Von"},
            "to_email": {"type": "str", "max_length": 255, "label": "An"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
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
        "create_insert": 'erstelle imap {ref} imap.example.local user ops@example.local mailbox INBOX titel "Ops Inbox" ',
        "update_insert": "aktualisiere imap {ref} mailbox INBOX ",
        "fields": {
            "host": {"type": "str", "max_length": 255, "label": "Host"},
            "port": {"type": "int", "min": 1, "max": 65535, "label": "Port"},
            "user": {"type": "str", "max_length": 255, "label": "User"},
            "password": {"type": "str", "max_length": 512, "label": "Passwort"},
            "mailbox": {"type": "str", "max_length": 255, "label": "Mailbox"},
            "timeout_seconds": {"type": "int", "min": 1, "max": 300, "label": "Timeout"},
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


def connection_insert_template(kind: str, action: str, ref: str) -> str:
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    key = "create_insert" if str(action).strip().lower() == "create" else "update_insert"
    template = str(spec.get(key) or "").strip()
    if not template:
        verb = "erstelle" if key == "create_insert" else "aktualisiere"
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
    clean_kind = normalize_connection_kind(kind)
    spec = CONNECTION_CATALOG.get(clean_kind, {})
    return [str(item).strip() for item in spec.get("semantic_suffixes", []) if str(item).strip()]


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
