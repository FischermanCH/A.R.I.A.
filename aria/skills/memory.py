from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
import re

from litellm import aembedding
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from aria.core.config import EmbeddingsConfig, MemoryConfig
from aria.core.qdrant_client import create_async_qdrant_client
from aria.skills.base import BaseSkill, SkillResult


class MemorySkill(BaseSkill):
    name = "memory"
    description = "Speichert und erinnert nutzerspezifische Fakten."
    max_context_chars = 1500
    CONTEXT_MEM_PREFIX = "aria_context-mem"

    def __init__(self, memory: MemoryConfig, embeddings: EmbeddingsConfig):
        self.memory = memory
        self.embeddings = embeddings
        self.timeout_seconds = embeddings.timeout_seconds
        self.qdrant = create_async_qdrant_client(
            url=memory.qdrant_url,
            api_key=(memory.qdrant_api_key or None),
            timeout=self.timeout_seconds,
        )
        self._collection_ready = False
        self._collection_cache: dict[tuple[str, int], str] = {}
        self._project_root = Path(__file__).resolve().parents[2]
        self._compression_prompt_cache: tuple[str, float] | None = None
        self.last_cleanup_status: dict[str, Any] = {
            "scope": "",
            "user_id": "",
            "removed_count": 0,
            "removed_collections": [],
            "timestamp": "",
        }

    def _set_last_cleanup_status(self, scope: str, user_id: str, removed: list[str]) -> None:
        self.last_cleanup_status = {
            "scope": str(scope or "").strip(),
            "user_id": str(user_id or "").strip(),
            "removed_count": len(removed),
            "removed_collections": list(removed),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _resolve_embedding_model(self) -> str:
        model = self.embeddings.model.strip()
        if not model:
            return model
        # LiteLLM aembedding requires provider prefix for many gateways.
        # Keep ollama* models untouched, and auto-prefix bare names as openai/.
        if "/" not in model and not model.lower().startswith("ollama"):
            return f"openai/{model}"
        return model

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    @staticmethod
    def _tokenize_for_match(text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_.-]+", text.lower())
        stop = {
            "und", "oder", "der", "die", "das", "ein", "eine", "mein", "meine",
            "dein", "deine", "du", "dich", "an", "von", "mit", "ist", "sind",
            "was", "weisst", "weisst", "noch", "erinnerst", "über",
        }
        return [t for t in tokens if len(t) >= 3 and t not in stop]

    @staticmethod
    def _clean_fact_text(text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(
            r"^(merke?\s+dir[:;,]?\s*|merk\s+dir[:;,]?\s*|speichere?\s*[:;,]?\s*|notier\s+dir[:;,]?\s*)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip(" .")
        return cleaned

    @staticmethod
    def _is_network_query(query_tokens: list[str]) -> bool:
        network_terms = {"netzwerk", "lan", "ip", "dns", "firewall", "pihole", "nas", "subnet", "gateway"}
        return any(token in network_terms for token in query_tokens)

    @staticmethod
    def _slug_user_id(user_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip().lower())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "web"

    def _user_filter(self, user_id: str) -> Filter:
        normalized = str(user_id or "").strip() or "web"
        return Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=normalized))])

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _type_label(memory_type: str) -> str:
        mapping = {
            "fact": "FAKT",
            "preference": "PRAEFERENZ",
            "knowledge": "WISSEN",
            "session": "KONTEXT",
        }
        return mapping.get(memory_type, "MEMORY")

    def _combined_score(
        self,
        base_score: float,
        memory_type: str,
        payload: dict[str, Any],
    ) -> float:
        cfg = self.memory.collections
        type_cfg = {
            "fact": cfg.facts,
            "preference": cfg.preferences,
            "knowledge": cfg.knowledge,
            "session": cfg.sessions,
        }.get(memory_type, cfg.sessions)
        weight = float(type_cfg.weight)

        if memory_type == "session" and bool(type_cfg.time_decay):
            created = self._parse_timestamp(payload.get("created_at")) or self._parse_timestamp(payload.get("timestamp"))
            if created:
                age_days = max(0.0, (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 86400.0)
                time_decay = max(0.3, 1.0 - (age_days / 30.0) * 0.7)
                weight *= time_decay

        return max(0.0, float(base_score)) * weight

    @staticmethod
    def _friendly_memory_error(exc: Exception) -> str:
        text = str(exc).lower()
        if any(token in text for token in ("connection refused", "failed to connect", "timeout", "temporarily unavailable")):
            return "memory_unavailable"
        if any(token in text for token in ("embedding", "invalid model", "api key", "authentication")):
            return "embedding_failed"
        return "memory_error"

    async def _list_collection_names(self) -> list[str]:
        try:
            resp = await self.qdrant.get_collections()
            names = [str(getattr(item, "name", "")).strip() for item in getattr(resp, "collections", [])]
            return sorted(set(name for name in names if name))
        except Exception:
            return []

    @staticmethod
    def _normalize_memory_type(collection: str, payload_type: str | None) -> str:
        raw = str(payload_type or "").strip().lower()
        if raw in {"fact", "preference", "knowledge", "session"}:
            return raw
        name = str(collection or "").lower()
        if "session" in name:
            return "session"
        if "preference" in name:
            return "preference"
        if "knowledge" in name:
            return "knowledge"
        if "context-mem" in name:
            return "knowledge"
        return "fact"

    async def _build_recall_targets(
        self,
        user_id: str,
        base_collection: str | None = None,
    ) -> list[dict[str, Any]]:
        slug = self._slug_user_id(user_id)
        cfg = self.memory.collections

        facts_collection = f"{cfg.facts.prefix}_{slug}"
        preference_collection = f"{cfg.preferences.prefix}_{slug}"
        knowledge_collection = f"{cfg.knowledge.prefix}_{slug}"
        context_mem_collection = f"{self.CONTEXT_MEM_PREFIX}_{slug}"
        session_prefix = f"{cfg.sessions.prefix}_{slug}_"
        current_session_collection = f"{session_prefix}{datetime.now().strftime('%y%m%d')}"
        legacy_collection = f"{self.memory.collection}_{slug}"

        known_names = await self._list_collection_names()
        session_collections = [name for name in known_names if name.startswith(session_prefix)]
        if current_session_collection not in session_collections:
            session_collections.append(current_session_collection)

        targets: list[dict[str, Any]] = [
            {
                "type": "fact",
                "label": self._type_label("fact"),
                "collection": facts_collection,
                "top_k": int(cfg.facts.top_k),
            },
            {
                "type": "preference",
                "label": self._type_label("preference"),
                "collection": preference_collection,
                "top_k": int(cfg.preferences.top_k),
            },
            {
                "type": "knowledge",
                "label": self._type_label("knowledge"),
                "collection": knowledge_collection,
                "top_k": int(cfg.knowledge.top_k),
            },
            {
                "type": "knowledge",
                "label": self._type_label("knowledge"),
                "collection": context_mem_collection,
                "top_k": int(cfg.knowledge.top_k),
            },
            {
                "type": "fact",
                "label": self._type_label("fact"),
                "collection": legacy_collection,
                "top_k": int(cfg.facts.top_k),
            },
        ]

        for session_collection in session_collections:
            targets.append(
                {
                    "type": "session",
                    "label": self._type_label("session"),
                    "collection": session_collection,
                    "top_k": int(cfg.sessions.top_k),
                }
            )

        if base_collection:
            targets.append(
                {
                    "type": "fact",
                    "label": self._type_label("fact"),
                    "collection": base_collection,
                    "top_k": int(cfg.facts.top_k),
                }
            )

        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for target in targets:
            key = (target["type"], target["collection"])
            if key not in unique:
                unique[key] = target

        return list(unique.values())

    async def _query_weighted_hits(
        self,
        vector: list[float],
        user_id: str,
        target: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            exists = await self.qdrant.collection_exists(collection_name=target["collection"])
            if not exists:
                return []
            query_result = await self.qdrant.query_points(
                collection_name=target["collection"],
                query=vector,
                query_filter=self._user_filter(user_id),
                limit=max(1, int(target["top_k"])),
            )
        except Exception:
            return []

        weighted: list[dict[str, Any]] = []
        for hit in self._extract_hits(query_result):
            payload = hit.payload or {}
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            score = self._combined_score(getattr(hit, "score", 0.0), target["type"], payload)
            weighted.append(
                {
                    "score": score,
                    "label": target["label"],
                    "type": target["type"],
                    "text": self._clean_fact_text(text),
                }
            )
        return weighted

    async def _query_forget_hits(
        self,
        vector: list[float],
        user_id: str,
        target: dict[str, Any],
        threshold: float,
    ) -> list[dict[str, Any]]:
        try:
            exists = await self.qdrant.collection_exists(collection_name=target["collection"])
            if not exists:
                return []
            query_result = await self.qdrant.query_points(
                collection_name=target["collection"],
                query=vector,
                query_filter=self._user_filter(user_id),
                limit=max(2, int(target["top_k"]) + 2),
            )
        except Exception:
            return []

        hits: list[dict[str, Any]] = []
        for hit in self._extract_hits(query_result):
            score = float(getattr(hit, "score", 0.0) or 0.0)
            if score < threshold:
                continue
            payload = hit.payload or {}
            text = self._clean_fact_text(str(payload.get("text", "")).strip())
            if not text:
                continue
            hit_id = getattr(hit, "id", None)
            if hit_id is None:
                continue
            hits.append(
                {
                    "collection": target["collection"],
                    "id": str(hit_id),
                    "type": target["type"],
                    "label": target["label"],
                    "text": text[:220],
                    "score": score,
                }
            )
        return hits

    async def _candidate_collections(self, base_collection: str) -> list[str]:
        base = (base_collection or self.memory.collection).strip() or self.memory.collection
        names: list[str] = [base]
        family_root = base.split("_session_", 1)[0]
        family_root = family_root.split("_dim_", 1)[0]

        for cached in self._collection_cache.values():
            if cached == base or cached.startswith(f"{base}_dim_") or cached == family_root or cached.startswith(f"{family_root}_"):
                if cached not in names:
                    names.append(cached)

        try:
            resp = await self.qdrant.get_collections()
            for item in getattr(resp, "collections", []):
                name = str(getattr(item, "name", "")).strip()
                if not name:
                    continue
                if (
                    name == base
                    or name.startswith(f"{base}_dim_")
                    or name == family_root
                    or name.startswith(f"{family_root}_")
                ):
                    if name not in names:
                        names.append(name)
        except Exception:
            pass

        return names

    async def _recall_keyword_fallback(
        self,
        query: str,
        user_id: str,
        top_k: int,
        base_collection: str | None = None,
        collections: list[str] | None = None,
    ) -> SkillResult:
        all_points: list[Any] = []
        collection_names = collections or await self._candidate_collections(base_collection or self.memory.collection)

        for collection_name in collection_names:
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection_name)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=collection_name,
                        scroll_filter=self._user_filter(user_id),
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    all_points.extend(points)
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue

        if not all_points:
            return SkillResult(skill_name=self.name, content="Keine passende Erinnerung gefunden.", success=True)

        query_tokens = self._tokenize_for_match(query)
        is_network_query = self._is_network_query(query_tokens)
        network_terms = ("netzwerk", "lan", "ip", "dns", "firewall", "pihole", "nas", "subnet", "gateway")
        scored: list[tuple[int, str]] = []
        for point in all_points:
            payload = point.payload or {}
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            hay = text.lower()
            score = 0
            for token in query_tokens:
                if token in hay:
                    score += 1
            if is_network_query:
                for term in network_terms:
                    if term in hay:
                        score += 1
                if score == 0:
                    # For broad network requests include remaining user facts at low score,
                    # so knowledge spread across collections is not dropped.
                    score = 1
            if score > 0:
                scored.append((score, text))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return SkillResult(skill_name=self.name, content="Keine passende Erinnerung gefunden.", success=True)

        output_count = max(top_k, 6)
        selected_lines: list[str] = []
        seen: set[str] = set()
        for _, raw_text in scored:
            cleaned = self._clean_fact_text(raw_text)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            selected_lines.append(f"- {cleaned}")
            if len(selected_lines) >= output_count:
                break

        if not selected_lines:
            return SkillResult(skill_name=self.name, content="Keine passende Erinnerung gefunden.", success=True)

        content = "[Memory: hybride Suche]\n" + "\n".join(selected_lines)
        truncated, saved = self.truncate(content)
        return SkillResult(skill_name=self.name, content=truncated, success=True, tokens_saved=saved)

    async def _embed(self, text: str) -> tuple[list[float], dict[str, int]]:
        model_name = self._resolve_embedding_model()
        response = await aembedding(
            model=model_name,
            input=[text],
            api_base=self.embeddings.api_base,
            api_key=self.embeddings.api_key or None,
            timeout=self.timeout_seconds,
        )
        item = response.data[0]
        embedding = item["embedding"] if isinstance(item, dict) else item.embedding
        usage = self._extract_usage(response)
        return [float(v) for v in embedding], usage

    async def _ensure_collection(self, vector_size: int, base_collection: str | None = None) -> None:
        _ = await self._get_collection_for_vector(vector_size, base_collection=base_collection)

    async def _get_collection_vector_size(self, collection_name: str) -> int | None:
        try:
            info = await self.qdrant.get_collection(collection_name=collection_name)
            vectors = getattr(getattr(info, "config", None), "params", None)
            vectors = getattr(vectors, "vectors", None)
            if hasattr(vectors, "size"):
                return int(vectors.size)
            if isinstance(vectors, dict):
                first = next(iter(vectors.values()), None)
                if first is not None and hasattr(first, "size"):
                    return int(first.size)
        except Exception:
            return None
        return None

    async def _ensure_collection_exists(self, collection_name: str, vector_size: int) -> None:
        exists = await self.qdrant.collection_exists(collection_name=collection_name)
        if not exists:
            await self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    async def _get_collection_for_vector(self, vector_size: int, base_collection: str | None = None) -> str:
        base = (base_collection or self.memory.collection).strip()
        cache_key = (base, vector_size)
        if cache_key in self._collection_cache:
            return self._collection_cache[cache_key]

        await self._ensure_collection_exists(base, vector_size)
        base_size = await self._get_collection_vector_size(base)

        if base_size is None or base_size == vector_size:
            self._collection_cache[cache_key] = base
            return base

        alt = f"{base}_dim_{vector_size}"
        await self._ensure_collection_exists(alt, vector_size)
        self._collection_cache[cache_key] = alt
        return alt

    async def _store(
        self,
        text: str,
        user_id: str,
        base_collection: str | None = None,
        memory_type: str = "fact",
        source: str = "explicit",
    ) -> SkillResult:
        normalized_text = self._clean_fact_text(text).lower()
        normalized_user = user_id.strip()

        # Backward-compatible dedupe: detect existing payload text even if old points used random UUIDs.
        candidate_collections = await self._candidate_collections(base_collection or self.memory.collection)
        for col in candidate_collections:
            try:
                exists = await self.qdrant.collection_exists(collection_name=col)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=col,
                        scroll_filter=self._user_filter(user_id),
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for p in points:
                        payload = p.payload or {}
                        existing_user = str(payload.get("user_id", "")).strip()
                        existing_text = self._clean_fact_text(str(payload.get("text", ""))).lower()
                        if existing_user == normalized_user and existing_text == normalized_text:
                            return SkillResult(
                                skill_name=self.name,
                                content="Bereits gespeichert.",
                                success=True,
                                metadata={"deduplicated": True},
                            )
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue

        vector, usage = await self._embed(text)
        base_name = (base_collection or self.memory.collection).strip() or self.memory.collection
        collection_name = await self._get_collection_for_vector(len(vector), base_collection=base_name)

        deterministic_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{collection_name}|{user_id.strip()}|{text.strip().lower()}",
            )
        )

        point = PointStruct(
            id=deterministic_id,
            vector=vector,
            payload={
                "text": text,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": memory_type,
                "source": source,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        await self.qdrant.upsert(collection_name=collection_name, points=[point])
        return SkillResult(
            skill_name=self.name,
            content="Speicheraktion erfolgreich.",
            success=True,
            metadata={
                "embedding_usage": usage,
                "embedding_model": self._resolve_embedding_model(),
                "memory_type": memory_type,
            },
        )

    async def _recall(
        self,
        query: str,
        user_id: str,
        top_k: int,
        base_collection: str | None = None,
    ) -> SkillResult:
        try:
            vector, usage = await self._embed(query)
            recall_targets = await self._build_recall_targets(user_id=user_id, base_collection=base_collection)
            target_collections = [t["collection"] for t in recall_targets]
            tasks = [
                self._query_weighted_hits(vector=vector, user_id=user_id, target=target)
                for target in recall_targets
            ]
            query_results = await asyncio.gather(*tasks, return_exceptions=True)
            weighted_hits: list[dict[str, Any]] = []
            for item in query_results:
                if isinstance(item, Exception):
                    continue
                weighted_hits.extend(item)
        except Exception:
            return await self._recall_keyword_fallback(
                query=query,
                user_id=user_id,
                top_k=top_k,
                base_collection=base_collection,
                collections=(await self._candidate_collections(base_collection or self.memory.collection)),
            )

        if not weighted_hits:
            fallback = await self._recall_keyword_fallback(
                query=query,
                user_id=user_id,
                top_k=top_k,
                base_collection=base_collection,
                collections=target_collections,
            )
            fallback.metadata["embedding_usage"] = usage
            fallback.metadata["embedding_model"] = self._resolve_embedding_model()
            return fallback

        weighted_hits.sort(key=lambda item: item["score"], reverse=True)
        if not weighted_hits:
            return SkillResult(skill_name=self.name, content="Keine passende Erinnerung gefunden.", success=True)

        output_count = max(top_k, 5)
        lines: list[str] = []
        seen: set[str] = set()
        for item in weighted_hits:
            cleaned = str(item["text"]).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                lines.append(f"- [{item['label']}] {cleaned}")
            if len(lines) >= output_count:
                break

        content = "\n".join(lines) if lines else "Keine passende Erinnerung gefunden."
        truncated, saved = self.truncate(content)
        return SkillResult(
            skill_name=self.name,
            content=truncated,
            success=True,
            tokens_saved=saved,
            metadata={
                "embedding_usage": usage,
                "embedding_model": self._resolve_embedding_model(),
            },
        )

    @staticmethod
    def _coerce_point_id(value: str) -> str | int:
        raw = str(value).strip()
        if raw.isdigit():
            try:
                return int(raw)
            except ValueError:
                return raw
        return raw

    async def _forget_preview(
        self,
        query: str,
        user_id: str,
        threshold: float = 0.75,
        max_hits: int = 5,
    ) -> SkillResult:
        try:
            vector, usage = await self._embed(query)
            targets = await self._build_recall_targets(user_id=user_id)
            tasks = [
                self._query_forget_hits(
                    vector=vector,
                    user_id=user_id,
                    target=target,
                    threshold=threshold,
                )
                for target in targets
            ]
            query_results = await asyncio.gather(*tasks, return_exceptions=True)
            candidates: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for item in query_results:
                if isinstance(item, Exception):
                    continue
                for row in item:
                    key = (str(row["collection"]), str(row["id"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(row)
            candidates.sort(key=lambda c: float(c.get("score", 0.0)), reverse=True)
            candidates = candidates[:max_hits]
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=f"memory_forget_preview_error: {exc}",
            )

        if not candidates:
            return SkillResult(
                skill_name=self.name,
                content="Ich habe nichts Passendes zum Vergessen gefunden.",
                success=True,
                metadata={
                    "embedding_usage": usage,
                    "embedding_model": self._resolve_embedding_model(),
                    "forget_candidates": [],
                },
            )

        lines = [
            f"- [{str(c['label'])}] {str(c['text'])}"
            for c in candidates
        ]
        content = "Ich habe folgende Eintraege gefunden:\n" + "\n".join(lines)
        truncated, saved = self.truncate(content)
        return SkillResult(
            skill_name=self.name,
            content=truncated,
            success=True,
            tokens_saved=saved,
            metadata={
                "embedding_usage": usage,
                "embedding_model": self._resolve_embedding_model(),
                "forget_candidates": candidates,
            },
        )

    async def _forget_apply(
        self,
        user_id: str,
        candidates: list[dict[str, Any]],
    ) -> SkillResult:
        deleted = 0
        grouped: dict[str, list[str]] = {}
        for c in candidates:
            collection = str(c.get("collection", "")).strip()
            point_id = str(c.get("id", "")).strip()
            if not collection or not point_id:
                continue
            grouped.setdefault(collection, []).append(point_id)

        for collection, point_ids in grouped.items():
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                coerced_ids = [self._coerce_point_id(point_id) for point_id in point_ids]
                await self.qdrant.delete(
                    collection_name=collection,
                    points_selector=PointIdsList(points=coerced_ids),
                    wait=True,
                )
                deleted += len(point_ids)
            except Exception:
                continue

        if deleted <= 0:
            return SkillResult(
                skill_name=self.name,
                content="Nichts gelöscht. Bitte Vorschau erneut starten.",
                success=True,
            )
        if str(user_id or "").strip():
            await self.cleanup_empty_collections_for_user(user_id)
        return SkillResult(
            skill_name=self.name,
            content=f"Löschen bestätigt. {deleted} Eintraege entfernt.",
            success=True,
        )

    async def _list_rows_from_collection(
        self,
        collection: str,
        user_id: str,
        memory_type: str,
        label: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            exists = await self.qdrant.collection_exists(collection_name=collection)
            if not exists:
                return rows
            offset = None
            while True:
                points, next_offset = await self.qdrant.scroll(
                    collection_name=collection,
                    scroll_filter=self._user_filter(user_id),
                    limit=min(100, max(10, limit)),
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    payload = point.payload or {}
                    text = self._clean_fact_text(str(payload.get("text", "")).strip())
                    if not text:
                        continue
                    timestamp = (
                        str(payload.get("updated_at", "")).strip()
                        or str(payload.get("created_at", "")).strip()
                        or str(payload.get("timestamp", "")).strip()
                    )
                    rows.append(
                        {
                            "id": str(getattr(point, "id", "")),
                            "collection": collection,
                            "type": str(payload.get("type", memory_type)).strip() or memory_type,
                            "label": label,
                            "text": text,
                            "timestamp": timestamp,
                            "source": str(payload.get("source", "")).strip() or "n/a",
                        }
                    )
                    if len(rows) >= limit:
                        return rows
                if next_offset is None:
                    break
                offset = next_offset
        except Exception:
            return rows
        return rows

    async def list_memories(
        self,
        user_id: str,
        type_filter: str = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        targets = await self._build_recall_targets(user_id=user_id)
        filter_key = type_filter.strip().lower()
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for target in targets:
            target_type = str(target.get("type", "")).strip().lower()
            if filter_key and filter_key != "all" and target_type != filter_key:
                continue
            rows = await self._list_rows_from_collection(
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

        def _sort_key(item: dict[str, Any]) -> float:
            parsed = self._parse_timestamp(item.get("timestamp"))
            if not parsed:
                return 0.0
            return parsed.astimezone(timezone.utc).timestamp()

        items = sorted(unique.values(), key=_sort_key, reverse=True)
        return items[:limit]

    async def list_memories_global(
        self,
        user_id: str,
        type_filter: str = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        filter_key = type_filter.strip().lower()
        rows: list[dict[str, Any]] = []
        names = await self._list_collection_names()
        for collection in names:
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=collection,
                        scroll_filter=self._user_filter(user_id),
                        limit=min(200, max(20, limit)),
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points:
                        payload = point.payload or {}
                        text = self._clean_fact_text(str(payload.get("text", "")).strip())
                        if not text:
                            continue
                        memory_type = self._normalize_memory_type(collection, payload.get("type"))
                        if filter_key and filter_key != "all" and memory_type != filter_key:
                            continue
                        label = self._type_label(memory_type)
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
                            }
                        )
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue

        def _sort_key(item: dict[str, Any]) -> float:
            parsed = self._parse_timestamp(item.get("timestamp"))
            if not parsed:
                return 0.0
            return parsed.astimezone(timezone.utc).timestamp()

        rows.sort(key=_sort_key, reverse=True)
        return rows[:limit]

    async def get_user_collection_stats(self, user_id: str) -> list[dict[str, Any]]:
        names = await self._list_collection_names()
        stats: list[dict[str, Any]] = []
        for collection in names:
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                count = 0
                inferred_type = "fact"
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=collection,
                        scroll_filter=self._user_filter(user_id),
                        limit=256,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    if points:
                        if count == 0:
                            first_payload = (points[0].payload or {})
                            inferred_type = self._normalize_memory_type(collection, first_payload.get("type"))
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

    async def cleanup_empty_collections_for_user(self, user_id: str) -> list[str]:
        slug = self._slug_user_id(user_id)
        names = await self._list_collection_names()
        removed: list[str] = []

        for collection in names:
            lowered = collection.lower()
            if slug not in lowered:
                continue
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                points, _next_offset = await self.qdrant.scroll(
                    collection_name=collection,
                    limit=1,
                    with_payload=False,
                    with_vectors=False,
                )
                if points:
                    continue
                await self.qdrant.delete_collection(collection_name=collection)
                removed.append(collection)
            except Exception:
                continue
        self._set_last_cleanup_status(scope="user", user_id=user_id, removed=removed)
        return removed

    def _is_memory_collection_name(self, collection: str) -> bool:
        name = str(collection or "").strip().lower()
        if not name:
            return False

        prefixes = {
            str(self.memory.collection or "").strip().lower(),
            str(self.memory.collections.facts.prefix or "").strip().lower(),
            str(self.memory.collections.preferences.prefix or "").strip().lower(),
            str(self.memory.collections.sessions.prefix or "").strip().lower(),
            str(self.memory.collections.knowledge.prefix or "").strip().lower(),
            "aria_memory",  # legacy default prefix
        }

        for prefix in prefixes:
            if not prefix:
                continue
            if name == prefix or name.startswith(f"{prefix}_"):
                return True
        return False

    def _is_session_collection_name(self, collection: str) -> bool:
        name = str(collection or "").strip().lower()
        if not name:
            return False
        session_prefix = str(self.memory.collections.sessions.prefix or "").strip().lower()
        if session_prefix and (name == session_prefix or name.startswith(f"{session_prefix}_")):
            return True
        return name.startswith("aria_memory_") and "_session_" in name

    @staticmethod
    def _normalize_trigger_phrases(trigger_phrases: list[str]) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for item in trigger_phrases:
            text = re.sub(r"\s+", " ", str(item or "").strip().lower())
            if len(text) < 2 or text in seen:
                continue
            seen.add(text)
            rows.append(text)
        return rows

    @staticmethod
    def _matches_operational_trigger(text: str, trigger_phrases: list[str]) -> bool:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized:
            return False
        for phrase in trigger_phrases:
            if normalized == phrase:
                return True
            if normalized.startswith(f"{phrase} "):
                return True
            if normalized.startswith(f"{phrase}:"):
                return True
        return False

    async def cleanup_empty_collections_global(self) -> list[str]:
        names = await self._list_collection_names()
        removed: list[str] = []
        for collection in names:
            if not self._is_memory_collection_name(collection):
                continue
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                points, _next_offset = await self.qdrant.scroll(
                    collection_name=collection,
                    limit=1,
                    with_payload=False,
                    with_vectors=False,
                )
                if points:
                    continue
                await self.qdrant.delete_collection(collection_name=collection)
                removed.append(collection)
            except Exception:
                continue
        self._set_last_cleanup_status(scope="global", user_id="*", removed=removed)
        return removed

    async def cleanup_operational_session_entries(self, trigger_phrases: list[str]) -> dict[str, Any]:
        phrases = self._normalize_trigger_phrases(trigger_phrases)
        if not phrases:
            return {"removed_points": 0, "collections_touched": 0, "collections_removed": 0}

        names = await self._list_collection_names()
        grouped_ids: dict[str, list[str | int]] = {}
        touched_collections: set[str] = set()

        for collection in names:
            if not self._is_session_collection_name(collection):
                continue
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=collection,
                        limit=200,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points:
                        payload = getattr(point, "payload", {}) or {}
                        source = str(payload.get("source", "")).strip().lower()
                        text = str(payload.get("text", "")).strip()
                        point_id = getattr(point, "id", None)
                        if source != "auto_session" or point_id is None:
                            continue
                        if not self._matches_operational_trigger(text, phrases):
                            continue
                        grouped_ids.setdefault(collection, []).append(self._coerce_point_id(str(point_id)))
                        touched_collections.add(collection)
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue

        removed_points = 0
        for collection, point_ids in grouped_ids.items():
            if not point_ids:
                continue
            try:
                await self.qdrant.delete(
                    collection_name=collection,
                    points_selector=PointIdsList(points=point_ids),
                    wait=True,
                )
                removed_points += len(point_ids)
            except Exception:
                continue

        removed_collections = await self.cleanup_empty_collections_global()
        return {
            "removed_points": removed_points,
            "collections_touched": len(touched_collections),
            "collections_removed": len(removed_collections),
            "removed_collection_names": removed_collections,
        }

    async def search_memories(
        self,
        user_id: str,
        query: str,
        type_filter: str = "all",
        top_k: int = 25,
    ) -> list[dict[str, Any]]:
        vector, _usage = await self._embed(query)
        targets = await self._build_recall_targets(user_id=user_id)
        filter_key = type_filter.strip().lower()
        tasks = []
        active_targets: list[dict[str, Any]] = []
        for target in targets:
            target_type = str(target.get("type", "")).strip().lower()
            if filter_key and filter_key != "all" and target_type != filter_key:
                continue
            active_targets.append(target)
            tasks.append(
                self._query_forget_hits(
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
                        "timestamp": "",
                        "source": "n/a",
                    }
                )
        rows.sort(key=lambda value: float(value.get("score", 0.0)), reverse=True)
        return rows[:top_k]

    async def delete_memory_point(self, user_id: str, collection: str, point_id: str) -> bool:
        clean_user = str(user_id).strip()
        clean_collection = str(collection).strip()
        clean_id = str(point_id).strip()
        if not clean_collection or not clean_id:
            return False
        try:
            exists = await self.qdrant.collection_exists(collection_name=clean_collection)
            if not exists:
                return False
            await self.qdrant.delete(
                collection_name=clean_collection,
                points_selector=PointIdsList(points=[self._coerce_point_id(clean_id)]),
                wait=True,
            )
            if clean_user:
                await self.cleanup_empty_collections_for_user(clean_user)
            return True
        except Exception:
            return False

    async def update_memory_point(self, user_id: str, collection: str, point_id: str, text: str) -> bool:
        clean_collection = str(collection).strip()
        clean_id = str(point_id).strip()
        clean_text = self._clean_fact_text(str(text).strip())
        if not clean_collection or not clean_id or not clean_text:
            return False
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000]
        try:
            exists = await self.qdrant.collection_exists(collection_name=clean_collection)
            if not exists:
                return False
            points = await self.qdrant.retrieve(
                collection_name=clean_collection,
                ids=[self._coerce_point_id(clean_id)],
                with_payload=True,
                with_vectors=False,
            )
            if not points:
                return False
            payload = getattr(points[0], "payload", {}) or {}
            stored_user = str(payload.get("user_id", "")).strip()
            if stored_user != str(user_id).strip():
                return False
            await self.qdrant.set_payload(
                collection_name=clean_collection,
                payload={
                    "text": clean_text,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "source": "edited_ui",
                },
                points=[self._coerce_point_id(clean_id)],
                wait=True,
            )
            return True
        except Exception:
            return False

    def _load_compression_prompt_template(self) -> str:
        configured = str(self.memory.compression_summary_prompt or "").strip()
        path = Path(configured)
        if not path.is_absolute():
            path = (self._project_root / configured).resolve()

        fallback = "Summary {{kind}} {{day}}:\n{{entries}}"
        if not path.exists() or not path.is_file():
            return fallback
        try:
            mtime = path.stat().st_mtime
            if self._compression_prompt_cache and self._compression_prompt_cache[1] == mtime:
                return self._compression_prompt_cache[0]
            text = path.read_text(encoding="utf-8").strip() or fallback
            self._compression_prompt_cache = (text, mtime)
            return text
        except OSError:
            return fallback

    def _build_compression_summary(self, kind: str, day_raw: str, rows: list[dict[str, Any]]) -> str:
        template = self._load_compression_prompt_template()
        entries = "\n".join(f"- {row['text']}" for row in rows[:8])
        rendered = (
            template
            .replace("{{kind}}", kind)
            .replace("{{day}}", day_raw)
            .replace("{{entries}}", entries)
        ).strip()
        if rendered:
            return rendered
        return f"{kind}_summary {day_raw}: " + "; ".join(row["text"] for row in rows[:8])

    async def compress_old_sessions(
        self,
        user_id: str,
        compress_after_days: int = 7,
        monthly_after_days: int = 30,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "compressed_week": 0,
            "compressed_month": 0,
            "collections_removed": 0,
            "compressed_collections": [],
            "removed_collections": [],
            "skipped_recent": [],
            "skipped_empty": [],
            "failed_delete": [],
        }
        slug = self._slug_user_id(user_id)
        session_prefix = f"{self.memory.collections.sessions.prefix}_{slug}_"
        legacy_session_prefix = f"aria_memory_{slug}_session_"
        context_mem_collection = f"{self.CONTEXT_MEM_PREFIX}_{slug}"
        now = datetime.now(timezone.utc)

        names = await self._list_collection_names()
        session_names = [
            name
            for name in names
            if name.startswith(session_prefix) or name.startswith(legacy_session_prefix)
        ]
        for collection_name in session_names:
            rows = await self._list_rows_from_collection(
                collection=collection_name,
                user_id=user_id,
                memory_type="session",
                label=self._type_label("session"),
                limit=120,
            )
            if not rows:
                summary["skipped_empty"].append(collection_name)
                continue

            age_days: int | None = None
            if collection_name.startswith(session_prefix):
                day_raw = collection_name.removeprefix(session_prefix)
                try:
                    day = datetime.strptime(day_raw, "%y%m%d").replace(tzinfo=timezone.utc)
                    age_days = max(0, int((now - day).total_seconds() // 86400))
                except ValueError:
                    age_days = None

            if age_days is None:
                newest_ts: datetime | None = None
                for row in rows:
                    parsed = self._parse_timestamp(row.get("timestamp"))
                    if parsed is None:
                        continue
                    if newest_ts is None or parsed > newest_ts:
                        newest_ts = parsed
                if newest_ts is None:
                    # Unknown age: do not compress to avoid moving active context blindly.
                    continue
                age_days = max(0, int((now - newest_ts.astimezone(timezone.utc)).total_seconds() // 86400))

            if age_days < max(1, compress_after_days):
                summary["skipped_recent"].append(collection_name)
                continue

            if age_days >= max(monthly_after_days, compress_after_days + 1):
                kind = "month"
                memory_type = "knowledge"
                summary["compressed_month"] += 1
            else:
                kind = "week"
                memory_type = "knowledge"
                summary["compressed_week"] += 1

            day_raw = collection_name.removeprefix(session_prefix) if collection_name.startswith(session_prefix) else "legacy"
            text = self._build_compression_summary(kind=kind, day_raw=day_raw, rows=rows)
            await self._store(
                text=text,
                user_id=user_id,
                base_collection=context_mem_collection,
                memory_type=memory_type,
                source="compression",
            )
            summary["compressed_collections"].append(collection_name)
            try:
                await self.qdrant.delete_collection(collection_name=collection_name)
                summary["collections_removed"] += 1
                summary["removed_collections"].append(collection_name)
            except Exception:
                summary["failed_delete"].append(collection_name)
                continue
        await self.cleanup_empty_collections_for_user(user_id)
        return summary

    async def _discover_users_from_collections(self) -> list[str]:
        names = await self._list_collection_names()
        users: set[str] = set()
        prefixes = (
            self.memory.collections.facts.prefix.strip(),
            self.memory.collections.preferences.prefix.strip(),
            self.memory.collections.knowledge.prefix.strip(),
            self.memory.collections.sessions.prefix.strip(),
        )
        for name in names:
            for prefix in prefixes:
                if not prefix:
                    continue
                marker = f"{prefix}_"
                if not name.startswith(marker):
                    continue
                rest = name[len(marker):]
                if prefix == self.memory.collections.sessions.prefix.strip():
                    if "_" in rest:
                        rest = rest.rsplit("_", 1)[0]
                slug = self._slug_user_id(rest)
                if slug:
                    users.add(slug)
        return sorted(users)

    async def compress_all_users(
        self,
        compress_after_days: int = 7,
        monthly_after_days: int = 30,
    ) -> dict[str, int]:
        users = await self._discover_users_from_collections()
        total = {
            "users": len(users),
            "compressed_week": 0,
            "compressed_month": 0,
            "collections_removed": 0,
        }
        for user in users:
            stats = await self.compress_old_sessions(
                user_id=user,
                compress_after_days=compress_after_days,
                monthly_after_days=monthly_after_days,
            )
            total["compressed_week"] += int(stats.get("compressed_week", 0))
            total["compressed_month"] += int(stats.get("compressed_month", 0))
            total["collections_removed"] += int(stats.get("collections_removed", 0))
        return total

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

    async def execute(self, query: str, params: dict) -> SkillResult:
        action = str(params.get("action", "")).strip()
        user_id = str(params.get("user_id", "web"))
        collection = str(params.get("collection", "")).strip() or self.memory.collection
        try:
            if action == "store":
                text = str(params.get("text", query)).strip()
                if not text:
                    return SkillResult(skill_name=self.name, content="", success=False, error="Leerer Speichertext")
                return await self._store(
                    text=text,
                    user_id=user_id,
                    base_collection=collection,
                    memory_type=str(params.get("memory_type", "fact")).strip() or "fact",
                    source=str(params.get("source", "explicit")).strip() or "explicit",
                )

            if action == "recall":
                top_k = int(params.get("top_k", self.memory.top_k))
                return await self._recall(query=query, user_id=user_id, top_k=top_k, base_collection=collection)

            if action == "forget_preview":
                threshold = float(params.get("threshold", 0.75))
                max_hits = int(params.get("max_hits", 5))
                return await self._forget_preview(query=query, user_id=user_id, threshold=threshold, max_hits=max_hits)

            if action == "forget_apply":
                candidates = params.get("candidates", [])
                if not isinstance(candidates, list):
                    candidates = []
                return await self._forget_apply(user_id=user_id, candidates=candidates)

            if action == "compress_sessions":
                compress_after = int(params.get("compress_after_days", 7))
                monthly_after = int(params.get("monthly_after_days", 30))
                stats = await self.compress_old_sessions(
                    user_id=user_id,
                    compress_after_days=compress_after,
                    monthly_after_days=monthly_after,
                )
                return SkillResult(
                    skill_name=self.name,
                    content=(
                        f"Komprimierung beendet: Woche={stats['compressed_week']}, "
                        f"Monat={stats['compressed_month']}, gelöschte Collections={stats['collections_removed']}"
                    ),
                    success=True,
                    metadata={"compression_stats": stats},
                )

            return SkillResult(skill_name=self.name, content="", success=False, error="Unbekannte Aktion")
        except Exception as exc:  # noqa: BLE001
            category = self._friendly_memory_error(exc)
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=f"{category}: {exc}",
            )
