from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.config_ui.access_detail_routes as canonical_access_detail_routes
import aria.modules.config_ui.intelligence_workbench_routes as canonical_intelligence_workbench_routes
import aria.modules.config_ui.main_helpers as canonical_main_config_helpers
import aria.modules.config_ui.misc_helpers as canonical_misc_helpers
import aria.modules.config_ui.persona_routes as canonical_persona_routes
import aria.modules.config_ui.profile_helpers as canonical_profile_helpers
import aria.modules.config_ui.routes as canonical_config_routes
import aria.modules.config_ui.routing_index_routes as canonical_routing_index_routes
import aria.modules.config_ui.support_helpers as canonical_support_helpers
import aria.modules.config_ui.surface_helpers as canonical_surface_helpers
import aria.modules.config_ui.surface_routes as canonical_surface_routes
import aria.modules.ops_config_backup.detail_routes as canonical_operations_detail_routes


MODULE_PAIRS = (
    ("aria.modules.config_ui.routes", canonical_config_routes),
    ("aria.modules.config_ui.misc_helpers", canonical_misc_helpers),
    ("aria.modules.config_ui.profile_helpers", canonical_profile_helpers),
    ("aria.modules.config_ui.support_helpers", canonical_support_helpers),
    ("aria.modules.config_ui.surface_helpers", canonical_surface_helpers),
    ("aria.modules.config_ui.surface_routes", canonical_surface_routes),
    ("aria.modules.config_ui.access_detail_routes", canonical_access_detail_routes),
    ("aria.modules.config_ui.intelligence_workbench_routes", canonical_intelligence_workbench_routes),
    ("aria.modules.config_ui.persona_routes", canonical_persona_routes),
    ("aria.modules.config_ui.routing_index_routes", canonical_routing_index_routes),
    ("aria.modules.config_ui.main_helpers", canonical_main_config_helpers),
    ("aria.modules.ops_config_backup.detail_routes", canonical_operations_detail_routes),
)


def test_legacy_config_ui_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_moved_config_implementations_keep_repository_and_i18n_roots() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    aria_root = repository_root / "aria"

    assert canonical_intelligence_workbench_routes.BASE_DIR == repository_root
    i18n_stores = (
        canonical_access_detail_routes._CONFIG_ACCESS_I18N,
        canonical_main_config_helpers._MAIN_CONFIG_I18N,
        canonical_operations_detail_routes._CONFIG_OPS_I18N,
        canonical_persona_routes._CONFIG_PERSONA_I18N,
        canonical_profile_helpers._CONFIG_PROFILE_I18N,
        canonical_support_helpers._CONFIG_SUPPORT_I18N,
        canonical_surface_helpers._CONFIG_SURFACE_HELPERS_I18N,
        canonical_surface_routes._CONFIG_SURFACE_I18N,
    )
    assert {store.base_dir for store in i18n_stores} == {aria_root / "i18n"}


def test_product_code_imports_canonical_config_ui_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_main_composition_imports_canonical_config_ui_owner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    main_source = (repository_root / "aria" / "main.py").read_text(encoding="utf-8")

    assert "from aria.modules.config_ui.main_helpers import MainConfigHelperDeps" in main_source
    assert "from aria.modules.config_ui.routes import ConfigRouteDeps" in main_source
