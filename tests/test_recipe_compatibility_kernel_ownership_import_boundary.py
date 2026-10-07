from __future__ import annotations

import importlib
from pathlib import Path


MODULE_PAIRS = (
    ("aria.modules.recipe_store.manifests", "aria.modules.recipe_store.manifests"),
    ("aria.modules.recipe_store.manifests", "aria.modules.recipe_store.manifests"),
    ("aria.modules.recipe_runtime.runtime", "aria.modules.recipe_runtime.runtime"),
)


def test_recipe_compatibility_modules_are_identity_aliases() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_recipe_compatibility_constants_remain_available() -> None:
    manifests = importlib.import_module("aria.modules.recipe_store.manifests")
    assert manifests.SKILL_CATEGORY_DEFAULTS is manifests.RECIPE_CATEGORY_DEFAULTS


def test_production_code_uses_canonical_stored_recipe_imports() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []
