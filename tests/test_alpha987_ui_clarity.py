from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from aria.main import app
from aria.modules.config_ui.ui_audit import build_ui_route_inventory
from aria.modules.navigation_shell.navigation import CONFIG_HUB_GROUPS, NAV_NODES
from test_config_backup import _build_test_config_app
from test_config_routes import _build_profile_config_app


ROOT = Path(__file__).resolve().parents[1]


def _section(source: str, section_id: str) -> str:
    match = re.search(
        rf'<(?P<tag>section|details)[^>]*id="{re.escape(section_id)}"[^>]*>(.*?)</(?P=tag)>',
        source,
        re.DOTALL,
    )
    assert match, section_id
    return match.group(2)


def test_shared_ui_clarity_pattern_is_documented_and_theme_neutral() -> None:
    partial = (ROOT / "aria/templates/_ui_clarity.html").read_text(encoding="utf-8")
    styles = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")
    guide = (ROOT / "docs/ui/ui-clarity-pattern.md").read_text(encoding="utf-8")

    for macro in ("ui_info_panel", "ui_action_card", "ui_settings_section", "ui_danger_zone"):
        assert f"macro {macro}" in partial
    for css_class in (".ui-info-panel", ".ui-action-card", ".ui-settings-section", ".ui-danger-zone"):
        assert css_class in styles
    assert "#backup-bundle-fields[hidden]" in styles
    assert "1280" in guide and "800" in guide
    assert "exactly one primary" in guide.lower()
    assert "typed confirmation" in guide.lower()
    assert "--surface-card" in styles and "--muted" in styles


def test_backup_page_uses_three_actions_and_one_collapsible_information_panel(tmp_path: Path) -> None:
    response = TestClient(_build_test_config_app(tmp_path)).get("/config/backup")

    assert response.status_code == 200
    assert "Backup &amp; restore" in response.text
    assert "Here you can download" in response.text
    assert response.text.count('data-ui-pattern="action"') == 3
    assert response.text.count('data-primary-actions="1"') == 3
    assert 'id="backup-download"' in response.text
    assert 'id="backup-bundle-toggle"' in response.text
    assert 'id="backup-bundle-toggle" name="include_secrets" type="checkbox" value="1"' in response.text
    assert 'id="backup-bundle-fields"' in response.text and "hidden" in response.text
    assert response.text.count('data-ui-pattern="info"') == 1
    assert "Included and not included" in response.text
    info_start = response.text.index('data-ui-pattern="info"')
    assert "<button" not in response.text[info_start:]


def test_logs_page_separates_settings_action_info_and_last_danger_zone(tmp_path: Path) -> None:
    response = _build_profile_config_app(tmp_path).get("/config/logs")
    source = (ROOT / "aria/templates/config_logs.html").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "Here you can configure" in response.text
    assert response.text.count('data-ui-pattern="settings"') == 1
    assert response.text.count('data-ui-pattern="action"') == 1
    assert response.text.count('data-ui-pattern="info"') == 1
    assert response.text.count('data-ui-pattern="danger"') == 1
    settings = _section(response.text, "trace-settings")
    assert settings.count('type="submit"') == 1
    assert 'id="logs-danger-zone"' in response.text
    assert response.text.rfind('id="logs-danger-zone"') > response.text.rfind('data-ui-pattern="info"')
    assert 'id="confirm-reset"' in source
    assert 'id="confirm-factory-reset"' in source
    assert "ui-danger-consequences" in source


def test_backup_navigation_belongs_to_security_not_operations() -> None:
    groups = {group.id: group for group in CONFIG_HUB_GROUPS}

    assert "admin.backup" in groups["security_access"].item_ids
    assert "admin.backup" not in groups["operations"].item_ids
    assert NAV_NODES["admin.backup"].parent == "admin.access"


def test_ui_clarity_audit_lists_every_authenticated_registered_page() -> None:
    report = (ROOT / ".codex/reports/ui-clarity-audit.md").read_text(encoding="utf-8")
    routes = [row for row in build_ui_route_inventory(app) if row.owner_module != "auth_ui"]

    assert len(routes) >= 60
    for route in routes:
        assert f"`{route.path}`" in report, route.path
    assert "test-results/ui-clarity-audit-alpha987" in report
    assert "memories pages are audit-only" in report.lower()
    assert "follow-up build" in report.lower()


def test_alpha987_release_metadata_and_public_channel_contract() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release_meta = (ROOT / "aria/modules/release_update/release_meta.py").read_text(encoding="utf-8")
    changelog_en = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_de = (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8")

    assert 'version = "0.1.0-alpha1007"' in pyproject
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in release_meta
    assert "## 0.1.0-alpha987" in changelog_en
    assert "## 0.1.0-alpha987" in changelog_de
    assert "0.1.0-alpha983" in changelog_en
    assert "0.1.0-alpha983" in changelog_de
