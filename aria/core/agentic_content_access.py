from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from aria.core.action_plan import ActionPlan
from aria.core.connection_action_contract import connection_action_contract
from aria.core.connection_catalog import normalize_connection_kind


READ_SEARCH_PLANNER_ROLES = {"list", "read", "search"}


@dataclass(frozen=True, slots=True)
class AgenticContentAccessRequest:
    capability: str
    connection_kind: str
    connection_ref: str
    planner_role: str
    query: str = ""
    selector: str = ""
    limit: int = 10
    user_id: str = ""
    language: str = "de"
    sensitive_content: bool = False


@dataclass(frozen=True, slots=True)
class AgenticContentHit:
    item_id: str
    title: str = ""
    source: str = ""
    snippet: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgenticContentAccessResult:
    hits: tuple[AgenticContentHit, ...] = field(default_factory=tuple)
    summary: str = ""
    detail_lines: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    sensitive_content: bool = False


class AgenticContentAccessHandler(Protocol):
    def can_handle(self, request: AgenticContentAccessRequest) -> bool:
        ...

    async def access(self, request: AgenticContentAccessRequest) -> AgenticContentAccessResult:
        ...


def content_access_request_from_action_plan(
    plan: ActionPlan,
    *,
    user_id: str = "",
    language: str = "de",
    limit: int = 10,
) -> AgenticContentAccessRequest | None:
    contract = connection_action_contract(str(getattr(plan, "capability", "") or ""))
    if contract is None or contract.planner_role not in READ_SEARCH_PLANNER_ROLES:
        return None
    connection_ref = str(getattr(plan, "connection_ref", "") or "").strip()
    if "connection_ref" in contract.required_fields and not connection_ref:
        return None
    return AgenticContentAccessRequest(
        capability=contract.capability,
        connection_kind=normalize_connection_kind(str(getattr(plan, "connection_kind", "") or "")),
        connection_ref=connection_ref,
        planner_role=contract.planner_role,
        query=str(getattr(plan, "content", "") or "").strip(),
        selector=str(getattr(plan, "path", "") or "").strip(),
        limit=max(1, int(limit or 10)),
        user_id=str(user_id or "").strip(),
        language=str(language or "de").strip() or "de",
        sensitive_content=bool(contract.sensitive_content),
    )
