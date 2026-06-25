from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from aria.core.chat_context_filter import explicitly_requests_local_context
from aria.core.chat_context_filter import looks_like_general_knowledge_or_howto_request
from aria.core.llm_client import LLMClientError
from aria.core.text_utils import extract_json_object


@dataclass(frozen=True)
class ChatFreshnessDecision:
    needs_fresh_context: bool
    query: str = ""
    reason: str = ""
    confidence: str = ""
    source: str = "none"
    raw_response: str = ""


_CURRENTNESS_TERMS = (
    "aktuell",
    "aktuelle",
    "aktueller",
    "momentan",
    "derzeit",
    "heute",
    "neuste",
    "neueste",
    "letzte version",
    "latest",
    "current",
    "newest",
    "most recent",
    "release",
    "changelog",
    "version",
)

_TECH_PRODUCT_TERMS = (
    "openai",
    "codex",
    "claude",
    "anthropic",
    "github",
    "docker",
    "debian",
    "ubuntu",
    "python",
    "npm",
    "node",
    "qdrant",
    "searxng",
    "api",
    "sdk",
    "cli",
    "package",
    "paket",
    "install",
    "installation",
)


_EXPLICIT_WEB_RESEARCH_PATTERNS = (
    r"\b(?:recherchier(?:e|en)?|such(?:e|en)?|suche|suchen)\b.*\b(?:internet|web|online)\b",
    r"\b(?:internet|web|online)\b.*\b(?:recherchier(?:e|en)?|such(?:e|en)?|suche|suchen)\b",
    r"\b(?:search|research|look\s+up|browse)\b.*\b(?:internet|web|online)\b",
    r"\b(?:internet|web|online)\b.*\b(?:search|research|look\s+up|browse)\b",
)

_URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+", flags=re.IGNORECASE)


def explicitly_requests_web_research(message: str) -> bool:
    clean = re.sub(r"\s+", " ", str(message or "").strip().lower())
    if not clean:
        return False
    if explicitly_requests_local_context(clean):
        return False
    return any(re.search(pattern, clean, flags=re.IGNORECASE) for pattern in _EXPLICIT_WEB_RESEARCH_PATTERNS)


def _fallback_query(message: str) -> str:
    clean = re.sub(r"\s+", " ", str(message or "").strip())
    if not clean:
        return ""
    cleanup_patterns = (
        r"\b(?:bitte|please)\b",
        r"\b(?:im|in|on\s+the)\s+(?:internet|web)\b",
        r"\b(?:online)\b",
        r"\b(?:recherchier(?:e|en)?|such(?:e|en)?|suche|suchen|search|research|look\s+up|browse)\b",
    )
    query = clean
    for pattern in cleanup_patterns:
        query = re.sub(pattern, " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" .,:;!?")
    return query or clean


def chat_freshness_candidate(message: str, *, intents: list[str] | None = None) -> bool:
    clean = re.sub(r"\s+", " ", str(message or "").strip().lower())
    if not clean:
        return False
    if explicitly_requests_local_context(clean):
        return False
    if "web_search" in set(intents or []):
        return False
    if _URL_PATTERN.search(str(message or "")):
        return True
    if explicitly_requests_web_research(clean):
        return True
    if any(term in clean for term in _CURRENTNESS_TERMS):
        return True
    if looks_like_general_knowledge_or_howto_request(clean) and any(term in clean for term in _TECH_PRODUCT_TERMS):
        return True
    return False


def _fallback_decision(message: str, *, reason: str = "") -> ChatFreshnessDecision:
    clean = re.sub(r"\s+", " ", str(message or "").strip())
    lowered = clean.lower()
    needs = chat_freshness_candidate(clean)
    if needs:
        if explicitly_requests_web_research(clean):
            fallback_reason = "user explicitly requested web research"
        elif any(term in lowered for term in _CURRENTNESS_TERMS):
            fallback_reason = "question asks for current version/release/status information"
        else:
            fallback_reason = "technical product/setup question may depend on current external documentation"
        return ChatFreshnessDecision(
            needs_fresh_context=True,
            query=_fallback_query(clean),
            reason=reason or fallback_reason,
            confidence="medium",
            source="heuristic",
        )
    return ChatFreshnessDecision(
        needs_fresh_context=False,
        query="",
        reason=reason or "no current external product information required",
        confidence="low",
        source="heuristic",
    )


def _coerce_decision(payload: dict[str, Any], *, message: str, raw_response: str, source: str) -> ChatFreshnessDecision:
    needs = bool(payload.get("needs_fresh_context") or payload.get("needs_web") or payload.get("web_search"))
    query = str(payload.get("query", "") or payload.get("search_query", "") or "").strip()
    if needs and not query:
        query = re.sub(r"\s+", " ", str(message or "").strip())
    confidence = str(payload.get("confidence", "") or "").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium" if needs else "low"
    return ChatFreshnessDecision(
        needs_fresh_context=needs,
        query=query,
        reason=str(payload.get("reason", "") or "").strip(),
        confidence=confidence,
        source=source,
        raw_response=raw_response,
    )


async def decide_chat_freshness(
    *,
    message: str,
    intents: list[str],
    llm_client: Any | None,
    language: str | None = None,
    source: str = "",
    user_id: str = "",
    request_id: str = "",
) -> ChatFreshnessDecision:
    if "web_search" in set(intents or []):
        return ChatFreshnessDecision(
            needs_fresh_context=False,
            reason="web search already selected",
            confidence="low",
            source="none",
        )
    if explicitly_requests_local_context(message):
        return ChatFreshnessDecision(
            needs_fresh_context=False,
            reason="local context explicitly requested",
            confidence="low",
            source="none",
        )
    if llm_client is None:
        if not chat_freshness_candidate(message, intents=intents):
            return ChatFreshnessDecision(
                needs_fresh_context=False,
                reason="not a freshness candidate",
                confidence="low",
                source="none",
            )
        return _fallback_decision(message, reason="LLM freshness arbiter unavailable")

    system = (
        "You are a narrow freshness arbiter for ARIA. Decide whether a normal chat question "
        "needs current external web/documentation sources before answering. "
        "Choose true for current versions, release notes, API/SDK/CLI behavior, product status, "
        "installation paths, prices, provider docs, or software packages. "
        "Also choose true when the user explicitly asks you to search, browse, look up, or research "
        "something on the internet/web, even if the topic is not time-sensitive. "
        "Choose false for stable general knowledge, local note/document questions, casual chat, writing help, "
        "or opinions that do not depend on current external facts. "
        "For current version or latest release questions, make the query source-seeking: include "
        "the product/package name plus words like official, changelog, releases, package registry, "
        "GitHub releases, npm, PyPI, or vendor docs when they fit. Avoid generic news-only queries. "
        "Return JSON only."
    )
    user_template = (
        "User question:\n{message}\n\n"
        "Return JSON with this schema:\n"
        '{{"needs_fresh_context":true|false,"query":"short search query or empty",'
        '"confidence":"low|medium|high","reason":"brief"}}'
    )
    user = user_template.format(message=str(message or "").strip())
    try:
        response = await llm_client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            source=source,
            operation="chat_freshness_arbitration",
            user_id=user_id,
            request_id=request_id,
        )
    except LLMClientError as exc:
        return _fallback_decision(message, reason=f"LLM freshness arbiter failed: {exc}")
    raw = str(getattr(response, "content", "") or "").strip()
    payload = extract_json_object(raw)
    if not isinstance(payload, dict):
        try:
            parsed = json.loads(raw)
            payload = parsed if isinstance(parsed, dict) else None
        except Exception:
            payload = None
    if not isinstance(payload, dict):
        return _fallback_decision(message, reason="LLM freshness arbiter returned no JSON")
    return _coerce_decision(payload, message=message, raw_response=raw, source="llm")


def format_chat_freshness_debug(decision: ChatFreshnessDecision) -> str:
    status = "web_search" if decision.needs_fresh_context else "chat_only"
    parts = [
        "Routing Debug: chat_freshness",
        f"action={status}",
        f"source={decision.source or '-'}",
    ]
    if decision.confidence:
        parts.append(f"confidence={decision.confidence}")
    if decision.query:
        parts.append(f"query={decision.query}")
    if decision.reason:
        parts.append(f"reason={decision.reason}")
    return " ".join(parts)
