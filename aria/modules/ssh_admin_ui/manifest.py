"""Declarative metadata for SSH administration surfaces."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "ssh_admin_ui", "name": "SSH Admin UI", "parent": "ssh",
    "status": "surface_context_active", "risk": "high",
    "lifecycle": "bootstrap_static",
    "description": "Owns SSH config templates, provider route registration, page context, metadata helpers, and save/key adapters without invoking probe/runtime operations.",
    "routes_prefixes": ["/config/connections/ssh"],
    "routes": ["/config/connections/save", "/config/connections/key-exchange", "/config/connections/keygen", "/config/connections/ssh", "/config/connections/ssh/suggest-metadata"],
    "templates": ["config_connections_ssh.html"],
    "python": ["aria/modules/ssh_admin_ui/context.py", "aria/modules/ssh_admin_ui/metadata.py", "aria/modules/ssh_admin_ui/mutations.py", "aria/modules/ssh_admin_ui/reader.py", "aria/modules/ssh_admin_ui/support.py"],
    "tests": ["tests/test_config_routes.py", "tests/test_connection_admin.py", "tests/test_module_registry.py"],
    "depends_on": [
        "config_ui",
        "connections_mutations",
        "connections_profiles",
        "auth_policy",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "integration_points": [
        "aria/modules/connections_ui_readonly/context_helpers.py::SSH context adapter",
        "aria/modules/connections_ui_readonly/detail_routes.py::SSH detail route registration adapter",
        "aria/modules/connections_ui_readonly/metadata_routes.py::SSH metadata route registration adapter",
        "aria/modules/connections_mutations/handlers.py::SSH save/key action adapters",
        "aria/modules/connections_mutations/routes.py::SSH mutation route registration adapter",
    ],
    "explicitly_excluded": ["secret_access", "runtime_access"],
    "acceptance": ".codex/aria_acceptance/provider-ownership-submodules-alpha725.json",
    "build_allowed": False, "runtime_access_allowed": False,
    "notes": ["Central web modules compose SSH route registrars; SSH page context, metadata helpers, support helpers, and mutation adapters are owned here."],
}
