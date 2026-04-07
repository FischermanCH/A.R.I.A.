from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

from aria.core import connection_runtime


class _FakeHttpResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        return self._payload


def test_rss_page_probe_uses_fresh_cached_status(monkeypatch) -> None:
    checked_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    monkeypatch.setattr(
        connection_runtime,
        "get_connection_health",
        lambda _ref: {
            "last_checked_at": checked_at,
            "last_status": "ok",
            "last_target": "https://example.org/feed.xml",
            "last_message": "RSS-Test erfolgreich aus Cache",
            "last_success_at": checked_at,
        },
    )

    def _fail_live_probe(*_args, **_kwargs):
        raise AssertionError("live RSS probe should not run while cache is fresh")

    monkeypatch.setattr(connection_runtime, "_test_rss_connection", _fail_live_probe)

    row = {
        "title": "Security Feed",
        "feed_url": "https://example.org/feed.xml",
        "tags": ["Security"],
        "poll_interval_minutes": 60,
    }

    status = connection_runtime.build_connection_status_row(
        "rss",
        "security-feed",
        row,
        page_probe=True,
        lang="de",
    )

    assert status["status"] == "ok"
    assert status["message"] == "RSS-Test erfolgreich aus Cache"
    assert status["target"] == "https://example.org/feed.xml"
    assert status["display_name"] == "Security Feed"


def test_rss_page_probe_uses_last_cached_status_when_cache_is_stale(monkeypatch) -> None:
    checked_at = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    monkeypatch.setattr(
        connection_runtime,
        "get_connection_health",
        lambda _ref: {
            "last_checked_at": checked_at,
            "last_status": "error",
            "last_target": "https://example.org/feed.xml",
            "last_message": "old cached error",
            "last_success_at": checked_at,
        },
    )

    def _fail_live_probe(*_args, **_kwargs):
        raise AssertionError("live RSS probe should not run while rendering the RSS page")

    monkeypatch.setattr(connection_runtime, "_test_rss_connection", _fail_live_probe)

    row = {
        "title": "Security Feed",
        "feed_url": "https://example.org/feed.xml",
        "poll_interval_minutes": 15,
    }

    status = connection_runtime.build_connection_status_row(
        "rss",
        "security-feed",
        row,
        page_probe=True,
        lang="de",
    )

    assert status["status"] == "error"
    assert status["message"] == "old cached error"
    assert status["display_name"] == "Security Feed"


def test_rss_page_probe_uses_stable_feed_specific_poll_phase_offset(monkeypatch) -> None:
    checked_at = (datetime.now(timezone.utc) - timedelta(seconds=75)).isoformat()

    monkeypatch.setattr(
        connection_runtime,
        "get_connection_health",
        lambda _ref: {
            "last_checked_at": checked_at,
            "last_status": "ok",
            "last_target": "https://example.org/feed.xml",
            "last_message": "cached with offset",
            "last_success_at": checked_at,
        },
    )
    monkeypatch.setattr(connection_runtime, "_rss_poll_phase_offset_seconds", lambda _ref, _row, _poll_seconds: 30)

    status = connection_runtime.build_connection_status_row(
        "rss",
        "security-feed",
        {
            "title": "Security Feed",
            "feed_url": "https://example.org/feed.xml",
            "poll_interval_minutes": 1,
        },
        page_probe=True,
        lang="de",
    )

    assert status["status"] == "ok"
    assert status["message"] == "cached with offset"


def test_rss_poll_phase_offset_is_deterministic_and_feed_specific() -> None:
    offsets = []
    for idx in range(1, 8):
        row = {"feed_url": f"https://example.org/feed-{idx}.xml"}
        offset_once = connection_runtime._rss_poll_phase_offset_seconds(f"feed-{idx}", row, 60)
        offset_twice = connection_runtime._rss_poll_phase_offset_seconds(f"feed-{idx}", row, 60)
        assert offset_once == offset_twice
        assert 0 <= offset_once < 60
        offsets.append(offset_once)

    assert len(set(offsets)) > 1


def test_rss_page_probe_without_cache_returns_non_blocking_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(connection_runtime, "get_connection_health", lambda _ref: {})

    def _fail_live_probe(*_args, **_kwargs):
        raise AssertionError("live RSS probe should not run without explicit ping")

    monkeypatch.setattr(connection_runtime, "_test_rss_connection", _fail_live_probe)

    status = connection_runtime.build_connection_status_row(
        "rss",
        "security-feed",
        {"feed_url": "https://example.org/feed.xml"},
        page_probe=True,
        lang="de",
    )

    assert status["status"] == "error"
    assert status["message"] == "Noch kein RSS-Status im Cache. Nutze 'Jetzt pingen' für eine Live-Prüfung."
    assert status["target"] == "https://example.org/feed.xml"


def test_cached_only_connection_status_uses_health_store_without_live_probe(monkeypatch) -> None:
    monkeypatch.setattr(
        connection_runtime,
        "get_connection_health",
        lambda _ref: {
            "last_checked_at": "2026-04-07T10:00:00+00:00",
            "last_status": "ok",
            "last_target": "https://api.example.org",
            "last_message": "Zuletzt erfolgreich getestet",
            "last_success_at": "2026-04-07T10:00:00+00:00",
        },
    )

    def _fail_live_probe(*_args, **_kwargs):
        raise AssertionError("live probe should not run while rendering cached connection status")

    monkeypatch.setattr(connection_runtime, "_test_http_api_connection", _fail_live_probe)

    status = connection_runtime.build_connection_status_row(
        "http_api",
        "inventory",
        {"title": "Inventory API", "base_url": "https://api.example.org"},
        cached_only=True,
        lang="de",
    )

    assert status["status"] == "ok"
    assert status["message"] == "Zuletzt erfolgreich getestet"
    assert status["display_name"] == "Inventory API"


def test_cached_only_connection_status_without_cache_returns_warn_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(connection_runtime, "get_connection_health", lambda _ref: {})

    status = connection_runtime.build_connection_status_row(
        "searxng",
        "web-allgemein",
        {"title": "Web Allgemein"},
        cached_only=True,
        lang="de",
    )

    assert status["status"] == "warn"
    assert status["message"] == "Noch kein Status im Cache. Nutze den Test-Button fuer eine Live-Pruefung."


def test_rss_connection_test_accepts_rdf_rss_feed(monkeypatch) -> None:
    payload = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\" xmlns=\"http://purl.org/rss/1.0/\">
  <channel rdf:about=\"https://example.org/feed\">
    <title>Example RSS 1.0</title>
  </channel>
  <item>
    <title>Alpha headline</title>
  </item>
  <item>
    <title>Beta headline</title>
  </item>
</rdf:RDF>
"""
    monkeypatch.setattr(connection_runtime, "urlopen", lambda _req, timeout=0: _FakeHttpResponse(payload, status=200))

    message = connection_runtime._test_rss_connection(
        "rdf-feed",
        {"feed_url": "https://example.org/feed.rdf", "timeout_seconds": 10},
        lang="de",
    )

    assert message == "Feed geladen: Example RSS 1.0 · Neueste Artikel: Alpha headline | Beta headline"


def test_rss_connection_test_reads_beyond_initial_8kb_chunk(monkeypatch) -> None:
    entries = "".join(f"<item><title>Entry {idx}</title></item>" for idx in range(500))
    payload = f"<?xml version=\"1.0\"?><rss><channel><title>Long Feed</title>{entries}</channel></rss>".encode("utf-8")
    assert len(payload) > 8192
    monkeypatch.setattr(connection_runtime, "urlopen", lambda _req, timeout=0: _FakeHttpResponse(payload, status=200))

    message = connection_runtime._test_rss_connection(
        "long-feed",
        {"feed_url": "https://example.org/source.xml", "timeout_seconds": 10},
        lang="de",
    )

    assert message == "Feed geladen: Long Feed · Neueste Artikel: Entry 0 | Entry 1 | Entry 2"


def test_extract_rss_preview_titles_supports_atom_feed() -> None:
    payload = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry><title>First item</title></entry>
  <entry><title>Second item</title></entry>
</feed>
"""

    feed_title, titles = connection_runtime._extract_rss_preview_titles(payload, max_items=3)

    assert feed_title == "Atom Feed"
    assert titles == ["First item", "Second item"]


def test_searxng_connection_test_accepts_json_results(monkeypatch) -> None:
    payload = b'{"query":"aria health check","results":[{"title":"Example","url":"https://example.org","content":"Snippet","engines":["duckduckgo"]}]}'
    monkeypatch.setattr(connection_runtime, "urlopen", lambda _req, timeout=0: _FakeHttpResponse(payload, status=200))

    message = connection_runtime._test_searxng_connection(
        "web-search",
        {"base_url": "http://searxng:8080", "timeout_seconds": 10, "language": "de-CH", "safe_search": 1},
        lang="de",
    )

    assert message == "SearXNG-Test erfolgreich für web-search"


def test_searxng_connection_test_uses_default_stack_url_when_profile_url_is_missing(monkeypatch) -> None:
    payload = b'{"query":"aria health check","results":[{"title":"Example","url":"https://example.org","content":"Snippet","engines":["duckduckgo"]}]}'
    captured_url: dict[str, str] = {}

    def _fake_open(request, timeout=0):
        captured_url["url"] = request.full_url
        return _FakeHttpResponse(payload, status=200)

    monkeypatch.setattr(connection_runtime, "urlopen", _fake_open)

    message = connection_runtime._test_searxng_connection(
        "web-search",
        {"timeout_seconds": 10, "language": "de-CH", "safe_search": 1},
        lang="de",
    )

    assert message == "SearXNG-Test erfolgreich für web-search"
    assert captured_url["url"].startswith("http://searxng:8080/search?")


def test_searxng_connection_test_shows_actionable_hint_on_rate_limit(monkeypatch) -> None:
    def _fail(_request, timeout=0):
        raise HTTPError("http://searxng:8080/search?q=aria", 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setattr(connection_runtime, "urlopen", _fail)

    try:
        connection_runtime._test_searxng_connection(
            "web-search",
            {"timeout_seconds": 10, "language": "de-CH", "safe_search": 1},
            lang="de",
        )
    except ValueError as exc:
        assert "SEARXNG_LIMITER=false" in str(exc)
        assert "HTTP 429" in str(exc)
    else:
        raise AssertionError("429 rate limit should return actionable SearXNG hint")


def test_rss_connection_test_rejects_json_with_actionable_hint(monkeypatch) -> None:
    monkeypatch.setattr(
        connection_runtime,
        "urlopen",
        lambda _req, timeout=0: _FakeHttpResponse(b'{"vulnerabilities": []}', status=200),
    )

    try:
        connection_runtime._test_rss_connection(
            "nvd-json",
            {"feed_url": "https://services.nvd.nist.gov/rest/json/cves/2.0", "timeout_seconds": 10},
            lang="de",
        )
    except ValueError as exc:
        assert str(exc) == "RSS-Test fehlgeschlagen: Diese URL liefert JSON statt RSS/Atom-XML. Bitte als HTTP-API-Connection anlegen."
    else:
        raise AssertionError("JSON API URL should not pass RSS connection validation")
