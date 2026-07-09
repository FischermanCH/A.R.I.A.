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
        "plural_target_scope disabled_by_requested_single_target requested_ref=dev-node-01" in line
        for line in list(decision.resolved.get("detail_lines", []) or [])
    )


def test_ssh_target_scope_policy_expands_requested_group_context() -> None:
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

    assert decision.plural_target_scope is True
    assert list(decision.candidate_connections.keys()) == ["dev-node-01", "dev-node-02"]
    assert any(
        "plural_target_scope enabled_by_requested_ref_context requested_ref=developer server "
        "refs=dev-node-01, dev-node-02" in line
        for line in list(decision.resolved.get("detail_lines", []) or [])
    )


def test_ssh_target_scope_policy_keeps_all_linux_server_scope_on_full_fleet() -> None:
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
        "plural_target_scope kept_full_fleet_by_all_scope kind=ssh reason=no_specific_group_scope" in line
        for line in list(narrowing.resolved.get("detail_lines", []) or [])
    )
