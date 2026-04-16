from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from qdrant_client.models import Distance, PointStruct, VectorParams

from aria.core.connection_catalog import connection_kind_label, normalize_connection_kind
from aria.core.connection_semantic_resolver import build_connection_aliases


ROUTING_INDEX_VERSION = 1
DEFAULT_CONNECTION_ROUTING_KINDS: tuple[str, ...] = ("ssh", "sftp", "rss", "discord", "http_api")

_SECRET_FIELD_NAMES = {
    "api_key",
    "auth_token",
    "key_path",
    "password",
    "private_key",
    "secret",
    "token",
    "webhook_url",
}

_CONNECTION_ACTIONS: dict[str, tuple[str, ...]] = {
    "ssh": (
        "run command",
        "execute shell command",
        "server status",
        "health check",
        "uptime",
        "logs",
        "linux host",
        "befehl ausfuehren",
        "server pruefen",
    ),
    "sftp": (
        "read file",
        "list directory",
        "write file",
        "remote files",
        "datei lesen",
        "dateien anzeigen",
        "server dateien",
    ),
    "rss": (
        "read feed",
        "latest news",
        "headlines",
        "feed lesen",
        "neueste meldungen",
        "nachrichten",
    ),
    "discord": (
        "send message",
        "notify",
        "alert channel",
        "discord nachricht",
        "alarmieren",
        "meldung senden",
    ),
    "http_api": (
        "call api",
        "http request",
        "health endpoint",
        "api status",
        "api aufrufen",
        "endpoint pruefen",
    ),
}

_LANGUAGE_HINTS: dict[str, tuple[str, ...]] = {
    "ssh": ("run", "execute", "status", "uptime", "health", "fuehre", "starte", "pruefe", "status"),
    "sftp": ("read", "list", "file", "directory", "lies", "zeige", "datei", "ordner"),
    "rss": ("news", "latest", "feed", "headlines", "neu", "meldungen", "nachrichten"),
    "discord": ("send", "notify", "alert", "sende", "schicke", "melde", "alarmiere"),
    "http_api": ("api", "call", "endpoint", "health", "rufe", "hole", "status"),
}


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slug(value: str, *, fallback: str = "default") -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or fallback


def routing_collection_name(scope: str = "connections", *, instance_key: str = "") -> str:
    clean_scope = _slug(scope, fallback="connections")
    clean_instance = _slug(instance_key, fallback="")
    if clean_instance:
        return f"aria_routing_{clean_scope}_{clean_instance}"
    return f"aria_routing_{clean_scope}"


def _read_value(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _read_text(row: Any, name: str) -> str:
    return str(_read_value(row, name) or "").strip()


def _read_list(row: Any, name: str) -> list[str]:
    raw = _read_value(row, name)
    if not isinstance(raw, list):
        return []
    return [_normalize_ws(str(item)) for item in raw if _normalize_ws(str(item))]


def _dedupe(values: Iterable[str]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _normalize_ws(value)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(clean)
    return rows


def _safe_url_hints(value: str, *, include_path: bool = True) -> list[str]:
    clean = str(value or "").strip()
    if not clean:
        return []
    try:
        parsed = urlparse(clean)
    except ValueError:
        return []
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return []
    rows = [host]
    if host.startswith("www."):
        rows.append(host[4:])
    first_label = host.split(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    if first_label and first_label != host:
        rows.append(first_label)
    if include_path:
        path_tokens = [
            token
            for token in re.split(r"[^a-zA-Z0-9_-]+", str(parsed.path or ""))
            if 2 <= len(token) <= 32 and not re.fullmatch(r"[a-f0-9]{16,}", token.lower())
        ]
        rows.extend(token.replace("-", " ").replace("_", " ") for token in path_tokens[:4])
    return _dedupe(rows)


def _connection_target_hints(kind: str, row: Any) -> list[str]:
    hints: list[str] = []
    for field_name in ("host", "smtp_host", "mailbox", "topic", "root_path", "share"):
        value = _read_text(row, field_name)
        if value and field_name not in _SECRET_FIELD_NAMES:
            hints.append(value)
            if field_name in {"host", "smtp_host"} and "." in value:
                hints.append(value.split(".", 1)[0])

    service_url = _read_text(row, "service_url")
    hints.extend(_safe_url_hints(service_url, include_path=True))

    if kind == "rss":
        hints.extend(_safe_url_hints(_read_text(row, "feed_url"), include_path=True))
    elif kind == "http_api":
        hints.extend(_safe_url_hints(_read_text(row, "base_url"), include_path=True))
    elif kind == "webhook":
        hints.extend(_safe_url_hints(_read_text(row, "url"), include_path=False))
    elif kind == "discord":
        hints.extend(_safe_url_hints(_read_text(row, "webhook_url"), include_path=False))

    return _dedupe(hints)


def _connection_safe_aliases(kind: str, ref: str, row: Any) -> list[str]:
    unsafe_values = [
        _read_text(row, field_name).lower()
        for field_name in _SECRET_FIELD_NAMES
        if _read_text(row, field_name)
    ]
    aliases: list[str] = []
    for alias in build_connection_aliases(kind, ref, row) + _read_list(row, "aliases"):
        clean = _normalize_ws(alias)
        if not clean:
            continue
        lowered = clean.lower()
        if "://" in lowered:
            continue
        if any(secret and secret in lowered for secret in unsafe_values):
            continue
        aliases.append(clean)
    return _dedupe(aliases)


def _document_source_hash(payload: dict[str, Any]) -> str:
    raw = repr(sorted((str(key), repr(value)) for key, value in payload.items()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class RoutingDocument:
    scope: str
    kind: str
    ref: str
    title: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    supported_actions: list[str] = field(default_factory=list)
    language_hints: list[str] = field(default_factory=list)
    target_hints: list[str] = field(default_factory=list)
    text: str = ""
    source_hash: str = ""
    updated_at: str = ""

    @property
    def id(self) -> str:
        return str(uuid5(NAMESPACE_URL, f"aria-routing|{self.scope}|{self.kind}|{self.ref}"))

    def render_text(self) -> str:
        rows = [
            f"Scope: {self.scope}",
            f"Kind: {connection_kind_label(self.kind)}",
            f"Ref: {self.ref}",
        ]
        if self.title:
            rows.append(f"Title: {self.title}")
        if self.description:
            rows.append(f"Description: {self.description}")
        if self.aliases:
            rows.append("Aliases: " + ", ".join(self.aliases))
        if self.tags:
            rows.append("Tags: " + ", ".join(self.tags))
        if self.supported_actions:
            rows.append("Supported actions: " + ", ".join(self.supported_actions))
        if self.language_hints:
            rows.append("Language hints: " + ", ".join(self.language_hints))
        if self.target_hints:
            rows.append("Target hints: " + ", ".join(self.target_hints))
        return "\n".join(rows)

    def payload(self) -> dict[str, Any]:
        return {
            "routing_index_version": ROUTING_INDEX_VERSION,
            "scope": self.scope,
            "kind": self.kind,
            "ref": self.ref,
            "title": self.title,
            "description": self.description,
            "aliases": list(self.aliases),
            "tags": list(self.tags),
            "supported_actions": list(self.supported_actions),
            "language_hints": list(self.language_hints),
            "target_hints": list(self.target_hints),
            "text": self.text or self.render_text(),
            "source_hash": self.source_hash,
            "updated_at": self.updated_at,
        }


def build_connection_routing_documents(
    settings: Any,
    *,
    include_kinds: Iterable[str] = DEFAULT_CONNECTION_ROUTING_KINDS,
) -> list[RoutingDocument]:
    include = {normalize_connection_kind(kind) for kind in include_kinds if str(kind).strip()}
    connection_cfg = getattr(settings, "connections", None)
    if connection_cfg is None:
        return []

    now = datetime.now(timezone.utc).isoformat()
    documents: list[RoutingDocument] = []
    for kind in sorted(include):
        rows = getattr(connection_cfg, kind, {})
        if not isinstance(rows, dict):
            continue
        for ref, row in sorted(rows.items(), key=lambda item: str(item[0]).strip().lower()):
            clean_ref = str(ref or "").strip()
            if not clean_ref:
                continue
            aliases = _connection_safe_aliases(kind, clean_ref, row)
            tags = _dedupe(_read_list(row, "tags"))
            title = _read_text(row, "title")
            description = _read_text(row, "description")
            supported_actions = list(_CONNECTION_ACTIONS.get(kind, ()))
            language_hints = list(_LANGUAGE_HINTS.get(kind, ()))
            target_hints = _connection_target_hints(kind, row)
            source_payload = {
                "kind": kind,
                "ref": clean_ref,
                "title": title,
                "description": description,
                "aliases": aliases,
                "tags": tags,
                "supported_actions": supported_actions,
                "language_hints": language_hints,
                "target_hints": target_hints,
            }
            document = RoutingDocument(
                scope="connection",
                kind=kind,
                ref=clean_ref,
                title=title,
                description=description,
                aliases=aliases,
                tags=tags,
                supported_actions=supported_actions,
                language_hints=language_hints,
                target_hints=target_hints,
                source_hash=_document_source_hash(source_payload),
                updated_at=now,
            )
            document.text = document.render_text()
            documents.append(document)
    return documents


def routing_documents_fingerprint(documents: Iterable[RoutingDocument]) -> str:
    rows = [
        {
            "scope": document.scope,
            "kind": document.kind,
            "ref": document.ref,
            "source_hash": document.source_hash,
        }
        for document in documents
        if str(document.scope or "").strip() and str(document.kind or "").strip() and str(document.ref or "").strip()
    ]
    rows.sort(key=lambda item: (item["scope"], item["kind"], item["ref"], item["source_hash"]))
    payload = {
        "routing_index_version": ROUTING_INDEX_VERSION,
        "documents": rows,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RoutingIndexStore:
    def __init__(
        self,
        *,
        qdrant: Any,
        embedding_client: Any,
        collection_name: str = "aria_routing_connections",
    ) -> None:
        self.qdrant = qdrant
        self.embedding_client = embedding_client
        self.collection_name = collection_name
        self._collection_by_size: dict[int, str] = {}

    async def _embed(self, texts: list[str], *, operation: str) -> tuple[list[list[float]], dict[str, int], str]:
        response = await self.embedding_client.embed(texts, source="routing_index", operation=operation)
        return [list(map(float, vector)) for vector in response.vectors], dict(response.usage), str(response.model or "")

    async def _collection_vector_size(self, collection_name: str) -> int | None:
        try:
            info = await self.qdrant.get_collection(collection_name=collection_name)
        except Exception:
            return None
        vectors = getattr(getattr(info, "config", None), "params", None)
        vectors = getattr(vectors, "vectors", None)
        if hasattr(vectors, "size"):
            return int(vectors.size)
        if isinstance(vectors, dict):
            first = next(iter(vectors.values()), None)
            if first is not None and hasattr(first, "size"):
                return int(first.size)
        return None

    async def _ensure_collection_for_vector(self, vector_size: int) -> str:
        if vector_size in self._collection_by_size:
            return self._collection_by_size[vector_size]

        base = self.collection_name
        exists = await self.qdrant.collection_exists(collection_name=base)
        if not exists:
            await self.qdrant.create_collection(
                collection_name=base,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            self._collection_by_size[vector_size] = base
            return base

        base_size = await self._collection_vector_size(base)
        if base_size is None or base_size == vector_size:
            self._collection_by_size[vector_size] = base
            return base

        alt = f"{base}_dim_{vector_size}"
        alt_exists = await self.qdrant.collection_exists(collection_name=alt)
        if not alt_exists:
            await self.qdrant.create_collection(
                collection_name=alt,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        self._collection_by_size[vector_size] = alt
        return alt

    async def _existing_collection_for_vector(self, vector_size: int) -> str | None:
        if vector_size in self._collection_by_size:
            return self._collection_by_size[vector_size]

        base = self.collection_name
        try:
            exists = await self.qdrant.collection_exists(collection_name=base)
        except Exception:
            return None
        if not exists:
            return None

        base_size = await self._collection_vector_size(base)
        if base_size is None or base_size == vector_size:
            self._collection_by_size[vector_size] = base
            return base

        alt = f"{base}_dim_{vector_size}"
        try:
            alt_exists = await self.qdrant.collection_exists(collection_name=alt)
        except Exception:
            return None
        if not alt_exists:
            return None
        self._collection_by_size[vector_size] = alt
        return alt

    async def upsert_documents(self, documents: list[RoutingDocument], *, index_hash: str = "") -> dict[str, Any]:
        rows = [document for document in documents if str(document.text or "").strip()]
        if not rows:
            return {"documents": 0, "collections": [], "embedding_usage": {}, "embedding_model": "", "routing_index_hash": ""}
        routing_index_hash = str(index_hash or routing_documents_fingerprint(rows)).strip()
        vectors, usage, model = await self._embed([document.text for document in rows], operation="upsert_connections")
        if not vectors:
            return {
                "documents": 0,
                "collections": [],
                "embedding_usage": usage,
                "embedding_model": model,
                "routing_index_hash": routing_index_hash,
            }

        grouped: dict[str, list[PointStruct]] = {}
        for document, vector in zip(rows, vectors, strict=False):
            collection = await self._ensure_collection_for_vector(len(vector))
            payload = document.payload()
            payload["embedding_model"] = model
            payload["routing_index_hash"] = routing_index_hash
            payload["routing_index_document_count"] = len(rows)
            grouped.setdefault(collection, []).append(PointStruct(id=document.id, vector=vector, payload=payload))

        for collection, points in grouped.items():
            await self.qdrant.upsert(collection_name=collection, points=points)

        return {
            "documents": sum(len(points) for points in grouped.values()),
            "collections": sorted(grouped),
            "embedding_usage": usage,
            "embedding_model": model,
            "routing_index_hash": routing_index_hash,
        }

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

    async def query_connections(
        self,
        query: str,
        *,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        vectors, _usage, _model = await self._embed([clean_query], operation="query_connections")
        vector = vectors[0] if vectors else []
        if not vector:
            return []
        collection = await self._existing_collection_for_vector(len(vector))
        if not collection:
            return []
        query_result = await self.qdrant.query_points(
            collection_name=collection,
            query=vector,
            limit=max(1, int(limit)),
        )
        rows: list[dict[str, Any]] = []
        for hit in self._extract_hits(query_result):
            payload = dict(getattr(hit, "payload", {}) or {})
            if str(payload.get("scope", "")).strip().lower() != "connection":
                continue
            score = float(getattr(hit, "score", 0.0) or 0.0)
            if score < score_threshold:
                continue
            rows.append(
                {
                    "kind": str(payload.get("kind", "")).strip(),
                    "ref": str(payload.get("ref", "")).strip(),
                    "score": score,
                    "source": "qdrant_routing",
                    "reason": str(payload.get("title", "") or payload.get("description", "") or payload.get("text", "")).strip(),
                    "payload": payload,
                }
            )
        rows.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        return rows
