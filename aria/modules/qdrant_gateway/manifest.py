"""Declarative metadata for Qdrant client construction."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "qdrant_gateway",
    "name": "Qdrant Gateway",
    "parent": "memory",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns Qdrant URL privacy classification and AsyncQdrantClient construction without making requests, creating collections, or accessing user data.",
    "python": [
        "aria/modules/qdrant_gateway/client.py",
    ],
    "tests": [
        "tests/test_memory.py",
        "tests/test_runtime_diagnostics.py",
        "tests/test_runtime_memory_kernel_ownership_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [
        {
            "id": "qdrant_client.async_client",
            "category": "data_boundary",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "qdrant_request_collection_schema_index_or_payload_access",
        "url_api_key_timeout_or_warning_policy_changes",
        "productive_user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/memory-kernel-ownership-rail-alpha742.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": ["The historical aria.core path is an identity-preserving compatibility alias; tests monkeypatch the constructor and make zero requests."],
}
