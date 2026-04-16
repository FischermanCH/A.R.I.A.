from __future__ import annotations

import asyncio

from aria.core.routing_resolver import RoutingResolver, infer_preferred_connection_kind


class FakeCandidateProvider:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    async def query_connections(self, query: str, *, limit: int = 5, score_threshold: float = 0.0):
        self.calls.append({"query": query, "limit": limit, "score_threshold": score_threshold})
        return list(self.rows)


def test_routing_resolver_exact_ref_wins_without_qdrant() -> None:
    provider = FakeCandidateProvider([{"kind": "discord", "ref": "alerts-discord", "score": 0.99}])
    resolver = RoutingResolver(candidate_provider=provider)

    decision = asyncio.run(
        resolver.resolve_connection(
            "Run uptime on pihole1",
            {
                "ssh": {"pihole1": {"title": "Pi-hole DNS"}},
                "discord": {"alerts-discord": {"title": "Alerts"}},
            },
            preferred_kind="ssh",
        )
    )

    assert decision.found is True
    assert decision.kind == "ssh"
    assert decision.ref == "pihole1"
    assert decision.source == "exact_ref"
    assert provider.calls == []


def test_routing_resolver_alias_wins_before_qdrant() -> None:
    provider = FakeCandidateProvider([{"kind": "ssh", "ref": "wrong-host", "score": 0.99}])
    resolver = RoutingResolver(candidate_provider=provider)

    decision = asyncio.run(
        resolver.resolve_connection(
            "Pruefe den DNS blocker",
            {
                "ssh": {
                    "pihole1": {
                        "title": "Pi-hole DNS",
                        "aliases": ["DNS blocker"],
                    }
                }
            },
            preferred_kind="ssh",
        )
    )

    assert decision.found is True
    assert decision.kind == "ssh"
    assert decision.ref == "pihole1"
    assert decision.source == "alias"
    assert provider.calls == []


def test_routing_resolver_uses_qdrant_candidate_after_deterministic_miss() -> None:
    provider = FakeCandidateProvider(
        [
            {
                "kind": "ssh",
                "ref": "pihole1",
                "score": 0.84,
                "source": "qdrant_routing",
                "reason": "DNS blocker and DHCP helper",
            }
        ]
    )
    resolver = RoutingResolver(candidate_provider=provider)

    decision = asyncio.run(
        resolver.resolve_connection(
            "mach einen healthcheck auf dem DNS blocker",
            {"ssh": {"pihole1": {"title": "Pi-hole DNS"}}},
            preferred_kind="ssh",
        )
    )

    assert decision.found is True
    assert decision.kind == "ssh"
    assert decision.ref == "pihole1"
    assert decision.source == "qdrant_routing"
    assert decision.score == 0.84
    assert decision.reason == "DNS blocker and DHCP helper"
    assert provider.calls == [{"query": "mach einen healthcheck auf dem DNS blocker", "limit": 20, "score_threshold": 0.0}]


def test_routing_resolver_rejects_wrong_qdrant_kind_for_preferred_kind() -> None:
    provider = FakeCandidateProvider(
        [
            {"kind": "discord", "ref": "alerts-discord", "score": 0.99},
            {"kind": "ssh", "ref": "unknown-ssh", "score": 0.98},
        ]
    )
    resolver = RoutingResolver(candidate_provider=provider)

    decision = asyncio.run(
        resolver.resolve_connection(
            "mach einen healthcheck auf dem alarm kanal",
            {
                "ssh": {"pihole1": {"title": "Pi-hole DNS"}},
                "discord": {"alerts-discord": {"title": "Alerts"}},
            },
            preferred_kind="ssh",
        )
    )

    assert decision.found is False
    assert decision.kind == ""
    assert decision.ref == ""
    assert len(decision.candidates) == 2


def test_routing_resolver_infers_ssh_kind_before_qdrant_selection() -> None:
    provider = FakeCandidateProvider(
        [
            {"kind": "sftp", "ref": "pihole1", "score": 0.91},
            {"kind": "ssh", "ref": "pihole1", "score": 0.82},
        ]
    )
    resolver = RoutingResolver(candidate_provider=provider)

    decision = asyncio.run(
        resolver.resolve_connection(
            "Zeig mir die Laufzeit vom primären DNS Server",
            {
                "ssh": {"pihole1": {"title": "Pi-hole DNS"}},
                "sftp": {"pihole1": {"title": "Pi-hole files"}},
            },
        )
    )

    assert decision.found is True
    assert decision.kind == "ssh"
    assert decision.ref == "pihole1"
    assert provider.calls == [{"query": "Zeig mir die Laufzeit vom primären DNS Server", "limit": 20, "score_threshold": 0.0}]


def test_infer_preferred_connection_kind_maps_common_actions() -> None:
    available = ("ssh", "sftp", "discord", "rss")

    assert infer_preferred_connection_kind("Zeig mir die Laufzeit vom primären DNS Server", available_kinds=available) == "ssh"
    assert infer_preferred_connection_kind("Wie lange läuft mein DNS Server schon?", available_kinds=available) == "ssh"
    assert infer_preferred_connection_kind("Wie lange ist mein DNS Server schon online?", available_kinds=available) == "ssh"
    assert infer_preferred_connection_kind("Read /etc/hostname on ubnsrv-mgmt-master", available_kinds=available) == "sftp"
    assert infer_preferred_connection_kind("Send a test message to Discord alerts", available_kinds=available) == "discord"
    assert infer_preferred_connection_kind("What's new on heise online news", available_kinds=available) == "rss"


def test_routing_resolver_preserves_configured_ref_casing_from_qdrant() -> None:
    provider = FakeCandidateProvider([{"kind": "ssh", "ref": "pihole1", "score": 0.91}])
    resolver = RoutingResolver(candidate_provider=provider)

    decision = asyncio.run(
        resolver.resolve_connection(
            "linux dns healthcheck",
            {"ssh": {"PiHole1": {"title": "Pi-hole DNS"}}},
            preferred_kind="ssh",
        )
    )

    assert decision.found is True
    assert decision.ref == "PiHole1"
