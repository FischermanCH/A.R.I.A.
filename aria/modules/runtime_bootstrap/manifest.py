"""Declarative metadata for main runtime construction and support wiring."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "runtime_bootstrap",
    "name": "Runtime Bootstrap",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns main runtime construction and support wiring without granting runtime execution or productive reload access.",
    "python": [
        "aria/modules/runtime_bootstrap/manager.py",
        "aria/modules/runtime_bootstrap/support_helpers.py",
        "aria/modules/runtime_bootstrap/memory_helpers.py",
    ],
    "tests": [
        "tests/test_runtime_manager.py",
        "tests/test_memories_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "capability_context",
        "configuration_foundations",
        "model_gateway_clients",
        "model_usage_observability",
        "pipeline_orchestrator",
        "platform_primitives",
        "qdrant_gateway",
        "security_storage",
        "system_diagnostics",
    ],
    "external_boundaries": [
        {
            "id": "threading",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "runtime_constructor_or_reload_behavior_changes",
        "pipeline_model_prompt_or_usage_meter_behavior_changes",
        "startup_diagnostic_behavior_changes",
        "memory_or_qdrant_behavior_changes",
        "productive_config_secret_model_qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/runtime-inbound-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The three historical aria.web modules are identity-preserving compatibility aliases.",
        "Tests must use constructor fakes, monkeypatches, synthetic settings, or tmp_path.",
    ],
}
