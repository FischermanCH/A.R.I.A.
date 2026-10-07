"""Declarative metadata for shared skill result and execution contracts."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "skill_contracts",
    "name": "Skill Contracts",
    "parent": "platform_primitives",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns the pure BaseSkill and SkillResult contracts without constructing or executing any skill.",
    "python": [
        "aria/modules/skill_contracts/contracts.py",
    ],
    "tests": [
        "tests/test_skill_contract_owner_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [],
    "explicitly_excluded": [
        "skill_construction_or_registration",
        "memory_qdrant_or_websearch_execution",
        "routing_source_authority_or_answer_behavior",
        "runtime_or_pipeline_activation",
    ],
    "acceptance": ".codex/aria_acceptance/skill-contract-owner-evacuation-rail-alpha750.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The contracts are pure types and string truncation only.",
        "The historical aria.skills.base path remains an exact lazy identity alias.",
    ],
}
