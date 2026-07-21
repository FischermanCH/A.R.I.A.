from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import BoundedDecisionResult
from aria.core.llm_input_contract import build_llm_input_contract


ANSWER_COMPOSER_OPERATION = "aria_answer_composer"


@dataclass(frozen=True)
class AnswerComposerInput:
    answer_mode: str
    user_prompt: str
    language: str = "de"
    outcome: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    fallback_text: str = ""
    source: str = ""
    user_id: str = ""
    request_id: str = ""


@dataclass(frozen=True)
class AnswerComposerResult:
    text: str
    usage: dict[str, int] = field(default_factory=dict)
    debug_line: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


class AnswerComposer:
    def __init__(self, llm_client: Any | None) -> None:
        self.client = BoundedDecisionClient(llm_client)

    async def compose(self, payload: AnswerComposerInput) -> AnswerComposerResult:
        answer_request = {
            "answer_mode": payload.answer_mode,
            "outcome": payload.outcome,
            "evidence": payload.evidence,
            "hard_rules": {
                "local_store_checked": "If true, never say you have no access to the user's data.",
                "empty_or_no_match": "If status is empty/no_match, say that no matching entry was found in the checked source.",
                "found": "If status is found, mention only provided source/target rows.",
                "inventory_list_format": "For answer_mode=inventory_list, keep source rows as separate markdown bullet lines.",
                "source_bound": "Answer only from outcome/evidence when evidence_policy is source_bound.",
                "inventory_scope_authority": (
                    "For host/IP inventory questions, candidate_context or requires_llm_narrowing is not complete "
                    "inventory authority. Do not present it as all configured servers or a complete list."
                ),
                "semantic_scope_authority": (
                    "If semantic_scope_authority=candidate, the metadata proves configured host/IP values but not certain group membership. "
                    "Use cautious wording such as possible matching sources."
                ),
            },
            "requested_output_schema": {
                "answer": "user-facing answer text",
                "confidence": "high|medium|low",
                "reason": "short reason grounded in the supplied evidence packet",
            },
        }
        llm_input_contract = build_llm_input_contract(
            message=payload.user_prompt,
            language=payload.language,
            user_id=payload.user_id,
            decision_task="compose_source_bound_answer",
            world_map_extensions={"answer_request": answer_request},
        )
        result = await self.client.decide_json(
            operation=ANSWER_COMPOSER_OPERATION,
            system=(
                "You are ARIA's answer composer. Use llm_input_contract as the canonical normalized input. "
                "The user-facing wording is yours, but the answer_request evidence packet is authoritative. "
                "Answer only from the supplied outcome/evidence. Do not claim missing access when ARIA checked a local store. "
                "Do not invent sources, targets, counts, commands, or memories. Keep the answer concise and operator-friendly. "
                'Return JSON only: {"answer":"...","confidence":"high|medium|low","reason":"short"}'
            ),
            payload={
                "llm_input_contract": llm_input_contract,
            },
            source=payload.source,
            user_id=payload.user_id,
            request_id=payload.request_id,
        )
        text = self._valid_answer_text(result, payload)
        if not text:
            reason = result.error or "invalid_or_guardrail_blocked"
            return AnswerComposerResult(
                text=str(payload.fallback_text or "").strip(),
                usage=result.usage,
                debug_line=f"Routing Debug: answer_composer skipped reason={reason} llm_input_contract=v1",
            )
        confidence = str(result.payload.get("confidence", "") or "").strip().lower() or "-"
        reason = " ".join(str(result.payload.get("reason", "") or "").strip().split())[:120] or "-"
        return AnswerComposerResult(
            text=text,
            usage=result.usage,
            debug_line=f"Routing Debug: answer_composer source=llm llm_input_contract=v1 confidence={confidence} reason={reason}",
        )

    def _valid_answer_text(self, result: BoundedDecisionResult, payload: AnswerComposerInput) -> str:
        if not result.ok:
            return ""
        text = self._normalize_answer_text(str(result.payload.get("answer", "") or ""))
        if not text:
            return ""
        lowered = text.lower()
        local_checked = bool(dict(payload.evidence or {}).get("local_store_checked"))
        if local_checked and any(
            phrase in lowered
            for phrase in (
                "kein zugriff",
                "keinen zugriff",
                "nicht sehen",
                "cannot access",
                "can't access",
                "do not have access",
                "don't have access",
            )
        ):
            return ""
        status = str(dict(payload.outcome or {}).get("status", "") or "").strip().lower()
        if status in {"empty", "no_match"} and self._claims_positive_match(lowered):
            return ""
        if self._unbound_inventory_network_address_completion_claim(lowered, payload):
            return ""
        if self._unbound_inventory_network_address_uncautious_claim(lowered, payload):
            return ""
        if self._semantic_scope_candidate_group_certainty(lowered, payload):
            return ""
        if not self._covers_required_inventory_hosts(text, payload):
            return ""
        return text

    @classmethod
    def _unbound_inventory_network_address_completion_claim(cls, lowered_text: str, payload: AnswerComposerInput) -> bool:
        if not cls._prompt_requests_network_address(payload.user_prompt):
            return False
        outcome = dict(payload.outcome or {})
        kind = str(outcome.get("kind", "") or "").strip().lower()
        status = str(outcome.get("status", "") or "").strip().lower()
        if "inventory" not in kind or status not in {"found", "ok", "success"}:
            return False
        scope_contract = str(outcome.get("scope_contract", "") or "").strip().lower()
        if scope_contract == "bound":
            return False
        if not (bool(outcome.get("requires_llm_narrowing")) or scope_contract in {"", "candidate_context", "unbound_metadata"}):
            return False
        return cls._claims_inventory_completeness(lowered_text)

    @staticmethod
    def _claims_inventory_completeness(lowered: str) -> bool:
        return any(
            phrase in lowered
            for phrase in (
                "complete inventory",
                "complete list",
                "all configured",
                "all servers",
                "vollständige übersicht",
                "vollstaendige uebersicht",
                "vollständige liste",
                "vollstaendige liste",
                "alle konfigurierten",
                "alle server",
            )
        )

    @classmethod
    def _unbound_inventory_network_address_uncautious_claim(cls, lowered_text: str, payload: AnswerComposerInput) -> bool:
        if not cls._prompt_requests_network_address(payload.user_prompt):
            return False
        outcome = dict(payload.outcome or {})
        kind = str(outcome.get("kind", "") or "").strip().lower()
        status = str(outcome.get("status", "") or "").strip().lower()
        if "inventory" not in kind or status not in {"found", "ok", "success"}:
            return False
        scope_contract = str(outcome.get("scope_contract", "") or "").strip().lower()
        if scope_contract == "bound":
            return False
        if not (bool(outcome.get("requires_llm_narrowing")) or scope_contract in {"", "candidate_context", "unbound_metadata"}):
            return False
        if cls._has_candidate_caution(lowered_text):
            return False
        return bool(
            cls._claims_positive_match(lowered_text)
            or re.search(r"\bich\s+habe\s+(?:\*\*)?\d+\b", lowered_text)
            or re.search(r"\bi\s+(?:found|loaded)\s+\d+\b", lowered_text)
            or re.search(r"\b\d+\s+(?:ssh|sftp|server|servern|servers|verbindungen|connections)\b", lowered_text)
        )

    @staticmethod
    def _has_candidate_caution(lowered: str) -> bool:
        return any(
            phrase in lowered
            for phrase in (
                "mögliche",
                "moegliche",
                "möglicherweise",
                "moeglicherweise",
                "possible",
                "possibly",
                "candidate",
                "candidates",
                "kandidat",
                "kandidaten",
                "keine vertraglich gebundene",
                "not complete inventory authority",
            )
        )

    @staticmethod
    def _semantic_scope_candidate_group_certainty(lowered: str, payload: AnswerComposerInput) -> bool:
        outcome = dict(payload.outcome or {})
        if str(outcome.get("semantic_scope_authority", "") or "").strip().lower() != "candidate":
            return False
        return any(
            phrase in lowered
            for phrase in (
                "passende konfigurierte quellen",
                "matching configured sources",
                "these are the",
                "das sind die",
                "sind die dev",
                "are the dev",
            )
        )

    @classmethod
    def _covers_required_inventory_hosts(cls, text: str, payload: AnswerComposerInput) -> bool:
        if not cls._prompt_requests_network_address(payload.user_prompt):
            return True
        outcome = dict(payload.outcome or {})
        kind = str(outcome.get("kind", "") or "").strip().lower()
        status = str(outcome.get("status", "") or "").strip().lower()
        if "inventory" not in kind or status not in {"found", "ok", "success"}:
            return True
        scope_contract = str(outcome.get("scope_contract", "") or "").strip().lower()
        bound_refs = [str(ref or "").strip() for ref in list(outcome.get("bound_refs", []) or []) if str(ref or "").strip()]
        if scope_contract != "bound" and not bound_refs:
            return True
        requirements = cls._inventory_host_requirements(outcome.get("sources"))
        if bound_refs:
            bound_ref_set = set(bound_refs)
            requirements = [(ref, host) for ref, host in requirements if ref in bound_ref_set]
        if not requirements:
            return True
        normalized = cls._normalize_for_coverage(text)
        for ref, host in requirements:
            if cls._normalize_for_coverage(ref) not in normalized:
                return False
            if cls._normalize_for_coverage(host) not in normalized:
                return False
        return True

    @staticmethod
    def _prompt_requests_network_address(prompt: str) -> bool:
        return bool(
            re.search(
                r"\b(?:ip|ips|ip-adresse|ip-adressen|adresse|adressen|address|addresses|host|hosts|hostname|hostnames)\b",
                str(prompt or "").lower(),
            )
        )

    @classmethod
    def _inventory_host_requirements(cls, sources: Any) -> list[tuple[str, str]]:
        if not isinstance(sources, list):
            return []
        requirements: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for source in sources:
            if not isinstance(source, dict):
                continue
            items = source.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                ref = str(item.get("ref", "") or "").strip()
                host = str(item.get("host", "") or "").strip()
                if not ref or not host:
                    continue
                key = (ref, host)
                if key in seen:
                    continue
                seen.add(key)
                requirements.append(key)
        return requirements

    @staticmethod
    def _normalize_for_coverage(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    @staticmethod
    def _claims_positive_match(lowered: str) -> bool:
        return any(
            phrase in lowered
            for phrase in (
                "ich habe passende",
                "ich habe gefunden",
                "gefunden:",
                "i found matching",
                "i found this",
                "yes,",
                "ja,",
            )
        )

    @staticmethod
    def _normalize_answer_text(value: str) -> str:
        lines = [" ".join(line.strip().split()) for line in str(value or "").strip().splitlines()]
        return "\n".join(line for line in lines if line).strip()
