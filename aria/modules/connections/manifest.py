"""Declarative metadata for connection profiles and admin surfaces."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections",
    "name": "Connections",
    "status": "domain_namespace_active",
    "lifecycle": "contract_only",
    "risk": "high",
    "description": "Owns connection catalog, profile metadata, admin surfaces, health checks, and semantic resolution boundaries without owning runtime execution.",
    "candidate_submodules": [
        "connections_catalog",
        "connections_profiles",
        "connections_health_cache",
        "connection_status_rows",
        "connections_ui_readonly",
        "connections_ui",
        "connections_mutations",
        "connections_runtime_status",
        "connections_provider_manifest",
        "connections_semantic",
        "connection_routing",
        "routing_hint_generation",
    ],
    "routes_prefixes": [
        "/connections",
        "/config/connections",
    ],
    "python": [],
    "templates": [],
    "tests": [
        "tests/test_connection_*.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "auth_ui",
        "config_ui",
        "navigation_shell",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "secret_material_access",
        "connection_runtime_execution",
        "ssh_execution",
        "http_api_execution",
        "rss_fetch_runtime",
        "profile_persistence_behavior",
        "live_health_probe_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-connections-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Existing route registration remains in aria/main.py and aria/web/* route modules.",
        "Connection profiles are metadata boundaries only here; no profile read/write behavior changes.",
        "Runtime execution belongs to action-specific modules and must stay behind confirmation/guardrails.",
        "Connection routing and metadata-hint generation have explicit registered submodule owners.",
        "Concrete connection templates are owned by connections_ui_readonly and provider UI modules.",
        "All previously broad connection_* Python claims are assigned to registered Connections submodules.",
        "Provider modules depend on the Connections base; injected mutation/probe consumers live in connections_mutations and connections_runtime_status.",
    ],
}
