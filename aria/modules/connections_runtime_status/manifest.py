"""Declarative metadata for connection runtime status boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_runtime_status",
    "name": "Connections Runtime Status",
    "parent": "connections",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns connection status/probe implementation metadata and provider adapter diagnostics without executing probes or runtime actions.",
    "python": [
        "aria/modules/connections_runtime_status/runtime.py",
        "aria/modules/connections_runtime_status/inventory_source.py",
        "aria/modules/connections_runtime_status/native_tools.py",
    ],
    "tests": [
        "tests/test_connection_runtime.py",
        "tests/test_module_registry.py",
        "tests/test_module_registry_read_model.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_health_cache",
        "sftp",
        "configuration_foundations",
        "integration_support",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "integration_points": ["aria/modules/connections_runtime_status/native_tools.py::native_tool_contributions"],
    "explicitly_excluded": [
        "live_connection_probe_execution",
        "runtime_action_execution",
        "network_access",
        "secret_material_access",
        "provider_adapter_registration_changes",
        "status_row_behavior_changes",
        "health_store_mutation",
    ],
    "acceptance": ".codex/aria_acceptance/native-agent-connection-kind-alpha843-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "connection_status_rows remains the narrower function-level owner for passive row projection helpers.",
        "This import-boundary rail does not invoke a probe, register an adapter, or change provider status semantics.",
    ],
}
