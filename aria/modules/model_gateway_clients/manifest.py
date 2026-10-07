"""Declarative metadata for model gateway clients."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "model_gateway_clients",
    "name": "Model Gateway Clients",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "model_usage_observability",
    "description": "Owns lazy-loaded LLM and embedding gateway clients without creating clients or issuing provider requests.",
    "python": [
        "aria/modules/model_gateway_clients/llm.py",
        "aria/modules/model_gateway_clients/parameter_compat.py",
        "aria/modules/model_gateway_clients/embedding.py",
        "aria/modules/model_gateway_clients/native_tools.py",
    ],
    "tests": [
        "tests/test_kernel_contracts_gateway_support_import_boundary.py",
        "tests/test_llm_client.py",
        "tests/test_optional_temperature_model_compat.py",
        "tests/test_usage_meter.py",
        "tests/test_llm_audit.py",
        "tests/test_model_gateway_contract.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "configuration_foundations",
        "model_usage_observability",
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "litellm.lazy_provider_gateway",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "real_llm_embedding_or_http_requests",
        "prompt_routing_source_or_latency_behavior_changes",
        "productive_secret_log_prompt_or_user_data_access",
        "runtime_qdrant_connections_or_web_search",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/llm-tool-call-extraction-alpha826-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility paths are retired; this module is the canonical owner.",
        "Provider functions remain lazy-loaded and are monkeypatched in tests.",
    ],
}
