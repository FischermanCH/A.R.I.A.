"""Declarative metadata for pending routed action chat boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_pending_chat_boundary",
    "name": "Action Pending Chat Boundary",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "actions",
    "description": "Owns descriptive boundaries for routed action pending cookies, confirmation-token chat handoff, missing-input continuation checks, pending action state helpers, and chat response mapping without owning confirmation ledger semantics or runtime action execution.",
    "routes": [],
    "python": [
        "aria/modules/action_pending_chat_boundary/flows.py",
    ],
    "tests": [
        "tests/test_chat_tooling.py",
        "tests/test_pipeline.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_confirmation",
        "action_contracts",
        "connections_profiles",
        "connections_semantic",
        "memory",
        "ssh",
        "http_api",
        "rss",
        "chat_admin_composition",
        "pipeline_pending_action_contracts",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/pipeline_orchestrator/pipeline.py::execute_pending_routed_action",
        "aria/modules/pipeline_orchestrator/pipeline.py::continue_pending_routed_action_input",
        "aria/modules/pipeline_orchestrator/pipeline.py::arbitrate_pending_routed_action_input",
    ],
    "explicitly_excluded": [
        "action_confirmation_ledger_semantics",
        "pending_cookie_encoding_changes",
        "token_claim_or_replay_behavior",
        "runtime_action_execution",
        "memory_forget_execution_behavior",
        "connection_alias_persistence_behavior",
        "chat_turn_arbitration_behavior",
        "routing_authority_behavior",
        "guardrail_policy_behavior",
        "source_authority_behavior",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/chat-execution-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "flows.py also contains safe-fix, memory-forget, and connection-alias followups; their behavior remains explicitly excluded.",
        "ActionConfirmationLedger remains a separate action_confirmation boundary.",
        "Pipeline still owns pending action execution/continuation behavior until a later E2E-accepted wiring slice replaces one old responsibility.",
    ],
}
