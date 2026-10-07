from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.chat_surface.catalog as canonical_catalog
import aria.modules.chat_surface.routes as canonical_routes


MODULE_PAIRS = (
    ("aria.modules.chat_surface.catalog", canonical_catalog),
    ("aria.modules.chat_surface.routes", canonical_routes),
)


def test_legacy_chat_surface_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_moved_chat_catalog_keeps_aria_i18n_root() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    assert canonical_catalog._I18N.base_dir == repository_root / "aria" / "i18n"


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

    assert "from aria.modules.chat_surface.catalog import build_chat_command_catalog" in main_source
    assert "from aria.modules.chat_surface.routes import ChatSurfaceRouteDeps" in main_source
