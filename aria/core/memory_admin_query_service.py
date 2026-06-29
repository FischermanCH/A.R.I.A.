from __future__ import annotations

import asyncio
from datetime import timezone
from typing import Any


class MemoryAdminQueryService:
    def __init__(self, skill: Any) -> None:
        self.skill = skill

    def _timestamp_sort_key(self, item: dict[str, Any]) -> float:
        parsed = self.skill._parse_timestamp(item.get("timestamp"))
        if not parsed:
            return 0.0
        return parsed.astimezone(timezone.utc).timestamp()

    async def list_memories(
        self,
        user_id: str,
        *,
        type_filter: str = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        targets = await self.skill._build_recall_targets(user_id=user_id)
        filter_key = type_filter.strip().lower()
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for target in targets:
            target_type = str(target.get("type", "")).strip().lower()
            if filter_key and filter_key != "all" and target_type != filter_key:
                continue
            rows = await self.skill._list_rows_from_collection(
                collection=str(target["collection"]),
                user_id=user_id,
                memory_type=target_type,
                label=str(target["label"]),
                limit=max(20, limit // max(1, len(targets))),
            )
            for row in rows:
                key = (str(row.get("collection", "")), str(row.get("id", "")))
                if key[0] and key[1] and key not in unique:
                    unique[key] = row
        return sorted(unique.values(), key=self._timestamp_sort_key, reverse=True)[:limit]

    async def get_user_collection_stats(self, user_id: str) -> list[dict[str, Any]]:
        names = await self.skill._list_collection_names()
        stats: list[dict[str, Any]] = []
        for collection in names:
            if self.skill._is_document_guide_collection_name(collection) or self.skill._is_document_meta_collection_name(collection):
                continue
            try:
                exists = await self.skill.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                count = 0
                inferred_type = "fact"
                offset = None
                while True:
                    points, next_offset = await self.skill.qdrant.scroll(
                        collection_name=collection,
                        scroll_filter=self.skill._user_filter(user_id),
                        limit=256,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    if points:
                        if count == 0:
                            first_payload = points[0].payload or {}
                            inferred_type = self.skill._display_memory_type(collection, first_payload)
                        count += len(points)
                    if next_offset is None:
                        break
                    offset = next_offset
                if count <= 0:
                    continue
                stats.append(
                    {
                        "name": collection,
                        "points": count,
                        "kind": inferred_type,
                    }
                )
            except Exception:
                continue
        stats.sort(key=lambda item: int(item.get("points", 0) or 0), reverse=True)
        return stats

    async def list_memories_global(
        self,
        user_id: str,
        *,
        type_filter: str = "all",
        limit: int = 200,
        collection_filter: str = "",
    ) -> list[dict[str, Any]]:
        filter_key = type_filter.strip().lower()
        collection_key = str(collection_filter or "").strip()
        rows: list[dict[str, Any]] = []
        names = await self.skill._list_collection_names()
        for collection in names:
            if self.skill._is_document_guide_collection_name(collection) or self.skill._is_document_meta_collection_name(collection):
                continue
            if collection_key and collection != collection_key:
                continue
            try:
                exists = await self.skill.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.skill.qdrant.scroll(
                        collection_name=collection,
                        scroll_filter=self.skill._user_filter(user_id),
                        limit=min(200, max(20, limit)),
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points:
                        payload = point.payload or {}
                        text = self.skill._clean_fact_text(str(payload.get("text", "")).strip())
                        if not text:
                            continue
                        memory_type = self.skill._display_memory_type(collection, payload)
                        if filter_key and filter_key != "all" and memory_type != filter_key:
                            continue
                        label = self.skill._type_label(memory_type)
                        timestamp = (
                            str(payload.get("updated_at", "")).strip()
                            or str(payload.get("created_at", "")).strip()
                            or str(payload.get("timestamp", "")).strip()
                        )
                        rows.append(
                            {
                                "id": str(getattr(point, "id", "")),
                                "collection": collection,
                                "type": memory_type,
                                "label": label,
                                "text": text,
                                "timestamp": timestamp,
                                "source": str(payload.get("source", "")).strip() or "n/a",
                                "embedding_model": str(payload.get("embedding_model", "")).strip(),
                                "embedding_fingerprint": str(payload.get("embedding_fingerprint", "")).strip(),
                                "rollup_level": str(payload.get("rollup_level", "")).strip(),
                                "rollup_bucket": str(payload.get("rollup_bucket", "")).strip(),
                                "rollup_period_start": str(payload.get("rollup_period_start", "")).strip(),
                                "rollup_period_end": str(payload.get("rollup_period_end", "")).strip(),
                                "rollup_source_kind": str(payload.get("rollup_source_kind", "")).strip(),
                                "rollup_source_count": int(payload.get("rollup_source_count", 0) or 0),
                                "document_id": str(payload.get("document_id", "")).strip(),
                                "document_name": str(payload.get("document_name", "")).strip(),
                                "chunk_index": int(payload.get("chunk_index", 0) or 0),
                                "chunk_total": int(payload.get("chunk_total", 0) or 0),
                                "candidate_status": str(payload.get("candidate_status", "")).strip(),
                                "promotion_state": str(payload.get("promotion_state", "")).strip(),
                                "promotion_gate_result": str(payload.get("promotion_gate_result", "")).strip(),
                                "apply_state": str(payload.get("apply_state", "")).strip(),
                                "apply_gate_result": str(payload.get("apply_gate_result", "")).strip(),
                                "regression_required": bool(payload.get("regression_required") is True),
                                "regression_status": str(payload.get("regression_status", "")).strip(),
                                "regression_ref": str(payload.get("regression_ref", "")).strip(),
                                "regression_verified": bool(payload.get("regression_verified") is True),
                                "regression_verify_result": str(payload.get("regression_verify_result", "")).strip(),
                                "regression_verify_reason": str(payload.get("regression_verify_reason", "")).strip(),
                            }
                        )
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue
        rows.sort(key=self._timestamp_sort_key, reverse=True)
        return rows[:limit]

    async def list_memory_graph_points(
        self,
        user_id: str,
        *,
        limit: int = 96,
        collection_limit: int = 16,
    ) -> list[dict[str, Any]]:
        clean_user = str(user_id or "").strip() or "web"
        max_points = max(12, min(int(limit or 96), 160))
        max_collections = max(1, min(int(collection_limit or 16), 32))
        rows: list[dict[str, Any]] = []
        targets = await self.skill._build_recall_targets(user_id=clean_user)
        document_targets = await self.skill._build_document_targets(user_id=clean_user)
        seen_collections: set[str] = set()
        collection_names: list[str] = []
        for target in [*targets, *document_targets]:
            collection = str(target.get("collection", "")).strip()
            if collection and collection not in seen_collections:
                seen_collections.add(collection)
                collection_names.append(collection)
        try:
            resp = await self.skill.qdrant.get_collections()
            for item in getattr(resp, "collections", []):
                collection = str(getattr(item, "name", "")).strip()
                if not collection or collection in seen_collections:
                    continue
                if not collection.lower().startswith("aria_"):
                    continue
                if self.skill._is_document_guide_collection_name(collection) or self.skill._is_document_meta_collection_name(collection):
                    continue
                seen_collections.add(collection)
                collection_names.append(collection)
                if len(collection_names) >= max_collections:
                    break
        except Exception:
            pass
        for collection in collection_names:
            if len(rows) >= max_points:
                break
            if self.skill._is_document_guide_collection_name(collection) or self.skill._is_document_meta_collection_name(collection):
                continue
            try:
                exists = await self.skill.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                points, _next_offset = await self.skill.qdrant.scroll(
                    collection_name=collection,
                    scroll_filter=self.skill._user_filter(clean_user),
                    limit=max(6, min(32, max_points - len(rows))),
                    with_payload=True,
                    with_vectors=True,
                )
                if not points:
                    points, _next_offset = await self.skill.qdrant.scroll(
                        collection_name=collection,
                        limit=max(6, min(32, max_points - len(rows))),
                        with_payload=True,
                        with_vectors=True,
                    )
            except Exception:
                continue
            for point in points:
                payload = point.payload or {}
                text = self.skill._clean_fact_text(str(payload.get("text", "")).strip())
                if not text:
                    continue
                vector = getattr(point, "vector", None)
                if isinstance(vector, dict):
                    vector = next((value for value in vector.values() if isinstance(value, list)), None)
                if not isinstance(vector, list) or not vector:
                    continue
                memory_type = self.skill._display_memory_type(collection, payload)
                timestamp = (
                    str(payload.get("updated_at", "")).strip()
                    or str(payload.get("created_at", "")).strip()
                    or str(payload.get("timestamp", "")).strip()
                )
                rows.append(
                    {
                        "id": str(getattr(point, "id", "")),
                        "collection": collection,
                        "type": memory_type,
                        "label": self.skill._type_label(memory_type),
                        "text": text,
                        "timestamp": timestamp,
                        "source": str(payload.get("source", "")).strip() or "n/a",
                        "document_name": str(payload.get("document_name", "")).strip(),
                        "note_title": str(payload.get("note_title", "")).strip(),
                        "note_folder": str(payload.get("note_folder", "")).strip(),
                        "rollup_level": str(payload.get("rollup_level", "")).strip(),
                        "vector": [float(value) for value in vector if isinstance(value, (int, float))],
                    }
                )
                if len(rows) >= max_points:
                    break
            max_collections -= 1
            if max_collections <= 0:
                break
        rows.sort(key=self._timestamp_sort_key, reverse=True)
        return rows[:max_points]

    async def search_memories(
        self,
        user_id: str,
        query: str,
        *,
        type_filter: str = "all",
        top_k: int = 25,
    ) -> list[dict[str, Any]]:
        vector, _usage = await self.skill._embed(
            query,
            source="memory_search",
            operation="search_query",
            user_id=user_id,
        )
        targets = await self.skill._build_recall_targets(user_id=user_id)
        document_targets = await self.skill._build_document_targets(user_id=user_id)
        filter_key = type_filter.strip().lower()
        if filter_key == "document":
            targets = document_targets
        elif filter_key in {"", "all"}:
            targets = targets + document_targets
        tasks = []
        for target in targets:
            target_type = str(target.get("type", "")).strip().lower()
            if filter_key and filter_key != "all" and target_type != filter_key:
                continue
            tasks.append(
                self.skill._query_forget_hits(
                    vector=vector,
                    user_id=user_id,
                    target=target,
                    threshold=0.0,
                )
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in results:
            if isinstance(item, Exception):
                continue
            for row in item:
                key = (str(row.get("collection", "")), str(row.get("id", "")))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": str(row.get("id", "")),
                        "collection": str(row.get("collection", "")),
                        "type": str(row.get("type", "")),
                        "label": str(row.get("label", "")),
                        "text": str(row.get("text", "")),
                        "score": float(row.get("score", 0.0) or 0.0),
                        "timestamp": str(row.get("timestamp", "")),
                        "source": str(row.get("source", "n/a")),
                        "embedding_model": str(row.get("embedding_model", "")),
                        "embedding_fingerprint": str(row.get("embedding_fingerprint", "")),
                        "rollup_level": str(row.get("rollup_level", "")),
                        "rollup_bucket": str(row.get("rollup_bucket", "")),
                        "rollup_period_start": str(row.get("rollup_period_start", "")),
                        "rollup_period_end": str(row.get("rollup_period_end", "")),
                        "rollup_source_kind": str(row.get("rollup_source_kind", "")),
                        "rollup_source_count": int(row.get("rollup_source_count", 0) or 0),
                        "document_id": str(row.get("document_id", "")),
                        "document_name": str(row.get("document_name", "")),
                        "chunk_index": int(row.get("chunk_index", 0) or 0),
                        "chunk_total": int(row.get("chunk_total", 0) or 0),
                    }
                )
        rows.sort(key=lambda value: float(value.get("score", 0.0)), reverse=True)
        return rows[:top_k]
