from __future__ import annotations

from aria.core.stored_recipe_manifest_view import stored_recipe_candidate_metadata
from aria.core.stored_recipe_manifest_view import stored_recipe_scope
from aria.core.stored_recipe_manifest_view import stored_recipe_trigger_values


def test_stored_recipe_scope_collects_connection_kinds_and_step_types() -> None:
    manifest = {
        "id": "linux-health",
        "connections": ["ssh", "ssh", "sftp"],
        "steps": [
            {"type": "ssh_run"},
            {"type": "ssh_run"},
            {"type": "chat_send"},
        ],
    }

    assert stored_recipe_scope(manifest) == {
        "connection_kinds": ["ssh", "sftp"],
        "step_types": ["ssh_run", "chat_send"],
    }


def test_stored_recipe_candidate_metadata_uses_recipe_contract_defaults() -> None:
    manifest = {
        "id": "linux-health",
        "connections": ["ssh"],
        "steps": [{"type": "ssh_run"}],
    }

    assert stored_recipe_candidate_metadata(manifest) == {
        "candidate_role": "stored_recipe_candidate",
        "recipe_scope": {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        "recipe_origin": "stored_recipe_manifest",
        "experience_count": 0,
        "last_success_at": "",
        "promotion_state": "",
        "promotion_hint": "",
    }


def test_stored_recipe_trigger_values_normalize_name_id_and_keywords() -> None:
    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "router_keywords": ["health check", "linux health", "linux-health", "ok"],
    }

    assert stored_recipe_trigger_values(manifest) == [
        "linux health",
        "linux-health",
        "health check",
    ]
