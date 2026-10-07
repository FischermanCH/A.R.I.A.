"""Declarative metadata for watched-website runtime projections."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "website_runtime",
    "name": "Website Runtime",
    "parent": "connections",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high",
    "description": "Owns deterministic watched-website normalization and read/list projections without fetching, probing, mutating, or routing websites.",
    "python": [
        "aria/modules/website_runtime/chat_flows.py",
        "aria/modules/website_runtime/runtime.py",
        "aria/modules/website_runtime/native_tools.py",
    ],
    "integration_points": ["aria/modules/website_runtime/native_tools.py::native_tool_contributions"],
    "tests": [
        "tests/test_chat_websites_flows.py",
        "tests/test_website_link_readpoints.py",
        "tests/test_web_answer_website_kernel_ownership_import_boundary.py",
    ],
    "depends_on": [
        "connections_semantic",
        "platform_primitives",
        "website_ui",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "website_fetch_or_probe",
        "profile_persistence_or_mutation",
        "semantic_target_substitution",
        "connection_or_network_access",
        "websearch_or_source_authority",
        "routing_runtime_or_action_execution",
    ],
    "acceptance": ".codex/aria_acceptance/chat-execution-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The implementation is canonical under aria.modules.website_runtime.",
        "The historical aria.core path is an identity-preserving compatibility alias.",
        "The package-depth correction preserves aria/i18n as the translation root.",
    ],
}
