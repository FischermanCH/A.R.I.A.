from __future__ import annotations

from typing import Any


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
        entries.append(
            {
                "detail": detail,
                "type": str(row.get("type", "")).strip(),
                "label": str(row.get("label", "")).strip(),
                "collection": str(row.get("collection", "")).strip(),
                "document_id": str(row.get("document_id", "")).strip(),
                "document_name": str(row.get("document_name", "")).strip(),
                "chunk_index": int(row.get("chunk_index", 0) or 0),
                "chunk_total": int(row.get("chunk_total", 0) or 0),
                "_position": index,
            }
        )
    entries.sort(key=recall_source_priority)
    trimmed = entries[:max_items]
    for entry in trimmed:
        entry.pop("_position", None)
    return trimmed
