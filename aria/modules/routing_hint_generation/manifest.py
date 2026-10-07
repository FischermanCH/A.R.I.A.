"""Declarative metadata for routing metadata hint generation."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "routing_hint_generation",
    "name": "Routing Hint Generation",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "connections",
    "description": "Owns language-aware parsing and validation of admin routing metadata suggestions without granting those hints runtime route authority.",
    "python": [
        "aria/modules/routing_hint_generation/hints.py",
    ],
    "tests": [
        "tests/test_connection_routing_ownership_import_boundary.py",
        "tests/test_config_routes.py",
        "tests/test_recipes_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "recipe_store",
    ],
    "external_boundaries": [
        {
            "id": "admin_llm_calls",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "runtime_route_authority",
        "connection_profile_mutation",
        "llm_prompt_or_call_count_changes",
        "runtime_execution",
        "productive_config_secret_or_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/connection-routing-ownership-rail-alpha741.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The historical Core routing-hints path is an identity-preserving compatibility alias.",
        "Generated hints remain suggestions validated by existing contracts and do not become runtime authority.",
    ],
}
