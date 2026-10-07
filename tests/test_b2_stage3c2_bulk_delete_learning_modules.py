from __future__ import annotations

from pathlib import Path

from aria.modules import MODULE_MANIFESTS, module_registry_diagnostics


ROOT = Path(__file__).resolve().parents[1]
MODULES_ROOT = ROOT / "aria/modules"
REMOVED_MODULES = {
    "learning",
    "learning_admin_ui",
    "learning_artifacts",
    "learning_candidates",
    "learning_feedback",
    "learning_governance",
    "learning_runtime",
    "prepared_artifacts",
    "recipe_learning",
}


def test_legacy_learning_module_directories_and_registry_entries_are_absent() -> None:
    for module_id in REMOVED_MODULES:
        assert not (MODULES_ROOT / module_id).exists()
        assert module_id not in MODULE_MANIFESTS
    assert (MODULES_ROOT / "memory_learning_bridge").is_dir()


def test_retained_manifests_do_not_depend_on_removed_learning_modules() -> None:
    dangling = {
        (module_id, dependency)
        for module_id, manifest in MODULE_MANIFESTS.items()
        for dependency in manifest.get("depends_on", [])
        if dependency in REMOVED_MODULES
    }

    assert dangling == set()


def test_retained_python_has_no_imports_from_removed_learning_modules() -> None:
    forbidden_prefixes = tuple(f"aria.modules.{module_id}" for module_id in REMOVED_MODULES)
    offenders: list[str] = []
    for path in MODULES_ROOT.rglob("*.py"):
        if any(part in REMOVED_MODULES for part in path.relative_to(MODULES_ROOT).parts[:-1]):
            continue
        source = path.read_text(encoding="utf-8")
        if any(prefix in source for prefix in forbidden_prefixes):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_module_registry_has_expected_post_delete_shape() -> None:
    diagnostics = module_registry_diagnostics()

    assert diagnostics["module_count"] == 106
    assert diagnostics["validation_issue_count"] == 0
    assert diagnostics["dependency_cycle_count"] == 0


def test_deferred_stage3d_and_core_memory_surfaces_remain() -> None:
    from aria.modules.memory_learning_bridge.skill import MemorySkill

    assert MemorySkill is not None
    assert "memory_learning_bridge" in MODULE_MANIFESTS
