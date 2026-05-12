from __future__ import annotations

from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_id
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_inputs
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_metadata
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_preview
from aria.core.learned_recipe_candidate_view import learned_recipe_scope
from aria.core.learned_recipe_candidate_view import learned_recipe_trigger_values


def test_learned_recipe_scope_and_metadata_normalize_experience_record() -> None:
    record = {
        "intent": "health_check",
        "connection_kind": "ssh",
        "capability": "ssh_command",
        "experience_count": 7,
        "last_success_at": "2026-05-01T10:15:00Z",
        "promotion_state": "eligible",
        "promotion_hint": "Observed repeated successful Linux health checks.",
    }

    assert learned_recipe_scope(record) == {
        "connection_kinds": ["ssh"],
        "step_types": ["ssh_run"],
    }
    assert learned_recipe_candidate_metadata(record) == {
        "candidate_role": "learned_recipe_candidate",
        "recipe_scope": {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        "recipe_origin": "learned_experience_store",
        "experience_count": 7,
        "last_success_at": "2026-05-01T10:15:00Z",
        "promotion_state": "eligible",
        "promotion_hint": "Observed repeated successful Linux health checks.",
    }


def test_learned_recipe_candidate_helpers_build_preview_inputs_and_keywords() -> None:
    record = {
        "intent": "health_check",
        "connection_kind": "ssh",
        "capability": "ssh_command",
        "chosen_action": "uptime && df -h / && free -h",
        "router_keywords": ["linux health", "server health"],
    }

    assert learned_recipe_candidate_id(record) == "learned-ssh-health-check"
    assert learned_recipe_candidate_preview(record, language="de", localized_text=lambda _l, *, de, en: de) == "SSH-Befehl: uptime && df -h / && free -h"
    assert learned_recipe_candidate_inputs(record) == {"command": "uptime && df -h / && free -h"}
    assert learned_recipe_trigger_values(record) == [
        "health check",
        "ssh command",
        "linux health",
        "server health",
    ]
