from __future__ import annotations

from aria.core.action_plan import ActionPlan
from aria.core.learned_recipe_integration import record_routed_action_success
from aria.core.learned_recipe_integration import record_routed_stored_recipe_success
from aria.core.learned_recipe_integration import should_record_learned_recipe_success


def test_should_record_learned_recipe_success_accepts_template_capability_actions() -> None:
    action = {
        "candidate_kind": "template",
        "candidate_role": "template_candidate",
    }
    plan = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="srv-a",
        content="uptime",
    )

    assert should_record_learned_recipe_success(action, plan) is True


def test_should_record_learned_recipe_success_skips_recipe_candidates() -> None:
    action = {
        "candidate_kind": "recipe",
        "candidate_role": "stored_recipe_candidate",
    }
    plan = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="srv-a",
        content="uptime",
    )

    assert should_record_learned_recipe_success(action, plan) is False


def test_record_routed_action_success_builds_update_payload_from_template_action() -> None:
    captured: dict[str, object] = {}

    def _recorder(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    action = {
        "candidate_kind": "template",
        "candidate_role": "template_candidate",
        "candidate_id": "ssh_run_command",
        "title": "SSH Agentic Command",
        "preview": "SSH-Befehl aus Zielkontext und Benutzeranfrage",
        "intent": "run_command",
        "inputs": {"command": "uptime"},
        "router_keywords": ["status", "health"],
        "recipe_scope": {"connection_kind": "ssh"},
    }
    plan = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="srv-a",
        content="uptime",
    )

    result = record_routed_action_success(
        action=action,
        plan=plan,
        result_text="Kurzcheck fuer srv-a: erreichbar.",
        recorder=_recorder,
    )

    assert result == {"ok": True}
    assert captured == {
        "recipe_id": "ssh_run_command",
        "title": "SSH Agentic Command",
        "preview": "SSH-Befehl aus Zielkontext und Benutzeranfrage",
        "inputs": {"command": "uptime"},
        "router_keywords": ["status", "health"],
        "recipe_scope": {"connection_kind": "ssh"},
        "intent": "run_command",
        "connection_kind": "ssh",
        "connection_ref": "srv-a",
        "capability": "ssh_command",
        "chosen_action": "uptime",
        "policy_result": "allow",
        "execution_result": "success",
        "user_feedback": "",
        "user_message": "",
        "summary": "Kurzcheck fuer srv-a: erreichbar.",
    }


def test_record_routed_action_success_marks_plural_target_scope_context_only() -> None:
    captured: dict[str, object] = {}

    def _recorder(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    action = {
        "candidate_kind": "template",
        "candidate_role": "template_candidate",
        "candidate_id": "ssh_run_command",
        "title": "SSH Agentic Command",
        "intent": "run_command",
        "inputs": {"command": "uptime"},
        "recipe_scope": {"connection_kinds": ["ssh"]},
    }
    plan = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="srv-a",
        content="uptime",
        resolution_source="plural_target_scope",
    )

    result = record_routed_action_success(
        action=action,
        plan=plan,
        result_text="srv-a ok",
        recorder=_recorder,
        user_message="check all servers",
    )

    assert result == {"ok": True}
    assert captured["recipe_scope"] == {
        "connection_kinds": ["ssh"],
        "target_scope": "multi_target",
        "learning_origin": "plural_target_scope",
    }


def test_record_routed_action_success_records_normalized_api_request_path() -> None:
    captured: dict[str, object] = {}

    def _recorder(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    action = {
        "candidate_kind": "template",
        "candidate_role": "template_candidate",
        "candidate_id": "http_api_request",
        "title": "API Request",
        "intent": "api_request",
        "inputs": {"path": "/health"},
        "recipe_scope": {"connection_kinds": ["http_api"]},
    }
    plan = ActionPlan(
        capability="api_request",
        connection_kind="http_api",
        connection_ref="inventory-api",
        path="/health",
    )

    result = record_routed_action_success(
        action=action,
        plan=plan,
        result_text="ok",
        recorder=_recorder,
    )

    assert result == {"ok": True}
    assert captured["chosen_action"] == "/health"
    assert captured["capability"] == "api_request"


def test_record_routed_action_success_enriches_guardrail_healthcheck_learning() -> None:
    captured: dict[str, object] = {}

    def _recorder(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    action = {
        "candidate_kind": "template",
        "candidate_role": "template_candidate",
        "candidate_id": "ssh_run_command",
        "title": "SSH Agentic Command",
        "preview": "SSH-Befehl aus Zielkontext und Benutzeranfrage",
        "intent": "run_command",
        "inputs": {"command": "uptime"},
        "router_keywords": ["status"],
        "recipe_scope": {"connection_kinds": ["ssh"]},
        "reason": "guardrail_allowed_healthcheck",
        "guardrail_fallback_from": "uptime",
    }
    plan = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="pihole1",
        content="uptime -p && df -h && free -h && systemctl --failed --no-pager",
    )

    result = record_routed_action_success(
        action=action,
        plan=plan,
        result_text="Server-Healthcheck fuer pihole1: ok.",
        recorder=_recorder,
        user_message="wie geht es meinem dns server",
    )

    assert result == {"ok": True}
    assert captured["recipe_id"] == "learned-ssh-health-check-pihole1"
    assert captured["title"] == "Gelernter Server-Healthcheck: pihole1"
    assert captured["intent"] == "health_check"
    assert captured["inputs"] == {
        "command": "uptime -p && df -h && free -h && systemctl --failed --no-pager",
        "learned_from_command": "uptime",
    }
    assert captured["router_keywords"] == [
        "status",
        "wie geht es meinem dns server",
        "server healthcheck",
        "server status",
        "healthcheck",
        "health check",
        "wie geht es",
        "pihole1",
    ]
    assert captured["recipe_scope"] == {
        "connection_kinds": ["ssh"],
        "connection_refs": ["pihole1"],
        "learning_origin": "guardrail_healthcheck_fallback",
    }
    assert captured["user_message"] == "wie geht es meinem dns server"
    assert captured["chosen_action"] == "uptime -p && df -h && free -h && systemctl --failed --no-pager"


def test_record_routed_stored_recipe_success_accepts_single_step_ssh_recipe() -> None:
    captured: dict[str, object] = {}

    class _Result:
        success = True
        content = "[Stored Recipe Steps] Linux Health\nErgebnis:\nuptime"

    def _recorder(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    result = record_routed_stored_recipe_success(
        row={
            "id": "linux-health",
            "name": "Linux Health",
            "router_keywords": ["linux health", "server check"],
            "connections": ["ssh"],
            "steps": [
                {
                    "type": "ssh_run",
                    "params": {"command": "uptime"},
                }
            ],
        },
        skill_result=_Result(),
        recorder=_recorder,
    )

    assert result == {"ok": True}
    assert captured == {
        "recipe_id": "learned-linux-health",
        "title": "Linux Health",
        "preview": "",
        "inputs": {"command": "uptime"},
        "router_keywords": ["linux health", "server check"],
        "recipe_scope": {"connection_kinds": ["ssh"], "step_types": ["ssh_run"]},
        "intent": "health_check",
        "connection_kind": "ssh",
        "connection_ref": "",
        "capability": "ssh_command",
        "chosen_action": "uptime",
        "policy_result": "allow",
        "execution_result": "success",
        "user_feedback": "",
        "user_message": "",
        "summary": "[Stored Recipe Steps] Linux Health\nErgebnis:\nuptime",
    }


def test_record_routed_stored_recipe_success_skips_multi_step_recipes() -> None:
    class _Result:
        success = True
        content = "ok"

    captured: dict[str, object] = {}

    def _recorder(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    result = record_routed_stored_recipe_success(
        row={
            "id": "complex-health",
            "name": "Complex Health",
            "connections": ["ssh"],
            "steps": [
                {"type": "ssh_run", "params": {"command": "uptime"}},
                {"type": "chat_send", "params": {"message": "{prev_output}"}},
            ],
        },
        skill_result=_Result(),
        recorder=_recorder,
    )

    assert result is None
    assert captured == {}
