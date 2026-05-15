from __future__ import annotations

import json
import re
from typing import Any, Callable

from aria.core.agentic_action_resolution import action_draft_from_message_operation
from aria.core.agentic_action_resolution import agentic_action_contract_prompt
from aria.core.agentic_action_resolution import agentic_debug_line
from aria.core.connection_action_contract import connection_action_capability_for_executor_family
from aria.core.connection_action_contract import runtime_operation_for_capability


MESSAGE_CONNECTION_KINDS = ("discord", "webhook", "email", "mqtt")
MESSAGE_CAPABILITY_BY_KIND = {
    kind: capability
    for kind in MESSAGE_CONNECTION_KINDS
    if (capability := connection_action_capability_for_executor_family(kind, "message"))
}


def message_capability_for_kind(connection_kind: str) -> str:
    return MESSAGE_CAPABILITY_BY_KIND.get(str(connection_kind or "").strip().lower(), "")


def message_draft_is_complete(*, capability: str, topic: str = "", content: str = "") -> bool:
    clean_capability = str(capability or "").strip().lower()
    clean_content = str(content or "").strip()
    clean_topic = str(topic or "").strip()
    if runtime_operation_for_capability(clean_capability) == "publish":
        return bool(clean_topic and clean_content)
    if clean_capability in set(MESSAGE_CAPABILITY_BY_KIND.values()):
        return bool(clean_content)
    return True


def message_has_inline_content(message: str) -> bool:
    clean = str(message or "").strip()
    return bool(re.search(r'["\'`]\s*[^"\'`]+?\s*["\'`]', clean))


async def resolve_message_operation_from_dossier(
    *,
    client: Any | None,
    message: str,
    connection_kind: str,
    connection_ref: str,
    capability: str,
    existing_topic: str = "",
    existing_content: str = "",
    user_id: str = "",
    language: str | None = None,
    build_message_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    clean_kind = str(connection_kind or "").strip().lower()
    clean_ref = str(connection_ref or "").strip()
    clean_capability = str(capability or "").strip().lower() or message_capability_for_kind(clean_kind)
    if client is None or clean_kind not in MESSAGE_CAPABILITY_BY_KIND or not clean_ref or not clean_capability:
        return {}
    dossier = build_message_target_dossier(clean_kind, clean_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("outbound_message")
                    + " "
                    "You resolve one bounded outbound message draft for ARIA. "
                    "Use the target dossier and the user request to fill missing message content and, for MQTT, topic. "
                    "Keep content concise and faithful to the user request. "
                    "Return JSON only with this shape: "
                    '{"topic":"<topic or empty>","content":"<message content or empty>",'
                    '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Capability: {clean_capability}\n"
                    f"Existing topic: {str(existing_topic or '').strip()}\n"
                    f"Existing content: {str(existing_content or '').strip()}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="message_operation_decision",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    return {
        "topic": str(payload.get("topic", "") or "").strip(),
        "content": str(payload.get("content", "") or "").strip(),
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "dossier": dossier,
    }


async def apply_agentic_message_operation_resolution(
    *,
    client: Any | None,
    message: str,
    user_id: str = "",
    routing_decision: dict[str, Any] | None = None,
    action_debug: dict[str, Any] | None = None,
    capability_draft: Any | None = None,
    language: str | None = None,
    build_message_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    routing_debug_enabled: Callable[[], bool],
    with_capability_draft_updates: Callable[..., Any],
) -> tuple[dict[str, Any], Any | None, str]:
    action_payload = dict(action_debug or {})
    decision = dict(action_payload.get("decision", {}) or {})
    routing = dict(routing_decision or {})
    connection_kind = str(routing.get("kind", "") or "").strip().lower()
    if connection_kind not in MESSAGE_CAPABILITY_BY_KIND:
        return action_payload, capability_draft, ""
    connection_ref = str(routing.get("ref", "") or "").strip()
    if not connection_ref or str(decision.get("candidate_kind", "") or "").strip().lower() != "template":
        return action_payload, capability_draft, ""

    capability = str(getattr(capability_draft, "capability", "") or decision.get("capability", "") or "").strip()
    capability = capability or message_capability_for_kind(connection_kind)
    if capability not in set(MESSAGE_CAPABILITY_BY_KIND.values()):
        return action_payload, capability_draft, ""
    decision_inputs = dict(decision.get("inputs", {}) or {})
    existing_topic = str(
        getattr(capability_draft, "path", "")
        or decision.get("path", "")
        or decision_inputs.get("topic", "")
        or ""
    ).strip()
    existing_content = str(
        getattr(capability_draft, "content", "")
        or decision.get("content", "")
        or decision_inputs.get("message", "")
        or ""
    ).strip()
    dossier = build_message_target_dossier(connection_kind, connection_ref, user_id=user_id)
    if runtime_operation_for_capability(capability) == "publish" and not existing_topic:
        existing_topic = str(dossier.get("default_topic", "") or "").strip()
    if message_draft_is_complete(capability=capability, topic=existing_topic, content=existing_content):
        return action_payload, capability_draft, ""
    if not existing_content and message_has_inline_content(message):
        return action_payload, capability_draft, ""

    resolved = await resolve_message_operation_from_dossier(
        client=client,
        message=str(message or "").strip(),
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        capability=capability,
        existing_topic=existing_topic,
        existing_content=existing_content,
        user_id=user_id,
        language=language,
        build_message_target_dossier=build_message_target_dossier,
        extract_json_object=extract_json_object,
    )
    if not resolved:
        return action_payload, capability_draft, ""

    topic = str(resolved.get("topic", "") or existing_topic).strip()
    content = str(resolved.get("content", "") or existing_content).strip()
    draft = action_draft_from_message_operation(
        capability=capability,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        topic=topic,
        content=content,
        source="llm_decision",
        confidence=str(resolved.get("confidence", "") or "").strip(),
        reason=str(resolved.get("reason", "") or "").strip(),
        ask_user=bool(resolved.get("ask_user", False)),
    )

    if capability_draft is not None:
        capability_draft = with_capability_draft_updates(
            capability_draft,
            capability=capability,
            connection_kind=connection_kind,
            explicit_connection_ref=connection_ref,
            path=topic,
            content=content,
            notes=[
                *list(getattr(capability_draft, "notes", []) or []),
                "message_operation_decided_by_llm",
            ],
        )
    decision["capability"] = capability
    decision["inputs"] = {"message": content} if content else {}
    if runtime_operation_for_capability(capability) == "publish" and topic:
        decision["inputs"] = {**dict(decision.get("inputs", {}) or {}), "topic": topic}
    decision["input_items"] = [
        {"key": key, "key_label": key.replace("_", " ").title(), "value": value}
        for key, value in dict(decision.get("inputs", {}) or {}).items()
        if str(value).strip()
    ]
    decision["missing_input"] = "" if message_draft_is_complete(capability=capability, topic=topic, content=content) else "message"
    decision["missing_input_label"] = "" if not decision["missing_input"] else "Message"
    if bool(resolved.get("ask_user")):
        decision["ask_user"] = True
        decision["execution_state"] = "needs_confirmation"
    if str(resolved.get("reason", "") or "").strip():
        decision["reason"] = str(resolved.get("reason", "") or "").strip()
    action_payload["decision"] = decision

    debug_line = ""
    if routing_debug_enabled():
        debug_line = agentic_debug_line(
            "message_operation_decision",
            connection_ref=connection_ref,
            fields={
                "kind": connection_kind,
                "capability": capability,
                "topic": topic or "-",
                "confidence": str(resolved.get("confidence", "") or "").strip() or "-",
                "reason": str(resolved.get("reason", "") or "").strip() or "-",
            },
            draft=draft,
        )
    return action_payload, capability_draft, debug_line
