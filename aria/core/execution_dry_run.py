from __future__ import annotations

from typing import Any

from aria.core.action_plan import ActionPlan, CapabilityDraft, MemoryHints, build_action_plan
from aria.core.capability_router import CapabilityRouter
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.custom_skills import _load_custom_skill_manifests
from aria.core.guardrails import evaluate_guardrail, resolve_guardrail_profile


def _is_german_language(language: str) -> bool:
    return str(language or "").strip().lower().startswith("de")


def _localized_text(language: str, *, de: str, en: str) -> str:
    return de if _is_german_language(language) else en


def _read_row_value(row: Any, name: str) -> str:
    if isinstance(row, dict):
        return str(row.get(name, "") or "").strip()
    return str(getattr(row, name, "") or "").strip()


def _connection_row(settings: Any, kind: str, ref: str) -> Any | None:
    rows = getattr(getattr(settings, "connections", object()), str(kind or "").strip().lower(), {})
    if not isinstance(rows, dict):
        return None
    return rows.get(ref)


def _find_skill_manifest(skill_id: str) -> dict[str, Any] | None:
    clean_id = str(skill_id or "").strip()
    if not clean_id:
        return None
    manifests, _ = _load_custom_skill_manifests()
    for manifest in manifests:
        if str(manifest.get("id", "") or "").strip() == clean_id:
            return manifest
    return None


def _skill_first_step_preview(manifest: dict[str, Any] | None) -> tuple[str, str, str]:
    if not isinstance(manifest, dict):
        return "", "", ""
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return "", "", ""
    first = dict((steps[0] or {}))
    step_type = str(first.get("type", "") or "").strip().lower()
    params = dict(first.get("params", {}) or {})
    if step_type == "ssh_run":
        command = str(params.get("command", "") or "").strip()
        return "ssh_command", command, f"SSH command: {command}" if command else "SSH command from skill"
    if step_type in {"sftp_read", "smb_read"}:
        path = str(params.get("remote_path", "") or "").strip()
        return "file_read", path, f"Read remote path: {path}" if path else "Read remote file from skill"
    if step_type in {"sftp_write", "smb_write"}:
        path = str(params.get("remote_path", "") or "").strip()
        return "file_write", path, f"Write remote path: {path}" if path else "Write remote file from skill"
    if step_type == "discord_send":
        message = str(params.get("message", "") or "").strip()
        return "discord_send", message, f"Discord message: {message}" if message else "Discord message from skill"
    if step_type == "rss_read":
        return "feed_read", "", "Read feed via skill"
    return "", "", step_type or "Custom skill step"


def _infer_common_file_path(query: str) -> str:
    lower = str(query or "").strip().lower()
    path = CapabilityRouter._extract_path(lower)
    if path:
        return path
    if "hosts datei" in lower or "hosts file" in lower or "die hosts" in lower:
        return "/etc/hosts"
    if "authorized_keys" in lower:
        return "~/.ssh/authorized_keys"
    return ""


def _infer_message_content(query: str) -> str:
    generic = CapabilityRouter._extract_webhook_content(query)
    if generic:
        return generic
    lower = str(query or "").strip().lower()
    if "testnachricht" in lower or "test message" in lower:
        return "ARIA Testnachricht"
    return ""


def _infer_mail_search_query(query: str, connection_ref: str = "") -> str:
    return CapabilityRouter._extract_mail_search_query(query, connection_ref)


def _infer_mqtt_topic(query: str) -> str:
    return CapabilityRouter._extract_mqtt_topic(query)


def _infer_calendar_range(query: str) -> str:
    return CapabilityRouter._extract_calendar_range(query)


def _infer_calendar_search(query: str) -> str:
    return CapabilityRouter._extract_calendar_search(query)


def _template_draft(query: str, *, candidate_id: str, connection_kind: str, connection_ref: str) -> tuple[CapabilityDraft, str]:
    clean_kind = normalize_connection_kind(connection_kind)
    clean_ref = str(connection_ref or "").strip()
    draft = CapabilityDraft(capability="", connection_kind=clean_kind, explicit_connection_ref=clean_ref)
    preview = ""
    if candidate_id == "ssh_health_check":
        draft.capability = "ssh_command"
        draft.content = "uptime"
        preview = "SSH command: uptime"
    elif candidate_id == "ssh_run_command":
        draft.capability = "ssh_command"
        draft.content = CapabilityRouter._extract_ssh_command(query, clean_ref) or CapabilityRouter._extract_natural_ssh_command(query)
        preview = f"SSH command: {draft.content}" if draft.content else "SSH command still needs clarification"
    elif candidate_id == "sftp_read_file":
        draft.capability = "file_read"
        draft.path = _infer_common_file_path(query)
        preview = f"Read remote path: {draft.path}" if draft.path else "Remote file path still missing"
    elif candidate_id == "sftp_list_files":
        draft.capability = "file_list"
        draft.path = CapabilityRouter._extract_path(query) or "."
        preview = f"List remote path: {draft.path}"
    elif candidate_id == "sftp_write_file":
        draft.capability = "file_write"
        draft.path = _infer_common_file_path(query)
        draft.content = CapabilityRouter._extract_content(query)
        preview = f"Write remote path: {draft.path}" if draft.path else "Remote write path still missing"
    elif candidate_id == "smb_read_file":
        draft.capability = "file_read"
        draft.path = _infer_common_file_path(query)
        preview = f"Read share path: {draft.path}" if draft.path else "Share path still missing"
    elif candidate_id == "smb_list_files":
        draft.capability = "file_list"
        draft.path = CapabilityRouter._extract_path(query) or "."
        preview = f"List share path: {draft.path}"
    elif candidate_id == "smb_write_file":
        draft.capability = "file_write"
        draft.path = _infer_common_file_path(query)
        draft.content = CapabilityRouter._extract_content(query)
        preview = f"Write share path: {draft.path}" if draft.path else "Share write path still missing"
    elif candidate_id == "discord_send_message":
        draft.capability = "discord_send"
        draft.content = _infer_message_content(query)
        preview = f"Discord message: {draft.content}" if draft.content else "Discord message text still missing"
    elif candidate_id == "webhook_send_message":
        draft.capability = "webhook_send"
        draft.content = _infer_message_content(query)
        preview = f"Webhook payload: {draft.content}" if draft.content else "Webhook payload still missing"
    elif candidate_id == "email_send_message":
        draft.capability = "email_send"
        draft.content = _infer_message_content(query)
        preview = f"Email content: {draft.content}" if draft.content else "Email content still missing"
    elif candidate_id == "imap_read_mailbox":
        draft.capability = "mail_read"
        preview = "Read latest mailbox entries"
    elif candidate_id == "imap_search_mailbox":
        draft.capability = "mail_search"
        draft.content = _infer_mail_search_query(query, clean_ref)
        preview = f"Mailbox search: {draft.content}" if draft.content else "Mailbox search query still missing"
    elif candidate_id == "mqtt_publish_message":
        draft.capability = "mqtt_publish"
        draft.path = _infer_mqtt_topic(query)
        draft.content = _infer_message_content(query)
        if draft.path and draft.content:
            preview = f"MQTT publish to {draft.path}: {draft.content}"
        elif draft.path:
            preview = f"MQTT topic: {draft.path}"
        else:
            preview = "MQTT topic still missing"
    elif candidate_id == "rss_read_feed":
        draft.capability = "feed_read"
        preview = "Read recent feed entries"
    elif candidate_id == "google_calendar_read_events":
        draft.capability = "calendar_read"
        draft.path = _infer_calendar_range(query) or "upcoming"
        draft.content = _infer_calendar_search(query)
        preview = f"Read calendar range: {draft.path}"
    elif candidate_id == "http_api_request":
        draft.capability = "api_request"
        draft.path = CapabilityRouter._extract_path(query)
        preview = f"HTTP request path: {draft.path}" if draft.path else "API path still missing"
    return draft, preview


def _plan_to_payload(plan: ActionPlan, *, preview: str = "", source: str = "heuristic") -> dict[str, Any]:
    return {
        "found": True,
        "capability": str(plan.capability or "").strip(),
        "connection_kind": str(plan.connection_kind or "").strip(),
        "connection_ref": str(plan.connection_ref or "").strip(),
        "requested_connection_ref": str(plan.requested_connection_ref or "").strip(),
        "path": str(plan.path or "").strip(),
        "content": str(plan.content or "").strip(),
        "missing_fields": list(plan.missing_fields),
        "resolution_source": str(plan.resolution_source or "").strip(),
        "notes": list(plan.notes),
        "preview": str(preview or "").strip(),
        "source": source,
    }


def build_payload_dry_run(
    query: str,
    *,
    settings: Any,
    routing_decision: dict[str, Any] | None = None,
    action_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    routing = dict(routing_decision or {})
    action = dict(action_decision or {})
    if not bool(routing.get("found")):
        return {
            "available": True,
            "used": False,
            "status": "warn",
            "visual_status": "warn",
            "message": "Payload dry-run skipped: no routing target was resolved first.",
            "payload": {},
        }
    if not bool(action.get("found")):
        return {
            "available": True,
            "used": False,
            "status": "warn",
            "visual_status": "warn",
            "message": "Payload dry-run skipped: no action or skill candidate was selected first.",
            "payload": {},
        }

    connection_kind = normalize_connection_kind(str(routing.get("kind", "") or ""))
    connection_ref = str(routing.get("ref", "") or "").strip()
    candidate_kind = str(action.get("candidate_kind", "") or "").strip().lower()
    candidate_id = str(action.get("candidate_id", "") or "").strip()

    if candidate_kind == "template":
        draft, preview = _template_draft(query, candidate_id=candidate_id, connection_kind=connection_kind, connection_ref=connection_ref)
        if candidate_id == "mqtt_publish_message" and not str(draft.path or "").strip() and connection_ref:
            connection = _connection_row(settings, connection_kind, connection_ref)
            default_topic = _read_row_value(connection, "topic") if connection is not None else ""
            if default_topic:
                draft.path = default_topic
                if str(draft.content or "").strip():
                    preview = f"MQTT publish to {default_topic}: {draft.content}"
                else:
                    preview = f"MQTT topic: {default_topic}"
        hints = MemoryHints(connection_kind=connection_kind, connection_ref=connection_ref, source="routing_dry_run")
        plan = build_action_plan(draft, hints, available_connection_refs=[connection_ref] if connection_ref else [])
        payload = _plan_to_payload(plan, preview=preview, source="template_heuristic")
        status = "ok" if not payload["missing_fields"] else "warn"
        message = "Payload dry-run built a concrete executor payload." if status == "ok" else "Payload dry-run still needs one or more parameters."
        return {
            "available": True,
            "used": True,
            "status": status,
            "visual_status": status,
            "message": message,
            "payload": payload,
        }

    if candidate_kind == "skill":
        manifest = _find_skill_manifest(candidate_id)
        capability, raw_value, preview = _skill_first_step_preview(manifest)
        payload = {
            "found": True,
            "capability": capability or "custom_skill",
            "connection_kind": connection_kind,
            "connection_ref": connection_ref,
            "requested_connection_ref": "",
            "path": raw_value if capability in {"file_read", "file_write"} else "",
            "content": raw_value if capability in {"ssh_command", "discord_send"} else "",
            "missing_fields": [],
            "resolution_source": "skill_manifest",
            "notes": [],
            "preview": preview,
            "source": "skill_manifest",
            "skill_id": candidate_id,
            "skill_name": str((manifest or {}).get("name", "") or "").strip(),
        }
        return {
            "available": True,
            "used": True,
            "status": "ok" if manifest else "warn",
            "visual_status": "ok" if manifest else "warn",
            "message": (
                "Payload dry-run resolved the selected custom skill preview."
                if manifest
                else "Payload dry-run could not load the selected custom skill manifest."
            ),
            "payload": payload,
        }

    return {
        "available": True,
        "used": False,
        "status": "warn",
        "visual_status": "warn",
        "message": "Payload dry-run skipped: unsupported action candidate type.",
        "payload": {},
    }


def _guardrail_kind_for_capability(capability: str) -> str:
    clean = str(capability or "").strip().lower()
    if clean == "ssh_command":
        return "ssh_command"
    if clean in {"file_read", "file_write", "file_list"}:
        return "file_access"
    if clean in {"api_request", "webhook_send"}:
        return "http_request"
    if clean == "mqtt_publish":
        return "mqtt_publish"
    return ""


def _guardrail_text_for_payload(payload: dict[str, Any]) -> str:
    capability = str(payload.get("capability", "") or "").strip().lower()
    if capability == "ssh_command":
        return str(payload.get("content", "") or payload.get("preview", "") or "").strip()
    if capability in {"file_read", "file_write", "file_list"}:
        return str(payload.get("path", "") or payload.get("preview", "") or "").strip()
    if capability in {"api_request", "webhook_send"}:
        return str(payload.get("path", "") or payload.get("content", "") or "").strip()
    if capability == "mqtt_publish":
        return str(payload.get("path", "") or payload.get("content", "") or "").strip()
    return ""


def _is_safe_ssh_command(command: str) -> bool:
    clean = " ".join(str(command or "").strip().split()).lower()
    return clean in {"uptime", "hostname", "date", "whoami", "df -h", "free -h"}


def _field_label(name: str, language: str) -> str:
    clean = str(name or "").strip().lower()
    labels = {
        "command": _localized_text(language, de="Befehl", en="Command"),
        "connection_ref": _localized_text(language, de="Zielprofil", en="Target profile"),
        "remote_path": _localized_text(language, de="Remote-Pfad", en="Remote path"),
        "message": _localized_text(language, de="Nachricht", en="Message"),
        "search_query": _localized_text(language, de="Suchanfrage", en="Search query"),
        "topic": _localized_text(language, de="Topic", en="Topic"),
        "path": _localized_text(language, de="Pfad", en="Path"),
        "content": _localized_text(language, de="Inhalt", en="Content"),
    }
    return labels.get(clean, clean or _localized_text(language, de="Feld", en="Field"))


def _capability_label(capability: str, language: str) -> str:
    clean = str(capability or "").strip().lower()
    labels = {
        "ssh_command": _localized_text(language, de="SSH-Befehl", en="SSH command"),
        "file_list": _localized_text(language, de="Dateien anzeigen", en="List files"),
        "file_read": _localized_text(language, de="Datei lesen", en="Read file"),
        "file_write": _localized_text(language, de="Datei schreiben", en="Write file"),
        "discord_send": _localized_text(language, de="Discord-Nachricht senden", en="Send Discord message"),
        "calendar_read": _localized_text(language, de="Kalendertermine lesen", en="Read calendar events"),
        "webhook_send": _localized_text(language, de="Webhook senden", en="Send webhook"),
        "email_send": _localized_text(language, de="E-Mail senden", en="Send email"),
        "mail_read": _localized_text(language, de="Postfach lesen", en="Read mailbox"),
        "mail_search": _localized_text(language, de="Postfach durchsuchen", en="Search mailbox"),
        "mqtt_publish": _localized_text(language, de="MQTT-Nachricht senden", en="Publish MQTT message"),
        "api_request": _localized_text(language, de="API-Anfrage", en="API request"),
        "custom_skill": _localized_text(language, de="Custom Skill", en="Custom skill"),
    }
    return labels.get(clean, clean or _localized_text(language, de="Aktion", en="Action"))


def _confirmation_action_label(action: str, language: str) -> str:
    clean = str(action or "").strip().lower()
    return {
        "allow": _localized_text(language, de="Freigeben", en="Allow"),
        "ask_user": _localized_text(language, de="Zuerst nachfragen", en="Ask first"),
        "block": _localized_text(language, de="Blockieren", en="Block"),
    }.get(clean, clean or _localized_text(language, de="Unbekannt", en="Unknown"))


def _reason_label(
    reason: str,
    *,
    language: str,
    payload: dict[str, Any] | None = None,
    guardrail_ref: str = "",
) -> str:
    clean = str(reason or "").strip()
    if not clean:
        return ""
    payload = dict(payload or {})
    missing_fields = [str(item or "").strip() for item in list(payload.get("missing_fields", []) or []) if str(item or "").strip()]
    if clean == "missing_parameters":
        labels = ", ".join(_field_label(name, language) for name in missing_fields) if missing_fields else ""
        if labels:
            return _localized_text(
                language,
                de=f"Es fehlen noch Pflichtangaben: {labels}.",
                en=f"Required fields are still missing: {labels}.",
            )
        return _localized_text(
            language,
            de="Es fehlen noch Pflichtangaben fuer diese Aktion.",
            en="Required fields are still missing for this action.",
        )
    if clean == "routing_target_confirmation":
        return _localized_text(
            language,
            de="Das Ziel ist noch nicht eindeutig bestaetigt.",
            en="The target is not clearly confirmed yet.",
        )
    if clean == "ssh_command_needs_confirmation":
        return _localized_text(
            language,
            de="Der Befehl ist kein klarer sicherer Standardfall und sollte kurz bestaetigt werden.",
            en="This command is not a clear safe default and should be confirmed first.",
        )
    if clean == "side_effect_confirmation":
        capability_label = _capability_label(str(payload.get("capability", "") or ""), language)
        return _localized_text(
            language,
            de=f"{capability_label} veraendert etwas und sollte vor der Ausfuehrung bestaetigt werden.",
            en=f"{capability_label} changes something and should be confirmed before execution.",
        )
    if clean == "outbound_message_confirmation":
        return _localized_text(
            language,
            de="Ausgehende Nachrichten sollten vor dem Senden kurz bestaetigt werden.",
            en="Outgoing messages should be confirmed briefly before sending.",
        )
    if clean == "custom_skill_confirmation":
        return _localized_text(
            language,
            de="Custom Skills sollten vor der Ausfuehrung noch bestaetigt werden.",
            en="Custom skills should be confirmed before execution.",
        )
    if clean in {"guardrail_blocked", "guardrail_denied"}:
        if guardrail_ref:
            return _localized_text(
                language,
                de=f"Das Guardrail-Profil {guardrail_ref} blockiert diese Aktion.",
                en=f"Guardrail profile {guardrail_ref} blocks this action.",
            )
        return _localized_text(
            language,
            de="Das aktive Guardrail-Profil blockiert diese Aktion.",
            en="The active guardrail profile blocks this action.",
        )
    if clean == "No extra confirmation needed.":
        return _localized_text(
            language,
            de="Keine weitere Rueckfrage noetig.",
            en="No extra confirmation needed.",
        )
    if "_" not in clean and len(clean.split()) > 1:
        return clean
    return clean


def _decision_summary(
    *,
    action: str,
    language: str,
    target: str = "",
    preview: str = "",
) -> str:
    clean_action = str(action or "").strip().lower()
    clean_target = str(target or "").strip()
    clean_preview = str(preview or "").strip()
    if clean_action == "allow":
        if clean_target and clean_preview:
            return _localized_text(
                language,
                de=f"ARIA wuerde auf {clean_target} direkt ausfuehren: {clean_preview}",
                en=f"ARIA would execute on {clean_target} directly: {clean_preview}",
            )
        return _localized_text(
            language,
            de="ARIA wuerde diese Aktion ohne weitere Rueckfrage freigeben.",
            en="ARIA would allow this action without any further confirmation.",
        )
    if clean_action == "ask_user":
        if clean_target:
            return _localized_text(
                language,
                de=f"ARIA wuerde vor der Ausfuehrung auf {clean_target} noch nachfragen.",
                en=f"ARIA would ask for confirmation before executing on {clean_target}.",
            )
        return _localized_text(
            language,
            de="ARIA wuerde vor der Ausfuehrung noch nachfragen.",
            en="ARIA would ask for confirmation before execution.",
        )
    if clean_action == "block":
        if clean_target:
            return _localized_text(
                language,
                de=f"ARIA wuerde die geplante Aktion auf {clean_target} blockieren.",
                en=f"ARIA would block the planned action on {clean_target}.",
            )
        return _localized_text(
            language,
            de="ARIA wuerde diese Aktion blockieren.",
            en="ARIA would block this action.",
        )
    return ""


def evaluate_guardrail_confirm_dry_run(
    settings: Any,
    *,
    payload_debug: dict[str, Any] | None = None,
    routing_decision: dict[str, Any] | None = None,
    language: str = "",
) -> dict[str, Any]:
    payload = dict((payload_debug or {}).get("payload", {}) or {})
    routing = dict(routing_decision or {})
    if not bool(payload.get("found")):
        return {
            "available": True,
            "used": False,
            "status": "warn",
            "visual_status": "warn",
            "message": "Guardrail / confirm dry-run skipped: no payload is available yet.",
            "decision": {},
        }

    capability = str(payload.get("capability", "") or "").strip().lower()
    connection_kind = normalize_connection_kind(str(payload.get("connection_kind", "") or ""))
    connection_ref = str(payload.get("connection_ref", "") or "").strip()
    connection = _connection_row(settings, connection_kind, connection_ref)
    connection_method = _read_row_value(connection, "method").upper() if connection is not None else ""
    guardrail_ref = _read_row_value(connection, "guardrail_ref") if connection is not None else ""
    guardrail_kind = _guardrail_kind_for_capability(capability)
    guardrail_profile = resolve_guardrail_profile(settings, guardrail_ref) if guardrail_ref and guardrail_kind else None
    guardrail_text = _guardrail_text_for_payload(payload)
    guardrail_decision = evaluate_guardrail(
        profile_ref=guardrail_ref,
        profile=guardrail_profile,
        kind=guardrail_kind,
        text=guardrail_text,
    ) if guardrail_kind else None

    action = "allow"
    reason = "No extra confirmation needed."
    if guardrail_decision and not guardrail_decision.allowed:
        action = "block"
        reason = guardrail_decision.reason or "guardrail_blocked"
    elif list(payload.get("missing_fields", []) or []):
        action = "ask_user"
        reason = "missing_parameters"
    elif bool(routing.get("routing_ask_user")):
        action = "ask_user"
        reason = "routing_target_confirmation"
    elif capability == "ssh_command" and not _is_safe_ssh_command(str(payload.get("content", "") or "")):
        action = "ask_user"
        reason = "ssh_command_needs_confirmation"
    elif capability in {"file_write", "email_send", "webhook_send", "mqtt_publish"}:
        action = "ask_user"
        reason = "side_effect_confirmation"
    elif capability == "api_request":
        has_request_body = bool(str(payload.get("content", "") or "").strip())
        if connection_method not in {"GET", "HEAD"} or has_request_body:
            action = "ask_user"
            reason = "side_effect_confirmation"
    elif capability == "discord_send":
        action = "ask_user"
        reason = "outbound_message_confirmation"
    elif capability == "custom_skill":
        action = "ask_user"
        reason = "custom_skill_confirmation"

    status = "ok" if action == "allow" else ("warn" if action == "ask_user" else "error")
    target = f"{routing.get('kind', '')}/{routing.get('ref', '')}".strip("/")
    reason_label = _reason_label(reason, language=language, payload=payload, guardrail_ref=guardrail_ref)
    return {
        "available": True,
        "used": True,
        "status": status,
        "visual_status": status,
        "message": {
            "allow": _localized_text(language, de="Guardrail / Confirm-Dry-run wuerde die Ausfuehrung freigeben.", en="Guardrail / confirm dry-run would allow execution."),
            "ask_user": _localized_text(language, de="Guardrail / Confirm-Dry-run wuerde vor der Ausfuehrung nachfragen.", en="Guardrail / confirm dry-run would ask before execution."),
            "block": _localized_text(language, de="Guardrail / Confirm-Dry-run wuerde die Ausfuehrung blockieren.", en="Guardrail / confirm dry-run would block execution."),
        }[action],
        "decision": {
            "action": action,
            "action_label": _confirmation_action_label(action, language),
            "reason": reason,
            "reason_label": reason_label,
            "summary": _decision_summary(action=action, language=language, target=target),
            "guardrail_ref": guardrail_ref,
            "guardrail_kind": guardrail_kind,
            "guardrail_applied": bool(guardrail_ref and guardrail_kind),
            "guardrail_text": guardrail_text,
        },
    }


def build_execution_preview_dry_run(
    *,
    routing_decision: dict[str, Any] | None = None,
    action_decision: dict[str, Any] | None = None,
    payload_debug: dict[str, Any] | None = None,
    safety_debug: dict[str, Any] | None = None,
    language: str = "",
) -> dict[str, Any]:
    routing = dict(routing_decision or {})
    action = dict(action_decision or {})
    payload = dict((payload_debug or {}).get("payload", {}) or {})
    safety = dict((safety_debug or {}).get("decision", {}) or {})
    if not bool(routing.get("found")) or not bool(action.get("found")) or not bool(payload.get("found")):
        return {
            "available": True,
            "used": False,
            "status": "warn",
            "visual_status": "warn",
            "message": "Final execution preview is not complete yet.",
            "decision": {},
        }

    next_step = str(safety.get("action", "") or "ask_user").strip().lower() or "ask_user"
    status = "ok" if next_step == "allow" else ("warn" if next_step == "ask_user" else "error")
    preview_text = str(payload.get("preview", "") or "").strip()
    target = f"{routing.get('kind', '')}/{routing.get('ref', '')}".strip("/")
    reason = str(safety.get("reason", "") or "").strip()
    reason_label = _reason_label(reason, language=language, payload=payload, guardrail_ref=str(safety.get("guardrail_ref", "") or "").strip())
    message = {
        "allow": _localized_text(language, de="Wuerde mit dem aktuellen Dry-run-Plan ausfuehren.", en="Would execute with the current dry-run plan."),
        "ask_user": _localized_text(language, de="Wuerde vor der Ausfuehrung dieses Plans noch nachfragen.", en="Would ask the user before executing this plan."),
        "block": _localized_text(language, de="Wuerde den aktuellen Dry-run-Plan blockieren.", en="Would block execution with the current dry-run plan."),
    }[next_step]
    return {
        "available": True,
        "used": True,
        "status": status,
        "visual_status": status,
        "message": message,
        "decision": {
            "target": target,
            "candidate_kind": str(action.get("candidate_kind", "") or "").strip(),
            "candidate_id": str(action.get("candidate_id", "") or "").strip(),
            "capability": str(payload.get("capability", "") or "").strip(),
            "next_step": next_step,
            "next_step_label": _confirmation_action_label(next_step, language),
            "preview": preview_text,
            "reason": reason,
            "reason_label": reason_label,
            "summary": _decision_summary(action=next_step, language=language, target=target, preview=preview_text),
        },
    }
