from __future__ import annotations

from typing import Any


def _clean_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = "\n".join(" ".join(line.split()) for line in text.splitlines())
    text = "\n".join(line for line in text.splitlines() if line)
    if len(text) <= limit:
        return text
    head = max(0, (limit - 20) // 2)
    tail = max(0, limit - 20 - head)
    return f"{text[:head].rstrip()}\n...[truncated]...\n{text[-tail:].lstrip()}"


def _budgeted_rows(rows: list[dict[str, str]], *, max_total_chars: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    total = 0
    for row in reversed(rows):
        text = str(row.get("text", "") or "")
        next_total = total + len(text)
        if selected and next_total > max_total_chars:
            break
        if next_total > max_total_chars:
            text = _clean_text(text, limit=max(200, max_total_chars - total))
            row = {**row, "text": text}
            next_total = total + len(text)
        selected.append(row)
        total = next_total
    selected.reverse()
    return selected


def compact_recent_visible_chat_context(
    history: list[dict[str, Any]] | None,
    *,
    limit: int = 6,
    max_text_chars: int = 1800,
    max_total_chars: int = 5200,
) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    for item in list(history or [])[-max(1, int(limit or 1)) :]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        text = _clean_text(item.get("text"), limit=max_text_chars)
        if not text:
            continue
        row = {"role": role, "text": text}
        badge_intent = str(item.get("badge_intent", "") or "").strip()
        if badge_intent:
            row["badge_intent"] = badge_intent
        rows.append(row)
    rows = _budgeted_rows(rows, max_total_chars=max_total_chars)
    if not rows:
        return {}
    return {
        "source": "visible_chat_history",
        "contract": "conversation_context_for_elliptic_followup_routing",
        "messages": rows,
    }


def visible_chat_context_from_turn_context(turn_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(turn_context, dict):
        return {}
    context = turn_context.get("recent_visible_chat_context")
    if not isinstance(context, dict):
        return {}
    messages = context.get("messages")
    if not isinstance(messages, list):
        return {}
    return compact_recent_visible_chat_context(messages)


def semantic_query_with_visible_chat_context(message: str, turn_context: dict[str, Any] | None) -> str:
    context = visible_chat_context_from_turn_context(turn_context)
    messages = context.get("messages") if isinstance(context, dict) else None
    if not isinstance(messages, list) or not messages:
        return ""
    parts = [f"Current user message: {_clean_text(message, limit=900)}", "Recent visible chat context:"]
    for row in messages[-4:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role", "") or "").strip() or "message"
        text = _clean_text(row.get("text"), limit=1400)
        if text:
            parts.append(f"{role}: {text}")
    query = "\n".join(part for part in parts if part.strip())
    return _clean_text(query, limit=4200)
