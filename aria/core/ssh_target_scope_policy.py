from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aria.core.action_plan import CapabilityDraft
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_ref_scope import ConnectionRefScope
from aria.core.connection_semantic_resolver import ConnectionSemanticResolver
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.connection_dossiers import with_capability_draft_updates
from aria.core.pipeline_action_flow_helpers import append_debug_detail_lines
from aria.core.pipeline_action_flow_helpers import prune_satisfied_payload_missing_fields
from aria.core.ssh_policy import validate_ssh_readonly_policy


@dataclass(slots=True)
class SshTargetScopeNarrowing:
    resolved: dict[str, Any]
    candidate_connections: dict[str, Any]
    semantic_candidates: list[SemanticConnectionCandidate]


@dataclass(slots=True)
class SshPluralCommandPreparation:
    resolved: dict[str, Any]
    capability_draft: Any | None


@dataclass(slots=True)
class SshTargetScopeDecision:
    resolved: dict[str, Any]
    plural_target_scope: bool
    candidate_connections: dict[str, Any]


class SshTargetScopePolicy:
    def __init__(
        self,
        *,
        resolver: ConnectionSemanticResolver,
        routing_debug_enabled: Callable[[], bool],
    ) -> None:
        self._resolver = resolver
        self._routing_debug_enabled = routing_debug_enabled

    def should_finalize_plural_multi_target_action(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        capability_draft: Any | None,
        looks_like_plural_target: Callable[[str, str], bool] | None,
    ) -> bool:
        _ = (message, looks_like_plural_target)
        draft_multi_target_scope = self.capability_draft_has_multi_target_scope(capability_draft)
        resolved_multi_target_scope = any(
            "plural_target_scope blocks_single_target_resolution" in str(line or "")
            for line in list(resolved.get("detail_lines", []) or [])
        )
        if not draft_multi_target_scope and not resolved_multi_target_scope:
            return False

        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        if self._payload_multi_target_refs(payload):
            return False
        if str(payload.get("connection_ref", "") or "").strip():
            return False
        routing_decision = dict(resolved.get("decision", {}) or {})
        if str(routing_decision.get("ref", "") or "").strip():
            return False

        action_decision = dict((resolved.get("action_debug") or {}).get("decision", {}) or {})
        if str(action_decision.get("candidate_kind", "") or "").strip().lower() != "template":
            return False
        if str(action_decision.get("candidate_id", "") or "").strip() != "ssh_run_command":
            return False

        payload_kind = normalize_connection_kind(str(payload.get("connection_kind", "") or ""))
        draft_kind = normalize_connection_kind(str(getattr(capability_draft, "connection_kind", "") or ""))
        return payload_kind in {"", "ssh"} and draft_kind in {"", "ssh"}

    def resolve_requested_connection_scope(
        self,
        *,
        resolved: dict[str, Any],
        message: str,
        effective_kind: str,
        looks_like_plural_target: Callable[[str, str], bool] | None,
        candidate_connections: dict[str, Any],
        working_draft: Any,
        ref_scope: ConnectionRefScope,
    ) -> SshTargetScopeDecision:
        plural_target_scope = self.capability_draft_has_multi_target_scope(working_draft)
        explicit_ref = self._explicit_single_ref_from_scope_or_resolution(
            ref_scope=ref_scope,
            working_draft=working_draft,
            resolved=resolved,
        )
        if (
            plural_target_scope
            and effective_kind == "ssh"
            and explicit_ref
        ):
            plural_target_scope = False
            resolved = append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope disabled_by_explicit_single_target "
                f"explicit_ref={explicit_ref}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        requested_ref = str(ref_scope.requested_ref or "").strip()
        if (
            plural_target_scope
            and effective_kind == "ssh"
            and requested_ref
            and requested_ref in candidate_connections
        ):
            plural_target_scope = False
            resolved = append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope disabled_by_existing_requested_target "
                f"requested_ref={requested_ref}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        _ = (message, looks_like_plural_target)
        if plural_target_scope:
            resolved = append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope blocks_single_target_resolution "
                f"kind={effective_kind or '-'}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        return SshTargetScopeDecision(
            resolved=resolved,
            plural_target_scope=plural_target_scope,
            candidate_connections=candidate_connections,
        )

    @staticmethod
    def _explicit_single_ref_from_scope_or_resolution(
        *,
        ref_scope: ConnectionRefScope,
        working_draft: Any,
        resolved: dict[str, Any],
    ) -> str:
        explicit_ref = str(ref_scope.explicit_ref or "").strip()
        if explicit_ref:
            return explicit_ref
        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        decision = dict(resolved.get("decision", {}) or {})
        for value in (
            getattr(working_draft, "explicit_connection_ref", ""),
            payload.get("connection_ref", ""),
            decision.get("ref", ""),
        ):
            clean = str(value or "").strip()
            if clean:
                return clean
        for line in list(resolved.get("detail_lines", []) or []):
            match = re.search(r"\bexplicit_ref=([^\s`]+)", str(line or ""))
            if not match:
                continue
            clean = str(match.group(1) or "").strip()
            if clean and clean != "-":
                return clean
        return ""

    async def prepare_plural_multi_target_command(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        user_id: str,
        candidate_connections: dict[str, Any] | None,
        capability_draft: Any | None,
        language: str | None,
        resolve_command: Callable[..., Awaitable[tuple[dict[str, Any], Any | None, str]]],
    ) -> SshPluralCommandPreparation:
        refs = sorted(
            str(ref or "").strip()
            for ref in dict(candidate_connections or {}).keys()
            if str(ref or "").strip()
        )
        if len(refs) < 2:
            return SshPluralCommandPreparation(resolved, capability_draft)

        payload = dict((resolved.get("payload_debug") or {}).get("payload", {}) or {})
        existing_command = str(
            getattr(capability_draft, "content", "") or payload.get("content", "") or ""
        ).strip()
        if existing_command:
            return SshPluralCommandPreparation(resolved, capability_draft)

        representative_ref = refs[0]
        working_draft = capability_draft or CapabilityDraft(
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=representative_ref,
            content="",
            plan_class="command_single",
            behavior_profile="ssh_run_command",
        )
        working_draft = with_capability_draft_updates(
            working_draft,
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref=representative_ref,
            requested_connection_ref="",
            content="",
            plan_class=str(getattr(working_draft, "plan_class", "") or "command_single"),
            behavior_profile=str(getattr(working_draft, "behavior_profile", "") or "ssh_run_command"),
        )

        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        if not action_decision:
            action_decision = {
                "found": True,
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "capability": "ssh_command",
            }
            action_debug["decision"] = action_decision

        updated_action_debug, updated_draft, debug_line = await resolve_command(
            message=str(message or "").strip(),
            user_id=user_id,
            routing_decision={
                "found": True,
                "kind": "ssh",
                "ref": representative_ref,
                "source": "plural_target_scope",
            },
            action_debug=action_debug,
            capability_draft=working_draft,
            language=language,
        )
        updated_decision = dict((updated_action_debug or {}).get("decision", {}) or {})
        command = str(
            (updated_decision.get("inputs") or {}).get("command", "")
            or getattr(updated_draft, "content", "")
            or ""
        ).strip()
        if not command:
            if debug_line:
                resolved = append_debug_detail_lines(
                    resolved,
                    debug_line,
                    routing_debug_enabled=self._routing_debug_enabled(),
                )
            return SshPluralCommandPreparation(resolved, capability_draft)

        resolved["action_debug"] = updated_action_debug
        if debug_line:
            resolved = append_debug_detail_lines(
                resolved,
                debug_line,
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        resolved = append_debug_detail_lines(
            resolved,
            "Routing Debug: plural_target_scope command_draft "
            f"ref={representative_ref} command={command}",
            routing_debug_enabled=self._routing_debug_enabled(),
        )

        base_draft = capability_draft or CapabilityDraft(capability="ssh_command", connection_kind="ssh")
        base_draft = with_capability_draft_updates(
            base_draft,
            capability="ssh_command",
            connection_kind="ssh",
            explicit_connection_ref="",
            requested_connection_ref="",
            content=command,
            plan_class="command_single",
            behavior_profile="ssh_run_command",
        )
        return SshPluralCommandPreparation(resolved, base_draft)

    def apply_plural_multi_target_resolution(
        self,
        resolved: dict[str, Any],
        *,
        candidate_connections: dict[str, Any] | None,
        capability_draft: Any | None,
        language: str | None,
        adapt_command: Callable[[list[str], str, str, Any | None], tuple[str, str]],
        evaluate_safety: Callable[..., dict[str, Any]],
        build_execution_preview: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        payload_debug = dict(resolved.get("payload_debug", {}) or {})
        payload = dict(payload_debug.get("payload", {}) or {})
        command = str(
            getattr(capability_draft, "content", "") or payload.get("content", "") or ""
        ).strip()
        capability = normalize_capability(
            str(payload.get("capability", "") or getattr(capability_draft, "capability", "") or "")
        )
        connection_kind = normalize_connection_kind(
            str(payload.get("connection_kind", "") or getattr(capability_draft, "connection_kind", "") or "")
        )
        if capability != "ssh_command" or connection_kind != "ssh" or not command:
            return resolved
        if validate_ssh_readonly_policy(command).action != "allow":
            return resolved

        existing_refs = self._payload_multi_target_refs(payload)
        if not existing_refs:
            for item in list(getattr(capability_draft, "connection_refs", []) or []):
                clean_ref = str(item or "").strip()
                if clean_ref and clean_ref not in existing_refs:
                    existing_refs.append(clean_ref)
        draft_notes = [
            str(item or "").strip().lower()
            for item in list(getattr(capability_draft, "notes", []) or [])
            if str(item or "").strip()
        ]
        target_scope_authority = next(
            (
                note.split(":", 1)[1].strip()
                for note in draft_notes
                if note.startswith("target_scope_authority:") and note.split(":", 1)[1].strip()
            ),
            "",
        )
        missing_contract_refs_require_skip = (
            not existing_refs
            and "target_scope:multi_target" in draft_notes
            and target_scope_authority != "full_kind"
            and (
                "capability_draft_source:llm" in draft_notes
                or target_scope_authority in {"", "priority_sample"}
            )
        )
        if missing_contract_refs_require_skip:
            draft_source = next(
                (
                    note.split(":", 1)[1].strip()
                    for note in draft_notes
                    if note.startswith("capability_draft_source:") and note.split(":", 1)[1].strip()
                ),
                "-",
            )
            return append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope skipped_missing_contract_target_refs "
                f"source={draft_source} authority={target_scope_authority or '-'}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        refs = existing_refs or sorted(
            str(ref or "").strip()
            for ref in dict(candidate_connections or {}).keys()
            if str(ref or "").strip()
        )
        refs = sorted(dict.fromkeys(refs))
        if len(refs) < 2:
            return resolved

        adapted_command, adaptation_reason = adapt_command(
            refs,
            command,
            str(resolved.get("query", "") or ""),
            capability_draft,
        )
        if adapted_command and adapted_command != command:
            command = adapted_command
            payload["content"] = command
            if capability_draft is not None:
                capability_draft = with_capability_draft_updates(capability_draft, content=command)
            resolved = append_debug_detail_lines(
                resolved,
                f"Routing Debug: plural_target_scope {adaptation_reason}_command_adapted "
                f"command={command}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )

        payload["connection_ref"] = ""
        payload["connection_refs"] = refs
        payload["content"] = command
        missing_fields = prune_satisfied_payload_missing_fields(payload)
        notes = [
            str(item or "").strip()
            for item in list(payload.get("notes", []) or [])
            if str(item or "").strip()
        ]
        for item in list(getattr(capability_draft, "notes", []) or []):
            clean_note = str(item or "").strip()
            if clean_note and clean_note not in notes:
                notes.append(clean_note)
        target_intent = next(
            (
                note.split(":", 1)[1].strip().lower()
                for note in notes
                if note.lower().startswith("target_intent:") and note.split(":", 1)[1].strip()
            ),
            "",
        )
        payload.update(
            {
                "found": True,
                "capability": "ssh_command",
                "connection_kind": "ssh",
                "connection_ref": "",
                "connection_refs": refs,
                "content": command,
                "missing_fields": missing_fields,
                "preview": f"SSH command on {len(refs)} targets: {command}",
                "resolution_source": "plural_target_scope",
            }
        )
        if notes:
            payload["notes"] = notes
        if target_intent:
            payload["target_intent"] = target_intent
            if not str(payload.get("task_intent", "") or "").strip():
                payload["task_intent"] = target_intent
        payload_debug.update(
            {
                "used": True,
                "status": "ok" if not missing_fields else "warn",
                "visual_status": "ok" if not missing_fields else "warn",
                "message": "Payload dry-run built a multi-target SSH executor payload.",
                "payload": payload,
            }
        )
        resolved["payload_debug"] = payload_debug

        action_debug = dict(resolved.get("action_debug", {}) or {})
        action_decision = dict(action_debug.get("decision", {}) or {})
        action_decision.update(
            {
                "found": True,
                "candidate_kind": "template",
                "candidate_id": "ssh_run_command",
                "capability": "ssh_command",
                "inputs": {"command": command},
                "input_items": [{"key": "command", "key_label": "Command", "value": command}],
                "preview": f"SSH command on {len(refs)} targets: {command}",
                "ask_user": False,
                "missing_input": "",
                "missing_input_label": "",
                "execution_state": "ready",
            }
        )
        action_debug["decision"] = action_decision
        resolved["action_debug"] = action_debug

        routing_decision = dict(resolved.get("decision", {}) or {})
        safety_debug = evaluate_safety(
            payload_debug=payload_debug,
            routing_decision=routing_decision,
            language=str(language or ""),
        )
        safety_decision = dict(safety_debug.get("decision", {}) or {})
        safety_decision["multi_target_count"] = len(refs)
        safety_debug["decision"] = safety_decision
        resolved["safety_debug"] = safety_debug

        execution_debug = build_execution_preview(
            routing_decision=routing_decision,
            action_decision=dict((resolved.get("action_debug") or {}).get("decision", {}) or {}),
            payload_debug=payload_debug,
            safety_debug=safety_debug,
            language=str(language or ""),
        )
        execution_decision = dict(execution_debug.get("decision", {}) or {})
        if execution_decision:
            execution_decision["summary"] = f"ARIA would run on {len(refs)} SSH targets: SSH command: {command}"
            execution_decision["multi_target_count"] = len(refs)
        execution_debug["decision"] = execution_decision
        resolved["execution_debug"] = execution_debug
        return append_debug_detail_lines(
            resolved,
            "Routing Debug: plural_target_scope selected_multi_target "
            f"kind=ssh refs={', '.join(refs)} command={command}",
            routing_debug_enabled=self._routing_debug_enabled(),
        )

    def narrow_plural_target_connections_by_context(
        self,
        resolved: dict[str, Any],
        *,
        message: str,
        candidate_connections: dict[str, Any],
    ) -> SshTargetScopeNarrowing:
        _ = message
        resolved = append_debug_detail_lines(
            resolved,
            "Routing Debug: legacy_semantic_heuristic component=ssh_target_scope_policy "
            "decision=narrow_plural_target_connections_by_context effect=candidate_only "
            "authority=candidate_only manifest_class=red_p0 source=disabled",
            routing_debug_enabled=self._routing_debug_enabled(),
        )
        return SshTargetScopeNarrowing(resolved, candidate_connections, [])

    @staticmethod
    def capability_draft_has_multi_target_scope(capability_draft: Any | None) -> bool:
        notes = [str(note or "").strip().lower() for note in list(getattr(capability_draft, "notes", []) or [])]
        return "target_scope:multi_target" in notes

    @staticmethod
    def _payload_multi_target_refs(payload: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        for item in list(payload.get("connection_refs", []) or []):
            clean = str(item or "").strip()
            if clean and clean not in refs:
                refs.append(clean)
        return refs
