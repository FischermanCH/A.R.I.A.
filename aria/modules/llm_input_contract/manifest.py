"""Declarative metadata for the bounded LLM input envelope."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "llm_input_contract",
    "name": "LLM Input Contract",
    "parent": "actions",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns redacted bounded router and answer-composer input envelopes without selecting routes, sources, actions, or answers.",
    "python": [
        "aria/modules/llm_input_contract/contract.py",
        "aria/modules/llm_input_contract/decision_schema.py",
    ],
    "tests": [
        "tests/test_llm_input_contract.py",
        "tests/test_turn_context_input_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "router_or_answer_decision",
        "prompt_or_output_schema_changes",
        "source_authority_or_target_scope_changes",
        "runtime_action_or_confirmation",
        "llm_network_or_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/turn-context-input-ownership-rail-alpha740.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Importing the module performs no I/O and no model call.",
    ],
}
