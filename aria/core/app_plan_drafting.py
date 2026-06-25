from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _clean_text(value: Any, *, limit: int = 400) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clean_list(values: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    for value in values:
        clean = _clean_text(value, limit=320)
        if clean and clean not in rows:
            rows.append(clean)
        if len(rows) >= limit:
            break
    return rows


def build_install_update_plan_draft(app_identity: Mapping[str, Any]) -> dict[str, Any]:
    runtime_kind = _clean_text(app_identity.get("runtime_kind") or "unknown", limit=80).lower()
    app_root = _clean_text(app_identity.get("app_root"), limit=240)
    entry_artifacts = _clean_list(app_identity.get("entry_artifacts"), limit=16)
    health_surfaces = _clean_list(app_identity.get("health_surfaces"), limit=16)
    install_surfaces = _clean_list(app_identity.get("install_update_surfaces"), limit=16)
    rollback_surfaces = _clean_list(app_identity.get("rollback_surfaces"), limit=16)
    preflight_checks = [
        "confirm app identity hypothesis with operator",
        "verify current working tree/config files before changes",
        "check available disk space and permissions",
    ]
    backup_targets = [item.replace("backup:", "", 1) for item in rollback_surfaces if item.startswith("backup:")]
    proposed_steps: list[str]
    if runtime_kind == "docker_compose":
        proposed_steps = [
            "inspect compose configuration and referenced environment files",
            "pull or build images in preview mode where possible",
            "run docker compose up -d only after explicit confirmation",
        ]
        if not backup_targets:
            backup_targets = [item for item in entry_artifacts if item.endswith((".yml", ".yaml"))]
    elif runtime_kind == "systemd":
        proposed_steps = [
            "inspect unit file and current service status",
            "stage configuration changes without restarting service",
            "restart service only after explicit confirmation",
        ]
    elif runtime_kind == "node":
        proposed_steps = [
            "inspect package manager lockfile and scripts",
            "install dependencies in preview/dry-run mode where possible",
            "run build/start command only after explicit confirmation",
        ]
        if "package.json" in " ".join(entry_artifacts) and not backup_targets:
            backup_targets = [item for item in entry_artifacts if item.endswith("package.json")]
    elif runtime_kind == "python":
        proposed_steps = [
            "inspect dependency files and virtual environment layout",
            "prepare dependency install command without executing it",
            "restart application process only after explicit confirmation",
        ]
        if not backup_targets:
            backup_targets = [item for item in entry_artifacts if item.endswith(("pyproject.toml", "requirements.txt"))]
    else:
        proposed_steps = [
            "collect additional app identity evidence",
            "derive runtime-specific plan only after review",
        ]
    health_checks = health_surfaces or ["define non-mutating health check before promotion"]
    rollback_steps = [
        "restore backed up config/artifact files",
        "restore previous image/tag or package versions when known",
        "re-run health checks after rollback",
    ]
    blockers = []
    if runtime_kind == "unknown":
        blockers.append("runtime_kind_unknown")
    if not app_root:
        blockers.append("app_root_missing")
    if not health_surfaces:
        blockers.append("health_check_missing")
    if not rollback_surfaces and not backup_targets:
        blockers.append("rollback_surface_missing")
    return {
        "plan_kind": "install_update_plan_draft",
        "runtime_kind": runtime_kind,
        "app_root": app_root,
        "preflight_checks": preflight_checks,
        "backup_targets": backup_targets[:12],
        "proposed_steps": proposed_steps,
        "health_checks": health_checks,
        "rollback_steps": rollback_steps,
        "risk": "medium",
        "requires_confirmation": True,
        "runtime_activation_allowed": False,
        "blockers": blockers,
        "confidence": "medium" if not blockers else "low",
    }
