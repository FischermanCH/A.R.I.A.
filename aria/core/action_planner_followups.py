from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from aria.core.i18n import I18NStore

from aria.core.behavior_families import behavior_family_id_for
from aria.core.behavior_families import file_operation_mode
from aria.core.behavior_families import mailbox_access_mode
from aria.core.behavior_families import source_lookup_mode

_ACTION_PLANNER_FOLLOWUPS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _followup_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _ACTION_PLANNER_FOLLOWUPS_I18N.t(language or "de", f"action_planner_followups.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template



def follow_up_target_phrase(query: str, connection_ref: str, *, mode: str, localized_text: Callable[..., str], language: str = "") -> str:
    lowered = str(query or "").strip().lower()
    clean_ref = str(connection_ref or "").strip()
    if mode == "read":
        if "management server" in lowered:
            return _followup_text(language, "message_16", 'from the management server')
        if "pi-hole" in lowered or "pi hole" in lowered:
            return _followup_text(language, "message_18", 'from the pi-hole')
        return _followup_text(language, "message_19", 'from {clean_ref}', clean_ref=clean_ref) if clean_ref else _followup_text(language, "message_19", 'from this target')
    if mode == "write":
        if "management server" in lowered:
            return _followup_text(language, "message_22", 'to the management server')
        return _followup_text(language, "message_23", 'to {clean_ref}', clean_ref=clean_ref) if clean_ref else _followup_text(language, "message_23", 'to this target')
    if mode == "message":
        if "alerts channel" in lowered:
            return _followup_text(language, "message_26", 'to my alerts channel')
        if "channel" in lowered:
            return _followup_text(language, "message_28", 'to the channel')
        return _followup_text(language, "message_29", 'to {clean_ref}', clean_ref=clean_ref) if clean_ref else _followup_text(language, "message_29", 'to this target')
    if "pi-hole" in lowered or "pi hole" in lowered:
        return _followup_text(language, "message_31", 'on the pi-hole')
    if "dns server" in lowered or "dns-server" in lowered:
        return _followup_text(language, "message_33", 'on the DNS server')
    return _followup_text(language, "message_34", 'on {clean_ref}', clean_ref=clean_ref) if clean_ref else _followup_text(language, "message_34", 'on this target')


def suggested_follow_up_prompt(
    query: str,
    *,
    candidate: Any,
    connection_ref: str,
    missing_input: str = "",
    language: str = "",
    localized_text: Callable[..., str],
    extract_remote_path: Callable[[str], str],
    extract_message_text: Callable[[str], str],
    extract_mail_search_text: Callable[[str, str], str],
    extract_mqtt_topic_text: Callable[[str], str],
    extract_calendar_range_text: Callable[[str], str],
    extract_website_group_text: Callable[[str], str],
) -> str:
    inputs = dict(getattr(candidate, "inputs", {}) or {})
    behavior_profile = str(getattr(candidate, "behavior_profile", "") or inputs.get("behavior_profile", "") or "").strip().lower()
    if not behavior_profile:
        behavior_profile = str(getattr(candidate, "candidate_id", "") or "").strip().lower()
    plan_class = str(getattr(candidate, "plan_class", "") or "").strip().lower()
    family_id = behavior_family_id_for(behavior_profile=behavior_profile, plan_class=plan_class)
    clean_ref = str(connection_ref or "").strip()

    if behavior_profile == "ssh_run_command":
        target = follow_up_target_phrase(query, connection_ref, mode="ssh", localized_text=localized_text, language=language)
        return _followup_text(language, "message_62", 'Run "df -h" {target}', target=target)

    if family_id == "file_operation":
        mode = file_operation_mode(behavior_profile=behavior_profile, plan_class=plan_class)
        if mode == "read":
            target = follow_up_target_phrase(query, connection_ref, mode="read", localized_text=localized_text, language=language)
            example_path = "/etc/hosts" if missing_input == "remote_path" else (extract_remote_path(query) or "/etc/hosts")
            return _followup_text(language, "message_69", 'Read {example_path} {target}', example_path=example_path, target=target)
        if mode == "write":
            target = follow_up_target_phrase(query, connection_ref, mode="write", localized_text=localized_text, language=language)
            example_path = "/tmp/example.txt" if missing_input == "remote_path" else (extract_remote_path(query) or "/tmp/example.txt")
            return _followup_text(language, "message_73", 'Write "..." to {example_path} {target}', example_path=example_path, target=target)

    if behavior_profile in {"discord_send_message", "webhook_send_message", "email_send_message"}:
        message = (
            extract_message_text(query)
            or {
                "discord_send_message": "ARIA lebt",
                "webhook_send_message": "ARIA webhook test",
                "email_send_message": "ARIA Mail-Test",
            }.get(behavior_profile, "")
        )
        if behavior_profile == "discord_send_message":
            target = follow_up_target_phrase(query, connection_ref, mode="message", localized_text=localized_text, language=language)
            return _followup_text(language, "message_86", 'Send {target} "{message}"', target=target, message=message)
        if behavior_profile == "webhook_send_message":
            return _followup_text(language, "message_88", 'Send to {clean_ref_or_the_webhook} "{message}"', clean_ref_or_den_Webhook=clean_ref or "den Webhook", message=message, clean_ref_or_the_webhook=clean_ref or "the webhook")
        return _followup_text(language, "message_89", 'Send via {clean_ref_or_the_mail_profile} "{message}"', clean_ref_or_das_Mail_Profil=clean_ref or "das Mail-Profil", message=message, clean_ref_or_the_mail_profile=clean_ref or "the mail profile")

    if family_id == "mailbox_access":
        mode = mailbox_access_mode(behavior_profile=behavior_profile, plan_class=plan_class)
        if mode == "read":
            if clean_ref:
                return _followup_text(language, "message_94_with_ref", "Read the latest emails from {clean_ref}", clean_ref=clean_ref)
            return _followup_text(language, "message_94_no_ref", "Read the latest emails from the mailbox")
        if mode == "search":
            search = extract_mail_search_text(query, clean_ref) or "Rechnung"
            return _followup_text(language, "message_101", 'Search {clean_ref_or_the_mailbox} for "{search}"', clean_ref_or_dem_Postfach=clean_ref or "dem Postfach", search=search, clean_ref_or_the_mailbox=clean_ref or "the mailbox")

    if behavior_profile == "mqtt_publish_message":
        topic = extract_mqtt_topic_text(query) or "aria/events"
        message = extract_message_text(query) or "ARIA Event"
        return _followup_text(language, "message_110", 'Publish via {clean_ref_or_MQTT} to topic {topic} "{message}"', clean_ref_or_MQTT=clean_ref or "MQTT", topic=topic, message=message)

    if behavior_profile == "calendar_read_events":
        range_hint = extract_calendar_range_text(query) or "today"
        examples = {
            "today": _followup_text(language, "message_115", 'What is on my calendar today?'),
            "tomorrow": _followup_text(language, "message_116", 'What do I have on my calendar tomorrow?'),
            "next": _followup_text(language, "message_117", 'When is my next appointment?')
        }
        return examples.get(
            range_hint,
            _followup_text(language, "message_121_with_ref", "Show me the next events from {clean_ref}", clean_ref=clean_ref)
            if clean_ref
            else _followup_text(language, "message_121_no_ref", "Show me my next events"),
        )

    if family_id == "source_lookup":
        mode = source_lookup_mode(behavior_profile=behavior_profile, plan_class=plan_class)
        if mode == "digest":
            if clean_ref:
                return _followup_text(language, "message_131_with_ref", "Read the latest headlines from {clean_ref}", clean_ref=clean_ref)
            return _followup_text(language, "message_131_no_ref", "Read the latest headlines from the feed")
        if mode == "reference":
            if clean_ref:
                return _followup_text(language, "message_137_with_ref", "Open watched website {clean_ref}", clean_ref=clean_ref)
            return _followup_text(language, "message_137_no_ref", "Open the matching watched website")
        if mode == "listing":
            group = extract_website_group_text(query)
            if group:
                return _followup_text(language, "message_144_with_group", "List watched websites in {group}", group=group)
            return _followup_text(language, "message_144_no_group", "List watched websites")

    if family_id == "request_target":
        if clean_ref:
            return _followup_text(language, "message_151_with_ref", "Call the status endpoint on {clean_ref}", clean_ref=clean_ref)
        return _followup_text(language, "message_151_no_ref", "Call the status endpoint")

    return ""
