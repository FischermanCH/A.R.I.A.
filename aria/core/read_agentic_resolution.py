from __future__ import annotations

import json
from typing import Any, Callable

from aria.core.agentic_action_resolution import action_draft_from_read_operation
from aria.core.agentic_action_resolution import agentic_action_contract_prompt
from aria.core.agentic_action_resolution import agentic_debug_line
from aria.core.connection_action_contract import connection_action_capabilities_by_family


READ_CAPABILITIES = set(connection_action_capabilities_by_family("read"))


def read_draft_is_complete(*, capability: str, selector: str = "", query: str = "") -> bool:
    clean = str(capability or "").strip().lower()
    clean_selector = str(selector or "").strip()
    clean_query = str(query or "").strip()
    if clean == "mail_search":
        return bool(clean_query)
    if clean == "calendar_read":
        return bool(clean_selector)
    return clean in READ_CAPABILITIES


async def resolve_read_operation_from_dossier(
    *,
    client: Any | None,
    message: str,
    connection_kind: str,
    connection_ref: str,
    capability: str,
    existing_selector: str = "",
    existing_query: str = "",
    user_id: str = "",
    language: str | None = None,
    build_read_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    clean_kind = str(connection_kind or "").strip().lower()
    clean_ref = str(connection_ref or "").strip()
    clean_capability = str(capability or "").strip().lower()
    if client is None or clean_capability not in READ_CAPABILITIES:
        return {}
    if clean_kind != "website" and not clean_ref:
        return {}
    dossier = build_read_target_dossier(clean_kind, clean_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("read_operation")
                    + " "
                    "You resolve one bounded read-only action draft for ARIA. "
                    "Use the target dossier and user request to fill missing selector or query fields only. "
                    "Do not propose write/send actions for read-only capabilities. "
                    "For calendar, selector should be one of today, tomorrow, day_after_tomorrow, this_week, next_week, next, upcoming. "
                    "For mail_search, query should be the search term. For website_list, selector may be a group name. "
                    "Return JSON only with this shape: "
                    '{"selector":"<range/group/selector or empty>","query":"<search/filter or empty>",'
                    '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Capability: {clean_capability}\n"
                    f"Existing selector: {str(existing_selector or '').strip()}\n"
                    f"Existing query: {str(existing_query or '').strip()}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="read_operation_decision",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    return {
        "selector": str(payload.get("selector", "") or "").strip(),
        "query": str(payload.get("query", "") or "").strip(),
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "dossier": dossier,
    }


async def apply_agentic_read_operation_resolution(
    *,
    client: Any | None,
    message: str,
    user_id: str = "",
    routing_decision: dict[str, Any] | None = None,
    action_debug: dict[str, Any] | None = None,
    capability_draft: Any | None = None,
    language: str | None = None,
    build_read_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    routing_debug_enabled: Callable[[], bool],
    with_capability_draft_updates: Callable[..., Any],
) -> tuple[dict[str, Any], Any | None, str]:
    action_payload = dict(action_debug or {})
    decision = dict(action_payload.get("decision", {}) or {})
    routing = dict(routing_decision or {})
    capability = str(getattr(capability_draft, "capability", "") or decision.get("capability", "") or "").strip()
    if capability not in READ_CAPABILITIES:
        return action_payload, capability_draft, ""
    connection_kind = str(routing.get("kind", "") or getattr(capability_draft, "connection_kind", "") or "").strip().lower()
    connection_ref = str(routing.get("ref", "") or getattr(capability_draft, "explicit_connection_ref", "") or "").strip()
    if str(decision.get("candidate_kind", "") or "").strip().lower() != "template":
        return action_payload, capability_draft, ""

    existing_selector = str(getattr(capability_draft, "path", "") or decision.get("path", "") or "").strip()
    existing_query = str(getattr(capability_draft, "content", "") or decision.get("content", "") or "").strip()
    if read_draft_is_complete(capability=capability, selector=existing_selector, query=existing_query):
        return action_payload, capability_draft, ""

    resolved = await resolve_read_operation_from_dossier(
        client=client,
        message=str(message or "").strip(),
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        capability=capability,
        existing_selector=existing_selector,
        existing_query=existing_query,
        user_id=user_id,
        language=language,
        build_read_target_dossier=build_read_target_dossier,
        extract_json_object=extract_json_object,
    )
    if not resolved:
        return action_payload, capability_draft, ""

    selector = str(resolved.get("selector", "") or existing_selector).strip()
    query = str(resolved.get("query", "") or existing_query).strip()
    draft = action_draft_from_read_operation(
        capability=capability,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        selector=selector,
        query=query,
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
            path=selector,
            content=query,
            notes=[
                *list(getattr(capability_draft, "notes", []) or []),
                "read_operation_decided_by_llm",
            ],
        )
    decision["capability"] = capability
    decision["inputs"] = {key: value for key, value in {"selector": selector, "query": query}.items() if value}
    decision["input_items"] = [
        {"key": key, "key_label": key.title(), "value": value}
        for key, value in dict(decision.get("inputs", {}) or {}).items()
    ]
    if bool(resolved.get("ask_user")):
        decision["ask_user"] = True
        decision["execution_state"] = "needs_confirmation"
    if str(resolved.get("reason", "") or "").strip():
        decision["reason"] = str(resolved.get("reason", "") or "").strip()
    action_payload["decision"] = decision

    debug_line = ""
    if routing_debug_enabled():
        debug_line = agentic_debug_line(
            "read_operation_decision",
            connection_ref=connection_ref,
            fields={
                "kind": connection_kind,
                "capability": capability,
                "selector": selector or "-",
                "query": query or "-",
                "confidence": str(resolved.get("confidence", "") or "").strip() or "-",
                "reason": str(resolved.get("reason", "") or "").strip() or "-",
            },
            draft=draft,
        )
    return action_payload, capability_draft, debug_line
