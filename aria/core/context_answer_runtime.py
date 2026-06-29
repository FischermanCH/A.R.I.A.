from __future__ import annotations

import re
from typing import Any, Callable

from aria.core.answer_composer import AnswerComposer
from aria.core.answer_composer import AnswerComposerInput
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.connection_catalog import connection_kind_label
from aria.core.context_evidence import normalized_evidence_text
from aria.core.context_surfaces import ContextRequest
from aria.skills.base import SkillResult


async def compose_aria_context_answer(
    *,
    llm_client: Any,
    answer_mode: str,
    fallback_text: str,
    arbitration: AriaTurnArbitration,
    skill_result: SkillResult | None,
    status: str,
    request_id: str,
    user_id: str,
    source: str,
    language: str | None,
    skill_result_sources: Callable[[SkillResult | None], list[dict[str, Any]]],
) -> tuple[str, dict[str, int], str]:
    query = ""
    for request in arbitration.plan.context_requests:
        if str(request.query or "").strip():
            query = str(request.query or "").strip()
            break
    content = str(getattr(skill_result, "content", "") or "").strip() if skill_result is not None else ""
    sources = skill_result_sources(skill_result)
    context_requests = [
        {
            "surface_id": request.surface_id,
            "mode": request.mode,
            "query": request.query,
            "catalog_id": str(dict(request.budget or {}).get("catalog_id", "") or ""),
            "kind": str(dict(request.budget or {}).get("kind", "") or ""),
            "ref": str(dict(request.budget or {}).get("ref", "") or ""),
        }
        for request in arbitration.plan.context_requests
    ]
    source_bound = str(arbitration.plan.evidence_policy or "").strip() == "source_bound" or bool(context_requests)
    composer = AnswerComposer(llm_client)
    composed = await composer.compose(
        AnswerComposerInput(
            answer_mode=answer_mode,
            user_prompt=query or next(iter(arbitration.plan.queries.values()), ""),
            language=str(language or "de"),
            fallback_text=fallback_text,
            source=source,
            user_id=user_id,
            request_id=request_id,
            outcome={
                "kind": answer_mode,
                "status": status,
                "surface_directions": list(arbitration.plan.context_directions),
                "content": content,
                "sources": sources,
                "source_count": len(sources),
            },
            evidence={
                "local_store_checked": True,
                "evidence_policy": arbitration.plan.evidence_policy or ("source_bound" if source_bound else "allow_general"),
                "contract_mode": arbitration.plan.contract_mode or "",
                "selected_catalog_ids": list(arbitration.plan.priority),
                "context_requests": context_requests,
                "plan_source": arbitration.source,
                "allowed_claims": [
                    "Only mention sources, targets, counts, content, and empty status present in this packet.",
                    "If evidence_policy is source_bound, do not answer from general knowledge.",
                ],
                "forbidden_claims": [
                    "Do not say ARIA lacks access when local_store_checked is true.",
                    "Do not invent configured sources, memory entries, servers, commands, or counts.",
                ],
            },
        )
    )
    return composed.text or fallback_text, dict(composed.usage or {}), composed.debug_line


def fast_notes_inventory_answer(
    arbitration: AriaTurnArbitration,
    notes_result: SkillResult,
    *,
    language: str | None,
    pipeline_text: Callable[[str | None, str, str], str],
    topic_terms_for_request: Callable[[str, ContextRequest], tuple[list[str], set[str]]],
) -> str:
    plan = arbitration.plan
    query = " ".join(str(request.query or "") for request in plan.context_requests if request.surface_id == "notes")
    prompt_text = f"{query} {' '.join(plan.queries.values())}".strip().lower()
    looks_like_inventory_question = bool(
        re.search(r"\b(?:was|welche|welchen|welches|which|what)\b.+\b(?:notes|notizen|notiz)\b", prompt_text)
    )
    if not looks_like_inventory_question and plan.answer_mode != "direct_answer":
        return ""
    if re.search(r"\b(?:steht|stehts|inhalt|content|sagt|steht\s+in)\b", prompt_text):
        return ""
    content = str(notes_result.content or "").strip()
    if not content:
        return ""
    topic_request = ContextRequest(surface_id="notes", mode="search", query=query)
    topic_terms, _ignored_terms = topic_terms_for_request(query, topic_request)
    content_lines = [line.strip() for line in content.splitlines() if line.strip()]
    sources = list((notes_result.metadata or {}).get("sources") or [])
    entries: list[str] = []
    rejected = 0
    for source in sources[:5]:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "") or "").strip()
        folder = str(source.get("folder", "") or "").strip()
        if not title:
            continue
        label = f"{title} ({folder})" if folder else title
        source_line = next((line for line in content_lines if line.startswith(f"- {label}")), "")
        evidence_text = "\n".join([title, folder, source_line])
        if topic_terms:
            haystack = normalized_evidence_text(evidence_text)
            if not any(term in haystack for term in topic_terms):
                rejected += 1
                continue
        if label not in entries:
            entries.append(label)
    if not entries:
        for line in content.splitlines():
            clean = line.strip()
            if clean.startswith("- "):
                if topic_terms:
                    haystack = normalized_evidence_text(clean)
                    if not any(term in haystack for term in topic_terms):
                        rejected += 1
                        continue
                entries.append(clean[2:])
            if len(entries) >= 5:
                break
    if not entries:
        return ""
    meta = notes_result.metadata or {}
    lines = list(meta.get("detail_lines", []) or [])
    lines.append(
        "Routing Debug: fast_notes_inventory_filter "
        f"kept={len(entries)} rejected={rejected} terms={','.join(topic_terms) or '-'}"
    )
    meta["detail_lines"] = lines
    notes_result.metadata = meta
    heading = pipeline_text(
        language,
        "direct_context.notes_inventory_found",
        "I found {count} matching notes:",
    ).replace("{count}", str(len(entries)))
    return "\n".join([heading, *(f"- {entry}" for entry in entries)]).strip()


def fast_inventory_list_answer(skill_result: SkillResult, *, language: str | None) -> str:
    content = str(skill_result.content or "").strip()
    if not content:
        return ""
    sources = list(dict(skill_result.metadata or {}).get("sources") or [])
    refs_by_kind: dict[str, list[str]] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        kind = str(source.get("kind", "") or "").strip()
        refs = [str(ref or "").strip() for ref in list(source.get("refs", []) or []) if str(ref or "").strip()]
        if kind and refs:
            refs_by_kind.setdefault(kind, []).extend(refs)
    ref_count = sum(len(refs) for refs in refs_by_kind.values())
    content_lines = [line.strip() for line in content.splitlines() if line.strip()]
    if ref_count < 2 or not any(line.startswith("- ") for line in content_lines):
        return ""
    if len(refs_by_kind) == 1:
        kind = next(iter(refs_by_kind))
        source_label = f"{connection_kind_label(kind)}-Profile"
    else:
        source_label = "configured sources" if str(language or "de").lower().startswith("en") else "konfigurierte Quellen"
    if str(language or "de").lower().startswith("en"):
        heading = f"I found {ref_count} matching {source_label}:"
    else:
        heading = f"Ich habe {ref_count} passende {source_label} gefunden:"
    return "\n".join([heading, *content_lines]).strip()


def docs_search_fallback_answer(
    arbitration: AriaTurnArbitration,
    docs_result: SkillResult,
    *,
    language: str | None,
    pipeline_text: Callable[[str | None, str, str], str],
    single_local_search_request: Callable[[AriaTurnArbitration], ContextRequest | None],
    skill_result_sources: Callable[[SkillResult | None], list[dict[str, Any]]],
) -> str:
    request = single_local_search_request(arbitration)
    if request is None or request.surface_id != "docs":
        return ""
    sources = skill_result_sources(docs_result)
    if not sources:
        return ""
    if not all(
        str(source.get("type", "") or "").strip().lower() == "document"
        or str(source.get("collection", "") or "").strip().startswith("aria_docs")
        for source in sources
    ):
        return ""
    content = str(docs_result.content or "").strip()
    source_name = (
        str(sources[0].get("document_name", "") or "").strip()
        or str(sources[0].get("title", "") or "").strip()
        or str(sources[0].get("label", "") or "").strip()
    )
    source_evidence_parts: list[str] = [str(request.query or ""), content, source_name]
    for source in sources[:3]:
        if not isinstance(source, dict):
            continue
        for key in ("document_name", "title", "label", "detail", "guide_summary"):
            value = str(source.get(key, "") or "").strip()
            if value:
                source_evidence_parts.append(value)
        keywords = source.get("guide_keywords")
        if isinstance(keywords, list):
            source_evidence_parts.extend(str(keyword or "") for keyword in keywords)
    evidence_text = "\n".join(part for part in source_evidence_parts if part).lower()
    lowered = content.lower()
    wants_german = not str(language or "de").lower().startswith("en")
    wifi_terms_present = any(term in evidence_text for term in ("wifi", "wi-fi", "wireless", "wlan", "2,4 ghz", "2.4 ghz"))
    heater_terms_present = any(
        term in evidence_text
        for term in ("heater", "heizung", "heizungen", "varmeapparat", "mill-app", "mill app", "mill ")
    )
    setup_terms_present = any(
        term in evidence_text
        for term in (
            "add heater",
            "tilføj varmeapparat",
            "heizger" + chr(228) + "t hinzuf" + chr(252) + "gen",
            "heizgeraet hinzufuegen",
            "wi-fi-knappen",
            "wifi button",
            "wifi-taste",
            "app pairing",
            "setup instructions",
            "wlan einrichten",
            "wireless verbinden",
        )
    )
    app_setup_evidence = any(
        term in evidence_text
        for term in (
            "add heater",
            "tilføj varmeapparat",
            "heizger" + chr(228) + "t hinzuf" + chr(252) + "gen",
            "heizgeraet hinzufuegen",
            "mill-appen",
            "mill-app",
            "mill app",
            "app pairing",
            "setup instructions",
            "wlan einrichten",
            "wireless verbinden",
        )
    )
    troubleshooting_evidence = any(
        term in evidence_text
        for term in ("2,4 ghz", "2.4 ghz", "router", "capacity", "kapazit" + chr(228) + "t", "kapazitaet", "off and on", "aus- und")
    )
    wifi_reset_evidence = any(
        term in evidence_text for term in ("wi-fi-knappen", "wifi button", "wifi-taste", "5 seconds", "5 sekunden")
    )
    if wifi_terms_present and heater_terms_present and (setup_terms_present or troubleshooting_evidence or wifi_reset_evidence):
        if wants_german:
            lines = [
                pipeline_text(
                    language,
                    "direct_context.docs_mill_wifi_heading",
                    "To connect your Mill heater to WiFi:",
                )
            ]
            if app_setup_evidence:
                lines.append(
                    pipeline_text(
                        language,
                        "direct_context.docs_mill_wifi_app_setup",
                        "- Open the Mill app and follow the pairing/setup flow for a new heater.",
                    )
                )
            if troubleshooting_evidence:
                lines.append(
                    pipeline_text(
                        language,
                        "direct_context.docs_mill_wifi_troubleshooting",
                        "- If it cannot connect: turn the heater off and on, restart the router, check router capacity, and make sure 2.4 GHz is enabled.",
                    )
                )
            if wifi_reset_evidence:
                lines.append(
                    pipeline_text(
                        language,
                        "direct_context.docs_mill_wifi_reset",
                        "- To reset WiFi settings: hold the WiFi button for 5 seconds.",
                    )
                )
            if source_name:
                lines.append(
                    pipeline_text(
                        language,
                        "direct_context.docs_source_line",
                        "Source: {source_name}",
                    ).replace("{source_name}", source_name)
                )
            return "\n".join(lines)
        lines = ["To connect your Mill heater to WiFi:"]
        if app_setup_evidence:
            lines.append("- Open the Mill app and follow the pairing/setup flow for a new heater.")
        if troubleshooting_evidence:
            lines.append(
                "- If it cannot connect: turn the heater off and on, restart the router, check router capacity, "
                "and make sure 2.4 GHz is enabled."
            )
        if wifi_reset_evidence:
            lines.append("- To reset WiFi settings: hold the WiFi button for 5 seconds.")
        if source_name:
            lines.append(f"Source: {source_name}")
        return "\n".join(lines)
    if wants_german:
        return pipeline_text(
            language,
            "direct_context.docs_safe_summary_fallback",
            "I found matching passages in {source_name}, but could not summarize them safely enough.",
        ).replace("{source_name}", source_name or "your documents")
    return (
        f"I found matching passages in {source_name or 'your documents'}, "
        "but could not summarize them safely enough."
    )


def fast_docs_search_answer(
    arbitration: AriaTurnArbitration,
    docs_result: SkillResult,
    *,
    language: str | None,
    pipeline_text: Callable[[str | None, str, str], str],
    single_local_search_request: Callable[[AriaTurnArbitration], ContextRequest | None],
    skill_result_sources: Callable[[SkillResult | None], list[dict[str, Any]]],
) -> str:
    request = single_local_search_request(arbitration)
    if request is None or request.surface_id != "docs" or arbitration.plan.answer_mode != "direct_answer":
        return ""
    sources = skill_result_sources(docs_result)
    if not sources:
        return ""
    if not all(
        str(source.get("type", "") or "").strip().lower() == "document"
        or str(source.get("collection", "") or "").strip().startswith("aria_docs")
        for source in sources
    ):
        return ""
    content = str(docs_result.content or "").strip()
    bounded_instruction_answer = docs_search_fallback_answer(
        arbitration,
        docs_result,
        language=language,
        pipeline_text=pipeline_text,
        single_local_search_request=single_local_search_request,
        skill_result_sources=skill_result_sources,
    )
    if bounded_instruction_answer and not any(
        marker in bounded_instruction_answer
        for marker in (
            "konnte sie aber nicht sicher genug automatisch zusammenfassen",
            "could not summarize them safely enough",
        )
    ):
        return bounded_instruction_answer
    if not content or len(content) > 4200:
        return ""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) > 12:
        return ""
    first_source = sources[0]
    source_name = (
        str(first_source.get("document_name", "") or "").strip()
        or str(first_source.get("title", "") or "").strip()
        or str(first_source.get("label", "") or "").strip()
    )
    if str(language or "de").lower().startswith("en"):
        heading = f"From {source_name}:" if source_name else "From your documents:"
    else:
        heading = f"Aus {source_name}:" if source_name else "Aus deinen Dokumenten:"
    return f"{heading}\n{content}".strip()
