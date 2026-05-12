from __future__ import annotations

from typing import Any

from aria.core.action_candidate_taxonomy import is_recipe_candidate_kind
from aria.core.recipe_runtime_contract import build_recipe_intent
from aria.core.text_utils import localized_text


def resolve_pending_missing_input(action: dict[str, Any], payload: dict[str, Any]) -> str:
    explicit = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
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


def payload_missing_fields(payload: dict[str, Any]) -> list[str]:
    return [
        str(item or "").strip()
        for item in list(payload.get("missing_fields", []) or [])
        if str(item or "").strip()
    ]


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
    return pending_payload_intents(payload)


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
    reason = str(safety.get("reason_label", "") or "").strip()
    preview = str(payload.get("preview", "") or "").strip()
    if summary:
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
    if preview:
        lines.append(
            localized_text(
                language,
                de=f"Geplante Aktion: {preview}",
                en=f"Planned action: {preview}",
            )
        )
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
