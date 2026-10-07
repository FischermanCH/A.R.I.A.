"""Declarative metadata for provider capability execution composition."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "pipeline_capability_execution",
    "name": "Pipeline Capability Execution",
    "parent": "actions",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns the existing injected provider-capability executor and result projection without owning target selection, confirmation, guardrails, handler registration, or provider connections.",
    "python": [
        "aria/modules/pipeline_capability_execution/executor.py",
    ],
    "tests": [
        "tests/test_connection_action_contract.py",
        "tests/test_pipeline.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "platform_primitives",
        "recipe_runtime",
        "rss_digest",
        "runtime_result_summary",
        "sftp",
        "ssh_runtime",
        "skill_contracts",
        "website_runtime",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "target_capability_or_action_payload_changes",
        "confirmation_guardrail_or_policy_changes",
        "handler_registration_order_or_runtime_dispatch_changes",
        "provider_result_summary_or_error_mapping_changes",
        "real_provider_connection_or_secret_access",
    ],
    "acceptance": ".codex/aria_acceptance/pipeline-context-runtime-ownership-rail-alpha742.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The historical aria.core path is an identity-preserving compatibility alias.",
        "The moved I18NStore continues to resolve aria/i18n.",
        "Tests inject fake runtimes and perform no provider operation.",
    ],
}
