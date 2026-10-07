"""Declarative metadata for chat-side administration composition."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "chat_admin_composition",
    "name": "Chat Admin Composition",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns chat-side pending-token parsing, signing, encoding, decoding, and admin callback composition without changing confirmation, connection mutation, or update authority.",
    "python": [
        "aria/modules/chat_admin_composition/actions.py",
        "aria/modules/chat_admin_composition/flows.py",
    ],
    "tests": [
        "tests/test_chat_tooling.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "connections_catalog",
        "connections_profiles",
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "update_helper_callbacks",
            "category": "runtime_callback",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "token_signing_claim_or_replay_behavior_changes",
        "connection_create_update_or_delete_behavior_changes",
        "update_execution_behavior_changes",
        "auth_role_or_confirmation_authority_changes",
        "productive_secret_config_connection_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/chat-execution-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "All pending-token helpers previously described by the empty chat_pending_tokens metadata module are physically owned by actions.py; no helper implementation moved in this ownership convergence.",
        "The historical aria.web modules are identity-preserving compatibility aliases.",
        "Callbacks remain injected by aria.main; this module does not execute productive mutations or updates by itself.",
    ],
}
