"""Static module metadata registry.

The registry is descriptive only. Existing ARIA bootstrap code still owns
runtime registration until a later modularization slice explicitly changes it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aria.modules.action_confirmation.manifest import MODULE_MANIFEST as ACTION_CONFIRMATION_MANIFEST
from aria.modules.action_contracts.manifest import MODULE_MANIFEST as ACTION_CONTRACTS_MANIFEST
from aria.modules.action_draft_policy.manifest import MODULE_MANIFEST as ACTION_DRAFT_POLICY_MANIFEST
from aria.modules.action_pending_chat_boundary.manifest import MODULE_MANIFEST as ACTION_PENDING_CHAT_BOUNDARY_MANIFEST
from aria.modules.action_planner_result_state.manifest import MODULE_MANIFEST as ACTION_PLANNER_RESULT_STATE_MANIFEST
from aria.modules.action_planner_templates.manifest import MODULE_MANIFEST as ACTION_PLANNER_TEMPLATES_MANIFEST
from aria.modules.action_runtime_debug.manifest import MODULE_MANIFEST as ACTION_RUNTIME_DEBUG_MANIFEST
from aria.modules.actions.manifest import MODULE_MANIFEST as ACTIONS_MANIFEST
from aria.modules.agentic_contracts.manifest import MODULE_MANIFEST as AGENTIC_CONTRACTS_MANIFEST
from aria.modules.agentic_prompt_flow.manifest import MODULE_MANIFEST as AGENTIC_PROMPT_FLOW_MANIFEST
from aria.modules.agentic_stabilization.manifest import MODULE_MANIFEST as AGENTIC_STABILIZATION_MANIFEST
from aria.modules.authority_chain_audit.manifest import MODULE_MANIFEST as AUTHORITY_CHAIN_AUDIT_MANIFEST
from aria.modules.auth_ui.manifest import MODULE_MANIFEST as AUTH_UI_MANIFEST
from aria.modules.auth_policy.manifest import MODULE_MANIFEST as AUTH_POLICY_MANIFEST
from aria.modules.capability_error_messages.manifest import MODULE_MANIFEST as CAPABILITY_ERROR_MESSAGES_MANIFEST
from aria.modules.capability_runtime.manifest import MODULE_MANIFEST as CAPABILITY_RUNTIME_MANIFEST
from aria.modules.capability_context.manifest import MODULE_MANIFEST as CAPABILITY_CONTEXT_MANIFEST
from aria.modules.chat_admin_composition.manifest import MODULE_MANIFEST as CHAT_ADMIN_COMPOSITION_MANIFEST
from aria.modules.chat_execution_composition.manifest import MODULE_MANIFEST as CHAT_EXECUTION_COMPOSITION_MANIFEST
from aria.modules.chat_surface.manifest import MODULE_MANIFEST as CHAT_SURFACE_MANIFEST
from aria.modules.chat_history_storage.manifest import MODULE_MANIFEST as CHAT_HISTORY_STORAGE_MANIFEST
from aria.modules.config_backup.manifest import MODULE_MANIFEST as CONFIG_BACKUP_MANIFEST
from aria.modules.config_ui.manifest import MODULE_MANIFEST as CONFIG_UI_MANIFEST
from aria.modules.configuration_foundations.manifest import MODULE_MANIFEST as CONFIGURATION_FOUNDATIONS_MANIFEST
from aria.modules.connection_status_rows.manifest import MODULE_MANIFEST as CONNECTION_STATUS_ROWS_MANIFEST
from aria.modules.connection_routing.manifest import MODULE_MANIFEST as CONNECTION_ROUTING_MANIFEST
from aria.modules.connections_catalog.manifest import MODULE_MANIFEST as CONNECTIONS_CATALOG_MANIFEST
from aria.modules.connections_health_cache.manifest import MODULE_MANIFEST as CONNECTIONS_HEALTH_CACHE_MANIFEST
from aria.modules.connections_mutations.manifest import MODULE_MANIFEST as CONNECTIONS_MUTATIONS_MANIFEST
from aria.modules.connections_provider_manifest.manifest import MODULE_MANIFEST as CONNECTIONS_PROVIDER_MANIFEST
from aria.modules.connections_profiles.manifest import MODULE_MANIFEST as CONNECTIONS_PROFILES_MANIFEST
from aria.modules.connections_runtime_status.manifest import MODULE_MANIFEST as CONNECTIONS_RUNTIME_STATUS_MANIFEST
from aria.modules.connections_semantic.manifest import MODULE_MANIFEST as CONNECTIONS_SEMANTIC_MANIFEST
from aria.modules.connections_ui_readonly.manifest import MODULE_MANIFEST as CONNECTIONS_UI_READONLY_MANIFEST
from aria.modules.connections.manifest import MODULE_MANIFEST as CONNECTIONS_MANIFEST
from aria.modules.documents.manifest import MODULE_MANIFEST as DOCUMENTS_MANIFEST
from aria.modules.document_ingest.manifest import MODULE_MANIFEST as DOCUMENT_INGEST_MANIFEST
from aria.modules.document_memory.manifest import MODULE_MANIFEST as DOCUMENT_MEMORY_MANIFEST
from aria.modules.discord_ui.manifest import MODULE_MANIFEST as DISCORD_UI_MANIFEST
from aria.modules.discord_alerting.manifest import MODULE_MANIFEST as DISCORD_ALERTING_MANIFEST
from aria.modules.execution_dry_run.manifest import MODULE_MANIFEST as EXECUTION_DRY_RUN_MANIFEST
from aria.modules.execution_dry_run_payloads.manifest import MODULE_MANIFEST as EXECUTION_DRY_RUN_PAYLOADS_MANIFEST
from aria.modules.google_calendar_ui.manifest import MODULE_MANIFEST as GOOGLE_CALENDAR_UI_MANIFEST
from aria.modules.http_api.manifest import MODULE_MANIFEST as HTTP_API_MANIFEST
from aria.modules.http_api_admin_ui.manifest import MODULE_MANIFEST as HTTP_API_ADMIN_UI_MANIFEST
from aria.modules.http_api_policy.manifest import MODULE_MANIFEST as HTTP_API_POLICY_MANIFEST
from aria.modules.integration_support.manifest import MODULE_MANIFEST as INTEGRATION_SUPPORT_MANIFEST
from aria.modules.inbound_event_storage.manifest import MODULE_MANIFEST as INBOUND_EVENT_STORAGE_MANIFEST
from aria.modules.imap_ui.manifest import MODULE_MANIFEST as IMAP_UI_MANIFEST
from aria.modules.llm_input_contract.manifest import MODULE_MANIFEST as LLM_INPUT_CONTRACT_MANIFEST
from aria.modules.memory.manifest import MODULE_MANIFEST as MEMORY_MANIFEST
from aria.modules.memory_admin_ui.manifest import MODULE_MANIFEST as MEMORY_ADMIN_UI_MANIFEST
from aria.modules.memory_export.manifest import MODULE_MANIFEST as MEMORY_EXPORT_MANIFEST
from aria.modules.memory_learning_bridge.manifest import MODULE_MANIFEST as MEMORY_LEARNING_BRIDGE_MANIFEST
from aria.modules.mcp.manifest import MODULE_MANIFEST as MCP_MANIFEST
from aria.modules.memory_session_compression.manifest import MODULE_MANIFEST as MEMORY_SESSION_COMPRESSION_MANIFEST
from aria.modules.model_usage_observability.manifest import MODULE_MANIFEST as MODEL_USAGE_OBSERVABILITY_MANIFEST
from aria.modules.native_web_llm.manifest import MODULE_MANIFEST as NATIVE_WEB_LLM_MANIFEST
from aria.modules.model_gateway_clients.manifest import MODULE_MANIFEST as MODEL_GATEWAY_CLIENTS_MANIFEST
from aria.modules.native_toolcall_selftest.manifest import MODULE_MANIFEST as NATIVE_TOOLCALL_SELFTEST_MANIFEST
from aria.modules.native_agent.manifest import MODULE_MANIFEST as NATIVE_AGENT_MANIFEST
from aria.modules.mqtt_ui.manifest import MODULE_MANIFEST as MQTT_UI_MANIFEST
from aria.modules.navigation_shell.manifest import MODULE_MANIFEST as NAVIGATION_SHELL_MANIFEST
from aria.modules.notes.manifest import MODULE_MANIFEST as NOTES_MANIFEST
from aria.modules.ops_config_backup.manifest import MODULE_MANIFEST as OPS_CONFIG_BACKUP_MANIFEST
from aria.modules.operator_trace_boundary.manifest import MODULE_MANIFEST as OPERATOR_TRACE_BOUNDARY_MANIFEST
from aria.modules.pipeline_pending_action_contracts.manifest import MODULE_MANIFEST as PIPELINE_PENDING_ACTION_CONTRACTS_MANIFEST
from aria.modules.pipeline_capability_execution.manifest import MODULE_MANIFEST as PIPELINE_CAPABILITY_EXECUTION_MANIFEST
from aria.modules.pipeline_contracts.manifest import MODULE_MANIFEST as PIPELINE_CONTRACTS_MANIFEST
from aria.modules.pipeline_orchestrator.manifest import MODULE_MANIFEST as PIPELINE_ORCHESTRATOR_MANIFEST
from aria.modules.platform_primitives.manifest import MODULE_MANIFEST as PLATFORM_PRIMITIVES_MANIFEST
from aria.modules.qdrant_gateway.manifest import MODULE_MANIFEST as QDRANT_GATEWAY_MANIFEST
from aria.modules.recipes.manifest import MODULE_MANIFEST as RECIPES_MANIFEST
from aria.modules.recipes_ui.manifest import MODULE_MANIFEST as RECIPES_UI_MANIFEST
from aria.modules.recipe_legacy_skill_compat.manifest import MODULE_MANIFEST as RECIPE_LEGACY_SKILL_COMPAT_MANIFEST
from aria.modules.recipe_runtime.manifest import MODULE_MANIFEST as RECIPE_RUNTIME_MANIFEST
from aria.modules.recipe_store.manifest import MODULE_MANIFEST as RECIPE_STORE_MANIFEST
from aria.modules.release_update.manifest import MODULE_MANIFEST as RELEASE_UPDATE_MANIFEST
from aria.modules.routing_hint_generation.manifest import MODULE_MANIFEST as ROUTING_HINT_GENERATION_MANIFEST
from aria.modules.rss.manifest import MODULE_MANIFEST as RSS_MANIFEST
from aria.modules.rss_digest.manifest import MODULE_MANIFEST as RSS_DIGEST_MANIFEST
from aria.modules.rss_opml.manifest import MODULE_MANIFEST as RSS_OPML_MANIFEST
from aria.modules.rss_runtime.manifest import MODULE_MANIFEST as RSS_RUNTIME_MANIFEST
from aria.modules.rss_ui.manifest import MODULE_MANIFEST as RSS_UI_MANIFEST
from aria.modules.runtime_execution_registry.manifest import MODULE_MANIFEST as RUNTIME_EXECUTION_REGISTRY_MANIFEST
from aria.modules.runtime_bootstrap.manifest import MODULE_MANIFEST as RUNTIME_BOOTSTRAP_MANIFEST
from aria.modules.runtime_diagnostics.manifest import MODULE_MANIFEST as RUNTIME_DIAGNOSTICS_MANIFEST
from aria.modules.runtime_guardrails.manifest import MODULE_MANIFEST as RUNTIME_GUARDRAILS_MANIFEST
from aria.modules.runtime_result_summary.manifest import MODULE_MANIFEST as RUNTIME_RESULT_SUMMARY_MANIFEST
from aria.modules.security_storage.manifest import MODULE_MANIFEST as SECURITY_STORAGE_MANIFEST
from aria.modules.skill_contracts.manifest import MODULE_MANIFEST as SKILL_CONTRACTS_MANIFEST
from aria.modules.smb_ui.manifest import MODULE_MANIFEST as SMB_UI_MANIFEST
from aria.modules.smtp_ui.manifest import MODULE_MANIFEST as SMTP_UI_MANIFEST
from aria.modules.sftp.manifest import MODULE_MANIFEST as SFTP_MANIFEST
from aria.modules.sftp_admin_ui.manifest import MODULE_MANIFEST as SFTP_ADMIN_UI_MANIFEST
from aria.modules.ssh.manifest import MODULE_MANIFEST as SSH_MANIFEST
from aria.modules.ssh_admin_ui.manifest import MODULE_MANIFEST as SSH_ADMIN_UI_MANIFEST
from aria.modules.ssh_policy.manifest import MODULE_MANIFEST as SSH_POLICY_MANIFEST
from aria.modules.ssh_runtime.manifest import MODULE_MANIFEST as SSH_RUNTIME_MANIFEST
from aria.modules.static_help_docs.manifest import MODULE_MANIFEST as STATIC_HELP_DOCS_MANIFEST
from aria.modules.stats_ui.manifest import MODULE_MANIFEST as STATS_UI_MANIFEST
from aria.modules.system_diagnostics.manifest import MODULE_MANIFEST as SYSTEM_DIAGNOSTICS_MANIFEST
from aria.modules.system_inventory.manifest import MODULE_MANIFEST as SYSTEM_INVENTORY_MANIFEST
from aria.modules.ui_admin.manifest import MODULE_MANIFEST as UI_ADMIN_MANIFEST
from aria.modules.website_ui.manifest import MODULE_MANIFEST as WEBSITE_UI_MANIFEST
from aria.modules.website_runtime.manifest import MODULE_MANIFEST as WEBSITE_RUNTIME_MANIFEST
from aria.modules.validation import require_valid_module_registry


MODULE_MANIFESTS: dict[str, Mapping[str, Any]] = {
    str(ACTION_CONFIRMATION_MANIFEST["id"]): ACTION_CONFIRMATION_MANIFEST,
    str(ACTION_CONTRACTS_MANIFEST["id"]): ACTION_CONTRACTS_MANIFEST,
    str(ACTION_DRAFT_POLICY_MANIFEST["id"]): ACTION_DRAFT_POLICY_MANIFEST,
    str(ACTION_PENDING_CHAT_BOUNDARY_MANIFEST["id"]): ACTION_PENDING_CHAT_BOUNDARY_MANIFEST,
    str(ACTION_PLANNER_RESULT_STATE_MANIFEST["id"]): ACTION_PLANNER_RESULT_STATE_MANIFEST,
    str(ACTION_PLANNER_TEMPLATES_MANIFEST["id"]): ACTION_PLANNER_TEMPLATES_MANIFEST,
    str(ACTION_RUNTIME_DEBUG_MANIFEST["id"]): ACTION_RUNTIME_DEBUG_MANIFEST,
    str(ACTIONS_MANIFEST["id"]): ACTIONS_MANIFEST,
    str(AGENTIC_CONTRACTS_MANIFEST["id"]): AGENTIC_CONTRACTS_MANIFEST,
    str(AGENTIC_PROMPT_FLOW_MANIFEST["id"]): AGENTIC_PROMPT_FLOW_MANIFEST,
    str(AGENTIC_STABILIZATION_MANIFEST["id"]): AGENTIC_STABILIZATION_MANIFEST,
    str(AUTHORITY_CHAIN_AUDIT_MANIFEST["id"]): AUTHORITY_CHAIN_AUDIT_MANIFEST,
    str(AUTH_UI_MANIFEST["id"]): AUTH_UI_MANIFEST,
    str(AUTH_POLICY_MANIFEST["id"]): AUTH_POLICY_MANIFEST,
    str(CAPABILITY_ERROR_MESSAGES_MANIFEST["id"]): CAPABILITY_ERROR_MESSAGES_MANIFEST,
    str(CAPABILITY_RUNTIME_MANIFEST["id"]): CAPABILITY_RUNTIME_MANIFEST,
    str(CAPABILITY_CONTEXT_MANIFEST["id"]): CAPABILITY_CONTEXT_MANIFEST,
    str(CHAT_ADMIN_COMPOSITION_MANIFEST["id"]): CHAT_ADMIN_COMPOSITION_MANIFEST,
    str(CHAT_EXECUTION_COMPOSITION_MANIFEST["id"]): CHAT_EXECUTION_COMPOSITION_MANIFEST,
    str(CHAT_SURFACE_MANIFEST["id"]): CHAT_SURFACE_MANIFEST,
    str(CHAT_HISTORY_STORAGE_MANIFEST["id"]): CHAT_HISTORY_STORAGE_MANIFEST,
    str(CONFIG_BACKUP_MANIFEST["id"]): CONFIG_BACKUP_MANIFEST,
    str(CONFIG_UI_MANIFEST["id"]): CONFIG_UI_MANIFEST,
    str(CONFIGURATION_FOUNDATIONS_MANIFEST["id"]): CONFIGURATION_FOUNDATIONS_MANIFEST,
    str(CONNECTION_STATUS_ROWS_MANIFEST["id"]): CONNECTION_STATUS_ROWS_MANIFEST,
    str(CONNECTION_ROUTING_MANIFEST["id"]): CONNECTION_ROUTING_MANIFEST,
    str(CONNECTIONS_CATALOG_MANIFEST["id"]): CONNECTIONS_CATALOG_MANIFEST,
    str(CONNECTIONS_HEALTH_CACHE_MANIFEST["id"]): CONNECTIONS_HEALTH_CACHE_MANIFEST,
    str(CONNECTIONS_MUTATIONS_MANIFEST["id"]): CONNECTIONS_MUTATIONS_MANIFEST,
    str(CONNECTIONS_PROVIDER_MANIFEST["id"]): CONNECTIONS_PROVIDER_MANIFEST,
    str(CONNECTIONS_PROFILES_MANIFEST["id"]): CONNECTIONS_PROFILES_MANIFEST,
    str(CONNECTIONS_RUNTIME_STATUS_MANIFEST["id"]): CONNECTIONS_RUNTIME_STATUS_MANIFEST,
    str(CONNECTIONS_SEMANTIC_MANIFEST["id"]): CONNECTIONS_SEMANTIC_MANIFEST,
    str(CONNECTIONS_UI_READONLY_MANIFEST["id"]): CONNECTIONS_UI_READONLY_MANIFEST,
    str(CONNECTIONS_MANIFEST["id"]): CONNECTIONS_MANIFEST,
    str(DOCUMENTS_MANIFEST["id"]): DOCUMENTS_MANIFEST,
    str(DOCUMENT_INGEST_MANIFEST["id"]): DOCUMENT_INGEST_MANIFEST,
    str(DOCUMENT_MEMORY_MANIFEST["id"]): DOCUMENT_MEMORY_MANIFEST,
    str(DISCORD_UI_MANIFEST["id"]): DISCORD_UI_MANIFEST,
    str(DISCORD_ALERTING_MANIFEST["id"]): DISCORD_ALERTING_MANIFEST,
    str(EXECUTION_DRY_RUN_MANIFEST["id"]): EXECUTION_DRY_RUN_MANIFEST,
    str(EXECUTION_DRY_RUN_PAYLOADS_MANIFEST["id"]): EXECUTION_DRY_RUN_PAYLOADS_MANIFEST,
    str(GOOGLE_CALENDAR_UI_MANIFEST["id"]): GOOGLE_CALENDAR_UI_MANIFEST,
    str(HTTP_API_MANIFEST["id"]): HTTP_API_MANIFEST,
    str(HTTP_API_ADMIN_UI_MANIFEST["id"]): HTTP_API_ADMIN_UI_MANIFEST,
    str(HTTP_API_POLICY_MANIFEST["id"]): HTTP_API_POLICY_MANIFEST,
    str(INTEGRATION_SUPPORT_MANIFEST["id"]): INTEGRATION_SUPPORT_MANIFEST,
    str(INBOUND_EVENT_STORAGE_MANIFEST["id"]): INBOUND_EVENT_STORAGE_MANIFEST,
    str(IMAP_UI_MANIFEST["id"]): IMAP_UI_MANIFEST,
    str(LLM_INPUT_CONTRACT_MANIFEST["id"]): LLM_INPUT_CONTRACT_MANIFEST,
    str(MEMORY_EXPORT_MANIFEST["id"]): MEMORY_EXPORT_MANIFEST,
    str(MEMORY_LEARNING_BRIDGE_MANIFEST["id"]): MEMORY_LEARNING_BRIDGE_MANIFEST,
    str(MCP_MANIFEST["id"]): MCP_MANIFEST,
    str(MODEL_USAGE_OBSERVABILITY_MANIFEST["id"]): MODEL_USAGE_OBSERVABILITY_MANIFEST,
    str(NATIVE_WEB_LLM_MANIFEST["id"]): NATIVE_WEB_LLM_MANIFEST,
    str(MODEL_GATEWAY_CLIENTS_MANIFEST["id"]): MODEL_GATEWAY_CLIENTS_MANIFEST,
    str(NATIVE_TOOLCALL_SELFTEST_MANIFEST["id"]): NATIVE_TOOLCALL_SELFTEST_MANIFEST,
    str(NATIVE_AGENT_MANIFEST["id"]): NATIVE_AGENT_MANIFEST,
    str(MEMORY_ADMIN_UI_MANIFEST["id"]): MEMORY_ADMIN_UI_MANIFEST,
    str(MEMORY_MANIFEST["id"]): MEMORY_MANIFEST,
    str(MEMORY_SESSION_COMPRESSION_MANIFEST["id"]): MEMORY_SESSION_COMPRESSION_MANIFEST,
    str(MQTT_UI_MANIFEST["id"]): MQTT_UI_MANIFEST,
    str(NAVIGATION_SHELL_MANIFEST["id"]): NAVIGATION_SHELL_MANIFEST,
    str(NOTES_MANIFEST["id"]): NOTES_MANIFEST,
    str(OPS_CONFIG_BACKUP_MANIFEST["id"]): OPS_CONFIG_BACKUP_MANIFEST,
    str(OPERATOR_TRACE_BOUNDARY_MANIFEST["id"]): OPERATOR_TRACE_BOUNDARY_MANIFEST,
    str(PIPELINE_PENDING_ACTION_CONTRACTS_MANIFEST["id"]): PIPELINE_PENDING_ACTION_CONTRACTS_MANIFEST,
    str(PIPELINE_CAPABILITY_EXECUTION_MANIFEST["id"]): PIPELINE_CAPABILITY_EXECUTION_MANIFEST,
    str(PIPELINE_CONTRACTS_MANIFEST["id"]): PIPELINE_CONTRACTS_MANIFEST,
    str(PIPELINE_ORCHESTRATOR_MANIFEST["id"]): PIPELINE_ORCHESTRATOR_MANIFEST,
    str(PLATFORM_PRIMITIVES_MANIFEST["id"]): PLATFORM_PRIMITIVES_MANIFEST,
    str(QDRANT_GATEWAY_MANIFEST["id"]): QDRANT_GATEWAY_MANIFEST,
    str(RECIPES_MANIFEST["id"]): RECIPES_MANIFEST,
    str(RECIPES_UI_MANIFEST["id"]): RECIPES_UI_MANIFEST,
    str(RECIPE_LEGACY_SKILL_COMPAT_MANIFEST["id"]): RECIPE_LEGACY_SKILL_COMPAT_MANIFEST,
    str(RECIPE_RUNTIME_MANIFEST["id"]): RECIPE_RUNTIME_MANIFEST,
    str(RECIPE_STORE_MANIFEST["id"]): RECIPE_STORE_MANIFEST,
    str(RELEASE_UPDATE_MANIFEST["id"]): RELEASE_UPDATE_MANIFEST,
    str(ROUTING_HINT_GENERATION_MANIFEST["id"]): ROUTING_HINT_GENERATION_MANIFEST,
    str(RSS_MANIFEST["id"]): RSS_MANIFEST,
    str(RSS_DIGEST_MANIFEST["id"]): RSS_DIGEST_MANIFEST,
    str(RSS_OPML_MANIFEST["id"]): RSS_OPML_MANIFEST,
    str(RSS_RUNTIME_MANIFEST["id"]): RSS_RUNTIME_MANIFEST,
    str(RSS_UI_MANIFEST["id"]): RSS_UI_MANIFEST,
    str(RUNTIME_BOOTSTRAP_MANIFEST["id"]): RUNTIME_BOOTSTRAP_MANIFEST,
    str(RUNTIME_EXECUTION_REGISTRY_MANIFEST["id"]): RUNTIME_EXECUTION_REGISTRY_MANIFEST,
    str(RUNTIME_DIAGNOSTICS_MANIFEST["id"]): RUNTIME_DIAGNOSTICS_MANIFEST,
    str(RUNTIME_GUARDRAILS_MANIFEST["id"]): RUNTIME_GUARDRAILS_MANIFEST,
    str(RUNTIME_RESULT_SUMMARY_MANIFEST["id"]): RUNTIME_RESULT_SUMMARY_MANIFEST,
    str(SECURITY_STORAGE_MANIFEST["id"]): SECURITY_STORAGE_MANIFEST,
    str(SKILL_CONTRACTS_MANIFEST["id"]): SKILL_CONTRACTS_MANIFEST,
    str(SMB_UI_MANIFEST["id"]): SMB_UI_MANIFEST,
    str(SMTP_UI_MANIFEST["id"]): SMTP_UI_MANIFEST,
    str(SFTP_MANIFEST["id"]): SFTP_MANIFEST,
    str(SFTP_ADMIN_UI_MANIFEST["id"]): SFTP_ADMIN_UI_MANIFEST,
    str(SSH_MANIFEST["id"]): SSH_MANIFEST,
    str(SSH_ADMIN_UI_MANIFEST["id"]): SSH_ADMIN_UI_MANIFEST,
    str(SSH_POLICY_MANIFEST["id"]): SSH_POLICY_MANIFEST,
    str(SSH_RUNTIME_MANIFEST["id"]): SSH_RUNTIME_MANIFEST,
    str(STATIC_HELP_DOCS_MANIFEST["id"]): STATIC_HELP_DOCS_MANIFEST,
    str(STATS_UI_MANIFEST["id"]): STATS_UI_MANIFEST,
    str(SYSTEM_DIAGNOSTICS_MANIFEST["id"]): SYSTEM_DIAGNOSTICS_MANIFEST,
    str(SYSTEM_INVENTORY_MANIFEST["id"]): SYSTEM_INVENTORY_MANIFEST,
    str(UI_ADMIN_MANIFEST["id"]): UI_ADMIN_MANIFEST,
    str(WEBSITE_UI_MANIFEST["id"]): WEBSITE_UI_MANIFEST,
    str(WEBSITE_RUNTIME_MANIFEST["id"]): WEBSITE_RUNTIME_MANIFEST,
}

MODULE_MANIFEST_ISSUES = require_valid_module_registry(MODULE_MANIFESTS)


def get_module_manifest(module_id: str) -> Mapping[str, Any] | None:
    """Return declarative metadata for a module id, if known."""

    return MODULE_MANIFESTS.get(str(module_id or "").strip())
