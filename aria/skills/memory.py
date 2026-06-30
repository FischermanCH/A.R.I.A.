from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
import re

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
from aria.core.doc_meta_catalog import DOC_META_PREFIX, DocumentMetaCatalogStore, document_meta_collection_for_user
from aria.core.document_memory_helpers import document_collection_user_slug
from aria.core.document_memory_helpers import document_payload_id
from aria.core.document_memory_helpers import document_payload_name
from aria.core.document_memory_helpers import is_document_collection_name
from aria.core.document_memory_helpers import is_document_guide_collection_name
from aria.core.document_memory_helpers import is_document_meta_collection_name
from aria.core.document_memory_helpers import is_document_payload
from aria.core.document_memory_helpers import payload_user_matches
from aria.core.document_memory_helpers import slug_user_id
from aria.core.document_ingest import PreparedDocument
from aria.core.document_memory_service import DocumentMemoryService
from aria.core.embedding_client import EmbeddingClient
from aria.core.i18n import I18NStore
from aria.core.memory_admin_query_service import MemoryAdminQueryService
from aria.core.memory_recall_helpers import build_recall_source_entries
from aria.core.memory_recall_helpers import format_recall_source_detail
from aria.core.memory_recall_helpers import recall_source_priority
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.session_compression_service import SessionCompressionService
from aria.core.usage_meter import UsageMeter
from aria.skills.base import BaseSkill, SkillResult

_MEMORY_SKILL_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _memory_skill_text(key: str, default: str = "", **values: object) -> str:
    template = _MEMORY_SKILL_I18N.t("de", f"memory_skill.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _memory_skill_terms(key: str, fallback: tuple[str, ...]) -> set[str]:
    terms: list[str] = []
    for lang in ("de", "en"):
        raw = _MEMORY_SKILL_I18N.t(lang, f"memory_skill.{key}", "")
        terms.extend(term.strip().lower() for term in raw.split(",") if term.strip())
    return set(terms) or set(fallback)


class MemorySkill(BaseSkill):
    name = "memory"
    description = "Stores and recalls user-specific facts."
    max_context_chars = 1500
    CONTEXT_MEM_PREFIX = "aria_context-mem"
    DOCUMENT_GUIDE_PREFIX = "aria_doc_guides"
    LEARNING_PREFIX = "aria_learning"
    ROLLUP_LEVEL_WEEK = "week"
    ROLLUP_LEVEL_MONTH = "month"

    def __init__(
        self,
        memory: MemoryConfig,
        embeddings: EmbeddingsConfig,
        embedding_client: EmbeddingClient | None = None,
        usage_meter: UsageMeter | None = None,
    ):
        self.memory = memory
        self.embeddings = embeddings
        self.timeout_seconds = embeddings.timeout_seconds
        self.embedding_client = embedding_client or EmbeddingClient(embeddings, usage_meter=usage_meter)
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

    def _active_embedding_fingerprint(self) -> str:
        return str(self.embedding_client.fingerprint()).strip()

    def _memory_embedding_fingerprint(self) -> str:
        return str(getattr(self.memory, "embedding_fingerprint", "") or "").strip()

    def _payload_embedding_compatible(self, payload: dict[str, Any] | None) -> bool:
        data = payload or {}
        payload_fingerprint = str(data.get("embedding_fingerprint", "")).strip()
        active_fingerprint = self._active_embedding_fingerprint()
        if payload_fingerprint:
            return payload_fingerprint == active_fingerprint
        legacy_fingerprint = self._memory_embedding_fingerprint()
        if not legacy_fingerprint:
            return True
        return legacy_fingerprint == active_fingerprint

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
            "was", "weisst", "weisst", "noch", "erinnerst",
        }
        stop.update(_memory_skill_terms("match_stopwords", ("about",)))
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
        return slug_user_id(user_id)

    def _user_filter(self, user_id: str) -> Filter:
        normalized = str(user_id or "").strip() or "web"
        return Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=normalized))])

    def _payload_user_matches(self, payload_user_id: Any, requested_user_id: str) -> bool:
        return payload_user_matches(payload_user_id, requested_user_id)

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
            "reflection": "LERNEN",
            "learning_event": "LERN-EVENT",
            "learning_candidate": "LERN-KANDIDAT",
            "learning_active_hint": "AKTIVER LERN-HINWEIS",
            "learning_eval": "LERN-EVAL",
            "document": "DOKUMENT",
            "session": "KONTEXT",
        }
        return mapping.get(memory_type, "MEMORY")

    @staticmethod
    def _document_payload_name(payload: dict[str, Any] | None) -> str:
        return document_payload_name(payload)

    @staticmethod
    def _document_payload_id(payload: dict[str, Any] | None) -> str:
        return document_payload_id(payload)

    @staticmethod
    def _document_collection_user_slug(collection: str, prefix: str) -> str:
        return document_collection_user_slug(collection, prefix)

    @staticmethod
    def _is_document_payload(payload: dict[str, Any] | None) -> bool:
        return is_document_payload(payload)

    @staticmethod
    def _is_document_collection_name(collection: str) -> bool:
        return is_document_collection_name(collection)

    @classmethod
    def _is_document_guide_collection_name(cls, collection: str) -> bool:
        return is_document_guide_collection_name(collection, cls.DOCUMENT_GUIDE_PREFIX)

    @staticmethod
    def _is_document_meta_collection_name(collection: str) -> bool:
        return is_document_meta_collection_name(collection)

    def _document_guide_collection_for_user(self, user_id: str) -> str:
        return f"{self.DOCUMENT_GUIDE_PREFIX}_{self._slug_user_id(user_id)}"

    def _context_collection_for_user(self, user_id: str) -> str:
        return f"{self.CONTEXT_MEM_PREFIX}_{self._slug_user_id(user_id)}"

    def _is_rollup_payload(self, payload: dict[str, Any] | None) -> bool:
        data = payload or {}
        return (
            str(data.get("source", "")).strip().lower() == "compression"
            and str(data.get("rollup_level", "")).strip().lower() in {self.ROLLUP_LEVEL_WEEK, self.ROLLUP_LEVEL_MONTH}
        )

    @staticmethod
    def _session_day_from_collection_name(collection_name: str) -> date | None:
        raw = str(collection_name or "").strip()
        if not raw:
            return None
        day_raw = raw.rsplit("_", 1)[-1]
        if len(day_raw) != 6 or not day_raw.isdigit():
            return None
        try:
            return datetime.strptime(day_raw, "%y%m%d").date()
        except ValueError:
            return None

    @staticmethod
    def _week_bucket_for_day(day_value: date) -> tuple[str, date, date]:
        iso_year, iso_week, _ = day_value.isocalendar()
        start = day_value - timedelta(days=day_value.weekday())
        end = start + timedelta(days=6)
        return f"{iso_year}-W{iso_week:02d}", start, end

    @staticmethod
    def _month_bucket_for_day(day_value: date) -> tuple[str, date, date]:
        start = day_value.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        end = next_month - timedelta(days=1)
        return start.strftime("%Y-%m"), start, end

    def _display_memory_type(self, collection: str, payload: dict[str, Any] | None) -> str:
        if self._is_document_payload(payload) or self._is_document_collection_name(collection):
            return "document"
        return self._normalize_memory_type(collection, (payload or {}).get("type"))

    async def _store_rollup_summary(
        self,
        *,
        user_id: str,
        text: str,
        base_collection: str,
        rollup_level: str,
        rollup_bucket: str,
        period_start: date,
        period_end: date,
        source_kind: str,
        source_collections: list[str],
    ) -> SkillResult:
        vector, usage = await self._embed(
            text,
            source="compression",
            operation=f"{rollup_level}_rollup",
            user_id=user_id,
        )
        target_collection = await self._get_collection_for_vector(len(vector), base_collection=base_collection)
        point_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{target_collection}|{user_id.strip()}|rollup|{rollup_level}|{rollup_bucket}",
            )
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "text": text,
                "user_id": user_id,
                "timestamp": now_iso,
                "type": "knowledge",
                "source": "compression",
                "rollup_level": rollup_level,
                "rollup_bucket": rollup_bucket,
                "rollup_period_start": period_start.isoformat(),
                "rollup_period_end": period_end.isoformat(),
                "rollup_source_kind": source_kind,
                "rollup_source_count": len(source_collections),
                "rollup_source_collections": list(source_collections),
                "embedding_model": self._resolve_embedding_model(),
                "embedding_fingerprint": self._active_embedding_fingerprint(),
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        )
        await self.qdrant.upsert(collection_name=target_collection, points=[point])
        return SkillResult(
            skill_name=self.name,
            content="Rollup gespeichert.",
            success=True,
            metadata={
                "embedding_usage": usage,
                "embedding_model": self._resolve_embedding_model(),
                "rollup_level": rollup_level,
                "rollup_bucket": rollup_bucket,
                "collection": target_collection,
                "point_id": point_id,
            },
        )

    async def _list_rollup_rows(self, user_id: str, base_collection: str) -> list[dict[str, Any]]:
        rows = await self._list_rows_from_collection(
            collection=base_collection,
            user_id=user_id,
            memory_type="knowledge",
            label=self._type_label("knowledge"),
            limit=5000,
        )
        return [row for row in rows if str(row.get("source", "")).strip().lower() == "compression" and str(row.get("rollup_level", "")).strip()]

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
            "reflection": cfg.knowledge,
            "document": cfg.knowledge,
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
        if raw in {"fact", "preference", "knowledge", "session", "learning_event", "learning_candidate", "learning_active_hint", "learning_eval"}:
            return raw
        if raw in {"reflection", "learning"}:
            return "reflection"
        name = str(collection or "").lower()
        if "learning_evals" in name:
            return "learning_eval"
        if "learning_candidates" in name:
            return "learning_candidate"
        if "learning_active_hints" in name:
            return "learning_active_hint"
        if "learning_events" in name:
            return "learning_event"
        if "learning" in name:
            return "reflection"
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
        learning_collection = f"{self.LEARNING_PREFIX}_{slug}"
        learning_events_collection = f"{self.LEARNING_PREFIX}_events_{slug}"
        learning_candidates_collection = f"{self.LEARNING_PREFIX}_candidates_{slug}"
        learning_active_hints_collection = f"{self.LEARNING_PREFIX}_active_hints_{slug}"
        learning_evals_collection = f"{self.LEARNING_PREFIX}_evals_{slug}"
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
                "type": "reflection",
                "label": self._type_label("reflection"),
                "collection": learning_collection,
                "top_k": int(cfg.knowledge.top_k),
            },
            {
                "type": "learning_event",
                "label": self._type_label("learning_event"),
                "collection": learning_events_collection,
                "top_k": int(cfg.knowledge.top_k),
            },
            {
                "type": "learning_candidate",
                "label": self._type_label("learning_candidate"),
                "collection": learning_candidates_collection,
                "top_k": int(cfg.knowledge.top_k),
            },
            {
                "type": "learning_active_hint",
                "label": self._type_label("learning_active_hint"),
                "collection": learning_active_hints_collection,
                "top_k": int(cfg.knowledge.top_k),
            },
            {
                "type": "learning_eval",
                "label": self._type_label("learning_eval"),
                "collection": learning_evals_collection,
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

    async def _build_document_targets(self, user_id: str) -> list[dict[str, Any]]:
        _ = user_id
        names = await self._list_collection_names()
        targets: list[dict[str, Any]] = []
        for collection in names:
            if not self._is_document_collection_name(collection):
                continue
            targets.append(
                {
                    "type": "document",
                    "label": self._type_label("document"),
                    "collection": collection,
                    "top_k": int(self.memory.collections.knowledge.top_k),
                }
            )
        return targets

    @staticmethod
    def _build_document_guide_text(document: PreparedDocument, *, target_collection: str) -> str:
        return DocumentMemoryService.build_document_guide_text(document, target_collection=target_collection)

    async def _build_document_guide_point(
        self,
        *,
        user_id: str,
        document: PreparedDocument,
        target_collection: str,
    ) -> tuple[str, PointStruct, dict[str, int]]:
        return await DocumentMemoryService(self).build_document_guide_point(
            user_id=user_id,
            document=document,
            target_collection=target_collection,
        )

    async def _delete_document_guide_entries(
        self,
        *,
        user_id: str,
        target_collection: str,
        document_id: str = "",
        document_name: str = "",
    ) -> int:
        return await DocumentMemoryService(self).delete_document_guide_entries(
            user_id=user_id,
            target_collection=target_collection,
            document_id=document_id,
            document_name=document_name,
        )

    async def _query_document_guides(
        self,
        *,
        vector: list[float],
        query: str,
        user_id: str,
        max_hits: int,
    ) -> list[dict[str, Any]]:
        return await DocumentMemoryService(self).query_document_guides(
            vector=vector,
            query=query,
            user_id=user_id,
            max_hits=max_hits,
        )

    def _build_document_targets_from_guides(self, guide_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DocumentMemoryService.build_document_targets_from_guides(
            guide_hits,
            label=self._type_label("document"),
            top_k=int(self.memory.collections.knowledge.top_k),
        )

    async def _document_guide_payloads(self, *, user_id: str) -> list[dict[str, Any]]:
        guide_collection = self._document_guide_collection_for_user(user_id)
        requested_slug = self._slug_user_id(user_id)
        try:
            exists = await self.qdrant.collection_exists(collection_name=guide_collection)
            if not exists:
                return []
            rows: list[dict[str, Any]] = []
            offset = None
            while True:
                points, next_offset = await self.qdrant.scroll(
                    collection_name=guide_collection,
                    scroll_filter=None,
                    limit=200,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points or []:
                    payload = dict(getattr(point, "payload", {}) or {})
                    if str(payload.get("source", "")).strip() != "rag_document_guide":
                        continue
                    payload_user = str(payload.get("user_id", "") or "").strip()
                    if payload_user and not self._payload_user_matches(payload_user, requested_slug):
                        continue
                    rows.append(payload)
                if next_offset is None:
                    break
                offset = next_offset
            return rows
        except Exception:
            return []

    async def _document_chunk_catalog_payloads(self, *, user_id: str) -> list[dict[str, Any]]:
        clean_user = str(user_id or "").strip()
        requested_slug = self._slug_user_id(clean_user)
        names = await self._list_collection_names()
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for collection in names:
            if self._is_document_guide_collection_name(collection) or self._is_document_meta_collection_name(collection):
                continue
            is_document_collection = self._is_document_collection_name(collection)
            collection_user_slug = self._document_collection_user_slug(collection, "aria_docs")
            if collection_user_slug and collection_user_slug != requested_slug:
                continue
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=collection,
                        scroll_filter=None if is_document_collection else self._user_filter(clean_user),
                        limit=200,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points or []:
                        payload = dict(getattr(point, "payload", {}) or {})
                        if str(payload.get("source", "")).strip() == "rag_document_guide":
                            continue
                        if not self._is_document_payload(payload):
                            continue
                        payload_user = str(payload.get("user_id", "") or "").strip()
                        if payload_user:
                            if not self._payload_user_matches(payload_user, requested_slug):
                                continue
                        elif is_document_collection and collection_user_slug != requested_slug:
                            continue
                        document_id = self._document_payload_id(payload)
                        document_name = self._document_payload_name(payload)
                        if not document_id and not document_name:
                            document_id = f"{collection}:legacy-document"
                            document_name = collection
                        key = (collection, document_id or document_name)
                        row = grouped.setdefault(
                            key,
                            {
                                "source": "rag_document_chunk_catalog",
                                "user_id": requested_slug,
                                "document_id": document_id,
                                "document_name": document_name,
                                "target_collection": collection,
                                "mime_type": str(payload.get("mime_type", "") or "").strip(),
                                "source_type": str(payload.get("source_type", "") or "document").strip(),
                                "texts": [],
                                "keywords": set(),
                            },
                        )
                        if document_id and not str(row.get("document_id", "")).strip():
                            row["document_id"] = document_id
                        if document_name and not str(row.get("document_name", "")).strip():
                            row["document_name"] = document_name
                        text = self._clean_fact_text(str(payload.get("text", "") or "").strip())
                        if text and len(row["texts"]) < 6:
                            row["texts"].append(text[:360])
                        row["keywords"].update(self._tokenize_for_match(document_name))
                        row["keywords"].update(self._tokenize_for_match(text[:900]))
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue
        rows: list[dict[str, Any]] = []
        for row in grouped.values():
            snippets = [str(item).strip() for item in row.pop("texts", []) if str(item).strip()]
            keywords = sorted(str(item) for item in row.pop("keywords", set()) if str(item).strip())[:18]
            name = str(row.get("document_name", "") or "").strip()
            row["guide_summary"] = " ".join(snippets)[:900]
            row["guide_keywords"] = keywords
            row["text"] = "\n".join(
                part
                for part in (
                    f"Document: {name}" if name else "",
                    f"Collection: {row.get('target_collection', '')}",
                    f"Keywords: {', '.join(keywords[:10])}" if keywords else "",
                    f"Excerpt: {row['guide_summary']}" if row["guide_summary"] else "",
                )
                if part
            )
            rows.append(row)
        return rows

    async def _document_catalog_payloads(self, *, user_id: str) -> list[dict[str, Any]]:
        guides = await self._document_guide_payloads(user_id=user_id)
        chunks = await self._document_chunk_catalog_payloads(user_id=user_id)
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in chunks:
            key = (str(row.get("target_collection", "") or ""), str(row.get("document_id", "") or row.get("document_name", "") or ""))
            if key[0] and key[1]:
                by_key[key] = row
        for row in guides:
            key = (str(row.get("target_collection", "") or ""), str(row.get("document_id", "") or row.get("document_name", "") or ""))
            if key[0] and key[1]:
                by_key[key] = row
        return list(by_key.values())

    async def _recall_document_inventory(
        self,
        *,
        user_id: str,
        document_ids: list[str] | tuple[str, ...] | None = None,
        document_names: list[str] | tuple[str, ...] | None = None,
        target_collections: list[str] | tuple[str, ...] | None = None,
        limit: int = 12,
    ) -> SkillResult:
        requested_ids = {str(item or "").strip() for item in list(document_ids or []) if str(item or "").strip()}
        requested_names = {str(item or "").strip().lower() for item in list(document_names or []) if str(item or "").strip()}
        requested_collections = {str(item or "").strip() for item in list(target_collections or []) if str(item or "").strip()}
        rows = await self._document_catalog_payloads(user_id=user_id)
        selected_rows: list[dict[str, Any]] = []
        for row in rows:
            document_id = str(row.get("document_id", "") or "").strip()
            document_name = str(row.get("document_name", "") or "").strip()
            collection = str(row.get("target_collection", "") or "").strip()
            if requested_ids and document_id not in requested_ids:
                continue
            if not requested_ids and requested_names and document_name.lower() not in requested_names:
                continue
            if not requested_ids and not requested_names and requested_collections and collection not in requested_collections:
                continue
            selected_rows.append(row)

        selected_rows.sort(
            key=lambda row: (
                str(row.get("target_collection", "") or ""),
                str(row.get("document_name", "") or "").lower(),
                str(row.get("document_id", "") or ""),
            )
        )
        selected_rows = selected_rows[: max(1, int(limit or 12))]
        if not selected_rows:
            return SkillResult(
                skill_name=self.name,
                content="Keine passenden Dokumente gefunden.",
                success=True,
                metadata={
                    "document_inventory": True,
                    "sources": [],
                    "detail_lines": ["Routing Debug: document_inventory selected=0 reason=no_matching_document_metadata"],
                },
            )

        lines: list[str] = []
        sources: list[dict[str, Any]] = []
        for row in selected_rows:
            document_id = str(row.get("document_id", "") or "").strip()
            document_name = str(row.get("document_name", "") or "").strip()
            collection = str(row.get("target_collection", "") or "").strip()
            source_type = str(row.get("source_type", "") or "document").strip()
            parts = [f"Collection: {collection}" if collection else "", f"Document-ID: {document_id}" if document_id else ""]
            lines.append(f"- [Dokument: {document_name or document_id or collection}] {' · '.join(part for part in parts if part)}")
            sources.append(
                {
                    "type": "document",
                    "source_type": source_type,
                    "document_id": document_id,
                    "document_name": document_name,
                    "collection": collection,
                    "detail": f"Quelle: {document_name or document_id or collection} · {collection}".strip(),
                }
            )

        content = "\n".join(lines)
        truncated, saved = self.truncate(content)
        collections = sorted({str(row.get("target_collection", "") or "") for row in selected_rows if str(row.get("target_collection", "") or "")})
        metadata: dict[str, Any] = {
            "document_inventory": True,
            "sources": sources,
            "detail_lines": [
                "Routing Debug: document_inventory "
                f"selected={len(selected_rows)} collections={','.join(collections[:8]) or '-'} "
                f"requested_ids={len(requested_ids)}",
                *[str(entry.get("detail", "")).strip() for entry in sources if str(entry.get("detail", "")).strip()],
            ],
        }
        return SkillResult(skill_name=self.name, content=truncated, success=True, tokens_saved=saved, metadata=metadata)

    @staticmethod
    def _document_corpus_scan_terms(query: str) -> list[str]:
        tokens = MemorySkill._tokenize_for_match(query)
        rows: list[str] = []
        for token in tokens:
            clean = str(token or "").strip().lower()
            if len(clean) < 4:
                continue
            if clean not in rows:
                rows.append(clean)
        return rows[:12]

    @staticmethod
    def _document_scan_snippet(text: str, term: str, *, radius: int = 160) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        lower = raw.lower()
        index = lower.find(str(term or "").lower())
        if index < 0:
            return raw[: max(40, radius)]
        start = max(0, index - radius)
        end = min(len(raw), index + len(term) + radius)
        prefix = "..." if start else ""
        suffix = "..." if end < len(raw) else ""
        return f"{prefix}{raw[start:end].strip()}{suffix}"

    async def _recall_document_corpus_scan(
        self,
        *,
        query: str,
        user_id: str,
        target_collections: list[str] | tuple[str, ...] | None = None,
        limit: int = 8,
    ) -> SkillResult | None:
        terms = self._document_corpus_scan_terms(query)
        if not terms:
            return None
        requested_collections = {str(item or "").strip() for item in list(target_collections or []) if str(item or "").strip()}
        clean_user = str(user_id or "").strip()
        requested_slug = self._slug_user_id(clean_user)
        names = await self._list_collection_names()
        term_stats: dict[str, dict[str, Any]] = {
            term: {"chunks": 0, "documents": set(), "matches": []}
            for term in terms
        }
        documents: dict[tuple[str, str], dict[str, Any]] = {}
        scanned_chunks = 0
        for collection in names:
            collection_explicitly_requested = collection in requested_collections
            if requested_collections and collection not in requested_collections:
                continue
            if self._is_document_guide_collection_name(collection) or self._is_document_meta_collection_name(collection):
                continue
            is_document_collection = self._is_document_collection_name(collection)
            collection_user_slug = self._document_collection_user_slug(collection, "aria_docs")
            if collection_user_slug and collection_user_slug != requested_slug and not collection_explicitly_requested:
                continue
            try:
                exists = await self.qdrant.collection_exists(collection_name=collection)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=collection,
                        scroll_filter=None if is_document_collection else self._user_filter(clean_user),
                        limit=200,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points or []:
                        payload = dict(getattr(point, "payload", {}) or {})
                        if str(payload.get("source", "")).strip() == "rag_document_guide":
                            continue
                        if not self._is_document_payload(payload):
                            continue
                        payload_user = str(payload.get("user_id", "") or "").strip()
                        if payload_user:
                            if not self._payload_user_matches(payload_user, requested_slug) and not collection_explicitly_requested:
                                continue
                        elif is_document_collection and collection_user_slug != requested_slug and not collection_explicitly_requested:
                            continue
                        text = str(payload.get("text", "") or "").strip()
                        if not text:
                            continue
                        scanned_chunks += 1
                        document_id = self._document_payload_id(payload)
                        document_name = self._document_payload_name(payload)
                        if not document_id and not document_name:
                            document_id = f"{collection}:legacy-document"
                            document_name = collection
                        doc_key = (collection, document_id or document_name)
                        doc_row = documents.setdefault(
                            doc_key,
                            {
                                "collection": collection,
                                "document_id": document_id,
                                "document_name": document_name,
                                "chunks": 0,
                            },
                        )
                        doc_row["chunks"] = int(doc_row.get("chunks", 0) or 0) + 1
                        hay = text.lower()
                        for term in terms:
                            if term not in hay:
                                continue
                            stats = term_stats[term]
                            stats["chunks"] = int(stats.get("chunks", 0) or 0) + 1
                            stats["documents"].add(doc_key)
                            matches = stats["matches"]
                            if isinstance(matches, list) and len(matches) < max(1, int(limit or 1)):
                                matches.append(
                                    {
                                        "term": term,
                                        "collection": collection,
                                        "document_id": document_id,
                                        "document_name": document_name,
                                        "chunk_index": int(payload.get("chunk_index", 0) or 0),
                                        "chunk_total": int(payload.get("chunk_total", 0) or 0),
                                        "text": self._clean_fact_text(self._document_scan_snippet(text, term)),
                                    }
                                )
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue
        if not documents:
            return None

        total_matches = sum(int(stats.get("chunks", 0) or 0) for stats in term_stats.values())
        doc_count = len(documents)
        lines = [
            "[Dokument-Corpus-Scan]",
            _memory_skill_text(
                "document_corpus_scan_coverage",
                "Fully scanned: {documents} documents, {chunks} chunks.",
                documents=doc_count,
                chunks=scanned_chunks,
            ),
            "Suchbegriff-Abdeckung:",
        ]
        for term in terms:
            stats = term_stats[term]
            lines.append(
                f"- {term}: {int(stats.get('chunks', 0) or 0)} Treffer-Chunks in {len(stats.get('documents', set()) or set())} Dokumenten"
            )
        match_rows: list[dict[str, Any]] = []
        for term in terms:
            matches = term_stats[term].get("matches")
            if isinstance(matches, list):
                match_rows.extend(dict(match) for match in matches if isinstance(match, dict))
        if match_rows:
            lines.append(_memory_skill_text("document_corpus_scan_match_excerpts", "Match excerpts:"))
            for match in match_rows[: max(1, int(limit or 1))]:
                chunk = int(match.get("chunk_index", 0) or 0)
                total = int(match.get("chunk_total", 0) or 0)
                chunk_label = f" · Chunk {chunk}/{total}" if chunk and total else ""
                lines.append(
                    f"- [{match.get('term')}: {match.get('document_name') or match.get('document_id') or match.get('collection')}{chunk_label}] "
                    f"{match.get('text') or ''}"
                )
        else:
            lines.append(
                _memory_skill_text(
                    "document_corpus_scan_no_exact_matches",
                    "No exact matches for the search terms in the scanned document corpus.",
                )
            )
        content = "\n".join(lines)
        truncated, saved = self.truncate(content)
        sources = [
            {
                "type": "document",
                "source_type": "document_corpus_scan",
                "document_id": str(row.get("document_id", "") or ""),
                "document_name": str(row.get("document_name", "") or ""),
                "collection": str(row.get("collection", "") or ""),
                "chunks_scanned": int(row.get("chunks", 0) or 0),
                "detail": _memory_skill_text(
                    "document_corpus_scan_source_detail",
                    "Source: {source} · {collection} · fully scanned",
                    source=row.get("document_name") or row.get("document_id") or row.get("collection"),
                    collection=row.get("collection"),
                ),
            }
            for row in sorted(
                documents.values(),
                key=lambda item: (str(item.get("collection", "") or ""), str(item.get("document_name", "") or "").lower()),
            )
        ]
        metadata: dict[str, Any] = {
            "document_corpus_scan": {
                "exhaustive": True,
                "terms": terms,
                "documents_scanned": doc_count,
                "chunks_scanned": scanned_chunks,
                "match_chunks": total_matches,
            },
            "sources": sources,
            "detail_lines": [
                "Routing Debug: document_corpus_scan "
                f"exhaustive=true documents={doc_count} chunks={scanned_chunks} "
                f"terms={','.join(terms) or '-'} matches={total_matches}",
                *[str(entry.get("detail", "")).strip() for entry in sources if str(entry.get("detail", "")).strip()],
            ],
        }
        return SkillResult(skill_name=self.name, content=truncated, success=True, tokens_saved=saved, metadata=metadata)

    @staticmethod
    def _document_rows_match_query_terms(query: str, rows: list[dict[str, Any]]) -> bool:
        terms = MemorySkill._document_corpus_scan_terms(query)
        if not terms:
            return bool(rows)
        haystack = "\n".join(str(row.get("text", "") or "") for row in rows).lower()
        return any(term in haystack for term in terms)

    async def rebuild_document_meta_catalog(self, *, user_id: str) -> dict[str, Any]:
        guides = await self._document_catalog_payloads(user_id=user_id)

        class _SkillEmbeddingAdapter:
            def __init__(self, skill: MemorySkill) -> None:
                self.skill = skill

            async def embed(self, inputs: list[str], **kwargs: Any) -> Any:
                usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                vectors: list[list[float]] = []
                operation = str(kwargs.get("operation", "doc_meta_catalog") or "doc_meta_catalog")
                source = str(kwargs.get("source", "doc_meta_catalog") or "doc_meta_catalog")
                adapter_user_id = str(kwargs.get("user_id", "") or "")
                for text in inputs:
                    vector, usage = await self.skill._embed(
                        str(text or ""),
                        source=source,
                        operation=operation,
                        user_id=adapter_user_id,
                    )
                    vectors.append(vector)
                    for key in usage_total:
                        usage_total[key] += int(usage.get(key, 0) or 0)
                return type(
                    "EmbeddingResponse",
                    (),
                    {
                        "vectors": vectors,
                        "usage": usage_total,
                        "model": self.skill._resolve_embedding_model(),
                    },
                )()

        store = DocumentMetaCatalogStore(
            qdrant=self.qdrant,
            embedding_client=_SkillEmbeddingAdapter(self),
            collection_name=document_meta_collection_for_user(user_id),
        )
        return await store.rebuild_from_guides(user_id=user_id, guides=guides)

    async def rebuild_document_meta_catalogs_for_known_users(self) -> dict[str, Any]:
        users = await self._discover_users_from_collections()
        rebuilt: list[dict[str, Any]] = []
        for user_id in users:
            guides = await self._document_catalog_payloads(user_id=user_id)
            if not guides:
                continue
            try:
                result = await self.rebuild_document_meta_catalog(user_id=user_id)
            except Exception as exc:
                result = {"user_id": user_id, "status": "error", "error": str(exc)}
            else:
                result = {"user_id": user_id, **dict(result)}
            rebuilt.append(result)
        return {
            "users": len(users),
            "rebuilt_users": len(rebuilt),
            "documents": sum(int(row.get("documents", 0) or 0) for row in rebuilt),
            "results": rebuilt,
        }

    @staticmethod
    def _format_recall_source_detail(row: dict[str, Any]) -> str:
        return format_recall_source_detail(row)

    @staticmethod
    def _recall_source_priority(entry: dict[str, Any]) -> tuple[int, int]:
        return recall_source_priority(entry)

    def _build_recall_source_entries(
        self,
        rows: list[dict[str, Any]],
        *,
        max_items: int = 4,
    ) -> list[dict[str, Any]]:
        return build_recall_source_entries(rows, max_items=max_items)

    async def _query_weighted_hits(
        self,
        vector: list[float],
        user_id: str,
        target: dict[str, Any],
    ) -> list[dict[str, Any]]:
        must_conditions = [FieldCondition(key="user_id", match=MatchValue(value=str(user_id or "").strip() or "web"))]
        document_id = str(target.get("document_id", "")).strip()
        document_name = str(target.get("document_name", "")).strip()
        if document_id:
            must_conditions.append(FieldCondition(key="document_id", match=MatchValue(value=document_id)))
        elif document_name:
            must_conditions.append(FieldCondition(key="document_name", match=MatchValue(value=document_name)))
        try:
            exists = await self.qdrant.collection_exists(collection_name=target["collection"])
            if not exists:
                return []
            query_result = await self.qdrant.query_points(
                collection_name=target["collection"],
                query=vector,
                query_filter=Filter(must=must_conditions),
                limit=max(1, int(target["top_k"])),
            )
        except Exception:
            return []

        weighted: list[dict[str, Any]] = []
        for hit in self._extract_hits(query_result):
            payload = hit.payload or {}
            if not self._payload_embedding_compatible(payload):
                continue
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            score = self._combined_score(getattr(hit, "score", 0.0), target["type"], payload)
            if str(target.get("type", "")).strip().lower() == "document":
                score += float(target.get("guide_score", 0.0) or 0.0) * 0.15
            weighted.append(
                {
                    "score": score,
                    "label": target["label"],
                    "type": target["type"],
                    "text": self._clean_fact_text(text),
                    "collection": str(target.get("collection", "")).strip(),
                    "document_id": str(payload.get("document_id", "")).strip(),
                    "document_name": str(payload.get("document_name", "")).strip(),
                    "chunk_index": int(payload.get("chunk_index", 0) or 0),
                    "chunk_total": int(payload.get("chunk_total", 0) or 0),
                    "source": str(payload.get("source", "")).strip() or "n/a",
                    "rollup_level": str(payload.get("rollup_level", "")).strip(),
                    "rollup_bucket": str(payload.get("rollup_bucket", "")).strip(),
                    "rollup_period_start": str(payload.get("rollup_period_start", "")).strip(),
                    "rollup_period_end": str(payload.get("rollup_period_end", "")).strip(),
                    "rollup_source_kind": str(payload.get("rollup_source_kind", "")).strip(),
                    "rollup_source_count": int(payload.get("rollup_source_count", 0) or 0),
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
            if not self._payload_embedding_compatible(payload):
                continue
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
                    "timestamp": (
                        str(payload.get("updated_at", "")).strip()
                        or str(payload.get("created_at", "")).strip()
                        or str(payload.get("timestamp", "")).strip()
                    ),
                    "source": str(payload.get("source", "")).strip() or "n/a",
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
        detail_line = (
            "Routing Debug: memory_keyword_fallback "
            f"collections={len(collection_names)} top_k={int(top_k or 0)}"
        )

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
            return SkillResult(
                skill_name=self.name,
                content="Keine passende Erinnerung gefunden.",
                success=True,
                metadata={"detail_lines": [f"{detail_line} matches=0 reason=no_points"]},
            )

        query_tokens = self._tokenize_for_match(query)
        is_network_query = self._is_network_query(query_tokens)
        network_terms = ("netzwerk", "lan", "ip", "dns", "firewall", "pihole", "nas", "subnet", "gateway")
        scored: list[tuple[int, str]] = []
        for point in all_points:
            payload = point.payload or {}
            if not self._payload_embedding_compatible(payload):
                continue
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
            return SkillResult(
                skill_name=self.name,
                content="Keine passende Erinnerung gefunden.",
                success=True,
                metadata={"detail_lines": [f"{detail_line} matches=0 reason=no_keyword_match"]},
            )

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
            return SkillResult(
                skill_name=self.name,
                content="Keine passende Erinnerung gefunden.",
                success=True,
                metadata={"detail_lines": [f"{detail_line} matches=0 reason=no_selected_lines"]},
            )

        content = "[Memory: hybride Suche]\n" + "\n".join(selected_lines)
        truncated, saved = self.truncate(content)
        return SkillResult(
            skill_name=self.name,
            content=truncated,
            success=True,
            tokens_saved=saved,
            metadata={"detail_lines": [f"{detail_line} matches={len(selected_lines)} reason=keyword_match"]},
        )

    async def _embed(
        self,
        text: str,
        *,
        source: str = "",
        operation: str = "",
        user_id: str = "",
    ) -> tuple[list[float], dict[str, int]]:
        response = await self.embedding_client.embed(
            [text],
            source=source,
            operation=operation,
            user_id=user_id,
        )
        embedding = response.vectors[0] if response.vectors else []
        return [float(v) for v in embedding], dict(response.usage)

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

        vector, usage = await self._embed(
            text,
            source=source or "memory_store",
            operation="store_memory",
            user_id=user_id,
        )
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
                "embedding_model": self._resolve_embedding_model(),
                "embedding_fingerprint": self._active_embedding_fingerprint(),
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

    async def store_document(
        self,
        *,
        user_id: str,
        document: PreparedDocument,
        base_collection: str | None = None,
        source: str = "rag_upload",
    ) -> SkillResult:
        return await DocumentMemoryService(self).store_document(
            user_id=user_id,
            document=document,
            base_collection=base_collection,
            source=source,
        )

    async def _recall(
        self,
        query: str,
        user_id: str,
        top_k: int,
        base_collection: str | None = None,
        target_collections: list[str] | tuple[str, ...] | None = None,
        include_documents: bool = True,
        docs_only: bool = False,
        document_inventory: bool = False,
        document_corpus_scan: bool = False,
        document_ids: list[str] | tuple[str, ...] | None = None,
        document_names: list[str] | tuple[str, ...] | None = None,
        document_target_collections: list[str] | tuple[str, ...] | None = None,
    ) -> SkillResult:
        allowed_targets = {
            str(item or "").strip()
            for item in list(target_collections or [])
            if str(item or "").strip()
        }
        if document_inventory:
            inventory_targets = list(document_target_collections or []) or list(allowed_targets)
            return await self._recall_document_inventory(
                user_id=user_id,
                document_ids=document_ids,
                document_names=document_names,
                target_collections=inventory_targets,
                limit=max(top_k, 12),
            )
        if document_corpus_scan and docs_only and include_documents:
            corpus_scan = await self._recall_document_corpus_scan(
                query=query,
                user_id=user_id,
                target_collections=allowed_targets,
                limit=max(top_k, 8),
            )
            if corpus_scan is not None:
                return corpus_scan
        try:
            vector, usage = await self._embed(
                query,
                source="memory_recall",
                operation="recall_query",
                user_id=user_id,
            )
            recall_targets = []
            if not docs_only:
                recall_targets = await self._build_recall_targets(user_id=user_id, base_collection=base_collection)
                if allowed_targets:
                    recall_targets = [
                        target
                        for target in recall_targets
                        if str(target.get("collection", "") or "").strip() in allowed_targets
                    ]
            if include_documents:
                guide_hits = await self._query_document_guides(
                    vector=vector,
                    query=query,
                    user_id=user_id,
                    max_hits=min(max(2, top_k), 4),
                )
                document_targets = self._build_document_targets_from_guides(guide_hits)
                if allowed_targets:
                    document_targets = [
                        target
                        for target in document_targets
                        if str(target.get("collection", "") or "").strip() in allowed_targets
                    ]
                recall_targets = recall_targets + document_targets
            target_collections = [str(t["collection"]) for t in recall_targets]
            if document_corpus_scan and docs_only and include_documents:
                corpus_scan = await self._recall_document_corpus_scan(
                    query=query,
                    user_id=user_id,
                    target_collections=target_collections or allowed_targets,
                    limit=max(top_k, 8),
                )
                if corpus_scan is not None:
                    corpus_scan.metadata["embedding_usage"] = usage
                    corpus_scan.metadata["embedding_model"] = self._resolve_embedding_model()
                    return corpus_scan
            if not recall_targets:
                if docs_only and include_documents:
                    corpus_scan = await self._recall_document_corpus_scan(
                        query=query,
                        user_id=user_id,
                        target_collections=allowed_targets,
                        limit=max(top_k, 8),
                    )
                    if corpus_scan is not None:
                        corpus_scan.metadata["embedding_usage"] = usage
                        corpus_scan.metadata["embedding_model"] = self._resolve_embedding_model()
                        return corpus_scan
                metadata = {
                    "embedding_usage": usage,
                    "embedding_model": self._resolve_embedding_model(),
                    "detail_lines": ["Routing Debug: memory_recall_targets selected=0 reason=arbiter_restricted_context"],
                    "sources": [],
                }
                return SkillResult(
                    skill_name=self.name,
                    content="Keine passende Erinnerung gefunden.",
                    success=True,
                    metadata=metadata,
                )
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
            if docs_only and include_documents:
                corpus_scan = await self._recall_document_corpus_scan(
                    query=query,
                    user_id=user_id,
                    target_collections=allowed_targets,
                    limit=max(top_k, 8),
                )
                if corpus_scan is not None:
                    return corpus_scan
            return await self._recall_keyword_fallback(
                query=query,
                user_id=user_id,
                top_k=top_k,
                base_collection=base_collection,
                collections=(await self._candidate_collections(base_collection or self.memory.collection)),
            )

        if not weighted_hits:
            if docs_only and include_documents:
                corpus_scan = await self._recall_document_corpus_scan(
                    query=query,
                    user_id=user_id,
                    target_collections=target_collections or allowed_targets,
                    limit=max(top_k, 8),
                )
                if corpus_scan is not None:
                    corpus_scan.metadata["embedding_usage"] = usage
                    corpus_scan.metadata["embedding_model"] = self._resolve_embedding_model()
                    return corpus_scan
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
        selected_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in weighted_hits:
            cleaned = str(item["text"]).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                selected_rows.append(item)
                if str(item.get("type", "")).strip().lower() == "document" and str(item.get("document_name", "")).strip():
                    lines.append(f"- [{item['label']}: {item['document_name']}] {cleaned}")
                else:
                    lines.append(f"- [{item['label']}] {cleaned}")
            if len(lines) >= output_count:
                break

        if docs_only and include_documents and not self._document_rows_match_query_terms(query, selected_rows):
            corpus_scan = await self._recall_document_corpus_scan(
                query=query,
                user_id=user_id,
                target_collections=target_collections or allowed_targets,
                limit=max(top_k, 8),
            )
            if corpus_scan is not None:
                corpus_scan.metadata["embedding_usage"] = usage
                corpus_scan.metadata["embedding_model"] = self._resolve_embedding_model()
                return corpus_scan

        content = "\n".join(lines) if lines else "Keine passende Erinnerung gefunden."
        truncated, saved = self.truncate(content)
        source_entries = self._build_recall_source_entries(selected_rows)
        metadata: dict[str, Any] = {
            "embedding_usage": usage,
            "embedding_model": self._resolve_embedding_model(),
        }
        if source_entries:
            metadata["sources"] = source_entries
            metadata["detail_lines"] = [
                str(entry.get("detail", "")).strip()
                for entry in source_entries
                if str(entry.get("detail", "")).strip()
            ]
        detail_lines = list(metadata.get("detail_lines") or [])
        detail_lines.insert(
            0,
            "Routing Debug: memory_recall_targets "
            f"selected={len(target_collections)} collections={','.join(target_collections[:8]) or '-'} "
            f"include_documents={str(include_documents).lower()} docs_only={str(docs_only).lower()}",
        )
        metadata["detail_lines"] = detail_lines
        return SkillResult(
            skill_name=self.name,
            content=truncated,
            success=True,
            tokens_saved=saved,
            metadata=metadata,
        )

    @staticmethod
    def _coerce_string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list | tuple | set):
            return [str(item or "").strip() for item in value if str(item or "").strip()]
        return []

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
            vector, usage = await self._embed(
                query,
                source="memory_forget",
                operation="forget_preview_query",
                user_id=user_id,
            )
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
                content=_memory_skill_text("delete_preview_expired", "Nothing deleted. Please start the preview again."),
                success=True,
            )
        if str(user_id or "").strip():
            await self.cleanup_empty_collections_for_user(user_id)
        return SkillResult(
            skill_name=self.name,
            content=_memory_skill_text("delete_confirmed", "Delete confirmed. {deleted} entries removed.", deleted=deleted),
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
                            "type": self._display_memory_type(collection, payload),
                            "label": self._type_label(self._display_memory_type(collection, payload)),
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
        return await MemoryAdminQueryService(self).list_memories(
            user_id,
            type_filter=type_filter,
            limit=limit,
        )

    async def list_memories_global(
        self,
        user_id: str,
        type_filter: str = "all",
        limit: int = 200,
        collection_filter: str = "",
    ) -> list[dict[str, Any]]:
        return await MemoryAdminQueryService(self).list_memories_global(
            user_id,
            type_filter=type_filter,
            limit=limit,
            collection_filter=collection_filter,
        )

    async def list_memory_graph_points(
        self,
        user_id: str,
        limit: int = 96,
        collection_limit: int = 16,
    ) -> list[dict[str, Any]]:
        return await MemoryAdminQueryService(self).list_memory_graph_points(
            user_id,
            limit=limit,
            collection_limit=collection_limit,
        )

    async def get_user_collection_stats(self, user_id: str) -> list[dict[str, Any]]:
        return await MemoryAdminQueryService(self).get_user_collection_stats(user_id)

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
        return await MemoryAdminQueryService(self).search_memories(
            user_id,
            query,
            type_filter=type_filter,
            top_k=top_k,
        )

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

    async def delete_document(
        self,
        user_id: str,
        collection: str,
        *,
        document_id: str = "",
        document_name: str = "",
    ) -> int:
        return await DocumentMemoryService(self).delete_document(
            user_id,
            collection,
            document_id=document_id,
            document_name=document_name,
        )

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

    async def update_memory_point_payload(
        self,
        user_id: str,
        collection: str,
        point_id: str,
        payload_updates: dict[str, Any],
    ) -> bool:
        clean_collection = str(collection).strip()
        clean_id = str(point_id).strip()
        if not clean_collection or not clean_id or not isinstance(payload_updates, dict):
            return False
        safe_updates: dict[str, Any] = {}
        for key, value in payload_updates.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_updates[clean_key] = value
            else:
                safe_updates[clean_key] = str(value)
        if not safe_updates:
            return False
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
            safe_updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self.qdrant.set_payload(
                collection_name=clean_collection,
                payload=safe_updates,
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
        return await SessionCompressionService(self).compress_old_sessions(
            user_id,
            compress_after_days=compress_after_days,
            monthly_after_days=monthly_after_days,
        )

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
            for prefix in ("aria_docs", self.DOCUMENT_GUIDE_PREFIX, DOC_META_PREFIX):
                collection_user = self._document_collection_user_slug(name, prefix)
                if collection_user:
                    users.add(collection_user)
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
            if not (
                self._is_document_collection_name(name)
                or self._is_document_guide_collection_name(name)
                or self._is_document_meta_collection_name(name)
            ):
                continue
            try:
                exists = await self.qdrant.collection_exists(collection_name=name)
                if not exists:
                    continue
                offset = None
                while True:
                    points, next_offset = await self.qdrant.scroll(
                        collection_name=name,
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points or []:
                        payload = dict(getattr(point, "payload", {}) or {})
                        raw_user_id = str(payload.get("user_id", "") or "").strip()
                        if raw_user_id:
                            users.add(self._slug_user_id(raw_user_id))
                    if next_offset is None:
                        break
                    offset = next_offset
            except Exception:
                continue
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
                raw_targets = params.get("target_collections")
                if isinstance(raw_targets, str):
                    target_collections = [item.strip() for item in raw_targets.split(",") if item.strip()]
                elif isinstance(raw_targets, list | tuple | set):
                    target_collections = [str(item or "").strip() for item in raw_targets if str(item or "").strip()]
                else:
                    target_collections = None
                return await self._recall(
                    query=query,
                    user_id=user_id,
                    top_k=top_k,
                    base_collection=collection,
                    target_collections=target_collections,
                    include_documents=bool(params.get("include_documents", True)),
                    docs_only=bool(params.get("docs_only", False)),
                    document_inventory=bool(params.get("document_inventory", False)),
                    document_corpus_scan=bool(params.get("document_corpus_scan", False)),
                    document_ids=self._coerce_string_list(params.get("document_ids")),
                    document_names=self._coerce_string_list(params.get("document_names")),
                    document_target_collections=self._coerce_string_list(params.get("document_target_collections")),
                )

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
                        _memory_skill_text(
                            "compression_completed",
                            "Compression completed: week={week}, month={month}, removed collections={collections}",
                            week=stats["compressed_week"],
                            month=stats["compressed_month"],
                            collections=stats["collections_removed"],
                        )
                    ),
                    success=True,
                    metadata={"compression_stats": stats},
                )

            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=_memory_skill_text("unknown_action", "Unknown action"),
            )
        except Exception as exc:  # noqa: BLE001
            category = self._friendly_memory_error(exc)
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=f"{category}: {exc}",
            )
