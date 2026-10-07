"""Declarative metadata for recent capability-context storage."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "capability_context",
    "name": "Capability Context",
    "parent": "chat_surface",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns the local recent capability-context JSON store contract without deciding relevance, routing, execution, or memory behavior.",
    "python": [
        "aria/modules/capability_context/store.py",
    ],
    "tests": [
        "tests/test_capability_context_store.py",
        "tests/test_runtime_manager.py",
        "tests/test_pipeline.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "recent_context_relevance_decision",
        "routing_or_action_selection",
        "runtime_execution",
        "connection_probe_or_secret_access",
        "memory_or_qdrant_access",
        "productive_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/chat-context-capability-context-import-rail-alpha735.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Canonical implementation lives under aria.modules.capability_context.",
        "The aria.core path remains an identity-preserving compatibility alias.",
        "Tests exercise only caller-supplied temporary JSON paths.",
    ],
}
