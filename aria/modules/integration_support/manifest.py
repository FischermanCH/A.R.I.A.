"""Declarative metadata for integration support helpers."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "integration_support",
    "name": "Integration Support",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "connections",
    "description": "Owns error interpretation, endpoint derivation, and provider error normalization without opening integrations.",
    "python": [
        "aria/modules/integration_support/error_interpreter.py",
        "aria/modules/integration_support/runtime_endpoint.py",
        "aria/modules/integration_support/google_calendar.py",
    ],
    "tests": [
        "tests/test_kernel_contracts_gateway_support_import_boundary.py",
        "tests/test_error_interpreter.py",
        "tests/test_runtime_endpoint.py",
        "tests/test_connection_runtime.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "yaml",
            "category": "library_service",
            "disposition": "durable",
        },
        {
            "id": "python.network_error_types",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "network_http_socket_or_connection_execution",
        "cookie_auth_or_proxy_policy_changes",
        "productive_config_secret_or_user_data_access",
        "runtime_dispatch_or_execution",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/kernel-contracts-gateway-support-import-rail-alpha737.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility paths are retired; this module is the canonical owner.",
        "Tests use tmp_path, synthetic requests, and synthetic exceptions only.",
    ],
}
