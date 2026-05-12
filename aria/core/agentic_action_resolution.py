from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


AGENTIC_POLICY_ACTIONS = {"allow", "ask_user", "block"}


def agentic_action_contract_prompt(capability_family: str, *, target_fixed: bool = True) -> str:
    family = str(capability_family or "action").strip() or "action"
    target_line = (
        "Routing and target selection are already complete; do not change the target."
        if target_fixed
        else "Use the bounded target context; do not invent targets outside the provided candidates."
    )
    return (
        f"Agentic action contract for {family}: "
        "Use the deterministic context and target dossier as bounded context, not as permission to execute. "
        f"{target_line} "
        "Propose one concrete action draft or fill missing action details only. "
        "Never authorize execution; policy and guardrails decide allow, ask_user, or block after this draft. "
        "Never invent secrets, credentials, hosts, auth headers, webhook URLs, or provider-specific access details."
    )


def normalize_agentic_policy_action(value: str, *, default: str = "ask_user") -> str:
    clean = str(value or "").strip().lower()
    if clean in {"ask", "confirm", "needs_confirmation"}:
        clean = "ask_user"
    if clean in AGENTIC_POLICY_ACTIONS:
        return clean
    fallback = str(default or "ask_user").strip().lower()
    return fallback if fallback in AGENTIC_POLICY_ACTIONS else "ask_user"


@dataclass(slots=True)
class AgenticActionDraft:
    capability: str
    connection_kind: str
    connection_ref: str
    operation: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "llm"
    confidence: str = ""
    reason: str = ""
    ask_user: bool = False
    review_issues: list[str] = field(default_factory=list)

    def normalized_payload_value(self, key: str) -> str:
        return str(self.payload.get(key, "") or "").strip()

    def as_debug_suffix(self) -> str:
        parts = [
            f"agentic_source={self.source or '-'}",
            f"operation={self.operation or '-'}",
        ]
        if self.review_issues:
            parts.append(f"review_issues={','.join(self.review_issues)}")
        return " ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "connection_kind": self.connection_kind,
            "connection_ref": self.connection_ref,
            "operation": self.operation,
            "payload": dict(self.payload),
            "source": self.source,
            "confidence": self.confidence,
            "reason": self.reason,
            "ask_user": self.ask_user,
            "review_issues": list(self.review_issues),
        }


@dataclass(slots=True)
class AgenticPolicyResult:
    action: str
    reason: str
    normalized_payload: dict[str, Any] = field(default_factory=dict)
    policy_name: str = ""

    @property
    def allowed(self) -> bool:
        return self.action == "allow"

    @property
    def requires_confirmation(self) -> bool:
        return self.action == "ask_user"

    @property
    def blocked(self) -> bool:
        return self.action == "block"

    def as_debug_suffix(self) -> str:
        policy = self.policy_name or "-"
        return f"policy={policy} policy_action={self.action or '-'} policy_reason={self.reason or '-'}"


def action_draft_from_ssh_command(
    *,
    connection_ref: str,
    command: str,
    source: str,
    confidence: str = "",
    reason: str = "",
    ask_user: bool = False,
    review_issues: list[str] | None = None,
) -> AgenticActionDraft:
    return AgenticActionDraft(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref=str(connection_ref or "").strip(),
        operation="run_command",
        payload={"command": str(command or "").strip()},
        source=str(source or "llm").strip() or "llm",
        confidence=str(confidence or "").strip().lower(),
        reason=str(reason or "").strip(),
        ask_user=bool(ask_user),
        review_issues=list(review_issues or []),
    )


def action_draft_from_http_request(
    *,
    connection_ref: str,
    path: str,
    content: str = "",
    method: str = "GET",
    source: str,
    confidence: str = "",
    reason: str = "",
    ask_user: bool = False,
    review_issues: list[str] | None = None,
) -> AgenticActionDraft:
    return AgenticActionDraft(
        capability="api_request",
        connection_kind="http_api",
        connection_ref=str(connection_ref or "").strip(),
        operation="request",
        payload={
            "method": str(method or "GET").strip().upper() or "GET",
            "path": str(path or "").strip(),
            "content": str(content or "").strip(),
        },
        source=str(source or "llm").strip() or "llm",
        confidence=str(confidence or "").strip().lower(),
        reason=str(reason or "").strip(),
        ask_user=bool(ask_user),
        review_issues=list(review_issues or []),
    )


def action_draft_from_file_operation(
    *,
    connection_kind: str,
    connection_ref: str,
    operation: str,
    path: str,
    content: str = "",
    source: str,
    confidence: str = "",
    reason: str = "",
    ask_user: bool = False,
    review_issues: list[str] | None = None,
) -> AgenticActionDraft:
    clean_operation = str(operation or "").strip().lower()
    if clean_operation not in {"list", "read", "write"}:
        clean_operation = "read"
    capability = "file_list" if clean_operation == "list" else "file_write" if clean_operation == "write" else "file_read"
    return AgenticActionDraft(
        capability=capability,
        connection_kind=str(connection_kind or "").strip().lower(),
        connection_ref=str(connection_ref or "").strip(),
        operation=clean_operation,
        payload={
            "path": str(path or "").strip(),
            "content": str(content or "").strip(),
        },
        source=str(source or "llm").strip() or "llm",
        confidence=str(confidence or "").strip().lower(),
        reason=str(reason or "").strip(),
        ask_user=bool(ask_user),
        review_issues=list(review_issues or []),
    )


def action_draft_from_message_operation(
    *,
    capability: str,
    connection_kind: str,
    connection_ref: str,
    content: str,
    topic: str = "",
    source: str,
    confidence: str = "",
    reason: str = "",
    ask_user: bool = False,
    review_issues: list[str] | None = None,
) -> AgenticActionDraft:
    clean_capability = str(capability or "").strip().lower()
    operation = "publish" if clean_capability == "mqtt_publish" else "send"
    return AgenticActionDraft(
        capability=clean_capability,
        connection_kind=str(connection_kind or "").strip().lower(),
        connection_ref=str(connection_ref or "").strip(),
        operation=operation,
        payload={
            "topic": str(topic or "").strip(),
            "content": str(content or "").strip(),
        },
        source=str(source or "llm").strip() or "llm",
        confidence=str(confidence or "").strip().lower(),
        reason=str(reason or "").strip(),
        ask_user=bool(ask_user),
        review_issues=list(review_issues or []),
    )


def action_draft_from_read_operation(
    *,
    capability: str,
    connection_kind: str,
    connection_ref: str,
    selector: str = "",
    query: str = "",
    source: str,
    confidence: str = "",
    reason: str = "",
    ask_user: bool = False,
    review_issues: list[str] | None = None,
) -> AgenticActionDraft:
    clean_capability = str(capability or "").strip().lower()
    return AgenticActionDraft(
        capability=clean_capability,
        connection_kind=str(connection_kind or "").strip().lower(),
        connection_ref=str(connection_ref or "").strip(),
        operation="read",
        payload={
            "selector": str(selector or "").strip(),
            "query": str(query or "").strip(),
        },
        source=str(source or "llm").strip() or "llm",
        confidence=str(confidence or "").strip().lower(),
        reason=str(reason or "").strip(),
        ask_user=bool(ask_user),
        review_issues=list(review_issues or []),
    )


def ssh_policy_result(*, action: str, reason: str, command: str) -> AgenticPolicyResult:
    return AgenticPolicyResult(
        action=normalize_agentic_policy_action(action),
        reason=str(reason or "").strip(),
        normalized_payload={"command": str(command or "").strip()},
        policy_name="ssh_readonly",
    )


def http_policy_result(*, action: str, reason: str, path: str, content: str = "") -> AgenticPolicyResult:
    return AgenticPolicyResult(
        action=normalize_agentic_policy_action(action),
        reason=str(reason or "").strip(),
        normalized_payload={
            "path": str(path or "").strip(),
            "content": str(content or "").strip(),
        },
        policy_name="http_api",
    )


def file_policy_result(*, action: str, reason: str, path: str, content: str = "") -> AgenticPolicyResult:
    return AgenticPolicyResult(
        action=normalize_agentic_policy_action(action),
        reason=str(reason or "").strip(),
        normalized_payload={
            "path": str(path or "").strip(),
            "content": str(content or "").strip(),
        },
        policy_name="file_access",
    )


def message_policy_result(*, action: str, reason: str, content: str, topic: str = "") -> AgenticPolicyResult:
    return AgenticPolicyResult(
        action=normalize_agentic_policy_action(action),
        reason=str(reason or "").strip(),
        normalized_payload={
            "topic": str(topic or "").strip(),
            "content": str(content or "").strip(),
        },
        policy_name="message_confirm",
    )


def read_policy_result(*, action: str = "allow", reason: str = "read_only", selector: str = "", query: str = "") -> AgenticPolicyResult:
    return AgenticPolicyResult(
        action=normalize_agentic_policy_action(action, default="allow"),
        reason=str(reason or "read_only").strip(),
        normalized_payload={
            "selector": str(selector or "").strip(),
            "query": str(query or "").strip(),
        },
        policy_name="read_only",
    )


def ssh_policy_result_from_decision(decision: Any) -> AgenticPolicyResult:
    return ssh_policy_result(
        action=str(getattr(decision, "action", "") or ""),
        reason=str(getattr(decision, "reason", "") or ""),
        command=str(getattr(decision, "normalized_command", "") or ""),
    )


def http_policy_result_from_decision(decision: Any, *, fallback_path: str = "") -> AgenticPolicyResult:
    return http_policy_result(
        action=str(getattr(decision, "action", "") or ""),
        reason=str(getattr(decision, "reason", "") or ""),
        path=str(getattr(decision, "normalized_path", "") or fallback_path),
        content=str(getattr(decision, "normalized_content", "") or ""),
    )


def guardrail_policy_result_from_decision(
    decision: Any,
    *,
    fallback_path: str = "",
    fallback_content: str = "",
    policy_name: str = "guardrail",
) -> AgenticPolicyResult:
    allowed = bool(getattr(decision, "allowed", True))
    reason = str(getattr(decision, "reason", "") or "")
    return AgenticPolicyResult(
        action="allow" if allowed else "block",
        reason=reason or ("guardrail_allow" if allowed else "guardrail_block"),
        normalized_payload={
            "path": str(fallback_path or "").strip(),
            "content": str(fallback_content or "").strip(),
        },
        policy_name=str(policy_name or "guardrail").strip() or "guardrail",
    )


def agentic_debug_line(
    label: str,
    *,
    connection_ref: str,
    fields: dict[str, Any] | None = None,
    draft: AgenticActionDraft | None = None,
    policy: AgenticPolicyResult | None = None,
) -> str:
    parts = [f"Routing Debug: {str(label or '').strip()}", f"ref={str(connection_ref or '').strip() or '-'}"]
    for key, value in dict(fields or {}).items():
        clean_key = str(key or "").strip()
        if not clean_key:
            continue
        clean_value = str(value if value is not None else "").strip() or "-"
        parts.append(f"{clean_key}={clean_value}")
    if draft is not None and policy is not None:
        parts.append("boundary=draft_policy")
    elif draft is not None:
        parts.append("boundary=draft")
    elif policy is not None:
        parts.append("boundary=policy")
    if draft is not None:
        parts.append(draft.as_debug_suffix())
    if policy is not None:
        parts.append(policy.as_debug_suffix())
    return " ".join(parts)


def agentic_runtime_debug_line(
    *,
    capability: str,
    connection_kind: str,
    connection_ref: str,
    operation: str,
    payload: dict[str, Any] | None = None,
) -> str:
    fields = {
        "kind": str(connection_kind or "").strip() or "-",
        "capability": str(capability or "").strip() or "-",
        "operation": str(operation or "").strip() or "-",
    }
    for key, value in dict(payload or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value if value is not None else "").strip()
        if clean_key and clean_value:
            fields[clean_key] = clean_value
    return agentic_debug_line(
        "agentic_runtime",
        connection_ref=connection_ref,
        fields=fields,
    )
