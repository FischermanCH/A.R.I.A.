from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from aria.modules.connections_catalog.catalog import connection_kind_label

_CONNECTION_SYSTEM_PROMPT = (
    "Choose the best configured connection profile for the user request. Return JSON only with "
    '{"kind":"<listed kind or empty>","ref":"<listed ref or empty>","confidence":"high|medium|low",'
    '"reason":"short"}. Choose only from the supplied profiles; return empty values when none fits.'
)
_RSS_SYSTEM_PROMPT = (
    "Choose the best configured RSS profile for the user request. Return JSON only with "
    '{"ref":"<listed ref or empty>","confidence":"high|medium|low","reason":"short"}. '
    "Choose only from the supplied profiles; return an empty ref when none fits."
)


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

    clean_ref = str(ref or "").strip()
    _add(clean_ref)
    ref_tokens = split_connection_tokens(clean_ref)
    if ref_tokens:
        _add(" ".join(ref_tokens))

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

    return aliases[:10]


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
                candidates.append(
                    SemanticConnectionCandidate(
                        connection_kind=clean_kind,
                        connection_ref=clean_ref,
                        source="configured_candidate",
                        note="configured_candidate",
                        alias="",
                        score=0,
                    )
                )
        candidates.sort(key=lambda item: (0 if preferred and item.connection_kind == preferred else 1, item.connection_kind, item.connection_ref))
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
        _ = (force_llm, include_all_profiles, candidates)
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
                    f"- kind: {clean_kind} | ref: {clean_ref} | label: {connection_kind_label(clean_kind)} | aliases: {', '.join(aliases) or '-'}"
                )
        if not valid_pairs:
            return SemanticConnectionHint()

        preferred = str(preferred_kind or "").strip().lower()
        system_prompt = _CONNECTION_SYSTEM_PROMPT
        user_prompt = "\n".join(
            [
                f"Nutzeranfrage: {str(message or '').strip()}",
                f"Bevorzugter Typ: {preferred or '-'}",
                "",
                "Verfuegbare Connection-Profile:",
                *rows_for_prompt,
                "",
                "Use the full request and supplied profile metadata. Do not use unlisted targets.",
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
        _ = candidates
        if self._llm_client is None or not rows:
            return SemanticConnectionHint()

        prompt_lines: list[str] = []
        for ref, row in sorted(rows.items()):
            row = rows.get(ref, {})
            feed_url = self._read_row_value(row, "feed_url")
            title = self._read_row_value(row, "title")
            group_name = self._read_row_value(row, "group_name")
            aliases = self._build_rss_aliases(ref, row)
            scope = "grouped" if group_name else "single"
            prompt_lines.append(
                f"- ref: {ref} | scope: {scope} | title: {title or '-'} | group: {group_name or '-'} | url: {feed_url or '-'} | aliases: {', '.join(aliases) or '-'}"
            )

        system_prompt = _RSS_SYSTEM_PROMPT
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
