"""Declarative metadata for SSH policy contracts."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "ssh_policy", "name": "SSH Policy", "parent": "ssh",
    "status": "import_boundary_active", "risk": "high_core",
    "lifecycle": "bootstrap_static",
    "description": "Owns SSH read-only policy and guardrail command-list helpers without evaluating a live command or opening a connection.",
    "python": ["aria/modules/ssh_policy/guardrail_commands.py", "aria/modules/ssh_policy/policy.py"],
    "tests": ["tests/test_ssh_policy.py", "tests/test_http_guardrails.py", "tests/test_module_registry.py"],
    "depends_on": [
        "runtime_guardrails",
    ], "external_boundaries": [],
    "explicitly_excluded": ["ssh_policy_behavior_changes", "guardrail_changes", "ssh_execution", "host_or_network_access"],
    "acceptance": ".codex/aria_acceptance/provider-planning-policy-import-rail-alpha730.json",
    "build_allowed": False, "runtime_access_allowed": False,
    "notes": ["Implementations are canonical in this module; aria.core paths are identity-preserving aliases. Existing policy functions and command lists remain unchanged."],
}
