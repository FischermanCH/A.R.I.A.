from __future__ import annotations

import ast
from pathlib import Path

from aria.modules import MODULE_MANIFESTS


ROOT = Path(__file__).resolve().parents[1]


def _names_and_imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    return names, imports


def test_startup_keeps_maintenance_but_no_longer_enqueues_legacy_synthesis() -> None:
    source = (ROOT / "aria/main.py").read_text(encoding="utf-8")
    names, imports = _names_and_imports(ROOT / "aria/main.py")

    assert "enqueue_learning_job" not in names | imports
    assert "learning_synthesis_global" not in source
    assert 'source="startup_maintenance"' not in source
    retained = (
        "rebuild_document_meta_catalogs_for_known_users",
        "cleanup_empty_collections_global",
    )
    assert all(item in source for item in retained)
    assert [source.index(item) for item in retained] == sorted(source.index(item) for item in retained)


def test_recipe_runtime_has_no_learning_candidate_or_eval_coupling() -> None:
    path = ROOT / "aria/modules/recipe_runtime/runtime.py"
    source = path.read_text(encoding="utf-8")
    names, imports = _names_and_imports(path)
    forbidden = {
        "LearningClassifier",
        "store_learning_candidate",
        "LearningCandidateValidator",
        "store_learning_eval",
        "personal_claim_review_candidate",
    }

    assert not (forbidden & (names | imports))
    assert "aria.modules.learning_candidates" not in source


def test_core_memory_bridge_remains_after_legacy_learning_removal() -> None:
    manifest = MODULE_MANIFESTS["memory_learning_bridge"]

    assert manifest["id"] == "memory_learning_bridge"
    assert not {"learning_runtime", "learning_candidates"} & set(MODULE_MANIFESTS)
