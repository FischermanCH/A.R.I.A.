from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from aria.modules.action_planner_templates.taxonomy import candidate_kind_label as taxonomy_candidate_kind_label
from aria.modules.action_planner_templates.templates import action_template_behavior_profile
from aria.modules.action_planner_templates.templates import action_template_required_inputs
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.platform_primitives.text_utils import is_german


_CANDIDATE_DETAILS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _candidate_detail_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CANDIDATE_DETAILS_I18N.t(language or "de", f"action_planner_candidate_details.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _localized_text(language: str, *, de: str, en: str) -> str:
    return de if is_german(language) else en


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def candidate_metadata(source: Any) -> dict[str, Any]:
    return {
        "candidate_role": str(_source_value(source, "candidate_role") or "").strip(),
        "recipe_scope": dict(_source_value(source, "recipe_scope") or {}),
        "recipe_origin": str(_source_value(source, "recipe_origin") or "").strip(),
        "experience_count": int(_source_value(source, "experience_count") or 0),
        "last_success_at": str(_source_value(source, "last_success_at") or "").strip(),
        "promotion_state": str(_source_value(source, "promotion_state") or "").strip().lower(),
        "promotion_hint": str(_source_value(source, "promotion_hint") or "").strip(),
    }


def candidate_prompt_parts(source: Any) -> list[str]:
    metadata = candidate_metadata(source)
    parts: list[str] = []
    if metadata["recipe_origin"]:
        parts.append(f"recipe_origin={metadata['recipe_origin']}")
    if metadata["experience_count"] > 0:
        parts.append(f"experience_count={metadata['experience_count']}")
    if metadata["last_success_at"]:
        parts.append(f"last_success_at={metadata['last_success_at']}")
    if metadata["promotion_state"]:
        parts.append(f"promotion_state={metadata['promotion_state']}")
    if metadata["promotion_hint"]:
        parts.append(f"promotion_hint={metadata['promotion_hint']}")
    return parts


def candidate_decision_fields(source: Any, *, prefix: str = "") -> dict[str, Any]:
    metadata = candidate_metadata(source)
    return {
        f"{prefix}candidate_role": metadata["candidate_role"],
        f"{prefix}recipe_origin": metadata["recipe_origin"],
        f"{prefix}recipe_scope": dict(metadata["recipe_scope"] or {}),
        f"{prefix}experience_count": int(metadata["experience_count"] or 0),
        f"{prefix}last_success_at": metadata["last_success_at"],
        f"{prefix}promotion_state": metadata["promotion_state"],
        f"{prefix}promotion_hint": metadata["promotion_hint"],
    }


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
        **candidate_metadata(candidate),
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
    *,
    language: str = "",
    target_context: str = "",
    base_candidate_preview: Callable[[Any, str], str],
    resolved_inputs: dict[str, str] | None = None,
) -> str:
    payload["candidate_kind_label"] = taxonomy_candidate_kind_label(
        candidate.candidate_kind,
        role=str(getattr(candidate, "candidate_role", "") or "").strip(),
        language=language,
    )
    payload["intent_label"] = intent_label(str(payload.get("intent") or candidate.intent), language)
    payload["capability_label"] = capability_label(candidate.capability, language)
    payload["preview"] = base_candidate_preview(candidate, language)
    structured_inputs = dict(getattr(candidate, "inputs", {}) or {})
    structured_inputs.update(resolved_inputs or {})
    payload["inputs"] = {
        str(key or "").strip(): str(value or "").strip()
        for key, value in structured_inputs.items()
        if str(key or "").strip() and str(value or "").strip()
    }
    payload["input_items"] = serialize_input_items(payload["inputs"], language)
    missing_input = next(
        (
            key
            for key in action_template_required_inputs(str(candidate.candidate_id or "").strip())
            if not str(payload["inputs"].get(key, "") or "").strip()
        ),
        "",
    )
    payload["missing_input"] = missing_input
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
    *,
    language: str = "",
    target_context: str = "",
    execution_state: Callable[..., str],
    execution_state_label: Callable[..., str],
    base_candidate_preview: Callable[[Any, str], str],
) -> dict[str, Any]:
    payload = candidate_payload(candidate)
    missing_input = apply_candidate_labels(
        payload,
        candidate,
        language=language,
        target_context=target_context,
        base_candidate_preview=base_candidate_preview,
        resolved_inputs={},
    )
    state = execution_state(missing_input=missing_input)
    payload["execution_state"] = state
    payload["execution_state_label"] = execution_state_label(state, language)
    payload["missing_input"] = missing_input
    payload["clarifying_question"] = clarifying_question(candidate, missing_input, language) if missing_input else ""
    payload["example_prompt"] = ""
    return payload
