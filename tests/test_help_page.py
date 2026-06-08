from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import aria.main as main_mod


def test_help_page_renders_wiki_doc_hub() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/help?doc=quick-start")

    assert response.status_code == 200
    assert "Quick Start" in response.text
    assert "<article class=\"doc-markdown help-doc-article docs-content-surface\">" in response.text
    assert "help-doc-inline-nav" in response.text
    assert "/help?doc=qdrant" in response.text
    assert "/help?doc=searxng" in response.text
    assert "/licenses" in response.text


def test_help_home_renders_clickable_start_links() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/help")

    assert response.status_code == 200
    for doc_id in (
        "quick-start",
        "memory",
        "connections",
        "skills",
        "releases",
        "pricing",
        "security",
        "alpha-help-system",
        "help-system",
    ):
        assert f'href="/help?doc={doc_id}"' in response.text
    assert "<code>Quick Start</code>" not in response.text


def test_product_info_page_renders_docs_nav_and_markdown() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/product-info?doc=overview")

    assert response.status_code == 200
    assert "Produkt-Info" in response.text or "Product Info" in response.text
    assert "<article class=\"doc-markdown" in response.text
    assert "help-doc-pill" in response.text


def test_localized_doc_path_prefers_matching_language_file() -> None:
    base_dir = Path(__file__).resolve().parents[1]

    assert main_mod._localized_doc_path(base_dir, "docs/wiki/Quick-Start.md", "de") == "docs/wiki/Quick-Start.de.md"
    assert main_mod._localized_doc_path(base_dir, "docs/help/pricing.md", "en") == "docs/help/pricing.en.md"
    assert main_mod._localized_doc_path(base_dir, "docs/wiki/Quick-Start.md", "fr") == "docs/wiki/Quick-Start.md"


def test_help_page_renders_qdrant_doc() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/help?doc=qdrant")

    assert response.status_code == 200
    assert "Qdrant" in response.text
    assert "semantic" in response.text or "semant" in response.text


def test_licenses_page_renders_core_entries() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/licenses")

    assert response.status_code == 200
    assert "help-doc-pill" in response.text
    assert "MIT" in response.text
    assert "Apache-2.0" in response.text
    assert "AGPL-3.0" in response.text
    assert "github.com/qdrant/qdrant" in response.text
    assert "github.com/searxng/searxng" in response.text
    assert "github.com/qdrant/qdrant" in response.text

def test_base_template_declares_durable_favicon_assets() -> None:
    template = Path("aria/templates/base.html").read_text(encoding="utf-8")

    assert 'href="/favicon.ico' in template
    assert 'sizes="32x32" href="/static/favicon-32x32.png' in template
    assert 'sizes="16x16" href="/static/favicon-16x16.png' in template
    assert 'rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png' in template


def test_favicon_route_serves_real_icon_file() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/x-icon")
    assert response.content.startswith(b"\x00\x00\x01\x00")


def test_favicon_static_png_variants_exist() -> None:
    static_dir = Path("aria/static")

    for name in ("favicon-16x16.png", "favicon-32x32.png", "favicon-48x48.png", "apple-touch-icon.png"):
        payload = (static_dir / name).read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(payload) > 100
