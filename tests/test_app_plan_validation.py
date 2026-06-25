from __future__ import annotations

from aria.core.app_plan_drafting import build_install_update_plan_draft
from aria.core.app_plan_validation import validate_install_update_plan_draft


def test_validate_install_update_plan_draft_allows_review_for_complete_compose_plan() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "docker_compose",
            "app_root": "/srv/aria",
            "entry_artifacts": ["/srv/aria/docker-compose.yml"],
            "health_surfaces": ["port:8080"],
            "rollback_surfaces": ["backup:/srv/aria/docker-compose.yml", "record current container image/tag"],
        }
    )

    validation = validate_install_update_plan_draft(plan)

    assert validation["validation_state"] == "review_required"
    assert validation["risk_level"] == "medium"
    assert validation["missing_gates"] == []
    assert "run docker compose up -d only after explicit confirmation" in validation["mutating_steps"]
    assert "mutating_step_confirmation" in validation["required_confirmations"]
    assert validation["runtime_activation_allowed"] is False
    assert validation["promotion_allowed"] is False


def test_validate_install_update_plan_draft_blocks_systemd_without_health_and_rollback() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "systemd",
            "app_root": "/opt/app",
            "entry_artifacts": ["app.service"],
            "health_surfaces": [],
            "rollback_surfaces": [],
        }
    )

    validation = validate_install_update_plan_draft(plan)

    assert validation["validation_state"] == "blocked"
    assert "health_checks" in validation["missing_gates"]
    assert "rollback_surface_missing" in validation["draft_blockers"]
    assert validation["runtime_activation_allowed"] is False


def test_validate_install_update_plan_draft_blocks_unknown_runtime() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "unknown",
            "app_root": "",
            "entry_artifacts": [],
            "health_surfaces": [],
            "rollback_surfaces": [],
        }
    )

    validation = validate_install_update_plan_draft(plan)

    assert validation["validation_state"] == "blocked"
    assert validation["risk_level"] == "high"
    assert "runtime_kind" in validation["missing_gates"]
    assert "app_root" in validation["missing_gates"]
    assert "runtime_kind_unknown" in validation["draft_blockers"]


def test_validate_install_update_plan_draft_blocks_when_confirmation_missing() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "node",
            "app_root": "/opt/web",
            "entry_artifacts": ["/opt/web/package.json"],
            "health_surfaces": ["port:3000"],
            "rollback_surfaces": ["record current package versions"],
        }
    )
    plan["requires_confirmation"] = False

    validation = validate_install_update_plan_draft(plan)

    assert validation["validation_state"] == "blocked"
    assert "operator_confirmation" in validation["missing_gates"]
    assert "install dependencies in preview/dry-run mode where possible" in validation["mutating_steps"]
