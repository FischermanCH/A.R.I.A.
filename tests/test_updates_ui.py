from __future__ import annotations

from fastapi.testclient import TestClient

import aria.main as main_mod


def test_login_page_shows_update_notice_when_newer_version_exists(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label: {
            "current_label": "0.1.0-alpha26",
            "latest_label": "0.1.0-alpha27",
            "latest_tag": "v0.1.0-alpha.27",
            "update_available": True,
            "checked_at": "2026-04-05T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.27] - 2026-04-05",
            "release_notes_source": "CHANGELOG.md",
            "error": "",
        },
    )

    client = TestClient(main_mod.app)
    response = client.get("/login")

    assert response.status_code == 200
    assert "0.1.0-alpha27" in response.text
    assert "/updates" in response.text


def test_updates_page_renders_release_notes(monkeypatch) -> None:
    monkeypatch.setattr(
        main_mod,
        "_get_update_status",
        lambda _current_label: {
            "current_label": "0.1.0-alpha26",
            "latest_label": "0.1.0-alpha27",
            "latest_tag": "v0.1.0-alpha.27",
            "update_available": True,
            "checked_at": "2026-04-05T10:00:00+00:00",
            "source": "github-tags",
            "release_notes": "## [0.1.0-alpha.27] - 2026-04-05\n\n### Added\n- update hint",
            "release_notes_source": "CHANGELOG.md",
            "error": "",
        },
    )

    client = TestClient(main_mod.app)
    response = client.get("/updates")

    assert response.status_code == 200
    assert "0.1.0-alpha27" in response.text
    assert "CHANGELOG.md" in response.text
    assert "0.1.0-alpha27" in response.text
    assert "update hint" in response.text
