from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aria.core.recipe_promotion_contract import PROMOTION_STATE_PROMOTED
from aria.core.learned_recipe_store import load_learned_recipe_store_entries
from aria.core.learned_recipe_store import save_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import build_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry


def _normalized_recipe_id(
    *,
    recipe_id: str = "",
    intent: str = "",
    connection_kind: str = "",
    capability: str = "",
) -> str:
    entry = build_learned_recipe_store_entry(
        recipe_id=recipe_id,
        intent=intent,
        connection_kind=connection_kind,
        capability=capability,
    )
    return str(entry.get("recipe_id", "") or "").strip()


def _find_existing_entry(
    *,
    recipe_id: str = "",
    intent: str = "",
    connection_kind: str = "",
    capability: str = "",
) -> dict[str, Any] | None:
    target_id = _normalized_recipe_id(
        recipe_id=recipe_id,
        intent=intent,
        connection_kind=connection_kind,
        capability=capability,
    )
    if not target_id:
        return None
    for row in load_learned_recipe_store_entries():
        if str(row.get("recipe_id", "") or "").strip() == target_id:
            return dict(row)
    return None


def record_successful_learned_recipe_execution(
    *,
    intent: str,
    connection_kind: str,
    capability: str,
    chosen_action: str,
    connection_ref: str = "",
    policy_result: str = "allow",
    execution_result: str = "success",
    user_feedback: str = "",
    user_message: str = "",
    summary: str = "",
    recipe_id: str = "",
    title: str = "",
    preview: str = "",
    inputs: dict[str, str] | None = None,
    router_keywords: list[str] | None = None,
    recipe_scope: dict[str, Any] | None = None,
    recorded_at: str = "",
) -> dict[str, Any] | None:
    clean_execution_result = str(execution_result or "").strip().lower()
    if clean_execution_result != "success":
        return None

    existing = _find_existing_entry(
        recipe_id=recipe_id,
        intent=intent,
        connection_kind=connection_kind,
        capability=capability,
    ) or {}
    preserved_promotion_state = str(existing.get("promotion_state", "") or "").strip().lower()
    preserved_promotion_hint = str(existing.get("promotion_hint", "") or "").strip()
    if preserved_promotion_state != PROMOTION_STATE_PROMOTED and not preserved_promotion_hint.startswith("admin:"):
        preserved_promotion_state = ""
        preserved_promotion_hint = ""
    timestamp = str(recorded_at or "").strip() or datetime.now(timezone.utc).isoformat()
    next_experience_count = int(existing.get("experience_count", 0) or 0) + 1

    merged = {
        **existing,
        "recipe_id": str(recipe_id or existing.get("recipe_id", "") or "").strip(),
        "intent": str(intent or existing.get("intent", "") or "").strip(),
        "connection_kind": str(connection_kind or existing.get("connection_kind", "") or "").strip(),
        "connection_ref": str(connection_ref or existing.get("connection_ref", "") or "").strip(),
        "capability": str(capability or existing.get("capability", "") or "").strip(),
        "chosen_action": str(chosen_action or existing.get("chosen_action", "") or "").strip(),
        "policy_result": str(policy_result or existing.get("policy_result", "") or "").strip(),
        "execution_result": clean_execution_result,
        "user_feedback": str(user_feedback or existing.get("user_feedback", "") or "").strip(),
        "user_message": str(user_message or existing.get("user_message", "") or "").strip(),
        "experience_summary": str(summary or existing.get("experience_summary", "") or existing.get("summary", "") or "").strip(),
        "title": str(title or existing.get("title", "") or "").strip(),
        "preview": str(preview or existing.get("preview", "") or "").strip(),
        "inputs": dict(inputs or existing.get("inputs", {}) or {}),
        "router_keywords": list(router_keywords or existing.get("router_keywords", []) or []),
        "recipe_scope": dict(recipe_scope or existing.get("recipe_scope", {}) or {}),
        "experience_count": next_experience_count,
        "last_success_at": timestamp,
        "promotion_state": preserved_promotion_state,
        "promotion_hint": preserved_promotion_hint,
    }
    normalized = normalize_learned_recipe_store_entry(merged, fallback_connection_kind=connection_kind)
    return save_learned_recipe_store_entry(
        normalized,
        previous_id=str(existing.get("recipe_id", "") or "").strip() or None,
    )
