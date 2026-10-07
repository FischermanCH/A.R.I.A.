from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.ssh_policy.guardrail_commands", "aria.modules.ssh_policy.guardrail_commands"),
    ("aria.modules.ssh_policy.policy", "aria.modules.ssh_policy.policy"),
    ("aria.modules.http_api_policy.policy", "aria.modules.http_api_policy.policy"),
    ("aria.modules.rss_digest.options", "aria.modules.rss_digest.options"),
    ("aria.modules.rss_digest.execution_policy", "aria.modules.rss_digest.execution_policy"),
    ("aria.modules.rss_digest.grouping", "aria.modules.rss_digest.grouping"),
    ("aria.modules.rss_opml.opml", "aria.modules.rss_opml.opml"),
    ("aria.modules.capability_error_messages.messages", "aria.modules.capability_error_messages.messages"),
)


def test_legacy_provider_planning_policy_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_provider_planning_policy_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.ssh_policy.guardrail_commands": "combined_ssh_allow_commands",
        "aria.modules.ssh_policy.policy": "validate_ssh_readonly_policy",
        "aria.modules.http_api_policy.policy": "validate_http_api_request_policy",
        "aria.modules.rss_digest.options": "infer_rss_digest_options",
        "aria.modules.rss_digest.execution_policy": "RssActionSelectionPolicy",
        "aria.modules.rss_digest.grouping": "build_rss_status_groups",
        "aria.modules.rss_opml.opml": "parse_opml_feeds",
        "aria.modules.capability_error_messages.messages": "format_capability_execution_error",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
