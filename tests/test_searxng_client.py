from __future__ import annotations

from aria.core.searxng_client import SearXNGClient, SearXNGClientError, SearXNGSearchResult
from aria.skills.web_search import WebSearchSkill
from aria.skills.web_search import build_web_search_profile_options
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


def test_web_search_skill_does_not_turn_preferred_domains_into_site_queries() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            return type("Resp", (), {"query": query, "results": []})()

    settings = type(
        "Settings",
        (),
        {
            "connections": type(
                "Connections",
                (),
                {
                    "searxng": {
                        "official-sources": {
                            "title": "official-sources",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()
    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "was ist aktuell die neuste docker compose version",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["Docker Compose latest version official releases"],
                    "search_mode": "fast_answer",
                    "search_profile_ref": "official-sources",
                    "preferred_domains": ["github.com/docker/compose", "docs.docker.com"],
                },
            },
        )
    )

    assert result.success is False
    assert client.queries[0] == "Docker Compose latest version official releases"
    assert not any(query.startswith("site:github.com/docker/compose ") for query in client.queries)


def test_web_search_skill_fails_closed_for_noise_only_current_sources() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            return type(
                "Resp",
                (),
                {
                    "query": query,
                    "results": [
                        SearXNGSearchResult(
                            title="Best Amazon Prime Day Kindle deals 2026",
                            url="https://www.msn.com/en-us/technology/general/kindle-deals",
                            snippet="Deal roundup without official model specifications.",
                            engine="bing news",
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
                        "fresh-news": {
                            "title": "fresh-news",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()
    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "was ist der neuste amazon kindle",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["newest Amazon Kindle official specs"],
                    "search_mode": "fast_answer",
                    "search_profile_ref": "fresh-news",
                    "preferred_domains": ["amazon.com", "amazon.de", "aboutamazon.com"],
                },
            },
        )
    )

    assert result.success is False
    assert result.metadata["error_code"] == "web_source_no_reliable_sources"
    assert any("noise_sources_removed" in line for line in result.metadata["detail_lines"])
    assert any("no_reliable_non_noise_sources" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_continues_with_relevant_sources_when_preferred_domains_are_missing() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            return type(
                "Resp",
                (),
                {
                    "query": query,
                    "results": [
                        SearXNGSearchResult(
                            title="Apple Watch Ultra 3 im Vergleich zur Apple Watch Ultra 2",
                            url="https://www.computerbase.de/news/apple-watch-ultra-3-vergleich/",
                            snippet="Apple Watch Ultra 3, neue Funktionen und Vergleich zur Apple Watch Ultra 2.",
                            engine="brave",
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
                        "fresh-news": {
                            "title": "fresh-news",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()
    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "welches ist die neuste apple watch ultra und was kann sie mehr als die alte version",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["Apple Watch Ultra 3 2026 neue Funktionen"],
                    "search_mode": "fast_answer",
                    "search_profile_ref": "fresh-news",
                    "preferred_domains": ["apple.com", "support.apple.com"],
                },
            },
        )
    )

    assert result.success is True
    assert client.queries[0] == "Apple Watch Ultra 3 2026 neue Funktionen"
    assert not any(query.startswith("site:apple.com ") for query in client.queries)
    assert result.metadata["result_count"] == 1
    assert result.metadata["source_authority_outcome"] == "weak_only"
    assert "Source authority: weak_only" in result.content
    assert result.metadata["sources"][0]["source_authority_label"] == "weak_secondary"
    assert any("preferred_sources_missing_continuing" in line for line in result.metadata["detail_lines"])
    assert any("web_source_authority" in line and "outcome=weak_only" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_marks_preferred_sources_as_authoritative() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            return type(
                "Resp",
                (),
                {
                    "query": query,
                    "results": [
                        SearXNGSearchResult(
                            title="Apple Watch Ultra 3 - Technical Specifications",
                            url="https://support.apple.com/en-us/121000",
                            snippet="Official Apple Watch Ultra 3 technical specifications.",
                            engine="brave",
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
                        "fresh-news": {
                            "title": "fresh-news",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()
    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "welches ist die neuste apple watch ultra und was kann sie mehr als die alte version",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["Apple Watch Ultra 3 2026 official specs"],
                    "search_mode": "fast_answer",
                    "search_profile_ref": "fresh-news",
                    "preferred_domains": ["apple.com", "support.apple.com"],
                },
            },
        )
    )

    assert result.success is True
    assert result.metadata["source_authority_outcome"] == "preferred_sources"
    assert "Source authority: weak_only" not in result.content
    assert result.metadata["sources"][0]["source_authority_label"] == "preferred_source"
    assert any("web_source_authority" in line and "outcome=preferred_sources" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_rejects_irrelevant_preferred_domain_results() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            return type(
                "Resp",
                (),
                {
                    "query": query,
                    "results": [
                        SearXNGSearchResult(
                            title="Bedienungshilfeeinstellungen für die Kamerasteuerung auf dem iPhone anpassen",
                            url="https://support.apple.com/de-ch/guide/iphone/iph22c8345f8/ios",
                            snippet="Apple Support Seite für iPhone Kamerasteuerung.",
                            engine="brave",
                        ),
                        SearXNGSearchResult(
                            title="Magic Keyboard und Smart Keyboard für das iPad",
                            url="https://support.apple.com/de-de/guide/ipad/ipad4b92bd12/ipados",
                            snippet="Apple Support Seite für iPad Tastaturen.",
                            engine="brave",
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
                        "fresh-news": {
                            "title": "fresh-news",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()
    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "welches ist die neuste apple watch ultra und was kann sie mehr als die alte version",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["Apple Watch Ultra latest official specs new features comparison"],
                    "search_mode": "fast_answer",
                    "search_profile_ref": "fresh-news",
                    "preferred_domains": ["apple.com", "support.apple.com"],
                    "required_sources": ["official product specifications"],
                },
            },
        )
    )

    assert result.success is False
    assert result.metadata["error_code"] == "web_source_no_reliable_sources"
    assert any("web_source_filter" in line or "web_source_quality_gate" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_limits_fast_answer_sources() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            return type(
                "Resp",
                (),
                {
                    "query": query,
                    "results": [
                        SearXNGSearchResult(
                            title=f"Docker Compose release notes {index}",
                            url=f"https://docs.docker.com/compose/releases/{index}",
                            snippet="Docker Compose release notes and version information.",
                            engine="duckduckgo",
                        )
                        for index in range(1, 8)
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
                        "tech-search": {
                            "title": "tech-search",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 8,
                        }
                    }
                },
            )()
        },
    )()
    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "was ist aktuell die neuste docker compose version",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["Docker Compose latest release notes official"],
                    "search_mode": "fast_answer",
                    "search_profile_ref": "tech-search",
                    "preferred_domains": ["docs.docker.com"],
                    "required_sources": ["official release notes"],
                },
            },
        )
    )

    assert result.success is True
    assert result.metadata["result_count"] == 4
    assert any("web_source_result_budget" in line and "kept=4" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_does_not_add_product_specific_supplement_queries() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            results = [
                SearXNGSearchResult(
                    title="iPhone 17 Pro samt Watch Ultra 3 fuer 1 Euro",
                    url="https://www.n-tv.de/shopping-und-service/iphone-watch-bundle.html",
                    snippet="Bundle Angebot und Shopping-Deal.",
                    engine="bing news",
                    published_at="2026-05-22T09:00:00+00:00",
                    published_label="2026-05-22",
                ),
                SearXNGSearchResult(
                    title="Apple Watch Ultra 4 Geruechte",
                    url="https://www.appgefahren.de/apple-watch-ultra-4-geruechte.html",
                    snippet="News und Geruechte.",
                    engine="duckduckgo news",
                    published_at="2026-05-19T09:00:00+00:00",
                    published_label="2026-05-19",
                ),
            ]
            return type("Resp", (), {"query": kwargs.get("query", ""), "results": results})()

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

    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "suche im internet nach der neusten apple watch ultra und dem neusten iphone",
            {"language": "de"},
        )
    )

    assert result.success is True
    assert client.queries == ["suche im internet nach der neusten apple watch ultra und dem neusten iphone"]
    urls = [source["url"] for source in result.metadata["sources"]]
    assert set(urls) == {
        "https://www.n-tv.de/shopping-und-service/iphone-watch-bundle.html",
        "https://www.appgefahren.de/apple-watch-ultra-4-geruechte.html",
    }
    assert "official_supplement_count" not in result.metadata
    assert "web_source_filter" not in result.metadata
    assert "target_coverage" not in result.metadata


def test_web_search_skill_executes_llm_planned_source_queries() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            if "official" in query.lower():
                results = [
                    SearXNGSearchResult(
                        title="Apple Watch Ultra 2",
                        url="https://www.apple.com/apple-watch-ultra-2/",
                        snippet="Official Apple Watch Ultra 2 product information.",
                        engine="duckduckgo",
                    )
                ]
            else:
                results = [
                    SearXNGSearchResult(
                        title="ultralytics/xview",
                        url="https://hub.docker.com/r/ultralytics/xview",
                        snippet="Docker image unrelated to Apple Watch.",
                        engine="duckduckgo",
                    )
                ]
            return type("Resp", (), {"query": query, "results": results})()

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

    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "welches ist die neuste apple watch ultra",
            {
                "language": "de",
                "web_source_plan": {
                    "goal": "Find current Apple Watch Ultra model evidence.",
                    "queries": ["Apple Watch Ultra latest official Apple product comparison"],
                    "required_sources": ["official vendor or authoritative comparison"],
                    "avoid_sources": ["unrelated software packages"],
                },
            },
        )
    )

    assert result.success is True
    assert client.queries == [
        "Apple Watch Ultra latest official Apple product comparison",
        "welches ist die neuste apple watch ultra",
    ]
    urls = [source["url"] for source in result.metadata["sources"]]
    assert "https://www.apple.com/apple-watch-ultra-2/" in urls
    assert "https://hub.docker.com/r/ultralytics/xview" not in urls
    assert result.metadata["planned_query_count"] == 1
    assert result.metadata["web_source_plan"]["queries"] == ["Apple Watch Ultra latest official Apple product comparison"]
    assert result.metadata["search_categories"] == ["general"]
    assert any("web_source_filter" in line for line in result.metadata["detail_lines"])
    assert any("web_source_acquisition_plan" in line for line in result.metadata["detail_lines"])


def test_planned_web_search_zero_results_fail_closed() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            return type("Resp", (), {"query": query, "results": []})()

    settings = type(
        "Settings",
        (),
        {
            "connections": type(
                "Connections",
                (),
                {
                    "searxng": {
                        "fresh-news": {
                            "title": "Fresh News",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "max_results": 5,
                        }
                    }
                },
            )()
        },
    )()
    skill = WebSearchSkill(settings=settings, client=FakeClient())

    result = __import__("asyncio").run(
        skill.execute(
            "gibts vom rabbit r1 ein update das in den letzten wochen rausgekommen ist",
            {
                "language": "de",
                "web_source_plan": {
                    "search_mode": "fast_answer",
                    "search_profile_ref": "fresh-news",
                    "queries": ["Rabbit R1 release notes latest update"],
                    "preferred_domains": ["rabbit.tech"],
                },
            },
        )
    )

    assert result.success is False
    assert result.metadata["error_code"] == "web_source_no_reliable_sources"
    assert result.metadata["result_count"] == 0
    assert any("search_mode=fast_answer" in line for line in result.metadata["detail_lines"])
    assert any("0 Treffer" in line or "0 results" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_adds_required_domain_queries_from_source_plan() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            if query.startswith("site:apple.com "):
                results = [
                    SearXNGSearchResult(
                        title="Apple Watch Ultra 3",
                        url="https://www.apple.com/apple-watch-ultra-3/",
                        snippet="Official Apple Watch Ultra 3 product information.",
                        engine="duckduckgo",
                    )
                ]
            else:
                results = [
                    SearXNGSearchResult(
                        title="Apple Watch Ultra 4 rumor roundup",
                        url="https://example.org/apple-watch-ultra-4-rumors",
                        snippet="Third-party rumors about a future model.",
                        engine="bing news",
                    )
                ]
            return type("Resp", (), {"query": query, "results": results})()

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

    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "welches ist die neuste apple watch ultra",
            {
                "language": "de",
                "web_source_plan": {
                    "goal": "Find current Apple Watch Ultra model evidence.",
                    "queries": ["Apple Watch Ultra latest official Apple product comparison"],
                    "must_have_domains": ["apple.com"],
                    "required_sources": ["apple.com official product pages"],
                    "avoid_sources": ["speculation or rumor sites without official confirmation"],
                },
            },
        )
    )

    assert result.success is True
    assert client.queries[:2] == [
        "site:apple.com Apple Watch Ultra latest official Apple product comparison",
        "Apple Watch Ultra latest official Apple product comparison",
    ]
    urls = [source["url"] for source in result.metadata["sources"]]
    assert "https://www.apple.com/apple-watch-ultra-3/" in urls
    assert result.metadata["executed_queries"][0].startswith("site:apple.com ")
    assert any("web_source_queries" in line and "site:apple.com" in line for line in result.metadata["detail_lines"])


def test_web_search_profile_options_expose_safe_profile_metadata() -> None:
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
                            "title": "Internet Search",
                            "description": "General product and news search.",
                            "base_url": "http://searxng:8080",
                            "categories": ["general", "news"],
                            "engines": ["duckduckgo", "startpage"],
                            "aliases": ["internet", "web"],
                            "tags": ["general"],
                            "max_results": 10,
                        }
                    }
                },
            )()
        },
    )()

    options = build_web_search_profile_options(settings)

    assert options == [
        {
            "ref": "www-search",
            "title": "Internet Search",
            "description": "General product and news search.",
            "tags": ["general"],
            "aliases": ["internet", "web"],
            "categories": ["general", "news"],
            "engines": ["duckduckgo", "startpage"],
            "language": "",
            "safe_search": "",
            "time_range": "",
            "max_results": 10,
        }
    ]


def test_web_search_skill_filters_source_plan_garbage_before_curation() -> None:
    class FakeClient:
        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            return type(
                "Resp",
                (),
                {
                    "query": query,
                    "results": [
                        SearXNGSearchResult(
                            title="What went wrong? Troubleshooting JavaScript",
                            url="https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting/What_went_wrong",
                            snippet="Troubleshooting JavaScript errors in a browser.",
                            engine="mdn",
                        ),
                        SearXNGSearchResult(
                            title="Debugging CSS",
                            url="https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Styling_basics/Debugging_CSS",
                            snippet="Debugging web development layouts.",
                            engine="mdn",
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
                        "tech-search": {
                            "title": "Technical Search",
                            "base_url": "http://searxng:8080",
                            "timeout_seconds": 10,
                            "categories": ["general", "it"],
                            "engines": ["duckduckgo", "startpage", "brave"],
                            "max_results": 10,
                        }
                    }
                },
            )()
        },
    )()

    skill = WebSearchSkill(settings=settings, client=FakeClient())
    result = __import__("asyncio").run(
        skill.execute(
            "ich habe ein docker compose problem, such technische quellen dazu",
            {
                "language": "de",
                "web_source_plan": {
                    "goal": "Find technical sources for a Docker Compose problem.",
                    "queries": ["Docker Compose Fehler Lösung Troubleshooting"],
                    "preferred_domains": ["docs.docker.com", "stackoverflow.com", "github.com"],
                    "search_profile_ref": "tech-search",
                },
            },
        )
    )

    assert result.success is False
    assert result.metadata["error_code"] == "web_source_no_reliable_sources"
    assert result.metadata["result_count"] == 0
    assert any("reason=anchor_terms" in line for line in result.metadata["detail_lines"])
    assert not any(query.startswith("site:docs.docker.com ") for query in result.metadata["executed_queries"])


def test_web_search_skill_uses_source_plan_search_profile_ref() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def search(self, **kwargs):
            self.calls.append(dict(kwargs))
            return type(
                "Resp",
                (),
                {
                    "query": kwargs.get("query", ""),
                    "results": [
                        SearXNGSearchResult(
                            title="Linux troubleshooting docs",
                            url="https://example.org/linux-troubleshooting",
                            snippet="A technical source for Linux troubleshooting.",
                            engine="brave",
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
                            "title": "Internet Search",
                            "base_url": "http://searxng:8080",
                            "categories": ["general", "news"],
                            "engines": ["duckduckgo"],
                            "max_results": 10,
                        },
                        "tech-search": {
                            "title": "Technical Search",
                            "base_url": "http://searxng:8080",
                            "categories": ["general", "it"],
                            "engines": ["brave"],
                            "max_results": 7,
                        },
                    }
                },
            )()
        },
    )()

    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "linux docker compose fehler analysieren",
            {
                "language": "de",
                "web_source_plan": {
                    "goal": "Find technical troubleshooting sources.",
                    "queries": ["linux docker compose error troubleshooting"],
                    "search_profile_ref": "tech-search",
                },
            },
        )
    )

    assert result.success is True
    assert client.calls[0]["categories"] == ["general", "it"]
    assert client.calls[0]["engines"] == ["brave"]
    assert client.calls[0]["max_results"] == 8
    assert result.metadata["connection_ref"] == "tech-search"
    assert result.metadata["search_profile_ref"] == "tech-search"
    assert result.metadata["search_profile_source"] == "source_plan"
    assert any("web_search_profile selected=tech-search source=source_plan" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_fails_closed_for_unknown_source_plan_profile() -> None:
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
                            "title": "Internet Search",
                            "base_url": "http://searxng:8080",
                            "categories": ["general", "news"],
                        }
                    }
                },
            )()
        },
    )()

    skill = WebSearchSkill(settings=settings)

    result = __import__("asyncio").run(
        skill.execute(
            "aktuelle produktnews",
            {
                "language": "de",
                "web_source_plan": {
                    "goal": "Find product news.",
                    "queries": ["current product news"],
                    "search_profile_ref": "missing-search",
                },
            },
        )
    )

    assert result.success is False
    assert result.error == "Ausgewaehltes SearXNG-Profil ist nicht konfiguriert: missing-search"
    assert result.metadata["error_code"] == "web_search_profile_not_found"


def test_web_search_skill_does_not_double_prefix_existing_site_query_from_source_plan() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            return type("Resp", (), {"query": query, "results": []})()

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

    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "gibts vom rabbit r1 ein update",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["site:rabbit.tech Rabbit R1 update July 2026"],
                    "required_sources": ["rabbit.tech official website"],
                    "avoid_sources": ["User forums without official confirmation"],
                },
            },
        )
    )

    assert result.success is False
    assert result.metadata["error_code"] == "web_source_no_reliable_sources"
    assert client.queries[0] == "site:rabbit.tech Rabbit R1 update July 2026"
    assert "site:rabbit.tech site:rabbit.tech" not in " ".join(client.queries)


def test_web_search_skill_discards_offdomain_results_from_site_query() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            if query.startswith("site:apple.com "):
                results = [
                    SearXNGSearchResult(
                        title="Apple Watch Ultra Docker image",
                        url="https://hub.docker.com/r/example/apple-watch-ultra",
                        snippet="Unrelated container image.",
                        engine="docker hub",
                    ),
                    SearXNGSearchResult(
                        title="Apple Watch Ultra 3",
                        url="https://www.apple.com/apple-watch-ultra-3/",
                        snippet="Official Apple Watch Ultra 3 product information.",
                        engine="duckduckgo",
                    ),
                ]
            else:
                results = []
            return type("Resp", (), {"query": query, "results": results})()

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

    skill = WebSearchSkill(settings=settings, client=FakeClient())
    result = __import__("asyncio").run(
        skill.execute(
            "welches ist die neuste apple watch ultra",
            {
                "language": "de",
                "web_source_plan": {
                    "queries": ["Apple Watch Ultra latest official Apple product comparison"],
                    "must_have_domains": ["apple.com"],
                    "required_sources": ["apple.com official product pages"],
                    "avoid_sources": ["speculation or rumor sites without official confirmation"],
                },
            },
        )
    )

    assert result.success is True
    urls = [source["url"] for source in result.metadata["sources"]]
    assert "https://www.apple.com/apple-watch-ultra-3/" in urls
    assert all("hub.docker.com" not in url for url in urls)
    assert any("web_source_provider_contract" in line and "removed=1" in line for line in result.metadata["detail_lines"])


def test_web_search_skill_returns_primary_error_without_product_supplement_fallback() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs):
            query = str(kwargs.get("query", ""))
            self.queries.append(query)
            raise SearXNGClientError("SearXNG request failed: timed out")

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

    client = FakeClient()
    skill = WebSearchSkill(settings=settings, client=client)

    result = __import__("asyncio").run(
        skill.execute(
            "suche im internet nach der neusten apple watch ultra und dem neusten iphone",
            {"language": "de"},
        )
    )

    assert result.success is False
    assert client.queries == ["suche im internet nach der neusten apple watch ultra und dem neusten iphone"]
    assert "timed out" in str(result.error)


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
        assert timeout_seconds == 4
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
