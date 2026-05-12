from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.action_plan import ActionPlan
from aria.core.connection_catalog import connection_kind_label
from aria.core.text_utils import is_english
from aria.core.i18n import I18NStore
from aria.core.website_runtime import find_website_matches
from aria.core.website_runtime import normalize_website_rows

_CAPABILITY_MESSAGES_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _capability_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CAPABILITY_MESSAGES_I18N.t(language or "de", f"pipeline_capability_messages.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template



def format_capability_missing_message(
    plan: ActionPlan,
    *,
    connection_rows: Any,
    language: str | None = None,
) -> str:
    available_refs = sorted(connection_rows.keys()) if isinstance(connection_rows, dict) else []
    kind_label = connection_kind_label(plan.connection_kind)
    if plan.requested_connection_ref:
        if "connection_ref" in list(plan.missing_fields or []):
            text = _capability_text(language, "message_23", 'I do not know a matching {kind_label} profile for `{plan_requested_connection_ref}` yet.', plan_requested_connection_ref=plan.requested_connection_ref, kind_label=kind_label)
        else:
            text = _capability_text(language, "message_29", 'I could not find the requested {kind_label} profile `{plan_requested_connection_ref}`.', kind_label=kind_label, plan_requested_connection_ref=plan.requested_connection_ref)
        if available_refs:
            text += _capability_text(language, "message_35", ' Available {kind_label} profiles: ', kind_label=kind_label) + ", ".join(available_refs) + "."
        elif "connection_ref" in list(plan.missing_fields or []):
            text += _capability_text(language, "message_41", ' There are currently no configured {kind_label} profiles.', kind_label=kind_label)
        if "connection_ref" in list(plan.missing_fields or []) and available_refs:
            text += _capability_text(language, "message_47", ' Just reply with the matching profile name. If it fits, ARIA can remember that mapping as an alias afterwards.')
        if plan.connection_kind == "website" and isinstance(connection_rows, dict):
            rows = normalize_website_rows(connection_rows)
            matches = find_website_matches(plan.requested_connection_ref, rows)
            if matches:
                suggestions = []
                for _, ref, row in matches[:3]:
                    title = str(row.get("title", "") or "").strip() or ref
                    suggestions.append(f"{title} (`{ref}`)")
                text += _capability_text(language, "message_60", ' Likely matches: ') + ", ".join(suggestions) + "."
        return text

    if is_english(language):
        labels = {
            "connection_ref": f"which {kind_label} profile / target I should use",
            "path": "which file path I should use",
            "content": "which content I should send or write",
        }
    else:
        labels = {
            "connection_ref": f"welches {kind_label}-Profil / welches Ziel ich verwenden soll",
            "path": "welchen Dateipfad ich verwenden soll",
            "content": "welchen Inhalt ich schreiben soll",
        }
    if plan.capability == "ssh_command":
        labels["content"] = _capability_text(language, "message_80", "which command I should run")
    missing = [labels.get(item, item) for item in plan.missing_fields]

    capability_intro = {
        "feed_read": _capability_text(language, "message_84", 'I can read this feed'),
        "calendar_read": _capability_text(language, "message_85", 'I can read the calendar'),
        "webhook_send": _capability_text(language, "message_86", 'I can send this via webhook'),
        "discord_send": _capability_text(language, "message_87", 'I can send this to Discord'),
        "api_request": _capability_text(language, "message_88", 'I can call this HTTP API'),
        "email_send": _capability_text(language, "message_89", 'I can send this message by email'),
        "mail_read": _capability_text(language, "message_90", 'I can read the mailbox'),
        "mail_search": _capability_text(language, "message_91", 'I can search the mailbox'),
        "mqtt_publish": _capability_text(language, "message_92", "I can publish this message via MQTT"),
        "ssh_command": _capability_text(language, "message_93", "I can run the SSH command"),
    }
    intro = capability_intro.get(
        str(plan.capability or "").strip().lower(),
        _capability_text(language, "message_97", 'I can do this via {kind_label}', kind_label=kind_label)
    )
    text = intro + _capability_text(language, "message_99", ', but I still need: ') + "; ".join(missing) + "."
    if "connection_ref" in plan.missing_fields:
        if available_refs:
            text += _capability_text(language, "message_102", ' Available {kind_label} profiles: ', kind_label=kind_label)+ ", ".join(available_refs) + "."
        else:
            text += _capability_text(language, "message_104", ' There are currently no configured {kind_label} profiles.', kind_label=kind_label)
    return text


def sanitize_capability_error(exc: Exception, *, language: str | None = None) -> str:
    if isinstance(exc, ValueError):
        return str(exc).strip() or _capability_text(language, "message_114", "Invalid input.")
    raw = str(exc).strip()
    if raw:
        return raw[:220]
    return _capability_text(language, "message_118", 'Unexpected runtime error.')


def format_capability_execution_error(
    plan: ActionPlan,
    exc: Exception,
    *,
    language: str | None = None,
) -> str:
    labels = {
        "feed_read": _capability_text(language, "message_128", 'The feed could not be read.'),
        "website_read": _capability_text(language, "message_129", "The watched website could not be opened."),
        "website_list": _capability_text(language, "message_130", 'The watched websites could not be read.'),
        "calendar_read": _capability_text(language, "message_131", 'The calendar events could not be read.'),
        "webhook_send": _capability_text(language, "message_132", 'The webhook could not be sent.'),
        "discord_send": _capability_text(language, "message_133", 'The Discord message could not be sent.'),
        "api_request": _capability_text(language, "message_134", "The HTTP API request could not be executed."),
        "email_send": _capability_text(language, "message_135", 'The email could not be sent.'),
        "mail_read": _capability_text(language, "message_136", 'The mailbox could not be read.'),
        "mail_search": _capability_text(language, "message_137", 'The mailbox could not be searched.'),
        "mqtt_publish": _capability_text(language, "message_138", "The MQTT message could not be published."),
        "ssh_command": _capability_text(language, "message_139", "The SSH command could not be executed."),
    }
    default_label = _capability_text(language, "message_141", 'The {connection_kind_label_plan_connection_kind} action could not be executed.', connection_kind_label_plan_connection_kind=connection_kind_label(plan.connection_kind))
    base = labels.get(str(plan.capability or "").strip().lower(), default_label)
    reason = sanitize_capability_error(exc, language=language)
    return _capability_text(language, "message_148", '{base} Reason: {reason}', base=base, reason=reason)
