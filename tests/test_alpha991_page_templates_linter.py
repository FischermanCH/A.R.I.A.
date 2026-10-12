from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.modules.connections_mutations.admin_helpers import (
    ConnectionAdminHelperDeps,
    ConnectionAdminHelpers,
)
from aria.modules.connections_profiles.admin import ConnectionAdminError


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aria" / "templates"
PAGE_BASES = {
    "overview": "page_types/overview_page.html",
    "detail": "page_types/detail_page.html",
    "create": "page_types/create_page.html",
    "settings": "page_types/settings_page.html",
    "tool": "page_types/tool_page.html",
}


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_current_ui_release_contract_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in _text("pyproject.toml")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in _text(
        "aria/modules/release_update/release_meta.py"
    )
    assert _text("CHANGELOG.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert _text("CHANGELOG.de.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "0.1.0-alpha983" in _text("CHANGELOG.md")


@pytest.mark.parametrize("page_type,template", PAGE_BASES.items())
def test_one_base_template_exists_for_each_page_type(page_type: str, template: str) -> None:
    source = (TEMPLATES / template).read_text(encoding="utf-8")
    assert source.count('{% extends "base.html" %}') == 1
    assert f'data-page-type-base="{page_type}"' in source
    assert "page_body" in source
    assert "page_danger" in source


def test_authenticated_pages_no_longer_extend_root_base_directly() -> None:
    allowed = {"login.html", "session_expired.html"}
    direct = {
        path.name
        for path in TEMPLATES.glob("*.html")
        if path.read_text(encoding="utf-8").startswith('{% extends "base.html" %}')
    }
    assert direct <= allowed


def test_page_linter_contract_covers_every_rule_and_reports() -> None:
    from aria.modules.config_ui.page_linter import RULE_IDS, lint_page_snapshots

    assert RULE_IDS == tuple(f"R{number}" for number in range(1, 19)) + tuple(f"R{number}" for number in range(25, 33))
    result = lint_page_snapshots([])
    assert result.rule_ids == RULE_IDS
    assert result.pages == 0
    allowlist = json.loads(
        _text("tests/e2e/page_linter_allowlist.json")
    )
    assert allowlist["version"] == 1
    assert allowlist["entries"][0] == {
        "path": "/",
        "rule": "R2",
        "reason": (
            "Der Chat ist eine immersive Arbeitsfläche; die globale A.R.I.A.-Kopfleiste ist der "
            "Titel und R3 verbietet dort bewusst eine zusätzliche Seitenhilfe."
        ),
    }
    assert {(row["path"], row["rule"], row["reason"]) for row in allowlist["entries"][1:]} == set()
    assert (ROOT / ".codex/reports/page-linter-0.1.0-alpha992.md").exists()
    assert (ROOT / ".codex/reports/page-linter-0.1.0-alpha992.json").exists()


def test_page_linter_rules_are_blocking_and_allowlist_is_explicit() -> None:
    from aria.modules.config_ui.page_linter import lint_page_snapshots

    broken = {
        "path": "/broken",
        "page_type": "overview",
        "inherits_page_base": False,
        "title_count": 2,
        "purposes": ["generic", "generic"],
        "purpose_directly_after_title": False,
        "generic_or_duplicate_purpose": True,
        "visible_inventory": False,
        "statistics_blocks": 2,
        "open_statistics_blocks": 1,
        "duplicate_text_blocks": ["duplicated"],
        "visible_technical_ids": ["a" * 32],
        "ascii_umlaut_terms": ["fuer"],
        "english_denied_terms": ["profiles"],
        "plain_action_elements": ["Run"],
        "filter_uses_primary_style": True,
        "max_primary_actions_per_section": 2,
        "danger_not_final": True,
        "secret_hits": ["seeded-secret"],
        "bad_count_labels": ["14 profile"],
        "visible_snake_case": ["likes_game"],
        "bad_control_dimensions": ["chip (200x90)"],
        "editable_detail_identifiers": ["connection_ref"],
        "german_denied_terms": ["Zurück zu Verbindungen"],
        "invalid_back_links": ["javascript:history.back()"],
        "overview_create_action_count": 2,
        "visible_raw_values": ["2026-10-10T08:00:00+02:00"],
        "bad_locale_values": ["$1.2345"],
        "form_geometry_issues": ["unlabelled:query"],
    }
    result = lint_page_snapshots([broken])
    assert set(result.rule_ids) == {*(f"R{number}" for number in range(1, 19)), *(f"R{number}" for number in range(25, 33))}
    assert set(row.rule for row in result.blocking_findings) == set(result.rule_ids) - {"R3", "R5", "R31", "R32"}
    allowed = lint_page_snapshots(
        [broken],
        allowlist={
            "entries": [
                {"path": "/broken", "rule": rule, "reason": "review fixture"}
                for rule in result.rule_ids
            ]
        },
    )
    assert allowed.passed


def test_chat_and_detail_specific_linter_rules() -> None:
    from aria.modules.config_ui.page_linter import lint_page_snapshots

    chat = {"path": "/", "page_type": "overview", "title_count": 1, "purposes": ["Help"]}
    detail = {
        "path": "/config/connections/ssh/example",
        "page_type": "detail",
        "title_count": 1,
        "purposes": [],
        "statistics_blocks": 1,
        "has_create_action": True,
    }
    result = lint_page_snapshots([chat, detail])
    assert {row.rule for row in result.blocking_findings} >= {"R3", "R5"}


def test_personal_model_hides_ids_and_maps_known_predicates() -> None:
    source = _text("aria/templates/_personal_claim_item.html")
    for label in (
        "Lieblingsspiel",
        "Morgengetränk",
        "Antwortstil",
        "Diagnose-Aufbau",
        "Spielt",
    ):
        assert label in source
    assert 'class="claim-technical-details"' in source
    summary_end = source.index("</summary>")
    assert "claim.claim_key" not in source[:summary_end]
    assert "scope_global" in source and "überall" in source
    assert "Feedback +" not in source
    assert 'class="learning-candidate-controls personal-claim-visible-actions"' in source
    assert 'ui-secondary-action ui-compact-action personal-claim-correct' in source
    assert "data-open-claim-editor" not in source
    assert "Korrigieren" in source and "Löschen" in source


def test_connection_detail_ref_is_text_and_rename_is_explicit() -> None:
    ssh = _text("aria/templates/config_connections_ssh.html")
    fields = _text("aria/templates/_connection_schema_fields.html")
    assert 'name="connection_ref"' in ssh
    assert 'data-connection-ref-text="true"' in fields
    assert 'type="hidden" name="{{ field.name }}"' in fields
    assert "config_conn.rename_profile" in fields
    assert "config_conn.rename_recipe_warning" in fields


def test_connection_overview_inventory_is_visible_with_open_and_test_actions() -> None:
    clarity = _text("aria/templates/_connection_clarity.html")
    ssh = _text("aria/templates/config_connections_ssh.html")
    webhook = _text("aria/templates/config_connections_webhook.html")
    assert 'data-ui-connection-inventory="visible"' in clarity
    assert "connection-overview-inventory__body" in clarity
    assert "connection_inventory" in ssh and ", true)" in ssh
    assert "config_conn.open_profile" in ssh
    assert "config_conn.test_profile" in ssh
    assert "connection_inventory" in webhook and ", true)" in webhook


def _connection_helpers(recipes: list[dict[str, object]]) -> ConnectionAdminHelpers:
    deps = ConnectionAdminHelperDeps(
        connection_admin_specs={"ssh": {"health_prefix": "ssh", "secret_keys": []}},
        connection_edit_page=lambda kind: f"/config/connections/{kind}",
        connection_ref_query_param=lambda kind: "ref",
        normalize_connection_kind=lambda kind: kind,
        delete_connection_health=lambda key: None,
        read_raw_config=lambda: {"connections": {"ssh": {"old": {"host": "host"}}}},
        write_raw_config=lambda raw: None,
        reload_runtime=lambda: None,
        get_secure_store=lambda raw: None,
        sanitize_connection_name=lambda value: str(value or "").strip(),
        settings=SimpleNamespace(),
        pipeline=SimpleNamespace(_load_stored_recipe_runtime=lambda: recipes),
    )
    return ConnectionAdminHelpers(deps)


def test_connection_rename_blocks_known_recipe_reference_and_allows_unused_ref() -> None:
    recipe = {"steps": [{"type": "ssh_run", "params": {"connection_ref": "old"}}]}
    with pytest.raises(ConnectionAdminError, match="profile_ref_used_by_recipe"):
        _connection_helpers([recipe]).prepare_connection_save("ssh", "new", "old")
    _raw, _store, _rows, ref, original, creating = _connection_helpers([]).prepare_connection_save(
        "ssh", "new", "old"
    )
    assert (ref, original, creating) == ("new", "old", False)


def test_memory_browser_partial_stays_byte_identical() -> None:
    assert hashlib.sha256(
        (TEMPLATES / "_memory_drilldown_browser.html").read_bytes()
    ).hexdigest() == "e91e7164266e0452a10622c7009075800b8ee6b4db64de3ddc17b972bfdfcc1c"


def test_current_e2e_contract_wires_page_linter_and_visual_review() -> None:
    source = _text("tests/e2e/scenarios.py")
    assert "page-linter-0.1.0-alpha992" in source
    assert "U15" in source
    assert "U16" in source
    assert "browser-byte-identity" in source


def test_stats_runtime_diagnostics_are_not_misclassified_as_german_ui_copy() -> None:
    source = _text("aria/templates/stats.html")
    assert 'data-ui-technical-content' in source
    assert "technical.preflight" in source
    assert "technical.gateway" in source
    assert "technical.summary" in source
