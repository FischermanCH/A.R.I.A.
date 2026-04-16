from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any

from aria.core.embedding_client import EmbeddingClient
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.routing_index import (
    DEFAULT_CONNECTION_ROUTING_KINDS,
    RoutingIndexStore,
    build_connection_routing_documents,
    routing_collection_name,
    routing_documents_fingerprint,
)
from aria.core.routing_resolver import RoutingDecision, RoutingResolver, infer_preferred_connection_kind


def routing_index_instance_key(settings: Any) -> str:
    """Return a stable per-instance key for generated routing collections."""

    public_url = str(getattr(getattr(settings, "aria", None), "public_url", "") or "").strip()
    if public_url:
        return public_url
    title = str(getattr(getattr(settings, "ui", None), "title", "") or "").strip()
    port = str(getattr(getattr(settings, "aria", None), "port", "") or "").strip()
    return " ".join(part for part in (title, port) if part)


def routing_connections_collection_name(settings: Any) -> str:
    return routing_collection_name(
        "connections",
        instance_key=routing_index_instance_key(settings),
    )


def _available_connection_pools(settings: Any) -> dict[str, dict[str, Any]]:
    connections = getattr(settings, "connections", None)
    if connections is None:
        return {}
    pools: dict[str, dict[str, Any]] = {}
    for kind in DEFAULT_CONNECTION_ROUTING_KINDS:
        clean_kind = normalize_connection_kind(kind)
        rows = getattr(connections, clean_kind, {})
        if isinstance(rows, dict) and rows:
            pools[clean_kind] = dict(rows)
    return pools


def _decision_payload(decision: RoutingDecision) -> dict[str, Any]:
    return {
        "found": decision.found,
        "kind": decision.kind,
        "ref": decision.ref,
        "capability": decision.capability,
        "source": decision.source,
        "score": float(decision.score),
        "reason": decision.reason,
    }


def _candidate_reject_reason(
    candidate: dict[str, Any],
    available_connection_pools: dict[str, dict[str, Any]],
    *,
    preferred_kind: str = "",
) -> str:
    kind = normalize_connection_kind(str(candidate.get("kind", "") or ""))
    ref = str(candidate.get("ref", "") or "").strip()
    if not kind or not ref:
        return "candidate has no kind/ref"
    clean_preferred = normalize_connection_kind(preferred_kind)
    if clean_preferred and kind != clean_preferred:
        return f"kind {kind} does not match preferred kind {clean_preferred}"
    pool = available_connection_pools.get(kind, {})
    if not isinstance(pool, dict) or not pool:
        return f"no configured {kind} profiles"
    configured_refs = {str(configured_ref).strip().lower() for configured_ref in pool}
    if ref.lower() not in configured_refs:
        return f"profile {ref} is not configured"
    return ""


def _safe_candidate_payload_preview(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(payload.get("title", "") or "").strip(),
        "description": str(payload.get("description", "") or "").strip(),
        "aliases": list(payload.get("aliases", []) or [])[:8],
        "tags": list(payload.get("tags", []) or [])[:8],
        "supported_actions": list(payload.get("supported_actions", []) or [])[:8],
        "target_hints": list(payload.get("target_hints", []) or [])[:8],
    }


def _debug_candidate_rows(
    candidates: list[dict[str, Any]],
    available_connection_pools: dict[str, dict[str, Any]],
    *,
    preferred_kind: str = "",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        resolved = RoutingResolver._qdrant_candidate_is_valid(
            candidate,
            available_connection_pools,
            preferred_kind=preferred_kind,
        )
        reject_reason = "" if resolved else _candidate_reject_reason(
            candidate,
            available_connection_pools,
            preferred_kind=preferred_kind,
        )
        payload = dict(candidate.get("payload", {}) or {})
        rows.append(
            {
                "accepted": bool(resolved),
                "reject_reason": reject_reason,
                "kind": normalize_connection_kind(str(candidate.get("kind", "") or "")),
                "ref": str(candidate.get("ref", "") or "").strip(),
                "score": float(candidate.get("score", 0.0) or 0.0),
                "source": str(candidate.get("source", "") or "qdrant_routing"),
                "reason": str(candidate.get("reason", "") or "").strip(),
                "payload": _safe_candidate_payload_preview(payload),
            }
        )
    rows.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
    return rows


def _status_payload(
    *,
    status: str,
    message: str,
    collection_name: str,
    document_count: int,
    indexed_count: int | None = None,
    collection_names: list[str] | None = None,
    detail: str = "",
    embedding_model: str = "",
    embedding_usage: dict[str, int] | None = None,
    current_config_hash: str = "",
    indexed_config_hash: str = "",
    stale: bool = False,
) -> dict[str, Any]:
    clean_status = str(status or "warn").strip().lower() or "warn"
    if clean_status not in {"ok", "warn", "error"}:
        clean_status = "warn"
    return {
        "status": clean_status,
        "visual_status": clean_status,
        "message": message,
        "detail": detail,
        "collection_name": collection_name,
        "collection_names": list(collection_names or []),
        "collection_count": len(collection_names or []),
        "document_count": int(document_count),
        "indexed_count": indexed_count,
        "embedding_model": embedding_model,
        "embedding_usage": dict(embedding_usage or {}),
        "current_config_hash": current_config_hash,
        "indexed_config_hash": indexed_config_hash,
        "stale": bool(stale),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _memory_is_qdrant(settings: Any) -> tuple[bool, str]:
    memory = getattr(settings, "memory", None)
    if memory is None:
        return False, "Memory configuration is missing."
    if not bool(getattr(memory, "enabled", False)):
        return False, "Memory is disabled; routing index is not available."
    backend = str(getattr(memory, "backend", "") or "").strip().lower()
    if backend != "qdrant":
        return False, f"Memory backend is {backend or 'unset'}, not qdrant."
    qdrant_url = str(getattr(memory, "qdrant_url", "") or "").strip()
    if not qdrant_url:
        return False, "Qdrant URL is not configured."
    return True, ""


async def _maybe_close(client: Any) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def _list_routing_collections(qdrant: Any, base_name: str) -> list[str]:
    try:
        response = await qdrant.get_collections()
    except Exception:
        try:
            exists = await qdrant.collection_exists(collection_name=base_name)
        except Exception:
            return []
        return [base_name] if exists else []

    result = getattr(response, "result", response)
    raw_collections = getattr(result, "collections", [])
    rows: list[str] = []
    for item in raw_collections or []:
        name = str(getattr(item, "name", "") or "").strip()
        if name == base_name or name.startswith(f"{base_name}_dim_"):
            rows.append(name)
    return sorted(set(rows))


async def _collection_point_count(qdrant: Any, collection_name: str) -> int | None:
    try:
        info = await qdrant.get_collection(collection_name=collection_name)
    except Exception:
        return None
    result = getattr(info, "result", info)
    for attr in ("points_count", "vectors_count", "indexed_vectors_count"):
        value = getattr(result, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    count = getattr(qdrant, "count", None)
    if count is None:
        return None
    try:
        response = await count(collection_name=collection_name, exact=True)
    except Exception:
        return None
    value = getattr(response, "count", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _extract_scroll_points(scroll_result: Any) -> list[Any]:
    if scroll_result is None:
        return []
    if isinstance(scroll_result, tuple) and scroll_result:
        first = scroll_result[0]
        return first if isinstance(first, list) else []
    if isinstance(scroll_result, list):
        return scroll_result
    points = getattr(scroll_result, "points", None)
    if isinstance(points, list):
        return points
    result = getattr(scroll_result, "result", None)
    if isinstance(result, tuple) and result:
        first = result[0]
        return first if isinstance(first, list) else []
    if isinstance(result, list):
        return result
    return []


async def _collection_routing_index_hash(qdrant: Any, collection_name: str) -> str:
    scroll = getattr(qdrant, "scroll", None)
    if scroll is None:
        return ""
    try:
        result = await scroll(
            collection_name=collection_name,
            limit=16,
            with_payload=True,
            with_vectors=False,
        )
    except Exception:
        return ""
    for point in _extract_scroll_points(result):
        payload = dict(getattr(point, "payload", {}) or {})
        value = str(payload.get("routing_index_hash", "") or "").strip()
        if value:
            return value
    return ""


async def _indexed_routing_hash(qdrant: Any, collection_names: list[str]) -> str:
    for collection_name in collection_names:
        value = await _collection_routing_index_hash(qdrant, collection_name)
        if value:
            return value
    return ""


async def build_connection_routing_index_status(
    settings: Any,
    *,
    qdrant_client: Any | None = None,
) -> dict[str, Any]:
    documents = build_connection_routing_documents(settings)
    collection_name = routing_connections_collection_name(settings)
    document_count = len(documents)
    current_hash = routing_documents_fingerprint(documents)
    qdrant_enabled, reason = _memory_is_qdrant(settings)
    if not qdrant_enabled:
        return _status_payload(
            status="warn",
            message=reason,
            collection_name=collection_name,
            document_count=document_count,
            current_config_hash=current_hash,
        )
    if document_count == 0:
        return _status_payload(
            status="ok",
            message="No routable connection profiles configured.",
            collection_name=collection_name,
            document_count=0,
            indexed_count=0,
            current_config_hash=current_hash,
            indexed_config_hash=current_hash,
        )

    created_client = qdrant_client is None
    qdrant = qdrant_client
    if qdrant is None:
        memory = settings.memory
        qdrant = create_async_qdrant_client(
            url=memory.qdrant_url,
            api_key=getattr(memory, "qdrant_api_key", "") or None,
            timeout=4,
        )

    try:
        collection_names = await _list_routing_collections(qdrant, collection_name)
        if not collection_names:
            return _status_payload(
                status="warn",
                message="Routing index has not been built yet.",
                collection_name=collection_name,
                document_count=document_count,
                indexed_count=0,
                current_config_hash=current_hash,
            )

        counts = [await _collection_point_count(qdrant, name) for name in collection_names]
        known_counts = [count for count in counts if count is not None]
        indexed_count = sum(known_counts) if known_counts else None
        indexed_hash = await _indexed_routing_hash(qdrant, collection_names)
        stale = bool(indexed_hash and indexed_hash != current_hash)
        if not indexed_hash:
            status = "warn"
            message = "Routing index metadata is missing; rebuild recommended."
        elif stale:
            status = "warn"
            message = "Routing index may be outdated; rebuild recommended."
        elif indexed_count is None:
            status = "ok"
            message = "Routing index collection exists; point count is not available."
        elif indexed_count < document_count:
            status = "warn"
            message = f"Routing index is incomplete: {indexed_count}/{document_count} profiles indexed."
        else:
            status = "ok"
            message = f"Routing index ready: {indexed_count}/{document_count} profiles indexed."
        return _status_payload(
            status=status,
            message=message,
            collection_name=collection_name,
            collection_names=collection_names,
            document_count=document_count,
            indexed_count=indexed_count,
            current_config_hash=current_hash,
            indexed_config_hash=indexed_hash,
            stale=stale or not bool(indexed_hash),
        )
    except Exception as exc:
        return _status_payload(
            status="error",
            message="Routing index status check failed.",
            collection_name=collection_name,
            document_count=document_count,
            detail=str(exc),
            current_config_hash=current_hash,
        )
    finally:
        if created_client and qdrant is not None:
            await _maybe_close(qdrant)


async def rebuild_connection_routing_index(
    settings: Any,
    *,
    qdrant_client: Any | None = None,
    embedding_client: Any | None = None,
) -> dict[str, Any]:
    documents = build_connection_routing_documents(settings)
    collection_name = routing_connections_collection_name(settings)
    document_count = len(documents)
    current_hash = routing_documents_fingerprint(documents)
    qdrant_enabled, reason = _memory_is_qdrant(settings)
    if not qdrant_enabled:
        return _status_payload(
            status="warn",
            message=reason,
            collection_name=collection_name,
            document_count=document_count,
            current_config_hash=current_hash,
        )
    if document_count == 0:
        return _status_payload(
            status="ok",
            message="No routable connection profiles configured.",
            collection_name=collection_name,
            document_count=0,
            indexed_count=0,
            current_config_hash=current_hash,
            indexed_config_hash=current_hash,
        )

    created_client = qdrant_client is None
    qdrant = qdrant_client
    if qdrant is None:
        memory = settings.memory
        qdrant = create_async_qdrant_client(
            url=memory.qdrant_url,
            api_key=getattr(memory, "qdrant_api_key", "") or None,
            timeout=10,
        )
    embedder = embedding_client or EmbeddingClient(settings.embeddings)

    try:
        store = RoutingIndexStore(
            qdrant=qdrant,
            embedding_client=embedder,
            collection_name=collection_name,
        )
        result = await store.upsert_documents(documents, index_hash=current_hash)
        indexed_count = int(result.get("documents", 0) or 0)
        collections = [str(name) for name in result.get("collections", []) if str(name).strip()]
        indexed_hash = str(result.get("routing_index_hash", "") or "").strip()
        status = "ok" if indexed_count >= document_count else "warn"
        if status == "ok":
            message = f"Routing index rebuilt: {indexed_count}/{document_count} profiles indexed."
        else:
            message = f"Routing index rebuild incomplete: {indexed_count}/{document_count} profiles indexed."
        return _status_payload(
            status=status,
            message=message,
            collection_name=collection_name,
            collection_names=collections,
            document_count=document_count,
            indexed_count=indexed_count,
            embedding_model=str(result.get("embedding_model", "") or ""),
            embedding_usage=dict(result.get("embedding_usage", {}) or {}),
            current_config_hash=current_hash,
            indexed_config_hash=indexed_hash,
            stale=bool(indexed_hash and indexed_hash != current_hash),
        )
    except Exception as exc:
        return _status_payload(
            status="error",
            message="Routing index rebuild failed.",
            collection_name=collection_name,
            document_count=document_count,
            detail=str(exc),
            current_config_hash=current_hash,
        )
    finally:
        if created_client and qdrant is not None:
            await _maybe_close(qdrant)


async def test_connection_routing_query(
    settings: Any,
    query: str,
    *,
    preferred_kind: str = "",
    qdrant_client: Any | None = None,
    embedding_client: Any | None = None,
    limit: int = 5,
    score_threshold: float = 0.0,
) -> dict[str, Any]:
    clean_query = str(query or "").strip()
    clean_preferred = normalize_connection_kind(preferred_kind)
    if clean_preferred == "auto":
        clean_preferred = ""

    available_pools = _available_connection_pools(settings)
    requested_preferred = clean_preferred or "auto"
    inferred_preferred = infer_preferred_connection_kind(
        clean_query,
        explicit_kind=clean_preferred,
        available_kinds=available_pools.keys(),
    )
    effective_preferred = inferred_preferred or clean_preferred
    available_counts = {kind: len(rows) for kind, rows in sorted(available_pools.items())}
    deterministic = RoutingResolver._deterministic_connection_match(
        clean_query,
        available_pools,
        preferred_kind=effective_preferred,
    )

    qdrant_enabled, qdrant_reason = _memory_is_qdrant(settings)
    qdrant_error = ""
    qdrant_candidates: list[dict[str, Any]] = []
    created_client = qdrant_client is None
    qdrant = qdrant_client

    if clean_query and qdrant_enabled:
        try:
            if qdrant is None:
                memory = settings.memory
                qdrant = create_async_qdrant_client(
                    url=memory.qdrant_url,
                    api_key=getattr(memory, "qdrant_api_key", "") or None,
                    timeout=8,
                )
            embedder = embedding_client or EmbeddingClient(settings.embeddings)
            store = RoutingIndexStore(
                qdrant=qdrant,
                embedding_client=embedder,
                collection_name=routing_connections_collection_name(settings),
            )
            query_limit = max(1, int(limit))
            if effective_preferred:
                query_limit = max(query_limit, min(50, query_limit * 4))
            qdrant_candidates = await store.query_connections(
                clean_query,
                limit=query_limit,
                score_threshold=float(score_threshold),
            )
        except Exception as exc:
            qdrant_error = str(exc)
        finally:
            if created_client and qdrant is not None:
                await _maybe_close(qdrant)

    candidate_rows = _debug_candidate_rows(
        qdrant_candidates,
        available_pools,
        preferred_kind=effective_preferred,
    )
    accepted_candidates = [candidate for candidate in candidate_rows if bool(candidate.get("accepted"))]

    if deterministic.found:
        decision = deterministic
        message = f"Deterministic routing matched {deterministic.kind}/{deterministic.ref} via {deterministic.source}."
    elif accepted_candidates:
        winner = accepted_candidates[0]
        decision = RoutingDecision(
            kind=str(winner.get("kind", "") or ""),
            ref=str(winner.get("ref", "") or ""),
            source=str(winner.get("source", "") or "qdrant_routing"),
            score=float(winner.get("score", 0.0) or 0.0),
            reason=str(winner.get("reason", "") or ""),
        )
        message = f"Qdrant routing candidate selected {decision.kind}/{decision.ref}."
    else:
        decision = RoutingDecision()
        message = "No routing target matched."

    if qdrant_error:
        status = "warn" if decision.found else "error"
    elif decision.found:
        status = "ok"
    else:
        status = "warn"

    return {
        "status": status,
        "visual_status": status,
        "message": message,
        "query": clean_query,
        "preferred_kind": effective_preferred or "auto",
        "requested_preferred_kind": requested_preferred,
        "inferred_preferred_kind": inferred_preferred,
        "available_counts": available_counts,
        "deterministic": _decision_payload(deterministic),
        "qdrant": {
            "enabled": qdrant_enabled,
            "message": qdrant_reason if not qdrant_enabled else "",
            "error": qdrant_error,
            "candidate_count": len(candidate_rows),
            "accepted_count": len(accepted_candidates),
            "candidates": candidate_rows,
        },
        "decision": _decision_payload(decision),
        "executed": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
