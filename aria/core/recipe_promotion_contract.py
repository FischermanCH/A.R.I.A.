from __future__ import annotations

from typing import Any

PROMOTION_STATE_OBSERVED = "observed"
PROMOTION_STATE_REVIEW_READY = "review_ready"
PROMOTION_STATE_ELIGIBLE = "eligible"
PROMOTION_STATE_PROMOTED = "promoted"

PROMOTION_STATES = (
    PROMOTION_STATE_OBSERVED,
    PROMOTION_STATE_REVIEW_READY,
    PROMOTION_STATE_ELIGIBLE,
    PROMOTION_STATE_PROMOTED,
)

DEFAULT_REVIEW_READY_EXPERIENCE_COUNT = 3
DEFAULT_ELIGIBLE_EXPERIENCE_COUNT = 5


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def promotion_state_rank(state: str) -> int:
    clean = str(state or "").strip().lower()
    if clean == PROMOTION_STATE_OBSERVED:
        return 1
    if clean == PROMOTION_STATE_REVIEW_READY:
        return 2
    if clean == PROMOTION_STATE_ELIGIBLE:
        return 3
    if clean == PROMOTION_STATE_PROMOTED:
        return 4
    return 0


def derive_recipe_promotion(source: Any | None = None) -> dict[str, str]:
    explicit_state = str(_source_value(source, "promotion_state") or "").strip().lower()
    explicit_hint = str(_source_value(source, "promotion_hint") or "").strip()
    if explicit_state or explicit_hint:
        return {
            "promotion_state": explicit_state,
            "promotion_hint": explicit_hint,
        }

    experience_count = int(_source_value(source, "experience_count") or 0)
    try:
        evidence = float(_source_value(source, "learning_evidence") or 0.0)
    except (TypeError, ValueError):
        evidence = 0.0
    maturity_score = evidence if evidence > 0 else float(experience_count)
    if maturity_score >= DEFAULT_ELIGIBLE_EXPERIENCE_COUNT:
        return {
            "promotion_state": PROMOTION_STATE_ELIGIBLE,
            "promotion_hint": "Repeated successful runs make this learned recipe eligible for promotion.",
        }
    if maturity_score >= DEFAULT_REVIEW_READY_EXPERIENCE_COUNT:
        return {
            "promotion_state": PROMOTION_STATE_REVIEW_READY,
            "promotion_hint": "Multiple successful runs make this learned recipe ready for review.",
        }
    if experience_count > 0:
        return {
            "promotion_state": PROMOTION_STATE_OBSERVED,
            "promotion_hint": "Observed successful runs; collect more evidence before review.",
        }
    return {
        "promotion_state": "",
        "promotion_hint": "",
    }
