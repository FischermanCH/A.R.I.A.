from __future__ import annotations

from typing import Any

from aria.core.recipe_promotion_contract import derive_recipe_promotion

RECIPE_PROMOTION_METADATA_KEYS = (
    "promotion_state",
    "promotion_hint",
)

RECIPE_EXPERIENCE_METADATA_KEYS = (
    "experience_count",
    "last_success_at",
    *RECIPE_PROMOTION_METADATA_KEYS,
)

RECIPE_EXPERIENCE_RECORD_KEYS = (
    "intent",
    "connection_kind",
    "connection_ref",
    "capability",
    "chosen_action",
    "policy_result",
    "execution_result",
    "user_feedback",
    "summary",
    *RECIPE_EXPERIENCE_METADATA_KEYS,
)


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def normalize_recipe_promotion(source: Any | None = None) -> dict[str, str]:
    return derive_recipe_promotion(source)


def normalize_recipe_experience(source: Any | None = None) -> dict[str, Any]:
    return {
        "experience_count": int(_source_value(source, "experience_count") or 0),
        "last_success_at": str(_source_value(source, "last_success_at") or "").strip(),
        **normalize_recipe_promotion(source),
    }


def build_recipe_experience_record(
    *,
    intent: str = "",
    connection_kind: str = "",
    connection_ref: str = "",
    capability: str = "",
    chosen_action: str = "",
    policy_result: str = "",
    execution_result: str = "",
    user_feedback: str = "",
    summary: str = "",
    experience: Any | None = None,
) -> dict[str, Any]:
    return {
        "intent": str(intent or "").strip(),
        "connection_kind": str(connection_kind or "").strip().lower(),
        "connection_ref": str(connection_ref or "").strip(),
        "capability": str(capability or "").strip().lower(),
        "chosen_action": str(chosen_action or "").strip(),
        "policy_result": str(policy_result or "").strip().lower(),
        "execution_result": str(execution_result or "").strip().lower(),
        "user_feedback": str(user_feedback or "").strip().lower(),
        "summary": str(summary or "").strip(),
        **normalize_recipe_experience(experience),
    }


def recipe_experience_prompt_parts(source: Any) -> list[str]:
    experience = normalize_recipe_experience(source)
    parts: list[str] = []
    if experience["experience_count"] > 0:
        parts.append(f"experience_count={experience['experience_count']}")
    if experience["last_success_at"]:
        parts.append(f"last_success_at={experience['last_success_at']}")
    if experience["promotion_state"]:
        parts.append(f"promotion_state={experience['promotion_state']}")
    if experience["promotion_hint"]:
        parts.append(f"promotion_hint={experience['promotion_hint']}")
    return parts


def recipe_experience_decision_fields(source: Any, *, prefix: str = "") -> dict[str, Any]:
    experience = normalize_recipe_experience(source)
    return {
        f"{prefix}experience_count": int(experience["experience_count"] or 0),
        f"{prefix}last_success_at": experience["last_success_at"],
        f"{prefix}promotion_state": experience["promotion_state"],
        f"{prefix}promotion_hint": experience["promotion_hint"],
    }
