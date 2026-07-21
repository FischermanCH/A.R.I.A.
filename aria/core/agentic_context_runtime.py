from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
import re
import time
from typing import Any

from aria.core.active_learning_hint_runtime import recall_active_learning_hints
from aria.core.active_learning_hint_runtime import should_skip_active_learning_hints_for_turn
from aria.core.aria_turn_arbitration import AriaTurnArbiter
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnCollectionOption
from aria.core.aria_turn_arbitration import build_aria_turn_menu
from aria.core.action_plan import CapabilityDraft
from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.context_answer_runtime import compose_aria_context_answer
from aria.core.context_answer_runtime import document_corpus_scan_match_chunks
from aria.core.context_answer_runtime import document_inventory_sources_for_query
from aria.core.context_answer_runtime import docs_search_fallback_answer
from aria.core.context_answer_runtime import fast_docs_search_answer
from aria.core.context_answer_runtime import fast_notes_inventory_answer
from aria.core.connection_catalog import connection_kind_label
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_semantic_resolver import build_connection_aliases
from aria.core.connection_semantic_resolver import connection_label_match_score
from aria.core.chat_turn_context import compact_recent_visible_chat_context
from aria.core.chat_context_filter import explicitly_requests_local_context
from aria.core.chat_freshness import chat_freshness_candidate
from aria.core.chat_freshness import decide_chat_freshness
from aria.core.chat_freshness import explicitly_requests_web_research
from aria.core.context_evidence import common_request_terms
from aria.core.context_evidence import evidence_terms
from aria.core.context_evidence import inventory_matches
from aria.core.context_evidence import inventory_query_terms
from aria.core.context_evidence import inventory_soft_scope_terms
from aria.core.context_evidence import normalized_evidence_text
from aria.core.context_evidence import request_scope_terms
from aria.core.context_evidence import text_matches_evidence
from aria.core.context_source_counts import context_source_count
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.context_surfaces import ContextRequest
from aria.core.context_runtime_state import ContextRuntimeState
from aria.core.context_runtime_state import turn_frame_from_arbitration
from aria.core.i18n import I18NStore
from aria.core.meta_catalog_routing import MetaCatalogRouter
from aria.core.meta_catalog_routing import MetaCatalogRoutingConfig
from aria.core.meta_catalog_routing import META_CATALOG_ROUTING_OPERATION
from aria.core.meta_catalog_routing import MetaCatalogRoutingInput
from aria.core.pipeline_models import PipelineResult
from aria.core.stage_timing import StageTimingLedger
from aria.core.stage_timing import insert_stage_timing_detail_lines
from aria.core.surface_loader_runtime import SurfaceLoaderRuntime
from aria.core.surface_loader_runtime import _BROAD_ADDRESS_SCOPE_TOKENS
from aria.core.surface_loader_runtime import _query_requests_specific_connection_scope
from aria.core.surface_loader_runtime import _query_requests_network_address
from aria.core.surface_loader_runtime import _tokenize_inventory_scope
from aria.core.turn_intent_arbitration import TurnIntentArbiter
from aria.skills.base import SkillResult


_AGENTIC_CONTEXT_RUNTIME_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")
CONNECTION_EVIDENCE_SCOPE_REVIEW_OPERATION = "connection_evidence_scope_review"


class AgenticContextRuntimeMixin:
    @staticmethod
    def _pipeline_text(language: str | None, key: str, default: str = "", **values: object) -> str:
        template = _AGENTIC_CONTEXT_RUNTIME_I18N.t(language or "de", f"pipeline.{key}", default or key)
        if not values:
            return template
        try:
            return template.format(**values)
        except Exception:
            return template

    def _agentic_context_surface_loader(self) -> SurfaceLoaderRuntime:
        return SurfaceLoaderRuntime(self)

    def _agentic_context_runtime_state(self) -> ContextRuntimeState:
        return ContextRuntimeState(self._aria_turn_frames)

    async def _aria_turn_collection_options(self, *, user_id: str) -> tuple[AriaTurnCollectionOption, ...]:
        raw_targets: list[dict[str, Any]] = []
        if self.memory_skill is not None:
            for method_name in ("_build_recall_targets", "_build_document_targets"):
                method = getattr(self.memory_skill, method_name, None)
                if method is None:
                    continue
                try:
                    targets = await method(user_id=user_id)
                except Exception:
                    continue
                if isinstance(targets, list):
                    raw_targets.extend(target for target in targets if isinstance(target, dict))
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "web").strip().lower())
        slug = re.sub(r"_+", "_", slug).strip("_") or "web"
        raw_targets.append(
            {
                "type": "notes",
                "label": "NOTIZ",
                "collection": f"aria_notes_{slug}",
                "top_k": 5,
            }
        )
        options: list[AriaTurnCollectionOption] = []
        seen: set[str] = set()
        for target in raw_targets:
            name = str(target.get("collection") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            kind = str(target.get("type") or "memory").strip() or "memory"
            label = str(target.get("label") or kind).strip()
            top_k = int(target.get("top_k", 5) or 5)
            options.append(
                AriaTurnCollectionOption(
                    name=name,
                    kind=kind,
                    description=label,
                    allowed_actions=("search",),
                    default_top_k=max(1, min(top_k, 20)),
                )
            )
        return tuple(options)

    async def _build_aria_turn_menu(
        self,
        *,
        user_id: str,
        runtime_recipes: list[dict[str, Any]],
    ):
        return build_aria_turn_menu(
            collections=await self._aria_turn_collection_options(user_id=user_id),
            connection_kinds=self._available_connection_kinds_for_aria_turn(),
            recipes_available=bool(runtime_recipes),
            notes_available=True,
            docs_available=True,
            web_search_available=self.web_search_skill is not None,
            websites_available=bool(self._website_rows()),
            pending_available=True,
            admin_available=True,
            learning_available=True,
            policy_notes=("Side effects require confirmation and policy/guardrail validation.",),
            budget={"max_collections": 6, "default_timeout_ms": 2500},
        )

    def _normalize_explicit_web_research_contract(
        self,
        arbitration: AriaTurnArbitration | None,
        *,
        message: str,
        user_id: str,
        request_id: str,
    ) -> AriaTurnArbitration | None:
        if arbitration is None:
            return None
        if self.web_search_skill is None:
            return arbitration
        if not explicitly_requests_web_research(message):
            return arbitration
        plan = arbitration.plan
        if "web_research" in plan.intents or any(request.surface_id == "web" for request in plan.context_requests):
            return arbitration
        action_names = {str(action or "").strip().lower() for action in plan.actions if str(action or "").strip()}
        rss_read_actions = {"rss_read_feed", "feed_read", "connection_action_rss"}
        rss_read_only_action = bool(action_names) and action_names.issubset(rss_read_actions) and not plan.needs_confirmation
        if (plan.actions or plan.needs_confirmation or plan.answer_mode == "plan_action") and not rss_read_only_action:
            return arbitration
        query = str(message or "").strip()
        request = ContextRequest(
            surface_id="web",
            mode="search",
            query=query,
            depth="shallow",
            limit=8,
            budget={"explicit_web_research_contract": True},
            user_id=user_id,
            turn_id=request_id,
        )
        intents = tuple(dict.fromkeys([intent for intent in plan.intents if intent != "chat"] + ["web_research"]))
        normalized_plan = replace(
            plan,
            intents=intents,
            surfaces=("web",),
            actions=(),
            needs_context=True,
            context_directions=("web",),
            context_depth="shallow" if plan.context_depth == "none" else plan.context_depth,
            queries={**dict(plan.queries or {}), "web": query},
            context_requests=(request,),
            priority=("web",),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="low" if plan.risk == "none" else plan.risk,
            needs_confirmation=False,
            reason=(plan.reason or "explicit_web_research_contract")[:140],
        )
        return replace(arbitration, plan=normalized_plan)

    def _normalize_web_search_action_contract(
        self,
        arbitration: AriaTurnArbitration | None,
        *,
        message: str,
        user_id: str,
        request_id: str,
    ) -> AriaTurnArbitration | None:
        if arbitration is None:
            return None
        if self.web_search_skill is None:
            return arbitration
        plan = arbitration.plan
        action_names = {str(action or "").strip().lower() for action in plan.actions if str(action or "").strip()}
        selected_connection_kinds = {
            kind
            for kind, _ref in self._aria_turn_selected_connections_from_catalog(arbitration)
            if kind
        }
        if "web_search" not in action_names and "searxng" not in selected_connection_kinds:
            return arbitration
        query = str(plan.queries.get("web") or "").strip()
        if not query:
            query = next(
                (
                    str(request.query or "").strip()
                    for request in plan.context_requests
                    if str(request.query or "").strip()
                ),
                "",
            )
        query = query or str(message or "").strip()
        if not query:
            return arbitration
        request = ContextRequest(
            surface_id="web",
            mode="search",
            query=query,
            depth="shallow",
            limit=8,
            budget={
                "web_search_action_normalized": True,
                "previous_actions": list(plan.actions),
                "previous_surfaces": list(plan.surfaces),
            },
            user_id=user_id,
            turn_id=request_id,
        )
        intents = tuple(dict.fromkeys([intent for intent in plan.intents if intent != "chat"] + ["web_research"]))
        normalized_plan = replace(
            plan,
            intents=intents,
            surfaces=("web",),
            actions=(),
            needs_context=True,
            context_directions=("web",),
            context_depth="shallow" if plan.context_depth == "none" else plan.context_depth,
            queries={**dict(plan.queries or {}), "web": query},
            context_requests=(request,),
            priority=("web",),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="low",
            needs_confirmation=False,
            reason=(plan.reason or "web_search_action_contract_normalized")[:140],
        )
        return replace(arbitration, plan=normalized_plan)

    async def _normalize_fresh_web_context_contract(
        self,
        arbitration: AriaTurnArbitration | None,
        *,
        message: str,
        user_id: str,
        request_id: str,
        language: str | None = None,
        source: str = "",
    ) -> AriaTurnArbitration | None:
        if arbitration is None:
            return None
        if self.web_search_skill is None:
            return arbitration
        if explicitly_requests_web_research(message):
            return arbitration
        if not chat_freshness_candidate(message, intents=list(arbitration.plan.intents or ())):
            return arbitration
        if explicitly_requests_local_context(message):
            return arbitration
        plan = arbitration.plan
        action_names = {str(action or "").strip().lower() for action in plan.actions if str(action or "").strip()}
        rss_read_actions = {"rss_read_feed", "feed_read", "connection_action_rss"}
        rss_read_only_action = bool(action_names) and action_names.issubset(rss_read_actions) and not plan.needs_confirmation
        if (plan.actions or plan.needs_confirmation or plan.answer_mode == "plan_action") and not rss_read_only_action:
            return arbitration
        existing_web_requests = tuple(request for request in plan.context_requests if request.surface_id == "web")
        if existing_web_requests and any(
            isinstance((request.budget or {}).get("web_source_plan"), dict)
            and bool((request.budget or {}).get("web_source_plan"))
            for request in existing_web_requests
        ):
            return arbitration
        try:
            freshness_decision = await asyncio.wait_for(
                decide_chat_freshness(
                    message=message,
                    intents=list(plan.intents or ("chat",)),
                    llm_client=self.llm_client,
                    language=language,
                    source=source,
                    user_id=user_id,
                    request_id=request_id,
                ),
                timeout=12.0,
            )
        except asyncio.TimeoutError:
            return arbitration
        if not freshness_decision.needs_fresh_context:
            return arbitration
        query = freshness_decision.query or str(message or "").strip()
        freshness_budget = {
            "freshness_contract": True,
            "freshness_source": freshness_decision.source,
            "freshness_reason": freshness_decision.reason,
            "previous_surfaces": list(plan.surfaces or ()),
            "previous_context_directions": list(plan.context_directions or ()),
        }
        if existing_web_requests:
            requests = tuple(
                replace(
                    request,
                    query=query,
                    budget={
                        **dict(request.budget or {}),
                        **freshness_budget,
                        "previous_query": request.query,
                    },
                    user_id=request.user_id or user_id,
                    turn_id=request.turn_id or request_id,
                )
                if request.surface_id == "web"
                else request
                for request in plan.context_requests
            )
        else:
            requests = (
                ContextRequest(
                    surface_id="web",
                    mode="search",
                    query=query,
                    depth="shallow",
                    limit=8,
                    budget=freshness_budget,
                    user_id=user_id,
                    turn_id=request_id,
                ),
            )
        normalized_plan = replace(
            plan,
            intents=tuple(dict.fromkeys([intent for intent in plan.intents if intent not in {"chat", "local_retrieval"}] + ["web_research"])),
            surfaces=("web",),
            actions=(),
            needs_context=True,
            context_directions=("web",),
            context_depth="shallow" if plan.context_depth == "none" else plan.context_depth,
            queries={**dict(plan.queries or {}), "web": query},
            context_requests=requests,
            priority=("web",),
            answer_mode="direct_answer",
            contract_mode="answer",
            evidence_policy="source_bound",
            risk="low" if plan.risk == "none" else plan.risk,
            needs_confirmation=False,
            reason=(freshness_decision.reason or "freshness_web_context_contract")[:140],
        )
        return replace(arbitration, plan=normalized_plan)

    @staticmethod
    def _aria_turn_is_notes_only_context(arbitration: AriaTurnArbitration | None) -> bool:
        if arbitration is None:
            return False
        plan = arbitration.plan
        if not plan.needs_context:
            return False
        directions = {str(item or "").strip().lower() for item in plan.context_directions if str(item or "").strip()}
        collections = [str(item or "").strip().lower() for item in plan.collections if str(item or "").strip()]
        request_surfaces = {request.surface_id for request in plan.context_requests}
        has_notes = "notes" in directions or "notes" in request_surfaces or any("notes" in collection for collection in collections)
        has_non_notes_direction = bool(directions - {"notes"})
        has_non_notes_collection = any("notes" not in collection for collection in collections)
        has_non_notes_request = bool(request_surfaces - {"notes"})
        return has_notes and not has_non_notes_direction and not has_non_notes_collection and not has_non_notes_request

    @staticmethod
    def _merge_aria_turn_intents(base_intents: list[str], arbitration: AriaTurnArbitration | None) -> list[str]:
        merged = list(base_intents or ["chat"])
        if arbitration is None:
            return merged
        plan = arbitration.plan
        if "context_inventory" in plan.intents and "context_inventory" not in merged:
            merged.append("context_inventory")
        local_retrieval_surfaces = {
            request.surface_id
            for request in plan.context_requests
            if request.mode != "inventory" or request.surface_id in {"memory", "notes", "docs"}
        }
        selected_local_context = bool(
            "local_retrieval" in plan.intents
            or set(plan.context_directions) & {"memory", "learning", "notes", "docs", "sessions"}
            or plan.collections
            or local_retrieval_surfaces & {"memory", "notes", "docs"}
        )
        if selected_local_context:
            has_memory_surface = bool(local_retrieval_surfaces & {"memory", "notes", "docs"})
            if plan.context_requests and not has_memory_surface and not plan.collections and not set(plan.context_directions) & {"memory", "learning", "notes", "docs", "sessions"}:
                pass
            elif AgenticContextRuntimeMixin._aria_turn_is_notes_only_context(arbitration):
                if "notes_search" not in merged:
                    merged.append("notes_search")
            elif "memory_recall" not in merged:
                merged.append("memory_recall")
        selected_web_context = bool(
            "web_research" in plan.intents
            or "web" in {str(direction or "").strip().lower() for direction in plan.context_directions}
            or any(request.surface_id == "web" and request.mode in {"search", "answer"} for request in plan.context_requests)
        )
        if selected_web_context and "web_search" not in merged:
            merged.append("web_search")
        if "learning_feedback" in plan.intents and "memory_recall" not in merged:
            merged.append("memory_recall")
        keep_chat_intent = any(
            bool((request.budget or {}).get("keep_chat_intent"))
            for request in plan.context_requests
        )
        if "chat" in merged and len(merged) > 1 and "local_retrieval" not in plan.intents and not keep_chat_intent:
            return [intent for intent in merged if intent != "chat"] or ["chat"]
        return merged or ["chat"]

    @staticmethod
    def _aria_turn_query_overrides(arbitration: AriaTurnArbitration | None) -> dict[str, str]:
        if arbitration is None:
            return {}
        plan = arbitration.plan
        request_queries = {
            request.surface_id: str(request.query or "").strip()
            for request in plan.context_requests
            if request.surface_id in {"memory", "notes", "docs", "web"} and str(request.query or "").strip()
        }
        collection_queries = [str(plan.queries.get(collection) or "").strip() for collection in plan.collections]
        clean_queries = [query for query in collection_queries if query]
        clean_queries.extend(query for query in request_queries.values() if query not in clean_queries)
        overrides: dict[str, str] = {}
        if clean_queries:
            merged_query = " ".join(dict.fromkeys(clean_queries))[:900]
            if "local_retrieval" in plan.intents:
                overrides["memory_recall"] = request_queries.get("memory") or request_queries.get("docs") or merged_query
                if any("notes" in collection.lower() for collection in plan.collections) or any(request.surface_id == "notes" for request in plan.context_requests) or "notes" in {
                    str(item or "").strip().lower() for item in plan.priority
                }:
                    overrides["notes_search"] = request_queries.get("notes") or merged_query
            if "web_research" in plan.intents:
                overrides["web_search"] = request_queries.get("web") or merged_query
        return overrides

    def _aria_turn_slug_user_id(self, user_id: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "web").strip().lower())
        return re.sub(r"_+", "_", slug).strip("_") or "web"

    def _aria_turn_local_family_collection(self, ref: str, *, user_id: str) -> str:
        slug = self._aria_turn_slug_user_id(user_id)
        memory_cfg = getattr(getattr(self.settings, "memory", None), "collections", None)
        facts_prefix = str(getattr(getattr(memory_cfg, "facts", None), "prefix", "") or "aria_facts")
        preferences_prefix = str(getattr(getattr(memory_cfg, "preferences", None), "prefix", "") or "aria_preferences")
        knowledge_prefix = str(getattr(getattr(memory_cfg, "knowledge", None), "prefix", "") or "aria_knowledge")
        sessions_prefix = str(getattr(getattr(memory_cfg, "sessions", None), "prefix", "") or "aria_sessions")
        mapping = {
            "facts": f"{facts_prefix}_{slug}",
            "preferences": f"{preferences_prefix}_{slug}",
            "knowledge": f"{knowledge_prefix}_{slug}",
            "context_mem": f"aria_context-mem_{slug}",
            "sessions": f"{sessions_prefix}_{slug}",
            "reflections": f"aria_learning_{slug}",
            "events": f"aria_learning_events_{slug}",
            "candidates": f"aria_learning_candidates_{slug}",
            "active_hints": f"aria_learning_active_hints_{slug}",
            "evals": f"aria_learning_evals_{slug}",
            "user_notes": f"aria_notes_{slug}",
        }
        return mapping.get(str(ref or "").strip(), "")

    @staticmethod
    def _aria_turn_docs_request_text(plan: AriaTurnPlan) -> str:
        parts: list[str] = []
        for value in list(plan.queries.values()):
            clean = str(value or "").strip()
            if clean:
                parts.append(clean)
        for request in plan.context_requests:
            if request.surface_id != "docs":
                continue
            clean = str(request.query or "").strip()
            if clean:
                parts.append(clean)
        return " ".join(dict.fromkeys(parts))

    @staticmethod
    def _aria_turn_docs_query_needs_corpus_scan(query: str) -> bool:
        lower = str(query or "").strip().lower()
        if not lower:
            return False
        lower_ascii = lower.translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )
        corpus_scope = any(
            marker in lower_ascii
            for marker in (
                "eines der",
                "einer der",
                "einem der",
                "allen dokument",
                "alle dokument",
                "any of",
                "available",
                "vorhanden",
                "haben",
            )
        )
        substance_scope = any(
            marker in lower_ascii
            for marker in (
                "bestandteil",
                "inhaltsstoff",
                "zusammensetzung",
                "wirkstoff",
                "component",
                "ingredient",
                "contains",
                "enthalten",
                "kommt",
            )
        )
        docs_scope = any(
            marker in lower_ascii
            for marker in (
                "beipackzettel",
                "dokument",
                "document",
                "pdf",
                "medikament",
            )
        )
        return docs_scope and corpus_scope and substance_scope

    @staticmethod
    def _aria_turn_docs_query_is_broad_inventory(query: str) -> bool:
        lower = str(query or "").strip().lower()
        if not lower:
            return False
        lower_ascii = lower.translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )
        inventory_scope = any(
            marker in lower_ascii
            for marker in ("liste", "auflisten", "welche", f"was f{chr(117)}er", f"{chr(117)}ebersicht", "inventory")
        )
        available_scope = any(
            marker in lower_ascii
            for marker in (
                "haben",
                "vorhanden",
                "verfuegbar",
                "available",
                "abgelegt",
                "gespeichert",
                "speicher",
                "store",
            )
        )
        docs_scope = any(marker in lower_ascii for marker in ("beipackzettel", "dokument", "document", "pdf", "medikament"))
        return inventory_scope and available_scope and docs_scope

    @staticmethod
    def _aria_turn_docs_query_is_named_document_family_inventory(query: str) -> bool:
        lower = str(query or "").strip().lower()
        lower_ascii = lower.translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )
        return any(marker in lower_ascii for marker in ("beipackzettel", "medikament"))

    def _aria_turn_context_overrides(
        self,
        arbitration: AriaTurnArbitration | None,
        *,
        user_id: str = "web",
        message: str | None = None,
    ) -> dict[str, Any]:
        if arbitration is None:
            return {}
        plan = arbitration.plan
        web_source_plan: dict[str, Any] = {}
        for request in plan.context_requests:
            if request.surface_id != "web":
                continue
            budget = dict(request.budget or {})
            candidate = budget.get("web_source_plan")
            if isinstance(candidate, dict) and candidate:
                web_source_plan = candidate
                break
        request_surfaces = {request.surface_id for request in plan.context_requests}
        priority_surfaces = {
            str(item or "").strip().split("|", 2)[1]
            for item in plan.priority
            if str(item or "").strip().startswith("local|") and len(str(item or "").strip().split("|", 2)) == 3
        }
        has_local_retrieval_contract = bool(
            "local_retrieval" in plan.intents
            or set(plan.context_directions) & {"memory", "learning", "docs", "sessions", "notes"}
            or request_surfaces & {"memory", "learning", "docs", "sessions", "notes"}
            or priority_surfaces & {"memory", "docs", "notes"}
        )
        if not has_local_retrieval_contract:
            return {"web_source_plan": web_source_plan} if web_source_plan else {}
        selected = [str(collection or "").strip() for collection in plan.collections if str(collection or "").strip()]
        memory_like: list[str] = []
        include_documents = "docs" in plan.context_directions or "docs" in request_surfaces
        docs_only = bool("docs" in plan.context_directions or "docs" in request_surfaces)
        document_corpus_scope = any(str(item or "").strip() == "local|docs|documents" for item in plan.priority)
        docs_request_text = " ".join(
            part for part in (self._aria_turn_docs_request_text(plan), str(message or "").strip()) if part
        )
        docs_corpus_question = self._aria_turn_docs_query_needs_corpus_scan(docs_request_text)
        broad_docs_inventory = self._aria_turn_docs_query_is_broad_inventory(docs_request_text) and (
            document_corpus_scope or self._aria_turn_docs_query_is_named_document_family_inventory(docs_request_text)
        )
        include_sessions = "sessions" in plan.context_directions or "sessions" in request_surfaces
        bound_local_collections: list[str] = []
        document_ids: list[str] = []
        document_names: list[str] = []
        document_target_collections: list[str] = []
        for request in plan.context_requests:
            budget = dict(request.budget or {})
            entity_type = str(budget.get("entity_type", "") or "").strip()
            kind = str(budget.get("kind", "") or "").strip()
            if request.surface_id == "docs" and entity_type == "local_context" and kind == "document_meta":
                for value, target in (
                    (budget.get("document_id") or budget.get("ref"), document_ids),
                    (budget.get("document_name"), document_names),
                    (budget.get("target_collection"), document_target_collections),
                ):
                    clean = str(value or "").strip()
                    if clean and clean not in target:
                        target.append(clean)
                include_documents = True
            if entity_type != "local_context":
                continue
            ref = str(budget.get("ref", "") or "").strip()
            if not ref:
                catalog_id = str(budget.get("catalog_id", "") or "").strip()
                parts = catalog_id.split("|", 2)
                if len(parts) == 3 and parts[0] == "local" and parts[1] in {"memory", "notes", "docs"}:
                    ref = parts[2].strip()
            if request.surface_id == "docs" or kind == "docs_family":
                include_documents = True
                continue
            collection = self._aria_turn_local_family_collection(ref, user_id=user_id)
            if collection and request.surface_id == "memory":
                bound_local_collections.append(collection)
        for collection in selected:
            lower = collection.lower()
            if "notes" in lower:
                continue
            if "session" in lower and not include_sessions:
                continue
            if "docs" in lower or "document" in lower:
                include_documents = True
            memory_like.append(collection)
        for surface in priority_surfaces:
            if surface == "memory":
                for value in plan.priority:
                    parts = str(value or "").strip().split("|", 2)
                    if len(parts) != 3 or parts[0] != "local" or parts[1] != "memory":
                        continue
                    collection = self._aria_turn_local_family_collection(parts[2], user_id=user_id)
                    if collection and collection not in memory_like:
                        memory_like.append(collection)
        local_memory_directions = {"memory", "learning", "docs", "sessions"}
        has_memory_direction = bool(set(plan.context_directions) & local_memory_directions or request_surfaces & local_memory_directions)
        if bound_local_collections:
            memory_like = list(dict.fromkeys([*bound_local_collections, *memory_like]))
        if selected and not memory_like and not has_memory_direction:
            return {"memory_recall_enabled": False}
        overrides: dict[str, Any] = {
            "memory_recall_enabled": bool(memory_like or has_memory_direction),
            "include_documents": include_documents,
        }
        if docs_only:
            overrides["docs_only"] = True
            if plan.context_depth == "deep" or document_corpus_scope or docs_corpus_question:
                overrides["document_corpus_scan"] = True
            if document_target_collections:
                overrides["document_target_collections"] = document_target_collections
        if (
            len(document_ids) >= 2
            or broad_docs_inventory
            or any(request.mode == "inventory" and request.surface_id == "docs" for request in plan.context_requests)
        ):
            overrides["document_inventory"] = True
            overrides["document_ids"] = [] if broad_docs_inventory else document_ids
            overrides["document_names"] = [] if broad_docs_inventory else document_names
            overrides["document_target_collections"] = document_target_collections
            overrides["memory_top_k"] = min(12, max(5, len(document_ids) or len(document_names) or 5))
        if memory_like:
            overrides["memory_target_collections"] = memory_like
            overrides["memory_top_k"] = max(int(overrides.get("memory_top_k") or 0), min(5, max(2, len(memory_like) * 2)))
        return overrides

    @staticmethod
    def _aria_turn_allowed_context_skill_names(arbitration: AriaTurnArbitration | None) -> set[str]:
        if arbitration is None or not arbitration.plan.needs_context:
            return set()
        plan = arbitration.plan
        allowed: set[str] = set()
        requests = tuple(plan.context_requests)
        for request in requests:
            if request.mode == "inventory":
                if request.surface_id in {"memory", "notes", "docs"} and str(request.query or "").strip():
                    if request.surface_id == "notes":
                        allowed.add("notes_search")
                    else:
                        allowed.add("memory_recall")
                    continue
                allowed.add("context_inventory")
                continue
            if request.surface_id == "notes":
                allowed.add("notes_search")
            elif request.surface_id in {"memory", "docs"}:
                allowed.add("memory_recall")
            elif request.surface_id == "web":
                allowed.add("web_search")
        if not requests:
            directions = {str(item or "").strip().lower() for item in plan.context_directions}
            if "notes" in directions:
                allowed.add("notes_search")
            if directions & {"memory", "learning", "docs", "sessions"}:
                allowed.add("memory_recall")
            if "web" in directions:
                allowed.add("web_search")
            if "connections" in directions and "context_inventory" in plan.intents:
                allowed.add("context_inventory")
        return allowed

    def _aria_turn_filter_skill_results_for_selected_context(
        self,
        *,
        arbitration: AriaTurnArbitration | None,
        skill_results: list[SkillResult],
    ) -> tuple[list[SkillResult], list[str]]:
        allowed = self._aria_turn_allowed_context_skill_names(arbitration)
        if not allowed:
            return skill_results, []
        kept: list[SkillResult] = []
        filtered: list[str] = []
        for result in skill_results:
            name = str(result.skill_name or "").strip()
            if name in allowed:
                kept.append(result)
            else:
                filtered.append(name or "-")
        if not filtered:
            return kept, []
        return kept, [
            "Routing Debug: context_isolation "
            f"allowed={','.join(sorted(allowed)) or '-'} filtered={','.join(dict.fromkeys(filtered)) or '-'} "
            "reason=turn_plan_source_contract"
        ]

    @staticmethod
    def _aria_turn_context_ledger_lines(
        *,
        arbitration: AriaTurnArbitration | None,
        query_overrides: dict[str, str],
        context_overrides: dict[str, Any],
        skill_results: list[SkillResult],
    ) -> list[str]:
        if arbitration is None:
            return []
        plan = arbitration.plan
        selected_collections = ",".join(plan.collections) or "-"
        selected_directions = ",".join(plan.context_directions) or "-"
        selected_actions = ",".join(plan.actions) or "-"
        selected_requests = ",".join(
            f"{request.surface_id}:{request.mode}" for request in plan.context_requests
        ) or "-"
        loaded_skills = ",".join(dict.fromkeys(str(result.skill_name or "").strip() for result in skill_results if str(result.skill_name or "").strip())) or "-"
        context_sources = 0
        detail_count = 0
        embedding_tokens = 0
        for result in skill_results:
            meta = result.metadata or {}
            sources = meta.get("sources")
            context_sources += context_source_count(sources)
            detail_lines = meta.get("detail_lines")
            if isinstance(detail_lines, list):
                detail_count += len([line for line in detail_lines if str(line or "").strip()])
            usage = meta.get("embedding_usage")
            if isinstance(usage, dict):
                embedding_tokens += int(usage.get("total_tokens", 0) or 0)
        query_keys = ",".join(sorted(query_overrides)) or "-"
        memory_targets = ",".join(str(item or "").strip() for item in list(context_overrides.get("memory_target_collections") or []) if str(item or "").strip()) or "-"
        arbiter_prompt_tokens = int(arbitration.usage.get("prompt_tokens", 0) or 0)
        arbiter_completion_tokens = int(arbitration.usage.get("completion_tokens", 0) or 0)
        arbiter_total_tokens = int(arbitration.usage.get("total_tokens", 0) or 0)
        routing_payload_bytes = int(arbitration.diagnostics.get("payload_bytes", 0) or 0)
        routing_system_chars = int(arbitration.diagnostics.get("system_chars", 0) or 0)
        routing_payload_keys = int(arbitration.diagnostics.get("payload_keys", 0) or 0)
        return [
            "Routing Debug: context_ledger "
            f"phase=selection needs_context={str(plan.needs_context).lower()} directions={selected_directions} "
            f"depth={plan.context_depth} collections={selected_collections} actions={selected_actions} "
            f"requests={selected_requests} query_overrides={query_keys} memory_targets={memory_targets} "
            f"memory_enabled={str(bool(context_overrides.get('memory_recall_enabled', True))).lower()} "
            f"include_documents={str(bool(context_overrides.get('include_documents', True))).lower()} "
            f"document_corpus_scan={str(bool(context_overrides.get('document_corpus_scan', False))).lower()}",
            "Routing Debug: context_ledger "
            f"phase=loaded skills={loaded_skills} sources={context_sources} detail_lines={detail_count} "
            f"embedding_tokens={embedding_tokens} arbiter_tokens={arbiter_total_tokens} "
            f"arbiter_prompt_tokens={arbiter_prompt_tokens} arbiter_completion_tokens={arbiter_completion_tokens} "
            f"routing_payload_bytes={routing_payload_bytes} routing_system_chars={routing_system_chars} "
            f"routing_payload_keys={routing_payload_keys}",
        ]

    @staticmethod
    def _aria_turn_context_packet_lines(
        *,
        arbitration: AriaTurnArbitration | None,
        skill_results: list[SkillResult],
    ) -> list[str]:
        if arbitration is None:
            return []
        plan = arbitration.plan
        result_by_surface: dict[str, list[SkillResult]] = {}
        for result in skill_results:
            name = str(result.skill_name or "").strip()
            surfaces: set[str] = set()
            if name == "notes_search":
                surfaces.add("notes")
            elif name == "web_search":
                surfaces.add("web")
            elif name == "memory_recall":
                if any(request.surface_id == "docs" for request in plan.context_requests):
                    surfaces.add("docs")
                if any(request.surface_id in {"memory", "learning", "sessions"} for request in plan.context_requests):
                    surfaces.add("memory")
                if not surfaces:
                    surfaces.add("memory")
            elif name == "context_inventory":
                for source in list((result.metadata or {}).get("sources") or []):
                    if isinstance(source, dict):
                        surface = str(source.get("surface", "") or "").strip()
                        if surface:
                            surfaces.add(surface)
                if not surfaces:
                    surfaces.update(request.surface_id for request in plan.context_requests if request.mode == "inventory")
            for surface in surfaces:
                result_by_surface.setdefault(surface, []).append(result)

        request_labels: list[str] = []
        loaded_labels: list[str] = []
        empty_labels: list[str] = []
        missing_labels: list[str] = []
        blocked_labels: list[str] = []
        for request in plan.context_requests:
            surface = request.surface_id
            if not surface:
                continue
            request_labels.append(f"{surface}:{request.mode}")
            results = result_by_surface.get(surface, [])
            if not results:
                missing_labels.append(surface)
                continue
            source_count = 0
            has_content = False
            had_failure = False
            for result in results:
                if not result.success:
                    had_failure = True
                    continue
                meta = result.metadata or {}
                sources = meta.get("sources")
                source_count += context_source_count(sources)
                if str(result.content or "").strip():
                    has_content = True
            if source_count or has_content:
                loaded_labels.append(f"{surface}:{source_count}")
            elif had_failure:
                blocked_labels.append(surface)
            else:
                empty_labels.append(surface)

        if not request_labels and plan.needs_context:
            for surface in plan.context_directions:
                clean = str(surface or "").strip()
                if clean:
                    request_labels.append(f"{clean}:implicit")
                    if clean not in result_by_surface:
                        missing_labels.append(clean)

        freshness = any(
            bool(dict(request.budget or {}).get("freshness_contract"))
            for request in plan.context_requests
        )
        return [
            "Routing Debug: context_packet "
            f"turn_plan_source={arbitration.source} requests={','.join(request_labels) or '-'} "
            f"loaded={','.join(loaded_labels) or '-'} empty={','.join(dict.fromkeys(empty_labels)) or '-'} "
            f"missing={','.join(dict.fromkeys(missing_labels)) or '-'} blocked={','.join(dict.fromkeys(blocked_labels)) or '-'} "
            f"evidence_policy={plan.evidence_policy or '-'} contract_mode={plan.contract_mode or '-'} "
            f"answer_mode={plan.answer_mode} freshness_contract={str(freshness).lower()}"
        ]

    @staticmethod
    def _aria_turn_answer_contract_line(
        *,
        arbitration: AriaTurnArbitration,
        kind: str,
        status: str,
        source_count: int,
    ) -> str:
        plan = arbitration.plan
        return (
            "Routing Debug: answer_contract "
            f"kind={kind or '-'} status={status or '-'} mode={plan.contract_mode or '-'} "
            f"evidence_policy={plan.evidence_policy or '-'} answer_mode={plan.answer_mode} "
            f"source_count={max(0, int(source_count or 0))} source_bound={str((plan.evidence_policy or '') == 'source_bound').lower()}"
        )

    @staticmethod
    def _aria_turn_has_loaded_local_context(skill_results: list[SkillResult]) -> bool:
        for result in skill_results:
            if not result.success:
                continue
            meta = result.metadata or {}
            sources = meta.get("sources")
            if isinstance(sources, list) and sources:
                return True
            content = str(result.content or "").strip()
            if content and "Keine passende Erinnerung gefunden" not in content:
                return True
        return False

    def _aria_turn_empty_local_context_text(
        self,
        arbitration: AriaTurnArbitration,
        *,
        language: str | None = None,
    ) -> str:
        directions = {str(item or "").strip().lower() for item in arbitration.plan.context_directions}
        collections = {str(item or "").strip().lower() for item in arbitration.plan.collections}
        wants_notes = "notes" in directions or any("notes" in collection for collection in collections)
        wants_docs = "docs" in directions or any("docs" in collection or "document" in collection for collection in collections)
        wants_memory = bool(directions & {"memory", "learning", "sessions"}) or any(
            any(marker in collection for marker in ("facts", "learning", "sessions", "preferences"))
            for collection in collections
        )
        if str(language or "de").lower().startswith("en"):
            if wants_notes and not wants_docs and not wants_memory:
                return self._pipeline_text(language, "local_context_empty.notes", "I searched your notes for this, but did not find a matching entry.")
            if wants_docs and not wants_notes and not wants_memory:
                return self._pipeline_text(language, "local_context_empty.docs", "I searched your documents for this, but did not find a matching entry.")
            if wants_memory and not wants_notes and not wants_docs:
                return self._pipeline_text(language, "local_context_empty.memory", "I searched the selected memory and learning context for this, but did not find a matching entry.")
            return self._pipeline_text(language, "local_context_empty.sources", "I searched the selected local sources for this, but did not find a matching entry.")
        if wants_notes and not wants_docs and not wants_memory:
            return self._pipeline_text(language, "local_context_empty.notes", "I searched your notes for this, but did not find a matching entry.")
        if wants_docs and not wants_notes and not wants_memory:
            return self._pipeline_text(language, "local_context_empty.docs", "I searched your documents for this, but did not find a matching entry.")
        if wants_memory and not wants_notes and not wants_docs:
            return self._pipeline_text(language, "local_context_empty.memory", "I searched the selected memory and learning context for this, but did not find a matching entry.")
        return self._pipeline_text(language, "local_context_empty.sources", "I searched the selected local sources for this, but did not find a matching entry.")

    @staticmethod
    def _aria_turn_context_request_query(arbitration: AriaTurnArbitration, surface_id: str) -> str:
        for request in arbitration.plan.context_requests:
            if request.surface_id == surface_id and str(request.query or "").strip():
                return str(request.query or "").strip()
        return str(arbitration.plan.queries.get(surface_id) or "").strip()

    @staticmethod
    def _aria_turn_evidence_terms(query: str, *, ignored_terms: set[str] | None = None) -> list[str]:
        return evidence_terms(query, ignored_terms=ignored_terms)

    @staticmethod
    def _aria_turn_common_request_terms() -> set[str]:
        return set(common_request_terms())

    @staticmethod
    def _aria_turn_inventory_soft_scope_terms() -> set[str]:
        return set(inventory_soft_scope_terms())

    def _aria_turn_request_scope_terms(
        self,
        surface_id: str,
        mode: str = "",
        *,
        include_soft_scope: bool = True,
    ) -> set[str]:
        connection_kinds = tuple(
            (kind, connection_kind_label(kind))
            for kind in self._available_connection_kinds_for_aria_turn()
        ) if surface_id == "connections" else ()
        return request_scope_terms(
            surface_id,
            mode,
            connection_kinds=connection_kinds,
            include_soft_scope=include_soft_scope,
        )

    def _aria_turn_topic_terms_for_request(self, query: str, request: ContextRequest) -> tuple[list[str], set[str]]:
        ignored = self._aria_turn_request_scope_terms(request.surface_id, request.mode, include_soft_scope=True)
        terms = self._aria_turn_evidence_terms(query, ignored_terms=ignored)
        if terms:
            return terms, ignored
        fallback_ignored = self._aria_turn_request_scope_terms(request.surface_id, request.mode, include_soft_scope=False)
        return self._aria_turn_evidence_terms(query, ignored_terms=fallback_ignored), fallback_ignored

    @staticmethod
    def _aria_turn_text_matches_evidence(query: str, text: str, *, ignored_terms: set[str] | None = None, require_all: bool = False) -> bool:
        return text_matches_evidence(query, text, ignored_terms=ignored_terms, require_all=require_all)

    def _aria_turn_inventory_ignored_terms(self, surface_id: str, request: ContextRequest, *, include_scope_terms: bool = True) -> set[str]:
        return self._aria_turn_request_scope_terms(surface_id, request.mode, include_soft_scope=include_scope_terms)

    @staticmethod
    def _aria_turn_inventory_matches(query: str, text: str) -> bool:
        return inventory_matches(query, text)

    @staticmethod
    def _aria_turn_inventory_query_terms(query: str) -> list[str]:
        return inventory_query_terms(query)

    def _aria_turn_inventory_evidence_hits(
        self,
        hits: list[dict[str, Any]],
        *,
        request: ContextRequest,
        query: str,
        limit: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        kept = list(hits[: max(1, int(limit or 1))])
        return kept, [
            "Routing Debug: inventory_candidate_context "
            f"surface={request.surface_id} kept={len(kept)} candidates={len(hits)} "
            "deterministic_filter=disabled"
        ]

    @staticmethod
    def _aria_turn_query_requests_network_address(query: str) -> bool:
        lower = str(query or "").strip().lower()
        return bool(
            re.search(
                r"\b(?:ip|ips|ip-adresse|ip-adressen|adresse|adressen|address|addresses|host|hosts|hostname|hostnames)\b",
                lower,
            )
        )

    def _aria_turn_format_inventory_metadata(self, surface_id: str, metadata: dict[str, Any], query: str, *, limit: int = 50) -> tuple[str, list[dict[str, Any]]]:
        if not metadata:
            return "No inventory metadata is available for the selected surface.", []
        return "Inventory metadata exists, but no indexed or contract-bound inventory context was selected.", []

    async def _aria_turn_inventory_index_result(self, request: ContextRequest, query: str) -> SkillResult | None:
        return await self._agentic_context_surface_loader()._load_inventory_index_result(request, query)

    async def _aria_turn_inventory_result(self, arbitration: AriaTurnArbitration, request: ContextRequest) -> SkillResult | None:
        return await self._agentic_context_surface_loader()._load_inventory_request(arbitration, request)

    async def _aria_turn_inventory_skill_results(self, arbitration: AriaTurnArbitration | None) -> list[SkillResult]:
        return await self._agentic_context_surface_loader().load_inventory(arbitration)

    @staticmethod
    def _aria_turn_result_has_sources(result: SkillResult) -> bool:
        meta = result.metadata or {}
        sources = meta.get("sources")
        return isinstance(sources, list) and bool(sources)

    @staticmethod
    def _aria_turn_memory_exists_request(arbitration: AriaTurnArbitration | None) -> bool:
        if arbitration is None:
            return False
        plan = arbitration.plan
        if plan.actions or plan.needs_confirmation or "web_research" in plan.intents:
            return False
        for request in plan.context_requests:
            if request.surface_id == "memory" and request.mode in {"exists", "inventory"} and str(request.query or "").strip():
                return True
        return False

    def _aria_turn_memory_exists_evidence_query(self, arbitration: AriaTurnArbitration) -> str:
        for request in arbitration.plan.context_requests:
            if request.surface_id == "memory" and request.mode in {"exists", "inventory"} and str(request.query or "").strip():
                return str(request.query or "").strip()
        for query in arbitration.plan.queries.values():
            if str(query or "").strip():
                return str(query or "").strip()
        return ""

    def _aria_turn_single_local_search_request(self, arbitration: AriaTurnArbitration) -> ContextRequest | None:
        plan = arbitration.plan
        if plan.actions or plan.needs_confirmation or "web_research" in plan.intents:
            return None
        requests = [
            request
            for request in plan.context_requests
            if request.surface_id in {"memory", "docs"}
            and request.mode in {"search", "answer", "summarize"}
            and str(request.query or "").strip()
        ]
        if len(requests) != 1:
            return None
        directions = {str(item or "").strip().lower() for item in plan.context_directions if str(item or "").strip()}
        if directions and not directions <= {"memory", "learning", "docs", "sessions"}:
            return None
        if plan.collections:
            collection_text = " ".join(str(collection or "").lower() for collection in plan.collections)
            if requests[0].surface_id == "docs" and "doc" not in collection_text:
                return None
        return requests[0]

    def _aria_turn_local_search_has_evidence(self, request: ContextRequest, result: SkillResult) -> bool:
        ignored_terms = {request.surface_id, str(request.mode or "").strip().lower(), "search", "suche", "find", "lookup"}
        query = str(request.query or "").strip()
        content = str(result.content or "").strip()
        meta = result.metadata or {}
        sources = [dict(item) for item in list(meta.get("sources", []) or []) if isinstance(item, dict)]
        evidence_reason = ""
        doc_sources = [
            source
            for source in sources
            if str(source.get("type", "") or "").strip().lower() == "document"
            or str(source.get("collection", "") or "").strip().lower().startswith("aria_docs_")
        ]
        if bool(meta.get("document_inventory", False)) and doc_sources:
            matched_sources, _terms, _rejected = document_inventory_sources_for_query(doc_sources, query)
            matched = bool(matched_sources)
            if not matched:
                evidence_reason = "document_inventory_no_matches"
        elif request.surface_id == "docs":
            if bool(meta.get("document_inventory", False)):
                matched_sources, _terms, _rejected = document_inventory_sources_for_query(doc_sources, query)
                matched = bool(matched_sources)
            else:
                scan_match_chunks = document_corpus_scan_match_chunks(meta)
                if scan_match_chunks == 0:
                    matched = False
                    evidence_reason = "document_corpus_scan_no_matches"
                else:
                    doc_text = "\n".join(
                        [
                            *[
                                str(source.get("text", "") or source.get("detail", "") or source.get("source", "") or "")
                                for source in doc_sources
                            ],
                            content,
                        ]
                    )
                    matched = bool(doc_sources) and self._aria_turn_text_matches_evidence(
                        query,
                        doc_text,
                        ignored_terms=ignored_terms,
                    )
        else:
            matched = self._aria_turn_text_matches_evidence(query, content, ignored_terms=ignored_terms)
        lines = list(meta.get("detail_lines", []) or [])
        lines.append(
            "Routing Debug: evidence_filter "
            f"surface={request.surface_id} mode={request.mode} matched={str(matched).lower()} "
            f"terms={','.join(self._aria_turn_evidence_terms(query, ignored_terms=ignored_terms)) or '-'}"
            f"{(' reason=' + evidence_reason) if evidence_reason else ''}"
        )
        meta["detail_lines"] = lines
        result.metadata = meta
        return matched

    def _aria_turn_notes_evidence_query(self, arbitration: AriaTurnArbitration) -> str:
        for request in arbitration.plan.context_requests:
            if request.surface_id == "notes" and str(request.query or "").strip():
                return str(request.query or "").strip()
        for key in ("notes",):
            query = str(arbitration.plan.queries.get(key) or "").strip()
            if query:
                return query
        for query in arbitration.plan.queries.values():
            if str(query or "").strip():
                return str(query or "").strip()
        return ""

    def _aria_turn_notes_only_has_evidence(self, arbitration: AriaTurnArbitration, result: SkillResult) -> bool:
        query = self._aria_turn_notes_evidence_query(arbitration)
        content = str(result.content or "").strip()
        request = ContextRequest(surface_id="notes", mode="search", query=query)
        terms, ignored_terms = self._aria_turn_topic_terms_for_request(query, request)
        if terms:
            haystack = normalized_evidence_text(content)
            matched = any(term in haystack for term in terms)
        else:
            matched = bool(content)
        meta = result.metadata or {}
        lines = list(meta.get("detail_lines", []) or [])
        lines.append(
            "Routing Debug: evidence_filter "
            f"surface=notes mode=search matched={str(matched).lower()} "
            f"terms={','.join(terms) or '-'}"
        )
        meta["detail_lines"] = lines
        result.metadata = meta
        return matched

    def _aria_turn_memory_exists_has_evidence(self, arbitration: AriaTurnArbitration, result: SkillResult) -> bool:
        query = self._aria_turn_memory_exists_evidence_query(arbitration)
        content = str(result.content or "").strip()
        request = next(
            (
                item
                for item in arbitration.plan.context_requests
                if item.surface_id == "memory" and item.mode in {"exists", "inventory"}
            ),
            ContextRequest(surface_id="memory", mode="exists", query=query),
        )
        topic_terms, ignored_terms = self._aria_turn_topic_terms_for_request(query, request)
        matched = self._aria_turn_text_matches_evidence(query, content, ignored_terms=ignored_terms, require_all=True)
        meta = result.metadata or {}
        lines = list(meta.get("detail_lines", []) or [])
        lines.append(
            "Routing Debug: evidence_filter "
            f"surface=memory mode=exists matched={str(matched).lower()} "
            f"terms={','.join(topic_terms) or '-'}"
        )
        meta["detail_lines"] = lines
        result.metadata = meta
        return matched

    @staticmethod
    def _aria_turn_skill_result_sources(result: SkillResult | None) -> list[dict[str, Any]]:
        if result is None:
            return []
        sources = dict(result.metadata or {}).get("sources")
        if not isinstance(sources, list):
            return []
        return [dict(item) for item in sources if isinstance(item, dict)]

    @staticmethod
    def _aria_turn_merge_inventory_results(results: list[SkillResult]) -> SkillResult | None:
        inventory_results = [result for result in results if result.skill_name == "context_inventory" and result.success]
        if not inventory_results:
            return None
        contents: list[str] = []
        sources: list[dict[str, Any]] = []
        detail_lines: list[str] = []
        bound_refs: list[str] = []
        has_unbound_inventory = False
        semantic_scope_authority = "explicit_config"
        semantic_scope_rejected_refs: list[str] = []
        evidence_bundles: list[dict[str, Any]] = []
        source_keys: set[tuple[str, str, tuple[str, ...]]] = set()
        for result in inventory_results:
            content = str(result.content or "").strip()
            if content and content not in contents:
                contents.append(content)
            meta = dict(result.metadata or {})
            if str(meta.get("scope_contract", "") or "").strip() != "bound" or bool(meta.get("requires_llm_narrowing")):
                has_unbound_inventory = True
            semantic_authority = str(meta.get("semantic_scope_authority", "") or "").strip() or "explicit_config"
            if semantic_authority == "candidate":
                semantic_scope_authority = "candidate"
            elif semantic_authority == "reviewed" and semantic_scope_authority != "candidate":
                semantic_scope_authority = "reviewed"
            for ref in list(meta.get("semantic_scope_rejected_refs", []) or []):
                clean_ref = str(ref or "").strip()
                if clean_ref and clean_ref not in semantic_scope_rejected_refs:
                    semantic_scope_rejected_refs.append(clean_ref)
            for ref in list(meta.get("bound_refs", []) or []):
                clean_ref = str(ref or "").strip()
                if clean_ref and clean_ref not in bound_refs:
                    bound_refs.append(clean_ref)
            bundle = meta.get("evidence_bundle")
            if isinstance(bundle, dict) and bundle:
                evidence_bundles.append(dict(bundle))
            for line in list(meta.get("detail_lines", []) or []):
                clean_line = str(line or "").strip()
                if clean_line:
                    detail_lines.append(clean_line)
            raw_sources = meta.get("sources")
            if not isinstance(raw_sources, list):
                continue
            for source in raw_sources:
                if not isinstance(source, dict):
                    continue
                refs = tuple(str(ref or "").strip() for ref in list(source.get("refs", []) or []) if str(ref or "").strip())
                key = (
                    str(source.get("surface", "") or "").strip(),
                    str(source.get("kind", "") or "").strip(),
                    refs,
                )
                if key in source_keys:
                    continue
                source_keys.add(key)
                sources.append(dict(source))
        evidence_bundle = AgenticContextRuntimeMixin._merge_connection_evidence_bundles(evidence_bundles)
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content="\n\n".join(contents),
            metadata={
                "sources": sources,
                "scope_contract": "candidate_context" if has_unbound_inventory else "bound",
                "bound_refs": bound_refs,
                "semantic_scope_authority": semantic_scope_authority,
                "semantic_scope_rejected_refs": semantic_scope_rejected_refs,
                "evidence_bundle": evidence_bundle,
                "requires_llm_narrowing": has_unbound_inventory,
                "detail_lines": [
                    *detail_lines,
                    f"Routing Debug: inventory_merge results={len(inventory_results)} sources={len(sources)}",
                    *(
                        [
                            "Routing Debug: evidence_bundle merged "
                            f"surface={evidence_bundle.get('surface') or '-'} "
                            f"authority={evidence_bundle.get('authority') or '-'} "
                            f"completeness={evidence_bundle.get('completeness') or '-'} "
                            f"rows={int(evidence_bundle.get('row_count') or 0)}"
                        ]
                        if evidence_bundle
                        else []
                    ),
                ],
            },
        )

    @staticmethod
    def _merge_connection_evidence_bundles(bundles: list[dict[str, Any]]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        row_keys: set[tuple[str, str]] = set()
        field_set: list[str] = []
        selected_kinds: list[str] = []
        selected_refs: list[str] = []
        row_refs: list[str] = []
        completeness_rank = {"candidate_only": 0, "semantic_subset": 1, "explicit_refs": 2, "full_kind": 3}
        completeness = ""
        authority = "config"
        query = ""
        scope_contract = "bound"
        semantic_scope_authority = "explicit_config"
        for bundle in bundles:
            if str(bundle.get("surface", "") or "") != "connections":
                continue
            if not query:
                query = str(bundle.get("query", "") or "").strip()
            if str(bundle.get("authority", "") or "") != "config":
                authority = "candidate"
            if str(bundle.get("scope_contract", "") or "") != "bound":
                scope_contract = "candidate_context"
            bundle_completeness = str(bundle.get("completeness", "") or "").strip()
            if not completeness or completeness_rank.get(bundle_completeness, -1) < completeness_rank.get(completeness, -1):
                completeness = bundle_completeness
            bundle_semantic = str(bundle.get("semantic_scope_authority", "") or "").strip()
            if bundle_semantic == "candidate":
                semantic_scope_authority = "candidate"
            elif bundle_semantic == "reviewed" and semantic_scope_authority != "candidate":
                semantic_scope_authority = "reviewed"
            for field in list(bundle.get("field_set", []) or []):
                clean = str(field or "").strip()
                if clean and clean not in field_set:
                    field_set.append(clean)
            for kind in list(bundle.get("selected_kinds", []) or []):
                clean = str(kind or "").strip()
                if clean and clean not in selected_kinds:
                    selected_kinds.append(clean)
            for ref in list(bundle.get("selected_refs", []) or []):
                clean = str(ref or "").strip()
                if clean and clean not in selected_refs:
                    selected_refs.append(clean)
            for row in list(bundle.get("rows", []) or []):
                if not isinstance(row, dict):
                    continue
                kind = str(row.get("kind", "") or "").strip()
                ref = str(row.get("ref", "") or "").strip()
                key = (kind, ref)
                if key in row_keys:
                    continue
                row_keys.add(key)
                rows.append(dict(row))
                if ref and ref not in row_refs:
                    row_refs.append(ref)
        if not rows:
            return {}
        return {
            "surface": "connections",
            "authority": authority,
            "completeness": completeness or "candidate_only",
            "scope_contract": scope_contract,
            "semantic_scope_authority": semantic_scope_authority,
            "query": query,
            "field_set": field_set,
            "row_count": len(rows),
            "selected_kinds": selected_kinds,
            "selected_refs": selected_refs,
            "row_refs": row_refs,
            "rows": rows,
        }

    async def _compose_aria_context_answer(
        self,
        *,
        answer_mode: str,
        fallback_text: str,
        arbitration: AriaTurnArbitration,
        skill_result: SkillResult | None,
        status: str,
        request_id: str,
        user_id: str,
        source: str,
        language: str | None,
    ) -> tuple[str, dict[str, int], str]:
        return await compose_aria_context_answer(
            llm_client=self.llm_client,
            answer_mode=answer_mode,
            fallback_text=fallback_text,
            arbitration=arbitration,
            skill_result=skill_result,
            status=status,
            request_id=request_id,
            user_id=user_id,
            source=source,
            language=language,
            skill_result_sources=self._aria_turn_skill_result_sources,
        )

    def _aria_turn_fast_notes_inventory_answer(
        self,
        arbitration: AriaTurnArbitration,
        notes_result: SkillResult,
        *,
        language: str | None = None,
    ) -> str:
        return fast_notes_inventory_answer(
            arbitration,
            notes_result,
            language=language,
            pipeline_text=self._pipeline_text,
            topic_terms_for_request=self._aria_turn_topic_terms_for_request,
        )

    def _aria_turn_fast_docs_search_answer(
        self,
        arbitration: AriaTurnArbitration,
        docs_result: SkillResult,
        *,
        language: str | None = None,
    ) -> str:
        return fast_docs_search_answer(
            arbitration,
            docs_result,
            language=language,
            pipeline_text=self._pipeline_text,
            single_local_search_request=self._aria_turn_single_local_search_request,
            skill_result_sources=self._aria_turn_skill_result_sources,
        )

    def _aria_turn_docs_search_fallback_answer(
        self,
        arbitration: AriaTurnArbitration,
        docs_result: SkillResult,
        *,
        language: str | None = None,
    ) -> str:
        return docs_search_fallback_answer(
            arbitration,
            docs_result,
            language=language,
            pipeline_text=self._pipeline_text,
            single_local_search_request=self._aria_turn_single_local_search_request,
            skill_result_sources=self._aria_turn_skill_result_sources,
        )

    async def _aria_turn_direct_context_result(
        self,
        *,
        arbitration: AriaTurnArbitration | None,
        skill_results: list[SkillResult],
        detail_lines: list[str],
        intents: list[str],
        decision: Any,
        safe_fix_plan: list[dict[str, Any]] | None,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
        language: str | None = None,
    ) -> PipelineResult | None:
        if arbitration is None:
            return None
        plan = arbitration.plan
        if plan.actions or plan.needs_confirmation:
            return None
        direct_kind = ""
        answer_status = "found"
        text = ""
        inventory_result = self._aria_turn_merge_inventory_results(skill_results)
        if inventory_result is not None and "context_inventory" in plan.intents and "web_research" not in plan.intents:
            direct_kind = "inventory"
            content = str(inventory_result.content or "").strip()
            has_sources = self._aria_turn_result_has_sources(inventory_result)
            inventory_meta = dict(inventory_result.metadata or {})
            evidence_bundle = inventory_meta.get("evidence_bundle")
            if isinstance(evidence_bundle, dict) and evidence_bundle:
                self._remember_aria_turn_evidence_bundle(evidence_bundle, user_id=user_id)
            scope_contract = str(inventory_meta.get("scope_contract", "") or "").strip()
            semantic_scope_authority = str(inventory_meta.get("semantic_scope_authority", "") or "").strip()
            requires_llm_narrowing = bool(inventory_meta.get("requires_llm_narrowing")) or scope_contract not in {"bound"}
            answer_status = "found" if has_sources else "empty"
            if not has_sources:
                text = self._pipeline_text(language, "direct_context.inventory_empty", "I found no matching entries in the selected inventory.")
            elif requires_llm_narrowing:
                text = self._pipeline_text(
                    language,
                    "direct_context.inventory_needs_narrowing",
                    "I loaded inventory candidates, but no contract-bound source was selected. I will not turn them into a broad deterministic list.",
                )
            elif semantic_scope_authority == "candidate" and str(language or "de").lower().startswith("en"):
                text = f"I found possible matching configured sources:\n{content}"
            elif semantic_scope_authority == "candidate":
                text = f"Ich habe moegliche passende konfigurierte Quellen gefunden:\n{content}"
            elif str(language or "de").lower().startswith("en"):
                text = f"I found matching configured sources:\n{content}"
            else:
                text = f"Ich habe passende konfigurierte Quellen gefunden:\n{content}"
            text, composer_usage, composer_debug = await self._compose_aria_context_answer(
                answer_mode="inventory_list" if has_sources else "inventory_empty",
                fallback_text=text,
                arbitration=arbitration,
                skill_result=inventory_result,
                status="found" if has_sources else "empty",
                request_id=request_id,
                user_id=user_id,
                source=source,
                language=language,
            )
        elif self._aria_turn_is_notes_only_context(arbitration) and "web_research" not in plan.intents:
            notes_result = next((result for result in skill_results if result.skill_name == "notes_search" and result.success), None)
            if notes_result is None:
                return None
            if not self._aria_turn_notes_only_has_evidence(arbitration, notes_result):
                return None
            direct_kind = "notes_search"
            content = str(notes_result.content or "").strip()
            if str(language or "de").lower().startswith("en"):
                text = f"I found this in your notes:\n{content}"
            else:
                text = f"{self._pipeline_text(language, 'direct_context.notes_found_prefix', 'I found this in your notes:')}\n{content}"
            fast_notes_text = self._aria_turn_fast_notes_inventory_answer(arbitration, notes_result, language=language)
            if fast_notes_text:
                text = fast_notes_text
                composer_usage = {}
                composer_debug = "Routing Debug: answer_composer skipped reason=fast_notes_inventory_answer"
            else:
                text, composer_usage, composer_debug = await self._compose_aria_context_answer(
                    answer_mode="notes_answer",
                    fallback_text=text,
                    arbitration=arbitration,
                    skill_result=notes_result,
                    status="found",
                    request_id=request_id,
                    user_id=user_id,
                    source=source,
                    language=language,
                )
        elif self._aria_turn_memory_exists_request(arbitration):
            memory_result = next((result for result in skill_results if result.skill_name == "memory_recall" and result.success), None)
            if memory_result is None:
                return None
            direct_kind = "memory_exists"
            content = str(memory_result.content or "").strip()
            has_context = self._aria_turn_has_loaded_local_context([memory_result]) and self._aria_turn_memory_exists_has_evidence(arbitration, memory_result)
            answer_status = "found" if has_context else "no_match"
            if not has_context:
                text = self._pipeline_text(language, "direct_context.memory_exists_empty", "No, I found no matching entries in the searched memory sources.")
            elif str(language or "de").lower().startswith("en"):
                text = f"Yes, I found matching memory entries:\n{content}"
            else:
                text = f"{self._pipeline_text(language, 'direct_context.memory_exists_found_prefix', 'Yes, I found matching memory entries:')}\n{content}"
            text, composer_usage, composer_debug = await self._compose_aria_context_answer(
                answer_mode="memory_exists",
                fallback_text=text,
                arbitration=arbitration,
                skill_result=memory_result,
                status="found" if has_context else "no_match",
                request_id=request_id,
                user_id=user_id,
                source=source,
                language=language,
            )
        else:
            local_search_request = self._aria_turn_single_local_search_request(arbitration)
            if local_search_request is not None:
                memory_result = next((result for result in skill_results if result.skill_name == "memory_recall" and result.success), None)
                has_document_inventory = bool(memory_result and (memory_result.metadata or {}).get("document_inventory", False))
                if (
                    memory_result is not None
                    and (plan.answer_mode == "direct_answer" or has_document_inventory)
                    and self._aria_turn_has_loaded_local_context([memory_result])
                    and self._aria_turn_local_search_has_evidence(local_search_request, memory_result)
                ):
                    direct_kind = "docs_search" if has_document_inventory else f"{local_search_request.surface_id}_search"
                    answer_status = "found"
                    content = str(memory_result.content or "").strip()
                    if str(language or "de").lower().startswith("en"):
                        label = "documents" if local_search_request.surface_id == "docs" or has_document_inventory else "memory"
                        text = f"I found this in your {label}:\n{content}"
                    elif local_search_request.surface_id == "docs" or has_document_inventory:
                        text = f"In deinen Dokumenten habe ich dazu gefunden:\n{content}"
                    else:
                        text = f"In deinem Memory habe ich dazu gefunden:\n{content}"
                    fast_docs_text = (
                        self._aria_turn_fast_docs_search_answer(arbitration, memory_result, language=language)
                        if local_search_request.surface_id == "docs" or has_document_inventory
                        else ""
                    )
                    if fast_docs_text:
                        text = fast_docs_text
                        composer_usage = {}
                        composer_debug = "Routing Debug: answer_composer skipped reason=fast_docs_search_answer"
                    else:
                        docs_fallback_text = (
                            self._aria_turn_docs_search_fallback_answer(arbitration, memory_result, language=language)
                            if local_search_request.surface_id == "docs" or has_document_inventory
                            else text
                        )
                        text, composer_usage, composer_debug = await self._compose_aria_context_answer(
                            answer_mode=f"{local_search_request.surface_id}_search",
                            fallback_text=docs_fallback_text or text,
                            arbitration=arbitration,
                            skill_result=memory_result,
                            status="found",
                            request_id=request_id,
                            user_id=user_id,
                            source=source,
                            language=language,
                        )
        if not direct_kind:
            return None

        result_detail_lines: list[str] = []
        source_count = 0
        for result in skill_results:
            sources = (result.metadata or {}).get("sources")
            source_count += context_source_count(sources)
            detail = (result.metadata or {}).get("detail_lines")
            if isinstance(detail, list):
                result_detail_lines.extend(str(line) for line in detail if str(line or "").strip())
        duration_ms = int((time.perf_counter() - start) * 1000)
        usage_snapshot = self._current_usage_snapshot()
        usage = dict(usage_snapshot.get("usage", {}) or {})
        if "composer_usage" not in locals():
            composer_usage = {}
        if "composer_debug" not in locals():
            composer_debug = ""
        for key, value in dict(composer_usage or {}).items():
            usage[key] = int(usage.get(key, 0) or 0) + int(value or 0)
        embedding_usage = dict(usage_snapshot.get("embedding_usage", {}) or {})
        skill_errors = self._skill_errors(skill_results)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=intents,
            router_level=decision.level,
            usage=usage,
            chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
            embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
            embedding_usage=embedding_usage,
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            duration_ms=duration_ms,
            source=source,
            skill_errors=skill_errors,
            extraction_model=f"direct_context_{direct_kind}",
            extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
        )
        return PipelineResult(
            request_id=request_id,
            text=text,
            usage=usage,
            intents=intents,
            skill_errors=skill_errors,
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            safe_fix_plan=safe_fix_plan,
            detail_lines=[
                *detail_lines,
                *result_detail_lines,
                *(
                    [
                        "Routing Debug: evidence_bundle stored "
                        f"surface={evidence_bundle.get('surface') or '-'} "
                        f"authority={evidence_bundle.get('authority') or '-'} "
                        f"completeness={evidence_bundle.get('completeness') or '-'} "
                        f"rows={int(evidence_bundle.get('row_count') or 0)}"
                    ]
                    if "evidence_bundle" in locals() and isinstance(evidence_bundle, dict) and evidence_bundle
                    else []
                ),
                *([composer_debug] if composer_debug else []),
                self._aria_turn_answer_contract_line(
                    arbitration=arbitration,
                    kind=direct_kind,
                    status=answer_status,
                    source_count=source_count,
                ),
                f"Routing Debug: direct_context_answer kind={direct_kind} reason=turn_plan_selected_loaded_context",
            ],
        )

    async def _aria_turn_empty_local_context_result(
        self,
        *,
        arbitration: AriaTurnArbitration | None,
        skill_results: list[SkillResult],
        detail_lines: list[str],
        intents: list[str],
        decision: Any,
        safe_fix_plan: list[dict[str, Any]] | None,
        start: float,
        request_id: str,
        user_id: str,
        source: str,
        language: str | None = None,
    ) -> PipelineResult | None:
        if arbitration is None:
            return None
        plan = arbitration.plan
        if not plan.needs_context:
            return None
        if "web_research" in plan.intents or "web" in plan.context_directions:
            return None
        selected_local_context = bool(
            "local_retrieval" in plan.intents
            or "context_inventory" in plan.intents
            or plan.collections
            or plan.context_requests
            or set(plan.context_directions) & {"memory", "learning", "notes", "docs", "sessions", "connections", "workspace"}
        )
        if not selected_local_context:
            return None
        notes_only_without_evidence = False
        if self._aria_turn_is_notes_only_context(arbitration):
            notes_result = next((result for result in skill_results if result.skill_name == "notes_search" and result.success), None)
            notes_only_without_evidence = notes_result is not None and not self._aria_turn_notes_only_has_evidence(arbitration, notes_result)
        local_search_without_evidence = False
        local_search_request = self._aria_turn_single_local_search_request(arbitration)
        if local_search_request is not None:
            memory_result = next((result for result in skill_results if result.skill_name == "memory_recall" and result.success), None)
            local_search_without_evidence = memory_result is not None and not self._aria_turn_local_search_has_evidence(local_search_request, memory_result)
        if self._aria_turn_has_loaded_local_context(skill_results) and not notes_only_without_evidence and not local_search_without_evidence:
            return None

        duration_ms = int((time.perf_counter() - start) * 1000)
        usage_snapshot = self._current_usage_snapshot()
        usage = dict(usage_snapshot.get("usage", {}) or {})
        embedding_usage = dict(usage_snapshot.get("embedding_usage", {}) or {})
        skill_errors = self._skill_errors(skill_results)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=intents,
            router_level=decision.level,
            usage=usage,
            chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
            embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
            embedding_usage=embedding_usage,
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            duration_ms=duration_ms,
            source=source,
            skill_errors=skill_errors,
            extraction_model="local_context_empty_guardrail",
            extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
        )
        selected_directions = ",".join(plan.context_directions) or "-"
        selected_collections = ",".join(plan.collections) or "-"
        result_detail_lines: list[str] = []
        source_count = 0
        for result in skill_results:
            sources = (result.metadata or {}).get("sources")
            source_count += context_source_count(sources)
            detail = (result.metadata or {}).get("detail_lines")
            if isinstance(detail, list):
                result_detail_lines.extend(str(line) for line in detail if str(line or "").strip())
        fallback_text = self._aria_turn_empty_local_context_text(arbitration, language=language)
        text, composer_usage, composer_debug = await self._compose_aria_context_answer(
            answer_mode="empty_source_bound",
            fallback_text=fallback_text,
            arbitration=arbitration,
            skill_result=None,
            status="empty",
            request_id=request_id,
            user_id=user_id,
            source=source,
            language=language,
        )
        for key, value in dict(composer_usage or {}).items():
            usage[key] = int(usage.get(key, 0) or 0) + int(value or 0)
        return PipelineResult(
            request_id=request_id,
            text=text,
            usage=usage,
            intents=intents,
            skill_errors=skill_errors,
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            safe_fix_plan=safe_fix_plan,
            detail_lines=[
                *detail_lines,
                *result_detail_lines,
                *([composer_debug] if composer_debug else []),
                self._aria_turn_answer_contract_line(
                    arbitration=arbitration,
                    kind="empty_source_bound",
                    status="empty",
                    source_count=source_count,
                ),
                "Routing Debug: local_context_empty "
                f"directions={selected_directions} collections={selected_collections} "
                f"boundary=guardrail reason={'no_evidence_sources' if (notes_only_without_evidence or local_search_without_evidence) else 'no_loaded_sources'}",
            ],
        )

    @staticmethod
    def _aria_turn_uses_meta_catalog_contract(arbitration: AriaTurnArbitration | None) -> bool:
        return arbitration is not None and arbitration.source == META_CATALOG_ROUTING_OPERATION

    @staticmethod
    def _aria_turn_has_confident_local_context(arbitration: AriaTurnArbitration | None) -> bool:
        if arbitration is None:
            return False
        plan = arbitration.plan
        meta_catalog_contract = AgenticContextRuntimeMixin._aria_turn_uses_meta_catalog_contract(arbitration)
        if not meta_catalog_contract and plan.confidence < 0.82:
            return False
        if "web_research" in plan.intents or "web" in plan.context_directions:
            return False
        if plan.contract_mode == "action" or any(request.mode == "action" for request in plan.context_requests):
            selected_action_kinds = {
                kind
                for kind, _ref in AgenticContextRuntimeMixin._aria_turn_selected_connections_from_catalog(arbitration)
                if kind in {"ssh", "rss"}
            }
            if selected_action_kinds:
                return False
        if plan.actions or plan.needs_confirmation:
            return False
        if "context_inventory" in plan.intents:
            return bool(plan.context_requests or "connections" in plan.context_directions)
        local_directions = {"memory", "learning", "notes", "docs", "sessions"}
        selected_local_context = bool(
            set(plan.context_directions) & local_directions
            or plan.collections
            or any(request.surface_id in {"memory", "notes", "docs"} for request in plan.context_requests)
        )
        return bool(plan.needs_context and selected_local_context)

    @staticmethod
    def _aria_turn_action_capability(action: str, kind: str = "") -> str:
        clean_action = str(action or "").strip().lower()
        clean_kind = normalize_connection_kind(str(kind or ""))
        if clean_action in {"ssh_run_command", "connection_action_ssh"} or clean_kind == "ssh":
            return "ssh_command"
        if clean_action in {"website_list", "connection_action_website"}:
            return "website_list"
        if clean_action in {"website_read"} or clean_kind == "website":
            return "website_read"
        if clean_action in {"feed_read", "connection_action_rss"} or clean_kind == "rss":
            return "feed_read"
        if clean_kind in {"sftp", "smb"}:
            if "write" in clean_action:
                return "file_write"
            if "read" in clean_action:
                return "file_read"
            return "file_list"
        if clean_kind == "google_calendar":
            return "calendar_read"
        if clean_kind == "webhook":
            return "webhook_send"
        if clean_kind == "discord":
            return "discord_send"
        if clean_kind == "http_api":
            return "api_request"
        if clean_kind == "email":
            return "email_send"
        if clean_kind == "imap":
            return "mail_search" if "search" in clean_action else "mail_read"
        if clean_kind == "mqtt":
            return "mqtt_publish"
        if clean_action.startswith("connection_action_"):
            tail = normalize_connection_kind(clean_action.removeprefix("connection_action_"))
            return f"{tail}_action" if tail else ""
        return clean_action

    @staticmethod
    def _aria_turn_file_operation_from_query(query: str) -> tuple[str, str]:
        text = str(query or "").strip()
        lower = text.lower()
        path = ""
        quoted = re.search(r"['\"](/[^'\"]+)['\"]", text)
        if quoted:
            path = str(quoted.group(1) or "").strip()
        else:
            raw = re.search(r"(^|\s)(/[^\s,;:]+)", text)
            if raw:
                path = str(raw.group(2) or "").strip()
        if any(term in lower for term in ("schreib", "write", "speichere", "erstelle", "create", "upload")):
            return "file_write", path
        if not path and any(term in lower for term in ("hosts datei", "host datei", "hosts file", "host file")):
            path = "/etc/hosts"
        if any(term in lower for term in ("lies", "lese", "read", "zeige mir die datei", "open file", "oeffne datei")):
            return "file_read", path
        if path == "/etc/hosts":
            return "file_read", path
        if any(term in lower for term in ("liste", "list", "dateien", "files", "verzeichnis", "directory", "ordner")):
            return "file_list", path or "."
        return "file_list", path or "."

    @staticmethod
    def _aria_turn_selected_connection_from_catalog(arbitration: AriaTurnArbitration | None) -> tuple[str, str]:
        if arbitration is None:
            return "", ""
        for value in arbitration.plan.priority:
            parts = str(value or "").strip().split("|", 2)
            if len(parts) == 3 and parts[0] == "connection":
                return normalize_connection_kind(parts[1]), parts[2].strip()
        for request in arbitration.plan.context_requests:
            budget = dict(request.budget or {})
            if str(budget.get("entity_type", "") or "").strip() == "connection":
                return normalize_connection_kind(str(budget.get("kind", "") or "")), str(budget.get("ref", "") or "").strip()
        return "", ""

    @staticmethod
    def _aria_turn_selected_connections_from_catalog(arbitration: AriaTurnArbitration | None) -> tuple[tuple[str, str], ...]:
        if arbitration is None:
            return ()
        rows: list[tuple[str, str]] = []
        for value in arbitration.plan.priority:
            parts = str(value or "").strip().split("|", 2)
            if len(parts) == 3 and parts[0] == "connection":
                kind = normalize_connection_kind(parts[1])
                ref = parts[2].strip()
                if kind and ref and (kind, ref) not in rows:
                    rows.append((kind, ref))
        for request in arbitration.plan.context_requests:
            budget = dict(request.budget or {})
            if str(budget.get("entity_type", "") or "").strip() != "connection":
                continue
            kind = normalize_connection_kind(str(budget.get("kind", "") or ""))
            ref = str(budget.get("ref", "") or "").strip()
            if kind and ref and (kind, ref) not in rows:
                rows.append((kind, ref))
        return tuple(rows)

    def _aria_turn_connection_row(self, kind: str, ref: str) -> Any | None:
        rows = getattr(getattr(getattr(self, "settings", object()), "connections", object()), normalize_connection_kind(kind), {})
        if not isinstance(rows, dict):
            return None
        return rows.get(str(ref or "").strip())

    def _aria_turn_explicit_ref_is_prompt_bound(self, query: str, *, kind: str, ref: str) -> bool:
        clean_ref = str(ref or "").strip()
        clean_kind = normalize_connection_kind(kind)
        if not clean_ref or not clean_kind:
            return False
        row = self._aria_turn_connection_row(clean_kind, clean_ref)
        if row is None:
            return True
        aliases = build_connection_aliases(clean_kind, clean_ref, row)
        for alias in [clean_ref, *aliases]:
            if connection_label_match_score(query, alias) > 0:
                return True
        return False

    @staticmethod
    def _aria_turn_requested_ref_hint_from_query(query: str) -> str:
        text = re.sub(r"https?://\S+", " ", str(query or ""), flags=re.IGNORECASE)
        text = re.sub(r"(?:^|\s)/(?:\S+)", " ", text)
        patterns = (
            r"\b[a-zA-Z][a-zA-Z0-9]*(?:[-_.][a-zA-Z0-9]+)+\b",
            r"\b[a-zA-Z]+[0-9][a-zA-Z0-9_-]*\b",
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return str(match.group(0) or "").strip()
        return ""

    def _aria_turn_seed_capability_draft(
        self,
        arbitration: AriaTurnArbitration | None,
        *,
        user_message: str = "",
    ) -> CapabilityDraft | None:
        if arbitration is None:
            return None
        plan = arbitration.plan
        if not (
            plan.actions
            or plan.answer_mode == "plan_action"
            or plan.needs_confirmation
            or plan.contract_mode == "action"
            or any(request.mode == "action" for request in plan.context_requests)
        ):
            return None
        query = next((request.query for request in plan.context_requests if str(request.query or "").strip()), "")
        raw_query = str(user_message or query or "").strip()
        selected_connections = self._aria_turn_selected_connections_from_catalog(arbitration)
        selected_by_kind: dict[str, list[str]] = {}
        for item_kind, item_ref in selected_connections:
            if item_kind and item_ref:
                selected_by_kind.setdefault(item_kind, []).append(item_ref)
        action = str(next(iter(plan.actions), "") or "").strip()
        kind, ref = self._aria_turn_selected_connection_from_catalog(arbitration)
        clean_actions = [str(item or "").strip() for item in plan.actions if str(item or "").strip()]
        ssh_actions = {"ssh_run_command", "connection_action_ssh"}
        rss_actions = {"rss_read_feed", "feed_read", "connection_action_rss"}
        target_scope_authority = str(getattr(plan, "target_scope_authority", "") or "").strip().lower()
        full_kind_scope = target_scope_authority == "full_kind"
        if any(action_item.lower() in ssh_actions for action_item in clean_actions) and selected_by_kind.get("ssh"):
            action = next(action_item for action_item in clean_actions if action_item.lower() in ssh_actions)
            kind = "ssh"
            ref = selected_by_kind["ssh"][0]
            selected_connections = tuple(("ssh", item_ref) for item_ref in selected_by_kind["ssh"])
        elif any(action_item.lower() in ssh_actions for action_item in clean_actions) and full_kind_scope:
            action = next(action_item for action_item in clean_actions if action_item.lower() in ssh_actions)
            kind = "ssh"
            ref = ""
        elif not clean_actions and selected_by_kind.get("ssh"):
            action = "ssh_run_command"
            kind = "ssh"
            ref = selected_by_kind["ssh"][0]
            selected_connections = tuple(("ssh", item_ref) for item_ref in selected_by_kind["ssh"])
        elif any(action_item.lower() in rss_actions for action_item in clean_actions) and selected_by_kind.get("rss"):
            action = next(action_item for action_item in clean_actions if action_item.lower() in rss_actions)
            kind = "rss"
            ref = selected_by_kind["rss"][0]
            selected_connections = tuple(("rss", item_ref) for item_ref in selected_by_kind["rss"])
        elif not clean_actions and selected_by_kind.get("rss") and (
            plan.contract_mode == "action" or any(request.mode == "action" for request in plan.context_requests)
        ):
            action = "rss_read_feed"
            kind = "rss"
            ref = selected_by_kind["rss"][0]
            selected_connections = tuple(("rss", item_ref) for item_ref in selected_by_kind["rss"])
        elif not clean_actions and (selected_by_kind.get("sftp") or selected_by_kind.get("smb")) and (
            plan.contract_mode == "action" or any(request.mode == "action" for request in plan.context_requests)
        ):
            kind = "sftp" if selected_by_kind.get("sftp") else "smb"
            inferred_capability, _inferred_path = self._aria_turn_file_operation_from_query(query)
            if not self._aria_turn_has_file_action_evidence(query, inferred_path=_inferred_path):
                return None
            action = inferred_capability or "file_list"
            ref = selected_by_kind[kind][0]
            selected_connections = tuple((kind, item_ref) for item_ref in selected_by_kind[kind])
        capability = self._aria_turn_action_capability(action, kind)
        if not capability:
            return None
        selected_kinds = {item_kind for item_kind, _item_ref in selected_connections if item_kind}
        multi_target = (
            len(selected_connections) > 1 and (not selected_kinds or len(selected_kinds) == 1)
        ) or (capability == "ssh_command" and kind == "ssh" and full_kind_scope)
        connection_refs = [
            item_ref
            for item_kind, item_ref in selected_connections
            if item_kind and item_ref and (not selected_kinds or item_kind in selected_kinds)
        ]
        if multi_target:
            kind = next(iter(selected_kinds), kind)
            ref = ""
        meta_catalog_contract = self._aria_turn_uses_meta_catalog_contract(arbitration)
        authoritative_subset = target_scope_authority in {"explicit_refs", "semantic_group", "last_turn_scope"}
        ignored_connection_refs: list[str] = []
        if multi_target and not authoritative_subset:
            ignored_connection_refs = list(connection_refs)
            connection_refs = []
        inferred_path = ""
        if kind in {"sftp", "smb"} and capability in {"file_list", "file_read", "file_write"}:
            inferred_capability, inferred_path = self._aria_turn_file_operation_from_query(query)
            if inferred_capability:
                capability = inferred_capability
        path = ""
        content = ""
        if capability in {"file_list", "file_read", "file_write", "calendar_read", "api_request", "mqtt_publish"}:
            path = str(inferred_path if kind in {"sftp", "smb"} else query or "").strip()
        if capability in {"webhook_send", "discord_send", "email_send", "mail_search", "mqtt_publish", "file_write"}:
            content = str(query or "").strip()
        if capability in {"website_read", "feed_read"}:
            content = str(query or "").strip()
        notes = [
            f"capability_draft_source:{'meta_catalog' if meta_catalog_contract else 'legacy_backup'}",
            f"turn_contract_source:{arbitration.source}",
            f"turn_contract_actions:{','.join(plan.actions)}",
            f"turn_contract_priority:{','.join(plan.priority)}",
        ]
        if multi_target:
            notes.append("target_scope:multi_target")
            notes.append(f"target_scope_authority:{target_scope_authority or 'priority_sample'}")
            if full_kind_scope:
                notes.append("turn_contract_target_refs:full_kind")
            elif connection_refs:
                notes.append(f"turn_contract_target_refs:{','.join(connection_refs)}")
            elif ignored_connection_refs:
                notes.append(f"turn_contract_priority_refs_ignored:{','.join(ignored_connection_refs)}")
        requested_ref = ""
        if (
            ref
            and not multi_target
            and target_scope_authority == "explicit_refs"
            and not self._aria_turn_explicit_ref_is_prompt_bound(raw_query, kind=kind, ref=ref)
        ):
            requested_ref = self._aria_turn_requested_ref_hint_from_query(raw_query)
            notes.append("explicit_target_authority:blocked_unbound_ref")
            notes.append(f"explicit_target_candidate_blocked:{kind}/{ref}")
            ref = ""
        return CapabilityDraft(
            capability=capability,
            connection_kind=kind,
            explicit_connection_ref=ref,
            requested_connection_ref=requested_ref,
            path=path,
            content="" if capability == "ssh_command" else content,
            confidence=max(0.62, float(plan.confidence or 0.0)),
            connection_refs=connection_refs if multi_target and authoritative_subset else [],
            notes=notes,
        )

    @staticmethod
    def _aria_turn_has_file_action_evidence(query: str, *, inferred_path: str = "") -> bool:
        if str(inferred_path or "").strip() not in {"", "."}:
            return True
        lower = str(query or "").strip().lower()
        if not lower:
            return False
        file_scope = bool(
            re.search(
                r"\b(?:datei|dateien|file|files|pfad|path|verzeichnis|directory|ordner|folder)\b",
                lower,
            )
        )
        file_action = bool(
            re.search(
                r"\b(?:liste|list|lies|lese|read|zeige|oeffne|open|schreib|write|speichere|erstelle|create|upload)\b",
                lower,
            )
        )
        return file_scope and file_action

    @staticmethod
    def _aria_turn_forces_selected_context(arbitration: AriaTurnArbitration | None) -> bool:
        if arbitration is None:
            return False
        plan = arbitration.plan
        if not plan.needs_context:
            return False
        if plan.actions or plan.needs_confirmation:
            return False
        return bool(plan.context_directions or plan.collections or plan.context_requests)

    @staticmethod
    def _insert_stage_timing_detail_lines(detail_lines: list[str] | None, timing: StageTimingLedger) -> list[str]:
        return insert_stage_timing_detail_lines(detail_lines, timing)

    @staticmethod
    def _aria_turn_can_direct_inventory_fast_path(arbitration: AriaTurnArbitration | None) -> bool:
        if arbitration is None:
            return False
        plan = arbitration.plan
        if (
            plan.actions
            or plan.needs_confirmation
            or "web_research" in plan.intents
        ):
            return False
        if plan.contract_mode == "action" or any(request.mode == "action" for request in plan.context_requests):
            selected_action_kinds = {
                kind
                for kind, _ref in AgenticContextRuntimeMixin._aria_turn_selected_connections_from_catalog(arbitration)
                if kind in {"ssh", "rss"}
            }
            if selected_action_kinds:
                return False
        if "context_inventory" not in plan.intents:
            return False
        requests = tuple(plan.context_requests)
        if not requests:
            return "connections" in {str(item or "").strip().lower() for item in plan.context_directions}
        inventory_requests = [request for request in requests if request.mode == "inventory"]
        if not inventory_requests:
            return False
        return all(request.surface_id not in {"memory", "notes", "docs"} for request in inventory_requests)

    def _aria_turn_can_direct_memory_exists_fast_path(self, arbitration: AriaTurnArbitration | None) -> bool:
        if not self._aria_turn_memory_exists_request(arbitration):
            return False
        if arbitration is None:
            return False
        plan = arbitration.plan
        if plan.actions or plan.needs_confirmation or "web_research" in plan.intents:
            return False
        return True

    async def _aria_turn_memory_exists_skill_result(
        self,
        *,
        arbitration: AriaTurnArbitration,
        user_id: str,
        memory_collection: str | None,
        session_collection: str | None,
        context_overrides: dict[str, Any],
    ) -> SkillResult:
        return await self._agentic_context_surface_loader().load_memory_exists(
            arbitration=arbitration,
            user_id=user_id,
            memory_collection=memory_collection,
            session_collection=session_collection,
            context_overrides=context_overrides,
        )

    @staticmethod
    def _aria_turn_frame_from_arbitration(arbitration: AriaTurnArbitration | None):
        return turn_frame_from_arbitration(arbitration)

    def _aria_turn_last_frame_payload(self, user_id: str) -> dict[str, Any]:
        return self._agentic_context_runtime_state().last_frame_payload(user_id)

    def _remember_aria_turn_evidence_bundle(
        self,
        bundle: dict[str, Any] | None,
        *,
        user_id: str,
    ) -> None:
        self._agentic_context_runtime_state().remember_evidence_bundle(bundle, user_id=user_id)

    @staticmethod
    def _connection_evidence_query_terms(message: str) -> list[str]:
        return [
            token
            for token in _tokenize_inventory_scope(message)
            if len(token) >= 3 and token not in _BROAD_ADDRESS_SCOPE_TOKENS
        ]

    @classmethod
    def _connection_evidence_row_matches(cls, row: dict[str, Any], terms: list[str]) -> bool:
        if not terms:
            return True
        haystack = " ".join(
            str(value or "")
            for value in (
                row.get("kind"),
                row.get("ref"),
                row.get("title"),
                row.get("host"),
                row.get("description"),
                row.get("group_name"),
                " ".join(str(tag or "") for tag in list(row.get("tags", []) or [])),
            )
        ).lower()
        return any(term in haystack for term in terms)

    @staticmethod
    def _connection_evidence_ref_from_catalog_id(catalog_id: str) -> str:
        parts = [part.strip() for part in str(catalog_id or "").split("|")]
        if len(parts) >= 3 and parts[0] == "connection":
            return parts[2]
        return ""

    @staticmethod
    def _connection_evidence_kind_from_catalog_id(catalog_id: str) -> str:
        parts = [part.strip() for part in str(catalog_id or "").split("|")]
        if len(parts) >= 2 and parts[0] == "connection":
            return parts[1]
        return ""

    @classmethod
    def _connection_evidence_rows_by_refs(cls, rows: list[dict[str, Any]], selected_refs: list[str]) -> list[dict[str, Any]]:
        ref_set = {str(ref or "").strip() for ref in selected_refs if str(ref or "").strip()}
        if not ref_set:
            return []
        selected: list[dict[str, Any]] = []
        for row in rows:
            ref = str(row.get("ref", "") or "").strip()
            title = str(row.get("title", "") or "").strip()
            if ref in ref_set or title in ref_set:
                selected.append(row)
        return selected

    @classmethod
    def _connection_evidence_rows_by_kinds(cls, rows: list[dict[str, Any]], selected_kinds: list[str]) -> list[dict[str, Any]]:
        kind_set = {str(kind or "").strip() for kind in selected_kinds if str(kind or "").strip()}
        if not kind_set:
            return []
        return [row for row in rows if str(row.get("kind", "") or "").strip() in kind_set]

    @classmethod
    def _connection_evidence_rows_excluding_refs(cls, rows: list[dict[str, Any]], selected_refs: list[str]) -> list[dict[str, Any]]:
        ref_set = {str(ref or "").strip() for ref in selected_refs if str(ref or "").strip()}
        if not ref_set:
            return []
        excluded: list[dict[str, Any]] = []
        for row in rows:
            ref = str(row.get("ref", "") or "").strip()
            title = str(row.get("title", "") or "").strip()
            if ref not in ref_set and title not in ref_set:
                excluded.append(row)
        return excluded

    @classmethod
    def _connection_evidence_rows_for_turn_contract(
        cls,
        *,
        bundle: dict[str, Any],
        arbitration: AriaTurnArbitration | None,
        message: str,
    ) -> tuple[list[dict[str, Any]], str]:
        if arbitration is None:
            return [], "missing_turn_contract"
        plan = arbitration.plan
        if plan.actions or plan.needs_confirmation or plan.contract_mode == "action":
            return [], "action_contract"
        selected_surfaces = {
            str(item or "").strip()
            for item in [*list(plan.surfaces or ()), *list(plan.context_directions or ())]
            if str(item or "").strip() and str(item or "").strip() != "-"
        }
        if selected_surfaces and selected_surfaces != {"connections"}:
            return [], "surface_change"

        raw_rows = [dict(row) for row in list(bundle.get("rows", []) or []) if isinstance(row, dict)]
        rows_with_hosts = [row for row in raw_rows if str(row.get("host", "") or "").strip()]
        if not rows_with_hosts:
            return [], "no_host_rows"

        requests = [
            request
            for request in list(plan.context_requests or ())
            if request.surface_id == "connections" and request.mode == "inventory"
        ]
        if any(request.surface_id != "connections" for request in list(plan.context_requests or ())):
            return [], "mixed_surface_request"

        request = requests[0] if requests else None
        budget = dict(request.budget or {}) if request is not None else {}
        scope_operation = str(plan.scope_operation or budget.get("scope_operation", "") or "").strip()
        if scope_operation == "surface_change":
            return [], "surface_change"
        scope_authority = str(plan.target_scope_authority or "").strip()
        if scope_authority == "last_turn_scope" and not scope_operation:
            return [], "missing_scope_operation"
        if (
            not plan.needs_context
            or "context_inventory" not in set(plan.intents or ())
        ) and not (scope_authority == "last_turn_scope" and scope_operation == "reuse_same_set"):
            return [], "not_inventory_contract"
        if not requests and scope_operation not in {"reuse_same_set"}:
            return [], "missing_connections_inventory_request"
        requested_host_fields = _query_requests_network_address(message) or any(
            _query_requests_network_address(str(request.query or "")) for request in requests
        )
        if not requested_host_fields and scope_operation not in {"narrow_subset", "exclude_subset"}:
            return [], "field_mismatch"

        selected_refs = [
            str(ref or "").strip()
            for ref in list(budget.get("selected_refs", []) or [])
            if str(ref or "").strip()
        ]
        selected_kinds = [
            str(kind or "").strip()
            for kind in list(budget.get("selected_kinds", []) or [])
            if str(kind or "").strip()
        ]
        for key in ("ref", "ref_hint"):
            value = str(budget.get(key, "") or "").strip()
            if value and value not in selected_refs:
                selected_refs.append(value)
        for key in ("kind", "kind_hint"):
            value = str(budget.get(key, "") or "").strip()
            if value and value not in selected_kinds:
                selected_kinds.append(value)
        for catalog_id in list(plan.priority or ()):
            ref = cls._connection_evidence_ref_from_catalog_id(str(catalog_id or ""))
            kind = cls._connection_evidence_kind_from_catalog_id(str(catalog_id or ""))
            if ref and ref not in selected_refs:
                selected_refs.append(ref)
            if kind and kind not in selected_kinds:
                selected_kinds.append(kind)

        completeness = str(bundle.get("completeness", "") or "").strip()
        bundle_kinds = {str(kind or "").strip() for kind in list(bundle.get("selected_kinds", []) or []) if str(kind or "").strip()}

        if scope_operation == "reuse_same_set" and scope_authority == "last_turn_scope":
            return rows_with_hosts, "reused_same_set"

        if scope_operation == "exclude_subset":
            if not selected_refs:
                return [], "missing_subset_refs"
            rows = cls._connection_evidence_rows_excluding_refs(rows_with_hosts, selected_refs)
            return rows, "reused_exclude_subset" if rows else "field_miss"

        if scope_operation == "narrow_subset":
            if not selected_refs:
                return [], "missing_subset_refs"
            rows = cls._connection_evidence_rows_by_refs(rows_with_hosts, selected_refs)
            return rows, "reused_narrow_subset" if rows else "field_miss"

        if scope_authority == "full_kind" or scope_operation == "expand_to_kind" or bool(budget.get("bind_selected_kinds")):
            if completeness != "full_kind":
                return [], "scope_expand_requires_loader"
            if not selected_kinds:
                if scope_operation == "expand_to_kind":
                    return rows_with_hosts, "reused_full_kind"
                return [], "missing_kind_scope"
            if bundle_kinds and not set(selected_kinds).issubset(bundle_kinds):
                return [], "kind_not_in_bundle"
            rows = cls._connection_evidence_rows_by_kinds(rows_with_hosts, selected_kinds)
            return rows, "reused_full_kind" if rows else "field_miss"

        if selected_refs and (
            scope_authority in {"explicit_refs", "semantic_group"}
            or bool(budget.get("bind_selected_refs"))
        ):
            rows = cls._connection_evidence_rows_by_refs(rows_with_hosts, selected_refs)
            return rows, "reused_explicit_refs" if rows else "field_miss"

        return [], "ambiguous_turn_scope"

    @classmethod
    def _connection_evidence_host_ip_answer(
        cls,
        *,
        bundle: dict[str, Any],
        message: str,
        language: str | None,
        selected_rows: list[dict[str, Any]] | None = None,
        selected_status: str = "",
    ) -> tuple[str, list[dict[str, Any]], str]:
        if str(bundle.get("surface", "") or "") != "connections":
            return "", [], "wrong_surface"
        if str(bundle.get("authority", "") or "") != "config":
            return "", [], "non_config_authority"
        if "host" not in {str(field or "") for field in list(bundle.get("field_set", []) or [])}:
            return "", [], "missing_host_field"
        if not _query_requests_network_address(message) and selected_status not in {"reused_exclude_subset", "reused_narrow_subset"}:
            return "", [], "query_not_host_ip"
        raw_rows = [dict(row) for row in list(bundle.get("rows", []) or []) if isinstance(row, dict)]
        rows_with_hosts = [row for row in raw_rows if str(row.get("host", "") or "").strip()]
        if not rows_with_hosts:
            return "", [], "no_host_rows"
        if selected_rows is not None:
            rows = [dict(row) for row in selected_rows if str(row.get("host", "") or "").strip()]
            if not rows:
                return "", [], selected_status or "field_miss"
        else:
            terms = cls._connection_evidence_query_terms(message)
            matching = [row for row in rows_with_hosts if cls._connection_evidence_row_matches(row, terms)]
            if not matching and terms:
                return "", [], "field_miss"
            rows = matching or rows_with_hosts
        completeness = str(bundle.get("completeness", "") or "").strip()
        if str(language or "de").lower().startswith("en"):
            if completeness == "full_kind":
                prefix = "From the last config-bound inventory, these entries have host/IP data:"
            elif completeness in {"explicit_refs", "semantic_subset"}:
                prefix = "From the matching entries in the last config-bound inventory, I can reuse this host/IP data:"
            else:
                prefix = "I found candidate host/IP data in the last inventory, but I will not present it as complete:"
            row_lines = [
                f"- **{str(row.get('ref', '') or '').strip()}** ({str(row.get('kind', '') or '').strip() or '-'})"
                f": Host/IP `{str(row.get('host', '') or '').strip()}`"
                + (f"; title `{str(row.get('title', '') or '').strip()}`" if str(row.get("title", "") or "").strip() else "")
                for row in rows
            ]
        else:
            if completeness == "full_kind":
                prefix = "Aus dem letzten config-gebundenen Inventar haben diese Eintraege Host/IP-Daten:"
            elif completeness in {"explicit_refs", "semantic_subset"}:
                prefix = "Aus den passenden Eintraegen im letzten config-gebundenen Inventar kann ich diese Host/IP-Daten wiederverwenden:"
            else:
                prefix = "Ich habe Kandidaten fuer Host/IP-Daten im letzten Inventar, bezeichne sie aber nicht als vollstaendig:"
            row_lines = [
                f"- **{str(row.get('ref', '') or '').strip()}** ({str(row.get('kind', '') or '').strip() or '-'})"
                f": Host/IP `{str(row.get('host', '') or '').strip()}`"
                + (f"; Titel `{str(row.get('title', '') or '').strip()}`" if str(row.get("title", "") or "").strip() else "")
                for row in rows
            ]
        if selected_rows is not None:
            return "\n".join([prefix, *row_lines]), rows, selected_status or "reused_by_turn_contract"
        return "\n".join([prefix, *row_lines]), rows, "reused" if matching or not terms else "all_rows"

    @classmethod
    def _connection_evidence_subset_answer(
        cls,
        *,
        bundle: dict[str, Any],
        language: str | None,
        selected_rows: list[dict[str, Any]],
        selected_status: str,
    ) -> tuple[str, list[dict[str, Any]], str]:
        if str(bundle.get("surface", "") or "") != "connections":
            return "", [], "wrong_surface"
        if str(bundle.get("authority", "") or "") != "config":
            return "", [], "non_config_authority"
        rows = [
            dict(row)
            for row in list(selected_rows or [])
            if isinstance(row, dict) and str(row.get("ref", "") or "").strip()
        ]
        if not rows:
            return "", [], selected_status or "field_miss"
        is_exclusion = selected_status in {"reused_exclude_subset", "scope_review_exclude_subset"}
        if str(language or "de").lower().startswith("en"):
            prefix = (
                "From the last config-bound inventory, these entries remain after the exclusion:"
                if is_exclusion
                else "From the last config-bound inventory, these entries match the scoped follow-up:"
            )
            row_lines = [
                f"- **{str(row.get('ref', '') or '').strip()}** ({str(row.get('kind', '') or '').strip() or '-'})"
                + (f": title `{str(row.get('title', '') or '').strip()}`" if str(row.get("title", "") or "").strip() else "")
                + (f"; Host/IP `{str(row.get('host', '') or '').strip()}`" if str(row.get("host", "") or "").strip() else "")
                for row in rows
            ]
        else:
            prefix = (
                "Aus dem letzten config-gebundenen Inventar bleiben nach dem Ausschluss diese Eintraege uebrig:"
                if is_exclusion
                else "Aus dem letzten config-gebundenen Inventar passen diese Eintraege zur eingegrenzten Folgefrage:"
            )
            row_lines = [
                f"- **{str(row.get('ref', '') or '').strip()}** ({str(row.get('kind', '') or '').strip() or '-'})"
                + (f": Titel `{str(row.get('title', '') or '').strip()}`" if str(row.get("title", "") or "").strip() else "")
                + (f"; Host/IP `{str(row.get('host', '') or '').strip()}`" if str(row.get("host", "") or "").strip() else "")
                for row in rows
            ]
        return "\n".join([prefix, *row_lines]), rows, selected_status or "reused_subset"

    @staticmethod
    def _connection_evidence_subset_bundle(
        bundle: dict[str, Any],
        rows: list[dict[str, Any]],
        *,
        status: str,
    ) -> dict[str, Any]:
        if not isinstance(bundle, dict) or not bundle:
            return {}
        selected_rows = [dict(row) for row in rows if isinstance(row, dict)]
        if not selected_rows:
            return {}
        next_bundle = dict(bundle)
        selected_refs: list[str] = []
        selected_kinds: list[str] = []
        field_set: list[str] = []
        for row in selected_rows:
            ref = str(row.get("ref", "") or "").strip()
            kind = str(row.get("kind", "") or "").strip()
            if ref and ref not in selected_refs:
                selected_refs.append(ref)
            if kind and kind not in selected_kinds:
                selected_kinds.append(kind)
            for field in ("kind", "ref", "title", "host", "description", "group_name", "tags"):
                if row.get(field) and field not in field_set:
                    field_set.append(field)
        completeness = str(bundle.get("completeness", "") or "").strip() or "explicit_refs"
        if status in {"reused_narrow_subset", "scope_review_narrow_subset"}:
            completeness = "semantic_subset"
        elif status in {"reused_exclude_subset", "scope_review_exclude_subset"}:
            completeness = "semantic_subset"
        next_bundle.update(
            {
                "rows": selected_rows,
                "row_count": len(selected_rows),
                "row_refs": selected_refs,
                "selected_refs": selected_refs,
                "selected_kinds": selected_kinds,
                "field_set": field_set,
                "completeness": completeness,
                "semantic_scope_authority": "reviewed" if status.startswith("scope_review_") else bundle.get("semantic_scope_authority", "explicit_config"),
            }
        )
        return next_bundle

    @classmethod
    def _connection_evidence_scope_review_needed(
        cls,
        *,
        arbitration: AriaTurnArbitration | None,
        message: str,
        selected_status: str,
    ) -> bool:
        if arbitration is None:
            return False
        plan = arbitration.plan
        scope_operation = str(plan.scope_operation or "").strip()
        if selected_status == "surface_change":
            selected_surfaces = {
                str(item or "").strip()
                for item in [*list(plan.surfaces or ()), *list(plan.context_directions or ())]
                if str(item or "").strip() and str(item or "").strip() != "-"
            }
            if (
                str(plan.target_scope_authority or "").strip() == "last_turn_scope"
                and scope_operation == "surface_change"
                and (not selected_surfaces or selected_surfaces == {"connections"})
                and "context_inventory" in set(plan.intents or ())
            ):
                return True
            return False
        if selected_status in {"missing_subset_refs", "ambiguous_turn_scope"}:
            return True
        tokens = set(_tokenize_inventory_scope(message))
        has_exclusion_cue = bool(tokens & {"ausser", "except", "exclude", "excluding", "nicht", "non", "not", "ohne"})
        if selected_status == "reused_narrow_subset":
            return has_exclusion_cue
        if selected_status == "reused_exclude_subset":
            return False
        if scope_operation == "exclude_subset":
            return selected_status not in {"reused_exclude_subset"}
        if scope_operation == "narrow_subset":
            return True
        if scope_operation == "reuse_same_set" and (
            _query_requests_specific_connection_scope(message)
            or bool(cls._connection_evidence_query_terms(message))
        ):
            return True
        return False

    async def _review_connection_evidence_followup_scope(
        self,
        *,
        bundle: dict[str, Any],
        arbitration: AriaTurnArbitration | None,
        message: str,
        selected_status: str,
        source: str,
        user_id: str,
        request_id: str,
    ) -> tuple[list[dict[str, Any]], str, str]:
        if not self._connection_evidence_scope_review_needed(
            arbitration=arbitration,
            message=message,
            selected_status=selected_status,
        ):
            return [], "", "not_required"
        if arbitration is None:
            return [], "", "missing_turn_contract"
        rows = [
            dict(row)
            for row in list(bundle.get("rows", []) or [])
            if isinstance(row, dict) and str(row.get("ref", "") or "").strip()
        ]
        rows_with_hosts = [row for row in rows if str(row.get("host", "") or "").strip()]
        if not rows_with_hosts:
            return [], "", "no_host_rows"
        plan = arbitration.plan
        candidates = [
            {
                "ref": str(row.get("ref", "") or "").strip(),
                "kind": str(row.get("kind", "") or "").strip(),
                "title": str(row.get("title", "") or "").strip(),
                "host": str(row.get("host", "") or "").strip(),
                "description": str(row.get("description", "") or "").strip(),
                "group_name": str(row.get("group_name", "") or "").strip(),
                "tags": [str(tag) for tag in list(row.get("tags", []) or [])[:12]],
            }
            for row in rows_with_hosts
        ]
        result = await BoundedDecisionClient(getattr(self, "llm_client", None)).decide_json(
            operation=CONNECTION_EVIDENCE_SCOPE_REVIEW_OPERATION,
            system=(
                "You review an inventory follow-up against the last config-bound connection evidence. "
                "Use only the provided candidates and the user message. Decide whether the user asks for the same set, "
                "a semantic subset, an exclusion from the current set, or needs clarification. "
                "For subsets/exclusions, return only refs from candidates. Do not add refs. "
                'Return JSON only: {"operation":"reuse_same_set|narrow_subset|exclude_subset|clarify",'
                '"selected_refs":["..."],"excluded_refs":["..."],"empty_result_allowed":false,'
                '"confidence":"high|medium|low","reason":"short"}'
            ),
            payload={
                "message": str(message or "").strip(),
                "proposed_turn_contract": {
                    "target_scope_authority": str(plan.target_scope_authority or "").strip(),
                    "scope_operation": str(plan.scope_operation or "").strip(),
                    "priority": list(plan.priority or ())[:20],
                    "context_requests": [
                        {
                            "surface_id": request.surface_id,
                            "mode": request.mode,
                            "query": request.query,
                            "budget": dict(request.budget or {}),
                        }
                        for request in list(plan.context_requests or ())[:4]
                    ],
                },
                "last_evidence": {
                    "surface": str(bundle.get("surface", "") or "").strip(),
                    "authority": str(bundle.get("authority", "") or "").strip(),
                    "completeness": str(bundle.get("completeness", "") or "").strip(),
                    "row_count": int(bundle.get("row_count") or len(candidates)),
                    "candidates": candidates,
                },
                "rules": {
                    "config_metadata_authority": "Config proves refs and host fields.",
                    "scope_review_boundary": "The review may bind only a subset/exclusion of provided refs or ask for clarification.",
                    "empty_exclusion": "If the current set already consists only of the excluded group, an empty result is allowed.",
                },
            },
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return [], "", f"unavailable:{result.error or 'unknown'}"
        operation = str(result.payload.get("operation", "") or "").strip().lower()
        if operation not in {"reuse_same_set", "narrow_subset", "exclude_subset", "clarify"}:
            return [], "", "invalid_operation"
        confidence = str(result.payload.get("confidence", "") or "").strip().lower()
        if confidence not in {"high", "medium"}:
            return [], "", f"low_confidence:{confidence or '-'}"
        available = {str(row.get("ref", "") or "").strip(): row for row in rows_with_hosts}
        selected_refs = [
            str(ref or "").strip()
            for ref in list(result.payload.get("selected_refs", []) or [])
            if str(ref or "").strip() in available
        ]
        excluded_refs = [
            str(ref or "").strip()
            for ref in list(result.payload.get("excluded_refs", []) or [])
            if str(ref or "").strip() in available
        ]
        reason = " ".join(str(result.payload.get("reason", "") or "").strip().split())[:120] or "-"
        debug = (
            "Routing Debug: connection_evidence_scope_review "
            f"operation={operation} confidence={confidence} selected={','.join(selected_refs) or '-'} "
            f"excluded={','.join(excluded_refs) or '-'} reason={reason}"
        )
        if operation == "reuse_same_set":
            return rows_with_hosts, "scope_review_reuse_same_set", debug
        if operation == "narrow_subset":
            if not selected_refs:
                return [], "", f"{debug} outcome=no_selected_refs"
            return [available[ref] for ref in selected_refs], "scope_review_narrow_subset", debug
        if operation == "exclude_subset":
            refs_to_exclude = set(excluded_refs or selected_refs)
            if not refs_to_exclude:
                return [], "", f"{debug} outcome=no_excluded_refs"
            rows_after_exclusion = [row for row in rows_with_hosts if str(row.get("ref", "") or "").strip() not in refs_to_exclude]
            if rows_after_exclusion:
                return rows_after_exclusion, "scope_review_exclude_subset", debug
            if bool(result.payload.get("empty_result_allowed")):
                return [], "scope_review_exclude_subset_empty", debug
            return [], "", f"{debug} outcome=empty_not_allowed"
        return [], "", f"{debug} outcome=clarify"

    @staticmethod
    def _connection_evidence_empty_exclusion_answer(*, language: str | None) -> str:
        if str(language or "de").lower().startswith("en"):
            return "None of the entries in the last scoped inventory remain after excluding that group."
        return "Keine der zuletzt eingegrenzten Verbindungen bleibt uebrig, wenn ich diese Gruppe ausschliesse."

    async def _aria_turn_last_evidence_followup_result(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        language: str | None,
        start: float,
        aria_turn_arbitration: AriaTurnArbitration | None,
        detail_lines: list[str] | None = None,
        last_frame_payload: dict[str, Any] | None = None,
    ) -> PipelineResult | None:
        frame = last_frame_payload if isinstance(last_frame_payload, dict) else self._aria_turn_last_frame_payload(user_id)
        bundle = frame.get("evidence_bundle") if isinstance(frame, dict) else None
        if not isinstance(bundle, dict) or not bundle:
            return None
        selected_rows, status = self._connection_evidence_rows_for_turn_contract(
            bundle=bundle,
            arbitration=aria_turn_arbitration,
            message=message,
        )
        review_debug = ""
        reviewed_rows, reviewed_status, review_debug = await self._review_connection_evidence_followup_scope(
            bundle=bundle,
            arbitration=aria_turn_arbitration,
            message=message,
            selected_status=status,
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if reviewed_status:
            selected_rows = reviewed_rows
            status = reviewed_status
        if not selected_rows:
            if status == "scope_review_exclude_subset_empty":
                duration_ms = int((time.perf_counter() - start) * 1000)
                usage_snapshot = self._current_usage_snapshot()
                usage = dict(usage_snapshot.get("usage", {}) or {})
                await self.token_tracker.log(
                    request_id=request_id,
                    user_id=user_id,
                    intents=["context_inventory"],
                    router_level=2,
                    usage=usage,
                    chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
                    embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
                    embedding_usage=dict(usage_snapshot.get("embedding_usage", {}) or {}),
                    chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
                    embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
                    total_cost_usd=usage_snapshot.get("total_cost_usd"),
                    duration_ms=duration_ms,
                    source=source,
                    skill_errors=[],
                    extraction_model="evidence_bundle_followup",
                    extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                )
                return PipelineResult(
                    request_id=request_id,
                    text=self._connection_evidence_empty_exclusion_answer(language=language),
                    usage=usage,
                    intents=["context_inventory"],
                    skill_errors=[],
                    router_level=2,
                    duration_ms=duration_ms,
                    chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
                    embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
                    total_cost_usd=usage_snapshot.get("total_cost_usd"),
                    safe_fix_plan=[],
                    detail_lines=[
                        *list(detail_lines or []),
                        *([review_debug] if review_debug else []),
                        "Routing Debug: evidence_bundle reused "
                        f"surface=connections authority={bundle.get('authority') or '-'} "
                        f"completeness={bundle.get('completeness') or '-'} "
                        f"fields={','.join(list(bundle.get('field_set', []) or [])) or '-'} "
                        f"rows={int(bundle.get('row_count') or 0)} matched=0 status={status}",
                        "Routing Debug: answerability "
                        f"surface=connections completeness={bundle.get('completeness') or '-'} "
                        "authority=config field=host decision=answer_from_last_evidence_bundle_empty",
                        "Routing Debug: direct_context_answer kind=evidence_bundle_followup reason=last_turn_field_reuse",
                    ],
                )
            if detail_lines is not None:
                detail_lines.append(
                    "Routing Debug: evidence_bundle_followup rejected "
                    f"surface={bundle.get('surface') or '-'} completeness={bundle.get('completeness') or '-'} reason={status}"
                )
            plan = aria_turn_arbitration.plan if aria_turn_arbitration is not None else None
            if (
                plan is not None
                and str(plan.target_scope_authority or "").strip() == "last_turn_scope"
                and status in {"missing_scope_operation", "not_inventory_contract", "missing_connections_inventory_request"}
            ):
                duration_ms = int((time.perf_counter() - start) * 1000)
                usage_snapshot = self._current_usage_snapshot()
                usage = dict(usage_snapshot.get("usage", {}) or {})
                await self.token_tracker.log(
                    request_id=request_id,
                    user_id=user_id,
                    intents=["context_inventory"],
                    router_level=2,
                    usage=usage,
                    chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
                    embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
                    embedding_usage=dict(usage_snapshot.get("embedding_usage", {}) or {}),
                    chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
                    embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
                    total_cost_usd=usage_snapshot.get("total_cost_usd"),
                    duration_ms=duration_ms,
                    source=source,
                    skill_errors=[],
                    extraction_model="evidence_bundle_followup_blocked",
                    extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                )
                text = self._pipeline_text(
                    language,
                    "direct_context.evidence_followup_scope_unclear",
                    "Ich kann diese Folgefrage nicht sauber aus dem letzten Inventar beantworten, weil der Scope-Vertrag fehlt. Bitte frage die Liste mit eindeutigem Scope erneut an.",
                )
                return PipelineResult(
                    request_id=request_id,
                    text=text,
                    usage=usage,
                    intents=["context_inventory"],
                    skill_errors=[],
                    router_level=2,
                    duration_ms=duration_ms,
                    chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
                    embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
                    total_cost_usd=usage_snapshot.get("total_cost_usd"),
                    safe_fix_plan=[],
                    detail_lines=[
                        *list(detail_lines or []),
                        "Routing Debug: evidence_bundle_followup blocked "
                        f"surface={bundle.get('surface') or '-'} reason={status} boundary=scope_contract",
                    ],
                )
            return None
        subset_statuses = {
            "reused_exclude_subset",
            "scope_review_exclude_subset",
            "reused_narrow_subset",
            "scope_review_narrow_subset",
        }
        answer_field = "host"
        answer_decision = "answer_from_last_evidence_bundle"
        answer_reason = "last_turn_field_reuse"
        if status in subset_statuses and not _query_requests_network_address(message):
            text, rows, status = self._connection_evidence_subset_answer(
                bundle=bundle,
                language=language,
                selected_rows=selected_rows,
                selected_status=status,
            )
            answer_field = "ref"
            answer_decision = "answer_from_last_evidence_bundle_subset"
            answer_reason = "last_turn_scope_subset"
        else:
            text, rows, status = self._connection_evidence_host_ip_answer(
                bundle=bundle,
                message=message,
                language=language,
                selected_rows=selected_rows,
                selected_status=status,
            )
        if not text:
            if detail_lines is not None:
                detail_lines.append(
                    "Routing Debug: evidence_bundle_followup rejected "
                    f"surface={bundle.get('surface') or '-'} completeness={bundle.get('completeness') or '-'} reason={status}"
                )
            return None
        duration_ms = int((time.perf_counter() - start) * 1000)
        usage_snapshot = self._current_usage_snapshot()
        usage = dict(usage_snapshot.get("usage", {}) or {})
        next_bundle = self._connection_evidence_subset_bundle(bundle, rows, status=status) or bundle
        self._remember_aria_turn_evidence_bundle(next_bundle, user_id=user_id)
        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=["context_inventory"],
            router_level=2,
            usage=usage,
            chat_model=str(usage_snapshot.get("chat_model", "") or self.settings.llm.model),
            embedding_model=str(usage_snapshot.get("embedding_model", "") or self.settings.embeddings.model),
            embedding_usage=dict(usage_snapshot.get("embedding_usage", {}) or {}),
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            duration_ms=duration_ms,
            source=source,
            skill_errors=[],
            extraction_model="evidence_bundle_followup",
            extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
        )
        return PipelineResult(
            request_id=request_id,
            text=text,
            usage=usage,
            intents=["context_inventory"],
            skill_errors=[],
            router_level=2,
            duration_ms=duration_ms,
            chat_cost_usd=usage_snapshot.get("chat_cost_usd"),
            embedding_cost_usd=usage_snapshot.get("embedding_cost_usd"),
            total_cost_usd=usage_snapshot.get("total_cost_usd"),
            safe_fix_plan=[],
            detail_lines=[
                *list(detail_lines or []),
                *([review_debug] if review_debug else []),
                "Routing Debug: evidence_bundle reused "
                f"surface=connections authority={bundle.get('authority') or '-'} "
                f"completeness={bundle.get('completeness') or '-'} "
                f"fields={','.join(list(bundle.get('field_set', []) or [])) or '-'} "
                f"rows={int(bundle.get('row_count') or 0)} matched={len(rows)} status={status}",
                "Routing Debug: evidence_bundle stored "
                f"surface={next_bundle.get('surface') or '-'} authority={next_bundle.get('authority') or '-'} "
                f"completeness={next_bundle.get('completeness') or '-'} rows={int(next_bundle.get('row_count') or 0)}",
                "Routing Debug: answerability "
                f"surface=connections completeness={bundle.get('completeness') or '-'} "
                f"authority=config field={answer_field} decision={answer_decision}",
                f"Routing Debug: direct_context_answer kind=evidence_bundle_followup reason={answer_reason}",
            ],
        )

    async def _arbitrate_aria_turn(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        language: str | None,
        runtime_recipes: list[dict[str, Any]],
        recent_history: list[dict[str, Any]] | None = None,
    ) -> AriaTurnArbitration | None:
        menu = await self._build_aria_turn_menu(user_id=user_id, runtime_recipes=runtime_recipes)
        surface_registry = build_builtin_surface_registry(self.settings)
        turn_context = {
            "semantic_contract": "qdrant_meta_catalog_first_with_legacy_fallback",
            "last_turn_frame": self._aria_turn_last_frame_payload(user_id),
            "recent_visible_chat_context": compact_recent_visible_chat_context(recent_history),
        }
        meta_arbitration = await MetaCatalogRouter(
            settings=self.settings,
            embedding_client=self.embedding_client,
            llm_client=self.llm_client,
            config=MetaCatalogRoutingConfig(
                strict_contract_enabled=bool(
                    getattr(getattr(self.settings, "routing", object()), "meta_catalog_strict_contract_enabled", True)
                )
            ),
        ).route(
            MetaCatalogRoutingInput(
                message=message,
                menu=menu,
                surface_registry=surface_registry,
                language=language,
                turn_context=turn_context,
                source="pipeline",
                user_id=user_id,
                request_id=request_id,
            )
        )
        self._last_meta_catalog_fallback_debug_lines = []
        if meta_arbitration.source != "fallback":
            self._remember_aria_turn_frame(meta_arbitration, user_id=user_id)
            return meta_arbitration
        self._last_meta_catalog_fallback_debug_lines = [
            "Routing Debug: meta_catalog_contract phase=backup_fallback "
            f"legacy_semantics=enabled reason={meta_arbitration.plan.reason or 'fallback'}"
            + (f" error={meta_arbitration.error}" if meta_arbitration.error else "")
        ]
        arbitration = await AriaTurnArbiter(self.llm_client).arbitrate(
            message=message,
            menu=menu,
            surface_registry=surface_registry,
            language=language,
            turn_context=turn_context,
            source="pipeline",
            user_id=user_id,
            request_id=request_id,
        )
        if arbitration.source == "fallback":
            return None
        self._remember_aria_turn_frame(arbitration, user_id=user_id)
        return arbitration

    def _remember_aria_turn_frame(
        self,
        arbitration: AriaTurnArbitration | None,
        *,
        user_id: str,
    ) -> None:
        self._agentic_context_runtime_state().remember_frame(arbitration, user_id=user_id)

    async def _recall_active_learning_hints(
        self,
        message: str,
        *,
        user_id: str,
    ) -> list[dict[str, str]]:
        return await recall_active_learning_hints(self.memory_skill, message, user_id=user_id)

    def _should_skip_active_learning_hints_for_turn(self, message: str) -> bool:
        return should_skip_active_learning_hints_for_turn(
            message,
            available_connection_kinds=self._capability_routing_connection_pools(),
        )

    async def _classify_routing_agentic(
        self,
        message: str,
        *,
        keyword_decision: RouterDecision,
        language: str | None = None,
        user_id: str = "",
        request_id: str = "",
        source: str = "pipeline",
    ) -> RouterDecision:
        intents = [str(intent or "").strip().lower() for intent in list(keyword_decision.intents or [])]
        active_learning_hints = []
        if "web_search" not in intents and not self._should_skip_active_learning_hints_for_turn(message):
            active_learning_hints = await self._recall_active_learning_hints(message, user_id=user_id)
        self._last_active_learning_hints = active_learning_hints
        arbitration = await TurnIntentArbiter(self.llm_client).arbitrate(
            message=message,
            keyword_decision=keyword_decision,
            language=language,
            available_intents=self._available_turn_intents(),
            source=source,
            user_id=user_id,
            request_id=request_id,
            active_learning_hints=active_learning_hints,
        )
        return arbitration.decision
