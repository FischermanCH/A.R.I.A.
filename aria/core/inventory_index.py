from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from qdrant_client.models import Distance, PointStruct, VectorParams

from aria.core.connection_catalog import connection_kind_label, connection_routing_spec, normalize_connection_kind, ordered_connection_kinds
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.routing_index import _dedupe, _document_source_hash, _read_list, _read_text, _slug


INVENTORY_INDEX_VERSION = 1


def inventory_index_instance_key(settings: Any) -> str:
    public_url = str(getattr(getattr(settings, "aria", None), "public_url", "") or "").strip()
    if public_url:
        return public_url
    title = str(getattr(getattr(settings, "ui", None), "title", "") or "").strip()
    port = str(getattr(getattr(settings, "aria", None), "port", "") or "").strip()
    return " ".join(part for part in (title, port) if part)


def inventory_collection_name(settings: Any, *, backup: bool = False) -> str:
    instance = _slug(inventory_index_instance_key(settings), fallback="")
    base = f"aria_inventory_{instance}" if instance else "aria_inventory"
    return f"{base}__backup" if backup else base


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


@dataclass(slots=True)
class InventoryDocument:
    surface_id: str
    kind: str
    ref: str
    title: str = ""
    description: str = ""
    group_name: str = ""
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    text: str = ""
    source_hash: str = ""
    updated_at: str = ""

    @property
    def id(self) -> str:
        return str(uuid5(NAMESPACE_URL, f"aria-inventory|{self.surface_id}|{self.kind}|{self.ref}"))

    def render_text(self) -> str:
        rows = [
            f"Surface: {self.surface_id}",
            f"Kind: {connection_kind_label(self.kind) if self.surface_id == 'connections' else self.kind}",
            f"Ref: {self.ref}",
        ]
        if self.title:
            rows.append(f"Title: {self.title}")
        if self.description:
            rows.append(f"Description: {self.description}")
        if self.group_name:
            rows.append(f"Group: {self.group_name}")
        if self.aliases:
            rows.append("Aliases: " + ", ".join(self.aliases))
        if self.tags:
            rows.append("Tags: " + ", ".join(self.tags))
        if self.capabilities:
            rows.append("Capabilities: " + ", ".join(self.capabilities))
        return "\n".join(rows)

    def payload(self) -> dict[str, Any]:
        return {
            "inventory_index_version": INVENTORY_INDEX_VERSION,
            "surface_id": self.surface_id,
            "kind": self.kind,
            "ref": self.ref,
            "title": self.title,
            "description": self.description,
            "group_name": self.group_name,
            "aliases": list(self.aliases),
            "tags": list(self.tags),
            "capabilities": list(self.capabilities),
            "text": self.text or self.render_text(),
            "source_hash": self.source_hash,
            "updated_at": self.updated_at,
        }


def _connection_capabilities(kind: str) -> list[str]:
    try:
        return list(connection_routing_spec(kind).supported_actions)
    except Exception:
        return []


def _safe_inventory_label(value: str) -> str:
    clean = _normalize_ws(value)
    lower = clean.lower()
    if not clean or "://" in lower or "@" in clean:
        return ""
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", clean):
        return ""
    if re.search(r"\b[a-z0-9-]+\.[a-z]{2,}\b", lower):
        return ""
    return clean


def _inventory_aliases(ref: str, row: Any) -> list[str]:
    aliases = [str(ref or "").strip()]
    aliases.extend(_read_list(row, "aliases"))
    return _dedupe(label for alias in aliases if (label := _safe_inventory_label(alias)))


def _surface_summary_documents(settings: Any) -> list[InventoryDocument]:
    now = datetime.now(timezone.utc).isoformat()
    documents: list[InventoryDocument] = []
    for surface in build_builtin_surface_registry(settings).all():
        payload = surface.as_meta_context()
        capabilities = _dedupe(
            [
                *list(payload.get("supported_modes", []) or []),
                str(payload.get("cost_hint", "") or ""),
                str(payload.get("latency_hint", "") or ""),
                str(payload.get("risk_hint", "") or ""),
            ]
        )
        source_payload = {
            "surface_id": surface.surface_id,
            "kind": "surface",
            "ref": surface.surface_id,
            "title": surface.display_name,
            "description": surface.what_it_knows,
            "group_name": surface.surface_type,
            "capabilities": capabilities,
            "routing_metadata": dict(surface.routing_metadata or {}),
        }
        document = InventoryDocument(
            surface_id=surface.surface_id,
            kind="surface",
            ref=surface.surface_id,
            title=surface.display_name,
            description=f"{surface.what_it_knows} {surface.what_it_can_load}".strip(),
            group_name=surface.surface_type,
            aliases=[surface.surface_id],
            tags=list(surface.supported_modes),
            capabilities=capabilities,
            source_hash=_document_source_hash(source_payload),
            updated_at=now,
        )
        document.text = document.render_text()
        documents.append(document)
    return documents


def build_inventory_documents(settings: Any) -> list[InventoryDocument]:
    connections = getattr(settings, "connections", None)
    documents = _surface_summary_documents(settings)
    if connections is None:
        return documents
    now = datetime.now(timezone.utc).isoformat()
    for raw_kind in ordered_connection_kinds():
        kind = normalize_connection_kind(raw_kind)
        rows = getattr(connections, kind, {})
        if not isinstance(rows, dict):
            continue
        for ref, row in sorted(rows.items(), key=lambda item: str(item[0]).strip().lower()):
            clean_ref = str(ref or "").strip()
            if not clean_ref:
                continue
            title = _read_text(row, "title")
            description = _read_text(row, "description")
            group_name = _read_text(row, "group_name")
            aliases = _inventory_aliases(clean_ref, row)
            tags = _dedupe(_read_list(row, "tags"))
            capabilities = _connection_capabilities(kind)
            source_payload = {
                "surface_id": "connections",
                "kind": kind,
                "ref": clean_ref,
                "title": title,
                "description": description,
                "group_name": group_name,
                "aliases": aliases,
                "tags": tags,
                "capabilities": capabilities,
            }
            document = InventoryDocument(
                surface_id="connections",
                kind=kind,
                ref=clean_ref,
                title=title,
                description=description,
                group_name=group_name,
                aliases=aliases,
                tags=tags,
                capabilities=capabilities,
                source_hash=_document_source_hash(source_payload),
                updated_at=now,
            )
            document.text = document.render_text()
            documents.append(document)
    return documents


def inventory_documents_fingerprint(documents: Iterable[InventoryDocument]) -> str:
    rows = [
        {
            "surface_id": document.surface_id,
            "kind": document.kind,
            "ref": document.ref,
            "source_hash": document.source_hash,
        }
        for document in documents
        if document.surface_id and document.kind and document.ref
    ]
    rows.sort(key=lambda item: (item["surface_id"], item["kind"], item["ref"], item["source_hash"]))
    raw = json.dumps({"inventory_index_version": INVENTORY_INDEX_VERSION, "documents": rows}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InventoryIndexStore:
    def __init__(self, *, qdrant: Any, embedding_client: Any, collection_name: str) -> None:
        self.qdrant = qdrant
        self.embedding_client = embedding_client
        self.collection_name = collection_name

    async def _embed(self, texts: list[str], *, operation: str) -> tuple[list[list[float]], dict[str, int], str]:
        response = await self.embedding_client.embed(texts, source="inventory_index", operation=operation)
        return [list(map(float, vector)) for vector in response.vectors], dict(response.usage), str(response.model or "")

    async def _delete_collection_if_exists(self, collection_name: str) -> bool:
        try:
            exists = await self.qdrant.collection_exists(collection_name=collection_name)
        except Exception:
            exists = False
        if not exists:
            return False
        await self.qdrant.delete_collection(collection_name=collection_name)
        return True

    async def _create_collection(self, collection_name: str, vector_size: int) -> None:
        await self.qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    @staticmethod
    def _extract_hits(query_result: Any) -> list[Any]:
        if query_result is None:
            return []
        if isinstance(query_result, list):
            return query_result
        points = getattr(query_result, "points", None)
        if isinstance(points, list):
            return points
        result = getattr(query_result, "result", None)
        if isinstance(result, list):
            return result
        return []

    async def _copy_collection(self, source: str, target: str) -> int:
        try:
            exists = await self.qdrant.collection_exists(collection_name=source)
        except Exception:
            exists = False
        if not exists:
            return 0
        rows: list[Any] = []
        offset = None
        while True:
            batch, offset = await self.qdrant.scroll(
                collection_name=source,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            rows.extend(batch or [])
            if offset is None:
                break
        if not rows:
            return 0
        first_vector = getattr(rows[0], "vector", None) or []
        await self._delete_collection_if_exists(target)
        await self._create_collection(target, len(first_vector))
        points = [
            PointStruct(id=getattr(row, "id", ""), vector=list(getattr(row, "vector", []) or []), payload=dict(getattr(row, "payload", {}) or {}))
            for row in rows
        ]
        await self.qdrant.upsert(collection_name=target, points=points)
        return len(points)

    async def rebuild_documents(self, documents: list[InventoryDocument], *, index_hash: str = "", backup_collection_name: str = "", keep_backup: bool = True) -> dict[str, Any]:
        rows = [document for document in documents if str(document.text or "").strip()]
        clean_hash = str(index_hash or inventory_documents_fingerprint(rows)).strip()
        if not rows:
            return {"documents": 0, "collection": self.collection_name, "inventory_index_hash": clean_hash, "embedding_usage": {}, "embedding_model": "", "backup_documents": 0}
        vectors, usage, model = await self._embed([document.text for document in rows], operation="rebuild_inventory")
        if not vectors:
            return {"documents": 0, "collection": self.collection_name, "inventory_index_hash": clean_hash, "embedding_usage": usage, "embedding_model": model, "backup_documents": 0}
        backup_documents = 0
        if keep_backup and backup_collection_name:
            backup_documents = await self._copy_collection(self.collection_name, backup_collection_name)
        await self._delete_collection_if_exists(self.collection_name)
        await self._create_collection(self.collection_name, len(vectors[0]))
        points: list[PointStruct] = []
        for document, vector in zip(rows, vectors, strict=False):
            payload = document.payload()
            payload["embedding_model"] = model
            payload["inventory_index_hash"] = clean_hash
            payload["inventory_index_document_count"] = len(rows)
            points.append(PointStruct(id=document.id, vector=vector, payload=payload))
        await self.qdrant.upsert(collection_name=self.collection_name, points=points)
        return {
            "documents": len(points),
            "collection": self.collection_name,
            "inventory_index_hash": clean_hash,
            "embedding_usage": usage,
            "embedding_model": model,
            "backup_collection": backup_collection_name if keep_backup else "",
            "backup_documents": backup_documents,
        }

    async def query_inventory(self, query: str, *, surface_id: str = "", limit: int = 12, score_threshold: float = 0.0) -> list[dict[str, Any]]:
        clean_query = _normalize_ws(query)
        if not clean_query:
            return []
        try:
            exists = await self.qdrant.collection_exists(collection_name=self.collection_name)
        except Exception:
            return []
        if not exists:
            return []
        vectors, _usage, _model = await self._embed([clean_query], operation="query_inventory")
        vector = vectors[0] if vectors else []
        if not vector:
            return []
        result = await self.qdrant.query_points(collection_name=self.collection_name, query=vector, limit=max(1, int(limit)))
        rows: list[dict[str, Any]] = []
        clean_surface = str(surface_id or "").strip().lower()
        for hit in self._extract_hits(result):
            payload = dict(getattr(hit, "payload", {}) or {})
            if clean_surface and str(payload.get("surface_id", "") or "").strip().lower() != clean_surface:
                continue
            score = float(getattr(hit, "score", 0.0) or 0.0)
            if score < score_threshold:
                continue
            rows.append(
                {
                    "surface_id": str(payload.get("surface_id", "") or "").strip(),
                    "kind": str(payload.get("kind", "") or "").strip(),
                    "ref": str(payload.get("ref", "") or "").strip(),
                    "score": score,
                    "source": "qdrant_inventory",
                    "payload": payload,
                }
            )
        rows.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        return rows


async def create_inventory_qdrant_client(settings: Any, *, timeout: int = 10) -> Any:
    memory = settings.memory
    return create_async_qdrant_client(
        url=memory.qdrant_url,
        api_key=getattr(memory, "qdrant_api_key", "") or None,
        timeout=timeout,
    )
