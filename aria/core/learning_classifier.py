from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.learning_events import redact_learning_payload


LEARNING_CANDIDATE_ARTIFACT_TYPES = {
    "memory_reflection",
    "routing_hint",
    "source_rule_candidate",
    "procedure_candidate",
    "recipe_candidate",
    "recipe_improvement",
    "skill_candidate",
    "eval_candidate",
    "app_artifact_candidate",
    "app_identity_candidate",
    "install_plan_candidate",
    "health_check_candidate",
    "artifact_pattern_candidate",
    "artifact_improvement_candidate",
    "negative_pattern_candidate",
    "ignore",
}
LEARNING_CANDIDATE_RISKS = {"low", "medium", "high"}


def _clean_text(value: Any, *, limit: int = 1600) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clean_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        clean = _clean_text(item, limit=240)
        if clean:
            items.append(clean)
        if len(items) >= limit:
            break
    return items


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def learning_candidates_collection_for_user(user_id: str) -> str:
    return f"aria_learning_candidates_{_slug_user_id(user_id)}"


def normalize_learning_candidate(candidate: Mapping[str, Any], *, event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _clean_text(event.get("event_id"), limit=120)
    user_id = _clean_text(candidate.get("user_id") or event.get("user_id"), limit=120)
    artifact_type = _clean_text(candidate.get("artifact_type"), limit=80).lower()
    if artifact_type not in LEARNING_CANDIDATE_ARTIFACT_TYPES:
        artifact_type = "ignore"
    risk = _clean_text(candidate.get("risk") or event.get("risk") or "medium", limit=40).lower()
    if risk not in LEARNING_CANDIDATE_RISKS:
        risk = "medium"
    status = _clean_text(candidate.get("status") or "proposed", limit=40).lower()
    if status not in {"proposed", "reviewed", "promoted", "rejected", "superseded", "ignored"}:
        status = "proposed"
    if artifact_type == "ignore":
        status = "ignored"
    title = _clean_text(candidate.get("title") or candidate.get("summary") or event.get("summary"), limit=120)
    summary = _clean_text(candidate.get("summary") or event.get("summary"), limit=600)
    reason = _clean_text(candidate.get("reason"), limit=600)
    created_at = _clean_text(candidate.get("created_at") or datetime.now(timezone.utc).isoformat(), limit=80)
    candidate_id = _clean_text(candidate.get("candidate_id"), limit=160)
    if not candidate_id:
        candidate_id = f"learning-candidate-{uuid4().hex}"
    return {
        "candidate_id": candidate_id,
        "created_at": created_at,
        "event_id": event_id,
        "user_id": user_id,
        "artifact_type": artifact_type,
        "status": status,
        "risk": risk,
        "title": title,
        "summary": summary,
        "reason": reason,
        "evidence": redact_learning_payload(candidate.get("evidence") or event.get("evidence") or {}),
        "proposed_change": redact_learning_payload(candidate.get("proposed_change") or {}),
        "review_criteria": _clean_list(candidate.get("review_criteria")),
        "eval_prompt": _clean_text(candidate.get("eval_prompt"), limit=400),
        "expected_behavior": _clean_text(candidate.get("expected_behavior"), limit=600),
        "confidence": _clean_text(candidate.get("confidence") or "medium", limit=40).lower(),
        "source": _clean_text(candidate.get("source") or "learning_classifier", limit=120),
        "metadata": redact_learning_payload(candidate.get("metadata") or {}),
    }


def build_learning_candidate_text(candidate: Mapping[str, Any]) -> str:
    parts = [
        f"Learning Candidate: {_clean_text(candidate.get('title'), limit=160)}",
        f"Type: {_clean_text(candidate.get('artifact_type'), limit=80)}",
        f"Status: {_clean_text(candidate.get('status'), limit=80)}",
        f"Risk: {_clean_text(candidate.get('risk'), limit=80)}",
        f"Event: {_clean_text(candidate.get('event_id'), limit=160)}",
        f"Summary: {_clean_text(candidate.get('summary'), limit=900)}",
        f"Reason: {_clean_text(candidate.get('reason'), limit=700)}",
    ]
    expected = _clean_text(candidate.get("expected_behavior"), limit=700)
    if expected:
        parts.append(f"Expected behavior: {expected}")
    eval_prompt = _clean_text(candidate.get("eval_prompt"), limit=500)
    if eval_prompt:
        parts.append(f"Eval prompt: {eval_prompt}")
    criteria = _clean_list(candidate.get("review_criteria"), limit=8)
    if criteria:
        parts.append("Review criteria: " + "; ".join(criteria))
    proposed_change = candidate.get("proposed_change")
    if proposed_change:
        parts.append("Proposed change: " + _clean_text(json.dumps(proposed_change, ensure_ascii=False), limit=1200))
    evidence = candidate.get("evidence")
    if isinstance(evidence, Mapping):
        app_identity = evidence.get("app_identity_hypothesis")
        if isinstance(app_identity, Mapping):
            parts.append("App identity hypothesis: " + _clean_text(json.dumps(app_identity, ensure_ascii=False), limit=1200))
        plan_draft = evidence.get("install_update_plan_draft")
        if isinstance(plan_draft, Mapping):
            parts.append("Install/update plan draft: " + _clean_text(json.dumps(plan_draft, ensure_ascii=False), limit=1400))
        plan_validation = evidence.get("install_update_plan_validation")
        if isinstance(plan_validation, Mapping):
            parts.append("Install/update plan validation: " + _clean_text(json.dumps(plan_validation, ensure_ascii=False), limit=1200))
        health_drafts = evidence.get("health_check_drafts")
        if isinstance(health_drafts, list) and health_drafts:
            parts.append("Health check drafts: " + _clean_text(json.dumps(health_drafts, ensure_ascii=False), limit=1000))
        regression_drafts = evidence.get("regression_drafts")
        if isinstance(regression_drafts, list) and regression_drafts:
            parts.append("Regression drafts: " + _clean_text(json.dumps(regression_drafts, ensure_ascii=False), limit=1200))
        pytest_proposal = evidence.get("pytest_skeleton_proposal")
        if isinstance(pytest_proposal, Mapping):
            parts.append("Pytest skeleton proposal: " + _clean_text(json.dumps(pytest_proposal, ensure_ascii=False), limit=1400))
    return "\n".join(part for part in parts if part and not part.endswith(": ")).strip()


def fallback_learning_candidate(event: Mapping[str, Any], *, reason: str = "classifier_unavailable") -> dict[str, Any]:
    summary = _clean_text(event.get("summary"), limit=600)
    lowered = summary.lower()
    if any(term in lowered for term in ("source", "quelle", "snippet", "page excerpt", "official", "url", "anchor")):
        artifact_type = "source_rule_candidate"
        title = "Source handling candidate"
        expected = "Prefer fetched official page excerpts over search snippets for concrete URL or anchor questions."
    elif any(term in lowered for term in ("app identity", "application identity", "runtime_kind", "app_root", "app identity hypothesis")):
        artifact_type = "app_identity_candidate"
        title = "App identity candidate"
        expected = "Review an app identity hypothesis before deriving install/update plans or health checks."
    elif any(term in lowered for term in ("docker", "compose", "systemd", "service", "dockerfile", "package.json", "pyproject", "requirements")):
        artifact_type = "app_artifact_candidate"
        title = "Host app artifact candidate"
        expected = "Capture observed host/application artifacts as review-only inventory before planning installs or updates."
    elif any(term in lowered for term in ("health", "healthy", "unhealthy", "running", "listening", "port", "failed service")):
        artifact_type = "health_check_candidate"
        title = "Health check candidate"
        expected = "Turn observed services, ports, or health outputs into review-only health check criteria."
    elif any(term in lowered for term in ("install", "update", "upgrade", "deploy", "migration")):
        artifact_type = "install_plan_candidate"
        title = "Install/update plan candidate"
        expected = "Build a review-only install/update plan from observed app artifacts, with preview, rollback, and health gates."
    elif any(term in lowered for term in ("workflow", "ablauf", "immer wenn", "wenn ich", "procedure", "recipe")):
        artifact_type = "procedure_candidate"
        title = "Procedure candidate"
        expected = "Turn repeated user workflow feedback into a review-only procedure candidate."
    elif any(term in lowered for term in ("test", "regression", "ausreisser", "bug", "fehler")):
        artifact_type = "eval_candidate"
        title = "Eval candidate"
        expected = "Capture this incident as a regression candidate."
    elif summary:
        artifact_type = "memory_reflection"
        title = "Learning reflection candidate"
        expected = "Keep this as review-only learning guidance."
    else:
        artifact_type = "ignore"
        title = "Ignored learning event"
        expected = ""
    return normalize_learning_candidate(
        {
            "artifact_type": artifact_type,
            "title": title,
            "summary": summary,
            "reason": reason,
            "risk": "low"
            if artifact_type
            in {
                "memory_reflection",
                "source_rule_candidate",
                "eval_candidate",
                "app_artifact_candidate",
                "app_identity_candidate",
                "health_check_candidate",
            }
            else "medium",
            "expected_behavior": expected,
            "review_criteria": [
                "candidate is visible in Qdrant",
                "candidate remains review-only until promoted",
            ],
            "confidence": "low" if reason != "heuristic_fallback" else "medium",
            "source": "learning_classifier_fallback",
        },
        event=event,
    )


class LearningClassifier:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def classify(
        self,
        event: Mapping[str, Any],
        *,
        user_id: str = "",
        source: str = "learning_classifier",
        request_id: str = "",
    ) -> dict[str, Any]:
        system = (
            "You classify ARIA learning events into review-only learning candidates. "
            "Return JSON only. Never create executable runtime behavior. "
            "Allowed artifact_type values: memory_reflection, routing_hint, source_rule_candidate, "
            "procedure_candidate, recipe_candidate, recipe_improvement, skill_candidate, eval_candidate, "
            "app_artifact_candidate, app_identity_candidate, install_plan_candidate, health_check_candidate, ignore. "
            "Use status='proposed' for useful candidates and status='ignored' for noise. "
            "Use risk low|medium|high. Higher risk means any side effect, automation, credentials, or runtime action. "
            "Do not invent evidence. Prefer source_rule_candidate for URL/source-quality feedback, "
            "procedure_candidate for reusable workflows, recipe_candidate for executable but review-only recipes, "
            "eval_candidate for regression tests, app_artifact_candidate for observed files/services/runtime inventory, "
            "app_identity_candidate for app-root/runtime-kind hypotheses, "
            "install_plan_candidate for install/update/deploy plan candidates, health_check_candidate for service/port/health checks, "
            "and ignore for transient chatter. "
            "Output keys: artifact_type,status,risk,title,summary,reason,proposed_change,review_criteria,"
            "eval_prompt,expected_behavior,confidence."
        )
        result = await self.decision_client.decide_json(
            operation="learning_event_classification",
            system=system,
            payload={"event": dict(event)},
            source=source,
            user_id=user_id or str(event.get("user_id", "") or ""),
            request_id=request_id,
        )
        if not result.ok:
            candidate = fallback_learning_candidate(event, reason=result.error or "classifier_unavailable")
        else:
            candidate = normalize_learning_candidate(result.payload, event=event)
            if confidence_score(candidate.get("confidence")) <= 0.0:
                candidate["confidence"] = "medium"
        metadata = dict(candidate.get("metadata", {}) or {})
        metadata["classification_usage"] = result.usage
        metadata["classifier_error"] = result.error
        candidate["metadata"] = metadata
        return candidate


async def store_learning_candidate(
    *,
    memory_skill: Any,
    candidate: Mapping[str, Any],
    user_id: str,
) -> Any:
    collection = learning_candidates_collection_for_user(user_id)
    text = build_learning_candidate_text(candidate)
    return await memory_skill.execute(
        query=text,
        params={
            "action": "store",
            "text": text,
            "user_id": user_id,
            "collection": collection,
            "memory_type": "learning_candidate",
            "source": "learning_classifier",
        },
    )
