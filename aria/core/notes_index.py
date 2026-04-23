from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from aria.core.config import EmbeddingsConfig, MemoryConfig
from aria.core.document_ingest import _chunk_text, _normalize_document_text
from aria.core.embedding_client import EmbeddingClient
from aria.core.notes_store import NoteRecord
from aria.core.qdrant_client import create_async_qdrant_client


@dataclass(frozen=True)
class NotesIndexOverview:
    enabled: bool
    reachable: bool
    collection: str
    points: int


@dataclass(frozen=True)
class NoteSearchHit:
    note_id: str
    title: str
    folder: str
    relative_path: str
    updated_at: str
    score: float
    snippet: str
    chunk_index: int
    chunk_total: int


class NotesIndex:
    PREFIX = "aria_notes"

    def __init__(
        self,
        memory: MemoryConfig,
        embeddings: EmbeddingsConfig,
        embedding_client: EmbeddingClient | None = None,
    ):
        self.memory = memory
        self.embeddings = embeddings
        self.embedding_client = embedding_client or EmbeddingClient(embeddings)
        self.timeout_seconds = embeddings.timeout_seconds
        self.qdrant = create_async_qdrant_client(
            url=memory.qdrant_url,
            api_key=(memory.qdrant_api_key or None),
            timeout=self.timeout_seconds,
        )
        self._collection_cache: dict[tuple[str, int], str] = {}

    async def aclose(self) -> None:
        close = getattr(self.qdrant, "close", None)
        if callable(close):
            await close()

    @staticmethod
    def _slug_user_id(user_id: str) -> str:
        import re

        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "web"

    def collection_for_user(self, user_id: str) -> str:
        return f"{self.PREFIX}_{self._slug_user_id(user_id)}"

    def enabled(self) -> bool:
        return bool(self.memory.enabled and str(self.memory.backend or "").strip().lower() == "qdrant")

    def _embedding_fingerprint(self) -> str:
        return str(self.embedding_client.fingerprint()).strip()

    def _embedding_model(self) -> str:
        model = str(self.embeddings.model or "").strip()
        if not model:
            return model
        if "/" not in model and not model.lower().startswith("ollama"):
            return f"openai/{model}"
        return model

    async def _ensure_collection_exists(self, collection_name: str, vector_size: int) -> str:
        cache_key = (collection_name, int(vector_size))
        cached = self._collection_cache.get(cache_key)
        if cached:
            return cached
        exists = await self.qdrant.collection_exists(collection_name=collection_name)
        if not exists:
            await self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=int(vector_size), distance=Distance.COSINE),
            )
        self._collection_cache[cache_key] = collection_name
        return collection_name

    async def _embed_chunks(self, chunks: list[str], *, user_id: str) -> tuple[list[list[float]], dict[str, int]]:
        if not chunks:
            return [], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        response = await self.embedding_client.embed(
            chunks,
            source="notes",
            operation="reindex_note",
            user_id=user_id,
        )
        vectors = [[float(value) for value in vector] for vector in response.vectors]
        return vectors, dict(response.usage)

    async def _point_ids_for_note(self, collection_name: str, *, user_id: str, note_id: str) -> list[str | int]:
        points: list[str | int] = []
        offset: Any = None
        note_filter = Filter(
            must=[
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id or "").strip())),
                FieldCondition(key="note_id", match=MatchValue(value=str(note_id or "").strip())),
            ]
        )
        while True:
            rows, next_offset = await self.qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=note_filter,
                limit=128,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            for row in rows:
                point_id = getattr(row, "id", None)
                if point_id not in (None, ""):
                    points.append(point_id)
            if next_offset is None:
                break
            offset = next_offset
        return points

    async def delete_note(self, *, user_id: str, note_id: str) -> None:
        if not self.enabled():
            return
        collection_name = self.collection_for_user(user_id)
        try:
            exists = await self.qdrant.collection_exists(collection_name=collection_name)
        except Exception:
            return
        if not exists:
            return
        point_ids = await self._point_ids_for_note(collection_name, user_id=user_id, note_id=note_id)
        if not point_ids:
            return
        from qdrant_client.models import PointIdsList

        await self.qdrant.delete(collection_name=collection_name, points_selector=PointIdsList(points=point_ids), wait=True)

    async def reindex_note(self, note: NoteRecord) -> dict[str, Any]:
        if not self.enabled():
            return {"indexed": False, "reason": "disabled", "chunk_count": 0, "collection": self.collection_for_user(note.user_id)}
        tag_line = f"Tags: {', '.join(note.tags)}\n\n" if note.tags else ""
        text = _normalize_document_text(f"# {note.title}\n\n{tag_line}{note.body}")
        chunks = _chunk_text(text)
        if not chunks:
            await self.delete_note(user_id=note.user_id, note_id=note.note_id)
            return {"indexed": True, "chunk_count": 0, "collection": self.collection_for_user(note.user_id)}
        vectors, usage = await self._embed_chunks(chunks, user_id=note.user_id)
        if not vectors:
            raise RuntimeError("Notiz konnte nicht eingebettet werden.")
        collection_name = await self._ensure_collection_exists(self.collection_for_user(note.user_id), len(vectors[0]))
        await self.delete_note(user_id=note.user_id, note_id=note.note_id)
        points: list[PointStruct] = []
        total = len(chunks)
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False), start=1):
            point_id = str(uuid5(NAMESPACE_URL, f"{collection_name}|{note.note_id}|{index}"))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "text": chunk,
                        "user_id": note.user_id,
                        "note_id": note.note_id,
                        "note_title": note.title,
                        "note_folder": note.folder,
                        "note_path": note.relative_path,
                        "note_tags": list(note.tags or []),
                        "chunk_index": index,
                        "chunk_total": total,
                        "source": "notes",
                        "embedding_model": self._embedding_model(),
                        "embedding_fingerprint": self._embedding_fingerprint(),
                        "created_at": note.created_at,
                        "updated_at": note.updated_at,
                    },
                )
            )
        await self.qdrant.upsert(collection_name=collection_name, points=points, wait=True)
        return {
            "indexed": True,
            "collection": collection_name,
            "chunk_count": len(points),
            "embedding_usage": usage,
        }

    async def overview(self, user_id: str) -> NotesIndexOverview:
        collection_name = self.collection_for_user(user_id)
        if not self.enabled():
            return NotesIndexOverview(enabled=False, reachable=False, collection=collection_name, points=0)
        try:
            exists = await self.qdrant.collection_exists(collection_name=collection_name)
            if not exists:
                return NotesIndexOverview(enabled=True, reachable=True, collection=collection_name, points=0)
            info = await self.qdrant.get_collection(collection_name=collection_name)
            points = int(getattr(info, "points_count", 0) or 0)
            return NotesIndexOverview(enabled=True, reachable=True, collection=collection_name, points=points)
        except Exception:
            return NotesIndexOverview(enabled=True, reachable=False, collection=collection_name, points=0)

    async def search_notes(self, *, user_id: str, query: str, limit: int = 8) -> list[NoteSearchHit]:
        if not self.enabled():
            return []
        clean_query = _normalize_document_text(str(query or ""))
        if not clean_query:
            return []
        collection_name = self.collection_for_user(user_id)
        try:
            exists = await self.qdrant.collection_exists(collection_name=collection_name)
            if not exists:
                return []
            vectors, _usage = await self._embed_chunks([clean_query], user_id=user_id)
            if not vectors:
                return []
            query_result = await self.qdrant.query_points(
                collection_name=collection_name,
                query=vectors[0],
                query_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=str(user_id or "").strip()))]
                ),
                limit=max(6, int(limit) * 4),
            )
        except Exception:
            return []

        grouped: dict[str, NoteSearchHit] = {}
        for hit in self._extract_hits(query_result):
            payload = hit.payload or {}
            note_id = str(payload.get("note_id", "")).strip()
            if not note_id:
                continue
            score = float(getattr(hit, "score", 0.0) or 0.0)
            snippet = str(payload.get("text", "")).strip()
            candidate = NoteSearchHit(
                note_id=note_id,
                title=str(payload.get("note_title", "")).strip() or "Notiz",
                folder=str(payload.get("note_folder", "")).strip(),
                relative_path=str(payload.get("note_path", "")).strip(),
                updated_at=str(payload.get("updated_at", "")).strip(),
                score=score,
                snippet=snippet[:260].strip(),
                chunk_index=int(payload.get("chunk_index", 0) or 0),
                chunk_total=int(payload.get("chunk_total", 0) or 0),
            )
            current = grouped.get(note_id)
            if current is None or candidate.score > current.score:
                grouped[note_id] = candidate
        rows = sorted(grouped.values(), key=lambda item: item.score, reverse=True)
        return rows[: max(1, int(limit))]

    @staticmethod
    def _extract_hits(query_result: Any) -> list[Any]:
        if query_result is None:
            return []
        if isinstance(query_result, list):
            return list(query_result)
        points = getattr(query_result, "points", None)
        if points is not None:
            return list(points)
        return []
