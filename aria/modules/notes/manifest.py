"""Declarative metadata for Notes surfaces and storage boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "notes",
    "name": "Notes",
    "parent": "documents",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "description": "Owns Notes routes, templates, storage/index/context helpers, and chat-flow metadata without reading or mutating productive Notes or Qdrant.",
    "routes_prefixes": [
        "/notes",
    ],
    "routes": [
        "/notes",
        "/notes/save",
        "/notes/delete",
        "/notes/move",
        "/notes/bulk/move",
        "/notes/folders/create",
        "/notes/folders/rename",
    ],
    "templates": [
        "notes.html",
        "_docs_nav.html",
    ],
    "python": [
        "aria/modules/notes/action_arbitration.py",
        "aria/modules/notes/context.py",
        "aria/modules/notes/index.py",
        "aria/modules/notes/magic.py",
        "aria/modules/notes/chat_flows.py",
        "aria/modules/notes/routes.py",
        "aria/modules/notes/store.py",
        "aria/modules/notes/links.py",
        "aria/modules/notes/native_tools.py",
    ],
    "tests": [
        "tests/test_chat_notes_flows.py",
        "tests/test_document_link_readpoints.py",
        "tests/test_notes_action_arbitration.py",
        "tests/test_notes_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_confirmation",
        "document_ingest",
        "configuration_foundations",
        "model_usage_observability",
        "platform_primitives",
        "qdrant_gateway",
    ],
    "external_boundaries": [
        {
            "id": "embeddings",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "integration_points": ["aria/modules/notes/native_tools.py::native_tool_contributions"],
    "explicitly_excluded": [
        "legacy_notes_delete_or_move_behavior_changes",
        "notes_index_mutation_behavior_changes",
        "embedding_calls",
        "qdrant_access",
        "web_search_execution",
        "chat_action_arbitration_changes",
    ],
    "acceptance": ".codex/aria_acceptance/native-notes-upsert-by-title-alpha853-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Notes service implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "Existing /notes URLs and notes.html rendering now read ownership from this module.",
        "The manifest instantiates no Notes store, index, embedding client, Qdrant client, URL fetch, or WebSearch skill.",
    ],
}
