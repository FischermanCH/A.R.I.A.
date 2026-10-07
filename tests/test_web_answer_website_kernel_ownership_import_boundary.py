from __future__ import annotations

import importlib
from pathlib import Path

from aria.modules import MODULE_MANIFESTS


MODULE_PAIRS = (
    ("aria.core.website_runtime", "aria.modules.website_runtime.runtime"),
)


def test_web_answer_website_private_legacy_modules_are_removed() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(canonical_path)
        try:
            importlib.import_module(legacy_path)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"private legacy module still importable: {legacy_path}")


def test_production_code_uses_canonical_web_answer_website_imports() -> None:
    blocked = tuple(legacy_path for legacy_path, _canonical_path in MODULE_PAIRS)
    offenders: list[str] = []

    for path in sorted(Path("aria").rglob("*.py")):
        if path == Path("aria/modules/legacy_aliases.py"):
            continue
        source = path.read_text(encoding="utf-8")
        for legacy_path in blocked:
            if legacy_path in source:
                offenders.append(f"{path}:{legacy_path}")

    assert offenders == []


def test_web_answer_website_manifests_own_canonical_implementations() -> None:
    assert "aria/modules/website_runtime/runtime.py" in MODULE_MANIFESTS["website_runtime"]["python"]


def test_website_runtime_i18n_root_survives_move() -> None:
    runtime = importlib.import_module("aria.modules.website_runtime.runtime")
    expected = Path(__file__).resolve().parents[1] / "aria" / "i18n"

    assert runtime._WEBSITE_RUNTIME_I18N.base_dir == expected
