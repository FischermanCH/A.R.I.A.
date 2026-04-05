from __future__ import annotations

import json

import aria.core.update_check as update_check
from aria.core.update_check import extract_changelog_section
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
