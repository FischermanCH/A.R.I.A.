from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from aria.core.learning_classifier import normalize_learning_candidate
from aria.core.learning_classifier import store_learning_candidate
from aria.core.learning_validator import fallback_learning_eval
from aria.core.learning_validator import store_learning_eval


PROCEDURE_SKILL_GUIDANCE_TYPES = {"procedure_candidate", "skill_candidate"}


def _clean_text(value: Any, *, limit: int = 1000) -> str:
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


def _workflow_is_captureable(event: Mapping[str, Any]) -> bool:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    outcome = _clean_text(evidence.get("outcome"), limit=120)
    if outcome not in {"connection_action_executed", "confirmed_connection_action_executed"}:
        return False
    if evidence.get("skill_errors"):
        return False
    return bool(_clean_text(evidence.get("capability"), limit=120) and _clean_text(evidence.get("connection_kind"), limit=120))


def _procedure_skill_query(event: Mapping[str, Any]) -> str:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    parts = [
        "review-only procedure skill workflow memory",
        _clean_text(evidence.get("user_message"), limit=300),
        _clean_text(evidence.get("connection_kind"), limit=120),
        _clean_text(evidence.get("capability"), limit=120),
        _clean_text(evidence.get("candidate_kind"), limit=120),
        _clean_text(evidence.get("candidate_id"), limit=160),
    ]
    return " ".join(part for part in parts if part).strip()


def extract_procedure_skill_guidance(rows: list[Mapping[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    guidance: list[dict[str, Any]] = []
    for row in rows:
        raw_text = str(row.get("text") or "")
        candidate_type = _field_from_text(raw_text, "Type").lower()
        if candidate_type not in PROCEDURE_SKILL_GUIDANCE_TYPES:
            continue
        guidance.append(
            {
                "candidate_type": candidate_type,
                "title": _field_from_text(raw_text, "Learning Candidate"),
                "summary": _field_from_text(raw_text, "Summary") or _clean_text(raw_text, limit=500),
                "collection": _clean_text(row.get("collection"), limit=160),
                "point_id": _clean_text(row.get("id"), limit=160),
                "score": float(row.get("score", 0.0) or 0.0),
                "effect": "generalize_or_refine",
                "promotion_allowed": False,
                "runtime_activation_allowed": False,
            }
        )
        if len(guidance) >= limit:
            break
    return guidance


async def recall_procedure_skill_guidance(
    *,
    memory_skill: Any | None,
    user_id: str,
    event: Mapping[str, Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    if memory_skill is None:
        return []
    search = getattr(memory_skill, "search_memories", None)
    if not callable(search):
        return []
    query = _procedure_skill_query(event)
    if not query:
        return []
    try:
        rows = await search(
            user_id=user_id or "web",
            query=query,
            type_filter="learning_candidate",
            top_k=max(limit * 3, 12),
        )
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    return extract_procedure_skill_guidance(rows, limit=limit)


def _workflow_change(event: Mapping[str, Any], guidance: list[Mapping[str, Any]]) -> dict[str, Any]:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    return {
        "workflow_kind": "connection_workflow_procedure",
        "trigger_summary": _clean_text(evidence.get("user_message"), limit=500),
        "connection_kind": _clean_text(evidence.get("connection_kind"), limit=120),
        "connection_ref": _clean_text(evidence.get("connection_ref"), limit=160),
        "capability": _clean_text(evidence.get("capability"), limit=120),
        "candidate_kind": _clean_text(evidence.get("candidate_kind"), limit=120),
        "candidate_id": _clean_text(evidence.get("candidate_id"), limit=160),
        "safety_action": _clean_text(evidence.get("safety_action"), limit=80),
        "execution_next_step": _clean_text(evidence.get("execution_next_step"), limit=120),
        "result_intents": list(evidence.get("result_intents") or [])[:10],
        "similar_procedure_skill_guidance": list(guidance or [])[:5],
        "requires_review": True,
        "requires_eval": True,
        "requires_policy_guardrail_validation": True,
        "promotion_allowed": False,
        "runtime_activation_allowed": False,
    }


def build_procedure_candidate_from_outcome(
    event: Mapping[str, Any],
    *,
    guidance: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not _workflow_is_captureable(event):
        return None
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    connection_kind = _clean_text(evidence.get("connection_kind"), limit=120)
    capability = _clean_text(evidence.get("capability"), limit=120)
    user_message = _clean_text(evidence.get("user_message"), limit=500)
    safety_action = _clean_text(evidence.get("safety_action"), limit=80)
    risk = "high" if safety_action == "ask_user" else "medium"
    clean_guidance = _sanitize_guidance(guidance or [])
    summary = f"Review-only procedure candidate from successful {connection_kind}/{capability} workflow."
    if user_message:
        summary = f"{summary} Trigger: {user_message}"
    return normalize_learning_candidate(
        {
            "artifact_type": "procedure_candidate",
            "status": "proposed",
            "risk": risk,
            "title": f"{connection_kind} {capability} workflow procedure",
            "summary": summary,
            "reason": "A successful workflow can be generalized as a review-only procedure before becoming any active capability.",
            "proposed_change": _workflow_change(event, clean_guidance),
            "review_criteria": [
                "candidate is visible in Qdrant",
                "review confirms this is a reusable procedure",
                "procedure is covered by eval and guardrails before promotion",
                "runtime activation remains disabled",
            ],
            "eval_prompt": user_message,
            "expected_behavior": "Keep the reusable procedure review-only until evaluation, policy, guardrails, and human promotion pass.",
            "confidence": "medium",
            "source": "procedure_skill_memory",
            "metadata": {
                "review_only": True,
                "promotion_allowed": False,
                "runtime_activation_allowed": False,
                "similar_procedure_skill_guidance_count": len(clean_guidance),
            },
        },
        event=event,
    )


def _sanitize_guidance(guidance: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_type": _clean_text(item.get("candidate_type"), limit=80),
            "summary": _clean_text(item.get("summary"), limit=500),
            "collection": _clean_text(item.get("collection"), limit=160),
            "point_id": _clean_text(item.get("point_id"), limit=160),
            "score": float(item.get("score", 0.0) or 0.0),
            "effect": _clean_text(item.get("effect") or "generalize_or_refine", limit=80),
            "promotion_allowed": False,
            "runtime_activation_allowed": False,
        }
        for item in list(guidance or [])[:5]
        if isinstance(item, Mapping)
    ]


def build_skill_candidate_from_outcome(
    event: Mapping[str, Any],
    *,
    guidance: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    clean_guidance = _sanitize_guidance(guidance or [])
    if not clean_guidance or not _workflow_is_captureable(event):
        return None
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    connection_kind = _clean_text(evidence.get("connection_kind"), limit=120)
    capability = _clean_text(evidence.get("capability"), limit=120)
    user_message = _clean_text(evidence.get("user_message"), limit=500)
    proposed_change = _workflow_change(event, clean_guidance)
    proposed_change["skill_kind"] = "workflow_skill_candidate"
    proposed_change["source_procedure_guidance"] = clean_guidance
    summary = f"Review-only skill candidate from repeated {connection_kind}/{capability} workflow evidence."
    if user_message:
        summary = f"{summary} Trigger: {user_message}"
    return normalize_learning_candidate(
        {
            "artifact_type": "skill_candidate",
            "status": "proposed",
            "risk": "high",
            "title": f"{connection_kind} {capability} workflow skill",
            "summary": summary,
            "reason": "Similar procedure/skill memories suggest this workflow may deserve a gated reusable skill.",
            "proposed_change": proposed_change,
            "review_criteria": [
                "candidate is visible in Qdrant",
                "skill contract is reviewed before any implementation",
                "tests, policy, guardrails, and user approval exist before promotion",
                "no runtime activation is granted by this candidate",
            ],
            "eval_prompt": user_message,
            "expected_behavior": "Treat this as a high-risk review-only skill idea until explicit implementation, tests, and promotion gates exist.",
            "confidence": "low",
            "source": "procedure_skill_memory",
            "metadata": {
                "review_only": True,
                "promotion_allowed": False,
                "runtime_activation_allowed": False,
                "similar_procedure_skill_guidance_count": len(clean_guidance),
            },
        },
        event=event,
    )


async def _store_candidate_and_eval(
    *,
    memory_skill: Any,
    candidate: Mapping[str, Any],
    user_id: str,
    reason: str,
) -> dict[str, Any]:
    candidate_result = await store_learning_candidate(memory_skill=memory_skill, candidate=candidate, user_id=user_id)
    if not candidate_result.success:
        return {"captured": False, "reason": "candidate_store_failed", "candidate": dict(candidate)}
    eval_spec = fallback_learning_eval(candidate, reason=reason)
    eval_result = await store_learning_eval(memory_skill=memory_skill, eval_spec=eval_spec, user_id=user_id)
    return {
        "captured": bool(eval_result.success),
        "reason": "captured" if eval_result.success else "eval_store_failed",
        "candidate": dict(candidate),
        "eval": eval_spec,
    }


async def capture_procedure_skill_memory_from_outcome(
    *,
    event: Mapping[str, Any],
    user_id: str,
    memory_skill: Any | None,
) -> dict[str, Any]:
    if memory_skill is None:
        return {"captured": False, "reason": "memory_disabled"}
    guidance = await recall_procedure_skill_guidance(memory_skill=memory_skill, user_id=user_id, event=event)
    procedure = build_procedure_candidate_from_outcome(event, guidance=guidance)
    if procedure is None:
        return {"captured": False, "reason": "not_procedure_skill_outcome"}
    procedure_result = await _store_candidate_and_eval(
        memory_skill=memory_skill,
        candidate=procedure,
        user_id=user_id,
        reason="procedure_skill_memory",
    )
    skill = build_skill_candidate_from_outcome(event, guidance=guidance)
    skill_result = {"captured": False, "reason": "no_repeated_procedure_skill_guidance"}
    if skill is not None:
        skill_result = await _store_candidate_and_eval(
            memory_skill=memory_skill,
            candidate=skill,
            user_id=user_id,
            reason="procedure_skill_memory",
        )
    return {
        "captured": bool(procedure_result.get("captured")),
        "reason": "captured" if procedure_result.get("captured") else procedure_result.get("reason", "capture_failed"),
        "procedure": procedure_result,
        "skill": skill_result,
        "guidance": guidance,
    }
