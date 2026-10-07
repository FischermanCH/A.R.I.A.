"""Declarative metadata for the auth UI module."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "auth_ui",
    "name": "Auth UI",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns login/logout/session-expired surfaces, auth cookies, and auth middleware metadata.",
    "routes_prefixes": [
        "/login",
        "/logout",
        "/session-expired",
    ],
    "routes": [
        "/login",
        "/logout",
        "/session-expired",
    ],
    "python": [
        "aria/modules/auth_ui/cookies.py",
        "aria/modules/auth_ui/middleware.py",
        "aria/modules/auth_ui/routes.py",
        "aria/modules/auth_ui/session.py",
    ],
    "templates": [
        "login.html",
        "session_expired.html",
    ],
    "tests": [
        "tests/test_auth_middleware.py",
        "tests/test_auth_surface_routes.py",
    ],
    "depends_on": [
        "auth_policy",
        "configuration_foundations",
        "navigation_shell",
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "user_admin",
        "config_security_persistence",
        "chat_pipeline",
        "runtime_actions",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-auth-ui-route-url-readpoint-alpha693.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Auth middleware, routes, cookie helpers, and signed-session helpers are canonical under aria.modules.auth_ui.",
        "The four aria.web paths remain identity-preserving compatibility aliases.",
        "aria.main imports canonical owners; the ownership move changes no authentication, authorization, cookie, CSRF, session, or rate-limit behavior."
    ],
}
