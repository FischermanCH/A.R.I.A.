from __future__ import annotations

import asyncio
import shlex
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


def test_render_command_template_quotes_query_by_default() -> None:
    query = "$(touch /tmp/pwn); cat /etc/passwd | head"

    command = SSHRuntime._render_command_template("printf %s {query}", query)

    assert command == f"printf %s {shlex.quote(query)}"
    assert "$(touch /tmp/pwn)" in command


def test_render_command_template_supports_explicit_quoted_query_placeholder() -> None:
    query = "hello; reboot"

    command = SSHRuntime._render_command_template("grep -F {query:q} /tmp/input", query)

    assert command == f"grep -F {shlex.quote(query)} /tmp/input"


def test_execute_custom_ssh_command_rejects_backtick_query() -> None:
    connection = SimpleNamespace(
        host="127.0.0.1",
        user="aria",
        port=22,
        timeout_seconds=10,
        strict_host_key_checking="accept-new",
        key_path="",
        allow_commands=[],
        guardrail_ref="",
    )
    runtime = _runtime(connection=connection)

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="test",
            skill_name="Test",
            connection_ref="test-ssh",
            command_template="printf %s {query}",
            message="`touch /tmp/pwn`",
        )
    )

    assert result.success is False
    assert result.error == "custom_skill_ssh_command_rejected"


def test_extract_warning_hints_detects_common_update_warnings() -> None:
    hints = SSHRuntime._extract_warning_hints(
        "W: apt-key is deprecated\nThe following packages have been kept back:\n webmin",
        "W: Failed to fetch https://mirror.example/ubuntu",
    )
    assert "apt-key/GPG" in hints
    assert "Fetch" in hints


def test_execute_custom_ssh_command_hides_known_hosts_notice_from_display(monkeypatch) -> None:
    connection = SimpleNamespace(
        host="172.31.10.10",
        user="fischerman",
        port=22,
        timeout_seconds=10,
        strict_host_key_checking="accept-new",
        key_path="",
        allow_commands=[],
        guardrail_ref="",
    )
    runtime = _runtime(connection=connection)

    class _Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return (
                b"08:11:09 up 43 days\n",
                b"Warning: Permanently added '172.31.10.10' (ED25519) to the list of known hosts.\n",
            )

    async def fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="test",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="uptime",
            message="uptime",
        )
    )

    assert result.success is True
    assert "STDOUT:\n08:11:09 up 43 days" in result.content
    assert "Permanently added" not in result.content
    assert "STDERR:" not in result.content


def test_execute_custom_ssh_command_keeps_real_stderr_after_known_hosts_filter(monkeypatch) -> None:
    connection = SimpleNamespace(
        host="172.31.10.10",
        user="fischerman",
        port=22,
        timeout_seconds=10,
        strict_host_key_checking="accept-new",
        key_path="",
        allow_commands=[],
        guardrail_ref="",
    )
    runtime = _runtime(connection=connection)

    class _Proc:
        returncode = 127

        async def communicate(self) -> tuple[bytes, bytes]:
            return (
                b"",
                (
                    b"Warning: Permanently added '172.31.10.10' (ED25519) to the list of known hosts.\n"
                    b"bash: foo: command not found\n"
                ),
            )

    async def fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="test",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="foo",
            message="foo",
        )
    )

    assert result.success is False
    assert result.error == "custom_skill_ssh_nonzero_exit"
    assert "Permanently added" not in result.content
    assert "STDERR:\nbash: foo: command not found" in result.content
