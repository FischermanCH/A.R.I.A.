from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.chat_surface.actions as canonical_actions
import aria.modules.chat_surface.routes as canonical_routes


MODULE_PAIRS = (
    ("aria.modules.chat_surface.actions", canonical_actions),
    ("aria.modules.chat_surface.routes", canonical_routes),
)


def test_legacy_chat_surface_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_chat_actions_are_ui_only_and_bilingual() -> None:
    assert len(canonical_actions.build_chat_quick_actions("de")) == 4
    assert len(canonical_actions.build_chat_quick_actions("en")) == 4


def test_product_code_imports_canonical_chat_surface_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_main_composition_imports_canonical_chat_surface_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    main_source = (repository_root / "aria" / "main.py").read_text(encoding="utf-8")

    assert "aria.modules.chat_surface.catalog" not in main_source
    assert "from aria.modules.chat_surface.routes import ChatSurfaceRouteDeps" in main_source
