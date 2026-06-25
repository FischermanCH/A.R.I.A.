from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from aria.core.learning_classifier import normalize_learning_candidate
from aria.core.learning_classifier import store_learning_candidate
from aria.core.learning_validator import fallback_learning_eval
from aria.core.learning_validator import store_learning_eval


RECIPE_GUIDANCE_TYPES = {"recipe_candidate", "recipe_improvement"}


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


def _recipe_guidance_query(event: Mapping[str, Any]) -> str:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    parts = [
        "review-only recipe candidate workflow",
        _clean_text(evidence.get("user_message"), limit=300),
        _clean_text(evidence.get("connection_kind"), limit=120),
        _clean_text(evidence.get("capability"), limit=120),
        _clean_text(evidence.get("outcome"), limit=120),
    ]
    return " ".join(part for part in parts if part).strip()


def extract_recipe_candidate_guidance(rows: list[Mapping[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    guidance: list[dict[str, Any]] = []
    for row in rows:
        raw_text = str(row.get("text") or "")
        candidate_type = _field_from_text(raw_text, "Type").lower()
        if candidate_type not in RECIPE_GUIDANCE_TYPES:
            continue
        guidance.append(
            {
                "candidate_type": candidate_type,
                "title": _field_from_text(raw_text, "Learning Candidate"),
                "summary": _field_from_text(raw_text, "Summary") or _clean_text(raw_text, limit=500),
                "collection": _clean_text(row.get("collection"), limit=160),
                "point_id": _clean_text(row.get("id"), limit=160),
                "score": float(row.get("score", 0.0) or 0.0),
                "effect": "dedupe_or_improve",
                "runtime_activation_allowed": False,
            }
        )
        if len(guidance) >= limit:
            break
    return guidance


async def recall_recipe_candidate_guidance(
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
    query = _recipe_guidance_query(event)
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
    return extract_recipe_candidate_guidance(rows, limit=limit)


def build_recipe_candidate_from_outcome(
    event: Mapping[str, Any],
    *,
    guidance: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), Mapping) else {}
    outcome = _clean_text(evidence.get("outcome"), limit=120)
    if outcome not in {"connection_action_executed", "confirmed_connection_action_executed"}:
        return None
    if evidence.get("skill_errors"):
        return None
    capability = _clean_text(evidence.get("capability"), limit=120)
    connection_kind = _clean_text(evidence.get("connection_kind"), limit=120)
    user_message = _clean_text(evidence.get("user_message"), limit=500)
    if not capability or not connection_kind:
        return None
    safety_action = _clean_text(evidence.get("safety_action"), limit=80)
    risk = "high" if safety_action == "ask_user" else "medium"
    clean_guidance = [
        {
            "candidate_type": _clean_text(item.get("candidate_type"), limit=80),
            "summary": _clean_text(item.get("summary"), limit=500),
            "collection": _clean_text(item.get("collection"), limit=160),
            "point_id": _clean_text(item.get("point_id"), limit=160),
            "score": float(item.get("score", 0.0) or 0.0),
            "effect": _clean_text(item.get("effect") or "dedupe_or_improve", limit=80),
            "runtime_activation_allowed": False,
        }
        for item in list(guidance or [])[:5]
        if isinstance(item, Mapping)
    ]
    proposed_change = {
        "recipe_kind": "connection_workflow_recipe_candidate",
        "trigger_summary": user_message,
        "connection_kind": connection_kind,
        "connection_ref": _clean_text(evidence.get("connection_ref"), limit=160),
        "capability": capability,
        "candidate_kind": _clean_text(evidence.get("candidate_kind"), limit=120),
        "candidate_id": _clean_text(evidence.get("candidate_id"), limit=160),
        "safety_action": safety_action,
        "execution_next_step": _clean_text(evidence.get("execution_next_step"), limit=120),
        "result_intents": list(evidence.get("result_intents") or [])[:10],
        "similar_recipe_guidance": clean_guidance,
        "requires_review": True,
        "requires_policy_guardrail_validation": True,
        "requires_regression": True,
        "promotion_allowed": False,
        "runtime_activation_allowed": False,
    }
    has_similar_recipe = bool(clean_guidance)
    artifact_type = "recipe_improvement" if has_similar_recipe else "recipe_candidate"
    if has_similar_recipe:
        proposed_change["recipe_kind"] = "connection_workflow_recipe_improvement"
        proposed_change["improves_existing_candidates"] = True
    title = (
        f"{connection_kind} {capability} workflow recipe improvement"
        if has_similar_recipe
        else f"{connection_kind} {capability} workflow recipe"
    )
    summary = (
        f"Review-only recipe improvement from successful {connection_kind}/{capability} workflow."
        if has_similar_recipe
        else f"Review-only recipe candidate from successful {connection_kind}/{capability} workflow."
    )
    if user_message:
        summary = f"{summary} Trigger: {user_message}"
    return normalize_learning_candidate(
        {
            "artifact_type": artifact_type,
            "status": "proposed",
            "risk": risk,
            "title": title,
            "summary": summary,
            "reason": "A successful connection workflow can be reviewed as a reusable recipe candidate.",
            "proposed_change": proposed_change,
            "review_criteria": [
                "candidate is visible in Qdrant",
                "review confirms the workflow should become a recipe",
                "policy and guardrails cover every runtime step",
                "regression or dry-run exists before promotion",
            ],
            "eval_prompt": user_message,
            "expected_behavior": "Generate a reusable recipe only after human review, regression, policy, and guardrail validation.",
            "confidence": "medium",
            "source": "recipe_candidate_generator",
            "metadata": {
                "review_only": True,
                "promotion_allowed": False,
                "runtime_activation_allowed": False,
                "similar_recipe_guidance_count": len(clean_guidance),
                "recipe_candidate_mode": "improvement" if has_similar_recipe else "new_candidate",
            },
        },
        event=event,
    )


async def capture_recipe_candidate_from_outcome(
    *,
    event: Mapping[str, Any],
    user_id: str,
    memory_skill: Any | None,
) -> dict[str, Any]:
    if memory_skill is None:
        return {"captured": False, "reason": "memory_disabled"}
    guidance = await recall_recipe_candidate_guidance(memory_skill=memory_skill, user_id=user_id, event=event)
    candidate = build_recipe_candidate_from_outcome(event, guidance=guidance)
    if candidate is None:
        return {"captured": False, "reason": "not_recipe_candidate_outcome"}
    candidate_result = await store_learning_candidate(memory_skill=memory_skill, candidate=candidate, user_id=user_id)
    if not candidate_result.success:
        return {"captured": False, "reason": "candidate_store_failed", "candidate": candidate}
    eval_spec = fallback_learning_eval(candidate, reason="recipe_candidate_generator")
    eval_result = await store_learning_eval(memory_skill=memory_skill, eval_spec=eval_spec, user_id=user_id)
    return {
        "captured": bool(eval_result.success),
        "reason": "captured" if eval_result.success else "eval_store_failed",
        "candidate": candidate,
        "eval": eval_spec,
        "guidance": guidance,
    }
