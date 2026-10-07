"""Declarative metadata for RSS digest contracts."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "rss_digest", "name": "RSS Digest", "parent": "rss",
    "status": "import_boundary_active", "risk": "medium_high",
    "lifecycle": "bootstrap_static",
    "description": "Owns RSS digest option inference, execution-option projection, and grouping helpers without fetching feeds or changing recipe runtime behavior.",
    "python": ["aria/modules/rss_digest/options.py", "aria/modules/rss_digest/execution_policy.py", "aria/modules/rss_digest/grouping.py"],
    "tests": ["tests/test_rss_grouping.py", "tests/test_skill_runtime_rss.py", "tests/test_module_registry.py"],
    "depends_on": [
        "platform_primitives",
    ], "external_boundaries": [],
    "explicitly_excluded": ["feed_fetch", "digest_behavior_changes", "recipe_runtime_changes", "connection_or_network_access"],
    "acceptance": ".codex/aria_acceptance/provider-planning-policy-import-rail-alpha730.json",
    "build_allowed": False, "runtime_access_allowed": False,
    "notes": ["Implementations are canonical in this module; aria.core paths are identity-preserving aliases. Existing option inference, limits, and grouping behavior remains unchanged."],
}
