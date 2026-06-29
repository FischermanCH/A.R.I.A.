from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointIdsList, PointStruct, VectorParams


DOC_META_CATALOG_VERSION = 1
DOC_META_PREFIX = "aria_doc_meta"
DOC_META_MANIFEST_ID = "00000000-0000-0000-0000-000000000001"


def _slug_user_id(user_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(user_id or "").strip().lower()).strip("_")
    return slug or "default"


def document_meta_collection_for_user(user_id: str) -> str:
    return f"{DOC_META_PREFIX}_{_slug_user_id(user_id)}"


def _normalize_ws(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = _normalize_ws(value)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _compact_terms(*values: Any, limit: int = 24) -> list[str]:
    terms: list[str] = []
    for value in values:
        if isinstance(value, list | tuple | set):
            terms.extend(str(item) for item in value)
            continue
        text = _normalize_ws(value)
        if not text:
            continue
        terms.append(text)
        terms.extend(re.findall(r"(?u)\b[\w][\w-]{2,}\b", text))
    return _dedupe(terms)[:limit]


def _semantic_document_aliases(*values: Any) -> list[str]:
    text = " ".join(
        " ".join(str(item) for item in value) if isinstance(value, list | tuple | set) else str(value or "")
        for value in values
    ).lower()
    aliases: list[str] = []
    if re.search(r"\b(heater|heaters|radiator|thermostat|heating)\b", text):
        aliases.extend(["heizung", "heizungen", "heizgeraet", "heizgeraete", "heater"])
    if re.search(r"\b(wifi|wi-fi|wireless|wlan)\b", text):
        aliases.extend(["wifi", "wi-fi", "wireless", "wlan"])
    return _dedupe(aliases)


def _render_document_meta_text(payload: dict[str, Any]) -> str:
    rows = [
        "Catalog type: document_meta",
        "Surface: docs",
        f"Kind: {payload.get('kind', 'document')}",
        f"Ref: {payload.get('ref', '')}",
        f"Title: {payload.get('title', '')}",
        f"Document: {payload.get('document_name', '')}",
        f"Collection: {payload.get('target_collection', '')}",
    ]
    summary = _normalize_ws(payload.get("description", ""))
    if summary:
        rows.append(f"Description: {summary}")
    topics = [str(item) for item in payload.get("knows", []) or [] if str(item).strip()]
    if topics:
        rows.append("Knows: " + ", ".join(topics))
    aliases = [str(item) for item in payload.get("aliases", []) or [] if str(item).strip()]
    if aliases:
        rows.append("Aliases: " + ", ".join(aliases))
    rows.append("Can load: source-bound document chunks, document guide, document collection target")
    rows.append("Risk: low")
    return "\n".join(row for row in rows if _normalize_ws(row)).strip()


class DocumentMetaCatalogStore:
    def __init__(self, *, qdrant: Any, embedding_client: Any, collection_name: str) -> None:
        self.qdrant = qdrant
        self.embedding_client = embedding_client
        self.collection_name = collection_name

    async def _embed(self, texts: list[str], *, operation: str, user_id: str = "") -> tuple[list[list[float]], dict[str, int], str]:
        response = await self.embedding_client.embed(texts, source="doc_meta_catalog", operation=operation, user_id=user_id)
        return [list(map(float, vector)) for vector in response.vectors], dict(response.usage), str(response.model or "")

    async def _ensure_collection(self, vector_size: int) -> None:
        try:
            exists = await self.qdrant.collection_exists(collection_name=self.collection_name)
        except Exception:
            exists = False
        if exists:
            return
        await self.qdrant.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    async def _scroll_all(self, *, scroll_filter: Filter | None = None, with_vectors: bool = False) -> list[Any]:
        rows: list[Any] = []
        offset = None
        while True:
            try:
                batch, offset = await self.qdrant.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=scroll_filter,
                    limit=200,
                    offset=offset,
                    with_payload=True,
                    with_vectors=with_vectors,
                )
            except TypeError:
                batch, offset = await self.qdrant.scroll(
                    collection_name=self.collection_name,
                    limit=200,
                    offset=offset,
                    with_payload=True,
                    with_vectors=with_vectors,
                )
                if scroll_filter is not None:
                    batch = [point for point in batch if self._matches_filter(dict(getattr(point, "payload", {}) or {}), scroll_filter)]
            rows.extend(batch or [])
            if offset is None:
                break
        return rows

    @staticmethod
    def _matches_filter(payload: dict[str, Any], query_filter: Filter | None) -> bool:
        if query_filter is None:
            return True
        for condition in getattr(query_filter, "must", []) or []:
            key = str(getattr(condition, "key", "") or "")
            match = getattr(condition, "match", None)
            if not key or match is None:
                continue
            if payload.get(key) != getattr(match, "value", None):
                return False
        return True

    async def _active_manifest(self) -> dict[str, Any]:
        try:
            exists = await self.qdrant.collection_exists(collection_name=self.collection_name)
        except Exception:
            exists = False
        if not exists:
            return {}
        for point in await self._scroll_all(scroll_filter=Filter(must=[FieldCondition(key="kind", match=MatchValue(value="catalog_manifest"))])):
            payload = dict(getattr(point, "payload", {}) or {})
            if str(payload.get("kind", "")).strip() == "catalog_manifest":
                return payload
        return {}

    @staticmethod
    def point_from_guide(*, guide_payload: dict[str, Any], build_id: str, user_id: str, vector: list[float], model: str) -> PointStruct:
        document_id = _normalize_ws(guide_payload.get("document_id"))
        document_name = _normalize_ws(guide_payload.get("document_name"))
        target_collection = _normalize_ws(guide_payload.get("target_collection"))
        title = Path(document_name).stem.replace("_", " ").replace("-", " ").strip() or document_name or document_id
        summary = _normalize_ws(guide_payload.get("guide_summary"))[:700]
        keywords = _compact_terms(
            guide_payload.get("guide_keywords", []),
            title,
            document_name,
            summary,
            guide_payload.get("text", ""),
        )
        semantic_aliases = _semantic_document_aliases(
            guide_payload.get("guide_keywords", []),
            title,
            document_name,
            summary,
            guide_payload.get("text", ""),
        )
        catalog_id = f"local|docs|document|{document_id or uuid5(NAMESPACE_URL, document_name)}"
        payload = {
            "doc_meta_catalog_version": DOC_META_CATALOG_VERSION,
            "catalog_id": catalog_id,
            "entity_type": "local_context",
            "surface_id": "docs",
            "kind": "document_meta",
            "ref": document_id or document_name,
            "title": title,
            "description": summary,
            "group_name": "Imported Documents",
            "aliases": _dedupe([document_name, title, *[str(item) for item in guide_payload.get("guide_keywords", []) or []], *semantic_aliases])[:24],
            "tags": ["documents", "docs", "uploaded_document", str(guide_payload.get("source_type", "") or "").strip(), *semantic_aliases[:6]],
            "knows": _dedupe([*keywords, *semantic_aliases])[:32],
            "can_load": ["source-bound document chunks", "document guide", "document collection target"],
            "can_do": [],
            "action_candidates": [],
            "loader_contract": "Search the referenced document collection with docs_only=True and source-bound evidence.",
            "executor_contract": "",
            "risk_hint": "low",
            "confirmation_policy": "confirmation_not_required_for_read_only_document_search",
            "data_persistence": "user_data_preserved",
            "user_id": user_id,
            "catalog_build_id": build_id,
            "document_id": document_id,
            "document_name": document_name,
            "target_collection": target_collection,
            "mime_type": str(guide_payload.get("mime_type", "") or "").strip(),
            "source_type": str(guide_payload.get("source_type", "") or "").strip(),
            "embedding_model": model,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        payload["text"] = _render_document_meta_text(payload)
        point_id = str(uuid5(NAMESPACE_URL, f"aria-doc-meta|{user_id}|{build_id}|{document_id}|{target_collection}"))
        return PointStruct(id=point_id, vector=vector, payload=payload)

    async def _activate_empty_build(self, *, user_id: str, build_id: str, previous_build_id: str) -> dict[str, Any]:
        try:
            exists = await self.qdrant.collection_exists(collection_name=self.collection_name)
        except Exception:
            exists = False
        if not exists:
            return {
                "documents": 0,
                "collection": self.collection_name,
                "active_build_id": "",
                "previous_build_id": previous_build_id,
                "status": "empty",
            }
        rows = await self._scroll_all(with_vectors=True)
        vector_size = 0
        point_ids: list[str | int] = []
        for point in rows:
            vector = getattr(point, "vector", None) or []
            if not vector_size and isinstance(vector, list):
                vector_size = len(vector)
            payload = dict(getattr(point, "payload", {}) or {})
            if str(payload.get("kind", "") or "") != "catalog_manifest":
                point_id = getattr(point, "id", "")
                if point_id:
                    point_ids.append(point_id)
        if point_ids:
            await self.qdrant.delete(collection_name=self.collection_name, points_selector=PointIdsList(points=point_ids), wait=True)
        if vector_size <= 0:
            return {
                "documents": 0,
                "collection": self.collection_name,
                "active_build_id": "",
                "previous_build_id": previous_build_id,
                "status": "empty",
            }
        manifest = PointStruct(
            id=DOC_META_MANIFEST_ID,
            vector=[0.0 for _ in range(vector_size)],
            payload={
                "kind": "catalog_manifest",
                "doc_meta_catalog_version": DOC_META_CATALOG_VERSION,
                "user_id": user_id,
                "active_build_id": build_id,
                "previous_build_id": previous_build_id,
                "built_at": datetime.now(timezone.utc).isoformat(),
                "document_count": 0,
                "collection": self.collection_name,
            },
        )
        await self.qdrant.upsert(collection_name=self.collection_name, points=[manifest])
        return {
            "documents": 0,
            "collection": self.collection_name,
            "active_build_id": build_id,
            "previous_build_id": previous_build_id,
            "status": "active",
        }

    async def rebuild_from_guides(self, *, user_id: str, guides: list[dict[str, Any]]) -> dict[str, Any]:
        clean_user = _slug_user_id(str(user_id or "").strip() or "default")
        active = await self._active_manifest()
        previous_build_id = str(active.get("active_build_id", "") or "").strip()
        build_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        guide_rows = [dict(row) for row in guides if _normalize_ws(row.get("document_id") or row.get("document_name"))]
        texts = [
            _render_document_meta_text(
                {
                    "kind": "document_meta",
                    "document_name": row.get("document_name", ""),
                    "title": Path(str(row.get("document_name", ""))).stem,
                    "target_collection": row.get("target_collection", ""),
                    "description": row.get("guide_summary", ""),
                    "knows": _dedupe([
                        *_compact_terms(row.get("guide_keywords", []), row.get("text", "")),
                        *_semantic_document_aliases(
                            row.get("guide_keywords", []),
                            row.get("document_name", ""),
                            row.get("guide_summary", ""),
                            row.get("text", ""),
                        ),
                    ])[:32],
                }
            )
            for row in guide_rows
        ]
        if not texts:
            return await self._activate_empty_build(user_id=clean_user, build_id=build_id, previous_build_id=previous_build_id)
        vectors, usage, model = await self._embed(texts, operation="rebuild_doc_meta_catalog", user_id=clean_user)
        if not vectors:
            return {"documents": 0, "collection": self.collection_name, "active_build_id": previous_build_id, "previous_build_id": str(active.get("previous_build_id", "") or ""), "status": "empty_vectors", "embedding_usage": usage}
        await self._ensure_collection(len(vectors[0]))
        points = [
            self.point_from_guide(guide_payload=row, build_id=build_id, user_id=clean_user, vector=vector, model=model)
            for row, vector in zip(guide_rows, vectors, strict=False)
        ]
        manifest = PointStruct(
            id=DOC_META_MANIFEST_ID,
            vector=[0.0 for _ in vectors[0]],
            payload={
                "kind": "catalog_manifest",
                "doc_meta_catalog_version": DOC_META_CATALOG_VERSION,
                "user_id": clean_user,
                "active_build_id": build_id,
                "previous_build_id": previous_build_id,
                "built_at": datetime.now(timezone.utc).isoformat(),
                "document_count": len(points),
                "collection": self.collection_name,
            },
        )
        await self.qdrant.upsert(collection_name=self.collection_name, points=[*points, manifest])
        await self._delete_stale_builds(keep_build_ids={build_id, previous_build_id})
        return {
            "documents": len(points),
            "collection": self.collection_name,
            "active_build_id": build_id,
            "previous_build_id": previous_build_id,
            "embedding_usage": usage,
            "embedding_model": model,
            "status": "active",
        }

    async def _delete_stale_builds(self, *, keep_build_ids: set[str]) -> int:
        keep = {item for item in keep_build_ids if str(item).strip()}
        rows = await self._scroll_all()
        point_ids: list[str | int] = []
        for point in rows:
            payload = dict(getattr(point, "payload", {}) or {})
            if str(payload.get("kind", "") or "") == "catalog_manifest":
                continue
            build_id = str(payload.get("catalog_build_id", "") or "").strip()
            if build_id and build_id not in keep:
                point_ids.append(getattr(point, "id", ""))
        point_ids = [point_id for point_id in point_ids if point_id]
        if not point_ids:
            return 0
        await self.qdrant.delete(collection_name=self.collection_name, points_selector=PointIdsList(points=point_ids), wait=True)
        return len(point_ids)

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

    async def query_catalog(self, query: str, *, user_id: str, limit: int = 8, score_threshold: float = 0.0) -> list[dict[str, Any]]:
        clean_query = _normalize_ws(query)
        if not clean_query:
            return []
        clean_user = _slug_user_id(str(user_id or "").strip() or "default")
        active = await self._active_manifest()
        active_build_id = str(active.get("active_build_id", "") or "").strip()
        if not active_build_id:
            return []
        vectors, _usage, _model = await self._embed([clean_query], operation="query_doc_meta_catalog", user_id=user_id)
        vector = vectors[0] if vectors else []
        if not vector:
            return []
        user_values = []
        for raw_user in (clean_user, str(user_id or "").strip() or "default"):
            if raw_user and raw_user not in user_values:
                user_values.append(raw_user)
        rows: list[dict[str, Any]] = []
        seen_catalog_ids: set[str] = set()
        for user_value in user_values:
            query_filter = Filter(
                must=[
                    FieldCondition(key="kind", match=MatchValue(value="document_meta")),
                    FieldCondition(key="user_id", match=MatchValue(value=user_value)),
                    FieldCondition(key="catalog_build_id", match=MatchValue(value=active_build_id)),
                ]
            )
            try:
                result = await self.qdrant.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=query_filter,
                    limit=max(1, int(limit)),
                )
            except TypeError:
                result = await self.qdrant.query_points(collection_name=self.collection_name, query=vector, limit=max(1, int(limit)))
            for hit in self._extract_hits(result):
                payload = dict(getattr(hit, "payload", {}) or {})
                if not self._matches_filter(payload, query_filter):
                    continue
                score = float(getattr(hit, "score", 0.0) or 0.0)
                if score < score_threshold:
                    continue
                catalog_id = str(payload.get("catalog_id", "") or "").strip()
                if not catalog_id or catalog_id in seen_catalog_ids:
                    continue
                seen_catalog_ids.add(catalog_id)
                rows.append(
                    {
                        "catalog_id": catalog_id,
                        "surface_id": "docs",
                        "kind": "document_meta",
                        "ref": str(payload.get("ref", "") or "").strip(),
                        "score": score,
                        "source": "qdrant_doc_meta_catalog",
                        "payload": payload,
                    }
                )
        rows.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        return rows
