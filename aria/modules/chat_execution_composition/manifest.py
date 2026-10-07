"""Declarative metadata for web chat execution composition."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "chat_execution_composition",
    "name": "Chat Execution Composition",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "high_core",
    "description": "Owns web chat route orchestration without owning routing, source, confirmation, or runtime semantics.",
    "routes": [
        "/jobs",
        "/jobs/panel",
        "/jobs/{job_id}/notice",
        "/jobs/{job_id}/cancel",
        "/jobs/{job_id}/pause",
        "/jobs/{job_id}/resume",
        "/jobs/{job_id}/extend",
        "/jobs/{job_id}/finish",
        "/jobs/{job_id}/delete",
        "/jobs/clear-completed",
        "/jobs/{job_id}/correct",
        "/jobs/{job_id}/confirm",
        "/jobs/{job_id}/decline",
        "/chat",
        "/chat/progress",
        "/chat/history/clear",
    ],
    "python": [
        "aria/modules/chat_execution_composition/route_helpers.py",
        "aria/modules/chat_execution_composition/flow.py",
        "aria/modules/chat_execution_composition/routes.py",
    ],
    "templates": [
        "agent_jobs.html",
    ],
    "static": [
        "chat-request-deadline.js",
    ],
    "tests": [
        "tests/test_chat_tooling.py",
        "tests/test_session_recovery.py",
        "tests/test_chat_notes_flows.py",
        "tests/test_chat_websites_flows.py",
        "tests/test_chat_request_deadline.py",
        "tests/test_async_agent_jobs.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_pending_chat_boundary",
        "chat_admin_composition",
        "model_gateway_clients",
        "navigation_shell",
        "notes",
        "platform_primitives",
        "website_runtime",
    ],
    "external_boundaries": [
        {
            "id": "chat_history_callbacks",
            "category": "runtime_callback",
            "disposition": "durable",
        },
        {
            "id": "pipeline_callback",
            "category": "runtime_callback",
            "disposition": "durable",
        },
        {
            "id": "request_cookie_callbacks",
            "category": "runtime_callback",
            "disposition": "durable",
        },
        {
            "id": "template_renderer",
            "category": "library_service",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "routing_or_meta_catalog_behavior_changes",
        "source_authority_or_web_search_behavior_changes",
        "pending_confirmation_or_guardrail_behavior_changes",
        "runtime_handler_order_or_execution_changes",
        "chat_history_notes_website_or_learning_persistence_changes",
        "server_model_call_count_provider_timeout_or_retry_changes",
        "productive_qdrant_connection_secret_or_user_data_access",
        "runtime_access",
    ],
    "acceptance": ".codex/aria_acceptance/chat-execution-composition-ownership-rail-alpha747.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The three historical aria.web modules are identity-preserving compatibility aliases.",
        "The module composes injected callbacks and does not gain authority from registry metadata.",
    ],
}
