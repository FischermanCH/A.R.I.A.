from __future__ import annotations

from aria.core.recipe_promotion_contract import DEFAULT_ELIGIBLE_EXPERIENCE_COUNT
from aria.core.recipe_promotion_contract import DEFAULT_REVIEW_READY_EXPERIENCE_COUNT
from aria.core.recipe_promotion_contract import PROMOTION_STATE_ELIGIBLE
from aria.core.recipe_promotion_contract import PROMOTION_STATE_OBSERVED
from aria.core.recipe_promotion_contract import PROMOTION_STATE_PROMOTED
from aria.core.recipe_promotion_contract import PROMOTION_STATE_REVIEW_READY
from aria.core.recipe_promotion_contract import SIDE_EFFECT_REVIEW_READY_EXPERIENCE_COUNT
from aria.core.recipe_promotion_contract import derive_recipe_promotion
from aria.core.recipe_promotion_contract import learned_recipe_can_promote_to_stored_recipe
from aria.core.recipe_promotion_contract import learned_recipe_promotion_blockers
from aria.core.recipe_promotion_contract import promotion_state_rank


def test_derive_recipe_promotion_keeps_explicit_values() -> None:
    assert derive_recipe_promotion(
        {
            "experience_count": 10,
            "promotion_state": "promoted",
            "promotion_hint": "Already approved and stored.",
        }
    ) == {
        "promotion_state": "promoted",
        "promotion_hint": "Already approved and stored.",
    }


def test_derive_recipe_promotion_marks_observed_before_review_threshold() -> None:
    assert derive_recipe_promotion({"experience_count": DEFAULT_REVIEW_READY_EXPERIENCE_COUNT - 1}) == {
        "promotion_state": PROMOTION_STATE_OBSERVED,
        "promotion_hint": "Observed successful runs; collect more evidence before review.",
    }


def test_derive_recipe_promotion_marks_review_ready_at_threshold() -> None:
    assert derive_recipe_promotion({"experience_count": DEFAULT_REVIEW_READY_EXPERIENCE_COUNT}) == {
        "promotion_state": PROMOTION_STATE_REVIEW_READY,
        "promotion_hint": "Multiple successful runs make this learned recipe ready for review.",
    }


def test_derive_recipe_promotion_marks_eligible_at_threshold() -> None:
    assert derive_recipe_promotion({"experience_count": DEFAULT_ELIGIBLE_EXPERIENCE_COUNT}) == {
        "promotion_state": PROMOTION_STATE_ELIGIBLE,
        "promotion_hint": "Repeated successful runs make this learned recipe eligible for promotion.",
    }


def test_derive_recipe_promotion_prefers_weighted_learning_evidence() -> None:
    assert derive_recipe_promotion({"experience_count": 9, "learning_evidence": 1.5}) == {
        "promotion_state": PROMOTION_STATE_OBSERVED,
        "promotion_hint": "Observed successful runs; collect more evidence before review.",
    }
    assert derive_recipe_promotion({"experience_count": 2, "learning_evidence": DEFAULT_REVIEW_READY_EXPERIENCE_COUNT}) == {
        "promotion_state": PROMOTION_STATE_REVIEW_READY,
        "promotion_hint": "Multiple successful runs make this learned recipe ready for review.",
    }


def test_derive_recipe_promotion_keeps_multi_target_observations_context_only() -> None:
    promotion = derive_recipe_promotion(
        {
            "experience_count": 8,
            "learning_evidence": 8.0,
            "recipe_scope": {"target_scope": "multi_target", "learning_origin": "plural_target_scope"},
        }
    )

    assert promotion["promotion_state"] == PROMOTION_STATE_OBSERVED
    assert "Multi-target observations stay context-only" in promotion["promotion_hint"]
    assert learned_recipe_promotion_blockers({"recipe_scope": {"target_scope": "multi_target"}}) == ["multi_target_scope"]


def test_derive_recipe_promotion_never_marks_side_effects_eligible() -> None:
    observed = derive_recipe_promotion({"experience_count": 4, "capability": "discord_send"})
    review = derive_recipe_promotion(
        {
            "experience_count": SIDE_EFFECT_REVIEW_READY_EXPERIENCE_COUNT,
            "learning_evidence": float(SIDE_EFFECT_REVIEW_READY_EXPERIENCE_COUNT),
            "capability": "discord_send",
        }
    )

    assert observed["promotion_state"] == PROMOTION_STATE_OBSERVED
    assert review["promotion_state"] == PROMOTION_STATE_REVIEW_READY
    assert "Side-effect learned actions stay review-only" in review["promotion_hint"]
    assert learned_recipe_can_promote_to_stored_recipe(
        {"promotion_state": PROMOTION_STATE_REVIEW_READY, "capability": "discord_send"}
    ) is False


def test_learned_recipe_can_promote_requires_review_state_and_no_blockers() -> None:
    assert learned_recipe_can_promote_to_stored_recipe(
        {"promotion_state": PROMOTION_STATE_ELIGIBLE, "capability": "ssh_command"}
    ) is True
    assert learned_recipe_can_promote_to_stored_recipe(
        {"promotion_state": PROMOTION_STATE_OBSERVED, "capability": "ssh_command"}
    ) is False
    assert learned_recipe_can_promote_to_stored_recipe(
        {
            "promotion_state": PROMOTION_STATE_ELIGIBLE,
            "capability": "ssh_command",
            "recipe_scope": {"target_scope": "multi_target"},
        }
    ) is False


def test_promotion_state_rank_orders_known_states() -> None:
    assert promotion_state_rank(PROMOTION_STATE_OBSERVED) < promotion_state_rank(PROMOTION_STATE_REVIEW_READY)
    assert promotion_state_rank(PROMOTION_STATE_REVIEW_READY) < promotion_state_rank(PROMOTION_STATE_ELIGIBLE)
    assert promotion_state_rank(PROMOTION_STATE_ELIGIBLE) < promotion_state_rank(PROMOTION_STATE_PROMOTED)
