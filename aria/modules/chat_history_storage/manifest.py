"""Declarative metadata for file chat-history storage."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "chat_history_storage",
    "name": "Chat History Storage",
    "parent": "chat_surface",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "description": "Owns bounded per-user JSON chat-history persistence independently from chat dispatch, auth, memory, and runtime actions.",
    "python": [
        "aria/modules/chat_history_storage/store.py",
    ],
    "tests": [
        "tests/test_chat_history.py",
        "tests/test_config_backup_chat_history_storage_import_boundary.py",
        "tests/test_session_recovery.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [
        {
            "id": "filesystem.caller_supplied_path",
            "category": "data_boundary",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "productive_chat_history_or_user_data_access",
        "chat_dispatch_or_post_behavior",
        "auth_or_session_semantic_changes",
        "memory_qdrant_or_runtime_actions",
        "docker_build_export",
    ],
    "acceptance": ".codex/aria_acceptance/config-backup-chat-history-storage-import-rail-alpha734.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Importing the module does not open or create a history directory; callers supply the path explicitly.",
    ],
}
