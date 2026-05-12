from __future__ import annotations

from aria.core.agentic_deterministic_boundaries import AGENTIC_PRODUCT_LOGIC_ROLE
from aria.core.agentic_deterministic_boundaries import DETERMINISTIC_BOUNDARIES
from aria.core.agentic_deterministic_boundaries import DETERMINISTIC_BOUNDARY_ROLES
from aria.core.agentic_deterministic_boundaries import deterministic_boundaries_by_role
from aria.core.agentic_deterministic_boundaries import deterministic_boundary_roles


def test_deterministic_boundaries_are_explicitly_not_product_logic() -> None:
    assert deterministic_boundary_roles() <= DETERMINISTIC_BOUNDARY_ROLES
    assert AGENTIC_PRODUCT_LOGIC_ROLE not in deterministic_boundary_roles()
    assert all(item.component and item.reason for item in DETERMINISTIC_BOUNDARIES)


def test_policy_boundary_is_the_required_execution_gate() -> None:
    policies = deterministic_boundaries_by_role("policy")

    assert len(policies) == 1
    assert "allow, ask_user, or block" in policies[0].reason
