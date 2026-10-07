from __future__ import annotations

import json
from pathlib import Path
import tomllib

import aria.modules.release_update.update_check as update_check
from aria.modules.release_update.release_meta import DEFAULT_RELEASE_LABEL


ROOT = Path(__file__).resolve().parents[1]
TARGET = "0.1.0-alpha982"


def _top_release_section(path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    section = update_check.extract_changelog_section(text, TARGET)
    assert section
    return section


def test_alpha982_release_metadata_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == TARGET
    assert DEFAULT_RELEASE_LABEL == TARGET


def test_public_changelogs_have_complete_bilingual_rollup() -> None:
    en = _top_release_section("CHANGELOG.md")
    de = _top_release_section("CHANGELOG.de.md")

    for heading in (
        "Highlights", "Added", "Changed", "Removed", "Fixed", "Security",
        "Upgrade Notes", "Known Limitations",
    ):
        assert f"### {heading}" in en
    for heading in (
        "Highlights", "Hinzugefuegt", "Geaendert", "Entfernt", "Behoben", "Sicherheit",
        "Upgrade-Hinweise", "Bekannte Einschraenkungen",
    ):
        assert f"### {heading}" in de

    for marker in ("modular", "self-learning", "recipes", "MCP", "memory"):
        assert marker.lower() in en.lower()
    for marker in ("modular", "selbstlern", "Rezepte", "MCP", "Gedaechtnis"):
        assert marker.lower() in de.lower()
    assert "only the GUI" in en
    assert "nur noch die GUI" in de


def test_release_docs_cover_upgrade_limits_and_publish_artifacts() -> None:
    release = (ROOT / "docs/release/github-release-v0.1.0-alpha.982.md").read_text(encoding="utf-8")
    setup = (ROOT / "docs/setup/mcp-and-blender.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/release/publish-runbook-alpha982.md").read_text(encoding="utf-8")
    docker_hub = (ROOT / "docs/release/docker-hub-overview.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    combined = "\n".join((release, docker_hub, readme))
    for marker in ("modular", "MCP", "background job", "memory", "confirmation"):
        assert marker.lower() in combined.lower()
    for marker in ("Claude", "paid", "user's machine", "cost", "E2E"):
        assert marker.lower() in release.lower()
    for marker in ("16000", "300", "temperature", "tool_choice=none", "call timeout"):
        assert marker.lower() in (release + setup).lower()
    for service in ("aria", "aria-updater", "qdrant"):
        assert service in docker_hub

    for marker in (
        "git add -A", "Release alpha982", "v0.1.0-alpha.982",
        "git push origin", "gh release create", "docker push",
        "fischermanch/aria:alpha", "fischermanch/aria:latest",
    ):
        assert marker in runbook


def test_update_channel_from_public_alpha604_selects_alpha982_and_notes(monkeypatch, tmp_path) -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    responses = {
        update_check.GITHUB_TAGS_API: json.dumps([{"name": "v0.1.0-alpha.982"}]),
        update_check.GITHUB_CHANGELOG_RAW: changelog,
    }

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.data = text.encode()

        def read(self) -> bytes:
            return self.data

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(
        update_check,
        "urlopen",
        lambda request, timeout=0: FakeResponse(responses[str(request.full_url)]),
    )
    status = update_check.refresh_update_status(tmp_path, current_label="0.1.0-alpha604")
    assert status["latest_label"] == TARGET
    assert status["latest_tag"] == "v0.1.0-alpha.982"
    assert status["update_available"] is True
    assert "### Highlights" in status["release_notes"]


def test_release_harnesses_are_isolated_and_cover_fresh_and_upgrade_paths() -> None:
    fresh = (ROOT / "scripts/e2e/fresh_install.sh").read_text(encoding="utf-8")
    upgrade = (ROOT / "scripts/e2e/upgrade_604.sh").read_text(encoding="utf-8")
    browser = (ROOT / "tests/e2e/upgrade_604.py").read_text(encoding="utf-8")

    for script in (fresh, upgrade):
        assert "aria-e2e-" in script
        assert "trap cleanup EXIT" in script
        assert "docker volume" not in script
    assert "fischermanch/aria:0.1.0-alpha.604" in upgrade
    for marker in (
        "second user", "connection", "chat history", "personal memory", "preference",
        "recipe", "legacy learning", "cleanup-legacy-learning",
    ):
        assert marker in browser.lower()


def test_acceptance_verification_has_release_gate_slots() -> None:
    acceptance = json.loads(
        (ROOT / ".codex/aria_acceptance/public-release-candidate-alpha982-review-build.json").read_text(
            encoding="utf-8"
        )
    )
    assert acceptance["target_internal_version"] == TARGET
    assert acceptance["build_allowed"] is True
