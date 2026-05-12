from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.core.planner_candidates import PlannerInputSet


AGENTIC_PROMPT_FLOW_PHASES: tuple[str, ...] = (
    "context_enrichment",
    "llm_action_proposal",
    "policy_guardrail_decision",
    "runtime_execution",
)


@dataclass(slots=True)
class AgenticPromptFlow:
    phases: tuple[str, ...] = AGENTIC_PROMPT_FLOW_PHASES
    context_sources: list[str] = field(default_factory=list)
    llm_role: str = "propose_action"
    policy_gate: str = "allow|ask_user|block"
    runtime_rule: str = "execute_only_after_policy"

    def as_dict(self) -> dict[str, Any]:
        return {
            "phases": list(self.phases),
            "context_sources": list(self.context_sources),
            "llm_role": self.llm_role,
            "policy_gate": self.policy_gate,
            "runtime_rule": self.runtime_rule,
        }

    def as_prompt_lines(self) -> list[str]:
        sources = ", ".join(self.context_sources) if self.context_sources else "-"
        return [
            "Agentic execution contract:",
            "1. Deterministic context enrichment may provide bounded candidates, dossiers, policy hints, session context, and experience memory.",
            "2. Treat deterministic context as advisory context unless it is a policy or hard runtime constraint.",
            "3. The LLM proposes the target/action choice or missing action details inside the bounded contract.",
            "4. The LLM never grants execution permission; policy and guardrails decide allow, ask_user, or block.",
            "5. Runtime executes only normalized actions accepted by policy.",
            f"Context sources present: {sources}",
        ]


def build_agentic_prompt_flow(planner_input: PlannerInputSet) -> AgenticPromptFlow:
    sources: list[str] = []
    if list(planner_input.connection_candidates or []):
        sources.append("connection_candidates")
    if list(planner_input.action_candidates or []):
        sources.append("action_candidates")
    if dict(planner_input.session_context or {}):
        sources.append("session_context")
    if any(str(note or "").strip() for note in list(planner_input.notes or [])):
        sources.append("planner_notes")
    session_context = dict(planner_input.session_context or {})
    if str(session_context.get("recipe_experience", "") or "").strip():
        sources.append("experience_memory")
    return AgenticPromptFlow(context_sources=sources)


def agentic_prompt_flow_debug_line(flow: AgenticPromptFlow, *, planner_source: str = "") -> str:
    source = str(planner_source or "llm").strip().lower() or "llm"
    context = ",".join(flow.context_sources) if flow.context_sources else "-"
    phases = ">".join(flow.phases)
    return (
        "Planner: agentic_prompt_flow "
        f"phases={phases} context={context} proposal={source} "
        f"policy={flow.policy_gate} runtime={flow.runtime_rule}"
    )
