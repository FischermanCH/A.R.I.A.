from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.action_plan import CapabilityDraft
from aria.core.action_planner_templates import action_template_behavior_profile
from aria.core.action_planner_templates import action_template_plan_class
from aria.core.behavior_families import behavior_family_id_for
from aria.core.behavior_families import build_file_operation_draft
from aria.core.behavior_families import build_mailbox_access_draft
from aria.core.behavior_families import build_request_target_draft
from aria.core.behavior_families import build_source_lookup_draft
from aria.core.behavior_families import file_operation_behavior_profile_for
from aria.core.behavior_families import file_operation_mode
from aria.core.behavior_families import mailbox_access_behavior_profile_for
from aria.core.behavior_families import mailbox_access_mode
from aria.core.behavior_families import request_target_behavior_profile_for
from aria.core.behavior_families import request_target_mode
from aria.core.behavior_families import source_lookup_behavior_profile_for
from aria.core.behavior_families import source_lookup_mode
from aria.core.capability_router import CapabilityRouter
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.i18n import I18NStore

_TEMPLATE_PAYLOADS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _template_terms(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for lang in ("de", "en"):
        raw = _TEMPLATE_PAYLOADS_I18N.t(lang, f"execution_dry_run_template_payloads.{key}", "")
        terms.extend(term.strip().lower() for term in raw.split(",") if term.strip())
    return tuple(dict.fromkeys(terms)) or fallback


def _default_ssh_template_command(query: str, *, candidate_id: str = "", plan_class: str = "") -> str:
    lower = str(query or "").strip().lower()
    clean_candidate_id = str(candidate_id or "").strip().lower()
    clean_plan_class = str(plan_class or "").strip().lower()
    if clean_candidate_id == "ssh_run_command" or clean_plan_class == "command_single":
        if any(
            token in lower
            for token in _template_terms(
                "ssh_disk_terms",
                ("disk", "filesystem", "df "),
            )
        ):
            return "df -h"
        if any(
            token in lower
            for token in _template_terms(
                "ssh_memory_terms",
                ("ram", "memory", "free -h"),
            )
        ):
            return "free -h"
        if any(
            token in lower
            for token in _template_terms(
                "ssh_health_terms",
                ("health", "status", "uptime", "server", "host", "check"),
            )
        ):
            return "uptime"
        if not lower:
            return "uptime"
    return ""


def infer_common_file_path(query: str) -> str:
    lower = str(query or "").strip().lower()
    path = CapabilityRouter._extract_path(lower)
    if path:
        return path
    if "hosts datei" in lower or "hosts file" in lower or "die hosts" in lower:
        return "/etc/hosts"
    if "authorized_keys" in lower:
        return "~/.ssh/authorized_keys"
    return ""


def infer_message_content(query: str) -> str:
    generic = CapabilityRouter._extract_webhook_content(query)
    if generic:
        return generic
    lower = str(query or "").strip().lower()
    if "testnachricht" in lower or "test message" in lower:
        return "ARIA Testnachricht"
    return ""


def infer_mail_search_query(query: str, connection_ref: str = "") -> str:
    return CapabilityRouter._extract_mail_search_query(query, connection_ref)


def infer_mqtt_topic(query: str) -> str:
    return CapabilityRouter._extract_mqtt_topic(query)


def infer_calendar_range(query: str) -> str:
    return CapabilityRouter._extract_calendar_range(query)


def infer_calendar_search(query: str) -> str:
    return CapabilityRouter._extract_calendar_search(query)


def resolved_behavior_profile(*, plan_class: str, candidate_id: str) -> str:
    clean_plan_class = str(plan_class or "").strip().lower()
    if clean_plan_class == "command_single":
        return "ssh_run_command"
    family_id = behavior_family_id_for(plan_class=clean_plan_class)
    if family_id == "file_operation":
        return file_operation_behavior_profile_for(clean_plan_class)
    if family_id == "source_lookup":
        return source_lookup_behavior_profile_for(clean_plan_class)
    if family_id == "mailbox_access":
        return mailbox_access_behavior_profile_for(clean_plan_class)
    if family_id == "request_target":
        return request_target_behavior_profile_for(clean_plan_class)
    if clean_plan_class == "calendar_window":
        return "calendar_read_events"
    if clean_plan_class == "message_publish_basic":
        return "mqtt_publish_message"
    return action_template_behavior_profile(candidate_id)


def resolved_template_plan_class(*, candidate_id: str, plan_class: str = "") -> str:
    return str(plan_class or "").strip().lower() or action_template_plan_class(candidate_id)


def template_draft(
    query: str,
    *,
    candidate_id: str,
    connection_kind: str,
    connection_ref: str,
    plan_class: str = "",
) -> tuple[CapabilityDraft, str]:
    clean_kind = normalize_connection_kind(connection_kind)
    clean_ref = str(connection_ref or "").strip()
    draft = CapabilityDraft(capability="", connection_kind=clean_kind, explicit_connection_ref=clean_ref)
    preview = ""
    clean_plan_class = resolved_template_plan_class(candidate_id=candidate_id, plan_class=plan_class)
    behavior_profile = action_template_behavior_profile(candidate_id)
    family_id = behavior_family_id_for(behavior_profile=behavior_profile, plan_class=clean_plan_class)

    if clean_plan_class == "command_single" or behavior_profile == "ssh_run_command":
        draft.capability = "ssh_command"
        draft.content = CapabilityRouter._extract_ssh_command(query, clean_ref) or CapabilityRouter._extract_natural_ssh_command(query)
        if not str(draft.content or "").strip():
            draft.content = _default_ssh_template_command(query, candidate_id=candidate_id, plan_class=clean_plan_class)
        preview = f"SSH command: {draft.content}" if draft.content else "SSH command still needs clarification"
        return draft, preview

    if family_id == "file_operation":
        capability, path, content, preview = build_file_operation_draft(
            mode=file_operation_mode(behavior_profile=behavior_profile, plan_class=clean_plan_class),
            connection_kind=clean_kind,
            query=query,
            infer_common_file_path=infer_common_file_path,
            extract_path=CapabilityRouter._extract_path,
            extract_content=CapabilityRouter._extract_content,
        )
        draft.capability = capability
        draft.path = path
        draft.content = content
        return draft, preview

    if family_id == "source_lookup":
        capability, content, preview = build_source_lookup_draft(
            mode=source_lookup_mode(behavior_profile=behavior_profile, plan_class=clean_plan_class),
            query=query,
            extract_website_group=CapabilityRouter._extract_website_group,
        )
        draft.capability = capability
        draft.content = content
        return draft, preview

    if family_id == "mailbox_access":
        capability, content, preview = build_mailbox_access_draft(
            mode=mailbox_access_mode(behavior_profile=behavior_profile, plan_class=clean_plan_class),
            search_query=infer_mail_search_query(query, clean_ref),
        )
        draft.capability = capability
        draft.content = content
        return draft, preview

    if family_id == "request_target":
        capability, path = build_request_target_draft(
            mode=request_target_mode(behavior_profile=behavior_profile, plan_class=clean_plan_class),
            path=CapabilityRouter._extract_path(query),
        )
        draft.capability = capability
        draft.path = path
        preview = f"HTTP request path: {path}" if path else "API path still missing"
        return draft, preview

    if behavior_profile == "discord_send_message":
        draft.capability = "discord_send"
        draft.content = infer_message_content(query)
        preview = f"Discord message: {draft.content}" if draft.content else "Discord message text still missing"
        return draft, preview

    if behavior_profile == "webhook_send_message":
        draft.capability = "webhook_send"
        draft.content = infer_message_content(query)
        preview = f"Webhook payload: {draft.content}" if draft.content else "Webhook payload still missing"
        return draft, preview

    if behavior_profile == "email_send_message":
        draft.capability = "email_send"
        draft.content = infer_message_content(query)
        preview = f"Email content: {draft.content}" if draft.content else "Email content still missing"
        return draft, preview

    if behavior_profile == "mqtt_publish_message":
        draft.capability = "mqtt_publish"
        draft.path = infer_mqtt_topic(query)
        draft.content = infer_message_content(query)
        if draft.path and draft.content:
            preview = f"MQTT publish to {draft.path}: {draft.content}"
        elif draft.path:
            preview = f"MQTT topic: {draft.path}"
        else:
            preview = "MQTT topic still missing"
        return draft, preview

    if clean_plan_class == "calendar_window" or behavior_profile == "calendar_read_events":
        draft.capability = "calendar_read"
        draft.path = infer_calendar_range(query) or "upcoming"
        draft.content = infer_calendar_search(query)
        preview = f"Read calendar range: {draft.path}"
        return draft, preview

    return draft, preview


def apply_template_connection_defaults(
    *,
    settings: Any,
    candidate_id: str,
    plan_class: str,
    connection_kind: str,
    connection_ref: str,
    draft: CapabilityDraft,
    preview: str,
    connection_row: Any,
    read_row_value: Any,
) -> tuple[CapabilityDraft, str]:
    del settings
    if (
        (action_template_behavior_profile(candidate_id) == "mqtt_publish_message" or plan_class == "message_publish_basic")
        and not str(draft.path or "").strip()
        and connection_ref
    ):
        connection = connection_row(connection_kind, connection_ref)
        default_topic = read_row_value(connection, "topic") if connection is not None else ""
        if default_topic:
            draft.path = default_topic
            if str(draft.content or "").strip():
                preview = f"MQTT publish to {default_topic}: {draft.content}"
            else:
                preview = f"MQTT topic: {default_topic}"
    return draft, preview
