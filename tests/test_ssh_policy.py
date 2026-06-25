from __future__ import annotations

from aria.core.ssh_policy import command_matches_allow_commands, validate_ssh_readonly_policy


def test_validate_ssh_readonly_policy_allows_simple_readonly_command() -> None:
    decision = validate_ssh_readonly_policy("df -h /")

    assert decision.action == "allow"
    assert decision.reason == "ssh_readonly_policy_allow"


def test_validate_ssh_readonly_policy_allows_short_health_chain() -> None:
    decision = validate_ssh_readonly_policy("uptime && df -h / && free -h && systemctl is-active netalertx")

    assert decision.action == "allow"
    assert decision.reason == "ssh_readonly_policy_allow"


def test_validate_ssh_readonly_policy_allows_systemctl_failed_status_form() -> None:
    decision = validate_ssh_readonly_policy("systemctl --failed --no-pager")

    assert decision.action == "allow"
    assert decision.reason == "ssh_readonly_policy_allow"


def test_validate_ssh_readonly_policy_allows_dns_probe_commands() -> None:
    for command in (
        "dig @127.0.0.1 google.com +short +time=2",
        "host google.com 127.0.0.1",
        "nslookup google.com 127.0.0.1",
        "systemctl is-active pihole-FTL && dig @127.0.0.1 google.com +short +time=2",
    ):
        decision = validate_ssh_readonly_policy(command)

        assert decision.action == "allow"
        assert decision.reason == "ssh_readonly_policy_allow"


def test_validate_ssh_readonly_policy_allows_apt_upgradable_list() -> None:
    decision = validate_ssh_readonly_policy("apt list --upgradable")

    assert decision.action == "allow"
    assert decision.reason == "ssh_readonly_policy_allow"


def test_validate_ssh_readonly_policy_blocks_mutating_apt_operation() -> None:
    decision = validate_ssh_readonly_policy("apt upgrade")

    assert decision.action == "block"
    assert decision.reason == "ssh_command_mutating_operation"


def test_validate_ssh_readonly_policy_allows_exact_allowlisted_health_bundle() -> None:
    allow_commands = [
        "uptime -p",
        "df -h",
        "free -h",
        "systemctl --failed --no-pager",
        "journalctl -p 3 -xb --no-pager -n 40",
    ]
    decision = validate_ssh_readonly_policy(" && ".join(allow_commands), allow_commands=allow_commands)

    assert decision.action == "allow"
    assert decision.reason == "ssh_command_allow_list_allow"


def test_validate_ssh_readonly_policy_requires_confirmation_for_complex_readonly_chain() -> None:
    decision = validate_ssh_readonly_policy(
        "uptime && df -h / && free -h && systemctl status netalertx 2>/dev/null || ps aux | grep -i netalert | grep -v grep"
    )

    assert decision.action == "ask_user"
    assert decision.reason == "ssh_command_needs_confirmation"


def test_validate_ssh_readonly_policy_blocks_mutating_operation() -> None:
    decision = validate_ssh_readonly_policy("systemctl restart nginx")

    assert decision.action == "block"
    assert decision.reason == "ssh_command_mutating_operation"


def test_validate_ssh_readonly_policy_blocks_find_delete_form() -> None:
    decision = validate_ssh_readonly_policy("find /tmp -delete")

    assert decision.action == "block"
    assert decision.reason == "ssh_command_mutating_operation"


def test_validate_ssh_readonly_policy_blocks_ip_set_form() -> None:
    decision = validate_ssh_readonly_policy("ip link set eth0 down")

    assert decision.action == "block"
    assert decision.reason == "ssh_command_mutating_operation"


def test_validate_ssh_readonly_policy_blocks_sysctl_write_form() -> None:
    decision = validate_ssh_readonly_policy("sysctl -w net.ipv4.ip_forward=1")

    assert decision.action == "block"
    assert decision.reason == "ssh_command_mutating_operation"


def test_validate_ssh_readonly_policy_blocks_date_set_form() -> None:
    decision = validate_ssh_readonly_policy('date -s "2026-01-01"')

    assert decision.action == "block"
    assert decision.reason == "ssh_command_mutating_operation"


def test_validate_ssh_readonly_policy_blocks_allowlist_mismatch() -> None:
    decision = validate_ssh_readonly_policy("cat /etc/hosts", allow_commands=["uptime", "df -h"])

    assert decision.action == "block"
    assert decision.reason == "ssh_command_not_in_allow_list"


def test_command_matches_allow_commands_uses_structured_prefix_matching() -> None:
    assert command_matches_allow_commands("df -h /", ["df -h"]) is True
    assert command_matches_allow_commands("echo df -h /", ["df -h"]) is False
