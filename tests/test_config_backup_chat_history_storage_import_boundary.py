from __future__ import annotations

import json
from pathlib import Path

import aria.modules.chat_history_storage.store as legacy_chat_history
import aria.modules.config_backup.backup as legacy_config_backup
from aria.modules.chat_history_storage import store as chat_history_store
from aria.modules.config_backup import backup as config_backup


def test_legacy_modules_are_canonical_module_identities() -> None:
    assert legacy_config_backup is config_backup
    assert legacy_chat_history is chat_history_store


def test_chat_history_storage_is_bounded_to_supplied_temporary_path(tmp_path: Path) -> None:
    store = chat_history_store.FileChatHistoryStore(tmp_path / "history", max_messages=4)

    store.append_exchange(
        "../../Demo User",
        user_message="synthetic user message",
        assistant_message="synthetic assistant message",
        badge_icon="chat",
        badge_intent="chat",
        badge_tokens=2,
        badge_cost_usd="n/a",
        badge_duration="0.1",
    )

    files = list((tmp_path / "history").glob("*.json"))
    assert len(files) == 1
    assert files[0].parent == tmp_path / "history"
    assert "/" not in files[0].name
    assert "\\" not in files[0].name
    assert [row["role"] for row in store.load_history("../../Demo User")] == ["user", "assistant"]


def test_config_backup_parser_rejects_paths_outside_declared_areas() -> None:
    payload = {
        "schema_version": config_backup.BACKUP_SCHEMA_VERSION,
        "config": {},
        "secure_store": {"secrets": {}, "users": []},
        "stored_recipes": [],
        "prompt_files": {"../outside.md": "no"},
        "support_files": {},
    }

    try:
        config_backup.parse_config_backup_payload(json.dumps(payload))
    except ValueError as exc:
        assert "outside the allowed area" in str(exc)
    else:
        raise AssertionError("path traversal payload was accepted")
