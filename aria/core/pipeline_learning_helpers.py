from __future__ import annotations

import asyncio
import sys
from typing import Any

from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.host_artifact_learning import host_artifact_discovery_outcome_events
from aria.core.artifact_review_patterns import recall_artifact_review_patterns
from aria.core.learned_recipe_curator import curate_learned_recipe_entry
from aria.core.learning_outcomes import active_learning_hint_outcome_event
from aria.core.learning_outcomes import capture_learning_outcome
from aria.core.learning_outcomes import capture_web_search_learning_outcome
from aria.core.learning_outcomes import recipe_catalog_outcome_event
from aria.core.learning_worker import enqueue_learning_job
from aria.core.recipe_experience_memory import store_recipe_experience_memory
from aria.skills.base import SkillResult


class PipelineLearningHelpersMixin:
    @staticmethod
    def _learning_symbol(name: str, fallback: Any) -> Any:
        pipeline_module = sys.modules.get("aria.core.pipeline")
        return getattr(pipeline_module, name, fallback)

    def _schedule_learned_recipe_followup(
        self,
        *,
        entry: dict[str, Any] | None,
        user_id: str,
        language: str,
        detail_lines: list[str],
        curate: bool = True,
    ) -> None:
        if not entry:
            return

        async def _run() -> None:
            learned_entry = dict(entry or {})
            if curate:
                learned_entry, _curation_debug = await curate_learned_recipe_entry(
                    llm_client=self.llm_client,
                    entry=learned_entry,
                    language=language,
                    user_id=user_id,
                )
            if learned_entry and self.memory_skill is not None:
                await self._learning_symbol("store_recipe_experience_memory", store_recipe_experience_memory)(
                    self.memory_skill,
                    user_id=user_id,
                    entry=learned_entry,
                )

        try:
            task = asyncio.create_task(_run())
        except RuntimeError:
            return

        def _consume_result(done: asyncio.Task[None]) -> None:
            try:
                done.result()
            except Exception:
                pass

        task.add_done_callback(_consume_result)

    def _schedule_learning_outcome_recording(
        self,
        *,
        skill_results: list[SkillResult],
        message: str,
        user_id: str,
        request_id: str,
        session_id: str = "",
    ) -> None:
        if self.memory_skill is None:
            return
        web_results = [result for result in skill_results if result.skill_name == "web_search"]
        if not web_results:
            return
        for result in web_results:
            enqueue_learning_job(
                job_type="web_search_outcome",
                user_id=user_id,
                source="web_search_outcome",
                artifact_type="source_rule_candidate",
                request_id=request_id,
                session_id=session_id,
                summary="Capture web-search source handling outcome.",
            factory=lambda result=result: self._learning_symbol("capture_web_search_learning_outcome", capture_web_search_learning_outcome)(
                    message=message,
                    user_id=user_id,
                    result=result,
                    memory_skill=self.memory_skill,
                    llm_client=self.llm_client,
                    request_id=request_id,
                    session_id=session_id,
                ),
            )

    def _schedule_capability_fallback_learning_outcome(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        capability_draft: Any | None,
        llm_state: str,
        source: str,
    ) -> None:
        if self.memory_skill is None or capability_draft is None:
            return
        event = {
            "event_type": "runtime_outcome",
            "artifact_type": "routing_hint",
            "status": "fallback_used",
            "risk": "medium",
            "user_id": user_id,
            "source": "capability_draft_local_fallback",
            "request_id": request_id,
            "summary": "Local capability fallback produced an action draft after bounded LLM draft was unavailable or uncertain.",
            "evidence": {
                "user_message": str(message or "").strip(),
                "outcome": "local_capability_fallback_used",
                "llm_state": str(llm_state or "").strip(),
                "capability": normalize_capability(str(getattr(capability_draft, "capability", "") or "")),
                "connection_kind": normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or "")),
                "requested_connection_ref": str(getattr(capability_draft, "requested_connection_ref", "") or "").strip(),
                "content": str(getattr(capability_draft, "content", "") or "").strip(),
            },
            "metadata": {
                "source": source,
                "draft_notes": [str(note or "") for note in list(getattr(capability_draft, "notes", []) or [])],
            },
        }

        enqueue_learning_job(
            job_type="capability_fallback_outcome",
            user_id=user_id,
            source=str(event.get("source") or "capability_draft_local_fallback"),
            artifact_type=str(event.get("artifact_type") or "routing_hint"),
            request_id=request_id,
            summary=str(event.get("summary") or ""),
            factory=lambda event=event: self._learning_symbol("capture_learning_outcome", capture_learning_outcome)(
                event=event,
                user_id=user_id,
                memory_skill=self.memory_skill,
                llm_client=self.llm_client,
            ),
        )

    def _schedule_runtime_learning_outcome(
        self,
        *,
        event: dict[str, Any] | None,
        user_id: str,
    ) -> None:
        if self.memory_skill is None or not event:
            return

        enqueue_learning_job(
            job_type="runtime_outcome",
            user_id=user_id,
            source=str(event.get("source") or "runtime_outcome"),
            artifact_type=str(event.get("artifact_type") or ""),
            request_id=str(event.get("request_id") or ""),
            session_id=str(event.get("session_id") or ""),
            summary=str(event.get("summary") or ""),
            factory=lambda event=event: self._learning_symbol("capture_learning_outcome", capture_learning_outcome)(
                event=event,
                user_id=user_id,
                memory_skill=self.memory_skill,
                llm_client=self.llm_client,
            ),
        )

    def _schedule_recipe_catalog_learning_outcome(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        catalog_debug_line: str,
        runtime_recipe_count: int,
        explicit_recipe_question: bool,
    ) -> None:
        self._schedule_runtime_learning_outcome(
            event=recipe_catalog_outcome_event(
                message=message,
                user_id=user_id,
                request_id=request_id,
                catalog_debug_line=catalog_debug_line,
                runtime_recipe_count=runtime_recipe_count,
                explicit_recipe_question=explicit_recipe_question,
            ),
            user_id=user_id,
        )

    def _schedule_active_learning_hint_outcome(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        session_id: str = "",
        active_hints: list[dict[str, Any]] | None = None,
        final_intents: list[str] | None = None,
        router_level: int = 0,
    ) -> None:
        event = active_learning_hint_outcome_event(
            message=message,
            user_id=user_id,
            request_id=request_id,
            session_id=session_id,
            active_hints=active_hints,
            final_intents=final_intents,
            router_level=router_level,
        )
        self._schedule_runtime_learning_outcome(event=event, user_id=user_id)

    async def _schedule_host_artifact_learning_outcomes(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        result_text: str,
        payload: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> None:
        artifact_review_patterns: list[dict[str, Any]] = []
        if self.memory_skill is not None:
            recall_query = " ".join(
                part
                for part in (
                    "pytest skeleton prepared artifact review pattern",
                    str(message or "").strip(),
                    str(result_text or "").strip()[:900],
                )
                if part
            )
            artifact_review_patterns = await recall_artifact_review_patterns(
                memory_skill=self.memory_skill,
                user_id=user_id,
                query=recall_query,
                limit=6,
            )
        for event in host_artifact_discovery_outcome_events(
            message=message,
            user_id=user_id,
            request_id=request_id,
            session_id=session_id,
            result_text=result_text,
            payload=payload or {},
            artifact_review_patterns=artifact_review_patterns,
        ):
            self._schedule_runtime_learning_outcome(event=event, user_id=user_id)
