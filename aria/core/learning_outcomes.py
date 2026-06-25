from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from aria.core.learning_classifier import LearningClassifier
from aria.core.learning_classifier import store_learning_candidate
from aria.core.learning_events import record_learning_event
from aria.core.learning_validator import LearningCandidateValidator
from aria.core.learning_validator import store_learning_eval
from aria.core.procedure_skill_memory import capture_procedure_skill_memory_from_outcome
from aria.core.recipe_candidate_generator import capture_recipe_candidate_from_outcome
from aria.skills.base import SkillResult


def _clean_text(value: Any, *, limit: int = 1600) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def learning_events_collection_for_user(user_id: str) -> str:
    return f"aria_learning_events_{_slug_user_id(user_id)}"


def build_learning_event_text(event: Mapping[str, Any]) -> str:
    parts = [
        f"Learning Event: {_clean_text(event.get('event_id'), limit=160)}",
        f"Type: {_clean_text(event.get('event_type'), limit=80)} / {_clean_text(event.get('artifact_type'), limit=80)}",
        f"Status: {_clean_text(event.get('status'), limit=80)}",
        f"Risk: {_clean_text(event.get('risk'), limit=80)}",
        f"Source: {_clean_text(event.get('source'), limit=120)}",
        f"Summary: {_clean_text(event.get('summary'), limit=900)}",
    ]
    evidence = event.get("evidence")
    if isinstance(evidence, dict):
        prompt = _clean_text(evidence.get("user_message") or evidence.get("query"), limit=500)
        outcome = _clean_text(evidence.get("outcome"), limit=500)
        if prompt:
            parts.append(f"User message: {prompt}")
        if outcome:
            parts.append(f"Outcome: {outcome}")
    return "\n".join(part for part in parts if part and not part.endswith(": ")).strip()


async def capture_learning_outcome(
    *,
    event: Mapping[str, Any],
    user_id: str,
    memory_skill: Any | None,
    llm_client: Any | None,
) -> dict[str, Any]:
    if memory_skill is None:
        return {"captured": False, "reason": "memory_disabled"}
    try:
        stored_event = record_learning_event(event)
    except OSError:
        stored_event = dict(event)
    event_text = build_learning_event_text(stored_event)
    event_result = await memory_skill.execute(
        query=event_text,
        params={
            "action": "store",
            "text": event_text,
            "user_id": user_id,
            "collection": learning_events_collection_for_user(user_id),
            "memory_type": "learning_event",
            "source": str(stored_event.get("source") or "learning_outcome"),
        },
    )
    if not event_result.success:
        return {"captured": False, "reason": "event_store_failed", "event": stored_event}

    candidate = await LearningClassifier(llm_client).classify(
        stored_event,
        user_id=user_id,
        source=str(stored_event.get("source") or "learning_outcome"),
    )
    if str(candidate.get("artifact_type", "")).strip().lower() == "ignore":
        return {"captured": True, "reason": "candidate_ignored", "event": stored_event}
    candidate_result = await store_learning_candidate(memory_skill=memory_skill, candidate=candidate, user_id=user_id)
    if not candidate_result.success:
        return {"captured": False, "reason": "candidate_store_failed", "event": stored_event, "candidate": candidate}
    eval_spec = await LearningCandidateValidator(llm_client).validate(
        candidate,
        user_id=user_id,
        source=str(stored_event.get("source") or "learning_outcome"),
    )
    eval_result = await store_learning_eval(memory_skill=memory_skill, eval_spec=eval_spec, user_id=user_id)
    recipe_candidate_result = await capture_recipe_candidate_from_outcome(
        event=stored_event,
        user_id=user_id,
        memory_skill=memory_skill,
    )
    procedure_skill_result = await capture_procedure_skill_memory_from_outcome(
        event=stored_event,
        user_id=user_id,
        memory_skill=memory_skill,
    )
    return {
        "captured": bool(eval_result.success),
        "reason": "captured" if eval_result.success else "eval_store_failed",
        "event": stored_event,
        "candidate": candidate,
        "eval": eval_spec,
        "recipe_candidate": recipe_candidate_result,
        "procedure_skill": procedure_skill_result,
    }


def web_search_outcome_event(
    *,
    message: str,
    user_id: str,
    result: SkillResult,
    request_id: str = "",
    session_id: str = "",
) -> dict[str, Any] | None:
    if result.skill_name != "web_search" or not result.success:
        return None
    metadata = result.metadata or {}
    source_quality = str(metadata.get("source_quality_outcome") or "").strip()
    explicit_url_count = int(metadata.get("explicit_url_count", 0) or 0)
    if explicit_url_count <= 0:
        return None
    page_excerpt_count = int(metadata.get("page_excerpt_count", 0) or 0)
    fetch_attempt_count = int(metadata.get("fetch_attempt_count", 0) or 0)
    if page_excerpt_count > 0:
        summary = "Web search handled an explicit URL/source request with fetched page excerpts."
        status = "observed_success"
        outcome = "official_page_excerpt_available"
    else:
        summary = "Web search handled an explicit URL/source request without a readable page excerpt."
        status = "observed_gap"
        outcome = "explicit_url_without_page_excerpt"
    sources = metadata.get("sources")
    safe_sources = sources[:5] if isinstance(sources, list) else []
    return {
        "event_type": "runtime_outcome",
        "artifact_type": "source_rule_candidate",
        "status": status,
        "risk": "low",
        "user_id": user_id,
        "source": "web_search_outcome",
        "request_id": request_id,
        "session_id": session_id,
        "summary": summary,
        "evidence": {
            "user_message": _clean_text(message, limit=900),
            "outcome": outcome,
            "source_quality_outcome": source_quality,
            "explicit_url_count": explicit_url_count,
            "fetch_attempt_count": fetch_attempt_count,
            "page_excerpt_count": page_excerpt_count,
            "sources": safe_sources,
        },
        "metadata": {
            "skill_name": "web_search",
            "connection_ref": _clean_text(metadata.get("connection_ref"), limit=120),
            "connection_title": _clean_text(metadata.get("connection_title"), limit=160),
            "result_count": int(metadata.get("result_count", 0) or 0),
        },
    }


def recipe_catalog_outcome_event(
    *,
    message: str,
    user_id: str,
    request_id: str = "",
    session_id: str = "",
    catalog_debug_line: str = "",
    runtime_recipe_count: int = 0,
    explicit_recipe_question: bool = False,
) -> dict[str, Any]:
    status = "observed_gap" if explicit_recipe_question else "observed_signal"
    outcome = "explicit_recipe_catalog_miss" if explicit_recipe_question else "recipe_candidate_miss"
    summary = (
        "User explicitly asked for a stored recipe, but no strong stored recipe candidate matched."
        if explicit_recipe_question
        else "Stored recipe arbitration produced no strong candidate for this turn."
    )
    return {
        "event_type": "runtime_outcome",
        "artifact_type": "recipe_candidate",
        "status": status,
        "risk": "medium",
        "user_id": user_id,
        "source": "recipe_catalog_outcome",
        "request_id": request_id,
        "session_id": session_id,
        "summary": summary,
        "evidence": {
            "user_message": _clean_text(message, limit=900),
            "outcome": outcome,
            "catalog_debug_line": _clean_text(catalog_debug_line, limit=500),
            "runtime_recipe_count": int(runtime_recipe_count or 0),
            "explicit_recipe_question": bool(explicit_recipe_question),
        },
        "metadata": {
            "review_only": True,
            "promotion_allowed": False,
        },
    }


def connection_action_outcome_event(
    *,
    message: str,
    user_id: str,
    request_id: str = "",
    session_id: str = "",
    candidate_kind: str = "",
    candidate_id: str = "",
    payload: Mapping[str, Any] | None = None,
    safety_decision: Mapping[str, Any] | None = None,
    execution_decision: Mapping[str, Any] | None = None,
    result_intents: list[str] | None = None,
    skill_errors: list[str] | None = None,
) -> dict[str, Any]:
    safe_payload = dict(payload or {})
    errors = [_clean_text(error, limit=240) for error in list(skill_errors or []) if _clean_text(error, limit=240)]
    safety_action = _clean_text((safety_decision or {}).get("action"), limit=80)
    next_step = _clean_text((execution_decision or {}).get("next_step"), limit=80)
    if errors:
        status = "observed_gap"
        outcome = "connection_action_error"
    elif safety_action == "ask_user":
        status = "observed_success"
        outcome = "confirmed_connection_action_executed"
    else:
        status = "observed_success"
        outcome = "connection_action_executed"
    return {
        "event_type": "runtime_outcome",
        "artifact_type": "procedure_candidate",
        "status": status,
        "risk": "medium",
        "user_id": user_id,
        "source": "connection_action_outcome",
        "request_id": request_id,
        "session_id": session_id,
        "summary": "Connection action execution produced a review-only learning outcome.",
        "evidence": {
            "user_message": _clean_text(message, limit=900),
            "outcome": outcome,
            "candidate_kind": _clean_text(candidate_kind, limit=120),
            "candidate_id": _clean_text(candidate_id, limit=160),
            "capability": _clean_text(safe_payload.get("capability"), limit=120),
            "connection_kind": _clean_text(safe_payload.get("connection_kind"), limit=120),
            "connection_ref": _clean_text(safe_payload.get("connection_ref"), limit=160),
            "safety_action": safety_action,
            "execution_next_step": next_step,
            "result_intents": [_clean_text(intent, limit=160) for intent in list(result_intents or [])],
            "skill_errors": errors,
        },
        "metadata": {
            "review_only": True,
            "promotion_allowed": False,
        },
    }


def active_learning_hint_outcome_event(
    *,
    message: str,
    user_id: str,
    request_id: str = "",
    session_id: str = "",
    active_hints: list[Mapping[str, Any]] | None = None,
    final_intents: list[str] | None = None,
    router_level: int = 0,
) -> dict[str, Any] | None:
    hints = [dict(hint) for hint in list(active_hints or []) if isinstance(hint, Mapping)]
    if not hints:
        return None
    safe_hints: list[dict[str, Any]] = []
    collections: list[str] = []
    for hint in hints[:5]:
        collection = _clean_text(hint.get("collection"), limit=180)
        if collection and collection not in collections:
            collections.append(collection)
        safe_hints.append(
            {
                "source": _clean_text(hint.get("source"), limit=120),
                "collection": collection,
                "runtime_effect": _clean_text(hint.get("runtime_effect"), limit=80),
                "text": _clean_text(hint.get("text"), limit=700),
            }
        )
    return {
        "event_type": "runtime_outcome",
        "artifact_type": "routing_hint",
        "status": "observed_signal",
        "risk": "low",
        "user_id": user_id,
        "source": "active_learning_hint_outcome",
        "request_id": request_id,
        "session_id": session_id,
        "summary": "A reviewed Qdrant active learning hint was available as a weak signal during turn intent arbitration.",
        "evidence": {
            "user_message": _clean_text(message, limit=900),
            "outcome": "active_learning_hint_presented_to_arbiter",
            "active_hint_count": len(safe_hints),
            "active_hint_collections": collections,
            "active_hints": safe_hints,
            "final_intents": [_clean_text(intent, limit=120) for intent in list(final_intents or [])],
            "router_level": int(router_level or 0),
        },
        "metadata": {
            "runtime_effect": "weak_signal_only",
            "review_only": True,
            "promotion_allowed": False,
        },
    }


async def capture_web_search_learning_outcome(
    *,
    message: str,
    user_id: str,
    result: SkillResult,
    memory_skill: Any | None,
    llm_client: Any | None,
    request_id: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    event = web_search_outcome_event(
        message=message,
        user_id=user_id,
        result=result,
        request_id=request_id,
        session_id=session_id,
    )
    if not event:
        return {"captured": False, "reason": "not_learning_worthy"}
    return await capture_learning_outcome(
        event=event,
        user_id=user_id,
        memory_skill=memory_skill,
        llm_client=llm_client,
    )
