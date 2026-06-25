from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMOTABLE_LEARNING_TYPES = {"source_rule_candidate", "routing_hint"}
PROMOTABLE_RISKS = {"low"}
ACTIVE_HINT_MEMORY_TYPE = "learning_active_hint"
ACTIVE_HINT_RUNTIME_EFFECT = "weak_signal_only"


def _clean_text(value: Any, *, limit: int = 400) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _valid_regression_ref(value: str) -> bool:
    clean = str(value or "").strip()
    return clean.startswith("tests/") and ".py::" in clean and not any(char.isspace() for char in clean)


def learning_candidate_field_from_text(text: str, field: str) -> str:
    clean_field = re.escape(str(field or "").strip())
    if not clean_field:
        return ""
    match = re.search(rf"(?im)^\s*{clean_field}\s*:\s*(.+?)\s*$", str(text or ""))
    return _clean_text(match.group(1), limit=160).lower() if match else ""


def learning_candidate_gate_inputs(candidate: Mapping[str, Any]) -> dict[str, str]:
    text = str(candidate.get("text", "") or "")
    artifact_type = _clean_text(
        candidate.get("artifact_type")
        or candidate.get("candidate_type")
        or learning_candidate_field_from_text(text, "Type"),
        limit=120,
    ).lower()
    risk = _clean_text(candidate.get("risk") or learning_candidate_field_from_text(text, "Risk") or "medium", limit=80).lower()
    return {"artifact_type": artifact_type, "risk": risk}


def learning_candidate_promotion_gate(
    *,
    artifact_type: str,
    risk: str,
    decision: str,
    reviewed_by: str,
) -> dict[str, Any]:
    clean_decision = _clean_text(decision, limit=40).lower()
    clean_artifact_type = _clean_text(artifact_type, limit=120).lower()
    clean_risk = _clean_text(risk or "medium", limit=80).lower()
    now = datetime.now(timezone.utc).isoformat()
    if clean_decision == "reject":
        return {
            "promotion_state": "rejected",
            "promotion_gate_result": "rejected",
            "promotion_gate_reason": "candidate_rejected_by_reviewer",
            "promotion_gate_checked_at": now,
            "promotion_gate_checked_by": _clean_text(reviewed_by, limit=120),
            "runtime_activation_allowed": False,
        }
    if clean_decision != "review":
        return {
            "promotion_state": "blocked",
            "promotion_gate_result": "blocked",
            "promotion_gate_reason": "invalid_review_decision",
            "promotion_gate_checked_at": now,
            "promotion_gate_checked_by": _clean_text(reviewed_by, limit=120),
            "runtime_activation_allowed": False,
        }
    if clean_artifact_type in PROMOTABLE_LEARNING_TYPES and clean_risk in PROMOTABLE_RISKS:
        return {
            "promotion_state": "eligible",
            "promotion_gate_result": "eligible",
            "promotion_gate_reason": "low_risk_candidate_reviewed",
            "promotion_gate_checked_at": now,
            "promotion_gate_checked_by": _clean_text(reviewed_by, limit=120),
            "runtime_activation_allowed": False,
        }
    return {
        "promotion_state": "reviewed_blocked",
        "promotion_gate_result": "blocked",
        "promotion_gate_reason": "only_low_risk_source_rules_and_routing_hints_are_promotable",
        "promotion_gate_checked_at": now,
        "promotion_gate_checked_by": _clean_text(reviewed_by, limit=120),
        "runtime_activation_allowed": False,
    }


def learning_candidate_apply_allowed(*, artifact_type: str, risk: str, promotion_state: str) -> bool:
    return (
        _clean_text(artifact_type, limit=120).lower() in PROMOTABLE_LEARNING_TYPES
        and _clean_text(risk or "medium", limit=80).lower() in PROMOTABLE_RISKS
        and _clean_text(promotion_state, limit=80).lower() == "eligible"
    )


def learning_candidate_apply_preview_allowed(*, artifact_type: str, risk: str, apply_state: str) -> bool:
    return (
        _clean_text(artifact_type, limit=120).lower() in PROMOTABLE_LEARNING_TYPES
        and _clean_text(risk or "medium", limit=80).lower() in PROMOTABLE_RISKS
        and _clean_text(apply_state, limit=80).lower() == "prepared"
    )


def prepare_learning_candidate_apply_payload(
    *,
    artifact_type: str,
    risk: str,
    promotion_state: str,
    candidate_text: str,
    applied_by: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    clean_artifact_type = _clean_text(artifact_type, limit=120).lower()
    clean_risk = _clean_text(risk or "medium", limit=80).lower()
    if not learning_candidate_apply_allowed(
        artifact_type=clean_artifact_type,
        risk=clean_risk,
        promotion_state=promotion_state,
    ):
        return {
            "apply_state": "blocked",
            "apply_gate_result": "blocked",
            "apply_gate_reason": "candidate_not_eligible_for_low_risk_apply_prepare",
            "apply_prepared_at": now,
            "apply_prepared_by": _clean_text(applied_by, limit=120),
            "runtime_activation_allowed": False,
        }
    return {
        "apply_state": "prepared",
        "apply_gate_result": "prepared",
        "apply_gate_reason": "eligible_low_risk_candidate_prepared_for_admin_apply",
        "apply_prepared_at": now,
        "apply_prepared_by": _clean_text(applied_by, limit=120),
        "apply_candidate_type": clean_artifact_type,
        "apply_candidate_risk": clean_risk,
        "apply_requires_regression": True,
        "regression_required": True,
        "regression_status": "missing",
        "regression_ref": "",
        "apply_runtime_effect": "none",
        "apply_review_text": _clean_text(candidate_text, limit=1200),
        "runtime_activation_allowed": False,
    }


def link_learning_candidate_regression_payload(
    *,
    regression_ref: str,
    linked_by: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    clean_ref = _clean_text(regression_ref, limit=240)
    if not _valid_regression_ref(clean_ref):
        return {
            "regression_required": True,
            "regression_status": "missing",
            "regression_ref": "",
            "regression_link_result": "invalid",
            "regression_link_reason": "expected_tests_py_test_ref",
            "regression_link_checked_at": now,
            "regression_link_checked_by": _clean_text(linked_by, limit=120),
            "runtime_activation_allowed": False,
        }
    return {
        "regression_required": True,
        "regression_status": "linked",
        "regression_ref": clean_ref,
        "regression_link_result": "linked",
        "regression_link_reason": "admin_linked_regression_test",
        "regression_linked_at": now,
        "regression_linked_by": _clean_text(linked_by, limit=120),
        "runtime_activation_allowed": False,
    }


def verify_learning_candidate_regression_payload(
    *,
    regression_ref: str,
    repo_root: str | Path,
    verified_by: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    clean_ref = _clean_text(regression_ref, limit=240)
    base = {
        "regression_required": True,
        "regression_ref": clean_ref if _valid_regression_ref(clean_ref) else "",
        "regression_verified_at": now,
        "regression_verified_by": _clean_text(verified_by, limit=120),
        "runtime_activation_allowed": False,
    }
    if not _valid_regression_ref(clean_ref):
        return {
            **base,
            "regression_status": "missing",
            "regression_verified": False,
            "regression_test_exists": False,
            "regression_verify_result": "missing",
            "regression_verify_reason": "invalid_test_ref",
        }
    path_part, _, test_name = clean_ref.partition("::")
    test_path = (Path(repo_root) / path_part).resolve()
    root_path = Path(repo_root).resolve()
    try:
        test_path.relative_to(root_path)
    except ValueError:
        return {
            **base,
            "regression_status": "missing",
            "regression_verified": False,
            "regression_test_exists": False,
            "regression_verify_result": "missing",
            "regression_verify_reason": "test_path_outside_repo",
        }
    if not test_path.exists() or not test_path.is_file():
        return {
            **base,
            "regression_status": "linked",
            "regression_verified": False,
            "regression_test_exists": False,
            "regression_verify_result": "missing",
            "regression_verify_reason": "test_file_missing",
        }
    try:
        source = test_path.read_text(encoding="utf-8")
    except OSError:
        source = ""
    if not test_name or re.search(rf"(?m)^\s*def\s+{re.escape(test_name)}\s*\(", source) is None:
        return {
            **base,
            "regression_status": "linked",
            "regression_verified": False,
            "regression_test_exists": False,
            "regression_verify_result": "missing",
            "regression_verify_reason": "test_name_missing",
        }
    return {
        **base,
        "regression_status": "linked",
        "regression_verified": True,
        "regression_test_exists": True,
        "regression_verify_result": "not_run",
        "regression_verify_reason": "test_ref_found_not_executed",
    }


def run_learning_candidate_regression_payload(
    *,
    regression_ref: str,
    repo_root: str | Path,
    run_by: str,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    root_path = Path(repo_root).resolve()
    verify_payload = verify_learning_candidate_regression_payload(
        regression_ref=regression_ref,
        repo_root=root_path,
        verified_by=run_by,
    )
    now = datetime.now(timezone.utc).isoformat()
    base = {
        **verify_payload,
        "regression_last_run_at": now,
        "regression_last_run_by": _clean_text(run_by, limit=120),
        "runtime_activation_allowed": False,
    }
    if verify_payload.get("regression_verified") is not True:
        return {
            **base,
            "regression_verify_result": str(verify_payload.get("regression_verify_result") or "missing"),
            "regression_last_run_output": _clean_text(str(verify_payload.get("regression_verify_reason") or ""), limit=1200),
        }
    pytest_bin = root_path / ".venv" / "bin" / "pytest"
    command = [str(pytest_bin) if pytest_bin.exists() else "pytest", str(regression_ref).strip(), "-q"]
    try:
        completed = subprocess.run(
            command,
            cwd=str(root_path),
            check=False,
            capture_output=True,
            text=True,
            timeout=max(5, min(int(timeout_seconds or 60), 300)),
        )
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(part for part in [exc.stdout or "", exc.stderr or ""] if part).strip()
        return {
            **base,
            "regression_verify_result": "failed",
            "regression_verify_reason": "pytest_timeout",
            "regression_last_run_output": _clean_text(output or "pytest timed out", limit=2000),
            "regression_run_returncode": -1,
        }
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    passed = completed.returncode == 0
    return {
        **base,
        "regression_verify_result": "passed" if passed else "failed",
        "regression_verify_reason": "pytest_passed" if passed else "pytest_failed",
        "regression_last_run_output": _clean_text(output, limit=2000),
        "regression_run_returncode": int(completed.returncode),
    }


def build_learning_candidate_apply_preview(
    *,
    artifact_type: str,
    risk: str,
    apply_state: str,
    candidate_text: str,
    collection: str = "",
    point_id: str = "",
    regression_status: str = "",
    regression_ref: str = "",
    regression_verified: Any = False,
    regression_verify_result: str = "",
    regression_verify_reason: str = "",
) -> dict[str, Any]:
    clean_artifact_type = _clean_text(artifact_type, limit=120).lower()
    clean_risk = _clean_text(risk or "medium", limit=80).lower()
    allowed = learning_candidate_apply_preview_allowed(
        artifact_type=clean_artifact_type,
        risk=clean_risk,
        apply_state=apply_state,
    )
    clean_regression_status = _clean_text(regression_status or "missing", limit=80).lower()
    if clean_regression_status not in {"missing", "linked"}:
        clean_regression_status = "missing"
    clean_regression_ref = _clean_text(regression_ref, limit=240)
    clean_verify_result = _clean_text(regression_verify_result or "not_run", limit=80).lower()
    clean_verify_reason = _clean_text(regression_verify_reason, limit=160)
    is_verified = str(regression_verified).strip().lower() in {"1", "true", "yes", "on"} or regression_verified is True
    title = learning_candidate_field_from_text(candidate_text, "Learning Candidate") or _clean_text(candidate_text, limit=120)
    summary = learning_candidate_field_from_text(candidate_text, "Summary") or _clean_text(candidate_text, limit=500)
    expected = learning_candidate_field_from_text(candidate_text, "Expected behavior")
    if clean_artifact_type == "source_rule_candidate":
        proposed_kind = "source_rule"
        proposed_scope = "source_handling"
    elif clean_artifact_type == "routing_hint":
        proposed_kind = "routing_hint"
        proposed_scope = "turn_routing"
    else:
        proposed_kind = "unsupported"
        proposed_scope = "blocked"
    blockers = [] if allowed else ["candidate_not_prepared_or_not_low_risk"]
    if clean_regression_status != "linked":
        blockers.append("regression_missing")
    elif not is_verified:
        blockers.append("regression_not_verified")
    elif clean_verify_result != "passed":
        blockers.append("regression_not_passed")
    return {
        "allowed": allowed,
        "candidate_type": clean_artifact_type,
        "candidate_risk": clean_risk,
        "collection": _clean_text(collection, limit=180),
        "point_id": _clean_text(point_id, limit=180),
        "title": title,
        "summary": summary,
        "expected_behavior": expected,
        "proposed_kind": proposed_kind,
        "proposed_scope": proposed_scope,
        "proposed_state": "preview_only" if allowed else "blocked",
        "regression_required": True,
        "regression_status": clean_regression_status,
        "regression_ref": clean_regression_ref,
        "regression_linked": clean_regression_status == "linked" and bool(clean_regression_ref),
        "regression_verified": is_verified,
        "regression_verify_result": clean_verify_result,
        "regression_verify_reason": clean_verify_reason,
        "regression_run_allowed": is_verified and bool(clean_regression_ref),
        "runtime_activation": "disabled",
        "runtime_activation_allowed": False,
        "blockers": blockers,
        "candidate_text": _clean_text(candidate_text, limit=2000),
    }


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def learning_active_hints_collection_for_user(user_id: str) -> str:
    return f"aria_learning_active_hints_{_slug_user_id(user_id)}"


def learning_candidate_activation_preflight_payload(
    *,
    artifact_type: str,
    risk: str,
    promotion_state: str,
    apply_state: str,
    regression_status: str,
    regression_verified: Any,
    regression_verify_result: str,
    checked_by: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    blockers: list[str] = []
    clean_artifact_type = _clean_text(artifact_type, limit=120).lower()
    clean_risk = _clean_text(risk or "medium", limit=80).lower()
    if clean_artifact_type not in PROMOTABLE_LEARNING_TYPES:
        blockers.append("unsupported_candidate_type")
    if clean_risk not in PROMOTABLE_RISKS:
        blockers.append("candidate_risk_not_low")
    if _clean_text(promotion_state, limit=80).lower() != "eligible":
        blockers.append("promotion_not_eligible")
    if _clean_text(apply_state, limit=80).lower() != "prepared":
        blockers.append("apply_not_prepared")
    if _clean_text(regression_status, limit=80).lower() != "linked":
        blockers.append("regression_not_linked")
    is_verified = str(regression_verified).strip().lower() in {"1", "true", "yes", "on"} or regression_verified is True
    if not is_verified:
        blockers.append("regression_not_verified")
    if _clean_text(regression_verify_result, limit=80).lower() != "passed":
        blockers.append("regression_not_passed")
    passed = not blockers
    return {
        "activation_preflight_state": "passed" if passed else "blocked",
        "activation_preflight_result": "passed" if passed else "blocked",
        "activation_preflight_reason": "all_activation_gates_passed" if passed else ",".join(blockers),
        "activation_preflight_checked_at": now,
        "activation_preflight_checked_by": _clean_text(checked_by, limit=120),
        "activation_ready": passed,
        "activation_runtime_effect": ACTIVE_HINT_RUNTIME_EFFECT,
        "activation_blockers": blockers,
        "runtime_activation_allowed": False,
    }


def build_learning_candidate_activation_preview(
    *,
    artifact_type: str,
    risk: str,
    candidate_text: str,
    collection: str = "",
    point_id: str = "",
    regression_ref: str = "",
    activation_preflight_state: str = "",
    activation_blockers: Any = None,
    user_id: str = "",
) -> dict[str, Any]:
    clean_artifact_type = _clean_text(artifact_type, limit=120).lower()
    clean_risk = _clean_text(risk or "medium", limit=80).lower()
    clean_preflight = _clean_text(activation_preflight_state, limit=80).lower()
    if isinstance(activation_blockers, list):
        blockers = [_clean_text(item, limit=120) for item in activation_blockers if _clean_text(item, limit=120)]
    elif activation_blockers:
        blockers = [_clean_text(activation_blockers, limit=300)]
    else:
        blockers = []
    if clean_preflight != "passed":
        blockers.append("activation_preflight_not_passed")
    apply_preview = build_learning_candidate_apply_preview(
        artifact_type=clean_artifact_type,
        risk=clean_risk,
        apply_state="prepared",
        candidate_text=candidate_text,
        collection=collection,
        point_id=point_id,
        regression_status="linked",
        regression_ref=regression_ref,
        regression_verified=True,
        regression_verify_result="passed",
    )
    return {
        **apply_preview,
        "activation_allowed": not blockers,
        "activation_preflight_state": clean_preflight or "missing",
        "activation_blockers": blockers,
        "active_hint_collection": learning_active_hints_collection_for_user(user_id or "web"),
        "active_hint_type": ACTIVE_HINT_MEMORY_TYPE,
        "active_hint_source_collection": _clean_text(collection, limit=180),
        "active_hint_source_point_id": _clean_text(point_id, limit=180),
        "runtime_activation": ACTIVE_HINT_RUNTIME_EFFECT if not blockers else "disabled",
        "runtime_activation_allowed": False,
    }


def build_learning_active_hint_text(preview: Mapping[str, Any]) -> str:
    kind = _clean_text(preview.get("proposed_kind"), limit=80)
    scope = _clean_text(preview.get("proposed_scope"), limit=80)
    title = _clean_text(preview.get("title"), limit=160)
    summary = _clean_text(preview.get("summary"), limit=700)
    expected = _clean_text(preview.get("expected_behavior"), limit=500)
    regression_ref = _clean_text(preview.get("regression_ref"), limit=240)
    source_collection = _clean_text(preview.get("active_hint_source_collection") or preview.get("collection"), limit=180)
    source_point = _clean_text(preview.get("active_hint_source_point_id") or preview.get("point_id"), limit=180)
    lines = [
        f"Active Learning Hint: {title or kind}",
        f"Type: {kind}",
        f"Scope: {scope}",
        f"Runtime effect: {ACTIVE_HINT_RUNTIME_EFFECT}",
        f"Summary: {summary}",
    ]
    if expected:
        lines.append(f"Expected behavior: {expected}")
    if regression_ref:
        lines.append(f"Regression: {regression_ref}")
    if source_collection or source_point:
        lines.append(f"Source candidate: {source_collection}#{source_point}")
    lines.append("Instruction: Treat this as a weak learned signal. Ignore it when the current request does not match.")
    return "\n".join(line for line in lines if line.strip())


def learning_active_hint_store_params(
    *,
    preview: Mapping[str, Any],
    user_id: str,
) -> dict[str, Any]:
    return {
        "action": "store",
        "user_id": user_id,
        "collection": learning_active_hints_collection_for_user(user_id),
        "memory_type": ACTIVE_HINT_MEMORY_TYPE,
        "source": "learning_activation",
        "text": build_learning_active_hint_text(preview),
    }
