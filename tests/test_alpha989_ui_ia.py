from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

CONNECTION_TEMPLATES = (
    "config_connections_ssh.html",
    "config_connections_sftp.html",
    "config_connections_smb.html",
    "config_connections_discord.html",
    "config_connections_webhook.html",
    "config_connections_http_api.html",
    "config_connections_google_calendar.html",
    "config_connections_mqtt.html",
    "config_connections_smtp.html",
    "config_connections_imap.html",
    "config_connections_rss.html",
    "config_connections_websites.html",
    "config_connections_mcp.html",
)

MEMORY_TEMPLATE_HASHES = {
    "memories_overview.html": "a45298f6169df4805cb730e553c83ee39b7564aef6a3a005945aec8794b3046b",
    "memories_auto_memory.html": "e1646158cf41908180bd64f78506cc07cc3d3718fcf34f38f3b4a7984f01aac1",
    "config_memory.html": "008587f09858c1521543c75936a9d5dea5ff7bc14feadfb5a78422f16ab886b7",
    "memories_create.html": "a1576287d2c93f46d1efa9f3e8214b7f997571993310461ccf62febc719e221d",
    "memories_import.html": "72afb0f14573aa0c3d46a1c79a98380511c5cd898e8fb4fcc36b28971305a293",
    "memories_maintenance.html": "fc3c65cf815c2e4df8306a0df8d0f16ebc48597bf6347c9d6a54c53d41415b8b",
}


def test_alpha989_foundation_advances_to_alpha990_and_keeps_public_alpha983() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release_meta = (ROOT / "aria/modules/release_update/release_meta.py").read_text(encoding="utf-8")
    changelog_en = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_de = (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8")
    assert 'version = "0.1.0-alpha1007"' in pyproject
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in release_meta
    assert changelog_en.startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert changelog_de.startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "0.1.0-alpha983" in changelog_en
    assert "0.1.0-alpha983" in changelog_de


def test_connection_ia_has_canonical_overview_create_detail_contract() -> None:
    source = (ROOT / "aria/modules/connections_ui_readonly/ia_routes.py").read_text(encoding="utf-8")
    assert "connection_canonical_url" in source
    assert '"overview"' in source and '"create"' in source and '"detail"' in source
    assert "/new" in source
    assert "legacy_connection_redirect" in source
    assert "RedirectResponse" in source


@pytest.mark.parametrize("template_name", CONNECTION_TEMPLATES)
def test_every_connection_template_uses_canonical_page_type_shell(template_name: str) -> None:
    source = (ROOT / "aria/templates" / template_name).read_text(encoding="utf-8")
    assert "connection_page_type" in source, template_name
    assert 'data-ui-page-type="{{ connection_page_type }}"' in source
    assert "connection_page_type == 'create'" in source or "connection_page_type in ['create', 'detail']" in source


def test_edit_contexts_do_not_render_secret_fields() -> None:
    sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "aria/modules/connections_ui_readonly/context_helpers.py",
            "aria/modules/sftp_admin_ui/context.py",
            "aria/modules/ssh_admin_ui/context.py",
        )
    )
    edit_lists = re.findall(r'context\["[^\"]+_edit_form_fields"\].*?ordered_fields=\[(.*?)\]', sources, re.DOTALL)
    assert edit_lists
    for fields in edit_lists:
        assert not re.search(r'"(?:password|auth_token|webhook_url|ical_url|key_path)"', fields), fields
    assert "secret_rotation_fields" in sources


def test_shared_theme_styles_every_real_form_control_and_info_spacing() -> None:
    styles = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")
    assert ":where(input:not([type=\"checkbox\"]):not([type=\"radio\"]), select, textarea)" in styles
    assert ".ui-info-panel summary" in styles
    assert "gap:" in styles[styles.index(".ui-info-panel summary") : styles.index(".ui-info-panel summary") + 300]


def test_non_memory_authenticated_page_shell_has_no_generic_purpose_injection() -> None:
    base = (ROOT / "aria/templates/base.html").read_text(encoding="utf-8")
    assert "authenticated-page-purpose" not in base
    assert "page_purpose_fallback" not in base
    assert 'data-ui-page-type="' in base


def test_memory_browser_remains_byte_identical_while_other_memory_pages_move_in_alpha990() -> None:
    payload = (ROOT / "aria/templates/_memory_drilldown_browser.html").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == "e91e7164266e0452a10622c7009075800b8ee6b4db64de3ddc17b972bfdfcc1c"


def test_connection_danger_zone_is_final_and_not_inline() -> None:
    shared = (ROOT / "aria/templates/_connection_clarity.html").read_text(encoding="utf-8")
    assert "connection_danger_zone" in shared
    assert "ui-danger-consequences" in shared
    for name in CONNECTION_TEMPLATES:
        source = (ROOT / "aria/templates" / name).read_text(encoding="utf-8")
        assert "connection_danger_zone" in source or "_connection_delete_inline.html" in source, name


def test_alpha989_e2e_contract_defines_u7_u8_u9_and_55_page_index() -> None:
    source = (ROOT / "tests/e2e/scenarios.py").read_text(encoding="utf-8")
    assert "U7" in source and "U8" in source and "U9" in source
    assert "ui-ia-alpha989" in source
    assert "55" in source
