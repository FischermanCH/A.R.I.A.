from __future__ import annotations

from pathlib import Path

import yaml

from aria.modules.website_runtime.chat_flows import handle_chat_websites_flow


def _write_websites_config(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "website": {
                        "aria-docs": {
                            "url": "https://example.org/docs",
                            "group_name": "Docs",
                            "title": "ARIA Docs",
                            "description": "Technical documentation",
                            "tags": ["docs", "aria"],
                        },
                        "aria-blog": {
                            "url": "https://example.org/blog",
                            "group_name": "News",
                            "title": "ARIA Blog",
                        },
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_chat_websites_flow_can_open_websites(tmp_path: Path):
    import asyncio

    _write_websites_config(tmp_path)
    outcome = asyncio.run(handle_chat_websites_flow(clean_message="öffne beobachtete webseiten", base_dir=tmp_path))

    assert outcome is not None
    assert outcome.handled is True
    assert "/config/connections/websites" in outcome.assistant_text
    assert "2" in outcome.assistant_text


def test_chat_websites_flow_uses_website_route_readpoint(monkeypatch, tmp_path: Path):
    import asyncio
    import aria.modules.website_runtime.chat_flows as chat_websites_flows

    _write_websites_config(tmp_path)
    monkeypatch.setattr(chat_websites_flows, "websites_config_path", lambda: "/admin/websites")

    outcome = asyncio.run(handle_chat_websites_flow(clean_message="öffne beobachtete webseiten", base_dir=tmp_path))

    assert outcome is not None
    assert "`/admin/websites`" in outcome.assistant_text
    assert "/config/connections/websites" not in outcome.assistant_text


def test_selected_chat_websites_flow_opens_overview_for_list_request(tmp_path: Path):
    import asyncio

    _write_websites_config(tmp_path)
    outcome = asyncio.run(handle_chat_websites_flow(clean_message="zeige beobachtete webseiten", base_dir=tmp_path))

    assert outcome is not None
    assert "Aktuell vorhanden: 2" in outcome.assistant_text


def test_selected_chat_websites_flow_does_not_reparse_group_semantics(tmp_path: Path):
    import asyncio

    _write_websites_config(tmp_path)
    outcome = asyncio.run(handle_chat_websites_flow(clean_message="zeige beobachtete webseiten in Docs", base_dir=tmp_path))

    assert outcome is not None
    assert "Aktuell vorhanden: 2" in outcome.assistant_text


def test_selected_chat_websites_flow_does_not_reparse_single_target_semantics(tmp_path: Path):
    import asyncio

    _write_websites_config(tmp_path)
    outcome = asyncio.run(handle_chat_websites_flow(clean_message="öffne beobachtete webseite aria-docs", base_dir=tmp_path))

    assert outcome is not None
    assert "Aktuell vorhanden: 2" in outcome.assistant_text


def test_selected_chat_websites_flow_does_not_reparse_ambiguous_semantics(tmp_path: Path):
    import asyncio

    _write_websites_config(tmp_path)
    config_path = tmp_path / "config" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["connections"]["website"]["aria-guides"] = {
        "url": "https://example.org/guides",
        "group_name": "Docs",
        "title": "ARIA Guides",
        "tags": ["docs", "guides"],
    }
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")

    outcome = asyncio.run(handle_chat_websites_flow(clean_message="öffne beobachtete webseite docs", base_dir=tmp_path))

    assert outcome is not None
    assert "Aktuell vorhanden: 3" in outcome.assistant_text


def test_selected_chat_websites_flow_has_no_semantic_group_wordlist(tmp_path: Path):
    import asyncio

    _write_websites_config(tmp_path)
    outcome = asyncio.run(handle_chat_websites_flow(clean_message="zeige beobachtete webseiten in dokumentation", base_dir=tmp_path))

    assert outcome is not None
    assert "Aktuell vorhanden: 2" in outcome.assistant_text
