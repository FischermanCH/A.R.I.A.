from __future__ import annotations

from aria.core.recipe_candidate_contract import build_recipe_candidate_metadata
from aria.core.recipe_candidate_contract import normalize_recipe_experience


def test_normalize_recipe_experience_applies_clean_defaults() -> None:
    assert normalize_recipe_experience() == {
        "experience_count": 0,
        "last_success_at": "",
        "promotion_state": "",
        "promotion_hint": "",
    }


def test_build_recipe_candidate_metadata_merges_role_scope_origin_and_experience() -> None:
    metadata = build_recipe_candidate_metadata(
        candidate_role="learned_recipe_candidate",
        recipe_scope={"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        recipe_origin="learned_experience_store",
        experience={
            "experience_count": 7,
            "last_success_at": "2026-05-01T10:15:00Z",
            "promotion_state": "eligible",
            "promotion_hint": "Observed repeated successful Linux health checks.",
        },
    )

    assert metadata == {
        "candidate_role": "learned_recipe_candidate",
        "recipe_scope": {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        "recipe_origin": "learned_experience_store",
        "experience_count": 7,
        "last_success_at": "2026-05-01T10:15:00Z",
        "promotion_state": "eligible",
        "promotion_hint": "Observed repeated successful Linux health checks.",
    }
