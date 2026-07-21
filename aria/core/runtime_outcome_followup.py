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
        if not self.should_claim_previous_outcome_on_review_failure(message, frame):
            return None
        decision = await BoundedDecisionClient(self.llm_client).decide_json(
            operation="runtime_outcome_followup_resolution",
            system=(
                "You decide whether the user message is a follow-up to ARIA's last runtime outcome. "
                "Return JSON only. Choose action=use_previous_outcome, rerun_previous_action, "
                "run_read_only_followup, new_meta_catalog_turn, or clarify. Use only the provided followup_affordances. "
                "Use use_previous_outcome for pronouns or references such as 'davon', 'those', "
                "'which of them', or requests to rank, filter, compare, list, or explain the previous result. "
                "For disk/capacity outcomes, use affordance=summarize_targets when the user asks which targets match "
                "a threshold, have the least/most free space, or should be listed from the previous result. "
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
            return self.previous_outcome_fallback_result(
                frame=frame,
                message=message,
                request_id=request_id,
                language=language,
                start=start,
                reason="decision_unavailable",
            )
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
            return self.previous_outcome_fallback_result(
                frame=frame,
                message=message,
                request_id=request_id,
                language=language,
                start=start,
                reason="invalid_or_low_confidence_review",
                decision_action=action,
                decision_affordance=affordance,
                confidence=confidence,
            )
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
            return self.previous_outcome_fallback_result(
                frame=frame,
                message=message,
                request_id=request_id,
                language=language,
                start=start,
                reason=f"review_action_{action or 'empty'}",
                decision_action=action,
                decision_affordance=affordance,
                confidence=confidence,
            )
        if (
            frame.kind == "ssh"
            and frame.capability == "ssh_command"
            and frame.task_intent in {"package_update_check", "capacity_check", "health_check"}
        ):
            fallback_summary = (
                self.package_update_fallback(frame, language)
                if frame.task_intent == "package_update_check"
                else str(frame.summary or "").strip()
            )
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

    def previous_outcome_fallback_result(
        self,
        *,
        frame: RuntimeOutcomeFrame,
        message: str,
        request_id: str,
        language: str | None,
        start: float,
        reason: str,
        decision_action: str = "",
        decision_affordance: str = "",
        confidence: float = 0.0,
    ) -> PipelineResult | None:
        if (
            frame.kind != "ssh"
            or frame.capability != "ssh_command"
            or frame.task_intent not in {"package_update_check", "capacity_check", "health_check"}
        ):
            return None
        if not self.should_claim_previous_outcome_on_review_failure(message, frame):
            return None
        text = ""
        affordance = decision_affordance if decision_affordance in set(frame.followup_affordances) else ""
        if frame.task_intent == "package_update_check":
            text, affordance = self.package_update_outcome_summary(frame, message, language, affordance=affordance)
        elif frame.task_intent in {"capacity_check", "health_check"}:
            text, affordance = self.capacity_outcome_summary(frame, message, language, affordance=affordance)
        if not text:
            return None
        return PipelineResult(
            request_id=request_id,
            text=text,
            usage={},
            intents=["runtime_outcome_followup"],
            skill_errors=[],
            router_level=2,
            duration_ms=int((time.perf_counter() - start) * 1000),
            detail_lines=[
                "Routing Debug: runtime_outcome_followup "
                f"action=use_previous_outcome affordance={affordance or '-'} "
                f"surface={frame.surface_id} kind={frame.kind} capability={frame.capability} "
                f"task_intent={frame.task_intent} targets={len(frame.targets)} confidence={confidence:.2f} "
                f"claim=fail_closed_previous_outcome reason={reason} "
                f"review_action={decision_action or '-'} review_affordance={decision_affordance or '-'}",
                "Routing Debug: runtime_outcome_evidence_contract "
                f"surface=runtime_outcome authority=runtime_records completeness=records "
                f"task_intent={frame.task_intent} records={len(frame.records)} "
                "claim_limits=observed_runtime_fields_only",
            ],
        )

    @classmethod
    def package_update_outcome_summary(
        cls,
        frame: RuntimeOutcomeFrame,
        message: str,
        language: str | None,
        *,
        affordance: str = "",
    ) -> tuple[str, str]:
        packages_by_ref: dict[str, list[str]] = {}
        securityish_by_ref: dict[str, list[str]] = {}
        for row in frame.records:
            ref = str(row.get("ref", "") or "").strip()
            if not ref:
                continue
            packages: list[str] = []
            securityish: list[str] = []
            raw_text = str(row.get("raw_text", "") or row.get("text", "") or "")
            for package, channel in cls.parse_apt_upgradable_packages(raw_text):
                if not package:
                    continue
                packages.append(package)
                if cls.package_update_line_is_security_relevant(package, channel):
                    securityish.append(package)
            packages_by_ref[ref] = packages
            securityish_by_ref[ref] = securityish
        if not packages_by_ref:
            return (
                "Ich habe den letzten Update-Check gefunden, aber darin keine auswertbaren Paketnamen erkannt. "
                "Ich lasse diese Frage deshalb nicht auf Web oder Inventory kippen.",
                affordance or "list_packages_by_server",
            )
        lower = cls.ascii_lower(message)
        if cls.asks_security_relevance(lower):
            rows: list[str] = []
            for ref, packages in sorted(securityish_by_ref.items(), key=lambda item: (-len(item[1]), item[0])):
                if not packages:
                    continue
                rows.append(f"- `{ref}`: {', '.join(packages[:8])}{', ...' if len(packages) > 8 else ''}")
            if not rows:
                return (
                    "Aus dem letzten `apt list --upgradable`-Lauf kann ich keine bestaetigte Sicherheitsrelevanz ableiten. "
                    "Dafuer braeuchte ich Advisory-/CVE-Metadaten oder einen neuen gezielten Security-Check. "
                    "Ich benutze dafuer bewusst keine RSS-/Web-Quellen als Ersatz fuer die beobachteten Paketdaten.",
                    "explain_update_relevance",
                )
            return (
                "Aus dem letzten `apt list --upgradable`-Lauf sind diese Pakete technisch sicherheitsnah oder aus Security-Kanaelen erkennbar. "
                "Das ist noch keine bestaetigte CVE-Einstufung ohne Advisory-Abgleich:\n" + "\n".join(rows),
                "explain_update_relevance",
            )
        ranked = sorted(packages_by_ref.items(), key=lambda item: (-len(item[1]), item[0]))
        if not ranked:
            return "", affordance or "rank_updates"
        rows = [f"- `{ref}`: {len(packages)} Updates" for ref, packages in ranked[:10]]
        return (
            "Aus dem letzten Runtime-Update-Check haben diese Server die meisten Updates:\n"
            + "\n".join(rows),
            affordance or "rank_updates",
        )

    @classmethod
    def capacity_outcome_summary(
        cls,
        frame: RuntimeOutcomeFrame,
        message: str,
        language: str | None,
        *,
        affordance: str = "",
    ) -> tuple[str, str]:
        measurements: list[dict[str, Any]] = []
        for row in frame.records:
            ref = str(row.get("ref", "") or "").strip()
            parsed = cls.disk_measurement_from_record(row)
            if ref and parsed:
                measurements.append({"ref": ref, **parsed})
        if not measurements:
            fallback = str(frame.summary or "").strip()
            if fallback:
                return (
                    fallback
                    + "\n\nIch habe den letzten Disk-Check gefunden, aber keine strukturierten `df`-Werte aus den Runtime-Records extrahiert. "
                    "Ich lasse diese Frage deshalb nicht auf das SSH-Config-Inventar kippen.",
                    affordance or "summarize_targets",
                )
            return "", affordance or "summarize_targets"
        lower = cls.ascii_lower(message)
        threshold = cls.percent_threshold(lower)
        if threshold is not None:
            over = sorted(
                [item for item in measurements if float(item.get("use_pct", 0.0)) > threshold],
                key=lambda item: (-float(item["use_pct"]), item["ref"]),
            )
            if not over:
                return (
                    f"Aus dem letzten Runtime-Disk-Check liegt kein Server ueber {threshold:g}% Festplattenbelegung.",
                    affordance or "summarize_targets",
                )
            rows = [
                f"- `{item['ref']}`: {item['use_pct']:g}% belegt, {item['avail_label']} frei"
                for item in over
            ]
            return (
                f"Aus dem letzten Runtime-Disk-Check liegen diese Server ueber {threshold:g}% Festplattenbelegung:\n"
                + "\n".join(rows),
                affordance or "summarize_targets",
            )
        if "wenigsten" in lower or "least" in lower:
            ranked = sorted(measurements, key=lambda item: (float(item["avail_gib"]), item["ref"]))
            rows = [
                f"- `{item['ref']}`: {item['avail_label']} frei, {item['use_pct']:g}% belegt"
                for item in ranked[:10]
            ]
            return (
                "Aus dem letzten Runtime-Disk-Check haben diese Server am wenigsten freien Speicher:\n"
                + "\n".join(rows),
                affordance or "summarize_targets",
            )
        if "meisten" in lower or "most" in lower:
            ranked = sorted(measurements, key=lambda item: (-float(item["avail_gib"]), item["ref"]))
            rows = [
                f"- `{item['ref']}`: {item['avail_label']} frei, {item['use_pct']:g}% belegt"
                for item in ranked[:10]
            ]
            return (
                "Aus dem letzten Runtime-Disk-Check haben diese Server am meisten freien Speicher:\n"
                + "\n".join(rows),
                affordance or "summarize_targets",
            )
        fallback = str(frame.summary or "").strip()
        if fallback:
            return fallback, affordance or "summarize_targets"
        return "", affordance or "summarize_targets"

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
        if frame.task_intent in {"capacity_check", "health_check"}:
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
                    "server",
                    "speicher",
                    "festplatte",
                    "festplatten",
                    "belegung",
                    "frei",
                    "freien",
                    "wenigsten",
                    "meisten",
                    "ueber",
                    "unter",
                    "disk",
                    "capacity",
                    "threshold",
                    "%",
                )
            )
        return False

    @classmethod
    def should_claim_previous_outcome_on_review_failure(cls, message: str, frame: RuntimeOutcomeFrame) -> bool:
        lower_ascii = cls.ascii_lower(message)
        if frame.task_intent == "package_update_check":
            return any(
                marker in lower_ascii
                for marker in (
                    "update",
                    "updates",
                    "paket",
                    "pakete",
                    "package",
                    "packages",
                    "sicherheit",
                    "sicherheits",
                    "security",
                    "cve",
                )
            )
        if frame.task_intent in {"capacity_check", "health_check"}:
            if "%" in lower_ascii or re.search(r"\b(?:ueber|unter|over|above|below|threshold)\b", lower_ascii):
                return True
            return any(
                marker in lower_ascii
                for marker in (
                    "speicher",
                    "festplatte",
                    "festplatten",
                    "belegung",
                    "frei",
                    "freien",
                    "wenigsten",
                    "meisten",
                    "disk",
                    "capacity",
                )
            )
        return False

    @staticmethod
    def ascii_lower(text: str) -> str:
        return str(text or "").strip().lower().translate(
            {
                ord(chr(228)): "ae",
                ord(chr(246)): "oe",
                ord(chr(252)): "ue",
                ord(chr(223)): "ss",
            }
        )

    @staticmethod
    def parse_apt_upgradable_line(line: str) -> tuple[str, str]:
        clean = str(line or "").strip()
        if "/" not in clean or "upgradable" not in clean.lower():
            return "", ""
        package, _, rest = clean.partition("/")
        package = package.strip()
        channel = rest.split(None, 1)[0].strip() if rest.strip() else ""
        if not package:
            return "", ""
        return package, channel

    @classmethod
    def parse_apt_upgradable_packages(cls, text: str) -> list[tuple[str, str]]:
        clean = str(text or "").strip()
        if "/" not in clean or "upgradable" not in clean.lower():
            return []
        rows: list[tuple[str, str]] = []
        pattern = re.compile(
            r"(?P<package>[A-Za-z0-9][A-Za-z0-9+._:-]*)/"
            r"(?P<channel>\S+)\s+\S+.*?\[upgradable[^\]]*\]",
            flags=re.IGNORECASE,
        )
        for match in pattern.finditer(clean):
            package = match.group("package").strip()
            channel = match.group("channel").strip()
            if package:
                rows.append((package, channel))
        if rows:
            return rows
        for line in clean.splitlines():
            package, channel = cls.parse_apt_upgradable_line(line)
            if package:
                rows.append((package, channel))
        return rows

    @staticmethod
    def package_update_line_is_security_relevant(package: str, channel: str) -> bool:
        package_lower = str(package or "").strip().lower()
        channel_lower = str(channel or "").strip().lower()
        if "security" in channel_lower or "-security" in channel_lower:
            return True
        priority_terms = (
            "apparmor",
            "apt",
            "bind9",
            "ca-certificates",
            "curl",
            "dpkg",
            "fwupd",
            "gnupg",
            "libc",
            "linux-headers",
            "linux-image",
            "openssl",
            "openssh",
            "sudo",
            "systemd",
        )
        return any(term in package_lower for term in priority_terms)

    @staticmethod
    def asks_security_relevance(lower_ascii: str) -> bool:
        return any(
            token in str(lower_ascii or "")
            for token in (
                "security",
                "sicherheit",
                "sicherheits",
                "sicherheitsrelevant",
                "cve",
                "vulnerability",
                "kritisch",
                "critical",
            )
        )

    @staticmethod
    def percent_threshold(lower_ascii: str) -> float | None:
        match = re.search(r"(?:ueber|over|above|mehr\s+als|>\s*)\s*(\d+(?:[.,]\d+)?)\s*%", str(lower_ascii or ""))
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    @classmethod
    def storage_size_to_gib(cls, value: str, unit: str) -> float | None:
        try:
            amount = float(str(value or "").strip().replace(",", "."))
        except ValueError:
            return None
        clean_unit = str(unit or "").strip().lower().rstrip("b")
        multipliers = {
            "k": 1 / (1024 * 1024),
            "ki": 1 / (1024 * 1024),
            "m": 1 / 1024,
            "mi": 1 / 1024,
            "g": 1,
            "gi": 1,
            "t": 1024,
            "ti": 1024,
        }
        multiplier = multipliers.get(clean_unit)
        if multiplier is None:
            return None
        return amount * multiplier

    @classmethod
    def parse_storage_size(cls, text: str) -> tuple[float, str] | None:
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)([KMGTPE]i?B?|[kmgtpe]i?b?)", str(text or "").strip())
        if not match:
            return None
        gib = cls.storage_size_to_gib(match.group(1), match.group(2))
        if gib is None:
            return None
        return gib, str(text or "").strip()

    @classmethod
    def parse_df_measurement(cls, text: str) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for line in str(text or "").splitlines():
            clean = line.strip()
            if not clean:
                continue
            parts = clean.split()
            if parts and parts[0].lower() == "filesystem":
                for index in range(len(parts) - 1):
                    if parts[index].lower() == "mounted" and parts[index + 1].lower() == "on":
                        parts = parts[index + 2 :]
                        break
                else:
                    continue
            else:
                parts = clean.split()
            if len(parts) < 6:
                continue
            use_token = ""
            use_index = -1
            for index, part in enumerate(parts):
                if re.fullmatch(r"\d+(?:[.,]\d+)?%", part):
                    use_token = part
                    use_index = index
                    break
            if use_index < 3 or use_index + 1 >= len(parts):
                continue
            avail = cls.parse_storage_size(parts[use_index - 1])
            size = cls.parse_storage_size(parts[use_index - 3])
            used = cls.parse_storage_size(parts[use_index - 2])
            if not avail:
                continue
            try:
                use_pct = float(use_token.rstrip("%").replace(",", "."))
            except ValueError:
                continue
            mount = parts[use_index + 1]
            candidates.append(
                {
                    "mount": mount,
                    "size_gib": size[0] if size else 0.0,
                    "size_label": size[1] if size else "",
                    "used_gib": used[0] if used else 0.0,
                    "used_label": used[1] if used else "",
                    "avail_gib": avail[0],
                    "avail_label": avail[1],
                    "use_pct": use_pct,
                }
            )
        if not candidates:
            return None
        for candidate in candidates:
            if candidate.get("mount") == "/":
                return candidate
        return candidates[0]

    @classmethod
    def parse_summary_disk_measurement(cls, text: str) -> dict[str, Any] | None:
        clean = re.sub(r"\s+", " ", str(text or "").strip())
        if not clean:
            return None
        pct_match = re.search(r"(?P<pct>\d+(?:[.,]\d+)?)\s*%\s*(?:belegt|used|usage|ausgelastet)", clean, flags=re.IGNORECASE)
        free_match = re.search(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>tib|tb|gib|gb|g|mib|mb|m)\s+(?:frei|free|available)",
            clean,
            flags=re.IGNORECASE,
        )
        if not pct_match or not free_match:
            return None
        try:
            use_pct = float(pct_match.group("pct").replace(",", "."))
        except ValueError:
            return None
        avail_gib = cls.storage_size_to_gib(free_match.group("value"), free_match.group("unit"))
        if avail_gib is None:
            return None
        return {
            "mount": "/",
            "size_gib": 0.0,
            "size_label": "",
            "used_gib": 0.0,
            "used_label": "",
            "avail_gib": avail_gib,
            "avail_label": f"{free_match.group('value')}{free_match.group('unit')}",
            "use_pct": use_pct,
        }

    @classmethod
    def disk_measurement_from_record(cls, row: dict[str, Any]) -> dict[str, Any] | None:
        measurement = row.get("disk_measurement")
        if isinstance(measurement, dict):
            try:
                return {
                    "mount": str(measurement.get("mount", "") or "/"),
                    "size_gib": float(measurement.get("size_gib", 0.0) or 0.0),
                    "size_label": str(measurement.get("size_label", "") or ""),
                    "used_gib": float(measurement.get("used_gib", 0.0) or 0.0),
                    "used_label": str(measurement.get("used_label", "") or ""),
                    "avail_gib": float(measurement.get("avail_gib", 0.0) or 0.0),
                    "avail_label": str(measurement.get("avail_label", "") or ""),
                    "use_pct": float(measurement.get("use_pct", 0.0) or 0.0),
                }
            except (TypeError, ValueError):
                pass
        parsed = cls.parse_df_measurement(str(row.get("raw_text", "") or row.get("text", "") or ""))
        if parsed:
            return parsed
        return cls.parse_summary_disk_measurement(str(row.get("raw_text", "") or row.get("text", "") or ""))

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
