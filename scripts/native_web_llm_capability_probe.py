#!/usr/bin/env python3
"""Offline-first native Web-LLM capability probe.

Fixture mode is the default. A real provider request requires all live guards and
an API key supplied through the environment; the key is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlparse


LIVE_CONFIRMATION = "RUN_ONE_PAID_NATIVE_WEB_PROBE"
NATIVE_CHAT_SEARCH_MODEL_MARKERS = (
    "gpt-4o-search-preview",
    "gpt-4o-mini-search-preview",
    "gpt-5-search-api",
)


@dataclass(frozen=True)
class Citation:
    url: str
    title: str = ""
    cited_text: str = ""
    source: str = ""


@dataclass(frozen=True)
class CapabilityResult:
    provider_shape: str
    model: str
    answer: str
    citations: tuple[Citation, ...]
    native_search_uses: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int
    finish_reason: str
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return bool(self.answer.strip() and self.citations and self.native_search_uses > 0 and not self.errors)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            dumped = method()
            if isinstance(dumped, dict):
                return dumped
    return {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _valid_public_url(value: Any) -> str:
    clean = _text(value)
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return clean


def _citation_from_mapping(row: Any, *, source: str) -> Citation | None:
    item = _mapping(row)
    url = _valid_public_url(item.get("url") or item.get("uri"))
    if not url:
        return None
    return Citation(
        url=url,
        title=_text(item.get("title")),
        cited_text=_text(item.get("cited_text") or item.get("text") or item.get("snippet")),
        source=source,
    )


def _dedupe_citations(rows: list[Citation]) -> tuple[Citation, ...]:
    output: list[Citation] = []
    seen: set[str] = set()
    for row in rows:
        marker = row.url.rstrip("/").lower()
        if marker in seen:
            continue
        seen.add(marker)
        output.append(row)
    return tuple(output)


def _collect_citations(value: Any, *, source: str) -> list[Citation]:
    rows: list[Citation] = []
    if isinstance(value, list):
        for item in value:
            rows.extend(_collect_citations(item, source=source))
        return rows
    item = _mapping(value)
    if not item:
        return rows
    nested = _mapping(item.get("url_citation"))
    candidate = nested or item
    citation = _citation_from_mapping(candidate, source=source)
    if citation:
        if not citation.cited_text and _text(item.get("supported_text")):
            citation = Citation(
                url=citation.url,
                title=citation.title,
                cited_text=_text(item.get("supported_text")),
                source=citation.source,
            )
        rows.append(citation)
    return rows


def _usage_values(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    usage = _mapping(payload.get("usage"))
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    server_tool_use = _mapping(usage.get("server_tool_use"))
    web_uses = int(server_tool_use.get("web_search_requests") or 0)
    return input_tokens, output_tokens, total_tokens, web_uses


def _normalize_openai_responses(payload: dict[str, Any], *, duration_ms: int) -> CapabilityResult:
    answer_parts: list[str] = []
    citations: list[Citation] = []
    web_uses = 0
    finish_reason = _text(payload.get("status"))
    for raw_item in _list(payload.get("output")):
        item = _mapping(raw_item)
        item_type = _text(item.get("type"))
        if item_type == "web_search_call":
            web_uses += 1
            continue
        if item_type != "message":
            continue
        finish_reason = _text(item.get("status")) or finish_reason
        for raw_content in _list(item.get("content")):
            content = _mapping(raw_content)
            if _text(content.get("type")) not in {"output_text", "text"}:
                continue
            text = _text(content.get("text"))
            if text:
                answer_parts.append(text)
            for raw_annotation in _list(content.get("annotations")):
                annotation = _mapping(raw_annotation)
                if _text(annotation.get("type")) != "url_citation":
                    continue
                citation = _citation_from_mapping(annotation, source="openai.url_citation")
                if citation:
                    citations.append(citation)
    input_tokens, output_tokens, total_tokens, usage_web_uses = _usage_values(payload)
    web_uses = max(web_uses, usage_web_uses)
    errors: list[str] = []
    if not answer_parts:
        errors.append("answer_missing")
    if not citations:
        errors.append("provider_citations_missing")
    if web_uses < 1:
        errors.append("native_web_search_not_observed")
    return CapabilityResult(
        provider_shape="openai_responses",
        model=_text(payload.get("model")),
        answer="\n".join(answer_parts),
        citations=_dedupe_citations(citations),
        native_search_uses=web_uses,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        finish_reason=finish_reason,
        errors=tuple(errors),
    )


def _normalize_anthropic(payload: dict[str, Any], *, duration_ms: int) -> CapabilityResult:
    answer_parts: list[str] = []
    citations: list[Citation] = []
    content_web_uses = 0
    for raw_block in _list(payload.get("content")):
        block = _mapping(raw_block)
        block_type = _text(block.get("type"))
        if block_type == "server_tool_use" and _text(block.get("name")) == "web_search":
            content_web_uses += 1
            continue
        if block_type != "text":
            continue
        text = _text(block.get("text"))
        if text:
            answer_parts.append(text)
        for raw_citation in _list(block.get("citations")):
            citation = _citation_from_mapping(raw_citation, source="anthropic.web_search_citation")
            if citation:
                citations.append(citation)
    input_tokens, output_tokens, total_tokens, usage_web_uses = _usage_values(payload)
    web_uses = max(content_web_uses, usage_web_uses)
    errors: list[str] = []
    if not answer_parts:
        errors.append("answer_missing")
    if not citations:
        errors.append("provider_citations_missing")
    if web_uses < 1:
        errors.append("native_web_search_not_observed")
    return CapabilityResult(
        provider_shape="anthropic_messages",
        model=_text(payload.get("model")),
        answer="\n".join(answer_parts),
        citations=_dedupe_citations(citations),
        native_search_uses=web_uses,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        finish_reason=_text(payload.get("stop_reason")),
        errors=tuple(errors),
    )


def _normalize_chat_completion(payload: dict[str, Any], *, duration_ms: int) -> CapabilityResult:
    choices = _list(payload.get("choices"))
    choice = _mapping(choices[0]) if choices else {}
    message = _mapping(choice.get("message"))
    answer = _text(message.get("content"))
    citations: list[Citation] = []
    for raw_annotation in _list(message.get("annotations")):
        annotation = _mapping(raw_annotation)
        nested = _mapping(annotation.get("url_citation"))
        candidate = nested or annotation
        citation = _citation_from_mapping(candidate, source="openai.chat_annotation")
        if citation:
            citations.append(citation)
    provider_fields = _mapping(message.get("provider_specific_fields"))
    citations.extend(_collect_citations(message.get("citations"), source="message.citation"))
    citations.extend(_collect_citations(provider_fields.get("citations"), source="provider_specific.citation"))
    input_tokens, output_tokens, total_tokens, usage_web_uses = _usage_values(payload)
    web_uses = usage_web_uses
    for raw_call in _list(message.get("tool_calls")):
        call = _mapping(raw_call)
        function = _mapping(call.get("function"))
        if _text(call.get("type")) in {"web_search", "web_search_preview"} or _text(function.get("name")) in {
            "web_search",
            "WebSearch",
            "litellm_web_search",
        }:
            web_uses += 1
    model = _text(payload.get("model"))
    if web_uses < 1 and citations and any(marker in model.lower() for marker in NATIVE_CHAT_SEARCH_MODEL_MARKERS):
        web_uses = 1
    errors: list[str] = []
    if not answer:
        errors.append("answer_missing")
    if not citations:
        errors.append("provider_citations_missing")
    if web_uses < 1:
        errors.append("native_web_search_not_observed")
    return CapabilityResult(
        provider_shape="chat_completion",
        model=model,
        answer=answer,
        citations=_dedupe_citations(citations),
        native_search_uses=web_uses,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        finish_reason=_text(choice.get("finish_reason")),
        errors=tuple(errors),
    )


def normalize_native_web_response(payload: Any, *, duration_ms: int = 0) -> CapabilityResult:
    row = _mapping(payload)
    if _list(row.get("output")):
        return _normalize_openai_responses(row, duration_ms=duration_ms)
    content = _list(row.get("content"))
    if content and any(_text(_mapping(item).get("type")) in {"server_tool_use", "web_search_tool_result"} for item in content):
        return _normalize_anthropic(row, duration_ms=duration_ms)
    if _list(row.get("choices")):
        return _normalize_chat_completion(row, duration_ms=duration_ms)
    return CapabilityResult(
        provider_shape="unknown",
        model=_text(row.get("model")),
        answer="",
        citations=(),
        native_search_uses=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        duration_ms=duration_ms,
        finish_reason="",
        errors=("unsupported_response_shape",),
    )


def _result_payload(result: CapabilityResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["citations"] = [asdict(row) for row in result.citations]
    payload["passed"] = result.passed
    return payload


def _validate_expectations(
    result: CapabilityResult,
    expected_hosts: list[str],
    max_search_uses: int,
    expected_url_prefixes: list[str] | None = None,
) -> list[str]:
    errors = list(result.errors)
    if max_search_uses > 0 and result.native_search_uses > max_search_uses:
        errors.append("native_web_search_budget_exceeded")
    if expected_hosts:
        citation_hosts = {urlparse(row.url).hostname.lower() for row in result.citations if urlparse(row.url).hostname}
        if not any(any(host == expected or host.endswith(f".{expected}") for host in citation_hosts) for expected in expected_hosts):
            errors.append("expected_primary_host_missing")
    if expected_url_prefixes and not any(
        row.url.lower().startswith(prefix.lower())
        for row in result.citations
        for prefix in expected_url_prefixes
    ):
        errors.append("expected_primary_url_prefix_missing")
    return list(dict.fromkeys(errors))


def _load_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture_root_must_be_object")
    return payload


async def _run_live(args: argparse.Namespace) -> tuple[Any, int]:
    if args.confirm_paid_probe != LIVE_CONFIRMATION:
        raise ValueError("live_confirmation_missing")
    api_key = os.environ.get("ARIA_WEB_LLM_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ARIA_WEB_LLM_API_KEY_missing")
    if not args.model.strip() or not args.api_base.strip():
        raise ValueError("live_model_and_api_base_required")

    if args.max_search_uses < 1:
        raise ValueError("max_search_uses_must_be_positive")

    instructions = (
        "Answer the user directly in German. Use native web search. Prefer official primary sources. "
        "Every current-version claim must have a provider citation. Do not answer from model memory alone."
    )
    authority_instruction = _text(getattr(args, "authority_instruction", ""))
    if authority_instruction:
        instructions += " " + authority_instruction
    if args.transport == "openai_responses":
        from litellm import aresponses

        web_search_tool: dict[str, Any] = {"type": "web_search", "search_context_size": "low"}
        allowed_domains = [
            _text(domain).lower()
            for domain in getattr(args, "allowed_domains", [])
            if _text(domain)
        ]
        if allowed_domains:
            web_search_tool["filters"] = {"allowed_domains": allowed_domains}
        started = time.perf_counter()
        response = await aresponses(
            model=args.model,
            input=args.prompt,
            instructions=instructions,
            tools=[web_search_tool],
            include=["web_search_call.action.sources"],
            api_base=args.api_base,
            api_key=api_key,
            max_output_tokens=1200,
            timeout=args.timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return response, duration_ms

    from litellm import acompletion

    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": args.prompt},
    ]
    kwargs: dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "api_base": args.api_base,
        "api_key": api_key,
        "max_tokens": 1200,
        "timeout": args.timeout_seconds,
    }
    if args.transport == "anthropic_native":
        kwargs["temperature"] = 0
        kwargs["tools"] = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": args.max_search_uses,
            }
        ]
    elif args.transport == "openai_web_search_options":
        kwargs["web_search_options"] = {"search_context_size": "low"}
    else:
        raise ValueError("unsupported_live_transport")

    started = time.perf_counter()
    response = await acompletion(**kwargs)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return response, duration_ms


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path)
    source.add_argument("--live", action="store_true")
    parser.add_argument(
        "--transport",
        choices=("anthropic_native", "openai_responses", "openai_web_search_options"),
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--api-base", default="")
    parser.add_argument("--prompt", default="Welches ist die neueste Version von n8n?")
    parser.add_argument("--expected-host", action="append", default=[])
    parser.add_argument("--max-search-uses", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--confirm-paid-probe", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.live:
            if not args.transport:
                raise ValueError("live_transport_required")
            payload, duration_ms = asyncio.run(_run_live(args))
        else:
            payload = _load_fixture(args.fixture)
            duration_ms = int(payload.pop("_probe_duration_ms", 0) or 0)
        result = normalize_native_web_response(payload, duration_ms=duration_ms)
        expectation_errors = _validate_expectations(
            result,
            [host.strip().lower() for host in args.expected_host if host.strip()],
            args.max_search_uses,
        )
        output = _result_payload(result)
        output["errors"] = expectation_errors
        output["passed"] = bool(result.passed and not expectation_errors)
        print(json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if output["passed"] else 2
    except Exception as exc:
        print(json.dumps({"passed": False, "errors": [type(exc).__name__ + ":" + str(exc)]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
