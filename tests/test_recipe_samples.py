from __future__ import annotations

import json
from pathlib import Path

import aria.web.recipes_template_import as template_import


REPO_ROOT = Path(__file__).resolve().parents[1]
RECIPE_SAMPLE_DIR = REPO_ROOT / "samples" / "recipes"
LEGACY_SAMPLE_DIR = REPO_ROOT / "samples" / "skills"

EXPECTED_KEYS = {
    "category",
    "description",
    "enabled_default",
    "id",
    "name",
    "router_keywords",
    "schedule",
    "schema_version",
    "steps",
    "ui",
    "version",
}

ALLOWED_STEP_TYPES = {
    "chat_send",
    "discord_send",
    "llm_transform",
    "rss_read",
    "sftp_read",
    "smb_read",
    "ssh_run",
}


def _sample_payloads(sample_dir: Path) -> list[tuple[Path, dict]]:
    files = sorted(sample_dir.glob("*.json"))
    assert files
    rows: list[tuple[Path, dict]] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), path.name
        rows.append((path, payload))
    return rows


def test_recipe_sample_manifests_are_valid_json_and_use_supported_step_types() -> None:
    for path, payload in _sample_payloads(RECIPE_SAMPLE_DIR):
        assert EXPECTED_KEYS.issubset(payload.keys()), path.name
        assert isinstance(payload["steps"], list) and payload["steps"], path.name
        for step in payload["steps"]:
            assert step["type"] in ALLOWED_STEP_TYPES, f"{path.name}: {step['type']}"


def test_recipe_samples_are_recipe_first_public_surface() -> None:
    for path, payload in _sample_payloads(RECIPE_SAMPLE_DIR):
        description = str(payload.get("description", ""))
        ui = payload.get("ui", {})
        assert isinstance(ui, dict), path.name
        assert ui.get("config_path") == "/recipes", path.name
        assert "/skills" not in json.dumps(payload, ensure_ascii=False), path.name
        assert "Skill" not in description and "skill" not in description, path.name


def test_legacy_skill_samples_stay_available_only_as_backcompat_reference() -> None:
    recipe_names = {path.name for path, _payload in _sample_payloads(RECIPE_SAMPLE_DIR)}
    legacy_names = {path.name for path, _payload in _sample_payloads(LEGACY_SAMPLE_DIR)}

    assert legacy_names == recipe_names


def test_sample_recipe_dir_prefers_recipe_samples_and_keeps_legacy_fallback(monkeypatch, tmp_path: Path) -> None:
    recipe_dir = tmp_path / "samples" / "recipes"
    legacy_dir = tmp_path / "samples" / "skills"
    legacy_dir.mkdir(parents=True)
    monkeypatch.setattr(template_import, "SAMPLE_RECIPES_DIR", recipe_dir)
    monkeypatch.setattr(template_import, "LEGACY_SAMPLE_RECIPES_DIR", legacy_dir)

    assert template_import.sample_recipe_dir() == legacy_dir

    recipe_dir.mkdir(parents=True)
    assert template_import.sample_recipe_dir() == recipe_dir


def test_sample_recipe_rows_expose_review_metadata() -> None:
    rows = template_import.build_sample_recipe_rows()

    disk = next(row for row in rows if row["id"] == "ssh-disk-usage-template")
    assert disk["step_count"] == 3
    assert disk["step_types"] == ["ssh_run", "llm_transform", "chat_send"]
    assert disk["connections_label"] == "ssh"
    assert disk["trigger_count"] == 4
    assert disk["schedule_enabled"] is False
    assert disk["has_side_effect"] is False

    briefing = next(row for row in rows if row["id"] == "rss-morning-briefing-to-discord-template")
    assert briefing["schedule_enabled"] is True
    assert briefing["schedule_cron"] == "0 7 * * *"
    assert briefing["connections"] == ["rss", "discord"]
    assert briefing["has_side_effect"] is True
