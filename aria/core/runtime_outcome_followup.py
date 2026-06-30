from __future__ import annotations

import re
import shlex
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aria.core.action_plan import CapabilityDraft
from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.context_surfaces import RuntimeOutcomeFrame
from aria.core.pipeline_models import PipelineResult
from aria.core.router import RouterDecision


RuntimeActionRunner = Callable[
    [str, str, str, str, RouterDecision, float, CapabilityDraft, str | None],
    Awaitable[PipelineResult | None],
]
RuntimeSummaryBuilder = Callable[
    [str, str, list[dict[str, Any]], str, str | None],
    Awaitable[tuple[str, str]],
]
RuntimeFallbackBuilder = Callable[[RuntimeOutcomeFrame, str | None], str]


class RuntimeOutcomeFollowupResolver:
    def __init__(
        self,
        *,
        llm_client: Any,
        run_action: RuntimeActionRunner,
        summarize_updates: RuntimeSummaryBuilder,
        package_update_fallback: RuntimeFallbackBuilder,
    ) -> None:
        self.llm_client = llm_client
        self.run_action = run_action
        self.summarize_updates = summarize_updates
        self.package_update_fallback = package_update_fallback

    async def resolve(
        self,
        *,
        frame: RuntimeOutcomeFrame,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        language: str | None,
        start: float,
    ) -> PipelineResult | None:
        payload = frame.as_payload()
        if not payload or not frame.followup_affordances:
            return None
        direct_followup = await self.direct_followup_result(
            frame=frame,
            message=message,
            user_id=user_id,
            request_id=request_id,
            source=source,
            language=language,
            start=start,
        )
        if direct_followup is not None:
            return direct_followup
        if not self.should_run_followup_llm(message, frame):
            return None
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="runtime_outcome_followup_resolution",
            system=(
                "You decide whether the user message is a follow-up to ARIA's last runtime outcome. "
                "Return JSON only. Choose action=use_previous_outcome, rerun_previous_action, "
                "run_read_only_followup, new_meta_catalog_turn, or clarify. Use only the provided followup_affordances. "
                "Use use_previous_outcome for pronouns or references such as 'davon', 'those', "
                "'which of them', or requests to rank/explain the previous result. "
                "Use run_read_only_followup only when the user asks to inspect the same runtime target or a path/result "
                "from the previous output; then return target_ref and a concrete read-only SSH command. "
                "For SSH targets, return target_ref exactly as one of last_runtime_outcome.targets, without a kind prefix. "
                "For path inspection, use affordance=inspect_path when available. Do not invent data."
            ),
            payload={
                "message": str(message or "").strip(),
                "language": str(language or ""),
                "last_runtime_outcome": payload,
                "allowed_actions": [
                    "use_previous_outcome",
                    "rerun_previous_action",
                    "run_read_only_followup",
                    "new_meta_catalog_turn",
                    "clarify",
                ],
                "allowed_affordances": list(frame.followup_affordances),
            },
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not decision.ok:
            return None
        confidence = confidence_score(decision.payload.get("confidence"))
        action = str(decision.payload.get("action", "") or "").strip().lower()
        affordance = str(decision.payload.get("affordance", "") or "").strip().lower()
        allowed_affordances = set(frame.followup_affordances)
        requested_path = self.requested_path(dict(decision.payload or {}), message, frame)
        if action == "run_read_only_followup" and affordance not in allowed_affordances:
            if "inspect_path" in allowed_affordances:
                affordance = "inspect_path"
        if affordance not in allowed_affordances and requested_path and "inspect_path" in allowed_affordances:
            affordance = "inspect_path"
        if confidence < 0.62 or affordance not in allowed_affordances:
            return None
        if action == "run_read_only_followup":
            return await self.ssh_followup_action_result(
                frame=frame,
                decision_payload=dict(decision.payload or {}),
                message=message,
                user_id=user_id,
                request_id=request_id,
                source=source,
                language=language,
                start=start,
                confidence=confidence,
                affordance=affordance,
            )
        if action in {"new_meta_catalog_turn", "use_previous_outcome"} and affordance == "inspect_path" and requested_path:
            followup_payload = dict(decision.payload or {})
            followup_payload.setdefault("path", requested_path)
            if not str(followup_payload.get("command", "") or "").strip():
                followup_payload["command"] = self.inspect_path_command(requested_path)
            if not str(followup_payload.get("target_ref", "") or followup_payload.get("ref", "") or "").strip():
                followup_payload["target_ref"] = self.target_ref(followup_payload, frame)
            result = await self.ssh_followup_action_result(
                frame=frame,
                decision_payload=followup_payload,
                message=message,
                user_id=user_id,
                request_id=request_id,
                source=source,
                language=language,
                start=start,
                confidence=confidence,
                affordance=affordance,
            )
            if result is not None:
                result.detail_lines = [
                    "Routing Debug: runtime_outcome_followup normalized_from="
                    f"{action or '-'} source=frame_path_evidence path={requested_path}",
                    *list(result.detail_lines or []),
                ]
                return result
        if action != "use_previous_outcome":
            return None
        if frame.kind == "ssh" and frame.capability == "ssh_command" and frame.task_intent == "package_update_check":
            fallback_summary = self.package_update_fallback(frame, language)
            summary, summary_debug = await self.summarize_updates(
                str(message or "").strip(),
                frame.command,
                [dict(row) for row in frame.records],
                fallback_summary or frame.summary,
                language,
            )
            text = summary or fallback_summary or frame.summary
            detail_lines = [
                "Routing Debug: runtime_outcome_followup "
                f"action=use_previous_outcome affordance={affordance} "
                f"surface={frame.surface_id} kind={frame.kind} capability={frame.capability} "
                f"task_intent={frame.task_intent} targets={len(frame.targets)} confidence={confidence:.2f}",
            ]
            if summary_debug:
                detail_lines.append(summary_debug)
            return PipelineResult(
                request_id=request_id,
                text=text,
                usage=dict(decision.usage or {}),
                intents=["runtime_outcome_followup"],
                skill_errors=[],
                router_level=2,
                duration_ms=int((time.perf_counter() - start) * 1000),
                detail_lines=detail_lines,
            )
        return None

    async def direct_followup_result(
        self,
        *,
        frame: RuntimeOutcomeFrame,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        language: str | None,
        start: float,
    ) -> PipelineResult | None:
        if "inspect_path" not in set(frame.followup_affordances):
            return None
        requested_path = self.requested_path({}, message, frame)
        if not requested_path:
            return None
        target_ref = self.target_ref({}, frame)
        if not target_ref:
            return None
        result = await self.ssh_followup_action_result(
            frame=frame,
            decision_payload={
                "target_ref": target_ref,
                "path": requested_path,
                "command": self.inspect_path_command(requested_path),
            },
            message=message,
            user_id=user_id,
            request_id=request_id,
            source=source,
            language=language,
            start=start,
            confidence=0.90,
            affordance="inspect_path",
        )
        if result is not None:
            result.detail_lines = [
                "Routing Debug: runtime_outcome_followup fast_path=direct_path_evidence "
                f"path={requested_path} target={target_ref}",
                *list(result.detail_lines or []),
            ]
        return result

    async def ssh_followup_action_result(
        self,
        *,
        frame: RuntimeOutcomeFrame,
        decision_payload: dict[str, Any],
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        language: str | None,
        start: float,
        confidence: float,
        affordance: str,
    ) -> PipelineResult | None:
        if frame.kind != "ssh" or frame.capability != "ssh_command":
            return None
        command = str(decision_payload.get("command", "") or "").strip()
        targets = [str(target or "").strip() for target in frame.targets if str(target or "").strip()]
        target_ref = self.target_ref(decision_payload, frame)
        if not command and affordance == "inspect_path":
            path = self.requested_path(decision_payload, message, frame)
            if path and target_ref in set(targets):
                command = self.inspect_path_command(path)
        if not command or target_ref not in set(targets):
            return None
        draft = CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=target_ref,
            content=command,
            confidence=confidence,
            notes=[f"runtime_outcome_followup:{affordance}", "target_scope:single_target"],
        )
        result = await self.run_action(
            str(message or "").strip(),
            user_id,
            request_id,
            source,
            RouterDecision(intents=["runtime_action"], level=2),
            start,
            draft,
            language,
        )
        if result is None:
            return None
        result.detail_lines = [
            "Routing Debug: runtime_outcome_followup "
            f"action=run_read_only_followup affordance={affordance} "
            f"target={target_ref} command={command} confidence={confidence:.2f}",
            *list(result.detail_lines or []),
        ]
        return result

    @classmethod
    def should_run_followup_llm(cls, message: str, frame: RuntimeOutcomeFrame) -> bool:
        if cls.requested_path({}, message, frame):
            return True
        lower = str(message or "").strip().lower()
        lower_ascii = lower.translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )
        if frame.task_intent == "package_update_check":
            local_docs_scope = any(
                marker in lower_ascii
                for marker in (
                    "beipackzettel",
                    "dokument",
                    "document",
                    "pdf",
                    "medikament",
                    "glucosamin",
                    "inhaltsstoff",
                    "bestandteil",
                )
            )
            if local_docs_scope:
                return False
            return any(
                marker in lower_ascii
                for marker in (
                    "davon",
                    "diese",
                    "welche",
                    "paket",
                    "package",
                    "update",
                    "server",
                    "wichtig",
                    "prioritaet",
                    "priority",
                    "those",
                    "them",
                    "which",
                )
            )
        return False

    @staticmethod
    def target_ref(decision_payload: dict[str, Any], frame: RuntimeOutcomeFrame) -> str:
        target_ref = str(decision_payload.get("target_ref", "") or decision_payload.get("ref", "") or "").strip()
        if "/" in target_ref:
            target_kind, _, target_name = target_ref.partition("/")
            if target_kind.strip().lower() == str(frame.kind or "").strip().lower() and target_name.strip():
                target_ref = target_name.strip()
        targets = [str(target or "").strip() for target in frame.targets if str(target or "").strip()]
        if not target_ref and len(targets) == 1:
            target_ref = targets[0]
        return target_ref

    @staticmethod
    def clean_path_candidate(value: Any) -> str:
        clean = str(value or "").strip().strip("`'\".,;:)]}")
        if not clean.startswith("/") or "\x00" in clean or "\n" in clean or "\r" in clean:
            return ""
        if any(ch in clean for ch in ("|", ";", "&", "$", "`", "<", ">", "\\")):
            return ""
        while len(clean) > 1 and clean.endswith("/"):
            clean = clean[:-1]
        return clean

    @classmethod
    def posix_paths(cls, text: str) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"(?<![\w.-])/[A-Za-z0-9._~@%+=:,/-]*", str(text or "")):
            path = cls.clean_path_candidate(match.group(0))
            if not path or path == "/" or path in seen:
                continue
            seen.add(path)
            paths.append(path)
        return paths

    @classmethod
    def frame_paths(cls, frame: RuntimeOutcomeFrame) -> set[str]:
        texts = [str(frame.summary or "")]
        for row in frame.records:
            texts.append(str(row.get("raw_text", "") or row.get("text", "") or ""))
        paths: set[str] = set()
        for text in texts:
            paths.update(cls.posix_paths(text))
        return paths

    @classmethod
    def path_in_frame(cls, path: str, frame_paths: set[str]) -> bool:
        clean = cls.clean_path_candidate(path)
        if not clean:
            return False
        for frame_path in frame_paths:
            if clean == frame_path:
                return True
            if frame_path.startswith(clean.rstrip("/") + "/"):
                return True
        return False

    @classmethod
    def requested_path(
        cls,
        decision_payload: dict[str, Any],
        message: str,
        frame: RuntimeOutcomeFrame,
    ) -> str:
        frame_paths = cls.frame_paths(frame)
        if not frame_paths:
            return ""
        for key in ("path", "target_path", "directory", "dir", "requested_path"):
            path = cls.clean_path_candidate(decision_payload.get(key))
            if path and cls.path_in_frame(path, frame_paths):
                return path
        for path in cls.posix_paths(message):
            if cls.path_in_frame(path, frame_paths):
                return path
        return ""

    @classmethod
    def inspect_path_command(cls, path: str) -> str:
        clean = cls.clean_path_candidate(path)
        if not clean:
            return ""
        return f"ls -lah {shlex.quote(clean)}"
