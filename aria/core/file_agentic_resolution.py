from __future__ import annotations

import json
from typing import Any, Callable

from aria.core.agentic_action_resolution import action_draft_from_file_operation
from aria.core.agentic_action_resolution import agentic_action_contract_prompt
from aria.core.agentic_action_resolution import agentic_debug_line
from aria.core.behavior_families import file_operation_mode


def file_operation_from_capability(capability: str) -> str:
    clean = str(capability or "").strip().lower()
    if clean == "file_list":
        return "list"
    if clean == "file_write":
        return "write"
    if clean == "file_read":
        return "read"
    return ""


def file_operation_from_action(action_decision: dict[str, Any], capability: str = "") -> str:
    operation = file_operation_from_capability(capability)
    if operation:
        return operation
    operation = file_operation_mode(
        behavior_profile=str(action_decision.get("behavior_profile", "") or ""),
        plan_class=str(action_decision.get("plan_class", "") or ""),
    )
    if operation:
        return operation
    candidate_id = str(action_decision.get("candidate_id", "") or "").strip().lower()
    if "_list_" in candidate_id or candidate_id.endswith("_list_files"):
        return "list"
    if "_write_" in candidate_id or candidate_id.endswith("_write_file"):
        return "write"
    if "_read_" in candidate_id or candidate_id.endswith("_read_file"):
        return "read"
    return ""


def file_capability_for_operation(operation: str) -> str:
    clean = str(operation or "").strip().lower()
    if clean == "list":
        return "file_list"
    if clean == "write":
        return "file_write"
    return "file_read"


async def resolve_file_operation_from_dossier(
    *,
    client: Any | None,
    message: str,
    connection_kind: str,
    connection_ref: str,
    operation_hint: str,
    existing_path: str = "",
    existing_content: str = "",
    user_id: str = "",
    language: str | None = None,
    build_file_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    clean_kind = str(connection_kind or "").strip().lower()
    clean_ref = str(connection_ref or "").strip()
    clean_operation = str(operation_hint or "").strip().lower()
    if client is None or clean_kind not in {"sftp", "smb"} or not clean_ref or clean_operation not in {"list", "read", "write"}:
        return {}
    dossier = build_file_target_dossier(clean_kind, clean_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("file_operation")
                    + " "
                    "You resolve one bounded file operation for ARIA. "
                    "Use the target dossier, the requested operation hint, and the user request to choose a path and optional content. "
                    "Prefer paths within root_path when it is present. "
                    "For list/read, leave content empty. For write, include content only if the user clearly provided it. "
                    "Return JSON only with this shape: "
                    '{"operation":"list|read|write","path":"<path or empty>","content":"<content or empty>",'
                    '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Operation hint: {clean_operation}\n"
                    f"Existing path: {str(existing_path or '').strip()}\n"
                    f"Existing content: {str(existing_content or '').strip()}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="file_operation_decision",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    operation = str(payload.get("operation", "") or "").strip().lower()
    if operation not in {"list", "read", "write"}:
        operation = clean_operation
    return {
        "operation": operation,
        "path": str(payload.get("path", "") or "").strip(),
        "content": str(payload.get("content", "") or "").strip(),
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "dossier": dossier,
    }


async def apply_agentic_file_operation_resolution(
    *,
    client: Any | None,
    message: str,
    user_id: str = "",
    routing_decision: dict[str, Any] | None = None,
    action_debug: dict[str, Any] | None = None,
    capability_draft: Any | None = None,
    language: str | None = None,
    build_file_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    routing_debug_enabled: Callable[[], bool],
    with_capability_draft_updates: Callable[..., Any],
) -> tuple[dict[str, Any], Any | None, str]:
    action_payload = dict(action_debug or {})
    decision = dict(action_payload.get("decision", {}) or {})
    routing = dict(routing_decision or {})
    connection_kind = str(routing.get("kind", "") or "").strip().lower()
    if connection_kind not in {"sftp", "smb"}:
        return action_payload, capability_draft, ""
    connection_ref = str(routing.get("ref", "") or "").strip()
    if not connection_ref:
        return action_payload, capability_draft, ""
    if str(decision.get("candidate_kind", "") or "").strip().lower() != "template":
        return action_payload, capability_draft, ""

    current_capability = str(getattr(capability_draft, "capability", "") or decision.get("capability", "") or "").strip()
    operation_hint = file_operation_from_action(decision, current_capability)
    if operation_hint not in {"list", "read", "write"}:
        return action_payload, capability_draft, ""

    existing_path = str(getattr(capability_draft, "path", "") or decision.get("path", "") or "").strip()
    existing_content = str(getattr(capability_draft, "content", "") or decision.get("content", "") or "").strip()
    if operation_hint == "list":
        path = existing_path or "."
        decision["capability"] = "file_list"
        decision["inputs"] = {"remote_path": path}
        decision["input_items"] = [{"key": "remote_path", "key_label": "Remote path", "value": path}]
        decision["missing_input"] = ""
        decision["missing_input_label"] = ""
        action_payload["decision"] = decision
        if capability_draft is not None and not existing_path:
            capability_draft = with_capability_draft_updates(
                capability_draft,
                capability="file_list",
                connection_kind=connection_kind,
                explicit_connection_ref=connection_ref,
                path=path,
                plan_class="file_list_basic",
                behavior_profile="remote_list_files",
            )
        return action_payload, capability_draft, ""
    if operation_hint == "read" and existing_path:
        return action_payload, capability_draft, ""
    if operation_hint == "write" and existing_path and existing_content:
        return action_payload, capability_draft, ""
    resolved = await resolve_file_operation_from_dossier(
        client=client,
        message=str(message or "").strip(),
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        operation_hint=operation_hint,
        existing_path=existing_path,
        existing_content=existing_content,
        user_id=user_id,
        language=language,
        build_file_target_dossier=build_file_target_dossier,
        extract_json_object=extract_json_object,
    )
    if not resolved:
        return action_payload, capability_draft, ""

    operation = str(resolved.get("operation", "") or operation_hint).strip().lower()
    if operation not in {"list", "read", "write"}:
        operation = operation_hint
    path = str(resolved.get("path", "") or existing_path).strip()
    if operation == "list" and not path:
        path = "."
    content = str(resolved.get("content", "") or existing_content).strip() if operation == "write" else ""
    capability = file_capability_for_operation(operation)
    draft = action_draft_from_file_operation(
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        operation=operation,
        path=path,
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
            path=path,
            content=content,
            plan_class=f"file_{operation}_basic",
            behavior_profile="remote_list_files" if operation == "list" else f"remote_{operation}_file",
            notes=[
                *list(getattr(capability_draft, "notes", []) or []),
                "file_operation_decided_by_llm",
            ],
        )

    decision["capability"] = capability
    decision["inputs"] = {"remote_path": path} if path else {}
    decision["input_items"] = [{"key": "remote_path", "key_label": "Remote path", "value": path}] if path else []
    decision["missing_input"] = "" if path or operation == "list" else "remote_path"
    decision["missing_input_label"] = "" if path or operation == "list" else "Remote path"
    if bool(resolved.get("ask_user")):
        decision["ask_user"] = True
        decision["execution_state"] = "needs_confirmation"
    if str(resolved.get("reason", "") or "").strip():
        decision["reason"] = str(resolved.get("reason", "") or "").strip()
    action_payload["decision"] = decision

    debug_line = ""
    if routing_debug_enabled():
        debug_line = agentic_debug_line(
            "file_operation_decision",
            connection_ref=connection_ref,
            fields={
                "kind": connection_kind,
                "operation": operation,
                "path": path or "-",
                "confidence": str(resolved.get("confidence", "") or "").strip() or "-",
                "reason": str(resolved.get("reason", "") or "").strip() or "-",
            },
            draft=draft,
        )
    return action_payload, capability_draft, debug_line
