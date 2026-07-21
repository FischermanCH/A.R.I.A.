from __future__ import annotations

from aria.core.action_plan import CapabilityDraft
from aria.core.connection_ref_scope import ConnectionRefScope
from aria.core.connection_semantic_resolver import ConnectionSemanticResolver
from aria.core.ssh_target_scope_policy import SshTargetScopePolicy


def _policy() -> SshTargetScopePolicy:
    return SshTargetScopePolicy(
        resolver=ConnectionSemanticResolver(None),
        routing_debug_enabled=lambda: True,
    )


def test_ssh_target_scope_policy_keeps_requested_single_target_single() -> None:
    candidate_connections = {
        "dev-node-01": {
            "host": "192.0.2.11",
            "user": "root",
            "title": "Development Server 1",
            "aliases": ["dev server", "development"],
        },
        "dev-node-02": {
            "host": "192.0.2.12",
            "user": "root",
            "title": "Development Server 2",
            "aliases": ["dev server", "development"],
        },
    }

    decision = _policy().resolve_requested_connection_scope(
        resolved={"detail_lines": []},
        message="pruefe nur meinen dev-node-01",
        effective_kind="ssh",
        looks_like_plural_target=lambda *_args, **_kwargs: True,
        candidate_connections=candidate_connections,
        working_draft=CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            requested_connection_ref="dev-node-01",
            notes=["target_scope:multi_target"],
        ),
        ref_scope=ConnectionRefScope(explicit_ref="", requested_ref="dev-node-01"),
    )

    assert decision.plural_target_scope is False
    assert decision.candidate_connections == candidate_connections
    assert any(
        "plural_target_scope disabled_by_existing_requested_target requested_ref=dev-node-01" in line
        for line in list(decision.resolved.get("detail_lines", []) or [])
    )


def test_ssh_target_scope_policy_uses_live_capability_detail_explicit_ref() -> None:
    candidate_connections = {
        "ops-alert-01": {"host": "192.0.2.10", "user": "root", "title": "Monitoring server"},
        "dev-node-02": {"host": "192.0.2.11", "user": "root", "title": "Development server"},
    }

    decision = _policy().resolve_requested_connection_scope(
        resolved={
            "detail_lines": [
                "Routing Debug: capability_draft capability=ssh_command kind=ssh explicit_ref=ops-alert-01 "
                "requested_ref=- path=- content=uptime boundary=context_enrichment"
            ]
        },
        message="zeige mir den status vom monitoring server",
        effective_kind="ssh",
        looks_like_plural_target=lambda *_args, **_kwargs: True,
        candidate_connections=candidate_connections,
        working_draft=CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            notes=["target_scope:multi_target"],
        ),
        ref_scope=ConnectionRefScope(explicit_ref="", requested_ref=""),
    )

    assert decision.plural_target_scope is False
    assert any(
        "plural_target_scope disabled_by_explicit_single_target explicit_ref=ops-alert-01" in line
        for line in list(decision.resolved.get("detail_lines", []) or [])
    )
    assert not any(
        "plural_target_scope blocks_single_target_resolution" in line
        for line in list(decision.resolved.get("detail_lines", []) or [])
    )


def test_ssh_target_scope_policy_does_not_expand_requested_group_context_without_contract_scope() -> None:
    candidate_connections = {
        "dev-node-01": {
            "host": "192.0.2.11",
            "user": "root",
            "title": "Development Server 1",
            "aliases": ["dev server", "development", "code-server"],
        },
        "dev-node-02": {
            "host": "192.0.2.12",
            "user": "root",
            "title": "Development Server 2",
            "aliases": ["developer server", "development", "code-server"],
        },
        "ai-ui-01": {
            "host": "192.0.2.24",
            "user": "root",
            "title": "Open WebUI",
            "aliases": ["ai", "llm", "web-interface"],
        },
    }

    decision = _policy().resolve_requested_connection_scope(
        resolved={"detail_lines": []},
        message="haben meine developer server noch genug festplattenspeicher",
        effective_kind="ssh",
        looks_like_plural_target=lambda *_args, **_kwargs: False,
        candidate_connections=candidate_connections,
        working_draft=CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            requested_connection_ref="developer server",
            content="df -h",
        ),
        ref_scope=ConnectionRefScope(explicit_ref="", requested_ref="developer server"),
    )

    assert decision.plural_target_scope is False
    assert decision.candidate_connections == candidate_connections
    assert not any("enabled_by_requested_ref_context" in line for line in list(decision.resolved.get("detail_lines", []) or []))


def test_ssh_target_scope_policy_context_narrowing_is_candidate_only() -> None:
    candidate_connections = {
        "deb-node-01": {
            "host": "192.0.2.11",
            "user": "root",
            "title": "Debian Node",
            "aliases": ["debian", "linux server"],
        },
        "rp-node-01": {
            "host": "192.0.2.12",
            "user": "root",
            "title": "Raspberry Pi Node",
            "aliases": ["raspberry pi", "linux server"],
        },
        "ubn-mgmt-01": {
            "host": "192.0.2.21",
            "user": "root",
            "title": "Ubuntu Management",
            "aliases": ["ubuntu", "linux server", "management"],
        },
        "ubn-gaming-01": {
            "host": "192.0.2.22",
            "user": "root",
            "title": "Ubuntu Gaming",
            "aliases": ["ubuntu", "linux server", "gaming"],
        },
    }

    narrowing = _policy().narrow_plural_target_connections_by_context(
        {"detail_lines": []},
        message="pruefe bitte den festplattenplatz auf allen linux servern",
        candidate_connections=candidate_connections,
    )

    assert list(narrowing.candidate_connections.keys()) == list(candidate_connections.keys())
    assert any(
        "legacy_semantic_heuristic component=ssh_target_scope_policy "
        "decision=narrow_plural_target_connections_by_context effect=candidate_only" in line
        for line in list(narrowing.resolved.get("detail_lines", []) or [])
    )


def test_ssh_target_scope_policy_full_kind_authority_expands_to_all_candidates() -> None:
    candidate_connections = {
        "srv-a": {"host": "192.0.2.10", "user": "root"},
        "srv-b": {"host": "192.0.2.11", "user": "root"},
        "srv-c": {"host": "192.0.2.12", "user": "root"},
    }
    draft = CapabilityDraft(
        capability="ssh_command",
        connection_kind="ssh",
        content="uptime",
        notes=[
            "capability_draft_source:llm",
            "target_scope:multi_target",
            "target_scope_authority:full_kind",
            "turn_contract_target_refs:full_kind",
        ],
    )

    resolved = _policy().apply_plural_multi_target_resolution(
        {"query": "zeige mir den status meiner server", "detail_lines": []},
        candidate_connections=candidate_connections,
        capability_draft=draft,
        language="de",
        adapt_command=lambda refs, command, _query, _draft: (command, "noop"),
        evaluate_safety=lambda **_kwargs: {"decision": {}},
        build_execution_preview=lambda **_kwargs: {"decision": {}},
    )

    payload = resolved["payload_debug"]["payload"]
    assert payload["connection_refs"] == ["srv-a", "srv-b", "srv-c"]
    assert any(
        "plural_target_scope selected_multi_target kind=ssh refs=srv-a, srv-b, srv-c command=uptime" in line
        for line in list(resolved.get("detail_lines", []) or [])
    )


def test_ssh_target_scope_policy_priority_sample_without_refs_does_not_expand() -> None:
    candidate_connections = {
        "srv-a": {"host": "192.0.2.10", "user": "root"},
        "srv-b": {"host": "192.0.2.11", "user": "root"},
        "srv-c": {"host": "192.0.2.12", "user": "root"},
    }
    draft = CapabilityDraft(
        capability="ssh_command",
        connection_kind="ssh",
        content="uptime",
        notes=[
            "capability_draft_source:meta_catalog",
            "target_scope:multi_target",
            "target_scope_authority:priority_sample",
            "turn_contract_priority_refs_ignored:srv-a,srv-b",
        ],
    )

    resolved = _policy().apply_plural_multi_target_resolution(
        {"query": "zeige mir den status meiner server", "detail_lines": []},
        candidate_connections=candidate_connections,
        capability_draft=draft,
        language="de",
        adapt_command=lambda refs, command, _query, _draft: (command, "noop"),
        evaluate_safety=lambda **_kwargs: {"decision": {}},
        build_execution_preview=lambda **_kwargs: {"decision": {}},
    )

    assert "payload_debug" not in resolved
    assert any(
        "plural_target_scope skipped_missing_contract_target_refs "
        "source=meta_catalog authority=priority_sample" in line
        for line in list(resolved.get("detail_lines", []) or [])
    )
