from __future__ import annotations

import importlib
import sys

from aria.modules import MODULE_MANIFESTS
from aria.modules.inbound_event_storage.store import InboundEventStore
from aria.modules.inbound_event_storage.store import normalize_inbound_event


def test_notification_and_inbound_storage_legacy_imports_are_identity_aliases() -> None:
    pairs = {
        "aria.modules.discord_alerting.alerts": "aria.modules.discord_alerting.alerts",
        "aria.modules.inbound_event_storage.store": "aria.modules.inbound_event_storage.store",
    }

    for legacy_name, canonical_name in pairs.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert legacy is canonical
        assert sys.modules[legacy_name] is canonical


def test_notification_and_inbound_storage_manifests_are_passive() -> None:
    for module_id in ("discord_alerting", "inbound_event_storage"):
        manifest = MODULE_MANIFESTS[module_id]
        assert manifest["status"] == "import_boundary_active"
        assert manifest["build_allowed"] is False
        assert manifest["runtime_access_allowed"] is False


def test_inbound_storage_contract_uses_only_caller_supplied_tmp_path(tmp_path) -> None:
    store = InboundEventStore(tmp_path / "events.sqlite3")
    event = normalize_inbound_event(
        source_ref="watcher",
        provider_profile="senscap_watcher",
        content_type="application/json",
        body=b'{"value":22,"api_token":"secret"}',
        headers={"x-event-id": "evt-1"},
        remote_host="192.0.2.1",
    )

    event_id, duplicate = store.record(event, max_events_per_source=2)

    assert event_id == event.event_id
    assert duplicate is False
    assert "secret" not in store.list_recent()[0]["preview"]
