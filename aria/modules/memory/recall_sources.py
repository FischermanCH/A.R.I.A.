from __future__ import annotations

from typing import Any


DOCUMENT_EXCERPT_MAX_CHARS = 1_600


def bounded_document_excerpt(value: Any, *, max_chars: int = DOCUMENT_EXCERPT_MAX_CHARS) -> str:
    """Keep a source chunk readable while enforcing a strict per-hit bound."""

    text = str(value or "").strip()
    limit = max(1, int(max_chars))
    if len(text) <= limit:
        return text
    marker = "…"
    if limit == len(marker):
        return marker
    candidate = text[: max(1, limit - len(marker))]
    boundary = max(candidate.rfind("\n"), candidate.rfind(". "), candidate.rfind("! "), candidate.rfind("? "))
    if boundary >= max(40, limit // 2):
        candidate = candidate[: boundary + (0 if candidate[boundary] == "\n" else 1)]
    return candidate.rstrip() + marker


def format_recall_source_detail(row: dict[str, Any]) -> str:
    collection = str(row.get("collection", "")).strip()
    document_name = str(row.get("document_name", "")).strip()
    chunk_index = int(row.get("chunk_index", 0) or 0)
    chunk_total = int(row.get("chunk_total", 0) or 0)
    label = str(row.get("label", "")).strip() or "MEMORY"

    if document_name:
        parts = [f"Quelle: {document_name}"]
        if collection:
            parts.append(collection)
        if chunk_index > 0 and chunk_total > 0:
            parts.append(f"Chunk {chunk_index}/{chunk_total}")
        return " · ".join(parts)

    parts = [f"Quelle: {label}"]
    if collection:
        parts.append(collection)
    return " · ".join(parts)


def recall_source_priority(entry: dict[str, Any]) -> tuple[int, int]:
    source_type = str(entry.get("type", "")).strip().lower()
    priority_map = {
        "document": 0,
        "web": 0,
        "fact": 1,
        "preference": 2,
        "knowledge": 3,
        "session": 4,
    }
    return priority_map.get(source_type, 9), int(entry.get("_position", 0) or 0)


def build_recall_source_entries(
    rows: list[dict[str, Any]],
    *,
    max_items: int = 4,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        detail = format_recall_source_detail(row)
        if not detail or detail in seen:
            continue
        seen.add(detail)
        source_type = str(row.get("type", "")).strip()
        entries.append(
            {
                "detail": detail,
                "type": source_type,
                "label": str(row.get("label", "")).strip(),
                "collection": str(row.get("collection", "")).strip(),
                "document_id": str(row.get("document_id", "")).strip(),
                "document_name": str(row.get("document_name", "")).strip(),
                "chunk_index": int(row.get("chunk_index", 0) or 0),
                "chunk_total": int(row.get("chunk_total", 0) or 0),
                "score": float(row.get("score", 0.0) or 0.0),
                "excerpt": bounded_document_excerpt(row.get("text", "")) if source_type.lower() == "document" else "",
                "neighbor": bool(row.get("neighbor", False)) if source_type.lower() == "document" else False,
                "neighbor_of_chunk_index": int(row.get("neighbor_of_chunk_index", 0) or 0),
                "_position": index,
            }
        )
    entries.sort(key=recall_source_priority)
    trimmed = entries[:max_items]
    for entry in trimmed:
        entry.pop("_position", None)
    return trimmed
