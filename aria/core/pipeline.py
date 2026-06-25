from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from functools import wraps
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.core.action_plan import ActionPlan, CapabilityDraft, MemoryHints, build_action_plan
from aria.core.action_candidate_taxonomy import is_recipe_candidate_kind
from aria.core.action_candidate_taxonomy import normalize_action_candidate_kind
from aria.core.action_planner import debug_bounded_action_plan_decision
from aria.core.agentic_content_access import content_access_request_from_action_plan
from aria.core.agentic_content_access_registry import AgenticContentAccessRegistry
from aria.core.agentic_capability_execution import GenericCapabilityExecutionHandler
from aria.core.agentic_capability_execution import GenericCapabilityExecutionHooks
from aria.core.agentic_prompt_flow import AGENTIC_BOUNDARY_CONTEXT
from aria.core.agentic_prompt_flow import AGENTIC_BOUNDARY_DRAFT
from aria.core.agentic_prompt_flow import agentic_context_debug_line
from aria.core.agentic_prompt_flow import agentic_prompt_flow_debug_line
from aria.core.agentic_prompt_flow import build_agentic_prompt_flow
from aria.core.agentic_execution import AgenticExecutionHandler
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution_learning import AgenticExecutionLearningService
from aria.core.agentic_execution_learning import auto_learning_suppressed
from aria.core.agentic_execution_registry import AgenticExecutionRegistry
from aria.core.agentic_context_runtime import AgenticContextRuntimeMixin
from aria.core.aria_turn_arbitration import AriaTurnArbiter
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnCollectionOption
from aria.core.aria_turn_arbitration import AriaTurnPlan
from aria.core.aria_turn_arbitration import build_aria_turn_menu
from aria.core.agentic_rss_execution import RSSFeedExecutionHandler
from aria.core.agentic_rss_execution import RSSFeedExecutionHooks
from aria.core.agentic_ssh_execution import MultiTargetSSHExecutionHandler
from aria.core.agentic_ssh_execution import MultiTargetSSHExecutionHooks
from aria.core.blocked_action_explanation import explain_blocked_action
from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.bounded_planner import debug_bounded_planner_decision
from aria.core.capability_catalog import (
    capability_executor_kinds,
    capability_matches_connection_kind,
    normalize_capability,
)
from aria.core.capability_context import CapabilityContextStore
from aria.core.capability_router import CapabilityRouter
from aria.core.chat_context_filter import explicitly_requests_local_context
from aria.core.chat_context_filter import filter_chat_context_skill_results
from aria.core.chat_context_filter import looks_like_general_diagnostic_or_advice_request
from aria.core.chat_context_filter import skill_result_is_local_memory_context
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.connection_catalog import connection_kind_label
from aria.core.connection_catalog import connection_routing_spec
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_catalog import ordered_connection_kinds
from aria.core.connection_dossiers import build_file_target_dossier
from aria.core.connection_dossiers import build_http_api_target_dossier
from aria.core.connection_dossiers import build_message_target_dossier
from aria.core.connection_dossiers import build_read_target_dossier
from aria.core.connection_dossiers import with_capability_draft_updates
from aria.core.connection_semantic_resolver import ConnectionSemanticResolver
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.connection_semantic_resolver import SemanticConnectionHint
from aria.core.connection_semantic_resolver import build_connection_aliases
from aria.core.connection_semantic_resolver import build_routing_decision_record
from aria.core.connection_semantic_resolver import connection_label_match_score
from aria.core.connection_semantic_resolver import format_routing_decision_record
from aria.core.connection_semantic_resolver import message_has_connection_disambiguation_terms
from aria.core.connection_semantic_resolver import normalize_connection_alias
from aria.core.connection_semantic_resolver import split_connection_tokens
from aria.core.connection_action_contract import connection_action_direct_gate_executor_kinds
from aria.core.connection_action_contract import connection_action_executor_bindings
from aria.core.connection_action_contract import connection_action_executor_kinds
from aria.core.config import RoutingLanguageConfig, Settings
from aria.core.context import ContextAssembler
from aria.core.context_surfaces import ContextRequest
from aria.core.context_surfaces import RuntimeOutcomeFrame
from aria.core.context_surfaces import TurnFrame
from aria.core.routing_index import RoutingIndexStore
from aria.core.embedding_client import EmbeddingClient
from aria.core.error_interpreter import ErrorInterpreter
from aria.core.execution_dry_run import (
    build_execution_preview_dry_run,
    build_payload_dry_run,
    evaluate_guardrail_confirm_dry_run,
)
from aria.core.execution_dry_run_payloads import connection_row as payload_connection_row
from aria.core.execution_dry_run_payloads import read_row_value
from aria.core.artifact_review_patterns import recall_artifact_review_patterns
from aria.core.host_artifact_learning import host_artifact_discovery_outcome_events
from aria.core.http_api_agentic_resolution import apply_agentic_http_api_resolution as core_apply_agentic_http_api_resolution
from aria.core.http_api_policy import HTTPAPIPolicyDecision
from aria.core.file_agentic_resolution import apply_agentic_file_operation_resolution as core_apply_agentic_file_operation_resolution
from aria.core.messaging_agentic_resolution import apply_agentic_message_operation_resolution as core_apply_agentic_message_operation_resolution
from aria.core.read_agentic_resolution import apply_agentic_read_operation_resolution as core_apply_agentic_read_operation_resolution
from aria.core.read_agentic_resolution import read_draft_is_complete
from aria.core.i18n import I18NStore
from aria.core.inventory_index import InventoryIndexStore
from aria.core.inventory_index import create_inventory_qdrant_client
from aria.core.inventory_index import inventory_collection_name
from aria.core.executor_registry import ExecutorRegistry
from aria.core.agentic_runtime_debug import runtime_debug_line_for_plan
from aria.core.learned_recipe_integration import record_routed_stored_recipe_success
from aria.core.learned_recipe_curator import curate_learned_recipe_entry
from aria.core.learned_recipe_store_updates import record_successful_learned_recipe_execution
from aria.core.learning_outcomes import active_learning_hint_outcome_event
from aria.core.learning_outcomes import capture_learning_outcome
from aria.core.learning_outcomes import capture_web_search_learning_outcome
from aria.core.learning_outcomes import connection_action_outcome_event
from aria.core.learning_outcomes import recipe_catalog_outcome_event
from aria.core.learning_worker import enqueue_learning_job
from aria.core.pipeline_learning_helpers import PipelineLearningHelpersMixin
from aria.core.pipeline_recipe_helpers import PipelineRecipeHelpersMixin
from aria.core.pipeline_ssh_helpers import PipelineSSHHelpersMixin
from aria.core.pipeline_recipe_experience import format_recipe_experience_context
from aria.core.pipeline_recipe_experience import recipe_experience_context
from aria.core.pipeline_recipe_experience import recipe_experience_context_rows
from aria.core.pipeline_recipe_experience import recipe_experience_debug_lines
from aria.core.recipe_experience_memory import search_recipe_experience_memory
from aria.core.recipe_experience_memory import store_recipe_experience_memory
from aria.core.llm_client import LLMClient
from aria.core.memory_assist import MemoryAssistResolver
from aria.core.stage_timing import StageTimingLedger
from aria.core.pipeline_action_flow_helpers import append_debug_detail_lines
from aria.core.pipeline_action_flow_helpers import build_pending_action_state
from aria.core.pipeline_action_flow_helpers import build_routed_confirmation_text
from aria.core.pipeline_action_flow_helpers import build_routed_missing_input_text
from aria.core.pipeline_action_flow_helpers import payload_missing_fields
from aria.core.pipeline_action_flow_helpers import pending_payload_intents
from aria.core.pipeline_action_flow_helpers import resolve_pending_missing_input
from aria.core.pipeline_action_flow_helpers import resolved_next_step
from aria.core.pipeline_action_flow_helpers import resolved_routing_detail_lines
from aria.core.pipeline_action_flow_helpers import routed_action_intents
from aria.core.pipeline_action_flow_helpers import routing_reason_text
from aria.core.pipeline_capability_execution import PipelineCapabilityExecutor
from aria.core.pipeline_capability_details import build_pipeline_capability_detail_lines
from aria.core.pipeline_capability_details import default_mqtt_topic_from_settings
from aria.core.pipeline_capability_execution import website_rows_from_settings
from aria.core.pipeline_capability_messages import capability_execution_error_code
from aria.core.pipeline_capability_messages import format_capability_execution_error
from aria.core.pipeline_capability_messages import format_capability_missing_message
from aria.core.pipeline_capability_messages import sanitize_capability_error
from aria.core.pipeline_models import PipelineResult
from aria.core.pipeline_qdrant_helpers import qdrant_ask_on_low_confidence
from aria.core.pipeline_qdrant_helpers import qdrant_routing_enabled
from aria.core.pipeline_qdrant_helpers import qdrant_routing_limit
from aria.core.pipeline_qdrant_helpers import qdrant_routing_threshold
from aria.core.pipeline_qdrant_helpers import resolve_live_routing_chain as core_resolve_live_routing_chain
from aria.core.pipeline_qdrant_helpers import resolve_qdrant_connection_hint as core_resolve_qdrant_connection_hint
from aria.core.pipeline_qdrant_helpers import settings_without_qdrant_routing
from aria.core.pipeline_routing_debug_helpers import append_routing_record_to_resolved
from aria.core.pipeline_routing_debug_helpers import attach_connection_candidates_debug
from aria.core.prompt_loader import PromptLoader
from aria.core.pipeline_routing_debug_helpers import resolved_routing_chain_has_signal
from aria.core.pipeline_routing_debug_helpers import routing_debug_line
from aria.core.pipeline_routing_debug_helpers import routing_candidates_from_resolved
from aria.core.pipeline_routing_debug_helpers import serialize_connection_candidates
from aria.core.learning_promotion import learning_active_hints_collection_for_user
from aria.core.pipeline_turn_stages import PipelineTurnStagesMixin
from aria.core.pricing_catalog import resolve_pricing_entry
from aria.core.planner_candidates import build_connection_planner_input_set
from aria.core.planner_candidates import build_planner_input_set
from aria.core.planner_candidates import merge_planner_input_sets
from aria.core.planner_candidates import planner_candidate_from_action_payload
from aria.core.planner_candidates import planner_candidate_from_connection_payload
from aria.core.planner_candidates import planner_input_set_to_dict
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.recipe_runtime_contract import RECIPE_MANIFEST_MISSING_ERROR
from aria.core.recipe_runtime_contract import build_recipe_intent
from aria.core.recipe_runtime_contract import build_recipe_runtime_skill_name
from aria.core.recipe_result_view import friendly_recipe_error_text
from aria.core.router import KeywordRouter
from aria.core.router import RouterDecision
from aria.core.routing_admin import ensure_connection_routing_index_ready
from aria.core.routing_admin import resolve_connection_routing_chain
from aria.core.routing_admin import routing_connections_collection_name
from aria.core.routing_index import DEFAULT_CONNECTION_ROUTING_KINDS
from aria.core.routing_resolver import infer_preferred_connection_kind
from aria.core.routing_resolver import RoutingResolver
from aria.core.rss_digest_options import build_rss_digest_options_note
from aria.core.rss_digest_options import infer_rss_digest_options
from aria.core.rss_grouping import build_rss_status_groups
from aria.core.safe_fix import SafeFixExecutor, build_safe_fix_plan, extract_held_packages, format_held_packages_summary
from aria.core.turn_intent_arbitration import TurnIntentArbiter
from aria.core.recipe_runtime import (
    RecipeRuntime,
    build_recipe_status_text,
    load_recipe_toggles,
    load_stored_recipe_runtime,
    match_recipe_intents,
    match_stored_recipe_intents,
    normalize_recipe_keywords,
    normalize_recipe_steps,
    render_step_template,
    resolve_recipe_intent_with_llm,
    resolve_stored_recipe_intent_with_llm,
    sanitize_recipe_id,
    scored_stored_recipe_rows,
    should_skip_recipe_auto_memory_persist,
)
from aria.core.ssh_runtime import SSHRuntime
from aria.core.ssh_policy import validate_ssh_readonly_policy
from aria.core.text_utils import extract_json_object as core_extract_json_object
from aria.core.text_utils import is_english
from aria.core.text_utils import localized_text

_PIPELINE_INPUT_PATTERNS_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "pipeline_input_patterns.json"


def _load_pipeline_input_patterns() -> dict[str, list[str]]:
    try:
        raw = json.loads(_PIPELINE_INPUT_PATTERNS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load pipeline input patterns: {_PIPELINE_INPUT_PATTERNS_PATH}") from exc
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): [str(value) for value in values if str(value).strip()]
        for key, values in raw.items()
        if isinstance(values, list)
    }


_PIPELINE_INPUT_PATTERNS = _load_pipeline_input_patterns()
from aria.core.usage_meter import UsageMeter
from aria.skills.base import SkillResult
from aria.skills.memory import MemorySkill
from aria.skills.web_search import WebSearchSkill

_PIPELINE_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _pipeline_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _PIPELINE_I18N.t(language or "de", f"pipeline.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


_RSS_GROUP_BUNDLE_PREFIX = "__rss_group_bundle__:"


def _pre_rag_usage_scope(func: Any) -> Any:
    @wraps(func)
    async def wrapper(
        self: "Pipeline",
        message: str,
        user_id: str,
        *,
        request_id: str,
        source: str,
        decision: Any,
        start: float,
        runtime_recipes: list[dict[str, Any]],
        auto_memory_enabled: bool = False,
        language: str | None = None,
        seed_capability_draft: Any | None = None,
        semantic_source: str = "",
    ) -> tuple[PipelineResult | None, list[str], Any | None]:
        with self.usage_meter.scope(
            request_id=request_id,
            user_id=user_id,
            source=source,
            router_level=int(getattr(decision, "level", 0) or 0),
        ):
            result, custom_intents, capability_draft = await func(
                self,
                message,
                user_id,
                request_id=request_id,
                source=source,
                decision=decision,
                start=start,
                runtime_recipes=runtime_recipes,
                auto_memory_enabled=auto_memory_enabled,
                language=language,
                seed_capability_draft=seed_capability_draft,
                semantic_source=semantic_source,
            )
            if result is None:
                usage_snapshot = self._current_usage_snapshot()
                usage = dict(usage_snapshot.get("usage", {}) or {})
                embedding_usage = dict(usage_snapshot.get("embedding_usage", {}) or {})
                if int(usage.get("total_tokens", 0) or 0) > 0 or int(embedding_usage.get("total_tokens", 0) or 0) > 0:
                    await self.token_tracker.log(
                        request_id=request_id,
                        user_id=user_id,
                        intents=["agentic:pre_rag_no_action"],
                        router_level=int(getattr(decision, "level", 0) or 0),
                        usage=usage,
                        chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
                        embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
                        embedding_usage=embedding_usage,
                        chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
                        embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
                        total_cost_usd=usage_snapshot.get("total_cost_usd"),
                        duration_ms=int((time.perf_counter() - start) * 1000),
                        source=source,
                        skill_errors=[],
                        extraction_model="pre_rag_action_gate",
                        extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                    )
            return result, custom_intents, capability_draft

    return wrapper


class Pipeline(AgenticContextRuntimeMixin, PipelineLearningHelpersMixin, PipelineRecipeHelpersMixin, PipelineSSHHelpersMixin, PipelineTurnStagesMixin):
    """Session 2 Pipeline: Load -> Route -> Skills -> Context -> LLM -> Track."""

    def __init__(
        self,
        settings: Settings,
        prompt_loader: PromptLoader,
        llm_client: LLMClient,
        capability_context_store: CapabilityContextStore | None = None,
        usage_meter: UsageMeter | None = None,
        embedding_client: EmbeddingClient | None = None,
    ):
        self.settings = settings
        self.prompt_loader = prompt_loader
        self.llm_client = llm_client
        self.usage_meter = usage_meter or UsageMeter(settings)
        if hasattr(self.llm_client, "usage_meter") and getattr(self.llm_client, "usage_meter", None) is None:
            self.llm_client.usage_meter = self.usage_meter
        self.embedding_client = embedding_client or EmbeddingClient(settings.embeddings, usage_meter=self.usage_meter)

        self.router = KeywordRouter(settings.routing.for_language(None))
        self.capability_router = CapabilityRouter()
        self.capability_context_store = capability_context_store
        self.context_assembler = ContextAssembler()
        self.token_tracker = self.usage_meter.token_tracker

        self.memory_skill: MemorySkill | None = None
        if settings.memory.enabled and settings.memory.backend.lower() == "qdrant":
            self.memory_skill = MemorySkill(
                memory=settings.memory,
                embeddings=settings.embeddings,
                embedding_client=self.embedding_client,
                usage_meter=self.usage_meter,
            )
        self.web_search_skill: WebSearchSkill | None = None
        searxng_rows = getattr(getattr(settings, "connections", object()), "searxng", {})
        if isinstance(searxng_rows, dict) and bool(searxng_rows):
            self.web_search_skill = WebSearchSkill(settings=self.settings)
        self._project_root = Path(__file__).resolve().parents[2]
        self._stored_recipes_dir = self._project_root / "data" / "recipes"
        self._config_path = self._project_root / "config" / "config.yaml"
        self._error_interpreter = ErrorInterpreter(self._project_root / "config" / "error_interpreter.yaml")
        self._stored_recipe_cache: dict[str, Any] = {"sign": None, "rows": []}
        self._ssh_runtime = SSHRuntime(
            settings=self.settings,
            error_interpreter=self._error_interpreter,
            normalize_spaces=self._normalize_spaces,
            truncate_text=self._truncate_text,
            extract_held_packages=extract_held_packages,
        )
        self._safe_fix_executor = SafeFixExecutor(self._execute_custom_ssh_command)
        self._recipe_runtime = RecipeRuntime(
            settings=self.settings,
            llm_client=self.llm_client,
            memory_skill_getter=lambda: self.memory_skill,
            web_search_skill_getter=lambda: self.web_search_skill,
            execute_custom_ssh_command=self._execute_custom_ssh_command,
            extract_memory_store_text=self._extract_memory_store_text,
            extract_memory_recall_query=self._extract_memory_recall_query,
            extract_web_search_query=self._extract_web_search_query,
            facts_collection_for_user=self._facts_collection_for_user,
            preferences_collection_for_user=self._preferences_collection_for_user,
            normalize_spaces=self._normalize_spaces,
            truncate_text=self._truncate_text,
        )
        self._skill_runtime = self._recipe_runtime
        self._memory_assist = MemoryAssistResolver(lambda: self.memory_skill, lambda: self.capability_context_store)
        self._semantic_connection_resolver = ConnectionSemanticResolver(self.llm_client)
        self._capability_executor = PipelineCapabilityExecutor(
            skill_runtime=self._skill_runtime,
            execute_custom_ssh_command=lambda **kwargs: self._execute_custom_ssh_command(**kwargs),
            parse_rss_group_bundle_note=self._parse_rss_group_bundle_note,
            call_with_optional_language=self._call_with_optional_language,
            website_rows=self._website_rows,
            default_mqtt_topic=self._default_mqtt_topic,
            msg=self._msg,
            normalize_spaces=self._normalize_spaces,
            extract_json_object=self._extract_json_object,
        )
        self._executor_registry = ExecutorRegistry()
        for connection_kind, capability in connection_action_executor_bindings():
            handler = getattr(self._capability_executor, f"execute_{capability}", None)
            if handler is not None:
                self._executor_registry.register(connection_kind, capability, handler)
        self._content_access_registry = AgenticContentAccessRegistry([])
        self._aria_turn_frames: dict[str, TurnFrame] = {}
        self._runtime_outcome_frames: dict[str, RuntimeOutcomeFrame] = {}
        self._last_meta_catalog_fallback_debug_lines: list[str] = []

    @staticmethod
    def _connection_kind_label(kind: str) -> str:
        return connection_kind_label(kind)

    @staticmethod
    def _is_english(language: str | None) -> bool:
        return is_english(language)

    @classmethod
    def _msg(cls, language: str | None, de: str, en: str) -> str:
        return localized_text(language, de=de, en=en)

    def _load_recent_capability_context(self, user_id: str) -> dict[str, Any]:
        if self.capability_context_store is None:
            return {}
        try:
            row = self.capability_context_store.load_recent(user_id)
        except Exception:
            return {}
        return row if isinstance(row, dict) else {}

    @staticmethod
    def _looks_like_calendar_followup_message(message: str) -> bool:
        clean = re.sub(r"\s+", " ", str(message or "")).strip().lower()
        if not clean:
            return False
        if any(token in clean for token in ("kalender", "calendar")):
            return False
        spec = connection_routing_spec("google_calendar")
        if any(term in clean for term in spec.follow_up_time_terms):
            return True
        if any(clean == term or clean.startswith(term + " ") for term in spec.follow_up_starter_terms) and len(clean.split()) <= 8:
            return True
        if '"' in clean or "“" in clean or "”" in clean:
            return True
        return bool(re.search(r"\b(termine|events|meetings?|appointments?)\b", clean))

    def _rewrite_calendar_followup_message(self, message: str, user_id: str) -> str:
        clean_message = str(message or "").strip()
        if not clean_message:
            return clean_message
        if self.capability_router._looks_like_calendar_request(clean_message):
            return clean_message
        if not self._looks_like_calendar_followup_message(clean_message):
            return clean_message
        recent = self._load_recent_capability_context(user_id)
        if str(recent.get("capability", "") or "").strip() != "calendar_read":
            return clean_message
        recent_filter = str(recent.get("content", "") or "").strip()
        current_filter = str(self.capability_router._extract_calendar_search(clean_message) or "").strip()
        spec = connection_routing_spec("google_calendar")
        rewrite_prefix = spec.follow_up_rewrite_prefix or "Kalender"
        rewritten = f"{rewrite_prefix} {clean_message}"
        if recent_filter and not current_filter:
            lower = clean_message.lower()
            if any(term in lower for term in spec.follow_up_time_terms):
                rewritten += f" mit {recent_filter}"
        return rewritten

    @staticmethod
    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        return core_extract_json_object(text) or {}

    def _build_http_api_target_dossier(self, connection_ref: str, *, user_id: str = "") -> dict[str, Any]:
        rows = getattr(getattr(self.settings, "connections", object()), "http_api", {})
        if not isinstance(rows, dict):
            return {}
        row = rows.get(str(connection_ref or "").strip())
        if row is None:
            return {}
        recent = self._load_recent_capability_context(user_id)
        return build_http_api_target_dossier(rows, connection_ref, recent_context=recent)

    def _build_file_target_dossier(self, connection_kind: str, connection_ref: str, *, user_id: str = "") -> dict[str, Any]:
        clean_kind = normalize_connection_kind(connection_kind)
        rows = getattr(getattr(self.settings, "connections", object()), clean_kind, {})
        if not isinstance(rows, dict):
            return {}
        recent = self._load_recent_capability_context(user_id) if user_id else {}
        return build_file_target_dossier(
            rows,
            connection_ref,
            connection_kind=clean_kind,
            recent_context=recent,
        )

    def _build_message_target_dossier(self, connection_kind: str, connection_ref: str, *, user_id: str = "") -> dict[str, Any]:
        clean_kind = normalize_connection_kind(connection_kind)
        rows = getattr(getattr(self.settings, "connections", object()), clean_kind, {})
        if not isinstance(rows, dict):
            return {}
        recent = self._load_recent_capability_context(user_id) if user_id else {}
        return build_message_target_dossier(
            rows,
            connection_ref,
            connection_kind=clean_kind,
            recent_context=recent,
        )

    def _build_read_target_dossier(self, connection_kind: str, connection_ref: str, *, user_id: str = "") -> dict[str, Any]:
        clean_kind = normalize_connection_kind(connection_kind)
        rows = getattr(getattr(self.settings, "connections", object()), clean_kind, {})
        if clean_kind == "website":
            rows = self._website_rows()
        if not isinstance(rows, dict):
            return {}
        recent = self._load_recent_capability_context(user_id) if user_id else {}
        return build_read_target_dossier(
            rows,
            connection_ref,
            connection_kind=clean_kind,
            recent_context=recent,
        )

    async def _apply_agentic_http_api_resolution(
        self,
        *,
        message: str,
        plan: ActionPlan,
        user_id: str = "",
        language: str | None = None,
        llm_client: Any | None = None,
    ) -> tuple[ActionPlan, list[str], HTTPAPIPolicyDecision | None]:
        return await core_apply_agentic_http_api_resolution(
            client=self.llm_client if llm_client is None else llm_client,
            settings=self.settings,
            message=message,
            plan=plan,
            user_id=user_id,
            language=language,
            build_http_api_target_dossier=self._build_http_api_target_dossier,
            extract_json_object=self._extract_json_object,
            routing_debug_enabled=self._routing_debug_enabled,
        )

    async def _apply_agentic_file_operation_resolution(
        self,
        *,
        message: str,
        user_id: str = "",
        routing_decision: dict[str, Any] | None = None,
        action_debug: dict[str, Any] | None = None,
        capability_draft: Any | None = None,
        language: str | None = None,
        llm_client: Any | None = None,
    ) -> tuple[dict[str, Any], Any | None, str]:
        return await core_apply_agentic_file_operation_resolution(
            client=self.llm_client if llm_client is None else llm_client,
            message=message,
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=capability_draft,
            language=language,
            build_file_target_dossier=self._build_file_target_dossier,
            extract_json_object=self._extract_json_object,
            routing_debug_enabled=self._routing_debug_enabled,
            with_capability_draft_updates=with_capability_draft_updates,
        )

    async def _apply_agentic_message_operation_resolution(
        self,
        *,
        message: str,
        user_id: str = "",
        routing_decision: dict[str, Any] | None = None,
        action_debug: dict[str, Any] | None = None,
        capability_draft: Any | None = None,
        language: str | None = None,
        llm_client: Any | None = None,
    ) -> tuple[dict[str, Any], Any | None, str]:
        return await core_apply_agentic_message_operation_resolution(
            client=self.llm_client if llm_client is None else llm_client,
            message=message,
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=capability_draft,
            language=language,
            build_message_target_dossier=self._build_message_target_dossier,
            extract_json_object=self._extract_json_object,
            routing_debug_enabled=self._routing_debug_enabled,
            with_capability_draft_updates=with_capability_draft_updates,
        )

    async def _apply_agentic_read_operation_resolution(
        self,
        *,
        message: str,
        user_id: str = "",
        routing_decision: dict[str, Any] | None = None,
        action_debug: dict[str, Any] | None = None,
        capability_draft: Any | None = None,
        language: str | None = None,
        llm_client: Any | None = None,
    ) -> tuple[dict[str, Any], Any | None, str]:
        return await core_apply_agentic_read_operation_resolution(
            client=self.llm_client if llm_client is None else llm_client,
            message=message,
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=capability_draft,
            language=language,
            build_read_target_dossier=self._build_read_target_dossier,
            extract_json_object=self._extract_json_object,
            routing_debug_enabled=self._routing_debug_enabled,
            with_capability_draft_updates=with_capability_draft_updates,
        )

    async def _refresh_resolved_agentic_file_operation(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str = "",
        capability_draft: Any | None = None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        routing_decision = dict(resolved.get("decision", {}) or {})
        if normalize_connection_kind(str(routing_decision.get("kind", "") or "")) not in {"sftp", "smb"}:
            return resolved, capability_draft
        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        capability = str(payload.get("capability", "") or getattr(capability_draft, "capability", "") or action_decision.get("capability", "") or "").strip()
        if capability not in {"file_list", "file_read", "file_write", ""}:
            return resolved, capability_draft
        working_draft = capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(
                capability=capability,
                connection_kind=str(routing_decision.get("kind", "") or payload.get("connection_kind", "") or "").strip(),
                explicit_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
                requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
                path=str(payload.get("path", "") or "").strip(),
                content=str(payload.get("content", "") or "").strip(),
                plan_class=str(payload.get("plan_class", "") or action_decision.get("plan_class", "") or "").strip(),
                behavior_profile=str(payload.get("behavior_profile", "") or action_decision.get("behavior_profile", "") or "").strip(),
            )
        updated_action_debug, updated_draft, debug_line = await self._apply_agentic_file_operation_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
            llm_client=self.llm_client,
        )
        resolved["action_debug"] = updated_action_debug
        refreshed_payload = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
        )
        refreshed_payload = self._apply_capability_draft_overrides(
            refreshed_payload,
            capability_draft=updated_draft,
        )
        resolved["payload_debug"] = refreshed_payload
        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=refreshed_payload,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
            payload_debug=refreshed_payload,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, debug_line)
        return resolved, updated_draft

    async def _refresh_resolved_agentic_message_operation(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str = "",
        capability_draft: Any | None = None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        routing_decision = dict(resolved.get("decision", {}) or {})
        if normalize_connection_kind(str(routing_decision.get("kind", "") or "")) not in {"discord", "webhook", "email", "mqtt"}:
            return resolved, capability_draft
        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        capability = str(payload.get("capability", "") or getattr(capability_draft, "capability", "") or action_decision.get("capability", "") or "").strip()
        if capability not in {"discord_send", "webhook_send", "email_send", "mqtt_publish", ""}:
            return resolved, capability_draft
        working_draft = capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(
                capability=capability,
                connection_kind=str(routing_decision.get("kind", "") or payload.get("connection_kind", "") or "").strip(),
                explicit_connection_ref=str(routing_decision.get("ref", "") or payload.get("connection_ref", "") or "").strip(),
                requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
                path=str(payload.get("path", "") or "").strip(),
                content=str(payload.get("content", "") or "").strip(),
                plan_class=str(payload.get("plan_class", "") or action_decision.get("plan_class", "") or "").strip(),
                behavior_profile=str(payload.get("behavior_profile", "") or action_decision.get("behavior_profile", "") or "").strip(),
            )
        updated_action_debug, updated_draft, debug_line = await self._apply_agentic_message_operation_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
            llm_client=self.llm_client,
        )
        resolved["action_debug"] = updated_action_debug
        refreshed_payload = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
        )
        refreshed_payload = self._apply_capability_draft_overrides(
            refreshed_payload,
            capability_draft=updated_draft,
        )
        resolved["payload_debug"] = refreshed_payload
        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=refreshed_payload,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
            payload_debug=refreshed_payload,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, debug_line)
        return resolved, updated_draft

    async def _refresh_resolved_agentic_read_operation(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str = "",
        capability_draft: Any | None = None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        routing_decision = dict(resolved.get("decision", {}) or {})
        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        capability = str(payload.get("capability", "") or getattr(capability_draft, "capability", "") or action_decision.get("capability", "") or "").strip()
        if capability not in {"feed_read", "calendar_read", "mail_read", "mail_search", "website_read", "website_list"}:
            return resolved, capability_draft
        working_draft = capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(
                capability=capability,
                connection_kind=str(routing_decision.get("kind", "") or payload.get("connection_kind", "") or "").strip(),
                explicit_connection_ref=str(routing_decision.get("ref", "") or payload.get("connection_ref", "") or "").strip(),
                requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
                path=str(payload.get("path", "") or "").strip(),
                content=str(payload.get("content", "") or "").strip(),
                plan_class=str(payload.get("plan_class", "") or action_decision.get("plan_class", "") or "").strip(),
                behavior_profile=str(payload.get("behavior_profile", "") or action_decision.get("behavior_profile", "") or "").strip(),
            )
        else:
            working_draft = with_capability_draft_updates(
                working_draft,
                capability=str(getattr(working_draft, "capability", "") or capability).strip(),
                connection_kind=str(getattr(working_draft, "connection_kind", "") or routing_decision.get("kind", "") or payload.get("connection_kind", "") or "").strip(),
                explicit_connection_ref=str(getattr(working_draft, "explicit_connection_ref", "") or payload.get("requested_connection_ref", "") or "").strip(),
                path=str(getattr(working_draft, "path", "") or payload.get("path", "") or "").strip(),
                content=str(getattr(working_draft, "content", "") or payload.get("content", "") or "").strip(),
                plan_class=str(getattr(working_draft, "plan_class", "") or payload.get("plan_class", "") or action_decision.get("plan_class", "") or "").strip(),
                behavior_profile=str(getattr(working_draft, "behavior_profile", "") or payload.get("behavior_profile", "") or action_decision.get("behavior_profile", "") or "").strip(),
            )
        if read_draft_is_complete(
            capability=str(getattr(working_draft, "capability", "") or capability).strip(),
            selector=str(getattr(working_draft, "path", "") or "").strip(),
            query=str(getattr(working_draft, "content", "") or "").strip(),
        ):
            return resolved, working_draft
        updated_action_debug, updated_draft, debug_line = await self._apply_agentic_read_operation_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
            llm_client=self.llm_client,
        )
        resolved["action_debug"] = updated_action_debug
        refreshed_payload = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
        )
        refreshed_payload = self._apply_capability_draft_overrides(
            refreshed_payload,
            capability_draft=updated_draft,
        )
        resolved["payload_debug"] = refreshed_payload
        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=refreshed_payload,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
            payload_debug=refreshed_payload,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, debug_line)
        return resolved, updated_draft

    @staticmethod
    def _build_rss_group_bundle_note(group_name: str, refs: list[str]) -> str:
        payload = {
            "group": str(group_name or "").strip(),
            "refs": [str(item or "").strip() for item in list(refs or []) if str(item or "").strip()],
        }
        return _RSS_GROUP_BUNDLE_PREFIX + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _parse_rss_group_bundle_note(notes: list[str] | tuple[str, ...] | None) -> tuple[str, list[str]] | None:
        for item in list(notes or []):
            text = str(item or "").strip()
            if not text.startswith(_RSS_GROUP_BUNDLE_PREFIX):
                continue
            try:
                payload = json.loads(text[len(_RSS_GROUP_BUNDLE_PREFIX) :])
            except Exception:
                return None
            if not isinstance(payload, dict):
                return None
            group_name = str(payload.get("group", "") or "").strip()
            refs = [str(ref or "").strip() for ref in list(payload.get("refs", []) or []) if str(ref or "").strip()]
            if group_name and refs:
                return group_name, refs
        return None

    def _rss_group_bundle_from_config_groups(self, message: str, *, selected_ref: str = "") -> tuple[str, list[str]] | None:
        connection_rows = getattr(getattr(self.settings, "connections", object()), "rss", {})
        if not isinstance(connection_rows, dict):
            return None
        grouped: dict[str, list[str]] = {}
        for ref, row in connection_rows.items():
            clean_ref = str(ref or "").strip()
            if not clean_ref:
                continue
            if isinstance(row, dict):
                group_name = str(row.get("group_name", "") or "").strip()
            else:
                group_name = str(getattr(row, "group_name", "") or "").strip()
            if not group_name:
                continue
            grouped.setdefault(group_name, []).append(clean_ref)

        best: tuple[int, str, list[str]] | None = None
        clean_selected = str(selected_ref or "").strip()
        for group_name, refs in grouped.items():
            unique_refs = sorted({str(item or "").strip() for item in refs if str(item or "").strip()})
            if len(unique_refs) < 2:
                continue
            score = connection_label_match_score(message, group_name)
            if score <= 0:
                continue
            if clean_selected and clean_selected in unique_refs:
                score += 5
            candidate = (score, group_name, unique_refs)
            if best is None or candidate > best:
                best = candidate
        if best is None:
            return None
        _, group_name, refs = best
        return group_name, refs

    async def _rss_group_bundle_for_query(self, message: str, *, selected_ref: str = "") -> tuple[str, list[str]] | None:
        config_bundle = self._rss_group_bundle_from_config_groups(message, selected_ref=selected_ref)
        if config_bundle is not None:
            return config_bundle
        connection_rows = getattr(getattr(self.settings, "connections", object()), "rss", {})
        if not isinstance(connection_rows, dict):
            return None
        status_rows: list[dict[str, Any]] = []
        for ref, row in connection_rows.items():
            clean_ref = str(ref or "").strip()
            if not clean_ref:
                continue
            if isinstance(row, dict):
                feed_url = str(row.get("feed_url", "") or "").strip()
                group_name = str(row.get("group_name", "") or "").strip()
                title = str(row.get("title", "") or "").strip()
            else:
                feed_url = str(getattr(row, "feed_url", "") or "").strip()
                group_name = str(getattr(row, "group_name", "") or "").strip()
                title = str(getattr(row, "title", "") or "").strip()
            status_rows.append(
                {
                    "ref": clean_ref,
                    "target": feed_url,
                    "group_name": group_name,
                    "title": title,
                    "status": "ok",
                    "message": "ok",
                }
            )
        groups = await build_rss_status_groups(status_rows)
        grouped_rows: list[dict[str, Any]] = [row for row in list(groups or []) if isinstance(row, dict)]

        best: tuple[int, str, list[str]] | None = None
        clean_selected = str(selected_ref or "").strip()
        for row in grouped_rows:
            refs = [
                str(item.get("ref", "") or "").strip()
                for item in list(row.get("rows", []) or [])
                if isinstance(item, dict) and str(item.get("ref", "") or "").strip()
            ]
            if len(refs) < 2:
                continue
            group_name = str(row.get("name", "") or "").strip()
            score = connection_label_match_score(message, group_name)
            if score <= 0:
                continue
            if clean_selected and clean_selected in refs:
                score += 5
            candidate = (score, group_name, refs)
            if best is None or candidate > best:
                best = candidate
        if best is None:
            return None
        _, group_name, refs = best
        return group_name, refs

    @staticmethod
    def _rss_group_name_from_alias(alias: str) -> str:
        clean = normalize_connection_alias(alias)
        tokens = set(split_connection_tokens(clean))
        if "security" in tokens:
            return "Security"
        if "apple" in tokens:
            return "Apple"
        if "heise" in tokens:
            return "Heise"
        if {"project", "personal", "blog"} & tokens:
            return "Personal"
        if {"entwicklung", "developer", "developers", "development", "dev"} & tokens:
            return "Entwicklung"
        if {"tech", "news"} <= tokens or "tech" in tokens:
            return "News & Tech"
        return ""

    def _rss_group_bundle_from_candidate_aliases(
        self,
        message: str,
        *,
        selected_ref: str = "",
        candidate_rows: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[str]] | None:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in list(candidate_rows or []):
            if not isinstance(row, dict):
                continue
            kind = normalize_connection_kind(str(row.get("connection_kind", "") or ""))
            if kind != "rss":
                continue
            alias = normalize_connection_alias(str(row.get("alias", "") or ""))
            ref = str(row.get("connection_ref", "") or "").strip()
            if not alias or not ref:
                continue
            buckets.setdefault(alias, []).append(row)

        best: tuple[int, str, list[str]] | None = None
        clean_selected = str(selected_ref or "").strip()
        for alias, rows in buckets.items():
            refs = [str(item.get("connection_ref", "") or "").strip() for item in rows if str(item.get("connection_ref", "") or "").strip()]
            if len(refs) < 2:
                continue
            score = connection_label_match_score(message, alias)
            if score <= 0:
                continue
            if clean_selected and clean_selected in refs:
                score += 5
            group_name = self._rss_group_name_from_alias(alias) or alias.title()
            candidate = (score, group_name, sorted(set(refs)))
            if best is None or candidate > best:
                best = candidate
        if best is None:
            return None
        _, group_name, refs = best
        return group_name, refs

    async def _rss_digest_options_note_for_query(self, message: str, *, language: str = "") -> str:
        options = await infer_rss_digest_options(
            message,
            llm_client=self.llm_client,
            language=language,
        )
        return build_rss_digest_options_note(options)

    @staticmethod
    def _rss_candidates_need_semantic_refine(candidates: list[SemanticConnectionCandidate]) -> bool:
        rss_candidates = [item for item in list(candidates or []) if str(item.connection_kind or "").strip().lower() == "rss"]
        if len(rss_candidates) < 2:
            return False
        top_score = int(getattr(rss_candidates[0], "score", 0) or 0)
        second_score = int(getattr(rss_candidates[1], "score", 0) or 0)
        if top_score <= 0 or second_score <= 0:
            return False
        return top_score == second_score

    @staticmethod
    def _find_action_candidate_by_id(action_debug: dict[str, Any], *, candidate_kind: str, candidate_id: str) -> dict[str, Any] | None:
        clean_kind = normalize_action_candidate_kind(candidate_kind)
        clean_id = str(candidate_id or "").strip()
        for row in list(action_debug.get("candidates", []) or []):
            if not isinstance(row, dict):
                continue
            if normalize_action_candidate_kind(str(row.get("candidate_kind", "") or "").strip().lower()) != clean_kind:
                continue
            if str(row.get("candidate_id", "") or "").strip() != clean_id:
                continue
            return dict(row)
        return None

    @staticmethod
    def _call_with_optional_language(func: Any, *args: Any, language: str = "de", **kwargs: Any) -> Any:
        try:
            return func(*args, language=language, **kwargs)
        except TypeError as exc:
            message = str(exc)
            unexpected = re.search(r"unexpected keyword argument '([^']+)'", message)
            if not unexpected:
                raise
            bad_keyword = unexpected.group(1)
            if bad_keyword == "language":
                if kwargs:
                    try:
                        return func(*args, **kwargs)
                    except TypeError as retry_exc:
                        retry_unexpected = re.search(r"unexpected keyword argument '([^']+)'", str(retry_exc))
                        if retry_unexpected and retry_unexpected.group(1) in kwargs:
                            retry_kwargs = dict(kwargs)
                            retry_kwargs.pop(retry_unexpected.group(1), None)
                            return func(*args, **retry_kwargs)
                        raise
                return func(*args)
            if bad_keyword in kwargs:
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop(bad_keyword, None)
                return Pipeline._call_with_optional_language(
                    func,
                    *args,
                    language=language,
                    **retry_kwargs,
                )
            raise

    def _default_mqtt_topic(self, connection_ref: str) -> str:
        return default_mqtt_topic_from_settings(self.settings, connection_ref)

    def _build_capability_detail_lines(self, plan: ActionPlan, *, language: str | None = None) -> list[str]:
        return build_pipeline_capability_detail_lines(
            plan,
            settings=self.settings,
            parse_rss_group_bundle_note=self._parse_rss_group_bundle_note,
            truncate_text=self._truncate_text,
            language=language,
        )

    def _routing_debug_enabled(self) -> bool:
        return bool(getattr(getattr(self.settings, "ui", object()), "debug_mode", False))

    def _routing_debug_line(self, text: str) -> list[str]:
        return [text] if self._routing_debug_enabled() and str(text or "").strip() else []

    def _append_debug_detail_lines(self, resolved: dict[str, Any], *lines: str) -> dict[str, Any]:
        return append_debug_detail_lines(resolved, *lines, routing_debug_enabled=self._routing_debug_enabled())

    @staticmethod
    def _pipeline_text(language: str | None, key: str, default: str = "", **values: object) -> str:
        return _pipeline_text(language, key, default, **values)

    @staticmethod
    def _skill_errors(skill_results: list[SkillResult]) -> list[str]:
        return [str(result.error) for result in skill_results if not result.success and result.error]

    @staticmethod
    def _skill_failure_and_extraction_stats(skill_results: list[SkillResult]) -> tuple[list[str], str, dict[str, int]]:
        errors: list[str] = []
        extraction_model = "rule_based"
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
        for result in skill_results:
            if not result.success and result.error:
                errors.append(str(result.error))
            meta = result.metadata or {}
            extract_usage = meta.get("extraction_usage")
            if meta.get("extraction_model"):
                extraction_model = str(meta["extraction_model"])
            if not isinstance(extract_usage, dict):
                continue
            usage["prompt_tokens"] += int(extract_usage.get("prompt_tokens", 0) or 0)
            usage["completion_tokens"] += int(extract_usage.get("completion_tokens", 0) or 0)
            usage["total_tokens"] += int(extract_usage.get("total_tokens", 0) or 0)
            usage["calls"] += 1
        return errors, extraction_model, usage

    def _qdrant_routing_enabled(self) -> bool:
        return qdrant_routing_enabled(self.settings)

    def _qdrant_routing_limit(self) -> int:
        return qdrant_routing_limit(self.settings)

    def _qdrant_routing_threshold(self) -> float:
        return qdrant_routing_threshold(self.settings)

    def _qdrant_ask_on_low_confidence(self) -> bool:
        return qdrant_ask_on_low_confidence(self.settings)

    async def _resolve_qdrant_connection_hint(
        self,
        message: str,
        connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
        language: str | None = None,
    ) -> tuple[MemoryHints, list[str], bool]:
        del language
        return await core_resolve_qdrant_connection_hint(
            settings=self.settings,
            embedding_client=self.embedding_client,
            usage_meter=self.usage_meter,
            message=message,
            connection_pools=connection_pools,
            preferred_kind=preferred_kind,
            routing_debug_enabled=self._routing_debug_enabled(),
            create_async_qdrant_client_fn=create_async_qdrant_client,
            ensure_connection_routing_index_ready_fn=ensure_connection_routing_index_ready,
            routing_connections_collection_name_fn=routing_connections_collection_name,
            routing_index_store_cls=RoutingIndexStore,
        )

    @staticmethod
    def _collect_skill_detail_lines(skill_results: list[SkillResult]) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for result in skill_results:
            meta = result.metadata or {}
            raw_lines = meta.get("detail_lines")
            if not isinstance(raw_lines, list):
                continue
            for row in raw_lines:
                text = str(row).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                lines.append(text)
        return lines

    @staticmethod
    def _external_urls(message: str) -> list[str]:
        return [
            match.group(0).strip(" \t\r\n.,;!?")
            for match in re.finditer(r"https?://[^\s<>()\"']+", str(message or ""), flags=re.IGNORECASE)
            if match.group(0).strip(" \t\r\n.,;!?")
        ]

    @staticmethod
    def _recent_connection_refs(recent: dict[str, Any]) -> list[str]:
        refs = [
            str(item or "").strip()
            for item in list(recent.get("connection_refs", []) or [])
            if str(item or "").strip()
        ]
        if refs:
            return list(dict.fromkeys(refs))
        ref = str(recent.get("connection_ref", "") or "").strip()
        return [ref] if ref else []

    async def _llm_wants_recent_capability_context(
        self,
        message: str,
        *,
        recent: dict[str, Any],
        language: str | None = None,
    ) -> bool:
        if self.llm_client is None:
            return False
        refs = self._recent_connection_refs(recent)
        if not refs:
            return False
        prompt_payload = {
            "message": str(message or ""),
            "language": str(language or ""),
            "recent_runtime_context": {
                "capability": str(recent.get("capability", "") or ""),
                "connection_kind": str(recent.get("connection_kind", "") or ""),
                "connection_ref": str(recent.get("connection_ref", "") or ""),
                "connection_refs": refs,
                "content": str(recent.get("content", "") or ""),
                "result_summary": str(recent.get("result_summary", "") or ""),
            },
            "contract": (
                "Decide whether the user is asking about the immediately previous ARIA runtime action, "
                "its targets, command, or result. Return false for unrelated questions or requests for local notes/documents."
            ),
        }
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="recent_capability_context_relevance",
            system=(
                "You are a bounded relevance classifier. Return one JSON object only with "
                "use_context, confidence, reason. Do not answer the user and do not propose actions."
            ),
            payload=prompt_payload,
        )
        if not decision.ok:
            return False
        payload = decision.payload
        use_context = bool(payload.get("use_context"))
        confidence_raw = str(payload.get("confidence", "") or "").strip().lower()
        confidence = confidence_score(payload.get("confidence"))
        return use_context and confidence >= 0.55

    async def _recent_capability_context_skill_result(
        self,
        message: str,
        user_id: str,
        *,
        language: str | None = None,
    ) -> SkillResult | None:
        if self.capability_context_store is None or not user_id:
            return None
        try:
            recent = self.capability_context_store.load_recent(user_id)
        except Exception:
            return None
        if not isinstance(recent, dict) or not recent:
            return None
        refs = self._recent_connection_refs(recent)
        if not refs:
            return None
        if not await self._llm_wants_recent_capability_context(message, recent=recent, language=language):
            return None
        capability = str(recent.get("capability", "") or "").strip() or "unknown"
        kind = str(recent.get("connection_kind", "") or "").strip() or "unknown"
        command = str(recent.get("content", "") or "").strip()
        summary = str(recent.get("result_summary", "") or "").strip()
        runtime_effect = self._runtime_effect_for_recent_context(connection_kind=kind, command=command)
        lines = [
            "Recent ARIA runtime action:",
            f"- Capability: {capability}",
            f"- Connection kind: {kind}",
            f"- Targets: {', '.join(refs)}",
        ]
        if command:
            lines.append(f"- Command/content: {command}")
        if summary:
            lines.append(f"- Result summary: {summary}")
        detail = f"Kontext: letzte {connection_kind_label(kind)}-Ziele · {', '.join(refs)}"
        return SkillResult(
            skill_name="recent_capability_context",
            content="\n".join(lines),
            success=True,
            metadata={
                "detail_lines": [detail],
                "sources": [{"type": "recent_capability_context", "connection_kind": kind}],
                "connection_kind": kind,
                "command": command,
                "runtime_effect": runtime_effect,
            },
        )

    async def _message_wants_recent_runtime_context(
        self,
        message: str,
        user_id: str,
        *,
        language: str | None = None,
    ) -> bool:
        if self.capability_context_store is None or not user_id:
            return False
        try:
            recent = self.capability_context_store.load_recent(user_id)
        except Exception:
            return False
        if not isinstance(recent, dict) or not recent:
            return False
        if normalize_connection_kind(str(recent.get("connection_kind", "") or "")) != "ssh":
            return False
        if normalize_capability(str(recent.get("capability", "") or "")) != "ssh_command":
            return False
        return await self._llm_wants_recent_capability_context(message, recent=recent, language=language)

    @staticmethod
    def _runtime_effect_for_recent_context(*, connection_kind: str, command: str) -> str:
        kind = str(connection_kind or "").strip().lower()
        content = str(command or "").strip()
        if kind == "ssh" and content and validate_ssh_readonly_policy(content).action == "allow":
            return "read_only"
        return ""

    @staticmethod
    def _read_only_runtime_followup_instruction(skill_results: list[SkillResult]) -> str:
        has_read_only_context = any(
            result.skill_name == "recent_capability_context"
            and str((result.metadata or {}).get("runtime_effect", "") or "").strip() == "read_only"
            for result in skill_results
        )
        if not has_read_only_context:
            return ""
        return (
            "Operator follow-up policy: The recent runtime context has runtime_effect=read_only. "
            "If you offer a next step, keep it inspect-oriented and non-mutating. Prefer actions like listing affected items, "
            "showing per-target details, comparing results, or explaining impact. Do not offer state-changing operations "
            "such as updates, installs, restarts, deletes, writes, sends, or configuration changes unless the user explicitly asks for that operation."
        )

    @staticmethod
    def _local_context_summary_rows(skill_results: list[SkillResult], *, limit: int = 6) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for result in skill_results:
            if not skill_result_is_local_memory_context(result):
                continue
            meta = result.metadata or {}
            sources = meta.get("sources")
            source_parts: list[str] = []
            if isinstance(sources, list):
                for source in sources[:3]:
                    if not isinstance(source, dict):
                        continue
                    source_type = str(source.get("type", "") or "").strip()
                    name = str(source.get("document_name", "") or source.get("title", "") or source.get("collection", "") or "").strip()
                    if source_type or name:
                        source_parts.append(":".join(part for part in (source_type, name) if part))
            preview = " ".join(str(result.content or "").strip().split())[:280]
            rows.append(
                {
                    "skill_name": str(result.skill_name or "").strip(),
                    "sources": "; ".join(source_parts)[:240],
                    "preview": preview,
                }
            )
            if len(rows) >= max(1, limit):
                break
        return rows

    async def _llm_wants_local_chat_context(
        self,
        message: str,
        *,
        skill_results: list[SkillResult],
        intents: list[str],
        language: str | None = None,
    ) -> tuple[bool | None, str]:
        if self.llm_client is None:
            return None, "Routing Debug: chat_local_context_relevance skipped reason=no_llm_client"
        context_rows = self._local_context_summary_rows(skill_results)
        if not context_rows:
            return None, "Routing Debug: chat_local_context_relevance skipped reason=no_local_context_candidates"
        prompt_payload = {
            "message": str(message or ""),
            "language": str(language or ""),
            "intents": [str(intent or "") for intent in intents],
            "local_context_candidates": context_rows,
            "contract": (
                "Decide whether these local notes/documents/memory snippets are relevant context for answering the user. "
                "Return false for general how-to, current-version, broad diagnostic, or advice requests when the snippets are incidental. "
                "Return true when the user explicitly asks about their notes/documents/memory or when the snippets directly answer the request."
            ),
        }
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="chat_local_context_relevance",
            system=(
                "You are a bounded local-context relevance classifier. Return one JSON object only with "
                "use_local_context, confidence, reason. Do not answer the user and do not propose actions."
            ),
            payload=prompt_payload,
        )
        if not decision.ok:
            return None, f"Routing Debug: chat_local_context_relevance skipped reason={decision.error}"
        payload = decision.payload
        confidence_raw = str(payload.get("confidence", "") or "").strip().lower()
        confidence = confidence_score(payload.get("confidence"))
        if confidence < 0.55:
            return (
                None,
                "Routing Debug: chat_local_context_relevance skipped "
                f"reason=low_confidence confidence={confidence_raw or confidence}",
            )
        use_local_context = bool(payload.get("use_local_context", False))
        reason = self._normalize_spaces(str(payload.get("reason", "") or ""))[:180]
        return (
            use_local_context,
            "Routing Debug: chat_local_context_relevance "
            f"agentic_source=llm_decision use_local_context={str(use_local_context).lower()} "
            f"confidence={confidence_raw or confidence} candidates={len(context_rows)} reason={reason or '-'}",
        )

    async def _filter_chat_context_skill_results(
        self,
        skill_results: list[SkillResult],
        *,
        message: str,
        intents: list[str],
        allow_web_search_local_context: bool = True,
        language: str | None = None,
        debug_lines: list[str] | None = None,
        force_selected_context: bool = False,
    ) -> list[SkillResult]:
        if not skill_results:
            return []
        if "web_search" in intents:
            if allow_web_search_local_context:
                return list(skill_results)
            return [result for result in skill_results if not skill_result_is_local_memory_context(result)]
        if force_selected_context:
            if debug_lines is not None and self._routing_debug_enabled():
                debug_lines.append("Routing Debug: chat_local_context_relevance skipped reason=turn_plan_selected_context")
            return list(skill_results)
        if explicitly_requests_local_context(message):
            return list(skill_results)
        if not any(skill_result_is_local_memory_context(result) for result in skill_results):
            return list(skill_results)
        has_structured_local_context = any(
            isinstance((result.metadata or {}).get("sources"), list)
            and bool((result.metadata or {}).get("sources"))
            for result in skill_results
            if skill_result_is_local_memory_context(result)
        )
        if not has_structured_local_context:
            return filter_chat_context_skill_results(
                skill_results,
                message=message,
                intents=intents,
                allow_web_search_local_context=allow_web_search_local_context,
            )
        use_local_context, debug_line = await self._llm_wants_local_chat_context(
            message,
            skill_results=skill_results,
            intents=intents,
            language=language,
        )
        if debug_lines is not None and self._routing_debug_enabled() and debug_line:
            debug_lines.append(debug_line)
        if use_local_context is True:
            return list(skill_results)
        if use_local_context is False:
            return [result for result in skill_results if not skill_result_is_local_memory_context(result)]
        return filter_chat_context_skill_results(
            skill_results,
            message=message,
            intents=intents,
            allow_web_search_local_context=allow_web_search_local_context,
        )

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _slug_user_id(user_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip().lower())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "web"

    def _facts_collection_for_user(self, user_id: str) -> str:
        slug = self._slug_user_id(user_id)
        prefix = self.settings.memory.collections.facts.prefix.strip() or "aria_facts"
        return f"{prefix}_{slug}"

    def _preferences_collection_for_user(self, user_id: str) -> str:
        slug = self._slug_user_id(user_id)
        prefix = self.settings.memory.collections.preferences.prefix.strip() or "aria_preferences"
        return f"{prefix}_{slug}"

    def _extract_memory_store_text(
        self,
        message: str,
        routing_profile: RoutingLanguageConfig | None = None,
    ) -> str:
        text = self._normalize_spaces(message)
        lower = text.lower()
        active_routing = routing_profile or self.settings.routing.for_language(None)

        prefixes = [p.lower() for p in active_routing.memory_store_prefixes if p.strip()]

        for prefix in prefixes:
            if lower.startswith(prefix):
                extracted = text[len(prefix):].strip(" .,:;!?")
                if extracted:
                    return extracted

        parts = re.split(r"\b(?:dass|das)\b", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            extracted = parts[1].strip(" .,:;!?")
            if extracted:
                return extracted

        return text

    def _extract_memory_recall_query(
        self,
        message: str,
        routing_profile: RoutingLanguageConfig | None = None,
    ) -> str:
        text = self._normalize_spaces(message)
        active_routing = routing_profile or self.settings.routing.for_language(None)
        cleanup_keywords = [re.escape(k) for k in active_routing.memory_recall_cleanup_keywords if k.strip()]
        pattern = r"\b(" + "|".join(cleanup_keywords) + r")\b" if cleanup_keywords else r"$^"
        cleaned = re.sub(
            pattern,
            " ",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"[?!.:,;]+", " ", cleaned)
        cleaned = self._normalize_spaces(cleaned)
        return cleaned or text

    def _extract_web_search_query(
        self,
        message: str,
        routing_profile: RoutingLanguageConfig | None = None,
    ) -> str:
        text = self._normalize_spaces(message)
        urls = self._external_urls(text)
        if urls:
            return " ".join(urls)
        lower = text.lower()
        active_routing = routing_profile or self.settings.routing.for_language(None)

        prefixes = [p.lower() for p in active_routing.web_search_prefixes if p.strip()]
        for prefix in prefixes:
            if lower.startswith(prefix):
                extracted = text[len(prefix):].strip(" .,:;!?")
                if extracted:
                    return extracted

        cleanup_keywords = [re.escape(k) for k in active_routing.web_search_cleanup_keywords if k.strip()]
        if cleanup_keywords:
            text = re.sub(r"\b(" + "|".join(cleanup_keywords) + r")\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[?!.:,;]+", " ", text)
        text = self._normalize_spaces(text)
        return text or message

    @staticmethod
    def _truncate_text(text: str, limit: int = 1200) -> str:
        raw = str(text or "").strip()
        if len(raw) <= limit:
            return raw
        return raw[:limit] + "\n[... gekuerzt]"

    @staticmethod
    def _extract_held_packages(text: str) -> list[str]:
        return extract_held_packages(text)

    @staticmethod
    def _format_held_packages_summary(
        held_by_connection: dict[str, list[str]],
        connection_targets: dict[str, str],
    ) -> str:
        return format_held_packages_summary(held_by_connection, connection_targets)

    @staticmethod
    def _build_safe_fix_plan(skill_results: list[SkillResult]) -> list[dict[str, Any]]:
        return build_safe_fix_plan(skill_results)

    async def execute_safe_fix_plan(self, plan: list[dict[str, Any]], language: str = "de") -> SkillResult:
        return await self._safe_fix_executor.execute_plan(plan, language=language)

    async def _execute_custom_ssh_command(
        self,
        *,
        skill_id: str,
        skill_name: str,
        connection_ref: str,
        command_template: str,
        message: str,
        timeout_seconds: int | None = None,
        language: str = "de",
        policy_confirmed: bool = False,
    ) -> SkillResult:
        return await self._ssh_runtime.execute_custom_ssh_command(
            skill_id=skill_id,
            skill_name=skill_name,
            connection_ref=connection_ref,
            command_template=command_template,
            message=message,
            timeout_seconds=timeout_seconds,
            language=language,
            policy_confirmed=policy_confirmed,
        )

    async def _execute_custom_steps(self, row: dict[str, Any], message: str, language: str = "de") -> SkillResult:
        return await self._skill_runtime.execute_custom_steps(row=row, message=message, language=language)

    @staticmethod
    def _normalize_model_name(value: str) -> str:
        return value.strip().lower()

    def _resolve_pricing_entry(self, entries: dict[str, object], model_name: str) -> object | None:
        return resolve_pricing_entry(
            entries,
            model_name,
            model_aliases=getattr(self.settings.pricing, "model_aliases", {}),
        )

    async def _run_skills(
        self,
        intents: list[str],
        message: str,
        user_id: str,
        routing_profile: RoutingLanguageConfig,
        language: str = "de",
        runtime_recipes: list[dict[str, Any]] | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        auto_memory_enabled: bool = False,
        suppress_web_search_note_context: bool = False,
        query_overrides: dict[str, str] | None = None,
        context_overrides: dict[str, Any] | None = None,
    ) -> list[SkillResult]:
        return await self._skill_runtime.run_skills(
            intents=intents,
            message=message,
            user_id=user_id,
            routing_profile=routing_profile,
            language=language,
            runtime_recipes=runtime_recipes,
            memory_collection=memory_collection,
            session_collection=session_collection,
            auto_memory_enabled=auto_memory_enabled,
            suppress_web_search_note_context=suppress_web_search_note_context,
            query_overrides=query_overrides,
            context_overrides=context_overrides,
        )

    async def _execute_file_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_file_read(plan, language=language)

    async def _execute_file_write(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_file_write(plan, language=language)

    async def _execute_file_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_file_list(plan, language=language)

    async def _execute_feed_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_feed_read(plan, language=language)

    def _website_rows(self) -> dict[str, dict[str, object]]:
        return website_rows_from_settings(self.settings)

    async def _execute_website_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_website_read(plan, language=language)

    async def _execute_website_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_website_list(plan, language=language)

    async def _execute_calendar_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_calendar_read(plan, language=language)

    async def _execute_webhook_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_webhook_send(plan, language=language)

    async def _execute_discord_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_discord_send(plan, language=language)

    async def _execute_api_request(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_api_request(plan, language=language)

    async def _execute_email_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_email_send(plan, language=language)

    async def _execute_mail_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_mail_read(plan, language=language)

    async def _execute_mail_search(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_mail_search(plan, language=language)

    async def _execute_mqtt_publish(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_mqtt_publish(plan, language=language)

    async def _execute_ssh_command(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_ssh_command(plan, language=language)

    def _can_salvage_partial_ssh_result(self, result: SkillResult) -> bool:
        return self._capability_executor.can_salvage_partial_ssh_result(result)

    def _format_capability_missing_message(self, plan: ActionPlan, *, language: str | None = None) -> str:
        connection_rows = getattr(getattr(self.settings, "connections", object()), plan.connection_kind, {})
        return format_capability_missing_message(plan, connection_rows=connection_rows, language=language)

    def _sanitize_capability_error(self, exc: Exception, *, language: str | None = None) -> str:
        return sanitize_capability_error(exc, language=language)

    def _format_capability_execution_error(self, plan: ActionPlan, exc: Exception, *, language: str | None = None) -> str:
        return format_capability_execution_error(plan, exc, language=language)

    def _capability_execution_error_code(self, plan: ActionPlan, exc: Exception) -> str:
        return capability_execution_error_code(plan, exc)

    @staticmethod
    def _requested_connection_ref_is_soft_hint(value: str) -> bool:
        clean = str(value or "").strip().lower()
        if not clean:
            return False
        tokens = [token for token in re.split(r"[^a-z0-9]+", clean) if token]
        always_soft_tail_terms = (
            "channel",
            "kanal",
            "profile",
            "profil",
            "mailbox",
            "inbox",
            "topic",
            "broker",
            "feed",
            "endpoint",
            "http",
            "api",
        )
        serverish_tail_terms = (
            "server",
            "host",
            "system",
            "node",
        )
        generic_tokens = set(always_soft_tail_terms) | set(serverish_tail_terms)
        significant_tokens = [token for token in tokens if token not in generic_tokens]
        if clean.endswith(always_soft_tail_terms):
            return True
        if clean.endswith(serverish_tail_terms):
            return not significant_tokens
        if significant_tokens:
            return False
        return bool(tokens)

    @staticmethod
    def _requested_connection_ref_matches_candidate(
        requested_ref: str,
        *,
        connection_kind: str,
        connection_ref: str,
        row: Any,
    ) -> bool:
        clean_requested = str(requested_ref or "").strip()
        clean_ref = str(connection_ref or "").strip()
        if not clean_requested or not clean_ref:
            return False
        if clean_requested.lower() == clean_ref.lower():
            return True
        role_equivalence_groups = (
            {
                "dev",
                "developer",
                "developers",
                "development",
                "entwicklung",
                "entwickler",
                "entwicklungsserver",
                "entwicklungsumgebung",
            },
        )

        def _expand_role_tokens(tokens: set[str]) -> set[str]:
            expanded = set(tokens)
            for group in role_equivalence_groups:
                if expanded & group:
                    expanded.update(group)
            return expanded

        requested_tokens = {
            token
            for token in re.split(r"[^a-z0-9]+", clean_requested.lower())
            if token and token not in {"server", "host", "system", "node", "profile", "profil", "channel", "kanal"}
        }
        requested_tokens = _expand_role_tokens(requested_tokens)
        for alias in build_connection_aliases(connection_kind, clean_ref, row):
            if not alias:
                continue
            if str(alias).strip().lower() == clean_requested.lower():
                return True
            if connection_label_match_score(clean_requested, alias) > 0:
                return True
            if requested_tokens:
                alias_tokens = {
                    token
                    for token in re.split(r"[^a-z0-9]+", str(alias).strip().lower())
                    if token
                }
                alias_tokens = _expand_role_tokens(alias_tokens)
                if requested_tokens.issubset(alias_tokens):
                    return True
        return False

    @staticmethod
    def _payload_to_action_plan(payload: dict[str, Any]) -> ActionPlan:
        connection_ref = str(payload.get("connection_ref", "") or "").strip()
        requested_connection_ref = str(payload.get("requested_connection_ref", "") or "").strip()
        if Pipeline._requested_connection_ref_is_soft_hint(requested_connection_ref):
            requested_connection_ref = ""
        return ActionPlan(
            capability=str(payload.get("capability", "") or "").strip(),
            connection_kind=str(payload.get("connection_kind", "") or "").strip(),
            connection_ref=connection_ref,
            requested_connection_ref=requested_connection_ref,
            path=str(payload.get("path", "") or "").strip(),
            content=str(payload.get("content", "") or "").strip(),
            plan_class=str(payload.get("plan_class", "") or "").strip().lower(),
            behavior_profile=str(payload.get("behavior_profile", "") or "").strip().lower(),
            missing_fields=[
                str(item or "").strip()
                for item in list(payload.get("missing_fields", []) or [])
                if str(item or "").strip()
            ],
            resolution_source=str(payload.get("resolution_source", "") or "").strip(),
            notes=[
                str(item or "").strip()
                for item in list(payload.get("notes", []) or [])
                if str(item or "").strip()
            ],
        )

    async def _prepare_ssh_plural_multi_target_command(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str,
        candidate_connections: dict[str, Any] | None = None,
        capability_draft: Any | None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        refs = sorted(
            str(ref or "").strip()
            for ref in dict(candidate_connections or {}).keys()
            if str(ref or "").strip()
        )
        if len(refs) < 2:
            return resolved, capability_draft

        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        existing_command = str(
            getattr(capability_draft, "content", "") or payload.get("content", "") or ""
        ).strip()
        if existing_command:
            return resolved, capability_draft

        representative_ref = refs[0]
        working_draft = capability_draft or CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=representative_ref,
            content="",
            plan_class="command_single",
            behavior_profile="ssh_run_command",
        )
        working_draft = with_capability_draft_updates(
            working_draft,
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=representative_ref,
            requested_connection_ref="",
            content="",
            plan_class=str(getattr(working_draft, "plan_class", "") or "command_single"),
            behavior_profile=str(getattr(working_draft, "behavior_profile", "") or "ssh_run_command"),
        )

        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if not action_decision:
            action_decision = {
                "found": True,
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "capability": "ssh_command",
            }
            action_debug["decision"] = action_decision

        updated_action_debug, updated_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision={"found": True, "kind": "ssh", "ref": representative_ref, "source": "plural_target_scope"},
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
            llm_client=self.llm_client,
        )
        updated_decision = dict((updated_action_debug or {}).get("decision", {}) or {})
        command = str(
            (updated_decision.get("inputs") or {}).get("command", "")
            or getattr(updated_draft, "content", "")
            or ""
        ).strip()
        if not command:
            if debug_line:
                resolved = self._append_debug_detail_lines(resolved, debug_line)
            return resolved, capability_draft

        resolved["action_debug"] = updated_action_debug
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, debug_line)
        resolved = self._append_debug_detail_lines(
            resolved,
            "Routing Debug: plural_target_scope command_draft "
            f"ref={representative_ref} command={command}",
        )

        base_draft = capability_draft or CapabilityDraft(capability="ssh_command", connection_kind="ssh")
        base_draft = with_capability_draft_updates(
            base_draft,
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref="",
            requested_connection_ref="",
            content=command,
            plan_class="command_single",
            behavior_profile="ssh_run_command",
        )
        return resolved, base_draft

    def _apply_ssh_plural_multi_target_resolution(
        self,
        resolved: dict[str, Any],
        *,
        candidate_connections: dict[str, Any] | None = None,
        capability_draft: Any | None,
        language: str | None = None,
    ) -> dict[str, Any]:
        payload_debug = dict(resolved.get("payload_debug", {}) or {})
        payload = dict(payload_debug.get("payload", {}) or {})
        command = str(
            getattr(capability_draft, "content", "") or payload.get("content", "") or ""
        ).strip()
        capability = normalize_capability(str(payload.get("capability", "") or getattr(capability_draft, "capability", "") or ""))
        connection_kind = normalize_connection_kind(
            str(payload.get("connection_kind", "") or getattr(capability_draft, "connection_kind", "") or "")
        )
        if capability != "ssh_command" or connection_kind != "ssh" or not command:
            return resolved
        if validate_ssh_readonly_policy(command).action != "allow":
            return resolved
        existing_refs = self._payload_multi_target_refs(payload)
        refs = existing_refs or sorted(
            str(ref or "").strip()
            for ref in dict(candidate_connections or {}).keys()
            if str(ref or "").strip()
        )
        if len(refs) < 2:
            return resolved
        adapted_command, adaptation_reason = self._adapt_multi_target_ssh_operator_command(
            refs,
            command,
            str(resolved.get("query", "") or ""),
            capability_draft,
        )
        if adapted_command and adapted_command != command:
            command = adapted_command
            payload["content"] = command
            if capability_draft is not None:
                capability_draft = with_capability_draft_updates(capability_draft, content=command)
            resolved = self._append_debug_detail_lines(
                resolved,
                f"Routing Debug: plural_target_scope {adaptation_reason}_command_adapted "
                f"command={command}",
            )

        missing_fields = [
            str(item or "").strip()
            for item in list(payload.get("missing_fields", []) or [])
            if str(item or "").strip() and str(item or "").strip() != "connection_ref"
        ]
        payload.update(
            {
                "found": True,
                "capability": "ssh_command",
                "connection_kind": "ssh",
                "connection_ref": "",
                "connection_refs": refs,
                "content": command,
                "missing_fields": missing_fields,
                "preview": f"SSH command on {len(refs)} targets: {command}",
                "resolution_source": "plural_target_scope",
            }
        )
        payload_debug.update(
            {
                "used": True,
                "status": "ok" if not missing_fields else "warn",
                "visual_status": "ok" if not missing_fields else "warn",
                "message": "Payload dry-run built a multi-target SSH executor payload.",
                "payload": payload,
            }
        )
        resolved["payload_debug"] = payload_debug

        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        action_decision.update(
            {
                "found": True,
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "capability": "ssh_command",
                "inputs": {"command": command},
                "input_items": [{"key": "command", "key_label": "Command", "value": command}],
                "preview": f"SSH command on {len(refs)} targets: {command}",
                "ask_user": False,
                "missing_input": "",
                "missing_input_label": "",
                "execution_state": "ready",
            }
        )
        action_debug["decision"] = action_decision
        resolved["action_debug"] = action_debug

        routing_decision = dict(resolved.get("decision", {}) or {})
        safety_debug = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        safety_decision = dict(safety_debug.get("decision", {}) or {})
        safety_decision["multi_target_count"] = len(refs)
        safety_debug["decision"] = safety_decision
        resolved["safety_debug"] = safety_debug

        execution_debug = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=dict((resolved.get("action_debug") or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=safety_debug,
            language=str(language or ""),
        )
        execution_decision = dict(execution_debug.get("decision", {}) or {})
        if execution_decision:
            execution_decision["summary"] = f"ARIA would run on {len(refs)} SSH targets: SSH command: {command}"
            execution_decision["multi_target_count"] = len(refs)
        execution_debug["decision"] = execution_decision
        resolved["execution_debug"] = execution_debug
        return self._append_debug_detail_lines(
            resolved,
            "Routing Debug: plural_target_scope selected_multi_target "
            f"kind=ssh refs={', '.join(refs)} command={command}",
        )

    def _narrow_ssh_plural_target_connections_by_context(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        candidate_connections: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[SemanticConnectionCandidate]]:
        candidates = self._semantic_connection_resolver.collect_connection_candidates(
            message,
            {"ssh": candidate_connections},
            preferred_kind="ssh",
        )
        strong_candidates: list[SemanticConnectionCandidate] = []
        seen_refs: set[str] = set()
        for candidate in candidates:
            ref = str(candidate.connection_ref or "").strip()
            if candidate.connection_kind != "ssh" or ref not in candidate_connections:
                continue
            if int(candidate.score or 0) < 1000:
                continue
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            strong_candidates.append(candidate)
        if not strong_candidates:
            prompt_seed_terms = self._ssh_plural_context_seed_terms_from_message(message)
            if not prompt_seed_terms:
                return resolved, candidate_connections, candidates
            strong_candidates = self._expand_ssh_plural_context_group_candidates(
                message=message,
                candidate_connections=candidate_connections,
                seed_candidates=[],
                score=1000,
                seed_terms=prompt_seed_terms,
            )
            candidates = [*candidates, *strong_candidates]
            seen_refs = {str(candidate.connection_ref or "").strip() for candidate in strong_candidates}
            if not strong_candidates:
                return resolved, candidate_connections, candidates
        top_score = max(int(candidate.score or 0) for candidate in strong_candidates)
        strong_candidates = [
            candidate
            for candidate in strong_candidates
            if int(candidate.score or 0) == top_score
        ]
        seen_refs = {
            str(candidate.connection_ref or "").strip()
            for candidate in strong_candidates
            if str(candidate.connection_ref or "").strip()
        }
        if strong_candidates and (
            not self._ssh_plural_context_has_single_target_disambiguator(message)
            or self._ssh_plural_context_should_expand_role_group(message, strong_candidates)
        ):
            expanded_candidates = self._expand_ssh_plural_context_group_candidates(
                message=message,
                candidate_connections=candidate_connections,
                seed_candidates=strong_candidates,
                score=top_score,
            )
            for candidate in expanded_candidates:
                ref = str(candidate.connection_ref or "").strip()
                if ref and ref not in seen_refs:
                    seen_refs.add(ref)
                    strong_candidates.append(candidate)
        if not strong_candidates or len(strong_candidates) >= len(candidate_connections):
            return resolved, candidate_connections, candidates

        strong_candidates.sort(key=lambda candidate: str(candidate.connection_ref or ""))
        scoped_connections = {
            candidate.connection_ref: candidate_connections[candidate.connection_ref]
            for candidate in strong_candidates
        }
        aliases = ", ".join(
            str(candidate.alias or candidate.note or candidate.connection_ref or "-").strip()
            for candidate in strong_candidates
        )
        resolved = self._append_debug_detail_lines(
            resolved,
            "Routing Debug: plural_target_scope narrowed_by_connection_context "
            f"kind=ssh refs={', '.join(scoped_connections.keys())} aliases={aliases or '-'}",
        )
        return resolved, scoped_connections, candidates

    @staticmethod
    def _ssh_plural_context_has_single_target_disambiguator(message: str) -> bool:
        tokens = set(split_connection_tokens(message))
        single_target_terms = {
            "erster",
            "erste",
            "erstes",
            "ersten",
            "zweiter",
            "zweite",
            "zweites",
            "zweiten",
            "dritter",
            "dritte",
            "drittes",
            "dritten",
            "first",
            "second",
            "third",
            "only",
            "nur",
            "mein",
            "meinem",
        }
        if tokens & single_target_terms:
            return True
        if "meinen" in tokens and not (tokens & {"servern", "systemen", "hosts", "servers"}):
            return True
        return False

    @staticmethod
    def _ssh_plural_context_should_expand_role_group(
        message: str,
        seed_candidates: list[SemanticConnectionCandidate],
    ) -> bool:
        seed_terms = Pipeline._ssh_plural_context_seed_terms(message, seed_candidates)
        if not (seed_terms & {"dns", "pihole", "pi-hole"}):
            return False
        tokens = set(split_connection_tokens(message))
        mutating_terms = {
            "restart",
            "reboot",
            "start",
            "stop",
            "starte",
            "neustart",
            "update",
            "install",
            "delete",
            "remove",
            "loesche",
            "schreibe",
            "write",
        }
        if tokens & mutating_terms:
            return False
        health_terms = {
            "ok",
            "okay",
            "status",
            "health",
            "healthy",
            "check",
            "pruef",
            "pruefe",
            "fit",
            "gesund",
            "geht",
            "erreichbar",
        }
        return bool(tokens & health_terms)

    @staticmethod
    def _ssh_plural_context_seed_terms(
        message: str,
        seed_candidates: list[SemanticConnectionCandidate],
    ) -> set[str]:
        generic_terms = {
            "server",
            "srv",
            "host",
            "system",
            "node",
            "profile",
            "profil",
            "ssh",
        }
        message_tokens = set(split_connection_tokens(message))
        seed_terms: set[str] = set()
        for candidate in seed_candidates:
            candidate_labels = [
                str(candidate.alias or "").strip(),
                str(candidate.note or "").strip(),
                str(candidate.connection_ref or "").strip(),
            ]
            for label in candidate_labels:
                for token in split_connection_tokens(label):
                    if token in generic_terms or len(token) < 3:
                        continue
                    if token in message_tokens or any(token.startswith(message_token) for message_token in message_tokens):
                        seed_terms.add(token)
                    elif token.startswith("dev"):
                        seed_terms.add("dev")
        expanded_terms = set(seed_terms)
        if seed_terms & {
            "dev",
            "developer",
            "developers",
            "development",
            "entwicklungsserver",
            "entwicklungsumgebung",
            "entwicklung",
        }:
            expanded_terms.update(
                {
                    "dev",
                    "devserver",
                    "dev-server",
                    "development",
                    "developer",
                    "entwicklung",
                    "entwicklungsserver",
                    "entwicklungsumgebung",
                    "webentwicklung",
                    "coding",
                    "programming",
                    "programmierung",
                    "code-server",
                    "vscode",
                    "browser-ide",
                }
            )
        return expanded_terms

    @staticmethod
    def _ssh_plural_context_seed_terms_from_message(message: str) -> set[str]:
        generic_terms = {
            "all",
            "alle",
            "auf",
            "den",
            "der",
            "die",
            "ein",
            "eine",
            "genug",
            "habe",
            "haben",
            "hat",
            "ich",
            "mein",
            "meine",
            "meinen",
            "noch",
            "server",
            "servers",
            "srv",
            "ssh",
            "system",
            "systeme",
        }
        seed_terms = {
            token
            for token in split_connection_tokens(message)
            if len(token) >= 3 and token not in generic_terms
        }
        if seed_terms & {"dev", "developer", "developers", "development", "entwicklung", "entwicklungsserver"}:
            seed_terms.update(
                {
                    "dev",
                    "devserver",
                    "dev-server",
                    "development",
                    "developer",
                    "entwicklung",
                    "entwicklungsserver",
                    "entwicklungsumgebung",
                    "webentwicklung",
                    "coding",
                    "programming",
                    "programmierung",
                    "code-server",
                    "vscode",
                    "browser-ide",
                }
            )
        if seed_terms & {"dns", "pihole", "pi-hole"}:
            seed_terms.update({"dns", "pihole", "pi-hole", "adblock", "ad-blocking"})
        return seed_terms

    @staticmethod
    def _ssh_connection_aliases_match_seed_terms(
        aliases: list[str],
        seed_terms: set[str],
    ) -> str:
        if not seed_terms:
            return ""
        alias_blob = " ".join(normalize_connection_alias(alias) for alias in aliases if str(alias or "").strip())
        alias_tokens = set(split_connection_tokens(alias_blob))
        for term in sorted(seed_terms):
            clean_term = normalize_connection_alias(term)
            if not clean_term:
                continue
            if clean_term == "dev":
                if any(Pipeline._ssh_alias_token_matches_dev_seed(token) for token in alias_tokens):
                    return clean_term
                continue
            if clean_term in alias_blob:
                return clean_term
            term_tokens = split_connection_tokens(clean_term)
            if term_tokens and all(token in alias_tokens for token in term_tokens):
                return clean_term
        return ""

    @staticmethod
    def _ssh_alias_token_matches_dev_seed(token: str) -> bool:
        clean_token = str(token or "").strip().lower()
        if not clean_token:
            return False
        return (
            clean_token == "dev"
            or bool(re.fullmatch(r"dev[0-9]+", clean_token))
            or clean_token in {
                "devserver",
                "development",
                "developer",
                "entwicklungsserver",
                "entwicklungsumgebung",
                "entwicklung",
                "webentwicklung",
            }
        )

    def _expand_ssh_plural_context_group_candidates(
        self,
        *,
        message: str,
        candidate_connections: dict[str, Any],
        seed_candidates: list[SemanticConnectionCandidate],
        score: int,
        seed_terms: set[str] | None = None,
    ) -> list[SemanticConnectionCandidate]:
        seed_refs = {str(candidate.connection_ref or "").strip() for candidate in seed_candidates}
        effective_seed_terms = seed_terms or self._ssh_plural_context_seed_terms(message, seed_candidates)
        if not effective_seed_terms:
            return []
        expanded: list[SemanticConnectionCandidate] = []
        for ref, row in candidate_connections.items():
            clean_ref = str(ref or "").strip()
            if not clean_ref or clean_ref in seed_refs:
                continue
            aliases = build_connection_aliases("ssh", clean_ref, row)
            matched = self._ssh_connection_aliases_match_seed_terms(aliases, effective_seed_terms)
            if not matched:
                continue
            expanded.append(
                SemanticConnectionCandidate(
                    connection_kind="ssh",
                    connection_ref=clean_ref,
                    source="semantic_group_alias",
                    note=f"group_alias:{matched}",
                    alias=matched,
                    score=int(score or 0),
                )
            )
        return expanded

    async def _finalize_ssh_plural_multi_target_action(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str,
        capability_draft: Any | None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        draft_multi_target_scope = self._capability_draft_has_multi_target_scope(capability_draft)
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if not callable(looks_like_plural_target) and not draft_multi_target_scope:
            return resolved, capability_draft
        if not draft_multi_target_scope:
            try:
                if not bool(looks_like_plural_target(message, "ssh")):
                    return resolved, capability_draft
            except Exception:
                return resolved, capability_draft

        connection_pools = self._unified_routing_connection_pools()
        ssh_connections = connection_pools.get("ssh", {})
        if not isinstance(ssh_connections, dict) or len(ssh_connections) < 2:
            return resolved, capability_draft

        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        if self._payload_multi_target_refs(payload):
            return resolved, capability_draft
        if str(payload.get("connection_ref", "") or "").strip():
            return resolved, capability_draft
        routing_decision = dict(resolved.get("decision", {}) or {})
        if str(routing_decision.get("ref", "") or "").strip():
            return resolved, capability_draft

        action_decision = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        if str(action_decision.get("candidate_id", "") or "").strip() != "ssh_run_command":
            return resolved, capability_draft

        payload_kind = normalize_connection_kind(str(payload.get("connection_kind", "") or ""))
        draft_kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        if payload_kind not in {"", "ssh"} or draft_kind not in {"", "ssh"}:
            return resolved, capability_draft

        resolved, scoped_connections, semantic_candidates = self._narrow_ssh_plural_target_connections_by_context(
            resolved,
            message=message,
            candidate_connections=ssh_connections,
        )
        if len(scoped_connections) == 1:
            scoped_ref = str(next(iter(scoped_connections.keys())) or "").strip()
            if scoped_ref:
                scoped_resolved = await self._build_forced_routed_resolution(
                    message,
                    connection_kind="ssh",
                    connection_ref=scoped_ref,
                    language=language,
                    llm_client=None,
                    capability_draft=capability_draft,
                    source="plural_target_context",
                    reason=scoped_ref,
                )
                scoped_resolved["detail_lines"] = [
                    *self._resolved_routing_detail_lines(resolved),
                    *self._resolved_routing_detail_lines(scoped_resolved),
                ]
                scoped_resolved = self._append_routing_record_to_resolved(
                    scoped_resolved,
                    build_routing_decision_record(
                        stage="plural_target_context_resolution",
                        candidates=semantic_candidates,
                        hint=SemanticConnectionHint(
                            connection_kind="ssh",
                            connection_ref=scoped_ref,
                            source="plural_target_context",
                            note=scoped_ref,
                        ),
                        preferred_kind="ssh",
                    ),
                )
                scoped_resolved = self._attach_connection_candidates_debug(scoped_resolved, semantic_candidates)
                return scoped_resolved, capability_draft

        resolved, capability_draft = await self._prepare_ssh_plural_multi_target_command(
            resolved,
            message=message,
            user_id=user_id,
            candidate_connections=scoped_connections,
            capability_draft=capability_draft,
            language=language,
        )
        resolved = self._apply_ssh_plural_multi_target_resolution(
            resolved,
            candidate_connections=scoped_connections,
            capability_draft=capability_draft,
            language=language,
        )
        return resolved, capability_draft

    @staticmethod
    def _find_runtime_recipe(runtime_recipes: list[dict[str, Any]], recipe_id: str) -> dict[str, Any] | None:
        clean_recipe_id = str(recipe_id or "").strip()
        if not clean_recipe_id:
            return None
        for row in runtime_recipes:
            if str(row.get("id", "") or "").strip() == clean_recipe_id:
                return row
        return None

    @staticmethod
    def _zero_usage() -> dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _current_usage_snapshot(self) -> dict[str, Any]:
        snapshot = self.usage_meter.snapshot_scope(None)
        usage = dict(snapshot.get("usage", {}) or {})
        embedding_usage = dict(snapshot.get("embedding_usage", {}) or {})
        return {
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            "embedding_usage": {
                "prompt_tokens": int(embedding_usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(embedding_usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(embedding_usage.get("total_tokens", 0) or 0),
                "calls": int(embedding_usage.get("calls", 0) or 0),
            },
            "chat_model": str(snapshot.get("chat_model", "") or self.settings.llm.model).strip(),
            "embedding_model": str(snapshot.get("embedding_model", "") or self.settings.embeddings.model).strip(),
            "chat_cost_usd": snapshot.get("chat_cost_usd"),
            "embedding_cost_usd": snapshot.get("embedding_cost_usd"),
            "total_cost_usd": snapshot.get("total_cost_usd"),
        }

    async def _log_result_usage_snapshot(
        self,
        *,
        request_id: str,
        user_id: str,
        intents: list[str],
        router_level: int,
        duration_ms: int,
        source: str,
        skill_errors: list[str] | None = None,
        extraction_model: str = "bounded_routing_chain",
    ) -> None:
        usage_snapshot = self._current_usage_snapshot()
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=intents,
            router_level=router_level,
            usage=dict(usage_snapshot.get("usage", {}) or {}),
            chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
            embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
            embedding_usage=dict(usage_snapshot.get("embedding_usage", {}) or {}),
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            duration_ms=duration_ms,
            source=source,
            skill_errors=list(skill_errors or []),
            extraction_model=extraction_model,
            extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
        )

    def _routing_reason_text(self, resolved: dict[str, Any], *, language: str | None = None) -> str:
        return routing_reason_text(resolved, language=language)

    async def _blocked_action_response_text(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str,
        request_id: str,
        language: str | None = None,
        detail_lines: list[str] | None = None,
    ) -> tuple[str, list[str]]:
        routing = dict(resolved.get("decision", {}) or {})
        safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        fallback = self._routing_reason_text(resolved, language=language)
        target_kind = str(routing.get("kind", "") or payload.get("connection_kind", "") or "").strip()
        target_ref = str(routing.get("ref", "") or payload.get("connection_ref", "") or "").strip()
        target = f"{target_kind}/{target_ref}".strip("/")
        capability = str(payload.get("capability", "") or "").strip()
        guardrail_ref = str(safety.get("guardrail_ref", "") or "").strip()
        guardrail_kind = str(safety.get("guardrail_kind", "") or "").strip()
        guardrail_text = str(safety.get("guardrail_text", "") or "").strip()
        if (not guardrail_ref or not guardrail_kind or not guardrail_text) and target_kind and target_ref:
            row = payload_connection_row(self.settings, target_kind, target_ref)
            if row is not None:
                guardrail_ref = guardrail_ref or read_row_value(row, "guardrail_ref")
                if not guardrail_kind:
                    guardrail_kind = "ssh_command" if capability == "ssh_command" else guardrail_kind
        explanation = await explain_blocked_action(
            llm_client=self.llm_client,
            user_message=message,
            fallback_text=fallback,
            language=language,
            user_id=user_id,
            request_id=request_id,
            target=target,
            preview=str(payload.get("preview", "") or payload.get("content", "") or "").strip(),
            capability=capability,
            policy_reason=str(safety.get("reason", "") or "").strip(),
            policy_reason_label=str(safety.get("reason_label", "") or "").strip(),
            guardrail_ref=str(guardrail_ref or "").strip(),
            guardrail_kind=str(guardrail_kind or "").strip(),
            guardrail_text=str(guardrail_text or "").strip(),
            skip_llm_reason="ssh_policy_block_fast_path" if capability == "ssh_command" and str(safety.get("action", "") or "").strip().lower() == "block" else "",
            review_link_kind="ssh_policy" if capability == "ssh_command" and str(safety.get("action", "") or "").strip().lower() == "block" else "",
        )
        updated_details = list(detail_lines or [])
        if self._routing_debug_enabled() and explanation.debug_line and explanation.debug_line not in updated_details:
            updated_details.append(explanation.debug_line)
        return explanation.text, updated_details

    def _build_routed_confirmation_text(
        self,
        resolved: dict[str, Any],
        *,
        language: str | None = None,
    ) -> str:
        return build_routed_confirmation_text(resolved, language=language)

    def _build_routed_missing_input_text(
        self,
        resolved: dict[str, Any],
        *,
        language: str | None = None,
    ) -> str:
        return build_routed_missing_input_text(resolved, language=language)

    @staticmethod
    def _pending_follow_up_value(follow_up_message: str, *, missing_input: str) -> str:
        clean = str(follow_up_message or "").strip()
        if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {"'", '"', "`"}:
            clean = clean[1:-1].strip()
        if not clean:
            return ""
        quoted = re.search(r'["\'`]\s*([^"\'`]+?)\s*["\'`]', clean)
        if quoted and missing_input in {"command", "message", "search_query"}:
            return str(quoted.group(1) or "").strip()
        if missing_input == "remote_path":
            quoted = re.search(r'["\'`]\s*([^"\'`]+?)\s*["\'`]', clean)
            if quoted:
                return str(quoted.group(1) or "").strip()
            slash_path = re.search(r"(/[^\\s]+(?:/[^\\s]+)*)", clean)
            if slash_path:
                return str(slash_path.group(1) or "").strip()
        if missing_input in {"command", "message", "search_query"}:
            colon = re.search(r"[:=-]\s*(.+)$", clean)
            if colon:
                candidate = str(colon.group(1) or "").strip()
                if candidate:
                    return candidate
            for pattern in _PIPELINE_INPUT_PATTERNS.get(missing_input, ()):
                match = re.search(pattern, clean, re.IGNORECASE)
                if not match:
                    continue
                candidate = str(match.group(1) or "").strip(" \t\r\n.,;:!?")
                if candidate:
                    return candidate
        return clean

    @staticmethod
    def _resolve_pending_missing_input(action: dict[str, Any], payload: dict[str, Any]) -> str:
        return resolve_pending_missing_input(action, payload)

    @staticmethod
    def _payload_missing_fields(payload: dict[str, Any]) -> list[str]:
        return payload_missing_fields(payload)

    @staticmethod
    def _resolved_next_step(
        *,
        safety: dict[str, Any],
        execution: dict[str, Any],
    ) -> str:
        return resolved_next_step(safety=safety, execution=execution)

    @staticmethod
    def _build_pending_action_state(
        *,
        query: str,
        candidate_kind: str,
        candidate_id: str,
        resolved: dict[str, Any],
        action: dict[str, Any],
        payload: dict[str, Any],
        safety: dict[str, Any],
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        return build_pending_action_state(
            query=query,
            candidate_kind=candidate_kind,
            candidate_id=candidate_id,
            resolved=resolved,
            action=action,
            payload=payload,
            safety=safety,
            execution=execution,
        )

    @staticmethod
    def _pending_payload_intents(payload: dict[str, Any]) -> list[str]:
        return pending_payload_intents(payload)

    @staticmethod
    def _routed_action_intents(action: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        return routed_action_intents(action, payload)

    def _pending_input_to_draft(
        self,
        pending_action: dict[str, Any],
        follow_up_message: str,
    ) -> tuple[CapabilityDraft | None, str]:
        action = dict(pending_action.get("action_decision", {}) or {})
        payload = dict(pending_action.get("payload", {}) or {})
        routing = dict(pending_action.get("routing_decision", {}) or {})
        missing_input = self._resolve_pending_missing_input(action, payload)
        if not missing_input:
            return None, ""

        follow_up_value = self._pending_follow_up_value(follow_up_message, missing_input=missing_input)
        if not follow_up_value:
            return None, missing_input

        capability = str(payload.get("capability", "") or routing.get("capability", "") or "").strip()
        connection_kind = str(payload.get("connection_kind", "") or routing.get("kind", "") or "").strip()
        connection_ref = str(payload.get("connection_ref", "") or routing.get("ref", "") or "").strip()
        requested_connection_ref = str(payload.get("requested_connection_ref", "") or "").strip()
        path = str(payload.get("path", "") or "").strip()
        content = str(payload.get("content", "") or "").strip()
        plan_class = str(payload.get("plan_class", "") or action.get("plan_class", "") or "").strip().lower()
        behavior_profile = str(payload.get("behavior_profile", "") or action.get("behavior_profile", "") or "").strip().lower()

        if missing_input in {"command", "message", "search_query"}:
            content = follow_up_value
        elif missing_input in {"remote_path", "topic"}:
            path = follow_up_value
        elif missing_input == "connection_ref":
            connection_ref = follow_up_value
            requested_connection_ref = ""

        draft = CapabilityDraft(
            capability=capability,
            connection_kind=connection_kind,
            explicit_connection_ref=connection_ref,
            requested_connection_ref=requested_connection_ref,
            path=path,
            content=content,
            plan_class=plan_class,
            behavior_profile=behavior_profile,
            notes=[f"pending_input:{missing_input}"],
        )
        return draft, missing_input

    def _apply_filled_pending_input(
        self,
        resolved: dict[str, Any],
        *,
        language: str | None = None,
    ) -> dict[str, Any]:
        action_debug = dict(resolved.get("action_debug", {}) or {})
        action = dict(action_debug.get("decision", {}) or {})
        payload_debug = dict(resolved.get("payload_debug", {}) or {})
        payload = dict(payload_debug.get("payload", {}) or {})

        action["missing_input"] = ""
        action["missing_input_label"] = ""
        action["clarifying_question"] = ""
        action["example_prompt"] = ""
        action["reason"] = str(action.get("reason", "") or "").strip()
        action_debug["decision"] = action
        resolved["action_debug"] = action_debug

        payload["missing_input"] = ""
        payload["missing_input_label"] = ""
        payload_debug["payload"] = payload
        resolved["payload_debug"] = payload_debug

        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            language=str(language or ""),
        )
        ask_user = bool(dict((resolved.get("safety_debug") or {}).get("decision", {}) or {}).get("ask_user"))
        action["execution_state"] = "needs_confirmation" if ask_user else "ready"
        action["execution_state_label"] = _pipeline_text(
            language,
            "execution_state_needs_confirmation" if ask_user else "execution_state_ready",
            "Needs confirmation" if ask_user else "Ready",
        )
        action_debug["decision"] = action
        resolved["action_debug"] = action_debug
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_decision=action,
            payload_debug=payload_debug,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )
        return resolved

    def _build_routed_action_result(
        self,
        *,
        request_id: str,
        decision: Any,
        duration_ms: int,
        intents: list[str],
        text: str,
        detail_lines: list[str] | None = None,
        skill_errors: list[str] | None = None,
        pending_action: dict[str, Any] | None = None,
    ) -> PipelineResult:
        usage_snapshot = self._current_usage_snapshot()
        return PipelineResult(
            request_id=request_id,
            text=text,
            usage=dict(usage_snapshot.get("usage", {}) or {}),
            intents=intents,
            skill_errors=list(skill_errors or []),
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            safe_fix_plan=None,
            detail_lines=list(detail_lines or []),
            pending_action=dict(pending_action or {}) if pending_action else None,
        )

    def _settings_without_qdrant_routing(self) -> Settings:
        return settings_without_qdrant_routing(self.settings)

    async def _resolve_live_routing_chain(
        self,
        message: str,
        *,
        preferred_kind: str = "",
        llm_client: Any | None,
        language: str | None = None,
    ) -> dict[str, Any]:
        return await core_resolve_live_routing_chain(
            settings=self.settings,
            embedding_client=self.embedding_client,
            usage_meter=self.usage_meter,
            message=message,
            preferred_kind=preferred_kind,
            llm_client=llm_client,
            language=language,
            routing_debug_enabled=self._routing_debug_enabled(),
            create_async_qdrant_client_fn=create_async_qdrant_client,
            ensure_connection_routing_index_ready_fn=ensure_connection_routing_index_ready,
            resolve_connection_routing_chain_fn=resolve_connection_routing_chain,
        )

    @staticmethod
    def _resolved_routing_chain_has_signal(resolved: dict[str, Any] | None) -> bool:
        return resolved_routing_chain_has_signal(resolved)

    def _resolved_routing_detail_lines(self, resolved: dict[str, Any]) -> list[str]:
        return resolved_routing_detail_lines(resolved, routing_debug_enabled=self._routing_debug_enabled())

    def _append_routing_record_to_resolved(self, resolved: dict[str, Any], record: Any) -> dict[str, Any]:
        return append_routing_record_to_resolved(
            resolved,
            record,
            routing_debug_enabled=self._routing_debug_enabled(),
        )

    def _routing_candidates_from_resolved(self, resolved: dict[str, Any]) -> list[SemanticConnectionCandidate]:
        return routing_candidates_from_resolved(resolved)

    def _append_resolved_chain_routing_record(self, resolved: dict[str, Any]) -> dict[str, Any]:
        decision = dict(resolved.get("decision", {}) or {})
        if not bool(decision.get("found")):
            return resolved
        return self._append_routing_record_to_resolved(
            resolved,
            build_routing_decision_record(
                stage="routing_chain",
                candidates=self._routing_candidates_from_resolved(resolved),
                hint=SemanticConnectionHint(
                    connection_kind=str(decision.get("kind", "") or "").strip(),
                    connection_ref=str(decision.get("ref", "") or "").strip(),
                    source=str(decision.get("source", "") or "").strip(),
                    note=str(decision.get("reason", "") or "").strip(),
                ),
                preferred_kind=str(resolved.get("preferred_kind", "") or ""),
            ),
        )

    @staticmethod
    def _serialize_connection_candidates(candidates: list[SemanticConnectionCandidate]) -> list[dict[str, Any]]:
        return serialize_connection_candidates(candidates)

    def _attach_connection_candidates_debug(
        self,
        resolved: dict[str, Any],
        candidates: list[SemanticConnectionCandidate],
    ) -> dict[str, Any]:
        return attach_connection_candidates_debug(resolved, candidates)

    def _build_planner_input_object_from_resolved(
        self,
        *,
        message: str,
        resolved: dict[str, Any],
        user_id: str = "",
        preferred_connection_kind: str = "",
        connection_ref: str = "",
        language: str = "",
        notes: list[str] | None = None,
        extra_session_context: dict[str, str] | None = None,
    ) -> Any:
        connection_rows = [
            planner_candidate_from_connection_payload(row)
            for row in list(resolved.get("connection_candidates_debug", []) or [])
            if isinstance(row, dict)
        ]
        action_rows = [
            planner_candidate_from_action_payload(row)
            for row in list((resolved.get("action_debug") or {}).get("candidates", []) or [])
            if isinstance(row, dict)
        ]
        session_context = self._planner_session_context(
            user_id=user_id,
            message=message,
            preferred_connection_kind=preferred_connection_kind,
            resolved=resolved,
        )
        for key, value in dict(extra_session_context or {}).items():
            clean_key = str(key or "").strip()
            clean_value = str(value or "").strip()
            if clean_key and clean_value:
                session_context[clean_key] = clean_value
        connection_input = build_connection_planner_input_set(
            query=message,
            language=language,
            preferred_connection_kind=preferred_connection_kind,
            connection_ref=connection_ref,
            connection_candidates=connection_rows,
            notes=notes,
            session_context=session_context,
        )
        action_input = build_planner_input_set(
            query=message,
            language=language,
            preferred_connection_kind=preferred_connection_kind,
            connection_ref=connection_ref,
            action_candidates=action_rows,
            session_context=session_context,
        )
        return merge_planner_input_sets(connection_input, action_input)

    def _build_planner_input_set_from_resolved(
        self,
        *,
        message: str,
        resolved: dict[str, Any],
        user_id: str = "",
        preferred_connection_kind: str = "",
        connection_ref: str = "",
        language: str = "",
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        merged = self._build_planner_input_object_from_resolved(
            message=message,
            resolved=resolved,
            user_id=user_id,
            preferred_connection_kind=preferred_connection_kind,
            connection_ref=connection_ref,
            language=language,
            notes=notes,
        )
        return planner_input_set_to_dict(merged)

    def _planner_session_context(
        self,
        *,
        user_id: str,
        message: str,
        preferred_connection_kind: str = "",
        resolved: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        recent = self._load_recent_capability_context(user_id) if user_id else {}
        if not isinstance(recent, dict) or not recent:
            return {}

        session_context: dict[str, str] = {}
        recent_capability = str(recent.get("capability", "") or "").strip()
        recent_kind = normalize_connection_kind(str(recent.get("connection_kind", "") or ""))
        recent_ref = str(recent.get("connection_ref", "") or "").strip()
        recent_path = str(recent.get("path", "") or "").strip()
        recent_content = str(recent.get("content", "") or "").strip()
        clean_preferred = normalize_connection_kind(preferred_connection_kind)

        if recent_capability:
            session_context["recent_capability"] = recent_capability
        if recent_kind:
            session_context["recent_connection_kind"] = recent_kind
        if recent_ref:
            session_context["recent_connection_ref"] = recent_ref
        if recent_path:
            session_context["recent_path"] = recent_path
        if recent_content:
            session_context["recent_content"] = recent_content

        if clean_preferred and recent_kind and clean_preferred == recent_kind:
            session_context["recent_kind_matches_preferred"] = "true"

        if self._looks_like_calendar_followup_message(message) and recent_capability == "calendar_read":
            session_context["follow_up_type"] = "calendar_follow_up"

        wants_previous_connection = getattr(self._memory_assist, "_wants_previous_connection", None)
        if callable(wants_previous_connection):
            try:
                if wants_previous_connection(message):
                    session_context["follow_up_type"] = "same_connection"
            except Exception:
                pass
        wants_previous_path = getattr(self._memory_assist, "_wants_previous_path", None)
        if callable(wants_previous_path):
            try:
                if wants_previous_path(message):
                    session_context["follow_up_type"] = "same_path"
            except Exception:
                pass

        if isinstance(resolved, dict):
            decision = dict(resolved.get("decision", {}) or {})
            chosen_kind = normalize_connection_kind(str(decision.get("kind", "") or ""))
            chosen_ref = str(decision.get("ref", "") or "").strip()
            if chosen_kind:
                session_context["resolved_connection_kind_hint"] = chosen_kind
            if chosen_ref:
                session_context["resolved_connection_ref_hint"] = chosen_ref

        return session_context

    @staticmethod
    def _find_action_candidate_payload(
        action_debug: dict[str, Any],
        *,
        candidate_kind: str,
        candidate_id: str,
    ) -> dict[str, Any] | None:
        clean_kind = normalize_action_candidate_kind(candidate_kind)
        clean_id = str(candidate_id or "").strip()
        for row in list(action_debug.get("candidates", []) or []):
            if not isinstance(row, dict):
                continue
            if normalize_action_candidate_kind(str(row.get("candidate_kind", "") or "").strip().lower()) != clean_kind:
                continue
            if str(row.get("candidate_id", "") or "").strip() != clean_id:
                continue
            payload = dict(row)
            payload["found"] = True
            return payload
        return None

    @staticmethod
    def _bounded_planner_candidate_ids() -> set[str]:
        candidates = dict(connection_routing_spec("ssh").preferred_action_candidates)
        return set(candidates.get("bounded_planner") or candidates.get("bounded_planner_poc") or ["ssh_run_command"])

    @staticmethod
    def _should_try_bounded_planner(resolved: dict[str, Any]) -> bool:
        routing = dict(resolved.get("decision", {}) or {})
        if normalize_connection_kind(str(routing.get("kind", "") or "")) != "ssh":
            return False
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        if len(Pipeline._payload_multi_target_refs(payload)) >= 2:
            return False
        connection_candidates = [row for row in list(resolved.get("connection_candidates_debug", []) or []) if isinstance(row, dict)]
        if len(connection_candidates) < 2:
            return False
        action_debug = dict(resolved.get("action_debug", {}) or {})
        candidates = [row for row in list(action_debug.get("candidates", []) or []) if isinstance(row, dict)]
        candidate_ids = {
            str(row.get("candidate_id", "") or "").strip()
            for row in candidates
            if normalize_action_candidate_kind(str(row.get("candidate_kind", "") or "").strip().lower()) in {"template", "recipe"}
        }
        allowed = Pipeline._bounded_planner_candidate_ids()
        return bool(candidate_ids & allowed)

    @staticmethod
    def _filter_bounded_planner_action_candidates(resolved: dict[str, Any]) -> dict[str, Any]:
        action_debug = dict(resolved.get("action_debug", {}) or {})
        candidates = [row for row in list(action_debug.get("candidates", []) or []) if isinstance(row, dict)]
        if not candidates:
            return resolved
        allowed = Pipeline._bounded_planner_candidate_ids()
        filtered = [
            row
            for row in candidates
            if str(row.get("candidate_kind", "") or "").strip().lower() == "template"
            and str(row.get("candidate_id", "") or "").strip() in allowed
        ]
        if filtered:
            action_debug["candidates"] = filtered
            resolved["action_debug"] = action_debug
        return resolved

    async def _apply_bounded_planner(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str = "",
        capability_draft: Any | None = None,
        language: str | None = None,
        llm_client: Any | None = None,
    ) -> dict[str, Any]:
        if not self._should_try_bounded_planner(resolved):
            return resolved

        resolved = self._filter_bounded_planner_action_candidates(resolved)

        routing = dict(resolved.get("decision", {}) or {})
        experience_rows = await self._recipe_experience_context_rows(
            user_id=user_id,
            message=message,
            connection_kind=str(resolved.get("preferred_kind", "") or routing.get("kind", "") or ""),
            connection_ref=str(routing.get("ref", "") or ""),
        )
        experience_context = self._format_recipe_experience_context(experience_rows)
        planner_input = self._build_planner_input_object_from_resolved(
            message=message,
            resolved=resolved,
            user_id=user_id,
            preferred_connection_kind=str(resolved.get("preferred_kind", "") or routing.get("kind", "") or ""),
            connection_ref=str(routing.get("ref", "") or ""),
            language=str(language or ""),
            notes=["ssh_status_agentic"],
            extra_session_context=experience_context,
        )
        planner_result = await debug_bounded_planner_decision(
            planner_input,
            llm_client=llm_client,
            language=str(language or ""),
        )
        resolved["planner_debug"] = planner_result

        planner_decision = dict(planner_result.get("decision", {}) or {})
        if not bool(planner_decision.get("found")):
            return resolved

        target_kind = normalize_connection_kind(str(planner_decision.get("target_kind", "") or ""))
        target_ref = str(planner_decision.get("target_ref", "") or "").strip()
        action_kind = str(planner_decision.get("action_candidate_type", "") or "").strip().lower()
        action_id = str(planner_decision.get("action_candidate_id", "") or "").strip()
        if not target_kind or not target_ref or not action_kind or not action_id:
            return resolved

        routing["kind"] = target_kind
        routing["ref"] = target_ref
        routing["found"] = True
        if bool(planner_decision.get("ask_user")):
            routing["routing_ask_user"] = True
        if str(planner_decision.get("reason", "") or "").strip():
            routing["reason"] = str(planner_decision.get("reason", "") or "").strip()
        resolved["decision"] = routing

        action_debug = dict(resolved.get("action_debug", {}) or {})
        selected_action = self._find_action_candidate_payload(
            action_debug,
            candidate_kind=action_kind,
            candidate_id=action_id,
        )
        if selected_action is None:
            return resolved
        if bool(planner_decision.get("ask_user")):
            selected_action["execution_state"] = "needs_confirmation"
        action_debug["decision"] = selected_action
        action_debug, capability_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision=routing,
            action_debug=action_debug,
            capability_draft=capability_draft,
            language=language,
            llm_client=self.llm_client,
        )
        resolved["action_debug"] = action_debug

        payload_debug = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing,
            action_decision=selected_action,
        )
        payload_debug = self._apply_capability_draft_overrides(
            payload_debug,
            capability_draft=capability_draft,
        )
        resolved["payload_debug"] = payload_debug
        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=routing,
            language=str(language or ""),
        )
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=routing,
            action_decision=selected_action,
            payload_debug=payload_debug,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )

        if self._routing_debug_enabled():
            detail_lines = [str(item or "").strip() for item in list(resolved.get("detail_lines", []) or []) if str(item or "").strip()]
            flow_line = agentic_prompt_flow_debug_line(
                build_agentic_prompt_flow(planner_input),
                planner_source=str(planner_result.get("planner_source", "") or "llm"),
            )
            if flow_line not in detail_lines:
                detail_lines.append(flow_line)
            for experience_line in self._recipe_experience_debug_lines(experience_rows):
                if experience_line not in detail_lines:
                    detail_lines.append(experience_line)
            line = (
                f"Planner: bounded_planner selected `{target_kind}/{target_ref}` + "
                f"`{action_kind}/{action_id}`"
            )
            confidence = str(planner_result.get("confidence", "") or "").strip().lower()
            if confidence:
                line += f" confidence={confidence}"
            if bool(planner_decision.get("ask_user")):
                line += " ask_user=true"
            line += f" boundary={AGENTIC_BOUNDARY_DRAFT}"
            reason = self._normalize_spaces(str(planner_decision.get("reason", "") or ""))[:180]
            planner_debug_line = (
                "Routing Debug: action_plan_debug "
                f"agentic_source={str(planner_result.get('planner_source', '') or 'llm').strip().lower() or 'llm'} "
                f"target={target_kind}/{target_ref} action={action_kind}/{action_id} "
                f"confidence={confidence or '-'} ask_user={str(bool(planner_decision.get('ask_user'))).lower()} "
                f"candidate_count={int(planner_result.get('candidate_count', 0) or 0)} "
                f"execution_state={str(planner_result.get('execution_state', '') or '-').strip() or '-'} "
                f"reason={reason or '-'} boundary={AGENTIC_BOUNDARY_DRAFT}"
            )
            if debug_line and debug_line not in detail_lines:
                detail_lines.append(debug_line)
            if planner_debug_line not in detail_lines:
                detail_lines.append(planner_debug_line)
            if line not in detail_lines:
                detail_lines.append(line)
            resolved["detail_lines"] = detail_lines
        return resolved

    async def _recipe_experience_context_rows(
        self,
        *,
        user_id: str,
        message: str,
        connection_kind: str = "",
        connection_ref: str = "",
        capability: str = "",
        intent: str = "",
    ) -> list[dict[str, Any]]:
        return await recipe_experience_context_rows(
            self.memory_skill,
            user_id=user_id,
            message=message,
            connection_kind=connection_kind,
            connection_ref=connection_ref,
            capability=capability,
            intent=intent,
            search=search_recipe_experience_memory,
        )

    async def _recipe_experience_context(
        self,
        *,
        user_id: str,
        message: str,
        connection_kind: str = "",
        connection_ref: str = "",
        capability: str = "",
        intent: str = "",
    ) -> dict[str, str]:
        return await recipe_experience_context(
            self.memory_skill,
            user_id=user_id,
            message=message,
            connection_kind=connection_kind,
            connection_ref=connection_ref,
            capability=capability,
            intent=intent,
            search=search_recipe_experience_memory,
        )

    @staticmethod
    def _format_recipe_experience_context(rows: list[dict[str, Any]]) -> dict[str, str]:
        return format_recipe_experience_context(rows)

    @staticmethod
    def _recipe_experience_debug_lines(rows: list[dict[str, Any]]) -> list[str]:
        return recipe_experience_debug_lines(rows)

    @staticmethod
    def _apply_capability_draft_overrides(
        payload_debug: dict[str, Any],
        *,
        capability_draft: Any | None,
    ) -> dict[str, Any]:
        payload = dict(payload_debug.get("payload", {}) or {})
        if not bool(payload.get("found")) or capability_draft is None:
            return payload_debug

        path_override = str(getattr(capability_draft, "path", "") or "").strip()
        content_override = str(getattr(capability_draft, "content", "") or "").strip()
        changed = False
        capability_override = str(getattr(capability_draft, "capability", "") or "").strip()
        if capability_override in {"file_list", "file_read", "file_write"} and payload.get("capability") != capability_override:
            payload["capability"] = capability_override
            changed = True
        if capability_override == "file_list" and not str(payload.get("path", "") or "").strip():
            payload["path"] = "."
            payload["missing_fields"] = [
                str(item or "").strip()
                for item in list(payload.get("missing_fields", []) or [])
                if str(item or "").strip() and str(item or "").strip() != "path"
            ]
            connection_kind = str(payload.get("connection_kind", "") or "").strip()
            prefix = "List remote path" if connection_kind == "sftp" else "List share path" if connection_kind == "smb" else "List path"
            payload["preview"] = f"{prefix}: ."
            changed = True
        plan_class_override = str(getattr(capability_draft, "plan_class", "") or "").strip()
        if plan_class_override:
            payload["plan_class"] = plan_class_override
            changed = True
        behavior_profile_override = str(getattr(capability_draft, "behavior_profile", "") or "").strip()
        if behavior_profile_override:
            payload["behavior_profile"] = behavior_profile_override
            changed = True
        if path_override:
            payload["path"] = path_override
            missing_fields = [
                str(item or "").strip()
                for item in list(payload.get("missing_fields", []) or [])
                if str(item or "").strip() and str(item or "").strip() != "path"
            ]
            payload["missing_fields"] = missing_fields
            capability = str(payload.get("capability", "") or "").strip()
            connection_kind = str(payload.get("connection_kind", "") or "").strip()
            if capability == "file_list":
                prefix = "List remote path" if connection_kind == "sftp" else "List share path" if connection_kind == "smb" else "List path"
                payload["preview"] = f"{prefix}: {path_override}"
            elif capability == "file_read":
                prefix = "Read remote path" if connection_kind == "sftp" else "Read share path" if connection_kind == "smb" else "Read path"
                payload["preview"] = f"{prefix}: {path_override}"
            elif capability == "file_write":
                prefix = "Write remote path" if connection_kind == "sftp" else "Write share path" if connection_kind == "smb" else "Write path"
                payload["preview"] = f"{prefix}: {path_override}"
            elif capability == "calendar_read":
                payload["preview"] = f"Calendar range: {path_override}"
            elif capability == "mqtt_publish" and content_override:
                payload["preview"] = f"MQTT publish to {path_override}: {content_override}"
            changed = True
        if content_override:
            payload["content"] = content_override
            missing_fields = [
                str(item or "").strip()
                for item in list(payload.get("missing_fields", []) or [])
                if str(item or "").strip() and str(item or "").strip() != "content"
            ]
            payload["missing_fields"] = missing_fields
            capability = str(payload.get("capability", "") or "").strip()
            if capability == "discord_send":
                payload["preview"] = f"Discord message: {content_override}"
            elif capability == "webhook_send":
                payload["preview"] = f"Webhook payload: {content_override}"
            elif capability == "email_send":
                payload["preview"] = f"Email content: {content_override}"
            elif capability == "mail_search":
                payload["preview"] = f"Mailbox search: {content_override}"
            elif capability == "ssh_command":
                payload["preview"] = f"SSH command: {content_override}"
            elif capability == "calendar_read" and path_override:
                payload["preview"] = f"Calendar range: {path_override} · {content_override}"
            elif capability == "mqtt_publish" and path_override:
                payload["preview"] = f"MQTT publish to {path_override}: {content_override}"
            changed = True
        if changed:
            payload_debug["payload"] = payload
        return payload_debug

    @staticmethod
    def _draft_with_hint_path(draft: Any | None, hints: MemoryHints) -> Any | None:
        if draft is None or not str(getattr(hints, "path", "") or "").strip():
            return draft
        if str(getattr(draft, "path", "") or "").strip() not in {"", "."}:
            return draft
        return replace(draft, path=str(hints.path or "").strip())

    async def _build_kind_only_routed_resolution(
        self,
        message: str,
        *,
        connection_kind: str,
        language: str | None = None,
        llm_client: Any | None = None,
        capability_draft: Any | None = None,
        source: str = "kind_inferred",
        reason: str = "",
    ) -> dict[str, Any]:
        clean_kind = normalize_connection_kind(connection_kind)
        decision_payload = {
            "found": True,
            "kind": clean_kind,
            "ref": "",
            "capability": str(getattr(capability_draft, "capability", "") or "").strip(),
            "source": str(source or "kind_inferred").strip() or "kind_inferred",
            "score": 0.0,
            "reason": str(reason or clean_kind).strip(),
            "routing_ask_user": False,
            "routing_confidence": "",
            "routing_message": "",
        }
        action_debug = await debug_bounded_action_plan_decision(
            str(message or "").strip(),
            llm_client=llm_client,
            routing_decision=decision_payload,
            language=str(language or ""),
        )
        action_debug, capability_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=str(message or "").strip(),
            routing_decision=decision_payload,
            action_debug=dict(action_debug or {}),
            capability_draft=capability_draft,
            language=language,
            llm_client=self.llm_client,
        )
        action_debug, capability_draft, file_debug_line = await self._apply_agentic_file_operation_resolution(
            message=str(message or "").strip(),
            routing_decision=decision_payload,
            action_debug=dict(action_debug or {}),
            capability_draft=capability_draft,
            language=language,
            llm_client=self.llm_client,
        )
        action_debug, capability_draft, message_debug_line = await self._apply_agentic_message_operation_resolution(
            message=str(message or "").strip(),
            routing_decision=decision_payload,
            action_debug=dict(action_debug or {}),
            capability_draft=capability_draft,
            language=language,
            llm_client=self.llm_client,
        )
        action_debug, capability_draft, read_debug_line = await self._apply_agentic_read_operation_resolution(
            message=str(message or "").strip(),
            routing_decision=decision_payload,
            action_debug=dict(action_debug or {}),
            capability_draft=capability_draft,
            language=language,
            llm_client=self.llm_client,
        )
        payload_debug = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=decision_payload,
            action_decision=dict((action_debug or {}).get("decision", {}) or {}),
        )
        payload_debug = self._apply_capability_draft_overrides(
            payload_debug,
            capability_draft=capability_draft,
        )
        safety_debug = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=decision_payload,
            language=str(language or ""),
        )
        execution_debug = build_execution_preview_dry_run(
            routing_decision=decision_payload,
            action_decision=dict((action_debug or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=safety_debug,
            language=str(language or ""),
        )
        return {
            "status": "warn",
            "visual_status": "warn",
            "message": f"Routing still needs a concrete {clean_kind} profile.",
            "query": str(message or "").strip(),
            "preferred_kind": clean_kind or "auto",
            "requested_preferred_kind": clean_kind or "auto",
            "inferred_preferred_kind": clean_kind,
            "available_counts": {clean_kind: 0},
            "llm_ignore_deterministic": False,
            "deterministic": {},
            "detail_lines": [line for line in (debug_line, file_debug_line, message_debug_line, read_debug_line) if line],
            "qdrant": {
                "enabled": False,
                "message": "",
                "error": "",
                "candidate_count": 0,
                "accepted_count": 0,
                "candidates": [],
            },
            "decision": decision_payload,
            "llm_debug": {},
            "action_debug": action_debug,
            "payload_debug": payload_debug,
            "safety_debug": safety_debug,
            "execution_debug": execution_debug,
            "executed": False,
            "updated_at": "",
        }

    async def _resolve_unified_routed_action(
        self,
        message: str,
        *,
        user_id: str,
        language: str | None = None,
        capability_draft: Any | None = None,
        llm_client: Any | None | object = ...,
    ) -> dict[str, Any] | None:
        effective_llm_client = self.llm_client if llm_client is ... else llm_client
        effective_kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        if not effective_kind:
            effective_kind = infer_preferred_connection_kind(
                message,
                available_kinds=self._unified_routing_connection_pools().keys(),
            )
        connection_pools = self._unified_routing_connection_pools()
        candidate_connections = connection_pools.get(effective_kind, {}) if effective_kind else {}
        if isinstance(candidate_connections, dict) and len(candidate_connections) <= 1:
            effective_llm_client = None

        working_draft = capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(capability="", connection_kind=effective_kind)
        if effective_kind == "rss":
            effective_llm_client = None
        semantic_llm_client = (
            self.llm_client
            if self.llm_client is not None
            and effective_kind != "rss"
            and not str(getattr(working_draft, "explicit_connection_ref", "") or "").strip()
            else None
        )

        resolved = await self._resolve_live_routing_chain(
            message,
            preferred_kind=effective_kind,
            llm_client=effective_llm_client,
            language=language,
        )
        resolved = self._append_debug_detail_lines(
            resolved,
            agentic_context_debug_line(
                "capability_draft",
                {
                    "capability": str(getattr(working_draft, "capability", "") or "").strip() or "-",
                    "kind": effective_kind or "-",
                    "explicit_ref": str(getattr(working_draft, "explicit_connection_ref", "") or "").strip() or "-",
                    "requested_ref": str(getattr(working_draft, "requested_connection_ref", "") or "").strip() or "-",
                    "path": str(getattr(working_draft, "path", "") or "").strip() or "-",
                    "content": str(getattr(working_draft, "content", "") or "").strip() or "-",
                },
            ),
            agentic_context_debug_line(
                "candidate_pool",
                {
                    "effective_kind": effective_kind or "-",
                    "candidates": ", ".join(sorted(str(ref).strip() for ref in candidate_connections.keys() if str(ref).strip())) or "-",
                },
            ),
        )
        if effective_llm_client is not None and not self._resolved_routing_chain_complete(resolved):
            fallback_resolved = await self._resolve_live_routing_chain(
                message,
                preferred_kind=effective_kind,
                llm_client=None,
                language=language,
            )
            if self._resolved_routing_chain_has_signal(fallback_resolved):
                resolved = fallback_resolved
        resolved = self._append_resolved_chain_routing_record(resolved)
        resolved, working_draft = await self._refresh_resolved_agentic_ssh_command(
            resolved,
            message=message,
            user_id=user_id,
            capability_draft=working_draft,
            language=language,
        )
        resolved, working_draft = await self._refresh_resolved_agentic_file_operation(
            resolved,
            message=message,
            user_id=user_id,
            capability_draft=working_draft,
            language=language,
        )
        resolved, working_draft = await self._refresh_resolved_agentic_message_operation(
            resolved,
            message=message,
            user_id=user_id,
            capability_draft=working_draft,
            language=language,
        )
        resolved, working_draft = await self._refresh_resolved_agentic_read_operation(
            resolved,
            message=message,
            user_id=user_id,
            capability_draft=working_draft,
            language=language,
        )
        chain_complete = self._resolved_routing_chain_complete(resolved)

        if chain_complete and (not isinstance(candidate_connections, dict) or not candidate_connections):
            return self._apply_requested_connection_guard(resolved, capability_draft=working_draft, language=language)

        if not isinstance(candidate_connections, dict) or not candidate_connections:
            return None

        explicit_ref = str(getattr(working_draft, "explicit_connection_ref", "") or "").strip()
        requested_ref_hint = str(getattr(working_draft, "requested_connection_ref", "") or "").strip()
        contract_target_refs = [
            ref for ref in self._capability_draft_target_refs(working_draft) if ref in candidate_connections
        ]
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if (
            effective_kind == "ssh"
            and len(contract_target_refs) >= 2
            and self._capability_draft_has_multi_target_scope(working_draft)
        ):
            expand_to_fleet = self._ssh_multi_target_contract_should_expand_to_fleet(
                message=message,
                capability_draft=working_draft,
                contract_target_refs=contract_target_refs,
                candidate_connections=candidate_connections,
            )
            scoped_connections = (
                dict(candidate_connections)
                if expand_to_fleet
                else {
                    ref: candidate_connections[ref]
                    for ref in contract_target_refs
                    if ref in candidate_connections
                }
            )
            if expand_to_fleet:
                resolved = self._append_debug_detail_lines(
                    resolved,
                    "Routing Debug: plural_target_scope expanded_by_fleet_contract "
                    "kind=ssh "
                    f"selected_refs={', '.join(contract_target_refs)} "
                    f"expanded_refs={', '.join(scoped_connections.keys())} source=meta_catalog",
                )
            resolved = self._append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope bound_by_turn_contract "
                f"kind=ssh refs={', '.join(scoped_connections.keys())} source=meta_catalog",
            )
            contract_resolved = await self._build_kind_only_routed_resolution(
                message,
                connection_kind=effective_kind,
                language=language,
                llm_client=None,
                capability_draft=working_draft,
                source="turn_contract_targets",
                reason=", ".join(scoped_connections.keys()),
            )
            contract_resolved["detail_lines"] = self._resolved_routing_detail_lines(resolved)
            contract_candidates = self._semantic_connection_resolver.collect_connection_candidates(
                message,
                {effective_kind: scoped_connections},
                preferred_kind=effective_kind,
            )
            contract_resolved = self._append_routing_record_to_resolved(
                contract_resolved,
                build_routing_decision_record(
                    stage="turn_contract_target_resolution",
                    candidates=contract_candidates,
                    hint=SemanticConnectionHint(
                        connection_kind=effective_kind,
                        connection_ref="",
                        source="turn_contract_targets",
                        note=", ".join(scoped_connections.keys()),
                    ),
                    preferred_kind=effective_kind,
                ),
            )
            contract_resolved = self._attach_connection_candidates_debug(contract_resolved, contract_candidates)
            contract_resolved, working_draft = await self._prepare_ssh_plural_multi_target_command(
                contract_resolved,
                message=message,
                user_id=user_id,
                candidate_connections=scoped_connections,
                capability_draft=working_draft,
                language=language,
            )
            contract_resolved = self._apply_ssh_plural_multi_target_resolution(
                contract_resolved,
                candidate_connections=scoped_connections,
                capability_draft=working_draft,
                language=language,
            )
            contract_payload = dict((contract_resolved.get("payload_debug") or {}).get("payload", {}) or {})
            if len(self._payload_multi_target_refs(contract_payload)) >= 2:
                return self._apply_requested_connection_guard(
                    contract_resolved,
                    capability_draft=working_draft,
                    language=language,
                )
            resolved = self._append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope turn_contract_multi_target_skipped "
                "reason=policy_or_command_not_multi_target_safe",
            )
        if explicit_ref and effective_kind == "ssh":
            narrowed_resolved, scoped_connections, _semantic_scope_candidates = (
                self._narrow_ssh_plural_target_connections_by_context(
                    resolved,
                    message=message,
                    candidate_connections=candidate_connections,
                )
            )
            explicit_ref_score = connection_label_match_score(message, explicit_ref)
            if len(scoped_connections) > 1 and explicit_ref in scoped_connections and explicit_ref_score < 1000:
                resolved = narrowed_resolved
                explicit_ref = ""
                draft_notes = [
                    str(note or "").strip()
                    for note in list(getattr(working_draft, "notes", []) or [])
                    if str(note or "").strip()
                ]
                if "target_scope:multi_target" not in {note.lower() for note in draft_notes}:
                    draft_notes.append("target_scope:multi_target")
                working_draft = with_capability_draft_updates(
                    working_draft,
                    explicit_connection_ref="",
                    requested_connection_ref="",
                    notes=draft_notes,
                )
        if explicit_ref and explicit_ref in candidate_connections:
            explicit_hints = await self._memory_assist.resolve(
                draft=working_draft,
                message=message,
                user_id=user_id,
                available_connections=candidate_connections,
            )
            working_draft = self._draft_with_hint_path(working_draft, explicit_hints)
            if str(getattr(explicit_hints, "path", "") or "").strip():
                resolved = self._append_debug_detail_lines(
                    resolved,
                    "Routing Debug: memory_hint "
                    f"source={str(explicit_hints.source or '').strip() or '-'} "
                    f"ref={str(explicit_hints.connection_ref or '').strip() or '-'} "
                    f"matched_text={str(explicit_hints.matched_text or explicit_hints.path or '').strip() or '-'}",
                )
            explicit_candidates = self._semantic_connection_resolver.collect_connection_candidates(
                message,
                {effective_kind: candidate_connections},
                preferred_kind=effective_kind,
            )
            if (
                self.llm_client is not None
                and effective_kind != "rss"
                and len(candidate_connections) >= 2
                and message_has_connection_disambiguation_terms(message)
            ):
                semantic_hint = await self._semantic_connection_resolver.resolve_connection_with_llm(
                    message,
                    {effective_kind: candidate_connections},
                    preferred_kind=effective_kind,
                    force_llm=True,
                    include_all_profiles=True,
                )
                if semantic_hint.connection_ref and semantic_hint.connection_ref in candidate_connections:
                    if semantic_hint.connection_ref != explicit_ref:
                        resolved = self._append_debug_detail_lines(
                            resolved,
                            "Routing Debug: explicit_ref_reconsidered_by_semantic_llm "
                            f"from={explicit_ref} to={semantic_hint.connection_ref} note={semantic_hint.note or '-'}",
                        )
                        explicit_ref = semantic_hint.connection_ref
                        working_draft = with_capability_draft_updates(
                            working_draft,
                            explicit_connection_ref=explicit_ref,
                        )
                    else:
                        resolved = self._append_debug_detail_lines(
                            resolved,
                            "Routing Debug: explicit_ref_confirmed_by_semantic_llm "
                            f"ref={explicit_ref} note={semantic_hint.note or '-'}",
                        )
            resolved = self._append_debug_detail_lines(
                resolved,
                f"Routing Debug: explicit_ref selected ref={explicit_ref}",
            )
            explicit_resolved = await self._build_forced_routed_resolution(
                message,
                connection_kind=effective_kind,
                connection_ref=explicit_ref,
                language=language,
                llm_client=None,
                capability_draft=working_draft,
                source="explicit_ref",
                reason=explicit_ref,
            )
            explicit_resolved["detail_lines"] = [
                *self._resolved_routing_detail_lines(resolved),
                *self._resolved_routing_detail_lines(explicit_resolved),
            ]
            explicit_resolved = self._append_routing_record_to_resolved(
                explicit_resolved,
                build_routing_decision_record(
                    stage="explicit_connection_resolution",
                    candidates=explicit_candidates,
                    hint=SemanticConnectionHint(
                        connection_kind=effective_kind,
                        connection_ref=explicit_ref,
                        source="explicit_ref",
                        note=explicit_ref,
                    ),
                    preferred_kind=effective_kind,
                ),
            )
            explicit_resolved = self._attach_connection_candidates_debug(explicit_resolved, explicit_candidates)
            return self._apply_requested_connection_guard(
                explicit_resolved,
                capability_draft=working_draft,
                language=language,
            )

        plural_target_scope = self._capability_draft_has_multi_target_scope(working_draft)
        if (
            plural_target_scope
            and effective_kind == "ssh"
            and requested_ref_hint
            and self._ssh_plural_context_has_single_target_disambiguator(message)
        ):
            plural_target_scope = False
            resolved = self._append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope disabled_by_requested_single_target "
                f"requested_ref={requested_ref_hint}",
            )
        if callable(looks_like_plural_target) and not plural_target_scope and not explicit_ref and not requested_ref_hint:
            try:
                plural_target_scope = bool(looks_like_plural_target(message, effective_kind))
            except Exception:
                plural_target_scope = False
        if plural_target_scope:
            resolved = self._append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope blocks_single_target_resolution "
                f"kind={effective_kind or '-'}",
            )
        if (
            effective_kind == "ssh"
            and requested_ref_hint
            and not explicit_ref
            and not plural_target_scope
            and not self._ssh_plural_context_has_single_target_disambiguator(message)
            and len(candidate_connections) >= 2
        ):
            narrowed_resolved, scoped_connections, semantic_scope_candidates = (
                self._narrow_ssh_plural_target_connections_by_context(
                    resolved,
                    message=message,
                    candidate_connections=candidate_connections,
                )
            )
            if 1 < len(scoped_connections) < len(candidate_connections):
                plural_target_scope = True
                candidate_connections = scoped_connections
                resolved = self._append_debug_detail_lines(
                    narrowed_resolved,
                    "Routing Debug: plural_target_scope enabled_by_requested_ref_context "
                    f"requested_ref={requested_ref_hint} refs={', '.join(scoped_connections.keys())}",
                )
        if (
            effective_kind == "rss"
            and len(candidate_connections) == 1
            and not explicit_ref
            and not requested_ref_hint
        ):
            only_ref = next(iter(candidate_connections.keys()), "")
            only_ref = str(only_ref or "").strip()
            if only_ref:
                single_candidates = self._semantic_connection_resolver.collect_connection_candidates(
                    message,
                    {effective_kind: candidate_connections},
                    preferred_kind=effective_kind,
                )
                resolved = self._append_debug_detail_lines(
                    resolved,
                    f"Routing Debug: single_rss_profile selected ref={only_ref}",
                )
                single_resolved = await self._build_forced_routed_resolution(
                    message,
                    connection_kind=effective_kind,
                    connection_ref=only_ref,
                    language=language,
                    llm_client=None,
                    capability_draft=working_draft,
                    source="default_single_profile",
                    reason=only_ref,
                )
                single_resolved["detail_lines"] = self._resolved_routing_detail_lines(resolved)
                single_resolved = self._append_routing_record_to_resolved(
                    single_resolved,
                    build_routing_decision_record(
                        stage="single_connection_resolution",
                        candidates=single_candidates,
                        hint=SemanticConnectionHint(
                            connection_kind=effective_kind,
                            connection_ref=only_ref,
                            source="default_single_profile",
                            note=only_ref,
                        ),
                        preferred_kind=effective_kind,
                    ),
                )
                single_resolved = self._attach_connection_candidates_debug(single_resolved, single_candidates)
                return self._apply_requested_connection_guard(
                    single_resolved,
                    capability_draft=working_draft,
                    language=language,
                )

        hints = await self._memory_assist.resolve(
            draft=working_draft,
            message=message,
            user_id=user_id,
            available_connections=candidate_connections,
        )
        resolved = self._append_debug_detail_lines(
            resolved,
            "Routing Debug: memory_hint "
            f"source={str(hints.source or '').strip() or '-'} "
            f"ref={str(hints.connection_ref or '').strip() or '-'} "
            f"matched_text={str(hints.matched_text or '').strip() or '-'}",
        )
        semantic_record: Any | None = None
        semantic_candidates = self._semantic_connection_resolver.collect_connection_candidates(
            message,
            {effective_kind: candidate_connections},
            preferred_kind=effective_kind,
        )
        if (
            str(hints.connection_ref or "").strip()
            and str(hints.source or "").strip() == "memory_hint"
            and semantic_candidates
        ):
            top_candidate = semantic_candidates[0]
            top_ref = str(top_candidate.connection_ref or "").strip()
            top_score = int(getattr(top_candidate, "score", 0) or 0)
            if (
                top_ref
                and top_ref != str(hints.connection_ref or "").strip()
                and top_score >= 1000
                and not requested_ref_hint
                and not plural_target_scope
            ):
                old_ref = str(hints.connection_ref or "").strip()
                resolved = self._append_debug_detail_lines(
                    resolved,
                    "Routing Debug: memory_hint ignored_by_explicit_target "
                    f"ref={old_ref} explicit_ref={top_ref}",
                )
                resolved = self._append_debug_detail_lines(
                    resolved,
                    f"Routing Debug: explicit_ref selected ref={top_ref}",
                )
                hints = replace(
                    hints,
                    connection_kind=top_candidate.connection_kind or effective_kind,
                    connection_ref=top_ref,
                    source="explicit_ref",
                    matched_text=top_ref,
                    notes=list(hints.notes) + ([top_candidate.note] if top_candidate.note else []),
                )
                semantic_record = build_routing_decision_record(
                    stage="explicit_connection_resolution",
                    candidates=semantic_candidates,
                    hint=SemanticConnectionHint(
                        connection_kind=top_candidate.connection_kind or effective_kind,
                        connection_ref=top_ref,
                        source="explicit_ref",
                        note=top_ref,
                    ),
                    preferred_kind=effective_kind,
                )
        planner_connection_candidates = list(semantic_candidates)
        if not planner_connection_candidates:
            planner_connection_candidates = self._routing_candidates_from_resolved(resolved)
        if (
            not chain_complete
            and not str(hints.connection_ref or "").strip()
            and not plural_target_scope
            and semantic_candidates
            and not (effective_kind == "rss" and self._rss_candidates_need_semantic_refine(semantic_candidates))
        ):
            semantic_hint = self._semantic_connection_resolver.resolve_connection(
                message,
                {effective_kind: candidate_connections},
            )
            if semantic_hint.connection_ref and (
                not requested_ref_hint
                or self._requested_connection_ref_matches_candidate(
                    requested_ref_hint,
                    connection_kind=effective_kind,
                    connection_ref=semantic_hint.connection_ref,
                    row=dict(candidate_connections).get(semantic_hint.connection_ref, {}),
                )
            ):
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or effective_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
                semantic_record = build_routing_decision_record(
                    stage="semantic_candidate_resolution",
                    candidates=semantic_candidates,
                    hint=semantic_hint,
                    preferred_kind=effective_kind,
                )
            elif semantic_hint.connection_ref and requested_ref_hint:
                resolved = self._append_debug_detail_lines(
                    resolved,
                    "Routing Debug: semantic_hint blocked "
                    f"requested_ref={requested_ref_hint} ref={semantic_hint.connection_ref}",
                )
        if (
            not chain_complete
            and
            not str(hints.connection_ref or "").strip()
            and not plural_target_scope
            and semantic_llm_client is not None
            and len(candidate_connections) >= 2
            and (
                bool(requested_ref_hint)
                or not semantic_candidates
                or int(getattr(semantic_candidates[0], "score", 0) or 0) < 1000
            )
        ):
            semantic_hint = await self._semantic_connection_resolver.resolve_connection_with_llm(
                message,
                {effective_kind: candidate_connections},
                preferred_kind=effective_kind,
            )
            if semantic_hint.connection_ref and (
                not requested_ref_hint
                or self._requested_connection_ref_matches_candidate(
                    requested_ref_hint,
                    connection_kind=effective_kind,
                    connection_ref=semantic_hint.connection_ref,
                    row=dict(candidate_connections).get(semantic_hint.connection_ref, {}),
                )
            ):
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or effective_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
                semantic_record = build_routing_decision_record(
                    stage="semantic_llm_resolution",
                    candidates=semantic_candidates,
                    hint=semantic_hint,
                    preferred_kind=effective_kind,
                )
            elif semantic_hint.connection_ref and requested_ref_hint:
                resolved = self._append_debug_detail_lines(
                    resolved,
                    "Routing Debug: semantic_llm blocked "
                    f"requested_ref={requested_ref_hint} ref={semantic_hint.connection_ref}",
                )
        if (
            not chain_complete
            and str(hints.connection_ref or "").strip()
            and str(hints.source or "").strip() == "memory_hint"
            and effective_kind == "ssh"
            and not plural_target_scope
            and semantic_llm_client is not None
            and len(candidate_connections) >= 2
        ):
            semantic_hint = await self._semantic_connection_resolver.resolve_connection_with_llm(
                message,
                {effective_kind: candidate_connections},
                preferred_kind=effective_kind,
                force_llm=True,
                include_all_profiles=True,
            )
            if semantic_hint.connection_ref and semantic_hint.connection_ref in candidate_connections:
                old_ref = str(hints.connection_ref or "").strip()
                if semantic_hint.connection_ref != old_ref:
                    resolved = self._append_debug_detail_lines(
                        resolved,
                        "Routing Debug: memory_hint ignored_by_semantic_llm "
                        f"ref={old_ref} selected={semantic_hint.connection_ref}",
                    )
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or effective_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
                semantic_record = build_routing_decision_record(
                    stage="semantic_llm_resolution",
                    candidates=semantic_candidates,
                    hint=semantic_hint,
                    preferred_kind=effective_kind,
                )
        working_draft = self._draft_with_hint_path(working_draft, hints)

        if chain_complete:
            payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
            single_payload_ref = str(payload.get("connection_ref", "") or "").strip()
            if plural_target_scope and effective_kind == "ssh" and single_payload_ref:
                narrowed_resolved, scoped_connections, semantic_scope_candidates = (
                    self._narrow_ssh_plural_target_connections_by_context(
                        resolved,
                        message=message,
                        candidate_connections=candidate_connections,
                    )
                )
                single_payload_ref_score = connection_label_match_score(message, single_payload_ref)
                if (
                    len(scoped_connections) > 1
                    and single_payload_ref in scoped_connections
                    and single_payload_ref_score < 1000
                ):
                    multi_resolved = await self._build_kind_only_routed_resolution(
                        message,
                        connection_kind=effective_kind,
                        language=language,
                        llm_client=None,
                        capability_draft=working_draft,
                        source="plural_target_context",
                        reason=str(hints.matched_text or effective_kind),
                    )
                    multi_resolved["detail_lines"] = self._resolved_routing_detail_lines(narrowed_resolved)
                    multi_resolved = self._append_debug_detail_lines(
                        multi_resolved,
                        "Routing Debug: chain_complete_single_ref ignored_by_plural_target_context "
                        f"ref={single_payload_ref} refs={', '.join(scoped_connections.keys())}",
                    )
                    multi_resolved = self._append_routing_record_to_resolved(
                        multi_resolved,
                        build_routing_decision_record(
                            stage="plural_target_context_resolution",
                            candidates=semantic_scope_candidates or planner_connection_candidates,
                            hint=SemanticConnectionHint(
                                connection_kind=effective_kind,
                                connection_ref="",
                                source="plural_target_context",
                                note=", ".join(scoped_connections.keys()),
                            ),
                            preferred_kind=effective_kind,
                        ),
                    )
                    multi_resolved = self._attach_connection_candidates_debug(
                        multi_resolved,
                        semantic_scope_candidates or planner_connection_candidates,
                    )
                    multi_resolved, working_draft = await self._prepare_ssh_plural_multi_target_command(
                        multi_resolved,
                        message=message,
                        user_id=user_id,
                        candidate_connections=scoped_connections,
                        capability_draft=working_draft,
                        language=language,
                    )
                    multi_resolved = self._apply_ssh_plural_multi_target_resolution(
                        multi_resolved,
                        candidate_connections=scoped_connections,
                        capability_draft=working_draft,
                        language=language,
                    )
                    multi_payload = dict((multi_resolved.get("payload_debug") or {}).get("payload", {}) or {})
                    if len(self._payload_multi_target_refs(multi_payload)) >= 2:
                        return self._apply_requested_connection_guard(
                            multi_resolved,
                            capability_draft=working_draft,
                            language=language,
                        )
                    resolved = self._append_debug_detail_lines(
                        resolved,
                        "Routing Debug: plural_target_scope multi_target_rebuild_skipped "
                        "reason=policy_or_command_not_multi_target_safe",
                    )
            payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
            current_path = str(payload.get("path", "") or "").strip()
            if str(getattr(hints, "path", "") or "").strip() and current_path in {"", "."}:
                decision = dict(resolved.get("decision", {}) or {})
                rebuilt = await self._build_forced_routed_resolution(
                    message,
                    connection_kind=str(decision.get("kind", "") or effective_kind),
                    connection_ref=str(decision.get("ref", "") or hints.connection_ref or ""),
                    language=language,
                    llm_client=None,
                    capability_draft=working_draft,
                    source=str(decision.get("source", "") or "recent_context"),
                    reason=str(decision.get("reason", "") or hints.matched_text or hints.path or ""),
                )
                rebuilt["detail_lines"] = self._resolved_routing_detail_lines(resolved)
                resolved = rebuilt
            resolved = self._attach_connection_candidates_debug(resolved, planner_connection_candidates)
            return self._apply_requested_connection_guard(resolved, capability_draft=working_draft, language=language)

        forced_ref = str(hints.connection_ref or "").strip()
        requested_ref = str(getattr(working_draft, "requested_connection_ref", "") or "").strip()
        if forced_ref and plural_target_scope and effective_kind == "ssh":
            narrowed_resolved, scoped_connections, semantic_scope_candidates = (
                self._narrow_ssh_plural_target_connections_by_context(
                    resolved,
                    message=message,
                    candidate_connections=candidate_connections,
                )
            )
            forced_ref_score = connection_label_match_score(message, forced_ref)
            if len(scoped_connections) > 1 and forced_ref_score < 1000 and forced_ref not in scoped_connections:
                resolved = self._append_debug_detail_lines(
                    narrowed_resolved,
                    "Routing Debug: memory_hint ignored_by_plural_target_context "
                    f"ref={forced_ref} refs={', '.join(scoped_connections.keys())}",
                )
                hints = replace(
                    hints,
                    connection_ref="",
                    source="",
                    matched_text="",
                )
                forced_ref = ""
                planner_connection_candidates = semantic_scope_candidates or planner_connection_candidates
            elif len(scoped_connections) > 1 and forced_ref in scoped_connections and forced_ref_score < 1000:
                resolved = self._append_debug_detail_lines(
                    narrowed_resolved,
                    "Routing Debug: memory_hint ignored_by_plural_target_context "
                    f"ref={forced_ref} refs={', '.join(scoped_connections.keys())}",
                )
                hints = replace(
                    hints,
                    connection_ref="",
                    source="",
                    matched_text="",
                )
                forced_ref = ""
                planner_connection_candidates = semantic_scope_candidates or planner_connection_candidates
        if (
            forced_ref
            and requested_ref
            and str(hints.source or "").strip() == "memory_hint"
            and not self._requested_connection_ref_matches_candidate(
                requested_ref,
                connection_kind=effective_kind,
                connection_ref=forced_ref,
                row=dict(candidate_connections).get(forced_ref, {}),
            )
        ):
            resolved = self._append_debug_detail_lines(
                resolved,
                "Routing Debug: memory_hint blocked "
                f"requested_ref={requested_ref} ref={forced_ref}",
            )
            forced_ref = ""
        if not forced_ref and requested_ref and semantic_candidates:
            requested_hint = self._semantic_connection_resolver.resolve_connection(
                message,
                {effective_kind: candidate_connections},
            )
            if requested_hint.connection_ref and self._requested_connection_ref_matches_candidate(
                requested_ref,
                connection_kind=effective_kind,
                connection_ref=requested_hint.connection_ref,
                row=dict(candidate_connections).get(requested_hint.connection_ref, {}),
            ):
                hints = replace(
                    hints,
                    connection_kind=requested_hint.connection_kind or effective_kind,
                    connection_ref=requested_hint.connection_ref,
                    source=requested_hint.source or "semantic_alias",
                    notes=list(hints.notes) + ([requested_hint.note] if requested_hint.note else []),
                )
                forced_ref = str(requested_hint.connection_ref or "").strip()
                if forced_ref:
                    working_draft = with_capability_draft_updates(
                        working_draft,
                        explicit_connection_ref=forced_ref,
                        requested_connection_ref="",
                    )
                    resolved = self._append_debug_detail_lines(
                        resolved,
                        agentic_context_debug_line(
                            "capability_draft",
                            {
                                "capability": str(getattr(working_draft, "capability", "") or "-").strip() or "-",
                                "kind": effective_kind or "-",
                                "explicit_ref": forced_ref,
                                "requested_ref": "-",
                                "path": str(getattr(working_draft, "path", "") or "").strip() or "-",
                                "content": str(getattr(working_draft, "content", "") or "").strip() or "-",
                            },
                        ),
                    )
                    resolved = self._append_debug_detail_lines(
                        resolved,
                        f"Routing Debug: explicit_ref selected ref={forced_ref}",
                    )
                    resolved = self._append_debug_detail_lines(
                        resolved,
                        f"Routing: explicit_connection_resolution selected `{effective_kind}/{forced_ref}` source=explicit_ref note={forced_ref}",
                    )
                semantic_record = build_routing_decision_record(
                    stage="semantic_candidate_resolution",
                    candidates=semantic_candidates,
                    hint=requested_hint,
                    preferred_kind=effective_kind,
                )
        if not forced_ref and len(candidate_connections) == 1:
            forced_ref = str(next(iter(candidate_connections.keys())) or "").strip()
            if forced_ref and not str(hints.source or "").strip():
                hints = replace(hints, source="default_single_profile")
        if (
            not forced_ref
            and effective_kind == "rss"
            and candidate_connections
        ):
            semantic_hint = await self._semantic_connection_resolver.resolve_rss_ref(
                message,
                candidate_connections,
                candidates=semantic_candidates,
            )
            if semantic_hint.connection_ref:
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or effective_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
                forced_ref = str(semantic_hint.connection_ref or "").strip()
                semantic_record = build_routing_decision_record(
                    stage="rss_semantic_refine",
                    candidates=semantic_candidates,
                    hint=semantic_hint,
                    preferred_kind=effective_kind,
                )
        if not forced_ref:
            prior_plural_detail_lines = self._resolved_routing_detail_lines(resolved)
            kind_only = await self._build_kind_only_routed_resolution(
                message,
                connection_kind=effective_kind,
                language=language,
                llm_client=None,
                capability_draft=working_draft,
                source="kind_inferred",
                reason=str(hints.matched_text or effective_kind),
            )
            kind_only["detail_lines"] = prior_plural_detail_lines
            kind_only = self._append_routing_record_to_resolved(
                kind_only,
                build_routing_decision_record(
                    stage="kind_only_resolution",
                    candidates=[],
                    hint=SemanticConnectionHint(
                        connection_kind=effective_kind,
                        connection_ref="",
                        source="kind_inferred",
                        note=str(hints.matched_text or effective_kind),
                    ),
                    preferred_kind=effective_kind,
                ),
            )
            kind_only = self._attach_connection_candidates_debug(kind_only, planner_connection_candidates)
            if plural_target_scope:
                scoped_connections = candidate_connections
                kind_only, scoped_connections, semantic_scope_candidates = self._narrow_ssh_plural_target_connections_by_context(
                    kind_only,
                    message=message,
                    candidate_connections=candidate_connections,
                )
                if len(scoped_connections) == 1:
                    scoped_ref = str(next(iter(scoped_connections.keys())) or "").strip()
                    if scoped_ref:
                        scoped_resolved = await self._build_forced_routed_resolution(
                            message,
                            connection_kind=effective_kind,
                            connection_ref=scoped_ref,
                            language=language,
                            llm_client=None,
                            capability_draft=working_draft,
                            source="plural_target_context",
                            reason=scoped_ref,
                        )
                        scoped_resolved["detail_lines"] = self._resolved_routing_detail_lines(kind_only)
                        scoped_resolved = self._append_routing_record_to_resolved(
                            scoped_resolved,
                            build_routing_decision_record(
                                stage="plural_target_context_resolution",
                                candidates=semantic_scope_candidates or planner_connection_candidates,
                                hint=SemanticConnectionHint(
                                    connection_kind=effective_kind,
                                    connection_ref=scoped_ref,
                                    source="plural_target_context",
                                    note=scoped_ref,
                                ),
                                preferred_kind=effective_kind,
                            ),
                        )
                        scoped_resolved = self._attach_connection_candidates_debug(
                            scoped_resolved,
                            semantic_scope_candidates or planner_connection_candidates,
                        )
                        return self._apply_requested_connection_guard(
                            scoped_resolved,
                            capability_draft=working_draft,
                            language=language,
                        )
                kind_only, working_draft = await self._prepare_ssh_plural_multi_target_command(
                    kind_only,
                    message=message,
                    user_id=user_id,
                    candidate_connections=scoped_connections,
                    capability_draft=working_draft,
                    language=language,
                )
                kind_only = self._apply_ssh_plural_multi_target_resolution(
                    kind_only,
                    candidate_connections=scoped_connections,
                    capability_draft=working_draft,
                    language=language,
            )
            return self._apply_requested_connection_guard(kind_only, capability_draft=working_draft, language=language)

        if (
            effective_kind == "ssh"
            and forced_ref
            and not str(getattr(working_draft, "capability", "") or "").strip()
        ):
            working_draft = with_capability_draft_updates(
                working_draft,
                capability="ssh_command",
                connection_kind="ssh",
                explicit_connection_ref=forced_ref,
            )
            resolved = self._append_debug_detail_lines(
                resolved,
                agentic_context_debug_line(
                    "capability_draft",
                    {
                        "capability": "ssh_command",
                        "kind": "ssh",
                        "explicit_ref": forced_ref,
                        "requested_ref": "-",
                        "path": "-",
                        "content": str(getattr(working_draft, "content", "") or "").strip() or "-",
                    },
                ),
            )
        forced_resolved = await self._build_forced_routed_resolution(
            message,
            connection_kind=effective_kind,
            connection_ref=forced_ref,
            language=language,
            llm_client=None if str(hints.source or "").strip() in {"semantic_alias", "semantic_llm", "explicit_ref"} else effective_llm_client,
            capability_draft=working_draft,
            source=str(hints.source or "memory_hint"),
            reason=str(hints.matched_text or forced_ref),
        )
        forced_resolved["detail_lines"] = [
            *self._resolved_routing_detail_lines(resolved),
            *self._resolved_routing_detail_lines(forced_resolved),
        ]
        if semantic_record is not None:
            forced_resolved = self._append_routing_record_to_resolved(forced_resolved, semantic_record)
        forced_resolved = self._append_routing_record_to_resolved(
            forced_resolved,
            build_routing_decision_record(
                stage="forced_connection_resolution",
                candidates=[],
                hint=SemanticConnectionHint(
                    connection_kind=effective_kind,
                    connection_ref=forced_ref,
                    source=str(hints.source or "memory_hint"),
                    note=str(hints.matched_text or forced_ref),
                ),
                preferred_kind=effective_kind,
            ),
        )
        forced_resolved = self._attach_connection_candidates_debug(forced_resolved, planner_connection_candidates)
        if not self._resolved_routing_chain_complete(forced_resolved):
            payload = dict((forced_resolved.get("payload_debug") or {}).get("payload", {}) or {})
            missing_fields = [str(item or "").strip() for item in list(payload.get("missing_fields", []) or [])]
            if forced_ref and missing_fields == ["connection_ref"]:
                forced_resolved = await self._build_forced_routed_resolution(
                    message,
                    connection_kind=effective_kind,
                    connection_ref=forced_ref,
                    language=language,
                    llm_client=None,
                    capability_draft=working_draft,
                    source=str(hints.source or "memory_hint"),
                    reason=str(hints.matched_text or forced_ref),
                )
                forced_resolved["detail_lines"] = [
                    *self._resolved_routing_detail_lines(resolved),
                    *self._resolved_routing_detail_lines(forced_resolved),
                ]
                if semantic_record is not None:
                    forced_resolved = self._append_routing_record_to_resolved(forced_resolved, semantic_record)
                forced_resolved = self._append_routing_record_to_resolved(
                    forced_resolved,
                    build_routing_decision_record(
                        stage="forced_connection_resolution",
                        candidates=[],
                        hint=SemanticConnectionHint(
                            connection_kind=effective_kind,
                            connection_ref=forced_ref,
                            source=str(hints.source or "memory_hint"),
                            note=str(hints.matched_text or forced_ref),
                        ),
                        preferred_kind=effective_kind,
                    ),
                )
                forced_resolved = self._attach_connection_candidates_debug(forced_resolved, planner_connection_candidates)
                if self._resolved_routing_chain_complete(forced_resolved):
                    return self._apply_requested_connection_guard(forced_resolved, capability_draft=working_draft, language=language)
            kind_only = await self._build_kind_only_routed_resolution(
                message,
                connection_kind=effective_kind,
                language=language,
                llm_client=None,
                capability_draft=working_draft,
                source=str(hints.source or "kind_inferred"),
                reason=str(hints.matched_text or forced_ref or effective_kind),
            )
            kind_only["detail_lines"] = self._resolved_routing_detail_lines(resolved)
            kind_only = self._append_routing_record_to_resolved(
                kind_only,
                build_routing_decision_record(
                    stage="kind_only_resolution",
                    candidates=[],
                    hint=SemanticConnectionHint(
                        connection_kind=effective_kind,
                        connection_ref="",
                        source=str(hints.source or "kind_inferred"),
                        note=str(hints.matched_text or forced_ref or effective_kind),
                    ),
                    preferred_kind=effective_kind,
                ),
            )
            kind_only = self._attach_connection_candidates_debug(kind_only, planner_connection_candidates)
            return self._apply_requested_connection_guard(kind_only, capability_draft=working_draft, language=language)
        return self._apply_requested_connection_guard(forced_resolved, capability_draft=working_draft, language=language)

    @staticmethod
    def _resolved_routing_chain_complete(resolved: dict[str, Any]) -> bool:
        routing_decision = dict(resolved.get("decision", {}) or {})
        action_decision = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        return bool(routing_decision.get("found")) and bool(action_decision.get("found")) and bool(payload.get("found"))

    async def _build_forced_routed_resolution(
        self,
        message: str,
        *,
        connection_kind: str,
        connection_ref: str,
        language: str | None = None,
        llm_client: Any | None = None,
        capability_draft: Any | None = None,
        source: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        decision_payload = {
            "found": True,
            "kind": normalize_connection_kind(connection_kind),
            "ref": str(connection_ref or "").strip(),
            "capability": str(getattr(capability_draft, "capability", "") or "").strip(),
            "source": str(source or "memory_hint").strip() or "memory_hint",
            "score": 1.0,
            "reason": str(reason or connection_ref).strip(),
            "routing_ask_user": False,
            "routing_confidence": "",
            "routing_message": "",
        }
        action_debug = await debug_bounded_action_plan_decision(
            str(message or "").strip(),
            llm_client=llm_client,
            routing_decision=decision_payload,
            language=str(language or ""),
        )
        action_debug, capability_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=str(message or "").strip(),
            routing_decision=decision_payload,
            action_debug=dict(action_debug or {}),
            capability_draft=capability_draft,
            language=language,
            llm_client=self.llm_client,
        )
        payload_debug = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=decision_payload,
            action_decision=dict((action_debug or {}).get("decision", {}) or {}),
        )
        payload_debug = self._apply_capability_draft_overrides(
            payload_debug,
            capability_draft=capability_draft,
        )
        safety_debug = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=decision_payload,
            language=str(language or ""),
        )
        execution_debug = build_execution_preview_dry_run(
            routing_decision=decision_payload,
            action_decision=dict((action_debug or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=safety_debug,
            language=str(language or ""),
        )
        return {
            "status": "ok",
            "visual_status": "ok",
            "message": f"Forced routing selected {connection_kind}/{connection_ref}.",
            "query": str(message or "").strip(),
            "preferred_kind": normalize_connection_kind(connection_kind) or "auto",
            "requested_preferred_kind": normalize_connection_kind(connection_kind) or "auto",
            "inferred_preferred_kind": normalize_connection_kind(connection_kind),
            "available_counts": {normalize_connection_kind(connection_kind): 1},
            "llm_ignore_deterministic": False,
            "deterministic": {},
            "detail_lines": [debug_line] if debug_line else [],
            "qdrant": {
                "enabled": False,
                "message": "",
                "error": "",
                "candidate_count": 0,
                "accepted_count": 0,
                "candidates": [],
            },
            "decision": decision_payload,
            "llm_debug": {},
            "action_debug": action_debug,
            "payload_debug": payload_debug,
            "safety_debug": safety_debug,
            "execution_debug": execution_debug,
            "executed": False,
            "updated_at": "",
        }

    def _apply_requested_connection_guard(
        self,
        resolved: dict[str, Any],
        *,
        capability_draft: Any | None,
        language: str | None = None,
    ) -> dict[str, Any]:
        requested_ref = str(getattr(capability_draft, "requested_connection_ref", "") or "").strip()
        if not requested_ref:
            return resolved
        payload_debug = dict(resolved.get("payload_debug", {}) or {})
        payload = dict(payload_debug.get("payload", {}) or {})
        if not bool(payload.get("found")):
            return resolved
        actual_ref = str(payload.get("connection_ref", "") or "").strip()
        actual_refs = [
            str(item or "").strip()
            for item in list(payload.get("connection_refs", []) or [])
            if str(item or "").strip()
        ]
        routing_source = str(dict(resolved.get("decision", {}) or {}).get("source", "") or "").strip()
        payload["requested_connection_ref"] = requested_ref
        if actual_refs:
            payload_debug["payload"] = payload
            resolved["payload_debug"] = payload_debug
            return resolved
        if actual_ref and actual_ref.lower() == requested_ref.lower():
            payload_debug["payload"] = payload
            resolved["payload_debug"] = payload_debug
            return resolved
        connection_kind = str(payload.get("connection_kind", "") or dict(resolved.get("decision", {}) or {}).get("kind", "") or "").strip()
        connection_rows = self._unified_routing_connection_pools().get(connection_kind, {}) if connection_kind else {}
        if (
            actual_ref
            and connection_kind
            and actual_ref in dict(connection_rows or {})
            and self._requested_connection_ref_matches_candidate(
                requested_ref,
                connection_kind=connection_kind,
                connection_ref=actual_ref,
                row=dict(connection_rows or {}).get(actual_ref, {}),
            )
        ):
            payload_debug["payload"] = payload
            resolved["payload_debug"] = payload_debug
            return resolved
        if self._requested_connection_ref_is_soft_hint(requested_ref):
            if actual_ref:
                payload["requested_connection_ref"] = ""
                payload_debug["payload"] = payload
                resolved["payload_debug"] = payload_debug
                return resolved
            payload["requested_connection_ref"] = ""
            payload_debug["payload"] = payload
            resolved["payload_debug"] = payload_debug
            return resolved
        payload["connection_ref"] = ""
        missing_fields = [str(item or "").strip() for item in list(payload.get("missing_fields", []) or []) if str(item or "").strip()]
        if "connection_ref" not in missing_fields:
            missing_fields.insert(0, "connection_ref")
        payload["missing_fields"] = missing_fields
        payload["resolution_source"] = "requested_missing"
        payload_debug["payload"] = payload
        resolved["payload_debug"] = payload_debug
        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            language=str(language or ""),
        )
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_decision=dict((resolved.get("action_debug") or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )
        return resolved

    async def _execute_recipe_by_id(
        self,
        recipe_id: str,
        message: str,
        *,
        runtime_recipes: list[dict[str, Any]],
        language: str = "de",
    ) -> SkillResult:
        row = self._find_runtime_recipe(runtime_recipes, recipe_id)
        if row is None:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(recipe_id or "unknown"),
                content="",
                success=False,
                error=RECIPE_MANIFEST_MISSING_ERROR,
        )
        return await self._execute_custom_steps(row, message, language=language)

    def _build_multi_target_ssh_execution_handler(self) -> MultiTargetSSHExecutionHandler:
        def _remember_action(target_user_id: str, plan: ActionPlan) -> None:
            if self.capability_context_store is None:
                return
            try:
                self.capability_context_store.remember_action(
                    target_user_id,
                    capability=plan.capability,
                    connection_kind=plan.connection_kind,
                    connection_ref=plan.connection_ref,
                    path=plan.path,
                    content=plan.content,
                )
            except Exception:
                pass

        def _remember_multi_target_action(
            target_user_id: str,
            payload: dict[str, Any],
            refs: list[str],
            command: str,
            summary: str,
        ) -> None:
            if self.capability_context_store is None:
                return
            try:
                self.capability_context_store.remember_action(
                    target_user_id,
                    capability="ssh_command",
                    connection_kind="ssh",
                    connection_ref="",
                    path="",
                    content=command,
                    connection_refs=refs,
                    result_summary=summary,
                )
            except Exception:
                pass

        async def _execute_plan(plan: ActionPlan, target_language: str) -> str:
            return await self._executor_registry.execute(plan, language=target_language)

        async def _llm_summary(
            message: str,
            command: str,
            records: list[dict[str, str]],
            fallback_summary: str,
            target_language: str,
        ) -> tuple[str, str]:
            return await self._multi_target_ssh_llm_operator_summary(
                message=message,
                command=command,
                records=records,
                fallback_summary=fallback_summary,
                language=target_language,
            )

        return MultiTargetSSHExecutionHandler(
            MultiTargetSSHExecutionHooks(
                routing_debug_enabled=self._routing_debug_enabled,
                payload_to_action_plan=self._payload_to_action_plan,
                format_missing_message=lambda plan, target_language: self._format_capability_missing_message(
                    plan,
                    language=target_language,
                ),
                format_execution_error=lambda plan, exc, target_language: self._format_capability_execution_error(
                    plan,
                    exc,
                    language=target_language,
                ),
                build_capability_detail_lines=lambda plan, target_language: self._build_capability_detail_lines(
                    plan,
                    language=target_language,
                ),
                text=_pipeline_text,
                learning_service=self._agentic_execution_learning_service(),
                payload_multi_target_refs=self._payload_multi_target_refs,
                preflight_refs=self._preflight_multi_target_ssh_refs,
                execute_plan=_execute_plan,
                remember_action=_remember_action,
                remember_multi_target_action=_remember_multi_target_action,
                result_state=self._multi_target_ssh_result_state,
                extract_free_disk_threshold_gib=self._extract_free_disk_threshold_gib,
                extract_summary_free_disk_gib=self._extract_summary_free_disk_gib,
                operator_summary=lambda target_language, target_count, records: self._multi_target_ssh_operator_summary(
                    language=target_language,
                    target_count=target_count,
                    records=records,
                ),
                relevant_result_texts=self._multi_target_ssh_relevant_result_texts,
                llm_operator_summary=_llm_summary,
            )
        )

    def _agentic_execution_learning_service(self) -> AgenticExecutionLearningService:
        def _schedule(
            entry: dict[str, Any] | None,
            target_user_id: str,
            target_language: str,
            detail_lines: list[str],
            curate: bool,
        ) -> None:
            self._schedule_learned_recipe_followup(
                entry=entry,
                user_id=target_user_id,
                language=target_language,
                detail_lines=detail_lines,
                curate=curate,
            )

        return AgenticExecutionLearningService(schedule_followup=_schedule)

    def _build_rss_feed_execution_handler(self) -> RSSFeedExecutionHandler:
        def _remember_action(target_user_id: str, plan: ActionPlan) -> None:
            if self.capability_context_store is None:
                return
            try:
                self.capability_context_store.remember_action(
                    target_user_id,
                    capability=plan.capability,
                    connection_kind=plan.connection_kind,
                    connection_ref=plan.connection_ref,
                    path=plan.path,
                    content=plan.content,
                )
            except Exception:
                pass

        async def _execute_plan(plan: ActionPlan, target_language: str) -> str:
            return await self._executor_registry.execute(plan, language=target_language)

        async def _rss_group_bundle_for_query(query: str, selected_ref: str) -> tuple[str, list[str]] | None:
            return await self._rss_group_bundle_for_query(query, selected_ref=selected_ref)

        def _rss_group_bundle_from_candidate_aliases(
            query: str,
            selected_ref: str,
            candidate_rows: list[dict[str, Any]],
        ) -> tuple[str, list[str]] | None:
            return self._rss_group_bundle_from_candidate_aliases(
                query,
                selected_ref=selected_ref,
                candidate_rows=candidate_rows,
            )

        async def _rss_digest_options_note_for_query(query: str, target_language: str) -> str:
            return await self._rss_digest_options_note_for_query(query, language=target_language)

        return RSSFeedExecutionHandler(
            RSSFeedExecutionHooks(
                routing_debug_enabled=self._routing_debug_enabled,
                payload_to_action_plan=self._payload_to_action_plan,
                format_missing_message=lambda plan, target_language: self._format_capability_missing_message(
                    plan,
                    language=target_language,
                ),
                format_execution_error=lambda plan, exc, target_language: self._format_capability_execution_error(
                    plan,
                    exc,
                    language=target_language,
                ),
                build_capability_detail_lines=lambda plan, target_language: self._build_capability_detail_lines(
                    plan,
                    language=target_language,
                ),
                text=_pipeline_text,
                learning_service=self._agentic_execution_learning_service(),
                execute_plan=_execute_plan,
                remember_action=_remember_action,
                rss_group_bundle_for_query=_rss_group_bundle_for_query,
                rss_group_bundle_from_candidate_aliases=_rss_group_bundle_from_candidate_aliases,
                build_rss_group_bundle_note=self._build_rss_group_bundle_note,
                rss_digest_options_note_for_query=_rss_digest_options_note_for_query,
            )
        )

    def _build_generic_capability_execution_handler(self) -> GenericCapabilityExecutionHandler:
        def _remember_action(target_user_id: str, plan: ActionPlan) -> None:
            if self.capability_context_store is None:
                return
            try:
                self.capability_context_store.remember_action(
                    target_user_id,
                    capability=plan.capability,
                    connection_kind=plan.connection_kind,
                    connection_ref=plan.connection_ref,
                    path=plan.path,
                    content=plan.content,
                )
            except Exception:
                pass

        async def _execute_plan(plan: ActionPlan, target_language: str) -> str:
            return await self._executor_registry.execute(plan, language=target_language)

        async def _execute_content_access(
            plan: ActionPlan,
            target_user_id: str,
            target_language: str,
        ) -> tuple[str, list[str], list[str]] | None:
            return await self._execute_content_access_if_available(
                plan,
                user_id=target_user_id,
                language=target_language,
            )

        return GenericCapabilityExecutionHandler(
            GenericCapabilityExecutionHooks(
                routing_debug_enabled=self._routing_debug_enabled,
                payload_to_action_plan=self._payload_to_action_plan,
                format_missing_message=lambda plan, target_language: self._format_capability_missing_message(
                    plan,
                    language=target_language,
                ),
                format_execution_error=lambda plan, exc, target_language: self._format_capability_execution_error(
                    plan,
                    exc,
                    language=target_language,
                ),
                build_capability_detail_lines=lambda plan, target_language: self._build_capability_detail_lines(
                    plan,
                    language=target_language,
                ),
                text=_pipeline_text,
                learning_service=self._agentic_execution_learning_service(),
                execute_plan=_execute_plan,
                remember_action=_remember_action,
                execute_content_access=_execute_content_access,
                capability_execution_error_code=self._capability_execution_error_code,
            )
        )

    def _agentic_execution_handlers(self) -> list[AgenticExecutionHandler]:
        return [
            self._build_multi_target_ssh_execution_handler(),
            self._build_rss_feed_execution_handler(),
            self._build_generic_capability_execution_handler(),
        ]

    def _agentic_execution_registry(self) -> AgenticExecutionRegistry:
        return AgenticExecutionRegistry(self._agentic_execution_handlers())

    async def _execute_content_access_if_available(
        self,
        plan: ActionPlan,
        *,
        user_id: str,
        language: str,
    ) -> tuple[str, list[str], list[str]] | None:
        request = content_access_request_from_action_plan(
            plan,
            user_id=user_id,
            language=language,
        )
        if request is None:
            return None
        result = await self._content_access_registry.access_first(request)
        if result is None:
            return None
        detail_lines = list(result.detail_lines)
        if self._routing_debug_enabled():
            detail_lines.insert(
                0,
                "Routing Debug: agentic_content_access "
                f"kind={request.connection_kind} capability={request.capability} "
                f"planner_role={request.planner_role} sensitive_content={str(request.sensitive_content).lower()}",
            )
        return result.summary, detail_lines, list(result.errors)

    async def _execute_rss_feed_action(
        self,
        *,
        resolved: dict[str, Any],
        payload: dict[str, Any],
        action: dict[str, Any],
        user_id: str,
        language: str = "de",
    ) -> tuple[list[str], str, list[str], list[str]]:
        request = AgenticExecutionRequest(
            resolved=resolved,
            payload=payload,
            action=action,
            user_id=user_id,
            language=language,
        )
        result = await self._build_rss_feed_execution_handler().execute(request)
        return result.as_pipeline_tuple()

    async def _execute_multi_target_ssh_action(
        self,
        *,
        resolved: dict[str, Any],
        payload: dict[str, Any],
        action: dict[str, Any],
        user_id: str,
        language: str = "de",
    ) -> tuple[list[str], str, list[str], list[str]]:
        request = AgenticExecutionRequest(
            resolved=resolved,
            payload=payload,
            action=action,
            user_id=user_id,
            language=language,
        )
        result = await self._build_multi_target_ssh_execution_handler().execute(request)
        self._remember_runtime_outcome_frame(
            result.metadata.get("runtime_outcome") if isinstance(result.metadata, dict) else None,
            user_id=user_id,
            detail_lines=result.detail_lines,
        )
        return result.as_pipeline_tuple()

    def _remember_runtime_outcome_frame(self, payload: Any, *, user_id: str, detail_lines: list[str] | None = None) -> None:
        if not isinstance(payload, dict):
            return
        frame = RuntimeOutcomeFrame(
            surface_id=str(payload.get("surface_id", "") or ""),
            kind=str(payload.get("kind", "") or ""),
            capability=str(payload.get("capability", "") or ""),
            task_intent=str(payload.get("task_intent", "") or ""),
            command=str(payload.get("command", "") or ""),
            targets=tuple(payload.get("targets", []) or ()),
            records=tuple(row for row in list(payload.get("records", []) or []) if isinstance(row, dict)),
            summary=str(payload.get("summary", "") or ""),
            followup_affordances=tuple(payload.get("followup_affordances", []) or ()),
            confidence=0.92,
        )
        if not frame.as_payload():
            return
        self._runtime_outcome_frames[str(user_id or "web")] = frame
        if detail_lines is not None and self._routing_debug_enabled():
            detail_lines.append(
                "Routing Debug: runtime_outcome_frame stored "
                f"surface={frame.surface_id} kind={frame.kind} capability={frame.capability} "
                f"task_intent={frame.task_intent or '-'} targets={len(frame.targets)} "
                f"affordances={','.join(frame.followup_affordances) or '-'}"
            )

    async def _execute_routed_action(
        self,
        resolved: dict[str, Any],
        *,
        user_id: str,
        runtime_recipes: list[dict[str, Any]],
        language: str = "de",
    ) -> tuple[list[str], str, list[str], list[str]]:
        action = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        candidate_kind = normalize_action_candidate_kind(str(action.get("candidate_kind", "") or "").strip().lower())
        if is_recipe_candidate_kind(candidate_kind):
            recipe_id = str(action.get("candidate_id", "") or payload.get("skill_id", "") or "").strip()
            skill_result = await self._execute_recipe_by_id(
                recipe_id,
                resolved.get("query", "") or "",
                runtime_recipes=runtime_recipes,
                language=language,
            )
            intents = [build_recipe_intent(recipe_id)] if recipe_id else ["chat"]
            if not skill_result.success:
                raw_error = skill_result.error or "recipe_execution_failed"
                return intents, friendly_recipe_error_text(raw_error, language=language), [], [raw_error]
            detail_lines = self._collect_skill_detail_lines([skill_result])
            meta = skill_result.metadata or {}
            if bool(meta.get("direct_chat_response")):
                text = str(meta.get("direct_chat_text") or skill_result.content or "").strip()
            else:
                text = str(skill_result.content or "").strip()
            try:
                runtime_row = next(
                    (
                        dict(row or {})
                        for row in list(runtime_recipes or [])
                        if str((row or {}).get("id", "") or "").strip() == recipe_id
                    ),
                    {},
                )
                if runtime_row and not auto_learning_suppressed():
                    learned_entry = record_routed_stored_recipe_success(
                        row=runtime_row,
                        skill_result=skill_result,
                        recorder=record_successful_learned_recipe_execution,
                    )
                    self._schedule_learned_recipe_followup(
                        entry=learned_entry,
                        user_id=user_id,
                        language=language,
                        detail_lines=detail_lines,
                    )
            except Exception:
                pass
            return intents, text, detail_lines, []

        execution_request = AgenticExecutionRequest(
            resolved=resolved,
            payload=payload,
            action=action,
            user_id=user_id,
            language=language,
        )
        execution_result = await self._agentic_execution_registry().execute_first(execution_request)
        if execution_result is not None:
            return execution_result.as_pipeline_tuple()

        plan = self._payload_to_action_plan(payload)
        intents = [f"capability:{plan.capability}"] if str(plan.capability or "").strip() else ["chat"]
        return intents, self._format_capability_missing_message(plan, language=language), [], []

    async def _try_unified_routed_action(
        self,
        message: str,
        user_id: str,
        *,
        request_id: str,
        source: str,
        decision: Any,
        start: float,
        runtime_recipes: list[dict[str, Any]],
        capability_draft: Any | None = None,
        language: str | None = None,
    ) -> PipelineResult | None:
        strong_structured_signal = any(
            str(getattr(capability_draft, field, "") or "").strip()
            for field in ("explicit_connection_ref", "requested_connection_ref", "path", "content")
        )
        context_signal = False
        wants_previous_connection = getattr(self._memory_assist, "_wants_previous_connection", None)
        if callable(wants_previous_connection):
            try:
                context_signal = context_signal or bool(wants_previous_connection(message))
            except Exception:
                pass
        wants_previous_path = getattr(self._memory_assist, "_wants_previous_path", None)
        if callable(wants_previous_path):
            try:
                context_signal = context_signal or bool(wants_previous_path(message))
            except Exception:
                pass
        resolved = await self._resolve_unified_routed_action(
            message,
            user_id=user_id,
            language=language,
            capability_draft=capability_draft,
            llm_client=None if (strong_structured_signal or context_signal) else ...,
        )
        if resolved is None:
            return None

        resolved["query"] = message
        if not (capability_draft is None and self._resolved_routing_chain_complete(resolved)):
            resolved = await self._apply_bounded_planner(
                resolved,
                message=message,
                user_id=user_id,
                capability_draft=capability_draft,
                language=language,
                llm_client=self.llm_client,
            )
        resolved = self._force_template_action_for_capability_draft(
            resolved,
            capability_draft=capability_draft,
            message=message,
            language=language,
        )
        resolved, capability_draft = await self._finalize_ssh_plural_multi_target_action(
            resolved,
            message=message,
            user_id=user_id,
            capability_draft=capability_draft,
            language=language,
        )
        action = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
        execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        routing_detail_lines = self._resolved_routing_detail_lines(resolved)
        next_step = self._resolved_next_step(safety=safety, execution=execution)
        candidate_kind = str(action.get("candidate_kind", "") or "").strip().lower()
        candidate_id = str(action.get("candidate_id", "") or "").strip()
        intents = self._routed_action_intents(action, payload)
        async def _log_routed_result(result_intents: list[str], skill_errors: list[str] | None = None) -> int:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._log_result_usage_snapshot(
                request_id=request_id,
                user_id=user_id,
                intents=result_intents,
                router_level=decision.level,
                duration_ms=duration_ms,
                source=source,
                skill_errors=list(skill_errors or []),
                extraction_model="bounded_routing_chain",
            )
            return duration_ms

        if next_step == "block":
            text, routing_detail_lines = await self._blocked_action_response_text(
                resolved,
                message=message,
                user_id=user_id,
                request_id=request_id,
                language=language,
                detail_lines=routing_detail_lines,
            )
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
            )

        payload_missing_fields = self._payload_missing_fields(payload)
        if self._should_backfill_missing_ssh_command(resolved=resolved, payload=payload):
            resolved = await self._refresh_missing_ssh_command_resolution(
                resolved=resolved,
                message=message,
                user_id=user_id,
                language=language,
            )
            action = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
            safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
            execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
            payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
            next_step = self._resolved_next_step(safety=safety, execution=execution)
            payload_missing_fields = self._payload_missing_fields(payload)
        if payload_missing_fields:
            plan = self._payload_to_action_plan(payload)
            text = self._format_capability_missing_message(plan, language=language)
            pending_missing_input = self._resolve_pending_missing_input(action, payload)
            if pending_missing_input:
                action = dict(action)
                action["missing_input"] = pending_missing_input
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
                pending_action=self._build_pending_action_state(
                    query=message,
                    candidate_kind=candidate_kind,
                    candidate_id=candidate_id,
                    resolved=resolved,
                    action=action,
                    payload=payload,
                    safety=safety,
                    execution=execution,
                ),
            )

        if str(action.get("missing_input", "") or "").strip():
            text = self._build_routed_missing_input_text(resolved, language=language)
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
                pending_action=self._build_pending_action_state(
                    query=message,
                    candidate_kind=candidate_kind,
                    candidate_id=candidate_id,
                    resolved=resolved,
                    action=action,
                    payload=payload,
                    safety=safety,
                    execution=execution,
                ),
            )

        if next_step == "ask_user":
            text = self._build_routed_confirmation_text(resolved, language=language)
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
                pending_action=self._build_pending_action_state(
                    query=message,
                    candidate_kind=candidate_kind,
                    candidate_id=candidate_id,
                    resolved=resolved,
                    action=action,
                    payload=payload,
                    safety=safety,
                    execution=execution,
                ),
            )

        action_text, result_text, detail_lines, errors = await self._execute_routed_action(
            resolved,
            user_id=user_id,
            runtime_recipes=runtime_recipes,
            language=str(language or "de"),
        )
        duration_ms = await _log_routed_result(action_text, errors)
        return self._build_routed_action_result(
            request_id=request_id,
            decision=decision,
            duration_ms=duration_ms,
            intents=action_text,
            text=result_text,
            detail_lines=[*routing_detail_lines, *detail_lines],
            skill_errors=errors,
        )

    async def execute_pending_routed_action(
        self,
        pending_action: dict[str, Any],
        *,
        user_id: str,
        source: str = "web",
        auto_memory_enabled: bool = False,
        language: str | None = None,
    ) -> PipelineResult:
        start = time.perf_counter()
        request_id = str(uuid4())
        decision = self.classify_routing(str(pending_action.get("query", "") or ""), language=language)
        candidate_kind = str(pending_action.get("candidate_kind", "") or "").strip().lower()
        candidate_id = str(pending_action.get("candidate_id", "") or "").strip()
        runtime_recipes = self._load_stored_recipe_runtime()
        resolved = {
            "query": str(pending_action.get("query", "") or ""),
            "decision": dict(pending_action.get("routing_decision", {}) or {}),
            "action_debug": {"decision": dict(pending_action.get("action_decision", {}) or {})},
            "payload_debug": {"payload": dict(pending_action.get("payload", {}) or {})},
            "safety_debug": {"decision": dict(pending_action.get("safety_decision", {}) or {})},
            "execution_debug": {"decision": dict(pending_action.get("execution_decision", {}) or {})},
        }
        safety_decision = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
        if str(safety_decision.get("action", "") or "").strip().lower() == "ask_user":
            payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
            notes = [
                str(item or "").strip()
                for item in list(payload.get("notes", []) or [])
                if str(item or "").strip()
            ]
            reason = str(safety_decision.get("reason", "") or "").strip()
            marker = f"user_confirmed_policy:{reason}" if reason else "user_confirmed_policy"
            if marker not in notes:
                notes.append(marker)
            payload["notes"] = notes
            resolved["payload_debug"] = {"payload": payload}
        routing_detail_lines = self._resolved_routing_detail_lines(resolved)
        result_intents, result_text, detail_lines, errors = await self._execute_routed_action(
            resolved,
            user_id=user_id,
            runtime_recipes=runtime_recipes,
            language=str(language or "de"),
        )
        if auto_memory_enabled:
            payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
            self._schedule_runtime_learning_outcome(
                event=connection_action_outcome_event(
                    message=str(pending_action.get("query", "") or ""),
                    user_id=user_id,
                    request_id=request_id,
                    candidate_kind=candidate_kind,
                    candidate_id=candidate_id,
                    payload=payload,
                    safety_decision=dict((resolved.get("safety_debug") or {}).get("decision", {}) or {}),
                    execution_decision=dict((resolved.get("execution_debug") or {}).get("decision", {}) or {}),
                    result_intents=result_intents,
                    skill_errors=errors,
                ),
                user_id=user_id,
            )
            if not errors:
                await self._schedule_host_artifact_learning_outcomes(
                    message=str(pending_action.get("query", "") or ""),
                    user_id=user_id,
                    request_id=request_id,
                    result_text=result_text,
                    payload=payload,
                )
        duration_ms = int((time.perf_counter() - start) * 1000)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=result_intents,
            router_level=decision.level,
            usage=self._zero_usage(),
            chat_model=self.settings.llm.model,
            embedding_model=self.settings.embeddings.model,
            embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            duration_ms=duration_ms,
            source=source,
            skill_errors=errors,
            extraction_model="bounded_routing_chain_confirm",
            extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
        )
        return self._build_routed_action_result(
            request_id=request_id,
            decision=decision,
            duration_ms=duration_ms,
            intents=result_intents,
            text=result_text,
            detail_lines=[*routing_detail_lines, *detail_lines],
            skill_errors=errors,
        )

    async def continue_pending_routed_action_input(
        self,
        pending_action: dict[str, Any],
        follow_up_message: str,
        *,
        user_id: str,
        source: str = "web",
        language: str | None = None,
    ) -> PipelineResult:
        start = time.perf_counter()
        request_id = str(uuid4())
        base_query = str(pending_action.get("query", "") or "").strip()
        decision = self.classify_routing(base_query, language=language)
        runtime_recipes = self._load_stored_recipe_runtime()
        draft, missing_input = self._pending_input_to_draft(pending_action, follow_up_message)
        if draft is None:
            resolved = {
                "query": base_query,
                "decision": dict(pending_action.get("routing_decision", {}) or {}),
                "action_debug": {"decision": dict(pending_action.get("action_decision", {}) or {})},
                "payload_debug": {"payload": dict(pending_action.get("payload", {}) or {})},
                "safety_debug": {"decision": dict(pending_action.get("safety_decision", {}) or {})},
                "execution_debug": {"decision": dict(pending_action.get("execution_decision", {}) or {})},
            }
            text = self._build_routed_missing_input_text(resolved, language=language)
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=self._pending_payload_intents(dict(pending_action.get("payload", {}) or {})),
                router_level=decision.level,
                usage=self._zero_usage(),
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[],
                extraction_model="bounded_routing_chain_missing_input",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=self._pending_payload_intents(dict(pending_action.get("payload", {}) or {})),
                text=text,
                detail_lines=self._resolved_routing_detail_lines({"detail_lines": list(pending_action.get("detail_lines", []) or []), "decision": dict(pending_action.get("routing_decision", {}) or {})}),
                skill_errors=[],
                pending_action=dict(pending_action),
            )

        routing_decision = dict(pending_action.get("routing_decision", {}) or {})
        connection_kind = normalize_connection_kind(str(routing_decision.get("kind", "") or draft.connection_kind))
        connection_ref = str(routing_decision.get("ref", "") or draft.explicit_connection_ref).strip()
        resolved = await self._build_forced_routed_resolution(
            base_query,
            connection_kind=connection_kind,
            connection_ref=connection_ref,
            language=language,
            llm_client=None,
            capability_draft=draft,
            source=str(routing_decision.get("source", "") or "pending_follow_up"),
            reason=str(routing_decision.get("reason", "") or connection_ref or connection_kind),
        )
        resolved["query"] = base_query
        resolved = self._apply_filled_pending_input(
            resolved,
            language=language,
        )

        action = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
        execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        routing_detail_lines = self._resolved_routing_detail_lines(resolved)
        next_step = self._resolved_next_step(safety=safety, execution=execution)
        candidate_kind = str(action.get("candidate_kind", "") or "").strip().lower()
        candidate_id = str(action.get("candidate_id", "") or "").strip()
        intents = self._routed_action_intents(action, payload)

        async def _log_routed_result(result_intents: list[str], skill_errors: list[str] | None = None) -> int:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=result_intents,
                router_level=decision.level,
                usage=self._zero_usage(),
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=list(skill_errors or []),
                extraction_model="bounded_routing_chain_missing_input",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return duration_ms

        payload_missing_fields = self._payload_missing_fields(payload)
        if payload_missing_fields or str(action.get("missing_input", "") or "").strip():
            text = self._build_routed_missing_input_text(resolved, language=language)
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
                pending_action=self._build_pending_action_state(
                    query=base_query,
                    candidate_kind=candidate_kind,
                    candidate_id=candidate_id,
                    resolved=resolved,
                    action=action,
                    payload=payload,
                    safety=safety,
                    execution=execution,
                ),
            )

        if next_step == "block":
            text, routing_detail_lines = await self._blocked_action_response_text(
                resolved,
                message=base_query,
                user_id=user_id,
                request_id=request_id,
                language=language,
                detail_lines=routing_detail_lines,
            )
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
            )

        if next_step == "ask_user":
            text = self._build_routed_confirmation_text(resolved, language=language)
            duration_ms = await _log_routed_result(intents, [])
            return self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=intents,
                text=text,
                detail_lines=routing_detail_lines,
                skill_errors=[],
                pending_action=self._build_pending_action_state(
                    query=base_query,
                    candidate_kind=candidate_kind,
                    candidate_id=candidate_id,
                    resolved=resolved,
                    action=action,
                    payload=payload,
                    safety=safety,
                    execution=execution,
                ),
            )

        result_intents, result_text, detail_lines, errors = await self._execute_routed_action(
            resolved,
            user_id=user_id,
            runtime_recipes=runtime_recipes,
            language=str(language or "de"),
        )
        duration_ms = await _log_routed_result(result_intents, errors)
        return self._build_routed_action_result(
            request_id=request_id,
            decision=decision,
            duration_ms=duration_ms,
            intents=result_intents,
            text=result_text,
            detail_lines=[*routing_detail_lines, *detail_lines],
            skill_errors=errors,
        )

    async def _try_ssh_command_action(
        self,
        message: str,
        *,
        language: str | None = None,
    ) -> tuple[list[str], str, list[str], ActionPlan, list[str]] | None:
        rows = getattr(getattr(self.settings, "connections", object()), "ssh", {})
        if not isinstance(rows, dict) or not rows:
            return None

        alias_rows: dict[str, list[str]] = {}
        for ref, row in rows.items():
            clean_ref = str(ref).strip()
            if clean_ref:
                alias_rows[clean_ref] = build_connection_aliases("ssh", clean_ref, row)

        draft = self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={"ssh": rows.keys()},
            available_connection_aliases_by_kind={"ssh": alias_rows} if alias_rows else None,
        )
        if draft is None or draft.capability != "ssh_command":
            return None

        hints = MemoryHints()
        qdrant_details: list[str] = []
        if not str(draft.explicit_connection_ref or "").strip():
            hints, qdrant_details, _qdrant_block_fallback = await self._resolve_qdrant_connection_hint(
                message,
                {"ssh": rows},
                preferred_kind="ssh",
                language=language,
            )

        plan = build_action_plan(draft, hints, available_connection_refs=sorted(rows.keys()))
        intent = [f"capability:{plan.capability}"]
        if not plan.is_complete:
            return intent, self._format_capability_missing_message(plan, language=language), qdrant_details, plan, []

        details = qdrant_details + self._build_capability_detail_lines(plan, language=language)
        try:
            result_text = await self._execute_ssh_command(plan, language=str(language or "de"))
        except Exception as exc:
            error_text = self._format_capability_execution_error(plan, exc, language=language)
            error_code = self._capability_execution_error_code(plan, exc)
            return intent, error_text, details, plan, [error_code]
        return intent, result_text, details, plan, []

    async def _try_capability_action(
        self,
        message: str,
        user_id: str,
        language: str | None = None,
    ) -> tuple[list[str], str, list[str], ActionPlan, list[str]] | None:
        connection_pools: dict[str, dict[str, Any]] = {}
        direct_gate_kinds = set(connection_action_direct_gate_executor_kinds())
        for kind in ordered_connection_kinds():
            if kind not in direct_gate_kinds:
                continue
            rows = getattr(getattr(self.settings, "connections", object()), kind, {})
            if isinstance(rows, dict) and rows:
                connection_pools[kind] = rows

        connection_aliases_by_kind: dict[str, dict[str, list[str]]] = {}
        for kind, rows in connection_pools.items():
            alias_rows: dict[str, list[str]] = {}
            for ref, row in rows.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                alias_rows[clean_ref] = build_connection_aliases(kind, clean_ref, row)
            if alias_rows:
                connection_aliases_by_kind[kind] = alias_rows

        draft = self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={kind: rows.keys() for kind, rows in connection_pools.items()},
            available_connection_aliases_by_kind=connection_aliases_by_kind,
        )
        if draft is None:
            return None

        connection_pools = self._filter_capability_connection_pools(draft.capability, connection_pools)
        if not connection_pools:
            plan = build_action_plan(draft, MemoryHints(), available_connection_refs=[])
            intent = [f"capability:{plan.capability}"]
            return intent, self._format_capability_missing_message(plan, language=language), [], plan, []
        if draft.connection_kind not in connection_pools:
            draft = replace(
                draft,
                connection_kind=next(iter(connection_pools.keys()), ""),
                explicit_connection_ref="",
            )

        candidate_connections = connection_pools.get(draft.connection_kind, {})
        hints = await self._memory_assist.resolve(
            draft=draft,
            message=message,
            user_id=user_id,
            available_connections=candidate_connections,
        )
        if (
            draft.connection_kind == "rss"
            and not hints.connection_ref
            and not str(draft.explicit_connection_ref or "").strip()
            and not str(draft.requested_connection_ref or "").strip()
            and len(candidate_connections) == 1
        ):
            only_ref = next(iter(candidate_connections.keys()), "")
            if str(only_ref or "").strip():
                hints = replace(
                    hints,
                    connection_kind=draft.connection_kind,
                    connection_ref=str(only_ref).strip(),
                    source="default_single_profile",
                )
        if (
            not hints.connection_ref
            and not str(draft.explicit_connection_ref or "").strip()
            and len(candidate_connections) == 1
            and (
                not str(draft.requested_connection_ref or "").strip()
                or self._requested_connection_ref_is_soft_hint(str(draft.requested_connection_ref or ""))
            )
        ):
            only_ref = next(iter(candidate_connections.keys()), "")
            if str(only_ref or "").strip():
                hints = replace(
                    hints,
                    connection_kind=draft.connection_kind,
                    connection_ref=str(only_ref).strip(),
                    source="default_single_profile",
                )
        qdrant_details: list[str] = []
        qdrant_block_fallback = False
        routing_records: list[Any] = []
        semantic_candidates = self._semantic_connection_resolver.collect_connection_candidates(
            message,
            {draft.connection_kind: candidate_connections},
            preferred_kind=draft.connection_kind,
        )
        if (
            not hints.connection_ref
            and candidate_connections
            and not (draft.connection_kind == "rss" and self._rss_candidates_need_semantic_refine(semantic_candidates))
        ):
            semantic_hint = self._semantic_connection_resolver.resolve_connection(message, {draft.connection_kind: candidate_connections})
            if semantic_hint.connection_ref:
                routing_records.append(
                    build_routing_decision_record(
                        stage="semantic_alias",
                        candidates=semantic_candidates,
                        hint=semantic_hint,
                        preferred_kind=draft.connection_kind,
                    )
                )
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        if (
            draft.connection_kind == "rss"
            and not draft.explicit_connection_ref
            and len(semantic_candidates) >= 2
            and hints.source in {"", "semantic_alias"}
            and int(getattr(semantic_candidates[0], "score", 0) or 0) < 1000
        ):
            semantic_hint = await self._semantic_connection_resolver.resolve_rss_ref(
                message,
                candidate_connections,
                candidates=semantic_candidates,
            )
            if semantic_hint.connection_ref:
                routing_records.append(
                    build_routing_decision_record(
                        stage="rss_semantic_refine",
                        candidates=semantic_candidates,
                        hint=semantic_hint,
                        preferred_kind=draft.connection_kind,
                    )
                )
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        if not hints.connection_ref and candidate_connections:
            qdrant_hints, qdrant_details, qdrant_block_fallback = await self._resolve_qdrant_connection_hint(
                message,
                connection_pools,
                preferred_kind=draft.connection_kind,
                language=language,
            )
            if qdrant_hints.connection_ref:
                hints = qdrant_hints
        if (
            draft.connection_kind != "rss"
            and not hints.connection_ref
            and candidate_connections
            and not qdrant_block_fallback
        ):
            semantic_hint = await self._semantic_connection_resolver.resolve_connection_with_llm(
                message,
                {draft.connection_kind: candidate_connections},
                preferred_kind=draft.connection_kind,
            )
            if semantic_hint.connection_ref:
                routing_records.append(
                    build_routing_decision_record(
                        stage="semantic_llm",
                        candidates=semantic_candidates,
                        hint=semantic_hint,
                        preferred_kind=draft.connection_kind,
                    )
                )
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        if not hints.connection_ref and draft.connection_kind == "rss" and not qdrant_block_fallback:
            semantic_hint = await self._semantic_connection_resolver.resolve_rss_ref(
                message,
                candidate_connections,
                candidates=semantic_candidates,
            )
            if semantic_hint.connection_ref:
                routing_records.append(
                    build_routing_decision_record(
                        stage="rss_semantic_llm_fallback",
                        candidates=semantic_candidates,
                        hint=semantic_hint,
                        preferred_kind=draft.connection_kind,
                    )
                )
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        hints = self._sanitize_capability_hints(
            draft.capability,
            hints,
            available_kinds=set(connection_pools.keys()),
        )
        resolved_kind = hints.connection_kind or draft.connection_kind
        if resolved_kind != draft.connection_kind and resolved_kind in connection_pools:
            draft = replace(draft, connection_kind=resolved_kind)
            candidate_connections = connection_pools.get(draft.connection_kind, {})
        plan = build_action_plan(draft, hints, available_connection_refs=sorted(candidate_connections.keys()))
        intent = [f"capability:{plan.capability}"]
        if (
            plan.capability == "ssh_command"
            and plan.connection_ref
            and list(plan.missing_fields or []) == ["content"]
        ):
            routing_decision = {
                "found": True,
                "kind": "ssh",
                "ref": plan.connection_ref,
                "capability": "ssh_command",
            }
            resolved = {
                "decision": routing_decision,
                "action_debug": {
                    "decision": {
                        "found": True,
                        "candidate_kind": "template",
                        "candidate_id": "ssh_run_command",
                    }
                },
                "payload_debug": {
                    "payload": {
                        "capability": "ssh_command",
                        "connection_kind": "ssh",
                        "connection_ref": plan.connection_ref,
                        "requested_connection_ref": plan.requested_connection_ref,
                        "path": plan.path,
                        "content": plan.content,
                        "plan_class": plan.plan_class,
                        "behavior_profile": plan.behavior_profile,
                        "notes": list(plan.notes or []),
                        "missing_fields": ["content"],
                    }
                },
            }
            resolved = await self._refresh_missing_ssh_command_resolution(
                resolved=resolved,
                message=message,
                user_id=user_id,
                language=language,
            )
            action_debug = dict(resolved.get("action_debug", {}) or {})
            payload_debug = dict(resolved.get("payload_debug", {}) or {})
            safety_debug = dict(resolved.get("safety_debug", {}) or {})
            execution_debug = dict(resolved.get("execution_debug", {}) or {})
            next_step = self._resolved_next_step(
                safety=dict(safety_debug.get("decision", {}) or {}),
                execution=dict(execution_debug.get("decision", {}) or {}),
            )
            detail_lines = qdrant_details + self._build_capability_detail_lines(plan, language=language)
            detail_lines = [*detail_lines, *self._resolved_routing_detail_lines(resolved)]
            if next_step == "block":
                text, detail_lines = await self._blocked_action_response_text(
                    resolved,
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    language=language,
                    detail_lines=detail_lines,
                )
                return intent, text, detail_lines, plan, []
        if not plan.is_complete:
            return intent, self._format_capability_missing_message(plan, language=language), qdrant_details, plan, []

        routing_details: list[str] = []
        if self._routing_debug_enabled():
            for record in routing_records:
                routing_details.extend(format_routing_decision_record(record))
        if plan.capability == "api_request":
            plan, api_debug_lines, api_policy = await self._apply_agentic_http_api_resolution(
                message=message,
                plan=plan,
                user_id=user_id,
                language=language,
            )
            routing_details.extend(api_debug_lines)
            if api_policy is not None and api_policy.action == "ask_user":
                details = routing_details + qdrant_details + self._build_capability_detail_lines(plan, language=language)
                text = _pipeline_text(
                    language,
                    "http_api_needs_confirmation",
                    "The HTTP API request still needs confirmation before execution.",
                )
                return intent, text, details, plan, []
        details = routing_details + qdrant_details
        if self._routing_debug_enabled():
            details.append(runtime_debug_line_for_plan(plan))
        details.extend(self._build_capability_detail_lines(plan, language=language))
        content_access_result = await self._execute_content_access_if_available(
            plan,
            user_id=user_id,
            language=str(language or "de"),
        )
        if content_access_result is not None:
            text, content_detail_lines, content_errors = content_access_result
            return intent, text, details + content_detail_lines, plan, content_errors
        try:
            result_text = await self._executor_registry.execute(plan, language=str(language or "de"))
        except Exception as exc:
            error_text = self._format_capability_execution_error(plan, exc, language=language)
            error_code = self._capability_execution_error_code(plan, exc)
            return intent, error_text, details, plan, [error_code]
        return intent, result_text, details, plan, []

    def _unified_routing_connection_pools(self) -> dict[str, dict[str, Any]]:
        connection_pools: dict[str, dict[str, Any]] = {}
        for kind in DEFAULT_CONNECTION_ROUTING_KINDS:
            clean_kind = normalize_connection_kind(kind)
            rows = getattr(getattr(self.settings, "connections", object()), clean_kind, {})
            if isinstance(rows, dict) and rows:
                connection_pools[clean_kind] = rows
        return connection_pools

    def _capability_routing_connection_pools(self) -> dict[str, dict[str, Any]]:
        connection_pools: dict[str, dict[str, Any]] = {}
        for kind in connection_action_executor_kinds():
            clean_kind = normalize_connection_kind(kind)
            rows = getattr(getattr(self.settings, "connections", object()), clean_kind, {})
            if isinstance(rows, dict) and rows:
                connection_pools[clean_kind] = rows
        return connection_pools

    @staticmethod
    def _filter_capability_connection_pools(
        capability: str,
        connection_pools: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        allowed_kinds = {
            normalize_connection_kind(kind)
            for kind in capability_executor_kinds(capability)
            if normalize_connection_kind(kind)
        }
        if not allowed_kinds:
            return dict(connection_pools)
        return {
            kind: rows
            for kind, rows in connection_pools.items()
            if normalize_connection_kind(kind) in allowed_kinds and isinstance(rows, dict) and rows
        }

    @staticmethod
    def _sanitize_capability_hints(
        capability: str,
        hints: MemoryHints,
        *,
        available_kinds: set[str],
    ) -> MemoryHints:
        clean_kind = normalize_connection_kind(str(hints.connection_kind or ""))
        if not clean_kind:
            return hints
        if clean_kind in available_kinds and capability_matches_connection_kind(capability, clean_kind):
            return hints
        return MemoryHints()

    @staticmethod
    def _capability_matches_connection_kind(capability_draft: Any | None) -> bool:
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or "").strip())
        kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        return capability_matches_connection_kind(capability, kind)

    def _classify_capability_draft(
        self,
        message: str,
        *,
        language: str | None = None,
    ) -> Any | None:
        connection_pools = self._capability_routing_connection_pools()
        if not connection_pools:
            return None
        classification_pools = {kind: dict(rows) for kind, rows in connection_pools.items()}
        for kind in {"discord", "imap", "email", "mqtt", "webhook"}:
            clean_kind = normalize_connection_kind(kind)
            if clean_kind and clean_kind not in classification_pools:
                classification_pools[clean_kind] = {"__aria_missing_target__": {}}

        connection_aliases_by_kind: dict[str, dict[str, list[str]]] = {}
        for kind, rows in connection_pools.items():
            alias_rows: dict[str, list[str]] = {}
            for ref, row in rows.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                alias_rows[clean_ref] = build_connection_aliases(kind, clean_ref, row)
            if alias_rows:
                connection_aliases_by_kind[kind] = alias_rows

        lower = str(message or "").strip().lower()
        lower_ascii = lower.translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )
        ssh_runtime_question = (
            connection_pools.get("ssh")
            and any(term in lower for term in ("server", "host", "ssh"))
            and any(
                term in lower
                for term in (
                    "laufzeit",
                    "uptime",
                    "status",
                    " ok",
                    "ok",
                    "okay",
                    "ordnung",
                    "gesund",
                    "health",
                    "healthy",
                    "wie geht es",
                    "hd",
                    "harddisk",
                    "festplatte",
                    "festplatten",
                    "speicherplatz",
                )
            )
            and not any(
                term in lower
                for term in (
                    "servern",
                    "servers",
                    "all meinen server",
                    "meinen servern",
                    "meine server",
                    "developer server",
                    "dev-server",
                    "dev server",
                )
            )
        )
        draft = self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={kind: rows.keys() for kind, rows in classification_pools.items()},
            available_connection_aliases_by_kind=connection_aliases_by_kind,
        )
        if (
            draft is not None
            and ssh_runtime_question
            and normalize_capability(str(getattr(draft, "capability", "") or "")) in {"file_read", "file_list"}
        ):
            command = ""
            if any(term in lower for term in ("laufzeit", "uptime")):
                command = "uptime"
            elif any(term in lower for term in ("hd", "harddisk", "festplatte", "festplatten", "speicherplatz")):
                command = "df -h"
            return CapabilityDraft(
                capability="ssh_command",
                connection_kind="ssh",
                requested_connection_ref=self.capability_router._extract_requested_connection_ref_hint(
                    str(message or ""),
                    "ssh",
                    self.capability_router._lexicon_for_language(language),
                ),
                content=command,
                confidence=0.74,
                notes=["capability_draft_source:local_fallback"],
            )
        if draft is not None:
            return draft

        if ssh_runtime_question:
            if any(term in lower for term in ("laufzeit", "uptime")):
                return CapabilityDraft(
                    capability="ssh_command",
                    connection_kind="ssh",
                    requested_connection_ref=self.capability_router._extract_requested_connection_ref_hint(
                        str(message or ""),
                        "ssh",
                        self.capability_router._lexicon_for_language(language),
                    ),
                    content="uptime",
                    confidence=0.74,
                    notes=["capability_draft_source:local_fallback"],
                )
            if any(term in lower for term in ("hd", "harddisk", "festplatte", "festplatten", "speicherplatz")):
                return CapabilityDraft(
                    capability="ssh_command",
                    connection_kind="ssh",
                    requested_connection_ref=self.capability_router._extract_requested_connection_ref_hint(
                        str(message or ""),
                        "ssh",
                        self.capability_router._lexicon_for_language(language),
                    ),
                    content="df -h",
                    confidence=0.74,
                    notes=["capability_draft_source:local_fallback"],
                )
            if any(term in lower for term in ("status", " ok", "ok", "okay", "ordnung", "gesund", "health", "healthy", "wie geht es")):
                return CapabilityDraft(
                    capability="ssh_command",
                    connection_kind="ssh",
                    requested_connection_ref=self.capability_router._extract_requested_connection_ref_hint(
                        str(message or ""),
                        "ssh",
                        self.capability_router._lexicon_for_language(language),
                    ),
                    confidence=0.72,
                    notes=["capability_draft_source:local_fallback"],
                )
        file_kind = "smb" if connection_pools.get("smb") else "sftp" if connection_pools.get("sftp") else ""
        path = self.capability_router._extract_path(str(message or ""))
        if file_kind and path and any(term in lower_ascii for term in ("datei", "file", "oeffne", "open", "lies", "read")):
            return CapabilityDraft(
                capability="file_read",
                connection_kind=file_kind,
                path=path,
                confidence=0.74,
                notes=["capability_draft_source:local_fallback"],
            )
        if (
            connection_pools.get("ssh")
            and any(term in lower_ascii for term in ("loesche", "delete", "remove", "entferne"))
            and any(term in lower for term in ("server", "host", "ssh"))
        ):
            return CapabilityDraft(
                capability="ssh_command",
                connection_kind="ssh",
                confidence=0.72,
                notes=["capability_draft_source:local_fallback"],
            )
        return None

    def _should_try_llm_capability_draft(self, message: str, capability_draft: Any | None) -> bool:
        if capability_draft is not None or self.llm_client is None:
            return False
        connection_pools = self._capability_routing_connection_pools()
        return bool(connection_pools)

    def _should_try_capability_draft_agentic_first(self, message: str) -> bool:
        if self.llm_client is None:
            return False
        connection_pools = self._capability_routing_connection_pools()
        if not connection_pools:
            return False
        lower = str(message or "").strip().lower()
        return re.search(r"^\s*(?:run|execute)\s+\S+.*\s+on\s+\S+", lower) is None

    @staticmethod
    def _local_capability_fallback_allowed(llm_state: str) -> bool:
        clean = str(llm_state or "").strip().lower()
        if not clean:
            return True
        if clean in {"unavailable", "invalid:low_confidence", "invalid:empty_or_invalid_response", "invalid:llm_error", "invalid:missing_action"}:
            return True
        return clean.startswith("invalid:") and clean not in {"invalid:out_of_bounds"}

    def _should_try_agentic_capability_draft_first(self, message: str) -> bool:
        if self.llm_client is None:
            return False
        connection_pools = self._capability_routing_connection_pools()
        if not connection_pools:
            return False
        lower = str(message or "").strip().lower()
        lower_ascii = lower.translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )
        if re.search(r"^\s*(?:run|execute)\s+\S+.*\s+on\s+\S+", lower):
            return False
        if connection_pools.get("ssh") and any(term in lower for term in ("ssh", "server", "host", "node")):
            return True
        local_check_terms = ("pruef", "check", "kontrolliere", "health")
        non_ssh_terms = ("api", "http", "webhook", "discord", "mqtt", "rss", "kalender", "calendar", "endpoint")
        ssh_alias_terms: set[str] = set()
        for ref, row in dict(connection_pools.get("ssh") or {}).items():
            ssh_alias_terms.add(str(ref or "").strip().lower())
            if isinstance(row, dict):
                ssh_alias_terms.add(str(row.get("title", "") or "").strip().lower())
                aliases = row.get("aliases", [])
                if isinstance(aliases, list):
                    ssh_alias_terms.update(str(alias or "").strip().lower() for alias in aliases)
        ssh_alias_terms = {term for term in ssh_alias_terms if term and len(term) >= 3}
        if (
            connection_pools.get("ssh")
            and any(term in lower_ascii for term in local_check_terms)
            and not any(term in lower_ascii for term in non_ssh_terms)
            and any(term in lower for term in ssh_alias_terms)
        ):
            return True
        return False

    @staticmethod
    def _pre_rag_gate_may_classify_action(decision: Any) -> bool:
        intents = [str(intent or "").strip() for intent in list(getattr(decision, "intents", []) or [])]
        if intents in (["chat"], ["memory_recall"], ["memory_store"]):
            return True
        return False

    async def _classify_capability_draft_with_llm(
        self,
        message: str,
        *,
        language: str | None = None,
    ) -> Any | None:
        self._last_capability_draft_llm_state = ""
        if self.llm_client is None:
            self._last_capability_draft_llm_state = "unavailable"
            return None
        connection_pools = self._capability_routing_connection_pools()
        configured_kinds = sorted(str(kind).strip().lower() for kind, rows in connection_pools.items() if rows)
        allowed_pairs = sorted(
            {
                (normalize_connection_kind(kind), normalize_capability(capability))
                for kind, capability in connection_action_executor_bindings()
                if normalize_connection_kind(kind) in configured_kinds
            }
        )
        if not allowed_pairs:
            return None
        allowed_pair_set = set(allowed_pairs)
        prompt_payload = {
            "message": str(message or ""),
            "language": str(language or ""),
            "configured_connection_kinds": configured_kinds,
            "allowed_capability_bindings": [
                {"connection_kind": kind, "capability": capability}
                for kind, capability in allowed_pairs
            ],
            "contract": {
                "return_no_action_when": "The user is asking general knowledge, memory recall, document QA, or non-operational chat.",
                "return_action_when": "The user asks ARIA to inspect/read/send/check/list/run something through a configured connection kind.",
                "target_scope": "Use multi_target only when the user clearly refers to several/all targets.",
                "target_intent": "Use health_check for broad server fitness/health/status phrasing, capacity_check for broad resource/capacity questions, package_update_check for package/update-status questions, otherwise leave empty.",
                "content": "For ssh_command, include only a safe read-only command when obvious; otherwise leave content empty for the SSH resolver.",
            },
            "examples": [
                {
                    "message": "wie fit sind meine server?",
                    "action": "action",
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "target_scope": "multi_target",
                    "target_intent": "health_check",
                    "content": "uptime",
                },
                {
                    "message": "are my servers still looking good?",
                    "action": "action",
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "target_scope": "multi_target",
                    "target_intent": "health_check",
                    "content": "uptime",
                },
                {
                    "message": "haben meine server genug reserve?",
                    "action": "action",
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "target_scope": "multi_target",
                    "target_intent": "capacity_check",
                    "content": "uptime",
                },
                {
                    "message": "sind meine server up to date?",
                    "action": "action",
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "target_scope": "multi_target",
                    "target_intent": "package_update_check",
                    "content": "apt list --upgradable",
                },
            ],
        }
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="capability_draft_decision",
            system=(
                "You classify whether a user message is a bounded ARIA connection action. "
                "Return one JSON object only with: action, capability, connection_kind, "
                "target_scope, target_intent, content, confidence, reason. Never invent connection kinds or capabilities."
            ),
            payload=prompt_payload,
        )
        if not decision.ok:
            self._last_capability_draft_llm_state = f"invalid:{decision.error}"
            return None
        payload = decision.payload
        action = str(payload.get("action", "") or "").strip().lower()
        if action in {"chat", "no_action"}:
            self._last_capability_draft_llm_state = "no_action"
            return None
        if action not in {"action", "capability_action"}:
            self._last_capability_draft_llm_state = "invalid:missing_action"
            return None
        capability = normalize_capability(str(payload.get("capability", "") or ""))
        connection_kind = normalize_connection_kind(str(payload.get("connection_kind", "") or ""))
        if (connection_kind, capability) not in allowed_pair_set:
            self._last_capability_draft_llm_state = "invalid:out_of_bounds"
            return None
        confidence = confidence_score(payload.get("confidence"))
        if confidence < 0.55:
            self._last_capability_draft_llm_state = "invalid:low_confidence"
            return None
        self._last_capability_draft_llm_state = "action"
        notes = ["capability_draft_source:llm"]
        if str(payload.get("target_scope", "") or "").strip().lower() == "multi_target":
            notes.append("target_scope:multi_target")
        target_intent = str(payload.get("target_intent", "") or "").strip().lower()
        if target_intent in {"health_check", "capacity_check", "package_update_check"}:
            notes.append(f"target_intent:{target_intent}")
        return CapabilityDraft(
            capability=capability,
            connection_kind=connection_kind,
            requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
            content=str(payload.get("content", "") or "").strip(),
            confidence=confidence,
            notes=notes,
        )

    async def _llm_prefers_chat_over_connection_action(
        self,
        message: str,
        *,
        language: str | None = None,
    ) -> bool:
        if self.llm_client is None:
            return False
        connection_pools = self._capability_routing_connection_pools()
        if not connection_pools:
            return False
        configured_kinds = sorted(str(kind).strip().lower() for kind, rows in connection_pools.items() if rows)
        if not configured_kinds:
            return False
        prompt_payload = {
            "message": str(message or ""),
            "language": str(language or ""),
            "configured_connection_kinds": configured_kinds,
            "contract": {
                "chat": "Choose chat when the user asks for explanation, interpretation, advice, troubleshooting guidance, general LLM help, or asks what to do with pasted text/logs/errors. Connection names may be context.",
                "action": "Choose action only when the user asks ARIA to actually inspect/read/check/list/send/run something through a configured connection now.",
                "safety": "Do not choose action merely because a known host, service, connection name, or protocol appears in the message.",
            },
            "examples": [
                {
                    "message": "this syslog message mentions dev-node-01, what should I do?",
                    "route": "chat",
                    "reason": "The user asks for interpretation/advice about pasted log text.",
                },
                {
                    "message": "explain this kernel soft lockup from my ssh server",
                    "route": "chat",
                    "reason": "The user asks for explanation, not runtime execution.",
                },
                {
                    "message": "pruefe dev-node-01 jetzt auf cpu und ram",
                    "route": "action",
                    "reason": "The user explicitly asks ARIA to inspect the server now.",
                },
                {
                    "message": "liste die dateien auf meinem sftp fileserver-01",
                    "route": "action",
                    "reason": "The user asks for a file operation through a configured connection.",
                },
            ],
        }
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="pre_rag_action_arbitration",
            system=(
                "You arbitrate whether ARIA should answer in chat or execute a bounded connection action. "
                "Return one JSON object only with: route, confidence, reason. route must be chat or action."
            ),
            payload=prompt_payload,
        )
        if not decision.ok:
            return False
        payload = decision.payload
        route = str(payload.get("route", "") or "").strip().lower()
        if route not in {"chat", "no_action"}:
            return False
        return confidence_score(payload.get("confidence")) >= 0.55

    def _should_try_unified_routing(
        self,
        message: str,
        capability_draft: Any | None,
    ) -> bool:
        connection_pools = self._unified_routing_connection_pools()
        if not connection_pools:
            return False

        supported_kinds = set(connection_pools.keys())
        draft_kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        draft_matches_kind = self._capability_matches_connection_kind(capability_draft)
        if draft_kind in supported_kinds and draft_matches_kind:
            if str(getattr(capability_draft, "explicit_connection_ref", "") or "").strip():
                return True
            if str(getattr(capability_draft, "requested_connection_ref", "") or "").strip():
                return True
            if str(getattr(capability_draft, "path", "") or "").strip():
                return True
            if str(getattr(capability_draft, "content", "") or "").strip():
                return True
            return True

        preferred_kind = infer_preferred_connection_kind(
            message,
            explicit_kind=draft_kind if draft_matches_kind else "",
            available_kinds=supported_kinds,
        )
        deterministic = RoutingResolver._deterministic_connection_match(
            message,
            connection_pools,
            preferred_kind=preferred_kind,
        )
        if deterministic.found:
            return True

        return bool(preferred_kind and preferred_kind in supported_kinds)

    @staticmethod
    def _should_prefer_capability_action(capability_draft: Any | None) -> bool:
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or "").strip())
        return capability in {
            "website_read",
            "website_list",
            "api_request",
            "calendar_read",
        }

    def _should_suppress_recipe_candidates_for_capability_draft(
        self,
        capability_draft: Any | None,
        message: str = "",
    ) -> bool:
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or "").strip())
        kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        content = str(getattr(capability_draft, "content", "") or "").strip()
        if capability != "ssh_command" or kind != "ssh":
            return False
        if content:
            return True
        if self._capability_draft_has_multi_target_scope(capability_draft):
            return True
        if content == "df -h":
            return True
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if callable(looks_like_plural_target) and str(message or "").strip():
            try:
                return bool(looks_like_plural_target(message, "ssh"))
            except Exception:
                return False
        return False

    @staticmethod
    def _capability_draft_has_multi_target_scope(capability_draft: Any | None) -> bool:
        notes = [str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])]
        return "target_scope:multi_target" in notes

    @staticmethod
    def _capability_draft_target_refs(capability_draft: Any | None) -> list[str]:
        refs: list[str] = []
        for item in list(getattr(capability_draft, "connection_refs", []) or []):
            clean = str(item or "").strip()
            if clean and clean not in refs:
                refs.append(clean)
        if refs:
            return refs
        for note in list(getattr(capability_draft, "notes", []) or []):
            clean_note = str(note or "").strip()
            if not clean_note.lower().startswith("turn_contract_target_refs:"):
                continue
            raw_refs = clean_note.split(":", 1)[1]
            for item in raw_refs.split(","):
                clean = str(item or "").strip()
                if clean and clean not in refs:
                    refs.append(clean)
        return refs

    def _ssh_multi_target_contract_should_expand_to_fleet(
        self,
        *,
        message: str,
        capability_draft: Any | None,
        contract_target_refs: list[str],
        candidate_connections: dict[str, Any],
    ) -> bool:
        if len(candidate_connections) <= len(contract_target_refs):
            return False
        explicit_ref = str(getattr(capability_draft, "explicit_connection_ref", "") or "").strip()
        requested_ref = str(getattr(capability_draft, "requested_connection_ref", "") or "").strip()
        if explicit_ref or requested_ref:
            return False
        notes = [str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])]
        target_intent = next((note.split(":", 1)[1] for note in notes if note.startswith("target_intent:")), "")
        if target_intent not in {"health_check", "capacity_check", "package_update_check"}:
            return False
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if not callable(looks_like_plural_target):
            return False
        try:
            return bool(looks_like_plural_target(message, "ssh"))
        except Exception:
            return False

    @staticmethod
    def _capability_draft_is_llm_sourced(capability_draft: Any | None) -> bool:
        notes = [str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])]
        return "capability_draft_source:llm" in notes

    @staticmethod
    def _capability_draft_is_local_fallback(capability_draft: Any | None) -> bool:
        notes = [str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])]
        return "capability_draft_source:local_fallback" in notes

    async def _refine_seeded_capability_draft_objective_with_llm(
        self,
        capability_message: str,
        capability_draft: Any | None,
        *,
        language: str | None = None,
    ) -> Any | None:
        if capability_draft is None:
            return None
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or "").strip())
        kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        if capability != "ssh_command" or kind != "ssh":
            return capability_draft
        existing_notes = [str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])]
        if any(note.startswith("target_intent:") for note in existing_notes):
            return capability_draft
        refined = await self._classify_capability_draft_with_llm(capability_message, language=language)
        if refined is None:
            return capability_draft
        if normalize_capability(str(getattr(refined, "capability", "") or "")) != capability:
            return capability_draft
        if normalize_connection_kind(str(getattr(refined, "connection_kind", "") or "")) != kind:
            return capability_draft
        merged_notes: list[str] = []
        for note in [*list(getattr(capability_draft, "notes", []) or []), *list(getattr(refined, "notes", []) or [])]:
            clean = str(note or "").strip()
            if clean and clean not in merged_notes:
                merged_notes.append(clean)
        content = str(getattr(refined, "content", "") or "").strip() or str(getattr(capability_draft, "content", "") or "").strip()
        return with_capability_draft_updates(
            capability_draft,
            content=content,
            confidence=max(float(getattr(capability_draft, "confidence", 0.0) or 0.0), float(getattr(refined, "confidence", 0.0) or 0.0)),
            notes=merged_notes,
        )

    def _pre_rag_gate_debug_line(
        self,
        *,
        action_path: str,
        capability_draft: Any | None,
        reason: str = "",
    ) -> str:
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or "").strip()) or "-"
        kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or "")) or "-"
        explicit_ref = str(getattr(capability_draft, "explicit_connection_ref", "") or "").strip() or "-"
        requested_ref = str(getattr(capability_draft, "requested_connection_ref", "") or "").strip() or "-"
        path = str(getattr(capability_draft, "path", "") or "").strip() or "-"
        content = str(getattr(capability_draft, "content", "") or "").strip() or "-"
        fields = {
            "action_path": action_path,
            "capability": capability,
            "kind": kind,
            "explicit_ref": explicit_ref,
            "requested_ref": requested_ref,
            "path": path,
            "content": content,
            "boundary": AGENTIC_BOUNDARY_CONTEXT,
        }
        if reason:
            fields["reason"] = reason
        return routing_debug_line("pre_rag_action_gate", fields)

    def _prepend_pre_rag_gate_debug(
        self,
        result: PipelineResult,
        *,
        action_path: str,
        capability_draft: Any | None,
        reason: str = "",
    ) -> PipelineResult:
        if not self._routing_debug_enabled():
            return result
        result.detail_lines = [
            self._pre_rag_gate_debug_line(action_path=action_path, capability_draft=capability_draft, reason=reason),
            *list(result.detail_lines or []),
        ]
        return result

    def _pre_rag_no_action_debug_lines(
        self,
        *,
        capability_draft: Any | None,
        custom_intents: list[str],
    ) -> list[str]:
        if not self._routing_debug_enabled():
            return []
        if custom_intents:
            reason = "recipe_candidates_present"
        elif capability_draft is None:
            reason = "no_capability_draft"
        else:
            reason = "no_routable_action"
        return [
            self._pre_rag_gate_debug_line(
                action_path="no_action",
                capability_draft=capability_draft,
                reason=reason,
            )
        ]

    @_pre_rag_usage_scope
    async def _try_pre_rag_action_gate(
        self,
        message: str,
        user_id: str,
        *,
        request_id: str,
        source: str,
        decision: Any,
        start: float,
        runtime_recipes: list[dict[str, Any]],
        auto_memory_enabled: bool = False,
        language: str | None = None,
        seed_capability_draft: Any | None = None,
        semantic_source: str = "",
    ) -> tuple[PipelineResult | None, list[str], Any | None]:
        capability_message = self._rewrite_calendar_followup_message(message, user_id)
        capability_message = self._rewrite_ssh_followup_message(
            capability_message,
            user_id,
            language=language,
        )
        capability_draft = seed_capability_draft
        seeded_by_turn_contract = capability_draft is not None and str(semantic_source or "").strip() in {
            "aria_meta_catalog_routing",
            "aria_turn_surface_action_arbitration",
        }
        if not seeded_by_turn_contract and not self._pre_rag_gate_may_classify_action(decision):
            return None, [], None
        if seeded_by_turn_contract:
            capability_draft = await self._refine_seeded_capability_draft_objective_with_llm(
                capability_message,
                capability_draft,
                language=language,
            )
        if not seeded_by_turn_contract and self.capability_router.looks_like_general_instruction_request(capability_message):
            return None, [], None
        if not seeded_by_turn_contract and explicitly_requests_local_context(capability_message):
            return None, [], None
        if not seeded_by_turn_contract and self._external_urls(capability_message):
            return None, [], None
        if not seeded_by_turn_contract and await self._message_wants_recent_runtime_context(capability_message, user_id, language=language):
            return None, [], None
        if (
            not seeded_by_turn_contract
            and
            looks_like_general_diagnostic_or_advice_request(capability_message)
            and re.search(r"\bwas\s+mach(?:e)?\s+ich\s+damit\b", capability_message, flags=re.IGNORECASE)
            and await self._llm_prefers_chat_over_connection_action(capability_message, language=language)
        ):
            return None, [], None
        agentic_first_draft_attempted = False
        local_fallback_used = False
        llm_capability_state = ""
        if not seeded_by_turn_contract and self._should_try_capability_draft_agentic_first(capability_message):
            agentic_first_draft_attempted = True
            capability_draft = await self._classify_capability_draft_with_llm(
                capability_message,
                language=language,
            )
            llm_capability_state = str(getattr(self, "_last_capability_draft_llm_state", "") or "")
            if capability_draft is None and llm_capability_state == "no_action":
                return None, [], None
        if capability_draft is None and not seeded_by_turn_contract and self._local_capability_fallback_allowed(llm_capability_state):
            capability_draft = self._classify_capability_draft(capability_message, language=language)
            local_fallback_used = capability_draft is not None
            if local_fallback_used and auto_memory_enabled:
                self._schedule_capability_fallback_learning_outcome(
                    message=capability_message,
                    user_id=user_id,
                    request_id=request_id,
                    capability_draft=capability_draft,
                    llm_state=llm_capability_state or "not_attempted",
                    source=source,
                )
        if self._should_suppress_recipe_candidates_for_capability_draft(capability_draft, capability_message):
            custom_intents = []
        elif not seeded_by_turn_contract and self.llm_client is not None and runtime_recipes:
            custom_intents = await self._resolve_stored_recipe_intent_with_llm(message, runtime_recipes)
        elif not seeded_by_turn_contract:
            custom_intents = self._match_stored_recipe_intents(message, runtime_recipes)
        else:
            custom_intents = []
        if (
            not seeded_by_turn_contract
            and
            capability_draft is None
            and not custom_intents
            and looks_like_general_diagnostic_or_advice_request(capability_message)
            and not (
                (
                    "interpretiere" in capability_message.lower()
                    or "interpret " in capability_message.lower()
                    or "interpretation" in capability_message.lower()
                )
                and any(term in capability_message.lower() for term in ("syslog", "kernel", " log", "dmesg", "watchdog", "soft lockup"))
            )
            and await self._llm_prefers_chat_over_connection_action(capability_message, language=language)
        ):
            return None, custom_intents, capability_draft
        interpret_log_advice_request = (
            (
                "interpretiere" in capability_message.lower()
                or "interpret " in capability_message.lower()
                or "interpretation" in capability_message.lower()
            )
            and any(term in capability_message.lower() for term in ("syslog", "kernel", " log", "dmesg", "watchdog", "soft lockup"))
        )
        if (
            not custom_intents
            and not seeded_by_turn_contract
            and (
                (self._should_try_llm_capability_draft(capability_message, capability_draft) and not agentic_first_draft_attempted)
                or (interpret_log_advice_request and self.llm_client is not None and not agentic_first_draft_attempted)
            )
        ):
            llm_capability_draft = await self._classify_capability_draft_with_llm(
                capability_message,
                language=language,
            )
            if llm_capability_draft is not None:
                capability_draft = llm_capability_draft
        if self._should_suppress_recipe_candidates_for_capability_draft(capability_draft, capability_message):
            custom_intents = []
        if not custom_intents and self._capability_draft_should_use_inventory_context(capability_draft):
            inventory_result = await self._build_capability_inventory_context_result(
                message=capability_message,
                user_id=user_id,
                request_id=request_id,
                source=source,
                decision=decision,
                start=start,
                capability_draft=capability_draft,
                language=language,
            )
            if inventory_result is not None:
                return inventory_result, custom_intents, capability_draft
        if (
            not custom_intents
            and capability_draft is not None
            and self._capability_matches_connection_kind(capability_draft)
            and normalize_capability(str(getattr(capability_draft, "capability", "") or "")) == "ssh_command"
            and (
                self._capability_draft_has_multi_target_scope(capability_draft)
                or not str(getattr(capability_draft, "content", "") or "").strip()
            )
        ):
            runtime_effect = await self._classify_ssh_runtime_effect_for_gate(
                capability_message,
                user_id,
                capability_draft=capability_draft,
                language=language,
            )
            if (
                str(runtime_effect.get("runtime_effect", "") or "").strip().lower() == "mutating"
                and str(runtime_effect.get("confidence", "") or "").strip().lower() in {"high", "medium"}
            ):
                return await self._build_mutating_ssh_request_block_result(
                    message=capability_message,
                    user_id=user_id,
                    request_id=request_id,
                    source=source,
                    decision=decision,
                    start=start,
                    capability_draft=capability_draft,
                    runtime_effect=runtime_effect,
                    language=language,
                ), custom_intents, capability_draft
        if (
            not custom_intents
            and capability_draft is not None
            and (
                looks_like_general_diagnostic_or_advice_request(capability_message)
                or (
                    re.search(r"\binterpret(?:iere|ier|e|ing)?\b", capability_message, flags=re.IGNORECASE)
                    and re.search(r"\b(?:syslog|kernel|log|dmesg|watchdog|soft\s+lockup)\b", capability_message, flags=re.IGNORECASE)
                )
            )
            and not seeded_by_turn_contract
            and await self._llm_prefers_chat_over_connection_action(capability_message, language=language)
        ):
            return None, custom_intents, capability_draft

        capability_has_no_configured_targets = False
        if capability_draft is not None:
            filtered_capability_pools = self._filter_capability_connection_pools(
                str(getattr(capability_draft, "capability", "") or "").strip(),
                self._capability_routing_connection_pools(),
            )
            capability_has_no_configured_targets = self._capability_matches_connection_kind(capability_draft) and not filtered_capability_pools

        if not custom_intents and (
            self._should_prefer_capability_action(capability_draft)
            or capability_has_no_configured_targets
        ):
            if capability_has_no_configured_targets and capability_draft is not None:
                plan = build_action_plan(capability_draft, MemoryHints(), available_connection_refs=[])
                duration_ms = int((time.perf_counter() - start) * 1000)
                result = self._build_routed_action_result(
                    request_id=request_id,
                    decision=decision,
                    duration_ms=duration_ms,
                    intents=[f"capability:{plan.capability}"],
                    text=self._format_capability_missing_message(plan, language=language),
                    detail_lines=[],
                    skill_errors=[],
                )
                await self._log_result_usage_snapshot(
                    request_id=request_id,
                    user_id=user_id,
                    intents=[f"capability:{plan.capability}"],
                    router_level=decision.level,
                    duration_ms=duration_ms,
                    source=source,
                    skill_errors=[],
                    extraction_model="pre_rag_missing_capability_target",
                )
                return self._prepend_pre_rag_gate_debug(
                    result,
                    action_path="missing_capability_target",
                    capability_draft=capability_draft,
                ), custom_intents, capability_draft

            capability_result = await self._try_capability_action(
                capability_message,
                user_id,
                language=language,
            )
            if capability_result is not None:
                intents, text, detail_lines, _plan, skill_errors = capability_result
                duration_ms = int((time.perf_counter() - start) * 1000)
                result = self._build_routed_action_result(
                    request_id=request_id,
                    decision=decision,
                    duration_ms=duration_ms,
                    intents=intents,
                    text=text,
                    detail_lines=detail_lines,
                    skill_errors=skill_errors,
                )
                await self._log_result_usage_snapshot(
                    request_id=request_id,
                    user_id=user_id,
                    intents=intents,
                    router_level=decision.level,
                    duration_ms=duration_ms,
                    source=source,
                    skill_errors=skill_errors,
                    extraction_model="pre_rag_capability_action",
                )
                return self._prepend_pre_rag_gate_debug(
                    result,
                    action_path="capability_action",
                    capability_draft=capability_draft,
                ), custom_intents, capability_draft

        deterministic_direct_signal = (
            capability_draft is not None
            and self._capability_matches_connection_kind(capability_draft)
            and not self._capability_draft_is_llm_sourced(capability_draft)
            and normalize_capability(str(getattr(capability_draft, "capability", "") or "")) == "ssh_command"
            and bool(str(getattr(capability_draft, "explicit_connection_ref", "") or "").strip())
        )
        if not custom_intents and deterministic_direct_signal:
            capability_result = await self._try_capability_action(
                capability_message,
                user_id,
                language=language,
            )
            if capability_result is not None:
                intents, text, detail_lines, _plan, skill_errors = capability_result
                duration_ms = int((time.perf_counter() - start) * 1000)
                result = self._build_routed_action_result(
                    request_id=request_id,
                    decision=decision,
                    duration_ms=duration_ms,
                    intents=intents,
                    text=text,
                    detail_lines=detail_lines,
                    skill_errors=skill_errors,
                )
                await self._log_result_usage_snapshot(
                    request_id=request_id,
                    user_id=user_id,
                    intents=intents,
                    router_level=decision.level,
                    duration_ms=duration_ms,
                    source=source,
                    skill_errors=skill_errors,
                    extraction_model="pre_rag_capability_action",
                )
                return self._prepend_pre_rag_gate_debug(
                    result,
                    action_path="capability_action",
                    capability_draft=capability_draft,
                ), custom_intents, capability_draft

        explicit_or_targeted_signal = any(
            str(getattr(capability_draft, field, "") or "").strip()
            for field in ("explicit_connection_ref", "requested_connection_ref", "path")
        )
        content_signal = str(getattr(capability_draft, "content", "") or "").strip()
        llm_sourced_capability_draft = self._capability_draft_is_llm_sourced(capability_draft)
        strong_capability_signal = self._capability_matches_connection_kind(capability_draft) and (
            explicit_or_targeted_signal or (content_signal and not custom_intents and not llm_sourced_capability_draft)
        )
        should_try_unified = self._should_try_unified_routing(capability_message, capability_draft)
        if (
            should_try_unified
            and not strong_capability_signal
            and not custom_intents
            and not seeded_by_turn_contract
            and await self._llm_prefers_chat_over_connection_action(capability_message, language=language)
        ):
            return None, custom_intents, capability_draft
        if should_try_unified and (strong_capability_signal or not custom_intents):
            unified_routed_result = await self._try_unified_routed_action(
                capability_message,
                user_id,
                request_id=request_id,
                source=source,
                decision=decision,
                start=start,
                runtime_recipes=runtime_recipes,
                capability_draft=capability_draft,
                language=language,
            )
            if unified_routed_result is not None:
                return self._prepend_pre_rag_gate_debug(
                    unified_routed_result,
                    action_path="unified_routing",
                    capability_draft=capability_draft,
                ), custom_intents, capability_draft

        return None, custom_intents, capability_draft

    def _capability_draft_should_use_inventory_context(self, capability_draft: Any | None) -> bool:
        if capability_draft is None:
            return False
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or ""))
        if capability != "website_list":
            return False
        inventory_cfg = getattr(self.settings, "inventory_index", None)
        memory_cfg = getattr(self.settings, "memory", None)
        return bool(
            getattr(inventory_cfg, "enabled", True)
            and getattr(memory_cfg, "enabled", False)
            and str(getattr(memory_cfg, "backend", "") or "").strip().lower() == "qdrant"
        )

    def _capability_inventory_arbitration(self, *, capability_draft: Any, message: str, user_id: str, request_id: str) -> AriaTurnArbitration:
        query = str(getattr(capability_draft, "content", "") or "").strip() or str(message or "").strip()
        request = ContextRequest(
            surface_id="connections",
            mode="inventory",
            query=query,
            depth="shallow",
            limit=int(getattr(getattr(self.settings, "inventory_index", None), "candidate_limit", 12) or 12),
            user_id=user_id,
            turn_id=request_id,
        )
        plan = AriaTurnPlan(
            intents=("context_inventory",),
            surfaces=("connections",),
            collections=(),
            actions=(),
            needs_context=True,
            context_directions=("connections",),
            context_depth="shallow",
            queries={"connections": query},
            context_requests=(request,),
            priority=("connections",),
            answer_mode="direct_answer",
            risk="none",
            needs_confirmation=False,
            confidence=0.90,
            reason="capability_list_as_context_inventory",
        )
        return AriaTurnArbitration(plan=plan, source="capability_inventory_contract")

    async def _build_capability_inventory_context_result(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        decision: Any,
        start: float,
        capability_draft: Any,
        language: str | None = None,
    ) -> PipelineResult | None:
        arbitration = self._capability_inventory_arbitration(
            capability_draft=capability_draft,
            message=message,
            user_id=user_id,
            request_id=request_id,
        )
        skill_results = await self._agentic_context_surface_loader().load_inventory(arbitration)
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or "")) or "-"
        detail_lines = [
            arbitration.debug_line,
            "Routing Debug: action_to_context_inventory "
            f"capability={capability} surface=connections authoritative=true reason=inventory_index_contract",
        ]
        result = await self._aria_turn_direct_context_result(
            arbitration=arbitration,
            skill_results=skill_results,
            detail_lines=detail_lines,
            intents=["context_inventory"],
            decision=decision,
            safe_fix_plan=[],
            start=start,
            request_id=request_id,
            user_id=user_id,
            source=source,
            language=language,
        )
        if result is None:
            return None
        self._remember_aria_turn_frame(arbitration, user_id=user_id)
        return self._prepend_pre_rag_gate_debug(
            result,
            action_path="context_inventory",
            capability_draft=capability_draft,
            reason="capability_list_redirected_to_inventory_index",
        )

    def _force_template_action_for_capability_draft(
        self,
        resolved: dict[str, Any],
        *,
        capability_draft: Any | None,
        message: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        if not self._should_suppress_recipe_candidates_for_capability_draft(capability_draft, message):
            return resolved
        action_debug = dict(resolved.get("action_debug", {}) or {})
        decision = dict(action_debug.get("decision", {}) or {})
        if not is_recipe_candidate_kind(str(decision.get("candidate_kind", "") or "")):
            return resolved
        previous_payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        previous_multi_refs = self._payload_multi_target_refs(previous_payload)
        content = str(getattr(capability_draft, "content", "") or "").strip()
        candidates = [row for row in list(action_debug.get("candidates", []) or []) if isinstance(row, dict)]
        template = self._find_action_candidate_payload(
            action_debug,
            candidate_kind="template",
            candidate_id="ssh_run_command",
        )
        forced_decision = dict(template or decision)
        forced_decision.update(
            {
                "found": True,
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "capability": "ssh_command",
                "inputs": {"command": content} if content else dict(forced_decision.get("inputs", {}) or {}),
                "input_items": [{"key": "command", "key_label": "Command", "value": content}] if content else list(forced_decision.get("input_items", []) or []),
                "preview": f"SSH command: {content}" if content else str(forced_decision.get("preview", "") or ""),
                "reason": "capability_draft_preferred_over_recipe",
            }
        )
        action_debug["decision"] = forced_decision
        action_debug["candidates"] = [
            row
            for row in candidates
            if str(row.get("candidate_kind", "") or "").strip().lower() == "template"
        ] or candidates
        resolved["action_debug"] = action_debug
        routing_decision = dict(resolved.get("decision", {}) or {})
        payload_debug = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing_decision,
            action_decision=forced_decision,
        )
        payload_debug = self._apply_capability_draft_overrides(
            payload_debug,
            capability_draft=capability_draft,
        )
        resolved["payload_debug"] = payload_debug
        resolved["safety_debug"] = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        resolved["execution_debug"] = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=forced_decision,
            payload_debug=payload_debug,
            safety_debug=dict(resolved.get("safety_debug", {}) or {}),
            language=str(language or ""),
        )
        if previous_multi_refs:
            resolved = self._apply_ssh_plural_multi_target_resolution(
                resolved,
                candidate_connections={ref: {} for ref in previous_multi_refs},
                capability_draft=capability_draft,
                language=language,
            )
        resolved = self._append_debug_detail_lines(
            resolved,
            routing_debug_line(
                "recipe_candidate_suppressed",
                {
                    "reason": "capability_draft_preferred_over_recipe",
                    "capability": "ssh_command",
                },
            ),
        )
        return resolved

    def classify_routing(self, message: str, *, language: str | None = None) -> RouterDecision:
        routing_profile = self.settings.routing.for_language(language)
        return self.router.classify(message, routing=routing_profile)

    def _available_turn_intents(self) -> set[str]:
        intents = {"chat"}
        if self.memory_skill is not None:
            intents.update({"memory_store", "memory_recall", "memory_forget"})
        if self.web_search_skill is not None:
            intents.add("web_search")
        return intents

    def _available_connection_kinds_for_aria_turn(self) -> tuple[str, ...]:
        raw = getattr(self.settings, "connections", None)
        rows = raw.model_dump() if hasattr(raw, "model_dump") else {}
        if not isinstance(rows, dict):
            return ()
        kinds: list[str] = []
        for kind, values in rows.items():
            if not isinstance(values, dict) or not values:
                continue
            clean = str(kind or "").strip().lower()
            if clean and clean not in kinds:
                kinds.append(clean)
        return tuple(kinds)

    async def _runtime_task_arbitration_override(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        language: str | None,
        meta_arbitration: AriaTurnArbitration,
    ) -> AriaTurnArbitration | None:
        plan = meta_arbitration.plan
        if plan.actions or plan.needs_confirmation or plan.answer_mode == "plan_action":
            return None
        if "connections" not in set(plan.context_directions or ()) and "connections" not in set(plan.surfaces or ()):
            return None
        if not self._should_try_agentic_capability_draft_first(message):
            return None
        capability_draft = await self._classify_capability_draft_with_llm(message, language=language)
        if capability_draft is None:
            return None
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or ""))
        kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        if capability != "ssh_command" or kind != "ssh":
            return None
        notes = {str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])}
        if "target_scope:multi_target" not in notes:
            return None
        ssh_rows = getattr(getattr(self.settings, "connections", object()), "ssh", {})
        if not isinstance(ssh_rows, dict) or not ssh_rows:
            return None
        refs = tuple(str(ref or "").strip() for ref in sorted(ssh_rows.keys()) if str(ref or "").strip())
        if not refs:
            return None
        requests = tuple(
            ContextRequest(
                surface_id="connections",
                mode="action",
                query=str(message or "").strip(),
                depth="shallow",
                limit=1,
                budget={
                    "catalog_id": f"connection|ssh|{ref}",
                    "entity_type": "connection",
                    "kind": "ssh",
                    "ref": ref,
                    "contract_source": "runtime_task_capability_draft",
                },
                user_id=user_id,
                turn_id=request_id,
            )
            for ref in refs
        )
        target_intent = next((note.split(":", 1)[1] for note in notes if note.startswith("target_intent:")), "")
        arbitration = AriaTurnArbitration(
            source="runtime_task_contract",
            plan=AriaTurnPlan(
                intents=("runtime_action",),
                surfaces=("connections",),
                actions=("connection_action_ssh",),
                needs_context=True,
                context_directions=("connections",),
                context_depth="shallow",
                queries={"connections": str(message or "").strip()},
                context_requests=requests,
                priority=tuple(f"connection|ssh|{ref}" for ref in refs),
                answer_mode="plan_action",
                contract_mode="action",
                evidence_policy="source_bound",
                risk="medium",
                needs_confirmation=True,
                confidence=max(0.70, float(getattr(capability_draft, "confidence", 0.0) or 0.0)),
                reason=f"runtime_task_contract:{target_intent or 'ssh_command'}",
            ),
            usage={},
        )
        if self._routing_debug_enabled():
            self._last_meta_catalog_fallback_debug_lines = [
                meta_arbitration.debug_line,
                "Routing Debug: runtime_task_contract "
                f"source=capability_draft_decision capability=ssh_command kind=ssh "
                f"target_scope=multi_target target_intent={target_intent or '-'} "
                "meta_answer_contract=overridden",
            ]
        return arbitration

    def _last_runtime_outcome_frame(self, user_id: str) -> RuntimeOutcomeFrame:
        return self._runtime_outcome_frames.get(str(user_id or "web"), RuntimeOutcomeFrame())

    async def _try_runtime_outcome_followup_result(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        language: str | None,
        start: float,
    ) -> PipelineResult | None:
        frame = self._last_runtime_outcome_frame(user_id)
        payload = frame.as_payload()
        if not payload or not frame.followup_affordances:
            return None
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="runtime_outcome_followup_resolution",
            system=(
                "You decide whether the user message is a follow-up to ARIA's last runtime outcome. "
                "Return JSON only. Choose action=use_previous_outcome, rerun_previous_action, "
                "new_meta_catalog_turn, or clarify. Use only the provided followup_affordances. "
                "Use use_previous_outcome for pronouns or references such as 'davon', 'those', "
                "'which of them', or requests to rank/explain the previous result. Do not invent data."
            ),
            payload={
                "message": str(message or "").strip(),
                "language": str(language or ""),
                "last_runtime_outcome": payload,
                "allowed_actions": ["use_previous_outcome", "rerun_previous_action", "new_meta_catalog_turn", "clarify"],
                "allowed_affordances": list(frame.followup_affordances),
            },
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not decision.ok:
            return None
        confidence = confidence_score(decision.payload.get("confidence"))
        action = str(decision.payload.get("action", "") or "").strip().lower()
        affordance = str(decision.payload.get("affordance", "") or "").strip().lower()
        if confidence < 0.62 or action != "use_previous_outcome" or affordance not in set(frame.followup_affordances):
            return None
        if frame.kind == "ssh" and frame.capability == "ssh_command" and frame.task_intent == "package_update_check":
            fallback_summary = self._package_update_followup_fallback_summary(frame, language=language)
            summary, summary_debug = await self._multi_target_ssh_llm_operator_summary(
                message=str(message or "").strip(),
                command=frame.command,
                records=[dict(row) for row in frame.records],
                fallback_summary=fallback_summary or frame.summary,
                language=language,
            )
            text = summary or fallback_summary or frame.summary
            detail_lines = [
                "Routing Debug: runtime_outcome_followup "
                f"action=use_previous_outcome affordance={affordance} "
                f"surface={frame.surface_id} kind={frame.kind} capability={frame.capability} "
                f"task_intent={frame.task_intent} targets={len(frame.targets)} confidence={confidence:.2f}",
            ]
            if summary_debug:
                detail_lines.append(summary_debug)
            return PipelineResult(
                request_id=request_id,
                text=text,
                usage=dict(decision.usage or {}),
                intents=["runtime_outcome_followup"],
                skill_errors=[],
                router_level=2,
                duration_ms=int((time.perf_counter() - start) * 1000),
                detail_lines=detail_lines,
            )
        return None

    @staticmethod
    def _package_update_followup_fallback_summary(frame: RuntimeOutcomeFrame, *, language: str | None = None) -> str:
        package_refs: dict[str, set[str]] = {}
        for row in frame.records:
            ref = str(row.get("ref", "") or "").strip()
            raw_text = str(row.get("raw_text", "") or row.get("text", "") or "")
            for line in raw_text.splitlines():
                clean = line.strip()
                if "/" not in clean or "upgradable" not in clean.lower():
                    continue
                package = clean.split("/", 1)[0].strip()
                if not package:
                    continue
                package_refs.setdefault(package, set()).add(ref)
        if not package_refs:
            return "Ich habe den letzten Update-Check gefunden, aber darin keine auswertbaren Paketnamen erkannt."
        priority_terms = ("linux-image", "linux-headers", "openssl", "openssh", "sudo", "libc", "systemd", "apt", "dpkg", "curl", "gnupg")

        def _score(item: tuple[str, set[str]]) -> tuple[int, int, str]:
            package, refs = item
            securityish = 1 if any(term in package.lower() for term in priority_terms) else 0
            return securityish, len(refs), package

        ranked = sorted(package_refs.items(), key=_score, reverse=True)[:10]
        rows = [
            f"`{package}` ({len(refs)} Server: {', '.join(sorted(refs)[:5])}{', ...' if len(refs) > 5 else ''})"
            for package, refs in ranked
        ]
        return (
            "Aus dem letzten `apt list --upgradable`-Ergebnis wuerde ich zuerst diese Pakete anschauen: "
            + "; ".join(rows)
            + ". Ohne Advisory-Abgleich ist das eine technische Priorisierung nach Pakettyp und Verbreitung, keine bestaetigte CVE-Prioritaet."
        )

    async def process(
        self,
        message: str,
        user_id: str = "web",
        source: str = "web",
        language: str | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        auto_memory_enabled: bool = False,
        aria_turn_arbitration: AriaTurnArbitration | None = None,
    ) -> PipelineResult:
        start = time.perf_counter()
        timing = StageTimingLedger(enabled=self._routing_debug_enabled())
        request_id = str(uuid4())
        self._last_active_learning_hints = []

        persona = self.prompt_loader.get_persona()
        routing_profile = self.settings.routing.for_language(language)
        decision = RouterDecision(intents=["chat"], level=1)
        runtime_recipes: list[dict[str, Any]] | None = None

        def finalize_result(result: PipelineResult) -> PipelineResult:
            timing.add("pipeline_wall_time", int((time.perf_counter() - start) * 1000))
            result.detail_lines = self._insert_stage_timing_detail_lines(result.detail_lines, timing)
            return result

        def load_runtime_recipes_once() -> list[dict[str, Any]]:
            nonlocal runtime_recipes
            with timing.measure("load_runtime_recipes"):
                if runtime_recipes is None:
                    runtime_recipes = self._load_stored_recipe_runtime()
                return runtime_recipes

        if aria_turn_arbitration is None:
            with timing.measure("runtime_outcome_followup"):
                runtime_followup_result = await self._try_runtime_outcome_followup_result(
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    source=source,
                    language=language,
                    start=start,
                )
            if runtime_followup_result is not None:
                return finalize_result(runtime_followup_result)

        if aria_turn_arbitration is None:
            with timing.measure("aria_turn_arbiter"):
                aria_turn_arbitration = await self._arbitrate_aria_turn(
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    language=language,
                    runtime_recipes=[],
                )
        else:
            self._remember_aria_turn_frame(aria_turn_arbitration, user_id=user_id)
        meta_catalog_contract = self._aria_turn_uses_meta_catalog_contract(aria_turn_arbitration)
        action_contract_selected = bool(
            aria_turn_arbitration is not None
            and (
                aria_turn_arbitration.plan.actions
                or aria_turn_arbitration.plan.needs_confirmation
                or aria_turn_arbitration.plan.answer_mode == "plan_action"
            )
        )
        confident_local_context = self._aria_turn_has_confident_local_context(aria_turn_arbitration)
        if meta_catalog_contract:
            timing.add("legacy_router", 0)
            decision = replace(
                decision,
                intents=self._merge_aria_turn_intents(list(decision.intents or []), aria_turn_arbitration),
                level=max(int(decision.level or 1), 2),
            )
            self._last_active_learning_hints = []
        elif confident_local_context:
            timing.add("legacy_router", 0)
            self._last_active_learning_hints = []
        else:
            with timing.measure("legacy_router"):
                decision = self.classify_routing(message, language=language)
            with timing.measure("turn_intent_arbiter"):
                decision = await self._classify_routing_agentic(
                    message,
                    keyword_decision=decision,
                    language=language,
                    user_id=user_id,
                    request_id=request_id,
                    source=source,
                )
        if aria_turn_arbitration is not None:
            decision = replace(
                decision,
                intents=self._merge_aria_turn_intents(list(decision.intents or []), aria_turn_arbitration),
                level=max(int(decision.level or 1), 2),
            )
        recipe_status_recipes = load_runtime_recipes_once() if "recipe_status" in set(decision.intents or []) else []
        with timing.measure("recipe_status_stage"):
            recipe_status_stage = await self._run_recipe_status_stage(
                decision=decision,
                runtime_recipes=recipe_status_recipes,
                auto_memory_enabled=auto_memory_enabled,
                start=start,
                request_id=request_id,
                user_id=user_id,
                source=source,
        )
        if recipe_status_stage.direct_result is not None:
            return finalize_result(recipe_status_stage.direct_result)

        if confident_local_context or (meta_catalog_contract and not action_contract_selected):
            custom_intents: list[str] = []
            capability_draft = None
            recipe_intent_debug_lines = [
                *list(getattr(self, "_last_meta_catalog_fallback_debug_lines", []) or []),
                *([aria_turn_arbitration.debug_line] if aria_turn_arbitration is not None else []),
                *(
                    ["Routing Debug: meta_catalog_contract phase=context legacy_semantics=skipped"]
                    if meta_catalog_contract
                    else []
                ),
            ]
        elif action_contract_selected:
            runtime_recipes_for_actions = []
            seed_capability_draft = self._aria_turn_seed_capability_draft(aria_turn_arbitration)
            with timing.measure("pre_rag_action_stage"):
                pre_rag_stage = await self._run_pre_rag_action_stage(
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    source=source,
                    decision=decision,
                    start=start,
                    runtime_recipes=runtime_recipes_for_actions,
                    auto_memory_enabled=auto_memory_enabled,
                    language=language,
                    seed_capability_draft=seed_capability_draft,
                    semantic_source=str(aria_turn_arbitration.source if aria_turn_arbitration is not None else ""),
                )
            custom_intents = pre_rag_stage.custom_intents
            capability_draft = pre_rag_stage.capability_draft
            action_contract_phase = "action_preflight" if meta_catalog_contract else "backup_action_preflight"
            recipe_intent_debug_lines = [
                *list(getattr(self, "_last_meta_catalog_fallback_debug_lines", []) or []),
                *([aria_turn_arbitration.debug_line] if aria_turn_arbitration is not None else []),
                (
                    "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped"
                    if meta_catalog_contract
                    else "Routing Debug: legacy_backup_action_contract phase=action_preflight chat_fallback=blocked"
                ),
            ]
            if pre_rag_stage.direct_result is not None:
                pre_rag_stage.direct_result.detail_lines = [
                    *recipe_intent_debug_lines,
                    *list(pre_rag_stage.direct_result.detail_lines or []),
                ]
                return finalize_result(pre_rag_stage.direct_result)
            duration_ms = int((time.perf_counter() - start) * 1000)
            action_names = ",".join(aria_turn_arbitration.plan.actions) if aria_turn_arbitration is not None else "-"
            result = self._build_routed_action_result(
                request_id=request_id,
                decision=decision,
                duration_ms=duration_ms,
                intents=[f"capability:{getattr(capability_draft, 'capability', '') or 'action'}"],
                text=self._pipeline_text(
                    language,
                    "meta_catalog_action_preflight_not_executable",
                    "I found a matching action in the meta catalog, but no safe executable preflight was produced yet. I did not run anything.",
                ),
                detail_lines=[
                    *recipe_intent_debug_lines,
                    "Routing Debug: meta_catalog_action_preflight "
                    f"actions={action_names or '-'} capability={getattr(capability_draft, 'capability', '') or '-'} "
                    f"boundary=guardrail phase={action_contract_phase} reason=no_executable_preflight",
                ],
                skill_errors=[],
            )
            return finalize_result(result)
        else:
            runtime_recipes_for_actions = load_runtime_recipes_once()
            with timing.measure("pre_rag_action_stage"):
                pre_rag_stage = await self._run_pre_rag_action_stage(
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    source=source,
                    decision=decision,
                    start=start,
                    runtime_recipes=runtime_recipes_for_actions,
                    auto_memory_enabled=auto_memory_enabled,
                    language=language,
                )
            custom_intents = pre_rag_stage.custom_intents
            capability_draft = pre_rag_stage.capability_draft
            if pre_rag_stage.direct_result is not None:
                return finalize_result(pre_rag_stage.direct_result)
            with timing.measure("recipe_arbitration_stage"):
                recipe_stage = await self._run_recipe_arbitration_stage(
                    message=message,
                    runtime_recipes=runtime_recipes_for_actions,
                    decision=decision,
                    custom_intents=custom_intents,
                    capability_draft=capability_draft,
                    start=start,
                    request_id=request_id,
                    user_id=user_id,
                    source=source,
                    auto_memory_enabled=auto_memory_enabled,
                    language=language,
                )
            custom_intents = recipe_stage.custom_intents
            recipe_intent_debug_lines = [
                *([aria_turn_arbitration.debug_line] if aria_turn_arbitration is not None else []),
                *recipe_stage.debug_lines,
            ]
            if recipe_stage.direct_result is not None:
                return finalize_result(recipe_stage.direct_result)

        merged_intents = self._merge_custom_intents(decision.intents, custom_intents)
        if confident_local_context or meta_catalog_contract:
            freshness_debug_lines = []
            freshness_auto_web_search = False
        else:
            with timing.measure("freshness_stage"):
                freshness_stage = await self._run_freshness_stage(
                    message=message,
                    intents=merged_intents,
                    language=language,
                    source=source,
                    user_id=user_id,
                    request_id=request_id,
                )
            merged_intents = freshness_stage.intents
            freshness_debug_lines = freshness_stage.debug_lines
            freshness_auto_web_search = freshness_stage.auto_web_search
        aria_query_overrides = self._aria_turn_query_overrides(aria_turn_arbitration)
        aria_context_overrides = self._aria_turn_context_overrides(aria_turn_arbitration, user_id=user_id)
        force_selected_context = self._aria_turn_forces_selected_context(aria_turn_arbitration)
        skill_auto_memory_enabled = auto_memory_enabled and not force_selected_context
        direct_inventory_fast_path = self._aria_turn_can_direct_inventory_fast_path(aria_turn_arbitration)
        direct_memory_exists_fast_path = self._aria_turn_can_direct_memory_exists_fast_path(aria_turn_arbitration)
        surface_loader_runtime = self._agentic_context_surface_loader()
        if direct_inventory_fast_path:
            skill_results = []
            recipe_intent_debug_lines.append("Routing Debug: direct_context_fast_path kind=inventory reason=turn_plan_inventory_request")
        elif direct_memory_exists_fast_path and aria_turn_arbitration is not None:
            recipe_intent_debug_lines.append("Routing Debug: direct_context_fast_path kind=memory_exists reason=turn_plan_memory_exists_request")
            with timing.measure("memory_exists_loader"):
                skill_results = [
                    await surface_loader_runtime.load_memory_exists(
                        arbitration=aria_turn_arbitration,
                        user_id=user_id,
                        memory_collection=memory_collection,
                        session_collection=session_collection,
                        context_overrides=aria_context_overrides,
                    )
                ]
        else:
            with timing.measure("skill_runtime"):
                skill_results = await self._run_skills(
                    merged_intents,
                    message,
                    user_id,
                    routing_profile=routing_profile,
                    language=str(language or "de"),
                    runtime_recipes=runtime_recipes or [],
                    memory_collection=memory_collection,
                    session_collection=session_collection,
                    auto_memory_enabled=skill_auto_memory_enabled,
                    suppress_web_search_note_context=("web_search" in merged_intents and not explicitly_requests_local_context(message)),
                    query_overrides=aria_query_overrides,
                    context_overrides=aria_context_overrides,
                )
        with timing.measure("context_inventory_loader"):
            skill_results = [*skill_results, *await surface_loader_runtime.load_inventory(aria_turn_arbitration)]
        skill_results, context_isolation_debug_lines = self._aria_turn_filter_skill_results_for_selected_context(
            arbitration=aria_turn_arbitration,
            skill_results=skill_results,
        )
        recipe_intent_debug_lines = [
            *recipe_intent_debug_lines,
            *context_isolation_debug_lines,
            *self._aria_turn_context_ledger_lines(
                arbitration=aria_turn_arbitration,
                query_overrides=aria_query_overrides,
                context_overrides=aria_context_overrides,
                skill_results=skill_results,
            ),
        ]
        if auto_memory_enabled:
            self._schedule_learning_outcome_recording(
                skill_results=skill_results,
                message=message,
                user_id=user_id,
                request_id=request_id,
            )
        safe_fix_plan = self._build_safe_fix_plan(skill_results)
        with timing.measure("direct_context_answer"):
            direct_context_result = await self._aria_turn_direct_context_result(
                arbitration=aria_turn_arbitration,
                skill_results=skill_results,
                detail_lines=recipe_intent_debug_lines,
                intents=merged_intents,
                decision=decision,
                safe_fix_plan=safe_fix_plan,
                start=start,
                request_id=request_id,
                user_id=user_id,
                source=source,
                language=language,
        )
        if direct_context_result is not None:
            return finalize_result(direct_context_result)
        with timing.measure("empty_context_guardrail"):
            empty_local_context_result = await self._aria_turn_empty_local_context_result(
                arbitration=aria_turn_arbitration,
                skill_results=skill_results,
                detail_lines=recipe_intent_debug_lines,
                intents=merged_intents,
                decision=decision,
                safe_fix_plan=safe_fix_plan,
                start=start,
                request_id=request_id,
                user_id=user_id,
                source=source,
                language=language,
        )
        if empty_local_context_result is not None:
            return finalize_result(empty_local_context_result)
        with timing.measure("web_search_precheck_stage"):
            web_search_precheck_result = await self._run_web_search_precheck_stage(
                skill_results=skill_results,
                intents=merged_intents,
                decision=decision,
                safe_fix_plan=safe_fix_plan,
                start=start,
                request_id=request_id,
                user_id=user_id,
                source=source,
                language=language,
        )
        if web_search_precheck_result is not None:
            return finalize_result(web_search_precheck_result)

        if not force_selected_context:
            with timing.measure("recent_context_stage"):
                skill_results = await self._append_recent_context_stage(
                    skill_results=skill_results,
                    intents=merged_intents,
                    message=message,
                    user_id=user_id,
                    language=language,
                )
        skill_results, late_context_isolation_debug_lines = self._aria_turn_filter_skill_results_for_selected_context(
            arbitration=aria_turn_arbitration,
            skill_results=skill_results,
        )
        if late_context_isolation_debug_lines:
            recipe_intent_debug_lines = [*recipe_intent_debug_lines, *late_context_isolation_debug_lines]

        with timing.measure("direct_chat_response_stage"):
            direct_chat_response = await self._run_direct_chat_response_stage(
                skill_results=skill_results,
                intents=merged_intents,
                decision=decision,
                safe_fix_plan=safe_fix_plan,
                capability_draft=capability_draft,
                custom_intents=custom_intents,
                recipe_debug_lines=recipe_intent_debug_lines,
                freshness_debug_lines=freshness_debug_lines,
                freshness_auto_web_search=freshness_auto_web_search,
                force_selected_context=force_selected_context,
                include_pre_rag_debug=not confident_local_context,
                start=start,
                request_id=request_id,
                user_id=user_id,
                source=source,
                message=message,
                language=language,
            )
        if direct_chat_response is not None:
            if auto_memory_enabled:
                self._schedule_active_learning_hint_outcome(
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    active_hints=list(getattr(self, "_last_active_learning_hints", []) or []),
                    final_intents=list(direct_chat_response.intents or []),
                    router_level=int(direct_chat_response.router_level or 0),
                )
            return finalize_result(direct_chat_response)

        with timing.measure("final_chat_response_stage"):
            final_response = await self._run_final_chat_response_stage(
                skill_results=skill_results,
                intents=merged_intents,
                decision=decision,
                safe_fix_plan=safe_fix_plan,
                capability_draft=capability_draft,
                custom_intents=custom_intents,
                recipe_debug_lines=recipe_intent_debug_lines,
                freshness_debug_lines=freshness_debug_lines,
                freshness_auto_web_search=freshness_auto_web_search,
                force_selected_context=force_selected_context,
                include_pre_rag_debug=not confident_local_context,
                persona=persona,
                start=start,
                request_id=request_id,
                user_id=user_id,
                source=source,
                message=message,
                language=language,
            )
        if auto_memory_enabled:
            self._schedule_active_learning_hint_outcome(
                message=message,
                user_id=user_id,
                request_id=request_id,
                active_hints=list(getattr(self, "_last_active_learning_hints", []) or []),
                final_intents=list(final_response.intents or []),
                router_level=int(final_response.router_level or 0),
            )
        return finalize_result(final_response)
