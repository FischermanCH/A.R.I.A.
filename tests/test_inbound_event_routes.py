from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aria.modules.configuration_foundations.config import ConnectionsConfig, InboundWebhookConnectionConfig, LLMConfig, Settings
from aria.modules.inbound_event_storage.store import InboundEventStore
from aria.modules.inbound_event_storage.routes import InboundEventRouteDeps, register_inbound_event_routes


def _build_client(
    tmp_path,
    *,
    enabled: bool = True,
    max_body_bytes: int = 65536,
    max_events: int = 1000,
) -> tuple[TestClient, InboundEventStore]:
    settings = Settings(
        llm=LLMConfig(model="test-model"),
        connections=ConnectionsConfig(
            inbound_webhook={
                "watcher": InboundWebhookConnectionConfig(
                    enabled=enabled,
                    provider_profile="senscap_watcher",
                    max_body_bytes=max_body_bytes,
                    max_events=max_events,
                )
            }
        ),
    )
    store = InboundEventStore(tmp_path / "inbound-events.sqlite3")
    app = FastAPI()
    register_inbound_event_routes(
        app,
        InboundEventRouteDeps(
            get_settings=lambda: settings,
            get_token=lambda ref: "source-secret" if ref == "watcher" else "",
            event_store=store,
        ),
    )
    return TestClient(app), store


def test_inbound_event_accepts_machine_request_without_browser_session(tmp_path) -> None:
    client, store = _build_client(tmp_path)

    response = client.post(
        "/api/connections/inbound/watcher/events",
        headers={
            "X-ARIA-Inbound-Token": "source-secret",
            "X-Event-ID": "watcher-42",
        },
        json={
            "device_id": "sensecap-01",
            "measurement": "temperature",
            "value": 22.4,
            "unit": "C",
            "api_token": "must-not-survive",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    rows = store.list_recent(source_ref="watcher")
    assert len(rows) == 1
    assert rows[0]["contract"] == "inbound_event_v1"
    assert rows[0]["routing_policy"] == "log_only"
    assert rows[0]["activity_type"] == "inbound_event_received"
    assert rows[0]["processing_state"] == "stored"
    assert rows[0]["technical_fields"]["device_id"] == "sensecap-01"
    assert rows[0]["technical_fields"]["value"] == 22.4
    assert "must-not-survive" not in rows[0]["preview"]
    assert "[REDACTED]" in rows[0]["preview"]
    assert rows[0]["raw_body"] == ""


def test_inbound_event_fails_closed_for_unknown_source_and_bad_token(tmp_path) -> None:
    client, store = _build_client(tmp_path)

    unknown = client.post(
        "/api/connections/inbound/missing/events",
        headers={"X-ARIA-Inbound-Token": "source-secret"},
        json={"value": 1},
    )
    unauthorized = client.post(
        "/api/connections/inbound/watcher/events",
        headers={"X-ARIA-Inbound-Token": "wrong"},
        json={"value": 1},
    )

    assert unknown.status_code == 404
    assert unknown.json()["code"] == "unknown_source"
    assert unauthorized.status_code == 401
    assert unauthorized.json()["code"] == "invalid_token"
    assert store.list_recent() == []


def test_inbound_event_fails_closed_for_disabled_source(tmp_path) -> None:
    client, store = _build_client(tmp_path, enabled=False)

    response = client.post(
        "/api/connections/inbound/watcher/events",
        headers={"X-ARIA-Inbound-Token": "source-secret"},
        json={"value": 1},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "source_disabled"
    assert store.list_recent() == []


def test_inbound_event_enforces_content_type_and_body_limit(tmp_path) -> None:
    client, store = _build_client(tmp_path, max_body_bytes=12)

    unsupported = client.post(
        "/api/connections/inbound/watcher/events",
        headers={"X-ARIA-Inbound-Token": "source-secret", "Content-Type": "application/xml"},
        content="<value>1</value>",
    )
    oversized = client.post(
        "/api/connections/inbound/watcher/events",
        headers={"X-ARIA-Inbound-Token": "source-secret", "Content-Type": "text/plain"},
        content="x" * 13,
    )

    assert unsupported.status_code == 415
    assert unsupported.json()["code"] == "unsupported_content_type"
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "body_too_large"
    assert store.list_recent() == []


def test_inbound_event_rejects_invalid_json_without_storing_it(tmp_path) -> None:
    client, store = _build_client(tmp_path)

    response = client.post(
        "/api/connections/inbound/watcher/events",
        headers={
            "X-ARIA-Inbound-Token": "source-secret",
            "Content-Type": "application/json",
        },
        content='{"value":',
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_json"
    assert store.list_recent() == []


def test_inbound_event_is_idempotent_by_source_event_id(tmp_path) -> None:
    client, store = _build_client(tmp_path)
    headers = {
        "Authorization": "Bearer source-secret",
        "X-Event-ID": "stable-event",
        "Content-Type": "application/json",
    }

    first = client.post("/api/connections/inbound/watcher/events", headers=headers, content='{"value": 1}')
    second = client.post("/api/connections/inbound/watcher/events", headers=headers, content='{"value": 1}')

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["event_id"] == first.json()["event_id"]
    assert len(store.list_recent()) == 1


def test_inbound_event_retention_is_bounded_per_source(tmp_path) -> None:
    client, store = _build_client(tmp_path, max_events=2)

    for index in range(3):
        response = client.post(
            "/api/connections/inbound/watcher/events",
            headers={
                "X-ARIA-Inbound-Token": "source-secret",
                "X-Event-ID": f"event-{index}",
            },
            json={"value": index},
        )
        assert response.status_code == 202

    rows = store.list_recent(source_ref="watcher")
    assert len(rows) == 2
    assert {row["source_event_id"] for row in rows} == {"event-1", "event-2"}


def test_inbound_event_returns_stable_error_when_token_store_fails(tmp_path) -> None:
    settings = Settings(
        llm=LLMConfig(model="test-model"),
        connections=ConnectionsConfig(
            inbound_webhook={"watcher": InboundWebhookConnectionConfig()}
        ),
    )
    store = InboundEventStore(tmp_path / "inbound-events.sqlite3")
    app = FastAPI()

    def failing_token_resolver(ref: str) -> str:
        raise RuntimeError("secure store details must not escape")

    register_inbound_event_routes(
        app,
        InboundEventRouteDeps(
            get_settings=lambda: settings,
            get_token=failing_token_resolver,
            event_store=store,
        ),
    )

    response = TestClient(app).post(
        "/api/connections/inbound/watcher/events",
        headers={"X-ARIA-Inbound-Token": "anything"},
        json={"value": 1},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "source_auth_unavailable"
    assert "secure store details" not in response.text
