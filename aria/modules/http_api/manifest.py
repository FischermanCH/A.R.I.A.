"""Declarative metadata for HTTP/API action policy and execution boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "http_api",
    "name": "HTTP API",
    "status": "domain_namespace_active",
    "lifecycle": "contract_only",
    "risk": "high",
    "description": "Owns HTTP/API policy, agentic resolution metadata, connection template surface, and result summaries without issuing HTTP requests.",
    "candidate_submodules": [
        "http_api_policy",
        "http_api_runtime",
        "http_api_admin_ui",
    ],
    "routes_prefixes": [],
    "routes": [],
    "python": [],
    "templates": [],
    "tests": [
        "tests/test_http_api_policy.py",
        "tests/test_http_guardrails.py",
        "tests/test_execution_dry_run.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "runtime_guardrails",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "http_request_execution",
        "webhook_execution",
        "secret_material_access",
        "http_policy_behavior",
        "confirmation_semantics",
        "recipe_http_runtime_behavior",
        "external_network_access",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-http-api-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This module is a boundary label only; no outbound HTTP behavior changes are included.",
        "Policy, resolution, recipe-runtime, result-summary, and admin UI claims are delegated to narrow modules.",
        "HTTP/API action behavior needs separate guardrail and confirmation acceptance.",
    ],
}
