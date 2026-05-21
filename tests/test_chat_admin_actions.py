from __future__ import annotations

from aria.web.chat_admin_actions import _parse_connection_delete_request


def test_connection_delete_parser_ignores_webhook_payload_delete_text() -> None:
    assert _parse_connection_delete_request("sende an webhook : delete user record") is None


def test_connection_delete_parser_still_accepts_explicit_kind_delete() -> None:
    assert _parse_connection_delete_request("delete ssh pihole1") == ("ssh", "pihole1")


def test_connection_delete_parser_still_accepts_explicit_connection_delete() -> None:
    assert _parse_connection_delete_request("delete verbindung pihole1") == ("", "pihole1")
