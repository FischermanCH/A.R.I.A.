from __future__ import annotations

from aria.core.app_plan_artifacts import build_health_check_drafts
from aria.core.app_plan_artifacts import build_regression_drafts
from aria.core.app_plan_drafting import build_install_update_plan_draft
from aria.core.app_plan_validation import validate_install_update_plan_draft


def test_build_health_check_drafts_from_compose_plan() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "docker_compose",
            "app_root": "/srv/aria",
            "entry_artifacts": ["/srv/aria/docker-compose.yml"],
            "health_surfaces": ["port:8080", "health:healthy"],
            "rollback_surfaces": ["backup:/srv/aria/docker-compose.yml"],
        }
    )

    drafts = build_health_check_drafts(plan)

    assert {"check_kind": "tcp_port", "target": "8080", "command_preview": "ss -ltn | grep ':8080 '", "mutating": False, "requires_confirmation": False} in drafts
    assert any(draft["check_kind"] == "docker_compose_ps" and draft["target"] == "/srv/aria" for draft in drafts)
    assert all(draft["mutating"] is False for draft in drafts)


def test_build_health_check_drafts_from_systemd_plan() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "systemd",
            "app_root": "/opt/app",
            "entry_artifacts": ["app.service"],
            "health_surfaces": ["service:app.service"],
            "rollback_surfaces": ["service:app.service"],
        }
    )

    drafts = build_health_check_drafts(plan)

    assert drafts == [
        {
            "check_kind": "systemd_status",
            "target": "app.service",
            "command_preview": "systemctl is-active app.service",
            "mutating": False,
            "requires_confirmation": False,
        }
    ]


def test_build_regression_drafts_include_runtime_specific_gate() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "docker_compose",
            "app_root": "/srv/aria",
            "entry_artifacts": ["/srv/aria/docker-compose.yml"],
            "health_surfaces": ["port:8080"],
            "rollback_surfaces": ["backup:/srv/aria/docker-compose.yml"],
        }
    )
    validation = validate_install_update_plan_draft(plan)

    drafts = build_regression_drafts(plan, validation)

    names = [draft["name"] for draft in drafts]
    assert "test_install_update_plan_renders_without_execution" in names
    assert "test_install_update_plan_validation_blocks_missing_gates" in names
    assert "test_docker_compose_plan_requires_config_validation_before_up" in names
    assert all(draft["runtime_activation_allowed"] is False for draft in drafts)
