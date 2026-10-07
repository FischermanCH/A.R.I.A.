"""Declarative metadata for documents, notes, and context surfaces."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "documents",
    "name": "Documents",
    "status": "domain_namespace_active",
    "lifecycle": "contract_only",
    "risk": "medium_high",
    "description": "Owns document ingest, document memory helpers, notes, and docs/notes context surface metadata until narrower modules are proven.",
    "candidate_submodules": [
        "notes",
        "document_ingest",
        "document_memory",
    ],
    "routes_prefixes": [],
    "routes": [],
    "python": [],
    "templates": [],
    "tests": [
        "tests/test_document_ingest.py",
        "tests/test_notes_routes.py",
        "tests/test_notes_action_arbitration.py",
        "tests/test_chat_notes_flows.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [],
    "explicitly_excluded": [
        "document_ingest_behavior",
        "notes_mutation_behavior",
        "qdrant_document_memory_access",
        "meta_catalog_behavior",
        "context_loading_behavior",
        "answer_contract_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-documents-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Docs and notes overlap with memory, routing, MetaCatalog, and chat context.",
        "Qdrant-backed document memory must not move without explicit acceptance and runtime/user-data permission.",
        "Notes, ingest, document-memory, and context product claims are assigned to registered narrower modules.",
    ],
}
