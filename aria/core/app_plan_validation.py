from __future__ import annotations

from collections.abc import Mapping
from typing import Any


MUTATING_STEP_TERMS = (
    " up -d",
    " restart",
    " install",
    " build",
    " start",
    " pull",
    " run ",
)


def _clean_text(value: Any, *, limit: int = 400) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clean_list(values: Any, *, limit: int = 16) -> list[str]:
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


def _step_is_mutating(step: str) -> bool:
    lower = f" {step.lower()} "
    return any(term in lower for term in MUTATING_STEP_TERMS)


def validate_install_update_plan_draft(plan: Mapping[str, Any]) -> dict[str, Any]:
    runtime_kind = _clean_text(plan.get("runtime_kind") or "unknown", limit=80).lower()
    app_root = _clean_text(plan.get("app_root"), limit=240)
    preflight_checks = _clean_list(plan.get("preflight_checks"))
    backup_targets = _clean_list(plan.get("backup_targets"))
    proposed_steps = _clean_list(plan.get("proposed_steps"))
    health_checks = _clean_list(plan.get("health_checks"))
    rollback_steps = _clean_list(plan.get("rollback_steps"))
    draft_blockers = _clean_list(plan.get("blockers"))
    requires_confirmation = bool(plan.get("requires_confirmation") is True)
    missing_gates: list[str] = []
    if runtime_kind == "unknown":
        missing_gates.append("runtime_kind")
    if not app_root:
        missing_gates.append("app_root")
    if not preflight_checks:
        missing_gates.append("preflight_checks")
    if not backup_targets:
        missing_gates.append("backup_targets")
    if not proposed_steps:
        missing_gates.append("proposed_steps")
    if not health_checks or health_checks == ["define non-mutating health check before promotion"]:
        missing_gates.append("health_checks")
    if not rollback_steps:
        missing_gates.append("rollback_steps")
    if not requires_confirmation:
        missing_gates.append("operator_confirmation")
    mutating_steps = [step for step in proposed_steps if _step_is_mutating(step)]
    required_confirmations = ["operator_review", "explicit_execute_confirmation"]
    if mutating_steps:
        required_confirmations.append("mutating_step_confirmation")
    risk_level = "high" if runtime_kind == "unknown" else "medium"
    validation_state = "blocked" if missing_gates or draft_blockers else "review_required"
    regression_suggestions = [
        "verify plan renders as preview without executing commands",
        "verify backup targets exist before any mutating step",
        "verify health checks are non-mutating and run after proposed steps",
        "verify rollback steps restore previous known-good state",
    ]
    if runtime_kind == "docker_compose":
        regression_suggestions.append("verify compose plan includes config validation before up -d")
    elif runtime_kind == "systemd":
        regression_suggestions.append("verify systemd plan checks service status before restart")
    elif runtime_kind in {"node", "python"}:
        regression_suggestions.append("verify dependency install step is previewed before execution")
    return {
        "validation_state": validation_state,
        "risk_level": risk_level,
        "missing_gates": missing_gates,
        "draft_blockers": draft_blockers,
        "mutating_steps": mutating_steps,
        "required_confirmations": required_confirmations,
        "regression_suggestions": regression_suggestions,
        "runtime_activation_allowed": False,
        "promotion_allowed": False,
    }
