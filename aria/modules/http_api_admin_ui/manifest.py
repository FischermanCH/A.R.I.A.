"""Declarative metadata for HTTP/API and Webhook administration surfaces."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "http_api_admin_ui", "name": "HTTP API Admin UI", "parent": "http_api",
    "status": "surface_contract_active", "risk": "high",
    "lifecycle": "contract_only",
    "description": "Owns existing HTTP/API and Webhook config routes and templates without registering routes or invoking save/test operations.",
    "routes_prefixes": ["/config/connections/http-api", "/config/connections/webhook"],
    "routes": ["/config/connections/http-api", "/config/connections/http-api/save", "/config/connections/webhook", "/config/connections/webhook/save"],
    "templates": ["config_connections_http_api.html", "config_connections_webhook.html"],
    "python": [],
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
        "aria/modules/connections_ui_readonly/detail_routes.py::HTTP/API/Webhook GET handlers",
    ],
    "explicitly_excluded": ["route_registration_changes", "connection_save_test_or_probe", "http_or_webhook_execution", "secret_or_network_access", "runtime_access"],
    "acceptance": ".codex/aria_acceptance/provider-ownership-submodules-alpha725.json",
    "build_allowed": False, "runtime_access_allowed": False,
    "notes": ["Route decorators and handlers remain in the existing web modules."],
}
