from __future__ import annotations

from aria.core.app_plan_artifacts import build_regression_drafts
from aria.core.app_plan_drafting import build_install_update_plan_draft
from aria.core.app_plan_validation import validate_install_update_plan_draft
from aria.core.app_regression_proposals import build_pytest_skeleton_proposal


def test_build_pytest_skeleton_proposal_from_compose_regression_drafts() -> None:
    app_identity = {
        "runtime_kind": "docker_compose",
        "app_root": "/srv/aria",
        "entry_artifacts": ["/srv/aria/docker-compose.yml"],
        "health_surfaces": ["port:8080"],
        "rollback_surfaces": ["backup:/srv/aria/docker-compose.yml"],
    }
    plan = build_install_update_plan_draft(app_identity)
    validation = validate_install_update_plan_draft(plan)
    regression_drafts = build_regression_drafts(plan, validation)

    proposal = build_pytest_skeleton_proposal(
        regression_drafts=regression_drafts,
        plan_validation=validation,
        app_identity=app_identity,
    )

    assert proposal["proposal_kind"] == "pytest_skeleton_proposal"
    assert proposal["target_file"] == "tests/test_app_plan_generated.py"
    assert proposal["runtime_kind"] == "docker_compose"
    assert proposal["app_root"] == "/srv/aria"
    assert proposal["write_allowed"] is False
    assert proposal["runtime_activation_allowed"] is False
    assert "app_identity_payload" in proposal["required_fixtures"]
    assert any(item["name"] == "test_docker_compose_plan_requires_config_validation_before_up" for item in proposal["test_functions"])
    assert all(item["mutating"] is False for item in proposal["test_functions"])


def test_build_pytest_skeleton_proposal_keeps_blocked_plans_review_only() -> None:
    validation = {
        "validation_state": "blocked",
        "regression_suggestions": ["blocked plans should stay blocked"],
    }

    proposal = build_pytest_skeleton_proposal(
        regression_drafts=[],
        plan_validation=validation,
        app_identity={"runtime_kind": "unknown"},
    )

    assert proposal["validation_state"] == "blocked"
    assert proposal["write_allowed"] is False
    assert proposal["test_functions"][0]["name"] == "test_generated_app_plan_requires_regression_drafts"
    assert "blocked plans should generate blocker/gate tests, not execution tests" in proposal["safety_notes"]


def test_build_pytest_skeleton_proposal_carries_artifact_review_patterns_as_weak_guidance() -> None:
    proposal = build_pytest_skeleton_proposal(
        regression_drafts=[{"name": "test_plan_preview", "test_kind": "plan_preview", "expected": "preview renders"}],
        plan_validation={"validation_state": "review_required"},
        app_identity={"runtime_kind": "docker_compose", "app_root": "/srv/aria"},
        artifact_review_patterns=[
            {
                "pattern_type": "artifact_pattern_candidate",
                "effect": "encourage",
                "summary": "Accepted pytest skeleton shape",
                "collection": "aria_learning_candidates_u1",
                "point_id": "pattern-1",
                "score": 0.9,
            }
        ],
    )

    assert proposal["artifact_review_pattern_count"] == 1
    assert proposal["artifact_review_patterns"][0]["effect"] == "encourage"
    assert proposal["artifact_review_patterns"][0]["write_allowed"] is False
    assert proposal["artifact_review_patterns"][0]["runtime_activation_allowed"] is False
    assert "artifact review patterns are weak guidance only, not write or runtime permission" in proposal["safety_notes"]
