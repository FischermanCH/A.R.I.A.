"""Admin-only browser trigger for the native Tool-Calling selftest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
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
    @app.get("/config/native-toolcall-selftest")
    async def native_toolcall_selftest_page(request: Request) -> RedirectResponse:
        _require_admin(request)
        return RedirectResponse("/config/llm", status_code=303)

    async def _run_and_redirect(request: Request) -> RedirectResponse:
        _require_admin(request)
        try:
            diagnostics: dict[str, Any] = (await deps.run_selftest(deps.get_llm_config())).as_dict()
            passed = bool(diagnostics.get("native_tool_call_emitted")) and bool(
                diagnostics.get("final_answer_correct")
            )
            detail = (
                f"tool={diagnostics.get('tool_name') or '-'}; "
                f"result={diagnostics.get('tool_result') or '-'}; "
                f"provider_calls={diagnostics.get('provider_calls') or 0}"
            )
            status = "ok" if passed else "error"
        except Exception as exc:
            status = "error"
            detail = str(exc) or type(exc).__name__
        return RedirectResponse(
            "/config/llm?selftest_status=" + status + "&selftest_result=" + quote_plus(detail[:800]),
            status_code=303,
        )

    @app.post("/config/llm/toolcall-selftest")
    async def native_toolcall_selftest_run(request: Request) -> RedirectResponse:
        return await _run_and_redirect(request)

    @app.post("/config/native-toolcall-selftest")
    async def native_toolcall_selftest_legacy_run(request: Request) -> RedirectResponse:
        return await _run_and_redirect(request)
