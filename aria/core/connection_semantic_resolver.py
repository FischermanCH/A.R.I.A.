from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aria.core.connection_catalog import connection_kind_label, connection_routing_spec

_CONNECTION_SEMANTIC_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "connection_semantic_resolver.json"


def _load_connection_semantic_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_CONNECTION_SEMANTIC_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load connection semantic resolver lexicon: {_CONNECTION_SEMANTIC_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_CONNECTION_SEMANTIC_LEXICON = _load_connection_semantic_lexicon()


def _semantic_prompt(key: str) -> str:
    return str(_CONNECTION_SEMANTIC_LEXICON.get(key) or "").strip()


def _semantic_terms(key: str) -> tuple[str, ...]:
    raw = _CONNECTION_SEMANTIC_LEXICON.get(key, [])
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip().lower() for item in raw if str(item).strip())


def message_has_connection_disambiguation_terms(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(message or "").strip().lower())
    clean = f" {normalized} "
    if not clean.strip():
        return False
    return any(f" {term} " in clean for term in _semantic_terms("target_disambiguation_terms"))


@dataclass(slots=True)
class SemanticConnectionHint:
    connection_kind: str = ""
    connection_ref: str = ""
    source: str = ""
    note: str = ""


@dataclass(slots=True)
class SemanticConnectionCandidate:
    connection_kind: str = ""
    connection_ref: str = ""
    source: str = ""
    note: str = ""
    alias: str = ""
    score: int = 0


@dataclass(slots=True)
class RoutingDecisionRecord:
    stage: str = ""
    preferred_kind: str = ""
    chosen_kind: str = ""
    chosen_ref: str = ""
    chosen_source: str = ""
    chosen_note: str = ""
    candidate_count: int = 0
    candidates: list[SemanticConnectionCandidate] = field(default_factory=list)


def split_connection_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(value or "").lower()) if token]


def normalize_connection_alias(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).strip(" -_:,./")


def _is_generic_connection_label(label_tokens: list[str]) -> bool:
    generic_tokens = {
        "server",
        "host",
        "system",
        "node",
        "profile",
        "profil",
        "channel",
        "kanal",
        "feed",
        "news",
        "mail",
        "email",
        "api",
        "hook",
        "webhook",
        "mqtt",
        "rss",
    }
    if not label_tokens:
        return True
    significant_tokens = [token for token in label_tokens if token not in generic_tokens]
    return not significant_tokens


def build_connection_aliases(connection_kind: str, ref: str, row: Any) -> list[str]:
    aliases: list[str] = []

    def _read(name: str) -> str:
        if isinstance(row, dict):
            return str(row.get(name, "")).strip()
        return str(getattr(row, name, "")).strip()

    def _add(value: str) -> None:
        clean = normalize_connection_alias(value)
        if clean and clean not in aliases:
            aliases.append(clean)

    def _read_bool(name: str) -> bool:
        raw = row.get(name) if isinstance(row, dict) else getattr(row, name, False)
        return bool(raw)

    def _add_kind_meta_aliases(values: list[str], suffixes: list[str]) -> None:
        for value in values:
            clean_value = normalize_connection_alias(value)
            if not clean_value:
                continue
            for suffix in suffixes:
                clean_suffix = normalize_connection_alias(suffix)
                if not clean_suffix:
                    continue
                if clean_suffix in clean_value:
                    continue
                _add(f"{clean_value} {clean_suffix}")

    clean_ref = str(ref or "").strip()
    _add(clean_ref)
    ref_tokens = split_connection_tokens(clean_ref)
    if ref_tokens:
        _add(" ".join(ref_tokens))

    generic_tokens = {"feed", "feeds", "news", "rss", "atom", "api", "mail", "email", "hook", "webhook", "mqtt"}
    trimmed_tokens = [token for token in ref_tokens if token not in generic_tokens]
    if len(trimmed_tokens) >= 2:
        _add(" ".join(trimmed_tokens))

    meta_title = _read("title")
    meta_description = _read("description")
    meta_group_name = _read("group_name")
    _add(meta_title)
    _add(meta_group_name)
    if meta_description and len(meta_description) <= 120:
        _add(meta_description)
    meta_aliases = row.get("aliases", []) if isinstance(row, dict) else getattr(row, "aliases", [])
    if isinstance(meta_aliases, list):
        for item in meta_aliases:
            _add(str(item))
    meta_tags = row.get("tags", []) if isinstance(row, dict) else getattr(row, "tags", [])
    if isinstance(meta_tags, list):
        for item in meta_tags:
            _add(str(item))

    kind = str(connection_kind or "").strip().lower()
    if kind in {"sftp", "smb"}:
        host = _read("host")
        user = _read("user")
        root_path = _read("root_path")
        share = _read("share")
        ref_hostish = ref_tokens[0] if ref_tokens else ""
        if len(ref_tokens) >= 2 and ref_tokens[1].isdigit() and len(ref_hostish) >= 4:
            _add(ref_hostish)
            if share:
                _add(f"{ref_hostish} {share}")
        if ref_tokens and ref_tokens[-1].isdigit() and user:
            user_host_alias = normalize_connection_alias(f"{ref_tokens[0]}-{user}")
            if len(user_host_alias) >= 4:
                _add(user_host_alias)
                if share:
                    _add(f"{user_host_alias} {share}")
        _add(host)
        if host:
            host_short = host.split(".", 1)[0]
            _add(host_short)
        _add(user)
        _add(share)
        _add(root_path)
        if share and host:
            _add(f"{host_short if host else host} {share}")
        if "docker" in root_path.lower():
            _add("docker")
            _add("docker verzeichnis")
            _add("docker ordner")
    elif kind == "rss":
        feed_url = _read("feed_url")
        parsed = urlparse(feed_url)
        host = str(parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        _add(host)
        if host:
            _add(host.split(".", 1)[0].replace("-", " "))
    elif kind in {"webhook", "http_api"}:
        raw_url = _read("url") or _read("base_url")
        parsed = urlparse(raw_url)
        host = str(parsed.netloc or "").lower()
        path = str(parsed.path or "").strip("/")
        _add(host)
        if host:
            _add(host.split(".", 1)[0].replace("-", " "))
        if path:
            _add(path.replace("/", " "))
    elif kind == "website":
        raw_url = _read("url")
        parsed = urlparse(raw_url)
        host = str(parsed.netloc or "").lower()
        path = str(parsed.path or "").strip("/")
        _add(raw_url)
        _add(host)
        if host.startswith("www."):
            host = host[4:]
            _add(host)
        if host:
            _add(host.split(".", 1)[0].replace("-", " "))
        if path:
            _add(path.replace("/", " "))
        lower_blob = " ".join(
            value.lower()
            for value in (meta_title, meta_description, meta_group_name, " ".join(str(item) for item in meta_tags) if isinstance(meta_tags, list) else "")
            if str(value).strip()
        )
        if any(token in lower_blob for token in ("docs", "documentation", "dokumentation")):
            _add("docs")
            _add("documentation")
            _add("dokumentation")
    elif kind in {"email", "imap"}:
        _add(_read("user"))
        _add(_read("smtp_host") or _read("host"))
        _add(_read("from_email"))
        _add(_read("to_email"))
        _add(_read("mailbox"))
    elif kind == "mqtt":
        _add(_read("host"))
        _add(_read("topic"))
    elif kind == "discord":
        _add(_read("webhook_url"))
        title_blob = " ".join(
            value
            for value in (
                clean_ref,
                meta_title,
                meta_description,
                " ".join(str(item) for item in meta_tags) if isinstance(meta_tags, list) else "",
            )
            if str(value).strip()
        ).lower()
        if any(
            _read_bool(flag_name)
            for flag_name in (
                "alert_recipe_errors",
                "alert_skill_errors",
                "alert_safe_fix",
                "alert_connection_changes",
                "alert_system_events",
            )
        ):
            for value in (
                "alerts",
                "alerts channel",
                "alert channel",
                "notification channel",
                "ops alerts",
            ):
                _add(value)
        if any(token in title_blob for token in ("logs", "log", "logging")):
            for value in ("logs", "logs channel", "log channel"):
                _add(value)
        if _read_bool("allow_recipe_messages") or _read_bool("allow_skill_messages") or _read_bool("send_test_messages"):
            for value in (
                "messages",
                "messages channel",
                "chat channel",
                "test channel",
            ):
                _add(value)
        if any(token in title_blob for token in ("message", "messages", "chat")):
            for value in ("messages", "messages channel", "chat channel"):
                _add(value)

    meta_values: list[str] = []
    if meta_title:
        meta_values.append(meta_title)
    if meta_group_name:
        meta_values.append(meta_group_name)
    if isinstance(meta_tags, list):
        meta_values.extend(str(item) for item in meta_tags if str(item).strip())

    suffixes = connection_routing_spec(kind).semantic_suffixes
    if suffixes:
        _add_kind_meta_aliases(meta_values, suffixes)

    return aliases[:10]


def connection_label_match_score(message: str, label: str) -> int:
    clean_label = normalize_connection_alias(label)
    if not clean_label:
        return 0
    lower = normalize_connection_alias(message)
    message_tokens = set(split_connection_tokens(lower))
    label_tokens = split_connection_tokens(clean_label)
    if _is_generic_connection_label(label_tokens):
        return 0
    if clean_label and clean_label in lower:
        return 1000 + len(clean_label)
    if len(label_tokens) >= 2 and all(token in message_tokens for token in label_tokens):
        return 120 + len(label_tokens) * 12 + len(clean_label)
    if len(label_tokens) == 1 and label_tokens[0] in message_tokens and len(label_tokens[0]) >= 4:
        return 40 + len(label_tokens[0])
    return 0


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def build_routing_decision_record(
    *,
    stage: str,
    candidates: list[SemanticConnectionCandidate],
    hint: SemanticConnectionHint | None = None,
    preferred_kind: str = "",
) -> RoutingDecisionRecord:
    chosen = hint or SemanticConnectionHint()
    return RoutingDecisionRecord(
        stage=str(stage or "").strip(),
        preferred_kind=str(preferred_kind or "").strip().lower(),
        chosen_kind=str(chosen.connection_kind or "").strip().lower(),
        chosen_ref=str(chosen.connection_ref or "").strip(),
        chosen_source=str(chosen.source or "").strip(),
        chosen_note=str(chosen.note or "").strip(),
        candidate_count=len(list(candidates or [])),
        candidates=list(candidates or []),
    )


def format_routing_decision_record(record: RoutingDecisionRecord) -> list[str]:
    if not isinstance(record, RoutingDecisionRecord):
        return []
    lines: list[str] = []
    top_candidates = list(record.candidates or [])[:3]
    if top_candidates:
        rendered = "; ".join(
            f"`{item.connection_kind}/{item.connection_ref}` score={int(item.score)} source={item.source or '-'}"
            + (f" alias={item.alias}" if item.alias else "")
            for item in top_candidates
        )
        lines.append(
            f"Routing: {record.stage or 'candidate_resolver'} candidates={record.candidate_count}"
            + (f" preferred={record.preferred_kind}" if record.preferred_kind else "")
            + f" -> {rendered}"
        )
    if record.chosen_kind or record.chosen_ref:
        target = f"{record.chosen_kind}/{record.chosen_ref}" if record.chosen_ref else f"{record.chosen_kind}/-"
        line = (
            f"Routing: {record.stage or 'candidate_resolver'} selected "
            f"`{target}`"
        )
        if record.chosen_source:
            line += f" source={record.chosen_source}"
        if record.chosen_note:
            line += f" note={record.chosen_note}"
        lines.append(line)
    return lines


class ConnectionSemanticResolver:
    def __init__(self, llm_client: Any | None) -> None:
        self._llm_client = llm_client

    @staticmethod
    def _split_tokens(value: str) -> list[str]:
        return split_connection_tokens(value)

    @classmethod
    def _build_rss_aliases(cls, ref: str, row: Any) -> list[str]:
        return build_connection_aliases("rss", ref, row)[:8]

    @staticmethod
    def _read_row_value(row: Any, name: str) -> str:
        if isinstance(row, dict):
            return str(row.get(name, "")).strip()
        return str(getattr(row, name, "")).strip()

    @classmethod
    def _rss_scope_priority(cls, ref: str, row: Any) -> int:
        clean_ref = normalize_connection_alias(ref)
        title = normalize_connection_alias(cls._read_row_value(row, "title"))
        group_name = normalize_connection_alias(cls._read_row_value(row, "group_name"))
        tokens = set(split_connection_tokens(" ".join(part for part in (clean_ref, title, group_name) if part)))
        priority = 0
        if group_name:
            priority += 3
        if {"all", "alle"} & tokens:
            priority += 2
        if {"collection", "bundle", "aggregate", "aggregated", "sammlung"} & tokens:
            priority += 2
        return priority

    def resolve_connection(
        self,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
    ) -> SemanticConnectionHint:
        candidates = self.collect_connection_candidates(message, available_connection_pools)
        if not candidates:
            return SemanticConnectionHint()
        winner = candidates[0]
        if winner.score < 40:
            return SemanticConnectionHint()
        return SemanticConnectionHint(
            connection_kind=winner.connection_kind,
            connection_ref=winner.connection_ref,
            source=winner.source or "semantic_alias",
            note=winner.note or (f"alias:{winner.alias}" if winner.alias else ""),
        )

    def collect_connection_candidates(
        self,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
    ) -> list[SemanticConnectionCandidate]:
        preferred = str(preferred_kind or "").strip().lower()
        candidates: list[SemanticConnectionCandidate] = []
        for kind, rows in (available_connection_pools or {}).items():
            if not isinstance(rows, dict):
                continue
            clean_kind = str(kind).strip().lower()
            for ref, row in rows.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                aliases = build_connection_aliases(clean_kind, clean_ref, row)
                best_alias = ""
                best_score = 0
                for alias in aliases:
                    score = connection_label_match_score(message, alias)
                    if score > best_score:
                        best_score = score
                        best_alias = alias
                if best_score <= 0:
                    continue
                if preferred and clean_kind == preferred:
                    best_score += 5
                candidates.append(
                    SemanticConnectionCandidate(
                        connection_kind=clean_kind,
                        connection_ref=clean_ref,
                        source="semantic_alias",
                        note=f"alias:{best_alias}" if best_alias else "",
                        alias=best_alias,
                        score=best_score,
                    )
                )
        candidates.sort(
            key=lambda item: (
                item.score,
                1 if preferred and item.connection_kind == preferred else 0,
                len(item.alias),
                item.connection_kind,
                item.connection_ref,
            ),
            reverse=True,
        )
        return candidates

    async def resolve_connection_with_llm(
        self,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
        force_llm: bool = False,
        include_all_profiles: bool = False,
    ) -> SemanticConnectionHint:
        if self._llm_client is None:
            return SemanticConnectionHint()

        rows_for_prompt: list[str] = []
        valid_pairs: set[tuple[str, str]] = set()
        candidates = self.collect_connection_candidates(
            message,
            available_connection_pools,
            preferred_kind=preferred_kind,
        )
        if not force_llm and len(candidates) == 1 and candidates[0].score >= 40:
            winner = candidates[0]
            return SemanticConnectionHint(
                connection_kind=winner.connection_kind,
                connection_ref=winner.connection_ref,
                source=winner.source or "semantic_alias",
                note=winner.note or (f"alias:{winner.alias}" if winner.alias else ""),
            )
        if candidates and not include_all_profiles:
            for candidate in candidates:
                kind = candidate.connection_kind
                ref = candidate.connection_ref
                row = dict((available_connection_pools or {}).get(kind, {})).get(ref, {})
                valid_pairs.add((kind, ref))
                aliases = build_connection_aliases(kind, ref, row)[:6]
                rows_for_prompt.append(
                    f"- kind: {kind} | ref: {ref} | label: {connection_kind_label(kind)} | score: {candidate.score} | aliases: {', '.join(aliases) or '-'}"
                )
        else:
            for kind, rows in sorted((available_connection_pools or {}).items()):
                if not isinstance(rows, dict):
                    continue
                for ref, row in sorted(rows.items()):
                    clean_kind = str(kind).strip().lower()
                    clean_ref = str(ref).strip()
                    if not clean_ref:
                        continue
                    valid_pairs.add((clean_kind, clean_ref))
                    aliases = build_connection_aliases(clean_kind, clean_ref, row)[:6]
                    rows_for_prompt.append(
                        f"- kind: {clean_kind} | ref: {clean_ref} | label: {connection_kind_label(clean_kind)} | score: 0 | aliases: {', '.join(aliases) or '-'}"
                    )
        if len(valid_pairs) < 2:
            return SemanticConnectionHint()

        preferred = str(preferred_kind or "").strip().lower()
        system_prompt = _semantic_prompt("connection_system_prompt")
        user_prompt = "\n".join(
            [
                f"Nutzeranfrage: {str(message or '').strip()}",
                f"Bevorzugter Typ: {preferred or '-'}",
                "",
                "Verfuegbare Connection-Profile:",
                *rows_for_prompt,
                "",
                _semantic_prompt("connection_disambiguation_hint"),
            ]
        )
        try:
            response = await self._llm_client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception:
            return SemanticConnectionHint()

        payload = _extract_json_object(getattr(response, "content", "") or "") or {}
        kind = str(payload.get("kind", "")).strip().lower()
        ref = str(payload.get("ref", "")).strip()
        confidence = str(payload.get("confidence", "")).strip().lower()
        reason = str(payload.get("reason", "")).strip()
        if confidence not in {"high", "medium", "low"} or confidence == "low":
            return SemanticConnectionHint()
        if (kind, ref) not in valid_pairs:
            return SemanticConnectionHint()
        return SemanticConnectionHint(
            connection_kind=kind,
            connection_ref=ref,
            source="semantic_llm",
            note=f"semantic_llm:{reason or f'{kind}:{ref}'}",
        )

    async def resolve_rss_ref(
        self,
        message: str,
        available_connections: dict[str, Any],
        *,
        candidates: list[SemanticConnectionCandidate] | None = None,
    ) -> SemanticConnectionHint:
        rows = {
            str(ref).strip(): row
            for ref, row in (available_connections or {}).items()
            if str(ref).strip()
        }
        rss_candidates = [
            candidate
            for candidate in (candidates or self.collect_connection_candidates(message, {"rss": rows}, preferred_kind="rss"))
            if candidate.connection_kind == "rss" and candidate.connection_ref in rows
        ]
        if self._llm_client is None or len(rss_candidates) < 2:
            return SemanticConnectionHint()

        top_score = int(getattr(rss_candidates[0], "score", 0) or 0)
        top_candidates = [candidate for candidate in rss_candidates if int(getattr(candidate, "score", 0) or 0) == top_score]
        grouped_top_candidates = [
            candidate
            for candidate in top_candidates
            if self._rss_scope_priority(candidate.connection_ref, rows.get(candidate.connection_ref, {})) > 0
        ]
        if len(grouped_top_candidates) == 1:
            winner = grouped_top_candidates[0]
            return SemanticConnectionHint(
                connection_kind="rss",
                connection_ref=winner.connection_ref,
                source="semantic_group",
                note=f"semantic_group:{winner.connection_ref}",
            )
        prompt_candidates = grouped_top_candidates if len(grouped_top_candidates) >= 2 else rss_candidates

        prompt_lines: list[str] = []
        for candidate in prompt_candidates:
            ref = candidate.connection_ref
            row = rows.get(ref, {})
            feed_url = self._read_row_value(row, "feed_url")
            title = self._read_row_value(row, "title")
            group_name = self._read_row_value(row, "group_name")
            aliases = self._build_rss_aliases(ref, row)
            scope = "grouped" if self._rss_scope_priority(ref, row) > 0 else "single"
            prompt_lines.append(
                f"- ref: {ref} | score: {candidate.score} | scope: {scope} | title: {title or '-'} | group: {group_name or '-'} | url: {feed_url or '-'} | aliases: {', '.join(aliases) or '-'}"
            )

        system_prompt = _semantic_prompt("rss_system_prompt")
        user_prompt = "\n".join(
            [
                f"Nutzeranfrage: {str(message or '').strip()}",
                "",
                "Verfuegbare RSS-Profile:",
                *prompt_lines,
            ]
        )

        try:
            response = await self._llm_client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception:
            return SemanticConnectionHint()

        payload = _extract_json_object(getattr(response, "content", "") or "") or {}
        ref = str(payload.get("ref", "")).strip()
        confidence = str(payload.get("confidence", "")).strip().lower()
        reason = str(payload.get("reason", "")).strip()
        if ref not in rows or confidence not in {"high", "medium", "low"}:
            return SemanticConnectionHint()
        if confidence == "low":
            return SemanticConnectionHint()
        return SemanticConnectionHint(
            connection_kind="rss",
            connection_ref=ref,
            source="semantic_llm",
            note=f"semantic_llm:{reason or ref}",
        )
