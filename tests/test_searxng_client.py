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


def test_web_search_skill_prefers_release_sources_for_current_version_queries() -> None:
    skill = WebSearchSkill(settings=object())
    results = [
        SearXNGSearchResult(
            title="Claude Code bekommt Sprachmodus",
            url="https://t3n.de/news/claude-code-bekommt-sprachmodus-1732349/",
            snippet="News zu Claude Code ohne konkrete Release-Version.",
            engine="bing news",
            published_at="2026-03-04T10:00:00+00:00",
            published_label="2026-03-04",
        ),
        SearXNGSearchResult(
            title="Releases · anthropics/claude-code",
            url="https://github.com/anthropics/claude-code/releases",
            snippet="Latest releases and tags for Claude Code.",
            engine="duckduckgo",
        ),
        SearXNGSearchResult(
            title="@anthropic-ai/claude-code",
            url="https://www.npmjs.com/package/@anthropic-ai/claude-code",
            snippet="Official npm package with current version information.",
            engine="brave",
        ),
        SearXNGSearchResult(
            title="version",
            url="https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/version",
            snippet="Manifest version field documentation.",
            engine="mdn",
        ),
    ]

    ordered = skill._prepare_results("Claude Code current version latest release", results)  # type: ignore[attr-defined]

    assert [item.title for item in ordered[:2]] == [
        "Releases · anthropics/claude-code",
        "@anthropic-ai/claude-code",
    ]
    assert all("news" not in item.engine for item in ordered[:2])
    assert all("mozilla.org" not in item.url for item in ordered[:2])


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


def test_web_search_skill_fetches_page_excerpt_for_official_result() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            _ = kwargs
            return type(
                "Resp",
                (),
                {
                    "query": "area41 conference 2026 speakers topics agenda",
                    "results": [
                        SearXNGSearchResult(
                            title="AREA41: Switzerland's Premier Hacker and Security Conference",
                            url="https://area41.io/index.html#speakers",
                            snippet="Below is a selection of speakers selected for 2026.",
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

    calls: list[str] = []

    def fake_page_fetcher(url: str, timeout_seconds: int) -> str:
        calls.append(url)
        assert timeout_seconds == 8
        return """
        <html>
          <body>
            <section id="speakers">
              <h2>Speakers</h2>
              <article>
                <h3>Example Speaker</h3>
                <p>Breaking Every Guardrail Everywhere All At Once</p>
              </article>
              <article>
                <h3>Another Speaker</h3>
                <p>Hacking Every Entra ID Tenant With Actor Tokens</p>
              </article>
            </section>
          </body>
        </html>
        """

    skill = WebSearchSkill(settings=settings, client=FakeClient(), page_fetcher=fake_page_fetcher)

    result = __import__("asyncio").run(
        skill.execute(
            "was sind die themen der speaker an der area41 konferenz 2026",
            {"language": "de"},
        )
    )

    assert result.success is True
    assert calls == ["https://area41.io/index.html#speakers"]
    assert "Page excerpt:" in result.content
    assert "Breaking Every Guardrail Everywhere All At Once" in result.content
    assert "Hacking Every Entra ID Tenant With Actor Tokens" in result.content
    assert result.metadata["sources"][0]["page_excerpt"] is True


def test_web_search_skill_fetches_strong_domain_match_beyond_top_two_results() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            _ = kwargs
            return type(
                "Resp",
                (),
                {
                    "query": "area41 conference 2026 speakers topics agenda",
                    "results": [
                        SearXNGSearchResult(
                            title="Events | SIGS Community Network",
                            url="https://sig-switzerland.ch/events",
                            snippet="AREA41 conference listing",
                            engine="brave",
                        ),
                        SearXNGSearchResult(
                            title="AREA41 CONFERENCE 2026 - SWISS CONGRESS",
                            url="https://swiss-congress.ch/conferences/area41-conference-2026/",
                            snippet="Date and venue",
                            engine="duckduckgo",
                        ),
                        SearXNGSearchResult(
                            title="TRANSFORM 2026 | BFH Wirtschaft",
                            url="https://www.bfh.ch/de/aktuell/fachveranstaltungen/transform-2026/",
                            snippet="Unrelated conference",
                            engine="aol",
                        ),
                        SearXNGSearchResult(
                            title="AREA41: Switzerland's Premier Hacker and Security Conference",
                            url="https://area41.io/#speakers",
                            snippet="Official conference website.",
                            engine="duckduckgo",
                        ),
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
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()

    calls: list[str] = []

    def fake_page_fetcher(url: str, timeout_seconds: int) -> str:
        _ = timeout_seconds
        calls.append(url)
        if url == "https://area41.io/#speakers":
            return """
            <main>
              <section id="speakers">
                <h2>Speakers</h2>
                <article><h3>Area Speaker</h3><p>Browser Isolation Breakouts in the Wild</p></article>
              </section>
            </main>
            """
        return "<html><body>No speaker details here.</body></html>"

    skill = WebSearchSkill(settings=settings, client=FakeClient(), page_fetcher=fake_page_fetcher)

    result = __import__("asyncio").run(
        skill.execute(
            "was sind die themen der speaker an der area41 konferenz 2026",
            {"language": "de"},
        )
    )

    assert result.success is True
    assert "https://area41.io/#speakers" in calls
    assert "Browser Isolation Breakouts in the Wild" in result.content


def test_web_search_skill_fetches_explicit_url_when_search_has_no_results() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            _ = kwargs
            return type("Resp", (), {"query": "https://area41.io/index.html#speakers", "results": []})()

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
                            "timeout_seconds": 5,
                        }
                    }
                },
            )()
        },
    )()

    def fake_page_fetcher(url: str, timeout_seconds: int) -> str:
        _ = timeout_seconds
        assert url == "https://area41.io/index.html#speakers"
        return "<main><h2 id='speakers'>Speakers</h2><p>Mask off: analyzing a secure SD card</p></main>"

    skill = WebSearchSkill(settings=settings, client=FakeClient(), page_fetcher=fake_page_fetcher)

    result = __import__("asyncio").run(
        skill.execute(
            "https://area41.io/index.html#speakers",
            {"language": "de"},
        )
    )

    assert result.success is True
    assert "Mask off: analyzing a secure SD card" in result.content
    assert result.metadata["result_count"] == 1
    assert result.metadata["sources"][0]["engine"] == "page_fetch"
