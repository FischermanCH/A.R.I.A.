from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client.models import PointIdsList
from qdrant_client.models import PointStruct

from aria.core.document_ingest import PreparedDocument
from aria.skills.base import SkillResult


class DocumentMemoryService:
    def __init__(self, skill: Any) -> None:
        self.skill = skill

    @staticmethod
    def build_document_guide_text(document: PreparedDocument, *, target_collection: str) -> str:
        stem = Path(document.filename).stem.replace("_", " ").replace("-", " ").strip()
        keywords = ", ".join(document.keywords[:8]).strip()
        summary = str(document.summary or "").strip()
        parts = [
            f"Dokument: {document.filename}",
            f"Titel: {stem}" if stem else "",
            f"Collection: {target_collection}",
            f"Zusammenfassung: {summary}" if summary else "",
            f"Stichworte: {keywords}" if keywords else "",
            f"Quelle: {document.source_type.upper()}",
        ]
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def build_document_targets_from_guides(
        guide_hits: list[dict[str, Any]],
        *,
        label: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        if guide_hits:
            max_keyword_hits = max(int(hit.get("keyword_hits", 0) or 0) for hit in guide_hits)
            if max_keyword_hits > 0:
                guide_hits = [
                    hit
                    for hit in guide_hits
                    if int(hit.get("keyword_hits", 0) or 0) == max_keyword_hits
                ]

            if guide_hits:
                best_score = max(float(hit.get("guide_score", 0.0) or 0.0) for hit in guide_hits)
                threshold = max(best_score - 0.08, best_score * 0.9)
                guide_hits = [
                    hit
                    for hit in guide_hits
                    if float(hit.get("guide_score", 0.0) or 0.0) >= threshold
                ]

        targets: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for hit in guide_hits:
            document_id = str(hit.get("document_id", "")).strip()
            collection = str(hit.get("collection", "")).strip()
            if not document_id or not collection:
                continue
            key = (collection, document_id)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "type": "document",
                    "label": label,
                    "collection": collection,
                    "top_k": int(top_k),
                    "document_id": document_id,
                    "document_name": str(hit.get("document_name", "")).strip(),
                    "guide_score": float(hit.get("guide_score", 0.0) or 0.0),
                }
        )
        return targets

    async def build_document_guide_point(
        self,
        *,
        user_id: str,
        document: PreparedDocument,
        target_collection: str,
    ) -> tuple[str, PointStruct, dict[str, int]]:
        guide_text = self.skill._build_document_guide_text(document, target_collection=target_collection)
        vector, usage = await self.skill._embed(
            guide_text,
            source="rag_ingest",
            operation="document_guide",
            user_id=user_id,
        )
        guide_collection = await self.skill._get_collection_for_vector(
            len(vector),
            base_collection=self.skill._document_guide_collection_for_user(user_id),
        )
        point_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{guide_collection}|{user_id.strip()}|{target_collection}|{document.document_id}|guide",
            )
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "text": guide_text,
                "user_id": user_id,
                "timestamp": now_iso,
                "type": "knowledge",
                "source": "rag_document_guide",
                "document_id": document.document_id,
                "document_name": document.filename,
                "guide_summary": document.summary,
                "guide_keywords": list(document.keywords),
                "target_collection": target_collection,
                "mime_type": document.mime_type,
                "source_type": document.source_type,
                "embedding_model": self.skill._resolve_embedding_model(),
                "embedding_fingerprint": self.skill._active_embedding_fingerprint(),
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        )
        return guide_collection, point, usage

    async def delete_document_guide_entries(
        self,
        *,
        user_id: str,
        target_collection: str,
        document_id: str = "",
        document_name: str = "",
    ) -> int:
        guide_collection = self.skill._document_guide_collection_for_user(user_id)
        clean_user = str(user_id).strip()
        clean_target = str(target_collection).strip()
        clean_document_id = str(document_id).strip()
        clean_document_name = str(document_name).strip()
        if not clean_target or (not clean_document_id and not clean_document_name):
            return 0
        try:
            exists = await self.skill.qdrant.collection_exists(collection_name=guide_collection)
            if not exists:
                return 0
            point_ids: list[str | int] = []
            offset = None
            while True:
                points, next_offset = await self.skill.qdrant.scroll(
                    collection_name=guide_collection,
                    scroll_filter=self.skill._user_filter(clean_user),
                    limit=200,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    payload = getattr(point, "payload", {}) or {}
                    if str(payload.get("target_collection", "")).strip() != clean_target:
                        continue
                    matches = False
                    if clean_document_id and str(payload.get("document_id", "")).strip() == clean_document_id:
                        matches = True
                    elif clean_document_name and str(payload.get("document_name", "")).strip() == clean_document_name:
                        matches = True
                    if not matches:
                        continue
                    point_id = getattr(point, "id", None)
                    if point_id is None:
                        continue
                    point_ids.append(self.skill._coerce_point_id(str(point_id)))
                if next_offset is None:
                    break
                offset = next_offset
            if not point_ids:
                return 0
            await self.skill.qdrant.delete(
                collection_name=guide_collection,
                points_selector=PointIdsList(points=point_ids),
                wait=True,
            )
            return len(point_ids)
        except Exception:
            return 0

    async def query_document_guides(
        self,
        *,
        vector: list[float],
        query: str,
        user_id: str,
        max_hits: int,
    ) -> list[dict[str, Any]]:
        guide_collection = self.skill._document_guide_collection_for_user(user_id)
        try:
            exists = await self.skill.qdrant.collection_exists(collection_name=guide_collection)
            if not exists:
                return []
            query_result = await self.skill.qdrant.query_points(
                collection_name=guide_collection,
                query=vector,
                query_filter=self.skill._user_filter(user_id),
                limit=max(2, int(max_hits)),
            )
        except Exception:
            return []

        query_tokens = set(self.skill._tokenize_for_match(query))
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for hit in self.skill._extract_hits(query_result):
            payload = hit.payload or {}
            if not self.skill._payload_embedding_compatible(payload):
                continue
            document_id = str(payload.get("document_id", "")).strip()
            target_collection = str(payload.get("target_collection", "")).strip()
            document_name = str(payload.get("document_name", "")).strip()
            if not document_id or not target_collection:
                continue
            key = (target_collection, document_id)
            if key in seen:
                continue
            raw_score = float(getattr(hit, "score", 0.0) or 0.0)
            keyword_pool = {
                str(item).strip().lower()
                for item in (payload.get("guide_keywords", []) or [])
                if str(item).strip()
            }
            keyword_pool.update(self.skill._tokenize_for_match(Path(document_name).stem))
            guide_text = " ".join(
                [
                    str(payload.get("guide_summary", "")).strip(),
                    document_name,
                    str(payload.get("text", "")).strip(),
                ]
            ).lower()
            keyword_hits = sum(1 for token in query_tokens if token in keyword_pool)
            text_hits = sum(1 for token in query_tokens if token and token in guide_text)
            if raw_score < 0.18 and keyword_hits <= 0 and text_hits <= 0:
                continue
            seen.add(key)
            rows.append(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "collection": target_collection,
                    "guide_score": raw_score + (keyword_hits * 0.12) + (min(text_hits, 3) * 0.05),
                    "raw_score": raw_score,
                    "keyword_hits": keyword_hits,
                    "text_hits": text_hits,
                }
            )
        rows.sort(key=lambda row: float(row.get("guide_score", 0.0)), reverse=True)
        return rows[:max_hits]

    async def store_document(
        self,
        *,
        user_id: str,
        document: PreparedDocument,
        base_collection: str | None = None,
        source: str = "rag_upload",
    ) -> SkillResult:
        if not document.chunks:
            return SkillResult(skill_name=self.skill.name, content="", success=False, error="Leeres Dokument")

        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        base_name = (base_collection or self.skill.memory.collection).strip() or self.skill.memory.collection
        target_collection = ""
        points: list[PointStruct] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for chunk in document.chunks:
            vector, usage = await self.skill._embed(
                chunk.text,
                source="rag_ingest",
                operation="document_chunk",
                user_id=user_id,
            )
            for key in usage_total:
                usage_total[key] += int(usage.get(key, 0) or 0)
            if not target_collection:
                target_collection = await self.skill._get_collection_for_vector(len(vector), base_collection=base_name)
            point_id = str(
                uuid5(
                    NAMESPACE_URL,
                    (
                        f"{target_collection}|{user_id.strip()}|{document.document_id}|"
                        f"{chunk.index}|{chunk.text.strip().lower()}"
                    ),
                )
            )
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "text": chunk.text,
                        "user_id": user_id,
                        "timestamp": now_iso,
                        "type": "knowledge",
                        "source": source,
                        "document_id": document.document_id,
                        "document_name": document.filename,
                        "chunk_index": int(chunk.index),
                        "chunk_total": int(chunk.total),
                        "mime_type": document.mime_type,
                        "source_type": document.source_type,
                        "embedding_model": self.skill._resolve_embedding_model(),
                        "embedding_fingerprint": self.skill._active_embedding_fingerprint(),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    },
                )
            )

        guide_collection = ""
        guide_point: PointStruct | None = None
        doc_meta_catalog: dict[str, Any] = {}
        if target_collection:
            guide_collection, guide_point, guide_usage = await self.skill._build_document_guide_point(
                user_id=user_id,
                document=document,
                target_collection=target_collection,
            )
            for key in usage_total:
                usage_total[key] += int(guide_usage.get(key, 0) or 0)

        if points:
            await self.skill.qdrant.upsert(collection_name=target_collection, points=points)
            if guide_point is not None and guide_collection:
                try:
                    await self.skill.qdrant.upsert(collection_name=guide_collection, points=[guide_point])
                    try:
                        doc_meta_catalog = await self.skill.rebuild_document_meta_catalog(user_id=user_id)
                    except Exception as exc:
                        doc_meta_catalog = {"status": "error", "error": str(exc)}
                except Exception:
                    await self.skill.qdrant.delete(
                        collection_name=target_collection,
                        points_selector=PointIdsList(points=[self.skill._coerce_point_id(str(point.id)) for point in points]),
                        wait=True,
                    )
                    raise

        return SkillResult(
            skill_name=self.skill.name,
            content="Dokument erfolgreich importiert.",
            success=True,
            metadata={
                "embedding_usage": usage_total,
                "embedding_model": self.skill._resolve_embedding_model(),
                "memory_type": "document",
                "chunk_count": len(points),
                "collection": target_collection,
                "guide_collection": guide_collection,
                "doc_meta_catalog": doc_meta_catalog,
                "document_name": document.filename,
                "document_id": document.document_id,
            },
        )

    async def delete_document(
        self,
        user_id: str,
        collection: str,
        *,
        document_id: str = "",
        document_name: str = "",
    ) -> int:
        clean_user = str(user_id).strip()
        clean_collection = str(collection).strip()
        clean_document_id = str(document_id).strip()
        clean_document_name = str(document_name).strip()
        if not clean_collection or (not clean_document_id and not clean_document_name):
            return 0
        try:
            exists = await self.skill.qdrant.collection_exists(collection_name=clean_collection)
            if not exists:
                return 0
            point_ids: list[str | int] = []
            offset = None
            while True:
                points, next_offset = await self.skill.qdrant.scroll(
                    collection_name=clean_collection,
                    scroll_filter=self.skill._user_filter(clean_user),
                    limit=200,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    payload = getattr(point, "payload", {}) or {}
                    matches = False
                    if clean_document_id and str(payload.get("document_id", "")).strip() == clean_document_id:
                        matches = True
                    elif clean_document_name and str(payload.get("document_name", "")).strip() == clean_document_name:
                        matches = True
                    if not matches:
                        continue
                    point_id = getattr(point, "id", None)
                    if point_id is None:
                        continue
                    point_ids.append(self.skill._coerce_point_id(str(point_id)))
                if next_offset is None:
                    break
                offset = next_offset

            if not point_ids:
                return 0

            await self.skill.qdrant.delete(
                collection_name=clean_collection,
                points_selector=PointIdsList(points=point_ids),
                wait=True,
            )
            await self.skill._delete_document_guide_entries(
                user_id=clean_user,
                target_collection=clean_collection,
                document_id=clean_document_id,
                document_name=clean_document_name,
            )
            if clean_user:
                try:
                    await self.skill.rebuild_document_meta_catalog(user_id=clean_user)
                except Exception:
                    pass
            if clean_user:
                await self.skill.cleanup_empty_collections_for_user(clean_user)
            return len(point_ids)
        except Exception:
            return 0
