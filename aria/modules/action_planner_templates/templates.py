from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.modules.action_planner_templates.behavior_family_file_operation import build_file_operation_templates
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.platform_primitives.text_utils import is_english


_ACTION_TEMPLATE_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")

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
            "base_preview_key": "ssh_run_command",
            "required_inputs": ["command"],
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
            "base_preview_key": "rss_read_feed",
            "required_inputs": [],
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
            "base_preview_key": "website_read",
            "required_inputs": [],
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
            "base_preview_key": "website_list",
            "required_inputs": [],
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
            "base_preview_key": "google_calendar_read_events",
            "required_inputs": [],
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
            "base_preview_key": "discord_send_message",
            "required_inputs": ["message"],
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
            "base_preview_key": "webhook_send_message",
            "required_inputs": ["message"],
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
            "base_preview_key": "email_send_message",
            "required_inputs": ["message"],
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
            "base_preview_key": "imap_read_mailbox",
            "required_inputs": [],
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
            "base_preview_key": "imap_search_mailbox",
            "required_inputs": ["search_query"],
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
            "base_preview_key": "mqtt_publish_message",
            "required_inputs": ["message"],
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
            "base_preview_key": "http_api_request",
            "required_inputs": [],
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
    key = str(row.get("base_preview_key", "") or "").strip()
    if key:
        lang = "en" if is_english(language) else "de"
        value = _ACTION_TEMPLATE_I18N.t(lang, f"action_templates.{key}", "")
        if value:
            return value
    return str(fallback or "").strip()
