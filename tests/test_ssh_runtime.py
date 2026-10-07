from __future__ import annotations

import asyncio
import shlex
from types import SimpleNamespace

import pytest

from aria.modules.ssh_runtime.runtime import SSHRuntime, resolve_ssh_connection


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


def test_resolve_ssh_connection_prefers_ref_then_unique_title_then_unique_host() -> None:
    profiles = {
        "srv-a": SimpleNamespace(title="Primary App", host="10.0.0.10"),
        "srv-b": SimpleNamespace(title="Backup App", host="10.0.0.11"),
    }

    assert resolve_ssh_connection(profiles, "srv-a")[0] == "srv-a"
    assert resolve_ssh_connection(profiles, "SRV-A")[0] == "srv-a"
    assert resolve_ssh_connection(profiles, " primary app ")[0] == "srv-a"
    assert resolve_ssh_connection(profiles, " 10.0.0.11 ")[0] == "srv-b"


def test_resolve_ssh_connection_never_guesses_ambiguous_title_or_host() -> None:
    profiles = {
        "srv-a": SimpleNamespace(title="Shared", host="10.0.0.10"),
        "srv-b": SimpleNamespace(title="shared", host="10.0.0.10"),
    }

    assert resolve_ssh_connection(profiles, "shared") is None
    assert resolve_ssh_connection(profiles, "10.0.0.10") is None


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
    assert result.error == "recipe_ssh_guardrail_denied:readonly-linux"


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
    assert result.error == "recipe_ssh_guardrail_not_allowed:readonly-linux"


def test_whitelisted_recipe_bypasses_profile_terms(monkeypatch) -> None:
    connection = SimpleNamespace(host="127.0.0.1", user="aria", port=22, timeout_seconds=10,
        strict_host_key_checking="accept-new", key_path="", allow_commands=[], guardrail_ref="maintenance")
    runtime = _runtime(connection=connection, guardrails={"maintenance": {
        "kind": "ssh_command", "allow_terms": ["uptime"], "deny_terms": ["apt upgrade"],
        "allow_recipe_ids": ["trusted-maintenance"],
    }})

    class _Proc:
        returncode = 0
        async def communicate(self): return (b"updated\n", b"")
    async def fake_exec(*_args, **_kwargs): return _Proc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = asyncio.run(runtime.execute_custom_ssh_command(skill_id="trusted-maintenance", skill_name="Trusted",
        connection_ref="test-ssh", command_template="apt upgrade -y", message=""))
    assert result.success is True


def test_non_whitelisted_recipe_and_adhoc_remain_guarded() -> None:
    connection = SimpleNamespace(host="127.0.0.1", user="aria", port=22, timeout_seconds=10,
        strict_host_key_checking="accept-new", key_path="", allow_commands=[], guardrail_ref="maintenance")
    runtime = _runtime(connection=connection, guardrails={"maintenance": {
        "kind": "ssh_command", "allow_terms": ["uptime"], "deny_terms": ["apt upgrade"],
        "allow_recipe_ids": ["trusted-maintenance"],
    }})
    recipe = asyncio.run(runtime.execute_custom_ssh_command(skill_id="other-recipe", skill_name="Other",
        connection_ref="test-ssh", command_template="apt upgrade -y", message=""))
    adhoc = asyncio.run(runtime.execute_custom_ssh_command(skill_id="direct-ssh-command", skill_name="SSH",
        connection_ref="test-ssh", command_template="apt upgrade -y", message="", policy_confirmed=True))
    assert recipe.error == "recipe_ssh_guardrail_denied:maintenance"
    assert adhoc.error != ""


@pytest.mark.parametrize("command", [
    "rm -rf /", "dd if=/dev/zero of=/dev/sda", "mkfs.ext4 /dev/nvme0n1", ":(){ :|:& };:", "shutdown -h now",
])
def test_absolute_floor_blocks_whitelisted_recipe(command: str) -> None:
    connection = SimpleNamespace(host="127.0.0.1", user="aria", port=22, timeout_seconds=10,
        strict_host_key_checking="accept-new", key_path="", allow_commands=[], guardrail_ref="maintenance")
    runtime = _runtime(connection=connection, guardrails={"maintenance": {
        "kind": "ssh_command", "allow_terms": [], "deny_terms": [],
        "allow_recipe_ids": ["trusted-maintenance"],
    }})
    result = asyncio.run(runtime.execute_custom_ssh_command(skill_id="trusted-maintenance", skill_name="Trusted",
        connection_ref="test-ssh", command_template=command, message="", policy_confirmed=True))
    assert result.success is False
    assert result.error == "recipe_ssh_absolute_block"


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
    assert result.error == "recipe_ssh_command_rejected"


def test_execute_custom_ssh_command_blocks_direct_mutating_command_via_policy() -> None:
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
            skill_id="direct-ssh-command",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="systemctl restart nginx",
            message="restart nginx",
        )
    )

    assert result.success is False
    assert result.error == "recipe_ssh_policy_blocked:ssh_command_mutating_operation"


def test_execute_custom_ssh_command_confirmation_does_not_override_hard_block() -> None:
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
            skill_id="direct-ssh-command",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="systemctl restart nginx",
            message="restart nginx",
            policy_confirmed=True,
        )
    )

    assert result.success is False
    assert result.error == "recipe_ssh_policy_blocked:ssh_command_mutating_operation"


def test_execute_custom_ssh_command_requires_confirmation_for_direct_ssh_ask_user_policy() -> None:
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
            skill_id="direct-ssh-command",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="ps aux | grep nginx | grep -v grep",
            message="check nginx",
        )
    )

    assert result.success is False
    assert result.error == "recipe_ssh_policy_confirmation_required:ssh_command_needs_confirmation"


def test_execute_custom_ssh_command_runs_confirmed_direct_ssh_ask_user_policy(monkeypatch) -> None:
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

    class _Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"nginx is running\n", b"")

    async def fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="direct-ssh-command",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="ps aux | grep nginx | grep -v grep",
            message="check nginx",
            policy_confirmed=True,
        )
    )

    assert result.success is True
    assert result.metadata["custom_stdout"].strip() == "nginx is running"


def test_execute_custom_ssh_command_uses_structured_allowlist_matching_for_custom_skills() -> None:
    connection = SimpleNamespace(
        host="127.0.0.1",
        user="aria",
        port=22,
        timeout_seconds=10,
        strict_host_key_checking="accept-new",
        key_path="",
        allow_commands=["df -h"],
        guardrail_ref="",
    )
    runtime = _runtime(connection=connection)

    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="test",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template="echo df -h /",
            message="show disk",
        )
    )

    assert result.success is False
    assert result.error == "recipe_ssh_not_allowed"


def test_execute_custom_ssh_command_allows_direct_guardrail_health_bundle(monkeypatch) -> None:
    allow_commands = [
        "uptime -p",
        "df -h",
        "free -h",
        "systemctl --failed --no-pager",
        "journalctl -p 3 -xb --no-pager -n 40",
    ]
    connection = SimpleNamespace(
        host="192.0.2.14",
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
                "allow_terms": allow_commands,
                "deny_terms": ["rm -rf", "shutdown"],
            }
        },
    )

    class _Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"up 2 days\n", b"")

    async def fake_create_subprocess_exec(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    command = " && ".join(allow_commands)
    result = asyncio.run(
        runtime.execute_custom_ssh_command(
            skill_id="direct-ssh-command",
            skill_name="SSH Command",
            connection_ref="test-ssh",
            command_template=command,
            message="server healthcheck",
        )
    )

    assert result.success is True
    assert result.metadata["custom_command"] == command


def test_extract_warning_hints_detects_common_update_warnings() -> None:
    hints = SSHRuntime._extract_warning_hints(
        "W: apt-key is deprecated\nThe following packages have been kept back:\n webmin",
        "W: Failed to fetch https://mirror.example/ubuntu",
    )
    assert "apt-key/GPG" in hints
    assert "Fetch" in hints


def test_execute_custom_ssh_command_hides_known_hosts_notice_from_display(monkeypatch) -> None:
    connection = SimpleNamespace(
        host="192.0.2.14",
        user="demo_user",
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
                b"Warning: Permanently added '192.0.2.14' (ED25519) to the list of known hosts.\n",
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
    assert result.metadata["custom_command"] == "uptime"
    assert "43 days" in result.metadata["custom_stdout"]


def test_execute_custom_ssh_command_keeps_real_stderr_after_known_hosts_filter(monkeypatch) -> None:
    connection = SimpleNamespace(
        host="192.0.2.14",
        user="demo_user",
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
                    b"Warning: Permanently added '192.0.2.14' (ED25519) to the list of known hosts.\n"
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
    assert result.error == "recipe_ssh_nonzero_exit"
    assert "Permanently added" not in result.content
    assert "STDERR:\nbash: foo: command not found" in result.content
    assert result.metadata["custom_command"] == "foo"
    assert "bash: foo: command not found" in result.metadata["custom_stderr"]
