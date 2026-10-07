"""Admin-only browser trigger for the native Tool-Calling selftest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_toolcall_selftest.roundtrip import NativeToolcallDiagnostics, run_native_toolcall_selftest


@dataclass(frozen=True)
class NativeToolcallRouteDeps:
    templates: Jinja2Templates
    get_llm_config: Callable[[], LLMConfig]
    run_selftest: Callable[[LLMConfig], Awaitable[NativeToolcallDiagnostics]] = run_native_toolcall_selftest


def _require_admin(request: Request) -> None:
    role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
    if role != "admin" or not bool(getattr(request.state, "can_access_advanced_config", False)):
        raise HTTPException(status_code=403, detail="admin_required")


def register_native_toolcall_selftest_routes(app: FastAPI, deps: NativeToolcallRouteDeps) -> None:
    @app.get("/config/native-toolcall-selftest", response_class=HTMLResponse)
    async def native_toolcall_selftest_page(request: Request) -> HTMLResponse:
        _require_admin(request)
        return deps.templates.TemplateResponse(request=request, name="native_toolcall_selftest.html", context={"diagnostics": None, "error": ""})

    @app.post("/config/native-toolcall-selftest", response_class=HTMLResponse)
    async def native_toolcall_selftest_run(request: Request) -> HTMLResponse:
        _require_admin(request)
        diagnostics: dict[str, Any] | None = None
        error = ""
        try:
            diagnostics = (await deps.run_selftest(deps.get_llm_config())).as_dict()
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        return deps.templates.TemplateResponse(request=request, name="native_toolcall_selftest.html", context={"diagnostics": diagnostics, "error": error})
