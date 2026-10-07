"""Declarative metadata for the standalone native Tool-Calling selftest."""

MODULE_MANIFEST = {
    "id": "native_toolcall_selftest",
    "name": "Native Tool-Call Selftest",
    "status": "diagnostic_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_needs_proof",
    "parent": "model_gateway_clients",
    "description": "Owns one inert admin-triggered two-hop native Tool-Calling diagnostic with a deterministic add_numbers dummy tool.",
    "routes_prefixes": ["/config/native-toolcall-selftest"],
    "routes": ["/config/native-toolcall-selftest"],
    "python": ["aria/modules/native_toolcall_selftest/roundtrip.py", "aria/modules/native_toolcall_selftest/routes.py"],
    "templates": ["native_toolcall_selftest.html"],
    "tests": ["tests/test_native_toolcall_selftest.py"],
    "depends_on": ["configuration_foundations", "model_gateway_clients"],
    "external_boundaries": [{"id": "litellm.native_tool_call", "category": "library_service", "disposition": "durable"}],
    "explicitly_excluded": ["pipeline", "arbitration", "qdrant", "agentic_loop", "product_tools", "automatic_or_default_on_execution"],
    "acceptance": ".codex/aria_acceptance/native-toolcall-selftest-alpha828-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
