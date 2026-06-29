from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.action_plan import CapabilityDraft
from aria.core.action_plan import MemoryHints
from aria.core.connection_ref_scope import ConnectionRefScope
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.connection_semantic_resolver import SemanticConnectionHint
from aria.core.routed_action_resolver import RoutedActionResolver
from aria.core.routed_action_resolver import RoutedActionBuildCallbacks
from aria.core.routed_action_resolver import RoutedActionResolverCallbacks
from aria.core.routed_action_resolver import RoutedActionResolverInitialChain
from aria.core.routed_action_resolver import RoutedActionResolverRequest
from aria.core.routed_action_resolver import RoutedActionGuardCallbacks
from aria.core.routed_action_resolver import RoutedActionSemanticCallbacks
from aria.core.routed_action_resolver import RoutedActionSshCallbacks


async def _noop_refresh(resolved, **kwargs):
    return resolved, kwargs.get("capability_draft")


async def _default_resolve_live_routing_chain(_message: str, **_kwargs):
    return {"decision": {}, "detail_lines": []}


def _callbacks(
    *,
    resolve_unified,
    connection_pools: dict[str, dict[str, object]],
    default_llm_client: object | None = None,
    resolve_live_routing_chain=_default_resolve_live_routing_chain,
) -> RoutedActionResolverCallbacks:
    return RoutedActionResolverCallbacks(
        resolve_unified=resolve_unified,
        connection_pools=lambda: connection_pools,
        default_llm_client=lambda: default_llm_client,
        resolve_live_routing_chain=resolve_live_routing_chain,
        append_debug_detail_lines=lambda resolved, *lines: {
            **resolved,
            "detail_lines": [*list(resolved.get("detail_lines", []) or []), *lines],
        },
        chain_complete=lambda resolved: bool(resolved.get("complete")),
        chain_has_signal=lambda resolved: bool(resolved and resolved.get("signal")),
        append_chain_routing_record=lambda resolved: {**resolved, "chain_record": True},
        refresh_ssh_command=_noop_refresh,
        refresh_file_operation=_noop_refresh,
        refresh_message_operation=_noop_refresh,
        refresh_read_operation=_noop_refresh,
        apply_requested_guard=lambda resolved, **_kwargs: {**resolved, "guarded": True},
    )


def _resolver(
    *,
    connection_pools: dict[str, dict[str, object]],
    default_llm_client: object | None = None,
    resolve_live_routing_chain=_default_resolve_live_routing_chain,
) -> RoutedActionResolver:
    async def resolve_unified(_message: str, **_kwargs):
        return None

    return RoutedActionResolver(
        callbacks=_callbacks(
            resolve_unified=resolve_unified,
            connection_pools=connection_pools,
            default_llm_client=default_llm_client,
            resolve_live_routing_chain=resolve_live_routing_chain,
        )
    )


def test_routed_action_resolver_delegates_request_to_unified_callback() -> None:
    calls: list[dict[str, object]] = []
    llm_client = object()

    async def resolve_unified(message: str, **kwargs):
        calls.append({"message": message, **kwargs})
        return {"status": "ok", "query": message}

    resolver = RoutedActionResolver(
        callbacks=_callbacks(
            resolve_unified=resolve_unified,
            connection_pools={},
            default_llm_client=llm_client,
        )
    )

    result = asyncio.run(
        resolver.resolve(
            RoutedActionResolverRequest(
                message="wie fit sind meine server?",
                user_id="u1",
                language="de",
                capability_draft={"capability": "ssh_command"},
                llm_client=None,
            )
        )
    )

    assert result == {"status": "ok", "query": "wie fit sind meine server?"}
    assert calls == [
        {
            "message": "wie fit sind meine server?",
            "user_id": "u1",
            "language": "de",
            "capability_draft": {"capability": "ssh_command"},
            "llm_client": None,
        }
    ]


def test_routed_action_resolver_prepares_rss_without_llm_and_creates_empty_draft() -> None:
    llm_client = object()
    resolver = _resolver(
        connection_pools={"rss": {"heise-security-alerts": {"title": "Heise Security"}}},
        default_llm_client=llm_client,
    )

    prelude = resolver.prepare_request(
        RoutedActionResolverRequest(
            message="lies den feed heise-security-alerts",
            user_id="u1",
            capability_draft=SimpleNamespace(connection_kind="rss"),
        )
    )

    assert prelude.effective_kind == "rss"
    assert prelude.candidate_connections == {"heise-security-alerts": {"title": "Heise Security"}}
    assert prelude.effective_llm_client is None
    assert prelude.semantic_llm_client is None
    assert prelude.ref_scope.has_any is False

    empty_draft_prelude = resolver.prepare_request(
        RoutedActionResolverRequest(
            message="was habe ich fuer news feed fuer it security?",
            user_id="u1",
        )
    )
    assert isinstance(empty_draft_prelude.working_draft, CapabilityDraft)
    assert empty_draft_prelude.working_draft.connection_kind == "rss"


def test_routed_action_resolver_prepares_semantic_llm_for_non_rss_multi_candidate() -> None:
    llm_client = object()
    resolver = _resolver(
        connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}},
        default_llm_client=llm_client,
    )

    prelude = resolver.prepare_request(
        RoutedActionResolverRequest(
            message="wie fit sind meine server?",
            user_id="u1",
            capability_draft=SimpleNamespace(
                connection_kind="ssh",
                explicit_connection_ref="",
                requested_connection_ref="",
            ),
        )
    )

    assert prelude.effective_kind == "ssh"
    assert prelude.effective_llm_client is llm_client
    assert prelude.semantic_llm_client is llm_client
    assert prelude.ref_scope.has_explicit is False


def test_routed_action_resolver_skips_semantic_llm_for_explicit_ref() -> None:
    llm_client = object()
    resolver = _resolver(
        connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}},
        default_llm_client=llm_client,
    )

    prelude = resolver.prepare_request(
        RoutedActionResolverRequest(
            message="check srv-a",
            user_id="u1",
            capability_draft=SimpleNamespace(
                connection_kind="ssh",
                explicit_connection_ref="srv-a",
                requested_connection_ref="",
            ),
        )
    )

    assert prelude.effective_llm_client is llm_client
    assert prelude.ref_scope.explicit_ref == "srv-a"
    assert prelude.semantic_llm_client is None


def test_routed_action_resolver_initial_chain_uses_no_llm_fallback_with_signal() -> None:
    llm_client = object()
    calls: list[object | None] = []

    async def resolve_live_routing_chain(_message: str, **kwargs):
        calls.append(kwargs.get("llm_client"))
        if kwargs.get("llm_client") is None:
            return {"decision": {"kind": "ssh"}, "signal": True, "complete": True, "detail_lines": []}
        return {"decision": {}, "complete": False, "detail_lines": []}

    resolver = _resolver(
        connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}},
        default_llm_client=llm_client,
        resolve_live_routing_chain=resolve_live_routing_chain,
    )
    request = RoutedActionResolverRequest(
        message="wie fit sind meine server?",
        user_id="u1",
        capability_draft=SimpleNamespace(connection_kind="ssh"),
    )
    prelude = resolver.prepare_request(request)

    chain = asyncio.run(resolver.resolve_initial_chain(request, prelude))

    assert calls == [llm_client, None]
    assert chain.resolved["decision"] == {"kind": "ssh"}
    assert chain.resolved["chain_record"] is True
    assert chain.chain_complete is True


def test_routed_action_resolver_candidate_pool_outcome_guards_complete_chain_without_pool() -> None:
    resolver = _resolver(connection_pools={})
    request = RoutedActionResolverRequest(message="status", user_id="u1")
    prelude = resolver.prepare_request(request)
    chain = RoutedActionResolverInitialChain(
        resolved={"complete": True},
        working_draft=prelude.working_draft,
        chain_complete=True,
    )

    outcome = resolver.resolve_candidate_pool_outcome(
        prelude=prelude,
        initial_chain=chain,
        language="de",
    )

    assert outcome.handled is True
    assert outcome.resolved == {"complete": True, "guarded": True}


def test_routed_action_resolver_candidate_pool_outcome_returns_none_for_incomplete_empty_pool() -> None:
    resolver = _resolver(connection_pools={})
    request = RoutedActionResolverRequest(message="status", user_id="u1")
    prelude = resolver.prepare_request(request)
    chain = RoutedActionResolverInitialChain(
        resolved={"complete": False},
        working_draft=prelude.working_draft,
        chain_complete=False,
    )

    outcome = resolver.resolve_candidate_pool_outcome(
        prelude=prelude,
        initial_chain=chain,
        language="de",
    )

    assert outcome.handled is True
    assert outcome.resolved is None


def test_routed_action_resolver_strong_semantic_candidate_overrides_stale_memory_hint() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}})
    resolved = {"detail_lines": []}

    update = resolver.resolve_strong_semantic_candidate_override(
        resolved=resolved,
        hints=MemoryHints(connection_kind="ssh", connection_ref="srv-a", source="memory_hint"),
        semantic_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="srv-b",
                source="semantic_alias",
                note="explicit target",
                score=1000,
            )
        ],
        ref_scope=ConnectionRefScope(),
        plural_target_scope=False,
        effective_kind="ssh",
    )

    assert update.hints.connection_ref == "srv-b"
    assert update.hints.source == "explicit_ref"
    assert update.semantic_record is not None
    assert update.semantic_record.stage == "explicit_connection_resolution"
    assert update.resolved["detail_lines"] == [
        "Routing Debug: memory_hint ignored_by_explicit_target ref=srv-a explicit_ref=srv-b",
        "Routing Debug: explicit_ref selected ref=srv-b",
    ]


def test_routed_action_resolver_semantic_candidate_respects_requested_ref_guard() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}})
    semantic_resolver = SimpleNamespace(
        resolve_connection=lambda *_args, **_kwargs: SemanticConnectionHint(
            connection_kind="ssh",
            connection_ref="srv-b",
            source="semantic_alias",
            note="backup maybe",
        )
    )

    update = resolver.resolve_semantic_candidate_hint(
        "check backup server",
        semantic_resolver=semantic_resolver,
        requested_connection_ref_matches_candidate=lambda *_args, **_kwargs: False,
        resolved={"detail_lines": []},
        hints=MemoryHints(connection_kind="ssh", connection_ref="", source=""),
        effective_kind="ssh",
        candidate_connections={"srv-a": {}, "srv-b": {}},
        semantic_candidates=[SemanticConnectionCandidate(connection_kind="ssh", connection_ref="srv-b")],
        ref_scope=ConnectionRefScope(requested_ref="backup server"),
    )

    assert update.hints.connection_ref == ""
    assert update.semantic_record is None
    assert update.resolved["detail_lines"] == [
        "Routing Debug: semantic_hint blocked requested_ref=backup server ref=srv-b"
    ]


def test_routed_action_resolver_revalidates_ssh_memory_hint_with_semantic_llm() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}})
    calls: list[dict[str, object]] = []

    async def resolve_connection_with_llm(*_args, **kwargs):
        calls.append(kwargs)
        return SemanticConnectionHint(
            connection_kind="ssh",
            connection_ref="srv-b",
            source="semantic_llm",
            note="semantic_llm:target",
        )

    semantic_resolver = SimpleNamespace(resolve_connection_with_llm=resolve_connection_with_llm)

    update = asyncio.run(
        resolver.revalidate_ssh_memory_hint_with_semantic_llm(
            "check srv-b",
            semantic_resolver=semantic_resolver,
            resolved={"detail_lines": []},
            hints=MemoryHints(connection_kind="ssh", connection_ref="srv-a", source="memory_hint"),
            effective_kind="ssh",
            candidate_connections={"srv-a": {}, "srv-b": {}},
            semantic_candidates=[SemanticConnectionCandidate(connection_kind="ssh", connection_ref="srv-b")],
        )
    )

    assert calls == [{"preferred_kind": "ssh", "force_llm": True, "include_all_profiles": True}]
    assert update.hints.connection_ref == "srv-b"
    assert update.hints.source == "semantic_llm"
    assert update.semantic_record is not None
    assert update.semantic_record.stage == "semantic_llm_resolution"
    assert update.resolved["detail_lines"] == [
        "Routing Debug: memory_hint ignored_by_semantic_llm ref=srv-a selected=srv-b"
    ]


def test_routed_action_resolver_blocks_requested_ref_memory_hint_mismatch() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}})

    update = resolver.block_requested_ref_memory_hint_mismatch(
        requested_connection_ref_matches_candidate=lambda *_args, **_kwargs: False,
        resolved={"detail_lines": []},
        working_draft=SimpleNamespace(requested_connection_ref="backup server"),
        hints=MemoryHints(connection_kind="ssh", connection_ref="srv-a", source="memory_hint"),
        effective_kind="ssh",
        candidate_connections={"srv-a": {}, "srv-b": {}},
    )

    assert update.forced_ref == ""
    assert update.resolved["detail_lines"] == [
        "Routing Debug: memory_hint blocked requested_ref=backup server ref=srv-a"
    ]


def test_routed_action_resolver_binds_requested_ref_from_semantic_candidate() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}})
    semantic_resolver = SimpleNamespace(
        resolve_connection=lambda *_args, **_kwargs: SemanticConnectionHint(
            connection_kind="ssh",
            connection_ref="srv-b",
            source="semantic_alias",
            note="backup server",
        )
    )

    update = resolver.bind_requested_ref_from_semantic_candidate(
        "check backup server",
        semantic_resolver=semantic_resolver,
        requested_connection_ref_matches_candidate=lambda *_args, **_kwargs: True,
        resolved={"detail_lines": []},
        working_draft=CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            requested_connection_ref="backup server",
        ),
        hints=MemoryHints(connection_kind="ssh", connection_ref="", source=""),
        effective_kind="ssh",
        candidate_connections={"srv-a": {}, "srv-b": {}},
        semantic_candidates=[SemanticConnectionCandidate(connection_kind="ssh", connection_ref="srv-b")],
    )

    assert update.forced_ref == "srv-b"
    assert update.working_draft.explicit_connection_ref == "srv-b"
    assert update.working_draft.requested_connection_ref == ""
    assert update.semantic_record is not None
    assert update.semantic_record.stage == "semantic_candidate_resolution"
    assert update.resolved["detail_lines"][-2:] == [
        "Routing Debug: explicit_ref selected ref=srv-b",
        "Routing: explicit_connection_resolution selected `ssh/srv-b` source=explicit_ref note=srv-b",
    ]


def test_routed_action_resolver_refines_rss_forced_ref() -> None:
    resolver = _resolver(connection_pools={"rss": {"security-feed": {}, "ops-feed": {}}})

    async def resolve_rss_ref(*_args, **_kwargs):
        return SemanticConnectionHint(
            connection_kind="rss",
            connection_ref="security-feed",
            source="semantic_alias",
            note="security",
        )

    semantic_resolver = SimpleNamespace(resolve_rss_ref=resolve_rss_ref)

    update = asyncio.run(
        resolver.refine_rss_forced_ref(
            "lies security news",
            semantic_resolver=semantic_resolver,
            resolved={"detail_lines": []},
            working_draft=CapabilityDraft(capability="rss_read_feed", connection_kind="rss"),
            hints=MemoryHints(connection_kind="rss", connection_ref="", source=""),
            effective_kind="rss",
            candidate_connections={"security-feed": {}, "ops-feed": {}},
            semantic_candidates=[SemanticConnectionCandidate(connection_kind="rss", connection_ref="security-feed")],
        )
    )

    assert update.forced_ref == "security-feed"
    assert update.hints.connection_ref == "security-feed"
    assert update.semantic_record is not None
    assert update.semantic_record.stage == "rss_semantic_refine"


def test_routed_action_resolver_kind_only_path_uses_callback_bundles() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-a": {}, "srv-b": {}}})
    calls: list[str] = []

    async def build_kind_only(_message: str, **kwargs):
        calls.append("kind_only")
        return {
            "query": _message,
            "decision": {"found": True, "kind": kwargs.get("connection_kind", ""), "ref": ""},
            "detail_lines": ["kind-only-built"],
        }

    async def build_forced(_message: str, **_kwargs):
        calls.append("forced")
        return {"detail_lines": ["forced-built"]}

    def append_record(resolved, record):
        calls.append(f"record:{record.stage}")
        return {**resolved, "record_stage": record.stage}

    def attach_candidates(resolved, candidates):
        calls.append(f"candidates:{len(candidates)}")
        return {**resolved, "candidate_count": len(candidates)}

    def narrow_plural(resolved, **kwargs):
        calls.append("narrow")
        return resolved, kwargs["candidate_connections"], []

    async def prepare_plural(resolved, **kwargs):
        calls.append("prepare")
        return resolved, kwargs.get("capability_draft")

    def apply_plural(resolved, **_kwargs):
        calls.append("apply")
        return {**resolved, "multi_target_applied": True}

    def guard(resolved, **_kwargs):
        calls.append("guard")
        return {**resolved, "guarded": True}

    result = asyncio.run(
        resolver.resolve_kind_only_or_plural_context(
            "wie fit sind meine server?",
            user_id="u1",
            language="de",
            effective_kind="ssh",
            working_draft=CapabilityDraft(capability="ssh_command", connection_kind="ssh"),
            hints=MemoryHints(connection_kind="ssh", connection_ref="", matched_text="ssh"),
            resolved={"detail_lines": ["previous"]},
            plural_target_scope=True,
            candidate_connections={"srv-a": {}, "srv-b": {}},
            planner_connection_candidates=[],
            build_callbacks=RoutedActionBuildCallbacks(
                build_kind_only_resolution=build_kind_only,
                build_forced_resolution=build_forced,
                resolved_detail_lines=lambda resolved: list(resolved.get("detail_lines", []) or []),
                append_routing_record=append_record,
                attach_candidates_debug=attach_candidates,
            ),
            ssh_callbacks=RoutedActionSshCallbacks(
                narrow_plural_targets=narrow_plural,
                prepare_plural_command=prepare_plural,
                apply_plural_resolution=apply_plural,
            ),
            guard_callbacks=RoutedActionGuardCallbacks(apply_requested_guard=guard),
        )
    )

    assert result["guarded"] is True
    assert result["multi_target_applied"] is True
    assert result["record_stage"] == "kind_only_resolution"
    assert calls == ["kind_only", "record:kind_only_resolution", "candidates:0", "narrow", "prepare", "apply", "guard"]


def test_routed_action_resolver_forced_path_uses_semantic_and_guard_bundles() -> None:
    resolver = _resolver(connection_pools={"ssh": {"srv-b": {}}})
    calls: list[str] = []

    def requested_ref_matches(requested_ref: str, **kwargs) -> bool:
        calls.append(f"match:{requested_ref}:{kwargs.get('connection_ref')}")
        return True

    def append_record(resolved, record):
        calls.append(f"record:{record.stage}")
        return resolved

    async def finalize(_message: str, **kwargs):
        calls.append(f"finalize:{kwargs.get('forced_ref')}")
        return {"forced_ref": kwargs.get("forced_ref"), "semantic_stage": kwargs["semantic_record"].stage}

    semantic_resolver = SimpleNamespace(
        resolve_connection=lambda *_args, **_kwargs: SemanticConnectionHint(
            connection_kind="ssh",
            connection_ref="srv-b",
            source="semantic_alias",
            note="backup server",
        ),
        resolve_rss_ref=None,
    )

    result = asyncio.run(
        resolver.resolve_forced_or_kind_only_routed_action(
            "check backup server",
            user_id="u1",
            language="de",
            effective_kind="ssh",
            effective_llm_client=None,
            working_draft=CapabilityDraft(
                capability="ssh_command",
                connection_kind="ssh",
                requested_connection_ref="backup server",
            ),
            hints=MemoryHints(connection_kind="ssh", connection_ref="", source=""),
            resolved={"detail_lines": []},
            plural_target_scope=False,
            candidate_connections={"srv-b": {}},
            semantic_candidates=[SemanticConnectionCandidate(connection_kind="ssh", connection_ref="srv-b")],
            semantic_record=None,
            planner_connection_candidates=[],
            semantic_callbacks=RoutedActionSemanticCallbacks(
                semantic_resolver=semantic_resolver,
                requested_ref_matches_candidate=requested_ref_matches,
            ),
            build_callbacks=RoutedActionBuildCallbacks(
                build_kind_only_resolution=lambda *_args, **_kwargs: None,
                build_forced_resolution=lambda *_args, **_kwargs: None,
                resolved_detail_lines=lambda resolved: list(resolved.get("detail_lines", []) or []),
                append_routing_record=append_record,
                attach_candidates_debug=lambda resolved, _candidates: resolved,
            ),
            ssh_callbacks=RoutedActionSshCallbacks(
                narrow_plural_targets=lambda resolved, **kwargs: (resolved, kwargs["candidate_connections"], []),
                prepare_plural_command=lambda resolved, **kwargs: None,
                apply_plural_resolution=lambda resolved, **_kwargs: resolved,
            ),
            guard_callbacks=RoutedActionGuardCallbacks(
                apply_requested_guard=lambda resolved, **_kwargs: resolved,
                finalize_forced_resolution=finalize,
            ),
        )
    )

    assert result == {"forced_ref": "srv-b", "semantic_stage": "semantic_candidate_resolution"}
    assert calls == ["match:backup server:srv-b", "finalize:srv-b"]
