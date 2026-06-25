from __future__ import annotations

from typing import Any

from aria.core.embedding_client import EmbeddingClient
from aria.core.inventory_index import (
    InventoryIndexStore,
    build_inventory_documents,
    create_inventory_qdrant_client,
    inventory_collection_name,
    inventory_documents_fingerprint,
)
from aria.core.meta_catalog import (
    MetaCatalogStore,
    build_meta_catalog_documents,
    meta_catalog_collection_name,
    meta_catalog_documents_fingerprint,
)
from aria.core.usage_meter import UsageMeter


async def _maybe_close(client: Any) -> None:
    close = getattr(client, "close", None) or getattr(client, "aclose", None)
    if callable(close):
        result = close()
        if hasattr(result, "__await__"):
            await result


async def _collection_count(qdrant: Any, collection_name: str) -> int | None:
    try:
        exists = await qdrant.collection_exists(collection_name=collection_name)
    except Exception:
        return None
    if not exists:
        return 0
    try:
        info = await qdrant.get_collection(collection_name=collection_name)
    except Exception:
        return None
    for attr in ("points_count", "vectors_count"):
        value = getattr(info, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return None


async def _collection_index_hash(qdrant: Any, collection_name: str) -> str:
    try:
        exists = await qdrant.collection_exists(collection_name=collection_name)
    except Exception:
        exists = False
    if not exists:
        return ""
    try:
        rows, _offset = await qdrant.scroll(collection_name=collection_name, limit=1, with_payload=True, with_vectors=False)
    except Exception:
        return ""
    for row in rows or []:
        payload = dict(getattr(row, "payload", {}) or {})
        value = str(payload.get("inventory_index_hash", "") or "").strip()
        if value:
            return value
    return ""


async def _collection_payload_hash(qdrant: Any, collection_name: str, payload_key: str) -> str:
    try:
        exists = await qdrant.collection_exists(collection_name=collection_name)
    except Exception:
        exists = False
    if not exists:
        return ""
    try:
        rows, _offset = await qdrant.scroll(collection_name=collection_name, limit=1, with_payload=True, with_vectors=False)
    except Exception:
        return ""
    for row in rows or []:
        payload = dict(getattr(row, "payload", {}) or {})
        value = str(payload.get(payload_key, "") or "").strip()
        if value:
            return value
    return ""


def _memory_is_qdrant(settings: Any) -> tuple[bool, str]:
    memory = getattr(settings, "memory", None)
    if not bool(getattr(memory, "enabled", False)):
        return False, "Memory/Qdrant is disabled."
    if str(getattr(memory, "backend", "") or "").strip().lower() != "qdrant":
        return False, "Memory backend is not Qdrant."
    if not str(getattr(memory, "qdrant_url", "") or "").strip():
        return False, "Qdrant URL is not configured."
    return True, ""


def _status_payload(**values: Any) -> dict[str, Any]:
    payload = {
        "status": "unknown",
        "message": "",
        "collection_name": "",
        "backup_collection_name": "",
        "document_count": 0,
        "indexed_count": 0,
        "backup_count": 0,
        "current_config_hash": "",
        "indexed_config_hash": "",
        "stale": False,
        "detail": "",
    }
    payload.update(values)
    return payload


async def build_inventory_index_status(settings: Any, *, qdrant_client: Any | None = None) -> dict[str, Any]:
    documents = build_inventory_documents(settings)
    meta_documents = build_meta_catalog_documents(settings)
    document_count = len(documents)
    meta_document_count = len(meta_documents)
    current_hash = inventory_documents_fingerprint(documents)
    current_meta_hash = meta_catalog_documents_fingerprint(meta_documents)
    collection_name = inventory_collection_name(settings)
    backup_name = inventory_collection_name(settings, backup=True)
    meta_collection_name = meta_catalog_collection_name(settings)
    meta_backup_name = meta_catalog_collection_name(settings, backup=True)
    qdrant_enabled, reason = _memory_is_qdrant(settings)
    if not qdrant_enabled:
        return _status_payload(
            status="warn",
            message=reason,
            collection_name=collection_name,
            backup_collection_name=backup_name,
            document_count=document_count,
            current_config_hash=current_hash,
            meta_collection_name=meta_collection_name,
            meta_backup_collection_name=meta_backup_name,
            meta_document_count=meta_document_count,
            current_meta_catalog_hash=current_meta_hash,
        )
    created = qdrant_client is None
    qdrant = qdrant_client or await create_inventory_qdrant_client(settings, timeout=4)
    try:
        indexed_count = await _collection_count(qdrant, collection_name)
        backup_count = await _collection_count(qdrant, backup_name)
        indexed_hash = await _collection_index_hash(qdrant, collection_name)
        meta_indexed_count = await _collection_count(qdrant, meta_collection_name)
        meta_backup_count = await _collection_count(qdrant, meta_backup_name)
        indexed_meta_hash = await _collection_payload_hash(qdrant, meta_collection_name, "meta_catalog_hash")
        if indexed_count in (None,):
            status = "warn"
            message = "Inventory index collection exists, but point count is not available."
        elif indexed_count <= 0 and document_count > 0:
            status = "warn"
            message = "Inventory index has not been built yet."
        elif indexed_hash and indexed_hash != current_hash:
            status = "warn"
            message = "Inventory index may be outdated; rebuild recommended."
        elif document_count <= 0:
            status = "ok"
            message = "No inventory documents are currently available."
        elif indexed_count < document_count:
            status = "warn"
            message = f"Inventory index is incomplete: {indexed_count}/{document_count} items indexed."
        else:
            status = "ok"
            message = f"Inventory index ready: {indexed_count}/{document_count} items indexed."
        if status == "ok":
            if meta_indexed_count in (None,):
                status = "warn"
                message = "Meta catalog collection exists, but point count is not available."
            elif meta_indexed_count <= 0 and meta_document_count > 0:
                status = "warn"
                message = "Meta catalog has not been built yet."
            elif indexed_meta_hash and indexed_meta_hash != current_meta_hash:
                status = "warn"
                message = "Meta catalog may be outdated; rebuild recommended."
            elif meta_indexed_count < meta_document_count:
                status = "warn"
                message = f"Meta catalog is incomplete: {meta_indexed_count}/{meta_document_count} items indexed."
        return _status_payload(
            status=status,
            message=message,
            collection_name=collection_name,
            backup_collection_name=backup_name,
            document_count=document_count,
            indexed_count=indexed_count or 0,
            backup_count=backup_count or 0,
            current_config_hash=current_hash,
            indexed_config_hash=indexed_hash,
            stale=bool(indexed_hash and indexed_hash != current_hash)
            or not bool(indexed_hash) and document_count > 0
            or bool(indexed_meta_hash and indexed_meta_hash != current_meta_hash)
            or not bool(indexed_meta_hash) and meta_document_count > 0,
            meta_collection_name=meta_collection_name,
            meta_backup_collection_name=meta_backup_name,
            meta_document_count=meta_document_count,
            meta_indexed_count=meta_indexed_count or 0,
            meta_backup_count=meta_backup_count or 0,
            current_meta_catalog_hash=current_meta_hash,
            indexed_meta_catalog_hash=indexed_meta_hash,
        )
    except Exception as exc:
        return _status_payload(
            status="error",
            message="Inventory index status check failed.",
            detail=str(exc),
            collection_name=collection_name,
            backup_collection_name=backup_name,
            document_count=document_count,
            current_config_hash=current_hash,
            meta_collection_name=meta_collection_name,
            meta_backup_collection_name=meta_backup_name,
            meta_document_count=meta_document_count,
            current_meta_catalog_hash=current_meta_hash,
        )
    finally:
        if created and qdrant is not None:
            await _maybe_close(qdrant)


async def rebuild_inventory_index(settings: Any, *, qdrant_client: Any | None = None, embedding_client: Any | None = None, usage_meter: UsageMeter | None = None) -> dict[str, Any]:
    documents = build_inventory_documents(settings)
    meta_documents = build_meta_catalog_documents(settings)
    document_count = len(documents)
    meta_document_count = len(meta_documents)
    current_hash = inventory_documents_fingerprint(documents)
    current_meta_hash = meta_catalog_documents_fingerprint(meta_documents)
    collection_name = inventory_collection_name(settings)
    backup_name = inventory_collection_name(settings, backup=True)
    meta_collection_name = meta_catalog_collection_name(settings)
    meta_backup_name = meta_catalog_collection_name(settings, backup=True)
    qdrant_enabled, reason = _memory_is_qdrant(settings)
    if not qdrant_enabled:
        return _status_payload(
            status="warn",
            message=reason,
            collection_name=collection_name,
            backup_collection_name=backup_name,
            document_count=document_count,
            current_config_hash=current_hash,
            meta_collection_name=meta_collection_name,
            meta_backup_collection_name=meta_backup_name,
            meta_document_count=meta_document_count,
            current_meta_catalog_hash=current_meta_hash,
        )
    created = qdrant_client is None
    qdrant = qdrant_client or await create_inventory_qdrant_client(settings, timeout=12)
    embedder = embedding_client or EmbeddingClient(settings.embeddings, usage_meter=usage_meter)
    try:
        store = InventoryIndexStore(qdrant=qdrant, embedding_client=embedder, collection_name=collection_name)
        result = await store.rebuild_documents(
            documents,
            index_hash=current_hash,
            backup_collection_name=backup_name,
            keep_backup=bool(getattr(getattr(settings, "inventory_index", None), "keep_backup", True)),
        )
        meta_store = MetaCatalogStore(qdrant=qdrant, embedding_client=embedder, collection_name=meta_collection_name)
        meta_result = await meta_store.rebuild_documents(
            meta_documents,
            catalog_hash=current_meta_hash,
            backup_collection_name=meta_backup_name,
            keep_backup=bool(getattr(getattr(settings, "inventory_index", None), "keep_backup", True)),
        )
        indexed_count = int(result.get("documents", 0) or 0)
        meta_indexed_count = int(meta_result.get("documents", 0) or 0)
        status = "ok" if indexed_count >= document_count and meta_indexed_count >= meta_document_count else "warn"
        message = (
            f"Inventory index rebuilt: {indexed_count}/{document_count} items indexed. Meta catalog rebuilt: {meta_indexed_count}/{meta_document_count} items indexed."
            if status == "ok"
            else f"Rebuild incomplete: inventory {indexed_count}/{document_count}, meta catalog {meta_indexed_count}/{meta_document_count}."
        )
        return _status_payload(
            status=status,
            message=message,
            collection_name=collection_name,
            backup_collection_name=backup_name,
            document_count=document_count,
            indexed_count=indexed_count,
            backup_count=int(result.get("backup_documents", 0) or 0),
            current_config_hash=current_hash,
            indexed_config_hash=str(result.get("inventory_index_hash", "") or ""),
            embedding_model=str(result.get("embedding_model", "") or ""),
            embedding_usage=dict(result.get("embedding_usage", {}) or {}),
            meta_collection_name=meta_collection_name,
            meta_backup_collection_name=meta_backup_name,
            meta_document_count=meta_document_count,
            meta_indexed_count=meta_indexed_count,
            meta_backup_count=int(meta_result.get("backup_documents", 0) or 0),
            current_meta_catalog_hash=current_meta_hash,
            indexed_meta_catalog_hash=str(meta_result.get("meta_catalog_hash", "") or ""),
            meta_embedding_model=str(meta_result.get("embedding_model", "") or ""),
            meta_embedding_usage=dict(meta_result.get("embedding_usage", {}) or {}),
            stale=False,
        )
    except Exception as exc:
        return _status_payload(
            status="error",
            message="Inventory index rebuild failed.",
            detail=str(exc),
            collection_name=collection_name,
            backup_collection_name=backup_name,
            document_count=document_count,
            current_config_hash=current_hash,
            meta_collection_name=meta_collection_name,
            meta_backup_collection_name=meta_backup_name,
            meta_document_count=meta_document_count,
            current_meta_catalog_hash=current_meta_hash,
        )
    finally:
        if created and qdrant is not None:
            await _maybe_close(qdrant)
