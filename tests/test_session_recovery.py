from __future__ import annotations

from fastapi.testclient import TestClient

from aria.main import AUTH_COOKIE, CONNECTION_CREATE_PENDING_COOKIE, FORGET_PENDING_COOKIE, app


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
