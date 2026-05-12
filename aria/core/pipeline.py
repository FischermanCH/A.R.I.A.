from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, replace
from functools import wraps
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.core.action_plan import ActionPlan, CapabilityDraft, MemoryHints, build_action_plan
from aria.core.action_candidate_taxonomy import is_recipe_candidate_kind
from aria.core.action_candidate_taxonomy import normalize_action_candidate_kind
from aria.core.action_planner import debug_bounded_action_plan_decision
from aria.core.agentic_prompt_flow import agentic_prompt_flow_debug_line
from aria.core.agentic_prompt_flow import build_agentic_prompt_flow
from aria.core.bounded_planner import debug_bounded_planner_decision
from aria.core.capability_catalog import (
    capability_executor_kinds,
    capability_executor_bindings,
    capability_matches_connection_kind,
    normalize_capability,
)
from aria.core.capability_context import CapabilityContextStore
from aria.core.capability_router import CapabilityRouter
from aria.core.connection_catalog import connection_kind_label, connection_routing_spec, normalize_connection_kind
from aria.core.connection_dossiers import build_file_target_dossier
from aria.core.connection_dossiers import build_http_api_target_dossier
from aria.core.connection_dossiers import build_message_target_dossier
from aria.core.connection_dossiers import build_read_target_dossier
from aria.core.connection_dossiers import build_ssh_target_dossier
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
from aria.core.config import RoutingLanguageConfig, Settings
from aria.core.context import ContextAssembler
from aria.core.routing_index import RoutingIndexStore
from aria.core.embedding_client import EmbeddingClient
from aria.core.error_interpreter import ErrorInterpreter
from aria.core.execution_dry_run import (
    build_execution_preview_dry_run,
    build_payload_dry_run,
    evaluate_guardrail_confirm_dry_run,
)
from aria.core.execution_dry_run_payloads import connection_row as payload_connection_row
from aria.core.execution_dry_run_payloads import read_row_list
from aria.core.execution_dry_run_payloads import read_row_value
from aria.core.guardrails import evaluate_guardrail
from aria.core.guardrails import resolve_guardrail_profile
from aria.core.http_api_agentic_resolution import apply_agentic_http_api_resolution as core_apply_agentic_http_api_resolution
from aria.core.http_api_policy import HTTPAPIPolicyDecision
from aria.core.file_agentic_resolution import apply_agentic_file_operation_resolution as core_apply_agentic_file_operation_resolution
from aria.core.messaging_agentic_resolution import apply_agentic_message_operation_resolution as core_apply_agentic_message_operation_resolution
from aria.core.read_agentic_resolution import apply_agentic_read_operation_resolution as core_apply_agentic_read_operation_resolution
from aria.core.read_agentic_resolution import read_draft_is_complete
from aria.core.i18n import I18NStore
from aria.core.executor_registry import ExecutorRegistry
from aria.core.agentic_runtime_debug import runtime_debug_line_for_plan
from aria.core.learned_recipe_integration import record_routed_action_success
from aria.core.learned_recipe_integration import record_routed_stored_recipe_success
from aria.core.learned_recipe_store_updates import record_successful_learned_recipe_execution
from aria.core.pipeline_recipe_experience import format_recipe_experience_context
from aria.core.pipeline_recipe_experience import recipe_experience_context
from aria.core.pipeline_recipe_experience import recipe_experience_context_rows
from aria.core.pipeline_recipe_experience import recipe_experience_debug_lines
from aria.core.recipe_experience_memory import search_recipe_experience_memory
from aria.core.recipe_experience_memory import store_recipe_experience_memory
from aria.core.llm_client import LLMClient
from aria.core.memory_assist import MemoryAssistResolver
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
from aria.core.pipeline_capability_messages import format_capability_execution_error
from aria.core.pipeline_capability_messages import format_capability_missing_message
from aria.core.pipeline_capability_messages import sanitize_capability_error
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
from aria.core.pipeline_routing_debug_helpers import routing_candidates_from_resolved
from aria.core.pipeline_routing_debug_helpers import serialize_connection_candidates
from aria.core.pricing_catalog import resolve_pricing_entry
from aria.core.planner_candidates import build_connection_planner_input_set
from aria.core.planner_candidates import build_planner_input_set
from aria.core.planner_candidates import merge_planner_input_sets
from aria.core.planner_candidates import planner_candidate_from_action_payload
from aria.core.planner_candidates import planner_candidate_from_connection_payload
from aria.core.planner_candidates import planner_input_set_to_dict
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.recipe_runtime_contract import RECIPE_MANIFEST_MISSING_ERROR
from aria.core.recipe_runtime_contract import RECIPE_STATUS_INTENT
from aria.core.recipe_runtime_contract import build_recipe_intent
from aria.core.recipe_runtime_contract import build_recipe_runtime_skill_name
from aria.core.recipe_runtime_contract import is_recipe_intent
from aria.core.recipe_runtime_contract import is_recipe_status_intent
from aria.core.recipe_result_view import friendly_recipe_error_text
from aria.core.router import KeywordRouter
from aria.core.routing_admin import ensure_connection_routing_index_ready
from aria.core.routing_admin import resolve_connection_routing_chain
from aria.core.routing_admin import routing_connections_collection_name
from aria.core.routing_index import DEFAULT_CONNECTION_ROUTING_KINDS
from aria.core.routing_resolver import infer_preferred_connection_kind
from aria.core.routing_resolver import RoutingResolver
from aria.core.rss_grouping import build_rss_status_groups
from aria.core.safe_fix import SafeFixExecutor, build_safe_fix_plan, extract_held_packages, format_held_packages_summary
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
    should_skip_recipe_auto_memory_persist,
)
from aria.core.ssh_runtime import SSHRuntime
from aria.core.ssh_agentic_resolution import apply_agentic_ssh_command_resolution as core_apply_agentic_ssh_command_resolution
from aria.core.ssh_guardrail_commands import combined_ssh_allow_commands
from aria.core.ssh_guardrail_commands import ssh_guardrail_allow_terms
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


@dataclass
class PipelineResult:
    request_id: str
    text: str
    usage: dict[str, int]
    intents: list[str]
    skill_errors: list[str]
    router_level: int
    duration_ms: int
    chat_cost_usd: float | None = None
    embedding_cost_usd: float | None = None
    total_cost_usd: float | None = None
    safe_fix_plan: list[dict[str, Any]] | None = None
    detail_lines: list[str] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None

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
        language: str | None = None,
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
                language=language,
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


class Pipeline:
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
        if isinstance(getattr(getattr(settings, "connections", object()), "searxng", {}), dict):
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
        handler_map = {
            "file_read": self._capability_executor.execute_file_read,
            "file_write": self._capability_executor.execute_file_write,
            "file_list": self._capability_executor.execute_file_list,
            "feed_read": self._capability_executor.execute_feed_read,
            "website_read": self._capability_executor.execute_website_read,
            "website_list": self._capability_executor.execute_website_list,
            "calendar_read": self._capability_executor.execute_calendar_read,
            "webhook_send": self._capability_executor.execute_webhook_send,
            "discord_send": self._capability_executor.execute_discord_send,
            "api_request": self._capability_executor.execute_api_request,
            "email_send": self._capability_executor.execute_email_send,
            "mail_read": self._capability_executor.execute_mail_read,
            "mail_search": self._capability_executor.execute_mail_search,
            "mqtt_publish": self._capability_executor.execute_mqtt_publish,
            "ssh_command": self._capability_executor.execute_ssh_command,
        }
        for connection_kind, capability in capability_executor_bindings():
            handler = handler_map.get(capability)
            if handler is not None:
                self._executor_registry.register(connection_kind, capability, handler)

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
    def _looks_like_same_ssh_target_followup(message: str) -> bool:
        clean = re.sub(r"\s+", " ", str(message or "")).strip().lower()
        if not clean:
            return False
        spec = connection_routing_spec("ssh")
        for term in spec.follow_up_same_target_terms:
            clean_term = str(term or "").strip().lower()
            if not clean_term:
                continue
            if " " in clean_term:
                if clean_term in clean:
                    return True
                continue
            if re.search(rf"\b{re.escape(clean_term)}\b", clean):
                return True
        return False

    def _looks_like_ssh_followup_message(self, message: str, user_id: str, *, language: str | None = None) -> bool:
        clean = re.sub(r"\s+", " ", str(message or "")).strip()
        if not clean:
            return False
        recent = self._load_recent_capability_context(user_id)
        if str(recent.get("capability", "") or "").strip() != "ssh_command":
            return False
        if str(recent.get("connection_kind", "") or "").strip() != "ssh":
            return False
        lower = clean.lower()
        if self._looks_like_same_ssh_target_followup(clean):
            return True

        followup_starter = any(
            lower == term or lower.startswith(term + " ")
            for term in connection_routing_spec("ssh").follow_up_starter_terms
            if str(term).strip()
        )

        connection_pools = self._capability_routing_connection_pools()
        ssh_rows = dict(connection_pools.get("ssh", {}) or {})
        if not ssh_rows:
            return False
        alias_rows: dict[str, list[str]] = {}
        for ref, row in ssh_rows.items():
            clean_ref = str(ref).strip()
            if clean_ref:
                alias_rows[clean_ref] = build_connection_aliases("ssh", clean_ref, row)
        lexicon = self.capability_router._lexicon_for_language(language)
        explicit_kind, explicit_ref = self.capability_router._extract_explicit_connection_by_kind(
            clean,
            {"ssh": ssh_rows.keys()},
            lexicon,
            {"ssh": alias_rows} if alias_rows else None,
        )
        if explicit_kind == "ssh" and explicit_ref:
            return followup_starter or bool(re.search(r"\b(?:nochmal|erneut|wieder)\b", lower)) or bool(
                re.search(r"\bwie\s+sieht\s+es\b", lower)
            )
        requested_candidate = self.capability_router._extract_requested_connection_ref_hint(clean, "ssh", lexicon)
        if requested_candidate:
            return followup_starter or bool(re.search(r"\bwie\s+sieht\s+es\b", lower))
        return False

    def _rewrite_ssh_followup_message(self, message: str, user_id: str, *, language: str | None = None) -> str:
        clean_message = str(message or "").strip()
        if not clean_message:
            return clean_message
        if not self._looks_like_ssh_followup_message(clean_message, user_id, language=language):
            return clean_message

        recent = self._load_recent_capability_context(user_id)
        if str(recent.get("capability", "") or "").strip() != "ssh_command":
            return clean_message
        if str(recent.get("connection_kind", "") or "").strip() != "ssh":
            return clean_message

        connection_pools = self._capability_routing_connection_pools()
        ssh_rows = dict(connection_pools.get("ssh", {}) or {})
        if not ssh_rows:
            return clean_message
        alias_rows: dict[str, list[str]] = {}
        for ref, row in ssh_rows.items():
            clean_ref = str(ref).strip()
            if clean_ref:
                alias_rows[clean_ref] = build_connection_aliases("ssh", clean_ref, row)
        lexicon = self.capability_router._lexicon_for_language(language)
        explicit_kind, explicit_ref = self.capability_router._extract_explicit_connection_by_kind(
            clean_message,
            {"ssh": ssh_rows.keys()},
            lexicon,
            {"ssh": alias_rows} if alias_rows else None,
        )
        requested_candidate = self.capability_router._extract_requested_connection_ref_hint(clean_message, "ssh", lexicon)

        target_ref = explicit_ref if explicit_kind == "ssh" else ""
        target_phrase = requested_candidate if not target_ref else ""
        if not target_ref and not target_phrase and self._looks_like_same_ssh_target_followup(clean_message):
            target_ref = str(recent.get("connection_ref", "") or "").strip()

        if target_ref:
            rewrite_prefix = connection_routing_spec("ssh").follow_up_rewrite_prefix or "ssh"
            return f"{rewrite_prefix} {target_ref} {clean_message}"
        if target_phrase:
            rewrite_prefix = connection_routing_spec("ssh").follow_up_rewrite_prefix or "ssh"
            return f"{rewrite_prefix} {target_phrase} {clean_message}"
        return clean_message

    def _build_ssh_target_dossier(self, connection_ref: str, *, user_id: str = "") -> dict[str, Any]:
        rows = dict(self._capability_routing_connection_pools().get("ssh", {}) or {})
        recent = self._load_recent_capability_context(user_id) if user_id else {}
        dossier = build_ssh_target_dossier(rows, connection_ref, recent_context=recent)
        guardrail_ref = str(dossier.get("guardrail_ref", "") or "").strip()
        if not guardrail_ref:
            return dossier
        profile = resolve_guardrail_profile(self.settings, guardrail_ref)
        profile_kind = str(profile.get("kind", "") if isinstance(profile, dict) else getattr(profile, "kind", "")).strip()
        if profile_kind != "ssh_command":
            return dossier
        allow_terms = list(profile.get("allow_terms", []) or []) if isinstance(profile, dict) else list(getattr(profile, "allow_terms", []) or [])
        deny_terms = list(profile.get("deny_terms", []) or []) if isinstance(profile, dict) else list(getattr(profile, "deny_terms", []) or [])
        dossier["guardrail_allow_terms"] = [str(item).strip() for item in allow_terms if str(item).strip()]
        dossier["guardrail_deny_terms"] = [str(item).strip() for item in deny_terms if str(item).strip()]
        return dossier

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

    async def _apply_agentic_ssh_command_resolution(
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
        return await core_apply_agentic_ssh_command_resolution(
            client=self.llm_client if llm_client is None else llm_client,
            message=message,
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=capability_draft,
            language=language,
            build_ssh_target_dossier=self._build_ssh_target_dossier,
            extract_json_object=self._extract_json_object,
            normalize_spaces=self._normalize_spaces,
            routing_debug_enabled=self._routing_debug_enabled,
            msg=self._msg,
            with_capability_draft_updates=with_capability_draft_updates,
        )

    async def _refresh_resolved_agentic_ssh_command(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str = "",
        capability_draft: Any | None = None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        routing_decision = dict(resolved.get("decision", {}) or {})
        if normalize_connection_kind(str(routing_decision.get("kind", "") or "")) != "ssh":
            return resolved, capability_draft
        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        if str(action_decision.get("candidate_id", "") or "").strip() != "ssh_run_command":
            return resolved, capability_draft
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        working_draft = capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(
                capability=str(payload.get("capability", "") or "ssh_command").strip() or "ssh_command",
                connection_kind="ssh",
                explicit_connection_ref=str(payload.get("connection_ref", "") or "").strip(),
                requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
                path=str(payload.get("path", "") or "").strip(),
                content=str(payload.get("content", "") or "").strip(),
                plan_class=str(payload.get("plan_class", "") or "").strip(),
                behavior_profile=str(payload.get("behavior_profile", "") or "").strip(),
            )
        else:
            draft_updates: dict[str, Any] = {}
            if not str(getattr(working_draft, "content", "") or "").strip() and str(payload.get("content", "") or "").strip():
                draft_updates["content"] = str(payload.get("content", "") or "").strip()
            if not str(getattr(working_draft, "path", "") or "").strip() and str(payload.get("path", "") or "").strip():
                draft_updates["path"] = str(payload.get("path", "") or "").strip()
            if not str(getattr(working_draft, "explicit_connection_ref", "") or "").strip() and str(payload.get("connection_ref", "") or "").strip():
                draft_updates["explicit_connection_ref"] = str(payload.get("connection_ref", "") or "").strip()
            if not str(getattr(working_draft, "requested_connection_ref", "") or "").strip() and str(payload.get("requested_connection_ref", "") or "").strip():
                draft_updates["requested_connection_ref"] = str(payload.get("requested_connection_ref", "") or "").strip()
            if draft_updates:
                working_draft = with_capability_draft_updates(working_draft, **draft_updates)
        updated_action_debug, capability_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
            llm_client=self.llm_client,
        )
        resolved["action_debug"] = updated_action_debug
        original_payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        original_safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
        original_execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
        payload_debug = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
        )
        payload_debug = self._apply_capability_draft_overrides(
            payload_debug,
            capability_draft=capability_draft,
        )
        resolved["payload_debug"] = payload_debug
        recalculated_safety = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        recalculated_execution = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=recalculated_safety,
            language=str(language or ""),
        )
        refreshed_payload_content = str((payload_debug.get("payload") or {}).get("content", "") or "").strip()
        original_payload_content = str(original_payload.get("content", "") or "").strip()
        updated_decision = dict((updated_action_debug or {}).get("decision", {}) or {})
        fallback_replaced_blocked_command = bool(updated_decision.get("guardrail_fallback_from")) or (
            refreshed_payload_content
            and refreshed_payload_content != original_payload_content
        )
        if str(original_safety.get("action", "") or "").strip().lower() == "block" and not fallback_replaced_blocked_command:
            resolved["safety_debug"] = {"available": True, "used": True, "status": "block", "visual_status": "block", "decision": original_safety}
            resolved["execution_debug"] = {"available": True, "used": True, "status": "block", "visual_status": "block", "decision": original_execution}
        else:
            resolved["safety_debug"] = recalculated_safety
            resolved["execution_debug"] = recalculated_execution
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, debug_line)
        return resolved, capability_draft

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
        if "fischerman" in tokens:
            return "Fischerman"
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
    def _call_with_optional_language(func: Any, *args: Any, language: str = "de") -> Any:
        try:
            return func(*args, language=language)
        except TypeError as exc:
            if "unexpected keyword argument 'language'" not in str(exc):
                raise
            return func(*args)

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
    def _sanitize_skill_id(value: str) -> str:
        return sanitize_recipe_id(value)

    @staticmethod
    def _normalize_skill_keywords(value: Any) -> list[str]:
        return normalize_recipe_keywords(value)

    @staticmethod
    def _normalize_skill_steps(value: Any) -> list[dict[str, Any]]:
        return normalize_recipe_steps(value)

    @staticmethod
    def _render_step_template(template: str, values: dict[str, str]) -> str:
        return render_step_template(template, values)

    def _load_recipe_toggles(self) -> dict[str, bool]:
        return load_recipe_toggles(self._config_path)

    def _load_stored_recipe_runtime(self) -> list[dict[str, Any]]:
        rows, cache = load_stored_recipe_runtime(
            skills_dir=self._stored_recipes_dir,
            config_path=self._config_path,
            cache=self._stored_recipe_cache,
        )
        self._stored_recipe_cache = cache
        return rows

    def _match_stored_recipe_intents(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return match_stored_recipe_intents(message, runtime_skills)

    def _match_recipe_intents(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return match_recipe_intents(message, runtime_skills)

    async def _resolve_stored_recipe_intent_with_llm(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return await resolve_stored_recipe_intent_with_llm(message, runtime_skills, self.llm_client)

    async def _resolve_recipe_intent_with_llm(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return await resolve_recipe_intent_with_llm(message, runtime_skills, self.llm_client)

    @staticmethod
    def _should_skip_recipe_auto_memory_persist(intents: list[str]) -> bool:
        return should_skip_recipe_auto_memory_persist(intents)

    @staticmethod
    def _should_skip_auto_memory_persist(intents: list[str]) -> bool:
        return should_skip_recipe_auto_memory_persist(intents)

    def _build_recipe_status_text(self, runtime_recipes: list[dict[str, Any]], auto_memory_enabled: bool) -> str:
        return build_recipe_status_text(self.settings, runtime_recipes, auto_memory_enabled)

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
    ) -> SkillResult:
        return await self._ssh_runtime.execute_custom_ssh_command(
            skill_id=skill_id,
            skill_name=skill_name,
            connection_ref=connection_ref,
            command_template=command_template,
            message=message,
            timeout_seconds=timeout_seconds,
            language=language,
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
        requested_tokens = {
            token
            for token in re.split(r"[^a-z0-9]+", clean_requested.lower())
            if token and token not in {"server", "host", "system", "node", "profile", "profil", "channel", "kanal"}
        }
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

    @staticmethod
    def _payload_multi_target_refs(payload: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        for item in list(payload.get("connection_refs", []) or []):
            clean = str(item or "").strip()
            if clean and clean not in refs:
                refs.append(clean)
        return refs

    def _preflight_multi_target_ssh_refs(
        self,
        refs: list[str],
        command: str,
    ) -> tuple[list[str], list[dict[str, str]], list[str]]:
        allowed_refs: list[str] = []
        blocked: list[dict[str, str]] = []
        detail_lines = [
            "Routing Debug: multi_target_ssh_preflight "
            f"refs={len(refs)} command={command}"
        ]
        for ref in refs:
            row = payload_connection_row(self.settings, "ssh", ref)
            if row is None:
                reason = "connection_not_found"
                blocked.append({"ref": ref, "reason": reason, "action": "block"})
                detail_lines.append(
                    "Routing Debug: multi_target_ssh_preflight_target "
                    f"ref={ref} action=block reason={reason}"
                )
                continue

            guardrail_ref = read_row_value(row, "guardrail_ref")
            guardrail_profile = resolve_guardrail_profile(self.settings, guardrail_ref)
            allow_commands = combined_ssh_allow_commands(
                read_row_list(row, "allow_commands"),
                ssh_guardrail_allow_terms(guardrail_profile),
            )
            policy = validate_ssh_readonly_policy(command, allow_commands=allow_commands)
            guardrail_decision = evaluate_guardrail(
                profile_ref=guardrail_ref,
                profile=guardrail_profile,
                kind="ssh_command",
                text=command,
            )
            if policy.action != "allow":
                blocked.append({"ref": ref, "reason": policy.reason, "action": policy.action})
                detail_lines.append(
                    "Routing Debug: multi_target_ssh_preflight_target "
                    f"ref={ref} action={policy.action} reason={policy.reason}"
                )
                continue
            if not guardrail_decision.allowed:
                reason = guardrail_decision.reason or "guardrail_blocked"
                blocked.append({"ref": ref, "reason": reason, "action": "block"})
                detail_lines.append(
                    "Routing Debug: multi_target_ssh_preflight_target "
                    f"ref={ref} action=block reason={reason} guardrail={guardrail_ref or '-'}"
                )
                continue

            allowed_refs.append(ref)
            detail_lines.append(
                "Routing Debug: multi_target_ssh_preflight_target "
                f"ref={ref} action=allow reason={policy.reason} guardrail={guardrail_ref or '-'}"
            )

        detail_lines.append(
            "Routing Debug: multi_target_ssh_preflight_result "
            f"allowed={len(allowed_refs)} blocked={len(blocked)}"
        )
        return allowed_refs, blocked, detail_lines

    @staticmethod
    def _multi_target_ssh_result_state(text: str) -> str:
        clean = str(text or "").strip().lower()
        if not clean:
            return "ok"
        critical_tokens = (
            "(kritisch)",
            "(critical)",
            "handlungsbedarf",
            "action required",
            "critical",
        )
        warning_tokens = (
            "(eng)",
            "(tight)",
            "(erhoeht)",
            "(elevated)",
            "beobachten",
            "watch",
            "failed units",
            "nicht erreichbar",
            "unreachable",
        )
        if any(token in clean for token in critical_tokens):
            return "attention"
        if any(token in clean for token in warning_tokens):
            return "attention"
        return "ok"

    def _multi_target_ssh_operator_summary(
        self,
        *,
        language: str | None,
        target_count: int,
        records: list[dict[str, str]],
    ) -> str:
        ok_count = sum(1 for row in records if row.get("state") == "ok")
        attention_count = sum(1 for row in records if row.get("state") == "attention")
        blocked_count = sum(1 for row in records if row.get("state") == "blocked")
        error_count = sum(1 for row in records if row.get("state") == "error")
        if attention_count <= 0 and blocked_count <= 0 and error_count <= 0:
            return _pipeline_text(
                language,
                "multi_target_ssh_operator_ok",
                "Overall: {ok_count}/{count} SSH targets look ok.",
                ok_count=ok_count,
                count=target_count,
            )
        return _pipeline_text(
            language,
            "multi_target_ssh_operator_mixed",
            "Overall: {ok_count} ok, {attention_count} need attention, {blocked_count} blocked, {error_count} failed.",
            ok_count=ok_count,
            attention_count=attention_count,
            blocked_count=blocked_count,
            error_count=error_count,
        )

    @staticmethod
    def _multi_target_ssh_relevant_result_texts(records: list[dict[str, str]]) -> list[str]:
        has_attention = any(str(row.get("state", "") or "") != "ok" for row in records)
        if not has_attention:
            return []
        return [
            str(row.get("text", "") or "").strip()
            for row in records
            if str(row.get("state", "") or "") != "ok" and str(row.get("text", "") or "").strip()
        ]

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

    async def _finalize_ssh_plural_multi_target_action(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str,
        capability_draft: Any | None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if not callable(looks_like_plural_target):
            return resolved, capability_draft
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

        action_decision = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        if str(action_decision.get("candidate_id", "") or "").strip() != "ssh_run_command":
            return resolved, capability_draft

        payload_kind = normalize_connection_kind(str(payload.get("connection_kind", "") or ""))
        draft_kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        if payload_kind not in {"", "ssh"} or draft_kind not in {"", "ssh"}:
            return resolved, capability_draft

        resolved, capability_draft = await self._prepare_ssh_plural_multi_target_command(
            resolved,
            message=message,
            user_id=user_id,
            candidate_connections=ssh_connections,
            capability_draft=capability_draft,
            language=language,
        )
        resolved = self._apply_ssh_plural_multi_target_resolution(
            resolved,
            candidate_connections=ssh_connections,
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

    @staticmethod
    def _should_backfill_missing_ssh_command(
        *,
        resolved: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        return (
            Pipeline._payload_missing_fields(payload) == ["content"]
            and str(payload.get("capability", "") or "").strip() == "ssh_command"
            and normalize_connection_kind(str(dict(resolved.get("decision", {}) or {}).get("kind", "") or "")) == "ssh"
            and not str(payload.get("content", "") or "").strip()
        )

    async def _refresh_missing_ssh_command_resolution(
        self,
        *,
        resolved: dict[str, Any],
        message: str,
        user_id: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        ssh_draft = CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=str(payload.get("connection_ref", "") or "").strip(),
            requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
            path=str(payload.get("path", "") or "").strip(),
            content="",
            plan_class=str(payload.get("plan_class", "") or "").strip().lower(),
            behavior_profile=str(payload.get("behavior_profile", "") or "").strip().lower(),
            notes=[
                str(item or "").strip()
                for item in list(payload.get("notes", []) or [])
                if str(item or "").strip()
            ],
        )
        refreshed_action_debug, refreshed_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=message,
            user_id=user_id,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_debug=dict(resolved.get("action_debug", {}) or {}),
            capability_draft=ssh_draft,
            language=language,
            llm_client=self.llm_client,
        )
        refreshed_payload = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_decision=dict((refreshed_action_debug or {}).get("decision", {}) or {}),
        )
        refreshed_payload = self._apply_capability_draft_overrides(
            refreshed_payload,
            capability_draft=refreshed_draft,
        )
        refreshed_safety = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=refreshed_payload,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            language=str(language or ""),
        )
        refreshed_execution = build_execution_preview_dry_run(
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_decision=dict((refreshed_action_debug or {}).get("decision", {}) or {}),
            payload_debug=refreshed_payload,
            safety_debug=refreshed_safety,
            language=str(language or ""),
        )
        resolved["action_debug"] = refreshed_action_debug
        resolved["payload_debug"] = refreshed_payload
        resolved["safety_debug"] = refreshed_safety
        resolved["execution_debug"] = refreshed_execution
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, *[line for line in debug_line.splitlines() if line.strip()])
        return resolved

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
            if debug_line and debug_line not in detail_lines:
                detail_lines.append(debug_line)
            if line not in detail_lines:
                resolved["detail_lines"] = [*detail_lines, line]
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
            "Routing Debug: capability_draft "
            f"capability={str(getattr(working_draft, 'capability', '') or '').strip() or '-'} "
            f"kind={effective_kind or '-'} "
            f"explicit_ref={str(getattr(working_draft, 'explicit_connection_ref', '') or '').strip() or '-'} "
            f"requested_ref={str(getattr(working_draft, 'requested_connection_ref', '') or '').strip() or '-'} "
            f"path={str(getattr(working_draft, 'path', '') or '').strip() or '-'} "
            f"content={str(getattr(working_draft, 'content', '') or '').strip() or '-'}",
            "Routing Debug: candidate_pool "
            f"effective_kind={effective_kind or '-'} "
            f"candidates={', '.join(sorted(str(ref).strip() for ref in candidate_connections.keys() if str(ref).strip())) or '-'}",
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

        requested_ref_hint = str(getattr(working_draft, "requested_connection_ref", "") or "").strip()
        plural_target_scope = False
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if callable(looks_like_plural_target) and not explicit_ref and not requested_ref_hint:
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
        working_draft = self._draft_with_hint_path(working_draft, hints)

        if chain_complete:
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
            kind_only = await self._build_kind_only_routed_resolution(
                message,
                connection_kind=effective_kind,
                language=language,
                llm_client=None,
                capability_draft=working_draft,
                source="kind_inferred",
                reason=str(hints.matched_text or effective_kind),
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
                        source="kind_inferred",
                        note=str(hints.matched_text or effective_kind),
                    ),
                    preferred_kind=effective_kind,
                ),
            )
            kind_only = self._attach_connection_candidates_debug(kind_only, planner_connection_candidates)
            if plural_target_scope:
                kind_only, working_draft = await self._prepare_ssh_plural_multi_target_command(
                    kind_only,
                    message=message,
                    user_id=user_id,
                    candidate_connections=candidate_connections,
                    capability_draft=working_draft,
                    language=language,
                )
                kind_only = self._apply_ssh_plural_multi_target_resolution(
                    kind_only,
                    candidate_connections=candidate_connections,
                    capability_draft=working_draft,
                    language=language,
                )
            return self._apply_requested_connection_guard(kind_only, capability_draft=working_draft, language=language)

        forced_resolved = await self._build_forced_routed_resolution(
            message,
            connection_kind=effective_kind,
            connection_ref=forced_ref,
            language=language,
            llm_client=effective_llm_client,
            capability_draft=working_draft,
            source=str(hints.source or "memory_hint"),
            reason=str(hints.matched_text or forced_ref),
        )
        forced_resolved["detail_lines"] = self._resolved_routing_detail_lines(resolved)
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
        routing_source = str(dict(resolved.get("decision", {}) or {}).get("source", "") or "").strip()
        payload["requested_connection_ref"] = requested_ref
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

    async def _execute_multi_target_ssh_action(
        self,
        *,
        resolved: dict[str, Any],
        payload: dict[str, Any],
        action: dict[str, Any],
        user_id: str,
        language: str = "de",
    ) -> tuple[list[str], str, list[str], list[str]]:
        refs = self._payload_multi_target_refs(payload)
        command = str(payload.get("content", "") or "").strip()
        intents = ["capability:ssh_command"]
        if not refs or not command:
            plan = self._payload_to_action_plan(payload)
            return intents, self._format_capability_missing_message(plan, language=language), [], []

        detail_lines: list[str] = []
        result_records: list[dict[str, str]] = []
        errors: list[str] = []
        success_count = 0
        original_count = len(refs)
        allowed_refs, blocked_refs, preflight_detail_lines = self._preflight_multi_target_ssh_refs(refs, command)
        if self._routing_debug_enabled():
            detail_lines.extend(preflight_detail_lines)
        for blocked in blocked_refs:
            ref = str(blocked.get("ref", "") or "").strip()
            reason = str(blocked.get("reason", "") or "").strip() or "blocked"
            errors.append(f"capability_ssh_command_blocked:{ref}:{reason}")
            blocked_text = _pipeline_text(
                language,
                "multi_target_ssh_blocked_target",
                "{ref} blocked: {reason}.",
                ref=ref,
                reason=reason,
            )
            result_records.append({"ref": ref, "state": "blocked", "text": blocked_text})

        for ref in allowed_refs:
            plan = ActionPlan(
                capability="ssh_command",
                connection_kind="ssh",
                connection_ref=ref,
                content=command,
                plan_class=str(payload.get("plan_class", "") or "").strip().lower(),
                behavior_profile=str(payload.get("behavior_profile", "") or "").strip().lower(),
                resolution_source="plural_target_scope",
                notes=list(payload.get("notes", []) or []),
            )
            if self._routing_debug_enabled():
                detail_lines.append(runtime_debug_line_for_plan(plan))
            detail_lines.extend(self._build_capability_detail_lines(plan, language=language))
            try:
                result_text = await self._executor_registry.execute(plan, language=language)
            except Exception as exc:
                error_text = self._format_capability_execution_error(plan, exc, language=language)
                errors.append(f"capability_ssh_command_error:{ref}:{type(exc).__name__}")
                result_records.append({"ref": ref, "state": "error", "text": error_text})
                continue

            success_count += 1
            clean_text = str(result_text or "").strip()
            if clean_text:
                result_records.append(
                    {
                        "ref": ref,
                        "state": self._multi_target_ssh_result_state(clean_text),
                        "text": clean_text,
                    }
                )

            if self.capability_context_store is not None:
                try:
                    self.capability_context_store.remember_action(
                        user_id,
                        capability=plan.capability,
                        connection_kind=plan.connection_kind,
                        connection_ref=plan.connection_ref,
                        path=plan.path,
                        content=plan.content,
                    )
                except Exception:
                    pass
            try:
                learned_entry = record_routed_action_success(
                    action=action,
                    plan=plan,
                    result_text=clean_text,
                    recorder=record_successful_learned_recipe_execution,
                    user_message=str(resolved.get("query", "") or ""),
                )
                if learned_entry and self.memory_skill is not None:
                    await store_recipe_experience_memory(
                        self.memory_skill,
                        user_id=user_id,
                        entry=learned_entry,
                    )
            except Exception:
                pass

        relevant_summary = " ".join(self._multi_target_ssh_relevant_result_texts(result_records)).strip()
        if not result_records and not relevant_summary:
            summary = _pipeline_text(
                language,
                "multi_target_ssh_no_output",
                "No SSH target returned output.",
            )
        else:
            operator_summary = self._multi_target_ssh_operator_summary(
                language=language,
                target_count=original_count,
                records=result_records,
            )
            summary = f"{operator_summary} {relevant_summary}".strip()
        if errors:
            text = _pipeline_text(
                language,
                "multi_target_ssh_partial",
                "Checked {count} SSH targets; {success_count} succeeded and {error_count} failed. {summary}",
                count=original_count,
                success_count=success_count,
                error_count=len(errors),
                summary=summary,
            )
        else:
            text = _pipeline_text(
                language,
                "multi_target_ssh_success",
                "Checked {count} SSH targets. {summary}",
                count=original_count,
                summary=summary,
            )
        return intents, text, detail_lines, errors

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
                if runtime_row:
                    learned_entry = record_routed_stored_recipe_success(
                        row=runtime_row,
                        skill_result=skill_result,
                        recorder=record_successful_learned_recipe_execution,
                    )
                    if learned_entry and self.memory_skill is not None:
                        await store_recipe_experience_memory(
                            self.memory_skill,
                            user_id=user_id,
                            entry=learned_entry,
                        )
            except Exception:
                pass
            return intents, text, detail_lines, []

        if (
            normalize_capability(str(payload.get("capability", "") or "")) == "ssh_command"
            and normalize_connection_kind(str(payload.get("connection_kind", "") or "")) == "ssh"
            and self._payload_multi_target_refs(payload)
        ):
            return await self._execute_multi_target_ssh_action(
                resolved=resolved,
                payload=payload,
                action=action,
                user_id=user_id,
                language=language,
            )

        plan = self._payload_to_action_plan(payload)
        if (
            plan.capability == "feed_read"
            and normalize_connection_kind(plan.connection_kind) == "rss"
            and not str(getattr(plan, "requested_connection_ref", "") or "").strip()
        ):
            rss_bundle = await self._rss_group_bundle_for_query(
                str(resolved.get("query", "") or ""),
                selected_ref=plan.connection_ref,
            )
            if rss_bundle is None:
                rss_bundle = self._rss_group_bundle_from_candidate_aliases(
                    str(resolved.get("query", "") or ""),
                    selected_ref=plan.connection_ref,
                    candidate_rows=list(resolved.get("connection_candidates_debug", []) or []),
                )
            if rss_bundle is not None:
                plan = replace(plan, notes=[*list(plan.notes or []), self._build_rss_group_bundle_note(*rss_bundle)])
        intents = [f"capability:{plan.capability}"] if str(plan.capability or "").strip() else ["chat"]
        detail_lines: list[str] = []
        if self._routing_debug_enabled():
            detail_lines.append(runtime_debug_line_for_plan(plan))
        detail_lines.extend(self._build_capability_detail_lines(plan, language=language))
        try:
            result_text = await self._executor_registry.execute(plan, language=language)
        except Exception as exc:
            error_text = self._format_capability_execution_error(plan, exc, language=language)
            error_code = f"capability_{plan.capability}_error:{type(exc).__name__}"
            return intents, error_text, detail_lines, [error_code]
        if self.capability_context_store is not None and plan.is_complete:
            try:
                self.capability_context_store.remember_action(
                    user_id,
                    capability=plan.capability,
                    connection_kind=plan.connection_kind,
                    connection_ref=plan.connection_ref,
                    path=plan.path,
                    content=plan.content,
                )
            except Exception:
                pass
        try:
            learned_entry = record_routed_action_success(
                action=action,
                plan=plan,
                result_text=result_text,
                recorder=record_successful_learned_recipe_execution,
                user_message=str(resolved.get("query", "") or ""),
            )
            if learned_entry and self.memory_skill is not None:
                await store_recipe_experience_memory(
                    self.memory_skill,
                    user_id=user_id,
                    entry=learned_entry,
                )
        except Exception:
            pass
        return intents, result_text, detail_lines, []

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
            text = self._routing_reason_text(resolved, language=language)
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
        routing_detail_lines = self._resolved_routing_detail_lines(resolved)
        result_intents, result_text, detail_lines, errors = await self._execute_routed_action(
            resolved,
            user_id=user_id,
            runtime_recipes=runtime_recipes,
            language=str(language or "de"),
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
            text = self._routing_reason_text(resolved, language=language)
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
            error_code = f"capability_{plan.capability}_error:{type(exc).__name__}"
            return intent, error_text, details, plan, [error_code]
        return intent, result_text, details, plan, []

    async def _try_capability_action(
        self,
        message: str,
        user_id: str,
        language: str | None = None,
    ) -> tuple[list[str], str, list[str], ActionPlan, list[str]] | None:
        connection_pools: dict[str, dict[str, Any]] = {}
        for kind in ("sftp", "smb", "rss", "website", "webhook", "discord", "http_api", "email", "imap", "mqtt"):
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
                return intent, self._routing_reason_text(resolved, language=language), detail_lines, plan, []
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
        try:
            result_text = await self._executor_registry.execute(plan, language=str(language or "de"))
        except Exception as exc:
            error_text = self._format_capability_execution_error(plan, exc, language=language)
            error_code = f"capability_{plan.capability}_error:{type(exc).__name__}"
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
        for kind in ("ssh", "sftp", "smb", "google_calendar", "rss", "website", "webhook", "discord", "http_api", "email", "imap", "mqtt"):
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

        return self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={kind: rows.keys() for kind, rows in connection_pools.items()},
            available_connection_aliases_by_kind=connection_aliases_by_kind,
        )

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
        if content == "df -h":
            return True
        looks_like_plural_target = getattr(self._memory_assist, "_looks_like_plural_target_request", None)
        if callable(looks_like_plural_target) and str(message or "").strip():
            try:
                return bool(looks_like_plural_target(message, "ssh"))
            except Exception:
                return False
        return False

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
        line = (
            f"Routing Debug: pre_rag_action_gate action_path={action_path} "
            f"capability={capability} kind={kind} explicit_ref={explicit_ref} "
            f"requested_ref={requested_ref} path={path} content={content} "
            "boundary=context_enrichment"
        )
        if reason:
            line = f"{line} reason={reason}"
        return line

    def _prepend_pre_rag_gate_debug(self, result: PipelineResult, *, action_path: str, capability_draft: Any | None) -> PipelineResult:
        if not self._routing_debug_enabled():
            return result
        result.detail_lines = [
            self._pre_rag_gate_debug_line(action_path=action_path, capability_draft=capability_draft),
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
        language: str | None = None,
    ) -> tuple[PipelineResult | None, list[str], Any | None]:
        if decision.intents not in (["chat"], ["memory_recall"]):
            return None, [], None

        capability_message = self._rewrite_calendar_followup_message(message, user_id)
        capability_message = self._rewrite_ssh_followup_message(
            capability_message,
            user_id,
            language=language,
        )
        capability_draft = self._classify_capability_draft(capability_message, language=language)
        custom_intents = self._match_stored_recipe_intents(message, runtime_recipes)
        if self._should_suppress_recipe_candidates_for_capability_draft(capability_draft, capability_message):
            custom_intents = []

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

        explicit_or_targeted_signal = any(
            str(getattr(capability_draft, field, "") or "").strip()
            for field in ("explicit_connection_ref", "requested_connection_ref", "path")
        )
        content_signal = str(getattr(capability_draft, "content", "") or "").strip()
        strong_capability_signal = self._capability_matches_connection_kind(capability_draft) and (
            explicit_or_targeted_signal or (content_signal and not custom_intents)
        )
        if self._should_try_unified_routing(capability_message, capability_draft) and (strong_capability_signal or not custom_intents):
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
            "Routing Debug: recipe_candidate_suppressed reason=capability_draft_preferred_over_recipe capability=ssh_command",
        )
        return resolved

    def classify_routing(self, message: str, *, language: str | None = None) -> RouterDecision:
        routing_profile = self.settings.routing.for_language(language)
        return self.router.classify(message, routing=routing_profile)

    async def process(
        self,
        message: str,
        user_id: str = "web",
        source: str = "web",
        language: str | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        auto_memory_enabled: bool = False,
    ) -> PipelineResult:
        start = time.perf_counter()
        request_id = str(uuid4())

        persona = self.prompt_loader.get_persona()
        routing_profile = self.settings.routing.for_language(language)
        decision = self.classify_routing(message, language=language)
        runtime_recipes = self._load_stored_recipe_runtime()
        if any(is_recipe_status_intent(intent) for intent in decision.intents):
            duration_ms = int((time.perf_counter() - start) * 1000)
            text = self._build_recipe_status_text(runtime_recipes, auto_memory_enabled)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=[RECIPE_STATUS_INTENT],
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[],
                extraction_model="rule_based",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return PipelineResult(
                request_id=request_id,
                text=text,
                usage=usage,
                intents=[RECIPE_STATUS_INTENT],
                skill_errors=[],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=None,
            )

        custom_intents: list[str] = []
        capability_draft: Any | None = None
        pre_rag_result, custom_intents, capability_draft = await self._try_pre_rag_action_gate(
            message,
            user_id,
            request_id=request_id,
            source=source,
            decision=decision,
            start=start,
            runtime_recipes=runtime_recipes,
            language=language,
        )
        if pre_rag_result is not None:
            return pre_rag_result
        if (
            decision.intents in (["chat"], ["memory_recall"])
            and not custom_intents
            and not self._should_suppress_recipe_candidates_for_capability_draft(capability_draft, message)
        ):
            custom_intents = await self._resolve_stored_recipe_intent_with_llm(message, runtime_recipes)

        merged_intents = list(decision.intents)
        for intent in custom_intents:
            if intent not in merged_intents:
                merged_intents.append(intent)
        skill_results = await self._run_skills(
            merged_intents,
            message,
            user_id,
            routing_profile=routing_profile,
            language=str(language or "de"),
            runtime_recipes=runtime_recipes,
            memory_collection=memory_collection,
            session_collection=session_collection,
            auto_memory_enabled=auto_memory_enabled,
        )
        safe_fix_plan = self._build_safe_fix_plan(skill_results)
        web_search_results = [result for result in skill_results if result.skill_name == "web_search"]
        has_web_search_context = any(result.success and bool(str(result.content or "").strip()) for result in web_search_results)
        if "web_search" in merged_intents and web_search_results and not has_web_search_context:
            primary_error = next(
                (str(result.error or "").strip() for result in web_search_results if str(result.error or "").strip()),
                _pipeline_text(language, "web_search_failed", "Web search failed."),
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=merged_intents,
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[primary_error],
                extraction_model="web_search_precheck",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return PipelineResult(
                request_id=request_id,
                text=primary_error,
                usage=usage,
                intents=merged_intents,
                skill_errors=[primary_error],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=safe_fix_plan,
                detail_lines=self._collect_skill_detail_lines(skill_results),
            )

        direct_chat_result = next(
            (
                result
                for result in skill_results
                if bool((result.metadata or {}).get("direct_chat_response")) and bool(result.success)
            ),
            None,
        )
        if (
            direct_chat_result is not None
            and any(is_recipe_intent(str(intent)) for intent in merged_intents)
            and all(str(intent) == "chat" or is_recipe_intent(str(intent)) for intent in merged_intents)
        ):
            skill_detail_lines = [
                *self._pre_rag_no_action_debug_lines(
                    capability_draft=capability_draft,
                    custom_intents=custom_intents,
                ),
                *self._collect_skill_detail_lines(skill_results),
            ]
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=merged_intents,
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[r.error for r in skill_results if not r.success and r.error],
                extraction_model="rule_based",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return PipelineResult(
                request_id=request_id,
                text=str((direct_chat_result.metadata or {}).get("direct_chat_text") or direct_chat_result.content),
                usage=usage,
                intents=merged_intents,
                skill_errors=[r.error for r in skill_results if not r.success and r.error],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=safe_fix_plan,
                detail_lines=skill_detail_lines,
            )

        prompts = self.context_assembler.build(
            persona=persona,
            skill_results=skill_results,
            user_message=message,
            language=str(language or "de"),
        )

        with self.usage_meter.scope(
            request_id=request_id,
            user_id=user_id,
            source=source,
            router_level=decision.level,
        ) as usage_scope:
            llm_response = await self.llm_client.chat(
                prompts,
                source=source,
                operation="final_chat_response",
                user_id=user_id,
                request_id=request_id,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage_snapshot = self.usage_meter.snapshot_scope(usage_scope)

        embedding_model = str(usage_snapshot.get("embedding_model", "")).strip() or self.settings.embeddings.model
        extraction_prompt_tokens = 0
        extraction_completion_tokens = 0
        extraction_total_tokens = 0
        extraction_calls = 0
        extraction_model = "rule_based"
        for result in skill_results:
            meta = result.metadata or {}
            extract_usage = meta.get("extraction_usage")
            if isinstance(extract_usage, dict):
                extraction_prompt_tokens += int(extract_usage.get("prompt_tokens", 0) or 0)
                extraction_completion_tokens += int(extract_usage.get("completion_tokens", 0) or 0)
                extraction_total_tokens += int(extract_usage.get("total_tokens", 0) or 0)
                extraction_calls += 1
            if meta.get("extraction_model"):
                extraction_model = str(meta["extraction_model"])

        usage_total = usage_snapshot.get("usage", {}) if isinstance(usage_snapshot, dict) else {}
        if not bool(getattr(llm_response, "metered", False)):
            usage_total = {
                "prompt_tokens": int(llm_response.usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(llm_response.usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(llm_response.usage.get("total_tokens", 0) or 0),
            }
        embedding_usage = usage_snapshot.get("embedding_usage", {}) if isinstance(usage_snapshot, dict) else {}
        if not isinstance(embedding_usage, dict):
            embedding_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}

        chat_cost_usd = usage_snapshot.get("chat_cost_usd") if isinstance(usage_snapshot, dict) else None
        embedding_cost_usd = usage_snapshot.get("embedding_cost_usd") if isinstance(usage_snapshot, dict) else None
        total_cost_usd = usage_snapshot.get("total_cost_usd") if isinstance(usage_snapshot, dict) else None

        if not bool(getattr(llm_response, "metered", False)) and self.settings.pricing.enabled:
            chat_price_cfg = self._resolve_pricing_entry(
                self.settings.pricing.chat_models,
                self.settings.llm.model,
            )
            if chat_price_cfg:
                prompt_tokens = int(llm_response.usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(llm_response.usage.get("completion_tokens", 0) or 0)
                chat_cost_usd = (
                    (prompt_tokens * float(chat_price_cfg.input_per_million))
                    + (completion_tokens * float(chat_price_cfg.output_per_million))
                ) / 1_000_000
                total_cost_usd = chat_cost_usd if embedding_cost_usd is None else float(chat_cost_usd + float(embedding_cost_usd))

        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=merged_intents,
            router_level=decision.level,
            usage=usage_total,
            chat_model=str(usage_snapshot.get("chat_model", "")).strip() or self.settings.llm.model,
            embedding_model=embedding_model,
            embedding_usage=embedding_usage,
            chat_cost_usd=chat_cost_usd,
            embedding_cost_usd=embedding_cost_usd,
            total_cost_usd=total_cost_usd,
            duration_ms=duration_ms,
            source=source,
            skill_errors=[r.error for r in skill_results if not r.success and r.error],
            extraction_model=extraction_model,
            extraction_usage={
                "prompt_tokens": extraction_prompt_tokens,
                "completion_tokens": extraction_completion_tokens,
                "total_tokens": extraction_total_tokens,
                "calls": extraction_calls,
            },
        )

        skill_detail_lines = [
            *self._pre_rag_no_action_debug_lines(
                capability_draft=capability_draft,
                custom_intents=custom_intents,
            ),
            *self._collect_skill_detail_lines(skill_results),
        ]

        return PipelineResult(
            request_id=request_id,
            text=llm_response.content,
            usage=usage_total,
            intents=merged_intents,
            skill_errors=[r.error for r in skill_results if not r.success and r.error],
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=chat_cost_usd,
            embedding_cost_usd=embedding_cost_usd,
            total_cost_usd=total_cost_usd,
            safe_fix_plan=safe_fix_plan,
            detail_lines=skill_detail_lines,
        )
