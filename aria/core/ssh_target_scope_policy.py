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
from aria.core.connection_semantic_resolver import build_connection_aliases
from aria.core.connection_semantic_resolver import normalize_connection_alias
from aria.core.connection_semantic_resolver import split_connection_tokens
from aria.core.connection_dossiers import with_capability_draft_updates
from aria.core.pipeline_action_flow_helpers import append_debug_detail_lines
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
        draft_multi_target_scope = self.capability_draft_has_multi_target_scope(capability_draft)
        if not callable(looks_like_plural_target) and not draft_multi_target_scope:
            return False
        if not draft_multi_target_scope:
            try:
                if not bool(looks_like_plural_target(str(message or ""), "ssh")):
                    return False
            except Exception:
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
        if (
            plural_target_scope
            and effective_kind == "ssh"
            and ref_scope.has_requested
            and self.has_single_target_disambiguator(message)
        ):
            plural_target_scope = False
            resolved = append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope disabled_by_requested_single_target "
                f"requested_ref={ref_scope.requested_ref}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        if callable(looks_like_plural_target) and not plural_target_scope and not ref_scope.has_any:
            try:
                plural_target_scope = bool(looks_like_plural_target(message, effective_kind))
            except Exception:
                plural_target_scope = False
        if plural_target_scope:
            resolved = append_debug_detail_lines(
                resolved,
                "Routing Debug: plural_target_scope blocks_single_target_resolution "
                f"kind={effective_kind or '-'}",
                routing_debug_enabled=self._routing_debug_enabled(),
            )
        if (
            effective_kind == "ssh"
            and ref_scope.has_requested
            and not ref_scope.has_explicit
            and not plural_target_scope
            and not self.has_single_target_disambiguator(message)
            and len(candidate_connections) >= 2
        ):
            narrowing = self.narrow_plural_target_connections_by_context(
                resolved,
                message=message,
                candidate_connections=candidate_connections,
            )
            if 1 < len(narrowing.candidate_connections) < len(candidate_connections):
                plural_target_scope = True
                candidate_connections = narrowing.candidate_connections
                resolved = append_debug_detail_lines(
                    narrowing.resolved,
                    "Routing Debug: plural_target_scope enabled_by_requested_ref_context "
                    f"requested_ref={ref_scope.requested_ref} refs={', '.join(candidate_connections.keys())}",
                    routing_debug_enabled=self._routing_debug_enabled(),
                )
        return SshTargetScopeDecision(
            resolved=resolved,
            plural_target_scope=plural_target_scope,
            candidate_connections=candidate_connections,
        )

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
        refs = existing_refs or sorted(
            str(ref or "").strip()
            for ref in dict(candidate_connections or {}).keys()
            if str(ref or "").strip()
        )
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

        missing_fields = [
            str(item or "").strip()
            for item in list(payload.get("missing_fields", []) or [])
            if str(item or "").strip() and str(item or "").strip() != "connection_ref"
        ]
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
        candidates = self._resolver.collect_connection_candidates(
            message,
            {"ssh": candidate_connections},
            preferred_kind="ssh",
        )
        strong_candidates: list[SemanticConnectionCandidate] = []
        seen_refs: set[str] = set()
        for candidate in candidates:
            ref = str(candidate.connection_ref or "").strip()
            if candidate.connection_kind != "ssh" or ref not in candidate_connections:
                continue
            if int(candidate.score or 0) < 1000:
                continue
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            strong_candidates.append(candidate)

        if not strong_candidates:
            prompt_seed_terms = self._seed_terms_from_message(message)
            if not prompt_seed_terms:
                return SshTargetScopeNarrowing(resolved, candidate_connections, candidates)
            strong_candidates = self._expand_group_candidates(
                message=message,
                candidate_connections=candidate_connections,
                seed_candidates=[],
                score=1000,
                seed_terms=prompt_seed_terms,
            )
            candidates = [*candidates, *strong_candidates]
            seen_refs = {str(candidate.connection_ref or "").strip() for candidate in strong_candidates}
            if not strong_candidates:
                return SshTargetScopeNarrowing(resolved, candidate_connections, candidates)

        top_score = max(int(candidate.score or 0) for candidate in strong_candidates)
        strong_candidates = [
            candidate
            for candidate in strong_candidates
            if int(candidate.score or 0) == top_score
        ]
        seen_refs = {
            str(candidate.connection_ref or "").strip()
            for candidate in strong_candidates
            if str(candidate.connection_ref or "").strip()
        }
        if strong_candidates and (
            not self.has_single_target_disambiguator(message)
            or self._should_expand_role_group(message, strong_candidates)
        ):
            expanded_candidates = self._expand_group_candidates(
                message=message,
                candidate_connections=candidate_connections,
                seed_candidates=strong_candidates,
                score=top_score,
            )
            for candidate in expanded_candidates:
                ref = str(candidate.connection_ref or "").strip()
                if ref and ref not in seen_refs:
                    seen_refs.add(ref)
                    strong_candidates.append(candidate)

        if not strong_candidates or len(strong_candidates) >= len(candidate_connections):
            return SshTargetScopeNarrowing(resolved, candidate_connections, candidates)

        strong_candidates.sort(key=lambda candidate: str(candidate.connection_ref or ""))
        scoped_connections = {
            candidate.connection_ref: candidate_connections[candidate.connection_ref]
            for candidate in strong_candidates
        }
        aliases = ", ".join(
            str(candidate.alias or candidate.note or candidate.connection_ref or "-").strip()
            for candidate in strong_candidates
        )
        resolved = append_debug_detail_lines(
            resolved,
            "Routing Debug: plural_target_scope narrowed_by_connection_context "
            f"kind=ssh refs={', '.join(scoped_connections.keys())} aliases={aliases or '-'}",
            routing_debug_enabled=self._routing_debug_enabled(),
        )
        return SshTargetScopeNarrowing(resolved, scoped_connections, candidates)

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

    @staticmethod
    def has_single_target_disambiguator(message: str) -> bool:
        tokens = set(split_connection_tokens(message))
        single_target_terms = {
            "erster",
            "erste",
            "erstes",
            "ersten",
            "zweiter",
            "zweite",
            "zweites",
            "zweiten",
            "dritter",
            "dritte",
            "drittes",
            "dritten",
            "first",
            "second",
            "third",
            "only",
            "nur",
            "mein",
            "meinem",
        }
        if tokens & single_target_terms:
            return True
        if "meinen" in tokens and not (tokens & {"servern", "systemen", "hosts", "servers"}):
            return True
        return False

    @staticmethod
    def _should_expand_role_group(
        message: str,
        seed_candidates: list[SemanticConnectionCandidate],
    ) -> bool:
        seed_terms = SshTargetScopePolicy._seed_terms(message, seed_candidates)
        if not (seed_terms & {"dns", "pihole", "pi-hole"}):
            return False
        tokens = set(split_connection_tokens(message))
        mutating_terms = {
            "restart",
            "reboot",
            "start",
            "stop",
            "starte",
            "neustart",
            "update",
            "install",
            "delete",
            "remove",
            "loesche",
            "schreibe",
            "write",
        }
        if tokens & mutating_terms:
            return False
        health_terms = {
            "ok",
            "okay",
            "status",
            "health",
            "healthy",
            "check",
            "pruef",
            "pruefe",
            "fit",
            "gesund",
            "geht",
            "erreichbar",
        }
        return bool(tokens & health_terms)

    @staticmethod
    def _seed_terms(
        message: str,
        seed_candidates: list[SemanticConnectionCandidate],
    ) -> set[str]:
        generic_terms = {
            "server",
            "srv",
            "host",
            "system",
            "node",
            "profile",
            "profil",
            "ssh",
        }
        message_tokens = set(split_connection_tokens(message))
        seed_terms: set[str] = set()
        for candidate in seed_candidates:
            candidate_labels = [
                str(candidate.alias or "").strip(),
                str(candidate.note or "").strip(),
                str(candidate.connection_ref or "").strip(),
            ]
            for label in candidate_labels:
                for token in split_connection_tokens(label):
                    if token in generic_terms or len(token) < 3:
                        continue
                    if token in message_tokens or any(token.startswith(message_token) for message_token in message_tokens):
                        seed_terms.add(token)
                    elif token.startswith("dev"):
                        seed_terms.add("dev")
        expanded_terms = set(seed_terms)
        if seed_terms & {
            "dev",
            "developer",
            "developers",
            "development",
            "entwicklungsserver",
            "entwicklungsumgebung",
            "entwicklung",
        }:
            expanded_terms.update(
                {
                    "dev",
                    "devserver",
                    "dev-server",
                    "development",
                    "developer",
                    "entwicklung",
                    "entwicklungsserver",
                    "entwicklungsumgebung",
                    "webentwicklung",
                    "coding",
                    "programming",
                    "programmierung",
                    "code-server",
                    "vscode",
                    "browser-ide",
                }
            )
        return expanded_terms

    @staticmethod
    def _seed_terms_from_message(message: str) -> set[str]:
        generic_terms = {
            "all",
            "alle",
            "auf",
            "den",
            "der",
            "die",
            "ein",
            "eine",
            "genug",
            "habe",
            "haben",
            "hat",
            "ich",
            "mein",
            "meine",
            "meinen",
            "noch",
            "server",
            "servers",
            "srv",
            "ssh",
            "system",
            "systeme",
        }
        seed_terms = {
            token
            for token in split_connection_tokens(message)
            if len(token) >= 3 and token not in generic_terms
        }
        if seed_terms & {"dev", "developer", "developers", "development", "entwicklung", "entwicklungsserver"}:
            seed_terms.update(
                {
                    "dev",
                    "devserver",
                    "dev-server",
                    "development",
                    "developer",
                    "entwicklung",
                    "entwicklungsserver",
                    "entwicklungsumgebung",
                    "webentwicklung",
                    "coding",
                    "programming",
                    "programmierung",
                    "code-server",
                    "vscode",
                    "browser-ide",
                }
            )
        if seed_terms & {"dns", "pihole", "pi-hole"}:
            seed_terms.update({"dns", "pihole", "pi-hole", "adblock", "ad-blocking"})
        return seed_terms

    @staticmethod
    def _aliases_match_seed_terms(
        aliases: list[str],
        seed_terms: set[str],
    ) -> str:
        if not seed_terms:
            return ""
        alias_blob = " ".join(normalize_connection_alias(alias) for alias in aliases if str(alias or "").strip())
        alias_tokens = set(split_connection_tokens(alias_blob))
        for term in sorted(seed_terms):
            clean_term = normalize_connection_alias(term)
            if not clean_term:
                continue
            if clean_term == "dev":
                if any(SshTargetScopePolicy._alias_token_matches_dev_seed(token) for token in alias_tokens):
                    return clean_term
                continue
            if clean_term in alias_blob:
                return clean_term
            term_tokens = split_connection_tokens(clean_term)
            if term_tokens and all(token in alias_tokens for token in term_tokens):
                return clean_term
        return ""

    @staticmethod
    def _alias_token_matches_dev_seed(token: str) -> bool:
        clean_token = str(token or "").strip().lower()
        if not clean_token:
            return False
        return (
            clean_token == "dev"
            or bool(re.fullmatch(r"dev[0-9]+", clean_token))
            or clean_token in {
                "devserver",
                "development",
                "developer",
                "entwicklungsserver",
                "entwicklungsumgebung",
                "entwicklung",
                "webentwicklung",
            }
        )

    def _expand_group_candidates(
        self,
        *,
        message: str,
        candidate_connections: dict[str, Any],
        seed_candidates: list[SemanticConnectionCandidate],
        score: int,
        seed_terms: set[str] | None = None,
    ) -> list[SemanticConnectionCandidate]:
        seed_refs = {str(candidate.connection_ref or "").strip() for candidate in seed_candidates}
        effective_seed_terms = seed_terms or self._seed_terms(message, seed_candidates)
        if not effective_seed_terms:
            return []
        expanded: list[SemanticConnectionCandidate] = []
        for ref, row in candidate_connections.items():
            clean_ref = str(ref or "").strip()
            if not clean_ref or clean_ref in seed_refs:
                continue
            aliases = build_connection_aliases("ssh", clean_ref, row)
            matched = self._aliases_match_seed_terms(aliases, effective_seed_terms)
            if not matched:
                continue
            expanded.append(
                SemanticConnectionCandidate(
                    connection_kind="ssh",
                    connection_ref=clean_ref,
                    source="semantic_group_alias",
                    note=f"group_alias:{matched}",
                    alias=matched,
                    score=int(score or 0),
                )
            )
        return expanded
