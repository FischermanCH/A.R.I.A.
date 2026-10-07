from aria.modules.connection_routing.resolver import validate_qdrant_connection_candidate


def test_qdrant_candidate_validation_is_contract_only() -> None:
    pools = {
        "ssh": {"DnsNode01": {"title": "Primary DNS"}},
        "discord": {"alerts": {"title": "Alerts"}},
    }

    assert validate_qdrant_connection_candidate(
        {"kind": "ssh", "ref": "dnsnode01"}, pools, preferred_kind="ssh"
    ) == ("ssh", "DnsNode01")
    assert validate_qdrant_connection_candidate(
        {"kind": "discord", "ref": "alerts"}, pools, preferred_kind="ssh"
    ) is None
    assert validate_qdrant_connection_candidate(
        {"kind": "ssh", "ref": "unknown"}, pools, preferred_kind="ssh"
    ) is None
