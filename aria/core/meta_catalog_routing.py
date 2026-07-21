from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from aria.core.aria_turn_arbitration import ANSWER_MODES
from aria.core.aria_turn_arbitration import ARIA_TURN_INTENTS
from aria.core.aria_turn_arbitration import CONTEXT_DEPTHS
from aria.core.aria_turn_arbitration import EVIDENCE_POLICIES
from aria.core.aria_turn_arbitration import META_CONTRACT_MODES
from aria.core.aria_turn_arbitration import RISK_LEVELS
from aria.core.aria_turn_arbitration import SCOPE_OPERATIONS
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnMenu
from aria.core.aria_turn_arbitration import AriaTurnPlan
from aria.core.aria_turn_arbitration import _fallback_plan
from aria.core.aria_turn_arbitration import _unique_clean
from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.chat_turn_context import semantic_query_with_visible_chat_context
from aria.core.chat_turn_context import visible_chat_context_from_turn_context
from aria.core.context_surfaces import ContextRequest
from aria.core.context_surfaces import SurfaceRegistry
from aria.core.doc_meta_catalog import DocumentMetaCatalogStore, document_meta_collection_for_user
from aria.core.llm_input_contract import build_llm_input_contract
from aria.core.llm_input_contract import llm_input_contract_diagnostics
from aria.core.meta_catalog import MetaCatalogStore
from aria.core.meta_catalog import create_meta_catalog_qdrant_client
from aria.core.meta_catalog import meta_catalog_collection_name


META_CATALOG_ROUTING_OPERATION = "aria_meta_catalog_routing"
TARGET_SCOPE_AUTHORITIES = ("full_kind", "explicit_refs", "semantic_group", "last_turn_scope", "priority_sample")


@dataclass(frozen=True, slots=True)
class MetaCatalogRoutingConfig:
    candidate_limit: int = 16
    score_threshold: float = 0.0
    min_confidence: float = 0.62
    strict_contract_enabled: bool = True


@dataclass(frozen=True, slots=True)
class MetaCatalogRoutingInput:
    message: str
    menu: AriaTurnMenu
    surface_registry: SurfaceRegistry | None = None
    language: str | None = None
    turn_context: dict[str, Any] | None = None
    source: str = "pipeline"
    user_id: str = ""
    request_id: str = ""


@dataclass(frozen=True, slots=True)
class MetaCatalogRoutingTrace:
    hits: tuple[dict[str, Any], ...] = ()
    selected_catalog_ids: tuple[str, ...] = ()
    rejected_catalog_ids: tuple[str, ...] = ()
    error: str = ""
    usage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MetaCatalogSurfaceReviewOutcome:
    selected_catalog_ids: tuple[str, ...]
    requested_surfaces: tuple[str, ...]
    context_requests: tuple[ContextRequest, ...]
    block_reason: str = ""


def _compact_meta_hit(hit: dict[str, Any]) -> dict[str, Any]:
    payload = dict(hit.get("payload", {}) or {})
    return {
        "catalog_id": str(payload.get("catalog_id", "") or hit.get("catalog_id", "") or "").strip(),
        "entity_type": str(payload.get("entity_type", "") or "").strip(),
        "surface_id": str(payload.get("surface_id", "") or "").strip(),
        "kind": str(payload.get("kind", "") or "").strip(),
        "ref": str(payload.get("ref", "") or "").strip(),
        "title": str(payload.get("title", "") or "").strip()[:140],
        "description": str(payload.get("description", "") or "").strip()[:220],
        "document_id": str(payload.get("document_id", "") or "").strip(),
        "document_name": str(payload.get("document_name", "") or "").strip()[:220],
        "target_collection": str(payload.get("target_collection", "") or "").strip(),
        "group_name": str(payload.get("group_name", "") or "").strip()[:80],
        "knows": list(payload.get("knows", []) or [])[:8],
        "can_load": list(payload.get("can_load", []) or [])[:6],
        "can_do": list(payload.get("can_do", []) or [])[:6],
        "action_candidates": list(payload.get("action_candidates", []) or [])[:5],
        "loader_contract": str(payload.get("loader_contract", "") or "").strip()[:160],
        "executor_contract": str(payload.get("executor_contract", "") or "").strip()[:160],
        "risk_hint": str(payload.get("risk_hint", "") or "").strip(),
        "confirmation_policy": str(payload.get("confirmation_policy", "") or "").strip(),
        "score": float(hit.get("score", 0.0) or 0.0),
    }


def _as_sequence(value: Any) -> list[Any]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return list(value)
    return []


def _compact_last_turn_frame(turn_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(turn_context, dict):
        return {}
    frame = turn_context.get("last_turn_frame")
    if not isinstance(frame, dict):
        return {}
    return {
        "surface_id": str(frame.get("surface_id", "") or "").strip(),
        "mode": str(frame.get("mode", "") or "").strip(),
        "topic": " ".join(str(frame.get("topic", "") or "").split())[:180],
        "catalog_ids": list(frame.get("catalog_ids", []) or [])[:8] if isinstance(frame.get("catalog_ids"), list | tuple) else [],
        "evidence_policy": str(frame.get("evidence_policy", "") or "").strip(),
        "answer_mode": str(frame.get("answer_mode", "") or "").strip(),
        "evidence_bundle": _compact_evidence_bundle(frame.get("evidence_bundle")),
        "confidence": frame.get("confidence", 0.0),
    }


def _compact_evidence_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict) or not bundle:
        return {}
    return {
        "surface": str(bundle.get("surface", "") or "").strip(),
        "authority": str(bundle.get("authority", "") or "").strip(),
        "completeness": str(bundle.get("completeness", "") or "").strip(),
        "scope_contract": str(bundle.get("scope_contract", "") or "").strip(),
        "field_set": list(bundle.get("field_set", []) or [])[:12] if isinstance(bundle.get("field_set"), list | tuple) else [],
        "row_count": int(bundle.get("row_count") or 0),
        "selected_kinds": list(bundle.get("selected_kinds", []) or [])[:12]
        if isinstance(bundle.get("selected_kinds"), list | tuple)
        else [],
        "selected_refs": list(bundle.get("selected_refs", []) or [])[:12]
        if isinstance(bundle.get("selected_refs"), list | tuple)
        else [],
    }


def _explicit_local_surface(message: str) -> str:
    text = f" {str(message or '').strip().lower()} "
    if any(term in text for term in (" dokument", " dokumente", " dokumenten", " documents ", " docs ")):
        return "docs"
    if any(term in text for term in (" notiz", " notizen", " notes ")):
        return "notes"
    if any(
        term in text
        for term in (
            " mein memory",
            " meinem memory",
            " meinen memory",
            " in memory",
            " im memory",
            " aria memory",
            " erinnerung",
            " erinnerungen",
            " gespeicherte erinnerungen",
        )
    ):
        return "memory"
    return ""


def _catalog_match_tokens(text: str) -> set[str]:
    stop = {
        "ich", "mir", "mein", "meine", "meinen", "meinem", "wie", "was", "wo", "wer",
        "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine",
        "einen", "einem", "ans", "zur", "zum", "in", "im", "am", "an", "auf", "mit",
        "for", "the", "and", "how", "what", "where", "my", "your", "you",
    }
    return {
        token
        for token in re.findall(r"(?u)\b[\w][\w-]{2,}\b", str(text or "").lower())
        if token not in stop
    }


def _hit_search_text(hit: dict[str, Any]) -> str:
    payload = dict(hit.get("payload", {}) or {})
    parts: list[str] = []
    for key in ("title", "description", "group_name", "ref", "document_name", "text", "loader_contract"):
        parts.append(str(payload.get(key, "") or hit.get(key, "") or ""))
    for key in ("aliases", "tags", "knows", "can_load"):
        value = payload.get(key, hit.get(key, []))
        if isinstance(value, list | tuple | set):
            parts.extend(str(item) for item in value)
    return " ".join(parts)


def _catalog_lexical_overlap(query: str, hit: dict[str, Any]) -> int:
    query_tokens = _catalog_match_tokens(query)
    if not query_tokens:
        return 0
    hit_tokens = _catalog_match_tokens(_hit_search_text(hit))
    return len(query_tokens & hit_tokens)


def _router_acknowledges_connection_evidence(router_payload: dict[str, Any], selected_catalog_ids: tuple[str, ...]) -> bool:
    raw_ids = [
        str(item or "").strip()
        for item in _as_sequence(router_payload.get("catalog_ids") or router_payload.get("catalog_id"))
    ]
    if any(item.startswith("connection|") or item == "surface|connections" for item in [*raw_ids, *selected_catalog_ids]):
        return True
    reason = str(router_payload.get("reason", "") or "").strip().lower()
    if not reason:
        return False
    has_connection_kind = bool(re.search(r"\b(?:connection|connections|verbindung|verbindungen|ssh|sftp|smb|rss|website)\b", reason))
    has_evidence_word = bool(
        re.search(r"\b(?:match|matches|matched|candidate|candidates|entry|entries|profile|profiles|catalog|found|exist|known|configured)\b", reason)
    )
    return has_connection_kind and has_evidence_word


class MetaCatalogRouter:
    def __init__(
        self,
        *,
        settings: Any,
        embedding_client: Any,
        llm_client: Any | None,
        config: MetaCatalogRoutingConfig | None = None,
    ) -> None:
        self.settings = settings
        self.embedding_client = embedding_client
        self.decision_client = BoundedDecisionClient(llm_client)
        self.config = config or MetaCatalogRoutingConfig()

    async def route(self, routing_input: MetaCatalogRoutingInput) -> AriaTurnArbitration:
        clean_message = str(routing_input.message or "").strip()
        if not clean_message:
            return AriaTurnArbitration(plan=_fallback_plan(clean_message, reason="empty_message"), source="fallback")
        if clean_message.startswith("/"):
            return AriaTurnArbitration(plan=_fallback_plan(clean_message, reason="slash_command"), source="fallback")

        contextual_query = semantic_query_with_visible_chat_context(clean_message, routing_input.turn_context)
        hits, query_error = await self._query_meta_catalog(
            clean_message,
            user_id=routing_input.user_id,
            contextual_query=contextual_query,
        )
        if query_error:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason="meta_catalog_unavailable"),
                source="fallback",
                error=query_error,
            )
        if not hits:
            return AriaTurnArbitration(plan=_fallback_plan(clean_message, reason="meta_catalog_empty"), source="fallback")

        compact_hits = [_compact_meta_hit(hit) for hit in hits]
        by_catalog_id = {str(hit.get("catalog_id", "") or ""): hit for hit in compact_hits if str(hit.get("catalog_id", "") or "")}
        allowed_surfaces = {item.name for item in routing_input.menu.surfaces}
        if routing_input.surface_registry is not None:
            allowed_surfaces.update(routing_input.surface_registry.surface_ids())
        allowed_actions = {item.name for item in routing_input.menu.actions}
        allowed_actions.update(
            str(action or "").strip()
            for hit in compact_hits
            for action in list(hit.get("action_candidates", []) or [])
            if str(action or "").strip()
        )
        routing_meta_context = routing_input.menu.as_compact_payload(include_legacy_surfaces=routing_input.surface_registry is None)
        surface_meta_context = (
            routing_input.surface_registry.as_compact_routing_meta_context() if routing_input.surface_registry is not None else {}
        )
        last_turn_frame = _compact_last_turn_frame(routing_input.turn_context)
        recent_visible_chat_context = visible_chat_context_from_turn_context(routing_input.turn_context)
        routing_contract = {
            "required_contract_modes": sorted(META_CONTRACT_MODES),
            "required_evidence_policies": sorted(EVIDENCE_POLICIES),
            "context_request_modes": ["inventory", "exists", "search", "answer", "action"],
            "scope_operations": sorted(SCOPE_OPERATIONS),
            "prefer_catalog_context_over_legacy_wordlists": True,
            "selected_context_loads_are_source_bound": True,
            "legacy_semantics_after_valid_contract": "forbidden",
            "invalid_contract_behavior": "fallback_to_backup_path",
        }
        llm_input_contract = build_llm_input_contract(
            message=clean_message,
            language=str(routing_input.language or ""),
            user_id=routing_input.user_id,
            decision_task="meta_catalog_select_context_requests",
            routing_meta_context=routing_meta_context,
            surface_meta_context=surface_meta_context,
            world_map_extensions={
                "meta_catalog": compact_hits,
                "routing_contract": routing_contract,
            },
            last_turn_frame=last_turn_frame,
            recent_visible_chat_context=recent_visible_chat_context,
        )

        result = await self.decision_client.decide_json(
            operation=META_CATALOG_ROUTING_OPERATION,
            system=(
                "You are ARIA's meta-catalog context router. Return JSON only. "
                "Use llm_input_contract as the canonical normalized world map; it is not a route decision. "
                "The payload contains only llm_input_contract; do not rely on legacy top-level mirrors. "
                "Use only the provided catalog entries; do not answer the user. "
                "Decide whether ARIA should load more context or prepare an action preflight. "
                "Select catalog_ids only when the entry is semantically useful for the user prompt. "
                "Use recent_visible_chat_context as conversation evidence for elliptic follow-ups; if the user refers to the last visible action/output, route according to that referenced output before unrelated catalog topics. "
                "If nothing fits, return needs_context=false and answer_mode=direct_answer. "
                "Never invent surfaces, refs, collections, or actions. "
                "Side effects and command execution require needs_confirmation=true. "
                "Return an explicit contract with mode=answer|action|clarify|empty and "
                "evidence_policy=source_bound|allow_general. "
                "Use source_bound whenever ARIA loads selected local/catalog context. "
                "For runtime actions with multiple connection catalog_ids, set target_scope_authority: "
                "full_kind for a whole configured connection kind, explicit_refs for explicitly named refs, "
                "semantic_group for a reviewed subset, last_turn_scope only for a true follow-up to the last output, "
                "or priority_sample when catalog_ids are examples and not the complete target list. "
                "When a turn refers to last_turn_frame or changes inventory scope, set scope_operation explicitly: "
                "reuse_same_set, narrow_subset, expand_to_kind, exclude_subset, surface_change, or new_scope. "
                "For whole-kind inventory such as all SSH servers, use target_scope_authority=full_kind and "
                "scope_operation=expand_to_kind; put selected_kinds and bind_selected_kinds in the context request budget when known. "
                "For system inventories capabilities and recipes, request inventory mode even if the user says search/what are. "
                "Do not let catalog_ids/priority alone define a complete runtime target set. "
                "Output keys: needs_context, catalog_ids, context_requests, intents, surfaces, actions, "
                "target_scope_authority, scope_operation, answer_mode, context_depth, risk, needs_confirmation, confidence, reason, contract."
            ),
            payload={
                "llm_input_contract": llm_input_contract,
            },
            source=routing_input.source,
            user_id=routing_input.user_id,
            request_id=routing_input.request_id,
        )
        diagnostics = {**result.diagnostics, **llm_input_contract_diagnostics(llm_input_contract)}
        if not result.ok:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason=result.error or "meta_catalog_router_unavailable"),
                source="fallback",
                usage=result.usage,
                diagnostics=diagnostics,
                error=result.error,
            )
        confidence = confidence_score(result.payload.get("confidence"))
        if confidence < self.config.min_confidence:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason="meta_catalog_low_confidence"),
                source="fallback",
                usage=result.usage,
                diagnostics=diagnostics,
            )

        selected_catalog_ids = tuple(
            item for item in _unique_clean(result.payload.get("catalog_ids") or result.payload.get("catalog_id")) if item in by_catalog_id
        )
        rejected_catalog_ids = tuple(
            item for item in _as_sequence(result.payload.get("catalog_ids") or result.payload.get("catalog_id")) if str(item or "").strip() not in by_catalog_id
        )
        actions = _unique_clean(result.payload.get("actions") or result.payload.get("action"), allowed=allowed_actions)
        target_scope_authority = _unique_clean(
            result.payload.get("target_scope_authority"),
            allowed=TARGET_SCOPE_AUTHORITIES,
        )
        scope_operation = _unique_clean(result.payload.get("scope_operation"), allowed=SCOPE_OPERATIONS)
        requested_surfaces = _unique_clean(result.payload.get("surfaces") or result.payload.get("surface"), allowed=allowed_surfaces)
        raw_needs_context = bool(result.payload.get("needs_context", False))
        context_requests = self._context_requests(
            result.payload.get("context_requests") or result.payload.get("requests"),
            selected_catalog_ids=selected_catalog_ids,
            by_catalog_id=by_catalog_id,
            default_query=clean_message,
            surface_registry=routing_input.surface_registry,
            user_id=routing_input.user_id,
            request_id=routing_input.request_id,
        )
        explicit_surface = _explicit_local_surface(clean_message)
        reviewed_surface = await self._review_local_surface_contract(
            message=clean_message,
            language=str(routing_input.language or ""),
            router_payload=dict(result.payload or {}),
            selected_catalog_ids=selected_catalog_ids,
            requested_surfaces=requested_surfaces,
            context_requests=context_requests,
            actions=actions,
            explicit_surface=explicit_surface,
            compact_hits=compact_hits,
            by_catalog_id=by_catalog_id,
            source=routing_input.source,
            user_id=routing_input.user_id,
            request_id=routing_input.request_id,
            surface_registry=routing_input.surface_registry,
        )
        if reviewed_surface is not None:
            if reviewed_surface.block_reason:
                return AriaTurnArbitration(
                    plan=AriaTurnPlan(
                        intents=("chat",),
                        surfaces=("chat",),
                        needs_context=False,
                        context_directions=(),
                        context_depth="none",
                        context_requests=reviewed_surface.context_requests,
                        priority=reviewed_surface.selected_catalog_ids,
                        answer_mode="ask_clarification",
                        contract_mode="clarify",
                        evidence_policy="allow_general",
                        risk="low",
                        needs_confirmation=False,
                        confidence=confidence,
                        reason=reviewed_surface.block_reason[:160],
                    ),
                    source=META_CATALOG_ROUTING_OPERATION,
                    usage=result.usage,
                    diagnostics=diagnostics,
                    rejected={"catalog_ids": rejected_catalog_ids},
                )
            selected_catalog_ids = reviewed_surface.selected_catalog_ids
            requested_surfaces = reviewed_surface.requested_surfaces
            context_requests = reviewed_surface.context_requests

        normalized_connection_inventory = self._looks_like_connection_inventory_question(
            clean_message,
            requested_surfaces,
            selected_catalog_ids,
            by_catalog_id,
            context_requests=context_requests,
        )
        if normalized_connection_inventory:
            inventory_catalog_ids = tuple(
                catalog_id
                for catalog_id in selected_catalog_ids
                if str((by_catalog_id.get(catalog_id) or {}).get("surface_id", "") or "") == "connections"
                and str((by_catalog_id.get(catalog_id) or {}).get("kind", "") or "") in {"rss", "website", "ssh", "sftp", "smb"}
            )
            if inventory_catalog_ids:
                selected_catalog_ids = inventory_catalog_ids
            actions = ()
            requested_surfaces = ("connections",)
            context_requests = (
                ContextRequest(
                    surface_id="connections",
                    mode="inventory",
                    query=clean_message,
                    depth="shallow",
                    limit=12,
                    budget={
                        "meta_contract_normalized": "connection_inventory_question",
                        "catalog_hint_ids": list(selected_catalog_ids[:12]),
                        "scope_operation": scope_operation[0] if scope_operation else "",
                    },
                    user_id=routing_input.user_id,
                    turn_id=routing_input.request_id,
                ),
            )
            if routing_input.surface_registry is not None:
                context_requests = routing_input.surface_registry.validate_requests(context_requests)
        normalized_rss_action = self._looks_like_rss_read_action(
            clean_message,
            actions=actions,
            requested_surfaces=requested_surfaces,
            selected_catalog_ids=selected_catalog_ids,
            by_catalog_id=by_catalog_id,
            context_requests=context_requests,
        )
        if normalized_rss_action:
            actions = ("rss_read_feed",)
            requested_surfaces = ("connections",)
            context_requests = self._rss_action_context_requests(
                clean_message,
                selected_catalog_ids=selected_catalog_ids,
                by_catalog_id=by_catalog_id,
                existing_requests=context_requests,
                user_id=routing_input.user_id,
                request_id=routing_input.request_id,
            )
            if routing_input.surface_registry is not None:
                context_requests = routing_input.surface_registry.validate_requests(context_requests)
        surface_requires_context = bool(requested_surfaces and not actions and not set(requested_surfaces) <= {"chat"})
        if (raw_needs_context or surface_requires_context) and not context_requests and requested_surfaces and not actions:
            context_requests = self._surface_context_requests(
                requested_surfaces,
                default_query=clean_message,
                surface_registry=routing_input.surface_registry,
                user_id=routing_input.user_id,
                request_id=routing_input.request_id,
            )
        if explicit_surface and not actions:
            requested_surfaces = (explicit_surface,)
            context_requests = (
                ContextRequest(
                    surface_id=explicit_surface,
                    mode="search",
                    query=clean_message,
                    depth="shallow",
                    limit=12,
                    budget={"explicit_source_surface": explicit_surface},
                    user_id=routing_input.user_id,
                    turn_id=routing_input.request_id,
                ),
            )
            if routing_input.surface_registry is not None:
                context_requests = routing_input.surface_registry.validate_requests(context_requests)
        if context_requests:
            normalized_requests: list[ContextRequest] = []
            changed_system_inventory = False
            for request in context_requests:
                if request.surface_id in {"capabilities", "recipes"} and request.mode in {"answer", "search"}:
                    normalized_requests.append(
                        ContextRequest(
                            surface_id=request.surface_id,
                            mode="inventory",
                            query=request.query,
                            depth=request.depth,
                            limit=request.limit,
                            budget={
                                **dict(request.budget or {}),
                                "meta_contract_normalized": "system_inventory_mode",
                            },
                            user_id=request.user_id,
                            turn_id=request.turn_id,
                        )
                    )
                    changed_system_inventory = True
                    continue
                normalized_requests.append(request)
            if changed_system_inventory:
                context_requests = tuple(normalized_requests)
                if routing_input.surface_registry is not None:
                    context_requests = routing_input.surface_registry.validate_requests(context_requests)
        inferred_surfaces = tuple(dict.fromkeys(request.surface_id for request in context_requests if request.surface_id))
        surfaces = requested_surfaces or inferred_surfaces
        intents = _unique_clean(result.payload.get("intents") or result.payload.get("intent"), allowed=ARIA_TURN_INTENTS, fallback=("chat",))
        answer_mode = _unique_clean(result.payload.get("answer_mode"), allowed=ANSWER_MODES, fallback=("direct_answer",))[0]
        risk = _unique_clean(result.payload.get("risk"), allowed=RISK_LEVELS, fallback=("none",))[0]
        context_depth = _unique_clean(result.payload.get("context_depth"), allowed=CONTEXT_DEPTHS, fallback=("shallow",))[0]
        needs_context = bool(result.payload.get("needs_context", False)) or bool(context_requests)
        contract_mode, evidence_policy = self._contract_fields(
            result.payload,
            actions=actions,
            context_requests=context_requests,
            needs_context=needs_context,
            answer_mode=answer_mode,
        )
        if normalized_connection_inventory:
            contract_mode = "answer"
            evidence_policy = "source_bound"
            answer_mode = "direct_answer"
            risk = "none"
        if normalized_rss_action:
            contract_mode = "action"
            evidence_policy = "source_bound"
            answer_mode = "direct_answer"
            risk = "low"
        contract_error = self._contract_error(
            contract_mode=contract_mode,
            evidence_policy=evidence_policy,
            actions=actions,
            context_requests=context_requests,
            needs_context=needs_context,
            answer_mode=answer_mode,
        )
        if self.config.strict_contract_enabled and contract_error:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason=f"meta_catalog_contract_invalid:{contract_error}"),
                source="fallback",
                usage=result.usage,
                diagnostics=diagnostics,
            )
        if contract_mode in {"clarify", "empty"}:
            needs_context = False
            context_requests = ()
            actions = ()
            surfaces = ("chat",) if not surfaces else surfaces
            context_depth = "none"
            if contract_mode == "clarify":
                answer_mode = "ask_clarification"
            else:
                answer_mode = "direct_answer"

        context_directions = tuple(dict.fromkeys(request.surface_id for request in context_requests if request.surface_id))
        if context_requests and "context_inventory" not in intents and any(request.mode == "inventory" for request in context_requests):
            intents = tuple([*intents, "context_inventory"])
        if context_requests and "local_retrieval" not in intents and any(request.surface_id in {"memory", "notes", "docs"} for request in context_requests):
            intents = tuple([*intents, "local_retrieval"])
        if actions and "runtime_action" not in intents:
            intents = tuple([*intents, "runtime_action"])
        if not needs_context:
            context_directions = ()
            context_depth = "none"
        if needs_context and context_depth == "none":
            context_depth = "shallow"

        plan = AriaTurnPlan(
            intents=intents,
            surfaces=surfaces,
            actions=actions,
            needs_context=needs_context,
            context_directions=context_directions,
            context_depth=context_depth,
            queries={request.surface_id: request.query for request in context_requests if request.surface_id and request.query},
            context_requests=context_requests,
            priority=selected_catalog_ids,
            target_scope_authority=target_scope_authority[0] if target_scope_authority else "",
            scope_operation=scope_operation[0] if scope_operation else "",
            answer_mode=answer_mode,
            contract_mode=contract_mode,
            evidence_policy=evidence_policy,
            risk=risk,
            needs_confirmation=False
            if normalized_connection_inventory or normalized_rss_action
            else bool(result.payload.get("needs_confirmation", False)) or risk in {"medium", "high"},
            confidence=confidence,
            reason=str(result.payload.get("reason", "") or "meta_catalog_selected").strip()[:160],
        )
        return AriaTurnArbitration(
            plan=plan,
            source=META_CATALOG_ROUTING_OPERATION,
            usage=result.usage,
            diagnostics=diagnostics,
            rejected={"catalog_ids": rejected_catalog_ids},
        )

    async def _review_local_surface_contract(
        self,
        *,
        message: str,
        language: str,
        router_payload: dict[str, Any],
        selected_catalog_ids: tuple[str, ...],
        requested_surfaces: tuple[str, ...],
        context_requests: tuple[ContextRequest, ...],
        actions: tuple[str, ...],
        explicit_surface: str,
        compact_hits: list[dict[str, Any]],
        by_catalog_id: dict[str, dict[str, Any]],
        source: str,
        user_id: str,
        request_id: str,
        surface_registry: SurfaceRegistry | None,
    ) -> MetaCatalogSurfaceReviewOutcome | None:
        if actions or explicit_surface:
            return None
        selected_local = bool(
            set(requested_surfaces) & {"docs", "memory", "notes"}
            or any(request.surface_id in {"docs", "memory", "notes"} for request in context_requests)
        )
        if not selected_local:
            return None
        acknowledged_connection_evidence = _router_acknowledges_connection_evidence(router_payload, selected_catalog_ids)
        connection_hits = [
            hit
            for hit in compact_hits
            if str(hit.get("surface_id", "") or "") == "connections"
            and str(hit.get("kind", "") or "") in {"surface", "rss", "website", "ssh", "sftp", "smb"}
            and str(hit.get("catalog_id", "") or "").strip()
        ][:12]
        if not connection_hits:
            connection_hits = await self._recover_connection_review_hits(message, limit=12)
        if not connection_hits:
            if acknowledged_connection_evidence:
                traced_requests = self._with_surface_review_trace_requests(
                    context_requests,
                    from_surfaces=requested_surfaces,
                    to_surface="local_context",
                    decision="no_connection_evidence_recovered",
                    confidence=0.0,
                    selected_ids=(),
                    reason="router acknowledged connection evidence but no connection catalog candidates were recoverable",
                    surface_registry=surface_registry,
                )
                return MetaCatalogSurfaceReviewOutcome(
                    selected_catalog_ids=selected_catalog_ids,
                    requested_surfaces=requested_surfaces,
                    context_requests=traced_requests,
                    block_reason="meta_catalog_surface_review_blocked:no_connection_evidence_recovered",
                )
            return None
        selected_plan = {
            "catalog_ids": list(selected_catalog_ids),
            "surfaces": list(requested_surfaces),
            "context_requests": [request.as_payload() for request in context_requests[:8]],
            "selected_catalog_entries": [by_catalog_id[catalog_id] for catalog_id in selected_catalog_ids if catalog_id in by_catalog_id],
            "router_reason": str(router_payload.get("reason", "") or "").strip()[:600],
            "router_intents": _as_sequence(router_payload.get("intents") or router_payload.get("intent"))[:8],
            "router_actions": _as_sequence(router_payload.get("actions") or router_payload.get("action"))[:8],
            "router_contract": router_payload.get("contract") if isinstance(router_payload.get("contract"), dict) else {},
            "router_answer_mode": str(router_payload.get("answer_mode", "") or "").strip(),
        }
        review = await self.decision_client.decide_json(
            operation="meta_catalog_surface_contract_review",
            system=(
                "You are ARIA's meta-catalog surface-contract reviewer. Return JSON only. "
                "Do not answer the user. Correct only a surface mismatch between selected local context "
                "and provided connection catalog entries or the connections surface descriptor. "
                "Choose connections inventory when the user asks what "
                "configured/stored connection profiles, hosts, refs, IPs, services, feeds, or endpoints ARIA knows. "
                "Keep docs only when the user asks about uploaded documents, manuals, files, or document content. "
                "If selected_plan.router_reason acknowledges connection profiles but the selected structured plan uses docs, "
                "treat that as a self-consistency conflict and review the user goal against the provided catalog entries. "
                "Never invent catalog IDs."
            ),
            payload={
                "message": message,
                "language": language,
                "selected_plan": selected_plan,
                "competing_connection_catalog": connection_hits,
                "contract": (
                    "Return use_connections_inventory boolean, catalog_ids, query, confidence, reason. "
                    "catalog_ids must come from competing_connection_catalog. "
                    "If only the connections surface descriptor is available, returning its catalog_id means unbound connections inventory. "
                    "If uncertain, use false."
                ),
            },
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not review.ok:
            traced_requests = self._with_surface_review_trace_requests(
                context_requests,
                from_surfaces=requested_surfaces,
                to_surface="local_context",
                decision="review_unavailable",
                confidence=0.0,
                selected_ids=(),
                reason=review.error or "surface review unavailable",
                surface_registry=surface_registry,
            )
            return MetaCatalogSurfaceReviewOutcome(
                selected_catalog_ids=selected_catalog_ids,
                requested_surfaces=requested_surfaces,
                context_requests=traced_requests,
                block_reason="meta_catalog_surface_review_blocked:review_unavailable",
            )
        payload = review.payload
        confidence = confidence_score(payload.get("confidence"))
        if confidence < 0.65:
            traced_requests = self._with_surface_review_trace_requests(
                context_requests,
                from_surfaces=requested_surfaces,
                to_surface="local_context",
                decision="low_confidence",
                confidence=confidence,
                selected_ids=(),
                reason=str(payload.get("reason", "") or "").strip() or "surface review low confidence",
                surface_registry=surface_registry,
            )
            return MetaCatalogSurfaceReviewOutcome(
                selected_catalog_ids=selected_catalog_ids,
                requested_surfaces=requested_surfaces,
                context_requests=traced_requests,
                block_reason="meta_catalog_surface_review_blocked:low_confidence",
            )
        if not bool(payload.get("use_connections_inventory")):
            if acknowledged_connection_evidence:
                traced_requests = self._with_surface_review_trace_requests(
                    context_requests,
                    from_surfaces=requested_surfaces,
                    to_surface="local_context",
                    decision="self_contradictory_keep_local",
                    confidence=confidence,
                    selected_ids=(),
                    reason=(
                        str(payload.get("reason", "") or "").strip()
                        or "surface review kept local context despite router acknowledged connection evidence"
                    ),
                    surface_registry=surface_registry,
                )
                return MetaCatalogSurfaceReviewOutcome(
                    selected_catalog_ids=selected_catalog_ids,
                    requested_surfaces=requested_surfaces,
                    context_requests=traced_requests,
                    block_reason="meta_catalog_surface_review_blocked:self_contradictory_keep_local",
                )
            traced_requests = self._with_surface_review_trace_requests(
                context_requests,
                from_surfaces=requested_surfaces,
                to_surface="local_context",
                decision="keep_local",
                confidence=confidence,
                selected_ids=(),
                reason=str(payload.get("reason", "") or "").strip() or "review kept selected local surface",
                surface_registry=surface_registry,
            )
            return MetaCatalogSurfaceReviewOutcome(
                selected_catalog_ids=selected_catalog_ids,
                requested_surfaces=requested_surfaces,
                context_requests=traced_requests,
            )
        allowed = {str(hit.get("catalog_id", "") or "").strip() for hit in connection_hits}
        reviewed_ids = tuple(item for item in _unique_clean(payload.get("catalog_ids") or payload.get("catalog_id")) if item in allowed)
        if not reviewed_ids:
            traced_requests = self._with_surface_review_trace_requests(
                context_requests,
                from_surfaces=requested_surfaces,
                to_surface="local_context",
                decision="invalid_review_ids",
                confidence=confidence,
                selected_ids=(),
                reason=str(payload.get("reason", "") or "").strip() or "review did not return allowed connection catalog ids",
                surface_registry=surface_registry,
            )
            return MetaCatalogSurfaceReviewOutcome(
                selected_catalog_ids=selected_catalog_ids,
                requested_surfaces=requested_surfaces,
                context_requests=traced_requests,
                block_reason="meta_catalog_surface_review_blocked:invalid_review_ids",
            )
        query = str(payload.get("query", "") or "").strip() or message
        request = ContextRequest(
            surface_id="connections",
            mode="inventory",
            query=query,
            depth="shallow",
            limit=12,
            budget={
                "meta_contract_normalized": "surface_contract_review",
                "surface_review_decision": "use_connections_inventory",
                "catalog_hint_ids": list(reviewed_ids[:12]),
                "surface_review_from": ",".join(requested_surfaces) or "local_context",
                "surface_review_to": "connections",
                "surface_review_confidence": f"{confidence:.2f}",
                "surface_review_reason": str(payload.get("reason", "") or "").strip()[:180],
            },
            user_id=user_id,
            turn_id=request_id,
        )
        requests: tuple[ContextRequest, ...] = (request,)
        if surface_registry is not None:
            requests = surface_registry.validate_requests(requests)
        return MetaCatalogSurfaceReviewOutcome(
            selected_catalog_ids=reviewed_ids,
            requested_surfaces=("connections",),
            context_requests=requests,
        )

    async def _recover_connection_review_hits(self, message: str, *, limit: int) -> list[dict[str, Any]]:
        qdrant = None
        try:
            qdrant = await create_meta_catalog_qdrant_client(self.settings, timeout=5)
            raw_hits = await self._lexical_connection_hits(qdrant, message, limit=limit)
        except Exception:
            raw_hits = []
        finally:
            close = getattr(qdrant, "close", None) or getattr(qdrant, "aclose", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result
        recovered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in raw_hits:
            compact = _compact_meta_hit(hit)
            catalog_id = str(compact.get("catalog_id", "") or "").strip()
            if (
                not catalog_id
                or catalog_id in seen
                or str(compact.get("surface_id", "") or "") != "connections"
                or str(compact.get("kind", "") or "") not in {"surface", "rss", "website", "ssh", "sftp", "smb"}
            ):
                continue
            seen.add(catalog_id)
            recovered.append(compact)
            if len(recovered) >= max(1, int(limit or 1)):
                break
        return recovered

    @staticmethod
    def _with_surface_review_trace_requests(
        context_requests: tuple[ContextRequest, ...],
        *,
        from_surfaces: tuple[str, ...],
        to_surface: str,
        decision: str,
        confidence: float,
        selected_ids: tuple[str, ...],
        reason: str,
        surface_registry: SurfaceRegistry | None,
    ) -> tuple[ContextRequest, ...]:
        if not context_requests:
            return context_requests
        traced: list[ContextRequest] = []
        added = False
        for request in context_requests:
            budget = dict(request.budget or {})
            if not added:
                budget.update(
                    {
                        "meta_contract_normalized": "surface_contract_review",
                        "surface_review_decision": str(decision or "").strip() or "reviewed",
                        "catalog_hint_ids": list(selected_ids[:12]),
                        "surface_review_from": ",".join(from_surfaces) or "local_context",
                        "surface_review_to": str(to_surface or "").strip() or request.surface_id or "local_context",
                        "surface_review_confidence": f"{max(0.0, min(1.0, confidence)):.2f}",
                        "surface_review_reason": str(reason or "").strip()[:180],
                    }
                )
                added = True
            traced.append(
                ContextRequest(
                    surface_id=request.surface_id,
                    mode=request.mode,
                    query=request.query,
                    depth=request.depth,
                    limit=request.limit,
                    budget=budget,
                    user_id=request.user_id,
                    turn_id=request.turn_id,
                )
            )
        requests: tuple[ContextRequest, ...] = tuple(traced)
        if surface_registry is not None:
            requests = surface_registry.validate_requests(requests)
        return requests

    @staticmethod
    def _looks_like_connection_inventory_question(
        message: str,
        requested_surfaces: tuple[str, ...],
        selected_catalog_ids: tuple[str, ...],
        by_catalog_id: dict[str, dict[str, Any]],
        *,
        context_requests: tuple[ContextRequest, ...] = (),
    ) -> bool:
        clean = str(message or "").strip().lower()
        if not clean:
            return False
        has_connection_signal = "connections" in requested_surfaces or any(
            str((by_catalog_id.get(catalog_id) or {}).get("surface_id", "") or "") == "connections"
            for catalog_id in selected_catalog_ids
        ) or any(
            request.surface_id == "connections"
            for request in context_requests
        )
        if not has_connection_signal:
            return False
        fuer_pattern = "f" + chr(252) + "r|" + "f" + "uer|fur"
        inventory_phrases = (
            rf"\bwas\s+(?:habe|hab)\s+ich\s+(?:{fuer_pattern}|an)\b",
            r"\bwelche(?:n|s|r)?\s+.+\s+(?:habe|hab)\s+ich\b",
            rf"\bwas\s+(?:{fuer_pattern})\s+.+\s+(?:habe|hab)\s+ich\b",
            r"\bwhat\s+.+\s+do\s+i\s+have\b",
            r"\bwhich\s+.+\s+do\s+i\s+have\b",
            r"\blist\s+my\b",
            r"\bshow\s+my\b",
            r"\bzeige\s+(?:mir\s+)?meine\b",
        )
        if not any(re.search(pattern, clean) for pattern in inventory_phrases):
            return False
        return bool(
            re.search(
                r"\b(feed|feeds|rss|news|quelle|quellen|websites?|server|ssh|sftp|connection|connections|verbindung|verbindungen)\b",
                clean,
            )
        )

    @staticmethod
    def _looks_like_rss_read_action(
        message: str,
        *,
        actions: tuple[str, ...],
        requested_surfaces: tuple[str, ...],
        selected_catalog_ids: tuple[str, ...],
        by_catalog_id: dict[str, dict[str, Any]],
        context_requests: tuple[ContextRequest, ...],
    ) -> bool:
        clean = str(message or "").strip().lower()
        if not clean:
            return False
        rss_selected = any(
            str((by_catalog_id.get(catalog_id) or {}).get("surface_id", "") or "") == "connections"
            and str((by_catalog_id.get(catalog_id) or {}).get("kind", "") or "") == "rss"
            for catalog_id in selected_catalog_ids
        ) or any(
            request.surface_id == "connections"
            and str(dict(request.budget or {}).get("kind", "") or "") == "rss"
            for request in context_requests
        )
        if not rss_selected:
            return False
        if any(str(action or "").strip().lower() in {"rss_read_feed", "feed_read", "connection_action_rss"} for action in actions):
            return True
        if "connections" not in requested_surfaces and not any(request.surface_id == "connections" for request in context_requests):
            return False
        action_terms = "lies|lese|read|" + chr(246) + "ffne|oeffne|zeige|pruefe|pr" + chr(252) + "fe"
        return bool(
            re.search(rf"\b(?:{action_terms})\b", clean)
            and re.search(r"\b(?:feed|rss)\b", clean)
        )

    @staticmethod
    def _rss_action_context_requests(
        message: str,
        *,
        selected_catalog_ids: tuple[str, ...],
        by_catalog_id: dict[str, dict[str, Any]],
        existing_requests: tuple[ContextRequest, ...],
        user_id: str,
        request_id: str,
    ) -> tuple[ContextRequest, ...]:
        requests: list[ContextRequest] = []
        for request in existing_requests:
            budget = dict(request.budget or {})
            if request.surface_id == "connections" and str(budget.get("kind", "") or "") == "rss":
                requests.append(
                    ContextRequest(
                        surface_id="connections",
                        mode="action",
                        query=request.query or message,
                        depth=request.depth or "shallow",
                        limit=request.limit or 12,
                        budget=budget,
                        user_id=user_id,
                        turn_id=request_id,
                    )
                )
        if not requests:
            for catalog_id in selected_catalog_ids[:6]:
                hit = by_catalog_id.get(catalog_id) or {}
                if str(hit.get("surface_id", "") or "") != "connections" or str(hit.get("kind", "") or "") != "rss":
                    continue
                requests.append(
                    ContextRequest(
                        surface_id="connections",
                        mode="action",
                        query=message,
                        depth="shallow",
                        limit=12,
                        budget={
                            "catalog_id": catalog_id,
                            "entity_type": str(hit.get("entity_type", "") or ""),
                            "kind": "rss",
                            "ref": str(hit.get("ref", "") or ""),
                            "meta_contract_normalized": "rss_read_action",
                        },
                        user_id=user_id,
                        turn_id=request_id,
                    )
                )
                break
        return tuple(requests)

    @staticmethod
    def _contract_fields(
        payload: dict[str, Any],
        *,
        actions: tuple[str, ...],
        context_requests: tuple[ContextRequest, ...],
        needs_context: bool,
        answer_mode: str,
    ) -> tuple[str, str]:
        contract = payload.get("contract")
        contract_payload = contract if isinstance(contract, dict) else {}
        raw_mode = str(contract_payload.get("mode") or payload.get("mode") or "").strip().lower()
        raw_policy = str(contract_payload.get("evidence_policy") or payload.get("evidence_policy") or "").strip().lower()
        if raw_mode not in META_CONTRACT_MODES:
            if actions or answer_mode == "plan_action":
                raw_mode = "action"
            elif answer_mode == "ask_clarification":
                raw_mode = "clarify"
            elif needs_context or context_requests:
                raw_mode = "answer"
            else:
                raw_mode = "answer"
        if raw_policy not in EVIDENCE_POLICIES:
            raw_policy = "source_bound" if (needs_context or context_requests or raw_mode in {"action", "empty"}) else "allow_general"
        elif needs_context or context_requests or raw_mode in {"action", "empty"}:
            raw_policy = "source_bound"
        return raw_mode, raw_policy

    @staticmethod
    def _contract_error(
        *,
        contract_mode: str,
        evidence_policy: str,
        actions: tuple[str, ...],
        context_requests: tuple[ContextRequest, ...],
        needs_context: bool,
        answer_mode: str,
    ) -> str:
        if contract_mode not in META_CONTRACT_MODES:
            return "unknown_mode"
        if evidence_policy not in EVIDENCE_POLICIES:
            return "unknown_evidence_policy"
        if contract_mode == "action" and not (actions or answer_mode == "plan_action" or any(request.mode == "action" for request in context_requests)):
            return "action_without_action_candidate"
        if contract_mode in {"answer", "empty", "clarify"} and actions:
            return "non_action_contract_with_actions"
        if needs_context and evidence_policy != "source_bound":
            return "context_without_source_bound_evidence"
        return ""

    @staticmethod
    def _surface_context_requests(
        surfaces: tuple[str, ...],
        *,
        default_query: str,
        surface_registry: SurfaceRegistry | None,
        user_id: str,
        request_id: str,
    ) -> tuple[ContextRequest, ...]:
        requests: list[ContextRequest] = []
        for surface_id in surfaces[:6]:
            clean_surface = str(surface_id or "").strip()
            if not clean_surface:
                continue
            mode = "inventory" if clean_surface == "connections" else "search"
            requests.append(
                ContextRequest(
                    surface_id=clean_surface,
                    mode=mode,
                    query=default_query,
                    depth="shallow",
                    limit=12,
                    budget={"synthetic_context_request": "surface_selected_without_request"},
                    user_id=user_id,
                    turn_id=request_id,
                )
            )
        if surface_registry is not None:
            return surface_registry.validate_requests(requests)
        return tuple(requests)

    @staticmethod
    def _collapse_broad_inventory_requests(requests: list[ContextRequest]) -> list[ContextRequest]:
        collapsed: list[ContextRequest] = []
        inventory_by_key: dict[tuple[str, str], int] = {}
        for request in requests:
            if request.surface_id == "connections" and request.mode == "inventory" and not bool(dict(request.budget or {}).get("bind_ref")):
                key = (request.surface_id, request.query)
                existing_index = inventory_by_key.get(key)
                if existing_index is not None:
                    existing = collapsed[existing_index]
                    existing_budget = dict(existing.budget or {})
                    hint_ids = list(existing_budget.get("catalog_hint_ids", []) or [])
                    budget = dict(request.budget or {})
                    hint_id = str(budget.get("catalog_hint_id", "") or "").strip()
                    if hint_id and hint_id not in hint_ids:
                        hint_ids.append(hint_id)
                    collapsed[existing_index] = ContextRequest(
                        surface_id=existing.surface_id,
                        mode=existing.mode,
                        query=existing.query,
                        depth=existing.depth,
                        limit=max(existing.limit, request.limit),
                        budget={**existing_budget, "catalog_hint_ids": hint_ids[:12]},
                        user_id=existing.user_id,
                        turn_id=existing.turn_id,
                    )
                    continue
                budget = dict(request.budget or {})
                hint_id = str(budget.get("catalog_hint_id", "") or "").strip()
                if hint_id:
                    budget["catalog_hint_ids"] = [hint_id]
                for hard_key in ("catalog_id", "kind", "ref"):
                    budget.pop(hard_key, None)
                collapsed.append(
                    ContextRequest(
                        surface_id=request.surface_id,
                        mode=request.mode,
                        query=request.query,
                        depth=request.depth,
                        limit=request.limit,
                        budget=budget,
                        user_id=request.user_id,
                        turn_id=request.turn_id,
                    )
                )
                inventory_by_key[key] = len(collapsed) - 1
                continue
            collapsed.append(request)
        return collapsed

    async def _query_meta_catalog(
        self,
        query: str,
        *,
        user_id: str = "",
        contextual_query: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        qdrant = None
        try:
            qdrant = await create_meta_catalog_qdrant_client(self.settings, timeout=5)
            store = MetaCatalogStore(
                qdrant=qdrant,
                embedding_client=self.embedding_client,
                collection_name=meta_catalog_collection_name(self.settings),
            )
            limit = max(1, int(self.config.candidate_limit or 1))
            hits = await store.query_catalog(
                query,
                limit=limit,
                score_threshold=float(self.config.score_threshold or 0.0),
            )
            lexical_connection_hits = await self._lexical_connection_hits(qdrant, query, limit=min(4, limit))
            contextual_hits: list[dict[str, Any]] = []
            clean_contextual_query = str(contextual_query or "").strip()
            if clean_contextual_query and clean_contextual_query != str(query or "").strip():
                try:
                    contextual_hits = await store.query_catalog(
                        clean_contextual_query,
                        limit=min(4, limit),
                        score_threshold=float(self.config.score_threshold or 0.0),
                    )
                except Exception:
                    contextual_hits = []
            merged_contextual_hits = False
            if str(user_id or "").strip():
                try:
                    doc_store = DocumentMetaCatalogStore(
                        qdrant=qdrant,
                        embedding_client=self.embedding_client,
                        collection_name=document_meta_collection_for_user(user_id),
                    )
                    doc_hits = await doc_store.query_catalog(
                        query,
                        user_id=user_id,
                        limit=min(6, max(1, int(self.config.candidate_limit or 1))),
                        score_threshold=float(self.config.score_threshold or 0.0),
                    )
                except Exception:
                    doc_hits = []
                if doc_hits:
                    reserved_doc_hits = [
                        hit
                        for hit in doc_hits
                        if _catalog_lexical_overlap(query, hit) > 0
                    ][: min(4, limit)]
                    merged: list[dict[str, Any]] = []
                    seen: set[str] = set()
                    for hit in [*contextual_hits, *reserved_doc_hits, *lexical_connection_hits, *hits, *doc_hits]:
                        catalog_id = str(hit.get("catalog_id", "") or (dict(hit.get("payload", {}) or {})).get("catalog_id", "") or "").strip()
                        if not catalog_id or catalog_id in seen:
                            continue
                        seen.add(catalog_id)
                        merged.append(hit)
                        if len(merged) >= limit:
                            break
                    hits = merged
                    merged_contextual_hits = True
            if contextual_hits and not merged_contextual_hits:
                merged = []
                seen = set()
                for hit in [*contextual_hits, *lexical_connection_hits, *hits]:
                    catalog_id = str(hit.get("catalog_id", "") or (dict(hit.get("payload", {}) or {})).get("catalog_id", "") or "").strip()
                    if not catalog_id or catalog_id in seen:
                        continue
                    seen.add(catalog_id)
                    merged.append(hit)
                    if len(merged) >= limit:
                        break
                hits = merged
            elif lexical_connection_hits:
                merged = []
                seen = set()
                for hit in [*lexical_connection_hits, *hits]:
                    catalog_id = str(hit.get("catalog_id", "") or (dict(hit.get("payload", {}) or {})).get("catalog_id", "") or "").strip()
                    if not catalog_id or catalog_id in seen:
                        continue
                    seen.add(catalog_id)
                    merged.append(hit)
                    if len(merged) >= limit:
                        break
                hits = merged
            return hits, ""
        except Exception as exc:
            return [], str(exc).strip() or "query_failed"
        finally:
            close = getattr(qdrant, "close", None) or getattr(qdrant, "aclose", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result

    async def _lexical_connection_hits(self, qdrant: Any, query: str, *, limit: int) -> list[dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        scored_rows: list[tuple[int, float, dict[str, Any]]] = []
        offset = None
        while True:
            try:
                batch, offset = await qdrant.scroll(
                    collection_name=meta_catalog_collection_name(self.settings),
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception:
                return [row for _overlap, _score, row in scored_rows[: max(1, int(limit or 1))]]
            for point in batch or []:
                payload = dict(getattr(point, "payload", {}) or {})
                catalog_id = str(payload.get("catalog_id", "") or "").strip()
                overlap = _catalog_lexical_overlap(clean_query, {"payload": payload})
                if (
                    not catalog_id
                    or str(payload.get("surface_id", "") or "") != "connections"
                    or overlap <= 0
                ):
                    continue
                scored_rows.append(
                    (
                        overlap,
                        float(getattr(point, "score", 0.0) or 0.0),
                        {
                            "catalog_id": catalog_id,
                            "surface_id": str(payload.get("surface_id", "") or "").strip(),
                            "kind": str(payload.get("kind", "") or "").strip(),
                            "ref": str(payload.get("ref", "") or "").strip(),
                            "score": 0.0,
                            "source": "lexical_meta_catalog_recall",
                            "payload": payload,
                        },
                    )
                )
            if offset is None:
                break
        scored_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [row for _overlap, _score, row in scored_rows[: max(1, int(limit or 1))]]

    @staticmethod
    def _context_requests(
        values: Any,
        *,
        selected_catalog_ids: tuple[str, ...],
        by_catalog_id: dict[str, dict[str, Any]],
        default_query: str,
        surface_registry: SurfaceRegistry | None,
        user_id: str,
        request_id: str,
    ) -> tuple[ContextRequest, ...]:
        raw_rows = values if isinstance(values, list) else []
        requests: list[ContextRequest] = []
        for row in raw_rows[:12]:
            if not isinstance(row, dict):
                continue
            catalog_id = str(row.get("catalog_id", "") or "").strip()
            hit = by_catalog_id.get(catalog_id) if catalog_id else None
            surface_id = str(row.get("surface_id") or row.get("surface") or (hit or {}).get("surface_id") or "").strip()
            if not surface_id:
                continue
            mode = str(row.get("mode") or "search").strip()
            raw_budget = dict(row.get("budget") or {}) if isinstance(row.get("budget"), dict) else {}
            if surface_id == "connections" and mode == "inventory" and not bool(raw_budget.get("bind_ref")):
                raw_budget.pop("catalog_id", None)
                raw_budget.pop("kind", None)
                raw_budget.pop("ref", None)
            hit_budget = {}
            if hit is not None:
                if surface_id == "connections" and mode == "inventory":
                    hit_budget = {
                        "catalog_hint_id": catalog_id,
                        "entity_type_hint": str(hit.get("entity_type", "") or ""),
                        "kind_hint": str(hit.get("kind", "") or ""),
                        "ref_hint": str(hit.get("ref", "") or ""),
                    }
                else:
                    hit_budget = {
                        "catalog_id": catalog_id,
                        "entity_type": str(hit.get("entity_type", "") or ""),
                        "kind": str(hit.get("kind", "") or ""),
                        "ref": str(hit.get("ref", "") or ""),
                        "document_id": str(hit.get("document_id", "") or ""),
                        "document_name": str(hit.get("document_name", "") or ""),
                        "target_collection": str(hit.get("target_collection", "") or ""),
                    }
            requests.append(
                ContextRequest(
                    surface_id=surface_id,
                    mode=mode,
                    query=str(row.get("query") or default_query).strip(),
                    depth=str(row.get("depth") or row.get("context_depth") or "shallow").strip(),
                    limit=int(row.get("limit") or 12),
                    budget={**raw_budget, **hit_budget},
                    user_id=user_id,
                    turn_id=request_id,
                )
            )
        if not requests:
            for catalog_id in selected_catalog_ids[:6]:
                hit = by_catalog_id.get(catalog_id)
                surface_id = str((hit or {}).get("surface_id", "") or "").strip()
                if not surface_id:
                    continue
                mode = "inventory" if surface_id == "connections" else "search"
                if surface_id == "memory" and str((hit or {}).get("ref", "") or "") in {"facts", "preferences", "knowledge", "context_mem", "reflections", "events", "candidates", "active_hints", "evals"}:
                    mode = "exists" if "exist" in default_query.lower() or "habe ich" in default_query.lower() else "search"
                requests.append(
                    ContextRequest(
                        surface_id=surface_id,
                        mode=mode,
                        query=default_query,
                        depth="shallow",
                        limit=12,
                        budget=(
                            {
                                "catalog_hint_id": catalog_id,
                                "entity_type_hint": str((hit or {}).get("entity_type", "") or ""),
                                "kind_hint": str((hit or {}).get("kind", "") or ""),
                                "ref_hint": str((hit or {}).get("ref", "") or ""),
                            }
                            if surface_id == "connections" and mode == "inventory"
                            else {
                                "catalog_id": catalog_id,
                                "entity_type": str((hit or {}).get("entity_type", "") or ""),
                                "kind": str((hit or {}).get("kind", "") or ""),
                                "ref": str((hit or {}).get("ref", "") or ""),
                                "document_id": str((hit or {}).get("document_id", "") or ""),
                                "document_name": str((hit or {}).get("document_name", "") or ""),
                                "target_collection": str((hit or {}).get("target_collection", "") or ""),
                            }
                        ),
                        user_id=user_id,
                        turn_id=request_id,
                    )
                )
        requests = MetaCatalogRouter._collapse_broad_inventory_requests(requests)
        if surface_registry is not None:
            return surface_registry.validate_requests(requests)
        return tuple(requests)
