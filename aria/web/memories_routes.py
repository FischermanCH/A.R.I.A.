from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.core.pipeline import Pipeline
from aria.core.runtime_endpoint import cookie_should_be_secure, request_is_secure


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
AutoMemoryResolver = Callable[[Request], bool]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
PromptFileResolver = Callable[[str], Path]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]


def _is_admin_request(
    request: Request,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
) -> bool:
    auth = get_auth_session_from_request(request) or {}
    return sanitize_role(auth.get("role")) == "admin"


def _msg(lang: str, de: str, en: str) -> str:
    return de if str(lang or "de").strip().lower().startswith("de") else en


def _friendly_memory_error(lang: str, exc: Exception, de_default: str, en_default: str) -> str:
    if isinstance(exc, ValueError):
        detail = str(exc).strip()
        if detail:
            return detail
    return _msg(lang, de_default, en_default)


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
    counts = {"fact": 0, "preference": 0, "knowledge": 0, "session": 0}
    for row in rows:
        key = str(row.get("type", "")).strip().lower()
        if key in counts:
            counts[key] += 1
    return counts


def _build_type_points(collection_stats: list[dict[str, Any]]) -> dict[str, int]:
    type_points = {"fact": 0, "preference": 0, "knowledge": 0, "session": 0}
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


def _format_display_timestamp(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw.replace("T", " ", 1)


def _slug_user_id(user_id: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(user_id or "").strip())
    while "__" in clean:
        clean = clean.replace("__", "_")
    clean = clean.strip("_")
    return clean or "web"


def _memory_title(text: str, *, limit: int = 88) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return "Leerer Eintrag"
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


def _memory_collection_for_type(settings: Any, user_id: str, memory_type: str) -> str:
    slug = _slug_user_id(user_id)
    normalized = str(memory_type or "").strip().lower()
    if normalized == "preference":
        return f"{settings.memory.collections.preferences.prefix}_{slug}"
    if normalized == "knowledge":
        return f"{settings.memory.collections.knowledge.prefix}_{slug}"
    return f"{settings.memory.collections.facts.prefix}_{slug}"


def _memories_redirect(
    *,
    filter_type: str,
    query: str,
    page: int,
    limit: int,
    sort: str,
    info: str = "",
    error: str = "",
) -> RedirectResponse:
    url = (
        f"/memories?type={quote_plus(filter_type)}&q={quote_plus(query)}"
        f"&page={_coerce_page_number(page)}&limit={_coerce_page_size(limit)}&sort={quote_plus(sort)}"
    )
    if info:
        url += f"&info={quote_plus(info)}"
    if error:
        url += f"&error={quote_plus(error)}"
    return RedirectResponse(url=url, status_code=303)


def _memory_export_filename(username: str, filter_type: str, query: str) -> str:
    slug = _slug_user_id(username)
    scope = str(filter_type or "all").strip().lower() or "all"
    if scope not in {"all", "fact", "preference", "session", "knowledge"}:
        scope = "all"
    suffix = "search" if str(query or "").strip() else "all"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"aria-memory-{slug}-{scope}-{suffix}-{stamp}.json"


def _build_compression_result_message(stats: dict[str, Any], compress_after_days: int) -> str:
    moved = list(stats.get("compressed_collections", []) or [])
    removed = list(stats.get("removed_collections", []) or [])
    skipped_recent = list(stats.get("skipped_recent", []) or [])
    failed_delete = list(stats.get("failed_delete", []) or [])
    moved_total = int(stats.get("compressed_week", 0) or 0) + int(stats.get("compressed_month", 0) or 0)

    if moved_total <= 0:
        if skipped_recent:
            preview = ", ".join(skipped_recent[:3])
            return (
                f"Rollup beendet: nichts verschoben. "
                f"{len(skipped_recent)} Tages-Collections sind noch juenger als {compress_after_days} Tage "
                f"oder noch aktiver Tages-Kontext. Beispiele: {preview}"
            )
        return "Rollup beendet: nichts zu verschieben."

    parts = [
        f"Rollup beendet: verschoben={moved_total}, entfernt={int(stats.get('collections_removed', 0) or 0)}",
    ]
    if moved:
        parts.append(f"Verschoben: {', '.join(moved[:3])}")
    if skipped_recent:
        parts.append(
            f"Unverändert geblieben ({len(skipped_recent)}): juenger als {compress_after_days} Tage oder aktueller Tages-Kontext"
        )
    if failed_delete:
        parts.append(f"Nicht gelöscht ({len(failed_delete)}): {', '.join(failed_delete[:3])}")
    if removed and len(removed) != len(moved):
        parts.append(f"Entfernt: {', '.join(removed[:3])}")
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
    is_auto_memory_enabled: AutoMemoryResolver,
    read_raw_config: RawConfigReader,
    write_raw_config: RawConfigWriter,
    reload_runtime: RuntimeReloader,
    resolve_prompt_file: PromptFileResolver,
    get_secure_store: SecureStoreGetter,
    memory_collection_cookie: str,
    auto_memory_cookie: str,
) -> None:
    @app.get("/memories", response_class=HTMLResponse)
    async def memories_page(
        request: Request,
        type: str = "all",
        q: str = "",
        limit: int = 120,
        page: int = 1,
        sort: str = "updated_desc",
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        overview = await qdrant_overview(request)
        sort_key = _normalize_memory_sort(sort)
        page_size = _coerce_page_size(limit)
        page_number = _coerce_page_number(page)
        all_rows: list[dict[str, Any]] = []
        collection_stats: list[dict[str, Any]] = []

        if pipeline.memory_skill:
            try:
                if q.strip():
                    all_rows = await pipeline.memory_skill.search_memories(
                        user_id=username,
                        query=q.strip(),
                        type_filter=type,
                        top_k=300,
                    )
                else:
                    all_rows = await pipeline.memory_skill.list_memories_global(
                        user_id=username,
                        type_filter=type,
                        limit=600,
                    )
                collection_stats = await pipeline.memory_skill.get_user_collection_stats(username)
            except Exception as exc:  # noqa: BLE001
                error = error or str(exc)

        _sort_memory_rows(all_rows, sort_key)
        total_rows = len(all_rows)
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        if page_number > total_pages:
            page_number = total_pages
        start = (page_number - 1) * page_size
        end = start + page_size
        rows = all_rows[start:end]
        for row in rows:
            row["display_timestamp"] = _format_display_timestamp(row.get("timestamp"))
            row["title"] = _memory_title(str(row.get("text", "")))
            row["preview"] = _memory_preview(str(row.get("text", "")))
        counts = _build_memory_counts(all_rows)
        return templates.TemplateResponse(
            request=request,
            name="memories.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "rows": rows,
                "filter_type": type,
                "query": q,
                "limit": page_size,
                "page": page_number,
                "sort": sort_key,
                "total_rows": total_rows,
                "total_pages": total_pages,
                "prev_page": (page_number - 1) if page_number > 1 else 1,
                "next_page": (page_number + 1) if page_number < total_pages else total_pages,
                "counts": counts,
                "info_message": info,
                "error_message": error,
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "manual_memory_types": [
                    {"value": "fact", "label": "Fakt"},
                    {"value": "preference", "label": "Präferenz"},
                    {"value": "knowledge", "label": "Wissen"},
                ],
            },
        )

    @app.get("/memories/export")
    async def memories_export(
        request: Request,
        type: str = "all",
        q: str = "",
        sort: str = "updated_desc",
    ) -> JSONResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        sort_key = _normalize_memory_sort(sort)
        all_rows: list[dict[str, Any]] = []
        if pipeline.memory_skill:
            if q.strip():
                all_rows = await pipeline.memory_skill.search_memories(
                    user_id=username,
                    query=q.strip(),
                    type_filter=type,
                    top_k=5000,
                )
            else:
                all_rows = await pipeline.memory_skill.list_memories_global(
                    user_id=username,
                    type_filter=type,
                    limit=10000,
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
    async def memories_map_page(request: Request) -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        overview = await qdrant_overview(request)
        user_rows: list[dict[str, Any]] = []
        collection_stats: list[dict[str, Any]] = []
        if pipeline.memory_skill:
            try:
                stats = await pipeline.memory_skill.get_user_collection_stats(username)
                collection_stats = list(stats)
                all_status = {
                    str(item.get("name", "")): str(item.get("status", "ok"))
                    for item in overview.get("collections", [])
                }
                for row in stats:
                    name = str(row.get("name", "")).strip()
                    user_rows.append(
                        {
                            "name": name,
                            "points": int(row.get("points", 0) or 0),
                            "kind": str(row.get("kind", "fact")),
                            "status": all_status.get(name, "ok"),
                        }
                    )
            except Exception:
                user_rows = []

        user_rows.sort(key=lambda row: int(row.get("points", 0) or 0), reverse=True)
        max_points = max((int(row.get("points", 0) or 0) for row in user_rows), default=0)
        total_points = int(sum(int(row.get("points", 0) or 0) for row in user_rows))
        for row in user_rows:
            points = int(row.get("points", 0) or 0)
            row["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
            row["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
            row["node_size"] = max(16, min(54, int(16 + (row["pct"] / 100.0) * 38)))

        kind_totals = {"fact": 0, "preference": 0, "knowledge": 0, "session": 0}
        for row in user_rows:
            kind = str(row.get("kind", "fact"))
            if kind in kind_totals:
                kind_totals[kind] += int(row.get("points", 0) or 0)
        cleanup_status = _build_cleanup_status(pipeline.memory_skill)
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

        return templates.TemplateResponse(
            request=request,
            name="memories_map.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "qdrant_api_key": str(getattr(settings.memory, "qdrant_api_key", "") or ""),
                "qdrant_overview": overview,
                "map_rows": user_rows,
                "map_total_points": total_points,
                "map_kind_totals": kind_totals,
                "health": health,
                "cleanup_status": cleanup_status,
            },
        )

    @app.post("/memories/delete")
    async def memories_delete(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories?error=Memory+Skill+nicht+aktiv", status_code=303)
        ok = await pipeline.memory_skill.delete_memory_point(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
        )
        if ok:
            return _memories_redirect(
                filter_type=type,
                query=q,
                page=page,
                limit=limit,
                sort=sort,
                info="Eintrag gelöscht",
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            page=page,
            limit=limit,
            sort=sort,
            error="Eintrag konnte nicht gelöscht werden",
        )

    @app.post("/memories/edit")
    async def memories_edit(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        text: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories?error=Memory+Skill+nicht+aktiv", status_code=303)
        clean_text = str(text).strip()
        if not clean_text:
            return _memories_redirect(
                filter_type=type,
                query=q,
                page=page,
                limit=limit,
                sort=sort,
                error="Memory-Text darf nicht leer sein",
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
                page=page,
                limit=limit,
                sort=sort,
                info="Eintrag aktualisiert",
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            page=page,
            limit=limit,
            sort=sort,
            error="Eintrag konnte nicht aktualisiert werden",
        )

    @app.post("/memories/create")
    async def memories_create(
        request: Request,
        memory_type: str = Form("fact"),
        text: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories?error=Memory+Skill+nicht+aktiv", status_code=303)

        clean_type = str(memory_type or "fact").strip().lower()
        if clean_type not in {"fact", "preference", "knowledge"}:
            clean_type = "fact"
        clean_text = str(text or "").strip()
        if not clean_text:
            return _memories_redirect(
                filter_type=type,
                query=q,
                page=page,
                limit=limit,
                sort=sort,
                error="Memory-Text darf nicht leer sein",
            )
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000]

        try:
            result = await pipeline.memory_skill.execute(
                query=clean_text,
                params={
                    "action": "store",
                    "user_id": username,
                    "collection": _memory_collection_for_type(settings, username, clean_type),
                    "memory_type": clean_type,
                    "text": clean_text,
                    "source": "manual_ui",
                },
            )
            if result.success:
                return _memories_redirect(
                    filter_type=type,
                    query=q,
                    page=1,
                    limit=limit,
                    sort=sort,
                    info=result.content or "Memory gespeichert",
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                page=page,
                limit=limit,
                sort=sort,
                error=result.error or result.content or "Memory konnte nicht gespeichert werden",
            )
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            return _memories_redirect(
                filter_type=type,
                query=q,
                page=page,
                limit=limit,
                sort=sort,
                error=_friendly_memory_error(lang, exc, "Memory konnte nicht gespeichert werden.", "Could not save memory."),
            )

    @app.post("/memories/maintenance")
    async def memories_maintenance(request: Request) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories?error=Memory+Skill+nicht+aktiv", status_code=303)
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
                return RedirectResponse(url=f"/memories?info={quote_plus(result.content)}", status_code=303)
            message = result.error or "Komprimierung fehlgeschlagen"
            return RedirectResponse(url=f"/memories?error={quote_plus(message)}", status_code=303)
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Komprimierung konnte nicht gestartet werden.", "Could not start compression.")
            return RedirectResponse(url=f"/memories?error={quote_plus(error)}", status_code=303)

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
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        username = get_username_from_request(request) or "web"
        overview = await qdrant_overview(request)
        return templates.TemplateResponse(
            request=request,
            name="config_memory.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "collections": [row["name"] for row in overview.get("collections", [])],
                "default_collection": default_memory_collection_for_user(username),
                "active_collection": get_effective_memory_collection(request, username),
                "auto_memory": settings.auto_memory,
                "memory_cfg": settings.memory,
                "auto_memory_cookie": is_auto_memory_enabled(request),
                "qdrant_overview": overview,
                "has_qdrant_api_key": bool(getattr(settings.memory, "qdrant_api_key", "")),
                "compress_result": compress_result,
            },
        )

    @app.post("/memories/config/backend-save")
    @app.post("/config/memory/backend-save")
    async def config_memory_backend_save(
        request: Request,
        enabled: str = Form("0"),
        backend: str = Form("qdrant"),
        qdrant_url: str = Form(""),
        qdrant_api_key: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        try:
            clean_backend = str(backend or "").strip().lower() or "qdrant"
            if clean_backend != "qdrant":
                raise ValueError("Aktuell wird nur Qdrant als Memory-Backend unterstützt.")
            clean_url = str(qdrant_url or "").strip().rstrip("/")
            if not clean_url:
                raise ValueError("Qdrant URL darf nicht leer sein.")

            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            raw["memory"]["enabled"] = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
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
            return RedirectResponse(url="/memories/config?saved=1", status_code=303)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Memory-Backend konnte nicht gespeichert werden.", "Could not save memory backend.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}", status_code=303)

    @app.post("/memories/config/select")
    @app.post("/config/memory/select")
    async def config_memory_select(request: Request, collection: str = Form("")) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        clean = sanitize_collection_name(collection)
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        response = RedirectResponse(url="/memories/config?saved=1", status_code=303)
        if clean:
            response.set_cookie(
                key=memory_collection_cookie,
                value=clean,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        else:
            response.delete_cookie(memory_collection_cookie)
        return response

    @app.post("/memories/config/create")
    @app.post("/config/memory/create")
    async def config_memory_create(request: Request, collection_name: str = Form(...)) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        clean = sanitize_collection_name(collection_name)
        if not clean:
            return RedirectResponse(url="/memories/config?error=Ungültiger+Collection-Name", status_code=303)
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        response = RedirectResponse(url="/memories/config?saved=1", status_code=303)
        response.set_cookie(
            key=memory_collection_cookie,
            value=clean,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=secure_cookie,
            httponly=False,
        )
        return response

    @app.post("/memories/config/auto-save")
    @app.post("/config/memory/auto-save")
    async def config_memory_auto_save(
        request: Request,
        enabled: str = Form("0"),
        session_recall_top_k: int = Form(...),
        user_recall_top_k: int = Form(...),
        max_facts_per_message: int = Form(...),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        try:
            if session_recall_top_k <= 0:
                raise ValueError("session_recall_top_k muss > 0 sein.")
            if user_recall_top_k <= 0:
                raise ValueError("user_recall_top_k muss > 0 sein.")
            if max_facts_per_message <= 0:
                raise ValueError("max_facts_per_message muss > 0 sein.")

            raw = read_raw_config()
            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            raw["auto_memory"]["enabled"] = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
            raw["auto_memory"]["session_recall_top_k"] = int(session_recall_top_k)
            raw["auto_memory"]["user_recall_top_k"] = int(user_recall_top_k)
            raw["auto_memory"]["max_facts_per_message"] = int(max_facts_per_message)
            write_raw_config(raw)
            reload_runtime()

            secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
            response = RedirectResponse(url="/memories/config?saved=1", status_code=303)
            response.set_cookie(
                key=auto_memory_cookie,
                value="1" if raw["auto_memory"]["enabled"] else "0",
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Auto-Memory konnte nicht gespeichert werden.", "Could not save auto-memory settings.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}", status_code=303)

    @app.post("/memories/config/compress")
    @app.post("/config/memory/compress")
    async def config_memory_compress(request: Request) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        username = get_username_from_request(request)
        if not username:
            return RedirectResponse(url="/memories/config?error=Bitte+zuerst+Benutzernamen+setzen#rollup", status_code=303)
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/config?error=Memory+Skill+nicht+aktiv#rollup", status_code=303)
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
            message = _build_compression_result_message(stats, compress_after_days)
            return RedirectResponse(url=f"/memories/config?compress_result={quote_plus(message)}#rollup", status_code=303)
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Memory-Komprimierung ist fehlgeschlagen.", "Memory compression failed.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}#rollup", status_code=303)

    @app.post("/memories/config/compression-save")
    @app.post("/config/memory/compression-save")
    async def config_memory_compression_save(
        request: Request,
        compression_summary_prompt: str = Form(""),
        compress_after_days: int = Form(...),
        monthly_after_days: int = Form(...),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
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
            return RedirectResponse(url="/memories/config?saved=1#rollup", status_code=303)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Komprimierungs-Einstellungen konnten nicht gespeichert werden.", "Could not save compression settings.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}#rollup", status_code=303)
