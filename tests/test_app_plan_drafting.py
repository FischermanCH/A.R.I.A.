from __future__ import annotations

from aria.core.app_plan_drafting import build_install_update_plan_draft


def test_build_install_update_plan_draft_for_docker_compose() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "docker_compose",
            "app_root": "/srv/aria",
            "entry_artifacts": ["/srv/aria/docker-compose.yml", "/srv/aria/Dockerfile"],
            "health_surfaces": ["port:8080", "health:healthy"],
            "install_update_surfaces": ["docker compose up -d"],
            "rollback_surfaces": ["backup:/srv/aria/docker-compose.yml", "record current container image/tag"],
        }
    )

    assert plan["plan_kind"] == "install_update_plan_draft"
    assert plan["runtime_kind"] == "docker_compose"
    assert "/srv/aria/docker-compose.yml" in plan["backup_targets"]
    assert "run docker compose up -d only after explicit confirmation" in plan["proposed_steps"]
    assert "port:8080" in plan["health_checks"]
    assert plan["requires_confirmation"] is True
    assert plan["runtime_activation_allowed"] is False
    assert plan["blockers"] == []


def test_build_install_update_plan_draft_for_systemd_requires_health_and_rollback() -> None:
    plan = build_install_update_plan_draft(
        {
            "runtime_kind": "systemd",
            "app_root": "/opt/app",
            "entry_artifacts": ["app.service"],
            "health_surfaces": [],
            "install_update_surfaces": ["systemctl restart <service>"],
            "rollback_surfaces": [],
        }
    )

    assert plan["runtime_kind"] == "systemd"
    assert "restart service only after explicit confirmation" in plan["proposed_steps"]
    assert "define non-mutating health check before promotion" in plan["health_checks"]
    assert "health_check_missing" in plan["blockers"]
    assert "rollback_surface_missing" in plan["blockers"]
    assert plan["confidence"] == "low"


def test_build_install_update_plan_draft_for_node_and_python() -> None:
    node = build_install_update_plan_draft(
        {
            "runtime_kind": "node",
            "app_root": "/opt/web",
            "entry_artifacts": ["/opt/web/package.json"],
            "health_surfaces": ["port:3000"],
            "rollback_surfaces": ["record current package versions"],
        }
    )
    python = build_install_update_plan_draft(
        {
            "runtime_kind": "python",
            "app_root": "/opt/api",
            "entry_artifacts": ["/opt/api/pyproject.toml", "/opt/api/requirements.txt"],
            "health_surfaces": ["port:8000"],
            "rollback_surfaces": ["record current package versions"],
        }
    )

    assert "install dependencies in preview/dry-run mode where possible" in node["proposed_steps"]
    assert "/opt/web/package.json" in node["backup_targets"]
    assert "prepare dependency install command without executing it" in python["proposed_steps"]
    assert "/opt/api/pyproject.toml" in python["backup_targets"]
