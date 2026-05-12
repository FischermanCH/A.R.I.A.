from __future__ import annotations

from dataclasses import dataclass


DETERMINISTIC_BOUNDARY_ROLES = {"routing_hint", "normalizer", "policy", "runtime", "summary", "compatibility"}
AGENTIC_PRODUCT_LOGIC_ROLE = "product_logic"


@dataclass(frozen=True, slots=True)
class DeterministicBoundary:
    component: str
    role: str
    reason: str


DETERMINISTIC_BOUNDARIES: tuple[DeterministicBoundary, ...] = (
    DeterministicBoundary(
        component="routing lexicons and semantic resolver",
        role="routing_hint",
        reason="Suggest likely capability or target; LLM/planner may still resolve missing action details.",
    ),
    DeterministicBoundary(
        component="capability draft normalizers",
        role="normalizer",
        reason="Convert known payload shapes into stable runtime fields without inventing new intent.",
    ),
    DeterministicBoundary(
        component="guardrails, allowlists, deny rules, confirmation rules",
        role="policy",
        reason="Decide allow, ask_user, or block after any LLM-proposed draft.",
    ),
    DeterministicBoundary(
        component="runtime adapters",
        role="runtime",
        reason="Execute only normalized plans accepted by policy; never interpret free-form user intent.",
    ),
    DeterministicBoundary(
        component="result summarizers",
        role="summary",
        reason="Format execution output for humans without changing what was executed.",
    ),
    DeterministicBoundary(
        component="legacy recipe/skill wrappers",
        role="compatibility",
        reason="Keep old entry points working while product semantics move to recipes and agentic drafts.",
    ),
)


def deterministic_boundary_roles() -> set[str]:
    return {item.role for item in DETERMINISTIC_BOUNDARIES}


def deterministic_boundaries_by_role(role: str) -> tuple[DeterministicBoundary, ...]:
    clean = str(role or "").strip()
    return tuple(item for item in DETERMINISTIC_BOUNDARIES if item.role == clean)
