from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phone_chat_uses_document_scroll_and_sticky_composer() -> None:
    css = _text("aria/static/style.css")

    assert "@media (max-width: 900px), (max-height: 500px)" in css
    assert "flex-wrap: nowrap" in css
    assert ".chat-layout-fill .chat-box" in css
    assert "overflow: visible" in css
    assert ".chat-layout-fill .chat-form" in css
    assert "position: sticky" in css
    assert "bottom: env(safe-area-inset-bottom, 0px)" in css


def test_phone_chat_autoscroll_and_admin_layout_diagnostic_contract() -> None:
    template = _text("aria/templates/chat.html")

    assert "lastMessage.scrollIntoView" in template
    assert 'id="chat-layout-debug"' in template
    assert "layout_debug=1" in template
    assert "request.state.can_access_advanced_config" in template
    assert "pointer-events: none" in _text("aria/static/style.css")
    for field in (
        "innerWidth",
        "innerHeight",
        "visualViewport",
        "header",
        "messages",
        "composer",
        "scrollContainer",
        "userAgent",
        "cssVersion",
    ):
        assert field in template


def test_all_rendered_static_assets_are_release_versioned() -> None:
    base = _text("aria/templates/base.html")
    chat = _text("aria/templates/chat.html")
    memory_browser = _text("aria/templates/_memory_drilldown_browser.html")
    css = _text("aria/static/style.css")

    assert "request.state.ui_background_asset_url|e }}?v={{ release_asset_version }}" in base
    assert 'src="/static/chat-request-deadline.js?v=' in chat
    assert "navigation_shell_logo_path }}?v=" in memory_browser
    assert all("?v=" in match for match in re.findall(r'url\("(/static/[^\"]+)"\)', css))


def test_chat_timestamp_helper_formats_server_time_in_display_timezone() -> None:
    from aria.modules.platform_primitives.display_time import format_display_timestamp

    assert (
        format_display_timestamp(
            "2026-10-11T23:13:00Z", "Europe/Zurich", language="de"
        )
        == "12.10.2026, 01:13"
    )
    assert "format_display_timestamp" in _text("aria/modules/chat_surface/routes.py")
    assert "format_display_timestamp" in _text(
        "aria/modules/chat_execution_composition/routes.py"
    )
    assert "localizeChatTimestamps" in _text("aria/templates/chat.html")


def test_alpha1003_release_metadata_and_public_pin() -> None:
    assert 'version = "0.1.0-alpha1007"' in _text("pyproject.toml")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in _text(
        "aria/modules/release_update/release_meta.py"
    )
    assert _text("CHANGELOG.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert _text("CHANGELOG.de.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert (ROOT / "docs/release/publish-runbook-alpha1006.md").exists()
    assert (ROOT / "docs/release/github-release-v0.1.0-alpha.1007.md").exists()
    assert (ROOT / "docs/release/public-release-summary-alpha1006.md").exists()
