from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.config_backup import (
    backup_filename,
    build_config_backup_payload,
    parse_config_backup_payload,
    restore_config_backup_payload,
    summarize_config_backup_payload,
)
from aria.core.i18n import I18NStore
from aria.core.inventory_admin import build_inventory_index_status, rebuild_inventory_index


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Any]
Templates = Jinja2Templates
ConfigPageContextBuilder = Callable[..., dict[str, Any]]
ConfigRedirector = Callable[..., RedirectResponse]
FriendlyRouteError = Callable[[str, Exception, str, str], str]
LocalizedMessage = Callable[[str, str, str], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]
RuntimeReloader = Callable[[], None]
SkillTriggerRefresher = Callable[[], dict[str, Any]]
FactoryResetCleaner = Callable[[dict[str, Any]], dict[str, Any]]
DirectoryWiper = Callable[[Path], int]
QdrantFactoryClearer = Callable[[Any], Awaitable[int]]
CookieNameResolver = Callable[[Request, str, str], str]
_CONFIG_OPS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _ops_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CONFIG_OPS_I18N.t(language or "de", f"config_operations_detail_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class ConfigOperationsDetailRouteDeps:
    templates: Templates
    base_dir: Path
    error_interpreter_path: Path
    auth_cookie: str
    username_cookie: str
    memory_collection_cookie: str
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    build_config_page_context: ConfigPageContextBuilder
    redirect_with_return_to: ConfigRedirector
    friendly_route_error: FriendlyRouteError
    msg: LocalizedMessage
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    get_secure_store: SecureStoreGetter
    reload_runtime: RuntimeReloader
    refresh_skill_trigger_index: SkillTriggerRefresher
    apply_factory_reset_to_raw_config: FactoryResetCleaner
    wipe_directory_contents: DirectoryWiper
    clear_qdrant_factory_data: QdrantFactoryClearer
    cookie_name_for_request: CookieNameResolver


def register_config_operations_detail_routes(app: FastAPI, deps: ConfigOperationsDetailRouteDeps) -> None:
    @app.get("/config/operations/reindex")
    async def config_operations_reindex_legacy_page() -> RedirectResponse:
        return RedirectResponse(url="/memories/reindex", status_code=303)

    @app.get("/memories/reindex", response_class=HTMLResponse)
    async def memories_reindex_page(
        request: Request,
        saved: int = 0,
        rebuilt: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        settings = deps.get_settings()
        status = await build_inventory_index_status(settings)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/memories",
            page_return_to="/memories/reindex",
            page_heading=deps.msg(lang, "Memory Reindex", "Memory reindex"),
        )
        context.update(
            {
                "inventory_index": getattr(settings, "inventory_index", None),
                "inventory_index_status": status,
                "memory_nav": "reindex",
                "rebuilt": bool(rebuilt),
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_operations_reindex.html", context=context)

    @app.post("/config/operations/reindex/run")
    async def config_operations_reindex_legacy_run() -> RedirectResponse:
        return RedirectResponse(url="/memories/reindex", status_code=303)

    @app.post("/memories/reindex/run")
    async def memories_reindex_run(request: Request) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/memories/reindex?error=no_admin", status_code=303)
        pipeline = deps.get_pipeline()
        result = await rebuild_inventory_index(
            deps.get_settings(),
            usage_meter=getattr(pipeline, "usage_meter", None),
        )
        status = str(result.get("status", "") or "").strip().lower()
        if status == "error":
            message = str(result.get("detail", "") or result.get("message", "") or "Inventory reindex failed.")
            return RedirectResponse(url=f"/memories/reindex?error={quote_plus(message)}", status_code=303)
        info = str(result.get("message", "") or "Inventory index rebuilt.")
        return RedirectResponse(url=f"/memories/reindex?rebuilt=1&info={quote_plus(info)}", status_code=303)

    @app.post("/config/operations/reindex/save")
    async def config_operations_reindex_legacy_save() -> RedirectResponse:
        return RedirectResponse(url="/memories/reindex", status_code=303)

    @app.post("/memories/reindex/save")
    async def memories_reindex_save(
        request: Request,
        enabled: str = Form("0"),
        cron: str = Form(""),
        timezone: str = Form("Europe/Zurich"),
        run_on_startup: str = Form("0"),
        keep_backup: str = Form("0"),
        score_threshold: float = Form(0.35),
        candidate_limit: int = Form(12),
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/memories/reindex?error=no_admin", status_code=303)
        try:
            clean_cron = str(cron or "").strip()
            if len(clean_cron.split()) != 5:
                raise ValueError(_ops_text(str(getattr(request.state, "lang", "de") or "de"), "reindex_cron_invalid", "Cron expression must have five fields."))
            raw = deps.read_raw_config()
            raw.setdefault("inventory_index", {})
            if not isinstance(raw["inventory_index"], dict):
                raw["inventory_index"] = {}
            raw["inventory_index"].update(
                {
                    "enabled": str(enabled).strip().lower() in {"1", "true", "on", "yes"},
                    "cron": clean_cron,
                    "timezone": str(timezone or "Europe/Zurich").strip() or "Europe/Zurich",
                    "run_on_startup": str(run_on_startup).strip().lower() in {"1", "true", "on", "yes"},
                    "keep_backup": str(keep_backup).strip().lower() in {"1", "true", "on", "yes"},
                    "score_threshold": max(0.0, min(1.0, float(score_threshold))),
                    "candidate_limit": max(1, min(50, int(candidate_limit))),
                }
            )
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return RedirectResponse(url="/memories/reindex?saved=1", status_code=303)
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/memories/reindex?error={quote_plus(str(exc))}", status_code=303)

    @app.get("/config/backup", response_class=HTMLResponse)
    async def config_backup_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = deps.read_raw_config()
        secure_store = deps.get_secure_store(raw)
        backup_payload = build_config_backup_payload(
            base_dir=deps.base_dir,
            raw_config=raw,
            secure_store=secure_store,
            error_interpreter_path=deps.error_interpreter_path,
        )
        backup_summary = summarize_config_backup_payload(backup_payload)
        info_message = ""
        if info == "backup_imported":
            info_message = _ops_text(lang, "backup_imported", "Configuration backup restored successfully.")
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/operations",
            page_return_to="/config/operations",
            config_nav="operations",
            page_heading=deps.msg(lang, "Import / Export", "Import / export"),
        )
        context.update(
            {
                "backup_summary": backup_summary,
                "memory_export_url": "/memories/export?type=all&sort=updated_desc",
                "info_message": info_message or context.get("info_message", ""),
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_backup.html", context=context)

    @app.get("/config/backup/export")
    async def config_backup_export(request: Request) -> Response:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        raw = deps.read_raw_config()
        payload = build_config_backup_payload(
            base_dir=deps.base_dir,
            raw_config=raw,
            secure_store=deps.get_secure_store(raw),
            error_interpreter_path=deps.error_interpreter_path,
        )
        body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{backup_filename()}"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/config/backup/import")
    async def config_backup_import(
        request: Request,
        backup_file: UploadFile = File(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        previous_raw = deps.read_raw_config()
        previous_snapshot = build_config_backup_payload(
            base_dir=deps.base_dir,
            raw_config=previous_raw,
            secure_store=deps.get_secure_store(previous_raw),
            error_interpreter_path=deps.error_interpreter_path,
        )
        rollback_restored = False
        try:
            data = await backup_file.read()
            if not data:
                raise ValueError(_ops_text(str(getattr(request.state, "lang", "de") or "de"), "backup_file_empty", "Backup file is empty."))
            payload = parse_config_backup_payload(data)
            restore_config_backup_payload(
                base_dir=deps.base_dir,
                payload=payload,
                write_raw_config=deps.write_raw_config,
                get_secure_store=deps.get_secure_store,
                error_interpreter_path=deps.error_interpreter_path,
            )
            deps.refresh_skill_trigger_index()
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/backup?saved=1&info=backup_imported", request, fallback="/config")
        except Exception as exc:  # noqa: BLE001
            with suppress(Exception):
                restore_config_backup_payload(
                    base_dir=deps.base_dir,
                    payload=previous_snapshot,
                    write_raw_config=deps.write_raw_config,
                    get_secure_store=deps.get_secure_store,
                    error_interpreter_path=deps.error_interpreter_path,
                )
                deps.refresh_skill_trigger_index()
                deps.reload_runtime()
                rollback_restored = True
            lang = str(getattr(request.state, "lang", "de") or "de")
            message = str(exc).strip() or _ops_text(lang, "backup_import_failed", "Backup import failed.")
            if rollback_restored:
                message = _ops_text(lang, "backup_rollback_restored", "{message} Previous configuration was restored.", message=message)
            return deps.redirect_with_return_to(
                f"/config/backup?error={quote_plus(message)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/logs", response_class=HTMLResponse)
    async def config_logs_page(
        request: Request,
        saved: int = 0,
        pruned: int | None = None,
        reset: int | None = None,
        archive: str = "",
        factory_reset: int = 0,
        factory_qdrant: int | None = None,
        error: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        health = await pipeline.token_tracker.get_log_health()
        size_bytes = int(health.get("size_bytes", 0) or 0)
        if size_bytes >= 1024 * 1024:
            size_human = f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes >= 1024:
            size_human = f"{size_bytes / 1024:.1f} KB"
        else:
            size_human = f"{size_bytes} B"
        health["size_human"] = size_human
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/operations",
            page_return_to="/config/operations",
            config_nav="operations",
            page_heading=deps.msg(lang, "Logs & Retention", "Logs & retention"),
        )
        context.update(
            {
                "pruned": pruned,
                "reset": reset,
                "reset_archive": archive,
                "factory_reset": bool(factory_reset),
                "factory_qdrant": factory_qdrant,
                "token_tracking": settings.token_tracking,
                "health": health,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_logs.html", context=context)

    @app.post("/config/logs/save")
    async def config_logs_save(
        request: Request,
        enabled: str = Form("0"),
        retention_days: int = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            if retention_days < 0:
                raise ValueError(_ops_text(str(getattr(request.state, "lang", "de") or "de"), "retention_days_min", "retention_days must be >= 0."))
            active = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
            raw = deps.read_raw_config()
            raw.setdefault("token_tracking", {})
            if not isinstance(raw["token_tracking"], dict):
                raw["token_tracking"] = {}
            raw["token_tracking"]["enabled"] = active
            raw["token_tracking"]["retention_days"] = int(retention_days)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/logs?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/logs?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/logs/cleanup")
    async def config_logs_cleanup(request: Request, return_to: str = Form("")) -> RedirectResponse:
        try:
            settings = deps.get_settings()
            pipeline = deps.get_pipeline()
            removed = await pipeline.token_tracker.prune_old_entries(
                int(getattr(settings.token_tracking, "retention_days", 0) or 0)
            )
            return deps.redirect_with_return_to(
                f"/config/logs?pruned={int(removed.get('removed', 0) or 0)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/logs?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/logs/reset")
    async def config_logs_reset(
        request: Request,
        confirm_text: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            expected = "RESET"
            if str(confirm_text or "").strip().upper() != expected:
                raise ValueError(_ops_text(lang, "reset_confirm_exact", 'Please type "RESET" exactly to confirm.'))
            pipeline = deps.get_pipeline()
            removed = await pipeline.token_tracker.clear_log(archive=True)
            runtime_dir = (deps.base_dir / "data" / "runtime").resolve()
            for cache_name in ("stats_connections_cache.json",):
                try:
                    (runtime_dir / cache_name).unlink(missing_ok=True)
                except OSError:
                    pass
            archive_name = str(removed.get("archive_name", "") or "")
            archive_qs = f"&archive={quote_plus(archive_name)}" if archive_name else ""
            return deps.redirect_with_return_to(
                f"/config/logs?reset={int(removed.get('removed', 0) or 0)}{archive_qs}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = deps.friendly_route_error(
                lang,
                exc,
                _ops_text(lang, "stats_reset_failed", "Could not reset stats data."),
                "Could not reset stats data.",
            )
            return deps.redirect_with_return_to(
                f"/config/logs?error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/logs/factory-reset")
    async def config_logs_factory_reset(request: Request, confirm_text: str = Form("")) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            expected = "FACTORY RESET"
            if str(confirm_text or "").strip().upper() != expected:
                raise ValueError(_ops_text(lang, "factory_reset_confirm_exact", 'Please type "FACTORY RESET" exactly to confirm.'))

            settings = deps.get_settings()
            pipeline = deps.get_pipeline()
            raw = deps.read_raw_config()
            cleaned = deps.apply_factory_reset_to_raw_config(raw)
            deps.write_raw_config(cleaned)

            removed_stats = await pipeline.token_tracker.clear_log()
            removed_qdrant = await deps.clear_qdrant_factory_data(settings.memory)

            removed_files = 0
            for rel_dir in ("data/auth", "data/chat_history", "data/runtime", "data/recipes", "data/ssh_keys"):
                removed_files += deps.wipe_directory_contents((deps.base_dir / rel_dir).resolve())

            logs_dir = (deps.base_dir / "data" / "logs").resolve()
            for file_name in ("tokens.jsonl", "tokens.jsonl.bak_unknown_cleanup"):
                with suppress(OSError):
                    (logs_dir / file_name).unlink()

            deps.reload_runtime()

            info = _ops_text(lang, "factory_reset_done", "Factory reset completed. ARIA is back in first-start state.")
            response = RedirectResponse(
                url=(
                    f"/login?info={quote_plus(info)}"
                    f"&reset={int(removed_stats.get('removed', 0) or 0)}"
                    f"&qdrant={int(removed_qdrant)}"
                    f"&files={int(removed_files)}"
                ),
                status_code=303,
            )
            response.delete_cookie(deps.cookie_name_for_request(request, "auth", deps.auth_cookie))
            response.delete_cookie(deps.cookie_name_for_request(request, "username", deps.username_cookie))
            response.delete_cookie(deps.cookie_name_for_request(request, "memory_collection", deps.memory_collection_cookie))
            return response
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = deps.friendly_route_error(
                lang,
                exc,
                _ops_text(lang, "factory_reset_failed", "Could not run factory reset."),
                "Could not run factory reset.",
            )
            return RedirectResponse(url=f"/config/logs?error={quote_plus(error)}", status_code=303)
