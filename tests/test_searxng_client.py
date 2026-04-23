from __future__ import annotations

from aria.core.searxng_client import SearXNGClient, SearXNGSearchResult
from aria.skills.web_search import WebSearchSkill
from aria.skills.base import SkillResult


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


def test_web_search_skill_localizes_english_output() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            _ = kwargs
            return type(
                "Resp",
                (),
                {
                    "query": "rabbit r1 latest news",
                    "results": [
                        SearXNGSearchResult(
                            title="Rabbit R1 turns into Android agent",
                            url="https://example.org/rabbit",
                            snippet="Rabbit shifts from device to Android app.",
                            engine="startpage news",
                            published_at="2025-02-27T09:00:00+00:00",
                            published_label="2025-02-27",
                        )
                    ],
                },
            )()

    settings = type(
        "Settings",
        (),
        {
            "connections": type(
                "Connections",
                (),
                {
                    "searxng": {
                        "www-search": {
                            "title": "www-search",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                        }
                    }
                },
            )()
        },
    )()

    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "rabbit r1 latest news",
            {
                "language": "en",
            },
        )
    )

    assert isinstance(result, SkillResult)
    assert result.success is True
    assert "[Web Search via www-search]" in result.content
    assert "Search: rabbit r1 latest news" in result.content
    assert "Date: 2025-02-27" in result.content
    assert result.metadata["detail_lines"] == [
        "Source: Rabbit R1 turns into Android agent · https://example.org/rabbit · startpage news · 2025-02-27"
    ]


def test_web_search_skill_can_prepend_notes_context() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            _ = kwargs
            return type(
                "Resp",
                (),
                {
                    "query": "google calendar oauth",
                    "results": [
                        SearXNGSearchResult(
                            title="Google OAuth Docs",
                            url="https://example.org/google-oauth",
                            snippet="Audience and test users guide.",
                            engine="duckduckgo",
                        )
                    ],
                },
            )()

    settings = type(
        "Settings",
        (),
        {
            "connections": type(
                "Connections",
                (),
                {
                    "searxng": {
                        "web-search": {
                            "title": "web-search",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                        }
                    }
                },
            )()
        },
    )()

    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "google calendar oauth",
            {
                "language": "de",
                "note_context_hits": [
                    {
                        "note_id": "n1",
                        "title": "Google OAuth",
                        "folder": "Recherche",
                        "relative_path": "Recherche/google-oauth.md",
                        "updated_at": "2026-04-23T12:00:00+00:00",
                        "score": 0.91,
                        "snippet": "Audience, Test users und OAuth Playground",
                    }
                ],
            },
        )
    )

    assert result.success is True
    assert "Notiz-Kontext für die Suche" in result.content
    assert "Google OAuth (Recherche): Audience, Test users und OAuth Playground" in result.content
    assert result.metadata["detail_lines"][0] == "Notiz-Kontext: Google OAuth · Recherche"
