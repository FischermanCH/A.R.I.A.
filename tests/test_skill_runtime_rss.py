import json
from types import SimpleNamespace

from aria.core.skill_runtime import CustomSkillRuntime


def test_clean_feed_url_removes_tracking_parameters() -> None:
    url = (
        "https://www.heise.de/news/test.html"
        "?wt_mc=rss.red.ho.ho.atom.beitrag.beitrag&utm_source=rss&id=42"
    )
    cleaned = CustomSkillRuntime._clean_feed_url(url)
    assert cleaned == "https://www.heise.de/news/test.html?id=42"


def test_format_feed_timestamp_parses_iso_timestamp() -> None:
    formatted = CustomSkillRuntime._format_feed_timestamp("2026-03-28T20:00:00+01:00")
    assert formatted == "2026-03-28 20:00"


def test_format_feed_timestamp_parses_rfc2822_timestamp() -> None:
    formatted = CustomSkillRuntime._format_feed_timestamp("Sat, 28 Mar 2026 20:00:00 +0100")
    assert formatted == "2026-03-28 20:00"


def _build_runtime() -> CustomSkillRuntime:
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
    return CustomSkillRuntime(
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
    start_at, end_at, max_results = CustomSkillRuntime._google_calendar_time_bounds("tomorrow")

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

    monkeypatch.setattr("aria.core.skill_runtime.urlopen", fake_urlopen)

    result = runtime.execute_google_calendar_read("primary-calendar", "today", language="de")

    assert "Primary Calendar" in result
    assert "Team Standup" in result
    assert "Ort: Meet" in result
    assert any("oauth2.googleapis.com/token" in call for call in calls)
    assert any("/calendar/v3/calendars/primary/events" in call for call in calls)
