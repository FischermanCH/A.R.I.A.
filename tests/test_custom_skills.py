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
