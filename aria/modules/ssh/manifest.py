"""Declarative metadata for SSH policy, targeting, and runtime boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "ssh",
    "name": "SSH",
    "status": "domain_namespace_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns SSH policy, target scope, guardrail commands, agentic resolution metadata, and SSH result summaries without executing SSH.",
    "candidate_submodules": [
        "ssh_policy",
        "ssh_runtime",
        "ssh_admin_ui",
    ],
    "routes_prefixes": [],
    "routes": [],
    "python": [
        "aria/modules/ssh/profile_admin.py",
    ],
    "templates": [],
    "tests": [
        "tests/test_ssh_*.py",
        "tests/test_agentic_execution.py",
        "tests/test_execution_dry_run.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "runtime_guardrails",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "ssh_command_execution",
        "ssh_connection_open",
        "target_scope_policy_changes",
        "readonly_policy_changes",
        "confirmation_bypass",
        "host_filesystem_access",
        "user_secret_access",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-ssh-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "SSH is runtime/userdata/security critical; this slice is metadata only.",
        "Policy, resolution, runtime, target-scope, result-summary, and admin UI claims are delegated to narrow modules.",
        "No SSH target, connection, policy, command, or result summarizer behavior changes are included.",
        "Later work must prove read-only/confirmation boundaries with prompt and route evidence.",
    ],
}
