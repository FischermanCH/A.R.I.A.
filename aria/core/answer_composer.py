from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import BoundedDecisionResult


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
        result = await self.client.decide_json(
            operation=ANSWER_COMPOSER_OPERATION,
            system=(
                "You are ARIA's answer composer. The user-facing wording is yours, but the evidence packet is authoritative. "
                "Answer only from the supplied outcome/evidence. Do not claim missing access when ARIA checked a local store. "
                "Do not invent sources, targets, counts, commands, or memories. Keep the answer concise and operator-friendly. "
                'Return JSON only: {"answer":"...","confidence":"high|medium|low","reason":"short"}'
            ),
            payload={
                "language": payload.language,
                "answer_mode": payload.answer_mode,
                "user_prompt": payload.user_prompt,
                "outcome": payload.outcome,
                "evidence": payload.evidence,
                "hard_rules": {
                    "local_store_checked": "If true, never say you have no access to the user's data.",
                    "empty_or_no_match": "If status is empty/no_match, say that no matching entry was found in the checked source.",
                    "found": "If status is found, mention only provided source/target rows.",
                },
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
                debug_line=f"Routing Debug: answer_composer skipped reason={reason}",
            )
        confidence = str(result.payload.get("confidence", "") or "").strip().lower() or "-"
        reason = " ".join(str(result.payload.get("reason", "") or "").strip().split())[:120] or "-"
        return AnswerComposerResult(
            text=text,
            usage=result.usage,
            debug_line=f"Routing Debug: answer_composer source=llm confidence={confidence} reason={reason}",
        )

    def _valid_answer_text(self, result: BoundedDecisionResult, payload: AnswerComposerInput) -> str:
        if not result.ok:
            return ""
        text = " ".join(str(result.payload.get("answer", "") or "").strip().split())
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
        return text

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
