from __future__ import annotations

from aria.core.learning_promotion import build_learning_candidate_activation_preview
from aria.core.learning_promotion import learning_candidate_gate_inputs
from aria.core.learning_promotion import build_learning_candidate_apply_preview
from aria.core.learning_promotion import learning_active_hint_store_params
from aria.core.learning_promotion import learning_active_hints_collection_for_user
from aria.core.learning_promotion import learning_candidate_activation_preflight_payload
from aria.core.learning_promotion import link_learning_candidate_regression_payload
from aria.core.learning_promotion import prepare_learning_candidate_apply_payload
from aria.core.learning_promotion import learning_candidate_promotion_gate
from aria.core.learning_promotion import run_learning_candidate_regression_payload
from aria.core.learning_promotion import verify_learning_candidate_regression_payload


def test_learning_candidate_gate_inputs_parse_type_and_risk_from_text() -> None:
    inputs = learning_candidate_gate_inputs(
        {
            "text": (
                "Learning Candidate: Official page excerpts first\n"
                "Type: source_rule_candidate\n"
                "Status: proposed\n"
                "Risk: low"
            )
        }
    )

    assert inputs == {"artifact_type": "source_rule_candidate", "risk": "low"}


def test_learning_candidate_promotion_gate_marks_low_risk_source_rule_eligible() -> None:
    payload = learning_candidate_promotion_gate(
        artifact_type="source_rule_candidate",
        risk="low",
        decision="review",
        reviewed_by="neo",
    )

    assert payload["promotion_state"] == "eligible"
    assert payload["promotion_gate_result"] == "eligible"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_promotion_gate_blocks_procedure_candidates() -> None:
    payload = learning_candidate_promotion_gate(
        artifact_type="procedure_candidate",
        risk="medium",
        decision="review",
        reviewed_by="neo",
    )

    assert payload["promotion_state"] == "reviewed_blocked"
    assert payload["promotion_gate_result"] == "blocked"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_promotion_gate_rejects_candidate() -> None:
    payload = learning_candidate_promotion_gate(
        artifact_type="routing_hint",
        risk="low",
        decision="reject",
        reviewed_by="neo",
    )

    assert payload["promotion_state"] == "rejected"
    assert payload["promotion_gate_result"] == "rejected"


def test_prepare_learning_candidate_apply_payload_prepares_only_eligible_low_risk_candidate() -> None:
    payload = prepare_learning_candidate_apply_payload(
        artifact_type="source_rule_candidate",
        risk="low",
        promotion_state="eligible",
        candidate_text="Learning Candidate: Official page excerpts first",
        applied_by="neo",
    )

    assert payload["apply_state"] == "prepared"
    assert payload["apply_gate_result"] == "prepared"
    assert payload["apply_requires_regression"] is True
    assert payload["regression_required"] is True
    assert payload["regression_status"] == "missing"
    assert payload["runtime_activation_allowed"] is False


def test_prepare_learning_candidate_apply_payload_blocks_non_eligible_candidate() -> None:
    payload = prepare_learning_candidate_apply_payload(
        artifact_type="source_rule_candidate",
        risk="low",
        promotion_state="reviewed",
        candidate_text="Learning Candidate: Official page excerpts first",
        applied_by="neo",
    )

    assert payload["apply_state"] == "blocked"
    assert payload["apply_gate_result"] == "blocked"
    assert payload["runtime_activation_allowed"] is False


def test_build_learning_candidate_apply_preview_keeps_runtime_disabled() -> None:
    preview = build_learning_candidate_apply_preview(
        artifact_type="source_rule_candidate",
        risk="low",
        apply_state="prepared",
        candidate_text=(
            "Learning Candidate: Official page excerpts first\n"
            "Type: source_rule_candidate\n"
            "Summary: Prefer fetched official pages."
        ),
        collection="aria_learning_candidates_u1",
        point_id="candidate-1",
    )

    assert preview["allowed"] is True
    assert preview["proposed_kind"] == "source_rule"
    assert preview["regression_required"] is True
    assert preview["regression_status"] == "missing"
    assert "regression_missing" in preview["blockers"]
    assert preview["runtime_activation"] == "disabled"
    assert preview["runtime_activation_allowed"] is False


def test_build_learning_candidate_apply_preview_shows_linked_regression() -> None:
    preview = build_learning_candidate_apply_preview(
        artifact_type="routing_hint",
        risk="low",
        apply_state="prepared",
        candidate_text="Learning Candidate: Route explicit recall to memory",
        regression_status="linked",
        regression_ref="tests/test_pipeline.py::test_explicit_recall_uses_memory",
    )

    assert preview["regression_status"] == "linked"
    assert preview["regression_linked"] is True
    assert preview["regression_ref"] == "tests/test_pipeline.py::test_explicit_recall_uses_memory"
    assert "regression_missing" not in preview["blockers"]


def test_build_learning_candidate_apply_preview_blocks_unprepared_candidate() -> None:
    preview = build_learning_candidate_apply_preview(
        artifact_type="source_rule_candidate",
        risk="low",
        apply_state="eligible",
        candidate_text="Learning Candidate: Official page excerpts first",
    )

    assert preview["allowed"] is False
    assert preview["proposed_state"] == "blocked"
    assert "candidate_not_prepared_or_not_low_risk" in preview["blockers"]


def test_link_learning_candidate_regression_payload_accepts_test_ref() -> None:
    payload = link_learning_candidate_regression_payload(
        regression_ref="tests/test_pipeline.py::test_explicit_recall_uses_memory",
        linked_by="neo",
    )

    assert payload["regression_status"] == "linked"
    assert payload["regression_ref"] == "tests/test_pipeline.py::test_explicit_recall_uses_memory"
    assert payload["regression_link_result"] == "linked"
    assert payload["runtime_activation_allowed"] is False


def test_link_learning_candidate_regression_payload_rejects_non_test_ref() -> None:
    payload = link_learning_candidate_regression_payload(
        regression_ref="docs/manual-check.md",
        linked_by="neo",
    )

    assert payload["regression_status"] == "missing"
    assert payload["regression_ref"] == ""
    assert payload["regression_link_result"] == "invalid"
    assert payload["runtime_activation_allowed"] is False


def test_verify_learning_candidate_regression_payload_finds_existing_test() -> None:
    payload = verify_learning_candidate_regression_payload(
        regression_ref="tests/test_learning_promotion.py::test_verify_learning_candidate_regression_payload_finds_existing_test",
        repo_root=".",
        verified_by="neo",
    )

    assert payload["regression_status"] == "linked"
    assert payload["regression_verified"] is True
    assert payload["regression_test_exists"] is True
    assert payload["regression_verify_result"] == "not_run"
    assert payload["runtime_activation_allowed"] is False


def test_verify_learning_candidate_regression_payload_marks_missing_file() -> None:
    payload = verify_learning_candidate_regression_payload(
        regression_ref="tests/test_missing_file.py::test_nope",
        repo_root=".",
        verified_by="neo",
    )

    assert payload["regression_status"] == "linked"
    assert payload["regression_verified"] is False
    assert payload["regression_test_exists"] is False
    assert payload["regression_verify_result"] == "missing"
    assert payload["regression_verify_reason"] == "test_file_missing"


def test_verify_learning_candidate_regression_payload_marks_missing_test_name() -> None:
    payload = verify_learning_candidate_regression_payload(
        regression_ref="tests/test_learning_promotion.py::test_nope",
        repo_root=".",
        verified_by="neo",
    )

    assert payload["regression_verified"] is False
    assert payload["regression_verify_result"] == "missing"
    assert payload["regression_verify_reason"] == "test_name_missing"


def test_run_learning_candidate_regression_payload_runs_existing_test() -> None:
    payload = run_learning_candidate_regression_payload(
        regression_ref="tests/test_learning_promotion.py::test_link_learning_candidate_regression_payload_accepts_test_ref",
        repo_root=".",
        run_by="neo",
        timeout_seconds=30,
    )

    assert payload["regression_status"] == "linked"
    assert payload["regression_verified"] is True
    assert payload["regression_test_exists"] is True
    assert payload["regression_verify_result"] == "passed"
    assert payload["regression_run_returncode"] == 0
    assert payload["runtime_activation_allowed"] is False


def test_run_learning_candidate_regression_payload_does_not_run_missing_test() -> None:
    payload = run_learning_candidate_regression_payload(
        regression_ref="tests/test_learning_promotion.py::test_missing_case",
        repo_root=".",
        run_by="neo",
        timeout_seconds=30,
    )

    assert payload["regression_verified"] is False
    assert payload["regression_verify_result"] == "missing"
    assert payload["regression_last_run_output"] == "test_name_missing"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_activation_preflight_requires_passed_regression() -> None:
    payload = learning_candidate_activation_preflight_payload(
        artifact_type="source_rule_candidate",
        risk="low",
        promotion_state="eligible",
        apply_state="prepared",
        regression_status="linked",
        regression_verified=True,
        regression_verify_result="passed",
        checked_by="admin",
    )

    assert payload["activation_preflight_state"] == "passed"
    assert payload["activation_ready"] is True
    assert payload["activation_runtime_effect"] == "weak_signal_only"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_activation_preflight_blocks_missing_regression_run() -> None:
    payload = learning_candidate_activation_preflight_payload(
        artifact_type="routing_hint",
        risk="low",
        promotion_state="eligible",
        apply_state="prepared",
        regression_status="linked",
        regression_verified=True,
        regression_verify_result="not_run",
        checked_by="admin",
    )

    assert payload["activation_preflight_state"] == "blocked"
    assert "regression_not_passed" in payload["activation_blockers"]
    assert payload["runtime_activation_allowed"] is False


def test_activation_preview_and_store_params_target_qdrant_active_hint_collection() -> None:
    preview = build_learning_candidate_activation_preview(
        artifact_type="routing_hint",
        risk="low",
        candidate_text=(
            "Learning Candidate: Route URL questions\n"
            "Type: routing_hint\n"
            "Summary: Concrete source URLs should bias toward web_search."
        ),
        collection="aria_learning_candidates_u_1",
        point_id="p1",
        regression_ref="tests/test_turn_intent_arbitration.py::test_turn_intent_arbitration_can_override_keyword_signal_to_chat",
        activation_preflight_state="passed",
        user_id="U 1",
    )
    params = learning_active_hint_store_params(preview=preview, user_id="U 1")

    assert preview["activation_allowed"] is True
    assert preview["active_hint_collection"] == "aria_learning_active_hints_u_1"
    assert learning_active_hints_collection_for_user("U 1") == "aria_learning_active_hints_u_1"
    assert params["action"] == "store"
    assert params["collection"] == "aria_learning_active_hints_u_1"
    assert params["memory_type"] == "learning_active_hint"
    assert "weak learned signal" in params["text"]
