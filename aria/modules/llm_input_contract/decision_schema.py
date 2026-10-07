"""Passive output-schema metadata retained by the LLM input envelope."""

from __future__ import annotations

from typing import Any


TURN_DECISION_CONTRACT = "turn_decision_v3"
TURN_DECISION_OUTPUT_PROFILE = "aria_turn_router_output_v1"


def turn_decision_output_schema() -> dict[str, Any]:
    return {
        "profile": TURN_DECISION_OUTPUT_PROFILE,
        "decision_contract": {
            "name": TURN_DECISION_CONTRACT,
            "decision_kind": "answer|context|action|clarify",
            "contract": {"mode": "answer|action|clarify"},
        },
        "action_name": "zero or one name from actions[name]",
        "action_input_phase": "do not return action_inputs; runtime requests selected schema separately",
        "personal_context_resolution": (
            "{status:not_applicable|matched|complete_no_hit|inconclusive|independent_context,reason}; required with capsule"
        ),
        "id_sources": {
            "surface_ids": "surfaces[id]",
            "action_names": "actions[name]",
            "catalog_ids": "meta_catalog[catalog_id]|surfaces[catalog_id]",
            "connection_kinds": "connection_kinds[]",
            "web_search_profile_refs": "web_search_profiles[ref]",
            "learning_hint_ids": "reviewed_learning_hints[hint_id]",
            "personal_claim_ids": "personal_context_capsule.claims[claim_id]",
        },
    }
