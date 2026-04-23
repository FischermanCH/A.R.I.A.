from __future__ import annotations

from aria.core.execution_dry_run import (
    build_execution_preview_dry_run,
    build_payload_dry_run,
    evaluate_guardrail_confirm_dry_run,
)


class _Settings:
    class _Connections:
        ssh = {
            "pihole1": {
                "host": "pihole1.lan",
                "user": "root",
                "guardrail_ref": "safe-ssh",
            }
        }
        sftp = {
            "mgmt": {
                "host": "mgmt.lan",
                "user": "root",
            }
        }
        email = {
            "ops-mail": {
                "smtp_host": "mail.example.local",
                "user": "ops@example.local",
            }
        }
        imap = {
            "ops-mailbox": {
                "host": "imap.example.local",
                "user": "ops@example.local",
                "mailbox": "INBOX",
            }
        }
        mqtt = {
            "event-bus": {
                "host": "mqtt.example.local",
                "topic": "aria/events",
            }
        }
        webhook = {
            "ops-hook": {
                "url": "https://example.local/hook",
            }
        }
        google_calendar = {
            "primary-calendar": {
                "calendar_id": "primary",
            }
        }

    class _Security:
        guardrails = {
            "safe-ssh": {
                "kind": "ssh_command",
                "allow_terms": ["uptime", "hostname"],
                "deny_terms": ["rm -rf", "shutdown"],
            }
        }

    connections = _Connections()
    security = _Security()


def test_payload_dry_run_builds_ssh_health_check() -> None:
    result = build_payload_dry_run(
        "pruef mal den pi-hole",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "ssh", "ref": "pihole1"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "ssh_health_check"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "ssh_command"
    assert result["payload"]["content"] == "uptime"
    assert result["payload"]["preview"] == "SSH command: uptime"
    assert result["payload"]["missing_fields"] == []


def test_payload_dry_run_infers_hosts_file_path() -> None:
    result = build_payload_dry_run(
        "lies die hosts datei vom management server",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "sftp", "ref": "mgmt"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "sftp_read_file"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "file_read"
    assert result["payload"]["path"] == "/etc/hosts"


def test_payload_dry_run_builds_email_send_message() -> None:
    result = build_payload_dry_run(
        'sende mail "ARIA Test"',
        settings=_Settings(),
        routing_decision={"found": True, "kind": "email", "ref": "ops-mail"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "email_send_message"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "email_send"
    assert result["payload"]["content"] == "ARIA Test"


def test_payload_dry_run_builds_google_calendar_read() -> None:
    result = build_payload_dry_run(
        "was steht morgen in meinem kalender?",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "google_calendar", "ref": "primary-calendar"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "google_calendar_read_events"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "calendar_read"
    assert result["payload"]["path"] == "tomorrow"


def test_payload_dry_run_builds_mailbox_search() -> None:
    result = build_payload_dry_run(
        'suche im postfach nach "Rechnung"',
        settings=_Settings(),
        routing_decision={"found": True, "kind": "imap", "ref": "ops-mailbox"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "imap_search_mailbox"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "mail_search"
    assert result["payload"]["content"] == "Rechnung"


def test_payload_dry_run_builds_mqtt_publish() -> None:
    result = build_payload_dry_run(
        'sende per mqtt topic aria/events "ARIA lebt"',
        settings=_Settings(),
        routing_decision={"found": True, "kind": "mqtt", "ref": "event-bus"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "mqtt_publish_message"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "mqtt_publish"
    assert result["payload"]["path"] == "aria/events"
    assert result["payload"]["content"] == "ARIA lebt"


def test_guardrail_confirm_dry_run_allows_safe_health_check() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "content": "uptime",
            "preview": "SSH command: uptime",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_Settings(), payload_debug=payload_debug)

    assert result["status"] == "ok"
    assert result["decision"]["action"] == "allow"
    assert result["decision"]["guardrail_ref"] == "safe-ssh"


def test_guardrail_confirm_dry_run_allows_safe_disk_check() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "content": "df -h",
            "preview": "SSH command: df -h",
            "missing_fields": [],
        }
    }

    settings = _Settings()
    settings.security.guardrails["safe-ssh"]["allow_terms"] = ["uptime", "hostname", "df -h"]
    result = evaluate_guardrail_confirm_dry_run(settings, payload_debug=payload_debug)

    assert result["status"] == "ok"
    assert result["decision"]["action"] == "allow"
    assert result["decision"]["guardrail_ref"] == "safe-ssh"


def test_guardrail_confirm_dry_run_inherits_routing_target_confirmation() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "file_read",
            "connection_kind": "sftp",
            "connection_ref": "mgmt",
            "path": "/etc/hosts",
            "preview": "Read remote path: /etc/hosts",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(
        _Settings(),
        payload_debug=payload_debug,
        routing_decision={"found": True, "kind": "sftp", "ref": "mgmt", "routing_ask_user": True},
        language="de",
    )

    assert result["status"] == "warn"
    assert result["decision"]["action"] == "ask_user"
    assert result["decision"]["reason"] == "routing_target_confirmation"
    assert result["decision"]["action_label"] == "Zuerst nachfragen"
    assert result["decision"]["reason_label"] == "Das Ziel ist noch nicht eindeutig bestaetigt."
    assert "ARIA wuerde vor der Ausfuehrung auf sftp/mgmt noch nachfragen." == result["decision"]["summary"]


def test_guardrail_confirm_dry_run_blocks_denied_ssh_command() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "content": "rm -rf /tmp/test",
            "preview": "SSH command: rm -rf /tmp/test",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_Settings(), payload_debug=payload_debug)

    assert result["status"] == "error"
    assert result["decision"]["action"] == "block"
    assert result["decision"]["reason"] == "guardrail_denied"
    assert result["decision"]["reason_label"] == "Guardrail profile safe-ssh blocks this action."


def test_execution_preview_dry_run_reports_allow_path() -> None:
    result = build_execution_preview_dry_run(
        routing_decision={"found": True, "kind": "ssh", "ref": "pihole1"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "ssh_health_check"},
        payload_debug={
            "payload": {
                "found": True,
                "capability": "ssh_command",
                "preview": "SSH command: uptime",
            }
        },
        safety_debug={"decision": {"action": "allow", "reason": "safe_health_check"}},
        language="de",
    )

    assert result["status"] == "ok"
    assert result["decision"]["next_step"] == "allow"
    assert result["decision"]["next_step_label"] == "Freigeben"
    assert result["decision"]["target"] == "ssh/pihole1"
    assert result["decision"]["preview"] == "SSH command: uptime"
    assert result["decision"]["summary"] == "ARIA wuerde auf ssh/pihole1 direkt ausfuehren: SSH command: uptime"
