from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def test_rss_connection_test_accepts_rdf_rss_feed(monkeypatch) -> None:
    payload = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\" xmlns=\"http://purl.org/rss/1.0/\">
  <channel rdf:about=\"https://example.org/feed\">
    <title>Example RSS 1.0</title>
  </channel>
</rdf:RDF>
"""
    monkeypatch.setattr(connection_runtime, "urlopen", lambda _req, timeout=0: _FakeHttpResponse(payload, status=200))

    message = connection_runtime._test_rss_connection(
        "rdf-feed",
        {"feed_url": "https://example.org/feed.rdf", "timeout_seconds": 10},
        lang="de",
    )

    assert message == "RSS-Test erfolgreich für rdf-feed"


def test_rss_connection_test_reads_beyond_initial_8kb_chunk(monkeypatch) -> None:
    entries = "".join(f"<item><title>Entry {idx}</title></item>" for idx in range(500))
    payload = f"<?xml version=\"1.0\"?><source>{entries}</source>".encode("utf-8")
    assert len(payload) > 8192
    monkeypatch.setattr(connection_runtime, "urlopen", lambda _req, timeout=0: _FakeHttpResponse(payload, status=200))

    message = connection_runtime._test_rss_connection(
        "long-feed",
        {"feed_url": "https://example.org/source.xml", "timeout_seconds": 10},
        lang="de",
    )

    assert message == "RSS-Test erfolgreich für long-feed"


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
