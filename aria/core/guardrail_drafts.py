from __future__ import annotations

import json
import re
from typing import Any

from aria.core.connection_action_contract import connection_action_manifest_rows
from aria.core.guardrails import (
    GUARDRAIL_CATALOG,
    guardrail_kind_options,
    normalize_guardrail_connection_kinds,
    normalize_guardrail_kind,
)
from aria.core.text_utils import extract_json_object


_MAX_TERMS = 32
_MAX_TERM_LEN = 120


def _clean_text(value: Any, *, max_len: int = 400) -> str:
    return " ".join(str(value or "").split()).strip()[:max_len]


def _clean_ref(value: Any, fallback: str = "ki-guardrail") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return (text or fallback)[:64]


def _clean_terms(value: Any) -> list[str]:
    if isinstance(value, str):
        source = re.split(r"[\n,]+", value)
    elif isinstance(value, list):
        source = value
    else:
        source = []
    rows: list[str] = []
    seen: set[str] = set()
    for item in source:
        text = " ".join(str(item or "").split()).strip().lower()
        if not text:
            continue
        text = text[:_MAX_TERM_LEN]
        if text in seen:
            continue
        seen.add(text)
        rows.append(text)
        if len(rows) >= _MAX_TERMS:
            break
    return rows


def guardrail_connection_kind_options() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [{"value": "", "label": "Auto / passend zum Guardrail-Typ"}]
    seen: set[str] = set()
    for kind in guardrail_kind_options():
        spec = GUARDRAIL_CATALOG.get(kind, {})
        for connection_kind in sorted(spec.get("connection_kinds", set())):
            if connection_kind in seen:
                continue
            seen.add(connection_kind)
            rows.append({"value": connection_kind, "label": connection_kind.replace("_", " ").upper()})
    return rows


def build_guardrail_draft_context(raw_config: dict[str, Any], *, guardrail_kind: str = "", connection_kind: str = "") -> dict[str, Any]:
    clean_guardrail_kind = normalize_guardrail_kind(guardrail_kind or "ssh_command")
    if clean_guardrail_kind not in guardrail_kind_options():
        clean_guardrail_kind = "ssh_command"
    clean_connection_kind = str(connection_kind or "").strip().lower().replace("-", "_")
    guardrail_spec = GUARDRAIL_CATALOG.get(clean_guardrail_kind, {})
    compatible_kinds = sorted(str(item) for item in guardrail_spec.get("connection_kinds", set()))
    if clean_connection_kind and clean_connection_kind not in compatible_kinds:
        clean_connection_kind = ""

    raw_connections = raw_config.get("connections", {})
    connection_rows: list[dict[str, Any]] = []
    if isinstance(raw_connections, dict):
        for kind, rows in raw_connections.items():
            clean_kind = str(kind or "").strip().lower().replace("-", "_")
            if compatible_kinds and clean_kind not in compatible_kinds:
                continue
            if clean_connection_kind and clean_kind != clean_connection_kind:
                continue
            if not isinstance(rows, dict):
                continue
            connection_rows.append({"kind": clean_kind, "count": len(rows), "refs": sorted(str(ref) for ref in rows.keys())[:8]})

    security = raw_config.get("security", {})
    existing: list[dict[str, Any]] = []
    guardrails = security.get("guardrails", {}) if isinstance(security, dict) else {}
    if isinstance(guardrails, dict):
        for ref, profile in sorted(guardrails.items()):
            if not isinstance(profile, dict):
                continue
            kind = normalize_guardrail_kind(str(profile.get("kind", "") or "ssh_command"))
            if kind != clean_guardrail_kind:
                continue
            existing.append(
                {
                    "ref": str(ref),
                    "title": _clean_text(profile.get("title"), max_len=120),
                    "description": _clean_text(profile.get("description"), max_len=200),
                    "connection_kinds": normalize_guardrail_connection_kinds(profile.get("connection_kinds"), guardrail_kind=kind),
                    "allow_terms": _clean_terms(profile.get("allow_terms"))[:12],
                    "deny_terms": _clean_terms(profile.get("deny_terms"))[:12],
                }
            )

    contracts = [
        row
        for row in connection_action_manifest_rows()
        if str(row.get("guardrail_kind", "") or "").strip() == clean_guardrail_kind
    ]
    return {
        "guardrail_kind": clean_guardrail_kind,
        "guardrail_label": str(guardrail_spec.get("label") or clean_guardrail_kind),
        "connection_kind": clean_connection_kind,
        "compatible_connection_kinds": compatible_kinds,
        "connection_rows": connection_rows,
        "existing_guardrails": existing[:8],
        "action_contracts": contracts,
        "engine_semantics": {
            "allow_terms": "If allow_terms is non-empty, at least one term must match the requested action text.",
            "deny_terms": "If any deny term matches, the action is blocked before allow_terms are considered.",
            "matching": "Terms are normalized plain text matches, not regex patterns.",
        },
    }


def normalize_guardrail_draft(payload: dict[str, Any], *, fallback_kind: str = "ssh_command") -> dict[str, Any]:
    clean_kind = normalize_guardrail_kind(str(payload.get("kind", "") or fallback_kind))
    if clean_kind not in guardrail_kind_options():
        clean_kind = normalize_guardrail_kind(fallback_kind or "ssh_command")
    if clean_kind not in guardrail_kind_options():
        clean_kind = "ssh_command"
    connection_kinds = normalize_guardrail_connection_kinds(payload.get("connection_kinds"), guardrail_kind=clean_kind)
    title = _clean_text(payload.get("title"), max_len=160) or "KI Guardrail Vorschlag"
    ref = _clean_ref(payload.get("ref") or title, fallback=f"{clean_kind}-draft")
    examples = payload.get("examples", [])
    clean_examples: list[dict[str, str]] = []
    if isinstance(examples, list):
        for example in examples[:6]:
            if not isinstance(example, dict):
                continue
            clean_examples.append(
                {
                    "text": _clean_text(example.get("text"), max_len=160),
                    "expected": _clean_text(example.get("expected"), max_len=32),
                    "reason": _clean_text(example.get("reason"), max_len=180),
                }
            )
    notes = payload.get("review_notes", [])
    if isinstance(notes, str):
        notes = [notes]
    clean_notes = [_clean_text(item, max_len=180) for item in notes[:6] if _clean_text(item, max_len=180)]
    try:
        confidence = float(payload.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "ref": ref,
        "kind": clean_kind,
        "connection_kinds": connection_kinds,
        "title": title,
        "description": _clean_text(payload.get("description"), max_len=600),
        "allow_terms": _clean_terms(payload.get("allow_terms")),
        "deny_terms": _clean_terms(payload.get("deny_terms")),
        "scope_summary": _clean_text(payload.get("scope_summary"), max_len=400),
        "review_notes": clean_notes,
        "examples": clean_examples,
        "confidence": max(0.0, min(confidence, 1.0)),
        "source": "llm_guardrail_draft",
    }


async def suggest_guardrail_with_llm(
    *,
    llm_client: Any | None,
    instruction: str,
    draft_context: dict[str, Any],
    language: str = "de",
    user_id: str = "system",
    request_id: str = "",
) -> dict[str, Any]:
    clean_instruction = _clean_text(instruction, max_len=1200)
    if not clean_instruction:
        raise ValueError("Describe what this guardrail should allow or block first.")
    if llm_client is None:
        raise ValueError("LLM client is unavailable.")

    lang_name = "German" if str(language or "de").lower().startswith("de") else "English"
    guardrail_kind = str(draft_context.get("guardrail_kind") or "ssh_command")
    messages = [
        {
            "role": "system",
            "content": (
                "You create security guardrail drafts for ARIA. "
                "You only draft; the user must review and save manually. "
                "Return ONLY JSON. No markdown. No prose outside JSON. "
                "Use plain text terms, not regex. Do not invent secrets, hosts, credentials, or live results."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Language for user-facing fields: {lang_name}\n"
                f"User instruction: {clean_instruction}\n\n"
                "Guardrail engine semantics and available context:\n"
                f"{json.dumps(draft_context, ensure_ascii=False, sort_keys=True)}\n\n"
                "Return this JSON shape:\n"
                "{"
                "\"ref\":\"short-kebab-ref\","
                "\"kind\":\"one provided guardrail_kind\","
                "\"connection_kinds\":[\"optional exact connection kind such as sftp or smb\"],"
                "\"title\":\"short title\","
                "\"description\":\"what this draft protects\","
                "\"allow_terms\":[\"plain term\"],"
                "\"deny_terms\":[\"plain term\"],"
                "\"scope_summary\":\"where this should be attached\","
                "\"review_notes\":[\"what the user must verify\"],"
                "\"examples\":[{\"text\":\"example request/action\",\"expected\":\"allow|block\",\"reason\":\"why\"}],"
                "\"confidence\":0.0"
                "}\n"
                "Important: If the user only asks to block something, keep allow_terms empty unless they explicitly "
                "also request an allow-list. For SSH, never suggest shell wildcards as terms."
            ),
        },
    ]
    response = await llm_client.chat(
        messages,
        source="guardrail_draft",
        operation=f"draft_{guardrail_kind}",
        user_id=user_id,
        request_id=request_id,
    )
    payload = extract_json_object(str(getattr(response, "content", "") or "")) or {}
    if not payload:
        raise ValueError("The LLM did not return a usable guardrail draft.")
    return normalize_guardrail_draft(payload, fallback_kind=guardrail_kind)
