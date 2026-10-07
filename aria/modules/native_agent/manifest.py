"""Declarative metadata for the default-off standalone native agent."""

MODULE_MANIFEST = {
    "id": "native_agent",
    "name": "Native Agent",
    "status": "default_off_experimental",
    "lifecycle": "bootstrap_static",
    "risk": "high_needs_live_proof",
    "parent": "model_gateway_clients",
    "description": "Owns a bounded native Tool-Calling turn handler and server-owned personal-memory observation lifecycle.",
    "python": [
        "aria/modules/native_agent/handler.py",
        "aria/modules/native_agent/pipeline_bridge.py",
        "aria/modules/native_agent/tool_registry.py",
        "aria/modules/native_agent/pending_store.py",
    ],
    "tests": ["tests/test_native_agent.py"],
    "depends_on": ["action_confirmation", "configuration_foundations", "connections_runtime_status", "memory", "model_gateway_clients", "pipeline_contracts", "platform_primitives"],
    "external_boundaries": [{"id": "litellm.native_tool_loop", "category": "library_service", "disposition": "durable"}],
    "explicitly_excluded": ["bounded_decision", "legacy_arbitration_changes"],
    "acceptance": ".codex/aria_acceptance/native-agent-no-fabricated-actions-alpha852-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
