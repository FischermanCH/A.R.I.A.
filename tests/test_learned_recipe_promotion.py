from __future__ import annotations

import json
from pathlib import Path

import aria.core.recipe_manifests as recipe_manifests
import aria.core.learned_recipe_store as learned_store
from aria.core.learned_recipe_promotion import build_stored_recipe_manifest_from_learned_entry
from aria.core.learned_recipe_promotion import promote_learned_recipe_to_stored_recipe


def test_build_stored_recipe_manifest_from_learned_entry_maps_ssh_recipe() -> None:
    manifest = build_stored_recipe_manifest_from_learned_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "title": "Linux Health",
            "summary": "Checks a Linux host.",
            "connection_kind": "ssh",
            "connection_ref": "srv-a",
            "capability": "ssh_command",
            "chosen_action": "uptime && df -h /",
            "router_keywords": ["linux health", "server check"],
            "inputs": {"command": "uptime && df -h /"},
            "experience_count": 5,
        }
    )

    assert manifest["id"] == "ssh-health-check"
    assert manifest["name"] == "Linux Health"
    assert manifest["connections"] == ["ssh"]
    assert manifest["steps"][0]["type"] == "ssh_run"
    assert manifest["steps"][0]["params"]["connection_ref"] == "srv-a"
    assert manifest["steps"][0]["params"]["command"] == "uptime && df -h /"


def test_build_stored_recipe_manifest_blocks_multi_target_learned_recipe() -> None:
    try:
        build_stored_recipe_manifest_from_learned_entry(
            {
                "recipe_id": "learned-ssh-health-check",
                "connection_kind": "ssh",
                "connection_ref": "srv-a",
                "capability": "ssh_command",
                "chosen_action": "uptime",
                "experience_count": 8,
                "recipe_scope": {"target_scope": "multi_target", "learning_origin": "plural_target_scope"},
            }
        )
    except ValueError as exc:
        assert "Multi-target observations stay context-only" in str(exc)
    else:
        raise AssertionError("multi-target learned recipes must not promote directly")


def test_build_stored_recipe_manifest_blocks_side_effect_learned_recipe() -> None:
    try:
        build_stored_recipe_manifest_from_learned_entry(
            {
                "recipe_id": "learned-discord-send",
                "connection_kind": "discord",
                "connection_ref": "alerts",
                "capability": "discord_send",
                "chosen_action": "Deploy finished",
                "inputs": {"message": "Deploy finished"},
                "experience_count": 7,
                "promotion_state": "eligible",
            }
        )
    except ValueError as exc:
        assert "Side-effect learned actions stay review-only" in str(exc)
    else:
        raise AssertionError("side-effect learned recipes must not promote directly")


def test_promote_learned_recipe_to_stored_recipe_creates_manifest_and_updates_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", tmp_path)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", tmp_path / "data" / "recipes")
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", tmp_path / "data" / "recipes" / "_trigger_index.json")
    (tmp_path / "data" / "recipes").mkdir(parents=True, exist_ok=True)
    learned_store.invalidate_learned_recipe_store_cache()
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "title": "Linux Health",
            "summary": "Checks a Linux host.",
            "connection_kind": "ssh",
            "connection_ref": "srv-a",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "router_keywords": ["linux health"],
            "inputs": {"command": "uptime"},
            "experience_count": 5,
        }
    )

    stored = promote_learned_recipe_to_stored_recipe("learned-ssh-health-check")

    assert stored["id"] == "ssh-health-check"
    manifest = json.loads((tmp_path / "data" / "recipes" / "ssh-health-check.json").read_text(encoding="utf-8"))
    assert manifest["steps"][0]["type"] == "ssh_run"
    rows = learned_store.load_learned_recipe_store_entries()
    assert rows[0]["promotion_state"] == "promoted"
    assert rows[0]["stored_recipe_id"] == "ssh-health-check"
