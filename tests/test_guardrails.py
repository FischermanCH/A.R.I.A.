from __future__ import annotations

from types import SimpleNamespace

from aria.core.guardrails import (
    evaluate_guardrail,
    guardrail_is_compatible,
    resolve_guardrail_profile,
)


def test_guardrail_compatibility_matches_connection_kind() -> None:
    assert guardrail_is_compatible("ssh_command", "ssh") is True
    assert guardrail_is_compatible("http_request", "ssh") is False


def test_resolve_guardrail_profile_reads_generic_security_profiles() -> None:
    settings = SimpleNamespace(
        security=SimpleNamespace(
            guardrails={
                "readonly-linux": {
                    "kind": "ssh_command",
                    "title": "Read-only Linux",
                    "description": "Only safe read commands.",
                    "allow_terms": ["uptime", "df -h"],
                    "deny_terms": ["rm -rf"],
                }
            }
        )
    )

    profile = resolve_guardrail_profile(settings, "readonly-linux")

    assert profile is not None
    assert profile["kind"] == "ssh_command"
    assert profile["allow_terms"] == ["uptime", "df -h"]
    assert profile["deny_terms"] == ["rm -rf"]


def test_evaluate_guardrail_blocks_deny_term() -> None:
    decision = evaluate_guardrail(
        profile_ref="readonly-linux",
        profile={
            "kind": "ssh_command",
            "allow_terms": ["uptime", "df -h"],
            "deny_terms": ["rm -rf"],
        },
        kind="ssh_command",
        text="rm -rf /tmp/demo",
    )

    assert decision.allowed is False
    assert decision.reason == "guardrail_denied"


def test_evaluate_guardrail_blocks_allowlist_miss() -> None:
    decision = evaluate_guardrail(
        profile_ref="readonly-linux",
        profile={
            "kind": "ssh_command",
            "allow_terms": ["uptime", "df -h"],
            "deny_terms": [],
        },
        kind="ssh_command",
        text="cat /etc/hosts",
    )

    assert decision.allowed is False
    assert decision.reason == "guardrail_not_allowed"


def test_evaluate_guardrail_blocks_kind_mismatch() -> None:
    decision = evaluate_guardrail(
        profile_ref="readonly-linux",
        profile={
            "kind": "http_request",
            "allow_terms": [],
            "deny_terms": [],
        },
        kind="ssh_command",
        text="uptime",
    )

    assert decision.allowed is False
    assert decision.reason == "guardrail_kind_mismatch:http_request"
