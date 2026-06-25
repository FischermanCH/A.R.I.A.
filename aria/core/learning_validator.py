from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.learning_events import redact_learning_payload


def _clean_text(value: Any, *, limit: int = 1600) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clean_list(value: Any, *, limit: int = 10) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        clean = _clean_text(item, limit=260)
        if clean:
            rows.append(clean)
        if len(rows) >= limit:
            break
    return rows


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def learning_evals_collection_for_user(user_id: str) -> str:
    return f"aria_learning_evals_{_slug_user_id(user_id)}"


def normalize_learning_eval(eval_spec: Mapping[str, Any], *, candidate: Mapping[str, Any]) -> dict[str, Any]:
    eval_id = _clean_text(eval_spec.get("eval_id"), limit=160) or f"learning-eval-{uuid4().hex}"
    artifact_type = _clean_text(candidate.get("artifact_type"), limit=80)
    return {
        "eval_id": eval_id,
        "created_at": _clean_text(eval_spec.get("created_at") or datetime.now(timezone.utc).isoformat(), limit=80),
        "candidate_id": _clean_text(candidate.get("candidate_id"), limit=160),
        "event_id": _clean_text(candidate.get("event_id"), limit=160),
        "user_id": _clean_text(candidate.get("user_id"), limit=120),
        "candidate_type": artifact_type,
        "status": _clean_text(eval_spec.get("status") or "dry_run", limit=60),
        "promotion_allowed": bool(eval_spec.get("promotion_allowed") is True),
        "blockers": _clean_list(eval_spec.get("blockers") or ["review_required", "validator_not_promoting_yet"]),
        "eval_prompt": _clean_text(eval_spec.get("eval_prompt") or candidate.get("eval_prompt") or candidate.get("summary"), limit=600),
        "expected_path": _clean_text(eval_spec.get("expected_path"), limit=600),
        "expected_behavior": _clean_text(
            eval_spec.get("expected_behavior") or candidate.get("expected_behavior") or candidate.get("summary"),
            limit=900,
        ),
        "negative_examples": _clean_list(eval_spec.get("negative_examples")),
        "dry_run_steps": _clean_list(eval_spec.get("dry_run_steps")),
        "review_notes": _clean_text(eval_spec.get("review_notes") or eval_spec.get("reason"), limit=900),
        "source": _clean_text(eval_spec.get("source") or "learning_validator", limit=120),
        "metadata": redact_learning_payload(eval_spec.get("metadata") or {}),
    }


def fallback_learning_eval(candidate: Mapping[str, Any], *, reason: str = "validator_unavailable") -> dict[str, Any]:
    artifact_type = _clean_text(candidate.get("artifact_type"), limit=80)
    summary = _clean_text(candidate.get("summary"), limit=600)
    if artifact_type == "source_rule_candidate":
        expected_path = "web_search -> fetch official page excerpt -> answer from official excerpt"
        negative_examples = [
            "answer from search snippets only when an official page excerpt is available",
            "prefer aggregator snippets over the official source",
        ]
    elif artifact_type in {"procedure_candidate", "recipe_candidate", "recipe_improvement"}:
        expected_path = "candidate review -> dry-run -> policy/guardrail validation -> explicit promotion"
        negative_examples = [
            "activate candidate without review",
            "execute side effects before confirmation",
        ]
    elif artifact_type == "skill_candidate":
        expected_path = "skill idea -> contract review -> implementation proposal -> tests -> policy/guardrail validation -> explicit promotion"
        negative_examples = [
            "generate or activate code from one observed workflow",
            "treat a skill idea as an executable runtime capability",
        ]
    elif artifact_type == "app_artifact_candidate":
        expected_path = "host artifact inventory -> app identity hypothesis -> review -> plan/eval candidates"
        negative_examples = [
            "infer an app install plan from one filename without review",
            "overwrite files before inventory and rollback are reviewed",
        ]
    elif artifact_type == "app_identity_candidate":
        expected_path = "artifact inventory -> app-root/runtime-kind hypothesis -> review -> install/update and health candidates"
        negative_examples = [
            "treat an app identity hypothesis as confirmed without review",
            "derive mutating install steps before app root, runtime kind, rollback, and health surfaces are reviewed",
        ]
    elif artifact_type == "install_plan_candidate":
        expected_path = "artifact inventory -> install/update preview -> rollback plan -> policy/guardrail validation -> explicit confirmation"
        negative_examples = [
            "install or update packages without preview",
            "skip backup, rollback, or health checks",
        ]
    elif artifact_type == "health_check_candidate":
        expected_path = "observed service/port/health signal -> review -> non-mutating health check -> regression"
        negative_examples = [
            "treat one passing port as full app health",
            "run mutating diagnostics as a health check",
        ]
    elif artifact_type == "artifact_pattern_candidate":
        expected_path = "accepted prepared artifact -> pattern review -> future proposal guidance"
        negative_examples = [
            "treat an accepted artifact as permission to write files automatically",
            "promote a pattern without regression coverage",
        ]
    elif artifact_type == "artifact_improvement_candidate":
        expected_path = "needs-changes review -> improvement candidate -> revised proposal criteria"
        negative_examples = [
            "repeat the same weak artifact without using review notes",
            "turn review notes into a hard runtime rule",
        ]
    elif artifact_type == "negative_pattern_candidate":
        expected_path = "rejected prepared artifact -> negative pattern review -> avoid repeating proposal shape"
        negative_examples = [
            "suggest the same rejected target or structure again",
            "delete or mutate generated files because a proposal was rejected",
        ]
    elif artifact_type == "eval_candidate":
        expected_path = "turn incident into regression prompt -> expected behavior -> negative example"
        negative_examples = ["keep incident only as vague memory without regression criteria"]
    else:
        expected_path = "review candidate -> keep as context until validator/eval gates pass"
        negative_examples = ["promote candidate automatically"]
    return normalize_learning_eval(
        {
            "status": "dry_run",
            "promotion_allowed": False,
            "blockers": ["review_required", "eval_gate_missing", "promotion_gate_missing"],
            "eval_prompt": candidate.get("eval_prompt") or summary,
            "expected_path": expected_path,
            "expected_behavior": candidate.get("expected_behavior") or summary,
            "negative_examples": negative_examples,
            "dry_run_steps": [
                "inspect the candidate in Qdrant",
                "verify evidence and expected behavior",
                "build or attach a regression test before promotion",
            ],
            "review_notes": reason,
            "source": "learning_validator_fallback",
        },
        candidate=candidate,
    )


def build_learning_eval_text(eval_spec: Mapping[str, Any]) -> str:
    blockers = _clean_list(eval_spec.get("blockers"))
    negative_examples = _clean_list(eval_spec.get("negative_examples"))
    dry_run_steps = _clean_list(eval_spec.get("dry_run_steps"))
    parts = [
        f"Learning Eval Dry-Run: {_clean_text(eval_spec.get('candidate_type'), limit=120)}",
        f"Status: {_clean_text(eval_spec.get('status'), limit=80)}",
        f"Promotion allowed: {'yes' if eval_spec.get('promotion_allowed') is True else 'no'}",
        f"Candidate: {_clean_text(eval_spec.get('candidate_id'), limit=160)}",
        f"Event: {_clean_text(eval_spec.get('event_id'), limit=160)}",
        f"Eval prompt: {_clean_text(eval_spec.get('eval_prompt'), limit=700)}",
        f"Expected path: {_clean_text(eval_spec.get('expected_path'), limit=800)}",
        f"Expected behavior: {_clean_text(eval_spec.get('expected_behavior'), limit=900)}",
        "Blockers: " + "; ".join(blockers) if blockers else "",
        "Negative examples: " + "; ".join(negative_examples) if negative_examples else "",
        "Dry-run steps: " + "; ".join(dry_run_steps) if dry_run_steps else "",
        f"Review notes: {_clean_text(eval_spec.get('review_notes'), limit=800)}",
    ]
    return "\n".join(part for part in parts if part and not part.endswith(": ")).strip()


class LearningCandidateValidator:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def validate(
        self,
        candidate: Mapping[str, Any],
        *,
        user_id: str = "",
        source: str = "learning_validator",
        request_id: str = "",
    ) -> dict[str, Any]:
        system = (
            "You create a review-only validation and eval dry-run for an ARIA learning candidate. "
            "Return JSON only. Never allow promotion. Set promotion_allowed=false. "
            "Create concrete blockers, one eval_prompt, expected_path, expected_behavior, "
            "negative_examples, dry_run_steps, and review_notes. "
            "For source_rule_candidate, focus on official page excerpt vs snippet behavior. "
            "For recipe/procedure/skill candidates, require review, policy/guardrail validation, and tests. "
            "For app_artifact_candidate, app_identity_candidate, install_plan_candidate, and health_check_candidate, require inventory evidence, "
            "dry-run/preview, rollback or non-mutating health gates, and explicit review before any runtime use. "
            "Output keys: status,promotion_allowed,blockers,eval_prompt,expected_path,expected_behavior,"
            "negative_examples,dry_run_steps,review_notes."
        )
        result = await self.decision_client.decide_json(
            operation="learning_candidate_validation",
            system=system,
            payload={"candidate": dict(candidate)},
            source=source,
            user_id=user_id or str(candidate.get("user_id", "") or ""),
            request_id=request_id,
        )
        if not result.ok:
            eval_spec = fallback_learning_eval(candidate, reason=result.error or "validator_unavailable")
        else:
            payload = dict(result.payload)
            payload["promotion_allowed"] = False
            blockers = _clean_list(payload.get("blockers"))
            if "promotion_gate_missing" not in blockers:
                blockers.append("promotion_gate_missing")
            payload["blockers"] = blockers
            eval_spec = normalize_learning_eval(payload, candidate=candidate)
        metadata = dict(eval_spec.get("metadata", {}) or {})
        metadata["validation_usage"] = result.usage
        metadata["validator_error"] = result.error
        eval_spec["metadata"] = metadata
        return eval_spec


async def store_learning_eval(
    *,
    memory_skill: Any,
    eval_spec: Mapping[str, Any],
    user_id: str,
) -> Any:
    collection = learning_evals_collection_for_user(user_id)
    text = build_learning_eval_text(eval_spec)
    return await memory_skill.execute(
        query=text,
        params={
            "action": "store",
            "text": text,
            "user_id": user_id,
            "collection": collection,
            "memory_type": "learning_eval",
            "source": "learning_validator",
        },
    )
