from __future__ import annotations

import asyncio
from types import SimpleNamespace

import aria.core.action_planner as action_planner_mod
from aria.core.action_planner import bounded_action_candidates_for_target, debug_bounded_action_plan_decision


def test_bounded_action_candidates_include_builtin_ssh_health_template() -> None:
    candidates = bounded_action_candidates_for_target("pruef mal den pi-hole", connection_kind="ssh")

    ids = {(row.candidate_kind, row.candidate_id) for row in candidates}
    assert ("template", "ssh_health_check") in ids


def test_bounded_action_candidates_include_mailbox_and_mqtt_templates() -> None:
    imap_candidates = bounded_action_candidates_for_target("suche im postfach nach rechnung", connection_kind="imap")
    mqtt_candidates = bounded_action_candidates_for_target('sende per mqtt topic aria/events "test"', connection_kind="mqtt")

    imap_ids = {(row.candidate_kind, row.candidate_id) for row in imap_candidates}
    mqtt_ids = {(row.candidate_kind, row.candidate_id) for row in mqtt_candidates}

    assert ("template", "imap_search_mailbox") in imap_ids
    assert ("template", "imap_read_mailbox") in imap_ids
    assert ("template", "mqtt_publish_message") in mqtt_ids


def test_bounded_action_candidates_include_google_calendar_template() -> None:
    candidates = bounded_action_candidates_for_target("was steht heute in meinem kalender", connection_kind="google_calendar")

    ids = {(row.candidate_kind, row.candidate_id) for row in candidates}
    assert ("template", "google_calendar_read_events") in ids


def test_action_planner_dry_run_selects_builtin_template() -> None:
    class FakeLLMClient:
        async def chat(self, _messages: list[dict[str, str]], **_kwargs: object) -> object:
            return SimpleNamespace(
                content='{"candidate_kind":"template","candidate_id":"ssh_health_check","intent":"health_check","confidence":"high","ask_user":false,"reason":"Health check fits the request best."}'
            )

    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "pruef mal den pi-hole",
            llm_client=FakeLLMClient(),
            routing_decision={"found": True, "kind": "ssh", "ref": "pihole1", "reason": "secondary dns"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_kind_label"] == "Template"
    assert result["decision"]["candidate_id"] == "ssh_health_check"
    assert result["decision"]["intent"] == "health_check"
    assert result["decision"]["intent_label"] == "Gesundheitscheck"
    assert result["decision"]["capability"] == "ssh_command"
    assert result["decision"]["capability_label"] == "SSH-Befehl"
    assert result["decision"]["summary_line"] == "Template: Gesundheitscheck via SSH-Befehl auf ssh/pihole1"
    assert result["decision"]["score"] > 0
    assert result["decision"]["inputs"] == {"command": "uptime"}
    assert result["decision"]["input_items"] == [{"key": "command", "key_label": "Befehl", "value": "uptime"}]
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert result["decision"]["preview"] == "SSH-Befehl: uptime"
    assert result["confidence"] == "high"
    assert result["confidence_label"] == "Hoch"
    assert result["planner_source"] == "llm"
    assert result["planner_source_label"] == "LLM"
    assert result["execution_state"] == "ready"
    assert result["execution_state_label"] == "Bereit"
    assert result["target_context"] == "ssh/pihole1"
    assert result["target_reason"] == "secondary dns"


def test_action_planner_dry_run_can_select_custom_skill(monkeypatch) -> None:
    monkeypatch.setattr(
        action_planner_mod,
        "_load_custom_skill_manifests",
        lambda: (
            [
                {
                    "id": "linux-health",
                    "name": "Linux Health",
                    "description": "Prueft Linux Hosts.",
                    "connections": ["ssh"],
                    "router_keywords": ["linux health", "server check"],
                    "enabled_default": True,
                    "steps": [
                        {
                            "type": "ssh_run",
                            "params": {"command": "uptime"},
                        }
                    ],
                }
            ],
            [],
        ),
    )

    class FakeLLMClient:
        async def chat(self, _messages: list[dict[str, str]], **_kwargs: object) -> object:
            return SimpleNamespace(
                content='{"candidate_kind":"skill","candidate_id":"linux-health","intent":"health_check","confidence":"high","ask_user":false,"reason":"The custom skill already models this host check."}'
            )

    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "mach bitte einen linux health check",
            llm_client=FakeLLMClient(),
            routing_decision={"found": True, "kind": "ssh", "ref": "srv-a", "reason": "ssh target matched"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "skill"
    assert result["decision"]["candidate_kind_label"] == "Skill"
    assert result["decision"]["candidate_id"] == "linux-health"
    assert result["decision"]["intent"] == "health_check"
    assert result["decision"]["intent_label"] == "Gesundheitscheck"
    assert result["decision"]["capability_label"] == "SSH"
    assert result["decision"]["summary_line"] == "Skill: Gesundheitscheck via SSH auf ssh/srv-a"
    assert result["decision"]["inputs"] == {"command": "uptime"}
    assert result["decision"]["input_items"] == [{"key": "command", "key_label": "Befehl", "value": "uptime"}]
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert any(item["candidate_id"] == "linux-health" for item in result["candidates"])
    assert any(item["candidate_id"] == "linux-health" and item["inputs"] == {"command": "uptime"} for item in result["candidates"])
    assert result["execution_state"] == "ready"
    assert result["target_context"] == "ssh/srv-a"


def test_action_planner_recovers_from_llm_candidate_id_variant() -> None:
    class FakeLLMClient:
        async def chat(self, _messages: list[dict[str, str]], **_kwargs: object) -> object:
            return SimpleNamespace(
                content='{"candidate_kind":"template","candidate_id":"ssh healthcheck","intent":"health_check","confidence":"high","ask_user":false,"reason":"health check fits the request"}'
            )

    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "checke die healht auf meinem dns server",
            llm_client=FakeLLMClient(),
            routing_decision={"found": True, "kind": "ssh", "ref": "pihole1", "reason": "dns server"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "ssh_health_check"
    assert result["decision"]["inputs"] == {"command": "uptime"}
    assert result["decision"]["execution_state"] == "ready"
    assert result["planner_source"] == "llm"
    assert "bounded Recovery" in result["message"]


def test_action_planner_inherits_routing_confirmation_requirement() -> None:
    class FakeLLMClient:
        async def chat(self, _messages: list[dict[str, str]], **_kwargs: object) -> object:
            return SimpleNamespace(
                content='{"candidate_kind":"template","candidate_id":"discord_send_message","intent":"send_message","confidence":"high","ask_user":false,"reason":"send message fits the request"}'
            )

    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "schick eine testnachricht an meinen alerts channel",
            llm_client=FakeLLMClient(),
            routing_decision={
                "found": True,
                "kind": "discord",
                "ref": "fischerman-aria-messages",
                "reason": "fischerman-aria-messages",
                "routing_ask_user": True,
            },
            language="de",
        )
    )

    assert result["status"] == "warn"
    assert result["ask_user"] is True
    assert result["decision"]["candidate_id"] == "discord_send_message"
    assert result["decision"]["execution_state"] == "needs_confirmation"
    assert result["decision"]["reason"] == "Das Ziel ist noch nicht eindeutig bestaetigt; ARIA sollte vor der Ausfuehrung nachfragen."
    assert "Ziel sollte vor der Ausfuehrung bestaetigt werden" in result["message"]


def test_action_planner_without_llm_uses_heuristic_for_clear_single_direction() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "wie lange laeuft mein dns server schon",
            llm_client=None,
            routing_decision={"found": True, "kind": "ssh", "ref": "pihole1", "reason": "dns server"},
            language="de",
        )
    )

    assert result["available"] is False
    assert result["used"] is False
    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "ssh_health_check"
    assert result["ask_user"] is False


def test_action_planner_without_llm_derives_hosts_file_preview() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "lies die hosts datei vom management server",
            llm_client=None,
            routing_decision={"found": True, "kind": "sftp", "ref": "mgmt", "reason": "management server"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "sftp_read_file"
    assert result["decision"]["capability"] == "file_read"
    assert result["decision"]["intent_label"] == "Datei lesen"
    assert result["decision"]["capability_label"] == "Datei lesen"
    assert result["decision"]["summary_line"] == "Template: Datei lesen auf sftp/mgmt"
    assert result["decision"]["inputs"] == {"remote_path": "/etc/hosts"}
    assert result["decision"]["input_items"] == [{"key": "remote_path", "key_label": "Remote-Pfad", "value": "/etc/hosts"}]
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert result["decision"]["preview"] == "Remote-Pfad lesen: /etc/hosts"
    assert result["ask_user"] is False
    assert result["planner_source"] == "heuristic"
    assert result["planner_source_label"] == "Heuristik"
    assert result["confidence_label"] == "Mittel"
    assert result["execution_state"] == "ready"
    assert result["target_context"] == "sftp/mgmt"


def test_action_planner_without_llm_normalizes_natural_disk_check_to_df_h() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "check mal die festplatte auf meinen dns server",
            llm_client=None,
            routing_decision={"found": True, "kind": "ssh", "ref": "pihole1", "reason": "dns server"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "ssh_run_command"
    assert result["decision"]["inputs"] == {"command": "df -h"}
    assert result["decision"]["preview"] == "SSH-Befehl: df -h"
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert result["ask_user"] is False


def test_action_planner_without_llm_derives_discord_test_message_preview() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            'schick eine testnachricht an meinen alerts channel "ARIA lebt"',
            llm_client=None,
            routing_decision={"found": True, "kind": "discord", "ref": "alerts", "reason": "alerts channel"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "discord_send_message"
    assert result["decision"]["capability"] == "discord_send"
    assert result["decision"]["capability_label"] == "Discord-Nachricht senden"
    assert result["decision"]["summary_line"] == "Template: Nachricht senden auf discord/alerts"
    assert result["decision"]["inputs"] == {"message": "ARIA lebt"}
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert result["decision"]["preview"] == 'Discord-Nachricht: "ARIA lebt"'
    assert result["ask_user"] is False
    assert result["execution_state"] == "ready"


def test_action_planner_without_llm_derives_google_calendar_preview() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "was steht morgen in meinem kalender?",
            llm_client=None,
            routing_decision={"found": True, "kind": "google_calendar", "ref": "primary-calendar", "reason": "persönlicher kalender"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "google_calendar_read_events"
    assert result["decision"]["capability"] == "calendar_read"
    assert result["decision"]["intent_label"] == "Kalender lesen"
    assert result["decision"]["capability_label"] == "Kalendertermine lesen"
    assert result["decision"]["summary_line"] == "Template: Kalender lesen via Kalendertermine lesen auf google_calendar/primary-calendar"
    assert result["decision"]["inputs"] == {"range": "tomorrow"}
    assert result["decision"]["input_items"] == [{"key": "range", "key_label": "Zeitraum", "value": "tomorrow"}]
    assert result["decision"]["preview"] == "Kalender: Morgen"
    assert result["decision"]["execution_state"] == "ready"
    assert result["execution_state"] == "ready"


def test_action_planner_without_llm_derives_mailbox_search_preview() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            'suche im postfach nach "Rechnung"',
            llm_client=None,
            routing_decision={"found": True, "kind": "imap", "ref": "ops-mailbox", "reason": "ops inbox"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_id"] == "imap_search_mailbox"
    assert result["decision"]["capability"] == "mail_search"
    assert result["decision"]["capability_label"] == "Postfach durchsuchen"
    assert result["decision"]["inputs"] == {"search_query": "Rechnung"}
    assert result["decision"]["preview"] == "Mailbox-Suche: Rechnung"
    assert result["decision"]["execution_state"] == "ready"


def test_action_planner_without_llm_derives_mqtt_publish_preview() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            'sende per mqtt topic aria/events "ARIA lebt"',
            llm_client=None,
            routing_decision={"found": True, "kind": "mqtt", "ref": "event-bus", "reason": "mqtt broker"},
            language="de",
        )
    )

    assert result["status"] == "ok"
    assert result["decision"]["candidate_id"] == "mqtt_publish_message"
    assert result["decision"]["capability"] == "mqtt_publish"
    assert result["decision"]["capability_label"] == "MQTT-Nachricht senden"
    assert result["decision"]["inputs"] == {"topic": "aria/events", "message": "ARIA lebt"}
    assert result["decision"]["execution_state"] == "ready"


def test_action_planner_without_llm_asks_user_when_file_path_is_missing() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "lies die datei vom management server",
            llm_client=None,
            routing_decision={"found": True, "kind": "sftp", "ref": "mgmt", "reason": "management server"},
            language="de",
        )
    )

    assert result["status"] == "warn"
    assert result["ask_user"] is True
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "sftp_read_file"
    assert result["decision"]["intent_label"] == "Datei lesen"
    assert result["decision"]["capability_label"] == "Datei lesen"
    assert result["decision"]["summary_line"] == "Template: Datei lesen auf sftp/mgmt"
    assert result["decision"]["inputs"] == {}
    assert result["decision"]["input_items"] == []
    assert result["decision"]["execution_state"] == "needs_input"
    assert result["decision"]["execution_state_label"] == "Braucht Eingabe"
    assert result["missing_input"] == "remote_path"
    assert result["missing_input_label"] == "Remote-Pfad"
    assert result["clarifying_question"] == "Welchen Remote-Pfad soll ARIA lesen?"
    assert result["example_prompt"] == "Lies /etc/hosts vom management server"
    assert result["decision"]["reason"] == "Pflichtangabe fehlt: Remote-Pfad."
    assert result["planner_source"] == "heuristic"
    assert result["planner_source_label"] == "Heuristik"
    assert result["confidence_label"] == "Niedrig"
    assert result["execution_state"] == "needs_input"
    assert result["execution_state_label"] == "Braucht Eingabe"
    assert result["target_context"] == "sftp/mgmt"


def test_action_planner_without_llm_asks_user_on_ambiguous_request() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "mach was auf dem server",
            llm_client=None,
            routing_decision={"found": True, "kind": "ssh", "ref": "mgmt", "reason": "management server"},
            language="de",
        )
    )

    assert result["available"] is False
    assert result["used"] is False
    assert result["status"] == "warn"
    assert result["ask_user"] is True
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] in {"ssh_health_check", "ssh_run_command"}
    assert result["decision"]["execution_state"] == "needs_confirmation"
    assert result["decision"]["execution_state_label"] == "Braucht Bestaetigung"
    assert result["example_prompt"]
    assert result["execution_state"] == "needs_confirmation"
    assert result["execution_state_label"] == "Braucht Bestaetigung"
    assert result["target_context"] == "ssh/mgmt"


def test_action_planner_debug_sorts_ready_candidates_before_needs_input() -> None:
    result = asyncio.run(
        debug_bounded_action_plan_decision(
            "mach was auf dem server",
            llm_client=None,
            routing_decision={"found": True, "kind": "ssh", "ref": "mgmt", "reason": "management server"},
            language="de",
        )
    )

    candidate_ids = [item["candidate_id"] for item in result["candidates"]]
    assert candidate_ids[:2] == ["ssh_health_check", "ssh_run_command"]
    assert result["candidates"][0]["execution_state"] == "ready"
    assert result["candidates"][0]["execution_state_label"] == "Bereit"
    assert result["candidates"][0]["intent_label"] == "Gesundheitscheck"
    assert result["candidates"][0]["capability_label"] == "SSH-Befehl"
    assert result["candidates"][0]["input_items"] == [{"key": "command", "key_label": "Befehl", "value": "uptime"}]
    assert result["candidates"][0]["summary_line"] == "Template: Gesundheitscheck via SSH-Befehl"
    assert result["candidates"][0]["score"] >= result["candidates"][1]["score"]
    assert result["candidates"][1]["execution_state"] == "needs_input"
    assert result["candidates"][1]["missing_input"] == "command"
    assert result["candidates"][1]["summary_line"] == "Template: Kommando ausfuehren via SSH-Befehl"
    assert result["candidates"][1]["missing_input_label"] == "Befehl"
    assert result["candidates"][1]["intent_label"] == "Kommando ausfuehren"
    assert result["candidates"][1]["capability_label"] == "SSH-Befehl"
    assert result["candidates"][1]["clarifying_question"] == "Welchen Befehl soll ARIA auf diesem Ziel ausfuehren?"
    assert result["candidates"][1]["example_prompt"] == 'Fuehre "df -h" auf mgmt aus'
