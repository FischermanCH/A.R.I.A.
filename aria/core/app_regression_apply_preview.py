from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


def _clean_text(value: Any, *, limit: int = 400) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clean_list(values: Any, *, limit: int = 16) -> list[Any]:
    if not isinstance(values, list):
        return []
    return values[:limit]


def _safe_identifier(value: Any, *, fallback: str) -> str:
    raw = _clean_text(value, limit=140).lower()
    clean = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    if not clean:
        clean = fallback
    if not clean.startswith("test_"):
        clean = f"test_{clean}"
    return clean[:140]


def _existing_test_functions(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return re.findall(r"(?m)^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", source)


def _render_test_function(test: Mapping[str, Any]) -> str:
    name = _safe_identifier(test.get("name"), fallback="generated_app_plan_case")
    arrange = [_clean_text(item, limit=240) for item in _clean_list(test.get("arrange"), limit=8)]
    assertions = [_clean_text(item, limit=240) for item in _clean_list(test.get("assert"), limit=8)]
    act = _clean_text(test.get("act") or "call the helper under test", limit=240)
    lines = [
        f"def {name}():",
        "    # Generated proposal preview only. Review before writing.",
    ]
    for item in arrange:
        lines.append(f"    # Arrange: {item}")
    lines.append(f"    # Act: {act}")
    for item in assertions:
        lines.append(f"    # Assert: {item}")
    lines.extend(
        [
            "    assert True",
            "",
        ]
    )
    return "\n".join(lines)


def build_pytest_apply_preview(
    proposal: Mapping[str, Any],
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    target_file = _clean_text(proposal.get("target_file") or "", limit=240)
    blockers: list[str] = []
    warnings: list[str] = []
    if not target_file:
        blockers.append("target_file_missing")
        target_path = root / "tests" / "test_app_plan_generated.py"
        target_file = "tests/test_app_plan_generated.py"
    else:
        target_path = (root / target_file).resolve()
    try:
        target_path.relative_to(root)
    except ValueError:
        blockers.append("target_outside_repo")
    try:
        target_path.relative_to(root / "tests")
    except ValueError:
        blockers.append("target_outside_tests")
    existing_file = target_path.exists()
    if existing_file:
        warnings.append("target_file_exists")
    test_functions = [dict(item) for item in _clean_list(proposal.get("test_functions"), limit=20) if isinstance(item, Mapping)]
    existing_functions = set(_existing_test_functions(target_path))
    proposed_names: list[str] = []
    duplicate_functions: list[str] = []
    rendered_functions: list[str] = []
    for index, test in enumerate(test_functions, start=1):
        name = _safe_identifier(test.get("name"), fallback=f"generated_app_plan_case_{index}")
        proposed_names.append(name)
        if name in existing_functions or proposed_names.count(name) > 1:
            duplicate_functions.append(name)
        rendered_functions.append(_render_test_function({**test, "name": name}))
    if duplicate_functions:
        blockers.append("duplicate_test_function")
    if proposal.get("write_allowed") is True:
        warnings.append("proposal_write_allowed_true_ignored")
    code_preview = "\n".join(
        [
            "from __future__ import annotations",
            "",
            "",
            *rendered_functions,
        ]
    ).rstrip() + "\n"
    return {
        "preview_state": "blocked" if blockers else "preview_ready",
        "target_file": target_file,
        "target_exists": existing_file,
        "test_function_names": proposed_names,
        "duplicate_functions": duplicate_functions,
        "blockers": blockers,
        "warnings": warnings,
        "code_preview": code_preview,
        "write_allowed": False,
        "runtime_activation_allowed": False,
    }


def prepare_pytest_write_payload(
    preview: Mapping[str, Any],
    *,
    prepared_by: str,
) -> dict[str, Any]:
    code_preview = str(preview.get("code_preview") or "")
    blockers = [str(item) for item in _clean_list(preview.get("blockers"), limit=20)]
    warnings = [str(item) for item in _clean_list(preview.get("warnings"), limit=20)]
    test_function_names = [str(item) for item in _clean_list(preview.get("test_function_names"), limit=20)]
    target_file = _clean_text(preview.get("target_file") or "", limit=240)
    base_payload: dict[str, Any] = {
        "pytest_write_state": "blocked",
        "pytest_write_gate_result": "blocked",
        "pytest_write_requires_review": True,
        "pytest_write_allowed": False,
        "pytest_write_prepared_at": datetime.now(timezone.utc).isoformat(),
        "pytest_write_prepared_by": _clean_text(prepared_by or "web", limit=120),
        "pytest_target_file": target_file,
        "pytest_test_functions": test_function_names,
        "pytest_write_warnings": warnings,
        "runtime_activation_allowed": False,
    }
    if code_preview:
        base_payload["pytest_code_preview_sha256"] = hashlib.sha256(code_preview.encode("utf-8")).hexdigest()
    if preview.get("preview_state") != "preview_ready":
        return {
            **base_payload,
            "pytest_write_blockers": blockers or ["preview_not_ready"],
        }
    return {
        **base_payload,
        "pytest_write_state": "prepared",
        "pytest_write_gate_result": "prepared",
        "pytest_code_preview": code_preview,
        "pytest_write_blockers": [],
    }


def prepare_prepared_artifact_review_payload(
    *,
    artifact_kind: str,
    decision: str,
    review_notes: str = "",
    reviewed_by: str,
    prepared_state: str = "",
    code_preview_sha256: str = "",
    target_file: str = "",
) -> dict[str, Any]:
    clean_decision = str(decision or "").strip().lower()
    allowed_decisions = {"accepted", "needs_changes", "rejected"}
    is_prepared = str(prepared_state or "").strip().lower() == "prepared"
    review_state = "reviewed" if clean_decision in allowed_decisions and is_prepared else "blocked"
    if clean_decision not in allowed_decisions:
        clean_decision = "invalid"
    blockers: list[str] = []
    if clean_decision == "invalid":
        blockers.append("invalid_review_decision")
    if not is_prepared:
        blockers.append("artifact_not_prepared")
    clean_kind = _clean_text(artifact_kind or "prepared_artifact", limit=120)
    clean_notes = _clean_text(review_notes, limit=1200)
    now = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "prepared_artifact_kind": clean_kind,
        "prepared_artifact_review_state": review_state,
        "prepared_artifact_review_decision": clean_decision,
        "prepared_artifact_review_notes": clean_notes,
        "prepared_artifact_reviewed_at": now,
        "prepared_artifact_reviewed_by": _clean_text(reviewed_by or "web", limit=120),
        "prepared_artifact_review_blockers": blockers,
        "prepared_artifact_review_signal": "positive" if clean_decision == "accepted" and review_state == "reviewed" else clean_decision,
        "prepared_artifact_code_preview_sha256": _clean_text(code_preview_sha256, limit=100),
        "prepared_artifact_target_file": _clean_text(target_file, limit=240),
        "pytest_write_review_state": review_state,
        "pytest_write_review_decision": clean_decision,
        "pytest_write_review_notes": clean_notes,
        "pytest_write_reviewed_at": now,
        "pytest_write_reviewed_by": _clean_text(reviewed_by or "web", limit=120),
        "pytest_write_review_blockers": blockers,
        "pytest_write_allowed": False,
        "runtime_activation_allowed": False,
    }
    return payload
