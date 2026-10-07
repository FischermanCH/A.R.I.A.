"""Declarative metadata for ARIA configuration foundations."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "configuration_foundations",
    "name": "Configuration Foundations",
    "parent": "config_ui",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns settings models, validation, defaults, environment overlays, secret-value resolution, and passive UI theme/background normalization.",
    "python": [
        "aria/modules/configuration_foundations/config.py",
    ],
    "tests": [
        "tests/test_config_env_overrides.py",
        "tests/test_main_config_cache.py",
        "tests/test_config_routes.py",
        "tests/test_configuration_security_foundations_import_boundary.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [
        {
            "id": "module_registry.static_asset_readpoint",
            "category": "library_service",
            "disposition": "durable",
        },
        {
            "id": "yaml",
            "category": "library_service",
            "disposition": "durable",
        },
        {
            "id": "pydantic",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "productive_config_or_secret_access",
        "config_persistence_or_mutation",
        "auth_security_or_runtime_policy_changes",
        "runtime_dispatch_generation",
    ],
    "acceptance": ".codex/aria_acceptance/configuration-security-foundations-import-rail-alpha734.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The implementation is canonical in this module; aria.modules.configuration_foundations.config is an identity-preserving alias.",
        "Importing the module does not load a settings file, resolve a secret file, or mutate configuration."
    ]
}
