from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_action_contract import guardrail_kind_for_capability
from aria.core.agentic_action_resolution import action_draft_from_file_operation
from aria.core.agentic_action_resolution import action_draft_from_http_request
from aria.core.agentic_action_resolution import action_draft_from_message_operation
from aria.core.agentic_action_resolution import action_draft_from_read_operation
from aria.core.agentic_action_resolution import action_draft_from_ssh_command
from aria.core.agentic_action_resolution import agentic_debug_line
from aria.core.agentic_action_resolution import guardrail_policy_result_from_decision
from aria.core.agentic_action_resolution import http_policy_result_from_decision
from aria.core.agentic_action_resolution import message_policy_result
from aria.core.agentic_action_resolution import read_policy_result
from aria.core.agentic_action_resolution import ssh_policy_result_from_decision
from aria.core.execution_dry_run_payloads import build_payload_dry_run
from aria.core.execution_dry_run_payloads import connection_row
from aria.core.execution_dry_run_payloads import read_row_list
from aria.core.execution_dry_run_payloads import read_row_value
from aria.core.execution_dry_run_text import confirmation_action_label
from aria.core.execution_dry_run_text import decision_summary
from aria.core.execution_dry_run_text import reason_label
from aria.core.guardrails import evaluate_guardrail, resolve_guardrail_profile
from aria.core.http_api_policy import validate_http_api_request_policy
from aria.core.i18n import I18NStore
from aria.core.recipe_runtime_contract import RECIPE_CONFIRMATION_REASON
from aria.core.recipe_runtime_contract import RECIPE_EXECUTION_CAPABILITY
from aria.core.recipe_runtime_contract import is_recipe_execution_capability
from aria.core.ssh_guardrail_commands import combined_ssh_allow_commands
from aria.core.ssh_guardrail_commands import ssh_guardrail_allow_terms
from aria.core.ssh_policy import validate_ssh_readonly_policy


_EXECUTION_DRY_RUN_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _execution_dry_run_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    lang = "de" if str(language or "").strip().lower().startswith("de") else "en"
    template = _EXECUTION_DRY_RUN_I18N.t(lang, f"execution_dry_run.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template



def _join_guardrail_text(*parts: object) -> str:
    return " ".join(str(part or "").strip() for part in parts if str(part or "").strip())


def _file_guardrail_aliases(capability: str) -> str:
    if capability == "file_list":
        return "file_list file access list read readonly directory"
    if capability == "file_read":
        return "file_read file access read get download readonly"
    if capability == "file_write":
        return "file_write file access write create upload put delete"
    return "file access"


def _guardrail_text_for_payload(payload: dict[str, Any]) -> str:
    capability = str(payload.get("capability", "") or "").strip().lower()
    if capability == "ssh_command":
        return str(payload.get("content", "") or payload.get("preview", "") or "").strip()
    if capability in {"file_read", "file_write", "file_list"}:
        return _join_guardrail_text(
            _file_guardrail_aliases(capability),
            payload.get("path"),
            payload.get("content"),
            payload.get("preview"),
        )
    if capability == "api_request":
        return _join_guardrail_text(
            "api_request http_request status health get head",
            payload.get("path"),
            payload.get("content"),
            payload.get("preview"),
        )
    if capability == "webhook_send":
        return _join_guardrail_text(
            "webhook_send webhook http_request post status notification benachrichtigung",
            payload.get("path"),
            payload.get("content"),
            payload.get("preview"),
        )
    if capability == "mqtt_publish":
        return str(payload.get("path", "") or payload.get("content", "") or "").strip()
    return ""


def _file_agentic_dry_run_debug(
    *,
    capability: str,
    connection_kind: str,
    connection_ref: str,
    payload: dict[str, Any],
    guardrail_decision: Any | None,
) -> str:
    if capability not in {"file_list", "file_read", "file_write"}:
        return ""
    operation = "list" if capability == "file_list" else "write" if capability == "file_write" else "read"
    path = str(payload.get("path", "") or "").strip()
    content = str(payload.get("content", "") or "").strip()
    draft = action_draft_from_file_operation(
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        operation=operation,
        path=path,
        content=content,
        source=str(payload.get("source", "") or "payload_dry_run"),
    )
    policy = guardrail_policy_result_from_decision(
        guardrail_decision,
        fallback_path=path,
        fallback_content=content,
        policy_name="file_access",
    )
    return agentic_debug_line(
        "file_operation_policy",
        connection_ref=connection_ref,
        fields={"kind": connection_kind, "operation": operation, "path": path or "-"},
        draft=draft,
        policy=policy,
    )


def _ssh_agentic_dry_run_debug(
    *,
    capability: str,
    connection_ref: str,
    payload: dict[str, Any],
    policy_decision: Any | None,
) -> str:
    if capability != "ssh_command" or policy_decision is None:
        return ""
    command = str(payload.get("content", "") or "").strip()
    draft = action_draft_from_ssh_command(
        connection_ref=connection_ref,
        command=command,
        source=str(payload.get("source", "") or "payload_dry_run"),
    )
    return agentic_debug_line(
        "ssh_command_policy",
        connection_ref=connection_ref,
        fields={"action": getattr(policy_decision, "action", ""), "reason": getattr(policy_decision, "reason", ""), "command": command or "-"},
        draft=draft,
        policy=ssh_policy_result_from_decision(policy_decision),
    )


def _http_agentic_dry_run_debug(
    *,
    capability: str,
    connection_ref: str,
    payload: dict[str, Any],
    method: str,
    policy_decision: Any | None,
) -> str:
    if capability != "api_request" or policy_decision is None:
        return ""
    path = str(payload.get("path", "") or "").strip()
    content = str(payload.get("content", "") or "").strip()
    draft = action_draft_from_http_request(
        connection_ref=connection_ref,
        method=method or "GET",
        path=path,
        content=content,
        source=str(payload.get("source", "") or "payload_dry_run"),
    )
    return agentic_debug_line(
        "http_api_policy",
        connection_ref=connection_ref,
        fields={"method": method or "GET", "path": path or "-", "action": getattr(policy_decision, "action", "")},
        draft=draft,
        policy=http_policy_result_from_decision(policy_decision, fallback_path=path),
    )


def _message_agentic_dry_run_debug(
    *,
    capability: str,
    connection_kind: str,
    connection_ref: str,
    payload: dict[str, Any],
    action: str,
    reason: str,
) -> str:
    if capability not in {"discord_send", "webhook_send", "email_send", "mqtt_publish"}:
        return ""
    topic = str(payload.get("path", "") or "").strip()
    content = str(payload.get("content", "") or "").strip()
    draft = action_draft_from_message_operation(
        capability=capability,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        topic=topic,
        content=content,
        source=str(payload.get("source", "") or "payload_dry_run"),
    )
    policy = message_policy_result(action=action, reason=reason, topic=topic, content=content)
    return agentic_debug_line(
        "message_operation_policy",
        connection_ref=connection_ref,
        fields={"kind": connection_kind, "capability": capability, "topic": topic or "-"},
        draft=draft,
        policy=policy,
    )


def _read_agentic_dry_run_debug(
    *,
    capability: str,
    connection_kind: str,
    connection_ref: str,
    payload: dict[str, Any],
) -> str:
    if capability not in {"feed_read", "calendar_read", "mail_read", "mail_search", "website_read", "website_list"}:
        return ""
    selector = str(payload.get("path", "") or "").strip()
    query = str(payload.get("content", "") or "").strip()
    draft = action_draft_from_read_operation(
        capability=capability,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        selector=selector,
        query=query,
        source=str(payload.get("source", "") or "payload_dry_run"),
    )
    policy = read_policy_result(selector=selector, query=query)
    return agentic_debug_line(
        "read_operation_policy",
        connection_ref=connection_ref,
        fields={
            "kind": connection_kind,
            "capability": capability,
            "selector": selector or "-",
            "query": query or "-",
        },
        draft=draft,
        policy=policy,
    )


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
    connection = connection_row(settings, connection_kind, connection_ref)
    connection_method = read_row_value(connection, "method").upper() if connection is not None else ""
    guardrail_ref = read_row_value(connection, "guardrail_ref") if connection is not None else ""
    guardrail_kind = guardrail_kind_for_capability(capability)
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
    ssh_policy = None
    http_policy = None
    if guardrail_decision and not guardrail_decision.allowed:
        action = "block"
        reason = guardrail_decision.reason or "guardrail_blocked"
    elif list(payload.get("missing_fields", []) or []):
        action = "ask_user"
        reason = "missing_parameters"
    elif bool(routing.get("routing_ask_user")):
        action = "ask_user"
        reason = "routing_target_confirmation"
    elif capability == "ssh_command":
        ssh_allow_commands = read_row_list(connection, "allow_commands") if connection is not None else []
        ssh_allow_commands = combined_ssh_allow_commands(ssh_allow_commands, ssh_guardrail_allow_terms(guardrail_profile))
        ssh_policy = validate_ssh_readonly_policy(
            str(payload.get("content", "") or ""),
            allow_commands=ssh_allow_commands,
        )
        if ssh_policy.action == "block":
            action = "block"
            reason = ssh_policy.reason
        elif ssh_policy.action == "ask_user":
            action = "ask_user"
            reason = ssh_policy.reason
        else:
            reason = ssh_policy.reason
    elif capability in {"file_write", "email_send", "webhook_send", "mqtt_publish"}:
        action = "ask_user"
        reason = "side_effect_confirmation"
    elif capability == "api_request":
        http_policy = validate_http_api_request_policy(
            str(payload.get("path", "") or ""),
            content=str(payload.get("content", "") or ""),
            method=connection_method or "GET",
            health_path=read_row_value(connection, "health_path") if connection is not None else "/",
            status_like=bool("api_status_like" in {str(item or "").strip().lower() for item in list(payload.get("notes", []) or [])}),
        )
        if http_policy.action == "block":
            action = "block"
            reason = http_policy.reason
        elif http_policy.action == "ask_user":
            action = "ask_user"
            reason = http_policy.reason
        else:
            reason = http_policy.reason
    elif capability == "discord_send":
        action = "ask_user"
        reason = "outbound_message_confirmation"
    elif is_recipe_execution_capability(capability):
        action = "ask_user"
        reason = RECIPE_CONFIRMATION_REASON

    status = "ok" if action == "allow" else ("warn" if action == "ask_user" else "error")
    target_kind = str(routing.get("kind", "") or payload.get("connection_kind", "") or "").strip()
    target_ref = str(routing.get("ref", "") or payload.get("connection_ref", "") or "").strip()
    target = f"{target_kind}/{target_ref}".strip("/")
    reason_text = reason_label(reason, language=language, payload=payload, guardrail_ref=guardrail_ref)
    return {
        "available": True,
        "used": True,
        "status": status,
        "visual_status": status,
        "message": {
            "allow": _execution_dry_run_text(language, "message_148", 'Guardrail / confirm dry-run would allow execution.'),
            "ask_user": _execution_dry_run_text(language, "message_149", 'Guardrail / confirm dry-run would ask before execution.'),
            "block": _execution_dry_run_text(language, "message_150", 'Guardrail / confirm dry-run would block execution.'),
        }[action],
        "decision": {
            "action": action,
            "action_label": confirmation_action_label(action, language),
            "reason": reason,
            "reason_label": reason_text,
            "summary": decision_summary(
                action=action,
                language=language,
                target=target,
                preview=str(payload.get("preview", "") or "").strip(),
                guardrail_ref=guardrail_ref,
            ),
            "guardrail_ref": guardrail_ref,
            "guardrail_kind": guardrail_kind,
            "guardrail_applied": bool(guardrail_ref and guardrail_kind),
            "guardrail_text": guardrail_text,
            "agentic_debug": _ssh_agentic_dry_run_debug(
                capability=capability,
                connection_ref=connection_ref,
                payload=payload,
                policy_decision=ssh_policy,
            ) or _http_agentic_dry_run_debug(
                capability=capability,
                connection_ref=connection_ref,
                payload=payload,
                method=connection_method or "GET",
                policy_decision=http_policy,
            ) or _file_agentic_dry_run_debug(
                capability=capability,
                connection_kind=connection_kind,
                connection_ref=connection_ref,
                payload=payload,
                guardrail_decision=guardrail_decision,
            ) or _message_agentic_dry_run_debug(
                capability=capability,
                connection_kind=connection_kind,
                connection_ref=connection_ref,
                payload=payload,
                action=action,
                reason=reason,
            ) or _read_agentic_dry_run_debug(
                capability=capability,
                connection_kind=connection_kind,
                connection_ref=connection_ref,
                payload=payload,
            ),
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
    reason_text = reason_label(reason, language=language, payload=payload, guardrail_ref=str(safety.get("guardrail_ref", "") or "").strip())
    plan_class = str(payload.get("plan_class", "") or action.get("plan_class", "") or "").strip()
    behavior_profile = str(payload.get("behavior_profile", "") or action.get("behavior_profile", "") or "").strip()
    candidate_id = str(action.get("candidate_id", "") or "").strip()
    message = {
        "allow": _execution_dry_run_text(language, "message_203", 'Would execute with the current dry-run plan.'),
        "ask_user": _execution_dry_run_text(language, "message_204", 'Would ask the user before executing this plan.'),
        "block": _execution_dry_run_text(language, "message_205", 'Would block execution with the current dry-run plan.'),
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
            "candidate_id": candidate_id,
            "plan_class": plan_class,
            "behavior_profile": behavior_profile,
            "capability": str(payload.get("capability", "") or "").strip(),
            "next_step": next_step,
            "next_step_label": confirmation_action_label(next_step, language),
            "preview": preview_text,
            "reason": reason,
            "reason_label": reason_text,
            "summary": decision_summary(action=next_step, language=language, target=target, preview=preview_text),
        },
    }
