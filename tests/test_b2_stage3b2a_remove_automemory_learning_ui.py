from __future__ import annotations

from pathlib import Path

from aria.modules.memory_admin_ui.manifest import MODULE_MANIFEST
from aria.modules.navigation_shell.navigation import NAV_NODES


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_personal_model_template_has_no_legacy_learning_or_auto_memory_controls() -> None:
    template = _source("aria/templates/memories_auto_memory.html")

    assert "personal_claims" in template
    assert "_personal_claim_item.html" in template
    assert "_memory_auto_section.html" not in template
    assert "memory_auto_synthesize_path" not in template
    assert "learning_points" not in template
    assert "learning_review_points" not in template
    assert "Learning-Inventar" not in template
    assert "Learning inventory" not in template
    assert "Jetzt synthetisieren" not in template
    assert "Synthesize now" not in template


def test_personal_model_route_collects_only_personal_claims() -> None:
    routes = _source("aria/modules/memory_admin_ui/routes.py")
    page = routes.split("async def memories_auto_memory_page(", 1)[1].split(
        '@app.post("/memories/auto-memory/delete-point")', 1
    )[0]

    assert "list_personal_claims" in page
    assert "list_learning_points_global" not in page
    assert "last_learning_retention_status" not in page
    assert "last_learning_synthesis_status" not in page
    assert "LearningSynthesizer" not in routes
    assert '@app.post("/memories/auto-memory/synthesize")' not in routes
    assert '@app.post("/memories/config/auto-save")' not in routes
    assert '@app.post("/config/memory/auto-save")' not in routes


def test_navigation_and_manifest_expose_personal_model_without_retired_routes() -> None:
    node = NAV_NODES["memory.auto"]

    assert node.title_fallback == "Personal model"
    assert "/memories/auto-memory/synthesize" not in MODULE_MANIFEST["routes"]
    assert "/memories/config/auto-save" not in MODULE_MANIFEST["routes"]
    assert "/memories/auto-memory/claim-action" in MODULE_MANIFEST["routes"]
    assert "/memories/auto-memory/correct-claim" in MODULE_MANIFEST["routes"]
    assert "/memories/auto-memory/delete-claim" in MODULE_MANIFEST["routes"]


def test_alpha937_keeps_protected_memory_owners_untouched() -> None:
    acceptance = _source(
        ".codex/aria_acceptance/b2-stage3b2a-remove-automemory-learning-ui-alpha937-review-build.json"
    )

    assert '"target_internal_version": "0.1.0-alpha937"' in acceptance
    assert '"public_version_must_remain": "0.1.0-alpha604"' in acceptance
    assert _source("aria/modules/memory_learning_bridge/skill.py")
    assert _source("aria/modules/configuration_foundations/config.py")
