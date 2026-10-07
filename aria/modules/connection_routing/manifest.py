"""Declarative metadata for bounded connection routing."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connection_routing",
    "name": "Connection Routing",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "parent": "connections",
    "description": "Owns connection-routing documents, bounded candidate validation, diagnostics, index administration, and the pipeline Qdrant bridge without owning source authority, Fleet expansion, confirmation, guardrails, or runtime execution.",
    "python": [
        "aria/modules/connection_routing/index.py",
        "aria/modules/connection_routing/resolver.py",
        "aria/modules/connection_routing/bounded_llm.py",
        "aria/modules/connection_routing/admin.py",
        "aria/modules/connection_routing/pipeline_bridge.py",
    ],
    "tests": [
        "tests/test_connection_routing_ownership_import_boundary.py",
        "tests/test_routing_admin.py",
        "tests/test_routing_index.py",
        "tests/test_routing_resolver.py",
        "tests/test_pipeline.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_planner_templates",
        "configuration_foundations",
        "connections_catalog",
        "connections_semantic",
        "execution_dry_run",
        "model_gateway_clients",
        "model_usage_observability",
        "qdrant_gateway",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "public_current_fact_or_source_authority_behavior",
        "meta_catalog_or_turn_routing_behavior",
        "target_or_fleet_scope_authority_changes",
        "confirmation_or_guardrail_behavior",
        "candidate_threshold_or_fallback_changes",
        "llm_prompt_or_call_count_changes",
        "qdrant_schema_or_productive_index_mutation",
        "runtime_execution",
        "productive_config_secret_or_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/connection-routing-ownership-rail-alpha741.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Five historical Core routing paths and the pipeline Qdrant helper path are identity-preserving compatibility aliases.",
        "The alpha741 rail uses synthetic settings and fake Qdrant, embedding, UsageMeter, and LLM clients only.",
        "This boundary is structural and does not address the deferred alpha740 personal-memory or latency finding.",
    ],
}
