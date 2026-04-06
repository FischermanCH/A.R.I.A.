from __future__ import annotations

from types import SimpleNamespace

from aria.core.discord_alerts import runtime_host_line
from aria.core.runtime_endpoint import cookie_should_be_secure, request_is_secure, resolve_runtime_url


def _request(*, scheme: str = "http", headers: dict[str, str] | None = None, host: str = "localhost", port: int = 8800):
    return SimpleNamespace(
        headers=headers or {},
        url=SimpleNamespace(scheme=scheme, hostname=host, port=port),
    )


def _settings(*, host: str = "0.0.0.0", port: int = 8800, public_url: str = ""):
    return SimpleNamespace(aria=SimpleNamespace(host=host, port=port, public_url=public_url))


def test_request_is_secure_uses_forwarded_proto() -> None:
    request = _request(headers={"x-forwarded-proto": "https", "x-forwarded-host": "aria.example", "host": "aria.example"})

    assert request_is_secure(request) is True


def test_request_is_secure_falls_back_to_request_scheme() -> None:
    request = _request(scheme="https", headers={"host": "aria.local"})

    assert request_is_secure(request) is True


def test_request_is_secure_uses_first_forwarded_proto_value() -> None:
    request = _request(headers={"x-forwarded-proto": "https, http", "x-forwarded-host": "aria.example", "host": "aria.example"})

    assert request_is_secure(request) is True


def test_request_is_secure_ignores_bare_forwarded_proto_on_plain_http() -> None:
    request = _request(headers={"x-forwarded-proto": "https", "host": "aria.example"})

    assert request_is_secure(request) is False


def test_request_is_secure_supports_standard_forwarded_header() -> None:
    request = _request(headers={"forwarded": 'for=1.2.3.4;proto=https;host=aria.example', "host": "internal:8800"})

    assert request_is_secure(request) is True


def test_cookie_should_be_secure_uses_public_url_over_forwarded_headers() -> None:
    request = _request(headers={"forwarded": 'for=1.2.3.4;proto=https;host=aria.example', "host": "internal:8800"})

    assert cookie_should_be_secure(request, public_url="http://aria.black.lan") is False


def test_cookie_should_be_secure_accepts_https_public_url() -> None:
    request = _request(scheme="http", headers={"host": "internal:8800"})

    assert cookie_should_be_secure(request, public_url="https://aria.example") is True


def test_cookie_should_be_secure_falls_back_to_real_request_scheme() -> None:
    request = _request(scheme="https", headers={"host": "aria.local"})

    assert cookie_should_be_secure(request) is True


def test_resolve_runtime_url_prefers_forwarded_host_and_proto() -> None:
    request = _request(
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "aria.example",
            "host": "internal:8800",
        },
        host="internal",
        port=8800,
    )

    assert resolve_runtime_url(_settings(), request) == "https://aria.example"


def test_resolve_runtime_url_uses_request_host_when_no_forwarded_host() -> None:
    request = _request(headers={"host": "aria.local:8443"}, host="aria.local", port=8443)

    assert resolve_runtime_url(_settings(), request) == "http://aria.local:8443"


def test_resolve_runtime_url_prefers_configured_public_url_without_request() -> None:
    assert resolve_runtime_url(_settings(public_url="http://aria.black.lan/")) == "http://aria.black.lan"


def test_resolve_runtime_url_prefers_configured_public_url_over_request_host() -> None:
    request = _request(headers={"host": "172.18.0.3:8800"}, host="172.18.0.3", port=8800)

    assert resolve_runtime_url(_settings(public_url="http://aria.black.lan"), request) == "http://aria.black.lan"


def test_runtime_host_line_prefers_configured_public_url() -> None:
    assert runtime_host_line(_settings(public_url="http://aria.black.lan/")) == "Host: http://aria.black.lan"


def test_runtime_host_line_avoids_bind_all_bridge_guessing() -> None:
    assert runtime_host_line(_settings(host="0.0.0.0", port=8800, public_url="")) == (
        "Host: Public URL nicht konfiguriert (setze ARIA_PUBLIC_URL)"
    )
