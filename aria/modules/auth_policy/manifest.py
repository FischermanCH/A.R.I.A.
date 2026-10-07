"""Declarative metadata for role and protected-path authorization policy."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "auth_policy",
    "name": "Auth Policy",
    "parent": "auth_ui",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns pure role, admin-mode, and protected-path access predicates without owning authentication, sessions, cookies, redirects, or persistence.",
    "python": [
        "aria/modules/auth_policy/access_policy.py",
    ],
    "tests": [
        "tests/test_auth_access_kernel_ownership_import_boundary.py",
        "tests/test_auth_middleware.py",
        "tests/test_error_handling.py",
    ],
    "depends_on": [],
    "external_boundaries": [],
    "explicitly_excluded": [
        "password_hashing_or_verification",
        "user_store_or_role_mutation",
        "session_cookie_csrf_or_redirect_behavior",
        "route_registration_or_middleware_order",
        "productive_auth_config_secret_or_user_access",
    ],
    "acceptance": ".codex/aria_acceptance/auth-access-ownership-rail-alpha743.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The implementation is canonical under aria.modules.auth_policy.",
        "The historical aria.core path is an identity-preserving compatibility alias.",
        "This module contains pure predicates only.",
    ],
}
