"""Pending action payload, confirmation, and debug contracts."""

from __future__ import annotations

from typing import Any

from aria.modules.action_planner_templates.candidate_details import capability_label
from aria.modules.action_planner_templates.taxonomy import is_recipe_candidate_kind
from aria.modules.recipe_runtime.contracts import build_recipe_intent
from aria.modules.platform_primitives.text_utils import localized_text


def resolve_pending_missing_input(action: dict[str, Any], payload: dict[str, Any]) -> str:
    explicit = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
    if explicit == "connection_ref" and payload_connection_refs(payload):
        explicit = ""
    if explicit:
        return explicit
    missing_fields = payload_missing_fields(payload)
    if not missing_fields:
        return ""
    primary = missing_fields[0]
    capability = str(payload.get("capability", "") or "").strip().lower()
    if primary == "content":
        mapping = {
            "discord_send": "message",
            "webhook_send": "message",
            "email_send": "message",
            "mail_search": "search_query",
            "mqtt_publish": "message",
            "ssh_command": "command",
        }
        return mapping.get(capability, "content")
    if primary == "path":
        return "topic" if capability == "mqtt_publish" else "remote_path"
    return primary


def payload_connection_refs(payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in list(payload.get("connection_refs", []) or []):
        clean = str(item or "").strip()
        if clean and clean not in refs:
            refs.append(clean)
    return refs


def payload_field_is_satisfied(payload: dict[str, Any], field: str) -> bool:
    clean_field = str(field or "").strip()
    if not clean_field:
        return False
    if clean_field == "connection_ref":
        return bool(str(payload.get("connection_ref", "") or "").strip() or payload_connection_refs(payload))
    if clean_field in {"content", "command", "message", "search_query"}:
        return bool(str(payload.get("content", "") or payload.get(clean_field, "") or "").strip())
    if clean_field in {"path", "remote_path", "topic"}:
        return bool(str(payload.get("path", "") or payload.get(clean_field, "") or "").strip())
    return bool(str(payload.get(clean_field, "") or "").strip())


def prune_satisfied_payload_missing_fields(payload: dict[str, Any]) -> list[str]:
    return [
        str(item or "").strip()
        for item in list(payload.get("missing_fields", []) or [])
        if str(item or "").strip() and not payload_field_is_satisfied(payload, str(item or "").strip())
    ]


def payload_missing_fields(payload: dict[str, Any]) -> list[str]:
    connection_refs = payload_connection_refs(payload)
    return [
        str(item or "").strip()
        for item in list(payload.get("missing_fields", []) or [])
        if str(item or "").strip() and not (str(item or "").strip() == "connection_ref" and connection_refs)
    ]


def action_contract_missing_fields(
    *,
    routing: dict[str, Any],
    action: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    missing: list[str] = []

    def add(name: str) -> None:
        clean = str(name or "").strip()
        if clean and clean not in missing:
            missing.append(clean)

    connection_refs = payload_connection_refs(payload)
    for field in payload_missing_fields(payload):
        add(field)
    explicit = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
    if explicit and not payload_field_is_satisfied(payload, explicit):
        add(explicit)
    if not bool(payload.get("found")):
        add("payload")
    capability = str(payload.get("capability", "") or action.get("capability", "") or "").strip().lower()
    if not capability:
        add("capability")
    connection_kind = str(payload.get("connection_kind", "") or routing.get("kind", "") or "").strip().lower()
    connection_ref = str(payload.get("connection_ref", "") or routing.get("ref", "") or "").strip()
    if connection_kind and not connection_ref and not connection_refs:
        add("connection_ref")
    content = str(payload.get("content", "") or "").strip()
    path = str(payload.get("path", "") or "").strip()
    if capability == "ssh_command" and not content:
        add("command")
    elif capability in {"discord_send", "webhook_send", "email_send", "mqtt_publish"} and not content:
        add("message")
    elif capability == "mail_search" and not content:
        add("search_query")
    elif capability in {"file_read", "file_write"} and not path:
        add("remote_path")
    return missing


def resolved_next_step(*, safety: dict[str, Any], execution: dict[str, Any]) -> str:
    return str(execution.get("next_step", "") or safety.get("action", "") or "ask_user").strip().lower() or "ask_user"


def build_pending_action_state(
    *,
    query: str,
    candidate_kind: str,
    candidate_id: str,
    resolved: dict[str, Any],
    action: dict[str, Any],
    payload: dict[str, Any],
    safety: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    return {
        "query": query,
        "candidate_kind": candidate_kind,
        "candidate_id": candidate_id,
        "routing_decision": dict(resolved.get("decision", {}) or {}),
        "action_decision": action,
        "payload": payload,
        "safety_decision": safety,
        "execution_decision": execution,
    }


def pending_payload_intents(payload: dict[str, Any]) -> list[str]:
    capability = str(dict(payload or {}).get("capability", "") or "").strip()
    return [f"capability:{capability}"] if capability else ["chat"]


def routed_action_intents(action: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    candidate_kind = str(action.get("candidate_kind", "") or "").strip().lower()
    candidate_id = str(action.get("candidate_id", "") or "").strip()
    if is_recipe_candidate_kind(candidate_kind) and candidate_id:
        return [build_recipe_intent(candidate_id)]
    payload_intents = pending_payload_intents(payload)
    if payload_intents != ["chat"]:
        return payload_intents
    capability = str(action.get("capability", "") or "").strip()
    return [f"capability:{capability}"] if capability else payload_intents


def routing_reason_text(
    resolved: dict[str, Any],
    *,
    language: str | None = None,
) -> str:
    execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
    safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
    action = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
    payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
    summary = str(execution.get("summary", "") or "").strip()
    if summary:
        return summary
    reason = str(safety.get("reason_label", "") or action.get("reason", "") or "").strip()
    if reason:
        return reason
    preview = str(payload.get("preview", "") or "").strip()
    if preview:
        return preview
    return localized_text(
        language,
        de="ARIA hat eine konkrete Aktion vorbereitet.",
        en="ARIA prepared a concrete action.",
    )


def _routed_action_payload_summary(payload: dict[str, Any], *, language: str | None = None) -> str:
    capability = str(payload.get("capability", "") or "").strip()
    kind = str(payload.get("connection_kind", "") or "").strip()
    ref = str(payload.get("connection_ref", "") or "").strip()
    path = str(payload.get("path", "") or payload.get("selector", "") or "").strip()
    content = str(payload.get("content", "") or payload.get("query", "") or payload.get("message", "") or "").strip()
    refs = payload_connection_refs(payload)
    if ref:
        target = "/".join(part for part in (kind, ref) if part)
    elif refs:
        target = f"{kind}/" + ", ".join(refs) if kind else ", ".join(refs)
    else:
        target = kind
    if capability == "feed_read":
        label = "RSS lesen" if str(language or "de").lower().startswith("de") else "Read RSS feed"
    elif capability:
        label = capability_label(capability, language or "de")
    else:
        label = "Aktion" if str(language or "de").lower().startswith("de") else "Action"
    details: list[str] = []
    if target:
        details.append(target)
    if path:
        details.append(path)
    if content:
        details.append(content)
    if not details:
        return ""
    return localized_text(
        language,
        de=f"Geplante Aktion: {label}: {'; '.join(details)}",
        en=f"Planned action: {label}: {'; '.join(details)}",
    )


def build_routed_confirmation_text(
    resolved: dict[str, Any],
    *,
    language: str | None = None,
) -> str:
    execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
    safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
    payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
    lines: list[str] = []
    summary = str(execution.get("summary", "") or "").strip()
    policy_reason = str(safety.get("reason", "") or "").strip()
    reason = (
        ""
        if policy_reason == "turn_contract_action_preflight"
        else str(safety.get("reason_label", "") or "").strip()
    )
    preview = str(payload.get("preview", "") or "").strip()
    payload_summary = _routed_action_payload_summary(payload, language=language)
    if payload_summary:
        lines.append(payload_summary)
    elif summary:
        lines.append(summary)
    elif reason:
        lines.append(reason)
    else:
        lines.append(
            localized_text(
                language,
                de="ARIA moechte diese Aktion vor der Ausfuehrung noch bestaetigen.",
                en="ARIA wants to confirm this action before execution.",
            )
        )
    if reason and reason not in lines:
        lines.append(reason)
    if preview and not payload_summary:
        lines.append(
            localized_text(
                language,
                de=f"Geplante Aktion: {preview}",
                en=f"Planned action: {preview}",
            )
        )
    confirmed_refs = payload_connection_refs(payload)
    visible_text = "\n".join(lines)
    target_details_missing = bool(confirmed_refs) and any(ref not in visible_text for ref in confirmed_refs)
    if payload_summary and payload_summary not in lines and (not preview or target_details_missing):
        lines.append(payload_summary)
    return "\n\n".join(line for line in lines if line)


def build_routed_missing_input_text(
    resolved: dict[str, Any],
    *,
    language: str | None = None,
) -> str:
    action = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
    question = str((resolved.get("action_debug") or {}).get("clarifying_question", "") or action.get("clarifying_question", "") or "").strip()
    example_prompt = str((resolved.get("action_debug") or {}).get("example_prompt", "") or action.get("example_prompt", "") or "").strip()
    reason = str((resolved.get("safety_debug") or {}).get("decision", {}).get("reason_label", "") or action.get("reason", "") or "").strip()
    lines: list[str] = []
    if question:
        lines.append(question)
    elif reason:
        lines.append(reason)
    else:
        lines.append(
            localized_text(
                language,
                de="Bevor ARIA etwas ausfuehrt, fehlt noch eine Pflichtangabe.",
                en="Before ARIA can execute anything, one required field is still missing.",
            )
        )
    if example_prompt:
        lines.append(
            localized_text(
                language,
                de=f"Beispiel: {example_prompt}",
                en=f"Example: {example_prompt}",
            )
        )
    return "\n\n".join(line for line in lines if line)


def resolved_routing_detail_lines(
    resolved: dict[str, Any],
    *,
    routing_debug_enabled: bool,
) -> list[str]:
    lines = [
        str(item or "").strip()
        for item in list(resolved.get("detail_lines", []) or [])
        if str(item or "").strip()
    ]
    decision = dict(resolved.get("decision", {}) or {})
    if routing_debug_enabled and str(decision.get("source", "") or "").strip() == "qdrant_routing":
        kind = str(decision.get("kind", "") or "").strip()
        ref = str(decision.get("ref", "") or "").strip()
        score = float(decision.get("score", 0.0) or 0.0)
        line = f"Routing: Qdrant selected `{kind}/{ref}` score={score:.3f} source=qdrant_routing."
        if line not in lines:
            lines.append(line)
    return lines


def append_debug_detail_lines(
    resolved: dict[str, Any],
    *lines: str,
    routing_debug_enabled: bool,
) -> dict[str, Any]:
    additions = [
        str(item or "").strip()
        for item in lines
        if routing_debug_enabled and str(item or "").strip()
    ]
    if not additions:
        return resolved
    existing = [
        str(item or "").strip()
        for item in list(resolved.get("detail_lines", []) or [])
        if str(item or "").strip()
    ]
    for line in additions:
        if line not in existing:
            existing.append(line)
    resolved["detail_lines"] = existing
    return resolved
