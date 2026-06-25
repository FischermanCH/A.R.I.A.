from __future__ import annotations

import asyncio
import json

from aria.core.learning_classifier import LearningClassifier
from aria.core.learning_classifier import build_learning_candidate_text
from aria.core.learning_classifier import fallback_learning_candidate
from aria.core.learning_classifier import learning_candidates_collection_for_user
from aria.core.learning_classifier import normalize_learning_candidate


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}


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


def _event(summary: str) -> dict:
    return {
        "event_id": "evt-1",
        "event_type": "reflection",
        "artifact_type": "memory_reflection",
        "status": "observed",
        "risk": "low",
        "user_id": "u1",
        "source": "auto_memory",
        "summary": summary,
        "evidence": {"reflection": summary},
        "metadata": {"collection": "aria_learning_u1"},
    }


def test_learning_classifier_turns_area41_source_feedback_into_source_rule_candidate() -> None:
    llm = _LLM(
        {
            "artifact_type": "source_rule_candidate",
            "status": "proposed",
            "risk": "low",
            "title": "Official page excerpts first",
            "summary": "Prefer official page excerpts over snippets for concrete URL questions.",
            "reason": "The user corrected source handling.",
            "proposed_change": {"source_priority": ["official_page_excerpt", "search_snippet"]},
            "review_criteria": ["visible in Qdrant", "review-only"],
            "eval_prompt": "was sind die themen der speaker an der area41 konferenz 2026",
            "expected_behavior": "Fetch the official AREA41 page and answer from its excerpt.",
            "confidence": "high",
        }
    )

    candidate = asyncio.run(
        LearningClassifier(llm).classify(
            _event("For concrete conference URL questions, prefer official page excerpts over search snippets."),
            user_id="u1",
        )
    )

    assert llm.operations == ["learning_event_classification"]
    assert candidate["artifact_type"] == "source_rule_candidate"
    assert candidate["status"] == "proposed"
    assert candidate["risk"] == "low"
    assert candidate["metadata"]["classification_usage"]["total_tokens"] == 7
    assert "AREA41" in candidate["expected_behavior"]


def test_learning_classifier_fallback_keeps_source_feedback_review_only() -> None:
    candidate = fallback_learning_candidate(
        _event("Bei konkreten URLs offizielle Page Excerpts statt Such-Snippets nutzen."),
        reason="no_llm_client",
    )

    assert candidate["artifact_type"] == "source_rule_candidate"
    assert candidate["status"] == "proposed"
    assert candidate["source"] == "learning_classifier_fallback"


def test_learning_classifier_fallback_turns_host_artifacts_into_app_candidate() -> None:
    candidate = fallback_learning_candidate(
        {
            **_event("Runtime output exposed docker compose, systemd service, Dockerfile and package.json artifacts."),
            "artifact_type": "app_artifact_candidate",
            "source": "host_artifact_discovery",
        },
        reason="no_llm_client",
    )

    assert candidate["artifact_type"] == "app_artifact_candidate"
    assert candidate["risk"] == "low"
    assert "review-only inventory" in candidate["expected_behavior"]


def test_learning_classifier_fallback_turns_identity_hypothesis_into_identity_candidate() -> None:
    candidate = fallback_learning_candidate(
        {
            **_event("App identity hypothesis has runtime_kind docker_compose and app_root /srv/aria."),
            "artifact_type": "app_identity_candidate",
            "source": "host_artifact_discovery",
        },
        reason="no_llm_client",
    )

    assert candidate["artifact_type"] == "app_identity_candidate"
    assert candidate["risk"] == "low"
    assert "identity hypothesis" in candidate["expected_behavior"]


def test_learning_classifier_accepts_install_plan_candidate_from_llm() -> None:
    llm = _LLM(
        {
            "artifact_type": "install_plan_candidate",
            "status": "proposed",
            "risk": "medium",
            "title": "Install plan from compose artifacts",
            "summary": "Build a review-only install plan from observed compose and Dockerfile artifacts.",
            "reason": "Host inventory exposed install/update relevant files.",
            "proposed_change": {"requires": ["preview", "rollback", "health_check"]},
            "review_criteria": ["dry-run exists", "rollback exists"],
            "eval_prompt": "installiere diese app sauber",
            "expected_behavior": "Preview files and health gates before installing.",
            "confidence": "high",
        }
    )

    candidate = asyncio.run(
        LearningClassifier(llm).classify(
            _event("Runtime output exposed compose.yaml and Dockerfile for an install/update plan."),
            user_id="u1",
        )
    )

    assert candidate["artifact_type"] == "install_plan_candidate"
    assert candidate["risk"] == "medium"
    assert any("rollback" in item for item in candidate["review_criteria"])


def test_learning_candidate_text_and_collection_are_qdrant_friendly() -> None:
    candidate = normalize_learning_candidate(
        {
            "artifact_type": "procedure_candidate",
            "title": "Server update flow",
            "summary": "Reusable workflow candidate",
            "reason": "Repeated behavior",
            "review_criteria": ["dry run exists"],
        },
        event=_event("Wenn ich Serverupdate sage, soll ARIA erst pruefen und dann fragen."),
    )

    text = build_learning_candidate_text(candidate)

    assert learning_candidates_collection_for_user("U 1") == "aria_learning_candidates_u_1"
    assert "Learning Candidate: Server update flow" in text
    assert "Type: procedure_candidate" in text
    assert "Review criteria: dry run exists" in text


def test_learning_candidate_text_includes_app_identity_and_plan_draft() -> None:
    candidate = normalize_learning_candidate(
        {
            "artifact_type": "install_plan_candidate",
            "title": "Compose install plan",
            "summary": "Review-only install plan from app identity.",
            "evidence": {
                "app_identity_hypothesis": {"runtime_kind": "docker_compose", "app_root": "/srv/aria"},
                "install_update_plan_draft": {
                    "plan_kind": "install_update_plan_draft",
                    "requires_confirmation": True,
                    "runtime_activation_allowed": False,
                },
                "install_update_plan_validation": {
                    "validation_state": "review_required",
                    "runtime_activation_allowed": False,
                    "promotion_allowed": False,
                },
                "health_check_drafts": [
                    {"check_kind": "tcp_port", "target": "8080", "mutating": False},
                ],
                "regression_drafts": [
                    {"test_kind": "plan_preview", "name": "test_install_update_plan_renders_without_execution"},
                ],
                "pytest_skeleton_proposal": {
                    "proposal_kind": "pytest_skeleton_proposal",
                    "target_file": "tests/test_app_plan_generated.py",
                    "test_functions": [{"name": "test_install_update_plan_renders_without_execution"}],
                    "write_allowed": False,
                    "runtime_activation_allowed": False,
                },
            },
        },
        event=_event("Observed compose app identity."),
    )

    text = build_learning_candidate_text(candidate)

    assert "App identity hypothesis:" in text
    assert "docker_compose" in text
    assert "Install/update plan draft:" in text
    assert "runtime_activation_allowed" in text
    assert "Install/update plan validation:" in text
    assert "review_required" in text
    assert "Health check drafts:" in text
    assert "Regression drafts:" in text
    assert "Pytest skeleton proposal:" in text
    assert "tests/test_app_plan_generated.py" in text
