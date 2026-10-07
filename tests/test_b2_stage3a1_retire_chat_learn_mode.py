from __future__ import annotations

from pathlib import Path

from aria.modules.chat_execution_composition.manifest import MODULE_MANIFEST as CHAT_EXECUTION_MANIFEST
from aria.modules.chat_surface.manifest import MODULE_MANIFEST as CHAT_SURFACE_MANIFEST


ROOT = Path(__file__).resolve().parents[1]


def test_chat_execution_has_no_live_chat_learn_mode_coupling() -> None:
    source = (ROOT / "aria/modules/chat_execution_composition/routes.py").read_text(encoding="utf-8")

    assert "chat_learn_mode" not in source
    assert "_chat_learn_response" not in source
    assert "suppress_auto_learning" not in source
    assert "append_chat_learn_observation" not in source
    assert "recipe_learning" not in CHAT_EXECUTION_MANIFEST["depends_on"]
    assert "learning_runtime" not in CHAT_EXECUTION_MANIFEST["depends_on"]


def test_chat_surface_keeps_stored_manifest_view_without_learn_mode_state_or_controls() -> None:
    route_source = (ROOT / "aria/modules/chat_surface/routes.py").read_text(encoding="utf-8")
    catalog_source = (ROOT / "aria/modules/chat_surface/catalog.py").read_text(encoding="utf-8")
    template_source = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")

    assert "stored_recipe_identity_values" in route_source
    assert "chat_learn_mode" not in route_source
    assert "chat_learn_active" not in route_source
    assert "chat_learn_event_count" not in route_source
    assert "chat_learn_active" not in catalog_source
    assert '"group": "learning"' not in catalog_source
    assert "chat_learn_active" not in template_source
    assert "chat_learn_event_count" not in template_source
    assert "isLearnModeCommand" not in template_source
    assert "recipe_runtime" in CHAT_SURFACE_MANIFEST["depends_on"]
    assert "recipe_learning" not in CHAT_SURFACE_MANIFEST["depends_on"]


def test_retired_recipe_learning_implementation_is_absent_after_stage3c2() -> None:
    assert not (ROOT / "aria/modules/recipe_learning").exists()


def test_excluded_memory_and_native_files_are_not_part_of_stage3a1_product_scope() -> None:
    acceptance = (ROOT / ".codex/aria_acceptance/b2-stage3a1-retire-chat-learn-mode-alpha934-review-build.json").read_text(
        encoding="utf-8"
    )

    assert '"/memories"' in acceptance
    assert '"Native B1 recurrence"' in acceptance
