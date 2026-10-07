from __future__ import annotations

from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_candidate_metadata
from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_scope
from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_identity_values


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


def test_stored_recipe_scope_appends_fallback_connection_kind_once() -> None:
    manifest = {
        "connections": ["ssh", "rss", "ssh"],
        "steps": [{"type": "ssh"}, {"type": "rss"}, {"type": "ssh"}],
    }

    assert stored_recipe_scope(manifest, fallback_connection_kind="imap") == {
        "connection_kinds": ["ssh", "rss", "imap"],
        "step_types": ["ssh", "rss"],
    }


def test_stored_recipe_candidate_metadata_uses_recipe_contract_defaults() -> None:
    manifest = {
        "id": "linux-health",
        "connections": ["ssh"],
        "steps": [{"type": "ssh_run"}],
    }


def test_stored_recipe_candidate_metadata_preserves_experience_promotion_projection() -> None:
    manifest = {
        "id": "linux-health",
        "connections": ["ssh"],
        "steps": [{"type": "ssh_run"}],
    }

    assert stored_recipe_candidate_metadata(
        manifest,
        experience={"experience_count": 3, "last_success_at": " 2026-10-01T12:00:00Z "},
    ) == {
        "candidate_role": "stored_recipe_candidate",
        "recipe_scope": {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        "recipe_origin": "stored_recipe_manifest",
        "experience_count": 3,
        "last_success_at": "2026-10-01T12:00:00Z",
        "promotion_state": "review_ready",
        "promotion_hint": "Multiple successful runs make this learned recipe ready for review.",
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


def test_stored_recipe_identity_values_ignore_legacy_router_keywords() -> None:
    manifest = {
        "id": "linux-health",
        "name": "Linux Health",
        "router_keywords": ["health check", "linux health", "linux-health", "ok"],
    }

    assert stored_recipe_identity_values(manifest) == [
        "linux health",
        "linux-health",
    ]
