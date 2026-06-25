from __future__ import annotations

from collections.abc import Mapping
from typing import Any


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


def build_health_check_drafts(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    runtime_kind = _clean_text(plan.get("runtime_kind") or "unknown", limit=80).lower()
    health_checks = _clean_list(plan.get("health_checks"))
    app_root = _clean_text(plan.get("app_root"), limit=240)
    drafts: list[dict[str, Any]] = []
    for item in health_checks:
        if item.startswith("port:"):
            port = item.split(":", 1)[1].strip()
            drafts.append(
                {
                    "check_kind": "tcp_port",
                    "target": port,
                    "command_preview": f"ss -ltn | grep ':{port} '",
                    "mutating": False,
                    "requires_confirmation": False,
                }
            )
        elif item.startswith("service:"):
            service = item.split(":", 1)[1].strip()
            drafts.append(
                {
                    "check_kind": "systemd_status",
                    "target": service,
                    "command_preview": f"systemctl is-active {service}",
                    "mutating": False,
                    "requires_confirmation": False,
                }
            )
        elif item.startswith("health:"):
            drafts.append(
                {
                    "check_kind": "runtime_health_signal",
                    "target": item.split(":", 1)[1].strip(),
                    "command_preview": "inspect runtime health output",
                    "mutating": False,
                    "requires_confirmation": False,
                }
            )
    if runtime_kind == "docker_compose" and app_root:
        drafts.append(
            {
                "check_kind": "docker_compose_ps",
                "target": app_root,
                "command_preview": f"cd {app_root} && docker compose ps",
                "mutating": False,
                "requires_confirmation": False,
            }
        )
    return drafts[:16]


def build_regression_drafts(plan: Mapping[str, Any], validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    runtime_kind = _clean_text(plan.get("runtime_kind") or "unknown", limit=80).lower()
    validation_state = _clean_text(validation.get("validation_state") or "blocked", limit=80)
    suggestions = _clean_list(validation.get("regression_suggestions"))
    drafts = [
        {
            "test_kind": "plan_preview",
            "name": "test_install_update_plan_renders_without_execution",
            "expected": "plan renders preview and keeps runtime_activation_allowed=false",
            "mutating": False,
            "source": "plan_validation",
        },
        {
            "test_kind": "gate_validation",
            "name": "test_install_update_plan_validation_blocks_missing_gates",
            "expected": "missing backup, health, app root, or confirmation gates keep the plan blocked",
            "mutating": False,
            "source": "plan_validation",
        },
    ]
    if runtime_kind == "docker_compose":
        drafts.append(
            {
                "test_kind": "runtime_specific_gate",
                "name": "test_docker_compose_plan_requires_config_validation_before_up",
                "expected": "compose plan includes non-mutating config/ps validation before up -d",
                "mutating": False,
                "source": "plan_validation",
            }
        )
    elif runtime_kind == "systemd":
        drafts.append(
            {
                "test_kind": "runtime_specific_gate",
                "name": "test_systemd_plan_requires_status_check_before_restart",
                "expected": "systemd plan includes status check before restart",
                "mutating": False,
                "source": "plan_validation",
            }
        )
    elif runtime_kind in {"node", "python"}:
        drafts.append(
            {
                "test_kind": "runtime_specific_gate",
                "name": "test_dependency_plan_requires_preview_before_install",
                "expected": "dependency install step is previewed before execution",
                "mutating": False,
                "source": "plan_validation",
            }
        )
    return [
        {
            **draft,
            "validation_state": validation_state,
            "suggestions": suggestions[:6],
            "runtime_activation_allowed": False,
        }
        for draft in drafts[:8]
    ]
