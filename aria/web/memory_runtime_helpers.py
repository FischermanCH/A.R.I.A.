from __future__ import annotations

from collections.abc import Callable, Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Request

from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.qdrant_storage_diagnostics import (
    build_qdrant_storage_warning,
    list_local_qdrant_collection_names,
    resolve_qdrant_storage_path,
)

CollectionNameSanitizer = Callable[[str | None], str]
CurrentMemoryDayGetter = Callable[[], str]
RequestCookieGetter = Callable[[Request, str], str]
SettingsGetter = Callable[[], Any]


@dataclass(frozen=True)
class MemoryRuntimeHelperDeps:
    base_dir: Path
    get_settings: SettingsGetter
    sanitize_collection_name: CollectionNameSanitizer
    current_memory_day: CurrentMemoryDayGetter
    request_cookie_value: RequestCookieGetter
    session_cookie: str
    memory_collection_cookie: str


@dataclass(frozen=True)
class MemoryRuntimeHelpers:
    default_memory_collection_for_user: Callable[[str], str]
    ensure_session_id: Callable[[Request], str]
    get_effective_memory_collection: Callable[[Request, str], str]
    session_memory_collection_for_user: Callable[[str, str], str]
    is_auto_memory_enabled: Callable[[Request], bool]
    qdrant_base_url: Callable[[Request], str]
    qdrant_dashboard_url: Callable[[Request], str]
    list_qdrant_collections: Callable[[], Awaitable[list[str]]]
    qdrant_overview: Callable[[Request], Awaitable[dict[str, Any]]]


def build_memory_runtime_helpers(deps: MemoryRuntimeHelperDeps) -> MemoryRuntimeHelpers:
    BASE_DIR = deps.base_dir
    _get_settings = deps.get_settings
    _sanitize_collection_name = deps.sanitize_collection_name
    _current_memory_day = deps.current_memory_day
    _request_cookie_value = deps.request_cookie_value
    SESSION_COOKIE = deps.session_cookie
    MEMORY_COLLECTION_COOKIE = deps.memory_collection_cookie

    def default_memory_collection_for_user(user_id: str) -> str:
        settings = _get_settings()
        slug = _sanitize_collection_name(user_id.lower())
        if not slug:
            slug = "web"
        prefix = settings.memory.collections.facts.prefix.strip() or "aria_facts"
        return f"{prefix}_{slug}"

    def ensure_session_id(request: Request) -> str:
        current = _sanitize_collection_name(_request_cookie_value(request, SESSION_COOKIE))
        if current:
            return current
        return uuid4().hex[:12]

    def get_effective_memory_collection(request: Request, user_id: str) -> str:
        selected = _sanitize_collection_name(_request_cookie_value(request, MEMORY_COLLECTION_COOKIE))
        if selected:
            return selected
        return default_memory_collection_for_user(user_id)

    def session_memory_collection_for_user(user_id: str, session_id: str) -> str:
        settings = _get_settings()
        slug = _sanitize_collection_name(user_id.lower())
        if not slug:
            slug = "web"
        session_prefix = settings.memory.collections.sessions.prefix.strip() or "aria_sessions"
        _ = session_id
        return f"{session_prefix}_{slug}_{_current_memory_day()}"

    def is_auto_memory_enabled(request: Request) -> bool:
        _ = request
        settings = _get_settings()
        return bool(settings.auto_memory.enabled)

    def qdrant_base_url(request: Request) -> str:
        settings = _get_settings()
        base = (settings.memory.qdrant_url or "").strip()
        parsed = urlparse(base)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            host = (parsed.hostname or "").strip()
            if host.lower() == "qdrant":
                req_host = (request.url.hostname or "").strip() or "localhost"
                if ":" in req_host and not req_host.startswith("["):
                    req_host = f"[{req_host}]"
                port = parsed.port or 6333
                return f"{parsed.scheme}://{req_host}:{port}"
            if host in {"localhost", "127.0.0.1", "::1"}:
                req_host = (request.url.hostname or "").strip()
                if req_host:
                    host = req_host
            if not host:
                host = parsed.hostname or "localhost"
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            port = parsed.port
            port_part = f":{port}" if port else ""
            return f"{parsed.scheme}://{host}{port_part}"
        return base

    def qdrant_dashboard_url(request: Request) -> str:
        base = qdrant_base_url(request).rstrip("/")
        if not base:
            return ""
        return f"{base}/dashboard#/collections"

    async def list_qdrant_collections() -> list[str]:
        settings = _get_settings()
        if not settings.memory.enabled or settings.memory.backend.lower() != "qdrant":
            return []
        client = create_async_qdrant_client(
            url=settings.memory.qdrant_url,
            api_key=(settings.memory.qdrant_api_key or None),
            timeout=10,
        )
        try:
            resp = await client.get_collections()
            names = [c.name for c in getattr(resp, "collections", []) if getattr(c, "name", "")]
            names.sort()
            return names
        except Exception:
            return []

    async def qdrant_overview(request: Request) -> dict[str, Any]:
        settings = _get_settings()
        storage_path = resolve_qdrant_storage_path(BASE_DIR, settings.memory.qdrant_url)
        local_collection_names = list_local_qdrant_collection_names(storage_path)
        empty = {
            "enabled": settings.memory.enabled and settings.memory.backend.lower() == "qdrant",
            "qdrant_url": qdrant_base_url(request),
            "dashboard_url": qdrant_dashboard_url(request),
            "collections": [],
            "collection_count": 0,
            "total_points": 0,
            "max_points": 0,
            "reachable": False,
            "error": "",
            "storage_path": str(storage_path) if storage_path else "",
            "storage_collection_count": len(local_collection_names),
            "storage_warning": "",
            "storage_warning_missing": [],
        }
        if not empty["enabled"]:
            return empty

        client = create_async_qdrant_client(
            url=settings.memory.qdrant_url,
            api_key=(settings.memory.qdrant_api_key or None),
            timeout=10,
        )
        try:
            resp = await client.get_collections()
            names = [c.name for c in getattr(resp, "collections", []) if getattr(c, "name", "")]
            names = sorted(set(names))
            rows: list[dict[str, Any]] = []
            max_points = 0
            for name in names:
                points = 0
                vectors = 0
                indexed_vectors = 0
                status = "ok"
                try:
                    info = await client.get_collection(collection_name=name)
                    points = int(getattr(info, "points_count", 0) or 0)
                    vectors = int(getattr(info, "vectors_count", 0) or 0)
                    indexed_vectors = int(getattr(info, "indexed_vectors_count", 0) or 0)
                    raw_status = getattr(info, "status", None)
                    if raw_status is not None:
                        status = str(raw_status)
                except Exception:
                    status = "error"
                max_points = max(max_points, points)
                rows.append({
                    "name": name,
                    "points": points,
                    "vectors": vectors,
                    "indexed_vectors": indexed_vectors,
                    "status": status,
                })

            for row in rows:
                row["points_bar_pct"] = int((row["points"] / max_points) * 100) if max_points > 0 else 0

            storage_warning = build_qdrant_storage_warning(
                storage_path=storage_path,
                local_collection_names=local_collection_names,
                api_collection_names=names,
            )
            return {
                "enabled": True,
                "qdrant_url": qdrant_base_url(request),
                "dashboard_url": qdrant_dashboard_url(request),
                "collections": rows,
                "collection_count": len(rows),
                "total_points": int(sum(r["points"] for r in rows)),
                "max_points": max_points,
                "reachable": True,
                "error": "",
                "storage_path": str(storage_path) if storage_path else "",
                "storage_collection_count": len(local_collection_names),
                "storage_warning": str(storage_warning.get("message", "") or ""),
                "storage_warning_missing": list(storage_warning.get("missing_from_api", []) or []),
            }
        except Exception as exc:
            empty["error"] = str(exc)
            storage_warning = build_qdrant_storage_warning(
                storage_path=storage_path,
                local_collection_names=local_collection_names,
                api_collection_names=[],
            )
            empty["storage_warning"] = str(storage_warning.get("message", "") or "")
            empty["storage_warning_missing"] = list(storage_warning.get("missing_from_api", []) or [])
            return empty

    return MemoryRuntimeHelpers(
        default_memory_collection_for_user=default_memory_collection_for_user,
        ensure_session_id=ensure_session_id,
        get_effective_memory_collection=get_effective_memory_collection,
        session_memory_collection_for_user=session_memory_collection_for_user,
        is_auto_memory_enabled=is_auto_memory_enabled,
        qdrant_base_url=qdrant_base_url,
        qdrant_dashboard_url=qdrant_dashboard_url,
        list_qdrant_collections=list_qdrant_collections,
        qdrant_overview=qdrant_overview,
    )
