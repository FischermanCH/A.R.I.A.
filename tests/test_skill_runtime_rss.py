import json
from types import SimpleNamespace
from urllib.error import HTTPError

from aria.core.recipe_runtime import RecipeRuntime


def test_clean_feed_url_removes_tracking_parameters() -> None:
    url = (
        "https://www.heise.de/news/test.html"
        "?wt_mc=rss.red.ho.ho.atom.beitrag.beitrag&utm_source=rss&id=42"
    )
    cleaned = RecipeRuntime._clean_feed_url(url)
    assert cleaned == "https://www.heise.de/news/test.html?id=42"


def test_format_feed_timestamp_parses_iso_timestamp() -> None:
    formatted = RecipeRuntime._format_feed_timestamp("2026-03-28T20:00:00+01:00")
    assert formatted == "2026-03-28 20:00"


def test_format_feed_timestamp_parses_rfc2822_timestamp() -> None:
    formatted = RecipeRuntime._format_feed_timestamp("Sat, 28 Mar 2026 20:00:00 +0100")
    assert formatted == "2026-03-28 20:00"


def test_parse_feed_timestamp_normalizes_naive_and_aware_datetimes() -> None:
    aware = RecipeRuntime._parse_feed_timestamp("2026-04-26T20:08:00+02:00")
    naive = RecipeRuntime._parse_feed_timestamp("2026-04-26T20:00:00")

    assert aware is not None and aware.tzinfo is not None
    assert naive is not None and naive.tzinfo is not None


def test_execute_rss_group_read_sorts_mixed_timestamp_types(monkeypatch) -> None:
    runtime = _build_runtime()

    def fake_load_rss_entries(connection_ref: str, *, language: str = "de"):
        _ = language
        if connection_ref == "feed-a":
            return "Feed A", [
                {
                    "title": "Entry A",
                    "link": "https://example.org/a",
                    "published": "2026-04-26T20:08:00+02:00",
                    "summary": "Aware timestamp",
                }
            ]
        return "Feed B", [
            {
                "title": "Entry B",
                "link": "https://example.org/b",
                "published": "2026-04-26T19:59:00",
                "summary": "Naive timestamp",
            }
        ]

    monkeypatch.setattr(runtime, "_load_rss_entries", fake_load_rss_entries)

    result = runtime.execute_rss_group_read("Security", ["feed-a", "feed-b"], language="de")

    assert "Neueste Einträge aus Kategorie `Security`:" in result
    assert "Entry A" in result
    assert "Entry B" in result


def _build_runtime() -> RecipeRuntime:
    settings = SimpleNamespace(
        connections=SimpleNamespace(
            google_calendar={
                "primary-calendar": SimpleNamespace(
                    calendar_id="primary",
                    client_id="client-id",
                    client_secret="client-secret",
                    refresh_token="refresh-token",
                    timeout_seconds=10,
                )
            }
        )
    )
    return RecipeRuntime(
        settings=settings,
        llm_client=None,
        memory_skill_getter=lambda: None,
        web_search_skill_getter=lambda: None,
        execute_custom_ssh_command=lambda *args, **kwargs: None,
        extract_memory_store_text=lambda *args, **kwargs: "",
        extract_memory_recall_query=lambda *args, **kwargs: "",
        extract_web_search_query=lambda *args, **kwargs: "",
        facts_collection_for_user=lambda _user: "",
        preferences_collection_for_user=lambda _user: "",
        normalize_spaces=lambda text: text,
        truncate_text=lambda text, _limit: text,
    )


def test_google_calendar_range_bounds_for_tomorrow() -> None:
    start_at, end_at, max_results = RecipeRuntime._google_calendar_time_bounds("tomorrow")

    assert start_at.date().isoformat() <= end_at.date().isoformat()
    assert (end_at - start_at).days == 1
    assert max_results == 12


def test_execute_google_calendar_read_formats_events(monkeypatch) -> None:
    runtime = _build_runtime()

    class _Response:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = json.dumps(payload).encode("utf-8")

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = (exc_type, exc, tb)

    calls: list[str] = []

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        _ = timeout
        url = getattr(request, "full_url", str(request))
        calls.append(url)
        if "oauth2.googleapis.com/token" in url:
            return _Response({"access_token": "token-123"})
        return _Response(
            {
                "summary": "Primary Calendar",
                "items": [
                    {
                        "summary": "Team Standup",
                        "start": {"dateTime": "2026-04-22T09:00:00+02:00"},
                        "location": "Meet",
                    }
                ],
            }
        )

    monkeypatch.setattr("aria.core.recipe_runtime.urlopen", fake_urlopen)

    result = runtime.execute_google_calendar_read("primary-calendar", "today", language="de")

    assert "Primary Calendar" in result
    assert "Team Standup" in result
    assert "Ort: Meet" in result
    assert any("oauth2.googleapis.com/token" in call for call in calls)
    assert any("/calendar/v3/calendars/primary/events" in call for call in calls)


def test_execute_google_calendar_read_passes_search_query_to_google(monkeypatch) -> None:
    runtime = _build_runtime()

    class _Response:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = json.dumps(payload).encode("utf-8")

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = (exc_type, exc, tb)

    calls: list[str] = []

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        _ = timeout
        url = getattr(request, "full_url", str(request))
        calls.append(url)
        if "oauth2.googleapis.com/token" in url:
            return _Response({"access_token": "token-123"})
        return _Response({"summary": "Primary Calendar", "items": []})

    monkeypatch.setattr("aria.core.recipe_runtime.urlopen", fake_urlopen)

    result = runtime.execute_google_calendar_read("primary-calendar", "next_week", "Zahnarzt", language="de")

    assert "Keine Termine" in result
    assert "Zahnarzt" in result
    assert any("q=Zahnarzt" in call for call in calls if "/calendar/v3/calendars/primary/events" in call)


def test_execute_google_calendar_read_surfaces_revoked_refresh_token_helpfully(monkeypatch) -> None:
    runtime = _build_runtime()

    class _TokenError(HTTPError):
        def __init__(self) -> None:
            super().__init__("https://oauth2.googleapis.com/token", 400, "Bad Request", hdrs=None, fp=None)

        def read(self) -> bytes:
            return b'{"error":"invalid_grant","error_description":"Token has been expired or revoked."}'

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        _ = timeout
        url = getattr(request, "full_url", str(request))
        if "oauth2.googleapis.com/token" in url:
            raise _TokenError()
        raise AssertionError("Calendar fetch should not run after token failure.")

    monkeypatch.setattr("aria.core.recipe_runtime.urlopen", fake_urlopen)

    try:
        runtime.execute_google_calendar_read("primary-calendar", "today", language="de")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError for revoked refresh token.")

    assert "Refresh-Token" in message
    assert "mit Google verbinden" in message
