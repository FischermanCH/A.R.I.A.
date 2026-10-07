"""Declarative metadata for model-usage observability."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "model_usage_observability",
    "name": "Model Usage Observability",
    "parent": "stats_ui",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns pricing, token tracking, usage metering, and redacted LLM audit implementations without reading or writing productive logs.",
    "python": [
        "aria/modules/model_usage_observability/pricing_catalog.py",
        "aria/modules/model_usage_observability/token_tracker.py",
        "aria/modules/model_usage_observability/usage_meter.py",
        "aria/modules/model_usage_observability/llm_audit.py",
    ],
    "tests": [
        "tests/test_pricing_catalog.py",
        "tests/test_token_tracker.py",
        "tests/test_usage_meter.py",
        "tests/test_llm_audit.py",
        "tests/test_stats_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "configuration_foundations",
        "recipe_runtime",
    ],
    "external_boundaries": [
        {
            "id": "filesystem.runtime_logs",
            "category": "data_boundary",
            "disposition": "durable",
        },
        {
            "id": "httpx",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "live_pricing_http_refresh",
        "real_llm_or_embedding_calls",
        "productive_token_or_audit_log_access",
        "productive_retention_or_stats_mutation",
        "routing_runtime_qdrant_connections_or_web_search",
    ],
    "acceptance": ".codex/aria_acceptance/model-usage-observability-import-rail-alpha732.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "Tests use tmp_path, fake settings, fake HTTP, and monkeypatched trackers only.",
    ],
}
