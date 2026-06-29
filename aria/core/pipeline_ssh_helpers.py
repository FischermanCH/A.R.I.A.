from __future__ import annotations

import json
import re
import time
from typing import Any

from aria.core.action_plan import CapabilityDraft
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import connection_routing_spec
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_dossiers import build_ssh_target_dossier
from aria.core.connection_dossiers import with_capability_draft_updates
from aria.core.connection_semantic_resolver import build_connection_aliases
from aria.core.execution_dry_run import build_execution_preview_dry_run
from aria.core.execution_dry_run import build_payload_dry_run
from aria.core.execution_dry_run import evaluate_guardrail_confirm_dry_run
from aria.core.execution_dry_run_payloads import connection_row as payload_connection_row
from aria.core.execution_dry_run_payloads import read_row_list
from aria.core.execution_dry_run_payloads import read_row_value
from aria.core.guardrails import evaluate_guardrail
from aria.core.guardrails import resolve_guardrail_profile
from aria.core.pipeline_models import PipelineResult
from aria.core.pipeline_routing_debug_helpers import routing_debug_line
from aria.core.ssh_agentic_resolution import apply_agentic_ssh_command_resolution as core_apply_agentic_ssh_command_resolution
from aria.core.ssh_agentic_resolution import classify_ssh_requested_runtime_effect
from aria.core.ssh_guardrail_commands import combined_ssh_allow_commands
from aria.core.ssh_guardrail_commands import ssh_guardrail_allow_terms
from aria.core.ssh_policy import validate_ssh_readonly_policy


class PipelineSSHHelpersMixin:
    @staticmethod
    def _payload_multi_target_refs(payload: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        for item in list(payload.get("connection_refs", []) or []):
            clean = str(item or "").strip()
            if clean and clean not in refs:
                refs.append(clean)
        return refs

    @staticmethod
    def _multi_target_ssh_result_state(text: str) -> str:
        clean = str(text or "").strip().lower()
        if not clean:
            return "ok"
        critical_tokens = (
            "(kritisch)",
            "(critical)",
            "handlungsbedarf",
            "action required",
            "critical",
        )
        warning_tokens = (
            "(eng)",
            "(tight)",
            "(erhoeht)",
            "(elevated)",
            "beobachten",
            "watch",
            "failed units",
            "nicht erreichbar",
            "unreachable",
        )
        if any(token in clean for token in critical_tokens):
            return "attention"
        if any(token in clean for token in warning_tokens):
            return "attention"
        return "ok"

    @staticmethod
    def _storage_size_to_gib(value: str, unit: str) -> float | None:
        try:
            amount = float(str(value or "").strip().replace(",", "."))
        except ValueError:
            return None
        clean_unit = str(unit or "").strip().lower()
        if not clean_unit:
            return amount
        clean_unit = clean_unit.rstrip("b")
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
    def _extract_free_disk_threshold_gib(cls, message: str) -> tuple[float, str] | None:
        clean = str(message or "").strip().lower()
        if not clean:
            return None
        has_disk_context = any(
            token in clean
            for token in (
                "festplatte",
                "festplatten",
                "speicherplatz",
                "disk",
                "disks",
                "filesystem",
                "dateisystem",
            )
        )
        has_free_context = any(token in clean for token in ("frei", "freien", "free", "available", "avail"))
        if not has_disk_context or not has_free_context:
            return None
        match = re.search(r"(?:mehr\s+als|mindestens|minimum|at\s+least|more\s+than)?\s*(\d+(?:[.,]\d+)?)\s*(tib|tb|gib|gb|g|mib|mb|m)\b", clean)
        if not match:
            return None
        value = match.group(1)
        unit = match.group(2)
        threshold = cls._storage_size_to_gib(value, unit)
        if threshold is None or threshold <= 0:
            return None
        label_value = value.replace(",", ".")
        label_unit = unit.upper()
        if label_unit == "G":
            label_unit = "GB"
        elif label_unit == "M":
            label_unit = "MB"
        return threshold, f"{label_value}{label_unit}"

    @classmethod
    def _extract_summary_free_disk_gib(cls, text: str) -> tuple[float, str] | None:
        clean = str(text or "").strip()
        if not clean:
            return None
        patterns = (
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>tib|tb|gib|gb|g|mib|mb|m)\s+frei\b",
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>tib|tb|gib|gb|g|mib|mb|m)\s+free\b",
        )
        for pattern in patterns:
            match = re.search(pattern, clean, flags=re.IGNORECASE)
            if not match:
                continue
            gib = cls._storage_size_to_gib(match.group("value"), match.group("unit"))
            if gib is None:
                continue
            return gib, f"{match.group('value')}{match.group('unit')}"
        return None

    @classmethod
    def _multi_target_ssh_free_disk_measurements(cls, records: list[dict[str, str]]) -> list[dict[str, Any]]:
        measurements: list[dict[str, Any]] = []
        for row in records:
            parsed = cls._extract_summary_free_disk_gib(str(row.get("raw_text", "") or row.get("text", "") or ""))
            ref = str(row.get("ref", "") or "").strip()
            if not ref or not parsed:
                continue
            measurements.append({"ref": ref, "free_gib": parsed[0], "free_label": parsed[1]})
        return measurements

    @staticmethod
    def _multi_target_ssh_payload_facts(payload: dict[str, Any]) -> dict[str, Any]:
        facts = payload.get("facts")
        return facts if isinstance(facts, dict) else {}

    @staticmethod
    def _multi_target_ssh_summary_mentioned_below_count(summary: str) -> int | None:
        clean = str(summary or "").strip().lower()
        if not clean:
            return None
        patterns = (
            r"\b(\d+)\s+von\s+\d+\s+(?:server|servern|ssh-ziele|ssh targets|targets|hosts)\s+(?:unterschreiten|liegen\s+unter|sind\s+unter|below)",
            r"\b(?:von\s+\d+\s+servern\s+)?(?:unterschreiten|liegen\s+unter|sind\s+unter|below)\s+(\d+)\b",
            r"\b(\d+)\s+(?:server|servern|ssh-ziele|ssh targets|targets|hosts)\s+(?:unterschreiten|liegen\s+unter|sind\s+unter|below)",
            r"\b(\d+)\s+(?:die\s+)?(?:10-?gb|schwelle|threshold).{0,32}(?:unterschreiten|unter|below)",
            r"\b(?:unterschreiten|unter|below).{0,32}\b(\d+)\s+(?:server|servern|targets|hosts)",
        )
        for pattern in patterns:
            match = re.search(pattern, clean)
            if not match:
                continue
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _multi_target_ssh_refs_from_fact(value: Any) -> set[str]:
        if not isinstance(value, list):
            return set()
        return {str(item or "").strip() for item in value if str(item or "").strip()}

    def _validate_multi_target_ssh_summary_facts(
        self,
        *,
        summary: str,
        payload: dict[str, Any],
        records: list[dict[str, str]],
    ) -> tuple[float | None, str, list[str], list[str], list[dict[str, Any]]]:
        facts = self._multi_target_ssh_payload_facts(payload)
        raw_threshold = facts.get("threshold_gib")
        threshold_gib: float | None = None
        try:
            if raw_threshold is not None:
                threshold_gib = float(raw_threshold)
        except (TypeError, ValueError):
            threshold_gib = None
        threshold_label = str(facts.get("threshold_label", "") or "").strip()
        if threshold_gib is None or threshold_gib <= 0:
            return None, threshold_label, [], [], []
        if not threshold_label:
            threshold_label = f"{threshold_gib:g}GB"
        measurements = self._multi_target_ssh_free_disk_measurements(records)
        if not measurements:
            return threshold_gib, threshold_label, [], [], []
        expected_below = {row["ref"] for row in measurements if float(row["free_gib"]) < threshold_gib}
        expected_ok = {row["ref"] for row in measurements if float(row["free_gib"]) >= threshold_gib}
        llm_below = self._multi_target_ssh_refs_from_fact(facts.get("below_threshold_refs"))
        issues: list[str] = []
        if llm_below and llm_below != expected_below:
            missing = sorted(expected_below - llm_below)
            extra = sorted(llm_below - expected_below)
            if missing:
                issues.append(f"missing_below_refs={','.join(missing)}")
            if extra:
                issues.append(f"extra_below_refs={','.join(extra)}")
        mentioned_below_count = self._multi_target_ssh_summary_mentioned_below_count(summary)
        if mentioned_below_count is not None and mentioned_below_count != len(expected_below):
            issues.append(f"below_count_mismatch=summary:{mentioned_below_count},measured:{len(expected_below)}")
        return threshold_gib, threshold_label, sorted(expected_below), sorted(expected_ok), issues

    def _build_validated_multi_target_ssh_threshold_summary(
        self,
        *,
        language: str | None,
        target_count: int,
        threshold_label: str,
        below_refs: list[str],
        measurements: list[dict[str, Any]],
    ) -> str:
        by_ref = {str(row["ref"]): row for row in measurements}
        free_word = "free" if str(language or "").lower().startswith("en") else "frei"
        below_parts = [
            f"`{ref}` ({str(by_ref.get(ref, {}).get('free_label', '?'))} {free_word})"
            for ref in below_refs
        ]
        ok_count = max(0, target_count - len(below_refs))
        if not below_refs:
            return self._pipeline_text(
                language,
                "multi_target_ssh_disk_threshold_all_ok",
                "Overall: {ok_count}/{count} SSH targets have at least {threshold} free. No action required.",
                ok_count=ok_count,
                count=target_count,
                threshold=threshold_label,
            )
        return self._pipeline_text(
            language,
            "multi_target_ssh_disk_threshold_validated_mixed",
            "No, not everywhere: {below_count}/{count} SSH targets are below {threshold}: {below_refs}. The other {ok_count} targets meet the threshold.",
            below_count=len(below_refs),
            count=target_count,
            threshold=threshold_label,
            below_refs=", ".join(below_parts),
            ok_count=ok_count,
        )

    def _multi_target_ssh_operator_summary(
        self,
        *,
        language: str | None,
        target_count: int,
        records: list[dict[str, str]],
    ) -> str:
        ok_count = sum(1 for row in records if row.get("state") == "ok")
        attention_count = sum(1 for row in records if row.get("state") == "attention")
        blocked_count = sum(1 for row in records if row.get("state") == "blocked")
        error_count = sum(1 for row in records if row.get("state") == "error")
        if attention_count <= 0 and blocked_count <= 0 and error_count <= 0:
            return self._pipeline_text(
                language,
                "multi_target_ssh_operator_ok",
                "Overall: {ok_count}/{count} SSH targets look ok.",
                ok_count=ok_count,
                count=target_count,
            )
        return self._pipeline_text(
            language,
            "multi_target_ssh_operator_mixed",
            "Overall: {ok_count} ok, {attention_count} need attention, {blocked_count} blocked, {error_count} failed.",
            ok_count=ok_count,
            attention_count=attention_count,
            blocked_count=blocked_count,
            error_count=error_count,
        )

    @staticmethod
    def _multi_target_ssh_relevant_result_texts(records: list[dict[str, str]]) -> list[str]:
        has_attention = any(str(row.get("state", "") or "") != "ok" for row in records)
        if not has_attention:
            return []
        return [
            str(row.get("text", "") or "").strip()
            for row in records
            if str(row.get("state", "") or "") != "ok" and str(row.get("text", "") or "").strip()
        ]

    @staticmethod
    def _compact_multi_target_ssh_result_text(text: str, *, state: str) -> str:
        clean_lines = [
            re.sub(r"\s+", " ", str(line or "").strip())
            for line in str(text or "").splitlines()
            if str(line or "").strip()
        ]
        clean = "\n".join(clean_lines).strip()
        if not clean:
            return ""
        max_chars = 1200 if str(state or "").strip().lower() != "ok" else 420
        if len(clean) <= max_chars:
            return clean
        return f"{clean[:max_chars].rstrip()}..."

    async def _multi_target_ssh_llm_operator_summary(
        self,
        *,
        message: str,
        command: str,
        records: list[dict[str, str]],
        fallback_summary: str,
        language: str | None,
    ) -> tuple[str, str]:
        if self.llm_client is None or not records:
            return "", "Routing Debug: multi_target_ssh_summary skipped reason=no_llm_client_or_records"
        result_rows: list[dict[str, str]] = []
        for row in records:
            state = str(row.get("state", "") or "").strip()
            text = self._compact_multi_target_ssh_result_text(
                str(row.get("raw_text", "") or row.get("text", "") or "").strip(),
                state=state,
            )
            if not text:
                continue
            result_rows.append(
                {
                    "ref": str(row.get("ref", "") or "").strip(),
                    "state": state,
                    "result": text,
                }
            )
        if not result_rows:
            return "", ""
        lang = "en" if str(language or "").lower().startswith("en") else "de"
        messages = [
            {
                "role": "system",
                "content": (
                    "You summarize already executed ARIA multi-target SSH read-only results. "
                    "Do not propose or execute commands. Do not invent data. "
                    "Answer the user's exact question from the given results. "
                    "If the user mentions a threshold, compare every result against that threshold. "
                    "When a free-disk threshold is relevant, include a facts object with threshold_gib, "
                    "threshold_label, below_threshold_refs, near_threshold_refs, and ok_refs. "
                    "Keep the response concise and action-oriented. "
                    'Return JSON only: {"summary":"...","confidence":"low|medium|high","reason":"...",'
                    '"facts":{"threshold_gib":null,"threshold_label":"","below_threshold_refs":[],'
                    '"near_threshold_refs":[],"ok_refs":[]}}'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "language": lang,
                        "user_question": str(message or "").strip(),
                        "executed_command": str(command or "").strip(),
                        "targets": result_rows,
                        "deterministic_fallback_summary": str(fallback_summary or "").strip(),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            response = await self.llm_client.chat(
                messages,
                operation="ssh_multi_target_summary",
            )
        except Exception:
            return "", "Routing Debug: multi_target_ssh_summary skipped reason=llm_error"
        payload = self._extract_json_object(getattr(response, "content", "") or "")
        summary = str(payload.get("summary", "") or "").strip()
        if not summary:
            return "", "Routing Debug: multi_target_ssh_summary skipped reason=empty_or_invalid_response"
        confidence = str(payload.get("confidence", "") or "").strip().lower()
        if confidence not in {"high", "medium"}:
            return "", f"Routing Debug: multi_target_ssh_summary skipped reason=low_confidence confidence={confidence or '-'}"
        reason = str(payload.get("reason", "") or "").strip()
        threshold_gib, threshold_label, below_refs, _ok_refs, validation_issues = (
            self._validate_multi_target_ssh_summary_facts(summary=summary, payload=payload, records=records)
        )
        if validation_issues and threshold_gib:
            measurements = self._multi_target_ssh_free_disk_measurements(records)
            repair_messages = [
                {
                    "role": "system",
                    "content": (
                        "Repair an ARIA operator summary. The previous summary contradicted measured SSH "
                        "disk facts. Use the measured facts as authoritative. Do not propose commands. "
                        "Return JSON only with the same schema as before."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "language": lang,
                            "user_question": str(message or "").strip(),
                            "executed_command": str(command or "").strip(),
                            "previous_response": payload,
                            "validation_issues": validation_issues,
                            "validated_measurements": measurements,
                            "expected_below_threshold_refs": below_refs,
                            "threshold_gib": threshold_gib,
                            "threshold_label": threshold_label,
                            "deterministic_fallback_summary": str(fallback_summary or "").strip(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
            try:
                repair_response = await self.llm_client.chat(
                    repair_messages,
                    operation="ssh_multi_target_summary_repair",
                )
                repair_payload = self._extract_json_object(getattr(repair_response, "content", "") or "")
                repair_summary = str(repair_payload.get("summary", "") or "").strip()
                repair_confidence = str(repair_payload.get("confidence", "") or "").strip().lower()
                _repair_threshold, _repair_label, _repair_below, _repair_ok, repair_issues = (
                    self._validate_multi_target_ssh_summary_facts(
                        summary=repair_summary,
                        payload=repair_payload,
                        records=records,
                    )
                )
                if repair_summary and repair_confidence in {"high", "medium"} and not repair_issues:
                    repair_reason = str(repair_payload.get("reason", "") or "").strip()
                    return (
                        repair_summary,
                        "Routing Debug: multi_target_ssh_summary "
                        f"agentic_source=llm_decision confidence={repair_confidence} "
                        f"validation=repair reason={repair_reason or '-'}",
                    )
            except Exception:
                pass
            validated_summary = self._build_validated_multi_target_ssh_threshold_summary(
                language=language,
                target_count=len(records),
                threshold_label=threshold_label,
                below_refs=below_refs,
                measurements=measurements,
            )
            return (
                validated_summary,
                "Routing Debug: multi_target_ssh_summary "
                f"agentic_source=llm_decision confidence={confidence} validation=fallback "
                f"reason=fact_validation_failed issues={';'.join(validation_issues)}",
            )
        debug_line = (
            "Routing Debug: multi_target_ssh_summary "
            f"agentic_source=llm_decision confidence={confidence} reason={reason or '-'}"
        )
        return summary, debug_line

    def _preflight_multi_target_ssh_refs(
        self,
        refs: list[str],
        command: str,
    ) -> tuple[list[str], list[dict[str, str]], list[str]]:
        allowed_refs: list[str] = []
        blocked: list[dict[str, str]] = []
        detail_lines = [
            "Routing Debug: multi_target_ssh_preflight "
            f"refs={len(refs)} command={command}"
        ]
        for ref in refs:
            row = payload_connection_row(self.settings, "ssh", ref)
            if row is None:
                reason = "connection_not_found"
                blocked.append({"ref": ref, "reason": reason, "action": "block"})
                detail_lines.append(
                    "Routing Debug: multi_target_ssh_preflight_target "
                    f"ref={ref} action=block reason={reason}"
                )
                continue

            guardrail_ref = read_row_value(row, "guardrail_ref")
            guardrail_profile = resolve_guardrail_profile(self.settings, guardrail_ref)
            allow_commands = combined_ssh_allow_commands(
                read_row_list(row, "allow_commands"),
                ssh_guardrail_allow_terms(guardrail_profile),
            )
            policy = validate_ssh_readonly_policy(command, allow_commands=allow_commands)
            guardrail_decision = evaluate_guardrail(
                profile_ref=guardrail_ref,
                profile=guardrail_profile,
                kind="ssh_command",
                text=command,
            )
            if policy.action != "allow":
                blocked.append({"ref": ref, "reason": policy.reason, "action": policy.action})
                detail_lines.append(
                    "Routing Debug: multi_target_ssh_preflight_target "
                    f"ref={ref} action={policy.action} reason={policy.reason}"
                )
                continue
            if not guardrail_decision.allowed:
                reason = guardrail_decision.reason or "guardrail_blocked"
                blocked.append({"ref": ref, "reason": reason, "action": "block"})
                detail_lines.append(
                    "Routing Debug: multi_target_ssh_preflight_target "
                    f"ref={ref} action=block reason={reason} guardrail={guardrail_ref or '-'}"
                )
                continue

            allowed_refs.append(ref)
            detail_lines.append(
                "Routing Debug: multi_target_ssh_preflight_target "
                f"ref={ref} action=allow reason={policy.reason} guardrail={guardrail_ref or '-'}"
            )

        detail_lines.append(
            "Routing Debug: multi_target_ssh_preflight_result "
            f"allowed={len(allowed_refs)} blocked={len(blocked)}"
        )
        return allowed_refs, blocked, detail_lines

    def _ssh_command_allowed_for_all_refs(self, refs: list[str], command: str) -> bool:
        clean_command = str(command or "").strip()
        if not refs or not clean_command:
            return False
        for ref in refs:
            row = payload_connection_row(self.settings, "ssh", ref)
            if row is None:
                return False
            guardrail_ref = read_row_value(row, "guardrail_ref")
            guardrail_profile = resolve_guardrail_profile(self.settings, guardrail_ref)
            allow_commands = combined_ssh_allow_commands(
                read_row_list(row, "allow_commands"),
                ssh_guardrail_allow_terms(guardrail_profile),
            )
            if validate_ssh_readonly_policy(clean_command, allow_commands=allow_commands).action != "allow":
                return False
            if not evaluate_guardrail(
                profile_ref=guardrail_ref,
                profile=guardrail_profile,
                kind="ssh_command",
                text=clean_command,
            ).allowed:
                return False
        return True

    @staticmethod
    def _capability_draft_target_intent(capability_draft: Any | None) -> str:
        for note in list(getattr(capability_draft, "notes", []) or []):
            clean = str(note or "").strip().lower()
            if clean.startswith("target_intent:"):
                return clean.split(":", 1)[1].strip()
        return ""

    def _adapt_multi_target_ssh_operator_command(
        self,
        refs: list[str],
        command: str,
        message: str,
        capability_draft: Any | None = None,
    ) -> tuple[str, str]:
        clean_command = str(command or "").strip()
        target_intent = self._capability_draft_target_intent(capability_draft)
        if target_intent == "package_update_check":
            reason = "package_update"
        elif target_intent == "capacity_check":
            reason = "capacity"
        elif target_intent == "health_check":
            reason = "health"
        else:
            return clean_command, ""
        if clean_command.lower() not in {"", "uptime", "uptime -p"}:
            return clean_command, ""
        if reason == "package_update":
            for candidate in ("apt list --upgradable",):
                if self._ssh_command_allowed_for_all_refs(refs, candidate):
                    return candidate, reason
            return clean_command, ""
        for candidate in ("uptime -p && df -h && free -h", "uptime && df -h && free -h", "df -h && free -h", "df -h", "free -h"):
            if self._ssh_command_allowed_for_all_refs(refs, candidate):
                return candidate, reason
        return clean_command, ""

    @staticmethod
    def _looks_like_same_ssh_target_followup(message: str) -> bool:
        clean = re.sub(r"\s+", " ", str(message or "")).strip().lower()
        if not clean:
            return False
        spec = connection_routing_spec("ssh")
        for term in spec.follow_up_same_target_terms:
            clean_term = str(term or "").strip().lower()
            if not clean_term:
                continue
            if " " in clean_term:
                if clean_term in clean:
                    return True
                continue
            if re.search(rf"\b{re.escape(clean_term)}\b", clean):
                return True
        return False

    def _looks_like_ssh_followup_message(self, message: str, user_id: str, *, language: str | None = None) -> bool:
        clean = re.sub(r"\s+", " ", str(message or "")).strip()
        if not clean:
            return False
        recent = self._load_recent_capability_context(user_id)
        if str(recent.get("capability", "") or "").strip() != "ssh_command":
            return False
        if str(recent.get("connection_kind", "") or "").strip() != "ssh":
            return False
        lower = clean.lower()
        if self._looks_like_same_ssh_target_followup(clean):
            return True

        followup_starter = any(
            lower == term or lower.startswith(term + " ")
            for term in connection_routing_spec("ssh").follow_up_starter_terms
            if str(term).strip()
        )

        connection_pools = self._capability_routing_connection_pools()
        ssh_rows = dict(connection_pools.get("ssh", {}) or {})
        if not ssh_rows:
            return False
        alias_rows: dict[str, list[str]] = {}
        for ref, row in ssh_rows.items():
            clean_ref = str(ref).strip()
            if clean_ref:
                alias_rows[clean_ref] = build_connection_aliases("ssh", clean_ref, row)
        lexicon = self.capability_router._lexicon_for_language(language)
        explicit_kind, explicit_ref = self.capability_router._extract_explicit_connection_by_kind(
            clean,
            {"ssh": ssh_rows.keys()},
            lexicon,
            {"ssh": alias_rows} if alias_rows else None,
        )
        if explicit_kind == "ssh" and explicit_ref:
            return followup_starter or bool(re.search(r"\b(?:nochmal|erneut|wieder)\b", lower)) or bool(
                re.search(r"\bwie\s+sieht\s+es\b", lower)
            )
        requested_candidate = self.capability_router._extract_requested_connection_ref_hint(clean, "ssh", lexicon)
        if requested_candidate:
            return followup_starter or bool(re.search(r"\bwie\s+sieht\s+es\b", lower))
        return False

    def _rewrite_ssh_followup_message(self, message: str, user_id: str, *, language: str | None = None) -> str:
        clean_message = str(message or "").strip()
        if not clean_message:
            return clean_message
        if not self._looks_like_ssh_followup_message(clean_message, user_id, language=language):
            return clean_message

        recent = self._load_recent_capability_context(user_id)
        if str(recent.get("capability", "") or "").strip() != "ssh_command":
            return clean_message
        if str(recent.get("connection_kind", "") or "").strip() != "ssh":
            return clean_message

        connection_pools = self._capability_routing_connection_pools()
        ssh_rows = dict(connection_pools.get("ssh", {}) or {})
        if not ssh_rows:
            return clean_message
        alias_rows: dict[str, list[str]] = {}
        for ref, row in ssh_rows.items():
            clean_ref = str(ref).strip()
            if clean_ref:
                alias_rows[clean_ref] = build_connection_aliases("ssh", clean_ref, row)
        lexicon = self.capability_router._lexicon_for_language(language)
        explicit_kind, explicit_ref = self.capability_router._extract_explicit_connection_by_kind(
            clean_message,
            {"ssh": ssh_rows.keys()},
            lexicon,
            {"ssh": alias_rows} if alias_rows else None,
        )
        requested_candidate = self.capability_router._extract_requested_connection_ref_hint(clean_message, "ssh", lexicon)

        target_ref = explicit_ref if explicit_kind == "ssh" else ""
        target_phrase = requested_candidate if not target_ref else ""
        if not target_ref and not target_phrase and self._looks_like_same_ssh_target_followup(clean_message):
            target_ref = str(recent.get("connection_ref", "") or "").strip()

        if target_ref:
            rewrite_prefix = connection_routing_spec("ssh").follow_up_rewrite_prefix or "ssh"
            return f"{rewrite_prefix} {target_ref} {clean_message}"
        if target_phrase:
            rewrite_prefix = connection_routing_spec("ssh").follow_up_rewrite_prefix or "ssh"
            return f"{rewrite_prefix} {target_phrase} {clean_message}"
        return clean_message

    def _build_ssh_target_dossier(self, connection_ref: str, *, user_id: str = "") -> dict[str, Any]:
        rows = dict(self._capability_routing_connection_pools().get("ssh", {}) or {})
        recent = self._load_recent_capability_context(user_id) if user_id else {}
        dossier = build_ssh_target_dossier(rows, connection_ref, recent_context=recent)
        guardrail_ref = str(dossier.get("guardrail_ref", "") or "").strip()
        if not guardrail_ref:
            return dossier
        profile = resolve_guardrail_profile(self.settings, guardrail_ref)
        profile_kind = str(profile.get("kind", "") if isinstance(profile, dict) else getattr(profile, "kind", "")).strip()
        if profile_kind != "ssh_command":
            return dossier
        allow_terms = list(profile.get("allow_terms", []) or []) if isinstance(profile, dict) else list(getattr(profile, "allow_terms", []) or [])
        deny_terms = list(profile.get("deny_terms", []) or []) if isinstance(profile, dict) else list(getattr(profile, "deny_terms", []) or [])
        dossier["guardrail_allow_terms"] = [str(item).strip() for item in allow_terms if str(item).strip()]
        dossier["guardrail_deny_terms"] = [str(item).strip() for item in deny_terms if str(item).strip()]
        return dossier

    async def _apply_agentic_ssh_command_resolution(
        self,
        *,
        message: str,
        user_id: str = "",
        routing_decision: dict[str, Any] | None = None,
        action_debug: dict[str, Any] | None = None,
        capability_draft: Any | None = None,
        language: str | None = None,
        llm_client: Any | None = None,
    ) -> tuple[dict[str, Any], Any | None, str]:
        return await core_apply_agentic_ssh_command_resolution(
            client=self.llm_client if llm_client is None else llm_client,
            message=message,
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=capability_draft,
            language=language,
            build_ssh_target_dossier=self._build_ssh_target_dossier,
            extract_json_object=self._extract_json_object,
            normalize_spaces=self._normalize_spaces,
            routing_debug_enabled=self._routing_debug_enabled,
            msg=self._msg,
            with_capability_draft_updates=with_capability_draft_updates,
        )

    async def _refresh_resolved_agentic_ssh_command(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str = "",
        capability_draft: Any | None = None,
        language: str | None = None,
    ) -> tuple[dict[str, Any], Any | None]:
        routing_decision = dict(resolved.get("decision", {}) or {})
        if normalize_connection_kind(str(routing_decision.get("kind", "") or "")) != "ssh":
            return resolved, capability_draft
        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return resolved, capability_draft
        if str(action_decision.get("candidate_id", "") or "").strip() != "ssh_run_command":
            return resolved, capability_draft
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        working_draft = capability_draft
        if working_draft is None:
            working_draft = CapabilityDraft(
                capability=str(payload.get("capability", "") or "ssh_command").strip() or "ssh_command",
                connection_kind="ssh",
                explicit_connection_ref=str(payload.get("connection_ref", "") or "").strip(),
                requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
                path=str(payload.get("path", "") or "").strip(),
                content=str(payload.get("content", "") or "").strip(),
                plan_class=str(payload.get("plan_class", "") or "").strip(),
                behavior_profile=str(payload.get("behavior_profile", "") or "").strip(),
            )
        else:
            draft_updates: dict[str, Any] = {}
            if not str(getattr(working_draft, "content", "") or "").strip() and str(payload.get("content", "") or "").strip():
                draft_updates["content"] = str(payload.get("content", "") or "").strip()
            if not str(getattr(working_draft, "path", "") or "").strip() and str(payload.get("path", "") or "").strip():
                draft_updates["path"] = str(payload.get("path", "") or "").strip()
            if not str(getattr(working_draft, "explicit_connection_ref", "") or "").strip() and str(payload.get("connection_ref", "") or "").strip():
                draft_updates["explicit_connection_ref"] = str(payload.get("connection_ref", "") or "").strip()
            if not str(getattr(working_draft, "requested_connection_ref", "") or "").strip() and str(payload.get("requested_connection_ref", "") or "").strip():
                draft_updates["requested_connection_ref"] = str(payload.get("requested_connection_ref", "") or "").strip()
            if draft_updates:
                working_draft = with_capability_draft_updates(working_draft, **draft_updates)
        updated_action_debug, capability_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision=routing_decision,
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
            llm_client=self.llm_client,
        )
        resolved["action_debug"] = updated_action_debug
        original_payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        original_safety = dict((resolved.get("safety_debug") or {}).get("decision", {}) or {})
        original_execution = dict((resolved.get("execution_debug") or {}).get("decision", {}) or {})
        payload_debug = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
        )
        payload_debug = self._apply_capability_draft_overrides(
            payload_debug,
            capability_draft=capability_draft,
        )
        resolved["payload_debug"] = payload_debug
        recalculated_safety = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=payload_debug,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        recalculated_execution = build_execution_preview_dry_run(
            routing_decision=routing_decision,
            action_decision=dict((updated_action_debug or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=recalculated_safety,
            language=str(language or ""),
        )
        refreshed_payload_content = str((payload_debug.get("payload") or {}).get("content", "") or "").strip()
        original_payload_content = str(original_payload.get("content", "") or "").strip()
        updated_decision = dict((updated_action_debug or {}).get("decision", {}) or {})
        fallback_replaced_blocked_command = bool(updated_decision.get("guardrail_fallback_from")) or (
            refreshed_payload_content
            and refreshed_payload_content != original_payload_content
        )
        if str(original_safety.get("action", "") or "").strip().lower() == "block" and not fallback_replaced_blocked_command:
            resolved["safety_debug"] = {"available": True, "used": True, "status": "block", "visual_status": "block", "decision": original_safety}
            resolved["execution_debug"] = {"available": True, "used": True, "status": "block", "visual_status": "block", "decision": original_execution}
        else:
            resolved["safety_debug"] = recalculated_safety
            resolved["execution_debug"] = recalculated_execution
        if debug_line:
            resolved = self._append_debug_detail_lines(resolved, debug_line)
        return resolved, capability_draft

    async def _classify_ssh_runtime_effect_for_gate(
        self,
        message: str,
        user_id: str,
        *,
        capability_draft: Any | None,
        language: str | None = None,
    ) -> dict[str, str]:
        capability = normalize_capability(str(getattr(capability_draft, "capability", "") or ""))
        kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        if capability != "ssh_command" or kind != "ssh":
            return {"runtime_effect": "unknown", "confidence": "low", "reason": "not_ssh_command"}
        ssh_rows = getattr(getattr(self.settings, "connections", object()), "ssh", {}) or {}
        refs = sorted(str(ref or "").strip() for ref in dict(ssh_rows).keys() if str(ref or "").strip())
        connection_ref = (
            str(getattr(capability_draft, "explicit_connection_ref", "") or "").strip()
            or (refs[0] if refs else "")
        )
        if not connection_ref:
            return {"runtime_effect": "unknown", "confidence": "low", "reason": "missing_target"}
        return await classify_ssh_requested_runtime_effect(
            client=self.llm_client,
            message=message,
            connection_ref=connection_ref,
            command=str(getattr(capability_draft, "content", "") or "").strip(),
            user_id=user_id,
            language=language,
            build_ssh_target_dossier=self._build_ssh_target_dossier,
            extract_json_object=self._extract_json_object,
        )

    def _mutating_ssh_request_block_text(
        self,
        message: str,
        *,
        runtime_effect: dict[str, str],
        language: str | None = None,
    ) -> str:
        return "\n".join(
            [
                self._pipeline_text(language, "mutating_ssh_request_block.no_execution", "I did not run anything."),
                self._pipeline_text(
                    language,
                    "mutating_ssh_request_block.guardrail",
                    "Guardrail/SSH policy blocked this state-changing request.",
                ),
                self._pipeline_text(
                    language,
                    "mutating_ssh_request_block.no_readonly_fallback",
                    "ARIA will not replace it with a read-only status probe; ask for an explicit read-only check if you only want inspection.",
                ),
            ]
        )

    async def _build_mutating_ssh_request_block_result(
        self,
        *,
        message: str,
        user_id: str,
        request_id: str,
        source: str,
        decision: Any,
        start: float,
        capability_draft: Any | None,
        runtime_effect: dict[str, str],
        language: str | None = None,
    ) -> PipelineResult:
        duration_ms = int((time.perf_counter() - start) * 1000)
        detail_lines = [
            routing_debug_line(
                "ssh_requested_runtime_effect",
                {
                    "agentic_source": "llm_decision",
                    "runtime_effect": str(runtime_effect.get("runtime_effect", "") or "unknown"),
                    "confidence": str(runtime_effect.get("confidence", "") or "low"),
                    "reason": str(runtime_effect.get("reason", "") or "-") or "-",
                    "boundary": "pre_rag_action_gate",
                },
            )
        ]
        result = self._build_routed_action_result(
            request_id=request_id,
            decision=decision,
            duration_ms=duration_ms,
            intents=["capability:ssh_command"],
            text=self._mutating_ssh_request_block_text(message, runtime_effect=runtime_effect, language=language),
            detail_lines=detail_lines,
            skill_errors=[],
        )
        await self._log_result_usage_snapshot(
            request_id=request_id,
            user_id=user_id,
            intents=["capability:ssh_command"],
            router_level=decision.level,
            duration_ms=duration_ms,
            source=source,
            skill_errors=[],
            extraction_model="ssh_requested_runtime_effect",
        )
        return self._prepend_pre_rag_gate_debug(
            result,
            action_path="mutating_ssh_request_block",
            capability_draft=capability_draft,
        )

    def _should_backfill_missing_ssh_command(
        self,
        *,
        resolved: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        return (
            self._payload_missing_fields(payload) == ["content"]
            and str(payload.get("capability", "") or "").strip() == "ssh_command"
            and normalize_connection_kind(str(dict(resolved.get("decision", {}) or {}).get("kind", "") or "")) == "ssh"
            and not str(payload.get("content", "") or "").strip()
        )

    async def _refresh_missing_ssh_command_resolution(
        self,
        *,
        resolved: dict[str, Any],
        message: str,
        user_id: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        ssh_draft = CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=str(payload.get("connection_ref", "") or "").strip(),
            requested_connection_ref=str(payload.get("requested_connection_ref", "") or "").strip(),
            path=str(payload.get("path", "") or "").strip(),
            content="",
            plan_class=str(payload.get("plan_class", "") or "").strip().lower(),
            behavior_profile=str(payload.get("behavior_profile", "") or "").strip().lower(),
            notes=[
                str(item or "").strip()
                for item in list(payload.get("notes", []) or [])
                if str(item or "").strip()
            ],
        )
        refreshed_action_debug, refreshed_draft, debug_line = await self._apply_agentic_ssh_command_resolution(
            message=message,
            user_id=user_id,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_debug=dict(resolved.get("action_debug", {}) or {}),
            capability_draft=ssh_draft,
            language=language,
            llm_client=self.llm_client,
        )
        refreshed_payload = build_payload_dry_run(
            str(message or "").strip(),
            settings=self.settings,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_decision=dict((refreshed_action_debug or {}).get("decision", {}) or {}),
        )
        refreshed_payload = self._apply_capability_draft_overrides(
            refreshed_payload,
            capability_draft=refreshed_draft,
        )
        refreshed_safety = evaluate_guardrail_confirm_dry_run(
            self.settings,
            payload_debug=refreshed_payload,
            routing_decision=dict(resolved.get("decision", {}) or {}),
            language=str(language or ""),
        )
        refreshed_execution = build_execution_preview_dry_run(
            routing_decision=dict(resolved.get("decision", {}) or {}),
            action_decision=dict((refreshed_action_debug or {}).get("decision", {}) or {}),
            payload_debug=refreshed_payload,
            safety_debug=refreshed_safety,
            language=str(language or ""),
        )
        resolved["action_debug"] = refreshed_action_debug
        resolved["payload_debug"] = refreshed_payload
        resolved["safety_debug"] = refreshed_safety
        resolved["execution_debug"] = refreshed_execution
        if debug_line:
            resolved = self._append_debug_detail_lines(
                resolved,
                *[line for line in debug_line.splitlines() if line.strip()],
            )
        return resolved
