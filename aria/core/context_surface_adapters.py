from __future__ import annotations

from typing import Any, Iterable

from aria.core.connection_catalog import (
    connection_kind_label,
    connection_menu_meta,
    connection_routing_spec,
    ordered_connection_kinds,
)
from aria.core.context_surfaces import ContextSurface, SurfaceRegistry


SECRET_FIELD_NAMES = {
    "api_key",
    "auth_token",
    "ical_url",
    "key_path",
    "password",
    "private_key",
    "secret",
    "token",
    "url",
    "webhook_url",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            dumped = dict_method()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    return {}


def _iter_configured_connection_rows(settings: Any) -> Iterable[tuple[str, str, dict[str, Any]]]:
    connections = getattr(settings, "connections", None)
    for kind in ordered_connection_kinds():
        rows = _as_dict(getattr(connections, kind, {}))
        for ref, raw_row in rows.items():
            clean_ref = str(ref or "").strip()
            if not clean_ref:
                continue
            yield kind, clean_ref, _as_dict(raw_row)


def _safe_connection_summary(row: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for field in ("title", "description", "aliases", "tags", "group_name", "calendar_id", "mailbox"):
        if field in SECRET_FIELD_NAMES:
            continue
        value = row.get(field)
        if value in (None, "", [], {}):
            continue
        summary[field] = value
    return summary


def _connection_inventory_metadata(settings: Any) -> dict[str, Any]:
    by_kind: dict[str, dict[str, Any]] = {}
    for kind in ordered_connection_kinds():
        spec = connection_routing_spec(kind)
        menu_meta = connection_menu_meta(kind)
        by_kind[kind] = {
            "label": connection_kind_label(kind),
            "configured_count": 0,
            "configured_refs": [],
            "safe_summaries": [],
            "config_page": menu_meta.get("url", ""),
            "supported_actions": list(spec.supported_actions),
        }
    for kind, ref, row in _iter_configured_connection_rows(settings):
        entry = by_kind.setdefault(
            kind,
            {
                "label": connection_kind_label(kind),
                "configured_count": 0,
                "configured_refs": [],
                "safe_summaries": [],
                "config_page": "",
                "supported_actions": [],
            },
        )
        entry["configured_count"] = int(entry.get("configured_count", 0) or 0) + 1
        refs = list(entry.get("configured_refs", []) or [])
        refs.append(ref)
        entry["configured_refs"] = refs[:200]
        safe_summary = _safe_connection_summary(row)
        if safe_summary:
            summaries = list(entry.get("safe_summaries", []) or [])
            summaries.append({"ref": ref, **safe_summary})
            entry["safe_summaries"] = summaries[:200]
    configured = {kind: meta for kind, meta in by_kind.items() if int(meta.get("configured_count", 0) or 0) > 0}
    return {
        "configured_total": sum(int(meta.get("configured_count", 0) or 0) for meta in by_kind.values()),
        "configured_kinds": sorted(configured),
        "configured": configured,
        "available_kinds": list(by_kind.keys()),
    }


def _connection_routing_metadata(settings: Any) -> dict[str, Any]:
    inventory = _connection_inventory_metadata(settings)
    configured_kinds = list(inventory.get("configured_kinds") or [])
    return {
        "configured_total": int(inventory.get("configured_total", 0) or 0),
        "configured_kinds": configured_kinds,
        "configured_kind_labels": {
            kind: connection_kind_label(kind)
            for kind in configured_kinds[:20]
        },
        "inventory_is_safe_to_load": True,
        "secrets_available_to_router": False,
    }


def build_memory_surface(settings: Any | None = None) -> ContextSurface:
    memory = getattr(settings, "memory", None)
    collections = getattr(memory, "collections", None)
    metadata = {
        "enabled": bool(getattr(memory, "enabled", True)),
        "backend": str(getattr(memory, "backend", "qdrant") or "qdrant"),
        "collection": str(getattr(memory, "collection", "aria_memory") or "aria_memory"),
        "top_k_default": int(getattr(memory, "top_k", 3) or 3),
        "collection_prefixes": {
            name: str(getattr(getattr(collections, name, None), "prefix", "") or "")
            for name in ("facts", "preferences", "sessions", "knowledge")
            if getattr(collections, name, None) is not None
        },
    }
    return ContextSurface(
        surface_id="memory",
        surface_type="local_context",
        display_name="Memory",
        what_it_knows="Durable user facts, preferences, prior sessions, learning reflections, candidates, evals, and remembered project context.",
        what_it_can_load="Source-bound snippets from configured local memory and learning collections, with explicit empty results when nothing matches.",
        what_it_can_do="Store or update memories only through reviewable memory/learning contracts.",
        supported_modes=("answer", "exists", "search", "inventory", "learn", "summarize"),
        cost_hint="cheap",
        latency_hint="fast",
        risk_hint="low",
        loader_contract="Load bounded, source-bound local memory context for a structured ContextRequest; never invent access when no sources load.",
        executor_contract="Memory writes require the existing memory/learning write contract and user/policy permissions.",
        guardrail_notes=("Do not expose hidden system data.", "Preserve existing memory collections."),
        routing_metadata={
            "enabled": metadata["enabled"],
            "backend": metadata["backend"],
            "families": list(metadata["collection_prefixes"].keys()),
        },
        metadata=metadata,
    )


def build_notes_surface(settings: Any | None = None) -> ContextSurface:
    return ContextSurface(
        surface_id="notes",
        surface_type="local_context",
        display_name="Notes",
        what_it_knows="User-maintained notes, project notes, and note metadata stored by ARIA.",
        what_it_can_load="Matching note excerpts and note inventory, or a source-bound empty result.",
        what_it_can_do="Create, update, or search notes only through guarded note contracts.",
        supported_modes=("answer", "exists", "search", "inventory", "summarize", "action"),
        cost_hint="cheap",
        latency_hint="fast",
        risk_hint="low",
        loader_contract="Load note context only for selected ContextRequests; notes are not a terminal pre-pipeline side-flow.",
        executor_contract="Note mutations require an explicit action plan and existing notes guardrails.",
        guardrail_notes=("Preserve existing notes.", "Do not convert missing note results into generic chat claims."),
        routing_metadata={"configured": True},
        metadata={"configured": True},
    )


def build_docs_surface(settings: Any | None = None) -> ContextSurface:
    return ContextSurface(
        surface_id="docs",
        surface_type="local_context",
        display_name="Documents",
        what_it_knows="Imported documents, project documentation, and indexed document chunks.",
        what_it_can_load="Relevant document excerpts, source references, and document inventory.",
        what_it_can_do="Answer or summarize from loaded document context; document writes/imports stay behind explicit UI or action contracts.",
        supported_modes=("answer", "exists", "search", "inventory", "summarize"),
        cost_hint="cheap",
        latency_hint="medium",
        risk_hint="low",
        loader_contract="Load document chunks for a bounded query and return source-bound empty results when no document matches.",
        guardrail_notes=("Preserve imported documents.",),
        routing_metadata={"configured": True},
        metadata={"configured": True},
    )


def build_connections_surface(settings: Any | None = None) -> ContextSurface:
    return ContextSurface(
        surface_id="connections",
        surface_type="inventory_and_runtime",
        display_name="Connections",
        what_it_knows="Configured connection inventory, safe refs, non-secret metadata, service types, and available guarded runtime adapters.",
        what_it_can_load="Connection inventory, safe metadata, related services, and candidate target context without exposing secrets.",
        what_it_can_do="Propose or execute guarded actions only through registered connection executors, policy, confirmation, and dry-run contracts.",
        supported_modes=("answer", "inventory", "search", "action", "clarify"),
        cost_hint="free",
        latency_hint="instant",
        risk_hint="medium",
        loader_contract="Load safe connection inventory and matching non-secret metadata for structured ContextRequests.",
        executor_contract="Connection actions require executor-specific schema validation, guardrails, policy, permissions, and confirmation where required.",
        guardrail_notes=("Never expose secrets.", "Preserve configured connections and refs.", "Actions must pass guardrails before runtime."),
        routing_metadata=_connection_routing_metadata(settings),
        metadata=_connection_inventory_metadata(settings),
    )


def build_web_surface(settings: Any | None = None) -> ContextSurface:
    searxng = getattr(getattr(settings, "connections", None), "searxng", {})
    metadata = {
        "configured_count": len(_as_dict(searxng)),
        "default_available": True,
    }
    return ContextSurface(
        surface_id="web",
        surface_type="external_context",
        display_name="Web",
        what_it_knows="Fresh external web/search/page context through configured web search adapters.",
        what_it_can_load="Search results, fetched page excerpts, URLs, titles, and source references.",
        what_it_can_do="Fetch or search external sources when the TurnPlan selects web context.",
        supported_modes=("answer", "search", "summarize"),
        cost_hint="medium",
        latency_hint="slow",
        risk_hint="low",
        loader_contract="Load fresh external context only when selected; include source refs and freshness/debug information.",
        guardrail_notes=("Prefer direct source refs for factual claims.",),
        routing_metadata=metadata,
        metadata=metadata,
    )


def build_builtin_surface_registry(settings: Any | None = None) -> SurfaceRegistry:
    return SurfaceRegistry(
        [
            build_memory_surface(settings),
            build_notes_surface(settings),
            build_docs_surface(settings),
            build_connections_surface(settings),
            build_web_surface(settings),
        ]
    )
