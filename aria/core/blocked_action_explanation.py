from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aria.core.i18n import I18NStore

_BLOCKED_ACTION_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _blocked_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    lang = "de" if str(language or "").strip().lower().startswith("de") else "en"
    template = _BLOCKED_ACTION_I18N.t(lang, f"blocked_action_explanation.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class BlockedActionExplanation:
    text: str
    debug_line: str
    used_llm: bool = False


def guardrail_config_link(guardrail_ref: str, language: str | None = None) -> str:
    clean_ref = str(guardrail_ref or "").strip()
    if not clean_ref:
        return ""
    href = f"/config/security?guardrail_ref={quote(clean_ref, safe='')}"
    label = _blocked_text(
        language,
        "guardrail_link_label",
        "Review/change guardrail",
    )
    return f"{label}: [{clean_ref}]({href}) ({href})"


def security_guardrails_link(language: str | None = None) -> str:
    href = "/config/security"
    label = _blocked_text(
        language,
        "security_link_label",
        "Review security rules",
    )
    target = _blocked_text(
        language,
        "security_link_target",
        "Security Guardrails",
    )
    return f"{label}: [{target}]({href}) ({href})"


def _guardrail_block_fallback_text(*, target: str, guardrail_ref: str, language: str | None) -> str:
    clean_ref = str(guardrail_ref or "").strip()
    if not clean_ref:
        return ""
    clean_target = str(target or "").strip()
    if clean_target:
        return _blocked_text(
            language,
            "guardrail_block_summary_target",
            "The action on `{target}` was blocked by Guardrail profile `{guardrail_ref}`. This is an active security rule, not a technical execution error.",
            target=clean_target,
            guardrail_ref=clean_ref,
        )
    return _blocked_text(
        language,
        "guardrail_block_summary",
        "The action was blocked by Guardrail profile `{guardrail_ref}`. This is an active security rule, not a technical execution error.",
        guardrail_ref=clean_ref,
    )


def _clean_llm_text(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith(("text", "markdown")):
            text = text.split("\n", 1)[-1].strip()
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _ascii_fold_german(value: str) -> str:
    return str(value or "").translate(
        {
            0x00E4: "ae",
            0x00F6: "oe",
            0x00FC: "ue",
            0x00C4: "Ae",
            0x00D6: "Oe",
            0x00DC: "Ue",
            0x00DF: "ss",
        }
    )


def _normalize_for_presence(value: str) -> str:
    text = _ascii_fold_german(value).lower()
    text = text.replace("`", " ").replace("*", " ")
    return " ".join(text.split())


def _preview_presence_terms(preview: str) -> list[str]:
    clean = str(preview or "").strip()
    if not clean:
        return []
    terms = [clean]
    if ":" in clean:
        tail = clean.split(":", 1)[1].strip()
        if tail:
            terms.append(tail)
    return [
        term
        for term in terms
        if len(_normalize_for_presence(term)) >= 4
    ]


def _text_already_mentions_preview(text: str, preview: str) -> bool:
    haystack = _normalize_for_presence(text)
    return any(_normalize_for_presence(term) in haystack for term in _preview_presence_terms(preview))


def _strip_weak_guardrail_link_lines(text: str, *, guardrail_ref: str, language: str | None) -> str:
    clean_ref = str(guardrail_ref or "").strip()
    if not clean_ref:
        return str(text or "").strip()
    label = _blocked_text(language, "guardrail_link_label", "Review/change guardrail")
    normalized_label = _normalize_for_presence(label)
    normalized_ref = _normalize_for_presence(clean_ref)
    kept: list[str] = []
    for line in str(text or "").splitlines():
        normalized = _normalize_for_presence(line)
        if normalized.startswith(normalized_label) and normalized_ref in normalized and "/config/security" not in line:
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def _looks_like_safe_block_explanation(text: str) -> bool:
    clean = " ".join(_ascii_fold_german(str(text or "")).lower().split())
    if len(clean) < 24 or len(clean) > 1400:
        return False
    block_markers = (
        "nicht ausfuehren",
        "kann diese aktion nicht",
        "cannot execute",
        "can't execute",
        "is blocked",
        "wurde blockiert",
        "blockiert",
        "guardrail",
    )
    if not any(marker in clean for marker in block_markers):
        return False
    unsafe_suggestions = (
        "trotzdem ausfuehren",
        "force execute",
        "run it anyway",
        "ignore the guardrail",
        "guardrail umgehen",
        "policy umgehen",
    )
    return not any(marker in clean for marker in unsafe_suggestions)


def _ensure_context_lines(
    *,
    text: str,
    preview: str,
    guardrail_ref: str,
    language: str | None,
    review_link_kind: str = "",
) -> str:
    base_text = _strip_weak_guardrail_link_lines(text, guardrail_ref=guardrail_ref, language=language)
    lines = [base_text]
    clean_preview = str(preview or "").strip()
    if clean_preview and not _text_already_mentions_preview(base_text, clean_preview):
        planned = _blocked_text(
            language,
            "planned_action",
            "Planned action: {preview}",
            preview=clean_preview,
        )
        lines.append(planned)
    link = guardrail_config_link(guardrail_ref, language)
    if not link and str(review_link_kind or "").strip() == "ssh_policy":
        link = security_guardrails_link(language)
    if link and "/config/security" not in "\n".join(lines):
        lines.append(link)
    return "\n\n".join(line for line in lines if line).strip()


def _fallback_debug(reason: str) -> str:
    clean = str(reason or "fallback").strip().replace(" ", "_") or "fallback"
    return (
        "Routing Debug: blocked_action_explanation "
        f"agentic_source=deterministic_fallback reason={clean} boundary=policy_guardrail_decision"
    )


async def explain_blocked_action(
    *,
    llm_client: Any | None,
    user_message: str,
    fallback_text: str,
    language: str | None,
    user_id: str,
    request_id: str,
    target: str,
    preview: str,
    capability: str,
    policy_reason: str,
    policy_reason_label: str,
    guardrail_ref: str = "",
    guardrail_kind: str = "",
    guardrail_text: str = "",
    timeout_seconds: float = 4.0,
    skip_llm_reason: str = "",
    review_link_kind: str = "",
) -> BlockedActionExplanation:
    fallback_source = _guardrail_block_fallback_text(
        target=target,
        guardrail_ref=guardrail_ref,
        language=language,
    ) or str(fallback_text or "").strip()
    fallback = _ensure_context_lines(
        text=fallback_source,
        preview=preview,
        guardrail_ref=guardrail_ref,
        language=language,
        review_link_kind=review_link_kind,
    )
    if skip_llm_reason:
        return BlockedActionExplanation(text=fallback, debug_line=_fallback_debug(skip_llm_reason))
    if llm_client is None:
        return BlockedActionExplanation(text=fallback, debug_line=_fallback_debug("llm_client_missing"))

    lang = "de" if str(language or "").strip().lower().startswith("de") else "en"
    link = guardrail_config_link(guardrail_ref, language)
    if not link and str(review_link_kind or "").strip() == "ssh_policy":
        link = security_guardrails_link(language)
    system = (
        "You write the user-facing explanation for an ARIA action that has already been blocked by policy/guardrails. "
        "Never change or question the decision. Never suggest bypassing policy. "
        "Be concise, factual, and helpful. Mention the target and planned action when available. "
        "If a guardrail link is provided, include it exactly. Return plain text only."
    )
    user = "\n".join(
        [
            f"language: {lang}",
            f"user_message: {user_message}",
            f"target: {target}",
            f"planned_action: {preview}",
            f"capability: {capability}",
            f"policy_reason: {policy_reason}",
            f"policy_reason_label: {policy_reason_label}",
            f"guardrail_ref: {guardrail_ref}",
            f"guardrail_kind: {guardrail_kind}",
            f"guardrail_text: {guardrail_text}",
            f"guardrail_link: {link}",
            "required_meaning: ARIA cannot execute this action because the active policy/guardrail blocks it.",
        ]
    )
    try:
        response = await asyncio.wait_for(
            llm_client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                source="routing",
                operation="blocked_action_explanation",
                user_id=user_id,
                request_id=request_id,
            ),
            timeout=max(0.05, float(timeout_seconds or 4.0)),
        )
    except asyncio.TimeoutError:
        return BlockedActionExplanation(text=fallback, debug_line=_fallback_debug("llm_timeout"))
    except Exception:  # noqa: BLE001 - explanation must never break the policy block path.
        return BlockedActionExplanation(text=fallback, debug_line=_fallback_debug("llm_error"))

    text = _clean_llm_text(str(getattr(response, "content", "") or ""))
    if not _looks_like_safe_block_explanation(text):
        return BlockedActionExplanation(text=fallback, debug_line=_fallback_debug("llm_unusable"))

    text = _ensure_context_lines(
        text=text,
        preview=preview,
        guardrail_ref=guardrail_ref,
        language=language,
        review_link_kind=review_link_kind,
    )
    return BlockedActionExplanation(
        text=text,
        debug_line=(
            "Routing Debug: blocked_action_explanation "
            "agentic_source=llm_decision confidence=bounded boundary=policy_guardrail_decision"
        ),
        used_llm=True,
    )
