"""Declarative metadata for Memory session compression."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "memory_session_compression",
    "name": "Memory Session Compression",
    "parent": "memory",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns caller-injected session-to-week and week-to-month rollup orchestration without opening Qdrant or user data on import.",
    "python": [
        "aria/modules/memory_session_compression/service.py",
    ],
    "tests": [
        "tests/test_memory_compression.py",
        "tests/test_memory_session_compression_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "memory",
    ],
    "external_boundaries": [
        {
            "id": "memory_skill.qdrant_collaborator",
            "category": "data_boundary",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "productive_qdrant_or_user_data_access",
        "startup_maintenance_execution",
        "compression_threshold_or_bucket_changes",
        "rollup_or_delete_semantic_changes",
        "embedding_llm_or_network_access",
    ],
    "acceptance": ".codex/aria_acceptance/memory-session-compression-ownership-rail-alpha740.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The service receives its MemorySkill collaborator from the caller and performs no work on import.",
    ],
}
