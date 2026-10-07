from __future__ import annotations

import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_stored_manifest_view_is_owned_by_recipe_runtime_with_same_projection() -> None:
    view = importlib.import_module("aria.modules.recipe_runtime.stored_manifest_view")
    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "connections": ["ssh", "ssh", "sftp"],
        "steps": [{"type": "ssh_run"}, {"type": "chat_send"}],
    }

    assert view.stored_recipe_candidate_metadata(manifest) == {
        "candidate_role": "stored_recipe_candidate",
        "recipe_scope": {
            "connection_kinds": ["ssh", "sftp"],
            "step_types": ["ssh_run", "chat_send"],
        },
        "recipe_origin": "stored_recipe_manifest",
        "experience_count": 0,
        "last_success_at": "",
        "promotion_state": "",
        "promotion_hint": "",
    }
    assert view.stored_recipe_identity_values(manifest) == ["linux health", "linux-health"]
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria.modules.recipe_learning.stored_manifest_view")


def test_retained_consumers_use_relocated_stored_manifest_view() -> None:
    consumers = (
        "aria/modules/recipes_ui/stored_ui.py",
        "aria/modules/recipes_ui/routes.py",
        "aria/modules/chat_surface/routes.py",
        "aria/modules/execution_dry_run_payloads/payloads.py",
        "aria/modules/action_planner_templates/recipe_candidates.py",
    )
    for path in consumers:
        source = _source(path)
        assert "aria.modules.recipe_runtime.stored_manifest_view" in source
        assert "aria.modules.recipe_learning.stored_manifest_view" not in source

    runtime_manifest = importlib.import_module("aria.modules.recipe_runtime.manifest").MODULE_MANIFEST
    assert "aria/modules/recipe_runtime/stored_manifest_view.py" in runtime_manifest["python"]


def test_action_planner_templates_keep_live_apis_without_recipe_learning() -> None:
    paths = (
        "aria/modules/action_planner_templates/bounded_planner.py",
        "aria/modules/action_planner_templates/planner.py",
        "aria/modules/action_planner_templates/candidate_details.py",
        "aria/modules/action_planner_templates/planner_candidates.py",
        "aria/modules/action_planner_templates/recipe_candidates.py",
    )
    for path in paths:
        assert "aria.modules.recipe_learning" not in _source(path)

    planner_source = _source("aria/modules/action_planner_templates/planner.py")
    recipe_candidates_source = _source("aria/modules/action_planner_templates/recipe_candidates.py")
    assert "def _load_learned_recipe_records" not in planner_source
    assert "def _learned_recipe_candidates" not in planner_source
    assert "def build_learned_recipe_action_candidates" not in recipe_candidates_source

    candidate_details = importlib.import_module("aria.modules.action_planner_templates.candidate_details")
    planner = importlib.import_module("aria.modules.action_planner_templates.planner")
    taxonomy = importlib.import_module("aria.modules.action_planner_templates.taxonomy")
    templates = importlib.import_module("aria.modules.action_planner_templates.templates")
    behavior_families = importlib.import_module("aria.modules.action_planner_templates.behavior_families")
    file_operations = importlib.import_module("aria.modules.action_planner_templates.behavior_family_file_operation")
    assert callable(candidate_details.capability_label)
    assert callable(planner.debug_bounded_action_plan_decision)
    assert callable(taxonomy.is_recipe_candidate_kind)
    assert templates.ACTION_TEMPLATE_LIBRARY
    assert behavior_families
    assert file_operations


def test_startup_and_stats_drop_dead_recipe_learning_paths() -> None:
    main_source = _source("aria/main.py")
    stats_source = _source("aria/modules/stats_ui/routes.py")
    stats_template = _source("aria/templates/stats.html")
    stats_manifest = importlib.import_module("aria.modules.stats_ui.manifest").MODULE_MANIFEST

    assert "purge_legacy_learning_once" not in main_source
    assert "promote_recipe_experience_to_learned_review" not in stats_source
    assert "/stats/recipe-experience/review" not in stats_source
    assert "/stats/recipe-experience/review" not in stats_template
    assert "/stats/recipe-experience/review" not in stats_manifest["routes"]
    assert "recipe_learning" not in stats_manifest["depends_on"]


def test_recipe_learning_has_no_retained_product_importers_and_is_removed() -> None:
    offenders: list[str] = []
    for path in (ROOT / "aria").rglob("*.py"):
        if "aria.modules.recipe_learning" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
    registry = importlib.import_module("aria.modules.registry")
    assert not (ROOT / "aria/modules/recipe_learning").exists()
    assert registry.get_module_manifest("recipe_learning") is None
