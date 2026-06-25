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
from aria.core.inventory_index import create_inventory_qdrant_client, inventory_index_instance_key
from aria.core.routing_index import _dedupe, _document_source_hash, _read_list, _read_text, _slug


META_CATALOG_VERSION = 1

SECRET_FIELD_NAMES = {
    "api_key",
    "auth_token",
    "ical_url",
    "key_path",
    "password",
    "private_key",
    "secret",
    "token",
    "url",
    "webhook_url",
}


def meta_catalog_collection_name(settings: Any, *, backup: bool = False) -> str:
    instance = _slug(inventory_index_instance_key(settings), fallback="")
    base = f"aria_meta_catalog_{instance}" if instance else "aria_meta_catalog"
    return f"{base}__backup" if backup else base


def _normalize_ws(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_label(value: Any) -> str:
    clean = _normalize_ws(value)
    lower = clean.lower()
    if not clean or "://" in lower or "@" in clean:
        return ""
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", clean):
        return ""
    if re.search(r"\b[a-z0-9-]+\.[a-z]{2,}\b", lower):
        return ""
    return clean


def _safe_text_field(value: Any, *, limit: int = 512) -> str:
    clean = _normalize_ws(value)
    if not clean:
        return ""
    clean = re.sub(r"https?://\S+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b\S+@\S+\b", "", clean)
    clean = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "", clean)
    clean = re.sub(r"\b[a-z0-9-]+\.[a-z]{2,}(?:\.\w+)?\b", "", clean, flags=re.IGNORECASE)
    return _normalize_ws(clean)[: max(1, int(limit or 1))]


def _safe_aliases(ref: str, row: Any) -> list[str]:
    values = [ref, *_read_list(row, "aliases")]
    return _dedupe(label for value in values if (label := _safe_label(value)))


def _risk_hint_for_connection(kind: str, supported_actions: list[str]) -> str:
    mutating = {"write", "send", "execute", "run command", "befehl", "message", "notify"}
    text = " ".join(supported_actions).lower()
    if kind in {"ssh", "sftp", "smb", "webhook", "discord", "email", "mqtt", "http_api"} and any(token in text for token in mutating):
        return "medium"
    return "low"


def _confirmation_policy_for_connection(kind: str, supported_actions: list[str]) -> str:
    text = " ".join(supported_actions).lower()
    if kind == "ssh":
        return "confirmation_required_for_commands_and_multi_target_checks"
    if any(token in text for token in ("write", "send", "execute", "run command", "notify", "message")):
        return "confirmation_required_for_side_effects"
    return "confirmation_not_required_for_read_only_inventory"


def _connection_can_load(kind: str) -> list[str]:
    if kind == "ssh":
        return ["safe profile metadata", "target role", "allowed command policy", "last known connection status", "preflight target dossier"]
    if kind in {"sftp", "smb"}:
        return ["safe profile metadata", "root path scope", "file inventory context", "preflight target dossier"]
    if kind in {"rss", "website"}:
        return ["safe source metadata", "group and tags", "observed-source inventory", "latest readable source context"]
    if kind in {"http_api", "webhook"}:
        return ["safe profile metadata", "endpoint purpose", "health or request contract", "preflight target dossier"]
    if kind in {"email", "imap"}:
        return ["safe mailbox metadata", "message scope", "preflight target dossier"]
    return ["safe profile metadata", "inventory context", "preflight target dossier"]


def _connection_knows(kind: str, title: str, description: str, tags: list[str]) -> list[str]:
    base = [connection_kind_label(kind), normalize_connection_kind(kind)]
    if kind == "ssh":
        base.extend(["server", "linux host", "health", "updates", "disk", "services", "uptime"])
    elif kind in {"rss", "website"}:
        base.extend(["observed source", "topics", "news", "source inventory"])
    elif kind in {"sftp", "smb"}:
        base.extend(["remote files", "directories", "file transfer"])
    elif kind in {"http_api", "webhook"}:
        base.extend(["api", "endpoint", "health"])
    elif kind in {"email", "imap"}:
        base.extend(["mail", "mailbox", "messages"])
    base.extend([title, description, *tags])
    return _dedupe(_normalize_ws(item) for item in base if _normalize_ws(item))[:24]


@dataclass(slots=True)
class MetaCatalogDocument:
    catalog_id: str
    entity_type: str
    surface_id: str
    kind: str
    ref: str
    title: str = ""
    description: str = ""
    group_name: str = ""
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    knows: list[str] = field(default_factory=list)
    can_load: list[str] = field(default_factory=list)
    can_do: list[str] = field(default_factory=list)
    action_candidates: list[str] = field(default_factory=list)
    loader_contract: str = ""
    executor_contract: str = ""
    risk_hint: str = "low"
    confirmation_policy: str = ""
    data_persistence: str = "user_data_preserved"
    text: str = ""
    source_hash: str = ""
    updated_at: str = ""

    @property
    def id(self) -> str:
        return str(uuid5(NAMESPACE_URL, f"aria-meta-catalog|{self.catalog_id}"))

    def render_text(self) -> str:
        rows = [
            f"Catalog type: {self.entity_type}",
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
        if self.knows:
            rows.append("Knows: " + ", ".join(self.knows))
        if self.can_load:
            rows.append("Can load: " + ", ".join(self.can_load))
        if self.can_do:
            rows.append("Can do: " + ", ".join(self.can_do))
        if self.action_candidates:
            rows.append("Action candidates: " + ", ".join(self.action_candidates))
        if self.loader_contract:
            rows.append(f"Loader contract: {self.loader_contract}")
        if self.executor_contract:
            rows.append(f"Executor contract: {self.executor_contract}")
        rows.append(f"Risk: {self.risk_hint}")
        if self.confirmation_policy:
            rows.append(f"Confirmation: {self.confirmation_policy}")
        return "\n".join(rows)

    def payload(self) -> dict[str, Any]:
        return {
            "meta_catalog_version": META_CATALOG_VERSION,
            "catalog_id": self.catalog_id,
            "entity_type": self.entity_type,
            "surface_id": self.surface_id,
            "kind": self.kind,
            "ref": self.ref,
            "title": self.title,
            "description": self.description,
            "group_name": self.group_name,
            "aliases": list(self.aliases),
            "tags": list(self.tags),
            "knows": list(self.knows),
            "can_load": list(self.can_load),
            "can_do": list(self.can_do),
            "action_candidates": list(self.action_candidates),
            "loader_contract": self.loader_contract,
            "executor_contract": self.executor_contract,
            "risk_hint": self.risk_hint,
            "confirmation_policy": self.confirmation_policy,
            "data_persistence": self.data_persistence,
            "text": self.text or self.render_text(),
            "source_hash": self.source_hash,
            "updated_at": self.updated_at,
        }


def _surface_documents(settings: Any) -> list[MetaCatalogDocument]:
    now = datetime.now(timezone.utc).isoformat()
    documents: list[MetaCatalogDocument] = []
    for surface in build_builtin_surface_registry(settings).all():
        payload = surface.as_meta_context()
        source_payload = {"entity_type": "surface", **payload}
        document = MetaCatalogDocument(
            catalog_id=f"surface|{surface.surface_id}",
            entity_type="surface",
            surface_id=surface.surface_id,
            kind="surface",
            ref=surface.surface_id,
            title=surface.display_name,
            description=surface.what_it_knows,
            aliases=[surface.surface_id, surface.display_name],
            tags=list(surface.supported_modes),
            knows=[surface.what_it_knows],
            can_load=[surface.what_it_can_load],
            can_do=[surface.what_it_can_do] if surface.what_it_can_do else list(surface.supported_modes),
            loader_contract=surface.loader_contract,
            executor_contract=surface.executor_contract,
            risk_hint=surface.risk_hint,
            confirmation_policy="executor_policy" if surface.executor_contract else "none_for_context_loading",
            data_persistence=surface.data_persistence,
            source_hash=_document_source_hash(source_payload),
            updated_at=now,
        )
        document.text = document.render_text()
        documents.append(document)
    return documents


def _memory_collection_prefix(settings: Any, name: str, fallback: str) -> str:
    collections = getattr(getattr(settings, "memory", None), "collections", None)
    row = getattr(collections, name, None)
    return str(getattr(row, "prefix", "") or fallback).strip() or fallback


def _local_context_documents(settings: Any) -> list[MetaCatalogDocument]:
    now = datetime.now(timezone.utc).isoformat()
    facts_prefix = _memory_collection_prefix(settings, "facts", "aria_facts")
    preferences_prefix = _memory_collection_prefix(settings, "preferences", "aria_preferences")
    knowledge_prefix = _memory_collection_prefix(settings, "knowledge", "aria_knowledge")
    sessions_prefix = _memory_collection_prefix(settings, "sessions", "aria_sessions")
    rows = [
        {
            "catalog_id": "local|memory|facts",
            "surface_id": "memory",
            "kind": "memory_family",
            "ref": "facts",
            "title": "Memory Facts",
            "description": "Durable user facts and remembered factual project context.",
            "tags": ["facts", "memory", facts_prefix],
            "knows": ["facts", "remembered facts", "durable user memory"],
            "can_load": ["source-bound fact memory snippets"],
        },
        {
            "catalog_id": "local|memory|preferences",
            "surface_id": "memory",
            "kind": "memory_family",
            "ref": "preferences",
            "title": "Memory Preferences",
            "description": "User preferences, durable UI rules, response preferences, and behavioral instructions.",
            "tags": ["preferences", "rules", preferences_prefix],
            "knows": ["preferences", "durable rules", "user instructions"],
            "can_load": ["source-bound preference memory snippets"],
        },
        {
            "catalog_id": "local|memory|knowledge",
            "surface_id": "memory",
            "kind": "memory_family",
            "ref": "knowledge",
            "title": "Memory Knowledge",
            "description": "Condensed knowledge, project context, summaries, and general remembered context.",
            "tags": ["knowledge", "context", knowledge_prefix],
            "knows": ["knowledge", "project context", "summaries"],
            "can_load": ["source-bound knowledge memory snippets"],
        },
        {
            "catalog_id": "local|memory|context_mem",
            "surface_id": "memory",
            "kind": "memory_family",
            "ref": "context_mem",
            "title": "Context Memory",
            "description": "Compressed contextual memory and long-running project context.",
            "tags": ["context memory", "compression", "aria_context-mem"],
            "knows": ["compressed context", "long-running context", "project summaries"],
            "can_load": ["source-bound compressed context snippets"],
        },
        {
            "catalog_id": "local|memory|sessions",
            "surface_id": "memory",
            "kind": "memory_family",
            "ref": "sessions",
            "title": "Recent Sessions",
            "description": "Recent user sessions and chat history summaries.",
            "tags": ["sessions", "history", sessions_prefix],
            "knows": ["recent sessions", "chat history", "conversation context"],
            "can_load": ["bounded recent session snippets"],
        },
        {
            "catalog_id": "local|learning|reflections",
            "surface_id": "memory",
            "kind": "learning_family",
            "ref": "reflections",
            "title": "Learning Reflections",
            "description": "Learned reflections, corrections, durable feedback, and improvement notes.",
            "tags": ["learning", "reflections", "feedback", "aria_learning"],
            "knows": ["learning reflections", "feedback", "corrections"],
            "can_load": ["source-bound learning reflection snippets"],
        },
        {
            "catalog_id": "local|learning|events",
            "surface_id": "memory",
            "kind": "learning_family",
            "ref": "events",
            "title": "Learning Events",
            "description": "Review-only learning events captured from feedback and runtime outcomes.",
            "tags": ["learning events", "outcomes", "aria_learning_events"],
            "knows": ["learning events", "runtime outcomes", "feedback events"],
            "can_load": ["bounded learning event snippets"],
        },
        {
            "catalog_id": "local|learning|candidates",
            "surface_id": "memory",
            "kind": "learning_family",
            "ref": "candidates",
            "title": "Learning Candidates",
            "description": "Review-only candidates for procedures, recipes, skills, tests, and improvements.",
            "tags": ["learning candidates", "procedure candidates", "recipe candidates", "skill candidates"],
            "knows": ["learning candidates", "procedures", "recipes", "skill candidates"],
            "can_load": ["bounded learning candidate snippets"],
        },
        {
            "catalog_id": "local|learning|evals",
            "surface_id": "memory",
            "kind": "learning_family",
            "ref": "evals",
            "title": "Learning Evals",
            "description": "Validation and evaluation artifacts for learning candidates.",
            "tags": ["learning evals", "validation", "review"],
            "knows": ["learning evaluations", "validation state", "review blockers"],
            "can_load": ["bounded learning eval snippets"],
        },
        {
            "catalog_id": "local|notes|user_notes",
            "surface_id": "notes",
            "kind": "notes_family",
            "ref": "user_notes",
            "title": "User Notes",
            "description": "User-maintained notes, project notes, folders, tags, and note excerpts.",
            "tags": ["notes", "notizen", "project notes"],
            "knows": ["notes", "note folders", "note excerpts", "project notes"],
            "can_load": ["source-bound note excerpts", "note inventory"],
            "can_do": ["search notes", "open notes", "create note"],
            "action_candidates": ["notes_search", "notes_action"],
            "risk_hint": "low",
            "confirmation_policy": "confirmation_required_for_note_mutations",
        },
        {
            "catalog_id": "local|docs|documents",
            "surface_id": "docs",
            "kind": "docs_family",
            "ref": "documents",
            "title": "Imported Documents",
            "description": "Imported PDFs, manuals, project documents, document chunks, and document summaries.",
            "tags": ["documents", "docs", "pdf", "manuals"],
            "knows": ["imported documents", "manuals", "PDF chunks", "document summaries"],
            "can_load": ["source-bound document chunks", "document inventory"],
        },
    ]
    documents: list[MetaCatalogDocument] = []
    for row in rows:
        payload = {"entity_type": "local_context", **row}
        document = MetaCatalogDocument(
            catalog_id=str(row["catalog_id"]),
            entity_type="local_context",
            surface_id=str(row["surface_id"]),
            kind=str(row["kind"]),
            ref=str(row["ref"]),
            title=str(row["title"]),
            description=str(row["description"]),
            tags=_dedupe(row.get("tags", [])),
            knows=_dedupe(row.get("knows", [])),
            can_load=_dedupe(row.get("can_load", [])),
            can_do=_dedupe(row.get("can_do", [])),
            action_candidates=_dedupe(row.get("action_candidates", [])),
            loader_contract="load_only_the_selected_local_context_family_for_the_structured_context_request",
            executor_contract="local_mutations_require_explicit_action_policy_and_review" if row.get("action_candidates") else "",
            risk_hint=str(row.get("risk_hint", "low") or "low"),
            confirmation_policy=str(row.get("confirmation_policy", "none_for_context_loading") or "none_for_context_loading"),
            source_hash=_document_source_hash(payload),
            updated_at=now,
        )
        document.text = document.render_text()
        documents.append(document)
    return documents


def _connection_action_candidates(kind: str) -> list[str]:
    try:
        spec = connection_routing_spec(kind)
    except Exception:
        return []
    rows: list[str] = []
    for values in dict(spec.preferred_action_candidates or {}).values():
        rows.extend(str(value or "").strip() for value in values)
    return _dedupe(rows)


def build_meta_catalog_documents(settings: Any) -> list[MetaCatalogDocument]:
    documents = _surface_documents(settings)
    documents.extend(_local_context_documents(settings))
    connections = getattr(settings, "connections", None)
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
            title = _safe_text_field(_read_text(row, "title"), limit=160)
            description = _safe_text_field(_read_text(row, "description"), limit=512)
            group_name = _safe_text_field(_read_text(row, "group_name"), limit=120)
            aliases = _safe_aliases(clean_ref, row)
            tags = _dedupe(label for tag in _read_list(row, "tags") if (label := _safe_label(tag) or _safe_text_field(tag, limit=40)))
            try:
                spec = connection_routing_spec(kind)
                supported_actions = list(spec.supported_actions)
            except Exception:
                supported_actions = []
            source_payload = {
                "entity_type": "connection",
                "surface_id": "connections",
                "kind": kind,
                "ref": clean_ref,
                "title": title,
                "description": description,
                "group_name": group_name,
                "aliases": aliases,
                "tags": tags,
                "supported_actions": supported_actions,
                "action_candidates": _connection_action_candidates(kind),
            }
            document = MetaCatalogDocument(
                catalog_id=f"connection|{kind}|{clean_ref}",
                entity_type="connection",
                surface_id="connections",
                kind=kind,
                ref=clean_ref,
                title=title,
                description=description,
                group_name=group_name,
                aliases=aliases,
                tags=tags,
                knows=_connection_knows(kind, title, description, tags),
                can_load=_connection_can_load(kind),
                can_do=supported_actions,
                action_candidates=_connection_action_candidates(kind),
                loader_contract="load_safe_connection_meta_and_preflight_context_without_exposing_secrets",
                executor_contract="execute_only_after_schema_validation_policy_guardrails_and_required_confirmation",
                risk_hint=_risk_hint_for_connection(kind, supported_actions),
                confirmation_policy=_confirmation_policy_for_connection(kind, supported_actions),
                source_hash=_document_source_hash(source_payload),
                updated_at=now,
            )
            document.text = document.render_text()
            documents.append(document)
    return documents


def meta_catalog_documents_fingerprint(documents: Iterable[MetaCatalogDocument]) -> str:
    rows = [
        {
            "catalog_id": document.catalog_id,
            "source_hash": document.source_hash,
        }
        for document in documents
        if document.catalog_id and document.source_hash
    ]
    rows.sort(key=lambda item: (item["catalog_id"], item["source_hash"]))
    raw = json.dumps({"meta_catalog_version": META_CATALOG_VERSION, "documents": rows}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MetaCatalogStore:
    def __init__(self, *, qdrant: Any, embedding_client: Any, collection_name: str) -> None:
        self.qdrant = qdrant
        self.embedding_client = embedding_client
        self.collection_name = collection_name

    async def _embed(self, texts: list[str], *, operation: str) -> tuple[list[list[float]], dict[str, int], str]:
        response = await self.embedding_client.embed(texts, source="meta_catalog", operation=operation)
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
        await self.qdrant.create_collection(collection_name=collection_name, vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE))

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
            batch, offset = await self.qdrant.scroll(collection_name=source, limit=100, offset=offset, with_payload=True, with_vectors=True)
            rows.extend(batch or [])
            if offset is None:
                break
        if not rows:
            return 0
        first_vector = getattr(rows[0], "vector", None) or []
        await self._delete_collection_if_exists(target)
        await self._create_collection(target, len(first_vector))
        points = [PointStruct(id=getattr(row, "id", ""), vector=list(getattr(row, "vector", []) or []), payload=dict(getattr(row, "payload", {}) or {})) for row in rows]
        await self.qdrant.upsert(collection_name=target, points=points)
        return len(points)

    async def rebuild_documents(self, documents: list[MetaCatalogDocument], *, catalog_hash: str = "", backup_collection_name: str = "", keep_backup: bool = True) -> dict[str, Any]:
        rows = [document for document in documents if str(document.text or "").strip()]
        clean_hash = str(catalog_hash or meta_catalog_documents_fingerprint(rows)).strip()
        if not rows:
            return {"documents": 0, "collection": self.collection_name, "meta_catalog_hash": clean_hash, "embedding_usage": {}, "embedding_model": "", "backup_documents": 0}
        vectors, usage, model = await self._embed([document.text for document in rows], operation="rebuild_meta_catalog")
        if not vectors:
            return {"documents": 0, "collection": self.collection_name, "meta_catalog_hash": clean_hash, "embedding_usage": usage, "embedding_model": model, "backup_documents": 0}
        backup_documents = 0
        if keep_backup and backup_collection_name:
            backup_documents = await self._copy_collection(self.collection_name, backup_collection_name)
        await self._delete_collection_if_exists(self.collection_name)
        await self._create_collection(self.collection_name, len(vectors[0]))
        points: list[PointStruct] = []
        for document, vector in zip(rows, vectors, strict=False):
            payload = document.payload()
            payload["embedding_model"] = model
            payload["meta_catalog_hash"] = clean_hash
            payload["meta_catalog_document_count"] = len(rows)
            points.append(PointStruct(id=document.id, vector=vector, payload=payload))
        await self.qdrant.upsert(collection_name=self.collection_name, points=points)
        return {
            "documents": len(points),
            "collection": self.collection_name,
            "meta_catalog_hash": clean_hash,
            "embedding_usage": usage,
            "embedding_model": model,
            "backup_collection": backup_collection_name if keep_backup else "",
            "backup_documents": backup_documents,
        }

    async def query_catalog(self, query: str, *, limit: int = 12, score_threshold: float = 0.0) -> list[dict[str, Any]]:
        clean_query = _normalize_ws(query)
        if not clean_query:
            return []
        try:
            exists = await self.qdrant.collection_exists(collection_name=self.collection_name)
        except Exception:
            return []
        if not exists:
            return []
        vectors, _usage, _model = await self._embed([clean_query], operation="query_meta_catalog")
        vector = vectors[0] if vectors else []
        if not vector:
            return []
        result = await self.qdrant.query_points(collection_name=self.collection_name, query=vector, limit=max(1, int(limit)))
        rows: list[dict[str, Any]] = []
        for hit in self._extract_hits(result):
            payload = dict(getattr(hit, "payload", {}) or {})
            score = float(getattr(hit, "score", 0.0) or 0.0)
            if score < score_threshold:
                continue
            catalog_id = str(payload.get("catalog_id", "") or "").strip()
            if not catalog_id:
                continue
            rows.append(
                {
                    "catalog_id": catalog_id,
                    "surface_id": str(payload.get("surface_id", "") or "").strip(),
                    "kind": str(payload.get("kind", "") or "").strip(),
                    "ref": str(payload.get("ref", "") or "").strip(),
                    "score": score,
                    "source": "qdrant_meta_catalog",
                    "payload": payload,
                }
            )
        rows.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        return rows


async def create_meta_catalog_qdrant_client(settings: Any, *, timeout: int = 10) -> Any:
    return await create_inventory_qdrant_client(settings, timeout=timeout)
