"""Native read-only access to user-bound imported documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

DOCUMENT_SOURCE_AUTHORITY = "documents:document_store"
_SAFE_FIELDS = (
    "document_id", "document_name", "collection", "chunk_count", "chunk_index",
    "score", "neighbor", "excerpt", "answer",
)
_CONTENT_TOP_K = 12
_CONTENT_FIELD_CHARS = 1_600
_CONTENT_TOTAL_CHARS = 9_000
_TOOL_RESULT_MAX_CHARS = 12_000
_INVENTORY_TOP_K = 200


def _bounded_content_field(value: str, *, max_chars: int) -> str:
    text = str(value or "").strip()
    limit = max(1, int(max_chars))
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    candidate = text[: limit - 1]
    boundary = max(candidate.rfind("\n"), candidate.rfind(". "), candidate.rfind("! "), candidate.rfind("? "))
    if boundary >= max(40, limit // 2):
        candidate = candidate[: boundary + (0 if candidate[boundary] == "\n" else 1)]
    return candidate.rstrip() + "…"


def _serialize_payload_bounded(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    documents = payload.get("documents")
    selection = payload.get("selection")
    if not isinstance(documents, list) or not isinstance(selection, dict):
        return encoded
    while len(encoded) > _TOOL_RESULT_MAX_CHARS and documents:
        candidates = [
            (len(str(row.get(field) or "")), row, field)
            for row in documents if isinstance(row, dict)
            for field in ("excerpt", "answer")
        ]
        size, row, field = max(candidates, default=(0, None, ""), key=lambda item: item[0])
        if row is not None and size > 200:
            row[field] = _bounded_content_field(str(row.get(field) or ""), max_chars=max(200, size - 400))
        else:
            documents.pop()
        selection["shown"] = len(documents)
        selection["truncated"] = True
        selection["notice"] = (
            f"gekuerzt: zeige {len(documents)} von {int(selection.get('available', 0) or 0)} "
            "relevanten Treffern; Inhalte sind ausschnittweise"
        )
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return encoded


def _safe_rows(
    items: Sequence[Mapping[str, Any]], *, user_id: str, action: str,
) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    content_truncated = False
    remaining_content_chars = _CONTENT_TOTAL_CHARS
    for item in items:
        if action != "inventory" and remaining_content_chars <= 0:
            content_truncated = True
            break
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
                original = row[key]
                per_hit_limit = min(_CONTENT_FIELD_CHARS, max(0, remaining_content_chars))
                row[key] = _bounded_content_field(original, max_chars=per_hit_limit) if original and per_hit_limit else ""
                if row[key] != original:
                    content_truncated = True
                remaining_content_chars = max(0, remaining_content_chars - len(row[key]))
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
    items: list[dict[str, Any]] = []
    for source in raw_sources:
        if not isinstance(source, Mapping):
            continue
        excerpt = str(source.get("excerpt") or source.get("text") or "").strip()
        chunk_count = source.get("chunk_count") or source.get("chunk_total") or ""
        items.append({
            "source_authority": DOCUMENT_SOURCE_AUTHORITY,
            "scope_user_id": user_id,
            "document_id": str(source.get("document_id") or "").strip(),
            "document_name": str(source.get("document_name") or "").strip(),
            "collection": str(source.get("collection") or source.get("target_collection") or "").strip(),
            "chunk_count": str(chunk_count).strip(),
            "chunk_index": str(source.get("chunk_index") or "").strip(),
            "score": str(source.get("score") or "").strip(),
            "neighbor": "true" if bool(source.get("neighbor", False)) else "false",
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
        detail_lines: tuple[str, ...] = ()
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
            metadata = result.metadata if isinstance(getattr(result, "metadata", None), Mapping) else {}
            detail_lines = tuple(
                str(line)[:600] for line in metadata.get("detail_lines", ())
                if str(line).startswith("Routing Debug: document_inventory")
            )
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
                if selection_truncated else "alle ausgewählten Treffer sind enthalten"
            ),
        }} if rows else {
            "status": "no_documents", "documents": [],
            "message": "No imported documents match the requested scope for this user.",
        }
        return NativeToolResult(
            (
                json.dumps(payload, ensure_ascii=True, sort_keys=True)
                if action == "inventory" else _serialize_payload_bounded(payload)
            ),
            "documents",
            detail_lines=detail_lines,
        )

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
