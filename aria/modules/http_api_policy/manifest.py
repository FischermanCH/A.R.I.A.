"""Declarative metadata for HTTP/API policy."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "http_api_policy", "name": "HTTP API Policy", "parent": "http_api",
    "status": "import_boundary_active", "risk": "high_core",
    "lifecycle": "bootstrap_static",
    "description": "Owns HTTP/API request policy contracts without issuing a request or changing guardrail decisions.",
    "python": ["aria/modules/http_api_policy/policy.py"],
    "tests": ["tests/test_http_api_policy.py", "tests/test_http_guardrails.py", "tests/test_module_registry.py"],
    "depends_on": [
        "runtime_guardrails",
    ], "external_boundaries": [],
    "explicitly_excluded": ["http_policy_behavior_changes", "guardrail_changes", "http_or_webhook_execution", "network_or_secret_access"],
    "acceptance": ".codex/aria_acceptance/provider-planning-policy-import-rail-alpha730.json",
    "build_allowed": False, "runtime_access_allowed": False,
}
