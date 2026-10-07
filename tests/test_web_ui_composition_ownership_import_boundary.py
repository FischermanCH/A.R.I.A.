from __future__ import annotations

from pathlib import Path

import aria.modules.navigation_shell.ui_helpers as canonical_main_ui_helpers
import aria.modules.stats_ui.routes as canonical_stats_routes


def test_moved_implementations_keep_repository_and_i18n_roots() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    aria_root = repository_root / "aria"

    assert canonical_stats_routes._project_root() == repository_root
    assert canonical_stats_routes._STATS_ROUTES_I18N.base_dir == aria_root / "i18n"
    assert canonical_main_ui_helpers._BASE_DIR == repository_root
    assert canonical_main_ui_helpers._MAIN_UI_I18N.base_dir == aria_root / "i18n"


def test_product_code_imports_canonical_web_ui_owners() -> None:
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

    assert "from aria.modules.stats_ui.activities import register_activities_routes" in main_source
    assert "from aria.modules.stats_ui.routes import register_stats_routes" in main_source
    assert "from aria.modules.static_help_docs.routes import DocsSurfaceRouteDeps" in main_source
    assert "from aria.modules.navigation_shell.request_helpers import MainRequestHelperDeps" in main_source
    assert "from aria.modules.navigation_shell.ui_helpers import (" in main_source
