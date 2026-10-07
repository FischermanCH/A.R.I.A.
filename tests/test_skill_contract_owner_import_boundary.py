from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from aria.modules.skill_contracts.contracts import BaseSkill, SkillResult


ROOT = Path(__file__).resolve().parents[1]
LEGACY_IMPORTS = {
    "aria.skills.base": "aria.modules.skill_contracts.contracts",
    "aria.skills.memory": "aria.modules.memory_learning_bridge.skill",
}


def test_skill_modules_resolve_to_exact_canonical_owner_identity() -> None:
    for legacy_name, canonical_name in LEGACY_IMPORTS.items():
        assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)


def test_skill_contract_values_and_truncation_stay_stable() -> None:
    result = SkillResult(skill_name="synthetic", content="ok", success=True)

    assert result.metadata == {}
    assert result.tokens_saved == 0
    assert BaseSkill.truncate(type("SyntheticSkill", (BaseSkill,), {"execute": None})(), "short") == ("short", 0)


def test_unknown_legacy_skill_module_still_fails() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria.skills.not_registered")


def test_legacy_skill_tree_only_keeps_package_initializer() -> None:
    assert sorted(path.name for path in (ROOT / "aria" / "skills").glob("*.py")) == ["__init__.py"]


def test_product_consumers_use_canonical_skill_owner_imports() -> None:
    findings: list[str] = []
    for path in (ROOT / "aria").rglob("*.py"):
        if path == ROOT / "aria" / "skills" / "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and str(node.module or "").startswith("aria.skills"):
                findings.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.module}")
            if isinstance(node, ast.Import):
                findings.extend(
                    f"{path.relative_to(ROOT)}:{node.lineno}:{alias.name}"
                    for alias in node.names
                    if alias.name.startswith("aria.skills")
                )

    assert findings == []
