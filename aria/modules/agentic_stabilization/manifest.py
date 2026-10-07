"""Declarative metadata for agentic stabilization gate contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "agentic_stabilization",
    "name": "Agentic Stabilization",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns passive stabilization prompt matrix and answerability debug-line attachment without reinterpreting answer text or changing routing/source/runtime behavior.",
    "python": [
        "aria/modules/agentic_stabilization/gate.py",
    ],
    "tests": [
        "tests/test_agentic_stabilization_gate.py",
        "tests/test_agentic_contract_prompt_flow_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "agentic_contracts",
        "operator_trace_boundary",
        "action_runtime_debug",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "answer_text_rewrite_or_guarding",
        "routing_or_source_authority_behavior",
        "prompt_semantic_changes",
        "runtime_dispatch_or_execution",
        "guardrail_or_confirmation_behavior",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/agentic-contract-prompt-flow-import-rail-alpha736.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility path is retired; this module is the canonical owner.",
        "Stabilization remains limited to debug contract line derivation; final answer text is returned unchanged.",
    ],
}
