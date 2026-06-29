from __future__ import annotations

from typing import Any, Iterable

from aria.core.learning_promotion import learning_active_hints_collection_for_user
from aria.core.routing_resolver import infer_preferred_connection_kind


def should_skip_active_learning_hints_for_turn(
    message: str,
    *,
    available_connection_kinds: Iterable[str],
) -> bool:
    kinds = {str(kind or "").strip().lower() for kind in available_connection_kinds if str(kind or "").strip()}
    if not kinds:
        return False
    preferred_kind = infer_preferred_connection_kind(message, available_kinds=kinds)
    return bool(preferred_kind)


async def recall_active_learning_hints(
    memory_skill: Any,
    message: str,
    *,
    user_id: str,
) -> list[dict[str, str]]:
    if memory_skill is None:
        return []
    clean_message = str(message or "").strip()
    if not clean_message:
        return []
    collection = learning_active_hints_collection_for_user(user_id or "web")
    try:
        result = await memory_skill.execute(
            clean_message,
            {
                "action": "recall",
                "user_id": user_id or "web",
                "collection": collection,
                "top_k": 2,
            },
        )
    except Exception:
        return []
    if not result.success:
        return []
    content = str(result.content or "").strip()
    if not content or "Keine passende Erinnerung gefunden" in content:
        return []
    hints: list[dict[str, str]] = []
    for line in (line.strip() for line in content.splitlines() if line.strip()):
        if len(hints) >= 2:
            break
        if "AKTIVER LERN-HINWEIS" not in line and "Active Learning Hint" not in line:
            continue
        hints.append(
            {
                "source": "qdrant_learning_active_hint",
                "collection": collection,
                "text": line[:700],
                "runtime_effect": "weak_signal_only",
            }
        )
    return hints
