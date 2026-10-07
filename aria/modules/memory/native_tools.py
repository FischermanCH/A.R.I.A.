"""Native read-only tool contribution owned by the Memory module."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from aria.modules.memory.personal import store_personal_claim
from aria.modules.memory.personal_claim_source import PERSONAL_CLAIM_SOURCE_AUTHORITY, load_personal_claim_evidence
from aria.modules.sdk import Evidence, NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

MEMORY_CONTEXT_SOURCE_AUTHORITY = "memory:context_collections"
_MEMORY_CONTEXT_SAFE_FIELDS = ("type", "text", "timestamp", "collection")
_MEMORY_CONTEXT_ROW_LIMIT = 16
_MEMORY_CONTEXT_TEXT_CHARS = 1_200


def _bounded_ascii_detail(value: Any, *, limit: int = 240) -> str:
    text = " ".join(str(value or "").strip().split())
    ascii_text = text.encode("ascii", "backslashreplace").decode("ascii")
    return ascii_text[:limit]


def _claim_rows(items: Sequence[Evidence | dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, Evidence):
            claim_id = str(item.payload.get("claim_id") or item.source.removeprefix("personal_claim:")).strip()
            summary = str(item.summary or "").strip()
            authority = str(item.payload.get("source_authority") or "").strip()
            if authority != PERSONAL_CLAIM_SOURCE_AUTHORITY or item.source != f"personal_claim:{claim_id}":
                raise ValueError("native_agent_memory_source_authority_mismatch")
        else:
            claim_id = str(item.get("claim_id") or "").strip()
            summary = str(item.get("summary") or "").strip()
            authority = str(item.get("source_authority") or "").strip()
            if authority != PERSONAL_CLAIM_SOURCE_AUTHORITY:
                raise ValueError("native_agent_memory_source_authority_mismatch")
        if claim_id and summary:
            rows.append({"claim_id": claim_id, "summary": summary})
    return rows


def _memory_context_rows(
    items: Sequence[Mapping[str, Any]], *, user_id: str,
) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    content_truncated = False
    for item in items:
        if str(item.get("source_authority") or "") != MEMORY_CONTEXT_SOURCE_AUTHORITY:
            raise ValueError("native_agent_memory_context_source_authority_mismatch")
        if str(item.get("scope_user_id") or "") != user_id:
            raise ValueError("native_agent_memory_context_scope_mismatch")
        row = {key: str(item.get(key) or "").strip() for key in _MEMORY_CONTEXT_SAFE_FIELDS}
        if len(row["text"]) > _MEMORY_CONTEXT_TEXT_CHARS:
            row["text"] = row["text"][:_MEMORY_CONTEXT_TEXT_CHARS]
            content_truncated = True
        if row["text"]:
            rows.append(row)
    return rows[:_MEMORY_CONTEXT_ROW_LIMIT], content_truncated


async def _load_memory_context(
    runtime_owner: Any, user_id: str, arguments: Mapping[str, Any],
) -> Sequence[Mapping[str, Any]]:
    loader = getattr(runtime_owner, "_native_agent_memory_context_loader", None)
    if callable(loader):
        return await loader(user_id, arguments)
    skill = runtime_owner.memory_skill
    query = str(arguments.get("query") or "").strip()
    memory_type = str(arguments.get("memory_type") or "all").strip()
    if query:
        result = await skill.execute(query=query, params={
            "action": "recall", "user_id": user_id, "collection": "", "top_k": 12,
            "include_documents": False, "include_learning_audit": False,
        })
        if not result.success:
            raise RuntimeError(str(result.error or "native_agent_memory_context_read_failed"))
        content = str(result.content or "").strip()
        return ({"source_authority": MEMORY_CONTEXT_SOURCE_AUTHORITY, "scope_user_id": user_id,
                 "type": "search_result", "text": content, "timestamp": "", "collection": ""},) if content else ()
    rows = await skill.list_memories(user_id, type_filter=memory_type, limit=_MEMORY_CONTEXT_ROW_LIMIT + 1)
    return tuple({**row, "source_authority": MEMORY_CONTEXT_SOURCE_AUTHORITY,
                  "scope_user_id": user_id} for row in rows)


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    def collection_for_user(name: str, user_id: str) -> str:
        resolver = getattr(runtime_owner, name, None)
        if not callable(resolver):
            resolver = getattr(runtime_owner, f"_{name}", None)
        if not callable(resolver):
            raise RuntimeError("native_agent_memory_capture_collection_unavailable")
        value = str(resolver(user_id) or "").strip()
        if not value:
            raise RuntimeError("native_agent_memory_capture_collection_unavailable")
        return value

    async def recall(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_tool_authority_mismatch")
        loader = getattr(runtime_owner, "_native_agent_claim_loader", None)
        items = await loader(context.user_id) if callable(loader) else await load_personal_claim_evidence(
            runtime_owner.memory_skill, user_id=context.user_id,
        )
        claims = _claim_rows(items)
        content = json.dumps(
            {"status": "ok", "claims": claims} if claims else {
                "status": "no_personal_claims", "claims": [],
                "message": "No active personal memory claims are stored for this user.",
            }, ensure_ascii=True, sort_keys=True,
        )
        return NativeToolResult(content=content, intent="memory_recall")

    async def read_context(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed = {"query", "memory_type"}
        if set(arguments) - allowed or any(not isinstance(arguments.get(key, ""), str) for key in allowed):
            raise ValueError("native_agent_memory_context_arguments_invalid")
        if str(arguments.get("memory_type") or "all") not in {"all", "fact", "preference", "knowledge", "session"}:
            raise ValueError("native_agent_memory_context_arguments_invalid")
        items = await _load_memory_context(runtime_owner, context.user_id, arguments)
        rows, content_truncated = _memory_context_rows(items, user_id=context.user_id)
        truncated = len(items) > len(rows) or content_truncated
        payload = {"status": "ok", "memory_context": rows, "selection": {
            "shown": len(rows), "available": len(items), "truncated": truncated,
            "notice": "gekuerzt: Ergebnisse oder Inhalte sind ausschnittweise" if truncated else "alle ausgewaehlten Treffer sind enthalten",
        }} if rows else {
            "status": "no_memory_context", "memory_context": [],
            "message": "No matching memory context is stored for this user.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "memory_context")

    async def forget(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed = {"claim_ids", "summary"}
        claim_ids = arguments.get("claim_ids")
        summary = arguments.get("summary", "")
        if (
            set(arguments) - allowed
            or not isinstance(claim_ids, list)
            or not claim_ids
            or any(not isinstance(item, str) or not item.strip() for item in claim_ids)
            or not isinstance(summary, str)
        ):
            raise ValueError("native_agent_memory_forget_arguments_invalid")
        normalized_ids = list(dict.fromkeys(item.strip() for item in claim_ids))
        preview = await runtime_owner.memory_skill.execute(query="", params={
            "action": "forget_preview",
            "user_id": context.user_id,
            "personal_claim_ids": normalized_ids,
            "max_hits": len(normalized_ids),
        })
        if not preview.success:
            raise RuntimeError(str(preview.error or "native_agent_memory_forget_preview_failed"))
        candidates = list((preview.metadata or {}).get("forget_candidates") or [])
        applied = await runtime_owner.memory_skill.execute(query="", params={
            "action": "forget_apply", "user_id": context.user_id, "candidates": candidates,
        })
        if not applied.success:
            raise RuntimeError(str(applied.error or "native_agent_memory_forget_apply_failed"))
        deleted_count = int((applied.metadata or {}).get("deleted_count") or 0)
        return NativeToolResult(
            json.dumps({"deleted_count": deleted_count}, ensure_ascii=True, sort_keys=True),
            "memory_forget",
        )

    async def capture(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed = {"claim_kind", "predicate", "value", "subject", "scope", "scope_ref"}
        required = {"claim_kind", "predicate", "value"}
        if set(arguments) - allowed or not required <= set(arguments):
            raise ValueError("native_agent_memory_capture_arguments_invalid")
        if any(not isinstance(arguments.get(key), str) for key in set(arguments)):
            raise ValueError("native_agent_memory_capture_arguments_invalid")
        claim_kind = str(arguments["claim_kind"]).strip()
        predicate = str(arguments["predicate"]).strip()
        value = str(arguments["value"]).strip()
        subject = str(arguments.get("subject") or "user").strip()
        scope = str(arguments.get("scope") or "global").strip()
        scope_ref = str(arguments.get("scope_ref") or "").strip()
        if (
            claim_kind not in {"fact", "preference"}
            or not predicate
            or not value
            or not subject
            or scope != "global"
        ):
            raise ValueError("native_agent_memory_capture_arguments_invalid")
        claim = {
            "claim_kind": claim_kind,
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "scope": "global",
            "scope_ref": scope_ref,
            "explicit_user_statement": True,
            "authority": "explicit_user",
            "risk": "low",
            "confidence": 1.0,
            "source": "native_capture",
        }
        try:
            result = await store_personal_claim(
                memory_skill=runtime_owner.memory_skill,
                llm_client=getattr(runtime_owner, "llm_client", None),
                claim=claim,
                user_id=context.user_id,
                facts_collection=collection_for_user("facts_collection_for_user", context.user_id),
                preferences_collection=collection_for_user("preferences_collection_for_user", context.user_id),
                request_id="",
            )
        except Exception as exc:
            result = {
                "stored": False,
                "reason": "claim_store_failed",
                "store_error": str(exc),
            }
        if bool(result.get("stored")):
            payload = {
                "status": "stored", "stored": True, "claim_kind": claim_kind,
                "subject": subject, "predicate": predicate, "value": value,
                "scope": "global", "reason": str(result.get("reason") or "claim_activated"),
            }
        else:
            raw_reason = str(result.get("reason") or "claim_store_failed")
            reason = raw_reason if raw_reason in {"invalid_claim", "claim_not_auto_activatable"} else "claim_store_failed"
            blockers = [
                str(item).strip() for item in list(result.get("activation_blockers") or [])
                if isinstance(item, str) and str(item).strip()
            ][:12]
            payload = {"status": "not_stored", "stored": False, "reason": reason}
            detail = _bounded_ascii_detail(result.get("store_error"))
            if detail:
                payload["detail"] = detail
            if reason == "claim_not_auto_activatable" and blockers:
                payload["activation_blockers"] = blockers
        return NativeToolResult(
            json.dumps(payload, ensure_ascii=True, sort_keys=True),
            "memory_capture",
        )

    return (
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="memory", name="recall_personal_memory",
            description="Read the user's active stored personal memory claims. This tool is read-only.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="read_only", confirmation_required=False,
            source_authority=PERSONAL_CLAIM_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_memory_enabled", order=100,
        ), handler=recall,
        ),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="memory", name="memory_context_read",
            description="Read or inventory the current user's facts, preferences, knowledge, context memory and sessions. Read-only.",
            input_schema={"type": "object", "properties": {
                "query": {"type": "string"},
                "memory_type": {"type": "string", "enum": ["all", "fact", "preference", "knowledge", "session"]},
            }, "required": []}, effect="read_only", confirmation_required=False,
            source_authority=MEMORY_CONTEXT_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_memory_enabled", order=110,
        ), handler=read_context),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="memory", name="memory_forget",
            description="Delete selected active personal memory claims for the current user after explicit confirmation.",
            input_schema={"type": "object", "properties": {
                "claim_ids": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            }, "required": ["claim_ids"]},
            effect="mutating", confirmation_required=True,
            source_authority=PERSONAL_CLAIM_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_write_memory_enabled", order=610,
        ), handler=forget),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="memory", name="memory_capture",
            description="Store one explicit personal fact or preference for the current user after confirmation.",
            input_schema={"type": "object", "properties": {
                "claim_kind": {"type": "string", "enum": ["fact", "preference"]},
                "predicate": {"type": "string"},
                "value": {"type": "string"},
                "subject": {"type": "string"},
                "scope": {"type": "string", "enum": ["global"]},
                "scope_ref": {"type": "string"},
            }, "required": ["claim_kind", "predicate", "value"]},
            effect="mutating", confirmation_required=True,
            source_authority=PERSONAL_CLAIM_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_write_memory_enabled", order=620,
        ), handler=capture),
    )
