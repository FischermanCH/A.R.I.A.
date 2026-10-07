from __future__ import annotations

from typing import Any

from aria.modules.configuration_foundations.config import Settings
from aria.modules.qdrant_gateway.client import create_async_qdrant_client
from aria.modules.connection_routing.admin import ensure_connection_routing_index_ready
from aria.modules.connection_routing.admin import resolve_connection_routing_chain


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
