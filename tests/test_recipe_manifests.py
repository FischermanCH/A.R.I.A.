import json

from aria.core import recipe_manifests
from aria.web.recipes_routes import _migrate_custom_skill_config


def test_save_stored_recipe_manifest_renames_file_and_prompt(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    recipe_prompts_dir = base_dir / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    recipe_prompts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")

    old_skill_path = recipes_dir / "old-skill.json"
    old_skill_path.write_text(
        json.dumps(
            {
                "id": "old-skill",
                "name": "Old Skill",
                "prompt_file": "prompts/recipes/old-skill.md",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )
    old_prompt_path = recipe_prompts_dir / "old-skill.md"
    old_prompt_path.write_text("prompt", encoding="utf-8")

    clean = recipe_manifests._save_stored_recipe_manifest(
        {
            "id": "new-skill",
            "name": "New Skill",
            "prompt_file": "prompts/recipes/old-skill.md",
            "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
        },
        previous_id="old-skill",
    )

    assert clean["id"] == "new-skill"
    assert clean["prompt_file"] == "prompts/recipes/new-skill.md"
    assert not old_skill_path.exists()
    assert (recipes_dir / "new-skill.json").exists()
    assert not old_prompt_path.exists()
    assert (recipe_prompts_dir / "new-skill.md").exists()


def test_migrate_custom_skill_config_moves_old_id_to_new_id() -> None:
    raw = {
        "skills": {
            "custom": {
                "old-skill": {"enabled": False, "note": "legacy"},
            }
        }
    }

    migrated = _migrate_custom_skill_config(raw, old_id="old-skill", new_id="new-skill", enabled=True)

    assert "old-skill" not in migrated["skills"]["custom"]
    assert migrated["skills"]["custom"]["new-skill"]["enabled"] is True
    assert migrated["skills"]["custom"]["new-skill"]["note"] == "legacy"


def test_delete_stored_recipe_manifest_removes_file_and_default_prompt(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    recipe_prompts_dir = base_dir / "prompts" / "recipes"
    recipe_prompts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")

    skill_path = recipes_dir / "linux-updates.json"
    skill_path.write_text(
        json.dumps(
            {
                "id": "linux-updates",
                "name": "Linux Updates",
                "prompt_file": "prompts/recipes/linux-updates.md",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )
    prompt_path = recipe_prompts_dir / "linux-updates.md"
    prompt_path.write_text("prompt", encoding="utf-8")

    result = recipe_manifests._delete_stored_recipe_manifest("linux-updates")

    assert result["id"] == "linux-updates"
    assert result["prompt_removed"] is True
    assert not skill_path.exists()
    assert not prompt_path.exists()


def test_load_stored_recipe_manifests_uses_cache_and_invalidates_on_change(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    recipes_dir = base_dir / "data" / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(recipe_manifests, "BASE_DIR", base_dir)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")
    recipe_manifests._invalidate_stored_recipe_manifest_cache()

    skill_path = recipes_dir / "ops-report.json"
    skill_path.write_text(
        json.dumps(
            {
                "id": "ops-report",
                "name": "Ops Report",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )

    original_json_loads = recipe_manifests.json.loads
    call_count = {"value": 0}

    def _counting_loads(raw: str) -> object:
        call_count["value"] += 1
        return original_json_loads(raw)

    monkeypatch.setattr(recipe_manifests.json, "loads", _counting_loads)

    rows_first, errors_first = recipe_manifests._load_stored_recipe_manifests()
    rows_second, errors_second = recipe_manifests._load_stored_recipe_manifests()

    assert errors_first == []
    assert errors_second == []
    assert rows_first[0]["name"] == "Ops Report"
    assert rows_second[0]["name"] == "Ops Report"
    assert call_count["value"] == 1

    rows_first[0]["name"] = "Mutated in test"
    rows_third, _ = recipe_manifests._load_stored_recipe_manifests()
    assert rows_third[0]["name"] == "Ops Report"

    skill_path.write_text(
        json.dumps(
            {
                "id": "ops-report",
                "name": "Ops Report Updated",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )

    rows_after_change, _ = recipe_manifests._load_stored_recipe_manifests()
    assert rows_after_change[0]["name"] == "Ops Report Updated"
    assert call_count["value"] == 2


def test_normalize_recipe_steps_manifest_keeps_valid_condition() -> None:
    steps = recipe_manifests._normalize_recipe_steps_manifest(
        [
            {
                "id": "s5",
                "type": "discord_send",
                "params": {"message": "{s4_output}"},
                "condition": {
                    "source": "s4_output",
                    "operator": "not_equals",
                    "value": "NO_ALERT",
                    "ignore_case": True,
                },
            }
        ]
    )

    assert steps == [
        {
            "id": "s5",
            "name": "",
            "type": "discord_send",
            "params": {"message": "{s4_output}"},
            "on_error": "stop",
            "condition": {
                "source": "s4_output",
                "operator": "not_equals",
                "value": "NO_ALERT",
                "ignore_case": True,
            },
        }
    ]
