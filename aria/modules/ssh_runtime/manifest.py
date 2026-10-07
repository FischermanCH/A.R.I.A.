"""Declarative metadata for SSH runtime adapters."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "ssh_runtime", "name": "SSH Runtime", "parent": "ssh",
    "status": "import_boundary_active", "risk": "high_core",
    "lifecycle": "bootstrap_static",
    "description": "Owns existing SSH execution adapter, runtime class, and canonical Pipeline SSH orchestration helpers without executing SSH.",
    "python": ["aria/modules/ssh_runtime/agentic_execution.py", "aria/modules/ssh_runtime/capability_execution.py", "aria/modules/ssh_runtime/held_packages.py", "aria/modules/ssh_runtime/native_tools.py", "aria/modules/ssh_runtime/outcome.py", "aria/modules/ssh_runtime/pipeline_helpers.py", "aria/modules/ssh_runtime/registry.py", "aria/modules/ssh_runtime/runtime.py", "aria/modules/ssh_runtime/status.py"],
    "tests": ["tests/test_ssh_runtime.py", "tests/test_native_agent_ssh_tools.py", "tests/test_agentic_execution.py", "tests/test_execution_dry_run.py", "tests/test_pipeline.py", "tests/test_module_registry.py"],
    "depends_on": [
        "action_contracts",
        "action_runtime_debug",
        "auth_policy",
        "connections_catalog",
        "connections_semantic",
        "execution_dry_run",
        "execution_dry_run_payloads",
        "pipeline_contracts",
        "recipe_runtime",
        "runtime_result_summary",
        "runtime_execution_registry",
        "runtime_guardrails",
        "ssh_policy",
        "skill_contracts",
    ],
    "integration_points": ["aria/modules/ssh_runtime/native_tools.py::native_tool_contributions"],
    "external_boundaries": [
        {
            "id": "runtime_action_execution_boundary",
            "category": "runtime_callback",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": ["ssh_connection_open", "guardrail_or_confirmation_changes", "host_filesystem_access", "secret_access", "productive_runtime_access"],
    "acceptance": ".codex/aria_acceptance/native-ssh-read-and-command-alpha854-review-build.json",
    "build_allowed": False, "runtime_access_allowed": False,
    "notes": ["The agentic handler, Pipeline SSH helpers, and SSHRuntime are canonical in this module; their aria.core paths are identity-preserving compatibility aliases. No adapter is instantiated and no runtime handler is called by this manifest."],
}
