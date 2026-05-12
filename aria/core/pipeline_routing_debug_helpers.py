from __future__ import annotations

from typing import Any

from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.connection_semantic_resolver import format_routing_decision_record


def resolved_routing_chain_has_signal(resolved: dict[str, Any] | None) -> bool:
    if not isinstance(resolved, dict):
        return False
    if bool(dict(resolved.get("decision", {}) or {}).get("found")):
        return True
    if bool(dict((resolved.get("action_debug") or {}).get("decision", {}) or {}).get("found")):
        return True
    return bool(dict((resolved.get("payload_debug") or {}).get("payload", {}) or {}).get("found"))


def append_routing_record_to_resolved(
    resolved: dict[str, Any],
    record: Any,
    *,
    routing_debug_enabled: bool,
) -> dict[str, Any]:
    if not routing_debug_enabled:
        return resolved
    existing = [
        str(item or "").strip()
        for item in list(resolved.get("detail_lines", []) or [])
        if str(item or "").strip()
    ]
    additions = [line for line in format_routing_decision_record(record) if line and line not in existing]
    if additions:
        resolved["detail_lines"] = [*existing, *additions]
    return resolved


def routing_candidates_from_resolved(resolved: dict[str, Any]) -> list[SemanticConnectionCandidate]:
    qdrant = dict(resolved.get("qdrant", {}) or {})
    rows = list(qdrant.get("candidates", []) or [])
    candidates: list[SemanticConnectionCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "accepted" in row and not bool(row.get("accepted")):
            continue
        kind = normalize_connection_kind(str(row.get("kind", "") or ""))
        ref = str(row.get("ref", "") or "").strip()
        if not kind or not ref:
            continue
        try:
            score = int(round(float(row.get("score", 0.0) or 0.0) * 1000))
        except (TypeError, ValueError):
            score = 0
        candidates.append(
            SemanticConnectionCandidate(
                connection_kind=kind,
                connection_ref=ref,
                source=str(row.get("source", "") or "routing_chain"),
                note=str(row.get("reason", "") or "").strip(),
                score=score,
            )
        )
    if candidates:
        return candidates
    decision = dict(resolved.get("decision", {}) or {})
    kind = normalize_connection_kind(str(decision.get("kind", "") or ""))
    ref = str(decision.get("ref", "") or "").strip()
    if kind and ref:
        try:
            score = int(round(float(decision.get("score", 0.0) or 0.0) * 1000))
        except (TypeError, ValueError):
            score = 0
        return [
            SemanticConnectionCandidate(
                connection_kind=kind,
                connection_ref=ref,
                source=str(decision.get("source", "") or "routing_chain"),
                note=str(decision.get("reason", "") or "").strip(),
                score=score,
            )
        ]
    return []


def serialize_connection_candidates(candidates: list[SemanticConnectionCandidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in list(candidates or []):
        kind = str(candidate.connection_kind or "").strip().lower()
        ref = str(candidate.connection_ref or "").strip()
        if not kind or not ref or (kind, ref) in seen:
            continue
        seen.add((kind, ref))
        rows.append(
            {
                "connection_kind": kind,
                "connection_ref": ref,
                "source": str(candidate.source or "").strip(),
                "note": str(candidate.note or "").strip(),
                "alias": str(candidate.alias or "").strip(),
                "score": float(candidate.score or 0.0),
                "preview": f"{kind}/{ref}",
                "title": ref,
            }
        )
    return rows


def attach_connection_candidates_debug(
    resolved: dict[str, Any],
    candidates: list[SemanticConnectionCandidate],
) -> dict[str, Any]:
    clean = serialize_connection_candidates(candidates)
    if clean:
        resolved["connection_candidates_debug"] = clean
    return resolved
