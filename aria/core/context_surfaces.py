from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


SURFACE_MODES = {
    "answer",
    "exists",
    "inventory",
    "search",
    "summarize",
    "action",
    "learn",
    "clarify",
    "block",
}

SURFACE_RISK_LEVELS = {"none", "low", "medium", "high"}
SURFACE_COST_HINTS = {"free", "cheap", "medium", "expensive", "unknown"}
SURFACE_LATENCY_HINTS = {"instant", "fast", "medium", "slow", "unknown"}


def _clean_text(value: Any, *, limit: int = 500) -> str:
    return " ".join(str(value or "").strip().split())[: max(1, int(limit or 1))]


def _clean_id(value: Any, *, limit: int = 120) -> str:
    text = _clean_text(value, limit=limit).lower()
    return "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in text).strip("_")


def _clean_tuple(values: Iterable[Any] | None, *, allowed: set[str] | None = None, limit: int = 30) -> tuple[str, ...]:
    rows: list[str] = []
    for value in list(values or [])[: max(1, int(limit or 1))]:
        clean = _clean_text(value, limit=120)
        if not clean:
            continue
        if allowed is not None and clean not in allowed:
            continue
        if clean not in rows:
            rows.append(clean)
    return tuple(rows)


def _clean_metadata(value: Any, *, depth: int = 3, list_limit: int = 25) -> Any:
    if depth <= 0:
        return _clean_text(value, limit=180)
    if isinstance(value, dict):
        rows: dict[str, Any] = {}
        for key, item in list(value.items())[: max(1, int(list_limit or 1))]:
            clean_key = _clean_id(key, limit=80)
            if not clean_key:
                continue
            rows[clean_key] = _clean_metadata(item, depth=depth - 1, list_limit=list_limit)
        return rows
    if isinstance(value, (list, tuple, set)):
        return [_clean_metadata(item, depth=depth - 1, list_limit=list_limit) for item in list(value)[: max(1, int(list_limit or 1))]]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return value
    return _clean_text(value, limit=240)


@dataclass(frozen=True, slots=True)
class ContextSurface:
    surface_id: str
    surface_type: str
    display_name: str
    what_it_knows: str
    what_it_can_load: str
    what_it_can_do: str = ""
    supported_modes: tuple[str, ...] = ("answer", "search")
    cost_hint: str = "unknown"
    latency_hint: str = "unknown"
    risk_hint: str = "low"
    data_persistence: str = "user_data_preserved"
    empty_behavior: str = "return_source_bound_empty_result"
    loader_contract: str = ""
    executor_contract: str = ""
    guardrail_notes: tuple[str, ...] = ()
    routing_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        surface_id = _clean_id(self.surface_id)
        if not surface_id:
            raise ValueError("surface_id is required")
        surface_type = _clean_id(self.surface_type)
        if not surface_type:
            raise ValueError("surface_type is required")
        object.__setattr__(self, "surface_id", surface_id)
        object.__setattr__(self, "surface_type", surface_type)
        object.__setattr__(self, "display_name", _clean_text(self.display_name or surface_id, limit=160))
        object.__setattr__(self, "what_it_knows", _clean_text(self.what_it_knows, limit=700))
        object.__setattr__(self, "what_it_can_load", _clean_text(self.what_it_can_load, limit=700))
        object.__setattr__(self, "what_it_can_do", _clean_text(self.what_it_can_do, limit=700))
        object.__setattr__(self, "supported_modes", _clean_tuple(self.supported_modes, allowed=SURFACE_MODES) or ("answer",))
        object.__setattr__(self, "cost_hint", self.cost_hint if self.cost_hint in SURFACE_COST_HINTS else "unknown")
        object.__setattr__(self, "latency_hint", self.latency_hint if self.latency_hint in SURFACE_LATENCY_HINTS else "unknown")
        object.__setattr__(self, "risk_hint", self.risk_hint if self.risk_hint in SURFACE_RISK_LEVELS else "low")
        object.__setattr__(self, "data_persistence", _clean_text(self.data_persistence, limit=180) or "user_data_preserved")
        object.__setattr__(self, "empty_behavior", _clean_text(self.empty_behavior, limit=220) or "return_source_bound_empty_result")
        object.__setattr__(self, "loader_contract", _clean_text(self.loader_contract, limit=500))
        object.__setattr__(self, "executor_contract", _clean_text(self.executor_contract, limit=500))
        object.__setattr__(self, "guardrail_notes", _clean_tuple(self.guardrail_notes, limit=12))
        object.__setattr__(self, "routing_metadata", _clean_metadata(self.routing_metadata, depth=3, list_limit=12))
        object.__setattr__(self, "metadata", _clean_metadata(self.metadata, depth=6))

    def as_meta_context(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_type": self.surface_type,
            "display_name": self.display_name,
            "what_it_knows": self.what_it_knows,
            "what_it_can_load": self.what_it_can_load,
            "what_it_can_do": self.what_it_can_do,
            "supported_modes": list(self.supported_modes),
            "cost_hint": self.cost_hint,
            "latency_hint": self.latency_hint,
            "risk_hint": self.risk_hint,
            "data_persistence": self.data_persistence,
            "empty_behavior": self.empty_behavior,
            "guardrail_notes": list(self.guardrail_notes),
            "routing_metadata": dict(self.routing_metadata),
        }

    def as_routing_signature(self) -> dict[str, Any]:
        return {
            "id": self.surface_id,
            "type": self.surface_type,
            "modes": list(self.supported_modes),
            "cost": self.cost_hint,
            "latency": self.latency_hint,
            "risk": self.risk_hint,
            "knows": _clean_text(self.what_it_knows, limit=180),
            "loads": _clean_text(self.what_it_can_load, limit=180),
            "routing": dict(self.routing_metadata),
        }


@dataclass(frozen=True, slots=True)
class ContextRequest:
    surface_id: str
    mode: str
    query: str = ""
    depth: str = "shallow"
    limit: int = 5
    budget: dict[str, Any] = field(default_factory=dict)
    user_id: str = ""
    turn_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", _clean_id(self.surface_id))
        object.__setattr__(self, "mode", self.mode if self.mode in SURFACE_MODES else "answer")
        object.__setattr__(self, "query", _clean_text(self.query, limit=900))
        object.__setattr__(self, "depth", _clean_text(self.depth, limit=80) or "shallow")
        object.__setattr__(self, "limit", max(1, min(50, int(self.limit or 5))))
        object.__setattr__(self, "user_id", _clean_text(self.user_id, limit=160))
        object.__setattr__(self, "turn_id", _clean_text(self.turn_id, limit=160))

    def as_payload(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "mode": self.mode,
            "query": self.query,
            "depth": self.depth,
            "limit": self.limit,
            "budget": dict(self.budget),
            "user_id": self.user_id,
            "turn_id": self.turn_id,
        }


@dataclass(frozen=True, slots=True)
class ContextItem:
    surface_id: str
    title: str
    content: str
    source_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "surface_id": _clean_id(self.surface_id),
            "title": _clean_text(self.title, limit=220),
            "content": _clean_text(self.content, limit=2000),
            "source_ref": _clean_text(self.source_ref, limit=260),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LoadedContextSurface:
    surface_id: str
    status: str
    items: tuple[ContextItem, ...] = ()
    message: str = ""
    latency_ms: int = 0
    cost: dict[str, Any] = field(default_factory=dict)
    debug: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        return {
            "surface_id": _clean_id(self.surface_id),
            "status": _clean_text(self.status, limit=80),
            "items": [item.as_payload() for item in self.items],
            "message": _clean_text(self.message, limit=600),
            "latency_ms": max(0, int(self.latency_ms or 0)),
            "cost": dict(self.cost),
            "debug": list(_clean_tuple(self.debug, limit=30)),
        }


@dataclass(frozen=True, slots=True)
class ContextPacket:
    turn_id: str
    requests: tuple[ContextRequest, ...] = ()
    loaded: tuple[LoadedContextSurface, ...] = ()
    debug: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        return {
            "turn_id": _clean_text(self.turn_id, limit=160),
            "requests": [request.as_payload() for request in self.requests],
            "loaded": [surface.as_payload() for surface in self.loaded],
            "debug": list(_clean_tuple(self.debug, limit=60)),
        }


@dataclass(frozen=True, slots=True)
class TurnFrame:
    surface_id: str = ""
    mode: str = ""
    topic: str = ""
    catalog_ids: tuple[str, ...] = ()
    evidence_policy: str = ""
    answer_mode: str = ""
    source_scope: str = ""
    answer_contract: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", _clean_id(self.surface_id))
        object.__setattr__(self, "mode", self.mode if self.mode in SURFACE_MODES else _clean_id(self.mode))
        object.__setattr__(self, "topic", _clean_text(self.topic, limit=500))
        object.__setattr__(self, "catalog_ids", _clean_tuple(self.catalog_ids, limit=12))
        object.__setattr__(self, "evidence_policy", _clean_text(self.evidence_policy, limit=80))
        object.__setattr__(self, "answer_mode", _clean_text(self.answer_mode, limit=80))
        object.__setattr__(self, "source_scope", _clean_text(self.source_scope, limit=160))
        object.__setattr__(self, "answer_contract", _clean_text(self.answer_contract, limit=240))
        object.__setattr__(self, "confidence", max(0.0, min(1.0, float(self.confidence or 0.0))))

    def as_payload(self) -> dict[str, Any]:
        if not self.surface_id and not self.mode and not self.topic:
            return {}
        return {
            "surface_id": self.surface_id,
            "mode": self.mode,
            "topic": self.topic,
            "catalog_ids": list(self.catalog_ids),
            "evidence_policy": self.evidence_policy,
            "answer_mode": self.answer_mode,
            "source_scope": self.source_scope,
            "answer_contract": self.answer_contract,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class RuntimeOutcomeFrame:
    frame_type: str = "runtime_outcome"
    surface_id: str = ""
    kind: str = ""
    capability: str = ""
    task_intent: str = ""
    command: str = ""
    targets: tuple[str, ...] = ()
    records: tuple[dict[str, Any], ...] = ()
    summary: str = ""
    followup_affordances: tuple[str, ...] = ()
    confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_type", _clean_id(self.frame_type or "runtime_outcome"))
        object.__setattr__(self, "surface_id", _clean_id(self.surface_id))
        object.__setattr__(self, "kind", _clean_id(self.kind))
        object.__setattr__(self, "capability", _clean_id(self.capability))
        object.__setattr__(self, "task_intent", _clean_id(self.task_intent))
        object.__setattr__(self, "command", _clean_text(self.command, limit=240))
        object.__setattr__(self, "targets", _clean_tuple(self.targets, limit=80))
        object.__setattr__(self, "summary", _clean_text(self.summary, limit=1200))
        object.__setattr__(self, "followup_affordances", _clean_tuple(self.followup_affordances, limit=20))
        object.__setattr__(self, "confidence", max(0.0, min(1.0, float(self.confidence or 0.0))))
        clean_records: list[dict[str, Any]] = []
        for row in list(self.records or [])[:80]:
            if not isinstance(row, dict):
                continue
            clean_records.append(
                {
                    "ref": _clean_text(row.get("ref", ""), limit=120),
                    "state": _clean_text(row.get("state", ""), limit=80),
                    "text": _clean_text(row.get("text", ""), limit=2400),
                    "raw_text": _clean_text(row.get("raw_text", ""), limit=4000),
                }
            )
        object.__setattr__(self, "records", tuple(clean_records))

    def as_payload(self) -> dict[str, Any]:
        if not self.surface_id and not self.capability and not self.records:
            return {}
        return {
            "frame_type": self.frame_type,
            "surface_id": self.surface_id,
            "kind": self.kind,
            "capability": self.capability,
            "task_intent": self.task_intent,
            "command": self.command,
            "targets": list(self.targets),
            "records": [dict(row) for row in self.records],
            "summary": self.summary,
            "followup_affordances": list(self.followup_affordances),
            "confidence": self.confidence,
        }


class SurfaceRegistry:
    def __init__(self, surfaces: Iterable[ContextSurface] = ()) -> None:
        self._surfaces: dict[str, ContextSurface] = {}
        for surface in surfaces:
            self.register(surface)

    def register(self, surface: ContextSurface) -> None:
        if surface.surface_id in self._surfaces:
            raise ValueError(f"Duplicate context surface: {surface.surface_id}")
        self._surfaces[surface.surface_id] = surface

    def get(self, surface_id: str) -> ContextSurface | None:
        return self._surfaces.get(_clean_id(surface_id))

    def all(self) -> tuple[ContextSurface, ...]:
        return tuple(self._surfaces.values())

    def surface_ids(self) -> tuple[str, ...]:
        return tuple(self._surfaces.keys())

    def as_routing_meta_context(self) -> dict[str, Any]:
        return {
            "surfaces": [surface.as_meta_context() for surface in self.all()],
            "contract": {
                "meaning": "The LLM may select only registered surface_id values.",
                "no_trigger_words": True,
                "new_surfaces_extend_by_registration": True,
                "stage_1_is_meta_only": True,
                "deep_inventory_loads_after_selection": True,
                "user_data_policy": "preserve_existing_user_data; adapt loaders instead of deleting connections, notes, memories, or documents",
            },
        }

    def as_compact_routing_meta_context(self) -> dict[str, Any]:
        return {
            "surfaces": [surface.as_routing_signature() for surface in self.all()],
            "contract": {
                "select_registered_surface_ids_only": True,
                "no_trigger_words": True,
                "stage_1_meta_only": True,
                "deep_context_after_selection": True,
                "preserve_user_data": True,
            },
        }

    def validate_requests(self, requests: Iterable[ContextRequest]) -> tuple[ContextRequest, ...]:
        valid: list[ContextRequest] = []
        for request in requests:
            surface = self.get(request.surface_id)
            if surface is None:
                continue
            if request.mode not in surface.supported_modes:
                continue
            valid.append(request)
        return tuple(valid)
