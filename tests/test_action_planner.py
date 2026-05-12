from __future__ import annotations

import asyncio
from types import SimpleNamespace

import aria.core.action_planner as action_planner_mod
from aria.core.action_candidate_taxonomy import LEARNED_EXPERIENCE_ORIGIN
from aria.core.action_candidate_taxonomy import LEARNED_RECIPE_CANDIDATE_ROLE
from aria.core.action_planner import ActionPlanCandidate
from aria.core.action_planner import _suggested_follow_up_prompt
from aria.core.action_planner import bounded_action_candidates_for_target, build_action_planner_input_set, debug_bounded_action_plan_decision
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.planner_candidates import build_connection_planner_input_set, build_planner_input_set, merge_planner_input_sets, planner_candidate_from_connection, planner_input_set_to_dict


def test_bounded_action_candidates_include_builtin_ssh_run_command_template() -> None:
    candidates = bounded_action_candidates_for_target("pruef mal den pi-hole", connection_kind="ssh")

    ids = {(row.candidate_kind, row.candidate_id) for row in candidates}
    assert ("template", "ssh_run_command") in ids


def test_bounded_action_candidates_include_mailbox_and_mqtt_templates() -> None:
    imap_candidates = bounded_action_candidates_for_target("suche im postfach nach rechnung", connection_kind="imap")
    mqtt_candidates = bounded_action_candidates_for_target('sende per mqtt topic aria/events "test"', connection_kind="mqtt")

    imap_ids = {(row.candidate_kind, row.candidate_id) for row in imap_candidates}
    mqtt_ids = {(row.candidate_kind, row.candidate_id) for row in mqtt_candidates}

    assert ("template", "imap_search_mailbox") in imap_ids
    assert ("template", "imap_read_mailbox") in imap_ids
    assert imap_candidates[0].candidate_id == "imap_search_mailbox"
    assert ("template", "mqtt_publish_message") in mqtt_ids


def test_bounded_action_candidates_use_default_read_preference_for_imap_following_kind_spec() -> None:
    candidates = bounded_action_candidates_for_target("was liegt im ops postfach", connection_kind="imap")

    assert candidates
    assert candidates[0].candidate_id == "imap_read_mailbox"


def test_bounded_action_candidates_use_same_mailbox_family_for_imap() -> None:
    candidates = bounded_action_candidates_for_target('suche im postfach nach "Rechnung"', connection_kind="imap")

    mailbox_read = next(item for item in candidates if item.candidate_id == "imap_read_mailbox")
    mailbox_search = next(item for item in candidates if item.candidate_id == "imap_search_mailbox")

    assert mailbox_read.plan_class == "mailbox_read_basic"
    assert mailbox_search.plan_class == "mailbox_search_basic"


def test_bounded_action_candidates_use_default_list_preference_for_sftp_following_kind_spec() -> None:
    candidates = bounded_action_candidates_for_target("was liegt auf dem files server", connection_kind="sftp")

    assert candidates
    assert candidates[0].candidate_id == "sftp_list_files"


def test_bounded_action_candidates_use_same_file_family_for_smb_and_sftp() -> None:
    sftp_candidates = bounded_action_candidates_for_target("lies die hosts datei", connection_kind="sftp")
    smb_candidates = bounded_action_candidates_for_target("lies die hosts datei", connection_kind="smb")

    sftp_read = next(item for item in sftp_candidates if item.candidate_id == "sftp_read_file")
    smb_read = next(item for item in smb_candidates if item.candidate_id == "smb_read_file")

    assert sftp_read.plan_class == "file_read_basic"
    assert smb_read.plan_class == "file_read_basic"


def test_bounded_action_candidates_merge_connection_routing_spec_keywords_into_templates() -> None:
    candidates = bounded_action_candidates_for_target("wie sieht der api status aus", connection_kind="http_api")

    api_request = next(item for item in candidates if item.candidate_id == "http_api_request")
    assert "api status" in api_request.router_keywords
    assert "endpoint pruefen" in api_request.router_keywords
    assert api_request.plan_class == "api_request_basic"


def test_suggested_follow_up_prompt_uses_file_family_metadata() -> None:
    prompt = _suggested_follow_up_prompt(
        "lies die datei vom management server",
        ActionPlanCandidate(
            candidate_kind="template",
            candidate_id="sftp_read_file",
            plan_class="file_read_basic",
        ),
        connection_ref="mgmt",
        missing_input="remote_path",
        language="de",
    )

    assert prompt == "Lies /etc/hosts vom management server"


def test_suggested_follow_up_prompt_uses_request_target_family_metadata() -> None:
    prompt = _suggested_follow_up_prompt(
        "pruefe den status der inventory api",
        ActionPlanCandidate(
            candidate_kind="template",
            candidate_id="http_api_request",
            plan_class="api_request_basic",
        ),
        connection_ref="inventory-api",
        language="de",
    )

    assert prompt == "Rufe den Status-Endpunkt von inventory-api ab"


def test_bounded_action_candidates_include_google_calendar_template() -> None:
    candidates = bounded_action_candidates_for_target("was steht heute in meinem kalender", connection_kind="google_calendar")

    ids = {(row.candidate_kind, row.candidate_id) for row in candidates}
    assert ("template", "google_calendar_read_events") in ids


def test_build_action_planner_input_set_exposes_normalized_action_candidates() -> None:
    planner_input = build_action_planner_input_set(
        "pruef mal den pi-hole",
        connection_kind="ssh",
        connection_ref="pihole1",
        language="de",
        notes=["ops pilot"],
    )

    assert planner_input.query == "pruef mal den pi-hole"
    assert planner_input.preferred_connection_kind == "ssh"
    assert planner_input.connection_ref == "pihole1"
    assert planner_input.notes == ["ops pilot"]
    assert any(item.candidate_type == "template" and item.candidate_id == "ssh_run_command" for item in planner_input.action_candidates)
    health = next(item for item in planner_input.action_candidates if item.candidate_id == "ssh_run_command")
    assert health.capability == "ssh_command"
    assert health.intent == "run_command"
    assert health.metadata["plan_class"] == "command_single"
    assert health.metadata["candidate_role"] == "template_candidate"
    assert health.metadata["recipe_origin"] == "built_in_template_library"
    assert health.metadata["recipe_scope"] == {"connection_kind": "ssh"}
    assert health.metadata["experience_count"] == 0
    assert health.metadata["last_success_at"] == ""
    assert health.metadata["promotion_state"] == ""
    assert health.metadata["promotion_hint"] == ""


def test_bounded_action_candidates_expose_plan_classes_for_bounded_templates() -> None:
    candidates = bounded_action_candidates_for_target("wie geht es dem monitoring server", connection_kind="ssh", language="de")

    health = next(item for item in candidates if item.candidate_id == "ssh_run_command")
    command = next(item for item in candidates if item.candidate_id == "ssh_run_command")

    assert health.plan_class == "command_single"
    assert command.plan_class == "command_single"


def test_planner_input_set_can_combine_connection_and_action_candidates() -> None:
    connection_candidate = planner_candidate_from_connection(
        SemanticConnectionCandidate(
            connection_kind="ssh",
            connection_ref="mgmt-server",
            source="semantic_alias",
            note="alias:management server",
            alias="management server",
            score=171,
        )
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )
    combined = build_planner_input_set(
        query="check health auf management server",
        language="de",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[connection_candidate],
        action_candidates=action_input.action_candidates,
        notes=["retrieval-first pilot"],
    )

    assert combined.connection_candidates[0].candidate_type == "connection"
    assert combined.connection_candidates[0].candidate_id == "mgmt-server"
    assert combined.connection_candidates[0].connection_kind == "ssh"
    assert any(item.candidate_type == "template" for item in combined.action_candidates)
    assert combined.notes == ["retrieval-first pilot"]


def test_connection_planner_input_set_normalizes_semantic_candidates() -> None:
    planner_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            )
        ],
        notes=["connection pilot"],
    )

    assert planner_input.connection_ref == "mgmt-server"
    assert planner_input.connection_candidates[0].candidate_type == "connection"
    assert planner_input.connection_candidates[0].connection_kind == "ssh"
    assert planner_input.notes == ["connection pilot"]


def test_merge_planner_input_sets_keeps_connection_and_action_candidates() -> None:
    connection_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            )
        ],
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )

    merged = merge_planner_input_sets(connection_input, action_input, notes=["planner merge"])
    payload = planner_input_set_to_dict(merged)

    assert payload["connection_ref"] == "mgmt-server"
    assert any(item["candidate_type"] == "connection" for item in payload["connection_candidates"])
    assert any(item["candidate_id"] == "ssh_run_command" for item in payload["action_candidates"])
    assert payload["notes"] == ["planner merge"]


def test_merge_planner_input_sets_keeps_session_context() -> None:
    connection_input = build_connection_planner_input_set(
        query="check health auf management server",
        preferred_connection_kind="ssh",
        connection_ref="mgmt-server",
        connection_candidates=[
            SemanticConnectionCandidate(
                connection_kind="ssh",
                connection_ref="mgmt-server",
                source="semantic_alias",
                note="alias:management server",
                alias="management server",
                score=171,
            )
        ],
        session_context={"recent_connection_ref": "mgmt-server"},
    )
    action_input = build_action_planner_input_set(
        "check health auf management server",
        connection_kind="ssh",
        connection_ref="mgmt-server",
        language="de",
    )

    merged = merge_planner_input_sets(
        connection_input,
        action_input,
        session_context={"recent_capability": "ssh_command"},
    )
    payload = planner_input_set_to_dict(merged)

    assert payload["session_context"] == {
        "recent_connection_ref": "mgmt-server",
        "recent_capability": "ssh_command",
    }


def test_action_planner_dry_run_selects_builtin_template() -> None:
    class FakeLLMClient:
        async def chat(self, _messages: list[dict[str, str]], **_kwargs: object) -> object:
            return SimpleNamespace(
                content='{"candidate_kind":"template","candidate_id":"ssh_run_command","intent":"health_check","confidence":"high","ask_user":false,"reason":"Health check fits the request best."}'
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
    assert result["decision"]["candidate_id"] == "ssh_run_command"
    assert result["decision"]["intent"] == "health_check"
    assert result["decision"]["intent_label"] == "Gesundheitscheck"
    assert result["decision"]["capability"] == "ssh_command"
    assert result["decision"]["capability_label"] == "SSH-Befehl"
    assert result["decision"]["summary_line"] == "Template: Gesundheitscheck via SSH-Befehl auf ssh/pihole1"
    assert result["decision"]["score"] >= 0
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
        "_load_stored_recipe_manifests",
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
                content='{"candidate_kind":"recipe","candidate_id":"linux-health","intent":"health_check","confidence":"high","ask_user":false,"reason":"The stored recipe already models this host check."}'
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
    assert result["decision"]["candidate_kind"] == "recipe"
    assert result["decision"]["candidate_kind_label"] == "Rezept"
    assert result["decision"]["candidate_id"] == "linux-health"
    assert result["decision"]["intent"] == "health_check"
    assert result["decision"]["intent_label"] == "Gesundheitscheck"
    assert result["decision"]["capability_label"] == "SSH"
    assert result["decision"]["summary_line"] == "Rezept: Gesundheitscheck via SSH auf ssh/srv-a"
    assert result["decision"]["candidate_role"] == "stored_recipe_candidate"
    assert result["decision"]["recipe_origin"] == "stored_recipe_manifest"
    assert result["decision"]["recipe_scope"] == {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]}
    assert result["decision"]["experience_count"] == 0
    assert result["decision"]["last_success_at"] == ""
    assert result["decision"]["promotion_state"] == ""
    assert result["decision"]["promotion_hint"] == ""
    assert result["decision"]["inputs"] == {"command": "uptime"}
    assert result["decision"]["input_items"] == [{"key": "command", "key_label": "Befehl", "value": "uptime"}]
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert any(item["candidate_id"] == "linux-health" for item in result["candidates"])
    assert any(item["candidate_id"] == "linux-health" and item["inputs"] == {"command": "uptime"} for item in result["candidates"])
    assert any(
        item["candidate_id"] == "linux-health"
        and item["candidate_role"] == "stored_recipe_candidate"
        and item["recipe_origin"] == "stored_recipe_manifest"
        and item["experience_count"] == 0
        and item["promotion_state"] == ""
        for item in result["candidates"]
    )
    assert result["execution_state"] == "ready"
    assert result["target_context"] == "ssh/srv-a"


def test_candidate_payload_preserves_learned_recipe_experience_metadata() -> None:
    candidate = ActionPlanCandidate(
        candidate_kind="recipe",
        candidate_id="learned-linux-health",
        title="Learned Linux Health",
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        preview="SSH command: uptime && df -h / && free -h",
        candidate_role=LEARNED_RECIPE_CANDIDATE_ROLE,
        recipe_scope={"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        recipe_origin=LEARNED_EXPERIENCE_ORIGIN,
        experience_count=7,
        last_success_at="2026-05-01T10:15:00Z",
        promotion_state="eligible",
        promotion_hint="Observed repeated successful Linux health checks.",
    )

    payload = action_planner_mod._candidate_payload(candidate)

    assert payload["candidate_role"] == LEARNED_RECIPE_CANDIDATE_ROLE
    assert payload["recipe_origin"] == LEARNED_EXPERIENCE_ORIGIN
    assert payload["recipe_scope"] == {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]}
    assert payload["experience_count"] == 7
    assert payload["last_success_at"] == "2026-05-01T10:15:00Z"
    assert payload["promotion_state"] == "eligible"
    assert payload["promotion_hint"] == "Observed repeated successful Linux health checks."


def test_bounded_action_candidates_include_learned_recipe_candidates_from_experience_records(monkeypatch) -> None:
    monkeypatch.setattr(action_planner_mod, "_load_stored_recipe_manifests", lambda: ([], []))
    monkeypatch.setattr(
        action_planner_mod,
        "_load_learned_recipe_records",
        lambda: [
            {
                "intent": "health_check",
                "connection_kind": "ssh",
                "capability": "ssh_command",
                "chosen_action": "uptime && df -h / && free -h",
                "experience_count": 7,
                "last_success_at": "2026-05-01T10:15:00Z",
                "promotion_state": "promoted",
                "promotion_hint": "Observed repeated successful Linux health checks.",
                "router_keywords": ["linux health", "server health"],
                "stored_recipe_id": "linux-health",
            }
        ],
    )

    candidates = bounded_action_candidates_for_target("mach bitte den gelernten linux health check", connection_kind="ssh", language="de")

    learned = next(item for item in candidates if item.candidate_role == LEARNED_RECIPE_CANDIDATE_ROLE)
    assert learned.candidate_id == "linux-health"
    assert learned.recipe_origin == LEARNED_EXPERIENCE_ORIGIN
    assert learned.recipe_scope == {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]}
    assert learned.preview == "SSH-Befehl: uptime && df -h / && free -h"
    assert learned.inputs == {"command": "uptime && df -h / && free -h"}
    assert learned.experience_count == 7
    assert learned.last_success_at == "2026-05-01T10:15:00Z"
    assert learned.promotion_state == "promoted"


def test_load_learned_recipe_records_only_allows_promoted_entries_with_stored_recipe_id(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_ENABLE_LEARNED_RECIPE_CANDIDATES", "1")
    monkeypatch.setattr(
        action_planner_mod,
        "load_learned_recipe_store_entries",
        lambda: [
            {"recipe_id": "learned-a", "promotion_state": "review_ready", "stored_recipe_id": "a"},
            {"recipe_id": "learned-b", "promotion_state": "eligible", "stored_recipe_id": "b"},
            {"recipe_id": "learned-c", "promotion_state": "promoted", "stored_recipe_id": ""},
            {"recipe_id": "learned-d", "promotion_state": "promoted", "stored_recipe_id": "stored-d"},
        ],
    )

    rows = action_planner_mod._load_learned_recipe_records()

    assert rows == [{"recipe_id": "learned-d", "promotion_state": "promoted", "stored_recipe_id": "stored-d"}]


def test_heuristic_action_decision_prefers_template_candidate_over_stored_recipe_candidate_on_equal_intent_and_score() -> None:
    template_candidate = ActionPlanCandidate(
        candidate_kind="template",
        candidate_id="ssh_run_command",
        intent="health_check",
        connection_kind="ssh",
        capability="ssh_command",
        candidate_role="template_candidate",
        recipe_origin="built_in_template_library",
        score=5.0,
    )
    recipe_candidate = ActionPlanCandidate(
        candidate_kind="recipe",
        candidate_id="linux-health",
        intent="health_check",
        connection_kind="ssh",
        capability="ssh",
        candidate_role="stored_recipe_candidate",
        recipe_origin="stored_recipe_manifest",
        score=5.0,
    )

    candidate, confidence, ask_user, reason = action_planner_mod._heuristic_action_decision(
        "mach bitte einen linux health check",
        [recipe_candidate, template_candidate],
    )

    assert candidate is template_candidate
    assert confidence == "medium"
    assert ask_user is False
    assert reason == "same_intent_role_priority"


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

    assert result["status"] == "warn"
    assert result["decision"] == {}
    assert result["planner_source"] == "llm"
    assert "ausserhalb der begrenzten Menge" in result["message"]


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
    assert result["decision"]["candidate_id"] == "ssh_run_command"
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
    assert result["status"] == "ok"
    assert result["ask_user"] is False
    assert result["decision"]["candidate_kind"] == "template"
    assert result["decision"]["candidate_id"] == "ssh_run_command"
    assert result["decision"]["execution_state"] == "ready"
    assert result["decision"]["execution_state_label"] == "Bereit"
    assert result["example_prompt"] == ""
    assert result["execution_state"] == "ready"
    assert result["execution_state_label"] == "Bereit"
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
    assert candidate_ids == ["ssh_run_command"]
    assert result["candidates"][0]["execution_state"] == "ready"
    assert result["candidates"][0]["execution_state_label"] == "Bereit"
    assert result["candidates"][0]["intent_label"] == "Kommando ausfuehren"
    assert result["candidates"][0]["capability_label"] == "SSH-Befehl"
    assert result["candidates"][0]["input_items"] == [{"key": "command", "key_label": "Befehl", "value": "uptime"}]
    assert result["candidates"][0]["summary_line"] == "Template: Kommando ausfuehren via SSH-Befehl"
