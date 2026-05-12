from __future__ import annotations

from pathlib import Path

import aria.core.learned_recipe_store as learned_store


def test_load_learned_recipe_store_entries_returns_empty_list_when_store_is_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    assert learned_store.load_learned_recipe_store_entries() == []


def test_save_and_reload_learned_recipe_store_entry_round_trips_normalized_entry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    saved = learned_store.save_learned_recipe_store_entry(
        {
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime && df -h / && free -h",
            "experience_count": 5,
        }
    )

    assert saved["recipe_id"] == "learned-ssh-health-check"
    assert saved["promotion_state"] == "eligible"

    loaded = learned_store.load_learned_recipe_store_entries()
    assert len(loaded) == 1
    assert loaded[0]["recipe_id"] == "learned-ssh-health-check"
    assert loaded[0]["preview"] == "SSH command: uptime && df -h / && free -h"


def test_save_learned_recipe_store_entry_replaces_existing_entry_by_recipe_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 2,
        }
    )
    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime && df -h / && free -h",
            "experience_count": 6,
        }
    )

    loaded = learned_store.load_learned_recipe_store_entries()
    assert len(loaded) == 1
    assert loaded[0]["chosen_action"] == "uptime && df -h / && free -h"
    assert loaded[0]["experience_count"] == 6


def test_delete_learned_recipe_store_entry_removes_matching_row(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 2,
        }
    )

    learned_store.delete_learned_recipe_store_entry("learned-ssh-health-check")

    assert learned_store.load_learned_recipe_store_entries() == []


def test_update_learned_recipe_store_entry_persists_admin_promotion_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 3,
        }
    )

    updated = learned_store.update_learned_recipe_store_entry(
        "learned-ssh-health-check",
        {
            "promotion_state": "promoted",
            "promotion_hint": "admin:Promoted from learned recipe review.",
        },
    )

    assert updated["promotion_state"] == "promoted"
    assert updated["promotion_hint"] == "admin:Promoted from learned recipe review."
