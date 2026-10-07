from __future__ import annotations

import hmac
import json
import sqlite3
from dataclasses import dataclass
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aria.modules.configuration_foundations.config import Settings
from aria.modules.inbound_event_storage.store import InboundEventStore, normalize_inbound_event


TokenResolver = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class InboundEventRouteDeps:
    get_settings: Callable[[], Settings]
    get_token: TokenResolver
    event_store: InboundEventStore


def _error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"ok": False, "code": code, "detail": detail})


def _request_token(request: Request) -> str:
    direct = str(request.headers.get("x-aria-inbound-token", "") or "").strip()
    if direct:
        return direct
    authorization = str(request.headers.get("authorization", "") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return str(request.query_params.get("token", "") or "").strip()


async def _bounded_body(request: Request, max_bytes: int) -> bytes | None:
    declared = str(request.headers.get("content-length", "") or "").strip()
    if declared:
        try:
            if int(declared) > max_bytes:
                return None
        except ValueError:
            pass
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def register_inbound_event_routes(app: FastAPI, deps: InboundEventRouteDeps) -> None:
    @app.post("/api/connections/inbound/{ref}/events")
    async def receive_inbound_event(ref: str, request: Request) -> JSONResponse:
        clean_ref = str(ref or "").strip().lower()
        settings = deps.get_settings()
        profile = settings.connections.inbound_webhook.get(clean_ref)
        if profile is None:
            return _error(404, "unknown_source", "Inbound source is not configured.")
        if not profile.enabled:
            return _error(403, "source_disabled", "Inbound source is disabled.")

        try:
            configured_token = str(deps.get_token(clean_ref) or "")
        except Exception:
            return _error(503, "source_auth_unavailable", "Inbound source authentication is not available.")
        supplied_token = _request_token(request)
        if not configured_token:
            return _error(503, "source_auth_unavailable", "Inbound source authentication is not configured.")
        if not supplied_token or not hmac.compare_digest(supplied_token, configured_token):
            return _error(401, "invalid_token", "Inbound source token is missing or invalid.")

        content_type = str(request.headers.get("content-type", "") or "").split(";", 1)[0].strip().lower()
        allowed_types = {str(value).strip().lower() for value in profile.allowed_content_types}
        if content_type not in allowed_types:
            return _error(415, "unsupported_content_type", "Content type is not allowed for this source.")

        max_body_bytes = max(1, min(int(profile.max_body_bytes), 10 * 1024 * 1024))
        body = await _bounded_body(request, max_body_bytes)
        if body is None:
            return _error(413, "body_too_large", "Request body exceeds the configured source limit.")
        if not body:
            return _error(400, "empty_body", "Request body is empty.")
        if content_type == "application/json":
            try:
                json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return _error(400, "invalid_json", "Request body is not valid JSON.")

        event = normalize_inbound_event(
            source_ref=clean_ref,
            provider_profile=str(profile.provider_profile or "generic").strip().lower(),
            content_type=content_type,
            body=body,
            headers=request.headers,
            remote_host=str(request.client.host if request.client else ""),
            routing_policy="log_only",
            store_raw_body=bool(profile.store_raw_body),
        )
        try:
            event_id, duplicate = deps.event_store.record(
                event,
                max_events_per_source=int(profile.max_events),
            )
        except sqlite3.Error:
            return _error(503, "event_store_unavailable", "Inbound event storage is not available.")
        return JSONResponse(
            status_code=200 if duplicate else 202,
            content={
                "ok": True,
                "event_id": event_id,
                "status": "duplicate" if duplicate else "accepted",
                "contract": event.contract,
            },
        )
