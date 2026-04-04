from __future__ import annotations

from aria.core.connection_catalog import (
    connection_chat_emoji,
    connection_chat_defaults,
    connection_field_specs,
    connection_menu_meta,
    connection_menu_rows,
    connection_overview_meta,
    connection_status_meta,
    connection_template_name,
    ordered_connection_kinds,
)


def test_connection_template_name_handles_special_route_names() -> None:
    assert connection_template_name("http_api") == "config_connections_http_api.html"
    assert connection_template_name("email") == "config_connections_smtp.html"
    assert connection_template_name("imap") == "config_connections_imap.html"


def test_connection_menu_rows_follow_catalog_order() -> None:
    rows = connection_menu_rows()
    assert [row["kind"] for row in rows] == ordered_connection_kinds()
    assert [row["kind"] for row in rows[-3:]] == ["mqtt", "email", "imap"]
    assert all(bool(row["alpha"]) for row in rows[-3:])


def test_connection_menu_meta_exposes_page_text_keys() -> None:
    webhook = connection_menu_meta("webhook")
    assert webhook["title_key"] == "config_conn.webhook_title"
    assert webhook["desc_key"] == "config_conn.webhook_subtitle"
    assert webhook["url"] == "/config/connections/webhook"


def test_connection_status_meta_supports_overrides_and_defaults() -> None:
    ssh = connection_status_meta("ssh")
    assert ssh["title_key"] == "config_conn.live_status"
    assert ssh["empty_key"] == "config_conn.no_profiles_status_hint"

    rss = connection_status_meta("rss")
    assert rss["title_key"] == "config_conn.rss_live_status"
    assert rss["empty_key"] == "config_conn.rss_no_profiles_hint"


def test_connection_overview_meta_supports_defaults() -> None:
    mqtt = connection_overview_meta("mqtt")
    assert mqtt["profiles"]["hint_key"] == "config_conn.mqtt_profiles_hint"
    assert mqtt["healthy"]["hint_key"] == "config_conn.mqtt_healthy_hint"
    assert mqtt["issues"]["hint_key"] == "config_conn.mqtt_issue_hint"


def test_connection_chat_emoji_uses_catalog_icons() -> None:
    assert connection_chat_emoji("rss") == "📰"
    assert connection_chat_emoji("ssh") == "🔐"


def test_rss_catalog_exposes_poll_interval_field() -> None:
    rss = connection_menu_meta("rss")
    assert rss["kind"] == "rss"
    defaults = connection_chat_defaults("rss")
    fields = connection_field_specs("rss")

    assert defaults["poll_interval_minutes"] == 60
    assert fields["poll_interval_minutes"]["type"] == "int"
    assert fields["poll_interval_minutes"]["min"] == 1
    assert fields["poll_interval_minutes"]["max"] == 10080
