from __future__ import annotations

import json
import re
from typing import Any

from aria.modules.execution_dry_run_payloads.payloads import connection_row as payload_connection_row
from aria.modules.execution_dry_run_payloads.payloads import read_row_list
from aria.modules.execution_dry_run_payloads.payloads import read_row_value
from aria.modules.runtime_guardrails.guardrails import evaluate_guardrail
from aria.modules.runtime_guardrails.guardrails import resolve_guardrail_profile
from aria.modules.ssh_policy.guardrail_commands import combined_ssh_allow_commands
from aria.modules.ssh_policy.guardrail_commands import ssh_guardrail_allow_terms
from aria.modules.ssh_policy.policy import validate_ssh_readonly_policy


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
    def _parse_disk_size_label(cls, text: str) -> tuple[float, str] | None:
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)([KMGTPE]i?B?|[kmgtpe]i?b?)", str(text or "").strip())
        if not match:
            return None
        gib = cls._storage_size_to_gib(match.group(1), match.group(2))
        if gib is None:
            return None
        return gib, str(text or "").strip()

    @classmethod
    def _extract_disk_measurement(cls, text: str) -> dict[str, Any] | None:
        clean_text = str(text or "").strip()
        if not clean_text:
            return None
        table_measurement = cls._extract_df_table_disk_measurement(clean_text)
        if table_measurement:
            return table_measurement
        return cls._extract_summary_disk_measurement(clean_text)

    @classmethod
    def _extract_df_table_disk_measurement(cls, text: str) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for line in str(text or "").splitlines():
            parts = str(line or "").strip().split()
            if not parts or parts[0].lower() == "filesystem" or len(parts) < 6:
                continue
            use_index = -1
            use_token = ""
            for index, part in enumerate(parts):
                if re.fullmatch(r"\d+(?:[.,]\d+)?%", part):
                    use_index = index
                    use_token = part
                    break
            if use_index < 3 or use_index + 1 >= len(parts):
                continue
            avail = cls._parse_disk_size_label(parts[use_index - 1])
            size = cls._parse_disk_size_label(parts[use_index - 3])
            used = cls._parse_disk_size_label(parts[use_index - 2])
            if not avail:
                continue
            try:
                use_pct = float(use_token.rstrip("%").replace(",", "."))
            except ValueError:
                continue
            candidates.append(
                {
                    "mount": parts[use_index + 1],
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
    def _extract_summary_disk_measurement(cls, text: str) -> dict[str, Any] | None:
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
        avail_gib = cls._storage_size_to_gib(free_match.group("value"), free_match.group("unit"))
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
    def _multi_target_ssh_free_disk_measurements(cls, records: list[dict[str, str]]) -> list[dict[str, Any]]:
        measurements: list[dict[str, Any]] = []
        for row in records:
            ref = str(row.get("ref", "") or "").strip()
            measurement = row.get("disk_measurement")
            if not isinstance(measurement, dict):
                measurement = cls._extract_disk_measurement(str(row.get("raw_text", "") or row.get("text", "") or ""))
            if not ref or not isinstance(measurement, dict):
                continue
            try:
                free_gib = float(measurement.get("avail_gib", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            free_label = str(measurement.get("avail_label", "") or "").strip()
            if not free_label:
                continue
            measurements.append({"ref": ref, "free_gib": free_gib, "free_label": free_label})
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
                "multi_target_ssh_operator_unreviewed",
                "{ok_count}/{count} SSH targets returned output; semantic assessment is unavailable.",
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
                        "structured_fallback_summary": str(fallback_summary or "").strip(),
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
                            "structured_fallback_summary": str(fallback_summary or "").strip(),
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
        if (
            clean_command.lower() not in {"", "uptime", "uptime -p"}
            and self._ssh_command_allowed_for_all_refs(refs, clean_command)
        ):
            return clean_command, ""
        if reason == "package_update":
            for candidate in ("apt list --upgradable",):
                if self._ssh_command_allowed_for_all_refs(refs, candidate):
                    return candidate, reason
            return clean_command, ""
        health_candidates = (
            "uptime -p && df -h / && free -h",
            "uptime && df -h / && free -h",
            "uptime -p && df -h && free -h",
            "uptime && df -h && free -h",
            "df -h && free -h",
            "df -h",
            "free -h",
        )
        for candidate in health_candidates:
            if self._ssh_command_allowed_for_all_refs(refs, candidate):
                return candidate, reason
        return clean_command, ""
