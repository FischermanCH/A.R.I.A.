from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aria.core.chat_context_filter import explicitly_requests_local_context
from aria.core.chat_context_filter import skill_result_is_local_memory_context
from aria.core.chat_freshness import decide_chat_freshness
from aria.core.chat_freshness import format_chat_freshness_debug
from aria.core.pipeline_models import PipelineResult
from aria.core.recipe_runtime_contract import RECIPE_STATUS_INTENT
from aria.core.recipe_runtime_contract import is_recipe_intent
from aria.core.recipe_runtime_contract import is_recipe_status_intent
from aria.skills.base import SkillResult


ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
ZERO_EMBEDDING_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


@dataclass
class PipelineRecipeStatusStageResult:
    direct_result: PipelineResult | None = None


@dataclass
class PipelinePreRagStageResult:
    custom_intents: list[str] = field(default_factory=list)
    capability_draft: Any | None = None
    direct_result: PipelineResult | None = None


@dataclass
class PipelineRecipeStageResult:
    custom_intents: list[str] = field(default_factory=list)
    debug_lines: list[str] = field(default_factory=list)
    direct_result: PipelineResult | None = None


@dataclass
class PipelineFreshnessStageResult:
    intents: list[str] = field(default_factory=list)
    debug_lines: list[str] = field(default_factory=list)
    auto_web_search: bool = False


class PipelineTurnStagesMixin:
    async def _run_recipe_status_stage(
        self,
        *,
        decision: Any,
        runtime_recipes: list[dict[str, Any]],
        auto_memory_enabled: bool,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
    ) -> PipelineRecipeStatusStageResult:
        if not any(is_recipe_status_intent(intent) for intent in decision.intents):
            return PipelineRecipeStatusStageResult()

        duration_ms = int((time.perf_counter() - start) * 1000)
        text = self._build_recipe_status_text(runtime_recipes, auto_memory_enabled)
        usage = dict(ZERO_USAGE)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=[RECIPE_STATUS_INTENT],
            router_level=decision.level,
            usage=usage,
            chat_model=self.settings.llm.model,
            embedding_model=self.settings.embeddings.model,
            embedding_usage=dict(ZERO_EMBEDDING_USAGE),
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            duration_ms=duration_ms,
            source=source,
            skill_errors=[],
            extraction_model="rule_based",
            extraction_usage=dict(ZERO_EMBEDDING_USAGE),
        )
        return PipelineRecipeStatusStageResult(
            direct_result=PipelineResult(
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
        )

    async def _run_pre_rag_action_stage(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        decision: Any,
        start: float,
        runtime_recipes: list[dict[str, Any]],
        auto_memory_enabled: bool = False,
        language: str | None = None,
        seed_capability_draft: Any | None = None,
        semantic_source: str = "",
    ) -> PipelinePreRagStageResult:
        direct_result, custom_intents, capability_draft = await self._try_pre_rag_action_gate(
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
        return PipelinePreRagStageResult(
            custom_intents=custom_intents,
            capability_draft=capability_draft,
            direct_result=direct_result,
        )

    async def _run_recipe_arbitration_stage(
        self,
        *,
        message: str,
        runtime_recipes: list[dict[str, Any]],
        decision: Any,
        custom_intents: list[str],
        capability_draft: Any | None,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
        auto_memory_enabled: bool = False,
        language: str | None = None,
    ) -> PipelineRecipeStageResult:
        trace_lines: list[str] = []
        resolved_custom_intents = list(custom_intents)
        if (
            decision.intents in (["chat"], ["memory_recall"])
            and not resolved_custom_intents
            and not self._should_suppress_recipe_candidates_for_capability_draft(capability_draft, message)
        ):
            resolved_custom_intents = await self._resolve_stored_recipe_intent_with_llm(
                message,
                runtime_recipes,
                debug_lines=trace_lines,
            )
        debug_lines = trace_lines if self._routing_debug_enabled() else []
        explicit_recipe_catalog_question = self._message_explicitly_asks_about_recipe(message)
        if resolved_custom_intents or (not self._recipe_intent_was_rejected(trace_lines) and not explicit_recipe_catalog_question):
            return PipelineRecipeStageResult(custom_intents=resolved_custom_intents, debug_lines=debug_lines)

        duration_ms = int((time.perf_counter() - start) * 1000)
        text, catalog_debug_line, usage = await self._build_recipe_catalog_explanation_response(
            message,
            runtime_recipes,
            language=language,
        )
        if auto_memory_enabled:
            self._schedule_recipe_catalog_learning_outcome(
                message=message,
                user_id=user_id,
                request_id=request_id,
                catalog_debug_line=catalog_debug_line,
                runtime_recipe_count=len(runtime_recipes),
                explicit_recipe_question=explicit_recipe_catalog_question,
            )
        if not self._recipe_catalog_debug_has_strong_match(catalog_debug_line) and not self._message_explicitly_asks_about_recipe(message):
            return PipelineRecipeStageResult(
                custom_intents=[],
                debug_lines=[*debug_lines, catalog_debug_line] if self._routing_debug_enabled() else debug_lines,
            )
        detail_lines: list[str] = []
        if self._routing_debug_enabled():
            detail_lines.extend(
                self._pre_rag_no_action_debug_lines(
                    capability_draft=capability_draft,
                    custom_intents=[],
                )
            )
            detail_lines.extend(debug_lines)
            detail_lines.append(catalog_debug_line)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=["chat"],
            router_level=decision.level,
            usage=usage,
            chat_model=self.settings.llm.model,
            embedding_model=self.settings.embeddings.model,
            embedding_usage=dict(ZERO_EMBEDDING_USAGE),
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            duration_ms=duration_ms,
            source=source,
            skill_errors=[],
            extraction_model="recipe_catalog_explanation",
            extraction_usage=dict(ZERO_EMBEDDING_USAGE),
        )
        return PipelineRecipeStageResult(
            custom_intents=[],
            debug_lines=debug_lines,
            direct_result=PipelineResult(
                request_id=request_id,
                text=text,
                usage=usage,
                intents=["chat"],
                skill_errors=[],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=None,
                detail_lines=detail_lines,
            ),
        )

    @staticmethod
    def _merge_custom_intents(base_intents: list[str], custom_intents: list[str]) -> list[str]:
        merged_intents = list(base_intents)
        for intent in custom_intents:
            if intent not in merged_intents:
                merged_intents.append(intent)
        return merged_intents

    async def _run_freshness_stage(
        self,
        *,
        message: str,
        intents: list[str],
        language: str | None,
        source: str,
        user_id: str,
        request_id: str,
    ) -> PipelineFreshnessStageResult:
        merged_intents = list(intents)
        debug_lines: list[str] = []
        auto_web_search = False
        if not (
            self.web_search_skill is not None
            and "web_search" not in merged_intents
            and not explicitly_requests_local_context(message)
            and not any(is_recipe_intent(str(intent)) for intent in merged_intents)
            and all(str(intent) in {"chat", "memory_recall"} for intent in merged_intents)
        ):
            return PipelineFreshnessStageResult(intents=merged_intents)

        freshness_decision = await decide_chat_freshness(
            message=message,
            intents=merged_intents,
            llm_client=self.llm_client,
            language=language,
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if freshness_decision.source != "none":
            debug_lines.append(format_chat_freshness_debug(freshness_decision))
        if freshness_decision.needs_fresh_context:
            merged_intents.append("web_search")
            auto_web_search = True
        return PipelineFreshnessStageResult(
            intents=merged_intents,
            debug_lines=debug_lines,
            auto_web_search=auto_web_search,
        )

    async def _append_recent_context_stage(
        self,
        *,
        skill_results: list[SkillResult],
        intents: list[str],
        message: str,
        user_id: str,
        language: str | None = None,
    ) -> list[SkillResult]:
        if not all(str(intent) in {"chat", "memory_recall"} for intent in intents):
            return skill_results
        recent_context_result = await self._recent_capability_context_skill_result(
            message,
            user_id,
            language=language,
        )
        if recent_context_result is None:
            return skill_results
        rows = list(skill_results)
        if not explicitly_requests_local_context(message):
            rows = [result for result in rows if not skill_result_is_local_memory_context(result)]
        return [*rows, recent_context_result]

    async def _run_web_search_precheck_stage(
        self,
        *,
        skill_results: list[SkillResult],
        intents: list[str],
        decision: Any,
        safe_fix_plan: list[dict[str, Any]] | None,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
        language: str | None = None,
    ) -> PipelineResult | None:
        web_search_results = [result for result in skill_results if result.skill_name == "web_search"]
        has_web_search_context = any(result.success and bool(str(result.content or "").strip()) for result in web_search_results)
        if "web_search" not in intents or not web_search_results or has_web_search_context:
            return None

        primary_error = next(
            (str(result.error or "").strip() for result in web_search_results if str(result.error or "").strip()),
            self._pipeline_text(language, "web_search_failed", "Web search failed."),
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        usage = dict(ZERO_USAGE)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=intents,
            router_level=decision.level,
            usage=usage,
            chat_model=self.settings.llm.model,
            embedding_model=self.settings.embeddings.model,
            embedding_usage=dict(ZERO_EMBEDDING_USAGE),
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            duration_ms=duration_ms,
            source=source,
            skill_errors=[primary_error],
            extraction_model="web_search_precheck",
            extraction_usage=dict(ZERO_EMBEDDING_USAGE),
        )
        return PipelineResult(
            request_id=request_id,
            text=primary_error,
            usage=usage,
            intents=intents,
            skill_errors=[primary_error],
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            safe_fix_plan=safe_fix_plan,
            detail_lines=self._collect_skill_detail_lines(skill_results),
        )

    async def _run_direct_chat_response_stage(
        self,
        *,
        skill_results: list[SkillResult],
        intents: list[str],
        decision: Any,
        safe_fix_plan: list[dict[str, Any]] | None,
        capability_draft: Any | None,
        custom_intents: list[str],
        recipe_debug_lines: list[str],
        freshness_debug_lines: list[str],
        freshness_auto_web_search: bool,
        force_selected_context: bool = False,
        include_pre_rag_debug: bool = True,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
        message: str,
        language: str | None = None,
    ) -> PipelineResult | None:
        direct_chat_result = next(
            (
                result
                for result in skill_results
                if bool((result.metadata or {}).get("direct_chat_response")) and bool(result.success)
            ),
            None,
        )
        if not (
            direct_chat_result is not None
            and any(is_recipe_intent(str(intent)) for intent in intents)
            and all(str(intent) == "chat" or is_recipe_intent(str(intent)) for intent in intents)
        ):
            return None

        local_context_debug_lines: list[str] = []
        filtered_direct_chat_skill_results = await self._filter_chat_context_skill_results(
            skill_results,
            message=message,
            intents=intents,
            allow_web_search_local_context=not freshness_auto_web_search,
            language=language,
            debug_lines=local_context_debug_lines,
            force_selected_context=force_selected_context,
        )
        skill_detail_lines = [
            *(
                self._pre_rag_no_action_debug_lines(
                    capability_draft=capability_draft,
                    custom_intents=custom_intents,
                )
                if include_pre_rag_debug
                else []
            ),
            *recipe_debug_lines,
            *freshness_debug_lines,
            *local_context_debug_lines,
            *self._collect_skill_detail_lines(filtered_direct_chat_skill_results),
        ]
        duration_ms = int((time.perf_counter() - start) * 1000)
        usage = dict(ZERO_USAGE)
        skill_errors = self._skill_errors(skill_results)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=intents,
            router_level=decision.level,
            usage=usage,
            chat_model=self.settings.llm.model,
            embedding_model=self.settings.embeddings.model,
            embedding_usage=dict(ZERO_EMBEDDING_USAGE),
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            duration_ms=duration_ms,
            source=source,
            skill_errors=skill_errors,
            extraction_model="rule_based",
            extraction_usage=dict(ZERO_EMBEDDING_USAGE),
        )
        return PipelineResult(
            request_id=request_id,
            text=str((direct_chat_result.metadata or {}).get("direct_chat_text") or direct_chat_result.content),
            usage=usage,
            intents=intents,
            skill_errors=skill_errors,
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=None,
            embedding_cost_usd=None,
            total_cost_usd=None,
            safe_fix_plan=safe_fix_plan,
            detail_lines=skill_detail_lines,
        )

    async def _run_final_chat_response_stage(
        self,
        *,
        skill_results: list[SkillResult],
        intents: list[str],
        decision: Any,
        safe_fix_plan: list[dict[str, Any]] | None,
        capability_draft: Any | None,
        custom_intents: list[str],
        recipe_debug_lines: list[str],
        freshness_debug_lines: list[str],
        freshness_auto_web_search: bool,
        force_selected_context: bool = False,
        include_pre_rag_debug: bool = True,
        persona: str,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
        message: str,
        language: str | None = None,
    ) -> PipelineResult:
        local_context_debug_lines: list[str] = []
        chat_context_skill_results = await self._filter_chat_context_skill_results(
            skill_results,
            message=message,
            intents=intents,
            allow_web_search_local_context=not freshness_auto_web_search,
            language=language,
            debug_lines=local_context_debug_lines,
            force_selected_context=force_selected_context,
        )
        prompts = self.context_assembler.build(
            persona=persona,
            skill_results=chat_context_skill_results,
            user_message=message,
            language=str(language or "de"),
        )
        read_only_followup_instruction = self._read_only_runtime_followup_instruction(chat_context_skill_results)
        if read_only_followup_instruction:
            prompts[0]["content"] = f"{prompts[0]['content']}\n\n{read_only_followup_instruction}"
        if freshness_auto_web_search:
            prompts[0]["content"] = (
                f"{prompts[0]['content']}\n\n"
                f"Freshness instruction: Today is {date.today().isoformat()}. "
                "When current web/search context is provided, prefer the freshest relevant sources. "
                "Do not mention outdated fallback dates or older training cutoffs unless the uncertainty is directly relevant."
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
        skill_errors, extraction_model, extraction_usage = self._skill_failure_and_extraction_stats(skill_results)

        usage_total = usage_snapshot.get("usage", {}) if isinstance(usage_snapshot, dict) else {}
        if not bool(getattr(llm_response, "metered", False)):
            usage_total = {
                "prompt_tokens": int(llm_response.usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(llm_response.usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(llm_response.usage.get("total_tokens", 0) or 0),
            }
        embedding_usage = usage_snapshot.get("embedding_usage", {}) if isinstance(usage_snapshot, dict) else {}
        if not isinstance(embedding_usage, dict):
            embedding_usage = dict(ZERO_EMBEDDING_USAGE)

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
            intents=intents,
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
            skill_errors=skill_errors,
            extraction_model=extraction_model,
            extraction_usage=extraction_usage,
        )

        skill_detail_lines = [
            *(
                self._pre_rag_no_action_debug_lines(
                    capability_draft=capability_draft,
                    custom_intents=custom_intents,
                )
                if include_pre_rag_debug
                else []
            ),
            *recipe_debug_lines,
            *freshness_debug_lines,
            *local_context_debug_lines,
            *self._collect_skill_detail_lines(chat_context_skill_results),
        ]

        return PipelineResult(
            request_id=request_id,
            text=llm_response.content,
            usage=usage_total,
            intents=intents,
            skill_errors=skill_errors,
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=chat_cost_usd,
            embedding_cost_usd=embedding_cost_usd,
            total_cost_usd=total_cost_usd,
            safe_fix_plan=safe_fix_plan,
            detail_lines=skill_detail_lines,
        )
