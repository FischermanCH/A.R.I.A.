"""Declarative metadata for the passive chat surface module."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "chat_surface",
    "name": "Chat Surface",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns the passive GET home/chat page and command catalog without changing chat dispatch.",
    "python": [
        "aria/modules/chat_surface/catalog.py",
        "aria/modules/chat_surface/routes.py",
    ],
    "templates": [
        "chat.html",
    ],
    "routes": [
        "/",
    ],
    "tests": [
        "tests/test_session_recovery.py",
        "tests/test_help_page.py",
        "tests/test_memories_routes.py",
        "tests/test_module_registry_read_model.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_profiles",
        "navigation_shell",
        "platform_primitives",
        "recipe_runtime",
        "recipes_ui",
        "auth_policy",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "chat_post_dispatch",
        "pending_action_boundary",
        "runtime_actions",
        "qdrant_access",
        "user_memory_data",
    ],
    "acceptance": ".codex/aria_acceptance/chat-surface-catalog-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The two historical aria.web modules are identity-preserving compatibility aliases.",
        "The module owns passive rendering and catalog construction only; POST dispatch remains excluded.",
    ],
}
