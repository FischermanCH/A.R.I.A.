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
        smb = {
            "mgmt": {
                "host": "fileserver.lan",
                "share": "ops",
                "user": "ops",
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
        http_api = {
            "inventory-api": {
                "base_url": "https://inventory.example.local",
                "health_path": "/health",
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


def test_payload_dry_run_builds_ssh_run_command() -> None:
    result = build_payload_dry_run(
        "pruef mal den pi-hole",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "ssh", "ref": "pihole1"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "ssh_run_command"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "ssh_command"
    assert result["payload"]["content"] == "uptime"
    assert result["payload"]["preview"] == "SSH command: uptime"
    assert result["payload"]["plan_class"] == "command_single"
    assert result["payload"]["behavior_profile"] == "ssh_run_command"
    assert result["payload"]["missing_fields"] == []


def test_payload_dry_run_builds_command_single_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        "wie geht es dem monitoring server",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "ssh", "ref": "pihole1"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "command_single"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "ssh_command"
    assert result["payload"]["content"] == "uptime"
    assert result["payload"]["plan_class"] == "command_single"
    assert result["payload"]["behavior_profile"] == "ssh_run_command"
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


def test_payload_dry_run_builds_file_read_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        "lies die hosts datei vom management server",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "smb", "ref": "mgmt"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "file_read_basic"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "file_read"
    assert result["payload"]["path"] == "/etc/hosts"
    assert result["payload"]["behavior_profile"] == "remote_read_file"


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


def test_payload_dry_run_builds_feed_read_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        "gib mir aktuelle security news",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "rss", "ref": "security-feed"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "feed_digest"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "feed_read"
    assert result["payload"]["behavior_profile"] == "rss_read_feed"


def test_payload_dry_run_builds_website_list_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        "zeige beobachtete webseiten in dokumentation",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "website", "ref": ""},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "website_listing"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "website_list"
    assert result["payload"]["content"] == "dokumentation"
    assert result["payload"]["behavior_profile"] == "website_list"


def test_payload_dry_run_builds_mail_read_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        "zeige mir die neuesten mails im ops postfach",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "imap", "ref": "ops-mailbox"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "mailbox_read_basic"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "mail_read"
    assert result["payload"]["behavior_profile"] == "imap_read_mailbox"


def test_payload_dry_run_builds_mail_search_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        'suche im postfach nach "Rechnung"',
        settings=_Settings(),
        routing_decision={"found": True, "kind": "imap", "ref": "ops-mailbox"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "mailbox_search_basic"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "mail_search"
    assert result["payload"]["content"] == "Rechnung"
    assert result["payload"]["behavior_profile"] == "imap_search_mailbox"


def test_payload_dry_run_builds_api_request_from_plan_class_without_template_id() -> None:
    result = build_payload_dry_run(
        "pruefe /health auf der inventory api",
        settings=_Settings(),
        routing_decision={"found": True, "kind": "http_api", "ref": "inventory-api"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "api_request_basic"},
    )

    assert result["status"] == "ok"
    assert result["payload"]["capability"] == "api_request"
    assert result["payload"]["path"] == "/health"
    assert result["payload"]["behavior_profile"] == "http_api_request"


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


def test_guardrail_confirm_dry_run_marks_message_agentic_boundary() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "mqtt_publish",
            "connection_kind": "mqtt",
            "connection_ref": "event-bus",
            "path": "aria/events",
            "content": "ARIA lebt",
            "preview": "MQTT publish to aria/events: ARIA lebt",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_Settings(), payload_debug=payload_debug, language="en")

    assert result["status"] == "warn"
    assert result["decision"]["reason"] == "side_effect_confirmation"
    assert result["decision"]["agentic_debug"].startswith("Routing Debug: message_operation_policy ref=event-bus")
    assert "agentic_source=payload_dry_run" in result["decision"]["agentic_debug"]
    assert "policy=message_confirm" in result["decision"]["agentic_debug"]


def test_guardrail_confirm_dry_run_marks_read_agentic_boundary() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "mail_search",
            "connection_kind": "imap",
            "connection_ref": "ops-mailbox",
            "content": "backup failed",
            "preview": "Search mailbox: backup failed",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_Settings(), payload_debug=payload_debug, language="en")

    assert result["status"] == "ok"
    assert result["decision"]["agentic_debug"].startswith("Routing Debug: read_operation_policy ref=ops-mailbox")
    assert "agentic_source=payload_dry_run" in result["decision"]["agentic_debug"]
    assert "policy=read_only" in result["decision"]["agentic_debug"]


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
    assert result["decision"]["agentic_debug"].startswith("Routing Debug: ssh_command_policy ref=pihole1")
    assert "agentic_source=payload_dry_run" in result["decision"]["agentic_debug"]
    assert "policy=ssh_readonly" in result["decision"]["agentic_debug"]


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


def test_guardrail_confirm_dry_run_allows_read_only_shell_chain() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "content": "uptime && df -h / && systemctl status netalertx 2>/dev/null || ps aux | grep -i netalert | grep -v grep",
            "preview": "SSH command: uptime && df -h / && systemctl status netalertx 2>/dev/null || ps aux | grep -i netalert | grep -v grep",
            "missing_fields": [],
        }
    }

    settings = _Settings()
    settings.security.guardrails["safe-ssh"]["allow_terms"] = [
        "uptime",
        "df -h /",
        "systemctl status",
        "ps aux",
        "grep -i netalert",
    ]
    result = evaluate_guardrail_confirm_dry_run(settings, payload_debug=payload_debug)

    assert result["status"] == "warn"
    assert result["decision"]["action"] == "ask_user"
    assert result["decision"]["guardrail_ref"] == "safe-ssh"
    assert result["decision"]["reason"] == "ssh_command_needs_confirmation"


def test_guardrail_confirm_dry_run_allows_exact_guardrail_health_bundle() -> None:
    allow_commands = [
        "uptime -p",
        "df -h",
        "free -h",
        "systemctl --failed --no-pager",
        "journalctl -p 3 -xb --no-pager -n 40",
    ]
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "content": " && ".join(allow_commands),
            "preview": f"SSH command: {' && '.join(allow_commands)}",
            "missing_fields": [],
        }
    }

    settings = _Settings()
    settings.security.guardrails["safe-ssh"]["allow_terms"] = allow_commands
    result = evaluate_guardrail_confirm_dry_run(settings, payload_debug=payload_debug)

    assert result["status"] == "ok"
    assert result["decision"]["action"] == "allow"
    assert result["decision"]["reason"] == "ssh_command_allow_list_allow"
    assert result["decision"]["agentic_debug"].startswith("Routing Debug: ssh_command_policy ref=pihole1")
    assert "agentic_source=payload_dry_run" in result["decision"]["agentic_debug"]
    assert "policy=ssh_readonly" in result["decision"]["agentic_debug"]


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
    assert "ARIA wuerde vor der Ausfuehrung auf sftp/mgmt noch nachfragen: Read remote path: /etc/hosts" == result["decision"]["summary"]


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
    assert result["decision"]["summary"] == "ARIA would block the planned action on ssh/pihole1: SSH command: rm -rf /tmp/test"


def test_guardrail_confirm_dry_run_ask_user_summary_includes_preview_when_available() -> None:
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
        language="en",
    )

    assert result["decision"]["summary"] == "ARIA would ask for confirmation before executing on sftp/mgmt: Read remote path: /etc/hosts"
    assert result["decision"]["agentic_debug"].startswith("Routing Debug: file_operation_policy ref=mgmt")
    assert "agentic_source=payload_dry_run" in result["decision"]["agentic_debug"]
    assert "policy=file_access" in result["decision"]["agentic_debug"]


def test_guardrail_confirm_dry_run_blocks_ssh_allowlist_mismatch() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "content": "cat /etc/hosts",
            "preview": "SSH command: cat /etc/hosts",
            "missing_fields": [],
        }
    }

    settings = _Settings()
    original = list(settings._Connections.ssh["pihole1"].get("allow_commands", []))
    original_guardrail = settings._Connections.ssh["pihole1"].get("guardrail_ref", "")
    settings._Connections.ssh["pihole1"]["allow_commands"] = ["uptime", "df -h"]
    settings._Connections.ssh["pihole1"]["guardrail_ref"] = ""
    try:
        result = evaluate_guardrail_confirm_dry_run(settings, payload_debug=payload_debug, language="de")
    finally:
        settings._Connections.ssh["pihole1"]["allow_commands"] = original
        settings._Connections.ssh["pihole1"]["guardrail_ref"] = original_guardrail

    assert result["status"] == "error"
    assert result["decision"]["action"] == "block"
    assert result["decision"]["reason"] == "ssh_command_not_in_allow_list"
    assert "Allowlist" in result["decision"]["reason_label"]


def test_guardrail_confirm_dry_run_allows_simple_http_api_health_check() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "api_request",
            "connection_kind": "http_api",
            "connection_ref": "inventory-api",
            "path": "/health",
            "content": "",
            "preview": "API request: /health",
            "notes": ["api_status_like"],
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_Settings(), payload_debug=payload_debug, language="de")

    assert result["status"] == "ok"
    assert result["decision"]["action"] == "allow"
    assert result["decision"]["reason"] == "http_api_readonly_policy_allow"
    assert result["decision"]["agentic_debug"].startswith("Routing Debug: http_api_policy ref=inventory-api")
    assert "agentic_source=payload_dry_run" in result["decision"]["agentic_debug"]
    assert "policy=http_api" in result["decision"]["agentic_debug"]


def test_guardrail_confirm_dry_run_blocks_mutating_http_api_path() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "api_request",
            "connection_kind": "http_api",
            "connection_ref": "inventory-api",
            "path": "/admin/restart",
            "content": "",
            "preview": "API request: /admin/restart",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_Settings(), payload_debug=payload_debug, language="de")

    assert result["status"] == "error"
    assert result["decision"]["action"] == "block"
    assert result["decision"]["reason"] == "http_api_mutating_path"


def test_execution_preview_dry_run_reports_allow_path() -> None:
    result = build_execution_preview_dry_run(
        routing_decision={"found": True, "kind": "ssh", "ref": "pihole1"},
        action_decision={"found": True, "candidate_kind": "template", "candidate_id": "ssh_run_command"},
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
    assert result["decision"]["plan_class"] == ""
    assert result["decision"]["preview"] == "SSH command: uptime"
    assert (
        result["decision"]["summary"]
        == "ARIA wuerde auf ssh/pihole1 direkt ausfuehren: SSH command: uptime"
    )


def test_execution_preview_dry_run_reports_command_single_plan_class_without_template_id() -> None:
    result = build_execution_preview_dry_run(
        routing_decision={"found": True, "kind": "ssh", "ref": "pihole1"},
        action_decision={"found": True, "candidate_kind": "template", "plan_class": "command_single"},
        payload_debug={
            "payload": {
                "found": True,
                "capability": "ssh_command",
                "preview": "",
                "plan_class": "command_single",
            }
        },
        safety_debug={"decision": {"action": "allow", "reason": "safe_health_check"}},
        language="de",
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_id"] == ""
    assert result["decision"]["plan_class"] == "command_single"
    assert result["decision"]["preview"] == ""
