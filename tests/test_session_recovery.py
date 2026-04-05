from __future__ import annotations

from fastapi.testclient import TestClient

import aria.main as main_mod
from aria.main import AUTH_COOKIE, CONNECTION_CREATE_PENDING_COOKIE, CSRF_COOKIE, FORGET_PENDING_COOKIE, app


def test_protected_route_with_invalid_auth_cookie_redirects_to_session_expired_and_clears_session() -> None:
    client = TestClient(app)
    client.cookies.set(AUTH_COOKIE, "invalid.session.cookie")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/session-expired?")
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{AUTH_COOKIE}=") for header in set_cookie_headers)


def test_session_expired_page_clears_auth_and_pending_cookies() -> None:
    client = TestClient(app)
    client.cookies.set(AUTH_COOKIE, "invalid.session.cookie")
    client.cookies.set(FORGET_PENDING_COOKIE, "pending")
    client.cookies.set(CONNECTION_CREATE_PENDING_COOKIE, "pending")

    response = client.get("/session-expired")

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{AUTH_COOKIE}=") for header in set_cookie_headers)
    assert any(header.startswith(f"{FORGET_PENDING_COOKIE}=") for header in set_cookie_headers)
    assert any(header.startswith(f"{CONNECTION_CREATE_PENDING_COOKIE}=") for header in set_cookie_headers)


def test_json_fetch_on_protected_route_returns_login_required_json() -> None:
    client = TestClient(app)

    response = client.post(
        "/config/llm/models",
        headers={
            "accept": "application/json",
            "x-requested-with": "fetch",
            "x-csrf-token": "dummy",
        },
        data={"api_base": "http://example.invalid"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert response.json()["code"] == "login_required"
    assert response.json()["login_url"].startswith("/login?next=")


def test_json_fetch_with_invalid_auth_cookie_returns_session_expired_json_and_clears_auth() -> None:
    client = TestClient(app)
    client.cookies.set(AUTH_COOKIE, "invalid.session.cookie")
    client.cookies.set(CSRF_COOKIE, "dummy")

    response = client.post(
        "/config/llm/models",
        headers={
            "accept": "application/json",
            "x-requested-with": "fetch",
            "x-csrf-token": "dummy",
        },
        data={"api_base": "http://example.invalid"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == "session_expired"
    assert payload["login_url"].startswith("/login?next=")
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{AUTH_COOKIE}=") for header in set_cookie_headers)


def test_valid_signed_cookie_survives_temporary_auth_store_unavailability(monkeypatch) -> None:
    client = TestClient(app)
    client.cookies.set(AUTH_COOKIE, main_mod._encode_auth_session("neo", "admin"))

    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    response = client.get("/stats", follow_redirects=False)

    assert response.status_code == 200


def test_json_fetch_with_temporary_auth_store_unavailability_keeps_auth_cookie(monkeypatch) -> None:
    client = TestClient(app)
    client.cookies.set(AUTH_COOKIE, main_mod._encode_auth_session("neo", "admin"))
    client.cookies.set(CSRF_COOKIE, "dummy")

    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    response = client.post(
        "/config/llm/models",
        headers={
            "accept": "application/json",
            "x-requested-with": "fetch",
            "x-csrf-token": "dummy",
        },
        data={"api_base": "http://example.invalid"},
        follow_redirects=False,
    )

    assert response.status_code in {401, 403}
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert not any(header.startswith(f"{AUTH_COOKIE}=") for header in set_cookie_headers)


def test_public_health_request_with_invalid_auth_cookie_does_not_delete_cookie() -> None:
    client = TestClient(app)
    client.cookies.set(AUTH_COOKIE, "invalid.session.cookie")

    response = client.get("/health", follow_redirects=False)

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert not any(header.startswith(f"{AUTH_COOKIE}=") for header in set_cookie_headers)
