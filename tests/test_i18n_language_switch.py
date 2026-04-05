from __future__ import annotations

from fastapi.testclient import TestClient

import aria.main as main_mod
from aria.main import LANG_COOKIE, app


def test_login_page_switches_to_english_via_query_and_sets_cookie() -> None:
    client = TestClient(app)
    current_lang_cookie = main_mod._cookie_name(LANG_COOKIE, public_url='http://testserver')

    response = client.get('/login?lang=en')

    assert response.status_code == 200
    assert 'Sign in with username and password.' in response.text
    set_cookie_headers = response.headers.get_list('set-cookie')
    assert any(header.startswith(f'{current_lang_cookie}=en') for header in set_cookie_headers)


def test_login_page_uses_language_cookie_for_follow_up_request() -> None:
    client = TestClient(app)
    client.cookies.set(main_mod._cookie_name(LANG_COOKIE, public_url='http://testserver'), 'en')

    response = client.get('/login')

    assert response.status_code == 200
    assert 'Sign in with username and password.' in response.text
