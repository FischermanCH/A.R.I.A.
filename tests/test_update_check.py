from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import aria.core.update_check as update_check
from aria.core.update_check import extract_changelog_section
from aria.core.update_check import extract_release_history
from aria.core.update_check import get_update_status
from aria.core.update_check import is_newer_release
from aria.core.update_check import normalize_release_label


def test_normalize_release_label_handles_tags_and_internal_labels() -> None:
    assert normalize_release_label("v0.1.0-alpha.26") == "0.1.0-alpha26"
    assert normalize_release_label("0.1.0-alpha26") == "0.1.0-alpha26"
    assert normalize_release_label("v1.2.3") == "1.2.3"


def test_is_newer_release_compares_alpha_numbers() -> None:
    assert is_newer_release("0.1.0-alpha27", "0.1.0-alpha26") is True
    assert is_newer_release("0.1.0-alpha26", "0.1.0-alpha26") is False
    assert is_newer_release("0.1.0-alpha25", "0.1.0-alpha26") is False


def test_extract_changelog_section_returns_matching_version_block() -> None:
    changelog = """
## [Unreleased]

### Added
- next thing

## [0.1.0-alpha.26] - 2026-04-05

### Fixed
- fixed one

## [0.1.0-alpha.25] - 2026-04-04

### Added
- older thing
""".strip()

    section = extract_changelog_section(changelog, "0.1.0-alpha26")

    assert "0.1.0-alpha.26" in section
    assert "fixed one" in section
    assert "older thing" not in section


def test_extract_release_history_returns_newest_sections_in_order() -> None:
    changelog = """
## [Unreleased]

## [0.1.0-alpha.54] - 2026-04-06

### Fixed
- newest

## [0.1.0-alpha.53] - 2026-04-06

### Added
- older

## [0.1.0-alpha.52] - 2026-04-06

### Changed
- oldest
""".strip()

    history = extract_release_history(changelog, max_items=3)

    assert [entry["label"] for entry in history] == [
        "0.1.0-alpha54",
        "0.1.0-alpha53",
        "0.1.0-alpha52",
    ]
    assert "newest" in history[0]["notes"]
    assert history[0]["tag"] == "v0.1.0-alpha.54"


def test_get_update_status_fetches_latest_tag_and_release_notes(monkeypatch, tmp_path) -> None:
    responses = {
        update_check.GITHUB_TAGS_API: json.dumps(
            [
                {"name": "v0.1.0-alpha.26"},
                {"name": "v0.1.0-alpha.27"},
            ]
        ),
        update_check.GITHUB_CHANGELOG_RAW: """
## [Unreleased]

## [0.1.0-alpha.27] - 2026-04-05

### Added
- update hint
""".strip(),
    }

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self._data = text.encode("utf-8")

        def read(self) -> bytes:
            return self._data

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        return FakeResponse(responses[str(request.full_url)])

    monkeypatch.setattr(update_check, "urlopen", fake_urlopen)

    status = get_update_status(tmp_path, current_label="0.1.0-alpha26", ttl_seconds=1)

    assert status["update_available"] is True
    assert status["latest_label"] == "0.1.0-alpha27"
    assert "update hint" in status["release_notes"]
    assert status["recent_releases"] == []


def test_get_update_status_ignores_cache_if_cached_latest_is_older_than_current(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "data" / "runtime" / "update_status.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "current_label": "0.1.0-alpha30",
                "latest_label": "0.1.0-alpha29",
                "latest_tag": "v0.1.0-alpha.29",
                "update_available": False,
                "checked_at": "2026-04-05T12:41:42.211750+00:00",
                "source": "github-tags",
                "release_notes": "",
                "release_notes_source": update_check.GITHUB_CHANGELOG_RAW,
                "error": "",
            }
        ),
        encoding="utf-8",
    )

    responses = {
        update_check.GITHUB_TAGS_API: json.dumps(
            [
                {"name": "v0.1.0-alpha.29"},
                {"name": "v0.1.0-alpha.30"},
            ]
        ),
        update_check.GITHUB_CHANGELOG_RAW: """
## [Unreleased]

## [0.1.0-alpha.30] - 2026-04-05

### Fixed
- restart/login issue
""".strip(),
    }

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self._data = text.encode("utf-8")

        def read(self) -> bytes:
            return self._data

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        return FakeResponse(responses[str(request.full_url)])

    monkeypatch.setattr(update_check, "urlopen", fake_urlopen)

    status = get_update_status(tmp_path, current_label="0.1.0-alpha30", ttl_seconds=60 * 60 * 6)

    assert status["latest_label"] == "0.1.0-alpha30"
    assert status["update_available"] is False


def test_get_update_status_refreshes_up_to_date_cache_quickly_for_new_releases(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "data" / "runtime" / "update_status.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "current_label": "0.1.0-alpha34",
                "latest_label": "0.1.0-alpha34",
                "latest_tag": "v0.1.0-alpha.34",
                "update_available": False,
                "checked_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                "source": "github-tags",
                "release_notes": "",
                "release_notes_source": update_check.GITHUB_CHANGELOG_RAW,
                "error": "",
            }
        ),
        encoding="utf-8",
    )

    responses = {
        update_check.GITHUB_TAGS_API: json.dumps(
            [
                {"name": "v0.1.0-alpha.34"},
                {"name": "v0.1.0-alpha.35"},
            ]
        ),
        update_check.GITHUB_CHANGELOG_RAW: """
## [Unreleased]

## [0.1.0-alpha.35] - 2026-04-05

### Fixed
- auth cookie cleanup
""".strip(),
    }

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self._data = text.encode("utf-8")

        def read(self) -> bytes:
            return self._data

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        return FakeResponse(responses[str(request.full_url)])

    monkeypatch.setattr(update_check, "urlopen", fake_urlopen)

    status = get_update_status(tmp_path, current_label="0.1.0-alpha34", ttl_seconds=60 * 60 * 6)

    assert status["latest_label"] == "0.1.0-alpha35"
    assert status["update_available"] is True


def test_get_update_status_falls_back_to_changelog_when_github_tags_rate_limited(monkeypatch, tmp_path) -> None:
    responses = {
        update_check.GITHUB_CHANGELOG_RAW: """
## [Unreleased]

## [0.1.0-alpha.40] - 2026-04-05

### Fixed
- memory map docs

## [0.1.0-alpha.39] - 2026-04-05

### Fixed
- older thing
""".strip(),
    }

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self._data = text.encode("utf-8")

        def read(self) -> bytes:
            return self._data

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        if str(request.full_url) == update_check.GITHUB_TAGS_API:
            raise HTTPError(str(request.full_url), 403, "rate limit exceeded", hdrs=None, fp=None)
        return FakeResponse(responses[str(request.full_url)])

    monkeypatch.setattr(update_check, "urlopen", fake_urlopen)

    status = get_update_status(tmp_path, current_label="0.1.0-alpha39", ttl_seconds=1)

    assert status["latest_label"] == "0.1.0-alpha40"
    assert status["update_available"] is True
    assert status["source"] == "github-changelog-fallback"
    assert status["error"] == ""
    assert "memory map docs" in status["release_notes"]
    assert [entry["label"] for entry in status["recent_releases"]] == ["0.1.0-alpha39"]
