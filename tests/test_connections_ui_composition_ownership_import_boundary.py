from __future__ import annotations

from pathlib import Path

import aria.modules.connections_ui_readonly.context_helpers as canonical_context_helpers
import aria.modules.connections_ui_readonly.reader_helpers as canonical_reader_helpers
import aria.modules.connections_ui_readonly.surface_helpers as canonical_surface_helpers
import aria.modules.connections_ui_readonly.surface_routes as canonical_surface_routes


def test_moved_connections_ui_implementations_keep_i18n_root() -> None:
    aria_root = Path(__file__).resolve().parents[1] / "aria"

    assert canonical_context_helpers._CONNECTION_CONTEXT_I18N.base_dir == aria_root / "i18n"
    assert canonical_reader_helpers._CONNECTION_READER_I18N.base_dir == aria_root / "i18n"
    assert canonical_surface_helpers._CONNECTIONS_SURFACE_HELPERS_I18N.base_dir == aria_root / "i18n"
    assert canonical_surface_routes._CONNECTIONS_SURFACE_ROUTES_I18N.base_dir == aria_root / "i18n"


def test_product_code_imports_canonical_connections_ui_owner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    wrapper_paths = {
        repository_root / "aria" / "web" / "connection_context_helpers.py",
        repository_root / "aria" / "web" / "connection_detail_routes.py",
        repository_root / "aria" / "web" / "connection_metadata_routes.py",
        repository_root / "aria" / "web" / "connection_page_helpers.py",
        repository_root / "aria" / "web" / "connection_reader_helpers.py",
        repository_root / "aria" / "web" / "connection_ui_helpers.py",
        repository_root / "aria" / "web" / "connections_surface_helpers.py",
        repository_root / "aria" / "web" / "connections_surface_routes.py",
    }
    forbidden_imports = tuple(f"aria.web.{path.stem}" for path in wrapper_paths)
    findings = [
        f"{path.relative_to(repository_root)}: {legacy_import}"
        for path in (repository_root / "aria").rglob("*.py")
        if path not in wrapper_paths
        and path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        for legacy_import in forbidden_imports
        if legacy_import in path.read_text(encoding="utf-8")
    ]

    assert findings == []


def test_config_composition_imports_canonical_connections_ui_owner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    source = (
        repository_root / "aria" / "modules" / "config_ui" / "routes.py"
    ).read_text(encoding="utf-8")

    for module_name in (
        "context_helpers",
        "detail_routes",
        "metadata_routes",
        "page_helpers",
        "reader_helpers",
        "surface_helpers",
        "surface_routes",
        "ui_helpers",
    ):
        assert f"aria.modules.connections_ui_readonly.{module_name}" in source


def test_provider_manifests_do_not_claim_removed_connections_ui_sources() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    stale_paths = (
        "aria/web/connection_context_helpers.py",
        "aria/web/connection_detail_routes.py",
        "aria/web/connection_metadata_routes.py",
        "aria/web/connection_page_helpers.py",
        "aria/web/connection_reader_helpers.py",
        "aria/web/connection_ui_helpers.py",
        "aria/web/connections_surface_helpers.py",
        "aria/web/connections_surface_routes.py",
    )
    findings = [
        f"{path.relative_to(repository_root)}: {stale_path}"
        for path in (repository_root / "aria" / "modules").glob("*/manifest.py")
        for stale_path in stale_paths
        if stale_path in path.read_text(encoding="utf-8")
    ]

    assert findings == []
