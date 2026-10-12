"""Authenticated user surface for the compact activity journal."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.modules import module_template_name
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.platform_primitives.display_time import (
    display_datetime,
    display_zone,
    local_date_bound,
    request_display_timezone,
)

from .runtime import activity_journal_store_for
from .service import delete_migrated_legacy_rollups, list_legacy_rollups, migrate_legacy_rollups


_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    values: list[str] = []
    if info:
        values.append("info=" + quote_plus(info))
    if error:
        values.append("error=" + quote_plus(error))
    suffix = "?" + "&".join(values) if values else ""
    return RedirectResponse("/memories/activity-journal" + suffix, status_code=303)


def _period_bounds(
    period: str,
    since: str,
    until: str,
    timezone_name: str,
    *,
    now: datetime | None = None,
) -> tuple[str, float | None, float | None]:
    clean_period = str(period or "").strip().lower()
    if (since or until) and clean_period in {"", "all"}:
        clean_period = "custom"
    if clean_period not in {"all", "today", "7d", "30d", "custom"}:
        clean_period = "all"
    if clean_period == "custom":
        return (
            clean_period,
            local_date_bound(since, timezone_name),
            local_date_bound(until, timezone_name, end=True),
        )
    if clean_period == "all":
        return clean_period, None, None
    zone = display_zone(timezone_name)
    local_now = (now or datetime.now(timezone.utc)).astimezone(zone)
    days = {"today": 0, "7d": 6, "30d": 29}[clean_period]
    first_day = local_now.date() - timedelta(days=days)
    start = datetime.combine(first_day, datetime.min.time(), tzinfo=zone)
    return clean_period, start.timestamp(), local_now.timestamp()


def _lang(request: Request) -> str:
    return str(getattr(request.state, "lang", "de") or "de").lower()


def _text(request: Request, key: str, default: str, **values: object) -> str:
    template = _I18N.t(_lang(request), f"activity_journal.{key}", default)
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


def register_activity_journal_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_pipeline: Callable[[], Any],
    get_settings: Callable[[], Any],
    get_username_from_request: Callable[[Request], str],
    read_raw_config: Callable[[], dict[str, Any]],
    write_raw_config: Callable[[dict[str, Any]], None],
    reload_runtime: Callable[[], None],
) -> None:
    template_name = module_template_name("activity_journal", "activity_journal.html") or "activity_journal.html"

    def _identity(request: Request) -> tuple[Any, str]:
        return get_pipeline(), str(get_username_from_request(request) or "").strip()

    @app.get("/memories/activity-journal", response_class=HTMLResponse)
    async def activity_journal_page(
        request: Request,
        q: str = "",
        outcome: str = "",
        tool: str = "",
        connection: str = "",
        server: str = "",
        period: str = "all",
        since: str = "",
        until: str = "",
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        pipeline, user_id = _identity(request)
        store = activity_journal_store_for(pipeline)
        settings = get_settings()
        timezone_name = request_display_timezone(request, settings)
        selected_period, since_epoch, until_epoch = _period_bounds(
            period, since, until, timezone_name,
        )
        config = getattr(settings, "agentic_loop", None)
        retention_days = min(365, max(7, int(getattr(config, "activity_journal_retention_days", 90) or 90)))
        enabled = bool(getattr(config, "activity_journal_enabled", True))
        rows = store.query(
            user_id,
            query=q,
            since=since_epoch,
            until=until_epoch,
            outcome=outcome,
            tool=tool,
            connection=connection,
            server=server,
            limit=200,
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        now_epoch = datetime.now(timezone.utc).timestamp()
        for row in rows:
            local = display_datetime(row["finished_at"], timezone_name)
            row["finished_time"] = local.strftime("%H:%M")
            elapsed = max(0, int(now_epoch - float(row["finished_at"])))
            if elapsed < 60:
                row["finished_relative"] = _text(request, "time_just_now", "gerade eben")
            elif elapsed < 3600:
                row["finished_relative"] = _text(request, "time_minutes_ago", "vor {count} Min.", count=elapsed // 60)
            elif elapsed < 86400:
                row["finished_relative"] = _text(request, "time_hours_ago", "vor {count} Std.", count=elapsed // 3600)
            else:
                row["finished_relative"] = _text(request, "time_days_ago", "vor {count} Tagen", count=elapsed // 86400)
            confirmations = dict(row.get("confirmations") or {})
            row["detail_rows"] = []
            if sum(int(confirmations.get(key, 0) or 0) for key in ("asked", "approved", "rejected")):
                row["detail_rows"].append((
                    _text(request, "confirmations", "Confirmations"),
                    f"{confirmations.get('asked', 0)}/{confirmations.get('approved', 0)}/{confirmations.get('rejected', 0)}",
                ))
            if str(row.get("source") or "live") != "live":
                row["detail_rows"].append((_text(request, "source", "Source"), _text(request, "legacy_source", "Imported context rollup")))
            day_key = local.strftime("%Y-%m-%d")
            day_label = local.strftime("%d.%m.%Y" if _lang(request) == "de" else "%Y-%m-%d")
            grouped[f"{day_key}|{day_label}"].append(row)
        legacy_rows: list[dict[str, Any]] = []
        memory_skill = getattr(pipeline, "memory_skill", None)
        if memory_skill is not None:
            try:
                legacy_rows = await list_legacy_rollups(memory_skill, user_id=user_id)
            except Exception:  # noqa: BLE001 - a preview failure must not break the journal.
                legacy_rows = []
        migrated_rows = store.query(user_id, source="legacy_context_rollup", limit=10_000)
        migrated_sources = {
            (str(source.get("collection") or ""), str(source.get("point_id") or ""))
            for migrated in migrated_rows
            for source in (
                list(migrated.get("legacy_sources") or ())
                or [{"collection": migrated.get("legacy_collection"), "point_id": migrated.get("legacy_point_id")}]
            )
        }
        legacy_preview = [
            {
                **row,
                "preview": str(row.get("outcome_phrase") or "")[:300],
                "migrated": any(
                    (str(source.get("collection") or ""), str(source.get("point_id") or "")) in migrated_sources
                    for source in row.get("legacy_sources", ())
                ),
            }
            for row in legacy_rows[:20]
        ]
        legacy_migrated_count = sum(
            1 for row in legacy_rows
            if any(
                (str(source.get("collection") or ""), str(source.get("point_id") or "")) in migrated_sources
                for source in row.get("legacy_sources", ())
            )
        )
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context={
                "title": getattr(getattr(settings, "ui", None), "title", "ARIA"),
                "memory_nav": "activity_journal",
                "journal_enabled": enabled,
                "can_manage_journal_settings": bool(
                    getattr(request.state, "can_access_advanced_config", False)
                ),
                "retention_days": retention_days,
                "journal_groups": [
                    (key.split("|", 1)[0], key.split("|", 1)[1], values)
                    for key, values in grouped.items()
                ],
                "journal_rendered_count": len(rows),
                "journal_count": store.count(user_id),
                "filters": {
                    "q": q, "outcome": outcome, "tool": tool,
                    "connection": connection, "server": server,
                    "period": selected_period, "since": since, "until": until,
                },
                "display_timezone": timezone_name,
                "legacy_count": len(legacy_rows),
                "legacy_migrated_count": legacy_migrated_count,
                "legacy_preview": legacy_preview,
                "info_message": info,
                "error_message": error,
            },
        )

    @app.post("/memories/activity-journal/settings")
    async def activity_journal_settings(
        request: Request,
        activity_journal_enabled: str = Form(""),
        retention_days: int = Form(90),
        csrf_token: str = Form(""),  # noqa: ARG001 - global form middleware validates it.
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return _redirect(error=_text(request, "error_settings_access", "Advanced configuration access is required."))
        if not 7 <= int(retention_days) <= 365:
            return _redirect(error=_text(request, "error_retention", "Retention must be between 7 and 365 days."))
        raw = read_raw_config()
        agentic = raw.setdefault("agentic_loop", {})
        if not isinstance(agentic, dict):
            agentic = {}
            raw["agentic_loop"] = agentic
        agentic["activity_journal_enabled"] = str(activity_journal_enabled).lower() in {"1", "true", "yes", "on"}
        agentic["activity_journal_retention_days"] = int(retention_days)
        try:
            write_raw_config(raw)
            reload_runtime()
        except (OSError, RuntimeError, ValueError):
            return _redirect(error=_text(request, "error_settings", "Could not save settings."))
        return _redirect(info=_text(request, "settings_saved", "Journal settings saved."))

    @app.get("/memories/activity-journal/export")
    async def activity_journal_export(request: Request) -> JSONResponse:
        pipeline, user_id = _identity(request)
        rows = activity_journal_store_for(pipeline).query(user_id, limit=10_000)
        return JSONResponse({"format": "aria_activity_journal_v1", "user_id": user_id, "entries": rows})

    @app.post("/memories/activity-journal/entry/keep")
    async def activity_journal_keep(
        request: Request,
        entry_id: str = Form(""),
        keep: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        pipeline, user_id = _identity(request)
        changed = activity_journal_store_for(pipeline).update_keep(
            user_id, entry_id, str(keep).lower() in {"1", "true", "yes", "on"},
        )
        return _redirect(info=_text(request, "entry_updated", "Entry updated.")) if changed else _redirect(error=_text(request, "entry_not_found", "Entry not found."))

    @app.post("/memories/activity-journal/entry/delete")
    async def activity_journal_delete(
        request: Request,
        entry_id: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        pipeline, user_id = _identity(request)
        deleted = activity_journal_store_for(pipeline).delete(user_id, entry_id)
        return _redirect(info=_text(request, "entry_deleted", "Entry deleted.")) if deleted else _redirect(error=_text(request, "entry_not_found", "Entry not found."))

    @app.post("/memories/activity-journal/delete-range")
    async def activity_journal_delete_range(
        request: Request,
        since: str = Form(""),
        until: str = Form(""),
        confirmation: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        expected = _text(request, "delete_range_phrase", "DELETE ACTIVITY JOURNAL")
        timezone_name = request_display_timezone(request, get_settings())
        start = local_date_bound(since, timezone_name)
        end = local_date_bound(until, timezone_name, end=True)
        if confirmation.strip() != expected or start is None or end is None or start > end:
            return _redirect(error=_text(request, "error_delete_range", "Confirmation or date range is invalid."))
        pipeline, user_id = _identity(request)
        removed = activity_journal_store_for(pipeline).delete_range(user_id, since=start, until=end)
        return _redirect(info=_text(request, "range_deleted", "Deleted {count} journal entries.", count=removed))

    @app.post("/memories/activity-journal/legacy/migrate")
    async def activity_journal_legacy_migrate(
        request: Request,
        confirmed: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        if str(confirmed).lower() not in {"1", "true", "yes", "on"}:
            return _redirect(error=_text(request, "error_migrate_confirm", "Please confirm the import."))
        pipeline, user_id = _identity(request)
        memory_skill = getattr(pipeline, "memory_skill", None)
        if memory_skill is None:
            return _redirect(error=_text(request, "error_memory_unavailable", "Memory storage is unavailable."))
        result = await migrate_legacy_rollups(activity_journal_store_for(pipeline), memory_skill, user_id=user_id)
        return _redirect(info=_text(
            request, "migration_result",
            "Imported {created} legacy entries; updated {updated}; {existing} already current.",
            created=result["created"], updated=result.get("updated", 0), existing=result["existing"],
        ))

    @app.post("/memories/activity-journal/legacy/delete")
    async def activity_journal_legacy_delete(
        request: Request,
        confirmation: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        expected = _text(request, "delete_legacy_phrase", "DELETE LEGACY ROLLUPS")
        if confirmation.strip() != expected:
            return _redirect(error=_text(request, "error_confirmation", "Confirmation is invalid."))
        pipeline, user_id = _identity(request)
        memory_skill = getattr(pipeline, "memory_skill", None)
        if memory_skill is None:
            return _redirect(error=_text(request, "error_memory_unavailable", "Memory storage is unavailable."))
        removed = await delete_migrated_legacy_rollups(activity_journal_store_for(pipeline), memory_skill, user_id=user_id)
        return _redirect(info=_text(request, "legacy_deleted", "Deleted {count} imported legacy rollups.", count=removed))
