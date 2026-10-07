"""Declarative metadata for connection provider contract projections."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "connections_provider_manifest",
    "name": "Connections Provider Manifest",
    "parent": "connections",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns read-only provider capability and runtime-adapter status projections without registering or executing adapters.",
    "python": [
        "aria/modules/connections_provider_manifest/projection.py",
    ],
    "tests": [
        "tests/test_connection_provider_manifest.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "connections_catalog",
        "runtime_execution_registry",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "runtime_adapter_registration",
        "runtime_action_execution",
        "capability_contract_changes",
        "guardrail_or_confirmation_changes",
        "network_or_secret_access",
    ],
    "acceptance": ".codex/aria_acceptance/connections-provider-import-train-alpha727.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The existing code projects action contracts and adapter registration status read-only.",
        "This manifest does not generate provider capabilities or alter runtime registry order.",
    ],
}
