from __future__ import annotations

import asyncio
import json

from aria.core.learning_validator import LearningCandidateValidator
from aria.core.learning_validator import build_learning_eval_text
from aria.core.learning_validator import fallback_learning_eval
from aria.core.learning_validator import learning_evals_collection_for_user
from aria.core.learning_validator import normalize_learning_eval


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}


class _LLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.operations: list[str] = []

    async def chat(self, messages, **kwargs):
        _ = messages
        operation = str(kwargs.get("operation") or "")
        if operation:
            self.operations.append(operation)
        return _Response(json.dumps(self.payload))


def _candidate() -> dict:
    return {
        "candidate_id": "cand-1",
        "event_id": "evt-1",
        "user_id": "u1",
        "artifact_type": "source_rule_candidate",
        "status": "proposed",
        "risk": "low",
        "title": "Official page excerpts first",
        "summary": "Prefer official page excerpts over snippets for concrete URL questions.",
        "eval_prompt": "was sind die themen der speaker an der area41 konferenz 2026",
        "expected_behavior": "Fetch official page excerpts and answer from those.",
    }


def test_learning_candidate_validator_creates_review_only_eval_spec() -> None:
    llm = _LLM(
        {
            "status": "dry_run",
            "promotion_allowed": True,
            "blockers": ["review_required"],
            "eval_prompt": "was sind die themen der speaker an der area41 konferenz 2026",
            "expected_path": "web_search -> official page excerpt -> answer",
            "expected_behavior": "Use official AREA41 page excerpts over snippets.",
            "negative_examples": ["answer from snippets only"],
            "dry_run_steps": ["run prompt", "inspect sources"],
            "review_notes": "candidate needs source regression",
        }
    )

    eval_spec = asyncio.run(LearningCandidateValidator(llm).validate(_candidate(), user_id="u1"))

    assert llm.operations == ["learning_candidate_validation"]
    assert eval_spec["promotion_allowed"] is False
    assert "promotion_gate_missing" in eval_spec["blockers"]
    assert eval_spec["metadata"]["validation_usage"]["total_tokens"] == 11
    assert "official" in eval_spec["expected_path"]


def test_learning_validator_fallback_creates_source_rule_dry_run() -> None:
    eval_spec = fallback_learning_eval(_candidate(), reason="no_llm_client")

    assert eval_spec["status"] == "dry_run"
    assert eval_spec["promotion_allowed"] is False
    assert "eval_gate_missing" in eval_spec["blockers"]
    assert "official page excerpt" in eval_spec["expected_path"]


def test_learning_validator_fallback_creates_app_artifact_inventory_dry_run() -> None:
    candidate = {
        **_candidate(),
        "artifact_type": "app_artifact_candidate",
        "summary": "Observed compose.yaml, Dockerfile, app.service and port 8080.",
    }

    eval_spec = fallback_learning_eval(candidate, reason="no_llm_client")

    assert eval_spec["promotion_allowed"] is False
    assert "host artifact inventory" in eval_spec["expected_path"]
    assert "overwrite files" in "; ".join(eval_spec["negative_examples"])


def test_learning_validator_fallback_creates_app_identity_dry_run() -> None:
    candidate = {
        **_candidate(),
        "artifact_type": "app_identity_candidate",
        "summary": "Hypothesis: runtime_kind docker_compose, app_root /srv/app, port 8080.",
    }

    eval_spec = fallback_learning_eval(candidate, reason="no_llm_client")

    assert eval_spec["promotion_allowed"] is False
    assert "app-root/runtime-kind hypothesis" in eval_spec["expected_path"]
    assert "without review" in "; ".join(eval_spec["negative_examples"])


def test_learning_validator_fallback_creates_install_plan_dry_run() -> None:
    candidate = {
        **_candidate(),
        "artifact_type": "install_plan_candidate",
        "risk": "medium",
        "summary": "Observed compose.yaml and Dockerfile for a possible install plan.",
    }

    eval_spec = fallback_learning_eval(candidate, reason="no_llm_client")

    assert eval_spec["promotion_allowed"] is False
    assert "rollback plan" in eval_spec["expected_path"]
    assert "skip backup" in "; ".join(eval_spec["negative_examples"])


def test_learning_validator_fallback_creates_health_check_dry_run() -> None:
    candidate = {
        **_candidate(),
        "artifact_type": "health_check_candidate",
        "summary": "Observed app.service active and port 8080 listening.",
    }

    eval_spec = fallback_learning_eval(candidate, reason="no_llm_client")

    assert eval_spec["promotion_allowed"] is False
    assert "non-mutating health check" in eval_spec["expected_path"]
    assert "one passing port" in "; ".join(eval_spec["negative_examples"])


def test_learning_eval_text_and_collection_are_qdrant_friendly() -> None:
    eval_spec = normalize_learning_eval(
        {
            "status": "dry_run",
            "promotion_allowed": False,
            "blockers": ["review_required"],
            "expected_path": "candidate review",
            "expected_behavior": "do not promote automatically",
        },
        candidate=_candidate(),
    )

    text = build_learning_eval_text(eval_spec)

    assert learning_evals_collection_for_user("U 1") == "aria_learning_evals_u_1"
    assert "Learning Eval Dry-Run: source_rule_candidate" in text
    assert "Promotion allowed: no" in text
    assert "Blockers: review_required" in text
