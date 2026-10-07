"""Declarative metadata for memory, Qdrant, and recall boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "memory",
    "name": "Memory",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns personal-memory contracts, neutral assist, recall contracts/source projection, and memory UI metadata without accessing user memory stores.",
    "candidate_submodules": [
        "personal_memory",
        "memory_recall",
        "memory_export",
        "qdrant_storage",
        "memory_admin_ui",
        "document_memory",
        "memory_learning_bridge",
        "memory_session_compression",
    ],
    "routes_prefixes": [
        "/memories",
        "/config/memory",
    ],
    "python": [
        "aria/modules/memory/assist.py",
        "aria/modules/memory/admin_query.py",
        "aria/modules/memory/personal.py",
        "aria/modules/memory/personal_claim_source.py",
        "aria/modules/memory/native_tools.py",
        "aria/modules/memory/recall_sources.py",
        "aria/modules/memory/recall_contract.py",
    ],
    "templates": [
        "_memory_*.html",
        "memories_*.html",
    ],
    "tests": [
        "tests/test_memory*.py",
        "tests/test_personal_memory.py",
        "tests/test_qdrant_*.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "configuration_foundations",
        "platform_primitives",
        "qdrant_gateway",
        "system_diagnostics",
        "chat_history_storage",
    ],
    "external_boundaries": [],
    "integration_points": ["aria/modules/memory/native_tools.py::native_tool_contributions"],
    "explicitly_excluded": [
        "qdrant_runtime_access",
        "qdrant_collection_mutation",
        "user_memory_read",
        "user_memory_write",
        "memory_export_submodule",
        "memory_compression_behavior",
        "recall_ranking_behavior",
        "auto_memory_behavior",
        "startup_memory_maintenance",
    ],
    "acceptance": ".codex/aria_acceptance/native-writes-memory-forget-notes-update-alpha851-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Personal, assist, and recall-source implementations are canonical here; historical aria.core paths are identity aliases.",
        "Qdrant and user memory access are explicitly forbidden in this slice.",
        "The generic Memory browser query facade is canonical under aria.modules.memory.",
        "The concrete config_memory.html template is owned by memory_admin_ui.",
        "Auto-Memory belongs to learning; document-memory files belong to document_memory; direct Learning imports belong to memory_learning_bridge.",
        "The pure recall parameter contract is canonical under aria.modules.memory; its aria.core path is a compatibility alias.",
        "Qdrant client construction is owned by qdrant_gateway.",
    ],
}
