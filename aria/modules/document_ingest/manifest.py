"""Declarative metadata for document ingest preparation."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "document_ingest",
    "name": "Document Ingest",
    "parent": "documents",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns local document normalization, chunking, and PreparedDocument metadata without ingesting or persisting a document.",
    "python": [
        "aria/modules/document_ingest/ingest.py",
    ],
    "tests": [
        "tests/test_document_ingest.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "document_file_read",
        "document_persistence",
        "embedding_calls",
        "qdrant_access",
        "user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/document-ingest-memory-import-rail-alpha731.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The implementation is canonical in this module; the aria.core path is an identity-preserving alias.",
        "Importing the manifest does not prepare, read, or persist a document.",
    ],
}
