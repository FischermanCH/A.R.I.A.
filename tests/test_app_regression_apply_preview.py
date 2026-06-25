from __future__ import annotations

from pathlib import Path

from aria.core.app_regression_apply_preview import build_pytest_apply_preview
from aria.core.app_regression_apply_preview import prepare_prepared_artifact_review_payload
from aria.core.app_regression_apply_preview import prepare_pytest_write_payload


def _proposal(**updates):
    base = {
        "proposal_kind": "pytest_skeleton_proposal",
        "target_file": "tests/test_app_plan_generated.py",
        "test_functions": [
            {
                "name": "test_install_update_plan_renders_without_execution",
                "test_kind": "plan_preview",
                "arrange": ["build plan"],
                "act": "call preview helper",
                "assert": ["runtime_activation_allowed is false"],
            }
        ],
        "write_allowed": False,
        "runtime_activation_allowed": False,
    }
    base.update(updates)
    return base


def test_build_pytest_apply_preview_renders_code_without_writing(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()

    preview = build_pytest_apply_preview(_proposal(), repo_root=tmp_path)

    assert preview["preview_state"] == "preview_ready"
    assert preview["target_file"] == "tests/test_app_plan_generated.py"
    assert preview["target_exists"] is False
    assert preview["write_allowed"] is False
    assert preview["runtime_activation_allowed"] is False
    assert "def test_install_update_plan_renders_without_execution()" in preview["code_preview"]
    assert "assert True" in preview["code_preview"]


def test_build_pytest_apply_preview_blocks_target_outside_tests(tmp_path: Path) -> None:
    preview = build_pytest_apply_preview(_proposal(target_file="aria/test_bad.py"), repo_root=tmp_path)

    assert preview["preview_state"] == "blocked"
    assert "target_outside_tests" in preview["blockers"]
    assert preview["write_allowed"] is False


def test_build_pytest_apply_preview_flags_existing_file_and_duplicate_function(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    target = tests_dir / "test_app_plan_generated.py"
    target.write_text(
        "def test_install_update_plan_renders_without_execution():\n    assert True\n",
        encoding="utf-8",
    )

    preview = build_pytest_apply_preview(_proposal(), repo_root=tmp_path)

    assert preview["preview_state"] == "blocked"
    assert preview["target_exists"] is True
    assert "target_file_exists" in preview["warnings"]
    assert "duplicate_test_function" in preview["blockers"]
    assert preview["duplicate_functions"] == ["test_install_update_plan_renders_without_execution"]


def test_build_pytest_apply_preview_ignores_write_allowed_true(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()

    preview = build_pytest_apply_preview(_proposal(write_allowed=True), repo_root=tmp_path)

    assert preview["write_allowed"] is False
    assert "proposal_write_allowed_true_ignored" in preview["warnings"]


def test_prepare_pytest_write_payload_prepares_qdrant_payload_without_write_permission(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    preview = build_pytest_apply_preview(_proposal(), repo_root=tmp_path)

    payload = prepare_pytest_write_payload(preview, prepared_by="tester")

    assert payload["pytest_write_state"] == "prepared"
    assert payload["pytest_write_gate_result"] == "prepared"
    assert payload["pytest_write_requires_review"] is True
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert payload["pytest_target_file"] == "tests/test_app_plan_generated.py"
    assert payload["pytest_test_functions"] == ["test_install_update_plan_renders_without_execution"]
    assert "def test_install_update_plan_renders_without_execution()" in payload["pytest_code_preview"]
    assert len(payload["pytest_code_preview_sha256"]) == 64
    assert payload["pytest_write_blockers"] == []


def test_prepare_pytest_write_payload_blocks_unready_preview(tmp_path: Path) -> None:
    preview = build_pytest_apply_preview(_proposal(target_file="aria/test_bad.py"), repo_root=tmp_path)

    payload = prepare_pytest_write_payload(preview, prepared_by="tester")

    assert payload["pytest_write_state"] == "blocked"
    assert payload["pytest_write_gate_result"] == "blocked"
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert "target_outside_tests" in payload["pytest_write_blockers"]
    assert "pytest_code_preview" not in payload
    assert len(payload["pytest_code_preview_sha256"]) == 64


def test_prepare_prepared_artifact_review_payload_records_accepted_feedback_without_write_permission() -> None:
    payload = prepare_prepared_artifact_review_payload(
        artifact_kind="pytest_skeleton_write",
        decision="accepted",
        review_notes="Looks useful.",
        reviewed_by="tester",
        prepared_state="prepared",
        code_preview_sha256="abc123",
        target_file="tests/test_app_plan_generated.py",
    )

    assert payload["prepared_artifact_review_state"] == "reviewed"
    assert payload["prepared_artifact_review_decision"] == "accepted"
    assert payload["prepared_artifact_review_signal"] == "positive"
    assert payload["pytest_write_review_state"] == "reviewed"
    assert payload["pytest_write_review_decision"] == "accepted"
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert payload["prepared_artifact_code_preview_sha256"] == "abc123"


def test_prepare_prepared_artifact_review_payload_blocks_unprepared_artifact() -> None:
    payload = prepare_prepared_artifact_review_payload(
        artifact_kind="pytest_skeleton_write",
        decision="accepted",
        reviewed_by="tester",
        prepared_state="blocked",
    )

    assert payload["prepared_artifact_review_state"] == "blocked"
    assert payload["prepared_artifact_review_decision"] == "accepted"
    assert "artifact_not_prepared" in payload["prepared_artifact_review_blockers"]
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
