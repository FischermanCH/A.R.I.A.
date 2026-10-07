"""Declarative metadata for the RSS runtime adapter."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "rss_runtime", "name": "RSS Runtime", "parent": "rss",
    "status": "import_boundary_active", "risk": "high_core",
    "lifecycle": "bootstrap_static",
    "description": "Owns the RSS execution boundary and its exact-profile read-only native tool contribution.",
    "python": ["aria/modules/rss_runtime/agentic_execution.py", "aria/modules/rss_runtime/native_tools.py"],
    "integration_points": ["aria/modules/rss_runtime/native_tools.py::native_tool_contributions"],
    "tests": ["tests/test_agentic_execution.py", "tests/test_skill_runtime_rss.py", "tests/test_module_registry.py"],
    "depends_on": [
        "action_contracts",
        "connections_catalog",
        "runtime_execution_registry",
    ],
    "external_boundaries": [
        {
            "id": "runtime_action_execution_boundary",
            "category": "runtime_callback",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": ["write_or_mutating_feed_operations", "routing_or_confirmation_changes"],
    "acceptance": ".codex/aria_acceptance/native-agent-history-and-connection-filter-alpha847-review-build.json",
    "build_allowed": False, "runtime_access_allowed": False,
    "notes": ["The agentic handler is canonical in this module and its aria.core path is a compatibility alias. Import remains passive; the native binding calls the existing RecipeRuntime RSS adapter only after an authenticated turn selects an exact configured profile."],
}
