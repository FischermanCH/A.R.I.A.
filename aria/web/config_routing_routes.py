from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Any]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
RoleSanitizer = Callable[[str | None], str]
StringSanitizer = Callable[[str | None], str]
ConfigPageContextBuilder = Callable[..., dict[str, Any]]
LogicalBackSetter = Callable[[Request], str]
ConfigRedirector = Callable[..., RedirectResponse]
LocalizedMessage = Callable[[str, str, str], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
LinesParser = Callable[[str], list[str]]
CustomSkillManifestLoader = Callable[[], tuple[list[dict[str, Any]], list[str]]]
CustomSkillFileResolver = Callable[[str], Path]
CustomSkillSaver = Callable[[dict[str, Any]], dict[str, Any]]
TriggerIndexBuilder = Callable[[], dict[str, Any]]
SkillRoutingInfoFormatter = Callable[[str, str], str]
KeywordSuggester = Callable[..., Awaitable[list[str]]]
RoutingIndexStatusBuilder = Callable[[Any], Awaitable[dict[str, Any]]]
RoutingIndexTester = Callable[..., Awaitable[dict[str, Any]]]
RoutingIndexRebuilder = Callable[[Any], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ConfigRoutingRouteDeps:
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_auth_session_from_request: AuthSessionResolver
    sanitize_role: RoleSanitizer
    sanitize_skill_id: StringSanitizer
    build_config_page_context: ConfigPageContextBuilder
    set_logical_back_url: LogicalBackSetter
    redirect_with_return_to: ConfigRedirector
    msg: LocalizedMessage
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    parse_lines: LinesParser
    load_custom_skill_manifests: CustomSkillManifestLoader
    custom_skill_file: CustomSkillFileResolver
    save_custom_skill_manifest: CustomSkillSaver
    refresh_skill_trigger_index: TriggerIndexBuilder
    format_skill_routing_info: SkillRoutingInfoFormatter
    suggest_skill_keywords_with_llm: KeywordSuggester
    build_connection_routing_index_status: RoutingIndexStatusBuilder
    test_connection_routing_query: RoutingIndexTester
    rebuild_connection_routing_index: RoutingIndexRebuilder


def register_config_routing_routes(app: FastAPI, deps: ConfigRoutingRouteDeps) -> None:
    @app.get("/config/routing", response_class=HTMLResponse)
    async def config_routing_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        scope: str = "default",
        routing_query: str = "",
        routing_kind: str = "auto",
        routing_llm_qdrant_only: int = 0,
    ) -> HTMLResponse:
        if str(routing_query or "").strip():
            target_url = (
                f"/config/workbench/routing?scope={quote_plus(str(scope or 'default'))}"
                f"&routing_query={quote_plus(str(routing_query or '').strip())}"
                f"&routing_kind={quote_plus(str(routing_kind or 'auto').strip().lower() or 'auto')}"
            )
            if bool(int(routing_llm_qdrant_only or 0)):
                target_url += "&routing_llm_qdrant_only=1"
            return deps.redirect_with_return_to(target_url, request, fallback="/config")
        settings = deps.get_settings()
        lang = str(getattr(request.state, "lang", "de") or "de")
        return_to = deps.set_logical_back_url(request, fallback="/config/workbench")
        supported_languages = list(getattr(request.state, "supported_languages", []) or [])
        selected_scope = str(scope or "default").strip().lower() or "default"
        valid_scopes = {"default", *supported_languages}
        if selected_scope not in valid_scopes:
            selected_scope = "default"

        routing = settings.routing.for_language(None if selected_scope == "default" else selected_scope)
        routing_index_status = await deps.build_connection_routing_index_status(settings)
        routing_qdrant_meta = {
            "enabled": bool(getattr(settings.routing, "qdrant_connection_routing_enabled", False)),
            "score_threshold": float(getattr(settings.routing, "qdrant_score_threshold", 0.72) or 0.0),
            "candidate_limit": int(getattr(settings.routing, "qdrant_candidate_limit", 5) or 5),
            "ask_on_low_confidence": bool(getattr(settings.routing, "qdrant_ask_on_low_confidence", True)),
        }
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/config/workbench",
            page_return_to="/config/workbench",
            config_nav="workbench",
            page_heading=deps.msg(lang, "Routing & Memory Rules", "Routing & memory rules"),
        )
        context.update(
            {
                "routing_index_status": routing_index_status,
                "routing_qdrant_meta": routing_qdrant_meta,
                "scope_options": ["default", *supported_languages],
                "selected_scope": selected_scope,
                "store_keywords_text": "\n".join(routing.memory_store_keywords),
                "recall_keywords_text": "\n".join(routing.memory_recall_keywords),
                "forget_keywords_text": "\n".join(routing.memory_forget_keywords),
                "store_prefixes_text": "\n".join(routing.memory_store_prefixes),
                "recall_cleanup_text": "\n".join(routing.memory_recall_cleanup_keywords),
                "return_to": return_to,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_routing.html", context=context)

    @app.get("/config/workbench/routing", response_class=HTMLResponse)
    async def config_routing_workbench_page(
        request: Request,
        scope: str = "default",
        routing_query: str = "",
        routing_kind: str = "auto",
        routing_llm_qdrant_only: int = 0,
    ) -> HTMLResponse:
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        lang = str(getattr(request.state, "lang", "de") or "de")
        return_to = deps.set_logical_back_url(request, fallback="/config/workbench")
        supported_languages = list(getattr(request.state, "supported_languages", []) or [])
        selected_scope = str(scope or "default").strip().lower() or "default"
        valid_scopes = {"default", *supported_languages}
        if selected_scope not in valid_scopes:
            selected_scope = "default"

        routing_index_status = await deps.build_connection_routing_index_status(settings)
        routing_test_result = None
        llm_qdrant_only = bool(int(routing_llm_qdrant_only or 0))
        if str(routing_query or "").strip():
            routing_test_result = await deps.test_connection_routing_query(
                settings,
                routing_query,
                preferred_kind=routing_kind,
                llm_ignore_deterministic=llm_qdrant_only,
                llm_client=getattr(pipeline, "llm_client", None),
                language=str(getattr(request.state, "lang", "") or getattr(settings.ui, "language", "") or ""),
            )
        context = deps.build_config_page_context(
            request,
            logical_back_fallback="/config/workbench",
            page_return_to="/config/workbench",
            config_nav="workbench",
            page_heading=deps.msg(lang, "Routing Workbench", "Routing workbench"),
        )
        context.update(
            {
                "routing_index_status": routing_index_status,
                "routing_test_result": routing_test_result,
                "routing_test_query": str(routing_query or "").strip(),
                "routing_test_kind": str(routing_kind or "auto").strip().lower() or "auto",
                "routing_test_llm_qdrant_only": llm_qdrant_only,
                "routing_test_kind_options": ["auto", "ssh", "sftp", "rss", "discord", "http_api"],
                "selected_scope": selected_scope,
                "return_to": return_to,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_routing_workbench.html", context=context)

    @app.get("/config/routing-index/status")
    async def config_routing_index_status(request: Request) -> JSONResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return JSONResponse({"status": "error", "message": "Admin access required."}, status_code=403)
        return JSONResponse(await deps.build_connection_routing_index_status(deps.get_settings()))

    @app.get("/config/routing-index/test")
    async def config_routing_index_test(
        request: Request,
        query: str = "",
        preferred_kind: str = "auto",
        llm_qdrant_only: int = 0,
    ) -> JSONResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return JSONResponse({"status": "error", "message": "Admin access required."}, status_code=403)
        settings = deps.get_settings()
        return JSONResponse(
            await deps.test_connection_routing_query(
                settings,
                query,
                preferred_kind=preferred_kind,
                llm_ignore_deterministic=bool(int(llm_qdrant_only or 0)),
                llm_client=getattr(deps.get_pipeline(), "llm_client", None),
                language=str(getattr(request.state, "lang", "") or getattr(settings.ui, "language", "") or ""),
            )
        )

    @app.post("/config/routing-index/rebuild")
    async def config_routing_index_rebuild(
        request: Request,
        scope: str = Form("default"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return deps.redirect_with_return_to(
                "/config/routing?error=Admin+access+required.",
                request,
                fallback="/config",
                return_to=return_to,
            )
        selected_scope = str(scope or "default").strip().lower() or "default"
        try:
            result = await deps.rebuild_connection_routing_index(deps.get_settings())
        except Exception as exc:
            return deps.redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        message = str(result.get("message", "") or "").strip() or "Routing index rebuild finished."
        target_param = "info" if str(result.get("status", "") or "").lower() != "error" else "error"
        return deps.redirect_with_return_to(
            f"/config/routing?scope={quote_plus(selected_scope)}&{target_param}={quote_plus(message)}",
            request,
            fallback="/config",
            return_to=return_to,
        )

    @app.post("/config/routing/qdrant/save")
    async def config_routing_qdrant_save(
        request: Request,
        scope: str = Form("default"),
        qdrant_connection_routing_enabled: str = Form("0"),
        qdrant_score_threshold: str = Form("0.72"),
        qdrant_candidate_limit: str = Form("5"),
        qdrant_ask_on_low_confidence: str = Form("0"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        selected_scope = str(scope or "default").strip().lower() or "default"
        if deps.sanitize_role(auth.get("role")) != "admin":
            return deps.redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&error=Admin+access+required.",
                request,
                fallback="/config",
                return_to=return_to,
            )
        try:
            threshold = float(str(qdrant_score_threshold or "0.72").strip().replace(",", "."))
            if threshold < 0.0 or threshold > 1.0:
                raise ValueError("Threshold muss zwischen 0.00 und 1.00 liegen.")
            candidate_limit = int(str(qdrant_candidate_limit or "5").strip())
            if candidate_limit < 1 or candidate_limit > 20:
                raise ValueError("Limit muss zwischen 1 und 20 liegen.")

            raw = deps.read_raw_config()
            raw.setdefault("routing", {})
            if not isinstance(raw["routing"], dict):
                raw["routing"] = {}
            routing_section = raw["routing"]
            routing_section["qdrant_connection_routing_enabled"] = str(qdrant_connection_routing_enabled or "") == "1"
            routing_section["qdrant_score_threshold"] = round(threshold, 4)
            routing_section["qdrant_candidate_limit"] = candidate_limit
            routing_section["qdrant_ask_on_low_confidence"] = str(qdrant_ask_on_low_confidence or "") == "1"
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&info={quote_plus('Live-Qdrant-Routing gespeichert.')}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/routing?scope={quote_plus(selected_scope)}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/routing/save")
    async def config_routing_save(
        request: Request,
        scope: str = Form("default"),
        memory_store_keywords: str = Form(""),
        memory_recall_keywords: str = Form(""),
        memory_forget_keywords: str = Form(""),
        memory_store_prefixes: str = Form(""),
        memory_recall_cleanup_keywords: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            store_keywords = deps.parse_lines(memory_store_keywords)
            recall_keywords = deps.parse_lines(memory_recall_keywords)
            forget_keywords = deps.parse_lines(memory_forget_keywords)
            store_prefixes = deps.parse_lines(memory_store_prefixes)
            recall_cleanup = deps.parse_lines(memory_recall_cleanup_keywords)
            if not store_keywords:
                raise ValueError("memory_store_keywords darf nicht leer sein.")
            if not recall_keywords:
                raise ValueError("memory_recall_keywords darf nicht leer sein.")
            if not forget_keywords:
                raise ValueError("memory_forget_keywords darf nicht leer sein.")
            if not store_prefixes:
                raise ValueError("memory_store_prefixes darf nicht leer sein.")
            if not recall_cleanup:
                raise ValueError("memory_recall_cleanup_keywords darf nicht leer sein.")

            supported_languages = list(getattr(request.state, "supported_languages", []) or [])
            selected_scope = str(scope or "default").strip().lower() or "default"
            valid_scopes = {"default", *supported_languages}
            if selected_scope not in valid_scopes:
                raise ValueError("Ungültiger Routing-Scope.")

            raw = deps.read_raw_config()
            raw.setdefault("routing", {})
            if not isinstance(raw["routing"], dict):
                raw["routing"] = {}
            routing_section = raw["routing"]
            payload = {
                "memory_store_keywords": store_keywords,
                "memory_recall_keywords": recall_keywords,
                "memory_forget_keywords": forget_keywords,
                "memory_store_prefixes": store_prefixes,
                "memory_recall_cleanup_keywords": recall_cleanup,
            }
            if selected_scope == "default":
                routing_section["default"] = payload
                routing_section["memory_store_keywords"] = store_keywords
                routing_section["memory_recall_keywords"] = recall_keywords
                routing_section["memory_forget_keywords"] = forget_keywords
                routing_section["memory_store_prefixes"] = store_prefixes
                routing_section["memory_recall_cleanup_keywords"] = recall_cleanup
            else:
                routing_section.setdefault("languages", {})
                if not isinstance(routing_section["languages"], dict):
                    routing_section["languages"] = {}
                routing_section["languages"][selected_scope] = payload
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"/config/routing?saved=1&scope={quote_plus(selected_scope)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/routing?scope={quote_plus(str(scope or 'default'))}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/skill-routing", response_class=HTMLResponse)
    async def config_skill_routing_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        lang = str(getattr(request.state, "lang", "de") or "de")
        manifests, load_errors = deps.load_custom_skill_manifests()
        index = deps.refresh_skill_trigger_index()
        rows: list[dict[str, Any]] = []
        for row in manifests:
            skill_id = str(row.get("id", "")).strip()
            rows.append(
                {
                    "id": skill_id,
                    "name": str(row.get("name", skill_id)).strip() or skill_id,
                    "router_keywords_text": ", ".join(row.get("router_keywords", [])) if isinstance(row.get("router_keywords", []), list) else "",
                    "json_path": str(deps.custom_skill_file(skill_id).relative_to(Path.cwd() / "fischerman" / "ARIA")) if False else "",
                }
            )
        # Use the configured file resolver against the actual repo base kept in the path object.
        for row in rows:
            skill_id = str(row.get("id", "")).strip()
            if skill_id:
                row["json_path"] = str(deps.custom_skill_file(skill_id))
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/workbench",
            page_return_to="/config/workbench",
            config_nav="workbench",
            page_heading=deps.msg(lang, "Skill Routing", "Skill routing"),
        )
        context.update(
            {
                "info_message": deps.format_skill_routing_info(lang, info),
                "rows": rows,
                "index": index,
                "load_errors": load_errors,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_skill_routing.html", context=context)

    @app.post("/config/skill-routing/save")
    async def config_skill_routing_save(
        request: Request,
        skill_id: str = Form(...),
        router_keywords: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            clean_id = deps.sanitize_skill_id(skill_id)
            if not clean_id:
                raise ValueError("Ungültige Skill-ID.")
            target = deps.custom_skill_file(clean_id)
            if not target.exists():
                raise ValueError("Skill-Datei nicht gefunden.")
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Skill-Datei ist kein JSON-Objekt.")
            raw["router_keywords"] = [item.strip() for item in str(router_keywords).split(",") if item.strip()]
            clean = deps.save_custom_skill_manifest(raw)
            return deps.redirect_with_return_to(
                f"/config/skill-routing?saved=1&info={quote_plus(clean.get('id', clean_id))}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return deps.redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/skill-routing/suggest")
    async def config_skill_routing_suggest(
        request: Request,
        skill_id: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            clean_id = deps.sanitize_skill_id(skill_id)
            if not clean_id:
                raise ValueError("Ungültige Skill-ID.")
            target = deps.custom_skill_file(clean_id)
            if not target.exists():
                raise ValueError("Skill-Datei nicht gefunden.")
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Skill-Datei ist kein JSON-Objekt.")
            lang = str(getattr(request.state, "lang", "de") or "de")
            keywords = await deps.suggest_skill_keywords_with_llm(raw, language=lang)
            if not keywords:
                raise ValueError("Keine Trigger-Keywords erzeugt.")
            raw["router_keywords"] = keywords
            deps.save_custom_skill_manifest(raw)
            return deps.redirect_with_return_to(
                f"/config/skill-routing?saved=1&info={quote_plus(f'suggest:{clean_id}:{len(keywords)}')}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return deps.redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/skill-routing/suggest-all")
    async def config_skill_routing_suggest_all(request: Request, return_to: str = Form("")) -> RedirectResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            manifests, _ = deps.load_custom_skill_manifests()
            lang = str(getattr(request.state, "lang", "de") or "de")
            updated = 0
            total_keywords = 0
            for manifest in manifests:
                skill_id = deps.sanitize_skill_id(manifest.get("id", ""))
                if not skill_id:
                    continue
                keywords = await deps.suggest_skill_keywords_with_llm(manifest, language=lang)
                if not keywords:
                    continue
                manifest["router_keywords"] = keywords
                deps.save_custom_skill_manifest(manifest)
                updated += 1
                total_keywords += len(keywords)
            return deps.redirect_with_return_to(
                f"/config/skill-routing?saved=1&info={quote_plus(f'suggest-all:{updated}:{total_keywords}')}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return deps.redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/skill-routing/rebuild")
    async def config_skill_routing_rebuild(request: Request, return_to: str = Form("")) -> RedirectResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return RedirectResponse(url="/skills?error=no_admin", status_code=303)
        try:
            deps.refresh_skill_trigger_index()
            return deps.redirect_with_return_to(
                "/config/skill-routing?saved=1&info=rebuild",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except OSError as exc:
            return deps.redirect_with_return_to(
                f"/config/skill-routing?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )
