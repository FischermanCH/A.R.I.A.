from __future__ import annotations

from types import SimpleNamespace

from aria.core.connection_ref_scope import ConnectionRefScope


def test_connection_ref_scope_normalizes_draft_refs() -> None:
    scope = ConnectionRefScope.from_draft(
        SimpleNamespace(
            explicit_connection_ref="  ops-backup-01  ",
            requested_connection_ref="  backup server  ",
        )
    )

    assert scope.explicit_ref == "ops-backup-01"
    assert scope.requested_ref == "backup server"
    assert scope.has_any is True
    assert scope.debug_fields() == {
        "explicit_ref": "ops-backup-01",
        "requested_ref": "backup server",
    }


def test_connection_ref_scope_payload_source_can_use_requested_ref_as_explicit() -> None:
    scope = ConnectionRefScope.from_payload(
        {"connection_ref": "ops-mgmt-01", "requested_connection_ref": "backup server"},
        routing_decision={"ref": "ops-routing-01"},
        explicit_ref_source="requested",
    )

    assert scope.explicit_ref == "backup server"
    assert scope.requested_ref == "backup server"


def test_connection_ref_scope_payload_prefers_routing_ref_by_default() -> None:
    scope = ConnectionRefScope.from_payload(
        {"connection_ref": "ops-mgmt-01", "requested_connection_ref": "backup server"},
        routing_decision={"ref": "ops-routing-01"},
    )

    assert scope.explicit_ref == "ops-routing-01"
    assert scope.requested_ref == "backup server"
