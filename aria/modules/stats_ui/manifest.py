"""Declarative metadata for the stats UI module."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "stats_ui",
    "name": "Stats UI",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_needs_proof",
    "description": "Owns stats/admin dashboard metadata, pricing/health summaries, and the passive module-registry operator projection.",
    "routes_prefixes": [
        "/stats",
        "/activities",
    ],
    "routes": [
        "/stats",
        "/activities",
        "/stats/reset",
        "/stats/pricing/refresh",
        "/stats/pricing/alias",
        "/stats/pricing/alias/delete",
        "/stats/pricing/manual",
        "/stats/pricing/manual/delete",
    ],
    "python": [
        "aria/modules/stats_ui/routes.py",
        "aria/modules/stats_ui/activities.py",
        "aria/modules/stats_ui/native_tools.py",
    ],
    "integration_points": ["aria/modules/stats_ui/native_tools.py::native_tool_contributions"],
    "templates": [
        "stats.html",
        "activities.html",
        "_stats_pricing_panel.html",
    ],
    "tests": [
        "tests/test_stats_routes.py",
    ],
    "depends_on": [
        "auth_policy",
        "configuration_foundations",
        "connection_routing",
        "connections_catalog",
        "connections_runtime_status",
        "integration_support",
        "model_usage_observability",
        "navigation_shell",
        "pipeline_orchestrator",
        "platform_primitives",
        "qdrant_gateway",
        "release_update",
        "runtime_diagnostics",
        "system_diagnostics",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
        {
            "id": "module_registry.read_model",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "qdrant_runtime_access",
        "connection_mutation",
        "pricing_refresh_behavior",
        "release_update_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/native-agent-admin-diagnostics-alpha846-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Stats and activities route implementations are canonical in aria.modules.stats_ui; historical aria.web paths are identity aliases.",
        "Module registry health is a passive structural projection only and does not claim per-module runtime health.",
    ],
}
