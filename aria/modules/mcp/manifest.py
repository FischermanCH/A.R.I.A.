"""Declarative metadata for the generic MCP client."""

MODULE_MANIFEST = {
    "id": "mcp",
    "name": "MCP Client",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_external_read_boundary",
    "description": "Owns opt-in MCP server discovery, cached read-only Tool projection and bounded Tool calls.",
    "python": [
        "aria/modules/mcp/runtime.py",
        "aria/modules/mcp/native_tools.py",
    ],
    "integration_points": ["aria/modules/mcp/native_tools.py::native_tool_contributions"],
    "tests": ["tests/test_mcp_client_foundation.py"],
    "depends_on": ["configuration_foundations"],
    "external_boundaries": [
        {"id": "mcp.remote_read_tools", "category": "library_service", "disposition": "durable"},
        {"id": "mcp.python_sdk", "category": "library_service", "disposition": "durable"},
    ],
    "explicitly_excluded": [
        "mutating_mcp_tools",
        "mcp_admin_ui",
        "aria_as_mcp_server",
        "productive_mcp_access_in_tests",
    ],
    "acceptance": ".codex/aria_acceptance/mcp-client-foundation-readonly-tools-alpha957-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
