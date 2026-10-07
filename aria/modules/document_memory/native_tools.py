"""Native read-only access to user-bound imported documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

DOCUMENT_SOURCE_AUTHORITY = "documents:document_store"
_SAFE_FIELDS = ("document_id", "document_name", "collection", "chunk_count", "excerpt", "answer")
_CONTENT_TOP_K = 6
_CONTENT_FIELD_CHARS = 1_600
_INVENTORY_TOP_K = 200


def _safe_rows(
    items: Sequence[Mapping[str, Any]], *, user_id: str, action: str,
) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    content_truncated = False
    for item in items:
        if str(item.get("source_authority") or "") != DOCUMENT_SOURCE_AUTHORITY:
            raise ValueError("native_agent_documents_source_authority_mismatch")
        if str(item.get("scope_user_id") or "") != user_id:
            raise ValueError("native_agent_documents_scope_mismatch")
        row = {key: str(item.get(key) or "").strip() for key in _SAFE_FIELDS}
        if action == "inventory":
            row["excerpt"] = ""
            row["answer"] = ""
        else:
            for key in ("excerpt", "answer"):
                if len(row[key]) > _CONTENT_FIELD_CHARS:
                    row[key] = row[key][:_CONTENT_FIELD_CHARS]
                    content_truncated = True
        if any(row.values()):
            rows.append(row)
    limit = _INVENTORY_TOP_K if action == "inventory" else _CONTENT_TOP_K
    return rows[:limit], content_truncated


def _result_source_items(
    result: Any, *, user_id: str, action: str,
) -> tuple[dict[str, Any], ...]:
    metadata = result.metadata if isinstance(getattr(result, "metadata", None), Mapping) else {}
    raw_sources = metadata.get("sources")
    if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes, bytearray)):
        return ()
    content_lines = [line.strip() for line in str(getattr(result, "content", "") or "").splitlines() if line.strip()]
    items: list[dict[str, Any]] = []
    for index, source in enumerate(raw_sources):
        if not isinstance(source, Mapping):
            continue
        fallback_excerpt = content_lines[index] if index < len(content_lines) else ""
        excerpt = str(source.get("excerpt") or source.get("text") or fallback_excerpt).strip()
        chunk_count = source.get("chunk_count") or source.get("chunk_total") or ""
        items.append({
            "source_authority": DOCUMENT_SOURCE_AUTHORITY,
            "scope_user_id": user_id,
            "document_id": str(source.get("document_id") or "").strip(),
            "document_name": str(source.get("document_name") or "").strip(),
            "collection": str(source.get("collection") or source.get("target_collection") or "").strip(),
            "chunk_count": str(chunk_count).strip(),
            "excerpt": "" if action == "inventory" else excerpt,
            "answer": "" if action != "answer" else str(source.get("answer") or "").strip(),
        })
    return tuple(items)


def _narrow_inventory_items(
    items: Sequence[Mapping[str, Any]], *, query: str,
) -> tuple[Mapping[str, Any], ...]:
    normalized_query = str(query or "").strip().casefold()
    if not normalized_query:
        return tuple(items)
    matched = tuple(
        item for item in items
        if any(
            identity and (identity in normalized_query or normalized_query in identity)
            for identity in (
                str(item.get("document_id") or "").strip().casefold(),
                str(item.get("document_name") or "").strip().casefold(),
                str(item.get("collection") or "").strip().casefold(),
            )
        )
    )
    return matched or tuple(items)


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def read_documents(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed = {"action", "query"}
        if set(arguments) - allowed or any(not isinstance(arguments.get(key, ""), str) for key in allowed):
            raise ValueError("native_agent_documents_arguments_invalid")
        action = str(arguments.get("action") or "inventory")
        query = str(arguments.get("query") or "").strip()
        if action not in {"inventory", "search", "answer", "summarize"} or (action != "inventory" and not query):
            raise ValueError("native_agent_documents_arguments_invalid")
        loader = getattr(runtime_owner, "_native_agent_documents_loader", None)
        if callable(loader):
            items = await loader(context.user_id, arguments)
        else:
            result = await runtime_owner.memory_skill.execute(query=query or "document inventory", params={
                "action": "recall", "user_id": context.user_id, "collection": "",
                "top_k": _INVENTORY_TOP_K if action == "inventory" else _CONTENT_TOP_K,
                "include_documents": True, "docs_only": True,
                "document_inventory": action == "inventory", "document_corpus_scan": action == "inventory",
            })
            if not result.success:
                raise RuntimeError(str(result.error or "native_agent_documents_read_failed"))
            content = str(result.content or "").strip()
            source_items = _result_source_items(result, user_id=context.user_id, action=action)
            if source_items:
                items = source_items
            elif action == "inventory":
                items = ()
            else:
                items = ({"source_authority": DOCUMENT_SOURCE_AUTHORITY, "scope_user_id": context.user_id,
                          "document_id": "", "document_name": "", "collection": "", "chunk_count": "",
                          "excerpt": content,
                          "answer": content if action in {"answer", "summarize"} else ""},) if content else ()
        if action == "inventory":
            items = _narrow_inventory_items(items, query=query)
        available = len(items)
        rows, content_truncated = _safe_rows(items, user_id=context.user_id, action=action)
        selection_truncated = available > len(rows) or content_truncated
        payload = {"status": "ok", "documents": rows, "selection": {
            "shown": len(rows), "available": available, "truncated": selection_truncated,
            "notice": (
                f"gekuerzt: zeige {len(rows)} von {available} relevanten Treffern; Inhalte sind ausschnittweise"
                if selection_truncated else "alle ausgewaehlten Treffer sind enthalten"
            ),
        }} if rows else {
            "status": "no_documents", "documents": [],
            "message": "No imported documents match the requested scope for this user.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "documents")

    return (NativeToolBinding(NativeToolContract(
        owner_module_id="document_memory", name="documents_read_search_inventory",
        description=(
            "Use action='inventory' to list which documents, PDFs or leaflets the current user has imported; "
            "inventory never answers content questions. Use action='search' or 'answer' to find content inside "
            "documents; search never proves completeness. Use action='summarize' only for source-bound document "
            "content. Read-only."
        ),
        input_schema={"type": "object", "properties": {
            "action": {"type": "string", "enum": ["inventory", "search", "answer", "summarize"]},
            "query": {"type": "string"},
        }, "required": ["action"]}, effect="read_only", confirmation_required=False,
        source_authority=DOCUMENT_SOURCE_AUTHORITY, user_scoped=True,
        rollout_flag="native_agent_memory_enabled", order=140,
    ), read_documents),)
