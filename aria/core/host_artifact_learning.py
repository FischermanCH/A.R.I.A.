from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from aria.core.app_plan_drafting import build_install_update_plan_draft
from aria.core.app_plan_artifacts import build_health_check_drafts
from aria.core.app_plan_artifacts import build_regression_drafts
from aria.core.app_plan_validation import validate_install_update_plan_draft
from aria.core.app_regression_proposals import build_pytest_skeleton_proposal


def _clean_text(value: Any, *, limit: int = 1200) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _unique(values: list[str], *, limit: int = 12) -> list[str]:
    rows: list[str] = []
    for value in values:
        clean = _clean_text(value, limit=240)
        if clean and clean not in rows:
            rows.append(clean)
        if len(rows) >= limit:
            break
    return rows


def extract_host_artifact_signals(result_text: str, *, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    text = str(result_text or "")
    lower = text.lower()
    path_hits = re.findall(
        r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._@%+=:,~-]+/)*[A-Za-z0-9._@%+=:,~-]+",
        text,
    )
    file_hits = re.findall(
        r"\b(?:docker-compose\.ya?ml|compose\.ya?ml|Dockerfile|Containerfile|package\.json|"
        r"pyproject\.toml|requirements\.txt|Pipfile|poetry\.lock|pnpm-lock\.yaml|yarn\.lock|"
        r"package-lock\.json|go\.mod|Cargo\.toml|Gemfile|Makefile|\.env\.example)\b",
        text,
        flags=re.IGNORECASE,
    )
    service_hits = re.findall(r"\b([A-Za-z0-9_.@-]+\.service)\b", text)
    port_hits = re.findall(r"(?:(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]|::|\*)[: ]+)?\b([1-9][0-9]{1,4})\b", text)
    ports = [port for port in port_hits if 1 <= int(port) <= 65535]
    health_terms = [
        term
        for term in ("healthy", "unhealthy", "running", "exited", "failed", "active", "inactive", "listening")
        if term in lower
    ]
    package_terms = [
        term
        for term in ("apt", "dpkg", "pip", "npm", "pnpm", "yarn", "docker", "compose", "systemctl", "systemd")
        if re.search(rf"\b{re.escape(term)}\b", lower)
    ]
    payload_data = dict(payload or {})
    connection_ref = _clean_text(payload_data.get("connection_ref"), limit=160)
    connection_kind = _clean_text(payload_data.get("connection_kind"), limit=120)
    capability = _clean_text(payload_data.get("capability"), limit=120)
    return {
        "paths": _unique(path_hits),
        "files": _unique(file_hits),
        "services": _unique(service_hits),
        "ports": _unique(ports),
        "health_terms": _unique(health_terms),
        "package_terms": _unique(package_terms),
        "connection_ref": connection_ref,
        "connection_kind": connection_kind,
        "capability": capability,
        "has_signal": bool(path_hits or file_hits or service_hits or ports or health_terms or package_terms),
    }


def _path_parent(path: str) -> str:
    try:
        parent = str(PurePosixPath(path).parent)
    except Exception:
        return ""
    return parent if parent and parent != "." else ""


def _infer_app_root(paths: list[str]) -> str:
    parents = [_path_parent(path) for path in paths if _path_parent(path)]
    if not parents:
        return ""
    counts: dict[str, int] = {}
    for parent in parents:
        counts[parent] = counts.get(parent, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], len(item[0]), item[0]))[0][0]


def build_app_identity_hypothesis(signals: Mapping[str, Any]) -> dict[str, Any]:
    files = [str(item) for item in list(signals.get("files", []) or [])]
    paths = [str(item) for item in list(signals.get("paths", []) or [])]
    services = [str(item) for item in list(signals.get("services", []) or [])]
    ports = [str(item) for item in list(signals.get("ports", []) or [])]
    health_terms = [str(item) for item in list(signals.get("health_terms", []) or [])]
    package_terms = [str(item) for item in list(signals.get("package_terms", []) or [])]
    lowered_files = {item.lower() for item in files}
    lowered_packages = {item.lower() for item in package_terms}
    if {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"} & lowered_files or "compose" in lowered_packages:
        runtime_kind = "docker_compose"
    elif services or "systemd" in lowered_packages or "systemctl" in lowered_packages:
        runtime_kind = "systemd"
    elif "package.json" in lowered_files or {"npm", "pnpm", "yarn"} & lowered_packages:
        runtime_kind = "node"
    elif {"pyproject.toml", "requirements.txt", "pipfile"} & lowered_files or "pip" in lowered_packages:
        runtime_kind = "python"
    elif "dockerfile" in lowered_files or "containerfile" in lowered_files or "docker" in lowered_packages:
        runtime_kind = "container_image"
    else:
        runtime_kind = "unknown"
    app_root = _infer_app_root(paths)
    entry_artifacts = _unique([*paths, *files], limit=16)
    health_surfaces = _unique(
        [*(f"service:{item}" for item in services), *(f"port:{item}" for item in ports), *(f"health:{item}" for item in health_terms)],
        limit=16,
    )
    install_update_surfaces = _unique(
        [
            *(f"file:{item}" for item in files),
            *(f"tool:{item}" for item in package_terms),
            *(["docker compose up -d"] if runtime_kind == "docker_compose" else []),
            *(["systemctl restart <service>"] if runtime_kind == "systemd" and services else []),
            *(["npm install/build"] if runtime_kind == "node" else []),
            *(["pip install"] if runtime_kind == "python" else []),
        ],
        limit=16,
    )
    rollback_surfaces = _unique(
        [
            *(f"backup:{item}" for item in paths if item.lower().endswith((".yml", ".yaml", "dockerfile", "containerfile", "package.json", "pyproject.toml", "requirements.txt"))),
            *(f"service:{item}" for item in services),
            *(["record current container image/tag"] if runtime_kind in {"docker_compose", "container_image"} else []),
            *(["record current package versions"] if runtime_kind in {"node", "python"} else []),
        ],
        limit=16,
    )
    confidence = "medium" if runtime_kind != "unknown" and (entry_artifacts or health_surfaces) else "low"
    return {
        "runtime_kind": runtime_kind,
        "app_root": app_root,
        "entry_artifacts": entry_artifacts,
        "health_surfaces": health_surfaces,
        "install_update_surfaces": install_update_surfaces,
        "rollback_surfaces": rollback_surfaces,
        "confidence": confidence,
    }


def host_artifact_discovery_outcome_events(
    *,
    message: str,
    user_id: str,
    result_text: str,
    payload: Mapping[str, Any] | None = None,
    artifact_review_patterns: list[Mapping[str, Any]] | None = None,
    request_id: str = "",
    session_id: str = "",
) -> list[dict[str, Any]]:
    signals = extract_host_artifact_signals(result_text, payload=payload)
    if not signals.get("has_signal"):
        return []
    app_identity = build_app_identity_hypothesis(signals)
    plan_draft = build_install_update_plan_draft(app_identity)
    plan_validation = validate_install_update_plan_draft(plan_draft)
    health_check_drafts = build_health_check_drafts(plan_draft)
    regression_drafts = build_regression_drafts(plan_draft, plan_validation)
    pytest_skeleton_proposal = build_pytest_skeleton_proposal(
        regression_drafts=regression_drafts,
        plan_validation=plan_validation,
        app_identity=app_identity,
        artifact_review_patterns=artifact_review_patterns,
    )
    evidence = {
        "user_message": _clean_text(message, limit=900),
        "outcome": "host_artifacts_observed",
        "observed_paths": signals["paths"],
        "observed_files": signals["files"],
        "observed_services": signals["services"],
        "observed_ports": signals["ports"],
        "health_terms": signals["health_terms"],
        "package_terms": signals["package_terms"],
        "connection_ref": signals["connection_ref"],
        "connection_kind": signals["connection_kind"],
        "capability": signals["capability"],
        "app_identity_hypothesis": app_identity,
        "install_update_plan_draft": plan_draft,
        "install_update_plan_validation": plan_validation,
        "health_check_drafts": health_check_drafts,
        "regression_drafts": regression_drafts,
        "pytest_skeleton_proposal": pytest_skeleton_proposal,
        "artifact_review_patterns": list(artifact_review_patterns or [])[:6],
        "result_excerpt": _clean_text(result_text, limit=1000),
    }
    events = [
        {
            "event_type": "runtime_outcome",
            "artifact_type": "app_artifact_candidate",
            "status": "observed_signal",
            "risk": "low",
            "user_id": user_id,
            "source": "host_artifact_discovery",
            "request_id": request_id,
            "session_id": session_id,
            "summary": "Runtime output exposed host/application artifacts that can become review-only app inventory.",
            "evidence": evidence,
            "metadata": {
                "review_only": True,
                "promotion_allowed": False,
                "candidate_family": "host_app_artifacts",
            },
        }
    ]
    if app_identity["runtime_kind"] != "unknown" or app_identity["app_root"]:
        events.append(
            {
                "event_type": "runtime_outcome",
                "artifact_type": "app_identity_candidate",
                "status": "observed_signal",
                "risk": "low",
                "user_id": user_id,
                "source": "host_artifact_discovery",
                "request_id": request_id,
                "session_id": session_id,
                "summary": "Observed host artifacts can form a review-only application identity hypothesis.",
                "evidence": evidence,
                "metadata": {
                    "review_only": True,
                    "promotion_allowed": False,
                    "candidate_family": "host_app_identity",
                    "runtime_kind": app_identity["runtime_kind"],
                    "app_root": app_identity["app_root"],
                },
            }
        )
    if signals["services"] or signals["ports"] or signals["health_terms"]:
        events.append(
            {
                "event_type": "runtime_outcome",
                "artifact_type": "health_check_candidate",
                "status": "observed_signal",
                "risk": "low",
                "user_id": user_id,
                "source": "host_artifact_discovery",
                "request_id": request_id,
                "session_id": session_id,
                "summary": "Runtime output exposed services, ports, or health terms that can become review-only health checks.",
                "evidence": evidence,
                "metadata": {
                    "review_only": True,
                    "promotion_allowed": False,
                    "candidate_family": "host_health_checks",
                },
            }
        )
    if signals["files"] or signals["package_terms"]:
        events.append(
            {
                "event_type": "runtime_outcome",
                "artifact_type": "install_plan_candidate",
                "status": "observed_signal",
                "risk": "medium",
                "user_id": user_id,
                "source": "host_artifact_discovery",
                "request_id": request_id,
                "session_id": session_id,
                "summary": "Runtime output exposed install/update relevant artifacts for a review-only plan candidate.",
                "evidence": evidence,
                "metadata": {
                    "review_only": True,
                    "promotion_allowed": False,
                    "candidate_family": "host_install_update_plans",
                    "plan_kind": plan_draft["plan_kind"],
                    "runtime_kind": plan_draft["runtime_kind"],
                    "requires_confirmation": True,
                    "validation_state": plan_validation["validation_state"],
                    "risk_level": plan_validation["risk_level"],
                    "health_check_draft_count": len(health_check_drafts),
                    "regression_draft_count": len(regression_drafts),
                    "pytest_skeleton_proposal": pytest_skeleton_proposal["proposal_kind"],
                },
            }
        )
    return events
