from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

from aria.main import (
    _build_client_skill_progress_hints,
    _discord_alert_error_lines,
    _enable_bootstrap_admin_mode_in_raw_config,
    _is_allowed_edit_path,
    _list_file_editor_entries,
    _friendly_error_text,
    _intent_badge,
    _render_assistant_message_html,
    _resolve_edit_file,
    _replace_agent_name,
    _validate_custom_skill_manifest,
)
from aria.core.access import can_access_settings, is_advanced_config_path
from aria.core.config import normalize_ui_background, normalize_ui_theme
from aria.core.connection_runtime import friendly_discord_test_error_message
from aria.core.skill_runtime import CustomSkillRuntime
from aria.web.config_routes import _apply_factory_reset_to_raw_config
from aria.web.config_routes import _friendly_ssh_setup_error_impl
from aria.web.config_routes import _read_ssh_connections_impl
from aria.web.skills_routes import _is_admin_mode_request
from aria.web.skills_routes import _is_valid_csrf_submission
from aria.web.skills_routes import _remove_custom_skill_config


def test_friendly_memory_unavailable_message() -> None:
    text = _friendly_error_text(["memory_unavailable: connection refused"])
    assert "Memory-Dienst nicht verfügbar" in text


def test_friendly_embedding_failed_message() -> None:
    text = _friendly_error_text(["embedding_failed: invalid model"])
    assert "Textverarbeitung fehlgeschlagen" in text


def test_discord_alert_error_lines_strip_multiline_smb_dump() -> None:
    text = _discord_alert_error_lines(
        [
            "custom_skill_smb_read_error:Failed to retrieve on Fischer_Ronny: Unable to open file\n"
            "==================== SMB Message 0 ====================\n"
            "SMB Header:\n"
            "-----------\n"
            "Command: 0x03 (SMB2_COM_TREE_CONNECT)",
        ]
    )

    assert text == "custom_skill_smb_read_error:Failed to retrieve on Fischer_Ronny: Unable to open file"
    assert "SMB2_COM_TREE_CONNECT" not in text


def test_intent_badge_uses_error_category() -> None:
    icon, label = _intent_badge(["chat"], ["embedding_failed: api key missing"])
    assert icon == "⚠"
    assert label == "embedding_failed"


def test_intent_badge_uses_capability_category() -> None:
    icon, label = _intent_badge(["capability:file_read"], [])
    assert icon == "📄"
    assert label == "file_read"


def test_intent_badge_uses_feed_category() -> None:
    icon, label = _intent_badge(["capability:feed_read"], [])
    assert icon == "📰"
    assert label == "feed_read"


def test_validate_custom_skill_manifest_keeps_skill_name() -> None:
    clean = _validate_custom_skill_manifest(
        {
            "id": "linux-server-update",
            "name": "Linux Server Update",
            "steps": [
                {
                    "id": "s1",
                    "name": "Zusammenfassung",
                    "type": "llm_transform",
                    "params": {"prompt": "Kurz zusammenfassen"},
                    "on_error": "stop",
                }
            ],
        }
    )
    assert clean["name"] == "Linux Server Update"
    assert clean["connections"] == ["llm"]


def test_validate_custom_skill_manifest_accepts_smb_and_rss_steps() -> None:
    clean = _validate_custom_skill_manifest(
        {
            "id": "news-briefing",
            "name": "News Briefing",
            "steps": [
                {
                    "id": "s1",
                    "name": "Feed laden",
                    "type": "rss_read",
                    "params": {"connection_ref": "news-main"},
                    "on_error": "stop",
                },
                {
                    "id": "s2",
                    "name": "Share lesen",
                    "type": "smb_read",
                    "params": {"connection_ref": "smb-main", "remote_path": "/"},
                    "on_error": "continue",
                },
            ],
        }
    )
    assert clean["connections"] == ["rss", "smb"]


def test_discord_test_error_403_gets_friendly_hint() -> None:
    text = friendly_discord_test_error_message(
        HTTPError("https://discord.com/api/webhooks/x/y", 403, "Forbidden", hdrs=None, fp=None)
    )
    assert "403" in text
    assert "Webhooks" in text


def test_render_assistant_message_html_renders_markdown_link() -> None:
    rendered = str(_render_assistant_message_html("1. [Titel](https://example.com/x)\n   2026-03-29 10:00"))
    assert '<a href="https://example.com/x"' in rendered
    assert ">Titel</a>" in rendered
    assert "<br>" in rendered


def test_clean_feed_summary_removes_html_and_truncates() -> None:
    raw = "<p>Hallo <strong>ARIA</strong> mit <a href='https://example.com'>Link</a> und etwas mehr Text für eine Summary.</p>"
    cleaned = CustomSkillRuntime._clean_feed_summary(raw, limit=40)
    assert "ARIA" in cleaned
    assert "<strong>" not in cleaned
    assert cleaned.endswith("…")


def test_replace_agent_name_swaps_plain_aria_tokens_only() -> None:
    text = _replace_agent_name("ARIA denkt nach. A.R.I.A bleibt technisch.", "NOVA")
    assert text == "NOVA denkt nach. A.R.I.A bleibt technisch."


def test_file_editor_allows_only_catalog_edit_targets() -> None:
    assert _is_allowed_edit_path(Path(__file__).resolve().parents[1] / "prompts" / "persona.md") is True
    assert _is_allowed_edit_path(Path(__file__).resolve().parents[1] / "prompts" / "skills" / "memory.md") is True
    assert _is_allowed_edit_path(Path(__file__).resolve().parents[1] / "docs" / "help" / "memory.md") is False
    assert _is_allowed_edit_path(Path(__file__).resolve().parents[1] / "aria" / "skills" / "example.py") is False


def test_file_editor_catalog_lists_help_files_as_readonly() -> None:
    rows = {row["path"]: row for row in _list_file_editor_entries()}
    assert rows["docs/help/memory.md"]["mode"] == "readonly"
    assert rows["prompts/persona.md"]["mode"] == "edit"


def test_file_editor_rejects_writing_readonly_help_file() -> None:
    try:
        _resolve_edit_file("docs/help/security.md")
    except ValueError as exc:
        assert "nur lesbar" in str(exc)
    else:
        raise AssertionError("readonly help file unexpectedly resolved as editable")


def test_build_client_skill_progress_hints_includes_triggers_and_steps() -> None:
    rows = _build_client_skill_progress_hints(
        [
            {
                "id": "server-update-2nodes",
                "name": "Server Update",
                "router_keywords": ["server update", "apt upgrade"],
                "steps": [
                    {"name": "Update Server 1"},
                    {"name": "Update Server 2"},
                    {"name": "Zusammenfassen"},
                ],
            }
        ]
    )
    assert rows[0]["id"] == "server-update-2nodes"
    assert "server update" in rows[0]["triggers"]
    assert rows[0]["steps"] == ["Update Server 1", "Update Server 2", "Zusammenfassen"]


def test_apply_factory_reset_to_raw_config_clears_runtime_sections() -> None:
    raw = {
        "connections": {"ssh": {"srv": {"host": "x"}}, "rss": {"feed": {"feed_url": "https://example.org"}}},
        "security": {"bootstrap_locked": True, "guardrails": {"g1": {"kind": "ssh_command"}}},
        "skills": {"custom": {"server-update": {"enabled": True}}},
        "channels": {"api": {"enabled": True, "auth_token": "secret"}},
        "ui": {"debug_mode": True, "language": "de"},
    }
    clean = _apply_factory_reset_to_raw_config(raw)
    assert clean["security"]["bootstrap_locked"] is False
    assert clean["security"]["guardrails"] == {}
    assert clean["skills"]["custom"] == {}
    assert clean["channels"]["api"]["auth_token"] == ""
    assert clean["ui"]["debug_mode"] is False
    assert clean["connections"]["ssh"] == {}
    assert clean["connections"]["rss"] == {}


def test_enable_bootstrap_admin_mode_in_raw_config_sets_debug_mode() -> None:
    raw = {"ui": {"language": "de", "debug_mode": False}}
    clean = _enable_bootstrap_admin_mode_in_raw_config(raw)
    assert clean["ui"]["debug_mode"] is True
    assert clean["ui"]["language"] == "de"


def test_can_access_settings_requires_admin_role() -> None:
    assert can_access_settings("admin") is True
    assert can_access_settings("user") is False
    assert can_access_settings("") is False


def test_advanced_config_path_covers_connections_prompts_and_language() -> None:
    assert is_advanced_config_path("/config/connections/ssh") is True
    assert is_advanced_config_path("/config/prompts") is True
    assert is_advanced_config_path("/config/language") is True
    assert is_advanced_config_path("/config/appearance") is True
    assert is_advanced_config_path("/config/backup") is True


def test_is_admin_mode_request_requires_advanced_mode_not_only_admin_role() -> None:
    request = SimpleNamespace(state=SimpleNamespace(can_access_advanced_config=False, debug_mode=False))
    assert _is_admin_mode_request(request, lambda _req: {"role": "admin"}, lambda role: str(role or "").strip().lower()) is False
    request2 = SimpleNamespace(state=SimpleNamespace(can_access_advanced_config=True, debug_mode=True))
    assert _is_admin_mode_request(request2, lambda _req: {"role": "admin"}, lambda role: str(role or "").strip().lower()) is True


def test_multipart_skill_import_csrf_validation_accepts_matching_token() -> None:
    assert _is_valid_csrf_submission("abc_DEF-123", "abc_DEF-123") is True
    assert _is_valid_csrf_submission("abc DEF-123", "abc_DEF-123") is False


def test_friendly_ssh_setup_error_for_missing_ssh_keygen_de() -> None:
    exc = FileNotFoundError(2, "No such file or directory", "ssh-keygen")
    text = _friendly_ssh_setup_error_impl("de", exc)
    assert "ssh-keygen" in text
    assert "manuell" in text


def test_friendly_ssh_setup_error_for_missing_ssh_keygen_en() -> None:
    exc = FileNotFoundError(2, "No such file or directory", "ssh-keygen")
    text = _friendly_ssh_setup_error_impl("en", exc)
    assert "ssh-keygen" in text
    assert "manually" in text


def test_normalize_ui_theme_falls_back_to_matrix() -> None:
    assert normalize_ui_theme("sunset") == "sunset"
    assert normalize_ui_theme("nope") == "matrix"


def test_normalize_ui_background_falls_back_to_grid() -> None:
    assert normalize_ui_background("aurora") == "aurora"
    assert normalize_ui_background("unknown") == "grid"


def test_read_ssh_connections_impl_keeps_connection_metadata() -> None:
    raw = {
        "connections": {
            "ssh": {
                "linux-main": {
                    "host": "10.0.0.5",
                    "port": 22,
                    "user": "aria",
                    "key_path": "/app/data/ssh_keys/linux-main_ed25519",
                    "timeout_seconds": 20,
                    "strict_host_key_checking": "accept-new",
                    "allow_commands": ["uptime"],
                    "guardrail_ref": "readonly-linux",
                    "title": "Linux Server",
                    "description": "Mein Linux Server fuer Updates",
                    "aliases": ["mein linux server", "updateserver"],
                    "tags": ["linux", "ops"],
                }
            }
        }
    }

    rows = _read_ssh_connections_impl(
        lambda: raw,
        lambda value: str(value or "").strip().lower(),
    )

    row = rows["linux-main"]
    assert row["guardrail_ref"] == "readonly-linux"
    assert row["title"] == "Linux Server"
    assert row["description"] == "Mein Linux Server fuer Updates"
    assert row["aliases"] == ["mein linux server", "updateserver"]
    assert row["tags"] == ["linux", "ops"]
    assert row["aliases_text"] == "mein linux server, updateserver"


def test_remove_custom_skill_config_drops_skill_entry() -> None:
    raw = {
        "skills": {
            "custom": {
                "linux-updates": {"enabled": True},
                "echo-chat": {"enabled": False},
            }
        }
    }

    clean = _remove_custom_skill_config(raw, "linux-updates")

    assert "linux-updates" not in clean["skills"]["custom"]
    assert "echo-chat" in clean["skills"]["custom"]
