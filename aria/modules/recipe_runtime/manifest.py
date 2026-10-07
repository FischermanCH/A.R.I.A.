"""Declarative metadata for Recipe runtime composition boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "recipe_runtime",
    "name": "Recipe Runtime",
    "parent": "recipes",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns Recipe runtime contracts, adapters, step execution, and canonical result/status rendering without executing a Recipe or provider action.",
    "python": [
        "aria/modules/recipe_runtime/calendar.py",
        "aria/modules/recipe_runtime/contracts.py",
        "aria/modules/recipe_runtime/file_adapters.py",
        "aria/modules/recipe_runtime/http.py",
        "aria/modules/recipe_runtime/messaging.py",
        "aria/modules/recipe_runtime/pipeline_helpers.py",
        "aria/modules/recipe_runtime/result_view.py",
        "aria/modules/recipe_runtime/rss.py",
        "aria/modules/recipe_runtime/runtime.py",
        "aria/modules/recipe_runtime/status.py",
        "aria/modules/recipe_runtime/stored_manifest_view.py",
        "aria/modules/recipe_runtime/steps.py",
        "aria/modules/recipe_runtime/native_tools.py",
    ],
    "integration_points": ["aria/modules/recipe_runtime/native_tools.py::native_tool_contributions"],
    "tests": [
        "tests/test_recipe_compatibility_kernel_ownership_import_boundary.py",
        "tests/test_recipe_result_view.py",
        "tests/test_recipe_runtime.py",
        "tests/test_skill_runtime_rss.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "configuration_foundations",
        "documents",
        "http_api_policy",
        "memory",
        "platform_primitives",
        "recipe_store",
        "rss_digest",
        "runtime_guardrails",
        "skill_contracts",
    ],
    "external_boundaries": [
        {
            "id": "calendar",
            "category": "library_service",
            "disposition": "durable",
        },
        {
            "id": "messaging",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "recipe_execution",
        "ssh_http_rss_file_message_or_calendar_execution",
        "guardrail_or_confirmation_changes",
        "natural_language_recipe_routing",
        "learning_or_memory_writes",
        "qdrant_or_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/native-agent-history-and-connection-filter-alpha847-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Runtime composition, steps, provider adapters, contracts, and readmodels are canonical under aria.modules.recipe_runtime.",
        "Their aria.core names remain identity-preserving compatibility aliases.",
        "Production consumers import the canonical module paths.",
        "recipe_runtime_http.py and recipe_runtime_rss.py remain non-exclusive references in their provider manifests.",
        "No runtime object is instantiated and no Recipe or provider action is executed by this import migration.",
        "PipelineRecipeHelpersMixin is canonical here; the historical core path remains an identity-preserving alias.",
        "Stored Recipe manifest projections are canonical here and remain passive read models.",
    ],
}
