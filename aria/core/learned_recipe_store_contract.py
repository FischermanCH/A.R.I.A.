from __future__ import annotations

from typing import Any

from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_id
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_inputs
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_preview
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_summary
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_title
from aria.core.learned_recipe_candidate_view import learned_recipe_scope
from aria.core.learned_recipe_candidate_view import learned_recipe_trigger_values
from aria.core.recipe_experience_contract import build_recipe_experience_record

LEARNED_RECIPE_STORE_ENTRY_KEYS = (
    "recipe_id",
    "stored_recipe_id",
    "title",
    "summary",
    "preview",
    "inputs",
    "router_keywords",
    "recipe_scope",
    "intent",
    "connection_kind",
    "connection_ref",
    "capability",
    "chosen_action",
    "policy_result",
    "execution_result",
    "user_feedback",
    "user_message",
    "experience_summary",
    "experience_count",
    "last_success_at",
    "promotion_state",
    "promotion_hint",
)


def normalize_learned_recipe_store_entry(
    source: dict[str, Any] | None,
    *,
    fallback_connection_kind: str = "",
) -> dict[str, Any]:
    record = dict(source or {})
    experience = build_recipe_experience_record(
        intent=str(record.get("intent", "") or "").strip(),
        connection_kind=str(record.get("connection_kind", "") or fallback_connection_kind or "").strip(),
        connection_ref=str(record.get("connection_ref", "") or "").strip(),
        capability=str(record.get("capability", "") or "").strip(),
        chosen_action=str(record.get("chosen_action", "") or "").strip(),
        policy_result=str(record.get("policy_result", "") or "").strip(),
        execution_result=str(record.get("execution_result", "") or "").strip(),
        user_feedback=str(record.get("user_feedback", "") or "").strip(),
        summary=str(record.get("experience_summary", "") or record.get("summary", "") or "").strip(),
        experience=record,
    )
    normalized: dict[str, Any] = {
        "recipe_id": learned_recipe_candidate_id(record),
        "stored_recipe_id": str(record.get("stored_recipe_id", "") or "").strip(),
        "title": learned_recipe_candidate_title(record, language="en", localized_text=lambda _l="", *, de, en: en),
        "preview": learned_recipe_candidate_preview(record, language="en", localized_text=lambda _l="", *, de, en: en),
        "inputs": learned_recipe_candidate_inputs(record),
        "router_keywords": learned_recipe_trigger_values(record),
        "recipe_scope": learned_recipe_scope(record, fallback_connection_kind=fallback_connection_kind),
        **experience,
        "user_message": str(record.get("user_message", "") or "").strip(),
        "summary": learned_recipe_candidate_summary(record, language="en", localized_text=lambda _l="", *, de, en: en),
        "experience_summary": experience["summary"],
    }
    return normalized


def build_learned_recipe_store_entry(
    *,
    intent: str = "",
    connection_kind: str = "",
    connection_ref: str = "",
    capability: str = "",
    chosen_action: str = "",
    policy_result: str = "",
    execution_result: str = "",
    user_feedback: str = "",
    user_message: str = "",
    summary: str = "",
    experience: Any | None = None,
    title: str = "",
    preview: str = "",
    inputs: dict[str, str] | None = None,
    router_keywords: list[str] | None = None,
    recipe_id: str = "",
    recipe_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = {
        "recipe_id": str(recipe_id or "").strip(),
        "id": str(recipe_id or "").strip(),
        "title": str(title or "").strip(),
        "preview": str(preview or "").strip(),
        "inputs": dict(inputs or {}),
        "router_keywords": [str(item or "").strip() for item in list(router_keywords or []) if str(item or "").strip()],
        "recipe_scope": dict(recipe_scope or {}),
        "intent": str(intent or "").strip(),
        "connection_kind": str(connection_kind or "").strip(),
        "connection_ref": str(connection_ref or "").strip(),
        "capability": str(capability or "").strip(),
        "chosen_action": str(chosen_action or "").strip(),
        "policy_result": str(policy_result or "").strip(),
        "execution_result": str(execution_result or "").strip(),
        "user_feedback": str(user_feedback or "").strip(),
        "user_message": str(user_message or "").strip(),
        "experience_summary": str(summary or "").strip(),
        **dict(experience or {}),
    }
    return normalize_learned_recipe_store_entry(raw, fallback_connection_kind=connection_kind)


def learned_recipe_store_list_row(source: dict[str, Any] | None, *, fallback_connection_kind: str = "") -> dict[str, Any]:
    entry = normalize_learned_recipe_store_entry(source, fallback_connection_kind=fallback_connection_kind)
    return {
        "recipe_id": entry["recipe_id"],
        "title": entry["title"],
        "intent": entry["intent"],
        "connection_kind": entry["connection_kind"],
        "capability": entry["capability"],
        "experience_count": entry["experience_count"],
        "last_success_at": entry["last_success_at"],
        "promotion_state": entry["promotion_state"],
        "promotion_hint": entry["promotion_hint"],
        "summary": entry["summary"],
    }
