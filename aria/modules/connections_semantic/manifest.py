"""Declarative metadata for connection semantic resolution boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_semantic",
    "name": "Connections Semantic",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "connections",
    "description": "Owns descriptive boundaries for connection ref scopes, semantic connection candidates, LLM hint parsing, routing-decision record formatting, and target dossiers without owning routed action selection.",
    "python": [
        "aria/modules/connections_semantic/ref_scope.py",
        "aria/modules/connections_semantic/resolver.py",
        "aria/modules/connections_semantic/dossiers.py",
    ],
    "tests": [
        "tests/test_connection_ref_scope.py",
        "tests/test_connection_semantic_resolver.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_profiles",
        "action_contracts",
        "ssh",
        "http_api",
        "rss",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "routed_action_resolution_behavior",
        "routing_authority_behavior",
        "semantic_llm_selection_policy_changes",
        "pipeline_orchestration_behavior",
        "chat_pending_action_flow",
        "action_execution_behavior",
        "confirmation_or_guardrail_behavior",
        "source_authority_behavior",
        "profile_persistence_behavior",
        "live_runtime_access",
        "qdrant_or_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/connection-semantic-runtime-handlers-import-rail-alpha728.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This slice is high/core because pipeline and runtime connection consumers use these helpers.",
        "The ref-scope, semantic resolver, and dossier implementations are canonical under aria.modules.connections_semantic; their aria.core paths are compatibility aliases.",
        "No LLM, routing, confirmation, source-authority, or runtime behavior is changed by this manifest.",
    ],
}
