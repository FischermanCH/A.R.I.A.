from __future__ import annotations

from aria.modules import MODULE_MANIFESTS, get_module_manifest


def test_module_registry_exposes_passive_metadata_for_known_modules() -> None:
    expected_ids = {
        "action_confirmation",
        "action_contracts",
        "action_draft_policy",
        "action_pending_chat_boundary",
        "action_planner_result_state",
        "action_planner_templates",
        "action_runtime_debug",
        "actions",
        "agentic_contracts",
        "agentic_prompt_flow",
        "agentic_stabilization",
        "authority_chain_audit",
        "auth_ui",
        "capability_error_messages",
        "capability_context",
        "chat_surface",
        "chat_history_storage",
        "config_backup",
        "config_ui",
        "configuration_foundations",
        "connection_status_rows",
        "connection_routing",
        "connections_catalog",
        "connections_health_cache",
        "connections_mutations",
        "connections_provider_manifest",
        "connections_profiles",
        "connections_runtime_status",
        "connections_semantic",
        "connections_ui_readonly",
        "connections",
        "documents",
        "document_ingest",
        "document_memory",
        "discord_alerting",
        "execution_dry_run_payloads",
        "execution_dry_run",
        "http_api",
        "http_api_admin_ui",
        "http_api_policy",
        "integration_support",
        "inbound_event_storage",
        "memory",
        "memory_export",
        "memory_learning_bridge",
        "model_gateway_clients",
        "navigation_shell",
        "notes",
        "ops_config_backup",
        "operator_trace_boundary",
        "pipeline_pending_action_contracts",
        "pipeline_capability_execution",
        "pipeline_contracts",
        "pipeline_orchestrator",
        "qdrant_gateway",
        "recipes",
        "recipe_legacy_skill_compat",
        "recipe_runtime",
        "recipe_store",
        "release_update",
        "routing_hint_generation",
        "rss",
        "rss_digest",
        "rss_opml",
        "rss_runtime",
        "runtime_execution_registry",
        "runtime_result_summary",
        "runtime_guardrails",
        "security_storage",
        "ssh",
        "ssh_admin_ui",
        "ssh_policy",
        "ssh_runtime",
        "static_help_docs",
        "stats_ui",
        "system_diagnostics",
        "system_inventory",
        "runtime_diagnostics",
        "ui_admin",
    }

    assert expected_ids.issubset(MODULE_MANIFESTS)
    for module_id in expected_ids:
        manifest = get_module_manifest(module_id)
        assert manifest is MODULE_MANIFESTS[module_id]
        assert manifest["id"] == module_id
        assert manifest["build_allowed"] is False
        assert manifest["runtime_access_allowed"] is False
        assert "acceptance" in manifest


def test_module_registry_returns_none_for_unknown_module() -> None:
    assert get_module_manifest("missing") is None


def test_config_template_ownership_no_longer_relies_on_ui_admin_wildcards() -> None:
    config_templates = {str(item) for item in MODULE_MANIFESTS["config_ui"].get("templates", [])}
    ui_admin_templates = {str(item) for item in MODULE_MANIFESTS["ui_admin"].get("templates", [])}

    assert "config*.html" not in config_templates
    assert "_config*.html" not in config_templates
    assert "config*.html" not in ui_admin_templates
    assert "_config*.html" not in ui_admin_templates
    assert "config_hub.html" in config_templates
    assert "config_admin_modules.html" in config_templates
    assert "_config_nav.html" in config_templates
