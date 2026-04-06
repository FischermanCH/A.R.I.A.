from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import aria.main as main_mod


def test_help_page_renders_wiki_doc_hub() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/help?doc=quick-start")

    assert response.status_code == 200
    assert "docs/wiki/Quick-Start.md" in response.text
    assert "Quick Start" in response.text
    assert "Wiki &amp; Guides" in response.text or "Wiki & Guides" in response.text
    assert "<article class=\"doc-markdown\">" in response.text


def test_localized_doc_path_prefers_matching_language_file() -> None:
    base_dir = Path("/home/fischerman/ARIA")

    assert main_mod._localized_doc_path(base_dir, "docs/wiki/Quick-Start.md", "de") == "docs/wiki/Quick-Start.de.md"
    assert main_mod._localized_doc_path(base_dir, "docs/help/pricing.md", "en") == "docs/help/pricing.en.md"
    assert main_mod._localized_doc_path(base_dir, "docs/wiki/Quick-Start.md", "fr") == "docs/wiki/Quick-Start.md"
