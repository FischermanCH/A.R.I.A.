from __future__ import annotations

from aria.core.action_plan import ActionPlan
from aria.core.capability_catalog import build_capability_detail_lines, capability_executor_bindings


def test_capability_executor_bindings_cover_expected_pairs() -> None:
    bindings = set(capability_executor_bindings())
    assert ("sftp", "file_read") in bindings
    assert ("smb", "file_write") in bindings
    assert ("rss", "feed_read") in bindings
    assert ("mqtt", "mqtt_publish") in bindings


def test_build_capability_detail_lines_uses_catalog_detail_metadata() -> None:
    api_details = build_capability_detail_lines(
        ActionPlan(capability="api_request", connection_kind="http_api", connection_ref="inventory-api", path="/health"),
        lambda kind: kind.upper(),
    )
    mqtt_details = build_capability_detail_lines(
        ActionPlan(capability="mqtt_publish", connection_kind="mqtt", connection_ref="event-bus", path="aria/events"),
        lambda kind: kind.upper(),
    )
    search_details = build_capability_detail_lines(
        ActionPlan(capability="mail_search", connection_kind="imap", connection_ref="ops-inbox", content="backup failed"),
        lambda kind: kind.upper(),
    )

    assert api_details[-1] == "Pfad: /health"
    assert mqtt_details[-1] == "Topic: aria/events"
    assert search_details[-1] == "Suche: backup failed"


def test_build_capability_detail_lines_supports_english_labels() -> None:
    details = build_capability_detail_lines(
        ActionPlan(capability="api_request", connection_kind="http_api", connection_ref="inventory-api", path="/health"),
        lambda kind: kind.upper(),
        language="en",
    )
    assert details == [
        "Executed via HTTP_API profile `inventory-api`",
        "Path: /health",
    ]
