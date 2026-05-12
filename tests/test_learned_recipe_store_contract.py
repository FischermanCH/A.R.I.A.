from __future__ import annotations

from aria.core.learned_recipe_store_contract import build_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import learned_recipe_store_list_row
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry


def test_normalize_learned_recipe_store_entry_builds_store_ready_shape() -> None:
    entry = normalize_learned_recipe_store_entry(
        {
            "intent": "health_check",
            "connection_kind": "SSH",
            "connection_ref": "srv-a",
            "capability": "SSH_COMMAND",
            "chosen_action": "uptime && df -h / && free -h",
            "policy_result": "ALLOW",
            "execution_result": "SUCCESS",
            "user_feedback": "GOOD",
            "user_message": "wie geht es meinem dns server",
            "experience_summary": "Worked well for repeated Linux health checks.",
            "experience_count": 7,
            "last_success_at": "2026-05-01T10:15:00Z",
            "promotion_state": "eligible",
            "promotion_hint": "Observed repeated successful Linux health checks.",
        }
    )

    assert entry == {
        "recipe_id": "learned-ssh-health-check",
        "stored_recipe_id": "",
        "title": "Learned recipe: health check",
        "summary": "Worked well for repeated Linux health checks.",
        "preview": "SSH command: uptime && df -h / && free -h",
        "inputs": {"command": "uptime && df -h / && free -h"},
        "router_keywords": ["health check", "ssh command"],
        "recipe_scope": {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        "intent": "health_check",
        "connection_kind": "ssh",
        "connection_ref": "srv-a",
        "capability": "ssh_command",
        "chosen_action": "uptime && df -h / && free -h",
        "policy_result": "allow",
        "execution_result": "success",
        "user_feedback": "good",
        "user_message": "wie geht es meinem dns server",
        "experience_summary": "Worked well for repeated Linux health checks.",
        "experience_count": 7,
        "last_success_at": "2026-05-01T10:15:00Z",
        "promotion_state": "eligible",
        "promotion_hint": "Observed repeated successful Linux health checks.",
    }


def test_build_learned_recipe_store_entry_applies_consistent_defaults() -> None:
    entry = build_learned_recipe_store_entry(
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        chosen_action="uptime",
        summary="Simple uptime check.",
        experience={"experience_count": 2},
    )

    assert entry["recipe_id"] == "learned-ssh-health-check"
    assert entry["stored_recipe_id"] == ""
    assert entry["title"] == "Learned recipe: health check"
    assert entry["summary"] == "Simple uptime check."
    assert entry["experience_count"] == 2
    assert entry["promotion_state"] == "observed"
    assert entry["promotion_hint"] == "Observed successful runs; collect more evidence before review."


def test_learned_recipe_store_list_row_returns_admin_friendly_subset() -> None:
    row = learned_recipe_store_list_row(
        {
            "intent": "health_check",
            "connection_kind": "ssh",
            "capability": "ssh_command",
            "chosen_action": "uptime",
            "experience_count": 3,
            "promotion_state": "review_ready",
            "promotion_hint": "Seen three successful runs.",
        }
    )

    assert row == {
        "recipe_id": "learned-ssh-health-check",
        "title": "Learned recipe: health check",
        "intent": "health_check",
        "connection_kind": "ssh",
        "capability": "ssh_command",
        "experience_count": 3,
        "last_success_at": "",
        "promotion_state": "review_ready",
        "promotion_hint": "Seen three successful runs.",
        "summary": "Recipe candidate derived from successful executions.",
    }
