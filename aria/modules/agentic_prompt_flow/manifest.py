"""Declarative metadata for agentic prompt flow contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "agentic_prompt_flow",
    "name": "Agentic Prompt Flow",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns pure agentic phase, boundary, and debug-line contracts without changing routing, policy, guardrails, or runtime execution.",
    "python": [
        "aria/modules/agentic_prompt_flow/prompt_flow.py",
    ],
    "tests": [
        "tests/test_agentic_contract_prompt_flow_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "actions",
    ],
    "external_boundaries": [
        {
            "id": "kernel.trace",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "prompt_text_semantics",
        "routing_or_source_authority_behavior",
        "policy_or_guardrail_behavior",
        "confirmation_behavior",
        "runtime_dispatch_or_execution",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/agentic-contract-prompt-flow-import-rail-alpha736.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility path is retired; this module is the canonical owner.",
        "This module only describes existing agentic phase and debug boundary projection behavior.",
    ],
}
