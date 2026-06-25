from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


ARTIFACT_REVIEW_PATTERN_TYPES = {
    "artifact_pattern_candidate": "encourage",
    "artifact_improvement_candidate": "improve",
    "negative_pattern_candidate": "avoid",
}


def _clean_text(value: Any, *, limit: int = 800) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _field_from_text(text: str, field: str) -> str:
    clean_field = re.escape(str(field or "").strip())
    if not clean_field:
        return ""
    match = re.search(rf"(?im)^\s*{clean_field}\s*:\s*(.+?)\s*$", str(text or ""))
    return _clean_text(match.group(1), limit=900) if match else ""


def artifact_review_pattern_query(
    *,
    app_identity: Mapping[str, Any] | None = None,
    regression_drafts: list[Mapping[str, Any]] | None = None,
    plan_validation: Mapping[str, Any] | None = None,
) -> str:
    identity = dict(app_identity or {})
    validation = dict(plan_validation or {})
    draft_names = [
        _clean_text(item.get("name") or item.get("test_kind"), limit=120)
        for item in list(regression_drafts or [])[:6]
        if isinstance(item, Mapping)
    ]
    parts = [
        "pytest skeleton prepared artifact review pattern",
        _clean_text(identity.get("runtime_kind"), limit=100),
        _clean_text(identity.get("app_root"), limit=180),
        _clean_text(validation.get("validation_state"), limit=100),
        *draft_names,
    ]
    return " ".join(part for part in parts if part).strip()


def extract_artifact_review_patterns(rows: list[Mapping[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for row in rows:
        raw_text = str(row.get("text") or "")
        pattern_type = _field_from_text(raw_text, "Type").lower()
        if pattern_type not in ARTIFACT_REVIEW_PATTERN_TYPES:
            continue
        summary = _field_from_text(raw_text, "Summary") or _clean_text(raw_text, limit=500)
        expected = _field_from_text(raw_text, "Expected behavior")
        patterns.append(
            {
                "pattern_type": pattern_type,
                "effect": ARTIFACT_REVIEW_PATTERN_TYPES[pattern_type],
                "summary": summary,
                "expected_behavior": expected,
                "collection": _clean_text(row.get("collection"), limit=160),
                "point_id": _clean_text(row.get("id"), limit=160),
                "score": float(row.get("score", 0.0) or 0.0),
                "runtime_activation_allowed": False,
                "write_allowed": False,
            }
        )
        if len(patterns) >= limit:
            break
    return patterns


async def recall_artifact_review_patterns(
    *,
    memory_skill: Any | None,
    user_id: str,
    query: str,
    limit: int = 6,
) -> list[dict[str, Any]]:
    if memory_skill is None:
        return []
    clean_query = _clean_text(query, limit=1000)
    if not clean_query:
        return []
    search = getattr(memory_skill, "search_memories", None)
    if not callable(search):
        return []
    try:
        rows = await search(
            user_id=user_id or "web",
            query=clean_query,
            type_filter="learning_candidate",
            top_k=max(limit * 3, 12),
        )
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    return extract_artifact_review_patterns(rows, limit=limit)
