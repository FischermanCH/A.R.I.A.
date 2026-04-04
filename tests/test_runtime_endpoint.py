from __future__ import annotations

from types import SimpleNamespace

from aria.core.runtime_endpoint import request_is_secure, resolve_runtime_url


def _request(*, scheme: str = "http", headers: dict[str, str] | None = None, host: str = "localhost", port: int = 8800):
    return SimpleNamespace(
        headers=headers or {},
        url=SimpleNamespace(scheme=scheme, hostname=host, port=port),
    )


def _settings(*, host: str = "0.0.0.0", port: int = 8800, public_url: str = ""):
    return SimpleNamespace(aria=SimpleNamespace(host=host, port=port, public_url=public_url))


def test_request_is_secure_uses_forwarded_proto() -> None:
    request = _request(headers={"x-forwarded-proto": "https", "host": "aria.example"})

    assert request_is_secure(request) is True


def test_request_is_secure_falls_back_to_request_scheme() -> None:
    request = _request(scheme="https", headers={"host": "aria.local"})

    assert request_is_secure(request) is True


def test_request_is_secure_uses_first_forwarded_proto_value() -> None:
    request = _request(headers={"x-forwarded-proto": "https, http", "host": "aria.example"})

    assert request_is_secure(request) is True


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
