from __future__ import annotations

from typing import Any

from aria.core.action_plan import MemoryHints
from aria.core.config import Settings
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.routing_admin import ensure_connection_routing_index_ready
from aria.core.routing_admin import resolve_connection_routing_chain
from aria.core.routing_admin import routing_connections_collection_name
from aria.core.routing_index import DEFAULT_CONNECTION_ROUTING_KINDS
from aria.core.routing_index import RoutingIndexStore
from aria.core.routing_resolver import RoutingResolver


def qdrant_routing_enabled(settings: Settings) -> bool:
    return bool(getattr(settings.routing, "qdrant_connection_routing_enabled", False))


def qdrant_routing_limit(settings: Settings) -> int:
    try:
        return max(1, min(20, int(getattr(settings.routing, "qdrant_candidate_limit", 5) or 5)))
    except (TypeError, ValueError):
        return 5


def qdrant_routing_threshold(settings: Settings) -> float:
    try:
        return max(0.0, min(1.0, float(getattr(settings.routing, "qdrant_score_threshold", 0.72) or 0.0)))
    except (TypeError, ValueError):
        return 0.72


def qdrant_ask_on_low_confidence(settings: Settings) -> bool:
    return bool(getattr(settings.routing, "qdrant_ask_on_low_confidence", True))


def settings_without_qdrant_routing(settings: Settings) -> Settings:
    clone = settings.model_copy(deep=True)
    try:
        clone.memory.enabled = False
    except Exception:
        pass
    return clone


async def resolve_qdrant_connection_hint(
    *,
    settings: Settings,
    embedding_client: Any,
    usage_meter: Any,
    message: str,
    connection_pools: dict[str, dict[str, Any]],
    preferred_kind: str = "",
    routing_debug_enabled: bool = False,
    create_async_qdrant_client_fn: Any = create_async_qdrant_client,
    ensure_connection_routing_index_ready_fn: Any = ensure_connection_routing_index_ready,
    routing_connections_collection_name_fn: Any = routing_connections_collection_name,
    routing_index_store_cls: Any = RoutingIndexStore,
) -> tuple[MemoryHints, list[str], bool]:
    def _debug_line(text: str) -> list[str]:
        return [text] if routing_debug_enabled and str(text or "").strip() else []

    if not qdrant_routing_enabled(settings):
        return MemoryHints(), [], False
    clean_kind = str(preferred_kind or "").strip().lower()
    if clean_kind and clean_kind not in set(DEFAULT_CONNECTION_ROUTING_KINDS):
        return MemoryHints(), _debug_line(f"Routing: Qdrant skipped for unsupported kind `{clean_kind}`."), False
    if clean_kind and clean_kind not in connection_pools:
        return MemoryHints(), [], False

    refresh_meta = await ensure_connection_routing_index_ready_fn(
        settings,
        embedding_client=embedding_client,
        usage_meter=usage_meter,
    )
    status = dict(refresh_meta.get("status", {}) or {})
    if status.get("status") == "error":
        return (
            MemoryHints(),
            _debug_line(
                f"Routing: Qdrant skipped, index status failed: {status.get('detail') or status.get('message') or 'unknown'}"
            ),
            qdrant_ask_on_low_confidence(settings),
        )
    if str(status.get("status", "") or "").lower() != "ok":
        return (
            MemoryHints(),
            _debug_line(
                f"Routing: Qdrant skipped, index is not ready: {status.get('message') or 'unknown'}"
            ),
            qdrant_ask_on_low_confidence(settings),
        )

    memory = settings.memory
    qdrant = create_async_qdrant_client_fn(
        url=memory.qdrant_url,
        api_key=getattr(memory, "qdrant_api_key", "") or None,
        timeout=8,
    )
    try:
        store = routing_index_store_cls(
            qdrant=qdrant,
            embedding_client=embedding_client,
            collection_name=routing_connections_collection_name_fn(settings),
        )
        resolver = RoutingResolver(candidate_provider=store)
        decision = await resolver.resolve_connection(
            message,
            connection_pools,
            preferred_kind=clean_kind,
            qdrant_limit=qdrant_routing_limit(settings),
            qdrant_score_threshold=qdrant_routing_threshold(settings),
        )
    finally:
        close = getattr(qdrant, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result

    if not decision.found:
        candidate_count = len(decision.candidates)
        if candidate_count:
            return (
                MemoryHints(),
                _debug_line(f"Routing: Qdrant returned {candidate_count} candidate(s), none accepted."),
                qdrant_ask_on_low_confidence(settings),
            )
        return (
            MemoryHints(),
            _debug_line("Routing: Qdrant found no accepted candidate."),
            qdrant_ask_on_low_confidence(settings),
        )

    detail = _debug_line(
        f"Routing: Qdrant selected `{decision.kind}/{decision.ref}` "
        f"score={decision.score:.3f} source={decision.source}."
    )
    return (
        MemoryHints(
            connection_kind=decision.kind,
            connection_ref=decision.ref,
            source=decision.source or "qdrant_routing",
            notes=[f"qdrant_routing:{decision.kind}/{decision.ref}:{decision.score:.3f}"],
        ),
        detail,
        False,
    )


async def resolve_live_routing_chain(
    *,
    settings: Settings,
    embedding_client: Any,
    usage_meter: Any,
    message: str,
    preferred_kind: str = "",
    llm_client: Any | None,
    language: str | None = None,
    routing_debug_enabled: bool = False,
    create_async_qdrant_client_fn: Any = create_async_qdrant_client,
    ensure_connection_routing_index_ready_fn: Any = ensure_connection_routing_index_ready,
    resolve_connection_routing_chain_fn: Any = resolve_connection_routing_chain,
) -> dict[str, Any]:
    def _debug_line(text: str) -> list[str]:
        return [text] if routing_debug_enabled and str(text or "").strip() else []

    chain_settings = settings
    detail_lines: list[str] = []
    qdrant_client: Any | None = None
    close_client = False

    memory = getattr(settings, "memory", None)
    memory_uses_qdrant = bool(
        memory is not None
        and bool(getattr(memory, "enabled", False))
        and str(getattr(memory, "backend", "") or "").strip().lower() == "qdrant"
    )
    if memory_uses_qdrant:
        if not qdrant_routing_enabled(settings):
            chain_settings = settings_without_qdrant_routing(settings)
        else:
            refresh_meta = await ensure_connection_routing_index_ready_fn(
                settings,
                embedding_client=embedding_client,
                usage_meter=usage_meter,
            )
            status = dict(refresh_meta.get("status", {}) or {})
            status_value = str(status.get("status", "") or "").strip().lower()
            if status_value == "error":
                detail_lines.extend(
                    _debug_line(
                        f"Routing: Qdrant skipped, index status failed: {status.get('detail') or status.get('message') or 'unknown'}"
                    )
                )
                chain_settings = settings_without_qdrant_routing(settings)
            elif status_value and status_value != "ok":
                detail_lines.extend(
                    _debug_line(
                        f"Routing: Qdrant skipped, index is not ready: {status.get('message') or 'unknown'}"
                    )
                )
                chain_settings = settings_without_qdrant_routing(settings)
            else:
                qdrant_client = create_async_qdrant_client_fn(
                    url=memory.qdrant_url,
                    api_key=getattr(memory, "qdrant_api_key", "") or None,
                    timeout=8,
                )
                close_client = True

    try:
        resolved = await resolve_connection_routing_chain_fn(
            chain_settings,
            message,
            preferred_kind=preferred_kind,
            llm_client=llm_client,
            qdrant_client=qdrant_client,
            embedding_client=embedding_client,
            usage_meter=usage_meter,
            language=str(language or ""),
            limit=qdrant_routing_limit(settings),
            score_threshold=qdrant_routing_threshold(settings),
        )
    finally:
        if close_client and qdrant_client is not None:
            close = getattr(qdrant_client, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result

    existing_details = [
        str(item or "").strip()
        for item in list(resolved.get("detail_lines", []) or [])
        if str(item or "").strip()
    ]
    if detail_lines or existing_details:
        resolved["detail_lines"] = [*detail_lines, *existing_details]
    return resolved
