from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_alpha992_release_contract_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in _text("pyproject.toml")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in _text(
        "aria/modules/release_update/release_meta.py"
    )
    assert _text("CHANGELOG.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert _text("CHANGELOG.de.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "0.1.0-alpha983" in _text("CHANGELOG.md")


def test_navigation_registry_has_one_canonical_parent_for_every_node() -> None:
    from aria.modules.navigation_shell.navigation import (
        CANONICAL_PARENT_SECTION_BY_NAV_ID,
        NAV_NODES,
    )

    assert set(CANONICAL_PARENT_SECTION_BY_NAV_ID) == set(NAV_NODES)
    assert all(
        isinstance(section, str) and section.strip()
        for section in CANONICAL_PARENT_SECTION_BY_NAV_ID.values()
    )
    assert CANONICAL_PARENT_SECTION_BY_NAV_ID["help.licenses"] == "help"
    assert CANONICAL_PARENT_SECTION_BY_NAV_ID["help.qdrant"] == "help"
    assert NAV_NODES["help.licenses"].href == "/licenses"
    assert NAV_NODES["help.qdrant"].href == "/help?doc=qdrant"


def test_memory_config_shortcut_keeps_memory_as_its_canonical_parent() -> None:
    from aria.modules.navigation_shell.navigation import canonical_parent_section

    class Request:
        class URL:
            path = "/config/memory"

        url = URL()
        query_params: dict[str, str] = {}

    assert canonical_parent_section(Request()) == "memory"


def test_licenses_and_qdrant_share_the_help_section_header() -> None:
    help_template = _text("aria/templates/help.html")
    licenses_template = _text("aria/templates/licenses.html")
    shared = _text("aria/templates/_help_section_header.html")

    assert '_help_section_header.html' in help_template
    assert '_help_section_header.html' in licenses_template
    assert 'data-ui-section-header="help"' in shared
    assert "help-doc-groups" in shared
    assert "help.qdrant" in shared
    assert "help.licenses" in shared


def test_connection_detail_ref_is_text_with_small_secondary_rename_action() -> None:
    fields = _text("aria/templates/_connection_schema_fields.html")

    assert 'data-connection-ref-text="true"' in fields
    assert 'type="hidden"' in fields
    assert 'data-connection-ref-submit' in fields
    assert 'data-connection-ref-rename-input' in fields
    assert 'class="ui-secondary-action ui-compact-action"' in fields
    assert 'readonly data-connection-ref-readonly="true"' not in fields


def test_connection_settings_description_is_not_repeated_in_summary_and_body() -> None:
    clarity = _text("aria/templates/_connection_clarity.html")
    ui = _text("aria/templates/_ui_clarity.html")

    assert "ui_settings_section(title, '', section_id, description, false)" in clarity
    assert "{% if description and description != summary_text %}<p class=\"ui-settings-section__description\"" in ui


def test_personal_model_uses_tabs_and_quiet_per_item_actions() -> None:
    page = _text("aria/templates/memories_auto_memory.html")
    item = _text("aria/templates/_personal_claim_item.html")

    assert 'role="tablist"' in page
    assert page.count('role="tab"') == 3
    assert 'aria-selected="true"' in page
    assert "config_memory.claim_summary" not in item
    assert 'class="ui-secondary-action ui-compact-action personal-claim-correct"' in item
    assert 'class="memory-learning-delete ui-danger-action ui-compact-action"' in item


def test_linter_hardened_regressions_block_alpha991_misses() -> None:
    from aria.modules.config_ui.page_linter import RULE_IDS, lint_page_snapshots

    assert RULE_IDS == tuple(f"R{number}" for number in range(1, 19)) + tuple(f"R{number}" for number in range(25, 33))
    broken = {
        "path": "/config/connections/ssh/example",
        "page_type": "detail",
        "inherits_page_base": True,
        "title_count": 1,
        "summary_body_duplicates": ["Host, Nutzer und Schlüssel dieses SSH-Profils."],
        "filter_primary_presentations": ["Alle"],
        "primary_actions_per_section": [{"section": "Profil", "count": 2}],
        "primary_actions_per_repeated_item": [{"item": "Outer Wilds", "count": 1}],
        "danger_actions_without_danger_style": ["Löschen"],
        "editable_detail_identifiers": ["connection_ref"],
        "canonical_parent_section": "help",
        "rendered_parent_section": "settings",
    }
    result = lint_page_snapshots([broken])
    by_rule = {row.rule for row in result.blocking_findings}
    assert {"R6", "R11", "R12", "R17", "R18"} <= by_rule


def test_linter_hardened_regressions_accept_corrected_presentation() -> None:
    from aria.modules.config_ui.page_linter import lint_page_snapshots

    corrected = {
        "path": "/licenses",
        "page_type": "tool",
        "inherits_page_base": True,
        "title_count": 1,
        "summary_body_duplicates": [],
        "filter_primary_presentations": [],
        "primary_actions_per_section": [{"section": "Lizenz", "count": 0}],
        "primary_actions_per_repeated_item": [],
        "danger_actions_without_danger_style": [],
        "editable_detail_identifiers": [],
        "canonical_parent_section": "help",
        "rendered_parent_section": "help",
    }
    assert lint_page_snapshots([corrected]).passed


def test_alpha992_e2e_contract_and_report_paths() -> None:
    scenarios = _text("tests/e2e/scenarios.py")
    assert "page-linter-0.1.0-alpha992" in scenarios
    assert "R1-R18" in scenarios
    assert "U16" in scenarios
    assert (ROOT / ".codex/reports/page-linter-0.1.0-alpha992.md").exists()
    assert (ROOT / ".codex/reports/page-linter-0.1.0-alpha992.json").exists()


def test_allowlist_stays_limited_to_reviewed_chat_and_timeboxed_stats() -> None:
    allowlist = json.loads(_text("tests/e2e/page_linter_allowlist.json"))
    assert allowlist["entries"][0]["path"] == "/"
    assert {(row["path"], row["rule"], row["reason"]) for row in allowlist["entries"][1:]} == set()
