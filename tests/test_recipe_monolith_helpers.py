import json
from types import SimpleNamespace

from fastapi.responses import JSONResponse, Response

from aria.core import recipe_manifests
from aria.core.recipe_runtime_status import build_recipe_status_text
from aria.web.recipes_manifest_actions import delete_stored_recipe_and_config
from aria.web.recipes_manifest_actions import stored_recipe_export_response


def test_build_recipe_status_text_groups_core_and_custom_recipes() -> None:
    settings = SimpleNamespace(
        memory=SimpleNamespace(enabled=True),
        connections=SimpleNamespace(searxng={"main": {}}),
    )

    text = build_recipe_status_text(
        settings,
        [
            {
                "id": "dns-health",
                "name": "DNS Health",
                "enabled": False,
                "description": "Checks DNS health.",
                "connections": ["ssh/pihole1"],
            }
        ],
        auto_memory_enabled=True,
        language="en",
    )

    assert "Recipes (Runtime status):" in text
    assert "[Core] Memory" in text
    assert "[Core] Auto-Memory" in text
    assert "[Core] Web Search" in text
    assert "[Custom] DNS Health" in text
    assert "Connections: ssh/pihole1" in text


def test_recipes_manifest_actions_delete_manifest_and_config(monkeypatch, tmp_path) -> None:
    recipes_dir = tmp_path / "data" / "recipes"
    prompts_dir = tmp_path / "prompts" / "recipes"
    recipes_dir.mkdir(parents=True)
    prompts_dir.mkdir(parents=True)
    monkeypatch.setattr(recipe_manifests, "BASE_DIR", tmp_path)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    monkeypatch.setattr(recipe_manifests, "SKILL_TRIGGER_INDEX_FILE", recipes_dir / "_trigger_index.json")

    (recipes_dir / "dns-health.json").write_text(
        json.dumps(
            {
                "id": "dns-health",
                "name": "DNS Health",
                "prompt_file": "prompts/recipes/dns-health.md",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"chat_message": "ok"}}],
            }
        ),
        encoding="utf-8",
    )
    (prompts_dir / "dns-health.md").write_text("prompt", encoding="utf-8")
    raw_config = {"skills": {"custom": {"dns-health": {"enabled": True}}}}
    writes: list[dict] = []
    reloaded = {"value": False}

    result = delete_stored_recipe_and_config(
        "dns-health",
        read_raw_config=lambda: raw_config,
        write_raw_config=lambda data: writes.append(data),
        reload_runtime=lambda: reloaded.update(value=True),
    )

    assert result["id"] == "dns-health"
    assert not (recipes_dir / "dns-health.json").exists()
    assert "dns-health" not in writes[-1]["skills"]["custom"]
    assert reloaded["value"] is True


def test_stored_recipe_export_response_returns_attachment(monkeypatch, tmp_path) -> None:
    recipes_dir = tmp_path / "data" / "recipes"
    recipes_dir.mkdir(parents=True)
    monkeypatch.setattr(recipe_manifests, "SKILLS_STORE_DIR", recipes_dir)
    (recipes_dir / "dns-health.json").write_text('{"id":"dns-health"}', encoding="utf-8")

    response = stored_recipe_export_response("dns-health")

    assert isinstance(response, Response)
    assert not isinstance(response, JSONResponse)
    assert response.media_type == "application/json"
    assert response.headers["Content-Disposition"] == 'attachment; filename="dns-health.json"'
    assert response.body == b'{"id":"dns-health"}'
