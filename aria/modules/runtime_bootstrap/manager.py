from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aria.modules.capability_context.store import CapabilityContextStore
from aria.modules.configuration_foundations.config import Settings, load_settings
from aria.modules.model_gateway_clients.llm import LLMClient
from aria.modules.native_web_llm.gateway import NativeWebLLMGateway
from aria.modules.native_web_llm.evidence import PublicWebEvidenceStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.platform_primitives.prompt_loader import PromptLoader
from aria.modules.model_usage_observability.usage_meter import UsageMeter


@dataclass(slots=True)
class RuntimeBundle:
    settings: Settings
    prompt_loader: PromptLoader
    usage_meter: UsageMeter
    llm_client: LLMClient
    pipeline: Pipeline
    web_llm_gateway: NativeWebLLMGateway | None = None


class RuntimeManager:
    def __init__(
        self,
        *,
        base_dir: Path,
        config_path: Path,
        initial_settings: Settings,
        capability_context_store: CapabilityContextStore,
    ) -> None:
        self._base_dir = base_dir
        self._config_path = config_path
        self._capability_context_store = capability_context_store
        self._lock = threading.RLock()
        self._bundle = self._build_runtime_bundle(initial_settings)
        self._startup_diagnostics = self.empty_startup_diagnostics()

    def _get_bundle(self) -> RuntimeBundle:
        with self._lock:
            return self._bundle

    @staticmethod
    def empty_startup_diagnostics() -> dict[str, Any]:
        return {
            "status": "warn",
            "checked_at": "",
            "checks": [],
        }

    def _build_runtime_bundle(self, runtime_settings: Settings) -> RuntimeBundle:
        runtime_prompt_loader = PromptLoader(self._base_dir / runtime_settings.prompts.persona)
        runtime_usage_meter = UsageMeter(runtime_settings)
        try:
            setattr(runtime_settings, "_aria_usage_meter", runtime_usage_meter)
        except Exception:
            pass
        runtime_llm_client = LLMClient(runtime_settings.llm, usage_meter=runtime_usage_meter)
        runtime_web_llm_gateway = (
            NativeWebLLMGateway(
                runtime_settings.web_llm,
                transport=runtime_settings.web_llm.transport,
                usage_meter=runtime_usage_meter,
            )
            if runtime_settings.web_llm.model
            else None
        )
        runtime_web_evidence_store = (
            PublicWebEvidenceStore(
                qdrant_url=runtime_settings.memory.qdrant_url,
                qdrant_api_key=runtime_settings.memory.qdrant_api_key,
                collection=runtime_settings.web_evidence.collection,
                read_timeout_ms=runtime_settings.web_evidence.read_timeout_ms,
                ttl_hours=runtime_settings.web_evidence.ttl_hours,
            )
            if runtime_settings.web_evidence.enabled
            and runtime_settings.memory.enabled
            and runtime_settings.memory.backend.lower() == "qdrant"
            else None
        )
        runtime_pipeline = Pipeline(
            settings=runtime_settings,
            prompt_loader=runtime_prompt_loader,
            llm_client=runtime_llm_client,
            capability_context_store=self._capability_context_store,
            usage_meter=runtime_usage_meter,
            web_llm_gateway=runtime_web_llm_gateway,
            web_evidence_store=runtime_web_evidence_store,
        )
        return RuntimeBundle(
            settings=runtime_settings,
            prompt_loader=runtime_prompt_loader,
            usage_meter=runtime_usage_meter,
            llm_client=runtime_llm_client,
            web_llm_gateway=runtime_web_llm_gateway,
            pipeline=runtime_pipeline,
        )

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def get_settings(self) -> Settings:
        return self._get_bundle().settings

    def get_prompt_loader(self) -> PromptLoader:
        return self._get_bundle().prompt_loader

    def get_usage_meter(self) -> UsageMeter:
        return self._get_bundle().usage_meter

    def get_llm_client(self) -> LLMClient:
        return self._get_bundle().llm_client

    def get_web_llm_gateway(self) -> NativeWebLLMGateway | None:
        return self._get_bundle().web_llm_gateway

    def get_pipeline(self) -> Pipeline:
        return self._get_bundle().pipeline

    def get_startup_diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._startup_diagnostics)

    def set_startup_diagnostics(self, diagnostics: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._startup_diagnostics = dict(diagnostics or {})
            return dict(self._startup_diagnostics)

    def reset_startup_diagnostics(self) -> dict[str, Any]:
        return self.set_startup_diagnostics(self.empty_startup_diagnostics())

    async def get_or_refresh_startup_diagnostics(
        self,
        refresher: Callable[[], Awaitable[dict[str, Any]]],
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        current = self.get_startup_diagnostics()
        if force_refresh or not current.get("checked_at"):
            refreshed = await refresher()
            return self.set_startup_diagnostics(refreshed)
        return current

    def reload_runtime(self) -> Settings:
        new_settings = load_settings(self._config_path)
        new_bundle = self._build_runtime_bundle(new_settings)
        with self._lock:
            self._bundle = new_bundle
            self._startup_diagnostics = self.empty_startup_diagnostics()
        return new_settings
