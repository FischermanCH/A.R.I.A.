from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Iterable

from aria.core.action_plan import CapabilityDraft
from aria.core.capability_catalog import capability_executor_kinds
from aria.core.connection_catalog import connection_routing_spec
from aria.core.connection_semantic_resolver import _is_generic_connection_label
from aria.core.routing_lexicon import CapabilityRoutingLexicon
from aria.core.routing_lexicon import get_default_capability_lexicon
from aria.core.routing_resolver import infer_preferred_connection_kind

_CAPABILITY_ROUTER_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "capability_router.json"


def _load_capability_router_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_CAPABILITY_ROUTER_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load capability router lexicon: {_CAPABILITY_ROUTER_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


def _lexicon_terms(section: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = section.get(key, [])
    if not isinstance(raw, list):
        return ()
    return tuple(str(value).strip().lower() for value in raw if str(value).strip())


_CAPABILITY_ROUTER_LEXICON = _load_capability_router_lexicon()


class CapabilityRouter:
    _REQUESTED_CONNECTION_ARTICLES = str(_CAPABILITY_ROUTER_LEXICON.get("requested_connection_articles") or "")
    _REQUESTED_CONNECTION_REQUIRED_ARTICLES = str(
        _CAPABILITY_ROUTER_LEXICON.get("requested_connection_required_articles") or ""
    )
    _WEBSITE_COLLECTION_TERMS = _lexicon_terms(_CAPABILITY_ROUTER_LEXICON, "website_collection_terms")

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

    @staticmethod
    def _looks_like_calendar_request(text: str) -> bool:
        lower = str(text or "").lower()
        if not lower:
            return False
        calendar = _CAPABILITY_ROUTER_LEXICON.get("calendar", {})
        calendar = calendar if isinstance(calendar, dict) else {}
        if any(term in lower for term in _lexicon_terms(calendar, "reject_terms")):
            return False
        if any(term in lower for term in _lexicon_terms(calendar, "direct_terms")):
            return True
        if any(term in lower for term in _lexicon_terms(calendar, "event_terms")) and any(
            marker in lower for marker in _lexicon_terms(calendar, "date_markers")
        ):
            return True
        return False

    @staticmethod
    def _extract_calendar_range(text: str) -> str:
        lower = str(text or "").strip().lower()
        if not lower:
            return ""
        calendar = _CAPABILITY_ROUTER_LEXICON.get("calendar", {})
        range_terms = calendar.get("range_terms", {}) if isinstance(calendar, dict) else {}
        if isinstance(range_terms, dict):
            for range_name in ("day_after_tomorrow", "tomorrow", "today", "this_week", "next_week", "next", "upcoming"):
                terms = range_terms.get(range_name, [])
                if isinstance(terms, list) and any(str(term).lower() in lower for term in terms):
                    return range_name
        return "upcoming"

    @staticmethod
    def _extract_calendar_search(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        quoted = re.search(r'["“](.+?)["”]', raw)
        if quoted:
            return str(quoted.group(1) or "").strip()
        calendar = _CAPABILITY_ROUTER_LEXICON.get("calendar", {})
        calendar = calendar if isinstance(calendar, dict) else {}
        patterns = calendar.get("search_patterns", [])
        patterns = patterns if isinstance(patterns, list) else []
        for pattern in patterns:
            match = re.search(str(pattern), raw, re.IGNORECASE)
            if not match:
                continue
            candidate = str(match.group(1) or "").strip(" .,:;!?")
            cleanup_pattern = str(calendar.get("search_cleanup_pattern") or "")
            if cleanup_pattern:
                candidate = re.sub(cleanup_pattern, "", candidate, flags=re.IGNORECASE).strip(" .,:;!?")
            if candidate:
                return candidate
        return ""

    @staticmethod
    def _extract_website_group(text: str) -> str:
        match = re.search(r"(?:\b(?:in|aus|from)\b)\s+(.+)$", str(text or "").strip(), re.IGNORECASE)
        if not match:
            return ""
        return str(match.group(1) or "").strip(" \t\r\n.,;:!?")

    @staticmethod
    def _extract_website_target_phrase(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        website = _CAPABILITY_ROUTER_LEXICON.get("website", {})
        patterns = website.get("target_patterns", []) if isinstance(website, dict) else []
        patterns = patterns if isinstance(patterns, list) else []
        for pattern in patterns:
            match = re.search(str(pattern), raw, re.IGNORECASE)
            if not match:
                continue
            candidate = str(match.group(1) or "").strip(" \t\r\n.,;:!?")
            if candidate:
                return candidate
        return ""

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
        patterns = _CAPABILITY_ROUTER_LEXICON.get("content_patterns", [])
        patterns = patterns if isinstance(patterns, list) else []
        for pattern in patterns:
            match = re.search(str(pattern), message, re.IGNORECASE)
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
        patterns = _CAPABILITY_ROUTER_LEXICON.get("mail_search_patterns", [])
        patterns = patterns if isinstance(patterns, list) else []
        for pattern in patterns:
            match = re.search(str(pattern), message, re.IGNORECASE)
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

    @classmethod
    def _extract_mail_search_query_with_lexicon(
        cls,
        message: str,
        explicit_ref: str,
        lexicon: CapabilityRoutingLexicon,
    ) -> str:
        quoted = re.search(r"['\"](.+?)['\"]", message)
        if quoted:
            return quoted.group(1).strip()
        lower = str(message or "").strip().lower()
        for after_term in lexicon.mail_search_after_terms:
            clean_term = str(after_term or "").strip().lower()
            if not clean_term:
                continue
            match = re.search(rf"\b{re.escape(clean_term)}\b\s+(.+)$", str(message or ""), re.IGNORECASE)
            if not match:
                continue
            value = str(match.group(1) or "").strip(" .,:;!?")
            if explicit_ref and value.lower().startswith(explicit_ref.lower() + " "):
                value = value[len(explicit_ref):].strip(" .,:;!?")
            if value:
                return value
        return cls._extract_mail_search_query(message, explicit_ref)

    @classmethod
    def _extract_mqtt_topic_with_lexicon(cls, message: str, lexicon: CapabilityRoutingLexicon) -> str:
        raw = str(message or "").strip()
        for topic_term in lexicon.mqtt_topic_terms:
            clean_term = str(topic_term or "").strip()
            if not clean_term:
                continue
            match = re.search(rf"\b{re.escape(clean_term)}\s+([A-Za-z0-9_./-]+)\b", raw, re.IGNORECASE)
            if match:
                candidate = str(match.group(1) or "").strip()
                if candidate:
                    return candidate
        return cls._extract_mqtt_topic(message)

    @staticmethod
    def _clean_ssh_command(value: str) -> str:
        command = str(value or "").strip(" \t\r\n.,;")
        prefix = str(_CAPABILITY_ROUTER_LEXICON.get("clean_ssh_command_prefix") or "")
        if prefix:
            command = re.sub(prefix, "", command, flags=re.IGNORECASE).strip()
        if (command.startswith('"') and command.endswith('"')) or (command.startswith("'") and command.endswith("'")):
            command = command[1:-1].strip()
        return command

    @classmethod
    def _extract_ssh_command(cls, message: str, explicit_ref: str = "") -> str:
        raw = str(message or "").strip()
        if not raw:
            return ""

        action = str(_CAPABILITY_ROUTER_LEXICON.get("ssh_action_pattern") or "")
        command_prefix = str(_CAPABILITY_ROUTER_LEXICON.get("ssh_command_prefix_pattern") or "")
        ref_variants: list[str] = []
        clean_ref = str(explicit_ref or "").strip()
        if clean_ref:
            ref_variants.append(re.escape(clean_ref))
            ref_spaced = re.sub(r"[-_]+", " ", clean_ref)
            if ref_spaced != clean_ref:
                ref_variants.append(re.escape(ref_spaced))
        if ref_variants:
            target = "(?:" + "|".join(ref_variants) + ")"
            raw_patterns = _CAPABILITY_ROUTER_LEXICON.get("ssh_target_patterns", [])
            patterns = (
                str(pattern).format(action=action, command_prefix=command_prefix, target=target)
                for pattern in raw_patterns
                if str(pattern).strip()
            )
            for pattern in patterns:
                match = re.search(pattern, raw, re.IGNORECASE)
                if match:
                    return cls._clean_ssh_command(match.group("cmd"))

        raw_patterns = _CAPABILITY_ROUTER_LEXICON.get("ssh_without_ref_patterns", [])
        patterns_without_ref = (
            str(pattern).format(action=action, command_prefix=command_prefix)
            for pattern in raw_patterns
            if str(pattern).strip()
        )
        for pattern in patterns_without_ref:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                return cls._clean_ssh_command(match.group("cmd"))
        return ""

    @classmethod
    def _extract_natural_ssh_command(cls, message: str) -> str:
        return ""

    @classmethod
    def _extract_natural_ssh_command_with_lexicon(cls, message: str, lexicon: CapabilityRoutingLexicon) -> str:
        lower = str(message or "").strip().lower()
        if cls._contains_any(lower, lexicon.ssh_natural_disk_terms):
            return "df -h"
        if cls._contains_any(lower, lexicon.ssh_natural_uptime_terms) or cls._contains_any(lower, lexicon.ssh_natural_online_terms):
            return "uptime"
        return cls._extract_natural_ssh_command(message)

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
        if len(ref_lower) >= 3 and ref_lower in lower:
            return 1000 + len(clean_ref)
        if len(ref_spaced) >= 3 and ref_spaced in lower:
            return 900 + len(clean_ref)
        if len(ref_lower) < 3 and ref_lower in message_tokens:
            return 1000 + len(clean_ref)
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
        message_tokens = set(self._split_ref_tokens(lower))
        if len(alias_lower) >= 3 and alias_lower in lower:
            return 700 + len(clean_alias)
        if len(alias_spaced) >= 3 and alias_spaced != alias_lower and alias_spaced in lower:
            return 650 + len(clean_alias)
        if len(alias_lower) < 3 and alias_lower in message_tokens:
            return 700 + len(clean_alias)
        alias_tokens = self._split_ref_tokens(alias_lower)
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
                if str(kind).strip().lower() == "rss":
                    continue
                alias_rows = ((aliases_by_kind or {}).get(kind, {}) or {}).get(clean_ref, [])
                for alias in alias_rows:
                    alias_tokens = self._split_ref_tokens(str(alias or ""))
                    if _is_generic_connection_label(alias_tokens):
                        continue
                    alias_score = self._connection_alias_match_score(message, str(alias))
                    if alias_score > 0:
                        candidates.append((alias_score, str(kind).strip().lower(), clean_ref))
        if not candidates:
            return "", ""
        candidates.sort(key=lambda item: (item[0], len(item[2])), reverse=True)
        _, kind, ref = candidates[0]
        return kind, ref

    def _requested_phrase_matches_connection(
        self,
        requested_phrase: str,
        *,
        connection_kind: str,
        connection_ref: str,
        aliases_by_kind: dict[str, dict[str, Iterable[str]]] | None = None,
        lexicon: CapabilityRoutingLexicon,
    ) -> bool:
        clean_requested = str(requested_phrase or "").strip()
        clean_ref = str(connection_ref or "").strip()
        clean_kind = str(connection_kind or "").strip().lower()
        if not clean_requested or not clean_ref or not clean_kind:
            return False
        if clean_requested.lower() == clean_ref.lower():
            return True
        if self._connection_ref_match_score(clean_requested, clean_ref, lexicon) > 0:
            return True
        alias_rows = ((aliases_by_kind or {}).get(clean_kind, {}) or {}).get(clean_ref, [])
        for alias in alias_rows:
            clean_alias = self._normalize(str(alias or ""))
            alias_tokens = self._split_ref_tokens(clean_alias)
            if _is_generic_connection_label(alias_tokens):
                continue
            if clean_alias.lower() == clean_requested.lower():
                return True
            if self._connection_alias_match_score(clean_requested, clean_alias) > 0:
                return True
        return False

    @staticmethod
    def _requested_ref_candidate_after_term(message: str, term: str) -> str:
        clean_term = str(term or "").strip()
        if not clean_term:
            return ""
        pattern = rf"\b{re.escape(clean_term)}\b\s+([a-z0-9._-]+)\b"
        match = re.search(pattern, str(message or ""), re.IGNORECASE)
        if not match:
            return ""
        return str(match.group(1) or "").strip()

    @staticmethod
    def _clean_requested_ref_candidate(candidate: str, ignore_tokens: set[str]) -> str:
        clean = re.sub(r"\s+", " ", str(candidate or "").strip(" \t\r\n.,;:!?")).strip()
        if not clean:
            return ""
        tokens = [token for token in re.split(r"\s+", clean) if token]
        while tokens and tokens[0].lower() in ignore_tokens:
            tokens.pop(0)
        if not tokens:
            return ""
        return " ".join(tokens[:4]).strip()

    @staticmethod
    def _invalid_requested_ref_phrase_candidate(
        candidate: str,
        *,
        prefixes: tuple[str, ...],
        suffixes: tuple[str, ...],
    ) -> bool:
        tokens = [token.lower() for token in re.split(r"\s+", str(candidate or "").strip()) if token.strip()]
        if not tokens:
            return True
        suffix_set = {str(item).strip().lower() for item in suffixes if str(item).strip()}
        prefix_set = {str(item).strip().lower() for item in prefixes if str(item).strip()}
        if any(token in prefix_set for token in tokens):
            return True
        if tokens[-1] in suffix_set and (len(tokens) == 1 or (len(tokens) == 2 and len(tokens[0]) <= 1)):
            return True
        return False

    @classmethod
    def _extract_requested_connection_phrase_hint(
        cls,
        message: str,
        connection_kind: str,
        ignore_tokens: set[str],
    ) -> str:
        raw = str(message or "").strip()
        kind = str(connection_kind or "").strip().lower()
        if not raw:
            return ""
        routing_spec = connection_routing_spec(kind)
        suffixes = tuple(routing_spec.requested_ref_suffixes)
        prefixes = tuple(routing_spec.requested_ref_prefixes)
        suffix_pattern = "|".join(re.escape(item) for item in suffixes if str(item).strip())
        prefix_pattern = "|".join(re.escape(item) for item in prefixes if str(item).strip())
        patterns: tuple[str, ...] = ()
        if suffix_pattern:
            patterns = (
                rf"\b(?:{prefix_pattern})\b\s+{cls._REQUESTED_CONNECTION_ARTICLES}\s*([a-z0-9._-]+(?:\s+[a-z0-9._-]+){{0,2}}\s+(?:{suffix_pattern}))\b"
                if prefix_pattern
                else "",
                rf"\b{cls._REQUESTED_CONNECTION_REQUIRED_ARTICLES}\s+([a-z0-9._-]+(?:\s+[a-z0-9._-]+){{0,2}}\s+(?:{suffix_pattern}))\b",
            )
        for pattern in patterns:
            if not pattern:
                continue
            match = re.search(pattern, raw, re.IGNORECASE)
            if not match:
                continue
            candidate = cls._clean_requested_ref_candidate(str(match.group(1) or ""), ignore_tokens)
            if candidate and not cls._invalid_requested_ref_phrase_candidate(
                candidate,
                prefixes=prefixes,
                suffixes=suffixes,
            ):
                return candidate
        return ""

    @classmethod
    def _extract_requested_connection_ref_hint(
        cls,
        message: str,
        connection_kind: str,
        lexicon: CapabilityRoutingLexicon,
    ) -> str:
        raw = str(message or "").strip()
        kind = str(connection_kind or "").strip().lower()
        if not raw or not kind:
            return ""
        if kind == "rss":
            return ""

        markers_by_kind: dict[str, tuple[str, ...]] = {
            "discord": lexicon.discord_requested_ref_terms,
            "webhook": lexicon.webhook_requested_ref_terms,
            "http_api": lexicon.api_requested_ref_terms,
            "email": lexicon.email_requested_ref_terms,
            "imap": lexicon.imap_requested_ref_terms,
            "mqtt": lexicon.mqtt_requested_ref_terms,
            "rss": lexicon.rss_requested_ref_terms,
        }
        ignore_tokens = {str(token).strip().lower() for token in lexicon.requested_connection_ref_ignore_terms}

        phrase_candidate = cls._extract_requested_connection_phrase_hint(raw, kind, ignore_tokens)
        if phrase_candidate:
            return phrase_candidate

        marker_terms: tuple[str, ...]
        if kind == "ssh":
            marker_terms = (*lexicon.ssh_requested_ref_prepositions, *lexicon.ssh_requested_ref_terms)
        else:
            marker_terms = markers_by_kind.get(kind, ())

        for marker in marker_terms:
            candidate = cls._requested_ref_candidate_after_term(raw, marker)
            if not candidate:
                continue
            cleaned_candidate = cls._clean_requested_ref_candidate(candidate, ignore_tokens)
            if not cleaned_candidate:
                continue
            if cleaned_candidate.lower() in ignore_tokens:
                continue
            return cleaned_candidate
        return ""

    @staticmethod
    def _fallback_kind_from_candidates(candidate_kinds: Iterable[str], preferred_order: Iterable[str]) -> str:
        ordered = [str(kind).strip().lower() for kind in candidate_kinds if str(kind).strip()]
        if not ordered:
            return ""
        if len(ordered) == 1:
            return ordered[0]
        for preferred in (str(kind).strip().lower() for kind in preferred_order if str(kind).strip()):
            if preferred in ordered:
                return preferred
        return ordered[0]

    def _resolve_connection_kind(
        self,
        message: str,
        *,
        capability: str,
        explicit_kind: str,
        available_kinds: set[str],
        lexicon: CapabilityRoutingLexicon,
    ) -> str:
        if explicit_kind:
            return explicit_kind
        candidate_kinds = [kind for kind in capability_executor_kinds(capability) if kind in available_kinds]
        if not candidate_kinds:
            return ""
        inferred = infer_preferred_connection_kind(
            message,
            available_kinds=candidate_kinds,
        )
        if inferred and inferred in set(candidate_kinds):
            return inferred
        return self._fallback_kind_from_candidates(candidate_kinds, lexicon.connection_kind_priority)

    def _has_remote_signal(
        self,
        *,
        lower: str,
        available_kinds: set[str],
        explicit_ref: str,
        ssh_intent: bool,
        has_feed_hint: bool,
        has_feed_request: bool,
        has_feed_subject: bool,
        has_api_hint: bool,
        has_discord_hint: bool,
        has_email_hint: bool,
        has_imap_hint: bool,
        has_mqtt_hint: bool,
        has_website_hint: bool,
        lexicon: CapabilityRoutingLexicon,
    ) -> bool:
        return (
            any(token in lower for token in lexicon.remote_terms)
            or bool(explicit_ref)
            or bool(self._extract_path(lower))
            or ssh_intent
            or has_feed_hint
            or (has_feed_request and "rss" in available_kinds and has_feed_subject)
            or has_api_hint
            or has_discord_hint
            or has_email_hint
            or has_imap_hint
            or has_mqtt_hint
            or has_website_hint
        )

    def _detect_capability(
        self,
        *,
        lower: str,
        explicit_kind: str,
        available_kinds: set[str],
        ssh_intent: bool,
        ssh_target_signal: bool,
        has_imap_hint: bool,
        has_email_hint: bool,
        has_mqtt_hint: bool,
        has_feed_request: bool,
        has_explicit_web_search_hint: bool,
        has_feed_hint: bool,
        has_feed_subject: bool,
        has_website_hint: bool,
        has_api_hint: bool,
        lexicon: CapabilityRoutingLexicon,
    ) -> tuple[str, float]:
        if self._looks_like_calendar_request(lower) and "google_calendar" in available_kinds:
            return "calendar_read", 0.8
        if ssh_intent and ssh_target_signal:
            return "ssh_command", 0.82
        if (has_imap_hint or explicit_kind == "imap") and self._contains_any(lower, lexicon.mail_search_terms):
            return "mail_search", 0.77
        if (has_imap_hint or explicit_kind == "imap") and self._contains_any(lower, lexicon.mail_read_terms):
            return "mail_read", 0.77
        if (has_email_hint or explicit_kind == "email") and self._contains_any(lower, lexicon.email_send_action_terms):
            return "email_send", 0.77
        if (has_mqtt_hint or explicit_kind == "mqtt") and self._contains_any(lower, lexicon.mqtt_action_terms):
            return "mqtt_publish", 0.76
        if (
            has_feed_request
            and not has_explicit_web_search_hint
            and (has_feed_hint or explicit_kind == "rss" or ("rss" in available_kinds and has_feed_subject))
        ):
            return "feed_read", 0.8
        if (has_website_hint or explicit_kind == "website") and (
            self._contains_any(lower, lexicon.list_terms)
            or any(term in lower for term in self._WEBSITE_COLLECTION_TERMS)
        ):
            return "website_list", 0.78
        if (has_website_hint or explicit_kind == "website") and self._contains_any(lower, lexicon.read_terms):
            return "website_read", 0.78
        if (has_api_hint or explicit_kind == "http_api") and self._contains_any(lower, lexicon.api_action_terms):
            return "api_request", 0.76
        if self._contains_any(lower, lexicon.list_terms):
            return "file_list", 0.8
        if self._contains_any(lower, lexicon.write_terms):
            return "file_write", 0.84
        if self._contains_any(lower, lexicon.read_terms):
            return "file_read", 0.8
        if (self._contains_any(lower, lexicon.discord_send_terms) or explicit_kind == "discord") and self._contains_any(
            lower, lexicon.discord_action_terms
        ):
            return "discord_send", 0.79
        has_webhook_hint = self._contains_any(lower, lexicon.webhook_send_terms) or explicit_kind == "webhook"
        has_webhook_action = self._contains_any(lower, lexicon.webhook_action_terms)
        if has_webhook_hint and has_webhook_action:
            return "webhook_send", 0.78
        return "", 0.0

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
        website_terms = connection_routing_spec("website").language_hints
        has_website_hint = "website" in available_kinds and self._contains_any(lower, website_terms)
        requested_ssh_target = (
            self._extract_requested_connection_ref_hint(raw, "ssh", lexicon)
            if "ssh" in available_kinds
            else ""
        )
        natural_ssh_command = self._extract_natural_ssh_command_with_lexicon(raw, lexicon)
        explicit_ssh_command = self._extract_ssh_command(raw, explicit_ref)
        ssh_command = explicit_ssh_command
        ssh_intent = bool(ssh_command) or self._contains_any(lower, lexicon.ssh_command_terms)
        ssh_intent = ssh_intent or bool(natural_ssh_command)
        ssh_target_signal = explicit_kind == "ssh" or has_ssh_hint or bool(requested_ssh_target)
        has_remote_hint = self._has_remote_signal(
            lower=lower,
            available_kinds=available_kinds,
            explicit_ref=explicit_ref,
            ssh_intent=ssh_intent,
            has_feed_hint=has_feed_hint,
            has_feed_request=has_feed_request,
            has_feed_subject=has_feed_subject,
            has_api_hint=has_api_hint,
            has_discord_hint=has_discord_hint,
            has_email_hint=has_email_hint,
            has_imap_hint=has_imap_hint,
            has_mqtt_hint=has_mqtt_hint,
            has_website_hint=has_website_hint,
            lexicon=lexicon,
        )
        if not has_remote_hint:
            if self._looks_like_calendar_request(lower) and "google_calendar" in available_kinds:
                has_remote_hint = True
            else:
                return None

        capability, confidence = self._detect_capability(
            lower=lower,
            explicit_kind=explicit_kind,
            available_kinds=available_kinds,
            ssh_intent=ssh_intent,
            ssh_target_signal=ssh_target_signal,
            has_imap_hint=has_imap_hint,
            has_email_hint=has_email_hint,
            has_mqtt_hint=has_mqtt_hint,
            has_feed_request=has_feed_request,
            has_explicit_web_search_hint=has_explicit_web_search_hint,
            has_feed_hint=has_feed_hint,
            has_feed_subject=has_feed_subject,
            has_website_hint=has_website_hint,
            has_api_hint=has_api_hint,
            lexicon=lexicon,
        )
        if not capability:
            return None

        executor_kinds = [kind for kind in capability_executor_kinds(capability) if kind]
        allowed_kinds = [kind for kind in executor_kinds if kind in available_kinds]
        allowed_kind_set = set(allowed_kinds or executor_kinds)
        if capability and not allowed_kind_set:
            return None
        if explicit_kind and explicit_kind not in allowed_kind_set:
            explicit_kind = ""
            explicit_ref = ""

        connection_kind = explicit_kind
        if capability == "ssh_command" and "ssh" in available_kinds:
            connection_kind = "ssh"
        if not connection_kind:
            connection_kind = self._resolve_connection_kind(
                raw,
                capability=capability,
                explicit_kind=explicit_kind,
                available_kinds=allowed_kind_set or available_kinds,
                lexicon=lexicon,
            ) or self._fallback_kind_from_candidates(allowed_kinds or executor_kinds or available_kinds, lexicon.connection_kind_priority)

        requested_connection_ref = ""
        requested_candidate = ""
        if connection_kind:
            requested_candidate = self._extract_requested_connection_ref_hint(raw, connection_kind, lexicon)
        if capability == "website_read" and not requested_candidate and not explicit_ref:
            requested_candidate = self._extract_website_target_phrase(raw)

        if (
            connection_kind == "ssh"
            and explicit_ref
            and requested_candidate
            and not self._requested_phrase_matches_connection(
                requested_candidate,
                connection_kind=connection_kind,
                connection_ref=explicit_ref,
                aliases_by_kind=available_connection_aliases_by_kind,
                lexicon=lexicon,
            )
        ):
            explicit_ref = ""
            if explicit_kind == connection_kind:
                explicit_kind = ""

        if connection_kind and not explicit_ref and requested_candidate:
            available_refs_for_kind = {
                str(ref).strip().lower()
                for ref in refs_by_kind.get(connection_kind, ())
                if str(ref).strip()
            }
            if requested_candidate.lower() not in available_refs_for_kind:
                requested_connection_ref = requested_candidate

        mail_search_content = self._extract_mail_search_query_with_lexicon(raw, explicit_ref, lexicon)
        mqtt_topic = self._extract_mqtt_topic_with_lexicon(raw, lexicon)

        return CapabilityDraft(
            capability=capability,
            connection_kind=connection_kind,
            explicit_connection_ref=explicit_ref,
            requested_connection_ref=requested_connection_ref,
            path=(
                self._extract_calendar_range(raw)
                if capability == "calendar_read"
                else mqtt_topic
                if capability == "mqtt_publish"
                else self._extract_path(raw)
            ),
            content=(
                self._extract_calendar_search(raw)
                if capability == "calendar_read"
                else self._extract_website_group(raw)
                if capability == "website_list"
                else
                ssh_command
                if capability == "ssh_command"
                else
                self._extract_webhook_content(raw, explicit_ref)
                if capability in {"webhook_send", "discord_send", "email_send", "mqtt_publish"}
                else mail_search_content
                if capability == "mail_search"
                else self._extract_content(raw)
            ),
            confidence=confidence,
        )
