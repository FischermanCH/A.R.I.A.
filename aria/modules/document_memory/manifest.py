"""Declarative metadata for document-memory persistence boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "document_memory",
    "name": "Document Memory",
    "parent": "documents",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns document meta-catalog and document-memory helper/service metadata without reading, embedding, or writing documents or Qdrant points.",
    "python": [
        "aria/modules/document_memory/meta_catalog.py",
        "aria/modules/document_memory/helpers.py",
        "aria/modules/document_memory/service.py",
        "aria/modules/document_memory/native_tools.py",
    ],
    "tests": [
        "tests/test_document_ingest.py",
        "tests/test_memory.py",
        "tests/test_document_ingest_memory_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "document_ingest",
        "memory",
        "skill_contracts",
    ],
    "external_boundaries": [],
    "integration_points": ["aria/modules/document_memory/native_tools.py::native_tool_contributions"],
    "explicitly_excluded": [
        "document_or_user_data_read",
        "embedding_calls",
        "qdrant_read_write_or_collection_mutation",
        "document_ingest_execution",
        "memory_recall_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/document-ingest-memory-import-rail-alpha731.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "No service instance, embedding client, or Qdrant client is created by this manifest.",
    ],
}
