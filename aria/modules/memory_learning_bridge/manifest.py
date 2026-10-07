"""Declarative metadata for direct Memory-to-Learning bridge code."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "memory_learning_bridge",
    "name": "Memory Learning Bridge",
    "parent": "memory",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns the retained Core MemorySkill runtime without Legacy Learning imports, retention, synthesis or inventory behavior.",
    "python": [
        "aria/modules/memory_learning_bridge/skill.py",
    ],
    "tests": [
        "tests/test_memory.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "system_diagnostics",
        "qdrant_gateway",
        "skill_contracts",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "memory_or_qdrant_read_write",
        "legacy_learning_behavior",
        "runtime_or_pipeline_wiring_changes",
    ],
    "acceptance": ".codex/aria_acceptance/memory-kernel-ownership-rail-alpha742.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Legacy Learning imports and methods were stripped in B2 Stage 3b-2b.",
        "The retained generic admin-query implementation is owned by memory.",
    ],
}
