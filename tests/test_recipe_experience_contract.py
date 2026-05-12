from __future__ import annotations

from aria.core.recipe_experience_contract import build_recipe_experience_record
from aria.core.recipe_experience_contract import normalize_recipe_experience
from aria.core.recipe_experience_contract import normalize_recipe_promotion
from aria.core.recipe_experience_contract import recipe_experience_decision_fields
from aria.core.recipe_experience_contract import recipe_experience_prompt_parts


def test_normalize_recipe_promotion_applies_clean_defaults() -> None:
    assert normalize_recipe_promotion() == {
        "promotion_state": "",
        "promotion_hint": "",
    }


def test_normalize_recipe_experience_applies_clean_defaults() -> None:
    assert normalize_recipe_experience() == {
        "experience_count": 0,
        "last_success_at": "",
        "promotion_state": "",
        "promotion_hint": "",
    }


def test_build_recipe_experience_record_normalizes_store_ready_shape() -> None:
    record = build_recipe_experience_record(
        intent="health_check",
        connection_kind="SSH",
        connection_ref="srv-a",
        capability="SSH_COMMAND",
        chosen_action="uptime && df -h / && free -h",
        policy_result="ALLOW",
        execution_result="SUCCESS",
        user_feedback="GOOD",
        summary="Worked well for repeated Linux health checks.",
        experience={
            "experience_count": 7,
            "last_success_at": "2026-05-01T10:15:00Z",
            "promotion_state": "eligible",
            "promotion_hint": "Observed repeated successful Linux health checks.",
        },
    )

    assert record == {
        "intent": "health_check",
        "connection_kind": "ssh",
        "connection_ref": "srv-a",
        "capability": "ssh_command",
        "chosen_action": "uptime && df -h / && free -h",
        "policy_result": "allow",
        "execution_result": "success",
        "user_feedback": "good",
        "summary": "Worked well for repeated Linux health checks.",
        "experience_count": 7,
        "last_success_at": "2026-05-01T10:15:00Z",
        "promotion_state": "eligible",
        "promotion_hint": "Observed repeated successful Linux health checks.",
    }


def test_recipe_experience_prompt_and_decision_fields_use_same_normalized_values() -> None:
    experience = {
        "experience_count": 3,
        "last_success_at": "2026-05-02T08:00:00Z",
        "promotion_state": "review_ready",
        "promotion_hint": "Seen three successful operator-confirmed runs.",
    }

    assert recipe_experience_prompt_parts(experience) == [
        "experience_count=3",
        "last_success_at=2026-05-02T08:00:00Z",
        "promotion_state=review_ready",
        "promotion_hint=Seen three successful operator-confirmed runs.",
    ]
    assert recipe_experience_decision_fields(experience, prefix="action_") == {
        "action_experience_count": 3,
        "action_last_success_at": "2026-05-02T08:00:00Z",
        "action_promotion_state": "review_ready",
        "action_promotion_hint": "Seen three successful operator-confirmed runs.",
    }


def test_normalize_recipe_experience_derives_promotion_defaults_from_experience_count() -> None:
    assert normalize_recipe_experience({"experience_count": 2}) == {
        "experience_count": 2,
        "last_success_at": "",
        "promotion_state": "observed",
        "promotion_hint": "Observed successful runs; collect more evidence before review.",
    }
