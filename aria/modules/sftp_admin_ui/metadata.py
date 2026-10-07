"""SFTP metadata suggestion route authority."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LocalizedMessage = Callable[[str, str, str], str]


def register_sftp_metadata_route(
    app: FastAPI,
    *,
    sanitize_connection_name: Callable[[str | None], str],
    suggest_ssh_metadata_with_llm: Callable[..., Any],
    msg: LocalizedMessage,
) -> None:
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
        return await suggest_sftp_connection_metadata_response(
            lang=lang,
            connection_ref=connection_ref,
            service_url=service_url,
            connection_title=connection_title,
            connection_description=connection_description,
            connection_aliases=connection_aliases,
            connection_tags=connection_tags,
            sanitize_connection_name=sanitize_connection_name,
            suggest_ssh_metadata_with_llm=suggest_ssh_metadata_with_llm,
            msg=msg,
        )


async def suggest_sftp_connection_metadata_response(
    *,
    lang: str,
    connection_ref: str = "",
    service_url: str = "",
    connection_title: str = "",
    connection_description: str = "",
    connection_aliases: str = "",
    connection_tags: str = "",
    sanitize_connection_name: Callable[[str | None], str],
    suggest_ssh_metadata_with_llm: Callable[..., Any],
    msg: LocalizedMessage,
) -> JSONResponse:
    clean_service_url = str(service_url or "").strip()
    if not clean_service_url:
        return JSONResponse(
            {
                "ok": False,
                "error": msg(lang, "Service-URL fehlt.", "Service URL is missing."),
            },
            status_code=400,
        )
    suggestion = await suggest_ssh_metadata_with_llm(
        service_url=clean_service_url,
        connection_ref=sanitize_connection_name(connection_ref),
        current_title=str(connection_title or "").strip(),
        current_description=str(connection_description or "").strip(),
        current_aliases=str(connection_aliases or "").strip(),
        current_tags=str(connection_tags or "").strip(),
        lang=lang,
    )
    return JSONResponse({"ok": True, **suggestion})
