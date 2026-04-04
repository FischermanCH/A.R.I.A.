from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.ssh_runtime import SSHRuntime


class _Interpreter:
    def interpret(self, **_: object) -> None:
        return None


def _runtime(*, connection: object, guardrails: dict[str, object] | None = None) -> SSHRuntime:
    settings = SimpleNamespace(
        connections=SimpleNamespace(ssh={"test-ssh": connection}),
        security=SimpleNamespace(guardrails=guardrails or {}),
    )
    return SSHRuntime(
        settings=settings,
        error_interpreter=_Interpreter(),
        normalize_spaces=lambda text: " ".join(str(text or "").split()),
        truncate_text=lambda text, limit=4000: str(text or "")[:limit],
        extract_held_packages=lambda text: [],
    )


def test_execute_custom_ssh_command_blocks_on_guardrail_deny_phrase() -> None:
    connection = SimpleNamespace(
        host="127.0.0.1",
        user="aria",
        port=22,
        timeout_seconds=10,
        strict_host_key_checking="accept-new",
        key_path="",
        allow_commands=[],
        guardrail_ref="readonly-linux",
    )
    runtime = _runtime(
        connection=connection,
        guardrails={
            "readonly-linux": {
                "kind": "ssh_command",
                "allow_terms": ["uptime", "df -h"],
                "deny_terms": ["rm -rf", "shutdown"],
            }
        },
    )

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="test",
            skill_name="Test",
            connection_ref="test-ssh",
            command_template="rm -rf /tmp/demo",
            message="lösche das mal",
        )
    )

    assert result.success is False
    assert result.error == "custom_skill_ssh_guardrail_denied:readonly-linux"


def test_execute_custom_ssh_command_blocks_when_guardrail_allowlist_does_not_match() -> None:
    connection = SimpleNamespace(
        host="127.0.0.1",
        user="aria",
        port=22,
        timeout_seconds=10,
        strict_host_key_checking="accept-new",
        key_path="",
        allow_commands=[],
        guardrail_ref="readonly-linux",
    )
    runtime = _runtime(
        connection=connection,
        guardrails={
            "readonly-linux": SimpleNamespace(
                kind="ssh_command",
                allow_terms=["uptime", "df -h"],
                deny_terms=[],
            )
        },
    )

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="test",
            skill_name="Test",
            connection_ref="test-ssh",
            command_template="cat /etc/hosts",
            message="zeig hosts",
        )
    )

    assert result.success is False
    assert result.error == "custom_skill_ssh_guardrail_not_allowed:readonly-linux"


def test_extract_warning_hints_detects_common_update_warnings() -> None:
    hints = SSHRuntime._extract_warning_hints(
        "W: apt-key is deprecated\nThe following packages have been kept back:\n webmin",
        "W: Failed to fetch https://mirror.example/ubuntu",
    )
    assert "apt-key/GPG" in hints
    assert "Fetch" in hints
