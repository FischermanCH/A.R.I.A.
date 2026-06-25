from __future__ import annotations

import re
from collections.abc import Mapping
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


def _safe_test_name(value: Any, *, fallback: str) -> str:
    raw = _clean_text(value, limit=120).lower()
    clean = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    if not clean:
        clean = fallback
    if not clean.startswith("test_"):
        clean = f"test_{clean}"
    return clean[:120]


def build_pytest_skeleton_proposal(
    *,
    regression_drafts: list[Mapping[str, Any]] | None,
    plan_validation: Mapping[str, Any] | None = None,
    app_identity: Mapping[str, Any] | None = None,
    artifact_review_patterns: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    validation = dict(plan_validation or {})
    identity = dict(app_identity or {})
    runtime_kind = _clean_text(identity.get("runtime_kind") or "unknown", limit=80).lower()
    app_root = _clean_text(identity.get("app_root"), limit=240)
    drafts = [dict(item) for item in _clean_list(regression_drafts or [], limit=8) if isinstance(item, Mapping)]
    test_functions: list[dict[str, Any]] = []
    for index, draft in enumerate(drafts, start=1):
        name = _safe_test_name(draft.get("name"), fallback=f"generated_app_plan_case_{index}")
        expected = _clean_text(draft.get("expected"), limit=500)
        test_functions.append(
            {
                "name": name,
                "test_kind": _clean_text(draft.get("test_kind"), limit=80),
                "arrange": [
                    "build a representative app identity hypothesis",
                    "build an install/update plan draft from the hypothesis",
                    "validate the draft without executing runtime commands",
                ],
                "act": "call the draft/validation helper under test",
                "assert": [
                    expected or "expected behavior from regression draft is satisfied",
                    "runtime_activation_allowed is false",
                    "promotion_allowed is false when validation data is present",
                ],
                "fixtures": ["app_identity_payload", "install_update_plan_draft"],
                "mutating": False,
            }
        )
    if not test_functions:
        test_functions.append(
            {
                "name": "test_generated_app_plan_requires_regression_drafts",
                "test_kind": "proposal_guard",
                "arrange": ["build an empty regression draft list"],
                "act": "build pytest skeleton proposal",
                "assert": ["proposal remains review-only", "write_allowed is false"],
                "fixtures": [],
                "mutating": False,
            }
        )
    safety_notes = [
        "proposal only, do not write files automatically",
        "tests must not execute install/update commands",
        "tests should assert preview/gate behavior only",
    ]
    if validation.get("validation_state") == "blocked":
        safety_notes.append("blocked plans should generate blocker/gate tests, not execution tests")
    patterns = [
        {
            "pattern_type": _clean_text(pattern.get("pattern_type"), limit=80),
            "effect": _clean_text(pattern.get("effect"), limit=40),
            "summary": _clean_text(pattern.get("summary"), limit=500),
            "expected_behavior": _clean_text(pattern.get("expected_behavior"), limit=500),
            "collection": _clean_text(pattern.get("collection"), limit=160),
            "point_id": _clean_text(pattern.get("point_id"), limit=160),
            "score": float(pattern.get("score", 0.0) or 0.0),
            "runtime_activation_allowed": False,
            "write_allowed": False,
        }
        for pattern in _clean_list(artifact_review_patterns or [], limit=6)
        if isinstance(pattern, Mapping)
    ]
    if patterns:
        safety_notes.append("artifact review patterns are weak guidance only, not write or runtime permission")
    return {
        "proposal_kind": "pytest_skeleton_proposal",
        "target_file": "tests/test_app_plan_generated.py",
        "runtime_kind": runtime_kind,
        "app_root": app_root,
        "test_functions": test_functions,
        "required_fixtures": sorted({fixture for item in test_functions for fixture in list(item.get("fixtures", []) or [])}),
        "safety_notes": safety_notes,
        "validation_state": _clean_text(validation.get("validation_state") or "unknown", limit=80),
        "artifact_review_patterns": patterns,
        "artifact_review_pattern_count": len(patterns),
        "write_allowed": False,
        "runtime_activation_allowed": False,
    }
