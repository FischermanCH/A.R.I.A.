from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


LocalizedMessage = Callable[[str, str, str], str]


@dataclass(frozen=True)
class ConnectionMetadataRouteDeps:
    sanitize_connection_name: Callable[[str | None], str]
    normalize_rss_feed_url_for_dedupe: Callable[[str | None], str]
    suggest_ssh_metadata_with_llm: Callable[..., Any]
    suggest_rss_metadata_with_llm: Callable[..., Any]
    suggest_website_metadata_with_llm: Callable[..., Any]
    msg: LocalizedMessage


def register_connection_metadata_routes(app: FastAPI, deps: ConnectionMetadataRouteDeps) -> None:
    @app.get("/config/connections/ssh/suggest-metadata")
    async def config_connections_ssh_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        service_url: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_service_url = str(service_url or "").strip()
        if not clean_service_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": deps.msg(lang, "Service-URL fehlt.", "Service URL is missing."),
                },
                status_code=400,
            )
        suggestion = await deps.suggest_ssh_metadata_with_llm(
            service_url=clean_service_url,
            connection_ref=deps.sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})

    @app.get("/config/connections/sftp/suggest-metadata")
    async def config_connections_sftp_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        service_url: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_service_url = str(service_url or "").strip()
        if not clean_service_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": deps.msg(lang, "Service-URL fehlt.", "Service URL is missing."),
                },
                status_code=400,
            )
        suggestion = await deps.suggest_ssh_metadata_with_llm(
            service_url=clean_service_url,
            connection_ref=deps.sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})

    @app.get("/config/connections/rss/suggest-metadata")
    async def config_connections_rss_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        feed_url: str = "",
        group_name: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_feed_url = deps.normalize_rss_feed_url_for_dedupe(feed_url)
        if not clean_feed_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": deps.msg(lang, "Feed-URL fehlt.", "Feed URL is missing."),
                },
                status_code=400,
            )
        suggestion = await deps.suggest_rss_metadata_with_llm(
            feed_url=clean_feed_url,
            connection_ref=deps.sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            group_name=str(group_name or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})

    @app.get("/config/connections/websites/suggest-metadata")
    async def config_connections_website_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        url: str = "",
        group_name: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_url = str(url or "").strip()
        if not clean_url:
            return JSONResponse(
                {
                    "ok": False,
                    "error": deps.msg(lang, "URL fehlt.", "URL is missing."),
                },
                status_code=400,
            )
        suggestion = await deps.suggest_website_metadata_with_llm(
            url=clean_url,
            connection_ref=deps.sanitize_connection_name(connection_ref),
            current_title=str(connection_title or "").strip(),
            current_description=str(connection_description or "").strip(),
            current_aliases=str(connection_aliases or "").strip(),
            current_tags=str(connection_tags or "").strip(),
            group_name=str(group_name or "").strip(),
            lang=lang,
        )
        return JSONResponse({"ok": True, **suggestion})
