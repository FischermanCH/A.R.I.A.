from __future__ import annotations

import re
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.learning_classifier import LearningClassifier
from aria.core.learning_classifier import store_learning_candidate
from aria.core.learning_events import record_learning_event
from aria.core.learning_validator import LearningCandidateValidator
from aria.core.learning_validator import store_learning_eval


def _clean_text(value: Any, *, limit: int = 1800) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _recent_history_context(history: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in list(history or [])[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        text = _clean_text(item.get("text"), limit=900)
        if role in {"user", "assistant"} and text:
            rows.append({"role": role, "text": text})
    return rows


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def _fallback_feedback_event(message: str, *, user_id: str, history: list[dict[str, Any]]) -> dict[str, Any] | None:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return None
    negative_terms = (
        "das war falsch",
        "das ist falsch",
        "stimmt nicht",
        "entt\u00e4uschend",
        "enttaeuschend",
        "meh",
        "du hast wieder",
        "nicht so",
        "so nicht",
    )
    positive_terms = (
        "genau so",
        "das ist besser",
        "das war gut",
        "sehr gut",
        "perfekt",
        "passt",
    )
    if not any(term in lowered for term in (*negative_terms, *positive_terms)):
        return None
    sentiment = "positive" if any(term in lowered for term in positive_terms) else "negative"
    return {
        "event_type": "feedback",
        "artifact_type": "user_feedback",
        "status": "observed",
        "risk": "low",
        "user_id": user_id,
        "source": "chat_feedback",
        "summary": _clean_text(message, limit=600),
        "evidence": {
            "user_message": _clean_text(message, limit=1000),
            "recent_history": _recent_history_context(history, limit=4),
            "sentiment": sentiment,
        },
        "metadata": {
            "detector": "fallback",
            "feedback_sentiment": sentiment,
        },
    }


class UserFeedbackLearningDetector:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def detect(
        self,
        message: str,
        *,
        user_id: str,
        history: list[dict[str, Any]] | None = None,
        source: str = "chat_feedback",
        request_id: str = "",
    ) -> dict[str, Any] | None:
        clean_message = _clean_text(message, limit=1200)
        if not clean_message:
            return None
        recent = _recent_history_context(list(history or []))
        system = (
            "Classify whether the current user message is durable feedback about ARIA's behavior, "
            "previous answer, source handling, routing, memory, UI, or workflow. Return JSON only. "
            "Do not classify ordinary new task requests as feedback. "
            "If feedback is durable, set is_feedback=true and include sentiment positive|negative|mixed, "
            "summary, artifact_hint source_rule_candidate|procedure_candidate|eval_candidate|memory_reflection|routing_hint, "
            "and reason. Otherwise is_feedback=false."
        )
        result = await self.decision_client.decide_json(
            operation="user_feedback_learning_detection",
            system=system,
            payload={"message": clean_message, "recent_history": recent},
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return _fallback_feedback_event(clean_message, user_id=user_id, history=recent)
        payload = dict(result.payload)
        if payload.get("is_feedback") is not True:
            return None
        sentiment = _clean_text(payload.get("sentiment") or "mixed", limit=40).lower()
        summary = _clean_text(payload.get("summary") or clean_message, limit=700)
        artifact_hint = _clean_text(payload.get("artifact_hint") or "memory_reflection", limit=80)
        return {
            "event_type": "feedback",
            "artifact_type": "user_feedback",
            "status": "observed",
            "risk": "low",
            "user_id": user_id,
            "source": "chat_feedback",
            "summary": summary,
            "evidence": {
                "user_message": clean_message,
                "recent_history": recent,
                "sentiment": sentiment,
                "reason": _clean_text(payload.get("reason"), limit=500),
            },
            "metadata": {
                "detector": "bounded_llm",
                "feedback_sentiment": sentiment,
                "artifact_hint": artifact_hint,
                "detection_usage": result.usage,
            },
        }


async def capture_user_feedback_learning(
    *,
    message: str,
    user_id: str,
    history: list[dict[str, Any]],
    memory_skill: Any | None,
    llm_client: Any | None,
) -> dict[str, Any]:
    if memory_skill is None:
        return {"captured": False, "reason": "memory_disabled"}
    event = await UserFeedbackLearningDetector(llm_client).detect(
        message,
        user_id=user_id,
        history=history,
    )
    if not event:
        return {"captured": False, "reason": "not_feedback"}
    stored_event = record_learning_event(event)
    event_text = "\n".join(
        part
        for part in (
            f"Learning Event: {stored_event.get('event_id')}",
            "Type: feedback / user_feedback",
            f"Status: {stored_event.get('status', 'observed')}",
            "Source: chat_feedback",
            f"Summary: {stored_event.get('summary')}",
        )
        if part
    )
    event_result = await memory_skill.execute(
        query=event_text,
        params={
            "action": "store",
            "text": event_text,
            "user_id": user_id,
            "collection": f"aria_learning_events_{_slug_user_id(user_id)}",
            "memory_type": "learning_event",
            "source": "chat_feedback",
        },
    )
    if not event_result.success:
        return {"captured": False, "reason": "event_store_failed", "event": stored_event}
    candidate = await LearningClassifier(llm_client).classify(
        stored_event,
        user_id=user_id,
        source="chat_feedback",
    )
    if str(candidate.get("artifact_type", "")).strip().lower() == "ignore":
        return {"captured": True, "reason": "candidate_ignored", "event": stored_event}
    candidate_result = await store_learning_candidate(memory_skill=memory_skill, candidate=candidate, user_id=user_id)
    if not candidate_result.success:
        return {"captured": False, "reason": "candidate_store_failed", "event": stored_event, "candidate": candidate}
    eval_spec = await LearningCandidateValidator(llm_client).validate(
        candidate,
        user_id=user_id,
        source="chat_feedback",
    )
    eval_result = await store_learning_eval(memory_skill=memory_skill, eval_spec=eval_spec, user_id=user_id)
    return {
        "captured": bool(eval_result.success),
        "reason": "captured" if eval_result.success else "eval_store_failed",
        "event": stored_event,
        "candidate": candidate,
        "eval": eval_spec,
    }
