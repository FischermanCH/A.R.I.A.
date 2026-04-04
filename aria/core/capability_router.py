from __future__ import annotations

import re
from typing import Iterable

from aria.core.action_plan import CapabilityDraft


class CapabilityRouter:
    def __init__(self) -> None:
        self._write_terms = (
            "schreib",
            "schreibe",
            "erstell",
            "erstelle",
            "erzeuge",
            "lege an",
            "leg an",
            "aktualisier",
            "update file",
            "überschreib",
            "ueberschreib",
            "speicher als datei",
            "speichere als datei",
            "speicher in",
            "speichere in",
            "write",
            "create file",
            "save file",
            "write file",
            "save to",
        )
        self._read_terms = (
            "lies",
            "lese",
            "lies mir",
            "les mir",
            "zeig",
            "zeige",
            "zeig mir",
            "zeige mir",
            "zeige den inhalt",
            "gib mir den inhalt",
            "inhalt von",
            "öffne",
            "oeffne",
            "lade",
            "hol",
            "read",
            "show file",
            "open file",
            "read file",
            "cat ",
        )
        self._feed_read_terms = (
            "rss",
            "feed",
            "atom feed",
            "newsfeed",
            "news feed",
            "news",
            "nachrichten",
            "feed lesen",
            "feed anzeigen",
            "feed zeigen",
            "neueste einträge",
            "neueste meldungen",
            "was für news",
            "was fuer news",
            "was gibt es neues",
            "was gibts neues",
            "was gibs neues",
            "was ist neu",
            "gibts neues",
            "gibs neues",
            "headlines",
            "latest entries",
            "latest posts",
        )
        self._webhook_send_terms = (
            "webhook",
            "per webhook",
            "via webhook",
            "an webhook",
            "zum webhook",
            "an den webhook",
            "post an",
            "poste an",
            "schick an",
            "sende an",
            "sende per webhook",
            "schicke per webhook",
            "notify via webhook",
            "callback",
            "endpoint",
        )
        self._discord_send_terms = (
            "discord",
            "an discord",
            "nach discord",
            "zu discord",
            "per discord",
            "via discord",
            "in discord",
            "discord senden",
            "discord schicken",
            "discord nachricht",
        )
        self._api_terms = (
            "api",
            "http api",
            "rest api",
            "endpoint",
            "rest endpoint",
        )
        self._api_action_terms = (
            "ruf",
            "rufe",
            "call",
            "frage",
            "fetch",
            "hole",
            "hol",
            "zeige",
            "zeig",
            "get",
            "post",
            "put",
            "patch",
            "head",
            "sende",
            "send",
        )
        self._email_send_terms = (
            "mail",
            "email",
            "e-mail",
            "per mail",
            "per email",
            "via mail",
            "via email",
            "smtp",
        )
        self._email_send_action_terms = (
            "send",
            "sende",
            "schick",
            "schicke",
            "mail",
            "maile",
            "verschick",
            "verschicke",
        )
        self._mail_read_terms = (
            "mails lesen",
            "mail lesen",
            "emails lesen",
            "email lesen",
            "zeige mails",
            "zeige emails",
            "neueste mails",
            "neueste emails",
            "ungelesene mails",
            "ungelesene emails",
            "inbox",
            "mailbox",
            "postfach",
        )
        self._mail_search_terms = (
            "suche mails",
            "suche emails",
            "finde mails",
            "finde emails",
            "durchsuche mailbox",
            "durchsuche postfach",
            "search mails",
            "search emails",
        )
        self._mqtt_terms = (
            "mqtt",
            "broker",
            "topic",
            "publish",
            "iot",
        )
        self._mqtt_action_terms = (
            "send",
            "sende",
            "schick",
            "schicke",
            "publish",
            "poste",
            "post",
        )
        self._webhook_action_terms = (
            "send",
            "sende",
            "schick",
            "schicke",
            "post",
            "poste",
            "melde",
            "alarmiere",
            "notify",
            "benachrichtige",
        )
        self._discord_action_terms = self._webhook_action_terms
        self._list_terms = (
            "liste",
            "liste mir",
            "list",
            "list files",
            "zeig dateien",
            "zeige dateien",
            "zeige mir die dateien",
            "was für dateien",
            "was fuer dateien",
            "welche dateien",
            "welche dateien liegen",
            "welche dateien gibt es",
            "was liegt in",
            "was ist in",
            "was liegt auf",
            "was ist auf",
            "was liegt in meinem share",
            "was ist in meinem share",
            "welche dateien liegen in",
            "inhalt von ordner",
            "inhalt vom ordner",
            "inhalt von verzeichnis",
            "ordner anzeigen",
            "ordnerinhalt",
            "verzeichnis",
            "daten aus",
            "daten im",
            "daten von",
            "zeige daten",
            "zeige mir daten",
            "zeige mir die daten",
            "inhalte von",
            "inhalt aus",
            "ordner von",
            "verzeichnis von",
            "directory",
            "files in",
            "ls ",
        )
        self._remote_terms = (
            "server",
            "remote",
            "host",
            "sftp",
            "share",
            "freigabe",
            "nas",
            "netzlaufwerk",
            "smb",
            "ordner",
            "verzeichnis",
            "datei",
            "file",
            "/",
        )
        self._sftp_hints = ("sftp", "server", "host", "ssh", "linux-server")
        self._smb_hints = (
            "smb",
            "share",
            "freigabe",
            "nas",
            "netzlaufwerk",
            "windows-share",
            "synology",
            "volume",
            "docker share",
            "docker verzeichnis",
        )
        self._rss_hints = ("rss", "feed", "atom", "newsfeed", "news feed")
        self._webhook_hints = ("webhook", "hook", "callback", "endpoint")
        self._discord_hints = ("discord", "channel", "server", "webhook")
        self._api_hints = ("api", "rest", "endpoint", "http api")
        self._email_hints = ("mail", "email", "e-mail", "smtp")
        self._imap_hints = ("imap", "mailbox", "postfach", "inbox", "mail", "email", "e-mail")
        self._mqtt_hints = ("mqtt", "broker", "topic", "iot")

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

    @staticmethod
    def _has_feed_subject_terms(text: str) -> bool:
        tokens = CapabilityRouter._split_ref_tokens(text)
        ignore = {
            "aktuell",
            "aktuelle",
            "auf",
            "aus",
            "bei",
            "das",
            "dem",
            "den",
            "der",
            "die",
            "eintraege",
            "entries",
            "es",
            "feed",
            "gibt",
            "gibts",
            "headlines",
            "im",
            "in",
            "ist",
            "latest",
            "meldungen",
            "mir",
            "neu",
            "neue",
            "neuen",
            "neues",
            "news",
            "online",
            "posts",
            "rss",
            "show",
            "tell",
            "the",
            "updates",
            "von",
            "was",
            "zeige",
            "zeig",
            "zu",
        }
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
        return any(
            msg.startswith(token)
            or token.startswith(msg)
            for msg in message_tokens
            if len(msg) >= 4
        )

    @staticmethod
    def _connection_ref_match_score(message: str, ref: str) -> int:
        lower = message.lower()
        message_tokens = set(CapabilityRouter._split_ref_tokens(lower))
        generic_tokens = {
            "api",
            "discord",
            "email",
            "feed",
            "hook",
            "http",
            "imap",
            "inbox",
            "mail",
            "mqtt",
            "news",
            "rss",
            "server",
            "share",
            "smtp",
            "sftp",
            "smb",
            "topic",
            "webhook",
        }
        clean_ref = str(ref).strip()
        if not clean_ref:
            return 0
        ref_lower = clean_ref.lower()
        ref_spaced = re.sub(r"[-_]+", " ", ref_lower)
        if ref_lower in lower:
            return 1000 + len(clean_ref)
        if ref_spaced in lower:
            return 900 + len(clean_ref)
        ref_tokens = CapabilityRouter._split_ref_tokens(clean_ref)
        significant_tokens = [token for token in ref_tokens if token not in generic_tokens]
        if len(significant_tokens) < 2:
            return 0
        if all(token in message_tokens for token in significant_tokens):
            return 100 + len(significant_tokens) * 10 + len(clean_ref)
        return 0

    @staticmethod
    def _connection_alias_match_score(message: str, alias: str) -> int:
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
        alias_tokens = CapabilityRouter._split_ref_tokens(alias_lower)
        message_tokens = set(CapabilityRouter._split_ref_tokens(lower))
        if len(alias_tokens) >= 2 and all(
            CapabilityRouter._token_matches_variant(token, message_tokens) for token in alias_tokens
        ):
            return 90 + len(alias_tokens) * 10 + len(clean_alias)
        if len(alias_tokens) == 1 and len(alias_tokens[0]) >= 4 and alias_tokens[0] in message_tokens:
            return 35 + len(alias_tokens[0])
        return 0

    @staticmethod
    def _extract_explicit_connection_ref(message: str, refs: Iterable[str]) -> str:
        candidates = sorted((str(ref).strip() for ref in refs if str(ref).strip()), key=len, reverse=True)
        best_ref = ""
        best_score = 0
        for ref in candidates:
            score = CapabilityRouter._connection_ref_match_score(message, ref)
            if score > best_score:
                best_ref = ref
                best_score = score
        return best_ref

    def _extract_explicit_connection_by_kind(
        self,
        message: str,
        refs_by_kind: dict[str, Iterable[str]],
        aliases_by_kind: dict[str, dict[str, Iterable[str]]] | None = None,
    ) -> tuple[str, str]:
        candidates: list[tuple[int, str, str]] = []
        for kind, refs in refs_by_kind.items():
            for ref in refs:
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                score = self._connection_ref_match_score(message, clean_ref)
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

    def classify(
        self,
        message: str,
        *,
        available_connection_refs: Iterable[str] = (),
        available_connection_refs_by_kind: dict[str, Iterable[str]] | None = None,
        available_connection_aliases_by_kind: dict[str, dict[str, Iterable[str]]] | None = None,
    ) -> CapabilityDraft | None:
        raw = self._normalize(message)
        lower = raw.lower()
        refs_by_kind = available_connection_refs_by_kind or {"sftp": available_connection_refs}
        explicit_kind, explicit_ref = self._extract_explicit_connection_by_kind(
            raw,
            refs_by_kind,
            available_connection_aliases_by_kind,
        )
        available_kinds = {
            str(kind).strip().lower()
            for kind, refs in refs_by_kind.items()
            if any(str(ref).strip() for ref in refs)
        }
        if not raw:
            return None

        has_feed_hint = self._contains_any(lower, self._rss_hints)
        has_feed_request = self._contains_any(lower, self._feed_read_terms)
        has_feed_subject = self._has_feed_subject_terms(lower)
        has_api_hint = self._contains_any(lower, self._api_hints)
        has_discord_hint = self._contains_any(lower, self._discord_hints)
        has_email_hint = self._contains_any(lower, self._email_hints)
        has_imap_hint = self._contains_any(lower, self._imap_hints)
        has_mqtt_hint = self._contains_any(lower, self._mqtt_hints)
        has_remote_hint = (
            any(token in lower for token in self._remote_terms)
            or bool(explicit_ref)
            or bool(self._extract_path(raw))
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
        if (has_imap_hint or explicit_kind == "imap") and self._contains_any(lower, self._mail_search_terms):
            capability = "mail_search"
            confidence = 0.77
        elif (has_imap_hint or explicit_kind == "imap") and self._contains_any(lower, self._mail_read_terms):
            capability = "mail_read"
            confidence = 0.77
        elif (has_email_hint or explicit_kind == "email") and self._contains_any(lower, self._email_send_action_terms):
            capability = "email_send"
            confidence = 0.77
        elif (has_mqtt_hint or explicit_kind == "mqtt") and self._contains_any(lower, self._mqtt_action_terms):
            capability = "mqtt_publish"
            confidence = 0.76
        elif has_feed_request and (has_feed_hint or explicit_kind == "rss" or ("rss" in available_kinds and has_feed_subject)):
            capability = "feed_read"
            confidence = 0.8
        elif self._contains_any(lower, self._list_terms):
            capability = "file_list"
            confidence = 0.8
        elif self._contains_any(lower, self._write_terms):
            capability = "file_write"
            confidence = 0.84
        elif self._contains_any(lower, self._read_terms):
            capability = "file_read"
            confidence = 0.8

        if not capability:
            has_webhook_hint = self._contains_any(lower, self._webhook_send_terms) or explicit_kind == "webhook"
            has_webhook_action = self._contains_any(lower, self._webhook_action_terms)
            if has_webhook_hint and has_webhook_action:
                capability = "webhook_send"
                confidence = 0.78
            elif (self._contains_any(lower, self._discord_send_terms) or explicit_kind == "discord") and self._contains_any(lower, self._discord_action_terms):
                capability = "discord_send"
                confidence = 0.79
            elif (has_api_hint or explicit_kind == "http_api") and self._contains_any(lower, self._api_action_terms):
                capability = "api_request"
                confidence = 0.76
            else:
                return None

        connection_kind = explicit_kind
        if not connection_kind:
            has_sftp_hint = self._contains_any(lower, self._sftp_hints)
            has_smb_hint = self._contains_any(lower, self._smb_hints)
            if has_smb_hint and not has_sftp_hint and "smb" in available_kinds:
                connection_kind = "smb"
            elif has_feed_hint and "rss" in available_kinds:
                connection_kind = "rss"
            elif self._contains_any(lower, self._webhook_hints) and "webhook" in available_kinds:
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

        return CapabilityDraft(
            capability=capability,
            connection_kind=connection_kind,
            explicit_connection_ref=explicit_ref,
            path=self._extract_mqtt_topic(raw) if capability == "mqtt_publish" else self._extract_path(raw),
            content=(
                self._extract_webhook_content(raw, explicit_ref)
                if capability in {"webhook_send", "discord_send", "email_send", "mqtt_publish"}
                else self._extract_mail_search_query(raw, explicit_ref)
                if capability == "mail_search"
                else self._extract_content(raw)
            ),
            confidence=confidence,
        )
