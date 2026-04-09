from __future__ import annotations

from aria.core.searxng_client import SearXNGClient, SearXNGSearchResult
from aria.skills.web_search import WebSearchSkill


def test_searxng_client_extracts_published_date_from_result_item() -> None:
    published_at, published_label = SearXNGClient._extract_published_meta(  # type: ignore[attr-defined]
        {"publishedDate": "2026-04-07T09:30:00Z"}
    )

    assert published_at.startswith("2026-04-07T09:30:00")
    assert published_label == "2026-04-07"


def test_web_search_skill_prioritizes_dated_results_for_recency_queries() -> None:
    skill = WebSearchSkill(settings=object())
    results = [
        SearXNGSearchResult(
            title="Older",
            url="https://example.org/older",
            snippet="old",
            engine="duckduckgo news",
            published_at="2026-03-20T10:00:00+00:00",
            published_label="2026-03-20",
        ),
        SearXNGSearchResult(
            title="Newest",
            url="https://example.org/newest",
            snippet="new",
            engine="bing news",
            published_at="2026-04-07T12:00:00+00:00",
            published_label="2026-04-07",
        ),
        SearXNGSearchResult(
            title="Undated",
            url="https://example.org/undated",
            snippet="unknown",
            engine="duckduckgo",
        ),
    ]

    ordered = skill._prepare_results("letzter release rabbit r1", results)  # type: ignore[attr-defined]

    assert [item.title for item in ordered] == ["Newest", "Older", "Undated"]


def test_web_search_skill_filters_results_without_meaningful_query_overlap() -> None:
    skill = WebSearchSkill(settings=object())
    results = [
        SearXNGSearchResult(
            title="Rabbit R1 wird zum Android-Agent",
            url="https://www.heise.de/news/rabbit-r1-agent-123.html",
            snippet="Das Rabbit R1 erscheint jetzt als Android-Agent.",
            engine="startpage news",
            published_at="2025-02-27T09:00:00+00:00",
            published_label="2025-02-27",
        ),
        SearXNGSearchResult(
            title="Renten News: Nachrichten zur gesetzlichen Rentenversicherung",
            url="https://www.handelsblatt.com/themen/rente",
            snippet="Aktuelle News und Entwicklungen zur Rente.",
            engine="aol",
            published_at="2025-02-28T09:00:00+00:00",
            published_label="2025-02-28",
        ),
    ]

    ordered = skill._prepare_results("suche im internet, was für neuigkeiten gibt es vom rabbit r1", results)  # type: ignore[attr-defined]

    assert [item.title for item in ordered] == ["Rabbit R1 wird zum Android-Agent"]
