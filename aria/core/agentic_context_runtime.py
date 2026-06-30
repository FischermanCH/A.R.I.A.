from __future__ import annotations

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
from aria.core.context_answer_runtime import compose_aria_context_answer
from aria.core.context_answer_runtime import docs_search_fallback_answer
from aria.core.context_answer_runtime import fast_docs_search_answer
from aria.core.context_answer_runtime import fast_inventory_list_answer
from aria.core.context_answer_runtime import fast_notes_inventory_answer
from aria.core.connection_catalog import connection_kind_label
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.chat_turn_context import compact_recent_visible_chat_context
from aria.core.chat_freshness import explicitly_requests_web_research
from aria.core.context_evidence import common_request_terms
from aria.core.context_evidence import evidence_terms
from aria.core.context_evidence import inventory_matches
from aria.core.context_evidence import inventory_query_terms
from aria.core.context_evidence import inventory_soft_scope_terms
from aria.core.context_evidence import normalized_evidence_text
from aria.core.context_evidence import request_scope_terms
from aria.core.context_evidence import text_matches_evidence
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
from aria.core.turn_intent_arbitration import TurnIntentArbiter
from aria.skills.base import SkillResult


_AGENTIC_CONTEXT_RUNTIME_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


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
        if "web_research" in plan.intents and "web_search" not in merged:
            merged.append("web_search")
        if "learning_feedback" in plan.intents and "memory_recall" not in merged:
            merged.append("memory_recall")
        if "chat" in merged and len(merged) > 1 and "local_retrieval" not in plan.intents:
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

    def _aria_turn_context_overrides(self, arbitration: AriaTurnArbitration | None, *, user_id: str = "web") -> dict[str, Any]:
        if arbitration is None:
            return {}
        plan = arbitration.plan
        if "local_retrieval" not in plan.intents:
            return {}
        selected = [str(collection or "").strip() for collection in plan.collections if str(collection or "").strip()]
        memory_like: list[str] = []
        request_surfaces = {request.surface_id for request in plan.context_requests}
        include_documents = "docs" in plan.context_directions or "docs" in request_surfaces
        docs_only = bool("docs" in plan.context_directions or "docs" in request_surfaces)
        document_corpus_scope = any(str(item or "").strip() == "local|docs|documents" for item in plan.priority)
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
            if plan.context_depth == "deep" or document_corpus_scope:
                overrides["document_corpus_scan"] = True
        if len(document_ids) >= 2 or any(request.mode == "inventory" and request.surface_id == "docs" for request in plan.context_requests):
            overrides["document_inventory"] = True
            overrides["document_ids"] = document_ids
            overrides["document_names"] = document_names
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
            if isinstance(sources, list):
                context_sources += len(sources)
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
        topic_terms, ignored_terms = self._aria_turn_topic_terms_for_request(query, request)
        filtered: list[dict[str, Any]] = []
        rejected = 0
        for hit in hits:
            payload = dict(hit.get("payload", {}) or {})
            evidence_text = " ".join(
                str(value or "")
                for value in (
                    payload.get("title", ""),
                    payload.get("description", ""),
                    payload.get("group_name", ""),
                    " ".join(str(tag) for tag in list(payload.get("tags", []) or [])),
                    " ".join(str(alias) for alias in list(payload.get("aliases", []) or [])),
                )
            )
            if not topic_terms or self._aria_turn_text_matches_evidence(query, evidence_text, ignored_terms=ignored_terms):
                filtered.append(hit)
            else:
                rejected += 1
            if len(filtered) >= max(1, int(limit or 1)):
                break
        return filtered, [
            "Routing Debug: evidence_filter "
            f"surface={request.surface_id} kept={len(filtered)} rejected={rejected} "
            f"terms={','.join(topic_terms) or '-'}"
        ]

    def _aria_turn_format_inventory_metadata(self, surface_id: str, metadata: dict[str, Any], query: str, *, limit: int = 50) -> tuple[str, list[dict[str, Any]]]:
        if not metadata:
            return "No inventory metadata is available for the selected surface.", []
        rows: list[str] = []
        sources: list[dict[str, Any]] = []
        configured = metadata.get("configured")
        if isinstance(configured, dict):
            request = ContextRequest(surface_id=surface_id, mode="inventory", query=query, limit=limit)
            query_terms, _ignored_terms = self._aria_turn_topic_terms_for_request(query, request)
            for kind in sorted(configured):
                entry = dict(configured.get(kind) or {})
                refs = [str(ref or "").strip() for ref in list(entry.get("configured_refs") or []) if str(ref or "").strip()]
                summaries = [dict(item or {}) for item in list(entry.get("safe_summaries") or []) if isinstance(item, dict)]
                kind_text = f"{kind} {entry.get('label') or ''} {entry.get('config_page') or ''}"
                kind_only_query = bool(query_terms) and any(term in kind_text.lower() for term in query_terms)
                matching_summaries: list[dict[str, Any]] = []
                for summary in summaries:
                    item_text = " ".join(
                        str(value or "")
                        for key, value in summary.items()
                        if key not in {"url", "host", "password", "token", "secret", "api_key", "key_path"}
                    )
                    item_haystack = f"{kind} {item_text}".lower()
                    if not query_terms or any(term in item_haystack for term in query_terms):
                        matching_summaries.append(summary)
                if query_terms and not kind_only_query and not matching_summaries:
                    continue
                visible_summaries = summaries if kind_only_query or not query_terms else matching_summaries
                matched_refs = [
                    str(summary.get("ref") or "").strip()
                    for summary in visible_summaries
                    if str(summary.get("ref") or "").strip()
                ]
                if query_terms and not kind_only_query:
                    refs_for_header = matched_refs
                    match_note = f"{len(visible_summaries)} matching of {len(summaries) or len(refs)} configured"
                else:
                    refs_for_header = refs
                    match_note = f"{len(refs)} configured"
                label = str(entry.get("label") or kind).strip() or kind
                rows.append(f"{label} ({kind}): {match_note}; refs: {', '.join(refs_for_header[:limit]) or '-'}")
                for summary in visible_summaries[:limit]:
                    ref = str(summary.get("ref") or "").strip()
                    details = ", ".join(
                        part
                        for part in (
                            str(summary.get("title") or "").strip(),
                            str(summary.get("description") or "").strip(),
                            f"group={str(summary.get('group_name') or '').strip()}" if str(summary.get("group_name") or "").strip() else "",
                            f"tags={','.join(str(tag) for tag in list(summary.get('tags') or [])[:6])}" if isinstance(summary.get("tags"), list) else "",
                        )
                        if part
                    )
                    if details:
                        rows.append(f"- {kind}/{ref}: {details}")
                truncated = max(0, len(visible_summaries) - min(len(visible_summaries), limit))
                if truncated:
                    rows.append(f"- {kind}: {truncated} weitere passende Eintraege nicht im Antwortkontext geladen (limit={limit}).")
                sources.append({"surface": surface_id, "kind": kind, "refs": refs_for_header[: max(20, limit)]})
        if not rows and not isinstance(configured, dict):
            text = str(metadata)
            if AgenticContextRuntimeMixin._aria_turn_inventory_matches(query, text):
                rows.append(f"{surface_id} inventory metadata: {metadata}")
                sources.append({"surface": surface_id})
        if not rows:
            return "No matching inventory metadata was found for the selected query.", []
        return "Configured inventory:\n" + "\n".join(rows[:60]), sources

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
        if request.surface_id == "docs":
            doc_sources = [
                source
                for source in sources
                if str(source.get("type", "") or "").strip().lower() == "document"
                or str(source.get("collection", "") or "").strip().lower().startswith("aria_docs_")
            ]
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
        source_keys: set[tuple[str, str, tuple[str, ...]]] = set()
        for result in inventory_results:
            content = str(result.content or "").strip()
            if content and content not in contents:
                contents.append(content)
            meta = dict(result.metadata or {})
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
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content="\n\n".join(contents),
            metadata={
                "sources": sources,
                "detail_lines": [
                    *detail_lines,
                    f"Routing Debug: inventory_merge results={len(inventory_results)} sources={len(sources)}",
                ],
            },
        )

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
        text = ""
        inventory_result = self._aria_turn_merge_inventory_results(skill_results)
        if inventory_result is not None and "context_inventory" in plan.intents and "web_research" not in plan.intents:
            direct_kind = "inventory"
            content = str(inventory_result.content or "").strip()
            has_sources = self._aria_turn_result_has_sources(inventory_result)
            if not has_sources:
                text = self._pipeline_text(language, "direct_context.inventory_empty", "I found no matching entries in the selected inventory.")
            elif str(language or "de").lower().startswith("en"):
                text = f"I found matching configured sources:\n{content}"
            else:
                text = f"Ich habe passende konfigurierte Quellen gefunden:\n{content}"
            fast_inventory_text = fast_inventory_list_answer(inventory_result, language=language) if has_sources else ""
            if fast_inventory_text:
                text = fast_inventory_text
                composer_usage = {}
                composer_debug = "Routing Debug: answer_composer skipped reason=fast_inventory_list_answer"
            else:
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
            if local_search_request is not None and plan.answer_mode == "direct_answer":
                memory_result = next((result for result in skill_results if result.skill_name == "memory_recall" and result.success), None)
                if (
                    memory_result is not None
                    and self._aria_turn_has_loaded_local_context([memory_result])
                    and self._aria_turn_local_search_has_evidence(local_search_request, memory_result)
                ):
                    direct_kind = f"{local_search_request.surface_id}_search"
                    content = str(memory_result.content or "").strip()
                    if str(language or "de").lower().startswith("en"):
                        label = "documents" if local_search_request.surface_id == "docs" else "memory"
                        text = f"I found this in your {label}:\n{content}"
                    elif local_search_request.surface_id == "docs":
                        text = f"In deinen Dokumenten habe ich dazu gefunden:\n{content}"
                    else:
                        text = f"In deinem Memory habe ich dazu gefunden:\n{content}"
                    fast_docs_text = (
                        self._aria_turn_fast_docs_search_answer(arbitration, memory_result, language=language)
                        if local_search_request.surface_id == "docs"
                        else ""
                    )
                    if fast_docs_text:
                        text = fast_docs_text
                        composer_usage = {}
                        composer_debug = "Routing Debug: answer_composer skipped reason=fast_docs_search_answer"
                    else:
                        docs_fallback_text = (
                            self._aria_turn_docs_search_fallback_answer(arbitration, memory_result, language=language)
                            if local_search_request.surface_id == "docs"
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
        for result in skill_results:
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
                *([composer_debug] if composer_debug else []),
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
        for result in skill_results:
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
                "Routing Debug: local_context_empty "
                f"directions={selected_directions} collections={selected_collections} "
                f"boundary=guardrail reason={'no_evidence_sources' if (notes_only_without_evidence or local_search_without_evidence) else 'no_loaded_sources'}",
            ],
        )

    @staticmethod
    def _aria_turn_uses_meta_catalog_contract(arbitration: AriaTurnArbitration | None) -> bool:
        return arbitration is not None and arbitration.source in {META_CATALOG_ROUTING_OPERATION, "runtime_task_contract"}

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

    def _aria_turn_seed_capability_draft(self, arbitration: AriaTurnArbitration | None) -> CapabilityDraft | None:
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
        if any(action_item.lower() in ssh_actions for action_item in clean_actions) and selected_by_kind.get("ssh"):
            action = next(action_item for action_item in clean_actions if action_item.lower() in ssh_actions)
            kind = "ssh"
            ref = selected_by_kind["ssh"][0]
            selected_connections = tuple(("ssh", item_ref) for item_ref in selected_by_kind["ssh"])
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
        capability = self._aria_turn_action_capability(action, kind)
        if not capability:
            return None
        if capability == "ssh_command" and selected_by_kind.get("ssh"):
            selected_connections = tuple(("ssh", item_ref) for item_ref in selected_by_kind["ssh"])
            kind = "ssh"
            if len(selected_connections) > 1:
                ref = ""
        selected_kinds = {item_kind for item_kind, _item_ref in selected_connections if item_kind}
        multi_target = len(selected_connections) > 1 and (not selected_kinds or len(selected_kinds) == 1)
        connection_refs = [
            item_ref
            for item_kind, item_ref in selected_connections
            if item_kind and item_ref and (not selected_kinds or item_kind in selected_kinds)
        ]
        if multi_target:
            kind = next(iter(selected_kinds), kind)
            ref = ""
        query = next((request.query for request in plan.context_requests if str(request.query or "").strip()), "")
        path = ""
        content = ""
        if capability in {"file_list", "file_read", "file_write", "calendar_read", "api_request", "mqtt_publish"}:
            path = str(query or "").strip()
        if capability in {"webhook_send", "discord_send", "email_send", "mail_search", "mqtt_publish", "file_write"}:
            content = str(query or "").strip()
        if capability in {"website_read", "feed_read"}:
            content = str(query or "").strip()
        notes = [
            f"capability_draft_source:{'meta_catalog' if self._aria_turn_uses_meta_catalog_contract(arbitration) else 'legacy_backup'}",
            f"turn_contract_source:{arbitration.source}",
            f"turn_contract_actions:{','.join(plan.actions)}",
            f"turn_contract_priority:{','.join(plan.priority)}",
        ]
        if multi_target:
            notes.append("target_scope:multi_target")
            notes.append(f"turn_contract_target_refs:{','.join(connection_refs)}")
        return CapabilityDraft(
            capability=capability,
            connection_kind=kind,
            explicit_connection_ref=ref,
            path=path,
            content="" if capability == "ssh_command" else content,
            confidence=max(0.62, float(plan.confidence or 0.0)),
            connection_refs=connection_refs if multi_target else [],
            notes=notes,
        )

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
        if plan.actions or plan.needs_confirmation or "web_research" in plan.intents:
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
            override_factory = getattr(self, "_runtime_task_arbitration_override", None)
            if callable(override_factory):
                override = await override_factory(
                    message=message,
                    user_id=user_id,
                    request_id=request_id,
                    language=language,
                    meta_arbitration=meta_arbitration,
                )
                if override is not None:
                    self._remember_aria_turn_frame(override, user_id=user_id)
                    return override
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

    def _remember_aria_turn_frame(self, arbitration: AriaTurnArbitration | None, *, user_id: str) -> None:
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
        if intents == ["recipe_status"]:
            self._last_active_learning_hints = []
            return keyword_decision
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
