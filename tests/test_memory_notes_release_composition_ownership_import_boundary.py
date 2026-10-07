from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.memory_admin_ui.routes as canonical_memories_routes
import aria.modules.notes.routes as canonical_notes_routes
import aria.modules.release_update.routes as canonical_update_routes


MODULE_PAIRS = (
    ("aria.modules.memory_admin_ui.routes", canonical_memories_routes),
    ("aria.modules.notes.routes", canonical_notes_routes),
    ("aria.modules.release_update.routes", canonical_update_routes),
)


def test_legacy_route_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_moved_route_implementations_keep_repository_and_i18n_roots() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    aria_root = repository_root / "aria"

    assert canonical_memories_routes.BASE_DIR == repository_root
    assert canonical_memories_routes._MEMORIES_ROUTES_I18N.base_dir == aria_root / "i18n"
    assert canonical_notes_routes._NOTES_ROUTES_I18N.base_dir == aria_root / "i18n"


def test_product_code_imports_canonical_route_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_main_composition_imports_canonical_route_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    main_source = (repository_root / "aria" / "main.py").read_text(encoding="utf-8")

    assert "from aria.modules.memory_admin_ui.routes import register_memories_routes" in main_source
    assert "from aria.modules.notes.routes import NotesRouteDeps, register_notes_routes" in main_source
    assert "from aria.modules.release_update.routes import SystemUpdateRouteDeps" in main_source
