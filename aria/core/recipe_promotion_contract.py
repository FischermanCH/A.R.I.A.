from __future__ import annotations

from typing import Any

from aria.core.connection_action_contract import connection_action_contract

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
SIDE_EFFECT_REVIEW_READY_EXPERIENCE_COUNT = 5

PROMOTION_BLOCKER_MULTI_TARGET = "multi_target_scope"
PROMOTION_BLOCKER_SIDE_EFFECT = "side_effect_requires_manual_recipe"


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def _source_scope(source: Any) -> dict[str, Any]:
    scope = _source_value(source, "recipe_scope")
    return dict(scope) if isinstance(scope, dict) else {}


def learned_recipe_promotion_blockers(source: Any | None = None) -> list[str]:
    blockers: list[str] = []
    scope = _source_scope(source)
    target_scope = str(scope.get("target_scope", "") or scope.get("scope_kind", "") or "").strip().lower()
    learning_origin = str(scope.get("learning_origin", "") or "").strip().lower()
    if target_scope in {"multi_target", "plural_target_scope"} or learning_origin == "plural_target_scope":
        blockers.append(PROMOTION_BLOCKER_MULTI_TARGET)

    capability = str(_source_value(source, "capability") or "").strip().lower()
    contract = connection_action_contract(capability)
    if bool(getattr(contract, "side_effect", False)):
        blockers.append(PROMOTION_BLOCKER_SIDE_EFFECT)
    return blockers


def learned_recipe_can_promote_to_stored_recipe(source: Any | None = None) -> bool:
    state = str(_source_value(source, "promotion_state") or "").strip().lower()
    if state == PROMOTION_STATE_PROMOTED:
        return False
    if state not in {PROMOTION_STATE_REVIEW_READY, PROMOTION_STATE_ELIGIBLE}:
        return False
    return not learned_recipe_promotion_blockers(source)


def learned_recipe_promotion_gate_hint(source: Any | None = None) -> str:
    blockers = set(learned_recipe_promotion_blockers(source))
    if PROMOTION_BLOCKER_MULTI_TARGET in blockers:
        return "Multi-target observations stay context-only; create an explicit reviewed recipe for the target set."
    if PROMOTION_BLOCKER_SIDE_EFFECT in blockers:
        return "Side-effect learned actions stay review-only; create an explicit recipe so policy, confirmation and inputs are visible."
    return ""


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

    gate_hint = learned_recipe_promotion_gate_hint(source)
    experience_count = int(_source_value(source, "experience_count") or 0)
    try:
        evidence = float(_source_value(source, "learning_evidence") or 0.0)
    except (TypeError, ValueError):
        evidence = 0.0
    maturity_score = evidence if evidence > 0 else float(experience_count)
    blockers = set(learned_recipe_promotion_blockers(source))
    if PROMOTION_BLOCKER_MULTI_TARGET in blockers:
        return {
            "promotion_state": PROMOTION_STATE_OBSERVED if experience_count > 0 else "",
            "promotion_hint": gate_hint,
        }
    if PROMOTION_BLOCKER_SIDE_EFFECT in blockers:
        if maturity_score >= SIDE_EFFECT_REVIEW_READY_EXPERIENCE_COUNT:
            return {
                "promotion_state": PROMOTION_STATE_REVIEW_READY,
                "promotion_hint": gate_hint,
            }
        if experience_count > 0:
            return {
                "promotion_state": PROMOTION_STATE_OBSERVED,
                "promotion_hint": gate_hint,
            }
        return {
            "promotion_state": "",
            "promotion_hint": gate_hint,
        }
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
