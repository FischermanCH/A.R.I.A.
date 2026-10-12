from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules.native_agent.handler import _looks_like_unsourced_action_claim
from aria.modules.native_agent.pipeline_bridge import warm_native_agent_local_state


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_alpha990_release_contract_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in _text("pyproject.toml")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in _text(
        "aria/modules/release_update/release_meta.py"
    )
    assert _text("CHANGELOG.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert _text("CHANGELOG.de.md").startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "0.1.0-alpha983" in _text("CHANGELOG.md")


def test_generic_purpose_filler_is_removed_and_chat_stays_clean() -> None:
    generic_de = "Hier kannst du diesen Bereich ansehen und die dafür freigegebenen Aktionen ausführen."
    generic_en = "Here you can review this area and run the actions authorized for it."
    corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "aria").rglob("*")
        if path.is_file() and path.suffix in {".html", ".json", ".py"}
    )
    assert generic_de not in corpus
    assert generic_en not in corpus
    chat = _text("aria/templates/chat.html")
    assert "ui-page-purpose" not in chat
    assert "authenticated-page-purpose" not in _text("aria/templates/base.html")


def test_collapsible_settings_pattern_is_documented_and_accessible() -> None:
    docs = _text("docs/ui/ui-clarity-pattern.md")
    macro = _text("aria/templates/_ui_clarity.html")
    assert "Collapsed settings" in docs
    assert "one-line summary" in docs
    assert "<details" in macro and "<summary" in macro
    assert "data-ui-settings-section" in macro
    assert "localStorage" in _text("aria/templates/base.html")


def test_connection_overview_and_detail_follow_shared_fidelity_contract() -> None:
    intro = _text("aria/templates/_connection_page_intro.html")
    status = _text("aria/templates/_connection_status_block_content.html")
    ssh = _text("aria/templates/config_connections_ssh.html")
    guardrail = _text("aria/templates/_connection_guardrail_select.html")
    assert "connection-overview-header" in intro
    assert "connection-overview-summary" in intro
    assert '<details class="connection-overview-summary ui-info-panel">' in intro
    assert "config_conn.open_profile" in status
    assert "connection_primary_action" not in ssh
    assert "config_conn.guardrail_label" in guardrail
    assert "ui-secondary-action" in ssh


def test_settings_pages_have_specific_purpose_and_collapsible_sections() -> None:
    for path in (
        "aria/templates/config_llm.html",
        "aria/templates/config_embeddings.html",
        "aria/templates/config_llm_debug.html",
        "aria/templates/config_language.html",
    ):
        source = _text(path)
        assert "ui-page-purpose" in source, path
        assert "data-ui-settings-section" in source or "ui_settings_section" in source, path
    embeddings = _text("aria/templates/config_embeddings.html")
    assert "config_embed.vector_invalidation_warning" in embeddings
    debug = _text("aria/templates/config_llm_debug.html")
    assert "llm_debug.privacy_notice" in debug


def test_selftest_is_merged_into_llm_and_old_url_redirects() -> None:
    llm = _text("aria/templates/config_llm.html")
    routes = _text("aria/modules/native_toolcall_selftest/routes.py")
    navigation = _text("aria/modules/navigation_shell/navigation.py")
    assert "Tool-Calling testen" in llm
    assert "/config/llm/toolcall-selftest" in llm
    assert "RedirectResponse" in routes and '"/config/llm"' in routes
    assert '"admin.native_toolcall_selftest"' not in navigation


def test_personal_model_is_readable_and_keeps_existing_action_routes() -> None:
    page = _text("aria/templates/memories_auto_memory.html")
    item = _text("aria/templates/_personal_claim_item.html")
    assert page.count('id="personal-model-title"') == 1
    assert "config_memory.personal_model_purpose" in page
    assert "config_memory.kind_preference" in item
    assert "config_memory.kind_fact" in item
    assert "config_memory.usage_used" in item and "config_memory.usage_offered" in item
    assert "config_memory.raw_claim_key" in item
    assert "/memories/auto-memory/correct-claim" in item
    assert "/memories/auto-memory/delete-claim" in item


def test_memory_browser_partial_remains_byte_identical_to_alpha989() -> None:
    assert hashlib.sha256(
        (ROOT / "aria/templates/_memory_drilldown_browser.html").read_bytes()
    ).hexdigest() == "e91e7164266e0452a10622c7009075800b8ee6b4db64de3ddc17b972bfdfcc1c"


def test_help_is_grouped_in_four_current_sections_without_duplicates() -> None:
    manifest = _text("aria/modules/static_help_docs/manifest.py")
    template = _text("aria/templates/help.html")
    section_header = _text("aria/templates/_help_section_header.html")
    for group in ("getting_started", "using_aria", "manage", "technical_legal"):
        assert f'"id": "{group}"' in manifest
    assert '"id": "alpha-help-system"' not in manifest
    assert '"id": "help-system"' not in manifest
    assert "_help_section_header.html" in template
    assert "help-doc-groups" in section_header
    assert "Agent & Hintergrund-Jobs" in manifest
    assert "Agentic Operator" not in manifest


def test_existing_state_descriptions_do_not_trigger_action_guard() -> None:
    assert not _looks_like_unsourced_action_claim(
        "Hier sind die Dokumente, die gespeichert wurden und bereits im Inventar stehen."
    )
    assert not _looks_like_unsourced_action_claim(
        "The documents that were imported are listed below."
    )
    assert _looks_like_unsourced_action_claim("Ich habe den blauen Würfel erstellt.")


def test_preloop_and_semantic_diagnostics_are_named_and_connection_aware() -> None:
    bridge = _text("aria/modules/native_agent/pipeline_bridge.py")
    assert "bindings=" in bridge
    assert "stores=" in bridge
    assert "recipes=" in bridge
    assert "source_connection=" in bridge
    assert "target_connection=" in bridge


def test_native_local_state_is_warmed_once_before_the_first_turn(tmp_path: Path) -> None:
    owner = SimpleNamespace(_project_root=tmp_path)

    first = warm_native_agent_local_state(owner)
    second = warm_native_agent_local_state(owner)

    assert first == second
    assert owner._native_pending_store is first["pending_store"]
    assert owner._native_observed_sequence_store is first["observed_sequence_store"]
    assert owner._native_observed_claim_store is first["observed_claim_store"]
    assert owner._native_recipe_embedding_cache is first["recipe_embedding_cache"]
    assert "warm_native_agent_local_state(" in _text("aria/main.py")


def test_alpha990_e2e_contract_defines_u10_through_u14_and_seeded_screenshots() -> None:
    scenarios = _text("tests/e2e/scenarios.py")
    for scenario in ("U10", "U11", "U12", "U13", "U14"):
        assert scenario in scenarios
    assert "ui-fidelity-alpha990" in scenarios
    assert "seeded" in scenarios.lower()


def test_i18n_json_stays_valid() -> None:
    for lang in ("de", "en"):
        json.loads(_text(f"aria/i18n/{lang}.json"))
