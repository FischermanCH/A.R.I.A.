from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from aria.core.llm_client import LLMClientError
from aria.core.pipeline import Pipeline
from aria.core.prompt_loader import PromptLoadError


def _extract_last_user_message(messages: list[dict[str, Any]]) -> str:
    for item in reversed(messages):
        if str(item.get("role", "")).lower() == "user":
            content = item.get("content", "")
            return str(content).strip()
    return ""


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Unauthorized")


def register_api_routes(app, pipeline: Pipeline, auth_token: str = "") -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["openai-compatible"])

    @router.post("/chat/completions")
    async def chat_completions(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if auth_token:
            expected = f"Bearer {auth_token}"
            if authorization != expected:
                raise _unauthorized()

        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="messages must be a non-empty list")

        user_message = _extract_last_user_message(messages)
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found in messages")

        user_id = str(payload.get("user", "api")).strip() or "api"
        model = str(payload.get("model", pipeline.settings.llm.model))

        try:
            result = await pipeline.process(
                user_message,
                user_id=user_id,
                source="api",
                language=str(payload.get("lang", "") or ""),
            )
        except (PromptLoadError, LLMClientError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {
            "id": f"chatcmpl-{result.request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(result.usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(result.usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(result.usage.get("total_tokens", 0) or 0),
            },
        }

    app.include_router(router)
    return router
