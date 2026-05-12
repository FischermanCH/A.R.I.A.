from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from aria.core.action_candidate_taxonomy import is_recipe_candidate_kind
from aria.core.action_candidate_taxonomy import candidate_kind_label as taxonomy_candidate_kind_label
from aria.core.action_planner_followups import suggested_follow_up_prompt as core_suggested_follow_up_prompt
from aria.core.action_planner_templates import action_template_behavior_profile
from aria.core.action_planner_templates import action_template_required_inputs
from aria.core.behavior_families import behavior_family_id_for
from aria.core.behavior_families import build_file_operation_preview
from aria.core.behavior_families import build_mailbox_access_preview
from aria.core.behavior_families import build_request_target_preview
from aria.core.behavior_families import build_source_lookup_preview
from aria.core.behavior_families import derive_file_operation_inputs
from aria.core.behavior_families import derive_mailbox_access_inputs
from aria.core.behavior_families import derive_source_lookup_inputs
from aria.core.behavior_families import file_operation_mode
from aria.core.behavior_families import mailbox_access_mode
from aria.core.behavior_families import request_target_mode
from aria.core.behavior_families import source_lookup_mode
from aria.core.capability_router import CapabilityRouter
from aria.core.i18n import I18NStore
from aria.core.recipe_candidate_view import recipe_candidate_metadata
from aria.core.text_utils import is_german


_CANDIDATE_DETAILS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _candidate_detail_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CANDIDATE_DETAILS_I18N.t(language or "de", f"action_planner_candidate_details.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _candidate_detail_terms(language: str | None, key: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    localized = _candidate_detail_text(language, key, "")
    terms = [item.strip().lower() for item in localized.split(",") if item.strip()]
    return tuple(dict.fromkeys([*terms, *defaults]))


def _localized_text(language: str, *, de: str, en: str) -> str:
    return de if is_german(language) else en


def _default_ssh_template_command(candidate: Any, query: str = "") -> str:
    intent = str(getattr(candidate, "intent", "") or "").strip().lower()
    candidate_id = str(getattr(candidate, "candidate_id", "") or "").strip().lower()
    lower_query = str(query or "").strip().lower()
    if intent == "health_check" or candidate_id == "ssh_run_command":
        if any(token in lower_query for token in ("festplatte", "disk", "filesystem", "dateisystem", "speicherplatz", "platz frei", "df ")):
            return "df -h"
        if any(token in lower_query for token in ("ram", "memory", "speicher", "arbeitsspeicher", "free -h")):
            return "free -h"
        if any(
            token in lower_query
            for token in _candidate_detail_terms("", "default_ssh_health_terms", ("health", "status", "uptime", "server", "host", "check"))
        ):
            return "uptime"
        if not lower_query:
            return "uptime"
    return ""


def candidate_payload(candidate: Any) -> dict[str, Any]:
    return {
        "found": True,
        "candidate_kind": candidate.candidate_kind,
        "candidate_kind_label": "",
        "candidate_id": candidate.candidate_id,
        "plan_class": str(candidate.plan_class or "").strip(),
        "behavior_profile": action_template_behavior_profile(candidate.candidate_id),
        "title": candidate.title,
        "intent": candidate.intent,
        "intent_label": "",
        "connection_kind": candidate.connection_kind,
        "capability": candidate.capability,
        "capability_label": "",
        **recipe_candidate_metadata(candidate),
        "preview": candidate.preview,
        "inputs": dict(candidate.inputs or {}),
        "input_items": [],
        "score": float(candidate.score or 0.0),
        "execution_state": "",
        "execution_state_label": "",
        "summary_line": "",
        "missing_input": "",
        "missing_input_label": "",
        "clarifying_question": "",
        "example_prompt": "",
        "reason": "",
    }


def derive_candidate_preview(
    candidate: Any,
    query: str,
    *,
    language: str = "",
    extract_command_text: Callable[[str], str],
    extract_remote_path: Callable[[str], str],
    extract_mail_search_text: Callable[[str], str],
    extract_message_text: Callable[[str], str],
    extract_mqtt_topic_text: Callable[[str], str],
    extract_website_group_text: Callable[[str], str],
    extract_calendar_range_text: Callable[[str], str],
    extract_calendar_search_text: Callable[[str], str],
    base_candidate_preview: Callable[[Any, str], str],
) -> str:
    if is_recipe_candidate_kind(candidate.candidate_kind):
        return candidate.preview
    profile = action_template_behavior_profile(candidate.candidate_id)
    family_id = behavior_family_id_for(behavior_profile=profile, plan_class=candidate.plan_class)
    if profile == "ssh_run_command":
        command = extract_command_text(query)
        if not command:
            command = _default_ssh_template_command(candidate, query)
        prefix = _localized_text(language, de="SSH-Befehl", en="SSH command")
        return f"{prefix}: {command}" if command else base_candidate_preview(candidate, language)
    if family_id == "file_operation":
        mode = file_operation_mode(behavior_profile=profile, plan_class=candidate.plan_class)
        path = extract_remote_path(query)
        return build_file_operation_preview(
            mode=mode,
            connection_kind=candidate.connection_kind,
            language=language,
            path=path or ("." if mode == "list" else ""),
            fallback=base_candidate_preview(candidate, language),
        )
    if family_id == "source_lookup":
        return build_source_lookup_preview(
            mode=source_lookup_mode(behavior_profile=profile, plan_class=candidate.plan_class),
            language=language,
            group_name=extract_website_group_text(query),
            fallback=base_candidate_preview(candidate, language),
        )
    if family_id == "mailbox_access":
        return build_mailbox_access_preview(
            mode=mailbox_access_mode(behavior_profile=profile, plan_class=candidate.plan_class),
            language=language,
            search_query=extract_mail_search_text(query),
            fallback=base_candidate_preview(candidate, language),
        )
    if family_id == "request_target":
        return build_request_target_preview(
            mode=request_target_mode(behavior_profile=profile, plan_class=candidate.plan_class),
            path=CapabilityRouter._extract_path(query),
            fallback=base_candidate_preview(candidate, language),
        )
    if profile == "discord_send_message":
        message = extract_message_text(query)
        prefix = _localized_text(language, de="Discord-Nachricht", en="Discord message")
        return f'{prefix}: "{message}"' if message else base_candidate_preview(candidate, language)
    if profile == "webhook_send_message":
        message = extract_message_text(query)
        prefix = _localized_text(language, de="Webhook-Payload", en="Webhook payload")
        return f'{prefix}: "{message}"' if message else base_candidate_preview(candidate, language)
    if profile == "email_send_message":
        message = extract_message_text(query)
        prefix = _localized_text(language, de="E-Mail-Inhalt", en="Email content")
        return f'{prefix}: "{message}"' if message else base_candidate_preview(candidate, language)
    if profile == "mqtt_publish_message":
        topic = extract_mqtt_topic_text(query)
        prefix = _localized_text(language, de="MQTT-Topic", en="MQTT topic")
        return f"{prefix}: {topic}" if topic else base_candidate_preview(candidate, language)
    if profile == "calendar_read_events":
        range_hint = extract_calendar_range_text(query)
        search = extract_calendar_search_text(query)
        range_labels = {
            "today": _localized_text(language, de="Heute", en="Today"),
            "tomorrow": _localized_text(language, de="Morgen", en="Tomorrow"),
            "day_after_tomorrow": _candidate_detail_text(language, "calendar_day_after_tomorrow", "Day after tomorrow"),
            "this_week": _localized_text(language, de="Diese Woche", en="This week"),
            "next_week": _candidate_detail_text(language, "calendar_next_week", "Next week"),
            "next": _candidate_detail_text(language, "calendar_next", "Next appointment"),
            "upcoming": _localized_text(language, de="Anstehende Termine", en="Upcoming events"),
        }
        label = range_labels.get(range_hint, range_labels["upcoming"])
        prefix = _localized_text(language, de="Kalender", en="Calendar")
        return f"{prefix}: {label}" + (f" · {search}" if search else "")
    return base_candidate_preview(candidate, language)


def derive_candidate_inputs(
    candidate: Any,
    query: str,
    *,
    extract_command_text: Callable[[str], str],
    extract_remote_path: Callable[[str], str],
    extract_mail_search_text: Callable[[str], str],
    extract_message_text: Callable[[str], str],
    extract_mqtt_topic_text: Callable[[str], str],
    extract_website_group_text: Callable[[str], str],
    extract_calendar_range_text: Callable[[str], str],
    extract_calendar_search_text: Callable[[str], str],
) -> dict[str, str]:
    if is_recipe_candidate_kind(candidate.candidate_kind):
        return dict(candidate.inputs or {})
    profile = action_template_behavior_profile(candidate.candidate_id)
    family_id = behavior_family_id_for(behavior_profile=profile, plan_class=candidate.plan_class)
    if profile == "ssh_run_command":
        command = extract_command_text(query)
        if not command:
            command = _default_ssh_template_command(candidate, query)
        return {"command": command} if command else {}
    if family_id == "file_operation":
        return derive_file_operation_inputs(
            mode=file_operation_mode(behavior_profile=profile, plan_class=candidate.plan_class),
            query=query,
            extract_remote_path=extract_remote_path,
        )
    if family_id == "source_lookup":
        return derive_source_lookup_inputs(
            mode=source_lookup_mode(behavior_profile=profile, plan_class=candidate.plan_class),
            extract_website_group=extract_website_group_text,
            query=query,
        )
    if family_id == "mailbox_access":
        return derive_mailbox_access_inputs(
            mode=mailbox_access_mode(behavior_profile=profile, plan_class=candidate.plan_class),
            search_query=extract_mail_search_text(query),
        )
    if family_id == "request_target":
        path = CapabilityRouter._extract_path(query)
        return {"request_path": path} if path else {}
    if profile == "calendar_read_events":
        rows = {"range": extract_calendar_range_text(query) or "upcoming"}
        search = extract_calendar_search_text(query)
        if search:
            rows["search_query"] = search
        return rows
    if profile in {"discord_send_message", "webhook_send_message", "email_send_message"}:
        message = extract_message_text(query)
        return {"message": message} if message else {}
    if profile == "mqtt_publish_message":
        rows: dict[str, str] = {}
        topic = extract_mqtt_topic_text(query)
        message = extract_message_text(query)
        if topic:
            rows["topic"] = topic
        if message:
            rows["message"] = message
        return rows
    return {}


def missing_required_input(
    candidate: Any,
    query: str,
    *,
    connection_ref: str = "",
    extract_command_text: Callable[[str], str],
    extract_remote_path: Callable[[str], str],
    extract_mail_search_text: Callable[[str], str],
    extract_message_text: Callable[[str], str],
    extract_mqtt_topic_text: Callable[[str], str],
    extract_website_group_text: Callable[[str], str],
    extract_calendar_range_text: Callable[[str], str],
    extract_calendar_search_text: Callable[[str], str],
) -> str:
    if is_recipe_candidate_kind(candidate.candidate_kind):
        return ""
    candidate_id = str(candidate.candidate_id or "").strip()
    inputs = derive_candidate_inputs(
        candidate,
        query,
        extract_command_text=extract_command_text,
        extract_remote_path=extract_remote_path,
        extract_mail_search_text=extract_mail_search_text,
        extract_message_text=extract_message_text,
        extract_mqtt_topic_text=extract_mqtt_topic_text,
        extract_website_group_text=extract_website_group_text,
        extract_calendar_range_text=extract_calendar_range_text,
        extract_calendar_search_text=extract_calendar_search_text,
    )
    for key in action_template_required_inputs(candidate_id):
        if not str(inputs.get(key, "") or "").strip():
            return key
    if action_template_behavior_profile(candidate_id) == "mqtt_publish_message":
        if not extract_mqtt_topic_text(query) and not str(connection_ref or "").strip():
            return "topic"
    return ""


def candidate_kind_label(kind: str, language: str = "") -> str:
    return taxonomy_candidate_kind_label(kind, language=language)


def intent_label(intent: str, language: str = "") -> str:
    clean = str(intent or "").strip().lower()
    mapping = {
        "health_check": _localized_text(language, de="Gesundheitscheck", en="Health check"),
        "run_command": _localized_text(language, de="Kommando ausfuehren", en="Run command"),
        "list_files": _localized_text(language, de="Dateien anzeigen", en="List files"),
        "read_file": _localized_text(language, de="Datei lesen", en="Read file"),
        "write_file": _localized_text(language, de="Datei schreiben", en="Write file"),
        "read_calendar": _localized_text(language, de="Kalender lesen", en="Read calendar"),
        "read_feed": _localized_text(language, de="Feed lesen", en="Read feed"),
        "send_message": _localized_text(language, de="Nachricht senden", en="Send message"),
        "read_mail": _localized_text(language, de="Postfach lesen", en="Read mailbox"),
        "search_mail": _localized_text(language, de="Postfach durchsuchen", en="Search mailbox"),
        "publish_message": _localized_text(language, de="Nachricht publizieren", en="Publish message"),
        "api_request": _localized_text(language, de="API-Anfrage", en="API request"),
        "transform": _localized_text(language, de="Transformieren", en="Transform"),
    }
    return mapping.get(clean, clean)


def capability_label(capability: str, language: str = "") -> str:
    clean = str(capability or "").strip().lower()
    mapping = {
        "ssh_command": _localized_text(language, de="SSH-Befehl", en="SSH command"),
        "ssh": "SSH",
        "file_read": _localized_text(language, de="Datei lesen", en="Read file"),
        "file_write": _localized_text(language, de="Datei schreiben", en="Write file"),
        "sftp": "SFTP",
        "smb": "SMB",
        "calendar_read": _localized_text(language, de="Kalendertermine lesen", en="Read calendar events"),
        "google_calendar": _localized_text(language, de="Google Kalender", en="Google Calendar"),
        "discord_send": _localized_text(language, de="Discord-Nachricht senden", en="Send Discord message"),
        "discord": "Discord",
        "rss_read": _localized_text(language, de="Feed lesen", en="Read feed"),
        "website_read": _candidate_detail_text(language, "capability_website_read", "Open watched website"),
        "website_list": _candidate_detail_text(language, "capability_website_list", "List watched websites"),
        "rss": "RSS",
        "website": _candidate_detail_text(language, "capability_website", "Watched websites"),
        "webhook_send": _localized_text(language, de="Webhook senden", en="Send webhook"),
        "webhook": "Webhook",
        "email_send": _localized_text(language, de="E-Mail senden", en="Send email"),
        "email": _localized_text(language, de="E-Mail", en="Email"),
        "mail_read": _localized_text(language, de="Postfach lesen", en="Read mailbox"),
        "mail_search": _localized_text(language, de="Postfach durchsuchen", en="Search mailbox"),
        "imap": "IMAP",
        "mqtt_publish": _localized_text(language, de="MQTT-Nachricht senden", en="Publish MQTT message"),
        "mqtt": "MQTT",
        "http_api_request": _localized_text(language, de="HTTP-API-Anfrage", en="HTTP API request"),
        "http_api": _localized_text(language, de="HTTP-API", en="HTTP API"),
        "chat_send": _localized_text(language, de="Chat-Antwort senden", en="Send chat reply"),
    }
    return mapping.get(clean, clean)


def input_key_label(key: str, language: str = "") -> str:
    clean = str(key or "").strip().lower()
    mapping = {
        "command": _localized_text(language, de="Befehl", en="Command"),
        "connection_ref": _localized_text(language, de="Zielprofil", en="Target profile"),
        "remote_path": _localized_text(language, de="Remote-Pfad", en="Remote path"),
        "message": _localized_text(language, de="Nachricht", en="Message"),
        "range": _localized_text(language, de="Zeitraum", en="Range"),
        "search_query": _localized_text(language, de="Suchanfrage", en="Search query"),
        "topic": _localized_text(language, de="Topic", en="Topic"),
        "limit": _localized_text(language, de="Limit", en="Limit"),
    }
    return mapping.get(clean, clean)


def labels_are_semantically_duplicate(primary: str, secondary: str) -> bool:
    clean_primary = str(primary or "").strip().lower()
    clean_secondary = str(secondary or "").strip().lower()
    if not clean_primary or not clean_secondary:
        return False
    if clean_primary == clean_secondary:
        return True
    primary_tokens = {token for token in re.split(r"[^a-z0-9]+", clean_primary) if token}
    secondary_tokens = {token for token in re.split(r"[^a-z0-9]+", clean_secondary) if token}
    if not primary_tokens or not secondary_tokens:
        return False
    return primary_tokens.issubset(secondary_tokens) or secondary_tokens.issubset(primary_tokens)


def plan_summary_line(
    *,
    candidate_kind_label: str = "",
    intent_label: str = "",
    capability_label: str = "",
    target_context: str = "",
    language: str = "",
) -> str:
    clean_kind = str(candidate_kind_label or "").strip()
    clean_intent = str(intent_label or "").strip()
    clean_capability = str(capability_label or "").strip()
    clean_target = str(target_context or "").strip()
    action_label = clean_intent or clean_capability
    capability_duplicate = labels_are_semantically_duplicate(clean_intent, clean_capability)
    if clean_capability and not capability_duplicate and action_label:
        connector = _localized_text(language, de=" via ", en=" via ")
        action_label = f"{action_label}{connector}{clean_capability}"
    elif not action_label:
        action_label = clean_kind
        clean_kind = ""
    prefix = f"{clean_kind}: " if clean_kind and action_label else clean_kind
    target_suffix = ""
    if clean_target:
        target_suffix = _localized_text(language, de=f" auf {clean_target}", en=f" on {clean_target}")
    return f"{prefix}{action_label}{target_suffix}".strip()


def serialize_input_items(inputs: dict[str, str], language: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in (inputs or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if not clean_key:
            continue
        rows.append(
            {
                "key": clean_key,
                "key_label": input_key_label(clean_key, language),
                "value": clean_value,
            }
        )
    return rows


def apply_candidate_labels(
    payload: dict[str, Any],
    candidate: Any,
    query: str,
    *,
    language: str = "",
    connection_ref: str = "",
    target_context: str = "",
    extract_command_text: Callable[[str], str],
    extract_remote_path: Callable[[str], str],
    extract_mail_search_text: Callable[[str], str],
    extract_message_text: Callable[[str], str],
    extract_mqtt_topic_text: Callable[[str], str],
    extract_website_group_text: Callable[[str], str],
    extract_calendar_range_text: Callable[[str], str],
    extract_calendar_search_text: Callable[[str], str],
    base_candidate_preview: Callable[[Any, str], str],
) -> str:
    payload["candidate_kind_label"] = taxonomy_candidate_kind_label(
        candidate.candidate_kind,
        role=str(getattr(candidate, "candidate_role", "") or "").strip(),
        language=language,
    )
    payload["intent_label"] = intent_label(str(payload.get("intent") or candidate.intent), language)
    payload["capability_label"] = capability_label(candidate.capability, language)
    payload["preview"] = derive_candidate_preview(
        candidate,
        query,
        language=language,
        extract_command_text=extract_command_text,
        extract_remote_path=extract_remote_path,
        extract_mail_search_text=extract_mail_search_text,
        extract_message_text=extract_message_text,
        extract_mqtt_topic_text=extract_mqtt_topic_text,
        extract_website_group_text=extract_website_group_text,
        extract_calendar_range_text=extract_calendar_range_text,
        extract_calendar_search_text=extract_calendar_search_text,
        base_candidate_preview=base_candidate_preview,
    )
    payload["inputs"] = derive_candidate_inputs(
        candidate,
        query,
        extract_command_text=extract_command_text,
        extract_remote_path=extract_remote_path,
        extract_mail_search_text=extract_mail_search_text,
        extract_message_text=extract_message_text,
        extract_mqtt_topic_text=extract_mqtt_topic_text,
        extract_website_group_text=extract_website_group_text,
        extract_calendar_range_text=extract_calendar_range_text,
        extract_calendar_search_text=extract_calendar_search_text,
    )
    payload["input_items"] = serialize_input_items(payload["inputs"], language)
    missing_input = missing_required_input(
        candidate,
        query,
        connection_ref=connection_ref,
        extract_command_text=extract_command_text,
        extract_remote_path=extract_remote_path,
        extract_mail_search_text=extract_mail_search_text,
        extract_message_text=extract_message_text,
        extract_mqtt_topic_text=extract_mqtt_topic_text,
        extract_website_group_text=extract_website_group_text,
        extract_calendar_range_text=extract_calendar_range_text,
        extract_calendar_search_text=extract_calendar_search_text,
    )
    payload["missing_input_label"] = input_key_label(missing_input, language)
    payload["summary_line"] = plan_summary_line(
        candidate_kind_label=str(payload.get("candidate_kind_label") or ""),
        intent_label=str(payload.get("intent_label") or ""),
        capability_label=str(payload.get("capability_label") or ""),
        target_context=target_context,
        language=language,
    )
    return missing_input


def clarifying_question(candidate: Any, missing_input: str, language: str = "") -> str:
    if missing_input == "command":
        return _localized_text(language, de="Welchen Befehl soll ARIA auf diesem Ziel ausfuehren?", en="Which command should ARIA run on this target?")
    if missing_input == "remote_path":
        if str(candidate.intent or "").strip().lower() == "write_file":
            return _localized_text(language, de="Auf welchen Remote-Pfad soll ARIA schreiben?", en="Which remote path should ARIA write to?")
        return _localized_text(language, de="Welchen Remote-Pfad soll ARIA lesen?", en="Which remote path should ARIA read?")
    if missing_input == "message":
        return _localized_text(language, de="Welche Nachricht soll ARIA senden?", en="What message should ARIA send?")
    if missing_input == "search_query":
        return _localized_text(language, de="Wonach soll ARIA im Postfach suchen?", en="What should ARIA search for in the mailbox?")
    if missing_input == "topic":
        return _localized_text(language, de="Auf welches MQTT-Topic soll ARIA senden?", en="Which MQTT topic should ARIA publish to?")
    return _localized_text(language, de="Was genau soll ARIA auf diesem Ziel tun?", en="What exactly should ARIA do on this target?")


def build_serialized_candidate(
    candidate: Any,
    query: str,
    *,
    language: str = "",
    connection_ref: str = "",
    target_context: str = "",
    execution_state: Callable[..., str],
    execution_state_label: Callable[..., str],
    extract_command_text: Callable[[str], str],
    extract_remote_path: Callable[[str], str],
    extract_mail_search_text: Callable[[str], str],
    extract_message_text: Callable[[str], str],
    extract_mqtt_topic_text: Callable[[str], str],
    extract_website_group_text: Callable[[str], str],
    extract_calendar_range_text: Callable[[str], str],
    extract_calendar_search_text: Callable[[str], str],
    base_candidate_preview: Callable[[Any, str], str],
) -> dict[str, Any]:
    payload = candidate_payload(candidate)
    missing_input = apply_candidate_labels(
        payload,
        candidate,
        query,
        language=language,
        connection_ref=connection_ref,
        target_context=target_context,
        extract_command_text=extract_command_text,
        extract_remote_path=extract_remote_path,
        extract_mail_search_text=extract_mail_search_text,
        extract_message_text=extract_message_text,
        extract_mqtt_topic_text=extract_mqtt_topic_text,
        extract_website_group_text=extract_website_group_text,
        extract_calendar_range_text=extract_calendar_range_text,
        extract_calendar_search_text=extract_calendar_search_text,
        base_candidate_preview=base_candidate_preview,
    )
    state = execution_state(missing_input=missing_input)
    payload["execution_state"] = state
    payload["execution_state_label"] = execution_state_label(state, language)
    payload["missing_input"] = missing_input
    payload["clarifying_question"] = clarifying_question(candidate, missing_input, language) if missing_input else ""
    payload["example_prompt"] = (
        core_suggested_follow_up_prompt(
            query,
            candidate=candidate,
            connection_ref=connection_ref,
            missing_input=missing_input,
            language=language,
            localized_text=_localized_text,
            extract_remote_path=extract_remote_path,
            extract_message_text=extract_message_text,
            extract_mail_search_text=lambda value, ref: extract_mail_search_text(value),
            extract_mqtt_topic_text=extract_mqtt_topic_text,
            extract_calendar_range_text=extract_calendar_range_text,
            extract_website_group_text=extract_website_group_text,
        )
        if missing_input
        else ""
    )
    return payload
