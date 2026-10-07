from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable

from aria.modules.platform_primitives.text_utils import extract_json_object


MAX_RESPONSE_SCHEMA_BYTES = 8192


@dataclass(frozen=True)
class BoundedDecisionResult:
    content: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    diagnostics: dict[str, int] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def llm_response_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }


def confidence_score(value: Any) -> float:
    raw = str(value or "").strip().lower()
    if raw in {"high", "hoch"}:
        return 0.82
    if raw in {"medium", "mittel"}:
        return 0.66
    if raw in {"low", "niedrig"}:
        return 0.34
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def bounded_decision_diagnostics(*, system: str, payload: dict[str, Any]) -> dict[str, int]:
    payload_json = encode_bounded_decision_payload(payload)
    return {
        "system_chars": len(str(system or "")),
        "payload_bytes": len(payload_json.encode("utf-8")),
        "payload_keys": len(payload),
    }


def encode_bounded_decision_payload(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


def response_schema_transport_issues(schema: object, *, path: str = "$") -> tuple[str, ...]:
    issues: list[str] = []
    if isinstance(schema, dict):
        if path == "$":
            schema_bytes = len(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            if schema_bytes > MAX_RESPONSE_SCHEMA_BYTES:
                issues.append(f"schema_too_large:{schema_bytes}")
            optional_properties = response_schema_optional_property_count(schema)
            if optional_properties > 24:
                issues.append(f"too_many_optional_properties:{optional_properties}")
        if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
            issues.append(f"open_object:{path}")
        if "oneOf" in schema:
            issues.append(f"unsupported_oneOf:{path}")
        if "minProperties" in schema:
            issues.append(f"unsupported_minProperties:{path}")
        for key, value in schema.items():
            issues.extend(response_schema_transport_issues(value, path=f"{path}.{key}"))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            issues.extend(response_schema_transport_issues(value, path=f"{path}[{index}]"))
    return tuple(issues)


def response_schema_optional_property_count(schema: object) -> int:
    if isinstance(schema, dict):
        properties = schema.get("properties")
        required = set(schema.get("required") or [])
        own_count = len(set(properties) - required) if isinstance(properties, dict) else 0
        return own_count + sum(response_schema_optional_property_count(value) for value in schema.values())
    if isinstance(schema, list):
        return sum(response_schema_optional_property_count(value) for value in schema)
    return 0


def response_schema_is_strict_compatible(schema: object) -> bool:
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                return False
            if set(properties) != set(schema.get("required") or []):
                return False
        return all(response_schema_is_strict_compatible(value) for value in schema.values())
    if isinstance(schema, list):
        return all(response_schema_is_strict_compatible(value) for value in schema)
    return True


def decision_response_format(
    *, operation: str, response_schema: dict[str, Any], strict: bool
) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": operation,
            "strict": strict,
            "schema": dict(response_schema),
        },
    }


class BoundedDecisionClient:
    def __init__(self, llm_client: Any | None):
        self.llm_client = llm_client
        self._strict_json_schema_supported: bool | None = None

    async def decide_json(
        self,
        *,
        operation: str,
        system: str,
        payload: dict[str, Any],
        source: str = "",
        user_id: str = "",
        request_id: str = "",
        response_schema: dict[str, Any] | None = None,
        validate_payload: Callable[[dict[str, Any]], tuple[str, ...]] | None = None,
        repair_once: bool = False,
    ) -> BoundedDecisionResult:
        diagnostics = bounded_decision_diagnostics(system=system, payload=payload)
        if self.llm_client is None:
            return BoundedDecisionResult(diagnostics=diagnostics, error="no_llm_client")
        schema_issues = response_schema_transport_issues(response_schema) if response_schema else ()
        if schema_issues:
            return BoundedDecisionResult(
                diagnostics={**diagnostics, "response_schema_transport_issues": len(schema_issues)},
                error="structured_output_schema_invalid",
            )
        strict_compatible = bool(response_schema and response_schema_is_strict_compatible(response_schema))
        use_strict = strict_compatible and self._strict_json_schema_supported is not False
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": encode_bounded_decision_payload(payload)},
        ]
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        last_content = ""
        last_error = ""
        strict_fallback_calls = 0
        for attempt in range(2 if repair_once else 1):
            response_format = (
                decision_response_format(
                    operation=operation,
                    response_schema=response_schema,
                    strict=use_strict,
                )
                if response_schema
                else None
            )
            try:
                response = await self.llm_client.chat(
                    messages,
                    operation=operation,
                    source=source,
                    user_id=user_id,
                    request_id=request_id,
                    **({"response_format": response_format} if response_format else {}),
                )
            except Exception:
                if use_strict and response_schema:
                    self._strict_json_schema_supported = False
                    use_strict = False
                    strict_fallback_calls += 1
                    try:
                        response = await self.llm_client.chat(
                            messages,
                            operation=operation,
                            source=source,
                            user_id=user_id,
                            request_id=request_id,
                            response_format=decision_response_format(
                                operation=operation,
                                response_schema=response_schema,
                                strict=False,
                            ),
                        )
                    except Exception:
                        return BoundedDecisionResult(
                            content=last_content,
                            usage=total_usage,
                            diagnostics={
                                **diagnostics,
                                "repair_calls": attempt,
                                "strict_fallback_calls": strict_fallback_calls,
                            },
                            error="structured_output_unavailable",
                        )
                else:
                    return BoundedDecisionResult(
                        content=last_content,
                        usage=total_usage,
                        diagnostics={
                            **diagnostics,
                            "repair_calls": attempt,
                            "strict_fallback_calls": strict_fallback_calls,
                        },
                        error="structured_output_unavailable" if response_schema else "llm_error",
                    )
            else:
                if use_strict:
                    self._strict_json_schema_supported = True
            usage = llm_response_usage(response)
            total_usage = {
                key: total_usage[key] + int(usage.get(key, 0) or 0)
                for key in total_usage
            }
            last_content = str(getattr(response, "content", "") or "").strip()
            parsed = extract_json_object(last_content)
            if isinstance(parsed, dict):
                validation_errors = tuple(validate_payload(parsed)) if validate_payload else ()
                if not validation_errors:
                    return BoundedDecisionResult(
                        content=last_content,
                        payload=parsed,
                        usage=total_usage,
                        diagnostics={
                            **diagnostics,
                            "repair_calls": attempt,
                            "strict_fallback_calls": strict_fallback_calls,
                        },
                    )
                last_error = str(validation_errors[0] or "contract_invalid")
            else:
                last_error = "empty_or_invalid_response"
            if attempt == 0 and repair_once:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            system
                            + "\nRepair the invalid prior response once. Return only one JSON object matching the same response schema. "
                            "Do not add, infer, or change authority beyond the original bounded input."
                        ),
                    },
                    {
                        "role": "user",
                        "content": encode_bounded_decision_payload({
                            "original_input": payload,
                            "invalid_response": last_content,
                            "validation_errors": [last_error],
                        }),
                    },
                ]
        return BoundedDecisionResult(
            content=last_content,
            usage=total_usage,
            diagnostics={
                **diagnostics,
                "repair_calls": int(repair_once),
                "strict_fallback_calls": strict_fallback_calls,
            },
            error=last_error or "contract_invalid",
        )

    async def complete_text(
        self,
        *,
        operation: str,
        system: str,
        payload: dict[str, Any],
        source: str = "",
        user_id: str = "",
        request_id: str = "",
    ) -> BoundedDecisionResult:
        diagnostics = bounded_decision_diagnostics(system=system, payload=payload)
        if self.llm_client is None:
            return BoundedDecisionResult(diagnostics=diagnostics, error="no_llm_client")
        try:
            response = await self.llm_client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": encode_bounded_decision_payload(payload)},
                ],
                operation=operation,
                source=source,
                user_id=user_id,
                request_id=request_id,
            )
        except Exception:
            return BoundedDecisionResult(diagnostics=diagnostics, error="llm_error")
        return BoundedDecisionResult(
            content=str(getattr(response, "content", "") or "").strip(),
            usage=llm_response_usage(response),
            diagnostics=diagnostics,
        )
