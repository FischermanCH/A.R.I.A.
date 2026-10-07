from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from aria.modules.configuration_foundations.config import Settings
from aria.modules.model_usage_observability.pricing_catalog import resolve_pricing_entry
from aria.modules.model_usage_observability.token_tracker import TokenTracker


def _empty_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _empty_embedding_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


@dataclass
class UsageScope:
    request_id: str
    user_id: str
    source: str
    router_level: int
    llm_usage: dict[str, int] = field(default_factory=_empty_usage)
    embedding_usage: dict[str, int] = field(default_factory=_empty_embedding_usage)
    chat_model: str = ""
    embedding_model: str = ""
    chat_cost_usd: float | None = None
    embedding_cost_usd: float | None = None
    llm_role: str = "main"
    native_web_search_uses: int = 0
    native_web_search_cost_usd: float | None = None
    flushed: bool = False


class UsageMeter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.token_tracker = TokenTracker(
            log_file=settings.token_tracking.log_file,
            enabled=settings.token_tracking.enabled,
        )
        self._scope_var: ContextVar[UsageScope | None] = ContextVar("aria_usage_scope", default=None)

    @staticmethod
    def _add_usage(target: dict[str, int], usage: dict[str, int], *, count_call: bool = False) -> None:
        target["prompt_tokens"] = int(target.get("prompt_tokens", 0) or 0) + int(usage.get("prompt_tokens", 0) or 0)
        target["completion_tokens"] = int(target.get("completion_tokens", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)
        target["total_tokens"] = int(target.get("total_tokens", 0) or 0) + int(usage.get("total_tokens", 0) or 0)
        if count_call:
            target["calls"] = int(target.get("calls", 0) or 0) + 1

    @staticmethod
    def _merge_cost(current: float | None, value: float | None) -> float | None:
        if value is None:
            return current
        if current is None:
            return float(value)
        return float(current) + float(value)

    @staticmethod
    def _clean_source(source: str, operation: str) -> str:
        clean = str(source or "").strip().lower().replace(" ", "_")
        if clean:
            return clean
        clean_operation = str(operation or "").strip().lower().replace(" ", "_")
        return clean_operation or "system"

    @staticmethod
    def _build_intents(kind: str, operation: str, source: str) -> list[str]:
        clean_operation = str(operation or "").strip().lower().replace(" ", "_")
        clean_source = str(source or "").strip().lower().replace(" ", "_")
        label = clean_operation or clean_source or "direct"
        return [f"{kind}:{label}"]

    @staticmethod
    def _usage_cost(
        *,
        usage: dict[str, int],
        price_cfg: Any | None,
        is_embedding: bool,
    ) -> float | None:
        if price_cfg is None:
            return None
        if is_embedding:
            input_tokens = int(usage.get("prompt_tokens", 0) or usage.get("total_tokens", 0) or 0)
            return (input_tokens * float(price_cfg.input_per_million)) / 1_000_000
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        return (
            (prompt_tokens * float(price_cfg.input_per_million))
            + (completion_tokens * float(price_cfg.output_per_million))
        ) / 1_000_000

    def _resolve_pricing_entry(self, entries: dict[str, Any], model_name: str) -> Any | None:
        return resolve_pricing_entry(
            entries,
            model_name,
            model_aliases=getattr(self.settings.pricing, "model_aliases", {}),
        )

    def current_scope(self) -> UsageScope | None:
        return self._scope_var.get()

    @contextmanager
    def scope(self, *, request_id: str, user_id: str, source: str, router_level: int) -> Any:
        existing = self.current_scope()
        if existing is not None:
            yield existing
            return
        scope = UsageScope(
            request_id=str(request_id or "").strip() or str(uuid4()),
            user_id=str(user_id or "").strip() or "web",
            source=self._clean_source(source, ""),
            router_level=int(router_level or 0),
        )
        token = self._scope_var.set(scope)
        try:
            yield scope
        finally:
            self._scope_var.reset(token)

    async def record_llm_call(
        self,
        *,
        model: str,
        usage: dict[str, int],
        source: str = "",
        operation: str = "",
        user_id: str = "",
        request_id: str = "",
        duration_ms: int = 0,
    ) -> float | None:
        usage_dict = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        }
        cost: float | None = None
        if self.settings.pricing.enabled:
            price_cfg = self._resolve_pricing_entry(self.settings.pricing.chat_models, model)
            cost = self._usage_cost(usage=usage_dict, price_cfg=price_cfg, is_embedding=False)

        scope = self.current_scope()
        if scope is not None:
            self._add_usage(scope.llm_usage, usage_dict)
            if model:
                scope.chat_model = str(model).strip()
            scope.chat_cost_usd = self._merge_cost(scope.chat_cost_usd, cost)
            return cost

        effective_source = self._clean_source(source, operation)
        await self.token_tracker.log(
            request_id=str(request_id or "").strip() or str(uuid4()),
            user_id=str(user_id or "").strip() or "system",
            intents=self._build_intents("llm", operation, effective_source),
            router_level=0,
            usage=usage_dict,
            chat_model=str(model or "").strip(),
            embedding_model="",
            embedding_usage=_empty_embedding_usage(),
            chat_cost_usd=cost,
            embedding_cost_usd=None,
            total_cost_usd=cost,
            duration_ms=int(duration_ms or 0),
            source=effective_source,
            skill_errors=[],
        )
        return cost

    async def record_web_llm_call(
        self,
        *,
        model: str,
        usage: dict[str, int],
        native_search_uses: int,
        source: str = "",
        operation: str = "native_web_answer",
        user_id: str = "",
        request_id: str = "",
        duration_ms: int = 0,
    ) -> float | None:
        usage_dict = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        }
        search_uses = max(0, int(native_search_uses or 0))
        token_cost: float | None = None
        search_cost: float | None = None
        if self.settings.pricing.enabled:
            price_cfg = self._resolve_pricing_entry(self.settings.pricing.chat_models, model)
            token_cost = self._usage_cost(usage=usage_dict, price_cfg=price_cfg, is_embedding=False)
            per_search = getattr(price_cfg, "native_web_search_per_call", None) if price_cfg is not None else None
            if per_search is not None:
                search_cost = search_uses * float(per_search)
        cost = self._merge_cost(token_cost, search_cost)

        scope = self.current_scope()
        if scope is not None:
            self._add_usage(scope.llm_usage, usage_dict)
            scope.chat_model = str(model or "").strip()
            scope.llm_role = "web"
            scope.native_web_search_uses += search_uses
            scope.native_web_search_cost_usd = self._merge_cost(scope.native_web_search_cost_usd, search_cost)
            scope.chat_cost_usd = self._merge_cost(scope.chat_cost_usd, cost)
            return cost

        effective_source = self._clean_source(source, operation)
        await self.token_tracker.log(
            request_id=str(request_id or "").strip() or str(uuid4()),
            user_id=str(user_id or "").strip() or "system",
            intents=self._build_intents("llm", operation, effective_source),
            router_level=0,
            usage=usage_dict,
            chat_model=str(model or "").strip(),
            embedding_model="",
            embedding_usage=_empty_embedding_usage(),
            chat_cost_usd=cost,
            embedding_cost_usd=None,
            total_cost_usd=cost,
            duration_ms=int(duration_ms or 0),
            source=effective_source,
            skill_errors=[] if search_uses <= 3 else ["native_web_search_budget_exceeded"],
            llm_role="web",
            native_web_search_uses=search_uses,
            native_web_search_cost_usd=search_cost,
        )
        return cost

    async def record_embedding_call(
        self,
        *,
        model: str,
        usage: dict[str, int],
        source: str = "",
        operation: str = "",
        user_id: str = "",
        request_id: str = "",
        duration_ms: int = 0,
    ) -> float | None:
        usage_dict = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
            "calls": max(1, int(usage.get("calls", 0) or 0)),
        }
        cost: float | None = None
        if self.settings.pricing.enabled:
            price_cfg = self._resolve_pricing_entry(self.settings.pricing.embedding_models, model)
            cost = self._usage_cost(usage=usage_dict, price_cfg=price_cfg, is_embedding=True)

        scope = self.current_scope()
        if scope is not None:
            self._add_usage(scope.embedding_usage, usage_dict, count_call=True)
            if model:
                scope.embedding_model = str(model).strip()
            scope.embedding_cost_usd = self._merge_cost(scope.embedding_cost_usd, cost)
            return cost

        effective_source = self._clean_source(source, operation)
        await self.token_tracker.log(
            request_id=str(request_id or "").strip() or str(uuid4()),
            user_id=str(user_id or "").strip() or "system",
            intents=self._build_intents("embedding", operation, effective_source),
            router_level=0,
            usage=_empty_usage(),
            chat_model="",
            embedding_model=str(model or "").strip(),
            embedding_usage=usage_dict,
            chat_cost_usd=None,
            embedding_cost_usd=cost,
            total_cost_usd=cost,
            duration_ms=int(duration_ms or 0),
            source=effective_source,
            skill_errors=[],
        )
        return cost

    def snapshot_scope(self, scope: UsageScope | None) -> dict[str, Any]:
        active_scope = scope or self.current_scope()
        if active_scope is None:
            return {
                "usage": _empty_usage(),
                "embedding_usage": _empty_embedding_usage(),
                "chat_model": "",
                "embedding_model": "",
                "chat_cost_usd": None,
                "embedding_cost_usd": None,
                "total_cost_usd": None,
                "llm_role": "",
                "native_web_search_uses": 0,
                "native_web_search_cost_usd": None,
            }
        total_cost: float | None = None
        for value in (active_scope.chat_cost_usd, active_scope.embedding_cost_usd):
            total_cost = self._merge_cost(total_cost, value)
        return {
            "usage": dict(active_scope.llm_usage),
            "embedding_usage": dict(active_scope.embedding_usage),
            "chat_model": active_scope.chat_model,
            "embedding_model": active_scope.embedding_model,
            "chat_cost_usd": active_scope.chat_cost_usd,
            "embedding_cost_usd": active_scope.embedding_cost_usd,
            "total_cost_usd": total_cost,
            "llm_role": active_scope.llm_role,
            "native_web_search_uses": active_scope.native_web_search_uses,
            "native_web_search_cost_usd": active_scope.native_web_search_cost_usd,
        }

    async def flush_current_scope(
        self,
        *,
        intents: list[str],
        duration_ms: int,
        skill_errors: list[str] | None = None,
        activity: dict[str, Any] | None = None,
    ) -> bool:
        scope = self.current_scope()
        if scope is None or scope.flushed:
            return False
        snapshot = self.snapshot_scope(scope)
        await self.token_tracker.log(
            request_id=scope.request_id,
            user_id=scope.user_id,
            intents=list(intents),
            router_level=scope.router_level,
            usage=dict(snapshot["usage"]),
            chat_model=str(snapshot["chat_model"]),
            embedding_model=str(snapshot["embedding_model"]),
            embedding_usage=dict(snapshot["embedding_usage"]),
            chat_cost_usd=snapshot["chat_cost_usd"],
            embedding_cost_usd=snapshot["embedding_cost_usd"],
            total_cost_usd=snapshot["total_cost_usd"],
            duration_ms=max(0, int(duration_ms or 0)),
            source=scope.source,
            skill_errors=list(skill_errors or []),
            llm_role=str(snapshot["llm_role"] or "main"),
            native_web_search_uses=int(snapshot["native_web_search_uses"] or 0),
            native_web_search_cost_usd=snapshot["native_web_search_cost_usd"],
            activity=activity,
        )
        scope.flushed = True
        return True
