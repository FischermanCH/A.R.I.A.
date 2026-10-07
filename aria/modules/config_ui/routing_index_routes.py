from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Any]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
StringSanitizer = Callable[[str | None], str]
RoutingIndexStatusBuilder = Callable[[Any], Awaitable[dict[str, Any]]]
RoutingQueryTester = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ConfigRoutingIndexRouteDeps:
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_auth_session_from_request: AuthSessionResolver
    sanitize_role: StringSanitizer
    build_connection_routing_index_status: RoutingIndexStatusBuilder
    test_connection_routing_query: RoutingQueryTester


def register_config_routing_index_routes(app: FastAPI, deps: ConfigRoutingIndexRouteDeps) -> None:
    @app.get("/config/routing-index/status")
    async def config_routing_index_status(request: Request) -> JSONResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return JSONResponse({"status": "error", "message": "Admin access required."}, status_code=403)
        return JSONResponse(await deps.build_connection_routing_index_status(deps.get_settings()))

    @app.get("/config/routing-index/test")
    async def config_routing_index_test(
        request: Request,
        query: str = "",
        preferred_kind: str = "auto",
    ) -> JSONResponse:
        auth = deps.get_auth_session_from_request(request) or {}
        if deps.sanitize_role(auth.get("role")) != "admin":
            return JSONResponse({"status": "error", "message": "Admin access required."}, status_code=403)
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        return JSONResponse(
            await deps.test_connection_routing_query(
                settings,
                query,
                preferred_kind=preferred_kind,
                llm_client=getattr(pipeline, "llm_client", None),
                language=str(getattr(request.state, "lang", "") or getattr(settings.ui, "language", "") or ""),
            )
        )
