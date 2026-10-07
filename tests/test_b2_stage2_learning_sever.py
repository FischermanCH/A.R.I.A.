from __future__ import annotations

from pathlib import Path

from aria.modules.memory_admin_ui.manifest import MODULE_MANIFEST as MEMORY_ADMIN_UI_MANIFEST
from aria.modules.pipeline_orchestrator.manifest import MODULE_MANIFEST as PIPELINE_MANIFEST
from aria.modules.pipeline_orchestrator.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_maintenance_surface_removes_legacy_learning_but_keeps_native_reset() -> None:
    template = _source("aria/templates/memories_maintenance.html")
    routes = _source("aria/modules/memory_admin_ui/routes.py")
    registered_routes = set(MEMORY_ADMIN_UI_MANIFEST["routes"])

    assert "Learning Worker" not in template
    assert "Self-Learning" not in template
    assert "learning_worker_status" not in template
    assert "self_learning" not in template
    assert "/memories/maintenance/reset-learning-suggestions" in template
    assert "Lern-Vorschläge zurücksetzen" in template

    for removed_symbol in (
        "_build_learning_review_queue",
        "_build_self_learning_maintenance_snapshot",
        "get_learning_worker_job",
        "get_learning_worker_status",
        "retry_learning_job",
        "flush_learning_worker_jobs",
    ):
        assert removed_symbol not in routes
    for removed_route in (
        "/memories/learning-worker/job/{job_id}",
        "/memories/learning-worker/retry",
        "/memories/learning-worker/flush",
    ):
        assert removed_route not in routes
        assert removed_route not in registered_routes
    assert "/memories/maintenance/reset-learning-suggestions" in routes
    assert "/memories/maintenance/reset-learning-suggestions" in registered_routes


def test_pipeline_no_longer_couples_learning_helpers_or_handlers() -> None:
    source = _source("aria/modules/pipeline_orchestrator/pipeline.py")
    dependency_ids = set(PIPELINE_MANIFEST["depends_on"])

    assert "PipelineLearningHelpersMixin" not in source
    assert "_register_learning_job_handlers" not in source
    assert all(base.__name__ != "PipelineLearningHelpersMixin" for base in Pipeline.__mro__)
    assert "learning_runtime" not in dependency_ids


def test_recipe_runtime_has_no_learning_governance_or_event_ledger_coupling() -> None:
    source = _source("aria/modules/recipe_runtime/runtime.py")

    for removed_symbol in (
        "record_learning_event",
        "LEARNING_EFFECT_AUDIT",
        "learning_content_fingerprint",
        "learning_events_collection_for_user",
        "learning_events_collection",
    ):
        assert removed_symbol not in source


def test_core_memory_bridge_remains_after_legacy_learning_removal() -> None:
    assert (ROOT / "aria/modules/memory_learning_bridge/skill.py").is_file()
    for removed in ("learning_runtime", "learning_candidates", "learning_governance"):
        assert not (ROOT / "aria/modules" / removed).exists()
