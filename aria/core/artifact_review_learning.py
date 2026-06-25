from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aria.core.learning_classifier import normalize_learning_candidate
from aria.core.learning_classifier import store_learning_candidate
from aria.core.learning_events import record_learning_event
from aria.core.learning_outcomes import build_learning_event_text
from aria.core.learning_outcomes import learning_events_collection_for_user
from aria.core.learning_validator import fallback_learning_eval
from aria.core.learning_validator import store_learning_eval


def _clean_text(value: Any, *, limit: int = 1600) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def prepared_artifact_review_event(
    *,
    user_id: str,
    candidate_collection: str,
    candidate_point_id: str,
    candidate_text: str,
    artifact_kind: str,
    review_payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    review_state = _clean_text(review_payload.get("prepared_artifact_review_state"), limit=80).lower()
    decision = _clean_text(review_payload.get("prepared_artifact_review_decision"), limit=80).lower()
    if review_state != "reviewed" or decision not in {"accepted", "needs_changes", "rejected"}:
        return None
    target_file = _clean_text(review_payload.get("prepared_artifact_target_file"), limit=240)
    summary_by_decision = {
        "accepted": "Prepared artifact review accepted a reusable proposal pattern.",
        "needs_changes": "Prepared artifact review requested changes to improve future proposals.",
        "rejected": "Prepared artifact review rejected a proposal pattern that should not be repeated.",
    }
    return {
        "event_type": "artifact_review",
        "artifact_type": "prepared_artifact_review",
        "status": f"review_{decision}",
        "risk": "low",
        "user_id": user_id,
        "source": "prepared_artifact_review",
        "summary": summary_by_decision[decision],
        "evidence": {
            "artifact_kind": _clean_text(artifact_kind, limit=120),
            "decision": decision,
            "review_notes": _clean_text(review_payload.get("prepared_artifact_review_notes"), limit=900),
            "target_file": target_file,
            "code_preview_sha256": _clean_text(review_payload.get("prepared_artifact_code_preview_sha256"), limit=100),
            "candidate_collection": _clean_text(candidate_collection, limit=160),
            "candidate_point_id": _clean_text(candidate_point_id, limit=160),
            "candidate_text_excerpt": _clean_text(candidate_text, limit=1200),
        },
        "metadata": {
            "review_only": True,
            "promotion_allowed": False,
            "runtime_activation_allowed": False,
            "pytest_write_allowed": False,
        },
    }


def prepared_artifact_review_candidate(event: Mapping[str, Any]) -> dict[str, Any]:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    decision = _clean_text(evidence.get("decision"), limit=80).lower()
    artifact_kind = _clean_text(evidence.get("artifact_kind") or "prepared_artifact", limit=120)
    target_file = _clean_text(evidence.get("target_file"), limit=240)
    notes = _clean_text(evidence.get("review_notes"), limit=500)
    if decision == "accepted":
        artifact_type = "artifact_pattern_candidate"
        title = "Accepted prepared artifact pattern"
        expected = "Use this accepted proposal shape as review-only guidance for future prepared artifacts."
        reason = "A human accepted the prepared artifact as useful."
    elif decision == "needs_changes":
        artifact_type = "artifact_improvement_candidate"
        title = "Prepared artifact improvement candidate"
        expected = "Use the review notes to improve future artifact proposals before they are prepared again."
        reason = "A human marked the prepared artifact as needing changes."
    else:
        artifact_type = "negative_pattern_candidate"
        title = "Rejected prepared artifact pattern"
        expected = "Avoid repeating this proposal shape, target, or weak test structure without new evidence."
        reason = "A human rejected the prepared artifact."
    summary_bits = [f"{artifact_kind} review: {decision}"]
    if target_file:
        summary_bits.append(f"target={target_file}")
    if notes:
        summary_bits.append(f"notes={notes}")
    return normalize_learning_candidate(
        {
            "artifact_type": artifact_type,
            "status": "proposed",
            "risk": "low",
            "title": title,
            "summary": "; ".join(summary_bits),
            "reason": reason,
            "expected_behavior": expected,
            "review_criteria": [
                "candidate is visible in Qdrant",
                "candidate remains review-only",
                "future proposals can cite this review outcome as weak guidance",
            ],
            "proposed_change": {
                "artifact_kind": artifact_kind,
                "decision": decision,
                "target_file": target_file,
                "review_notes": notes,
                "runtime_activation_allowed": False,
                "write_allowed": False,
            },
            "evidence": dict(evidence),
            "confidence": "high" if decision == "accepted" else "medium",
            "source": "prepared_artifact_review",
            "metadata": {
                "review_only": True,
                "promotion_allowed": False,
                "runtime_activation_allowed": False,
                "origin_event_type": event.get("event_type"),
            },
        },
        event=event,
    )


async def capture_prepared_artifact_review_learning(
    *,
    user_id: str,
    memory_skill: Any | None,
    candidate_collection: str,
    candidate_point_id: str,
    candidate_text: str,
    artifact_kind: str,
    review_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if memory_skill is None:
        return {"captured": False, "reason": "memory_disabled"}
    event = prepared_artifact_review_event(
        user_id=user_id,
        candidate_collection=candidate_collection,
        candidate_point_id=candidate_point_id,
        candidate_text=candidate_text,
        artifact_kind=artifact_kind,
        review_payload=review_payload,
    )
    if event is None:
        return {"captured": False, "reason": "review_not_captureable"}
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
            "source": "prepared_artifact_review",
        },
    )
    if not event_result.success:
        return {"captured": False, "reason": "event_store_failed", "event": stored_event}
    candidate = prepared_artifact_review_candidate(stored_event)
    candidate_result = await store_learning_candidate(memory_skill=memory_skill, candidate=candidate, user_id=user_id)
    if not candidate_result.success:
        return {"captured": False, "reason": "candidate_store_failed", "event": stored_event, "candidate": candidate}
    eval_spec = fallback_learning_eval(candidate, reason="prepared_artifact_review")
    eval_result = await store_learning_eval(memory_skill=memory_skill, eval_spec=eval_spec, user_id=user_id)
    return {
        "captured": bool(eval_result.success),
        "reason": "captured" if eval_result.success else "eval_store_failed",
        "event": stored_event,
        "candidate": candidate,
        "eval": eval_spec,
    }
