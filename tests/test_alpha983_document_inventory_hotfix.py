from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = "0.1.0-alpha983"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_alpha983_release_metadata_and_hotfix_notes_are_consistent() -> None:
    assert f'version = "{TARGET}"' in _read("pyproject.toml")
    assert f'DEFAULT_RELEASE_LABEL = "{TARGET}"' in _read(
        "aria/modules/release_update/release_meta.py"
    )
    assert TARGET in _read("docs/backlog/alpha-backlog.md")

    changelog_en = _read("CHANGELOG.md")
    changelog_de = _read("CHANGELOG.de.md")
    assert changelog_en.index("## 0.1.0-alpha983") < changelog_en.index("## 0.1.0-alpha982")
    assert changelog_de.index("## 0.1.0-alpha983") < changelog_de.index("## 0.1.0-alpha982")
    for text in (changelog_en, changelog_de):
        section = text.split("## 0.1.0-alpha983", 1)[1].split("## 0.1.0-alpha982", 1)[0].lower()
        assert "document" in section or "dokument" in section
        assert "inventory" in section or "inventar" in section
        assert "no data" in section or "keine daten" in section

    notes = _read("docs/release/github-release-v0.1.0-alpha.983.md")
    runbook = _read("docs/release/publish-runbook-alpha983.md")
    assert "public hotfix" in notes.lower()
    assert "v0.1.0-alpha.983" in runbook
    assert "fischermanch/aria:0.1.0-alpha.983" in runbook
    assert "Release alpha983" in runbook


def test_alpha983_e2e_harness_is_isolated_and_contains_s24() -> None:
    runner = _read("scripts/e2e/run.sh")
    scenarios = _read("tests/e2e/scenarios.py")
    assert 'QDRANT_NAME="${PREFIX}-qdrant"' in runner
    assert 'qdrant_url: "http://${QDRANT_NAME}:6333"' in runner
    assert "test_s24_document_inventory_lists_all_five_imported_documents" in scenarios
    assert "documents_read_search_inventory" in scenarios
    assert "s24-beipackzettel-" in scenarios


def test_alpha983_acceptance_targets_hotfix_and_forbids_runtime_access() -> None:
    acceptance = json.loads(
        _read(".codex/aria_acceptance/document-inventory-hotfix-alpha983-review-build.json")
    )
    assert acceptance["target_internal_version"] == TARGET
    assert acceptance["runtime_access_allowed"] is False
    assert acceptance["provider_calls"] == 0
    assert acceptance["build_allowed"] is True
