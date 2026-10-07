from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "native_web_llm",
    "name": "Native Web LLM",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns bounded semantic Web dispatch, provider-native search normalization and citation authority validation.",
    "python": [
        "aria/modules/native_web_llm/contracts.py",
        "aria/modules/native_web_llm/normalization.py",
        "aria/modules/native_web_llm/authority.py",
        "aria/modules/native_web_llm/dispatch.py",
        "aria/modules/native_web_llm/source_policy.py",
        "aria/modules/native_web_llm/evidence.py",
        "aria/modules/native_web_llm/gateway.py",
        "aria/modules/native_web_llm/pipeline_mixin.py",
        "aria/modules/native_web_llm/native_tools.py",
    ],
    "integration_points": ["aria/modules/native_web_llm/native_tools.py::native_tool_contributions"],
    "tests": [
        "tests/test_native_web_llm_runtime.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "configuration_foundations",
        "model_usage_observability",
        "qdrant_gateway",
    ],
    "external_boundaries": [
        {
            "id": "litellm.provider_native_web_gateway",
            "category": "library_service",
            "disposition": "durable",
        }
    ],
    "explicitly_excluded": [
        "main_llm_routing",
        "productive_provider_calls_in_tests",
        "personal_memory_storage",
    ],
    "acceptance": ".codex/aria_acceptance/native-web-gateway-alpha768.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
