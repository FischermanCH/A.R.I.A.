"""Declarative metadata for passive pipeline data contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "pipeline_contracts",
    "name": "Pipeline Contracts",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns passive pipeline result data contracts without orchestrating or executing pipeline work.",
    "python": [
        "aria/modules/pipeline_contracts/result.py",
        "aria/modules/pipeline_contracts/capability_details.py",
        "aria/modules/pipeline_contracts/text.py",
        "aria/modules/pipeline_contracts/context_contracts.py",
        "aria/modules/pipeline_contracts/context_assembler.py",
    ],
    "tests": [
        "tests/test_kernel_contracts_gateway_support_import_boundary.py",
        "tests/test_pipeline.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "connections_catalog",
        "platform_primitives",
        "skill_contracts",
    ],
    "external_boundaries": [
        {
            "id": "kernel.pipeline_orchestration",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "pipeline_orchestration_or_dispatch",
        "routing_action_guardrail_or_confirmation_behavior",
        "runtime_execution",
        "persistence_qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/kernel-contracts-gateway-support-import-rail-alpha737.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility path is retired; this module is the canonical owner.",
        "Importing this module only defines dataclasses and performs no work.",
    ],
}
