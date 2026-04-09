from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.requests import Request

import aria.main as main_mod
from aria.main import AUTH_COOKIE, CONNECTION_CREATE_PENDING_COOKIE, CSRF_COOKIE, FORGET_PENDING_COOKIE, app


def _current_cookie_name(base_name: str, host: str = "testserver") -> str:
    return main_mod._cookie_name(base_name, public_url=f"http://{host}")


def _current_cookie_scope(host: str = "testserver") -> str:
    return main_mod._cookie_scope_source(public_url=f"http://{host}")


def test_protected_route_with_invalid_auth_cookie_redirects_to_session_expired_and_clears_session() -> None:
    client = TestClient(app)
    client.cookies.set(_current_cookie_name(AUTH_COOKIE), "invalid.session.cookie")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/session-expired?")
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{_current_cookie_name(AUTH_COOKIE)}=") for header in set_cookie_headers)


def test_session_expired_page_clears_auth_and_pending_cookies() -> None:
    client = TestClient(app)
    client.cookies.set(_current_cookie_name(AUTH_COOKIE), "invalid.session.cookie")
    client.cookies.set(FORGET_PENDING_COOKIE, "pending")
    client.cookies.set(CONNECTION_CREATE_PENDING_COOKIE, "pending")

    response = client.get("/session-expired")

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{_current_cookie_name(AUTH_COOKIE)}=") for header in set_cookie_headers)
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
    client.cookies.set(_current_cookie_name(AUTH_COOKIE), "invalid.session.cookie")
    client.cookies.set(_current_cookie_name(CSRF_COOKIE), "dummy")

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
    assert any(header.startswith(f"{_current_cookie_name(AUTH_COOKIE)}=") for header in set_cookie_headers)


def test_valid_signed_cookie_survives_temporary_auth_store_unavailability(monkeypatch) -> None:
    client = TestClient(app)
    client.cookies.set(
        _current_cookie_name(AUTH_COOKIE),
        main_mod._encode_auth_session("neo", "admin", scope=_current_cookie_scope()),
    )

    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")

    response = client.get("/stats", follow_redirects=False)

    assert response.status_code == 200


def test_json_fetch_with_temporary_auth_store_unavailability_keeps_auth_cookie(monkeypatch) -> None:
    client = TestClient(app)
    client.cookies.set(
        _current_cookie_name(AUTH_COOKIE),
        main_mod._encode_auth_session("neo", "admin", scope=_current_cookie_scope()),
    )
    client.cookies.set(_current_cookie_name(CSRF_COOKIE), "dummy")

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
    assert not any(header.startswith(f"{_current_cookie_name(AUTH_COOKIE)}=") for header in set_cookie_headers)


def test_public_health_request_with_invalid_auth_cookie_does_not_delete_cookie() -> None:
    client = TestClient(app)
    client.cookies.set(_current_cookie_name(AUTH_COOKIE), "invalid.session.cookie")

    response = client.get("/health", follow_redirects=False)

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert not any(header.startswith(f"{_current_cookie_name(AUTH_COOKIE)}=") for header in set_cookie_headers)


def test_cookie_namespace_differs_between_ports() -> None:
    cookie_a = main_mod._cookie_name(AUTH_COOKIE, public_url="http://aria.black.lan:8800")
    cookie_b = main_mod._cookie_name(AUTH_COOKIE, public_url="http://aria.black.lan:8810")

    assert cookie_a != cookie_b


def test_cookie_scope_prefers_request_host_over_configured_public_url() -> None:
    host = "aria.black.lan:8820"
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/stats",
            "root_path": "",
            "query_string": b"",
            "headers": [
                (b"host", host.encode("utf-8")),
            ],
            "client": ("127.0.0.1", 1234),
            "server": ("aria.black.lan", 8820),
        }
    )

    expected = main_mod._cookie_name(AUTH_COOKIE, public_url=f"http://{host}")
    actual = main_mod._cookie_name(AUTH_COOKIE, request=request, public_url="http://aria.black.lan:8810")

    assert actual == expected


def test_memories_upload_without_file_returns_redirect_instead_of_validation_json(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    client = TestClient(app)
    client.cookies.set(
        _current_cookie_name(AUTH_COOKIE),
        main_mod._encode_auth_session("neo", "admin", scope=_current_cookie_scope()),
    )
    client.cookies.set(_current_cookie_name(CSRF_COOKIE), "dummy")

    response = client.post(
        "/memories/upload",
        data={
            "csrf_token": "dummy",
            "collection": "",
            "new_collection_name": "",
            "type": "all",
            "q": "",
            "page": "1",
            "limit": "50",
            "sort": "updated_desc",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/memories?")


def test_memories_upload_multipart_submission_reaches_route(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "get_master_key", lambda *_args, **_kwargs: "")
    client = TestClient(app)
    client.cookies.set(
        _current_cookie_name(AUTH_COOKIE),
        main_mod._encode_auth_session("neo", "admin", scope=_current_cookie_scope()),
    )
    client.cookies.set(_current_cookie_name(CSRF_COOKIE), "dummy")

    response = client.post(
        "/memories/upload",
        data={
            "csrf_token": "dummy",
            "collection": "",
            "new_collection_name": "",
            "type": "all",
            "q": "",
            "page": "1",
            "limit": "50",
            "sort": "updated_desc",
        },
        files={"document_file": ("wissen.txt", b"Ein wenig Testwissen fuer ARIA.", "text/plain")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/memories?")


def test_namespaced_auth_cookie_takes_precedence_over_invalid_legacy_cookie() -> None:
    host = "aria.black.lan:8810"
    valid_cookie = main_mod._encode_auth_session("neo", "admin", scope=_current_cookie_scope())
    cookie_header = "; ".join(
        [
            f"{AUTH_COOKIE}=invalid.session.cookie",
            f"{_current_cookie_name(AUTH_COOKIE, host)}={valid_cookie}",
        ]
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/stats",
            "root_path": "",
            "query_string": b"",
            "headers": [
                (b"host", host.encode("utf-8")),
                (b"cookie", cookie_header.encode("utf-8")),
            ],
            "client": ("127.0.0.1", 1234),
            "server": ("aria.black.lan", 8810),
        }
    )
    request.state.cookie_public_url = ""
    request.state.cookie_names = main_mod._cookie_names_for_request(request, public_url="")

    assert main_mod._request_cookie_value(request, AUTH_COOKIE) == valid_cookie


def test_legacy_auth_cookie_is_ignored_when_no_namespaced_cookie_exists() -> None:
    host = "aria.black.lan:8810"
    legacy_cookie = main_mod._encode_auth_session("neo", "admin", scope=_current_cookie_scope())
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/stats",
            "root_path": "",
            "query_string": b"",
            "headers": [
                (b"host", host.encode("utf-8")),
                (b"cookie", f"{AUTH_COOKIE}={legacy_cookie}".encode("utf-8")),
            ],
            "client": ("127.0.0.1", 1234),
            "server": ("aria.black.lan", 8810),
        }
    )
    request.state.cookie_public_url = f"http://{host}"
    request.state.cookie_names = main_mod._cookie_names_for_request(request, public_url=f"http://{host}")

    assert main_mod._request_cookie_value(request, AUTH_COOKIE) == ""


def test_auth_cookie_from_other_instance_scope_is_rejected() -> None:
    client = TestClient(app)
    foreign_scope = main_mod._cookie_scope_source(public_url="http://aria.black.lan:8810")
    client.cookies.set(
        _current_cookie_name(AUTH_COOKIE),
        main_mod._encode_auth_session("whity", "admin", scope=foreign_scope),
    )

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/session-expired?")
