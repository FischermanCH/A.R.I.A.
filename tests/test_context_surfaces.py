from __future__ import annotations

import pytest

from aria.core.context_surfaces import (
    ContextItem,
    ContextPacket,
    ContextRequest,
    ContextSurface,
    LoadedContextSurface,
    SurfaceRegistry,
)


def test_surface_registry_exports_generic_meta_context_without_trigger_contract() -> None:
    registry = SurfaceRegistry(
        [
            ContextSurface(
                surface_id="memory",
                surface_type="local_context",
                display_name="Memory",
                what_it_knows="Durable facts, preferences, learning, sessions, and prior user feedback.",
                what_it_can_load="Source-bound snippets from local user memory collections.",
                supported_modes=("answer", "search", "inventory"),
                cost_hint="cheap",
                latency_hint="fast",
                risk_hint="low",
            ),
            ContextSurface(
                surface_id="connections",
                surface_type="inventory",
                display_name="Connections",
                what_it_knows="Configured user connections, endpoint metadata, available services, and safe refs.",
                what_it_can_load="Connection inventory and matching non-secret metadata.",
                what_it_can_do="Request guarded execution through registered connection executors.",
                supported_modes=("answer", "inventory", "action"),
                cost_hint="free",
                latency_hint="instant",
                risk_hint="medium",
                guardrail_notes=("Never expose secrets.", "Actions require policy validation."),
            ),
        ]
    )

    payload = registry.as_routing_meta_context()

    assert payload["contract"]["no_trigger_words"] is True
    assert payload["contract"]["new_surfaces_extend_by_registration"] is True
    assert "preserve_existing_user_data" in payload["contract"]["user_data_policy"]
    assert [surface["surface_id"] for surface in payload["surfaces"]] == ["memory", "connections"]
    assert payload["surfaces"][1]["supported_modes"] == ["answer", "inventory", "action"]
    assert payload["surfaces"][1]["guardrail_notes"] == [
        "Never expose secrets.",
        "Actions require policy validation.",
    ]


def test_surface_registry_accepts_future_surface_without_central_changes() -> None:
    registry = SurfaceRegistry()
    registry.register(
        ContextSurface(
            surface_id="home-assistant",
            surface_type="home_brain",
            display_name="Home Assistant",
            what_it_knows="Smart-home entity metadata, rooms, devices, sensors, and automation state.",
            what_it_can_load="Relevant entity state and automation context for the requested home task.",
            what_it_can_do="Propose guarded smart-home actions through the registered executor.",
            supported_modes=("answer", "inventory", "action", "clarify"),
            cost_hint="cheap",
            latency_hint="fast",
            risk_hint="medium",
        )
    )

    valid = registry.validate_requests(
        [
            ContextRequest(surface_id="home-assistant", mode="inventory", query="Welche Sensoren sind aktiv?"),
            ContextRequest(surface_id="home-assistant", mode="action", query="Licht im Buero einschalten"),
        ]
    )

    assert registry.surface_ids() == ("home-assistant",)
    assert [request.mode for request in valid] == ["inventory", "action"]


def test_registry_rejects_duplicate_surfaces() -> None:
    surface = ContextSurface(
        surface_id="notes",
        surface_type="local_context",
        display_name="Notes",
        what_it_knows="User-maintained notes.",
        what_it_can_load="Matching note excerpts.",
    )
    registry = SurfaceRegistry([surface])

    with pytest.raises(ValueError, match="Duplicate context surface"):
        registry.register(surface)


def test_registry_validates_llm_requests_against_registered_surface_contracts() -> None:
    registry = SurfaceRegistry(
        [
            ContextSurface(
                surface_id="docs",
                surface_type="local_context",
                display_name="Docs",
                what_it_knows="Imported project documents.",
                what_it_can_load="Relevant document excerpts.",
                supported_modes=("answer", "search", "summarize"),
            )
        ]
    )

    valid = registry.validate_requests(
        [
            ContextRequest(surface_id="docs", mode="search", query="engine directive"),
            ContextRequest(surface_id="docs", mode="action", query="delete docs"),
            ContextRequest(surface_id="missing", mode="search", query="anything"),
        ]
    )

    assert valid == (ContextRequest(surface_id="docs", mode="search", query="engine directive"),)


def test_context_packet_serializes_loaded_and_empty_surfaces() -> None:
    packet = ContextPacket(
        turn_id="turn-1",
        requests=(
            ContextRequest(surface_id="notes", mode="search", query="UI-Regel"),
            ContextRequest(surface_id="websites", mode="inventory", query="Sport"),
        ),
        loaded=(
            LoadedContextSurface(
                surface_id="notes",
                status="empty",
                message="No matching notes found.",
                latency_ms=12,
            ),
            LoadedContextSurface(
                surface_id="websites",
                status="loaded",
                items=(
                    ContextItem(
                        surface_id="websites",
                        title="Sports feed",
                        content="Configured observed website with sports topic metadata.",
                        source_ref="website:sports-feed",
                    ),
                ),
                latency_ms=18,
                cost={"tokens": 0},
            ),
        ),
        debug=("turn_plan_selected_context",),
    )

    payload = packet.as_payload()

    assert payload["turn_id"] == "turn-1"
    assert payload["loaded"][0]["status"] == "empty"
    assert payload["loaded"][0]["items"] == []
    assert payload["loaded"][1]["items"][0]["source_ref"] == "website:sports-feed"
    assert payload["debug"] == ["turn_plan_selected_context"]
