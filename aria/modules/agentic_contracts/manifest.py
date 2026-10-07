"""Declarative metadata for agentic debug and evidence contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "agentic_contracts",
    "name": "Agentic Contracts",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns pure Routing-Debug line parsing and derived decision/evidence/answerability contracts without changing answer, routing, source, or runtime behavior.",
    "python": [
        "aria/modules/agentic_contracts/contracts.py",
    ],
    "tests": [
        "tests/test_agentic_stabilization_gate.py",
        "tests/test_agentic_contract_prompt_flow_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "actions",
        "action_runtime_debug",
    ],
    "external_boundaries": [
        {
            "id": "kernel.trace",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "routing_decision_behavior",
        "source_authority_behavior",
        "answer_text_generation",
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
        "Derived contracts continue to parse already-emitted debug lines only.",
    ],
}
