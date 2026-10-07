from __future__ import annotations

import json
import re
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
    assert "/licenses" in response.text


def test_help_home_renders_clickable_start_links() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/help")

    assert response.status_code == 200
    for doc_id in (
        "quick-start",
        "chat",
        "navigation",
        "memory",
        "notes",
        "connections",
        "skills",
        "agentic",
        "releases",
        "pricing",
        "security",
        "alpha-help-system",
        "help-system",
    ):
        assert f'href="/help?doc={doc_id}"' in response.text
    assert "<code>Quick Start</code>" not in response.text


def test_help_page_renders_current_workflow_docs() -> None:
    client = TestClient(main_mod.app)

    for doc_id, expected in {
        "chat": "Prompt Queue",
        "navigation": "Erweiterte Ansicht",
        "notes": "Markdown",
        "agentic": "Operator",
    }.items():
        response = client.get(f"/help?doc={doc_id}")

        assert response.status_code == 200
        assert expected in response.text


def test_product_info_page_renders_docs_nav_and_markdown() -> None:
    seen: list[tuple[str, str]] = []
    original = main_mod.TEMPLATES.env.globals["module_route_path"]

    def tracking_module_route_path(module_id: str, route_path: str):  # noqa: ANN202
        if module_id in {"release_update", "static_help_docs"}:
            seen.append((module_id, route_path))
        return original(module_id, route_path)

    main_mod.TEMPLATES.env.globals["module_route_path"] = tracking_module_route_path
    client = TestClient(main_mod.app)

    try:
        response = client.get("/product-info?doc=overview")
    finally:
        main_mod.TEMPLATES.env.globals["module_route_path"] = original

    assert response.status_code == 200
    assert "Produkt-Info" in response.text or "Product Info" in response.text
    assert "<article class=\"doc-markdown" in response.text
    assert "help-doc-pill" in response.text
    assert 'href="/updates"' in response.text
    assert ("release_update", "/updates") in seen
    assert ("static_help_docs", "/product-info") in seen


def test_product_info_page_uses_localized_product_doc_for_german() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/product-info?doc=overview", headers={"Accept-Language": "de"})

    assert response.status_code == 200
    assert "docs/product/overview.de.md" in response.text
    assert "ARIA ist ein kleiner, modularer KI-Assistent" in response.text
    assert "ARIA is a small, modular AI assistant" not in response.text


def test_product_info_page_keeps_english_product_doc_for_english() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/product-info?doc=overview&lang=en")

    assert response.status_code == 200
    assert "docs/product/overview.md" in response.text
    assert "ARIA is a small, modular AI assistant" in response.text


def test_help_page_language_query_can_switch_back_to_german_after_english() -> None:
    client = TestClient(main_mod.app)

    english = client.get("/help?doc=chat&lang=en")
    german = client.get("/help?doc=chat&lang=de")

    assert english.status_code == 200
    assert german.status_code == 200
    assert "Chat, Queue, and Confirmations" in english.text
    assert "Chat, Queue und Bestaetigungen" in german.text
    assert "Chat, Queue, and Confirmations" not in german.text


def test_docs_surface_pages_use_static_help_docs_template_readpoint(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []

    def fake_module_template_name(module_id: str, template_name: str) -> str | None:
        seen.append((module_id, template_name))
        return template_name

    monkeypatch.setattr("aria.modules.static_help_docs.routes.module_template_name", fake_module_template_name)
    client = TestClient(main_mod.app)

    assert client.get("/help").status_code == 200
    assert client.get("/product-info").status_code == 200
    assert client.get("/licenses").status_code == 200
    assert ("static_help_docs", "help.html") in seen
    assert ("static_help_docs", "product_info.html") in seen
    assert ("static_help_docs", "licenses.html") in seen


def test_docs_surface_pages_use_static_help_docs_route_readpoints(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []
    real_module_route_path = main_mod.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str) -> str:
        seen.append((module_id, route_path))
        return real_module_route_path(module_id, route_path) or ""

    monkeypatch.setitem(main_mod.TEMPLATES.env.globals, "module_route_path", tracking_module_route_path)
    client = TestClient(main_mod.app)

    help_response = client.get("/help")
    licenses_response = client.get("/licenses")
    product_info_response = client.get("/product-info")

    assert help_response.status_code == 200
    assert licenses_response.status_code == 200
    assert product_info_response.status_code == 200
    assert 'href="/help?doc=quick-start"' in help_response.text
    assert 'href="/help?doc=qdrant"' in help_response.text
    assert 'href="/licenses"' in help_response.text
    assert 'href="/help"' in licenses_response.text
    assert 'href="/help?doc=quick-start"' not in licenses_response.text
    assert 'href="/help"' in product_info_response.text
    assert 'href="/product-info"' in product_info_response.text
    assert 'href="/product-info?doc=overview"' in product_info_response.text
    assert ("static_help_docs", "/help") in seen
    assert ("static_help_docs", "/licenses") in seen
    assert ("static_help_docs", "/product-info") in seen
    assert ("release_update", "/updates") in seen


def test_base_shell_passive_navigation_uses_registry_route_readpoints(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []
    real_module_route_path = main_mod.module_route_path

    def tracking_module_route_path(module_id: str, route_path: str) -> str:
        seen.append((module_id, route_path))
        return real_module_route_path(module_id, route_path) or ""

    monkeypatch.setitem(main_mod.TEMPLATES.env.globals, "module_route_path", tracking_module_route_path)
    client = TestClient(main_mod.app)

    response = client.get("/help")

    assert response.status_code == 200
    assert 'href="/help?doc=' in response.text
    assert 'class="brand brand-home" href="/"' in response.text
    assert 'href="/login"' in response.text
    assert "None" not in response.text
    assert {
        ("chat_surface", "/"),
        ("release_update", "/update-reconnect-sw.js"),
        ("stats_ui", "/stats"),
        ("auth_ui", "/login"),
        ("auth_ui", "/logout"),
        ("static_help_docs", "/help"),
        ("release_update", "/updates"),
        ("notes", "/notes"),
    }.issubset(set(seen))


def test_product_info_asset_uses_static_help_docs_asset_readpoint(monkeypatch) -> None:
    seen: list[tuple[str, str, str]] = []

    def fake_module_asset_path(module_id: str, asset_name: str, base_dir: Path, *, asset_field: str) -> Path | None:
        seen.append((module_id, asset_name, asset_field))
        return base_dir / "docs" / "product" / asset_name

    monkeypatch.setattr("aria.modules.static_help_docs.routes.module_asset_path", fake_module_asset_path)
    client = TestClient(main_mod.app)

    response = client.get("/product-info/assets/aria_schichten_architektur.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert ("static_help_docs", "aria_schichten_architektur.svg", "product_info_assets") in seen


def test_product_info_asset_rejects_unregistered_asset() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/product-info/assets/missing.svg")

    assert response.status_code == 404


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
    assert "help-doc-inline-nav" not in response.text
    assert 'href="/help"' in response.text
    assert "Help System" in response.text or "Hilfe-System" in response.text
    assert 'href="/help?doc=quick-start"' not in response.text
    assert "MIT" in response.text
    assert "Permission is hereby granted" in response.text
    assert "Apache-2.0" in response.text
    assert "github.com/qdrant/qdrant" in response.text


def test_docker_image_packages_license_for_runtime_page() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY pyproject.toml README.md CHANGELOG.md LICENSE /app/" in dockerfile


def test_license_text_surface_uses_theme_text_token() -> None:
    stylesheet = Path("aria/static/style.css").read_text(encoding="utf-8")
    help_document_rule = stylesheet.split(".help-document {", 1)[1].split("}", 1)[0]

    assert "color: var(--text);" in help_document_rule


def test_licenses_template_omits_full_text_surface_when_license_text_is_empty() -> None:
    template = Path("aria/templates/licenses.html").read_text(encoding="utf-8")

    assert "{% if aria_license_text %}" in template
    assert "{% endif %}" in template.split('id="aria-license-text"', 1)[1]


def test_execution_history_labels_are_consistent_in_german_and_english() -> None:
    german = json.loads(Path("aria/i18n/de.json").read_text(encoding="utf-8"))
    english = json.loads(Path("aria/i18n/en.json").read_text(encoding="utf-8"))
    template = Path("aria/templates/activities.html").read_text(encoding="utf-8")

    assert german["activities.title"] == "Ausführungs-Historie"
    assert german["base.nav_activities"] == "Ausführungs-Historie"
    assert english["activities.title"] == "Execution History"
    assert english["base.nav_activities"] == "Execution History"
    assert "activities.title" in template

def test_base_template_declares_durable_favicon_assets() -> None:
    template = Path("aria/templates/base.html").read_text(encoding="utf-8")

    assert "module_route_path('chat_surface', '/')" in template
    assert "module_route_path('navigation_shell', '/favicon.ico')" in template
    assert "module_static_asset_url('navigation_shell', 'favicon-32x32.png')" in template
    assert "module_static_asset_url('navigation_shell', 'favicon-16x16.png')" in template
    assert "module_static_asset_url('navigation_shell', 'apple-touch-icon.png')" in template
    assert "module_static_asset_url('navigation_shell', 'style.css')" in template
    assert "module_static_asset_url('navigation_shell', 'logo-aria-v01.png')" in template
    assert "module_static_asset_url('navigation_shell', 'vendor/htmx-1.9.12.min.js')" in template


def test_templates_do_not_keep_hard_fallbacks_for_module_readpoints() -> None:
    fallback_pattern = re.compile(
        r"module_(?:route_path|route_prefix_path|static_asset_url)\([^)]*\)"
        r"[^\\n%}]*(?:\\bor\\b|else)\\s*['\\\"]/"
    )
    offenders: list[str] = []
    for template_path in sorted(Path("aria/templates").glob("*.html")):
        text = template_path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if fallback_pattern.search(line):
                offenders.append(f"{template_path}:{line_number}: {line.strip()}")

    assert offenders == []


def test_templates_do_not_keep_hardcoded_passive_ui_js_readpoints() -> None:
    blocked_snippets = {
        "aria/templates/_connection_page_intro.html": ("or '/config'", 'or "/config"'),
        "aria/templates/config_backup.html": (
            "else '/config/backup/export'",
            'else "/config/backup/export"',
            "else '/config/backup/import'",
            'else "/config/backup/import"',
        ),
        "aria/templates/_memory_drilldown_browser.html": (
            "detachLink.href = `/memories?",
            "postBrowserDelete('/memories/browser/delete-point'",
            'postBrowserDelete("/memories/browser/delete-point"',
            "postBrowserDelete('/memories/browser/delete-document'",
            'postBrowserDelete("/memories/browser/delete-document"',
        ),
        "aria/templates/_memory_graph.html": (
            "fetch('/memories/browser/delete-point'",
            'fetch("/memories/browser/delete-point"',
        ),
        "aria/templates/recipes_wizard.html": (
            'link.href = "/config";',
            "link.href = '/config';",
        ),
        "aria/templates/config_files.html": (
            "{% set picker_action = '/config/files' %}",
            "{% set save_action = '/config/files/save' %}",
        ),
        "aria/templates/config_prompts.html": (
            "{% set picker_action = '/config/prompts' %}",
            "{% set save_action = '/config/prompts/save' %}",
        ),
    }
    offenders: list[str] = []
    for filename, snippets in blocked_snippets.items():
        text = Path(filename).read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                offenders.append(f"{filename}: {snippet}")

    assert offenders == []


def test_base_template_renders_navigation_shell_static_assets_through_registry(monkeypatch) -> None:
    static_calls: list[tuple[str, str]] = []
    route_calls: list[tuple[str, str]] = []
    original_static = main_mod.TEMPLATES.env.globals["module_static_asset_url"]
    original_route = main_mod.TEMPLATES.env.globals["module_route_path"]

    def tracking_static_asset_url(module_id: str, asset_name: str) -> str:
        if module_id == "navigation_shell":
            static_calls.append((module_id, asset_name))
        return f"/static/{asset_name}"

    def tracking_route_path(module_id: str, route_path: str) -> str:
        if module_id in {"chat_surface", "navigation_shell"}:
            route_calls.append((module_id, route_path))
        return route_path

    monkeypatch.setitem(main_mod.TEMPLATES.env.globals, "module_static_asset_url", tracking_static_asset_url)
    monkeypatch.setitem(main_mod.TEMPLATES.env.globals, "module_route_path", tracking_route_path)
    response = TestClient(main_mod.app).get("/login")

    assert response.status_code == 200
    assert 'href="/favicon.ico?v=' in response.text
    assert 'sizes="32x32" href="/static/favicon-32x32.png?v=' in response.text
    assert 'sizes="16x16" href="/static/favicon-16x16.png?v=' in response.text
    assert 'rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png?v=' in response.text
    assert 'src="/static/vendor/htmx-1.9.12.min.js?v=' in response.text
    assert 'href="/static/style.css?v=' in response.text
    assert 'src="/static/logo-aria-v01.png?v=' in response.text
    assert 'class="brand brand-home" href="/"' in response.text
    assert ("chat_surface", "/") in route_calls
    assert ("navigation_shell", "/favicon.ico") in route_calls
    assert {
        "favicon-32x32.png",
        "favicon-16x16.png",
        "apple-touch-icon.png",
        "style.css",
        "logo-aria-v01.png",
        "vendor/htmx-1.9.12.min.js",
    }.issubset({asset_name for _, asset_name in static_calls})

    monkeypatch.setitem(main_mod.TEMPLATES.env.globals, "module_static_asset_url", original_static)
    monkeypatch.setitem(main_mod.TEMPLATES.env.globals, "module_route_path", original_route)


def test_favicon_route_serves_real_icon_file() -> None:
    client = TestClient(main_mod.app)

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/x-icon")
    assert response.content.startswith(b"\x00\x00\x01\x00")


def test_favicon_route_uses_navigation_shell_static_asset_readpoint(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "module_static_asset_path", lambda *_args, **_kwargs: None)
    client = TestClient(main_mod.app)

    response = client.get("/favicon.ico")

    assert response.status_code == 404


def test_favicon_static_png_variants_exist() -> None:
    static_dir = Path("aria/static")

    for name in ("favicon-16x16.png", "favicon-32x32.png", "favicon-48x48.png", "apple-touch-icon.png"):
        payload = (static_dir / name).read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(payload) > 100
