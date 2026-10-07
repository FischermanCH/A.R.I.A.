from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
import hmac
import math
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile

from aria.modules import module_route_path, module_template_name
from aria.modules.document_ingest.ingest import DocumentIngestError, prepare_uploaded_document, supported_upload_suffixes
from aria.modules.platform_primitives.actionable_sequence import ObservedSequenceStore
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.platform_primitives.observed_claims import ObservedClaimStore
from aria.modules.memory.personal import normalize_personal_claim
from aria.modules.memory.personal import personal_claim_from_payload
from aria.modules.memory.personal import personal_claim_payload_lifecycle_state
from aria.modules.memory.personal import personal_claim_payload_review_due
from aria.modules.memory.personal import store_personal_claim
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.system_diagnostics.qdrant_collection_classifier import classify_qdrant_collection
from aria.modules.system_diagnostics.qdrant_collection_classifier import is_notes_qdrant_collection
from aria.modules.system_diagnostics.qdrant_collection_classifier import is_recipe_experience_qdrant_collection
from aria.modules.system_diagnostics.qdrant_collection_classifier import is_routing_qdrant_collection
from aria.modules.system_inventory.admin import build_inventory_index_status
from aria.modules.integration_support.runtime_endpoint import cookie_should_be_secure


BASE_DIR = Path(__file__).resolve().parents[3]
_MEMORIES_ROUTES_I18N = I18NStore(BASE_DIR / "aria" / "i18n")

UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]

RoleSanitizer = Callable[[str | None], str]
SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Pipeline]
QdrantOverviewLoader = Callable[[Request], Awaitable[dict[str, Any]]]
QdrantDashboardUrlResolver = Callable[[Request], str]
CollectionDayParser = Callable[[str], datetime | None]
CollectionNameSanitizer = Callable[[str | None], str]
DefaultCollectionResolver = Callable[[str], str]
EffectiveCollectionResolver = Callable[[Request, str], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
PromptFileResolver = Callable[[str], Path]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]
InventoryIndexStatusBuilder = Callable[[Any], Awaitable[dict[str, Any]]]


def _is_admin_request(
    request: Request,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
) -> bool:
    auth = get_auth_session_from_request(request) or {}
    return sanitize_role(auth.get("role")) == "admin"


def _msg(lang: str, de: str, en: str) -> str:
    return de if str(lang or "de").strip().lower().startswith("de") else en


def _memory_routes_text(lang: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _MEMORIES_ROUTES_I18N.t(lang or "de", f"memories_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _memory_admin_template(template_name: str) -> str:
    resolved = module_template_name("memory_admin_ui", template_name)
    if resolved is None:
        raise RuntimeError(f"memory_admin_ui template is not registered: {template_name}")
    return resolved


def _memory_admin_route(route_path: str) -> str:
    resolved = module_route_path("memory_admin_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"memory_admin_ui route is not registered: {route_path}")
    return resolved


def _memory_admin_redirect_url(route_path: str, *, info: str = "", error: str = "") -> str:
    url = _memory_admin_route(route_path)
    params: list[str] = []
    if info:
        params.append(f"info={quote_plus(info)}")
    if error:
        params.append(f"error={quote_plus(error)}")
    if params:
        url += "?" + "&".join(params)
    return url


def _documents_route(route_path: str) -> str:
    resolved = module_route_path("notes", route_path)
    if resolved is None:
        raise RuntimeError(f"notes route is not registered: {route_path}")
    return resolved


def _config_ui_route(route_path: str) -> str:
    resolved = module_route_path("config_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"config_ui route is not registered: {route_path}")
    return resolved


def _recipes_ui_route(route_path: str) -> str:
    resolved = module_route_path("recipes_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"recipes_ui route is not registered: {route_path}")
    return resolved


def _friendly_memory_error(lang: str, exc: Exception, de_default: str, en_default: str) -> str:
    if isinstance(exc, ValueError):
        detail = str(exc).strip()
        if detail:
            return detail
    return _msg(lang, de_default, en_default)


def _is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    submitted = str(submitted_token or "").strip()
    expected = str(expected_token or "").strip()
    return bool(submitted and expected and hmac.compare_digest(submitted, expected))


def _normalize_memory_sort(value: str) -> str:
    sort_key = str(value).strip().lower()
    allowed_sorts = {"updated_desc", "updated_asc", "type", "collection", "score_desc"}
    if sort_key not in allowed_sorts:
        return "updated_desc"
    return sort_key


def _coerce_page_size(value: int) -> int:
    return max(10, min(int(value), 100))


def _coerce_page_number(value: int) -> int:
    return max(1, int(value))


def _coerce_form_int(value: Any, default: int) -> int:
    try:
        return int(str(value if value is not None else default).strip() or default)
    except (TypeError, ValueError):
        return default


def _is_uploaded_file(value: Any) -> bool:
    return isinstance(value, (UploadFile, StarletteUploadFile))


def _memory_row_timestamp(row: dict[str, Any]) -> float:
    raw = str(row.get("timestamp", "")).strip()
    if not raw:
        return 0.0
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return parsed.timestamp()


def _sort_memory_rows(rows: list[dict[str, Any]], sort_key: str) -> None:
    if sort_key == "updated_asc":
        rows.sort(key=_memory_row_timestamp)
        return
    if sort_key == "type":
        rows.sort(key=lambda row: (str(row.get("type", "")).lower(), -_memory_row_timestamp(row)))
        return
    if sort_key == "collection":
        rows.sort(key=lambda row: (str(row.get("collection", "")).lower(), -_memory_row_timestamp(row)))
        return
    if sort_key == "score_desc":
        rows.sort(key=lambda row: float(row.get("score", 0.0) or 0.0), reverse=True)
        return
    rows.sort(key=_memory_row_timestamp, reverse=True)


def _build_memory_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"fact": 0, "preference": 0, "knowledge": 0, "reflection": 0, "learning_event": 0, "learning_candidate": 0, "learning_active_hint": 0, "learning_eval": 0, "document": 0, "session": 0}
    for row in rows:
        key = str(row.get("type", "")).strip().lower()
        if key in counts:
            counts[key] += 1
    return counts


def _memory_group_order(value: str) -> int:
    order = {
        "document": 0,
        "knowledge": 1,
        "fact": 2,
        "preference": 3,
        "session": 4,
    }
    return order.get(str(value or "").strip().lower(), 99)


def _build_type_points(collection_stats: list[dict[str, Any]]) -> dict[str, int]:
    type_points = {"fact": 0, "preference": 0, "knowledge": 0, "reflection": 0, "learning_event": 0, "learning_candidate": 0, "learning_active_hint": 0, "learning_eval": 0, "document": 0, "session": 0}
    for item in collection_stats:
        kind = str(item.get("kind", "fact")).strip().lower()
        points = int(item.get("points", 0) or 0)
        if kind in type_points:
            type_points[kind] += points
    return type_points


def _build_memory_health(
    *,
    all_rows: list[dict[str, Any]],
    collection_stats: list[dict[str, Any]],
    filter_type: str,
    query: str,
    parse_collection_day_suffix: CollectionDayParser,
    compress_after_days: int,
    qdrant_reachable: bool,
) -> dict[str, Any]:
    type_points = _build_type_points(collection_stats)
    total_points = int(sum(type_points.values()))
    largest = max(collection_stats, key=lambda row: int(row.get("points", 0) or 0), default=None)
    largest_name = str((largest or {}).get("name", "")).strip() or "n/a"
    largest_points = int((largest or {}).get("points", 0) or 0)
    largest_share_pct = int((largest_points / total_points) * 100) if total_points > 0 else 0

    stale_sessions = 0
    now = datetime.now()
    for item in collection_stats:
        name = str(item.get("name", "")).strip()
        if "session" not in name.lower():
            continue
        day = parse_collection_day_suffix(name)
        if not day:
            continue
        age_days = max(0, (now - day).days)
        if age_days >= compress_after_days:
            stale_sessions += 1

    return {
        "rows_shown": 0,
        "rows_total": len(all_rows),
        "filter_type": filter_type,
        "search_query": query.strip(),
        "user_collections": len(collection_stats),
        "user_total_points": total_points,
        "type_points": type_points,
        "largest_collection_name": largest_name,
        "largest_collection_points": largest_points,
        "largest_collection_share_pct": largest_share_pct,
        "stale_sessions": stale_sessions,
        "compress_after_days": compress_after_days,
        "qdrant_reachable": bool(qdrant_reachable),
    }


def _build_cleanup_status(memory_skill: Any | None) -> dict[str, Any]:
    fallback = {
        "scope": "",
        "user_id": "",
        "removed_count": 0,
        "removed_collections": [],
        "timestamp": "",
    }
    if not memory_skill:
        return fallback
    return dict(getattr(memory_skill, "last_cleanup_status", {}) or fallback)


async def _build_memory_map_snapshot(
    *,
    pipeline: Any,
    username: str,
    lang: str,
    overview: dict[str, Any],
    is_admin: bool,
    settings: Any,
    parse_collection_day_suffix: CollectionDayParser,
    preferred_graph_collections: list[str] | None = None,
) -> dict[str, Any]:
    user_rows: list[dict[str, Any]] = []
    notes_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    system_rows: list[dict[str, Any]] = []
    collection_stats: list[dict[str, Any]] = []
    document_entries: list[dict[str, Any]] = []
    document_groups: list[dict[str, Any]] = []
    rollup_entries: list[dict[str, Any]] = []
    rollup_groups: list[dict[str, Any]] = []
    memory_graph: dict[str, Any] = {"nodes": [], "edges": [], "width": 0, "height": 0, "has_graph": False}
    qdrant_brain_graph: dict[str, Any] = {
        "nodes": [],
        "edges": [],
        "width": 0,
        "height": 0,
        "has_graph": False,
        "sample_count": 0,
        "edge_count": 0,
        "collection_count": 0,
        "error": "",
    }
    memory_skill = getattr(pipeline, "memory_skill", None)

    if memory_skill:
        try:
            stats = await memory_skill.get_user_collection_stats(username)
            collection_stats = list(stats)
            all_status = {
                str(item.get("name", "")): str(item.get("status", "ok"))
                for item in overview.get("collections", [])
            }
            for row in stats:
                name = str(row.get("name", "")).strip()
                kind = str(row.get("kind", "fact"))
                user_rows.append(
                    {
                        "name": name,
                        "points": int(row.get("points", 0) or 0),
                        "kind": kind,
                        "status": all_status.get(name, "ok"),
                        "browse_url": _memory_collection_link(kind=kind, collection=name),
                    }
                )
        except Exception:
            user_rows = []
        try:
            document_rows = await memory_skill.list_memories_global(
                user_id=username,
                type_filter="document",
                limit=5000,
            )
            document_entries = _build_document_entries(document_rows)
            document_groups = _build_document_collection_groups(document_entries)
        except Exception:
            document_entries = []
            document_groups = []
        try:
            knowledge_rows = await memory_skill.list_memories_global(
                user_id=username,
                type_filter="knowledge",
                limit=5000,
            )
            rollup_entries = _build_rollup_entries(knowledge_rows)
            rollup_groups = _build_rollup_groups(rollup_entries)
        except Exception:
            rollup_entries = []
            rollup_groups = []
        if hasattr(memory_skill, "list_memory_graph_points"):
            try:
                graph_rows = await memory_skill.list_memory_graph_points(
                    user_id=username,
                    limit=160,
                    collection_limit=32,
                    preferred_collections=preferred_graph_collections or [],
                )
                qdrant_brain_graph = _build_qdrant_brain_graph(list(graph_rows), lang=lang, max_nodes=160, max_edges=260)
            except Exception as exc:
                qdrant_brain_graph = {
                    "nodes": [],
                    "edges": [],
                    "width": 0,
                    "height": 0,
                    "has_graph": False,
                    "sample_count": 0,
                    "edge_count": 0,
                    "collection_count": 0,
                    "error": str(exc),
                }

    user_rows.sort(key=lambda row: int(row.get("points", 0) or 0), reverse=True)
    max_points = max((int(row.get("points", 0) or 0) for row in user_rows), default=0)
    total_points = int(sum(int(row.get("points", 0) or 0) for row in user_rows))
    for row in user_rows:
        points = int(row.get("points", 0) or 0)
        row["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
        row["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        row["node_size"] = max(16, min(54, int(16 + (row["pct"] / 100.0) * 38)))

    kind_totals = {"fact": 0, "preference": 0, "knowledge": 0, "reflection": 0, "learning_event": 0, "learning_candidate": 0, "learning_active_hint": 0, "learning_eval": 0, "document": 0, "session": 0}
    for row in user_rows:
        kind = str(row.get("kind", "fact"))
        if kind in kind_totals:
            kind_totals[kind] += int(row.get("points", 0) or 0)

    if is_admin:
        notes_rows = _build_notes_collection_rows(
            list(overview.get("collections", []) or []),
            username=username,
            browse_url=_documents_route("/notes"),
        )
        routing_rows = _build_routing_collection_rows(
            list(overview.get("collections", []) or []),
            known_user_collection_names={
                str(row.get("name", "")).strip() for row in [*user_rows, *notes_rows]
            },
            browse_url=_memory_admin_route("/memories"),
        )
        system_rows = _build_system_collection_rows(
            list(overview.get("collections", []) or []),
            known_collection_names={
                str(row.get("name", "")).strip() for row in [*user_rows, *notes_rows, *routing_rows]
            },
        )

    notes_total_points = int(sum(int(row.get("points", 0) or 0) for row in notes_rows))
    routing_total_points = int(sum(int(row.get("points", 0) or 0) for row in routing_rows))
    system_total_points = int(sum(int(row.get("points", 0) or 0) for row in system_rows))
    cleanup_status = _build_cleanup_status(memory_skill)
    cleanup_status["timestamp"] = _format_display_timestamp(cleanup_status.get("timestamp"))

    health = _build_memory_health(
        all_rows=[],
        collection_stats=collection_stats,
        filter_type="all",
        query="",
        parse_collection_day_suffix=parse_collection_day_suffix,
        compress_after_days=int(settings.memory.collections.sessions.compress_after_days or 7),
        qdrant_reachable=bool(overview.get("reachable")),
    )
    memory_graph = _build_memory_graph(
        username=username,
        lang=lang,
        map_rows=user_rows,
        kind_totals=kind_totals,
        document_groups=document_groups,
        rollup_groups=rollup_groups,
        notes_rows=notes_rows,
        routing_rows=routing_rows,
        system_rows=system_rows,
    )
    memory_graph["brain"] = qdrant_brain_graph

    return {
        "user_rows": user_rows,
        "notes_rows": notes_rows,
        "notes_total_points": notes_total_points,
        "routing_rows": routing_rows,
        "routing_total_points": routing_total_points,
        "system_rows": system_rows,
        "system_total_points": system_total_points,
        "collection_stats": collection_stats,
        "document_entries": document_entries,
        "document_groups": document_groups,
        "rollup_entries": rollup_entries,
        "rollup_groups": rollup_groups,
        "memory_graph": memory_graph,
        "health": health,
        "cleanup_status": cleanup_status,
        "kind_totals": kind_totals,
        "total_points": total_points,
    }


def _format_display_timestamp(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw.replace("T", " ", 1)


def _safe_browser_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _slug_user_id(user_id: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(user_id or "").strip())
    while "__" in clean:
        clean = clean.replace("__", "_")
    clean = clean.strip("_")
    return clean or "web"


def _memory_title(text: str, *, limit: int = 88) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return "Empty entry"
    for splitter in (". ", "! ", "? ", "\n"):
        if splitter in raw:
            raw = raw.split(splitter, 1)[0].strip()
            break
    if len(raw) <= limit:
        return raw
    return raw[: max(20, limit - 1)].rstrip() + "…"


def _memory_preview(text: str, *, limit: int = 180) -> str:
    raw = " ".join(str(text or "").strip().split())
    if len(raw) <= limit:
        return raw
    return raw[: max(40, limit - 1)].rstrip() + "…"


def _build_document_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if str(row.get("type", "")).strip().lower() != "document":
            continue
        collection = str(row.get("collection", "")).strip()
        document_id = str(row.get("document_id", "")).strip()
        document_name = str(row.get("document_name", "")).strip()
        key = (collection, document_id or document_name)
        if not key[0] or not key[1]:
            continue
        entry = grouped.setdefault(
            key,
            {
                "collection": collection,
                "document_id": document_id,
                "document_name": document_name or "Unbenanntes Dokument",
                "chunk_count": 0,
                "latest_timestamp": "",
                "preview": "",
                "source": str(row.get("source", "")).strip() or "n/a",
            },
        )
        entry["chunk_count"] += 1
        timestamp = str(row.get("timestamp", "")).strip()
        if timestamp and timestamp > str(entry.get("latest_timestamp", "")):
            entry["latest_timestamp"] = timestamp
        if not entry["preview"]:
            entry["preview"] = _memory_preview(str(row.get("text", "")).strip(), limit=120)

    items = list(grouped.values())
    items.sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
    for item in items:
        item["display_timestamp"] = _format_display_timestamp(item.get("latest_timestamp"))
    return items


def _build_document_collection_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        collection = str(entry.get("collection", "")).strip()
        if not collection:
            continue
        group = grouped.setdefault(
            collection,
            {
                "collection": collection,
                "document_count": 0,
                "chunk_count": 0,
                "latest_timestamp": "",
                "documents": [],
            },
        )
        group["document_count"] += 1
        group["chunk_count"] += int(entry.get("chunk_count", 0) or 0)
        timestamp = str(entry.get("latest_timestamp", "")).strip()
        if timestamp and timestamp > str(group.get("latest_timestamp", "")):
            group["latest_timestamp"] = timestamp
        group["documents"].append(entry)

    items = list(grouped.values())
    items.sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
    for item in items:
        item["display_timestamp"] = _format_display_timestamp(item.get("latest_timestamp"))
        item["documents"].sort(key=lambda row: str(row.get("latest_timestamp", "")), reverse=True)
    return items


def _build_document_drilldown_groups(rows: list[dict[str, Any]], *, max_chunks_per_document: int = 12) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    document_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if str(row.get("type", "")).strip().lower() != "document":
            continue
        collection = str(row.get("collection", "")).strip()
        if not _is_document_collection_name(collection):
            continue
        document_id = str(row.get("document_id", "")).strip()
        document_name = str(row.get("document_name", "")).strip() or "Unbenanntes Dokument"
        document_key = document_id or document_name
        if not collection or not document_key:
            continue
        group = grouped.setdefault(
            collection,
            {
                "collection": collection,
                "document_count": 0,
                "chunk_count": 0,
                "latest_timestamp": "",
                "documents": [],
            },
        )
        doc = document_lookup.get((collection, document_key))
        if doc is None:
            doc = {
                "id": f"document:{collection}:{document_key}",
                "collection": collection,
                "document_id": document_id,
                "document_name": document_name,
                "label": document_name,
                "chunk_count": 0,
                "latest_timestamp": "",
                "preview": "",
                "source": str(row.get("source", "")).strip() or "n/a",
                "chunks": [],
                "all_chunks": [],
            }
            document_lookup[(collection, document_key)] = doc
            group["documents"].append(doc)
            group["document_count"] += 1
        timestamp = str(row.get("timestamp", "")).strip()
        text = str(row.get("text", "")).strip()
        doc["chunk_count"] += 1
        group["chunk_count"] += 1
        if timestamp and timestamp > str(doc.get("latest_timestamp", "")):
            doc["latest_timestamp"] = timestamp
        if timestamp and timestamp > str(group.get("latest_timestamp", "")):
            group["latest_timestamp"] = timestamp
        if text and not doc.get("preview"):
            doc["preview"] = _memory_preview(text, limit=160)
        chunk_entry = {
            "id": str(row.get("id", "")).strip() or f"{doc['id']}:chunk:{doc['chunk_count']}",
            "label": f"Chunk {doc['chunk_count']}",
            "collection": collection,
            "document_id": document_id,
            "document_name": document_name,
            "chunk_index": int(row.get("chunk_index", 0) or doc["chunk_count"]),
            "chunk_total": int(row.get("chunk_total", 0) or 0),
            "preview": _memory_preview(text, limit=220),
            "timestamp": timestamp,
            "source": str(row.get("source", "")).strip() or "n/a",
        }
        doc["all_chunks"].append(chunk_entry)
        if len(doc["chunks"]) < max_chunks_per_document:
            doc["chunks"].append(chunk_entry)

    groups = list(grouped.values())
    groups.sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
    for group in groups:
        group["display_timestamp"] = _format_display_timestamp(group.get("latest_timestamp"))
        group["documents"].sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
        for doc in group["documents"]:
            doc["display_timestamp"] = _format_display_timestamp(doc.get("latest_timestamp"))
            doc["chunks"].sort(key=lambda item: str(item.get("timestamp", "")))
            doc["all_chunks"].sort(key=lambda item: str(item.get("timestamp", "")))
    return groups


def _memory_browser_node_id(prefix: str, value: str) -> str:
    clean = "".join(char if char.isalnum() else "-" for char in str(value or "").strip().lower())
    clean = "-".join(part for part in clean.split("-") if part)
    return f"{prefix}-{clean[:72] or 'item'}"


def _build_collection_point_entries(brain: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    entries: dict[str, list[dict[str, Any]]] = {}
    for row in list((brain or {}).get("nodes", []) or []):
        collection = str(row.get("collection", "")).strip()
        point_id = str(row.get("id", "")).strip()
        if not collection or not point_id:
            continue
        if _is_document_collection_name(collection) and str(row.get("level", "")).strip() == "chunk":
            continue
        entry = {
            "id": point_id,
            "label": str(row.get("label", "") or row.get("title", "") or row.get("kind", "") or "Entry").strip(),
            "collection": collection,
            "kind": str(row.get("kind", "") or row.get("type", "") or row.get("level", "") or "").strip(),
            "source": str(row.get("source", "") or "").strip(),
            "timestamp": str(row.get("timestamp", "") or "").strip(),
            "preview": _memory_preview(str(row.get("preview", "") or row.get("text", "") or "").strip(), limit=220),
            "learning_effect": str(row.get("learning_effect", "") or "").strip(),
            "learning_purpose": str(row.get("learning_purpose", "") or "").strip(),
            "importance_score": float(row.get("importance_score", 0.0) or 0.0),
            "review_worthy": bool(row.get("review_worthy") is True),
            "synthesis_target": str(row.get("synthesis_target", "") or "").strip(),
        }
        entries.setdefault(collection, []).append(entry)
    for rows in entries.values():
        rows.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return entries


def _build_collection_row_entries(
    rows: list[dict[str, Any]],
    *,
    username: str,
) -> dict[str, list[dict[str, Any]]]:
    entries: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        collection = str(row.get("collection", "")).strip()
        point_id = str(row.get("id", "")).strip()
        if not collection or not point_id:
            continue
        memory_type = str(row.get("type", "")).strip().lower()
        if memory_type == "document" or _is_document_collection_name(collection):
            continue
        if memory_type == "notes" or _is_notes_collection_name(collection, username=username):
            continue
        text = str(row.get("text", "")).strip()
        entry = {
            "id": point_id,
            "label": str(row.get("label", "") or row.get("title", "") or memory_type or "Entry").strip(),
            "collection": collection,
            "kind": memory_type,
            "source": str(row.get("source", "") or "").strip(),
            "timestamp": str(row.get("timestamp", "") or "").strip(),
            "preview": _memory_preview(text, limit=220),
            "learning_effect": str(row.get("learning_effect", "") or "").strip(),
            "learning_purpose": str(row.get("learning_purpose", "") or "").strip(),
            "importance_score": float(row.get("importance_score", 0.0) or 0.0),
            "review_worthy": bool(row.get("review_worthy") is True),
            "synthesis_target": str(row.get("synthesis_target", "") or "").strip(),
        }
        entries.setdefault(collection, []).append(entry)
    for collection_entries in entries.values():
        collection_entries.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return entries


def _build_note_drilldown_groups(
    rows: list[dict[str, Any]],
    *,
    username: str,
    max_chunks_per_note: int = 12,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    note_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        collection = str(row.get("collection", "")).strip()
        if not collection:
            continue
        memory_type = str(row.get("type", "")).strip().lower()
        if memory_type != "notes" and not _is_notes_collection_name(collection, username=username):
            continue
        note_id = str(row.get("note_id", "")).strip()
        note_title = str(row.get("note_title", "")).strip() or _memory_routes_text(
            "de",
            "unnamed_note",
            "Unnamed note",
        )
        note_path = str(row.get("note_path", "")).strip()
        note_key = note_id or note_path or note_title or str(row.get("id", "")).strip()
        if not note_key:
            continue
        group = grouped.setdefault(
            collection,
            {
                "collection": collection,
                "document_count": 0,
                "chunk_count": 0,
                "latest_timestamp": "",
                "documents": [],
            },
        )
        note = note_lookup.get((collection, note_key))
        if note is None:
            note = {
                "id": f"note:{collection}:{note_key}",
                "level": "document",
                "kind": "notes",
                "collection": collection,
                "note_id": note_id,
                "note_title": note_title,
                "note_folder": str(row.get("note_folder", "")).strip(),
                "note_path": note_path,
                "note_tags": list(row.get("note_tags", []) or []) if isinstance(row.get("note_tags", []), list) else [],
                "label": note_title,
                "chunk_count": 0,
                "latest_timestamp": "",
                "preview": "",
                "source": str(row.get("source", "")).strip() or "notes",
                "chunks": [],
                "all_chunks": [],
            }
            note_lookup[(collection, note_key)] = note
            group["documents"].append(note)
            group["document_count"] += 1
        timestamp = str(row.get("timestamp", "")).strip()
        text = str(row.get("text", "")).strip()
        note["chunk_count"] += 1
        group["chunk_count"] += 1
        if timestamp and timestamp > str(note.get("latest_timestamp", "")):
            note["latest_timestamp"] = timestamp
        if timestamp and timestamp > str(group.get("latest_timestamp", "")):
            group["latest_timestamp"] = timestamp
        if text and not note.get("preview"):
            note["preview"] = _memory_preview(text, limit=160)
        chunk_index = _safe_browser_int(row.get("chunk_index"), note["chunk_count"])
        chunk_entry = {
            "id": str(row.get("id", "")).strip() or f"{note['id']}:chunk:{note['chunk_count']}",
            "label": f"Chunk {chunk_index}",
            "collection": collection,
            "kind": "notes",
            "note_id": note_id,
            "note_title": note_title,
            "note_path": note_path,
            "chunk_index": chunk_index,
            "chunk_total": _safe_browser_int(row.get("chunk_total")),
            "preview": _memory_preview(text, limit=220),
            "timestamp": timestamp,
            "source": str(row.get("source", "")).strip() or "notes",
        }
        note["all_chunks"].append(chunk_entry)
        if len(note["chunks"]) < max_chunks_per_note:
            note["chunks"].append(chunk_entry)

    groups = list(grouped.values())
    groups.sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
    for group in groups:
        group["display_timestamp"] = _format_display_timestamp(group.get("latest_timestamp"))
        group["documents"].sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
        for note in group["documents"]:
            note["display_timestamp"] = _format_display_timestamp(note.get("latest_timestamp"))
            note["chunks"].sort(key=lambda item: _safe_browser_int(item.get("chunk_index")))
            note["all_chunks"].sort(key=lambda item: _safe_browser_int(item.get("chunk_index")))
    return groups


def _build_memory_drilldown_browser_snapshot(
    *,
    username: str,
    lang: str,
    collection_stats: list[dict[str, Any]],
    all_collections: list[dict[str, Any]] | None = None,
    document_rows: list[dict[str, Any]],
    collection_rows: list[dict[str, Any]] | None = None,
    brain: dict[str, Any] | None,
) -> dict[str, Any]:
    document_groups = _build_document_drilldown_groups(document_rows)
    note_groups = _build_note_drilldown_groups(list(collection_rows or []), username=username)
    row_entries_by_collection = _build_collection_row_entries(list(collection_rows or []), username=username)
    point_entries_by_collection = _build_collection_point_entries(brain)
    notes_by_collection = {
        str(group.get("collection", "")).strip(): group
        for group in note_groups
        if str(group.get("collection", "")).strip()
    }
    types: dict[str, dict[str, Any]] = {}
    collections: list[dict[str, Any]] = []
    stats_by_name = {
        str(row.get("name", "")).strip(): row
        for row in collection_stats
        if str(row.get("name", "")).strip()
    }
    source_collections = list(all_collections or []) or list(collection_stats)

    for row in source_collections:
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        classification = classify_qdrant_collection(name, username=username)
        stats_row = stats_by_name.get(name, {})
        kind = classification.kind
        if kind == "legacy_memory":
            kind = str(stats_row.get("kind", "") or row.get("kind", "") or "fact").strip().lower() or "fact"
        browser_kind = kind
        points = int(row.get("points", stats_row.get("points", 0)) or 0)
        note_group = notes_by_collection.get(name) if browser_kind == "notes" else None
        collection_documents = list((note_group or {}).get("documents", []) or [])
        collection_entries = (
            []
            if browser_kind == "notes" or collection_documents
            else row_entries_by_collection.get(name, point_entries_by_collection.get(name, []))
        )
        collection_document_count = int((note_group or {}).get("document_count", 0) or 0)
        collection_chunk_count = int((note_group or {}).get("chunk_count", 0) or 0)
        collection_preview = str((note_group or {}).get("display_timestamp", "") or "")
        types.setdefault(
            browser_kind,
            {
                "id": f"type:{browser_kind}",
                "kind": browser_kind,
                "label": _graph_kind_label(browser_kind, lang),
                "points": 0,
                "collection_count": 0,
            },
        )
        types[browser_kind]["points"] += points
        types[browser_kind]["collection_count"] += 1
        collections.append(
            {
                "id": _memory_browser_node_id("collection", name),
                "kind": browser_kind,
                "original_kind": kind,
                "kindLabel": _graph_kind_label(kind, lang),
                "label": name,
                "name": name,
                "points": points,
                "status": str(row.get("status", "") or stats_row.get("status", "") or ""),
                "vectors": int(row.get("vectors", 0) or 0),
                "indexed_vectors": int(row.get("indexed_vectors", 0) or 0),
                "documents": collection_documents,
                "entries": collection_entries,
                "document_count": collection_document_count,
                "chunk_count": collection_chunk_count,
                "preview": collection_preview,
                "href": _memory_collection_link(kind=kind, collection=name),
            }
        )

    document_type = types.setdefault(
        "document",
        {
            "id": "type:document",
            "kind": "document",
            "label": _graph_kind_label("document", lang),
            "points": 0,
            "collection_count": 0,
        },
    )
    known_document_collections = {str(item.get("name", "")).strip() for item in collections if str(item.get("kind")) == "document"}
    document_chunk_total = 0
    for group in document_groups:
        collection = str(group.get("collection", "")).strip()
        document_chunk_total += int(group.get("chunk_count", 0) or 0)
        if collection not in known_document_collections:
            collections.append(
                {
                    "id": _memory_browser_node_id("collection", collection),
                    "kind": "document",
                    "label": collection,
                    "name": collection,
                    "points": int(group.get("chunk_count", 0) or 0),
                    "documents": group.get("documents", []),
                    "entries": point_entries_by_collection.get(collection, []),
                    "document_count": int(group.get("document_count", 0) or 0),
                    "chunk_count": int(group.get("chunk_count", 0) or 0),
                    "preview": str(group.get("display_timestamp", "") or ""),
                    "href": _memory_collection_link(kind="document", collection=collection),
                }
            )
            continue
        for item in collections:
            if str(item.get("name", "")).strip() == collection and str(item.get("kind", "")).strip() == "document":
                item["documents"] = group.get("documents", [])
                item["document_count"] = int(group.get("document_count", 0) or 0)
                item["chunk_count"] = int(group.get("chunk_count", 0) or 0)
                item["points"] = max(int(item.get("points", 0) or 0), int(group.get("chunk_count", 0) or 0))
                item["preview"] = str(group.get("display_timestamp", "") or "")
                break
    document_type["points"] = max(int(document_type.get("points", 0) or 0), document_chunk_total)
    document_type["collection_count"] = max(
        int(document_type.get("collection_count", 0) or 0),
        len(document_groups),
    )
    notes_type = types.setdefault(
        "notes",
        {
            "id": "type:notes",
            "kind": "notes",
            "label": _graph_kind_label("notes", lang),
            "points": 0,
            "collection_count": 0,
        },
    )
    known_notes_collections = {str(item.get("name", "")).strip() for item in collections if str(item.get("kind")) == "notes"}
    notes_chunk_total = 0
    for group in note_groups:
        collection = str(group.get("collection", "")).strip()
        notes_chunk_total += int(group.get("chunk_count", 0) or 0)
        if collection not in known_notes_collections:
            collections.append(
                {
                    "id": _memory_browser_node_id("collection", collection),
                    "kind": "notes",
                    "original_kind": "notes",
                    "kindLabel": _graph_kind_label("notes", lang),
                    "label": collection,
                    "name": collection,
                    "points": int(group.get("chunk_count", 0) or 0),
                    "documents": group.get("documents", []),
                    "entries": [],
                    "document_count": int(group.get("document_count", 0) or 0),
                    "chunk_count": int(group.get("chunk_count", 0) or 0),
                    "preview": str(group.get("display_timestamp", "") or ""),
                    "href": _memory_collection_link(kind="notes", collection=collection),
                }
            )
            continue
        for item in collections:
            if str(item.get("name", "")).strip() == collection and str(item.get("kind", "")).strip() == "notes":
                item["documents"] = group.get("documents", [])
                item["entries"] = []
                item["document_count"] = int(group.get("document_count", 0) or 0)
                item["chunk_count"] = int(group.get("chunk_count", 0) or 0)
                item["points"] = max(int(item.get("points", 0) or 0), int(group.get("chunk_count", 0) or 0))
                item["preview"] = str(group.get("display_timestamp", "") or "")
                break
    notes_type["points"] = max(int(notes_type.get("points", 0) or 0), notes_chunk_total)
    notes_type["collection_count"] = max(
        int(notes_type.get("collection_count", 0) or 0),
        len(note_groups),
    )

    type_items = [item for item in types.values() if int(item.get("points", 0) or 0) > 0 or int(item.get("collection_count", 0) or 0) > 0]
    type_items.sort(key=lambda item: _graph_kind_order(str(item.get("kind", ""))))
    collections.sort(key=lambda item: (_graph_kind_order(str(item.get("kind", ""))), -int(item.get("points", 0) or 0), str(item.get("name", "")).lower()))
    root_points = sum(int(item.get("points", 0) or 0) for item in type_items)
    initial_type = "document" if any(str(item.get("kind", "")) == "document" for item in type_items) else str(type_items[0].get("kind", "all") if type_items else "all")
    return {
        "root": {
            "id": "root",
            "label": username,
            "meta": _msg(
                lang,
                f"{root_points} Punkte · {len(collections)} Collections",
                f"{root_points} points · {len(collections)} collections",
            ),
        },
        "types": type_items,
        "collections": collections,
        "initial_type": initial_type,
        "semantic": brain or {},
    }


def _document_matches_filter(row: dict[str, Any], *, document_id: str = "", document_name: str = "") -> bool:
    clean_document_id = str(document_id or "").strip()
    clean_document_name = str(document_name or "").strip()
    if clean_document_id and str(row.get("document_id", "")).strip() == clean_document_id:
        return True
    if clean_document_name and str(row.get("document_name", "")).strip() == clean_document_name:
        return True
    return False


def _rollup_group_order(level: str) -> int:
    order = {"week": 0, "month": 1}
    return order.get(str(level or "").strip().lower(), 99)


def _rollup_label(level: str) -> str:
    normalized = str(level or "").strip().lower()
    if normalized == "month":
        return "MONAT"
    return "WOCHE"


def _build_rollup_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("source", "")).strip().lower() != "compression":
            continue
        level = str(row.get("rollup_level", "")).strip().lower()
        if level not in {"week", "month"}:
            continue
        bucket = str(row.get("rollup_bucket", "")).strip()
        items.append(
            {
                "id": str(row.get("id", "")).strip(),
                "collection": str(row.get("collection", "")).strip(),
                "level": level,
                "level_label": _rollup_label(level),
                "bucket": bucket,
                "period_start": str(row.get("rollup_period_start", "")).strip(),
                "period_end": str(row.get("rollup_period_end", "")).strip(),
                "source_kind": str(row.get("rollup_source_kind", "")).strip(),
                "source_count": int(row.get("rollup_source_count", 0) or 0),
                "timestamp": str(row.get("timestamp", "")).strip(),
                "display_timestamp": _format_display_timestamp(row.get("timestamp")),
                "preview": _memory_preview(str(row.get("text", "")).strip(), limit=160),
                "title": _memory_title(str(row.get("text", "")).strip(), limit=96),
            }
        )
    items.sort(key=lambda item: (str(item.get("period_end", "")), str(item.get("timestamp", ""))), reverse=True)
    return items


def _build_rollup_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        level = str(entry.get("level", "")).strip().lower()
        if not level:
            continue
        group = grouped.setdefault(
            level,
            {
                "level": level,
                "label": _rollup_label(level),
                "count": 0,
                "entries": [],
            },
        )
        group["count"] += 1
        group["entries"].append(entry)
    items = list(grouped.values())
    items.sort(key=lambda item: (_rollup_group_order(item.get("level", "")), str(item.get("label", ""))))
    return items


def _graph_kind_order(kind: str) -> int:
    order = {
        "fact": 0,
        "preference": 1,
        "session": 2,
        "document": 3,
        "knowledge": 4,
        "self_learning": 5,
        "reflection": 6,
        "learning_event": 7,
        "learning_candidate": 8,
        "learning_active_hint": 9,
        "learning_eval": 10,
        "notes": 11,
        "routing": 12,
        "recipe_experience": 13,
        "system": 14,
        "external": 15,
    }
    return order.get(str(kind or "").strip().lower(), 99)


def _graph_kind_label(kind: str, lang: str | None = None) -> str:
    lang = str(lang or "de").strip().lower() or "de"
    normalized = str(kind or "").strip().lower()
    labels = {
        "fact": _memory_routes_text(lang, "graph.fact", "Facts"),
        "preference": _memory_routes_text(lang, "graph.preference", "Preferences"),
        "session": _memory_routes_text(lang, "graph.session", "Daily context"),
        "document": _memory_routes_text(lang, "graph.document", "Documents"),
        "knowledge": _memory_routes_text(lang, "graph.knowledge", "Knowledge"),
        "self_learning": _memory_routes_text(lang, "graph.self_learning", "Self-Learning"),
        "reflection": _memory_routes_text(lang, "graph.reflection", "Learning"),
        "learning_event": _memory_routes_text(lang, "graph.learning_event", "Learning Events"),
        "learning_candidate": _memory_routes_text(lang, "graph.learning_candidate", "Learning Candidates"),
        "learning_active_hint": _memory_routes_text(lang, "graph.learning_active_hint", "Active Learning Hints"),
        "learning_eval": _memory_routes_text(lang, "graph.learning_eval", "Learning Evals"),
        "notes": _memory_routes_text(lang, "graph.notes", "Notes"),
        "routing": "Routing",
        "recipe_experience": _memory_routes_text(lang, "graph.recipe_experience", "Recipe Experience"),
        "system": _memory_routes_text(lang, "graph.system", "System"),
        "external": "External",
    }
    return labels.get(normalized, normalized.upper() or "Memory")


def _graph_kind_icon(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    icons = {
        "root": "memories",
        "fact": "memories",
        "preference": "settings",
        "session": "activities",
        "document": "files",
        "knowledge": "llm",
        "self_learning": "skills",
        "reflection": "llm",
        "learning_event": "activities",
        "learning_candidate": "skills",
        "learning_active_hint": "llm",
        "learning_eval": "check",
        "notes": "notes",
        "routing": "routing",
        "recipe_experience": "skills",
        "system": "settings",
        "external": "files",
    }
    return icons.get(normalized, "memories")


def _routing_graph_link() -> str:
    return _memory_admin_route("/memories")


def _recipe_experience_graph_link() -> str:
    return _recipes_ui_route("/recipes/mine")


def _memory_setup_graph_link() -> str:
    return f"{_memory_admin_route('/memories/config')}#qdrant-access"


def _memory_graph_link(*, kind: str = "all", collection: str = "") -> str:
    return _memory_admin_route("/memories")


def _memory_collection_link(*, kind: str = "all", collection: str = "") -> str:
    normalized_kind = str(kind or "").strip().lower() or "all"
    if normalized_kind == "notes":
        return _documents_route("/notes")
    if normalized_kind not in {"all", "fact", "preference", "knowledge", "reflection", "learning_event", "learning_candidate", "learning_active_hint", "learning_eval", "document", "session"}:
        normalized_kind = "all"
    return _memory_graph_link(kind=normalized_kind, collection=collection)


def _memory_document_link(
    *,
    collection: str = "",
    document_id: str = "",
    document_name: str = "",
) -> str:
    return _memory_admin_route("/memories")


def _build_memory_graph(
    *,
    username: str,
    lang: str,
    map_rows: list[dict[str, Any]],
    kind_totals: dict[str, int],
    document_groups: list[dict[str, Any]],
    rollup_groups: list[dict[str, Any]],
    notes_rows: list[dict[str, Any]] | None = None,
    routing_rows: list[dict[str, Any]] | None = None,
    system_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    note_items = list(notes_rows or [])
    routing_items = list(routing_rows or [])
    system_items = list(system_rows or [])
    kinds = [kind for kind, points in kind_totals.items() if int(points or 0) > 0]
    if note_items:
        kinds.append("notes")
    if routing_items:
        kinds.append("routing")
    for row in system_items:
        kind = str(row.get("kind", "system")).strip().lower() or "system"
        if kind not in kinds:
            kinds.append(kind)
    if not kinds:
        return {"nodes": [], "edges": [], "width": 0, "height": 0, "has_graph": False}

    kinds.sort(key=_graph_kind_order)
    collection_rows_by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in kinds}
    for row in map_rows:
        kind = str(row.get("kind", "")).strip().lower()
        if kind in collection_rows_by_kind:
            collection_rows_by_kind[kind].append(row)
    for rows in collection_rows_by_kind.values():
        rows.sort(key=lambda item: int(item.get("points", 0) or 0), reverse=True)

    detail_nodes_by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in kinds}
    for kind in kinds:
        if kind == "document":
            for group in document_groups[:4]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(group.get("collection", "")).strip(),
                        "meta": (
                            f"{int(group.get('document_count', 0) or 0)} {_msg(lang, 'Dokumente', 'documents')}"
                            f" · {int(group.get('chunk_count', 0) or 0)} Chunks"
                        ),
                        "href": _memory_collection_link(
                            kind="document",
                            collection=str(group.get("collection", "")).strip(),
                        ),
                        "variant": "collection",
                    }
                )
            continue
        if kind == "knowledge":
            for group in rollup_groups[:2]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(group.get("label", "")).strip(),
                        "meta": _msg(
                            lang,
                            f"{int(group.get('count', 0) or 0)} Rollups",
                            f"{int(group.get('count', 0) or 0)} rollups",
                        ),
                        "href": _memory_graph_link(kind="knowledge"),
                        "variant": "rollup",
                    }
                )
        if kind == "notes":
            for row in note_items[:3]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(row.get("name", "")).strip(),
                        "meta": (
                            f"{int(row.get('points', 0) or 0)} {_msg(lang, 'Punkte', 'points')}"
                            f" · {int(row.get('share_pct', 0) or 0)}%"
                        ),
                        "href": str(row.get("browse_url", "")).strip() or _documents_route("/notes"),
                        "variant": "notes",
                    }
                )
            continue
        if kind == "routing":
            for row in routing_items[:3]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(row.get("name", "")).strip(),
                        "meta": (
                            f"{int(row.get('points', 0) or 0)} {_msg(lang, 'Punkte', 'points')}"
                            f" · {int(row.get('share_pct', 0) or 0)}%"
                        ),
                        "href": str(row.get("browse_url", "")).strip() or _routing_graph_link(),
                        "variant": "routing",
                    }
                )
            continue
        if kind in {"recipe_experience", "system"}:
            for row in [item for item in system_items if str(item.get("kind", "")).strip().lower() == kind][:3]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(row.get("name", "")).strip(),
                        "meta": (
                            f"{int(row.get('points', 0) or 0)} {_msg(lang, 'Punkte', 'points')}"
                            f" · {int(row.get('share_pct', 0) or 0)}%"
                        ),
                        "href": str(row.get("browse_url", "")).strip() or _memory_setup_graph_link(),
                        "variant": kind,
                    }
                )
            continue
        for row in collection_rows_by_kind.get(kind, [])[:2]:
            detail_nodes_by_kind[kind].append(
                {
                    "label": str(row.get("name", "")).strip(),
                    "meta": (
                        f"{int(row.get('points', 0) or 0)} {_msg(lang, 'Punkte', 'points')}"
                        f" · {int(row.get('share_pct', 0) or 0)}%"
                    ),
                    "href": _memory_collection_link(
                        kind=kind,
                        collection=str(row.get("name", "")).strip(),
                    ),
                    "variant": "collection",
                }
            )

    column_gap = 184
    root_y = 70
    type_y = 188
    detail_start_y = 316
    detail_gap_y = 100
    root_width = 190
    type_width = 150
    detail_width = 148
    stage_padding = 72
    width = max(732, stage_padding * 2 + max(1, len(kinds) - 1) * column_gap + type_width)
    start_x = width / 2 if len(kinds) == 1 else stage_padding + type_width / 2
    step = 0 if len(kinds) == 1 else (width - stage_padding * 2 - type_width) / max(1, len(kinds) - 1)
    max_detail_rows = max((len(items) for items in detail_nodes_by_kind.values()), default=0)
    height = 414 + max(0, max_detail_rows - 1) * detail_gap_y

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, float]] = []
    memory_total_points = sum(int(value or 0) for value in kind_totals.values())
    notes_total_points = sum(int(row.get("points", 0) or 0) for row in note_items)
    routing_total_points = sum(int(row.get("points", 0) or 0) for row in routing_items)
    system_total_points = sum(int(row.get("points", 0) or 0) for row in system_items)
    root_meta = _msg(lang, f"{memory_total_points} Punkte im Memory", f"{memory_total_points} points in memory")
    if notes_total_points > 0:
        root_meta += _msg(lang, f" · {notes_total_points} Notes-Punkte", f" · {notes_total_points} notes points")
    if routing_total_points > 0:
        root_meta += _msg(lang, f" · {routing_total_points} Routing-Punkte", f" · {routing_total_points} routing points")
    if system_items:
        root_meta += _msg(lang, f" · {len(system_items)} System-Collections", f" · {len(system_items)} system collections")
    nodes.append(
        {
            "id": "graph-root",
            "kind": "root",
            "label": username,
            "meta": root_meta,
            "left": round(width / 2 - root_width / 2, 2),
            "top": 20,
            "width": root_width,
            "href": _memory_graph_link(),
            "variant": "root",
            "icon": _graph_kind_icon("root"),
        }
    )

    for index, kind in enumerate(kinds):
        x_center = start_x + index * step
        type_id = f"graph-kind-{kind}"
        nodes.append(
            {
                "id": type_id,
                "kind": kind,
                "label": _graph_kind_label(kind, lang),
                "meta": (
                    _memory_routes_text(lang, "graph.routing_points", "{points} points · System", points=routing_total_points)
                    if kind == "routing"
                    else _memory_routes_text(
                        lang,
                        "graph.recipe_experience_points",
                        "{points} points · Learning",
                        points=sum(
                            int(row.get("points", 0) or 0)
                            for row in system_items
                            if str(row.get("kind", "")).strip().lower() == "recipe_experience"
                        ),
                    )
                    if kind == "recipe_experience"
                    else _memory_routes_text(lang, "graph.system_points", "{points} points · System", points=system_total_points)
                    if kind == "system"
                    else _memory_routes_text(lang, "graph.notes_points", "{points} points · Notes", points=notes_total_points)
                    if kind == "notes"
                    else _memory_routes_text(lang, "graph.points", "{points} points", points=int(kind_totals.get(kind, 0) or 0))
                ),
                "left": round(x_center - type_width / 2, 2),
                "top": round(type_y - 38, 2),
                "width": type_width,
                "href": _routing_graph_link()
                if kind == "routing"
                else _recipe_experience_graph_link()
                if kind == "recipe_experience"
                else _memory_setup_graph_link()
                if kind == "system"
                else "/notes"
                if kind == "notes"
                else _memory_graph_link(kind=kind if kind != "knowledge" else "knowledge"),
                "variant": "type",
                "icon": _graph_kind_icon(kind),
            }
        )
        edges.append(
            {
                "x1": round(width / 2, 2),
                "y1": root_y + 38,
                "x2": round(x_center, 2),
                "y2": type_y - 8,
            }
        )
        for detail_index, item in enumerate(detail_nodes_by_kind.get(kind, [])):
            detail_y = detail_start_y + detail_index * detail_gap_y
            nodes.append(
                {
                    "id": f"{type_id}-detail-{detail_index}",
                    "kind": kind,
                    "label": str(item.get("label", "")).strip(),
                    "meta": str(item.get("meta", "")).strip(),
                    "left": round(x_center - detail_width / 2, 2),
                    "top": round(detail_y - 28, 2),
                    "width": detail_width,
                    "href": str(item.get("href", "")).strip(),
                    "variant": str(item.get("variant", "detail")).strip(),
                    "icon": _graph_kind_icon(kind),
                }
            )
            edges.append(
                {
                    "x1": round(x_center, 2),
                    "y1": type_y + 34,
                    "x2": round(x_center, 2),
                    "y2": round(detail_y - 6, 2),
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "width": int(width),
        "height": int(height),
        "has_graph": True,
    }


def _brain_graph_preview(value: Any, limit: int = 180) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _brain_graph_kind_label(kind: str, lang: str | None = None) -> str:
    return _graph_kind_label(kind, lang)


def _brain_graph_vector(value: Any) -> list[float]:
    if isinstance(value, dict):
        value = next((item for item in value.values() if isinstance(item, list)), None)
    if not isinstance(value, list):
        return []
    vector: list[float] = []
    for item in value:
        if isinstance(item, (int, float)):
            vector.append(float(item))
    return vector


def _brain_graph_int(*values: Any) -> int:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _brain_graph_cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    if length <= 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(length))
    left_norm = math.sqrt(sum(left[index] * left[index] for index in range(length)))
    right_norm = math.sqrt(sum(right[index] * right[index] for index in range(length)))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _brain_graph_collection_label(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return "Collection"
    if len(clean) <= 34:
        return clean
    return f"{clean[:31]}..."


def _build_qdrant_brain_graph(
    rows: list[dict[str, Any]],
    *,
    lang: str,
    max_nodes: int = 96,
    max_edges: int = 180,
) -> dict[str, Any]:
    prepared: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        collection = str(row.get("collection", "")).strip()
        point_id = str(row.get("id", "")).strip()
        if not collection or not point_id:
            continue
        key = (collection, point_id)
        if key in seen:
            continue
        vector = _brain_graph_vector(row.get("vector"))
        if not vector:
            continue
        seen.add(key)
        kind = str(row.get("type", "")).strip().lower() or "unknown"
        chunk_index = _brain_graph_int(row.get("chunk_index"))
        document_name = str(row.get("document_name", "")).strip()
        title = (
            str(row.get("note_title", "")).strip()
            or (f"Chunk {chunk_index}" if document_name and chunk_index > 0 else "")
            or document_name
            or _brain_graph_preview(row.get("text"), 54)
            or point_id
        )
        prepared.append(
            {
                "raw": row,
                "vector": vector,
                "kind": kind,
                "collection": collection,
                "id": point_id,
                "label": title,
            }
        )
        if len(prepared) >= max_nodes:
            break

    if not prepared:
        return {
            "has_graph": False,
            "nodes": [],
            "edges": [],
            "width": 0,
            "height": 0,
            "sample_count": 0,
            "edge_count": 0,
            "collection_count": 0,
            "error": "",
        }

    collection_indexes: dict[str, list[int]] = {}
    for index, item in enumerate(prepared):
        collection_indexes.setdefault(str(item["collection"]), []).append(index)

    required_edges: dict[tuple[int, int], float] = {}
    optional_edges: dict[tuple[int, int], float] = {}

    def remember_edge(
        edges: dict[tuple[int, int], float],
        left_index: int,
        right_index: int,
        similarity: float,
    ) -> None:
        a, b = sorted((left_index, right_index))
        if a == b:
            return
        # Keep very weak but still best-known links visible enough to shape the graph.
        score = max(0.12, min(1.0, similarity))
        edges[(a, b)] = max(edges.get((a, b), 0.0), score)

    for indexes in collection_indexes.values():
        if len(indexes) < 2:
            continue
        pair_scores: list[tuple[int, int, float]] = []
        neighbor_scores: dict[int, list[tuple[int, float]]] = {index: [] for index in indexes}
        for offset, left_index in enumerate(indexes):
            left = prepared[left_index]
            for right_index in indexes[offset + 1 :]:
                right = prepared[right_index]
                similarity = _brain_graph_cosine(left["vector"], right["vector"])
                pair_scores.append((left_index, right_index, similarity))
                neighbor_scores[left_index].append((right_index, similarity))
                neighbor_scores[right_index].append((left_index, similarity))
        pair_scores.sort(key=lambda item: item[2], reverse=True)

        parent = {index: index for index in indexes}

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left_index: int, right_index: int) -> bool:
            left_root = find(left_index)
            right_root = find(right_index)
            if left_root == right_root:
                return False
            parent[right_root] = left_root
            return True

        # Qdrant's visualization feels connected because every point keeps a nearest-neighbor backbone.
        for left_index, right_index, similarity in pair_scores:
            if union(left_index, right_index):
                remember_edge(required_edges, left_index, right_index, similarity)

        k_neighbors = 7 if len(indexes) <= 48 else 5
        for left_index, scores in neighbor_scores.items():
            scores.sort(key=lambda item: item[1], reverse=True)
            for rank, (right_index, similarity) in enumerate(scores[:k_neighbors]):
                if rank < 2 or similarity >= 0.30:
                    remember_edge(optional_edges, left_index, right_index, similarity)

    combined_edges: dict[tuple[int, int], float] = dict(required_edges)
    optional_ranked = sorted(optional_edges.items(), key=lambda item: item[1], reverse=True)
    for edge_key, score in optional_ranked:
        if len(combined_edges) >= max_edges:
            break
        combined_edges[edge_key] = max(combined_edges.get(edge_key, 0.0), score)
    ranked_edges = sorted(
        [(a, b, score) for (a, b), score in combined_edges.items()],
        key=lambda item: item[2],
        reverse=True,
    )[:max_edges]

    width = 1180
    height = 760
    center_x = width / 2
    center_y = height / 2
    kinds = sorted({item["kind"] for item in prepared}, key=_graph_kind_order)
    kind_centers: dict[str, tuple[float, float]] = {}
    cluster_radius = 230 if len(kinds) > 1 else 0
    for index, kind in enumerate(kinds):
        angle = -math.pi / 2 + (2 * math.pi * index / max(1, len(kinds)))
        kind_centers[kind] = (
            center_x + math.cos(angle) * cluster_radius,
            center_y + math.sin(angle) * cluster_radius,
        )
    positions: list[list[float]] = []
    for index, item in enumerate(prepared):
        cluster_x, cluster_y = kind_centers.get(item["kind"], (center_x, center_y))
        angle = 2 * math.pi * index / max(1, len(prepared))
        positions.append([cluster_x + math.cos(angle) * 54, cluster_y + math.sin(angle) * 54])

    adjacency: dict[int, list[tuple[int, float]]] = {index: [] for index in range(len(prepared))}
    for a, b, score in ranked_edges:
        adjacency[a].append((b, score))
        adjacency[b].append((a, score))

    for _ in range(70):
        forces = [[0.0, 0.0] for _ in prepared]
        for index, item in enumerate(prepared):
            target_x, target_y = kind_centers.get(item["kind"], (center_x, center_y))
            forces[index][0] += (target_x - positions[index][0]) * 0.008
            forces[index][1] += (target_y - positions[index][1]) * 0.008
        for left_index in range(len(prepared)):
            for right_index in range(left_index + 1, len(prepared)):
                dx = positions[left_index][0] - positions[right_index][0]
                dy = positions[left_index][1] - positions[right_index][1]
                dist_sq = max(120.0, dx * dx + dy * dy)
                force = 820.0 / dist_sq
                dist = math.sqrt(dist_sq)
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                forces[left_index][0] += fx
                forces[left_index][1] += fy
                forces[right_index][0] -= fx
                forces[right_index][1] -= fy
        for left_index, neighbors in adjacency.items():
            for right_index, score in neighbors:
                dx = positions[right_index][0] - positions[left_index][0]
                dy = positions[right_index][1] - positions[left_index][1]
                forces[left_index][0] += dx * 0.010 * score
                forces[left_index][1] += dy * 0.010 * score
        for index in range(len(prepared)):
            positions[index][0] = max(54, min(width - 54, positions[index][0] + forces[index][0]))
            positions[index][1] = max(54, min(height - 54, positions[index][1] + forces[index][1]))

    nodes: list[dict[str, Any]] = []
    collection_summaries: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(prepared):
        row = item["raw"]
        x, y = positions[index]
        text = _brain_graph_preview(row.get("text"), 220)
        source = str(row.get("source", "")).strip() or "n/a"
        document_name = str(row.get("document_name", "")).strip()
        chunk_index = _brain_graph_int(row.get("chunk_index"))
        chunk_total = _brain_graph_int(row.get("chunk_total"))
        note_title = str(row.get("note_title", "")).strip()
        note_folder = str(row.get("note_folder", "")).strip()
        rollup_level = str(row.get("rollup_level", "")).strip()
        detail_parts = [item["collection"], _brain_graph_kind_label(item["kind"], lang), source]
        if document_name:
            detail_parts.append(document_name)
        if chunk_index > 0 and chunk_total > 0:
            detail_parts.append(f"Chunk {chunk_index}/{chunk_total}")
        elif chunk_index > 0:
            detail_parts.append(f"Chunk {chunk_index}")
        if note_title:
            detail_parts.append(note_title)
        if note_folder:
            detail_parts.append(note_folder)
        if rollup_level:
            detail_parts.append(f"Rollup: {rollup_level}")
        summary = collection_summaries.setdefault(
            item["collection"],
            {
                "id": f"brain-collection-{len(collection_summaries)}",
                "collection": item["collection"],
                "label": _brain_graph_collection_label(item["collection"]),
                "point_count": 0,
                "kinds": {},
                "preview": "",
            },
        )
        summary["point_count"] += 1
        summary["kinds"][item["kind"]] = int(summary["kinds"].get(item["kind"], 0) or 0) + 1
        if not summary["preview"]:
            summary["preview"] = text
        nodes.append(
            {
                "id": f"brain-node-{index}",
                "index": index,
                "kind": item["kind"],
                "level": "chunk" if document_name and chunk_index > 0 else item["kind"],
                "label": _brain_graph_preview(item["label"], 48),
                "meta": " · ".join(part for part in detail_parts if part),
                "preview": text,
                "collection": item["collection"],
                "point_id": item["id"],
                "source": source,
                "document_id": str(row.get("document_id", "")).strip(),
                "document_name": document_name,
                "chunk_index": chunk_index,
                "chunk_total": chunk_total,
                "learning_effect": str(row.get("learning_effect", "") or "").strip(),
                "learning_purpose": str(row.get("learning_purpose", "") or "").strip(),
                "importance_score": float(row.get("importance_score", 0.0) or 0.0),
                "review_worthy": bool(row.get("review_worthy") is True),
                "synthesis_target": str(row.get("synthesis_target", "") or "").strip(),
                "x": round(x, 2),
                "y": round(y, 2),
                "radius": 8 if item["kind"] in {"document", "notes"} else 7,
            }
        )
    collections: list[dict[str, Any]] = []
    for summary in collection_summaries.values():
        kinds_meta = ", ".join(
            f"{_brain_graph_kind_label(kind, lang)}: {count}"
            for kind, count in sorted(summary["kinds"].items(), key=lambda item: _graph_kind_order(item[0]))
        )
        collections.append(
            {
                "id": summary["id"],
                "collection": summary["collection"],
                "label": summary["label"],
                "point_count": summary["point_count"],
                "meta": kinds_meta,
                "preview": summary["preview"],
            }
        )
    collections.sort(key=lambda item: (-int(item["point_count"]), str(item["collection"]).lower()))

    edges = [
        {
            "source": a,
            "target": b,
            "score": round(score, 4),
            "x1": round(positions[a][0], 2),
            "y1": round(positions[a][1], 2),
            "x2": round(positions[b][0], 2),
            "y2": round(positions[b][1], 2),
            "width": round(0.55 + max(0.0, min(1.0, score)) * 1.25, 2),
        }
        for a, b, score in ranked_edges
    ]
    return {
        "has_graph": True,
        "nodes": nodes,
        "edges": edges,
        "width": width,
        "height": height,
        "sample_count": len(nodes),
        "edge_count": len(edges),
        "collection_count": len({item["collection"] for item in prepared}),
        "collections": collections,
    }


def _build_memory_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        kind = str(row.get("type", "")).strip().lower() or "unknown"
        entry = grouped.setdefault(
            kind,
            {
                "type": kind,
                "label": str(row.get("label", kind.upper())),
                "count": 0,
                "rows": [],
            },
        )
        entry["count"] += 1
        entry["rows"].append(row)
    items = list(grouped.values())
    items.sort(key=lambda item: (_memory_group_order(item.get("type", "")), str(item.get("label", ""))))
    return items


def _memories_redirect(
    *,
    filter_type: str,
    query: str,
    collection_filter: str,
    document_id: str = "",
    document_name: str = "",
    page: int,
    limit: int,
    sort: str,
    info: str = "",
    error: str = "",
) -> RedirectResponse:
    return RedirectResponse(
        url=_memory_admin_redirect_url("/memories", info=info, error=error),
        status_code=303,
    )


def _memories_map_redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    return RedirectResponse(
        url=_memory_admin_redirect_url("/memories", info=info, error=error),
        status_code=303,
    )


def _memories_overview_redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    return RedirectResponse(
        url=_memory_admin_redirect_url("/memories", info=info, error=error),
        status_code=303,
    )


def _memories_import_redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    return RedirectResponse(
        url=_memory_admin_redirect_url("/memories/import", info=info, error=error),
        status_code=303,
    )


def _memories_create_redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    return RedirectResponse(
        url=_memory_admin_redirect_url("/memories/create", info=info, error=error),
        status_code=303,
    )


def _memories_maintenance_redirect(
    *,
    info: str = "",
    error: str = "",
    focus: str = "",
) -> RedirectResponse:
    url = _memory_admin_redirect_url("/memories/maintenance", info=info, error=error)
    clean_focus = str(focus or "").strip().lower()
    if clean_focus in {"rollup", "reset", "cleanup", "reindex"}:
        url += ("&" if "?" in url else "?") + f"focus={quote_plus(clean_focus)}"
        url += f"#maint-{clean_focus}"
    return RedirectResponse(
        url=url,
        status_code=303,
    )


def _memories_auto_memory_redirect(*, saved: bool = False, error: str = "") -> RedirectResponse:
    url = _memory_admin_route("/memories/auto-memory")
    params: list[str] = []
    if saved:
        params.append("saved=1")
    if error:
        params.append(f"error={quote_plus(error)}")
    if params:
        url += "?" + "&".join(params)
    return RedirectResponse(url=url, status_code=303)


def _memories_config_redirect(
    *,
    saved: bool = False,
    error: str = "",
    compress_result: str = "",
    anchor: str = "",
) -> RedirectResponse:
    url = _memory_admin_route("/memories/config")
    params: list[str] = []
    if saved:
        params.append("saved=1")
    if compress_result:
        params.append(f"compress_result={quote_plus(compress_result)}")
    if error:
        params.append(f"error={quote_plus(error)}")
    if params:
        url += "?" + "&".join(params)
    clean_anchor = str(anchor or "").strip().lstrip("#")
    if clean_anchor:
        url += f"#{clean_anchor}"
    return RedirectResponse(url=url, status_code=303)


def _memories_intake_redirect(source_view: str, *, info: str = "", error: str = "") -> RedirectResponse:
    normalized = str(source_view or "").strip().lower()
    if normalized == "import":
        return _memories_import_redirect(info=info, error=error)
    if normalized == "create":
        return _memories_create_redirect(info=info, error=error)
    if normalized == "overview":
        return _memories_overview_redirect(info=info, error=error)
    return _memories_overview_redirect(info=info, error=error)


def _memory_export_filename(username: str, filter_type: str, query: str) -> str:
    slug = _slug_user_id(username)
    scope = str(filter_type or "all").strip().lower() or "all"
    if scope not in {"all", "fact", "preference", "session", "knowledge", "document"}:
        scope = "all"
    suffix = "search" if str(query or "").strip() else "all"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"aria-memory-{slug}-{scope}-{suffix}-{stamp}.json"


def _document_collection_prefix() -> str:
    return "aria_docs"


def _default_document_collection_for_user(username: str) -> str:
    slug = _slug_user_id(username)
    prefix = _document_collection_prefix()
    return f"{prefix}_{slug}" if slug else prefix


def _is_document_collection_name(name: str) -> bool:
    clean = str(name or "").strip().lower()
    prefix = _document_collection_prefix()
    return bool(clean) and (clean == prefix or clean.startswith(f"{prefix}_"))


def _normalize_document_collection_name(raw_name: str, sanitize_collection_name: CollectionNameSanitizer) -> str:
    clean = sanitize_collection_name(raw_name)
    if not clean:
        return ""
    if _is_document_collection_name(clean):
        return clean
    return sanitize_collection_name(f"{_document_collection_prefix()}_{clean}")


def _document_collection_names(collection_names: list[str]) -> list[str]:
    rows = [str(name or "").strip() for name in collection_names if _is_document_collection_name(str(name or "").strip())]
    return sorted(set(name for name in rows if name))


def _is_routing_collection_name(name: str) -> bool:
    return is_routing_qdrant_collection(name)


def _is_recipe_experience_collection_name(name: str) -> bool:
    return is_recipe_experience_qdrant_collection(name)


def _is_notes_collection_name(name: str, *, username: str = "") -> bool:
    return is_notes_qdrant_collection(name, username=username)


def _build_notes_collection_rows(
    overview_rows: list[dict[str, Any]],
    *,
    username: str,
    browse_url: str = "",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in overview_rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen or not _is_notes_collection_name(name, username=username):
            continue
        seen.add(name)
        items.append(
            {
                "name": name,
                "kind": "notes",
                "points": int(row.get("points", 0) or 0),
                "status": str(row.get("status", "ok")).strip() or "ok",
                "browse_url": str(browse_url or "").strip() or _documents_route("/notes"),
            }
        )
    items.sort(key=lambda item: (-(int(item.get("points", 0) or 0)), str(item.get("name", "")).lower()))
    total_points = int(sum(int(item.get("points", 0) or 0) for item in items))
    max_points = max((int(item.get("points", 0) or 0) for item in items), default=0)
    for item in items:
        points = int(item.get("points", 0) or 0)
        item["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        item["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
    return items


def _build_routing_collection_rows(
    overview_rows: list[dict[str, Any]],
    *,
    known_user_collection_names: set[str] | None = None,
    browse_url: str = "",
) -> list[dict[str, Any]]:
    blocked = {str(name or "").strip() for name in (known_user_collection_names or set()) if str(name or "").strip()}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in overview_rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen or name in blocked or not _is_routing_collection_name(name):
            continue
        seen.add(name)
        items.append(
            {
                "name": name,
                "kind": "routing",
                "points": int(row.get("points", 0) or 0),
                "status": str(row.get("status", "ok")).strip() or "ok",
                "browse_url": str(browse_url or "").strip(),
            }
        )
    items.sort(key=lambda item: (-(int(item.get("points", 0) or 0)), str(item.get("name", "")).lower()))
    total_points = int(sum(int(item.get("points", 0) or 0) for item in items))
    max_points = max((int(item.get("points", 0) or 0) for item in items), default=0)
    for item in items:
        points = int(item.get("points", 0) or 0)
        item["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        item["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
    return items


def _build_system_collection_rows(
    overview_rows: list[dict[str, Any]],
    *,
    known_collection_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    blocked = {str(name or "").strip() for name in (known_collection_names or set()) if str(name or "").strip()}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in overview_rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen or name in blocked:
            continue
        classification = classify_qdrant_collection(name)
        if not classification.is_aria or classification.kind not in {"recipe_experience", "system"}:
            continue
        kind = classification.kind if classification.kind == "recipe_experience" else "system"
        seen.add(name)
        items.append(
            {
                "name": name,
                "kind": kind,
                "points": int(row.get("points", 0) or 0),
                "status": str(row.get("status", "ok")).strip() or "ok",
                "browse_url": _recipe_experience_graph_link() if kind == "recipe_experience" else _memory_setup_graph_link(),
            }
        )
    items.sort(key=lambda item: (str(item.get("kind", "")), -(int(item.get("points", 0) or 0)), str(item.get("name", "")).lower()))
    total_points = int(sum(int(item.get("points", 0) or 0) for item in items))
    max_points = max((int(item.get("points", 0) or 0) for item in items), default=0)
    for item in items:
        points = int(item.get("points", 0) or 0)
        item["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        item["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
    return items


def _resolve_document_target_collection(
    *,
    request: Request,
    username: str,
    selected_collection: str,
    new_collection_name: str,
    existing_collections: list[str],
    sanitize_collection_name: CollectionNameSanitizer,
    get_effective_memory_collection: EffectiveCollectionResolver,
) -> str:
    lang = str(getattr(getattr(request, "state", object()), "lang", "de") or "de")
    existing_document_collections = set(_document_collection_names(existing_collections))

    normalized_new = _normalize_document_collection_name(new_collection_name, sanitize_collection_name)
    if normalized_new:
        return normalized_new

    clean_selected = sanitize_collection_name(selected_collection)
    if clean_selected:
        if not _is_document_collection_name(clean_selected):
            raise ValueError(_memory_routes_text(lang, "error.document_collections_only", "Please use document collections only."))
        if clean_selected not in existing_document_collections:
            raise ValueError(_memory_routes_text(lang, "error.document_collection_missing", "The selected document collection no longer exists."))
        return clean_selected

    active_collection = sanitize_collection_name(get_effective_memory_collection(request, username))
    if active_collection and _is_document_collection_name(active_collection):
        return active_collection

    return _default_document_collection_for_user(username)


def _build_compression_result_message(stats: dict[str, Any], compress_after_days: int, *, lang: str = "de") -> str:
    moved = list(stats.get("compressed_collections", []) or [])
    removed = list(stats.get("removed_collections", []) or [])
    skipped_recent = list(stats.get("skipped_recent", []) or [])
    failed_delete = list(stats.get("failed_delete", []) or [])
    moved_total = int(stats.get("compressed_week", 0) or 0) + int(stats.get("compressed_month", 0) or 0)

    if moved_total <= 0:
        if skipped_recent:
            preview = ", ".join(skipped_recent[:3])
            return _memory_routes_text(
                lang,
                "compression.no_move_recent",
                (
                    "Rollup finished: nothing moved. {count} daily collections are younger than "
                    "{days} days or still active daily context. Examples: {preview}"
                ),
                count=len(skipped_recent),
                days=compress_after_days,
                preview=preview,
            )
        return _memory_routes_text(lang, "compression.no_move", "Rollup finished: nothing to move.")

    parts = [
        _memory_routes_text(
            lang,
            "compression.summary",
            "Rollup finished: moved={moved}, removed={removed}",
            moved=moved_total,
            removed=int(stats.get("collections_removed", 0) or 0),
        ),
    ]
    if moved:
        parts.append(_memory_routes_text(lang, "compression.moved", "Moved: {items}", items=", ".join(moved[:3])))
    if skipped_recent:
        parts.append(
            _memory_routes_text(
                lang,
                "compression.skipped_recent",
                "Unchanged ({count}): younger than {days} days or current daily context",
                count=len(skipped_recent),
                days=compress_after_days,
            )
        )
    if failed_delete:
        parts.append(
            _memory_routes_text(
                lang,
                "compression.failed_delete",
                "Not deleted ({count}): {items}",
                count=len(failed_delete),
                items=", ".join(failed_delete[:3]),
            )
        )
    if removed and len(removed) != len(moved):
        parts.append(_memory_routes_text(lang, "compression.removed", "Removed: {items}", items=", ".join(removed[:3])))
    return " | ".join(parts)


def register_memories_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_settings: SettingsGetter,
    get_pipeline: PipelineGetter,
    get_username_from_request: UsernameResolver,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
    qdrant_overview: QdrantOverviewLoader,
    qdrant_dashboard_url: QdrantDashboardUrlResolver,
    parse_collection_day_suffix: CollectionDayParser,
    sanitize_collection_name: CollectionNameSanitizer,
    default_memory_collection_for_user: DefaultCollectionResolver,
    get_effective_memory_collection: EffectiveCollectionResolver,
    read_raw_config: RawConfigReader,
    write_raw_config: RawConfigWriter,
    reload_runtime: RuntimeReloader,
    resolve_prompt_file: PromptFileResolver,
    get_secure_store: SecureStoreGetter,
    memory_collection_cookie: str,
    inventory_index_status_builder: InventoryIndexStatusBuilder = build_inventory_index_status,
) -> None:
    def _cookie_name_for_request(request: Request, key: str, fallback: str) -> str:
        cookie_names = getattr(request.state, "cookie_names", {}) or {}
        if isinstance(cookie_names, dict):
            candidate = str(cookie_names.get(key, "") or "").strip()
            if candidate:
                return candidate
        return fallback

    @app.get("/memories", response_class=HTMLResponse)
    @app.get("/memories/overview", response_class=HTMLResponse)
    async def memories_overview_page(
        request: Request,
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        is_admin = _is_admin_request(request, get_auth_session_from_request, sanitize_role)
        overview = await qdrant_overview(request)
        active_collection = get_effective_memory_collection(request, username)
        default_collection = default_memory_collection_for_user(username)
        default_document_collection = _default_document_collection_for_user(username)
        collection_names = [
            str(row.get("name", "")).strip()
            for row in overview.get("collections", [])
            if str(row.get("name", "")).strip()
        ]
        document_collections = _document_collection_names(collection_names)
        collection_stats: list[dict[str, Any]] = []
        if getattr(pipeline, "memory_skill", None):
            with suppress(Exception):
                collection_stats = await pipeline.memory_skill.get_user_collection_stats(username)
        document_rows: list[dict[str, Any]] = []
        if getattr(pipeline, "memory_skill", None):
            with suppress(Exception):
                document_rows = await pipeline.memory_skill.list_memories_global(
                    user_id=username,
                    type_filter="document",
                    limit=5000,
                )
        memory_browser_rows: list[dict[str, Any]] = []
        if getattr(pipeline, "memory_skill", None):
            with suppress(Exception):
                memory_browser_rows = await pipeline.memory_skill.list_memories_global(
                    user_id=username,
                    type_filter="all",
                    limit=10000,
                )
            if memory_browser_rows:
                document_rows = [
                    row
                    for row in memory_browser_rows
                    if str(row.get("type", "")).strip().lower() == "document"
                    or _is_document_collection_name(str(row.get("collection", "")).strip())
                ]
        memory_browser_collection = str(request.query_params.get("collection", "") or "").strip()
        memory_browser_document = str(request.query_params.get("document", "") or "").strip()
        memory_browser_chunk = str(request.query_params.get("chunk", "") or "").strip()
        memory_browser_entry = str(request.query_params.get("entry", "") or "").strip()
        memory_browser_mode = str(request.query_params.get("mode", "") or "").strip().lower()
        user_memory_points = sum(int(row.get("points", 0) or 0) for row in collection_stats)
        map_snapshot = await _build_memory_map_snapshot(
            pipeline=pipeline,
            username=username,
            lang=lang,
            overview=overview,
            is_admin=is_admin,
            settings=settings,
            parse_collection_day_suffix=parse_collection_day_suffix,
            preferred_graph_collections=[memory_browser_collection] if memory_browser_collection else [],
        )
        routing_rows = list(map_snapshot.get("routing_rows", []) or [])
        system_rows = list(map_snapshot.get("system_rows", []) or [])
        overview_checks = [
            {
                "title": "Qdrant",
                "status": "ok" if overview.get("reachable") else "error",
                "summary": _msg(lang, "Erreichbar", "Reachable") if overview.get("reachable") else _msg(lang, "Nicht erreichbar", "Not reachable"),
                "meta": _msg(lang, f"{len(collection_names)} Collections", f"{len(collection_names)} collections"),
            },
            {
                "title": _msg(lang, "Aktive Collection", "Active collection"),
                "status": "ok" if active_collection else "warn",
                "summary": active_collection or default_collection,
                "meta": f"Default: {default_collection}",
            },
            {
                "title": "User Memory",
                "status": "ok" if user_memory_points > 0 else "warn",
                "summary": str(user_memory_points),
                "meta": _msg(lang, f"{len(collection_stats)} Collections mit Punkten", f"{len(collection_stats)} collections with points"),
            },
            {
                "title": _msg(lang, "Dokumente", "Documents"),
                "status": "ok" if document_collections else "warn",
                "summary": default_document_collection,
                "meta": _msg(lang, f"{len(document_collections)} Dokument-Collections", f"{len(document_collections)} document collections"),
            },
            {
                "title": _msg(lang, "System-Collections", "System collections"),
                "status": "ok" if system_rows or routing_rows else "warn",
                "summary": str(len(system_rows) + len(routing_rows)),
                "meta": _msg(lang, "Routing, Recipe Experience und weitere ARIA-Collections", "Routing, Recipe Experience, and other ARIA collections"),
            },
        ]
        memory_browser = _build_memory_drilldown_browser_snapshot(
            username=username,
            lang=lang,
            collection_stats=collection_stats,
            all_collections=list(overview.get("collections", []) or []),
            document_rows=document_rows,
            collection_rows=memory_browser_rows,
            brain=dict(map_snapshot.get("memory_graph", {}).get("brain", {}) or {}),
        )
        if memory_browser_collection:
            for browser_collection in memory_browser.get("collections", []):
                collection_name = str(browser_collection.get("name", "") or "").strip()
                collection_id = str(browser_collection.get("id", "") or "").strip()
                if memory_browser_collection not in {collection_name, collection_id}:
                    continue
                memory_browser["initial_type"] = str(browser_collection.get("kind", "") or memory_browser.get("initial_type", ""))
                memory_browser["initial_collection"] = collection_id
                memory_browser["initial_collection_name"] = collection_name
                if memory_browser_entry:
                    for entry in browser_collection.get("entries", []) or []:
                        if str(entry.get("id", "") or "").strip() == memory_browser_entry:
                            memory_browser["initial_entry"] = memory_browser_entry
                            memory_browser["initial_document"] = ""
                            memory_browser["initial_chunk"] = ""
                            break
                if not memory_browser.get("initial_entry"):
                    selected_document_id = ""
                    selected_chunk_id = ""
                    for document_item in browser_collection.get("documents", []) or []:
                        document_id = str(document_item.get("id", "") or "").strip()
                        chunks = list(document_item.get("all_chunks", []) or document_item.get("chunks", []) or [])
                        if memory_browser_chunk:
                            for chunk_item in chunks:
                                chunk_id = str(chunk_item.get("id", "") or "").strip()
                                if chunk_id == memory_browser_chunk:
                                    selected_document_id = document_id
                                    selected_chunk_id = chunk_id
                                    break
                            if selected_chunk_id:
                                break
                        if memory_browser_document and document_id == memory_browser_document:
                            selected_document_id = document_id
                            if memory_browser_mode == "semantic" and chunks:
                                selected_chunk_id = str(chunks[0].get("id", "") or "").strip()
                            break
                    if selected_document_id:
                        memory_browser["initial_document"] = selected_document_id
                    if selected_chunk_id:
                        memory_browser["initial_chunk"] = selected_chunk_id
                break
        if memory_browser_mode not in {"structure", "semantic"}:
            memory_browser_mode = "structure"
        if memory_browser_mode == "semantic" and not (memory_browser.get("initial_chunk") or memory_browser.get("initial_entry")):
            memory_browser_mode = "structure"
        memory_browser["can_delete"] = is_admin
        memory_browser["csrf_token"] = str(getattr(request.state, "csrf_token", "") or "")
        next_steps = [
            {
                "icon": "plus",
                "title": _memory_routes_text(
                    lang,
                    "next_step_memory_title_empty" if user_memory_points <= 0 else "next_step_memory_title_more",
                    "Create first memory" if user_memory_points <= 0 else "Add memory",
                ),
                "desc": _memory_routes_text(
                    lang,
                    "next_step_memory_desc_empty" if user_memory_points <= 0 else "next_step_memory_desc_more",
                    "Start with one small fact or preference so ARIA has something concrete in memory."
                    if user_memory_points <= 0
                    else "Add another fact or preference directly from the hub without jumping into the explorer first.",
                ),
                "href": _memory_admin_route("/memories/create"),
                "badge": _memory_routes_text(lang, "next_step_memory_badge", "Right here"),
            },
            {
                "icon": "upload",
                "title": _memory_routes_text(
                    lang,
                    "next_step_document_title_empty" if not document_collections else "next_step_document_title_more",
                    "Import first document" if not document_collections else "Import another document",
                ),
                "desc": _memory_routes_text(
                    lang,
                    "next_step_document_desc_empty" if not document_collections else "next_step_document_desc_more",
                    "PDFs, Markdown, and text files land in a document collection and then show up in the explorer and the map."
                    if not document_collections
                    else "Keep using the hub as the intake point for new PDFs or text files without opening setup.",
                ),
                "href": f"{_memory_admin_route('/memories/import')}#document-import",
                "badge": default_document_collection,
            },
            {
                "icon": "memories",
                "title": _memory_routes_text(lang, "next_step_explorer_title", "Open explorer"),
                "desc": _memory_routes_text(
                    lang,
                    "next_step_explorer_desc",
                    "Filter facts, documents, rollups, and day context so entries do not blur together later.",
                ),
                "href": _memory_admin_route("/memories"),
                "badge": _memory_routes_text(lang, "next_step_explorer_badge", "Search & filters"),
            },
        ]
        return templates.TemplateResponse(
            request=request,
            name=_memory_admin_template("memories_overview.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "memory",
                "info_message": info,
                "error_message": error,
                "active_collection": active_collection,
                "default_collection": default_collection,
                "default_document_collection": default_document_collection,
                "memory_cfg": settings.memory,
                "qdrant_overview": overview,
                "collection_count": len(collection_names),
                "document_collection_count": len(document_collections),
                "routing_collection_count": len(routing_rows),
                "system_collection_count": len(system_rows),
                "user_memory_points": user_memory_points,
                "overview_checks": overview_checks,
                "next_steps": next_steps,
                "memory_graph": map_snapshot["memory_graph"],
                "memory_browser": memory_browser,
                "memory_browser_fullscreen": str(request.query_params.get("fullscreen", "")).strip().lower() in {"1", "true", "yes"},
                "memory_browser_initial_mode": memory_browser_mode,
                "show_qdrant_brain": False,
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "document_collections": document_collections,
                "active_document_collection": (
                    active_collection
                    if _is_document_collection_name(active_collection)
                    else default_document_collection
                ),
                "supported_upload_suffixes": supported_upload_suffixes(),
            },
        )

    @app.get("/memories/import", response_class=HTMLResponse)
    async def memories_import_page(
        request: Request,
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        username = get_username_from_request(request) or "web"
        overview = await qdrant_overview(request)
        active_collection = get_effective_memory_collection(request, username)
        default_document_collection = _default_document_collection_for_user(username)
        collection_names = [
            str(row.get("name", "")).strip()
            for row in overview.get("collections", [])
            if str(row.get("name", "")).strip()
        ]
        document_collections = _document_collection_names(collection_names)
        return templates.TemplateResponse(
            request=request,
            name=_memory_admin_template("memories_import.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "import",
                "info_message": info,
                "error_message": error,
                "active_collection": active_collection,
                "default_document_collection": default_document_collection,
                "document_collections": document_collections,
                "active_document_collection": (
                    active_collection
                    if _is_document_collection_name(active_collection)
                    else default_document_collection
                ),
                "supported_upload_suffixes": supported_upload_suffixes(),
            },
        )

    @app.get("/memories/create", response_class=HTMLResponse)
    async def memories_create_page(
        request: Request,
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        username = get_username_from_request(request) or "web"
        return templates.TemplateResponse(
            request=request,
            name=_memory_admin_template("memories_create.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "create",
                "info_message": info,
                "error_message": error,
            },
        )

    @app.get("/memories/explorer", response_class=HTMLResponse)
    async def memories_page(
        request: Request,
        type: str = "all",
        q: str = "",
        collection_filter: str = "",
        document_id: str = "",
        document_name: str = "",
        limit: int = 120,
        page: int = 1,
        sort: str = "updated_desc",
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        return _memories_overview_redirect(info=info, error=error)

    @app.get("/memories/export")
    async def memories_export(
        request: Request,
        type: str = "all",
        q: str = "",
        collection_filter: str = "",
        sort: str = "updated_desc",
    ) -> JSONResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        sort_key = _normalize_memory_sort(sort)
        selected_collection = sanitize_collection_name(collection_filter)
        all_rows: list[dict[str, Any]] = []
        if pipeline.memory_skill:
            if q.strip():
                all_rows = await pipeline.memory_skill.search_memories(
                    user_id=username,
                    query=q.strip(),
                    type_filter=type,
                    top_k=5000,
                )
                if selected_collection:
                    all_rows = [
                        row
                        for row in all_rows
                        if str(row.get("collection", "")).strip() == selected_collection
                    ]
            else:
                all_rows = await pipeline.memory_skill.list_memories_global(
                    user_id=username,
                    type_filter=type,
                    limit=10000,
                    collection_filter=selected_collection,
                )
        _sort_memory_rows(all_rows, sort_key)
        payload = {
            "schema_version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "user_id": username,
            "filter": {
                "type": str(type or "all").strip().lower() or "all",
                "query": str(q or "").strip(),
                "sort": sort_key,
            },
            "count": len(all_rows),
            "items": all_rows,
        }
        return JSONResponse(
            content=payload,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{_memory_export_filename(username, type, q)}"'
                )
            },
        )

    @app.get("/memories/map", response_class=HTMLResponse)
    async def memories_map_page(request: Request) -> RedirectResponse:
        info = str(request.query_params.get("info") or "").strip()
        error = str(request.query_params.get("error") or "").strip()
        return _memories_map_redirect(info=info, error=error)

    @app.post("/memories/delete")
    async def memories_delete(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return _memories_overview_redirect(error="Memory nicht aktiv")
        ok = await pipeline.memory_skill.delete_memory_point(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
        )
        if ok:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                info=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "info.entry_deleted", "Entry deleted"),
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            document_id=document_id,
            document_name=document_name,
            page=page,
            limit=limit,
            sort=sort,
            error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.entry_delete_failed", "Entry could not be deleted"),
        )

    @app.post("/memories/delete-document")
    async def memories_delete_document(
        request: Request,
        collection: str = Form(...),
        document_id: str = Form(""),
        document_name: str = Form(""),
        view: str = Form(""),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        selected_document_id: str = Form(""),
        selected_document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return _memories_overview_redirect(error="Memory nicht aktiv")
        removed = await pipeline.memory_skill.delete_document(
            user_id=username,
            collection=sanitize_collection_name(collection),
            document_id=str(document_id).strip(),
            document_name=str(document_name).strip(),
        )
        target_view = str(view or "").strip().lower()
        if removed > 0:
            if target_view == "map":
                return _memories_map_redirect(info=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "info.document_removed", "Document removed · {count} chunks deleted", count=removed))
            return _memories_redirect(
                filter_type="document" if str(type).strip().lower() in {"all", "document"} else type,
                query=q,
                collection_filter=collection_filter,
                document_id="",
                document_name="",
                page=1,
                limit=limit,
                sort=sort,
                info=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "info.document_removed", "Document removed · {count} chunks deleted", count=removed),
            )
        if target_view == "map":
            return _memories_map_redirect(error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.document_remove_failed", "Document could not be removed"))
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            document_id=selected_document_id,
            document_name=selected_document_name,
            page=page,
            limit=limit,
            sort=sort,
            error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.document_remove_failed", "Document could not be removed"),
        )

    async def _memory_browser_json_payload(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _memory_browser_csrf_valid(request: Request, payload: dict[str, Any]) -> bool:
        submitted = request.headers.get("x-csrf-token") or payload.get("csrf_token")
        expected = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        return _is_valid_csrf_submission(str(submitted or ""), expected)

    @app.post("/memories/browser/delete-point")
    async def memories_browser_delete_point(request: Request) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return JSONResponse(
                content={"ok": False, "error": _memory_routes_text(lang, "error.admin_required", "Admin access required")},
                status_code=403,
            )
        payload = await _memory_browser_json_payload(request)
        if not _memory_browser_csrf_valid(request, payload):
            return JSONResponse(
                content={"ok": False, "error": _memory_routes_text(lang, "error.csrf_failed", "Security check failed. Please reload the page.")},
                status_code=403,
            )
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        collection = sanitize_collection_name(str(payload.get("collection", "") or ""))
        point_id = str(payload.get("point_id", "") or "").strip()
        if not getattr(pipeline, "memory_skill", None):
            return JSONResponse(content={"ok": False, "error": "memory_inactive"}, status_code=503)
        if not collection or not point_id:
            return JSONResponse(content={"ok": False, "error": "missing_target"}, status_code=400)
        ok = await pipeline.memory_skill.delete_memory_point(
            user_id=username,
            collection=collection,
            point_id=point_id,
        )
        return JSONResponse(content={"ok": bool(ok), "collection": collection, "point_id": point_id}, status_code=200 if ok else 404)

    @app.post("/memories/browser/delete-document")
    async def memories_browser_delete_document(request: Request) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return JSONResponse(
                content={"ok": False, "error": _memory_routes_text(lang, "error.admin_required", "Admin access required")},
                status_code=403,
            )
        payload = await _memory_browser_json_payload(request)
        if not _memory_browser_csrf_valid(request, payload):
            return JSONResponse(
                content={"ok": False, "error": _memory_routes_text(lang, "error.csrf_failed", "Security check failed. Please reload the page.")},
                status_code=403,
            )
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        collection = sanitize_collection_name(str(payload.get("collection", "") or ""))
        document_id = str(payload.get("document_id", "") or "").strip()
        document_name = str(payload.get("document_name", "") or "").strip()
        if not getattr(pipeline, "memory_skill", None):
            return JSONResponse(content={"ok": False, "error": "memory_inactive"}, status_code=503)
        if not collection or not (document_id or document_name):
            return JSONResponse(content={"ok": False, "error": "missing_target"}, status_code=400)
        removed = await pipeline.memory_skill.delete_document(
            user_id=username,
            collection=collection,
            document_id=document_id,
            document_name=document_name,
        )
        return JSONResponse(
            content={"ok": removed > 0, "collection": collection, "document_id": document_id, "document_name": document_name, "removed": removed},
            status_code=200 if removed > 0 else 404,
        )

    @app.post("/memories/edit")
    async def memories_edit(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        text: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not pipeline.memory_skill:
            return _memories_overview_redirect(error="Memory nicht aktiv")
        clean_text = str(text).strip()
        if not clean_text:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.memory_text_empty", "Memory text must not be empty"),
            )
        ok = await pipeline.memory_skill.update_memory_point(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            text=clean_text,
        )
        if ok:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                info=_msg(lang, "Eintrag aktualisiert", "Entry updated"),
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            document_id=document_id,
            document_name=document_name,
            page=page,
            limit=limit,
            sort=sort,
            error=_msg(lang, "Eintrag konnte nicht aktualisiert werden", "Entry could not be updated"),
        )

    @app.post("/memories/create")
    async def memories_create(
        request: Request,
        kind: str = Form("fact"),
        subject: str = Form(""),
        predicate: str = Form(""),
        value: str = Form(""),
        source_view: str = Form("create"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        source_key = str(source_view or "").strip().lower()
        intake_view = source_key if source_key in {"overview", "import", "create"} else "create"
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not pipeline.memory_skill:
            return _memories_intake_redirect(
                intake_view,
                error=_memory_routes_text(lang, "error.memory_backend_unavailable", "Memory backend is currently unavailable."),
            )

        clean_kind = str(kind or "").strip().lower()
        clean_subject = str(subject or "").strip()
        clean_predicate = str(predicate or "").strip()
        clean_value = str(value or "").strip()
        if clean_kind not in {"fact", "preference"}:
            return _memories_intake_redirect(
                intake_view,
                error=_memory_routes_text(lang, "error.personal_claim_kind_invalid", "Please choose fact or preference."),
            )
        if not clean_subject or not clean_predicate or not clean_value:
            return _memories_intake_redirect(
                intake_view,
                error=_memory_routes_text(
                    lang,
                    "error.personal_claim_fields_required",
                    "Subject, predicate and value are required.",
                ),
            )
        clean_subject = clean_subject[:160]
        clean_predicate = clean_predicate[:160]
        clean_value = clean_value[:700]

        def collection_for_user(name: str) -> str:
            resolver = getattr(pipeline, name, None)
            if not callable(resolver):
                resolver = getattr(pipeline, f"_{name}", None)
            if not callable(resolver):
                raise RuntimeError("memory_capture_collection_unavailable")
            collection = str(resolver(username) or "").strip()
            if not collection:
                raise RuntimeError("memory_capture_collection_unavailable")
            return collection

        claim = {
            "claim_kind": clean_kind,
            "subject": clean_subject or "user",
            "predicate": clean_predicate,
            "value": clean_value,
            "scope": "global",
            "explicit": True,
            "explicit_user_statement": True,
            "authority": "explicit_user",
            "risk": "low",
            "confidence": 1.0,
            "source": "manual_ui",
        }

        try:
            result = await store_personal_claim(
                memory_skill=pipeline.memory_skill,
                llm_client=getattr(pipeline, "llm_client", None),
                claim=claim,
                user_id=username,
                facts_collection=collection_for_user("facts_collection_for_user"),
                preferences_collection=collection_for_user("preferences_collection_for_user"),
                request_id="",
            )
            if bool(result.get("stored")):
                return _memories_intake_redirect(
                    intake_view,
                    info=_memory_routes_text(lang, "info.personal_claim_saved", "Personal claim saved."),
                )
            reason = str(result.get("reason") or "claim_store_failed").strip()[:120]
            store_error = str(result.get("store_error") or "").strip()[:240]
            detail = ": ".join(part for part in (reason, store_error) if part)
            message = _memory_routes_text(lang, "error.personal_claim_save_failed", "Could not save personal claim.")
            return _memories_intake_redirect(
                intake_view,
                error=f"{message} ({detail})" if detail else message,
            )
        except Exception as exc:  # noqa: BLE001
            return _memories_intake_redirect(
                intake_view,
                error=_friendly_memory_error(lang, exc, "Memory konnte nicht gespeichert werden.", "Could not save memory."),
            )

    @app.post("/memories/upload")
    async def memories_upload(request: Request) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        try:
            form = await request.form()
        except Exception:
            return _memories_redirect(
                filter_type="all",
                query="",
                collection_filter="",
                page=1,
                limit=50,
                sort="updated_desc",
                error=_msg(
                    lang,
                    "Upload-Formular konnte nicht gelesen werden. Bitte Seite neu laden und erneut versuchen.",
                    "Could not read the upload form. Please reload the page and try again.",
                ),
            )

        collection = str(form.get("collection", "") or "")
        new_collection_name = str(form.get("new_collection_name", "") or "")
        type = str(form.get("type", "all") or "all")
        q = str(form.get("q", "") or "")
        collection_filter = str(form.get("collection_filter", "") or "")
        document_id = str(form.get("document_id", "") or "")
        document_name = str(form.get("document_name", "") or "")
        source_view = str(form.get("source_view", "explorer") or "explorer").strip().lower()
        page = _coerce_form_int(form.get("page"), 1)
        limit = _coerce_form_int(form.get("limit"), 50)
        sort = _normalize_memory_sort(str(form.get("sort", "updated_desc") or "updated_desc"))
        csrf_token = str(form.get("csrf_token", "") or "")
        document_file = form.get("document_file") or form.get("file")

        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            if source_view in {"overview", "import"}:
                return _memories_intake_redirect(
                    source_view,
                    error=_memory_routes_text(lang, "error.csrf_failed", "Security check failed. Please reload the page.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.csrf_failed", "Security check failed. Please reload the page."),
            )
        if not pipeline.memory_skill:
            if source_view in {"overview", "import"}:
                return _memories_intake_redirect(
                    source_view,
                    error=_memory_routes_text(lang, "error.memory_backend_unavailable", "Memory backend is currently unavailable.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.memory_backend_unavailable", "Memory backend is currently unavailable."),
            )
        if not _is_uploaded_file(document_file):
            if source_view in {"overview", "import"}:
                return _memories_intake_redirect(source_view, error=_memory_routes_text(lang, "error.choose_file", "Please choose a file."))
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.choose_file", "Please choose a file."),
            )

        try:
            overview = await qdrant_overview(request)
            existing_collection_names = [
                str(row.get("name", "")).strip()
                for row in overview.get("collections", [])
                if str(row.get("name", "")).strip()
            ]
            raw = await document_file.read()
            prepared = prepare_uploaded_document(
                filename=document_file.filename or "",
                data=raw,
                content_type=getattr(document_file, "content_type", "") or "",
            )
            target_collection = _resolve_document_target_collection(
                request=request,
                username=username,
                selected_collection=collection,
                new_collection_name=new_collection_name,
                existing_collections=existing_collection_names,
                sanitize_collection_name=sanitize_collection_name,
                get_effective_memory_collection=get_effective_memory_collection,
            )
            result = await pipeline.memory_skill.store_document(
                user_id=username,
                document=prepared,
                base_collection=target_collection,
            )
            if not result.success:
                raise ValueError(result.error or _msg(lang, "Dokument konnte nicht importiert werden.", "Could not import document."))
            chunk_count = int((result.metadata or {}).get("chunk_count", 0) or 0)
            if source_view in {"overview", "import"}:
                return _memories_intake_redirect(
                    source_view,
                    info=_msg(
                        lang,
                        f"Dokument importiert: {prepared.filename} · {chunk_count} Chunks in {target_collection}",
                        f"Document imported: {prepared.filename} · {chunk_count} chunks into {target_collection}",
                    )
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id="",
                document_name="",
                page=1,
                limit=limit,
                sort=sort,
                info=_msg(
                    lang,
                    f"Dokument importiert: {prepared.filename} · {chunk_count} Chunks in {target_collection}",
                    f"Document imported: {prepared.filename} · {chunk_count} chunks into {target_collection}",
                ),
            )
        except (DocumentIngestError, ValueError) as exc:
            if source_view in {"overview", "import"}:
                return _memories_intake_redirect(
                    source_view,
                    error=str(exc).strip() or _memory_routes_text(lang, "error.document_import_failed", "Could not import document.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=str(exc).strip() or _memory_routes_text(lang, "error.document_import_failed", "Could not import document."),
            )
        except Exception as exc:  # noqa: BLE001
            if source_view in {"overview", "import"}:
                return _memories_intake_redirect(
                    source_view,
                    error=_friendly_memory_error(lang, exc, _memory_routes_text(lang, "error.document_import_failed_short", "Document import failed."), "Document import failed.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_friendly_memory_error(lang, exc, _memory_routes_text(lang, "error.document_import_failed_short", "Document import failed."), "Document import failed."),
            )

    @app.get("/memories/maintenance", response_class=HTMLResponse)
    async def memories_maintenance_page(
        request: Request,
        info: str = "",
        error: str = "",
        focus: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        username = get_username_from_request(request) or "web"
        inventory_index_status: dict[str, Any] = {}
        if bool(getattr(request.state, "can_access_advanced_config", False)):
            inventory_index_status = await inventory_index_status_builder(settings)
        return templates.TemplateResponse(
            request=request,
            name=_memory_admin_template("memories_maintenance.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "maintenance",
                "info_message": info,
                "error_message": error,
                "focus": str(focus or "").strip().lower(),
                "inventory_index_status": inventory_index_status,
            },
        )

    @app.post("/memories/maintenance")
    async def memories_maintenance_run(
        request: Request,
        source_view: str = Form(""),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            if str(source_view or "").strip().lower() == "maintenance":
                return _memories_maintenance_redirect(error="Memory nicht aktiv", focus="rollup")
            return _memories_overview_redirect(error="Memory nicht aktiv")
        try:
            session_cfg = settings.memory.collections.sessions
            result = await pipeline.memory_skill.execute(
                query="",
                params={
                    "action": "compress_sessions",
                    "user_id": username,
                    "compress_after_days": int(getattr(session_cfg, "compress_after_days", 7)),
                    "monthly_after_days": int(getattr(session_cfg, "monthly_after_days", 30)),
                },
            )
            if result.success:
                if str(source_view or "").strip().lower() == "maintenance":
                    return _memories_maintenance_redirect(info=result.content, focus="rollup")
                return _memories_redirect(
                    filter_type=type,
                    query=q,
                    collection_filter=collection_filter,
                    document_id=document_id,
                    document_name=document_name,
                    page=1,
                    limit=limit,
                    sort=sort,
                    info=result.content,
                )
            message = result.error or _memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.compression_failed", "Compression failed")
            if str(source_view or "").strip().lower() == "maintenance":
                return _memories_maintenance_redirect(error=message, focus="rollup")
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=1,
                limit=limit,
                sort=sort,
                error=message,
            )
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Komprimierung konnte nicht gestartet werden.", "Could not start compression.")
            if str(source_view or "").strip().lower() == "maintenance":
                return _memories_maintenance_redirect(error=error, focus="rollup")
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=1,
                limit=limit,
                sort=sort,
                error=error,
            )

    @app.post("/memories/maintenance/reset-learning-suggestions", response_model=None)
    async def memories_reset_learning_suggestions(
        request: Request,
        csrf_token: str = Form(""),
    ) -> RedirectResponse | JSONResponse:
        del csrf_token  # Validated by the global authenticated-form middleware.
        if get_auth_session_from_request(request) is None:
            return JSONResponse(status_code=401, content={"code": "login_required"})
        user_id = get_username_from_request(request)
        if not user_id:
            return JSONResponse(status_code=401, content={"code": "login_required"})
        pipeline = get_pipeline()
        runtime_root = Path(getattr(pipeline, "_project_root", Path.cwd())) / "data" / "runtime"
        claim_store = ObservedClaimStore(runtime_root / "observed_claims.json")
        sequence_store = ObservedSequenceStore(runtime_root / "observed_sequences.json")
        removed = claim_store.clear_user(user_id) + sequence_store.clear_user(user_id)
        lang = str(getattr(request.state, "lang", "de") or "de")
        info = _memory_routes_text(
            lang,
            "info.learning_suggestions_reset" if removed else "info.learning_suggestions_reset_empty",
            "Learning suggestions reset: {count}." if removed else "Nothing to reset.",
            count=removed,
        )
        return _memories_maintenance_redirect(info=info, focus="reset")

    @app.post("/memories/maintenance/cleanup-legacy-learning", response_model=None)
    async def memories_cleanup_legacy_learning(
        request: Request,
        csrf_token: str = Form(""),
    ) -> RedirectResponse | JSONResponse:
        del csrf_token  # Validated by the global authenticated-form middleware.
        if get_auth_session_from_request(request) is None:
            return JSONResponse(status_code=401, content={"code": "login_required"})
        user_id = get_username_from_request(request)
        if not user_id:
            return JSONResponse(status_code=401, content={"code": "login_required"})

        removable_kinds = {
            "learning_candidate",
            "learning_active_hint",
            "learning_eval",
            "learning_event",
            "reflection",
        }
        user_suffix = f"_{_slug_user_id(user_id)}"
        removed_names: list[str] = []
        pipeline = get_pipeline()
        qdrant = getattr(getattr(pipeline, "memory_skill", None), "qdrant", None)
        try:
            collection_response = await qdrant.get_collections() if qdrant is not None else None
        except Exception:  # noqa: BLE001
            collection_response = None
        for item in list(getattr(collection_response, "collections", ()) or ()):
            name = str(getattr(item, "name", "") or "").strip()
            if not name or not name.lower().endswith(user_suffix):
                continue
            classification = classify_qdrant_collection(name, username=user_id)
            if classification.kind not in removable_kinds:
                continue
            try:
                if not await qdrant.collection_exists(collection_name=name):
                    continue
                await qdrant.delete_collection(collection_name=name)
            except Exception:  # noqa: BLE001
                continue
            removed_names.append(name)

        lang = str(getattr(request.state, "lang", "de") or "de")
        info = _memory_routes_text(
            lang,
            "info.legacy_learning_cleanup" if removed_names else "info.legacy_learning_cleanup_empty",
            (
                "Legacy learning collections removed: {count}. {names}"
                if removed_names
                else "Nothing to clean up."
            ),
            count=len(removed_names),
            names=", ".join(removed_names[:8]),
        )
        return _memories_maintenance_redirect(info=info, focus="cleanup")

    @app.get("/memories/config", response_class=HTMLResponse)
    @app.get("/config/memory", response_class=HTMLResponse)
    async def config_memory_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        compress_result: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        username = get_username_from_request(request) or "web"
        overview = await qdrant_overview(request)
        return templates.TemplateResponse(
            request=request,
            name=_memory_admin_template("config_memory.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "maintenance",
                "saved": bool(saved),
                "error_message": error,
                "collections": [row["name"] for row in overview.get("collections", [])],
                "default_collection": default_memory_collection_for_user(username),
                "active_collection": get_effective_memory_collection(request, username),
                "memory_cfg": settings.memory,
                "index_cfg": getattr(settings, "inventory_index", None),
                "qdrant_overview": overview,
                "has_qdrant_api_key": bool(getattr(settings.memory, "qdrant_api_key", "")),
                "qdrant_api_key_value": str(getattr(settings.memory, "qdrant_api_key", "") or ""),
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "compress_result": compress_result,
            },
        )

    @app.get("/memories/auto-memory", response_class=HTMLResponse)
    async def memories_auto_memory_page(
        request: Request,
        saved: int = 0,
        error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        username = get_username_from_request(request) or "web"
        pipeline = get_pipeline()
        memory_skill = getattr(pipeline, "memory_skill", None)
        list_personal_claims = getattr(memory_skill, "list_personal_claims", None)
        personal_claims = (
            await list_personal_claims(user_id=username, limit=500)
            if callable(list_personal_claims)
            else []
        )
        for claim in personal_claims:
            claim["runtime_state"] = personal_claim_payload_lifecycle_state(claim)
            claim["review_due"] = personal_claim_payload_review_due(claim)
        return templates.TemplateResponse(
            request=request,
            name=_memory_admin_template("memories_auto_memory.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "personal_claims": personal_claims,
                "personal_active_claim_count": sum(
                    row.get("runtime_state") == "effective"
                    for row in personal_claims
                ),
                "personal_scheduled_claim_count": sum(
                    row.get("runtime_state") == "scheduled"
                    for row in personal_claims
                ),
                "personal_expired_claim_count": sum(
                    row.get("runtime_state") == "expired"
                    for row in personal_claims
                ),
                "personal_review_due_claim_count": sum(
                    row.get("review_due") is True
                    for row in personal_claims
                ),
                "personal_suspended_claim_count": sum(
                    str(row.get("claim_status") or "").strip().lower() == "suspended"
                    for row in personal_claims
                ),
            },
        )

    @app.post("/memories/auto-memory/delete-point")
    async def memories_auto_memory_delete_point(
        request: Request,
        collection: str = Form(""),
        point_id: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        expected = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected):
            return _memories_auto_memory_redirect(error="Security check failed. Please reload the page.")
        clean_collection = sanitize_collection_name(collection)
        allowed_prefixes = ("aria_learning_",)
        if not clean_collection.startswith(allowed_prefixes) or not str(point_id or "").strip():
            return _memories_auto_memory_redirect(error="invalid_learning_point")
        pipeline = get_pipeline()
        memory_skill = getattr(pipeline, "memory_skill", None)
        if memory_skill is None:
            return _memories_auto_memory_redirect(error="memory_inactive")
        username = get_username_from_request(request) or "web"
        deleted = await memory_skill.delete_memory_point(username, clean_collection, point_id)
        return _memories_auto_memory_redirect(saved=True) if deleted else _memories_auto_memory_redirect(error="learning_point_not_found")

    @app.post("/memories/auto-memory/claim-action")
    async def memories_auto_memory_claim_action(
        request: Request,
        collection: str = Form(""),
        point_id: str = Form(""),
        decision: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        expected = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected):
            return _memories_auto_memory_redirect(error="csrf_failed")
        settings = get_settings()
        collections_cfg = getattr(getattr(settings, "memory", None), "collections", None)
        allowed_prefixes = (
            str(getattr(getattr(collections_cfg, "facts", None), "prefix", "") or "aria_facts"),
            str(getattr(getattr(collections_cfg, "preferences", None), "prefix", "") or "aria_preferences"),
        )
        clean_collection = sanitize_collection_name(collection)
        clean_point_id = str(point_id or "").strip()
        clean_decision = str(decision or "").strip().lower()
        if (
            not clean_collection.startswith(tuple(f"{prefix}_" for prefix in allowed_prefixes))
            or not clean_point_id
            or clean_decision not in {"suspend", "reactivate", "pause", "resume", "complete", "reopen"}
        ):
            return _memories_auto_memory_redirect(error="invalid_personal_claim_action")
        pipeline = get_pipeline()
        memory_skill = getattr(pipeline, "memory_skill", None)
        username = get_username_from_request(request) or "web"
        point = await memory_skill.get_memory_point(username, clean_collection, clean_point_id) if memory_skill else None
        if not point or str(point.get("personal_claim_contract") or "") != "personal_claim_v1":
            return _memories_auto_memory_redirect(error="personal_claim_not_found")
        current_status = str(point.get("claim_status") or "").strip().lower()
        claim_kind = str(point.get("claim_kind") or "").strip().lower()
        lifecycle_decisions = {
            ("active", "pause"): "paused",
            ("paused", "resume"): "active",
            ("active", "complete"): "completed",
            ("paused", "complete"): "completed",
            ("completed", "reopen"): "active",
        }
        lifecycle_target = lifecycle_decisions.get((current_status, clean_decision))
        if clean_decision in {"pause", "resume", "complete", "reopen"}:
            if claim_kind not in {"goal", "project"} or not lifecycle_target:
                return _memories_auto_memory_redirect(error="personal_claim_status_conflict")
        if clean_decision == "suspend" and current_status != "active":
            return _memories_auto_memory_redirect(error="personal_claim_status_conflict")
        if clean_decision in {"reactivate", "resume", "reopen"}:
            if current_status != "suspended":
                if clean_decision == "reactivate":
                    return _memories_auto_memory_redirect(error="personal_claim_status_conflict")
            candidate = {**point, "claim_status": "active"}
            if personal_claim_payload_lifecycle_state(candidate) == "expired":
                return _memories_auto_memory_redirect(error="personal_claim_expired")
            list_personal_claims = getattr(memory_skill, "list_personal_claims", None)
            claims = await list_personal_claims(user_id=username, limit=500) if callable(list_personal_claims) else []
            conflicting_active = any(
                str(row.get("claim_status") or "").strip().lower() == "active"
                and str(row.get("claim_key") or "") == str(point.get("claim_key") or "")
                and str(row.get("id") or row.get("point_id") or "") != clean_point_id
                for row in claims
            )
            if conflicting_active:
                return _memories_auto_memory_redirect(error="personal_claim_status_conflict")
        now = datetime.now(timezone.utc).isoformat()
        if clean_decision == "suspend":
            updates = {
                "claim_status": "suspended",
                "claim_suspension_reason": "manual_user_control",
                "claim_suspended_at": now,
            }
        elif clean_decision == "reactivate":
            updates = {
                "claim_status": "active",
                "claim_suspension_reason": "",
                "claim_reactivated_at": now,
            }
        else:
            updates = {
                "claim_status": lifecycle_target,
                "claim_lifecycle_changed_at": now,
                "claim_lifecycle_change": clean_decision,
            }
        updated = await memory_skill.update_memory_point_payload(
            username,
            clean_collection,
            clean_point_id,
            updates,
        )
        return _memories_auto_memory_redirect(saved=True) if updated else _memories_auto_memory_redirect(error="personal_claim_action_failed")

    @app.post("/memories/auto-memory/correct-claim")
    async def memories_auto_memory_correct_claim(
        request: Request,
        collection: str = Form(""),
        point_id: str = Form(""),
        corrected_value: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        expected = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected):
            return _memories_auto_memory_redirect(error="csrf_failed")
        settings = get_settings()
        collections_cfg = getattr(getattr(settings, "memory", None), "collections", None)
        facts_prefix = str(getattr(getattr(collections_cfg, "facts", None), "prefix", "") or "aria_facts")
        preferences_prefix = str(
            getattr(getattr(collections_cfg, "preferences", None), "prefix", "") or "aria_preferences"
        )
        clean_collection = sanitize_collection_name(collection)
        clean_point_id = str(point_id or "").strip()
        clean_value = " ".join(str(corrected_value or "").strip().split())
        if (
            not clean_collection.startswith((f"{facts_prefix}_", f"{preferences_prefix}_"))
            or not clean_point_id
            or not clean_value
            or len(clean_value) > 700
        ):
            return _memories_auto_memory_redirect(error="invalid_personal_claim_correction")
        pipeline = get_pipeline()
        memory_skill = getattr(pipeline, "memory_skill", None)
        username = get_username_from_request(request) or "web"
        point = await memory_skill.get_memory_point(username, clean_collection, clean_point_id) if memory_skill else None
        original = personal_claim_from_payload(point)
        if (
            not original
            or original.get("status") != "active"
            or personal_claim_payload_lifecycle_state(point or {}) == "expired"
            or clean_value.casefold() == str(original.get("value") or "").casefold()
        ):
            return _memories_auto_memory_redirect(error="invalid_personal_claim_correction")
        corrected = normalize_personal_claim(
            {
                **original,
                "value": clean_value,
                "explicit": True,
                "authority": "user_correction",
                "confidence": 1.0,
                "source": "personal_model_ui",
            },
            user_id=username,
            source="personal_model_ui",
        )
        if not corrected:
            return _memories_auto_memory_redirect(error="invalid_personal_claim_correction")
        result = await store_personal_claim(
            memory_skill=memory_skill,
            llm_client=getattr(pipeline, "llm_client", None),
            claim=corrected,
            user_id=username,
            facts_collection=clean_collection,
            preferences_collection=clean_collection,
            request_id=f"personal-model-ui-{uuid4().hex}",
            explicit_supersedes_claim_id=str(original.get("claim_id") or ""),
        )
        if result.get("stored") is True:
            return _memories_auto_memory_redirect(saved=True)
        return _memories_auto_memory_redirect(error=str(result.get("reason") or "personal_claim_correction_failed"))

    @app.post("/memories/auto-memory/delete-claim")
    async def memories_auto_memory_delete_claim(
        request: Request,
        collection: str = Form(""),
        point_id: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        expected = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected):
            return _memories_auto_memory_redirect(error="csrf_failed")
        settings = get_settings()
        collections_cfg = getattr(getattr(settings, "memory", None), "collections", None)
        allowed_prefixes = (
            str(getattr(getattr(collections_cfg, "facts", None), "prefix", "") or "aria_facts"),
            str(getattr(getattr(collections_cfg, "preferences", None), "prefix", "") or "aria_preferences"),
        )
        clean_collection = sanitize_collection_name(collection)
        clean_point_id = str(point_id or "").strip()
        if (
            not clean_collection.startswith(tuple(f"{prefix}_" for prefix in allowed_prefixes))
            or not clean_point_id
        ):
            return _memories_auto_memory_redirect(error="invalid_personal_claim")
        pipeline = get_pipeline()
        memory_skill = getattr(pipeline, "memory_skill", None)
        username = get_username_from_request(request) or "web"
        point = await memory_skill.get_memory_point(username, clean_collection, clean_point_id) if memory_skill else None
        if not point or str(point.get("personal_claim_contract") or "") != "personal_claim_v1":
            return _memories_auto_memory_redirect(error="personal_claim_not_found")
        deleted = await memory_skill.delete_memory_point(username, clean_collection, clean_point_id)
        return _memories_auto_memory_redirect(saved=True) if deleted else _memories_auto_memory_redirect(error="personal_claim_delete_failed")

    @app.post("/memories/config/backend-save")
    @app.post("/config/memory/backend-save")
    async def config_memory_backend_save(
        request: Request,
        backend: str = Form("qdrant"),
        qdrant_url: str = Form(""),
        qdrant_api_key: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        try:
            clean_backend = str(backend or "").strip().lower() or "qdrant"
            if clean_backend != "qdrant":
                raise ValueError(_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.only_qdrant_supported", "Only Qdrant is currently supported as memory backend."))
            clean_url = str(qdrant_url or "").strip().rstrip("/")
            if not clean_url:
                raise ValueError("Qdrant URL darf nicht leer sein.")

            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            # Keep the memory backend active whenever this Qdrant setup is saved from the UI.
            raw["memory"]["enabled"] = True
            raw["memory"]["backend"] = clean_backend
            raw["memory"]["qdrant_url"] = clean_url
            raw["memory"]["qdrant_api_key"] = ""

            secure_store = get_secure_store(raw)
            clean_api_key = str(qdrant_api_key or "").strip()
            if secure_store:
                if clean_api_key:
                    secure_store.set_secret("memory.qdrant_api_key", clean_api_key)
                else:
                    stored_key = secure_store.get_secret("memory.qdrant_api_key", "")
                    if not stored_key:
                        secure_store.delete_secret("memory.qdrant_api_key")
            else:
                raw["memory"]["qdrant_api_key"] = clean_api_key

            write_raw_config(raw)
            reload_runtime()
            return _memories_config_redirect(saved=True)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Memory-Backend konnte nicht gespeichert werden.", "Could not save memory backend.")
            return _memories_config_redirect(error=error)

    @app.post("/memories/config/select")
    @app.post("/config/memory/select")
    async def config_memory_select(request: Request, collection: str = Form("")) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        clean = sanitize_collection_name(collection)
        settings = get_settings()
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        response = _memories_config_redirect(saved=True)
        if clean:
            response.set_cookie(
                key=_cookie_name_for_request(request, "memory_collection", memory_collection_cookie),
                value=clean,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        else:
            response.delete_cookie(_cookie_name_for_request(request, "memory_collection", memory_collection_cookie))
        return response

    @app.post("/memories/config/create")
    @app.post("/config/memory/create")
    async def config_memory_create(request: Request, collection_name: str = Form(...)) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        clean = sanitize_collection_name(collection_name)
        if not clean:
            return _memories_config_redirect(
                error=_memory_routes_text(
                    str(getattr(request.state, "lang", "de") or "de"),
                    "error.invalid_collection_name",
                    "Invalid collection name",
                )
            )
        settings = get_settings()
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        response = _memories_config_redirect(saved=True)
        response.set_cookie(
            key=_cookie_name_for_request(request, "memory_collection", memory_collection_cookie),
            value=clean,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=secure_cookie,
            httponly=False,
        )
        return response

    @app.post("/memories/config/compress")
    @app.post("/config/memory/compress")
    async def config_memory_compress(request: Request) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        username = get_username_from_request(request)
        if not username:
            return _memories_config_redirect(error="Bitte zuerst Benutzernamen setzen", anchor="rollup")
        if not pipeline.memory_skill:
            return _memories_config_redirect(error="Memory nicht aktiv", anchor="rollup")
        try:
            session_cfg = settings.memory.collections.sessions
            compress_after_days = int(session_cfg.compress_after_days or 7)
            monthly_after_days = int(session_cfg.monthly_after_days or 30)
            stats = await pipeline.memory_skill.compress_old_sessions(
                user_id=username,
                compress_after_days=compress_after_days,
                monthly_after_days=monthly_after_days,
            )
            await pipeline.token_tracker.log(
                request_id=str(uuid4()),
                user_id=username,
                intents=["memory_compress"],
                router_level=0,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                chat_model=settings.llm.model,
                embedding_model=settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=0,
                source="system",
                skill_errors=[],
                extraction_model="compression",
                extraction_usage={
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "calls": int(stats.get("compressed_week", 0)) + int(stats.get("compressed_month", 0)),
                },
            )
            message = _build_compression_result_message(stats, compress_after_days, lang=str(getattr(request.state, "lang", "de") or "de"))
            return _memories_config_redirect(compress_result=message, anchor="rollup")
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, _memory_routes_text(lang, "error.memory_compression_failed", "Memory compression failed."), "Memory compression failed.")
            return _memories_config_redirect(error=error, anchor="rollup")

    @app.post("/memories/config/compression-save")
    @app.post("/config/memory/compression-save")
    async def config_memory_compression_save(
        request: Request,
        compression_summary_prompt: str = Form(""),
        compress_after_days: int = Form(...),
        monthly_after_days: int = Form(...),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return _memories_overview_redirect(error="no_admin")
        try:
            if compress_after_days < 1:
                raise ValueError("compress_after_days muss >= 1 sein.")
            if monthly_after_days < compress_after_days:
                raise ValueError("monthly_after_days muss >= compress_after_days sein.")

            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            clean_path = str(compression_summary_prompt).strip().replace("\\", "/")
            if clean_path:
                target = resolve_prompt_file(clean_path)
                if not target.exists():
                    raise ValueError("Prompt-Datei existiert nicht.")
                raw["memory"]["compression_summary_prompt"] = clean_path
            raw["memory"].setdefault("collections", {})
            if not isinstance(raw["memory"]["collections"], dict):
                raw["memory"]["collections"] = {}
            raw["memory"]["collections"].setdefault("sessions", {})
            if not isinstance(raw["memory"]["collections"]["sessions"], dict):
                raw["memory"]["collections"]["sessions"] = {}
            raw["memory"]["collections"]["sessions"]["compress_after_days"] = int(compress_after_days)
            raw["memory"]["collections"]["sessions"]["monthly_after_days"] = int(monthly_after_days)
            write_raw_config(raw)
            reload_runtime()
            return _memories_config_redirect(saved=True, anchor="rollup")
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Komprimierungs-Einstellungen konnten nicht gespeichert werden.", "Could not save compression settings.")
            return _memories_config_redirect(error=error, anchor="rollup")
