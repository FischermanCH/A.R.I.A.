from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aria.core.behavior_families import build_file_operation_templates
from aria.core.text_utils import is_english

_ACTION_TEMPLATE_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "action_planner_templates.json"


def _load_action_template_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_ACTION_TEMPLATE_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load action planner template lexicon: {_ACTION_TEMPLATE_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_ACTION_TEMPLATE_LEXICON = _load_action_template_lexicon()


def _template_lexicon_value(candidate_id: str, key: str, default: str = "") -> str:
    raw = _ACTION_TEMPLATE_LEXICON.get(candidate_id, {})
    if not isinstance(raw, dict):
        return default
    value = str(raw.get(key) or "").strip()
    return value or default


def _template_lexicon_list(candidate_id: str, key: str) -> list[str]:
    raw = _ACTION_TEMPLATE_LEXICON.get(candidate_id, {})
    values = raw.get(key, []) if isinstance(raw, dict) else []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


ACTION_TEMPLATE_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "ssh": [
        {
            "candidate_id": "ssh_run_command",
            "plan_class": "command_single",
            "behavior_profile": "ssh_run_command",
            "title": "SSH Agentic Command",
            "summary": "Uses the routed SSH target plus request context to derive a suitable command for the host.",
            "intent": "run_command",
            "capability": "ssh_command",
            "preview": "SSH command derived from the routed target and request",
            "base_preview_de": "SSH-Befehl aus Zielkontext und Benutzeranfrage",
            "base_preview_en": "SSH command from routed target context and request",
            "required_inputs": [],
            "router_keywords": [
                "run command",
                "execute",
                "fuehre aus",
                *_template_lexicon_list("ssh_run_command", "router_keywords_extra"),
                "run",
                "status",
                "health",
                "check server",
                "server status",
                "online",
                "uptime",
                "ls",
                "df",
                "systemctl",
            ],
        },
    ],
    "sftp": build_file_operation_templates("sftp"),
    "smb": build_file_operation_templates("smb"),
    "rss": [
        {
            "candidate_id": "rss_read_feed",
            "plan_class": "feed_digest",
            "behavior_profile": "rss_read_feed",
            "title": "RSS Read Feed",
            "summary": "Reads recent feed entries and headlines from the target feed.",
            "intent": "read_feed",
            "capability": "rss_read",
            "preview": "Read recent feed entries",
            "base_preview_de": "Aktuelle Feed-Eintraege lesen",
            "base_preview_en": "Read recent feed entries",
            "required_inputs": [],
            "router_keywords": ["feed", "rss", "headlines", "latest news", "neueste meldungen", "nachrichten"],
        }
    ],
    "website": [
        {
            "candidate_id": "website_read",
            "plan_class": "website_reference",
            "behavior_profile": "website_read",
            "title": "Website Read",
            "summary": "Opens one configured watched website.",
            "intent": "read_website",
            "capability": "website_read",
            "preview": "Open watched website from configured sources",
            "base_preview_de": _template_lexicon_value("website_read", "base_preview_de", "Open watched website"),
            "base_preview_en": "Open watched website",
            "required_inputs": [],
            "router_keywords": ["website", "webseite", "quelle", "link", "open website", "oeffne webseite", "beobachtete webseite"],
        },
        {
            "candidate_id": "website_list",
            "plan_class": "website_listing",
            "behavior_profile": "website_list",
            "title": "Website List",
            "summary": "Lists configured watched websites, optionally filtered by group.",
            "intent": "list_websites",
            "capability": "website_list",
            "preview": "List watched websites",
            "base_preview_de": "Beobachtete Webseiten auflisten",
            "base_preview_en": "List watched websites",
            "required_inputs": [],
            "router_keywords": ["websites", "webseiten", "watched websites", "beobachtete webseiten", "list websites", "zeige webseiten"],
        },
    ],
    "google_calendar": [
        {
            "candidate_id": "google_calendar_read_events",
            "plan_class": "calendar_window",
            "behavior_profile": "calendar_read_events",
            "title": "Google Calendar Read Events",
            "summary": "Reads upcoming appointments and events from the selected Google Calendar.",
            "intent": "read_calendar",
            "capability": "calendar_read",
            "preview": "Read upcoming events from Google Calendar",
            "base_preview_de": "Kalendertermine lesen",
            "base_preview_en": "Read calendar events",
            "required_inputs": [],
            "router_keywords": [
                "calendar",
                "kalender",
                "termine",
                "meeting",
                "appointment",
                "heute",
                "morgen",
                "next appointment",
            ],
        }
    ],
    "discord": [
        {
            "candidate_id": "discord_send_message",
            "plan_class": "message_send_basic",
            "behavior_profile": "discord_send_message",
            "title": "Discord Send Message",
            "summary": "Sends a text message to the selected Discord target.",
            "intent": "send_message",
            "capability": "discord_send",
            "preview": "Send a message to Discord",
            "base_preview_de": "Nachricht an Discord senden",
            "base_preview_en": "Send a message to Discord",
            "required_inputs": ["message"],
            "router_keywords": ["send message", "discord", "channel", "alert", "schick", "sende", "nachricht"],
        }
    ],
    "webhook": [
        {
            "candidate_id": "webhook_send_message",
            "plan_class": "message_send_basic",
            "behavior_profile": "webhook_send_message",
            "title": "Webhook Send Message",
            "summary": "Sends a message or payload to the selected webhook target.",
            "intent": "send_message",
            "capability": "webhook_send",
            "preview": "Send a payload to the webhook target",
            "base_preview_de": "Payload an Webhook senden",
            "base_preview_en": "Send a payload to the webhook",
            "required_inputs": ["message"],
            "router_keywords": ["webhook", "hook", "callback", "send", "sende", "poste", "payload"],
        }
    ],
    "email": [
        {
            "candidate_id": "email_send_message",
            "plan_class": "message_send_basic",
            "behavior_profile": "email_send_message",
            "title": "Email Send Message",
            "summary": "Sends an email through the selected SMTP profile.",
            "intent": "send_message",
            "capability": "email_send",
            "preview": "Send an email via the configured SMTP target",
            "base_preview_de": _template_lexicon_value("email_send_message", "base_preview_de", "Send an email via SMTP"),
            "base_preview_en": "Send an email via SMTP",
            "required_inputs": ["message"],
            "router_keywords": ["email", "mail", "smtp", "send", "sende", "schick", "benachrichtigung"],
        }
    ],
    "imap": [
        {
            "candidate_id": "imap_read_mailbox",
            "plan_class": "mailbox_read_basic",
            "behavior_profile": "imap_read_mailbox",
            "title": "IMAP Read Mailbox",
            "summary": "Reads the latest emails from the selected mailbox.",
            "intent": "read_mail",
            "capability": "mail_read",
            "preview": "Read the latest emails from the mailbox",
            "base_preview_de": "Neueste E-Mails im Postfach lesen",
            "base_preview_en": "Read the latest emails from the mailbox",
            "required_inputs": [],
            "router_keywords": ["imap", "mailbox", "postfach", "inbox", "emails lesen", "mail lesen"],
        },
        {
            "candidate_id": "imap_search_mailbox",
            "plan_class": "mailbox_search_basic",
            "behavior_profile": "imap_search_mailbox",
            "title": "IMAP Search Mailbox",
            "summary": "Searches the selected mailbox for a query.",
            "intent": "search_mail",
            "capability": "mail_search",
            "preview": "Search the mailbox with the user query",
            "base_preview_de": "Postfach nach einer Anfrage durchsuchen",
            "base_preview_en": "Search the mailbox with a query",
            "required_inputs": ["search_query"],
            "router_keywords": ["imap", "mailbox", "postfach", "search mail", "suche mail", "finde emails"],
        },
    ],
    "mqtt": [
        {
            "candidate_id": "mqtt_publish_message",
            "plan_class": "message_publish_basic",
            "behavior_profile": "mqtt_publish_message",
            "title": "MQTT Publish Message",
            "summary": "Publishes a payload to the selected MQTT broker/topic.",
            "intent": "publish_message",
            "capability": "mqtt_publish",
            "preview": "Publish a message to the MQTT topic",
            "base_preview_de": "Nachricht an MQTT-Topic senden",
            "base_preview_en": "Publish a message to the MQTT topic",
            "required_inputs": ["message"],
            "router_keywords": ["mqtt", "topic", "broker", "publish", "sende event", "nachricht publizieren"],
        }
    ],
    "http_api": [
        {
            "candidate_id": "http_api_request",
            "plan_class": "api_request_basic",
            "behavior_profile": "http_api_request",
            "title": "HTTP API Request",
            "summary": "Calls the target API endpoint and returns the response.",
            "intent": "api_request",
            "capability": "http_api_request",
            "preview": "HTTP request to configured API target",
            "base_preview_de": "HTTP-Anfrage an das konfigurierte API-Ziel",
            "base_preview_en": "HTTP request to configured API target",
            "required_inputs": [],
            "router_keywords": ["api", "call endpoint", "request", "fetch api"],
        }
    ],
}


def action_template_definition(candidate_id: str) -> dict[str, Any]:
    clean_candidate_id = str(candidate_id or "").strip().lower()
    if not clean_candidate_id:
        return {}
    for rows in ACTION_TEMPLATE_LIBRARY.values():
        for row in rows:
            if str(row.get("candidate_id", "") or "").strip().lower() == clean_candidate_id:
                return dict(row)
    return {}


def action_template_behavior_profile(candidate_id: str) -> str:
    row = action_template_definition(candidate_id)
    return str(row.get("behavior_profile", "") or "").strip().lower()


def action_template_plan_class(candidate_id: str) -> str:
    row = action_template_definition(candidate_id)
    return str(row.get("plan_class", "") or "").strip().lower()


def action_template_required_inputs(candidate_id: str) -> list[str]:
    row = action_template_definition(candidate_id)
    return [str(item or "").strip() for item in list(row.get("required_inputs", []) or []) if str(item or "").strip()]


def action_template_base_preview(candidate_id: str, language: str = "", fallback: str = "") -> str:
    row = action_template_definition(candidate_id)
    if not is_english(language):
        de_value = str(row.get("base_preview_de", "") or "").strip()
        if de_value:
            return de_value
    en_value = str(row.get("base_preview_en", "") or "").strip()
    if en_value:
        return en_value
    return str(fallback or "").strip()
