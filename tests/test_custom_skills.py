import json

from aria.core import custom_skills
from aria.web.skills_routes import _migrate_custom_skill_config


def test_save_custom_skill_manifest_renames_file_and_prompt(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    prompts_dir = base_dir / "prompts" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")

    old_skill_path = skills_dir / "old-skill.json"
    old_skill_path.write_text(
        json.dumps(
            {
                "id": "old-skill",
                "name": "Old Skill",
                "prompt_file": "prompts/skills/old-skill.md",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )
    old_prompt_path = prompts_dir / "old-skill.md"
    old_prompt_path.write_text("prompt", encoding="utf-8")

    clean = custom_skills._save_custom_skill_manifest(
        {
            "id": "new-skill",
            "name": "New Skill",
            "prompt_file": "prompts/skills/old-skill.md",
            "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
        },
        previous_id="old-skill",
    )

    assert clean["id"] == "new-skill"
    assert clean["prompt_file"] == "prompts/skills/new-skill.md"
    assert not old_skill_path.exists()
    assert (skills_dir / "new-skill.json").exists()
    assert not old_prompt_path.exists()
    assert (prompts_dir / "new-skill.md").exists()


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


def test_delete_custom_skill_manifest_removes_file_and_default_prompt(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    prompts_dir = base_dir / "prompts" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")

    skill_path = skills_dir / "linux-updates.json"
    skill_path.write_text(
        json.dumps(
            {
                "id": "linux-updates",
                "name": "Linux Updates",
                "prompt_file": "prompts/skills/linux-updates.md",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )
    prompt_path = prompts_dir / "linux-updates.md"
    prompt_path.write_text("prompt", encoding="utf-8")

    result = custom_skills._delete_custom_skill_manifest("linux-updates")

    assert result["id"] == "linux-updates"
    assert result["prompt_removed"] is True
    assert not skill_path.exists()
    assert not prompt_path.exists()


def test_load_custom_skill_manifests_uses_cache_and_invalidates_on_change(monkeypatch, tmp_path) -> None:
    base_dir = tmp_path
    skills_dir = base_dir / "data" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(custom_skills, "BASE_DIR", base_dir)
    monkeypatch.setattr(custom_skills, "SKILLS_STORE_DIR", skills_dir)
    monkeypatch.setattr(custom_skills, "SKILL_TRIGGER_INDEX_FILE", skills_dir / "_trigger_index.json")
    custom_skills._invalidate_custom_skill_manifest_cache()

    skill_path = skills_dir / "ops-report.json"
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

    original_json_loads = custom_skills.json.loads
    call_count = {"value": 0}

    def _counting_loads(raw: str) -> object:
        call_count["value"] += 1
        return original_json_loads(raw)

    monkeypatch.setattr(custom_skills.json, "loads", _counting_loads)

    rows_first, errors_first = custom_skills._load_custom_skill_manifests()
    rows_second, errors_second = custom_skills._load_custom_skill_manifests()

    assert errors_first == []
    assert errors_second == []
    assert rows_first[0]["name"] == "Ops Report"
    assert rows_second[0]["name"] == "Ops Report"
    assert call_count["value"] == 1

    rows_first[0]["name"] = "Mutated in test"
    rows_third, _ = custom_skills._load_custom_skill_manifests()
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

    rows_after_change, _ = custom_skills._load_custom_skill_manifests()
    assert rows_after_change[0]["name"] == "Ops Report Updated"
    assert call_count["value"] == 2


def test_normalize_skill_steps_manifest_keeps_valid_condition() -> None:
    steps = custom_skills._normalize_skill_steps_manifest(
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
