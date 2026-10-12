from __future__ import annotations

from pathlib import Path

from aria.modules.config_ui.page_linter import RULE_IDS, lint_page_snapshots


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_alpha994_release_metadata_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in _text("pyproject.toml")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in _text(
        "aria/modules/release_update/release_meta.py"
    )
    assert _text("CHANGELOG.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert _text("CHANGELOG.de.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "public release remains `0.1.0-alpha983`" in _text("CHANGELOG.md")


def test_page_linter_declares_alpha994_rules_and_blocks_regressions() -> None:
    assert RULE_IDS == tuple(f"R{number}" for number in range(1, 19)) + tuple(f"R{number}" for number in range(25, 33))
    broken = {
        "path": "/config/connections/rss",
        "page_type": "overview",
        "inherits_page_base": True,
        "title_count": 1,
        "visible_inventory": True,
        "inventory_expected_count": 31,
        "inventory_rendered_count": 0,
        "german_denied_terms": ["Verbindungen"],
        "invalid_back_links": ["/config/connections/rss"],
        "overview_create_action_count": 2,
        "canonical_parent_section": "connections",
        "rendered_parent_section": "connections",
    }

    result = lint_page_snapshots([broken])

    assert {"R4", "R25", "R26", "R27"} <= {
        finding.rule for finding in result.blocking_findings
    }


def test_english_detector_exempts_user_text_but_finds_german_ui() -> None:
    from aria.modules.config_ui.page_linter import detect_german_ui_terms

    findings = detect_german_ui_terms(
        [
            "Connection overview",
            "Die Verbindung ist nicht verfügbar.",
            "München Lab",
            "A user description für den Garten",
        ],
        allowed_texts=["München Lab", "A user description für den Garten"],
    )

    assert findings == ["Die Verbindung ist nicht verfügbar."]


def test_connection_overview_has_one_create_action_and_real_back_link() -> None:
    intro = _text("aria/templates/_connection_page_intro.html")
    mode_nav = _text("aria/templates/_connection_mode_nav.html")

    assert "window.location.assign" not in intro
    assert 'data-ui-back-link="true"' in intro
    assert "connection-create-link" not in mode_nav


def test_rss_inventory_is_rendered_on_overview_with_groups_and_counts() -> None:
    template = _text("aria/templates/config_connections_rss.html")

    assert "connection_page_type == 'overview'" in template
    assert "data-rss-group-card" in template
    assert "data-rss-feed-card" in template
    assert "data-connection-inventory-item" in template
    assert "group.total" in template

    website = _text("aria/templates/config_connections_websites.html")
    assert "connection_page_type == 'overview'" in website
    assert "data-website-group-card" in website
    assert "data-connection-inventory-item" in website

    routes = _text("aria/modules/connections_ui_readonly/detail_routes.py")
    assert 'str(getattr(request.state, "lang", "de") or "de")' in routes


def test_sample_connection_descriptions_are_bilingual() -> None:
    for path in sorted((ROOT / "samples/connections").glob("*.sample.yaml")):
        text = path.read_text(encoding="utf-8")
        assert "description_de:" in text, path
        assert "description_en:" in text, path


def test_connection_types_hint_is_translated_in_both_catalogs() -> None:
    for language in ("de", "en"):
        assert '"connections_overview.section_types_hint"' in _text(
            f"aria/i18n/{language}.json"
        )
    assert '"config_conn.website_no_profiles_hint"' in _text("aria/i18n/en.json")


def test_persisted_connection_status_and_recipe_wizard_copy_follow_language() -> None:
    from aria.modules.connections_runtime_status.runtime import _localized_cached_message
    from aria.modules.recipe_store.wizard_catalog import (
        _recipe_type_connection_choices,
        _recipe_type_options,
        _recipe_type_presets,
    )

    assert _localized_cached_message(
        "Webhook-Test fehlgeschlagen: Das Ziel meldet 404. Die URL wurde wahrscheinlich geändert oder gelöscht.",
        lang="en",
    ).startswith("Webhook test failed:")
    assert _recipe_type_options("en")[1]["hint"] == "Runs a safe status check on a host or service."
    assert _recipe_type_presets("en")["health_check"]["hint"] == "Runs a safe status check on a host or service."
    assert _recipe_type_connection_choices("en")["health_check"][0] == {
        "kind": "ssh",
        "label_key": "connection.ssh.label",
        "label": "SSH connection",
        "field": "connection_ref",
        "step_type": "ssh_run",
        "hint_key": "connection.ssh.hint",
        "hint": "Choose the host or service where the check should run.",
    }


def test_navigation_registry_maps_connection_edit_pages_to_connections_parent() -> None:
    from aria.modules.navigation_shell.navigation import canonical_parent_href

    class Request:
        class URL:
            path = "/config/connections/rss"

        url = URL()
        query_params: dict[str, str] = {}

    assert canonical_parent_href(Request()) == "/connections"


def test_e2e_contract_seeds_all_connection_kinds_and_bilingual_linter() -> None:
    runner = _text("scripts/e2e/run.sh")
    scenarios = _text("tests/e2e/scenarios.py")

    for kind in (
        "ssh", "sftp", "smb", "discord", "rss", "website", "webhook",
        "http_api", "google_calendar", "mqtt", "email", "imap",
    ):
        assert f"  {kind}:" in runner or f'["{kind}"]' in runner
    assert 'for index in range(1, 33)' in runner
    linter = _text("aria/modules/config_ui/page_linter.py")
    assert all(f'"R{number}"' in linter for number in (25, 26, 27))
    assert "test_u19_alpha994_bilingual_page_linter_and_connection_inventory" in scenarios
    assert 'for language in ("de", "en")' in scenarios
