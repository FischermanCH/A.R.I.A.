"""Declarative metadata for runtime guardrail evaluation."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "runtime_guardrails",
    "name": "Runtime Guardrails",
    "parent": "actions",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns existing guardrail catalog, profile normalization, connection scoping, and local allow/deny evaluation without owning confirmation, policy, config persistence, or runtime execution.",
    "python": [
        "aria/modules/runtime_guardrails/guardrails.py",
    ],
    "tests": [
        "tests/test_guardrails.py",
        "tests/test_guardrail_drafts.py",
        "tests/test_http_guardrails.py",
        "tests/test_file_guardrails.py",
        "tests/test_runtime_memory_kernel_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [],
    "explicitly_excluded": [
        "guardrail_catalog_profile_or_evaluation_changes",
        "confirmation_or_policy_changes",
        "config_persistence_or_mutation",
        "runtime_execution_or_connection_access",
    ],
    "acceptance": ".codex/aria_acceptance/runtime-kernel-boundaries-ownership-rail-alpha742.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": ["The historical aria.core path is an identity-preserving compatibility alias."],
}
