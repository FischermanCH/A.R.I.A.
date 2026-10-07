from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.action_draft_policy.contracts", "aria.modules.action_draft_policy.contracts"),
    ("aria.modules.action_draft_policy.guardrail_drafts", "aria.modules.action_draft_policy.guardrail_drafts"),
    ("aria.modules.action_confirmation.ledger", "aria.modules.action_confirmation.ledger"),
    ("aria.modules.operator_trace_boundary.operator_trace", "aria.modules.operator_trace_boundary.operator_trace"),
    ("aria.modules.runtime_result_summary.summarizers", "aria.modules.runtime_result_summary.summarizers"),
    ("aria.modules.runtime_result_summary.summarizers.file_operation", "aria.modules.runtime_result_summary.summarizers.file_operation"),
    ("aria.modules.runtime_result_summary.summarizers.http_api", "aria.modules.runtime_result_summary.summarizers.http_api"),
    ("aria.modules.runtime_result_summary.summarizers.imap", "aria.modules.runtime_result_summary.summarizers.imap"),
    ("aria.modules.runtime_result_summary.summarizers.rss", "aria.modules.runtime_result_summary.summarizers.rss"),
    ("aria.modules.runtime_result_summary.summarizers.ssh", "aria.modules.runtime_result_summary.summarizers.ssh"),
)


def test_legacy_action_control_observability_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_action_control_observability_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.action_draft_policy.contracts": "AgenticActionDraft",
        "aria.modules.action_draft_policy.guardrail_drafts": "normalize_guardrail_draft",
        "aria.modules.action_confirmation.ledger": "ActionConfirmationLedger",
        "aria.modules.operator_trace_boundary.operator_trace": "build_operator_trace_lines",
        "aria.modules.runtime_result_summary.summarizers": "summarize_ssh_result_for_chat",
        "aria.modules.runtime_result_summary.summarizers.file_operation": "summarize_file_result_for_chat",
        "aria.modules.runtime_result_summary.summarizers.http_api": "summarize_http_api_result_for_chat",
        "aria.modules.runtime_result_summary.summarizers.imap": "summarize_imap_result_for_chat",
        "aria.modules.runtime_result_summary.summarizers.rss": "summarize_rss_category_result_for_chat",
        "aria.modules.runtime_result_summary.summarizers.ssh": "extract_df_metrics",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
