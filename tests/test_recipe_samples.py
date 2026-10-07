from __future__ import annotations

import json
from pathlib import Path

import pytest

from aria.modules import module_route_path
import aria.modules.recipe_store.template_import as template_import
import aria.modules.recipes_ui.route_support as recipes_route_support


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

ADAPTIVE_RECIPE_FILES = {
    "ssh-disk-usage-all-hosts.json",
    "ssh-updates-check-all-hosts.json",
    "ssh-uptime-all-hosts.json",
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


def test_shipped_recipe_set_contains_only_adaptive_ssh_templates() -> None:
    rows = _sample_payloads(RECIPE_SAMPLE_DIR)

    assert {path.name for path, _payload in rows} == ADAPTIVE_RECIPE_FILES
    for path, payload in rows:
        ssh_steps = [step for step in payload["steps"] if step.get("type") == "ssh_run"]
        assert len(ssh_steps) == 1, path.name
        params = ssh_steps[0]["params"]
        assert params.get("connection_kind") == "ssh", path.name
        assert params.get("binding") == "all", path.name
        assert "connection_ref" not in params, path.name


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


def test_legacy_skill_sample_root_contains_no_shipped_templates() -> None:
    assert list(LEGACY_SAMPLE_DIR.glob("*.json")) == []


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

    assert {row["id"] for row in rows} == {
        "ssh-disk-usage-all-hosts", "ssh-updates-check-all-hosts", "ssh-uptime-all-hosts",
    }
    disk = next(row for row in rows if row["id"] == "ssh-disk-usage-all-hosts")
    assert disk["step_count"] == 3
    assert disk["step_types"] == ["ssh_run", "llm_transform", "chat_send"]
    assert disk["connections_label"] == "ssh"
    assert "trigger_count" not in disk
    assert disk["schedule_enabled"] is False
    assert disk["has_side_effect"] is False

    assert all(row["schedule_enabled"] is False for row in rows)
    assert all(row["connections"] == ["ssh"] for row in rows)
    assert all(row["has_side_effect"] is False for row in rows)


def test_import_sample_recipe_success_default_uses_registry_route_readpoint(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    sample_dir = tmp_path / "samples" / "recipes"
    recipes_dir = tmp_path / "data" / "recipes"
    sample_dir.mkdir(parents=True)
    recipes_dir.mkdir(parents=True)
    (sample_dir / "demo.json").write_text(
        json.dumps(
            {
                "id": "demo-template",
                "name": "Demo",
                "description": "Demo recipe.",
                "version": "1.0",
                "schema_version": "1",
                "category": "demo",
                "router_keywords": [],
                "connections": [],
                "steps": [{"id": "say", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )

    def tracking_module_route_path(module_id: str, route_path: str, **kwargs: object) -> str | None:
        calls.append((module_id, route_path))
        return module_route_path(module_id, route_path, **kwargs)

    monkeypatch.setattr(recipes_route_support, "module_route_path", tracking_module_route_path)
    monkeypatch.setattr(template_import, "SAMPLE_RECIPES_DIR", sample_dir)
    monkeypatch.setattr(template_import, "LEGACY_SAMPLE_RECIPES_DIR", tmp_path / "samples" / "skills")
    monkeypatch.setattr(template_import, "BASE_DIR", tmp_path)
    monkeypatch.setattr(template_import, "_save_stored_recipe_manifest", lambda raw: raw)

    url = recipes_route_support.import_sample_recipe_success_url(sample_file="demo.json", surface_path="", lang="en")

    assert url == "/recipes?saved=1&info=imported:demo-template"
    assert ("recipes_ui", "/recipes") in calls


def test_import_sample_recipe_success_default_fails_closed_without_owner(monkeypatch, tmp_path: Path) -> None:
    sample_dir = tmp_path / "samples" / "recipes"
    sample_dir.mkdir(parents=True)
    (sample_dir / "demo.json").write_text(json.dumps({"id": "demo"}), encoding="utf-8")

    monkeypatch.setattr(recipes_route_support, "module_route_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_import, "SAMPLE_RECIPES_DIR", sample_dir)
    monkeypatch.setattr(template_import, "LEGACY_SAMPLE_RECIPES_DIR", tmp_path / "samples" / "skills")
    monkeypatch.setattr(template_import, "_save_stored_recipe_manifest", lambda raw: raw)

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes"):
        recipes_route_support.import_sample_recipe_success_url(sample_file="demo.json", surface_path="", lang="en")
