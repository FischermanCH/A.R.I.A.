from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
LocalizedDocPathResolver = Callable[[Path, str, str], str]
DocTextReader = Callable[[Path, str], str]
MarkdownRenderer = Callable[[str], Any]
Translator = Callable[[Request, str, str], str]


@dataclass(frozen=True)
class DocsSurfaceRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    localized_doc_path: LocalizedDocPathResolver
    read_doc_text: DocTextReader
    render_markdown_doc: MarkdownRenderer
    translate: Translator
    help_doc_catalog: tuple[dict[str, Any], ...]
    help_doc_map: dict[str, dict[str, Any]]
    help_doc_groups: tuple[dict[str, Any], ...]
    product_doc_catalog: tuple[dict[str, Any], ...]
    product_doc_map: dict[str, dict[str, Any]]
    product_info_asset_map: dict[str, Path]


def register_docs_surface_routes(app: FastAPI, deps: DocsSurfaceRouteDeps) -> None:
    @app.get("/help", response_class=HTMLResponse)
    async def help_page(request: Request, doc: str = "home") -> HTMLResponse:
        settings = deps.get_settings()
        username = deps.get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de").strip().lower()
        selected_doc = deps.help_doc_map.get(doc) or deps.help_doc_catalog[0]
        localized_help_path = deps.localized_doc_path(deps.base_dir, selected_doc["path"], lang)
        help_text = deps.read_doc_text(deps.base_dir, localized_help_path)
        help_sections = [
            {
                **group,
                "docs": [entry for entry in deps.help_doc_catalog if entry.get("group") == group["id"]],
            }
            for group in deps.help_doc_groups
        ]
        return deps.templates.TemplateResponse(
            request=request,
            name="help.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "help_docs": deps.help_doc_catalog,
                "help_sections": help_sections,
                "selected_doc": selected_doc,
                "help_path": localized_help_path,
                "help_text": help_text,
                "help_html": deps.render_markdown_doc(help_text),
            },
        )

    @app.get("/product-info", response_class=HTMLResponse)
    async def product_info_page(request: Request, doc: str = "overview") -> HTMLResponse:
        settings = deps.get_settings()
        username = deps.get_username_from_request(request)
        selected_doc = deps.product_doc_map.get(doc) or deps.product_doc_catalog[0]
        doc_path = deps.base_dir / selected_doc["path"]
        doc_text = ""
        if doc_path.exists():
            try:
                doc_text = doc_path.read_text(encoding="utf-8")
            except OSError:
                doc_text = ""
        return deps.templates.TemplateResponse(
            request=request,
            name="product_info.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "product_docs": deps.product_doc_catalog,
                "selected_doc": selected_doc,
                "doc_path": selected_doc["path"],
                "doc_text": doc_text,
                "doc_html": deps.render_markdown_doc(doc_text),
            },
        )

    @app.get("/licenses", response_class=HTMLResponse)
    async def licenses_page(request: Request) -> HTMLResponse:
        settings = deps.get_settings()
        username = deps.get_username_from_request(request)
        aria_license_text = ""
        try:
            aria_license_text = (deps.base_dir / "LICENSE").read_text(encoding="utf-8")
        except OSError:
            aria_license_text = ""
        license_entries = [
            {
                "name": "ARIA",
                "license": "MIT",
                "source": "LICENSE",
                "url": "",
                "icon": "product",
                "summary": deps.translate(request, "licenses.aria_summary", "Die lokale Projektlizenz fuer ARIA selbst."),
            },
            {
                "name": "Qdrant",
                "license": "Apache-2.0",
                "source": "github.com/qdrant/qdrant",
                "url": "https://github.com/qdrant/qdrant",
                "icon": "memories",
                "summary": deps.translate(request, "licenses.qdrant_summary", "Vector- und Retrieval-Store fuer Memory, Dokumente und Routing-Indexe."),
            },
            {
                "name": "SearXNG",
                "license": "AGPL-3.0",
                "source": "github.com/searxng/searxng",
                "url": "https://github.com/searxng/searxng",
                "icon": "searxng",
                "summary": deps.translate(request, "licenses.searxng_summary", "Separater Suchdienst fuer Web-Recherche ueber die JSON-API."),
            },
        ]
        return deps.templates.TemplateResponse(
            request=request,
            name="licenses.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "help_docs": deps.help_doc_catalog,
                "license_entries": license_entries,
                "aria_license_text": aria_license_text,
            },
        )

    @app.get("/product-info/assets/{asset_name}")
    async def product_info_asset(asset_name: str) -> Response:
        asset_path = deps.product_info_asset_map.get(asset_name)
        if not asset_path or not asset_path.exists():
            return Response(status_code=404)
        try:
            return Response(
                content=asset_path.read_text(encoding="utf-8"),
                media_type="image/svg+xml; charset=utf-8",
            )
        except OSError:
            return Response(status_code=404)
