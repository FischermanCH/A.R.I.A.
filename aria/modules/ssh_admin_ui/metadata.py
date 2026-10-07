"""SSH metadata suggestion route authority."""

from __future__ import annotations

import re
from html import unescape
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LocalizedMessage = Callable[[str, str, str], str]


def register_ssh_metadata_route(
    app: FastAPI,
    *,
    sanitize_connection_name: Callable[[str | None], str],
    suggest_ssh_metadata_with_llm_callback: Callable[..., Any],
    msg: LocalizedMessage,
) -> None:
    @app.get("/config/connections/ssh/suggest-metadata")
    async def config_connections_ssh_suggest_metadata(
        request: Request,
        connection_ref: str = "",
        host: str = "",
        user: str = "",
        port: str = "",
        service_url: str = "",
        connection_title: str = "",
        connection_description: str = "",
        connection_aliases: str = "",
        connection_tags: str = "",
    ) -> JSONResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return await suggest_ssh_connection_metadata_response(
            lang=lang,
            connection_ref=connection_ref,
            host=host,
            user=user,
            port=port,
            service_url=service_url,
            connection_title=connection_title,
            connection_description=connection_description,
            connection_aliases=connection_aliases,
            connection_tags=connection_tags,
            sanitize_connection_name=sanitize_connection_name,
            suggest_ssh_metadata_with_llm=suggest_ssh_metadata_with_llm_callback,
            msg=msg,
        )


def _extract_html_attribute_map(tag_html: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in re.finditer(r'([a-zA-Z_:][\w:.-]*)\s*=\s*(["\'])(.*?)\2', str(tag_html or ""), flags=re.DOTALL):
        key = str(match.group(1) or "").strip().lower()
        if not key:
            continue
        attrs[key] = unescape(str(match.group(3) or "").strip())
    return attrs


def _clean_html_text(value: str, max_length: int = 240) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def extract_ssh_service_seed(service_url: str, *, web_metadata_headers: dict[str, str]) -> dict[str, Any]:
    clean_url = str(service_url or "").strip()
    parsed = urlparse(clean_url)
    host = str(parsed.netloc or "").strip().lower()
    host_short = host[4:] if host.startswith("www.") else host
    fallback_aliases = [value for value in [host_short, host_short.split(".", 1)[0].replace("-", " ")] if value]
    seed = {
        "service_title": host_short or clean_url,
        "service_description": "",
        "keywords": [],
        "host": host_short,
        "aliases": fallback_aliases,
    }
    if not clean_url:
        return seed
    req = URLRequest(clean_url, headers=web_metadata_headers, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            payload = resp.read(256 * 1024)
    except Exception:
        return seed
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        return seed

    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    title = _clean_html_text(title_match.group(1), 120) if title_match else ""
    meta_description = ""
    keywords: list[str] = []
    og_title = ""
    h1_title = ""

    for match in re.finditer(r"<meta\b[^>]*>", text, flags=re.IGNORECASE):
        attrs = _extract_html_attribute_map(match.group(0))
        key = str(attrs.get("name") or attrs.get("property") or "").strip().lower()
        content = _clean_html_text(attrs.get("content", ""), 240)
        if not key or not content:
            continue
        if key in {"description", "og:description", "twitter:description"} and not meta_description:
            meta_description = content
        elif key in {"keywords", "news_keywords"} and not keywords:
            keywords = [item.strip()[:24] for item in re.split(r"[;,]", content) if item.strip()][:8]
        elif key in {"og:title", "twitter:title"} and not og_title:
            og_title = content[:120]

    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.IGNORECASE | re.DOTALL)
    if h1_match:
        h1_title = _clean_html_text(h1_match.group(1), 120)

    resolved_title = title or og_title or h1_title
    if resolved_title:
        seed["service_title"] = resolved_title
    if meta_description:
        seed["service_description"] = meta_description
    seed["keywords"] = keywords
    return seed


async def suggest_ssh_metadata_with_llm(
    *,
    llm_client: Any,
    suggest_connection_metadata_with_llm: Callable[..., Any],
    web_metadata_headers: dict[str, str],
    service_url: str,
    host: str = "",
    user: str = "",
    port: str = "",
    connection_ref: str,
    current_title: str,
    current_description: str,
    current_aliases: str,
    current_tags: str,
    lang: str,
) -> dict[str, Any]:
    clean_service_url = str(service_url or "").strip()
    clean_host = str(host or "").strip()
    clean_user = str(user or "").strip()
    clean_port = str(port or "").strip()
    if clean_service_url:
        seed = extract_ssh_service_seed(clean_service_url, web_metadata_headers=web_metadata_headers)
        source_label = "Service URL"
        source_value = clean_service_url
    else:
        host_short = clean_host.split(".", 1)[0].replace("-", " ")
        seed = {
            "service_title": clean_host or connection_ref,
            "service_description": "SSH host profile",
            "keywords": [item for item in ["ssh", clean_user, host_short] if item],
            "host": clean_host,
            "aliases": [item for item in [connection_ref, clean_host, host_short] if item],
        }
        source_label = "SSH host"
        source_value = f"{clean_user + '@' if clean_user else ''}{clean_host}{':' + clean_port if clean_port else ''}"
    return await suggest_connection_metadata_with_llm(
        llm_client,
        connection_kind_label="SSH",
        connection_ref=connection_ref,
        source_label=source_label,
        source_value=source_value,
        detected_title=seed["service_title"],
        detected_description=seed["service_description"],
        detected_keywords=seed["keywords"],
        fallback_aliases=seed["aliases"],
        current_title=current_title,
        current_description=current_description,
        current_aliases=current_aliases,
        current_tags=current_tags,
        lang=lang,
        goal_text=(
            "Goal: produce user-friendly metadata that helps ARIA route chat requests to this SSH connection. "
            "Aliases should reflect how someone would naturally refer to this host or the service behind it."
        ),
    )


async def autofill_service_connection_metadata(
    *,
    llm_client: Any,
    suggest_connection_metadata_with_llm: Callable[..., Any],
    connection_metadata_is_sparse: Callable[..., bool],
    web_metadata_headers: dict[str, str],
    connection_ref: str,
    service_url: str,
    current_title: str,
    current_description: str,
    current_aliases: str,
    current_tags: str,
    lang: str,
) -> tuple[dict[str, str], bool]:
    metadata = {
        "title": str(current_title or "").strip(),
        "description": str(current_description or "").strip(),
        "aliases": str(current_aliases or "").strip(),
        "tags": str(current_tags or "").strip(),
    }
    clean_service_url = str(service_url or "").strip()
    if not clean_service_url:
        return metadata, False
    if not connection_metadata_is_sparse(
        title=metadata["title"],
        description=metadata["description"],
        aliases=metadata["aliases"],
        tags=metadata["tags"],
    ):
        return metadata, False
    suggestion = await suggest_ssh_metadata_with_llm(
        llm_client=llm_client,
        suggest_connection_metadata_with_llm=suggest_connection_metadata_with_llm,
        web_metadata_headers=web_metadata_headers,
        service_url=clean_service_url,
        connection_ref=connection_ref,
        current_title=metadata["title"],
        current_description=metadata["description"],
        current_aliases=metadata["aliases"],
        current_tags=metadata["tags"],
        lang=lang,
    )
    return (
        {
            "title": str(suggestion.get("title", "") or "").strip(),
            "description": str(suggestion.get("description", "") or "").strip(),
            "aliases": str(suggestion.get("aliases", "") or "").strip(),
            "tags": str(suggestion.get("tags", "") or "").strip(),
        },
        True,
    )


async def suggest_ssh_connection_metadata_response(
    *,
    lang: str,
    connection_ref: str = "",
    host: str = "",
    user: str = "",
    port: str = "",
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
    clean_host = str(host or "").strip()
    if not clean_service_url and not clean_host:
        return JSONResponse(
            {
                "ok": False,
                "error": msg(lang, "Host/IP oder Service-URL fehlt.", "Host/IP or service URL is missing."),
            },
            status_code=400,
        )
    suggestion = await suggest_ssh_metadata_with_llm(
        service_url=clean_service_url,
        host=clean_host,
        user=str(user or "").strip(),
        port=str(port or "").strip(),
        connection_ref=sanitize_connection_name(connection_ref),
        current_title=str(connection_title or "").strip(),
        current_description=str(connection_description or "").strip(),
        current_aliases=str(connection_aliases or "").strip(),
        current_tags=str(connection_tags or "").strip(),
        lang=lang,
    )
    return JSONResponse({"ok": True, **suggestion})
