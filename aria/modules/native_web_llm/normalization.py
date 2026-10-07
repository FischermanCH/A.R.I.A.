from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aria.modules.native_web_llm.contracts import NativeWebCitation, NativeWebResult


NATIVE_CHAT_SEARCH_MODEL_MARKERS = (
    "gpt-4o-search-preview",
    "gpt-4o-mini-search-preview",
    "gpt-5-search-api",
)


def as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            dumped = method()
            if isinstance(dumped, dict):
                return dumped
    return {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def public_http_url(value: Any) -> str:
    clean = clean_text(value)
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return clean


def citation_from_mapping(value: Any, *, source: str) -> NativeWebCitation | None:
    row = as_mapping(value)
    url = public_http_url(row.get("url") or row.get("uri"))
    if not url:
        return None
    return NativeWebCitation(
        url=url,
        title=clean_text(row.get("title")),
        cited_text=clean_text(row.get("cited_text") or row.get("text") or row.get("snippet")),
        source=source,
    )


def dedupe_citations(rows: list[NativeWebCitation]) -> tuple[NativeWebCitation, ...]:
    output: list[NativeWebCitation] = []
    seen: set[str] = set()
    for row in rows:
        marker = row.url.rstrip("/").lower()
        if marker in seen:
            continue
        seen.add(marker)
        output.append(row)
    return tuple(output)


def usage_values(payload: dict[str, Any]) -> tuple[dict[str, int], int]:
    usage = as_mapping(payload.get("usage"))
    prompt = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    completion = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    input_details = as_mapping(usage.get("input_tokens_details") or usage.get("prompt_tokens_details"))
    output_details = as_mapping(usage.get("output_tokens_details") or usage.get("completion_tokens_details"))
    cached = int(input_details.get("cached_tokens") or 0)
    reasoning = int(output_details.get("reasoning_tokens") or 0)
    server_tool_use = as_mapping(usage.get("server_tool_use"))
    web_uses = int(server_tool_use.get("web_search_requests") or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "cached_tokens": cached,
        "total_tokens": total,
    }, web_uses


def _base_errors(answer: str, citations: list[NativeWebCitation], web_uses: int) -> list[str]:
    errors: list[str] = []
    if not answer.strip():
        errors.append("answer_missing")
    if not citations:
        errors.append("provider_citations_missing")
    if web_uses < 1:
        errors.append("native_web_search_not_observed")
    return errors


def normalize_openai_responses(payload: dict[str, Any], *, duration_ms: int) -> NativeWebResult:
    answer_parts: list[str] = []
    citations: list[NativeWebCitation] = []
    web_uses = 0
    finish_reason = clean_text(payload.get("status"))
    for raw_item in as_list(payload.get("output")):
        item = as_mapping(raw_item)
        item_type = clean_text(item.get("type"))
        if item_type == "web_search_call":
            web_uses += 1
            continue
        if item_type != "message":
            continue
        finish_reason = clean_text(item.get("status")) or finish_reason
        for raw_content in as_list(item.get("content")):
            content = as_mapping(raw_content)
            if clean_text(content.get("type")) not in {"output_text", "text"}:
                continue
            text = clean_text(content.get("text"))
            if text:
                answer_parts.append(text)
            for raw_annotation in as_list(content.get("annotations")):
                annotation = as_mapping(raw_annotation)
                if clean_text(annotation.get("type")) != "url_citation":
                    continue
                citation = citation_from_mapping(annotation, source="openai.url_citation")
                if citation:
                    citations.append(citation)
    usage, usage_web_uses = usage_values(payload)
    web_uses = max(web_uses, usage_web_uses)
    answer = "\n".join(answer_parts)
    return NativeWebResult(
        answer=answer,
        citations=dedupe_citations(citations),
        model=clean_text(payload.get("model")),
        provider_shape="openai_responses",
        native_search_uses=web_uses,
        usage=usage,
        duration_ms=duration_ms,
        finish_reason=finish_reason,
        errors=tuple(_base_errors(answer, citations, web_uses)),
    )


def normalize_anthropic_messages(payload: dict[str, Any], *, duration_ms: int) -> NativeWebResult:
    answer_parts: list[str] = []
    citations: list[NativeWebCitation] = []
    content_web_uses = 0
    for raw_block in as_list(payload.get("content")):
        block = as_mapping(raw_block)
        block_type = clean_text(block.get("type"))
        if block_type == "server_tool_use" and clean_text(block.get("name")) == "web_search":
            content_web_uses += 1
            continue
        if block_type != "text":
            continue
        text = clean_text(block.get("text"))
        if text:
            answer_parts.append(text)
        for raw_citation in as_list(block.get("citations")):
            citation = citation_from_mapping(raw_citation, source="anthropic.web_search_citation")
            if citation:
                citations.append(citation)
    usage, usage_web_uses = usage_values(payload)
    web_uses = max(content_web_uses, usage_web_uses)
    answer = "\n".join(answer_parts)
    return NativeWebResult(
        answer=answer,
        citations=dedupe_citations(citations),
        model=clean_text(payload.get("model")),
        provider_shape="anthropic_messages",
        native_search_uses=web_uses,
        usage=usage,
        duration_ms=duration_ms,
        finish_reason=clean_text(payload.get("stop_reason")),
        errors=tuple(_base_errors(answer, citations, web_uses)),
    )


def normalize_chat_completion(payload: dict[str, Any], *, duration_ms: int) -> NativeWebResult:
    choices = as_list(payload.get("choices"))
    choice = as_mapping(choices[0]) if choices else {}
    message = as_mapping(choice.get("message"))
    answer = clean_text(message.get("content"))
    citations: list[NativeWebCitation] = []
    for raw_annotation in as_list(message.get("annotations")):
        annotation = as_mapping(raw_annotation)
        citation = citation_from_mapping(
            as_mapping(annotation.get("url_citation")) or annotation,
            source="openai.chat_annotation",
        )
        if citation:
            citations.append(citation)
    usage, web_uses = usage_values(payload)
    model = clean_text(payload.get("model"))
    if web_uses < 1 and citations and any(marker in model.lower() for marker in NATIVE_CHAT_SEARCH_MODEL_MARKERS):
        web_uses = 1
    return NativeWebResult(
        answer=answer,
        citations=dedupe_citations(citations),
        model=model,
        provider_shape="chat_completion",
        native_search_uses=web_uses,
        usage=usage,
        duration_ms=duration_ms,
        finish_reason=clean_text(choice.get("finish_reason")),
        errors=tuple(_base_errors(answer, citations, web_uses)),
    )


def normalize_native_web_response(payload: Any, *, duration_ms: int = 0) -> NativeWebResult:
    row = as_mapping(payload)
    if as_list(row.get("output")):
        return normalize_openai_responses(row, duration_ms=duration_ms)
    content = as_list(row.get("content"))
    if content and any(
        clean_text(as_mapping(item).get("type")) in {"server_tool_use", "web_search_tool_result"}
        for item in content
    ):
        return normalize_anthropic_messages(row, duration_ms=duration_ms)
    if as_list(row.get("choices")):
        return normalize_chat_completion(row, duration_ms=duration_ms)
    return NativeWebResult(
        answer="",
        citations=(),
        model=clean_text(row.get("model")),
        provider_shape="unknown",
        native_search_uses=0,
        usage={
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
        },
        duration_ms=duration_ms,
        errors=("unsupported_response_shape",),
    )
