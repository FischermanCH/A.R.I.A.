"""Declarative metadata for RSS feed execution and grouping."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "rss",
    "name": "RSS",
    "status": "domain_namespace_active",
    "lifecycle": "contract_only",
    "risk": "medium_high",
    "description": "Owns RSS feed execution, digest options, grouping, OPML helpers, RSS result summaries, and RSS runtime metadata.",
    "python": [],
    "templates": [],
    "tests": [
        "tests/test_rss_grouping.py",
        "tests/test_rss_opml.py",
        "tests/test_skill_runtime_rss.py",
        "tests/test_result_summarizers.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "rss_connection_profile_persistence",
        "connection_metadata_suggestion",
        "routed_action_resolution_behavior",
        "recipe_runtime_behavior_change",
        "feed_fetch_behavior_change",
        "opml_import_export_behavior_change",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-rss-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "RSS config UI context currently lives in connection helpers and overlaps with connections.",
        "Digest, OPML, runtime, recipe-runtime, result-summary, and UI claims are delegated to narrow modules.",
        "The concrete RSS config template is owned by rss_ui.",
    ],
}
