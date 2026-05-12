from __future__ import annotations

from pathlib import Path

import aria.core.learned_recipe_store as learned_store
from aria.core.learned_recipe_store_updates import record_successful_learned_recipe_execution


def test_record_successful_learned_recipe_execution_creates_new_store_entry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    stored = record_successful_learned_recipe_execution(
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        chosen_action="uptime && df -h / && free -h",
        summary="Worked well for Linux host checks.",
        recorded_at="2026-05-03T10:00:00Z",
    )

    assert stored is not None
    assert stored["recipe_id"] == "learned-ssh-health-check"
    assert stored["experience_count"] == 1
    assert stored["last_success_at"] == "2026-05-03T10:00:00Z"
    assert stored["promotion_state"] == "observed"


def test_record_successful_learned_recipe_execution_increments_existing_entry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    record_successful_learned_recipe_execution(
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        chosen_action="uptime",
        recorded_at="2026-05-03T10:00:00Z",
    )
    stored = record_successful_learned_recipe_execution(
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        chosen_action="uptime && df -h / && free -h",
        recorded_at="2026-05-03T11:00:00Z",
    )

    assert stored is not None
    assert stored["experience_count"] == 2
    assert stored["chosen_action"] == "uptime && df -h / && free -h"
    assert stored["last_success_at"] == "2026-05-03T11:00:00Z"


def test_record_successful_learned_recipe_execution_reaches_review_ready_threshold(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    for index in range(3):
        stored = record_successful_learned_recipe_execution(
            intent="health_check",
            connection_kind="ssh",
            capability="ssh_command",
            chosen_action="uptime",
            recorded_at=f"2026-05-03T1{index}:00:00Z",
        )

    assert stored is not None
    assert stored["experience_count"] == 3
    assert stored["promotion_state"] == "review_ready"


def test_record_successful_learned_recipe_execution_ignores_non_success_results(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    stored = record_successful_learned_recipe_execution(
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        chosen_action="uptime",
        execution_result="error",
    )

    assert stored is None
    assert learned_store.load_learned_recipe_store_entries() == []


def test_record_successful_learned_recipe_execution_preserves_admin_dismiss_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    learned_store.save_learned_recipe_store_entry(
        {
            "recipe_id": "learned-ssh-health-check",
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 5,
            "promotion_state": "observed",
            "promotion_hint": "admin:Dismissed from review for now; collect fresh evidence before revisiting.",
        }
    )

    stored = record_successful_learned_recipe_execution(
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        chosen_action="uptime && df -h /",
        recorded_at="2026-05-03T12:00:00Z",
    )

    assert stored is not None
    assert stored["experience_count"] == 6
    assert stored["promotion_state"] == "observed"
    assert stored["promotion_hint"] == "admin:Dismissed from review for now; collect fresh evidence before revisiting."
