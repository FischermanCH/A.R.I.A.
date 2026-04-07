from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from litellm import aembedding

from aria.core.config import EmbeddingsConfig
from aria.core.usage_meter import UsageMeter


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    usage: dict[str, int]
    raw: Any
    model: str
    metered: bool = False
    cost_usd: float | None = None


class EmbeddingClient:
    def __init__(self, config: EmbeddingsConfig, usage_meter: UsageMeter | None = None):
        self.model = config.model
        self.api_base = config.api_base
        self.api_key = config.api_key
        self.timeout_seconds = config.timeout_seconds
        self.usage_meter = usage_meter

    def _resolve_model(self) -> str:
        model = str(self.model or "").strip()
        if not model:
            return model
        if "/" not in model and not model.lower().startswith("ollama"):
            return f"openai/{model}"
        return model

    @staticmethod
    def _normalize_api_base(api_base: str | None) -> str:
        raw = str(api_base or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return raw.rstrip("/")
        path = parsed.path.rstrip("/")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))

    def fingerprint(self) -> str:
        payload = {
            "model": self._resolve_model(),
            "api_base": self._normalize_api_base(self.api_base),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    async def embed(
        self,
        inputs: list[str],
        *,
        source: str = "",
        operation: str = "",
        user_id: str = "",
        request_id: str = "",
    ) -> EmbeddingResponse:
        model_name = self._resolve_model()
        start = time.perf_counter()
        response = await aembedding(
            model=model_name,
            input=inputs,
            api_base=self.api_base,
            api_key=self.api_key or None,
            timeout=self.timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        vectors: list[list[float]] = []
        for item in getattr(response, "data", []) or []:
            embedding = item["embedding"] if isinstance(item, dict) else item.embedding
            vectors.append([float(v) for v in embedding])
        usage = self._extract_usage(response)
        metered = False
        cost_usd: float | None = None
        if self.usage_meter is not None:
            cost_usd = await self.usage_meter.record_embedding_call(
                model=model_name,
                usage=usage,
                source=source,
                operation=operation,
                user_id=user_id,
                request_id=request_id,
                duration_ms=duration_ms,
            )
            metered = True
        return EmbeddingResponse(
            vectors=vectors,
            usage=usage,
            raw=response,
            model=model_name,
            metered=metered,
            cost_usd=cost_usd,
        )
