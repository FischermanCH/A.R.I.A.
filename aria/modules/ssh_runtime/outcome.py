"""SSH runtime outcome metadata authority."""

from __future__ import annotations

from aria.modules.action_contracts.plan import ActionPlan


def ssh_runtime_outcome_metadata(plan: ActionPlan, result_text: str) -> dict[str, dict[str, object]]:
    if str(plan.connection_kind or "").strip().lower() != "ssh":
        return {}
    if str(plan.capability or "").strip().lower() != "ssh_command":
        return {}
    ref = str(plan.connection_ref or "").strip()
    command = str(plan.content or "").strip()
    if not ref or not command:
        return {}
    clean_result = str(result_text or "").strip()
    state = "ok" if clean_result else "empty"
    return {
        "runtime_outcome": {
            "surface_id": "connections",
            "kind": "ssh",
            "capability": "ssh_command",
            "task_intent": "single_command",
            "command": command,
            "targets": [ref],
            "records": [
                {
                    "ref": ref,
                    "state": state,
                    "text": clean_result,
                    "raw_text": clean_result,
                }
            ],
            "summary": clean_result,
            "followup_affordances": ["inspect_path", "explain_result", "rerun_check"],
        }
    }
