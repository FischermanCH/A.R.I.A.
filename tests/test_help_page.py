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


def test_product_info_page_renders_docs_nav_and_markdown() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/product-info?doc=overview")

    assert response.status_code == 200
    assert "Produkt-Info" in response.text or "Product Info" in response.text
    assert "<article class=\"doc-markdown" in response.text
    assert "help-doc-pill" in response.text


def test_localized_doc_path_prefers_matching_language_file() -> None:
    base_dir = Path("/home/fischerman/ARIA")

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
    assert "fischerman.ch/projects/a-r-i-a-adaptive-reasoning-intelligence-agent/" in response.text
