from __future__ import annotations

from aria.core.config import (
    ConnectionsConfig,
    LLMConfig,
    RSSConnectionConfig,
    Settings,
    SSHConnectionConfig,
    WebsiteConnectionConfig,
)
from aria.core.context_surface_adapters import build_builtin_surface_registry


def _settings_with_connections() -> Settings:
    return Settings(
        llm=LLMConfig(model="test-model"),
        connections=ConnectionsConfig(
            ssh={
                "dns-node-01": SSHConnectionConfig(
                    host="10.0.0.53",
                    user="admin",
                    key_path="/home/example/.ssh/id_ed25519",
                    title="DNS Node",
                    description="Internal DNS maintenance host",
                    aliases=["dns"],
                    tags=["infra"],
                )
            },
            website={
                "sports-watch": WebsiteConnectionConfig(
                    url="https://example.invalid/sports",
                    title="Sports Watch",
                    description="Observed sports website",
                    group_name="Sport",
                )
            },
            rss={
                "sports-feed": RSSConnectionConfig(
                    feed_url="https://example.invalid/feed.xml",
                    title="Sports Feed",
                    group_name="Sport",
                )
            },
        ),
    )


def test_builtin_surface_registry_exposes_generic_surfaces() -> None:
    registry = build_builtin_surface_registry(_settings_with_connections())

    assert registry.surface_ids() == ("memory", "notes", "docs", "connections", "web")
    assert registry.get("connections") is not None
    assert registry.get("home-assistant") is None


def test_connections_surface_preserves_compact_stage_one_metadata_without_secret_inventory() -> None:
    payload = build_builtin_surface_registry(_settings_with_connections()).as_routing_meta_context()
    connections = next(surface for surface in payload["surfaces"] if surface["surface_id"] == "connections")

    metadata = connections["routing_metadata"]
    assert metadata["configured_total"] == 3
    assert set(metadata["configured_kinds"]) == {"rss", "ssh", "website"}
    assert metadata["configured_kind_labels"]["website"]
    assert "configured" not in metadata

    flattened = str(metadata)
    assert "dns-node-01" not in flattened
    assert "sports-watch" not in flattened
    assert "Sport" not in flattened
    assert "10.0.0.53" not in flattened
    assert "id_ed25519" not in flattened
    assert "https://example.invalid/sports" not in flattened
    assert "https://example.invalid/feed.xml" not in flattened


def test_connections_surface_keeps_deep_inventory_for_selected_loader() -> None:
    connections = build_builtin_surface_registry(_settings_with_connections()).get("connections")
    assert connections is not None

    metadata = connections.metadata
    assert metadata["configured_total"] == 3
    assert set(metadata["configured_kinds"]) == {"rss", "ssh", "website"}
    assert metadata["configured"]["ssh"]["configured_refs"] == ["dns-node-01"]
    assert metadata["configured"]["website"]["safe_summaries"][0]["group_name"] == "Sport"

    flattened = str(metadata)
    assert "10.0.0.53" not in flattened
    assert "id_ed25519" not in flattened
    assert "https://example.invalid/sports" not in flattened
    assert "https://example.invalid/feed.xml" not in flattened


def test_surface_metadata_reaches_routing_meta_context_for_llm_selection() -> None:
    payload = build_builtin_surface_registry(_settings_with_connections()).as_routing_meta_context()
    memory = next(surface for surface in payload["surfaces"] if surface["surface_id"] == "memory")
    web = next(surface for surface in payload["surfaces"] if surface["surface_id"] == "web")

    assert memory["routing_metadata"]["backend"] == "qdrant"
    assert "facts" in memory["routing_metadata"]["families"]
    assert web["routing_metadata"]["configured_count"] == 0
    assert payload["contract"]["new_surfaces_extend_by_registration"] is True
    assert payload["contract"]["stage_1_is_meta_only"] is True
