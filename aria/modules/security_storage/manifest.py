"""Declarative metadata for encrypted security storage and explicit admin tools."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "security_storage",
    "name": "Security Storage",
    "parent": "auth_ui",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns AES-GCM SQLite secret/user storage plus explicitly invoked secure migration and user-administration CLI implementations.",
    "python": [
        "aria/modules/security_storage/secure_store.py",
        "aria/modules/security_storage/migrate.py",
        "aria/modules/security_storage/auth_manager.py",
        "aria/modules/security_storage/user_admin.py",
    ],
    "tests": [
        "tests/test_config_backup.py",
        "tests/test_connection_cleanup.py",
        "tests/test_configuration_security_foundations_import_boundary.py",
        "tests/test_module_registry.py",
        "tests/test_auth_access_kernel_ownership_import_boundary.py"
    ],
    "depends_on": [
        "configuration_foundations",
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "argon2",
            "category": "library_service",
            "disposition": "durable",
        },
        {
            "id": "sqlite",
            "category": "data_boundary",
            "disposition": "durable",
        },
        {
            "id": "cryptography.aesgcm",
            "category": "library_service",
            "disposition": "durable",
        },
        {
            "id": "filesystem.supplied_paths",
            "category": "data_boundary",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "productive_secret_database_user_or_session_access",
        "automatic_or_productive_migration",
        "interactive_or_productive_user_mutation",
        "auth_policy_login_or_session_semantic_changes"
    ],
    "acceptance": ".codex/aria_acceptance/auth-access-ownership-rail-alpha743.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Storage, migration, AuthManager, and user-admin implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "Importing the module does not open a database, read a config, migrate secrets, or administer a user."
    ]
}
