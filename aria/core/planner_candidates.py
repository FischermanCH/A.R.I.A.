from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from aria.core.action_candidate_taxonomy import normalize_action_candidate_kind
from aria.core.recipe_candidate_view import recipe_candidate_metadata

if TYPE_CHECKING:
    from aria.core.action_planner import ActionPlanCandidate
    from aria.core.connection_semantic_resolver import SemanticConnectionCandidate


@dataclass(slots=True)
class PlannerCandidate:
    candidate_type: str
    candidate_id: str
    title: str = ""
    summary: str = ""
    connection_kind: str = ""
    capability: str = ""
    intent: str = ""
    preview: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    router_keywords: list[str] = field(default_factory=list)
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        return (normalize_action_candidate_kind(str(self.candidate_type or "").strip().lower()), str(self.candidate_id or "").strip())


@dataclass(slots=True)
class PlannerInputSet:
    query: str
    language: str = ""
    preferred_connection_kind: str = ""
    connection_ref: str = ""
    connection_candidates: list[PlannerCandidate] = field(default_factory=list)
    action_candidates: list[PlannerCandidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    session_context: dict[str, str] = field(default_factory=dict)


def planner_candidate_from_connection(candidate: "SemanticConnectionCandidate") -> PlannerCandidate:
    return PlannerCandidate(
        candidate_type="connection",
        candidate_id=str(candidate.connection_ref or "").strip(),
        title=str(candidate.connection_ref or "").strip(),
        summary=str(candidate.note or "").strip(),
        connection_kind=str(candidate.connection_kind or "").strip().lower(),
        preview=f"{str(candidate.connection_kind or '').strip().lower()}/{str(candidate.connection_ref or '').strip()}",
        source=str(candidate.source or "").strip(),
        score=float(candidate.score or 0.0),
        metadata={
            "alias": str(candidate.alias or "").strip(),
            "note": str(candidate.note or "").strip(),
        },
    )


def planner_candidate_from_action(candidate: "ActionPlanCandidate") -> PlannerCandidate:
    return PlannerCandidate(
        candidate_type=normalize_action_candidate_kind(str(candidate.candidate_kind or "").strip().lower()),
        candidate_id=str(candidate.candidate_id or "").strip(),
        title=str(candidate.title or "").strip(),
        summary=str(candidate.summary or "").strip(),
        connection_kind=str(candidate.connection_kind or "").strip().lower(),
        capability=str(candidate.capability or "").strip().lower(),
        intent=str(candidate.intent or "").strip().lower(),
        preview=str(candidate.preview or "").strip(),
        inputs=dict(candidate.inputs or {}),
        router_keywords=list(candidate.router_keywords or []),
        source=str(candidate.source or "").strip(),
        score=float(candidate.score or 0.0),
        metadata={
            "plan_class": str(getattr(candidate, "plan_class", "") or "").strip(),
            "behavior_profile": str(getattr(candidate, "behavior_profile", "") or "").strip(),
            **recipe_candidate_metadata(candidate),
        },
    )


def planner_candidate_from_connection_payload(payload: dict[str, Any]) -> PlannerCandidate:
    return PlannerCandidate(
        candidate_type="connection",
        candidate_id=str(payload.get("connection_ref", "") or payload.get("ref", "") or "").strip(),
        title=str(payload.get("title", "") or payload.get("connection_ref", "") or payload.get("ref", "") or "").strip(),
        summary=str(payload.get("note", "") or payload.get("reason", "") or "").strip(),
        connection_kind=str(payload.get("connection_kind", "") or payload.get("kind", "") or "").strip().lower(),
        preview=str(payload.get("preview", "") or "").strip()
        or f"{str(payload.get('connection_kind', '') or payload.get('kind', '')).strip().lower()}/{str(payload.get('connection_ref', '') or payload.get('ref', '')).strip()}",
        source=str(payload.get("source", "") or "").strip(),
        score=float(payload.get("score", 0.0) or 0.0),
        metadata={
            "alias": str(payload.get("alias", "") or "").strip(),
            "note": str(payload.get("note", "") or payload.get("reason", "") or "").strip(),
        },
    )


def planner_candidate_from_action_payload(payload: dict[str, Any]) -> PlannerCandidate:
    return PlannerCandidate(
        candidate_type=normalize_action_candidate_kind(str(payload.get("candidate_kind", "") or "").strip().lower()),
        candidate_id=str(payload.get("candidate_id", "") or "").strip(),
        title=str(payload.get("title", "") or "").strip(),
        summary=str(payload.get("summary", "") or "").strip(),
        connection_kind=str(payload.get("connection_kind", "") or "").strip().lower(),
        capability=str(payload.get("capability", "") or "").strip().lower(),
        intent=str(payload.get("intent", "") or "").strip().lower(),
        preview=str(payload.get("preview", "") or "").strip(),
        inputs=dict(payload.get("inputs", {}) or {}),
        router_keywords=[str(item or "").strip() for item in list(payload.get("router_keywords", []) or []) if str(item or "").strip()],
        source=str(payload.get("source", "") or "").strip(),
        score=float(payload.get("score", 0.0) or 0.0),
        metadata={
            "candidate_kind_label": str(payload.get("candidate_kind_label", "") or "").strip(),
            "intent_label": str(payload.get("intent_label", "") or "").strip(),
            "capability_label": str(payload.get("capability_label", "") or "").strip(),
            "plan_class": str(payload.get("plan_class", "") or "").strip(),
            "behavior_profile": str(payload.get("behavior_profile", "") or "").strip(),
            **recipe_candidate_metadata(payload),
        },
    )


def build_planner_input_set(
    *,
    query: str,
    language: str = "",
    preferred_connection_kind: str = "",
    connection_ref: str = "",
    connection_candidates: list[PlannerCandidate] | None = None,
    action_candidates: list[PlannerCandidate] | None = None,
    notes: list[str] | None = None,
    session_context: dict[str, str] | None = None,
) -> PlannerInputSet:
    return PlannerInputSet(
        query=str(query or "").strip(),
        language=str(language or "").strip(),
        preferred_connection_kind=str(preferred_connection_kind or "").strip().lower(),
        connection_ref=str(connection_ref or "").strip(),
        connection_candidates=list(connection_candidates or []),
        action_candidates=list(action_candidates or []),
        notes=[str(item or "").strip() for item in list(notes or []) if str(item or "").strip()],
        session_context={
            str(key or "").strip(): str(value or "").strip()
            for key, value in dict(session_context or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        },
    )


def build_connection_planner_input_set(
    *,
    query: str,
    language: str = "",
    preferred_connection_kind: str = "",
    connection_ref: str = "",
    connection_candidates: list["SemanticConnectionCandidate"] | list[PlannerCandidate] | None = None,
    notes: list[str] | None = None,
    session_context: dict[str, str] | None = None,
) -> PlannerInputSet:
    normalized: list[PlannerCandidate] = []
    for candidate in list(connection_candidates or []):
        if isinstance(candidate, PlannerCandidate):
            normalized.append(candidate)
        else:
            normalized.append(planner_candidate_from_connection(candidate))
    return build_planner_input_set(
        query=query,
        language=language,
        preferred_connection_kind=preferred_connection_kind,
        connection_ref=connection_ref,
        connection_candidates=normalized,
        notes=notes,
        session_context=session_context,
    )


def merge_planner_input_sets(
    *input_sets: PlannerInputSet,
    query: str = "",
    language: str = "",
    preferred_connection_kind: str = "",
    connection_ref: str = "",
    notes: list[str] | None = None,
    session_context: dict[str, str] | None = None,
) -> PlannerInputSet:
    merged_query = str(query or "").strip() or next((item.query for item in input_sets if str(item.query or "").strip()), "")
    merged_language = str(language or "").strip() or next((item.language for item in input_sets if str(item.language or "").strip()), "")
    merged_kind = str(preferred_connection_kind or "").strip().lower() or next(
        (item.preferred_connection_kind for item in input_sets if str(item.preferred_connection_kind or "").strip()),
        "",
    )
    merged_ref = str(connection_ref or "").strip() or next((item.connection_ref for item in input_sets if str(item.connection_ref or "").strip()), "")

    connection_candidates: list[PlannerCandidate] = []
    action_candidates: list[PlannerCandidate] = []
    seen_connections: set[tuple[str, str]] = set()
    seen_actions: set[tuple[str, str]] = set()
    merged_notes: list[str] = []
    merged_session_context: dict[str, str] = {}

    def _push_note(value: str) -> None:
        clean = str(value or "").strip()
        if clean and clean not in merged_notes:
            merged_notes.append(clean)

    for input_set in input_sets:
        for note in list(input_set.notes or []):
            _push_note(note)
        for key, value in dict(input_set.session_context or {}).items():
            clean_key = str(key or "").strip()
            clean_value = str(value or "").strip()
            if clean_key and clean_value and clean_key not in merged_session_context:
                merged_session_context[clean_key] = clean_value
        for candidate in list(input_set.connection_candidates or []):
            if candidate.key in seen_connections:
                continue
            seen_connections.add(candidate.key)
            connection_candidates.append(candidate)
        for candidate in list(input_set.action_candidates or []):
            if candidate.key in seen_actions:
                continue
            seen_actions.add(candidate.key)
            action_candidates.append(candidate)

    for note in list(notes or []):
        _push_note(note)
    for key, value in dict(session_context or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if clean_key and clean_value:
            merged_session_context[clean_key] = clean_value

    return build_planner_input_set(
        query=merged_query,
        language=merged_language,
        preferred_connection_kind=merged_kind,
        connection_ref=merged_ref,
        connection_candidates=connection_candidates,
        action_candidates=action_candidates,
        notes=merged_notes,
        session_context=merged_session_context,
    )


def planner_candidate_to_dict(candidate: PlannerCandidate) -> dict[str, Any]:
    return {
        "candidate_type": str(candidate.candidate_type or "").strip(),
        "candidate_id": str(candidate.candidate_id or "").strip(),
        "title": str(candidate.title or "").strip(),
        "summary": str(candidate.summary or "").strip(),
        "connection_kind": str(candidate.connection_kind or "").strip(),
        "capability": str(candidate.capability or "").strip(),
        "intent": str(candidate.intent or "").strip(),
        "preview": str(candidate.preview or "").strip(),
        "inputs": dict(candidate.inputs or {}),
        "router_keywords": list(candidate.router_keywords or []),
        "source": str(candidate.source or "").strip(),
        "score": float(candidate.score or 0.0),
        "metadata": dict(candidate.metadata or {}),
    }


def planner_input_set_to_dict(input_set: PlannerInputSet) -> dict[str, Any]:
    return {
        "query": str(input_set.query or "").strip(),
        "language": str(input_set.language or "").strip(),
        "preferred_connection_kind": str(input_set.preferred_connection_kind or "").strip(),
        "connection_ref": str(input_set.connection_ref or "").strip(),
        "connection_candidates": [planner_candidate_to_dict(candidate) for candidate in list(input_set.connection_candidates or [])],
        "action_candidates": [planner_candidate_to_dict(candidate) for candidate in list(input_set.action_candidates or [])],
        "notes": [str(item or "").strip() for item in list(input_set.notes or []) if str(item or "").strip()],
        "session_context": {
            str(key or "").strip(): str(value or "").strip()
            for key, value in dict(input_set.session_context or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        },
    }
