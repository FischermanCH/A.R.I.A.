from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_display_timezone_precedence_and_local_day(monkeypatch) -> None:
    from aria.modules.platform_primitives.display_time import (
        display_datetime,
        resolve_display_timezone,
    )

    monkeypatch.setenv("TZ", "America/Toronto")
    configured = SimpleNamespace(ui=SimpleNamespace(display_timezone="Europe/Zurich"))
    empty = SimpleNamespace(ui=SimpleNamespace(display_timezone=""))

    assert resolve_display_timezone(configured, browser_timezone="Asia/Tokyo") == "Europe/Zurich"
    assert resolve_display_timezone(empty, browser_timezone="Asia/Tokyo") == "America/Toronto"
    monkeypatch.delenv("TZ")
    assert resolve_display_timezone(empty, browser_timezone="Asia/Tokyo") == "Asia/Tokyo"
    assert resolve_display_timezone(empty, browser_timezone="Invalid/Zone") == "UTC"

    instant = datetime(2026, 10, 11, 23, 30, tzinfo=timezone.utc).timestamp()
    local = display_datetime(instant, "Europe/Zurich")
    assert local.date().isoformat() == "2026-10-12"
    assert local.strftime("%H:%M") == "01:30"


def test_journal_uses_period_selector_and_hides_custom_dates_by_default() -> None:
    from aria.modules.activity_journal.routes import _period_bounds
    from aria.modules.config_ui.page_linter import lint_page_snapshots

    template = _text("aria/templates/activity_journal.html")
    assert 'id="journal-period"' in template
    assert 'value="all"' in template
    assert 'value="today"' in template
    assert 'value="7d"' in template
    assert 'value="30d"' in template
    assert 'value="custom"' in template
    assert 'id="journal-custom-range"' in template
    assert "hidden" in template
    assert "toggleCustomRange" in template
    period, start, end = _period_bounds(
        "custom", "2026-10-12", "2026-10-12", "Europe/Zurich"
    )
    assert period == "custom"
    assert datetime.fromtimestamp(start, timezone.utc).isoformat().startswith("2026-10-11T22:00")
    assert datetime.fromtimestamp(end, timezone.utc).date().isoformat() == "2026-10-12"
    lint = lint_page_snapshots([{
        "path": "/memories/activity-journal",
        "page_type": "overview",
        "inherits_page_base": True,
        "title_count": 1,
        "canonical_parent_section": "memories",
        "rendered_parent_section": "memories",
        "journal_period_issues": ["custom date inputs visible for All"],
    }])
    assert any(row.rule == "R30" for row in lint.blocking_findings)


def test_mobile_chat_contract_uses_dynamic_viewport_and_document_scroll() -> None:
    css = _text("aria/static/style.css")
    template = _text("aria/templates/chat.html")
    assert "--aria-visual-viewport-offset-top" in template
    assert "100svh" in css and "100dvh" in css
    assert "@media (max-width: 900px), (max-height: 500px)" in css
    assert "position: sticky" in css
    assert "scrollIntoView" in template
    assert ".chat-box-wrap:has(.chat-jump-latest:not([hidden]))" in css


def test_alpha1002_release_metadata_and_public_pin() -> None:
    assert 'version = "0.1.0-alpha1007"' in _text("pyproject.toml")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in _text(
        "aria/modules/release_update/release_meta.py"
    )
    assert _text("CHANGELOG.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert _text("CHANGELOG.de.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "aria-alpha983-local.tar" in _text("docker/export-local-build.sh")
    assert "Public remains" in _text("CHANGELOG.md").split("## 0.1.0-alpha1001", 1)[0] or "public pin remains Alpha983" in _text("CHANGELOG.md").split("## 0.1.0-alpha1001", 1)[0]
