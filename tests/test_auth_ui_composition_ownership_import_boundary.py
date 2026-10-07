from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.auth_ui.cookies as canonical_cookies
import aria.modules.auth_ui.middleware as canonical_middleware
import aria.modules.auth_ui.routes as canonical_routes
import aria.modules.auth_ui.session as canonical_session


MODULE_PAIRS = (
    ("aria.modules.auth_ui.middleware", canonical_middleware),
    ("aria.modules.auth_ui.routes", canonical_routes),
    ("aria.modules.auth_ui.cookies", canonical_cookies),
    ("aria.modules.auth_ui.session", canonical_session),
)


def test_legacy_auth_ui_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_moved_auth_route_implementation_keeps_i18n_root() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    assert canonical_routes._AUTH_SURFACE_I18N.base_dir == repository_root / "aria" / "i18n"


def test_product_code_imports_canonical_auth_ui_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_main_composition_imports_canonical_auth_ui_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    main_source = (repository_root / "aria" / "main.py").read_text(encoding="utf-8")

    assert "import aria.modules.auth_ui.session as auth_session_helpers" in main_source
    assert "from aria.modules.auth_ui.middleware import AuthMiddlewareDeps" in main_source
    assert "from aria.modules.auth_ui.routes import AuthSurfaceRouteDeps" in main_source
    assert "from aria.modules.auth_ui.cookies import CookieHelper" in main_source
