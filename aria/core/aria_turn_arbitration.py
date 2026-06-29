from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import re
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.chat_turn_context import visible_chat_context_from_turn_context
from aria.core.context_surfaces import ContextRequest
from aria.core.context_surfaces import SurfaceRegistry


ARIA_TURN_ARBITRATION_OPERATION = "aria_turn_surface_action_arbitration"

CONTEXT_DIRECTIONS = {
    "none",
    "memory",
    "learning",
    "notes",
    "docs",
    "skills",
    "connections",
    "web",
    "workspace",
    "sessions",
    "recipes",
    "pending",
    "admin",
}

CONTEXT_DEPTHS = {"none", "meta", "shallow", "deep"}

ARIA_TURN_INTENTS = {
    "chat",
    "local_retrieval",
    "web_research",
    "runtime_action",
    "recipe",
    "pending_flow",
    "admin_flow",
    "learning_feedback",
    "context_inventory",
    "blocked",
}

ANSWER_MODES = {
    "direct_answer",
    "answer_from_context",
    "answer_with_source_grouping",
    "summarize_sources",
    "plan_action",
    "ask_clarification",
    "blocked",
}

RISK_LEVELS = {"none", "low", "medium", "high"}
META_CONTRACT_MODES = {"answer", "action", "clarify", "empty"}
EVIDENCE_POLICIES = {"source_bound", "allow_general"}


@dataclass(frozen=True, slots=True)
class AriaTurnSurfaceOption:
    name: str
    kind: str
    description: str = ""
    allowed_actions: tuple[str, ...] = ("select",)

    def as_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "allowed_actions": list(self.allowed_actions),
        }


@dataclass(frozen=True, slots=True)
class AriaTurnCollectionOption:
    name: str
    kind: str
    description: str = ""
    allowed_actions: tuple[str, ...] = ("search",)
    default_top_k: int = 5

    def as_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "allowed_actions": list(self.allowed_actions),
            "default_top_k": self.default_top_k,
        }


@dataclass(frozen=True, slots=True)
class AriaTurnActionOption:
    name: str
    kind: str
    description: str = ""
    risk: str = "low"
    requires_confirmation: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "risk": self.risk,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass(frozen=True, slots=True)
class AriaTurnMenu:
    surfaces: tuple[AriaTurnSurfaceOption, ...] = ()
    collections: tuple[AriaTurnCollectionOption, ...] = ()
    actions: tuple[AriaTurnActionOption, ...] = ()
    policy_notes: tuple[str, ...] = ()
    budget: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "surfaces": [item.as_payload() for item in self.surfaces],
            "collections": [item.as_payload() for item in self.collections],
            "actions": [item.as_payload() for item in self.actions],
            "policy_notes": list(self.policy_notes),
            "budget": dict(self.budget),
        }

    def as_compact_payload(self, *, include_legacy_surfaces: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "collections": [
                {"name": item.name, "kind": item.kind, "default_top_k": item.default_top_k}
                for item in self.collections
            ],
            "actions": [
                {
                    "name": item.name,
                    "kind": item.kind,
                    "risk": item.risk,
                    "requires_confirmation": item.requires_confirmation,
                }
                for item in self.actions
            ],
            "budget": dict(self.budget),
        }
        if include_legacy_surfaces:
            payload["legacy_surfaces"] = [
                {"name": item.name, "kind": item.kind, "allowed_actions": list(item.allowed_actions)}
                for item in self.surfaces
            ]
        return payload


@dataclass(frozen=True, slots=True)
class AriaTurnPlan:
    intents: tuple[str, ...] = ("chat",)
    surfaces: tuple[str, ...] = ()
    collections: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    needs_context: bool = False
    context_directions: tuple[str, ...] = ()
    context_depth: str = "none"
    queries: dict[str, str] = field(default_factory=dict)
    context_requests: tuple[ContextRequest, ...] = ()
    priority: tuple[str, ...] = ()
    answer_mode: str = "direct_answer"
    contract_mode: str = ""
    evidence_policy: str = ""
    risk: str = "none"
    needs_confirmation: bool = False
    confidence: float = 0.0
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AriaTurnArbitration:
    plan: AriaTurnPlan
    source: str = "fallback"
    usage: dict[str, int] = field(default_factory=dict)
    diagnostics: dict[str, int] = field(default_factory=dict)
    error: str = ""
    rejected: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def debug_line(self) -> str:
        plan = self.plan
        parts = [
            "Routing Debug: aria_turn_surface_action_arbitration",
            f"source={self.source}",
            f"intents={','.join(plan.intents) or '-'}",
            f"needs_context={str(plan.needs_context).lower()}",
            f"context_directions={','.join(plan.context_directions) or '-'}",
            f"context_depth={plan.context_depth}",
            f"surfaces={','.join(plan.surfaces) or '-'}",
            f"collections={','.join(plan.collections) or '-'}",
            f"actions={','.join(plan.actions) or '-'}",
            f"answer_mode={plan.answer_mode}",
            f"contract_mode={plan.contract_mode or '-'}",
            f"evidence_policy={plan.evidence_policy or '-'}",
            f"risk={plan.risk}",
            f"needs_confirmation={str(plan.needs_confirmation).lower()}",
            f"confidence={plan.confidence:.2f}",
        ]
        if plan.priority:
            parts.append(f"priority={','.join(plan.priority)[:180]}")
        if self.diagnostics:
            payload_bytes = int(self.diagnostics.get("payload_bytes", 0) or 0)
            system_chars = int(self.diagnostics.get("system_chars", 0) or 0)
            payload_keys = int(self.diagnostics.get("payload_keys", 0) or 0)
            if payload_bytes or system_chars or payload_keys:
                parts.append(
                    f"routing_payload_bytes={payload_bytes} routing_system_chars={system_chars} routing_payload_keys={payload_keys}"
                )
        if self.error:
            parts.append(f"error={self.error}")
        if plan.reason:
            parts.append(f"reason={plan.reason[:96]}")
        return " ".join(parts)


def build_aria_turn_menu(
    *,
    collections: Iterable[AriaTurnCollectionOption] = (),
    connection_kinds: Iterable[str] = (),
    recipes_available: bool = False,
    notes_available: bool = False,
    docs_available: bool = False,
    web_search_available: bool = False,
    websites_available: bool = False,
    pending_available: bool = False,
    admin_available: bool = False,
    learning_available: bool = True,
    policy_notes: Iterable[str] = (),
    budget: dict[str, Any] | None = None,
) -> AriaTurnMenu:
    surface_rows: list[AriaTurnSurfaceOption] = [
        AriaTurnSurfaceOption("chat", "chat", "ordinary answer without tool or retrieval execution"),
    ]
    collection_rows = tuple(collections)
    if collection_rows or notes_available or docs_available:
        surface_rows.append(
            AriaTurnSurfaceOption(
                "local_retrieval",
                "retrieval",
                "Qdrant-backed facts, learning, notes, documents, sessions, and combined local recall",
                ("search", "summarize"),
            )
        )
    if web_search_available:
        surface_rows.append(AriaTurnSurfaceOption("web_research", "web", "fresh web search or direct URL/source fetch", ("search", "fetch")))
    if websites_available:
        surface_rows.append(
            AriaTurnSurfaceOption("watched_websites", "websites", "configured watched website profiles", ("list", "read"))
        )
    if recipes_available:
        surface_rows.append(AriaTurnSurfaceOption("recipes", "recipe", "stored recipe catalog and recipe execution", ("explain", "execute")))
    clean_connection_kinds = tuple(dict.fromkeys(str(item or "").strip().lower() for item in connection_kinds if str(item or "").strip()))
    if clean_connection_kinds:
        surface_rows.append(
            AriaTurnSurfaceOption("runtime_actions", "runtime", "connection-backed capability execution", ("plan", "execute"))
        )
    if pending_available:
        surface_rows.append(AriaTurnSurfaceOption("pending_flow", "pending", "pending confirmations and follow-up actions", ("resume", "cancel")))
    if admin_available:
        surface_rows.append(AriaTurnSurfaceOption("admin_flow", "admin", "admin/configuration commands", ("inspect", "change")))
    if learning_available:
        surface_rows.append(
            AriaTurnSurfaceOption(
                "learning_feedback",
                "learning",
                "feedback, correction, learning-event capture, artifact review, and outcome tracking",
                ("capture", "review"),
            )
        )

    action_rows: list[AriaTurnActionOption] = []
    if notes_available:
        action_rows.append(
            AriaTurnActionOption(
                "notes_action",
                "notes",
                "open, create, save, or manage a note when the user explicitly asks for a notes operation",
                risk="low",
            )
        )
    if websites_available:
        action_rows.append(
            AriaTurnActionOption(
                "watched_website_action",
                "websites",
                "open or list configured watched website profiles",
                risk="low",
            )
        )
    for kind in clean_connection_kinds:
        action_rows.append(
            AriaTurnActionOption(
                name=f"connection_action_{kind}",
                kind=kind,
                description=f"plan or execute an allowed {kind} connection capability",
                risk="medium",
                requires_confirmation=True,
            )
        )
    if recipes_available:
        action_rows.append(
            AriaTurnActionOption(
                "recipe_action",
                "recipe",
                "explain or execute a stored recipe candidate",
                risk="medium",
                requires_confirmation=True,
            )
        )
    if pending_available:
        action_rows.append(
            AriaTurnActionOption("pending_action", "pending", "continue, cancel, or confirm a pending action", risk="medium", requires_confirmation=True)
        )
    if admin_available:
        action_rows.append(
            AriaTurnActionOption("admin_action", "admin", "perform an allowed admin/configuration action", risk="high", requires_confirmation=True)
        )
    if learning_available:
        action_rows.append(
            AriaTurnActionOption("learning_capture", "learning", "capture user feedback or learning outcome as review-only artifact", risk="low")
        )

    return AriaTurnMenu(
        surfaces=tuple(surface_rows),
        collections=collection_rows,
        actions=tuple(action_rows),
        policy_notes=tuple(str(item or "").strip() for item in policy_notes if str(item or "").strip()),
        budget=dict(budget or {}),
    )


def _unique_clean(values: Any, *, allowed: set[str] | None = None, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw_values: Iterable[Any]
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list | tuple | set):
        raw_values = values
    else:
        raw_values = []
    rows: list[str] = []
    for value in raw_values:
        clean = str(value or "").strip()
        if not clean:
            continue
        if allowed is not None and clean not in allowed:
            continue
        if clean not in rows:
            rows.append(clean)
    if not rows:
        return fallback
    return tuple(rows)


def _clean_queries(values: Any, *, allowed_collections: set[str], default_query: str) -> dict[str, str]:
    if not isinstance(values, dict):
        return {}
    queries: dict[str, str] = {}
    for key, value in values.items():
        clean_key = str(key or "").strip()
        if clean_key not in allowed_collections:
            continue
        clean_value = " ".join(str(value or "").strip().split())
        if not clean_value:
            clean_value = default_query
        queries[clean_key] = clean_value[:600]
    return queries


def _clean_context_requests(values: Any, *, surface_registry: SurfaceRegistry | None, default_query: str, user_id: str, request_id: str) -> tuple[ContextRequest, ...]:
    if surface_registry is None or not isinstance(values, list):
        return ()
    requests: list[ContextRequest] = []
    for row in values[:12]:
        if not isinstance(row, dict):
            continue
        mode = str(row.get("mode") or "answer").strip()
        request = ContextRequest(
            surface_id=str(row.get("surface_id") or row.get("surface") or "").strip(),
            mode=mode,
            query=str(row.get("query") or default_query).strip(),
            depth=str(row.get("depth") or row.get("context_depth") or "shallow").strip(),
            limit=int(row.get("limit") or (50 if mode == "inventory" else 5)),
            budget=dict(row.get("budget") or {}) if isinstance(row.get("budget"), dict) else {},
            user_id=user_id,
            turn_id=request_id,
        )
        requests.append(request)
    return surface_registry.validate_requests(requests)


def _context_request_queries(requests: Iterable[ContextRequest]) -> dict[str, str]:
    queries: dict[str, str] = {}
    for request in requests:
        key = request.surface_id
        query = str(request.query or "").strip()
        if key and query and key not in queries:
            queries[key] = query
    return queries


def _directions_from_context_requests(requests: Iterable[ContextRequest]) -> tuple[str, ...]:
    rows: list[str] = []
    for request in requests:
        surface_id = request.surface_id
        direction = "web" if surface_id == "web" else surface_id
        if direction and direction not in rows:
            rows.append(direction)
    return tuple(rows)


def _raw_sequence(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        raw_values: Iterable[Any] = [values]
    elif isinstance(values, list | tuple | set):
        raw_values = values
    else:
        raw_values = []
    rows: list[str] = []
    for value in raw_values:
        clean = str(value or "").strip()
        if clean and clean not in rows:
            rows.append(clean)
    return tuple(rows)


def _fallback_plan(message: str, *, reason: str = "") -> AriaTurnPlan:
    return AriaTurnPlan(
        intents=("chat",),
        answer_mode="direct_answer",
        confidence=0.0,
        reason=reason or "fallback_chat",
    )


def _compact_last_turn_frame(turn_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(turn_context, dict):
        return {}
    frame = turn_context.get("last_turn_frame")
    if not isinstance(frame, dict):
        return {}
    surface_id = str(frame.get("surface_id") or "").strip()
    mode = str(frame.get("mode") or "").strip()
    if not surface_id or not mode:
        return {}
    return {
        "surface_id": surface_id,
        "mode": mode,
        "topic": " ".join(str(frame.get("topic") or "").split())[:180],
        "catalog_ids": list(frame.get("catalog_ids", []) or [])[:8] if isinstance(frame.get("catalog_ids"), list | tuple) else [],
        "evidence_policy": str(frame.get("evidence_policy", "") or "").strip(),
        "answer_mode": str(frame.get("answer_mode", "") or "").strip(),
        "confidence": frame.get("confidence", 0.0),
    }


def _clean_contract_fields(
    payload: dict[str, Any],
    *,
    actions: tuple[str, ...],
    context_requests: tuple[ContextRequest, ...],
    needs_context: bool,
    answer_mode: str,
) -> tuple[str, str]:
    contract = payload.get("contract")
    contract_payload = contract if isinstance(contract, dict) else {}
    mode = str(contract_payload.get("mode") or payload.get("mode") or "").strip().lower()
    policy = str(contract_payload.get("evidence_policy") or payload.get("evidence_policy") or "").strip().lower()
    if mode not in META_CONTRACT_MODES:
        if actions or answer_mode == "plan_action":
            mode = "action"
        elif answer_mode == "ask_clarification":
            mode = "clarify"
        elif needs_context or context_requests:
            mode = "answer"
        else:
            mode = ""
    if policy not in EVIDENCE_POLICIES:
        policy = "source_bound" if needs_context or context_requests or mode in {"action", "empty"} else ""
    return mode, policy


class AriaTurnArbiter:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def arbitrate(
        self,
        *,
        message: str,
        menu: AriaTurnMenu,
        surface_registry: SurfaceRegistry | None = None,
        language: str | None = None,
        turn_context: dict[str, Any] | None = None,
        source: str = "pipeline",
        user_id: str = "",
        request_id: str = "",
    ) -> AriaTurnArbitration:
        clean_message = str(message or "").strip()
        if not clean_message:
            return AriaTurnArbitration(plan=_fallback_plan(clean_message, reason="empty_message"), source="fallback")
        if clean_message.startswith("/"):
            return AriaTurnArbitration(plan=_fallback_plan(clean_message, reason="slash_command"), source="fallback")

        allowed_surfaces = {item.name for item in menu.surfaces}
        if surface_registry is not None:
            allowed_surfaces.update(surface_registry.surface_ids())
        allowed_collections = {item.name for item in menu.collections}
        allowed_actions = {item.name for item in menu.actions}

        surface_meta_context = surface_registry.as_compact_routing_meta_context() if surface_registry is not None else {}
        system = (
            "You are ARIA's single agentic turn router. Return JSON only. "
            "Select whether this turn needs context, action, recipe, learning, web, or plain chat. "
            "Use registered ContextSurfaces only. Do not answer. No word lists or trigger-phrase logic. "
            "Treat last_turn_frame only as context, not as a command: continue it only when it truly fits the new user message. "
            "Use recent_visible_chat_context as conversation evidence for elliptic follow-ups; if the user refers to the last visible action/output, route according to that referenced output before unrelated catalog topics. "
            "Do not route operational/resource health, status, update, or execution requests to memory exists; choose an action-capable surface or ask for clarification. "
            "Side effects require needs_confirmation=true. "
            "Modes: inventory=list configured/stored objects; exists=check whether selected local content contains topic; search=load relevant context. "
            "Use concise topic queries. Output keys: needs_context, context_directions, context_depth, intents, surfaces, collections, actions, "
            "context_requests, queries, priority, answer_mode, risk, needs_confirmation, confidence, reason. Keep reason under 12 words."
        )
        result = await self.decision_client.decide_json(
            operation=ARIA_TURN_ARBITRATION_OPERATION,
            system=system,
            payload={
                "message": clean_message,
                "language": str(language or ""),
                "routing_meta_context": menu.as_compact_payload(include_legacy_surfaces=surface_registry is None),
                "surface_meta_context": surface_meta_context,
                "last_turn_frame": _compact_last_turn_frame(turn_context),
                "recent_visible_chat_context": visible_chat_context_from_turn_context(turn_context),
            },
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason=result.error or "arbiter_unavailable"),
                source="fallback",
                usage=result.usage,
                diagnostics=result.diagnostics,
                error=result.error,
            )
        result_payload = result.payload
        result_usage = result.usage
        result_source = ARIA_TURN_ARBITRATION_OPERATION
        confidence = confidence_score(result_payload.get("confidence"))
        if confidence < 0.62:
            return AriaTurnArbitration(
                plan=_fallback_plan(clean_message, reason="arbiter_low_confidence"),
                source="fallback",
                usage=result_usage,
                diagnostics=result.diagnostics,
            )

        intents = _unique_clean(result_payload.get("intents") or result_payload.get("intent"), allowed=ARIA_TURN_INTENTS, fallback=("chat",))
        surfaces = _unique_clean(result_payload.get("surfaces") or result_payload.get("surface"), allowed=allowed_surfaces)
        collections = _unique_clean(result_payload.get("collections") or result_payload.get("collection"), allowed=allowed_collections)
        actions = _unique_clean(result_payload.get("actions") or result_payload.get("action"), allowed=allowed_actions)
        context_requests = _clean_context_requests(
            result_payload.get("context_requests") or result_payload.get("requests"),
            surface_registry=surface_registry,
            default_query=clean_message,
            user_id=user_id,
            request_id=request_id,
        )
        context_directions = _unique_clean(
            result_payload.get("context_directions") or result_payload.get("directions") or result_payload.get("context_direction"),
            allowed=CONTEXT_DIRECTIONS,
        )
        answer_mode = _unique_clean(result_payload.get("answer_mode"), allowed=ANSWER_MODES, fallback=("direct_answer",))[0]
        risk = _unique_clean(result_payload.get("risk"), allowed=RISK_LEVELS, fallback=("none",))[0]
        context_depth = _unique_clean(result_payload.get("context_depth"), allowed=CONTEXT_DEPTHS, fallback=("none",))[0]
        priority = _unique_clean(result_payload.get("priority"))
        raw_needs_confirmation = bool(result_payload.get("needs_confirmation", False))
        preserved_followup_surface = False
        queries = _clean_queries(result_payload.get("queries"), allowed_collections=allowed_collections, default_query=clean_message)
        if preserved_followup_surface:
            context_directions = ()
            surfaces = ()
            collections = ()
            selected_mode = context_requests[0].mode if context_requests else ""
            if selected_mode == "inventory":
                intents = ("context_inventory",)
            elif selected_mode in {"exists", "search", "answer", "summarize"}:
                intents = ("local_retrieval",)
        if collections:
            queries = {name: queries.get(name, clean_message[:600]) for name in collections}
        for key, value in _context_request_queries(context_requests).items():
            queries.setdefault(key, value)
        inferred_directions: list[str] = []
        for collection in collections:
            lower = collection.lower()
            if "learning" in lower and "learning" not in inferred_directions:
                inferred_directions.append("learning")
            elif "notes" in lower and "notes" not in inferred_directions:
                inferred_directions.append("notes")
            elif "docs" in lower and "docs" not in inferred_directions:
                inferred_directions.append("docs")
            elif "sessions" in lower and "sessions" not in inferred_directions:
                inferred_directions.append("sessions")
            elif "memory" not in inferred_directions:
                inferred_directions.append("memory")
        if "web_research" in intents and "web" not in inferred_directions:
            inferred_directions.append("web")
        if "recipe" in intents and "recipes" not in inferred_directions:
            inferred_directions.append("recipes")
        if "runtime_action" in intents and "connections" not in inferred_directions:
            inferred_directions.append("connections")
        for direction in _directions_from_context_requests(context_requests):
            if direction in CONTEXT_DIRECTIONS and direction not in inferred_directions:
                inferred_directions.append(direction)
        if any(request.mode == "inventory" for request in context_requests) and "context_inventory" not in intents:
            intents = tuple([*intents, "context_inventory"])
        if any(request.surface_id == "web" for request in context_requests) and "web_research" not in intents:
            intents = tuple([*intents, "web_research"])
        if any(request.surface_id in {"memory", "notes", "docs"} for request in context_requests) and "local_retrieval" not in intents:
            intents = tuple([*intents, "local_retrieval"])
        if not context_directions:
            context_directions = tuple(inferred_directions)
        context_directions = tuple(direction for direction in context_directions if direction != "none")
        needs_context = bool(result_payload.get("needs_context", False)) or bool(context_directions) or bool(collections) or bool(context_requests)
        if not needs_context:
            context_directions = ()
            context_depth = "none"
        elif context_depth == "none":
            context_depth = "shallow"
        selected_action_options = {item.name: item for item in menu.actions if item.name in actions}
        needs_confirmation = raw_needs_confirmation or any(
            item.requires_confirmation or item.risk in {"medium", "high"} for item in selected_action_options.values()
        )
        rejected = {
            "surfaces": tuple(
                item
                for item in _raw_sequence(result_payload.get("surfaces") or result_payload.get("surface"))
                if item not in allowed_surfaces
            ),
            "collections": tuple(
                item
                for item in _raw_sequence(result_payload.get("collections") or result_payload.get("collection"))
                if item not in allowed_collections
            ),
            "actions": tuple(
                item
                for item in _raw_sequence(result_payload.get("actions") or result_payload.get("action"))
                if item not in allowed_actions
            ),
        }
        if "runtime_action" in intents and not actions:
            intents = tuple(item for item in intents if item != "runtime_action") or ("chat",)
            answer_mode = "ask_clarification"
        contract_mode, evidence_policy = _clean_contract_fields(
            result_payload,
            actions=actions,
            context_requests=context_requests,
            needs_context=needs_context,
            answer_mode=answer_mode,
        )
        plan = AriaTurnPlan(
            intents=intents,
            surfaces=surfaces,
            collections=collections,
            actions=actions,
            needs_context=needs_context,
            context_directions=context_directions,
            context_depth=context_depth,
            queries=queries,
            context_requests=context_requests,
            priority=priority,
            answer_mode=answer_mode,
            contract_mode=contract_mode,
            evidence_policy=evidence_policy,
            risk=risk,
            needs_confirmation=needs_confirmation,
            confidence=confidence,
            reason=" ".join(str(result_payload.get("reason") or "").strip().split())[:160],
        )
        return AriaTurnArbitration(plan=plan, source=result_source, usage=result_usage, diagnostics=result.diagnostics, rejected=rejected)
