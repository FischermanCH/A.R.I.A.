from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthorityChainBoundary:
    boundary_id: str
    component: str
    decision: str
    effect: str
    authority: str
    manifest_class: str
    source_marker: str
    owner_note: str


ALLOWED_AUTHORITY_EFFECTS: frozenset[str] = frozenset(
    {"candidate_only", "contract_bound", "observability_only", "validation_only"}
)

RETIRED_SEMANTIC_SOURCE_MARKERS: tuple[tuple[str, str], ...] = (
    ("meta_catalog_explicit_local_surface", "_explicit_local_surface"),
    ("meta_catalog_connection_inventory_phrases", "_looks_like_connection_inventory_question"),
    ("meta_catalog_rss_action_phrases", "_looks_like_rss_read_action"),
    ("meta_catalog_surface_review", "_review_local_surface_contract"),
    ("meta_catalog_surface_review_operation", "meta_catalog_surface_contract_review"),
    ("pre_rag_capability_draft_operation", "capability_draft_decision"),
    ("pre_rag_action_arbitration_operation", "pre_rag_action_arbitration"),
    ("pre_rag_capability_draft_result", "PreRagCapabilityDraftResult"),
)

RETIRED_CONTEXT_QUERY_SOURCE_MARKERS: tuple[tuple[str, str], ...] = (
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_explicit_web_research_fastpath_arbitration"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_fresh_web_research_fastpath_arbitration"),
    ("aria/modules/chat_execution_composition/routes.py", "_resolve_pipeline_followup_message"),
    ("aria/modules/chat_execution_composition/routes.py", "_rewrite_vague_web_search_followup"),
    ("aria/modules/chat_execution_composition/routes.py", "_rewrite_vague_local_context_followup"),
)

RETIRED_LEGACY_MODULES: tuple[str, ...] = (
    "aria/core/capability_router.py",
    "aria/core/capability_input_adapter.py",
    "aria/core/chat_freshness.py",
    "aria/core/context_evidence.py",
    "aria/core/followup_resolution.py",
    "aria/core/action_planner_followups.py",
    "aria/core/routing_lexicon.py",
    "aria/core/turn_intent_arbitration.py",
    "aria/modules/recipe_runtime/matching.py",
)

RETIRED_PRODUCTIVE_MARKERS: tuple[tuple[str, str], ...] = (
    ("aria/modules/native_web_llm/dispatch.py", "_LEXICON"),
    ("aria/modules/native_web_llm/source_policy.py", "_N8N_POLICY"),
    ("aria/modules/memory/personal.py", "explicit_personal_memory_capture_requested"),
    ("aria/modules/memory/personal.py", "exact_personal_claim_answer"),
    ("aria/modules/memory/personal.py", "exact_personal_subject_claim_ids"),
    ("aria/modules/memory_learning_bridge/skill.py", "_document_corpus_scan_terms"),
    ("aria/modules/memory_learning_bridge/skill.py", "_recall_document_corpus_scan"),
    ("aria/templates/chat.html", "messageHasAny"),
    ("aria/templates/chat.html", "resolveLikelyRecipeInfo"),
    ("aria/templates/chat.html", "looksLikeRecipeExecution"),
    ("aria/modules/recipe_runtime/runtime.py", "normalize_recipe_keywords"),
    ("aria/modules/recipe_store/wizard_save.py", "router_keywords"),
    ("aria/modules/execution_dry_run_payloads/template_payloads.py", "infer_message_content"),
    ("aria/modules/ops_config_backup/maintenance.py", "_load_operational_trigger_phrases"),
    ("aria/modules/memory_learning_bridge/skill.py", "cleanup_operational_session_entries"),
    ("aria/modules/connections_catalog/catalog.py", "semantic_suffixes"),
    ("aria/modules/connections_catalog/catalog.py", "routing_language_hints"),
    ("aria/modules/connections_catalog/catalog.py", "CONNECTION_FIELD_CHAT_CATALOG"),
    ("aria/modules/connections_semantic/resolver.py", "connection_label_match_score"),
    ("aria/modules/website_runtime/runtime.py", "find_website_matches"),
    ("aria/modules/document_memory/meta_catalog.py", "_semantic_document_aliases"),
    ("aria/modules/notes/magic.py", "infer_note_folder"),
    ("aria/modules/notes/magic.py", "infer_note_tags"),
    ("aria/modules/notes/context.py", "lexical_note_hits"),
    ("aria/modules/document_memory/service.py", "keyword_hits"),
    ("aria/modules/document_memory/service.py", "text_hits"),
    ("aria/modules/notes/chat_flows.py", "_NATURAL_NOTE_PATTERNS"),
    ("aria/modules/notes/chat_flows.py", "_QUICK_NOTE_PATTERNS"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_rewrite_ssh_followup_message"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_rewrite_calendar_followup_message"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_looks_like_plural_target_request"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_wants_previous_connection"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "_wants_previous_path"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "demoted_must_domains"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "normalized_stale_query_years"),
    ("aria/modules/pipeline_orchestrator/pipeline.py", "priority_terms = (\"linux-image\""),
    ("aria/modules/ssh_runtime/pipeline_helpers.py", "_extract_free_disk_threshold_gib"),
    ("aria/modules/ssh_runtime/pipeline_helpers.py", "_multi_target_ssh_result_state"),
    ("aria/modules/ssh_runtime/pipeline_helpers.py", "_looks_like_health_observation_command"),
    ("aria/modules/connections_mutations/handlers.py", "grouped_terms = ["),
    ("aria/modules/chat_surface/catalog.py", "_build_suggested_toolbox_group"),
    ("aria/modules/chat_surface/catalog.py", "_score_chat_command_entry"),
    ("aria/modules/connections_catalog/catalog.py", "connection_toolbox_keywords"),
    ("aria/modules/recipes_ui/stored_ui.py", "\"keywords\":"),
    ("aria/modules/memory_learning_bridge/skill.py", "_recall_keyword_fallback"),
    ("aria/modules/memory_learning_bridge/skill.py", "_memory_skill_terms"),
    ("aria/modules/memory_learning_bridge/skill.py", "match_stopwords"),
    ("aria/modules/memory_learning_bridge/skill.py", "_document_rows_match_query_terms"),
    ("aria/modules/memory_learning_bridge/skill.py", "exact_personal_claim_value"),
    ("aria/modules/notes/chat_flows.py", "lowered in note.title.lower()"),
    ("aria/i18n/de.json", "config_skill_routing"),
    ("aria/i18n/en.json", "config_skill_routing"),
    ("docs/product/architecture-summary.md", "router_keywords"),
)


AUTHORITY_CHAIN_BOUNDARIES: tuple[AuthorityChainBoundary, ...] = (
    AuthorityChainBoundary(
        "connection_target_selection",
        "routing_admin.resolve_connection_routing_chain",
        "connection_target",
        "contract_bound",
        "turn_contract_or_bounded_llm",
        "clean",
        "No authoritative routing target was selected.",
        "Qdrant and configured metadata provide candidates; they never choose the target.",
    ),
    AuthorityChainBoundary(
        "memory_retrieval_failure",
        "memory_learning_bridge.skill.MemorySkill",
        "semantic_retrieval_failure",
        "validation_only",
        "fail_closed",
        "clean",
        "memory_semantic_retrieval_failed",
        "Embedding/vector failure is reported and never replaced by keyword-scored user data.",
    ),
)


def authority_chain_boundary_map() -> dict[str, AuthorityChainBoundary]:
    return {boundary.boundary_id: boundary for boundary in AUTHORITY_CHAIN_BOUNDARIES}


def red_authority_boundaries() -> tuple[AuthorityChainBoundary, ...]:
    return tuple(boundary for boundary in AUTHORITY_CHAIN_BOUNDARIES if boundary.manifest_class.startswith("red_"))
