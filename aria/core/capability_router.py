from __future__ import annotations

import re
from typing import Iterable

from aria.core.action_plan import CapabilityDraft
from aria.core.routing_lexicon import CapabilityRoutingLexicon
from aria.core.routing_lexicon import get_default_capability_lexicon


class CapabilityRouter:
    def __init__(
        self,
        *,
        default_lexicon: CapabilityRoutingLexicon | None = None,
        language_lexicons: dict[str, CapabilityRoutingLexicon] | None = None,
    ) -> None:
        self._default_lexicon = default_lexicon or get_default_capability_lexicon()
        self._language_lexicons = {"en": get_default_capability_lexicon("en")}
        if language_lexicons:
            self._language_lexicons.update(
                {str(key).strip().lower(): value for key, value in language_lexicons.items() if str(key).strip()}
            )

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _contains_any(text: str, phrases: Iterable[str]) -> bool:
        lower = f" {text.lower()} "
        for phrase in phrases:
            token = str(phrase or "").strip().lower()
            if not token:
                continue
            if f" {token} " in lower or lower.strip().startswith(token + " ") or f" {token}" in lower:
                return True
        return False

    def _lexicon_for_language(self, language: str | None) -> CapabilityRoutingLexicon:
        lang_key = str(language or "").strip().lower()
        if not lang_key:
            return self._default_lexicon
        return self._language_lexicons.get(lang_key, self._default_lexicon)

    def _has_feed_subject_terms(self, text: str, lexicon: CapabilityRoutingLexicon) -> bool:
        tokens = self._split_ref_tokens(text)
        ignore = set(lexicon.feed_subject_ignore_terms)
        return any(token not in ignore for token in tokens)

    @staticmethod
    def _extract_path(message: str) -> str:
        quoted = re.search(r"['\"](/[^'\"]+)['\"]", message)
        if quoted:
            return quoted.group(1).strip()
        raw = re.search(r"(^|\s)(/[^\s,;:]+)", message)
        if raw:
            return raw.group(2).strip()
        path_after = re.search(r"\b(?:pfad|path)\b\s+([./~A-Za-z0-9_\-][^\s,;]*)", message, re.IGNORECASE)
        if path_after:
            return path_after.group(1).strip()
        return ""

    @staticmethod
    def _extract_content(message: str) -> str:
        patterns = (
            r"\b(?:mit\s+(?:dem\s+)?inhalt|inhalt|content)\b\s+['\"](.+?)['\"]\s*$",
            r"\b(?:mit\s+(?:dem\s+)?inhalt|inhalt|content)\b\s+(.+)$",
            r"\b(?:schreib|write)\b.+?\b(?:datei|file)\b.+?:\s*(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_webhook_content(message: str, explicit_ref: str = "") -> str:
        generic = CapabilityRouter._extract_content(message)
        if generic:
            return generic
        quoted = re.search(r"['\"](.+?)['\"]", message)
        if quoted:
            return quoted.group(1).strip()
        colon = re.search(r":\s*(.+)$", message)
        if colon:
            return colon.group(1).strip()
        clean = str(message or "").strip()
        ref = str(explicit_ref or "").strip()
        if ref:
            after_ref = re.search(rf"\b{re.escape(ref)}\b\s+(.+)$", clean, re.IGNORECASE)
            if after_ref:
                candidate = after_ref.group(1).strip(" .,:;!?")
                if candidate:
                    return candidate
        return ""

    @staticmethod
    def _extract_mail_search_query(message: str, explicit_ref: str = "") -> str:
        quoted = re.search(r"['\"](.+?)['\"]", message)
        if quoted:
            return quoted.group(1).strip()
        patterns = (
            r"\b(?:suche|finde|durchsuche|search)\b.+?\bnach\b\s+(.+)$",
            r"\b(?:suche|finde|durchsuche|search)\b\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,:;!?")
                if explicit_ref and value.lower().startswith(explicit_ref.lower() + " "):
                    value = value[len(explicit_ref):].strip(" .,:;!?")
                if value:
                    return value
        return ""

    @staticmethod
    def _extract_mqtt_topic(message: str) -> str:
        patterns = (
            r"\btopic\b\s+([A-Za-z0-9_./-]+)",
            r"\bauf topic\b\s+([A-Za-z0-9_./-]+)",
            r"\ban topic\b\s+([A-Za-z0-9_./-]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _clean_ssh_command(value: str) -> str:
        command = str(value or "").strip(" \t\r\n.,;")
        command = re.sub(r"^(?:den\s+|the\s+)?(?:command|befehl)\s+", "", command, flags=re.IGNORECASE).strip()
        if (command.startswith('"') and command.endswith('"')) or (command.startswith("'") and command.endswith("'")):
            command = command[1:-1].strip()
        return command

    @classmethod
    def _extract_ssh_command(cls, message: str, explicit_ref: str = "") -> str:
        raw = str(message or "").strip()
        if not raw:
            return ""

        action = r"(?:run|execute|exec|start|starte|führe|fuehre)"
        command_prefix = r"(?:(?:den|the)\s+)?(?:command|befehl)?"
        ref_variants: list[str] = []
        clean_ref = str(explicit_ref or "").strip()
        if clean_ref:
            ref_variants.append(re.escape(clean_ref))
            ref_spaced = re.sub(r"[-_]+", " ", clean_ref)
            if ref_spaced != clean_ref:
                ref_variants.append(re.escape(ref_spaced))
        if ref_variants:
            target = "(?:" + "|".join(ref_variants) + ")"
            patterns = (
                rf"^\s*{action}\s+{command_prefix}\s*(?P<cmd>.+?)\s+(?:on|auf|via|bei|von)\s+(?:ssh\s+)?{target}\s*(?:aus)?\s*[.!?]?\s*$",
                rf"^\s*(?:ssh\s+)?{target}\s+{action}\s+{command_prefix}\s*(?P<cmd>.+?)\s*[.!?]?\s*$",
                rf"^\s*ssh\s+{target}\s+(?P<cmd>.+?)\s*[.!?]?\s*$",
            )
            for pattern in patterns:
                match = re.search(pattern, raw, re.IGNORECASE)
                if match:
                    return cls._clean_ssh_command(match.group("cmd"))

        patterns_without_ref = (
            rf"^\s*{action}\s+{command_prefix}\s*(?P<cmd>.+?)\s+(?:via|per|über|ueber)\s+ssh\s*[.!?]?\s*$",
            rf"^\s*ssh\s+{action}\s+{command_prefix}\s*(?P<cmd>.+?)\s*[.!?]?\s*$",
        )
        for pattern in patterns_without_ref:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                return cls._clean_ssh_command(match.group("cmd"))
        return ""

    @classmethod
    def _extract_natural_ssh_command(cls, message: str) -> str:
        raw = str(message or "").strip()
        if not raw or cls._extract_path(raw):
            return ""
        lower = raw.lower()
        if re.search(r"\b(?:uptime|laufzeit|betriebszeit)\b", lower, re.IGNORECASE):
            return "uptime"
        if re.search(r"\b(?:health\s*check|healthcheck|gesundheitscheck|systemstatus)\b", lower, re.IGNORECASE):
            return "uptime"
        if re.search(r"\bwie\s+lange\s+l(?:ä|ae)?uft\b", lower, re.IGNORECASE):
            return "uptime"
        if re.search(r"\bseit\s+wann\s+l(?:ä|ae)?uft\b", lower, re.IGNORECASE):
            return "uptime"
        if re.search(r"\b(?:wie\s+lange|seit\s+wann)\s+ist\b.*\bonline\b", lower, re.IGNORECASE):
            return "uptime"
        if re.search(r"\bhow\s+long\b.*\b(?:running|up)\b", lower, re.IGNORECASE):
            return "uptime"
        if re.search(r"\bhow\s+long\b.*\b(?:been\s+online|online)\b", lower, re.IGNORECASE):
            return "uptime"
        return ""

    @staticmethod
    def _split_ref_tokens(value: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", str(value or "").lower()) if token]

    @staticmethod
    def _token_matches_variant(candidate: str, message_tokens: set[str]) -> bool:
        token = str(candidate or "").strip().lower()
        if not token:
            return False
        if token in message_tokens:
            return True
        if len(token) < 4:
            return False
        return any(msg.startswith(token) or token.startswith(msg) for msg in message_tokens if len(msg) >= 4)

    def _connection_ref_match_score(self, message: str, ref: str, lexicon: CapabilityRoutingLexicon) -> int:
        lower = message.lower()
        message_tokens = set(self._split_ref_tokens(lower))
        generic_tokens = set(lexicon.generic_connection_ref_tokens)
        clean_ref = str(ref).strip()
        if not clean_ref:
            return 0
        ref_lower = clean_ref.lower()
        ref_spaced = re.sub(r"[-_]+", " ", ref_lower)
        if ref_lower in lower:
            return 1000 + len(clean_ref)
        if ref_spaced in lower:
            return 900 + len(clean_ref)
        ref_tokens = self._split_ref_tokens(clean_ref)
        significant_tokens = [token for token in ref_tokens if token not in generic_tokens]
        if len(significant_tokens) < 2:
            return 0
        if all(token in message_tokens for token in significant_tokens):
            return 100 + len(significant_tokens) * 10 + len(clean_ref)
        return 0

    def _connection_alias_match_score(self, message: str, alias: str) -> int:
        clean_alias = str(alias).strip()
        if not clean_alias:
            return 0
        lower = message.lower()
        alias_lower = clean_alias.lower()
        alias_spaced = re.sub(r"[-_]+", " ", alias_lower)
        if alias_lower in lower:
            return 700 + len(clean_alias)
        if alias_spaced != alias_lower and alias_spaced in lower:
            return 650 + len(clean_alias)
        alias_tokens = self._split_ref_tokens(alias_lower)
        message_tokens = set(self._split_ref_tokens(lower))
        if len(alias_tokens) >= 2 and all(self._token_matches_variant(token, message_tokens) for token in alias_tokens):
            return 90 + len(alias_tokens) * 10 + len(clean_alias)
        if len(alias_tokens) == 1 and len(alias_tokens[0]) >= 4 and alias_tokens[0] in message_tokens:
            return 35 + len(alias_tokens[0])
        return 0

    def _extract_explicit_connection_ref(
        self,
        message: str,
        refs: Iterable[str],
        lexicon: CapabilityRoutingLexicon,
    ) -> str:
        candidates = sorted((str(ref).strip() for ref in refs if str(ref).strip()), key=len, reverse=True)
        best_ref = ""
        best_score = 0
        for ref in candidates:
            score = self._connection_ref_match_score(message, ref, lexicon)
            if score > best_score:
                best_ref = ref
                best_score = score
        return best_ref

    def _extract_explicit_connection_by_kind(
        self,
        message: str,
        refs_by_kind: dict[str, Iterable[str]],
        lexicon: CapabilityRoutingLexicon,
        aliases_by_kind: dict[str, dict[str, Iterable[str]]] | None = None,
    ) -> tuple[str, str]:
        candidates: list[tuple[int, str, str]] = []
        for kind, refs in refs_by_kind.items():
            for ref in refs:
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                score = self._connection_ref_match_score(message, clean_ref, lexicon)
                if score > 0:
                    candidates.append((score, str(kind).strip().lower(), clean_ref))
                alias_rows = ((aliases_by_kind or {}).get(kind, {}) or {}).get(clean_ref, [])
                for alias in alias_rows:
                    alias_score = self._connection_alias_match_score(message, str(alias))
                    if alias_score > 0:
                        candidates.append((alias_score, str(kind).strip().lower(), clean_ref))
        if not candidates:
            return "", ""
        candidates.sort(key=lambda item: (item[0], len(item[2])), reverse=True)
        _, kind, ref = candidates[0]
        return kind, ref

    @staticmethod
    def _extract_requested_connection_ref_hint(message: str, connection_kind: str) -> str:
        raw = str(message or "").strip()
        kind = str(connection_kind or "").strip().lower()
        if not raw or not kind:
            return ""

        patterns_by_kind: dict[str, tuple[str, ...]] = {
            "discord": (
                r"\bdiscord\s+([a-z0-9._-]+)\b",
                r"\bto discord\s+([a-z0-9._-]+)\b",
                r"\bnach discord\s+([a-z0-9._-]+)\b",
                r"\bvia discord\s+([a-z0-9._-]+)\b",
            ),
            "webhook": (
                r"\bwebhook\s+([a-z0-9._-]+)\b",
                r"\bvia webhook\s+([a-z0-9._-]+)\b",
                r"\bper webhook\s+([a-z0-9._-]+)\b",
            ),
            "http_api": (
                r"\bapi\s+([a-z0-9._-]+)\b",
                r"\bendpoint\s+([a-z0-9._-]+)\b",
            ),
            "email": (
                r"\bmail\s+([a-z0-9._-]+)\b",
                r"\bemail\s+([a-z0-9._-]+)\b",
            ),
            "imap": (
                r"\bpostfach\s+([a-z0-9._-]+)\b",
                r"\bmailbox\s+([a-z0-9._-]+)\b",
                r"\binbox\s+([a-z0-9._-]+)\b",
            ),
            "mqtt": (
                r"\bmqtt\s+([a-z0-9._-]+)\b",
                r"\bbroker\s+([a-z0-9._-]+)\b",
            ),
            "ssh": (
                r"\b(?:on|auf|via|bei|von)\s+([a-z0-9._-]+)\b",
                r"\bssh\s+([a-z0-9._-]+)\b",
            ),
            "rss": (
                r"\bfeed\s+([a-z0-9._-]+)\b",
                r"\brss\s+([a-z0-9._-]+)\b",
            ),
        }
        ignore_tokens = {
            "discord",
            "message",
            "nachricht",
            "webhook",
            "api",
            "endpoint",
            "mail",
            "email",
            "postfach",
            "mailbox",
            "inbox",
            "mqtt",
            "broker",
            "ssh",
            "shell",
            "feed",
            "rss",
            "topic",
        }
        for pattern in patterns_by_kind.get(kind, ()):
            match = re.search(pattern, raw, re.IGNORECASE)
            if not match:
                continue
            candidate = str(match.group(1) or "").strip()
            if not candidate:
                continue
            if candidate.lower() in ignore_tokens:
                continue
            return candidate
        return ""

    def classify(
        self,
        message: str,
        *,
        language: str | None = None,
        available_connection_refs: Iterable[str] = (),
        available_connection_refs_by_kind: dict[str, Iterable[str]] | None = None,
        available_connection_aliases_by_kind: dict[str, dict[str, Iterable[str]]] | None = None,
    ) -> CapabilityDraft | None:
        raw = self._normalize(message)
        if not raw:
            return None

        lower = raw.lower()
        lexicon = self._lexicon_for_language(language)
        refs_by_kind = available_connection_refs_by_kind or {"sftp": available_connection_refs}
        explicit_kind, explicit_ref = self._extract_explicit_connection_by_kind(
            raw,
            refs_by_kind,
            lexicon,
            available_connection_aliases_by_kind,
        )
        available_kinds = {
            str(kind).strip().lower()
            for kind, refs in refs_by_kind.items()
            if any(str(ref).strip() for ref in refs)
        }

        has_feed_hint = self._contains_any(lower, lexicon.rss_hints)
        has_feed_request = self._contains_any(lower, lexicon.feed_read_terms)
        has_feed_subject = self._has_feed_subject_terms(lower, lexicon)
        has_explicit_web_search_hint = self._contains_any(lower, lexicon.explicit_web_search_terms)
        has_api_hint = self._contains_any(lower, lexicon.api_hints)
        has_discord_hint = self._contains_any(lower, lexicon.discord_hints)
        has_email_hint = self._contains_any(lower, lexicon.email_hints)
        has_imap_hint = self._contains_any(lower, lexicon.imap_hints)
        has_mqtt_hint = self._contains_any(lower, lexicon.mqtt_hints)
        has_ssh_hint = self._contains_any(lower, lexicon.ssh_hints)
        natural_ssh_command = self._extract_natural_ssh_command(raw)
        ssh_command = self._extract_ssh_command(raw, explicit_ref) or natural_ssh_command
        has_remote_hint = (
            any(token in lower for token in lexicon.remote_terms)
            or bool(explicit_ref)
            or bool(self._extract_path(raw))
            or bool(ssh_command)
            or has_feed_hint
            or (has_feed_request and "rss" in available_kinds and has_feed_subject)
            or has_api_hint
            or has_discord_hint
            or has_email_hint
            or has_imap_hint
            or has_mqtt_hint
        )
        if not has_remote_hint:
            return None

        capability = ""
        confidence = 0.0
        if (
            ssh_command
            and (explicit_kind == "ssh" or has_ssh_hint or ("ssh" in available_kinds and not explicit_kind))
            and (self._contains_any(lower, lexicon.ssh_command_terms) or bool(natural_ssh_command))
        ):
            capability = "ssh_command"
            confidence = 0.82
        elif (has_imap_hint or explicit_kind == "imap") and self._contains_any(lower, lexicon.mail_search_terms):
            capability = "mail_search"
            confidence = 0.77
        elif (has_imap_hint or explicit_kind == "imap") and self._contains_any(lower, lexicon.mail_read_terms):
            capability = "mail_read"
            confidence = 0.77
        elif (has_email_hint or explicit_kind == "email") and self._contains_any(lower, lexicon.email_send_action_terms):
            capability = "email_send"
            confidence = 0.77
        elif (has_mqtt_hint or explicit_kind == "mqtt") and self._contains_any(lower, lexicon.mqtt_action_terms):
            capability = "mqtt_publish"
            confidence = 0.76
        elif (
            has_feed_request
            and not has_explicit_web_search_hint
            and (has_feed_hint or explicit_kind == "rss" or ("rss" in available_kinds and has_feed_subject))
        ):
            capability = "feed_read"
            confidence = 0.8
        elif self._contains_any(lower, lexicon.list_terms):
            capability = "file_list"
            confidence = 0.8
        elif self._contains_any(lower, lexicon.write_terms):
            capability = "file_write"
            confidence = 0.84
        elif self._contains_any(lower, lexicon.read_terms):
            capability = "file_read"
            confidence = 0.8

        if not capability:
            has_webhook_hint = self._contains_any(lower, lexicon.webhook_send_terms) or explicit_kind == "webhook"
            has_webhook_action = self._contains_any(lower, lexicon.webhook_action_terms)
            if has_webhook_hint and has_webhook_action:
                capability = "webhook_send"
                confidence = 0.78
            elif (self._contains_any(lower, lexicon.discord_send_terms) or explicit_kind == "discord") and self._contains_any(
                lower, lexicon.discord_action_terms
            ):
                capability = "discord_send"
                confidence = 0.79
            elif (has_api_hint or explicit_kind == "http_api") and self._contains_any(lower, lexicon.api_action_terms):
                capability = "api_request"
                confidence = 0.76
            else:
                return None

        connection_kind = explicit_kind
        if capability == "ssh_command" and "ssh" in available_kinds:
            connection_kind = "ssh"
        if not connection_kind:
            has_sftp_hint = self._contains_any(lower, lexicon.sftp_hints)
            has_smb_hint = self._contains_any(lower, lexicon.smb_hints)
            if capability == "ssh_command" and "ssh" in available_kinds:
                connection_kind = "ssh"
            elif has_smb_hint and not has_sftp_hint and "smb" in available_kinds:
                connection_kind = "smb"
            elif has_feed_hint and "rss" in available_kinds:
                connection_kind = "rss"
            elif self._contains_any(lower, lexicon.webhook_hints) and "webhook" in available_kinds:
                connection_kind = "webhook"
            elif has_discord_hint and "discord" in available_kinds:
                connection_kind = "discord"
            elif has_api_hint and "http_api" in available_kinds:
                connection_kind = "http_api"
            elif has_imap_hint and "imap" in available_kinds:
                connection_kind = "imap"
            elif has_email_hint and "email" in available_kinds:
                connection_kind = "email"
            elif has_mqtt_hint and "mqtt" in available_kinds:
                connection_kind = "mqtt"
            elif has_sftp_hint and "sftp" in available_kinds:
                connection_kind = "sftp"
            elif len(available_kinds) == 1:
                connection_kind = sorted(available_kinds)[0]
            elif "sftp" in available_kinds:
                connection_kind = "sftp"
            elif "smb" in available_kinds:
                connection_kind = "smb"
            elif "rss" in available_kinds:
                connection_kind = "rss"
            elif "webhook" in available_kinds:
                connection_kind = "webhook"
            elif "discord" in available_kinds:
                connection_kind = "discord"
            elif "http_api" in available_kinds:
                connection_kind = "http_api"
            elif "email" in available_kinds:
                connection_kind = "email"
            elif "imap" in available_kinds:
                connection_kind = "imap"
            elif "mqtt" in available_kinds:
                connection_kind = "mqtt"
            else:
                connection_kind = "sftp"

        requested_connection_ref = ""
        if connection_kind and not explicit_ref:
            requested_candidate = self._extract_requested_connection_ref_hint(raw, connection_kind)
            if requested_candidate:
                available_refs_for_kind = {
                    str(ref).strip().lower()
                    for ref in refs_by_kind.get(connection_kind, ())
                    if str(ref).strip()
                }
                if requested_candidate.lower() not in available_refs_for_kind:
                    requested_connection_ref = requested_candidate

        return CapabilityDraft(
            capability=capability,
            connection_kind=connection_kind,
            explicit_connection_ref=explicit_ref,
            requested_connection_ref=requested_connection_ref,
            path=self._extract_mqtt_topic(raw) if capability == "mqtt_publish" else self._extract_path(raw),
            content=(
                ssh_command
                if capability == "ssh_command"
                else
                self._extract_webhook_content(raw, explicit_ref)
                if capability in {"webhook_send", "discord_send", "email_send", "mqtt_publish"}
                else self._extract_mail_search_query(raw, explicit_ref)
                if capability == "mail_search"
                else self._extract_content(raw)
            ),
            confidence=confidence,
        )
