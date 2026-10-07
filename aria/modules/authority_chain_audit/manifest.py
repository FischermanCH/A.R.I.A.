"""Declarative metadata for static authority chain audit contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "authority_chain_audit",
    "name": "Authority Chain Audit",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "parent": "actions",
    "description": "Owns static audit metadata for retired authority boundaries without becoming a runtime dependency or changing routing/source decisions.",
    "python": [
        "aria/modules/authority_chain_audit/audit.py",
    ],
    "tests": [
        "tests/test_authority_chain_audit.py",
        "tests/test_authority_chain_audit_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "actions",
        "agentic_contracts",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "runtime_dependency",
        "routing_decision_behavior",
        "websearch_source_target_behavior",
        "source_authority_behavior",
        "latency_behavior",
        "guardrail_or_confirmation_behavior",
        "qdrant_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/authority-chain-audit-import-rail-alpha736.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The private Core compatibility path is retired; this module is the canonical owner.",
        "Audit marker paths intentionally keep historical source references; they do not describe the module file location.",
    ],
}
