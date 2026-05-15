from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from aria.core.agentic_action_resolution import (
    action_draft_from_ssh_command,
    agentic_action_contract_prompt,
    agentic_debug_line,
    ssh_policy_result_from_decision,
)
from aria.core.i18n import I18NStore
from aria.core.ssh_guardrail_commands import dossier_ssh_allow_commands
from aria.core.ssh_policy import validate_ssh_readonly_policy


_SSH_AGENTIC_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _ssh_agentic_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _SSH_AGENTIC_I18N.t(language or "de", f"ssh_agentic_resolution.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _ssh_agentic_terms(language: str | None, key: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    localized = _ssh_agentic_text(language, key, "")
    terms = [item.strip().lower() for item in localized.split(",") if item.strip()]
    return tuple(dict.fromkeys([*terms, *defaults]))


_HEALTHCHECK_REQUEST_TERMS = (
    "health",
    "healthcheck",
    "health check",
    "server health",
    "status",
    "zustand",
    "wie geht",
    "geht es",
    "how is",
    "how's",
    "check",
    "diagnose",
) + _ssh_agentic_terms("de", "healthcheck_terms", ())

_COMPREHENSIVE_HEALTHCHECK_REQUEST_TERMS = (
    "health",
    "healthcheck",
    "health check",
    "server health",
    "diagnose",
    "diagnostik",
    "wie geht",
    "geht es",
    "how is",
    "how's",
)

_MUTATING_REQUEST_TERMS = (
    "delete",
    "remove",
    "rm ",
    "restart",
    "reboot",
    "stop",
    "start",
) + _ssh_agentic_terms("de", "mutating_request_terms", ())

_GENERIC_STATUS_COMMANDS = {
    "uptime",
    "uptime -p",
}


def _guardrail_healthcheck_commands(dossier: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for item in list(dossier.get("guardrail_allow_terms", []) or []):
        command = str(item or "").strip()
        if not command or command in commands:
            continue
        policy = validate_ssh_readonly_policy(command)
        if policy.action == "allow":
            commands.append(command)
    return commands


def _looks_like_healthcheck_request(message: str, reason: str = "") -> bool:
    text = f"{message} {reason}".strip().lower()
    return any(term in text for term in _HEALTHCHECK_REQUEST_TERMS)


def _looks_like_comprehensive_healthcheck_request(message: str, reason: str = "") -> bool:
    text = f"{message} {reason}".strip().lower()
    return any(term in text for term in _COMPREHENSIVE_HEALTHCHECK_REQUEST_TERMS)


def _looks_like_mutating_request(message: str) -> bool:
    text = f" {str(message or '').strip().lower()} "
    return any(term in text for term in _MUTATING_REQUEST_TERMS)


def _is_generic_status_command(command: str) -> bool:
    return str(command or "").strip().lower() in _GENERIC_STATUS_COMMANDS


def _message_mentions_command(message: str, command: str) -> bool:
    clean_command = str(command or "").strip().lower()
    if not clean_command:
        return False
    clean_message = str(message or "").strip().lower()
    return clean_command in clean_message


def _message_explicitly_requests_existing_command(message: str, command: str) -> bool:
    return _is_generic_status_command(command) and _message_mentions_command(message, command)


def _should_reconsider_existing_command_with_llm(message: str, command: str) -> bool:
    return _is_generic_status_command(command) and not _message_mentions_command(message, command)


def _guardrail_healthcheck_fallback(
    *,
    message: str,
    reason: str,
    dossier: dict[str, Any],
    guardrail_intent: str = "",
) -> tuple[str, list[str]]:
    if _looks_like_mutating_request(message):
        return "", []
    clean_intent = str(guardrail_intent or "").strip().lower()
    if clean_intent not in {"health_check", "status_check"} and not _looks_like_healthcheck_request(message, reason):
        return "", []
    commands = _guardrail_healthcheck_commands(dossier)
    if not commands:
        return "", []
    return " && ".join(commands), commands


async def classify_ssh_guardrail_intent(
    *,
    client: Any | None,
    message: str,
    connection_ref: str,
    command: str = "",
    user_id: str = "",
    language: str | None = None,
    dossier: dict[str, Any] | None = None,
    build_ssh_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
) -> dict[str, str]:
    if client is None or not str(connection_ref or "").strip():
        return {}
    clean_dossier = dict(dossier or build_ssh_target_dossier(connection_ref, user_id=user_id) or {})
    if not _guardrail_healthcheck_commands(clean_dossier):
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    "You classify whether an SSH request should use an existing guardrail recipe. "
                    "The target is already selected and execution is still controlled by policy; "
                    "do not invent commands. "
                    "Return JSON only with this shape: "
                    '{"intent":"health_check|status_check|other","confidence":"high|medium|low","reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Current draft command: {str(command or '').strip()}\n"
                    f"Target dossier: {json.dumps(clean_dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="ssh_guardrail_intent",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    intent = str(payload.get("intent", "") or "").strip().lower() if payload else ""
    if intent not in {"health_check", "status_check", "other"}:
        intent = "other"
    return {
        "intent": intent,
        "confidence": str(payload.get("confidence", "") or "").strip().lower() if payload else "",
        "reason": str(payload.get("reason", "") or "").strip() if payload else "",
    }


def ssh_command_review_issues(command: str) -> list[str]:
    clean = str(command or "").strip()
    if not clean:
        return []
    lower = clean.lower()
    issues: list[str] = []
    if len(clean) > 160:
        issues.append("command_too_long")
    logical_ops = lower.count("&&") + lower.count("||")
    if logical_ops >= 4:
        issues.append("chain_too_complex")
    single_pipes = [segment.strip() for segment in lower.split("|") if segment.strip()]
    if "|" in lower and "||" not in lower and len(single_pipes) >= 4:
        issues.append("pipeline_too_complex")
    if lower.count("systemctl is-active") >= 2:
        issues.append("guessed_service_fallback_chain")
    if "ps aux" in lower and "grep -i" in lower:
        issues.append("process_grep_probe")
    if "docker ps" in lower and "systemctl is-active" in lower:
        issues.append("mixed_service_probe_modes")
    deduped: list[str] = []
    for issue in issues:
        if issue not in deduped:
            deduped.append(issue)
    return deduped


async def resolve_ssh_command_from_dossier(
    *,
    client: Any | None,
    message: str,
    connection_ref: str,
    user_id: str = "",
    language: str | None = None,
    build_ssh_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    normalize_spaces: Callable[[str], str],
) -> dict[str, Any]:
    if client is None or not str(connection_ref or "").strip():
        return {}
    dossier = build_ssh_target_dossier(connection_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("ssh_command")
                    + " "
                    "You decide one concrete SSH command for ARIA. "
                    "Use the target dossier and the user request to identify the concrete intended command. "
                    "If the user asks for a destructive or state-changing operation, still identify the intended "
                    "command instead of replacing it with a safe probe; policy will block or require confirmation. "
                    "Prefer the simplest command that answers the request. "
                    "Prefer a single command. Use a short read-only shell expression only when it materially improves the result. "
                    "Avoid service-specific fallback chains, process-grep probes, and shell redirections unless they are clearly necessary. "
                    "Prefer portable or broadly available inspection commands before distro-specific assumptions. "
                    "Respect allow_commands if they are present. "
                    "If guardrail_allow_terms are present and the request is a health or status check, choose those commands instead of inventing service-specific probes. "
                    "Return JSON only with this shape: "
                    '{"command":"<command or empty>","confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="ssh_command_decision",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    command = normalize_spaces(str(payload.get("command", "") or ""))
    return {
        "command": command,
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "dossier": dossier,
    }


async def resolve_ssh_mutating_command_from_dossier(
    *,
    client: Any | None,
    message: str,
    connection_ref: str,
    user_id: str = "",
    language: str | None = None,
    build_ssh_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    normalize_spaces: Callable[[str], str],
    rejected_command: str = "",
) -> dict[str, Any]:
    if client is None or not str(connection_ref or "").strip():
        return {}
    dossier = build_ssh_target_dossier(connection_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("ssh_mutating_command")
                    + " "
                    "You identify the concrete SSH command implied by a state-changing user request. "
                    "Do not replace the requested state-changing operation with a harmless status probe. "
                    "Return JSON only with this shape: "
                    '{"command":"<intended command or empty>","confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Rejected safe substitute: {str(rejected_command or '').strip() or '-'}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="ssh_command_mutating_intent",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    command = normalize_spaces(str(payload.get("command", "") or ""))
    return {
        "command": command,
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "dossier": dossier,
    }


async def review_ssh_command_candidate(
    *,
    client: Any | None,
    message: str,
    connection_ref: str,
    command: str,
    issues: list[str],
    user_id: str = "",
    language: str | None = None,
    build_ssh_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    normalize_spaces: Callable[[str], str],
) -> dict[str, Any]:
    if client is None or not str(connection_ref or "").strip() or not str(command or "").strip() or not issues:
        return {}
    dossier = build_ssh_target_dossier(connection_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("ssh_command_review")
                    + " "
                    "You review one SSH command for ARIA. "
                    "Keep the action read-only and safe. "
                    "If the proposed command is too complex, guessed, or awkward, simplify it while preserving the user's goal. "
                    "Prefer shorter, more portable inspection commands. "
                    "Avoid long fallback chains and avoid mixing multiple service-probe styles unless necessary. "
                    "Return JSON only with this shape: "
                    '{"command":"<command or empty>","confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Current command: {str(command or '').strip()}\n"
                    f"Review issues: {json.dumps(list(issues), ensure_ascii=False)}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="ssh_command_review",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    reviewed_command = normalize_spaces(str(payload.get("command", "") or ""))
    return {
        "command": reviewed_command,
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "issues": list(issues),
    }


async def apply_agentic_ssh_command_resolution(
    *,
    client: Any | None,
    message: str,
    user_id: str = "",
    routing_decision: dict[str, Any] | None = None,
    action_debug: dict[str, Any] | None = None,
    capability_draft: Any | None = None,
    language: str | None = None,
    build_ssh_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    normalize_spaces: Callable[[str], str],
    routing_debug_enabled: Callable[[], bool],
    msg: Callable[[str | None, str, str], str],
    with_capability_draft_updates: Callable[..., Any],
) -> tuple[dict[str, Any], Any | None, str]:
    action_payload = dict(action_debug or {})
    decision = dict(action_payload.get("decision", {}) or {})
    routing = dict(routing_decision or {})
    if str(routing.get("kind", "") or "").strip().lower() != "ssh":
        return action_payload, capability_draft, ""
    if str(decision.get("candidate_kind", "") or "").strip().lower() != "template":
        return action_payload, capability_draft, ""
    if str(decision.get("candidate_id", "") or "").strip() != "ssh_run_command":
        return action_payload, capability_draft, ""

    connection_ref = str(routing.get("ref", "") or "").strip()
    if not connection_ref:
        decision["ask_user"] = True
        decision["execution_state"] = "needs_input"
        decision["execution_state_label"] = msg(language, "Braucht Eingabe", "Needs input")
        decision["missing_input"] = "connection_ref"
        decision["missing_input_label"] = msg(language, "SSH-Profil", "SSH profile")
        decision["clarifying_question"] = msg(
            language,
            _ssh_agentic_text(language, "ask_ssh_profile", "Which SSH profile should ARIA use for this request?"),
            "Which SSH profile should ARIA use for this request?",
        )
        action_payload["decision"] = decision
        if capability_draft is not None:
            capability_draft = with_capability_draft_updates(
                capability_draft,
                plan_class="command_single",
                behavior_profile="ssh_run_command",
            )
        return action_payload, capability_draft, ""

    existing_command = normalize_spaces(str(getattr(capability_draft, "content", "") or decision.get("content", "") or ""))
    if existing_command and _is_generic_status_command(existing_command) and _looks_like_mutating_request(message):
        existing_command = ""
    pre_resolved: dict[str, Any] = {}
    if existing_command and _should_reconsider_existing_command_with_llm(message, existing_command):
        pre_resolved = await resolve_ssh_command_from_dossier(
            client=client,
            message=str(message or "").strip(),
            connection_ref=connection_ref,
            user_id=user_id,
            language=language,
            build_ssh_target_dossier=build_ssh_target_dossier,
            extract_json_object=extract_json_object,
            normalize_spaces=normalize_spaces,
        )
        if normalize_spaces(str(pre_resolved.get("command", "") or "")):
            existing_command = ""
    if existing_command:
        command = existing_command
        explicit_existing_command = _message_explicitly_requests_existing_command(str(message or "").strip(), command)
        dossier = build_ssh_target_dossier(connection_ref, user_id=user_id)
        allow_commands = dossier_ssh_allow_commands(dossier)
        policy = validate_ssh_readonly_policy(command, allow_commands=allow_commands)
        agentic_draft = action_draft_from_ssh_command(
            connection_ref=connection_ref,
            command=command,
            source="existing_draft",
            reason=str(decision.get("reason", "") or ""),
        )
        agentic_policy = ssh_policy_result_from_decision(policy)
        fallback_command, fallback_commands = _guardrail_healthcheck_fallback(
            message=str(message or "").strip(),
            reason=str(decision.get("reason", "") or ""),
            dossier=dossier,
        )
        guardrail_intent = {}
        if (
            not fallback_command
            and allow_commands
            and policy.action != "allow"
            and not _looks_like_mutating_request(str(message or "").strip())
        ):
            guardrail_intent = await classify_ssh_guardrail_intent(
                client=client,
                message=str(message or "").strip(),
                connection_ref=connection_ref,
                command=command,
                user_id=user_id,
                language=language,
                dossier=dossier,
                build_ssh_target_dossier=build_ssh_target_dossier,
                extract_json_object=extract_json_object,
            )
            fallback_command, fallback_commands = _guardrail_healthcheck_fallback(
                message=str(message or "").strip(),
                reason=str(decision.get("reason", "") or ""),
                dossier=dossier,
                guardrail_intent=str(guardrail_intent.get("intent", "") or ""),
            )
        should_use_guardrail_bundle = (
            bool(fallback_command)
            and not explicit_existing_command
            and policy.reason in {"ssh_command_not_in_allow_list", "ssh_command_unknown_readonly", "ssh_command_needs_confirmation"}
            and policy.action != "allow"
        ) or (
            bool(fallback_command)
            and not explicit_existing_command
            and (
                str(guardrail_intent.get("intent", "") or "") in {"health_check", "status_check"}
                or _looks_like_comprehensive_healthcheck_request(str(message or "").strip(), str(decision.get("reason", "") or ""))
            )
            and command != fallback_command
        )
        if should_use_guardrail_bundle:
            fallback_policy = validate_ssh_readonly_policy(fallback_command, allow_commands=allow_commands or fallback_commands)
            if fallback_policy.action == "allow":
                decision["guardrail_fallback_from"] = command
                decision["reason"] = "guardrail_allowed_healthcheck"
                command = fallback_command
                policy = fallback_policy
                agentic_draft = action_draft_from_ssh_command(
                    connection_ref=connection_ref,
                    command=command,
                    source="guardrail_fallback",
                    reason="guardrail_allowed_healthcheck",
                )
                agentic_policy = ssh_policy_result_from_decision(policy)
        preview = f"SSH command: {command}"
        decision["preview"] = preview
        decision["inputs"] = {"command": command}
        decision["input_items"] = [{"key": "command", "key_label": "Command", "value": command}]
        decision["missing_input"] = ""
        decision["missing_input_label"] = ""
        action_payload["decision"] = decision
        if capability_draft is not None:
            capability_draft = with_capability_draft_updates(
                capability_draft,
                content=command,
                plan_class="command_single",
                behavior_profile="ssh_run_command",
            )
        debug_line = ""
        if routing_debug_enabled() and policy.action != "allow":
            policy_line = agentic_debug_line(
                "ssh_command_policy",
                connection_ref=connection_ref,
                fields={"action": policy.action, "reason": policy.reason, "command": command},
                draft=agentic_draft,
                policy=agentic_policy,
            )
            debug_line = f"{debug_line}\n{policy_line}".strip() if debug_line else policy_line
        if routing_debug_enabled() and guardrail_intent:
            intent_line = (
                "Routing Debug: ssh_guardrail_intent "
                f"ref={connection_ref} intent={guardrail_intent.get('intent', '-') or '-'} "
                f"confidence={guardrail_intent.get('confidence', '-') or '-'} reason={guardrail_intent.get('reason', '-') or '-'}"
            )
            debug_line = f"{debug_line}\n{intent_line}".strip() if debug_line else intent_line
        if routing_debug_enabled() and decision.get("guardrail_fallback_from"):
            fallback_line = (
                "Routing Debug: ssh_command_guardrail_fallback "
                f"ref={connection_ref} from={decision.get('guardrail_fallback_from')} command={command}"
            )
            debug_line = f"{debug_line}\n{fallback_line}".strip() if debug_line else fallback_line
        return action_payload, capability_draft, debug_line

    resolved = pre_resolved or await resolve_ssh_command_from_dossier(
        client=client,
        message=str(message or "").strip(),
        connection_ref=connection_ref,
        user_id=user_id,
        language=language,
        build_ssh_target_dossier=build_ssh_target_dossier,
        extract_json_object=extract_json_object,
        normalize_spaces=normalize_spaces,
    )
    command = normalize_spaces(str(resolved.get("command", "") or ""))
    confidence = str(resolved.get("confidence", "") or "").strip().lower()
    reason = str(resolved.get("reason", "") or "").strip()
    if command and _looks_like_mutating_request(message) and _is_generic_status_command(command):
        mutating_resolved = await resolve_ssh_mutating_command_from_dossier(
            client=client,
            message=str(message or "").strip(),
            connection_ref=connection_ref,
            user_id=user_id,
            language=language,
            build_ssh_target_dossier=build_ssh_target_dossier,
            extract_json_object=extract_json_object,
            normalize_spaces=normalize_spaces,
            rejected_command=command,
        )
        mutating_command = normalize_spaces(str(mutating_resolved.get("command", "") or ""))
        if mutating_command and not _is_generic_status_command(mutating_command):
            resolved = mutating_resolved
            command = mutating_command
            confidence = str(resolved.get("confidence", "") or confidence).strip().lower()
            reason = str(resolved.get("reason", "") or reason).strip()
        else:
            command = ""
            reason = reason or "mutating_request_needs_specific_command"
    review_issues = ssh_command_review_issues(command)
    agentic_draft = action_draft_from_ssh_command(
        connection_ref=connection_ref,
        command=command,
        source="llm_decision",
        confidence=confidence,
        reason=reason,
        ask_user=bool(resolved.get("ask_user")),
        review_issues=review_issues,
    )
    review_debug_line = ""
    dossier = dict(resolved.get("dossier", {}) or {})
    if command and review_issues:
        reviewed = await review_ssh_command_candidate(
            client=client,
            message=str(message or "").strip(),
            connection_ref=connection_ref,
            command=command,
            issues=review_issues,
            user_id=user_id,
            language=language,
            build_ssh_target_dossier=build_ssh_target_dossier,
            extract_json_object=extract_json_object,
            normalize_spaces=normalize_spaces,
        )
        reviewed_command = normalize_spaces(str(reviewed.get("command", "") or ""))
        if reviewed_command:
            command = reviewed_command
            confidence = str(reviewed.get("confidence", "") or confidence).strip().lower()
            reason = str(reviewed.get("reason", "") or reason).strip()
            agentic_draft = action_draft_from_ssh_command(
                connection_ref=connection_ref,
                command=command,
                source="llm_review",
                confidence=confidence,
                reason=reason,
                ask_user=bool(reviewed.get("ask_user", False)),
                review_issues=review_issues,
            )
        if routing_debug_enabled():
            review_debug_line = agentic_debug_line(
                "ssh_command_review",
                connection_ref=connection_ref,
                fields={
                    "issues": ",".join(review_issues),
                    "command": command or "-",
                    "confidence": confidence or "-",
                    "reason": reason or "-",
                },
                draft=agentic_draft,
            )
    if not command:
        decision["ask_user"] = True
        decision["execution_state"] = "needs_input"
        decision["execution_state_label"] = msg(language, "Braucht Eingabe", "Needs input")
        decision["missing_input"] = "command"
        decision["missing_input_label"] = "Command"
        if reason:
            decision["reason"] = reason
        decision["clarifying_question"] = msg(
            language,
            _ssh_agentic_text(language, "ask_ssh_command", "Which SSH command should ARIA run on this target?"),
            "Which SSH command should ARIA run on this target?",
        )
        action_payload["decision"] = decision
        return action_payload, capability_draft, ""

    allow_commands = dossier_ssh_allow_commands(dossier)
    policy = validate_ssh_readonly_policy(command, allow_commands=allow_commands)
    agentic_policy = ssh_policy_result_from_decision(policy)
    explicit_resolved_command = _message_explicitly_requests_existing_command(str(message or "").strip(), command)
    fallback_command, fallback_commands = _guardrail_healthcheck_fallback(
        message=str(message or "").strip(),
        reason=reason,
        dossier=dossier,
    )
    guardrail_intent = {}
    if (
        not fallback_command
        and allow_commands
        and policy.action != "allow"
        and not _looks_like_mutating_request(str(message or "").strip())
    ):
        guardrail_intent = await classify_ssh_guardrail_intent(
            client=client,
            message=str(message or "").strip(),
            connection_ref=connection_ref,
            command=command,
            user_id=user_id,
            language=language,
            dossier=dossier,
            build_ssh_target_dossier=build_ssh_target_dossier,
            extract_json_object=extract_json_object,
        )
        fallback_command, fallback_commands = _guardrail_healthcheck_fallback(
            message=str(message or "").strip(),
            reason=reason,
            dossier=dossier,
            guardrail_intent=str(guardrail_intent.get("intent", "") or ""),
        )
    fallback_reasons = {"ssh_command_unknown_readonly", "ssh_command_not_in_allow_list", "ssh_command_needs_confirmation"}
    should_use_guardrail_bundle = (
        bool(fallback_command)
        and not explicit_resolved_command
        and policy.reason in fallback_reasons
        and policy.action != "allow"
    ) or (
        bool(fallback_command)
        and not explicit_resolved_command
        and (
            str(guardrail_intent.get("intent", "") or "") in {"health_check", "status_check"}
            or _looks_like_comprehensive_healthcheck_request(str(message or "").strip(), reason)
        )
        and command != fallback_command
    )
    if should_use_guardrail_bundle:
        fallback_policy = validate_ssh_readonly_policy(fallback_command, allow_commands=allow_commands or fallback_commands)
        if fallback_policy.action == "allow":
            original_command = command
            command = fallback_command
            policy = fallback_policy
            agentic_policy = ssh_policy_result_from_decision(policy)
            confidence = confidence or "high"
            reason = "guardrail_allowed_healthcheck"
            decision["guardrail_fallback_from"] = original_command
            agentic_draft = action_draft_from_ssh_command(
                connection_ref=connection_ref,
                command=command,
                source="guardrail_fallback",
                confidence=confidence,
                reason=reason,
                review_issues=review_issues,
            )
    if policy.action == "block":
        decision["preview"] = f"SSH command: {command}"
        decision["inputs"] = {"command": command}
        decision["input_items"] = [{"key": "command", "key_label": "Command", "value": command}]
        decision["ask_user"] = False
        decision["execution_state"] = "blocked"
        decision["execution_state_label"] = msg(language, "Blockiert", "Blocked")
        decision["reason"] = policy.reason
        action_payload["decision"] = decision
        if capability_draft is not None:
            capability_draft = with_capability_draft_updates(
                capability_draft,
                content=command,
                plan_class="command_single",
                behavior_profile="ssh_run_command",
            )
        debug_line = ""
        if routing_debug_enabled():
            debug_line = agentic_debug_line(
                "ssh_command_policy",
                connection_ref=connection_ref,
                fields={"action": "block", "reason": policy.reason, "command": command},
                draft=agentic_draft,
                policy=agentic_policy,
            )
        return action_payload, capability_draft, debug_line

    preview = f"SSH command: {command}"
    decision["preview"] = preview
    decision["inputs"] = {"command": command}
    decision["input_items"] = [{"key": "command", "key_label": "Command", "value": command}]
    decision["missing_input"] = ""
    decision["missing_input_label"] = ""
    decision["clarifying_question"] = ""
    decision["example_prompt"] = ""
    decision["reason"] = reason or str(decision.get("reason", "") or "").strip()
    if confidence:
        decision["confidence"] = confidence
        decision["confidence_label"] = confidence.capitalize()
    if bool(resolved.get("ask_user")):
        decision["ask_user"] = True
        decision["execution_state"] = "needs_confirmation"
        decision["execution_state_label"] = msg(
            language,
            _ssh_agentic_text(language, "needs_confirmation", "Needs confirmation"),
            "Needs confirmation",
        )
    elif policy.action == "ask_user":
        decision["ask_user"] = True
        decision["execution_state"] = "needs_confirmation"
        decision["execution_state_label"] = msg(
            language,
            _ssh_agentic_text(language, "needs_confirmation", "Needs confirmation"),
            "Needs confirmation",
        )
        decision["reason"] = policy.reason
    action_payload["decision"] = decision
    if capability_draft is not None:
        capability_draft = with_capability_draft_updates(
            capability_draft,
            content=command,
            plan_class="command_single",
            behavior_profile="ssh_run_command",
            notes=[
                *list(getattr(capability_draft, "notes", []) or []),
                "ssh_command_decided_by_llm",
                *([] if not bool(decision.get("guardrail_fallback_from")) else ["ssh_command_guardrail_healthcheck_fallback"]),
            ],
        )
    debug_line = ""
    if routing_debug_enabled():
        debug_line = agentic_debug_line(
            "ssh_command_decision",
            connection_ref=connection_ref,
            fields={"command": command, "confidence": confidence or "-", "reason": reason or "-"},
            draft=agentic_draft,
            policy=agentic_policy,
        )
        if review_debug_line:
            debug_line = f"{debug_line}\n{review_debug_line}"
        if guardrail_intent:
            debug_line = (
                f"{debug_line}\nRouting Debug: ssh_guardrail_intent "
                f"ref={connection_ref} intent={guardrail_intent.get('intent', '-') or '-'} "
                f"confidence={guardrail_intent.get('confidence', '-') or '-'} reason={guardrail_intent.get('reason', '-') or '-'}"
            )
        if decision.get("guardrail_fallback_from"):
            debug_line = (
                f"{debug_line}\nRouting Debug: ssh_command_guardrail_fallback "
                f"ref={connection_ref} from={decision.get('guardrail_fallback_from')} command={command}"
            )
        if policy.action != "allow":
            debug_line = (
                f"{debug_line}\n"
                + agentic_debug_line(
                    "ssh_command_policy",
                    connection_ref=connection_ref,
                    fields={"action": policy.action, "reason": policy.reason, "command": command},
                    draft=agentic_draft,
                    policy=agentic_policy,
                )
            )
    return action_payload, capability_draft, debug_line
