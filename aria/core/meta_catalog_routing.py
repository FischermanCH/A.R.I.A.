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
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnMenu
from aria.core.aria_turn_arbitration import AriaTurnPlan
from aria.core.aria_turn_arbitration import _fallback_plan
from aria.core.aria_turn_arbitration import _unique_clean
from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.context_surfaces import ContextRequest
from aria.core.context_surfaces import SurfaceRegistry
from aria.core.meta_catalog import MetaCatalogStore
from aria.core.meta_catalog import create_meta_catalog_qdrant_client
from aria.core.meta_catalog import meta_catalog_collection_name


META_CATALOG_ROUTING_OPERATION = "aria_meta_catalog_routing"


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


def _compact_meta_hit(hit: dict[str, Any]) -> dict[str, Any]:
    payload = dict(hit.get("payload", {}) or {})
    return {
        "catalog_id": str(payload.get("catalog_id", "") or hit.get("catalog_id", "") or "").strip(),
        "entity_type": str(payload.get("entity_type", "") or "").strip(),
        "surface_id": str(payload.get("surface_id", "") or "").strip(),
        "kind": str(payload.get("kind", "") or "").strip(),
        "ref": str(payload.get("ref", "") or "").strip(),
        "title": str(payload.get("title", "") or "").strip()[:180],
        "description": str(payload.get("description", "") or "").strip()[:320],
        "group_name": str(payload.get("group_name", "") or "").strip()[:120],
        "knows": list(payload.get("knows", []) or [])[:12],
        "can_load": list(payload.get("can_load", []) or [])[:10],
        "can_do": list(payload.get("can_do", []) or [])[:10],
        "action_candidates": list(payload.get("action_candidates", []) or [])[:8],
        "loader_contract": str(payload.get("loader_contract", "") or "").strip()[:240],
        "executor_contract": str(payload.get("executor_contract", "") or "").strip()[:240],
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
        "confidence": frame.get("confidence", 0.0),
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

        hits, query_error = await self._query_meta_catalog(clean_message)
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

        result = await self.decision_client.decide_json(
            operation=META_CATALOG_ROUTING_OPERATION,
            system=(
                "You are ARIA's meta-catalog context router. Return JSON only. "
                "Use only the provided catalog entries; do not answer the user. "
                "Decide whether ARIA should load more context or prepare an action preflight. "
                "Select catalog_ids only when the entry is semantically useful for the user prompt. "
                "If nothing fits, return needs_context=false and answer_mode=direct_answer. "
                "Never invent surfaces, refs, collections, or actions. "
                "Side effects and command execution require needs_confirmation=true. "
                "Return an explicit contract with mode=answer|action|clarify|empty and "
                "evidence_policy=source_bound|allow_general. "
                "Use source_bound whenever ARIA loads selected local/catalog context. "
                "Output keys: needs_context, catalog_ids, context_requests, intents, surfaces, actions, "
                "answer_mode, context_depth, risk, needs_confirmation, confidence, reason, contract."
            ),
            payload={
                "message": clean_message,
                "language": str(routing_input.language or ""),
                "meta_catalog": compact_hits,
                "routing_contract": {
                    "required_contract_modes": sorted(META_CONTRACT_MODES),
                    "required_evidence_policies": sorted(EVIDENCE_POLICIES),
                    "context_request_modes": ["inventory", "exists", "search", "answer", "action"],
                    "prefer_catalog_context_over_legacy_wordlists": True,
                    "selected_context_loads_are_source_bound": True,
                    "legacy_semantics_after_valid_contract": "forbidden",
                    "invalid_contract_behavior": "fallback_to_backup_path",
                },
                "last_turn_frame": _compact_last_turn_frame(routing_input.turn_context),
            },
            source=routing_input.source,
            user_id=routing_input.user_id,
            request_id=routing_input.request_id,
        )
        if not result.ok:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason=result.error or "meta_catalog_router_unavailable"),
                source="fallback",
                usage=result.usage,
                error=result.error,
            )
        confidence = confidence_score(result.payload.get("confidence"))
        if confidence < self.config.min_confidence:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason="meta_catalog_low_confidence"),
                source="fallback",
                usage=result.usage,
            )

        selected_catalog_ids = tuple(
            item for item in _unique_clean(result.payload.get("catalog_ids") or result.payload.get("catalog_id")) if item in by_catalog_id
        )
        rejected_catalog_ids = tuple(
            item for item in _as_sequence(result.payload.get("catalog_ids") or result.payload.get("catalog_id")) if str(item or "").strip() not in by_catalog_id
        )
        actions = _unique_clean(result.payload.get("actions") or result.payload.get("action"), allowed=allowed_actions)
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
        normalized_connection_inventory = self._looks_like_connection_inventory_question(clean_message, requested_surfaces, selected_catalog_ids, by_catalog_id)
        if normalized_connection_inventory:
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
                    },
                    user_id=routing_input.user_id,
                    turn_id=routing_input.request_id,
                ),
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
        explicit_surface = _explicit_local_surface(clean_message)
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
            answer_mode=answer_mode,
            contract_mode=contract_mode,
            evidence_policy=evidence_policy,
            risk=risk,
            needs_confirmation=False if normalized_connection_inventory else bool(result.payload.get("needs_confirmation", False)) or risk in {"medium", "high"},
            confidence=confidence,
            reason=str(result.payload.get("reason", "") or "meta_catalog_selected").strip()[:160],
        )
        return AriaTurnArbitration(
            plan=plan,
            source=META_CATALOG_ROUTING_OPERATION,
            usage=result.usage,
            rejected={"catalog_ids": rejected_catalog_ids},
        )

    @staticmethod
    def _looks_like_connection_inventory_question(
        message: str,
        requested_surfaces: tuple[str, ...],
        selected_catalog_ids: tuple[str, ...],
        by_catalog_id: dict[str, dict[str, Any]],
    ) -> bool:
        clean = str(message or "").strip().lower()
        if not clean:
            return False
        has_connection_signal = "connections" in requested_surfaces or any(
            str((by_catalog_id.get(catalog_id) or {}).get("surface_id", "") or "") == "connections"
            for catalog_id in selected_catalog_ids
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

    async def _query_meta_catalog(self, query: str) -> tuple[list[dict[str, Any]], str]:
        qdrant = None
        try:
            qdrant = await create_meta_catalog_qdrant_client(self.settings, timeout=5)
            store = MetaCatalogStore(
                qdrant=qdrant,
                embedding_client=self.embedding_client,
                collection_name=meta_catalog_collection_name(self.settings),
            )
            hits = await store.query_catalog(
                query,
                limit=max(1, int(self.config.candidate_limit or 1)),
                score_threshold=float(self.config.score_threshold or 0.0),
            )
            return hits, ""
        except Exception as exc:
            return [], str(exc).strip() or "query_failed"
        finally:
            close = getattr(qdrant, "close", None) or getattr(qdrant, "aclose", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result

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
