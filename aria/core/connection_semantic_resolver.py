from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from aria.core.connection_catalog import connection_kind_label, connection_semantic_suffixes


@dataclass(slots=True)
class SemanticConnectionHint:
    connection_kind: str = ""
    connection_ref: str = ""
    source: str = ""
    note: str = ""


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
    _add(meta_title)
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

    meta_values: list[str] = []
    if meta_title:
        meta_values.append(meta_title)
    if isinstance(meta_tags, list):
        meta_values.extend(str(item) for item in meta_tags if str(item).strip())

    suffixes = connection_semantic_suffixes(kind)
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


class ConnectionSemanticResolver:
    def __init__(self, llm_client: Any | None) -> None:
        self._llm_client = llm_client

    @staticmethod
    def _split_tokens(value: str) -> list[str]:
        return split_connection_tokens(value)

    @classmethod
    def _build_rss_aliases(cls, ref: str, row: Any) -> list[str]:
        return build_connection_aliases("rss", ref, row)[:8]

    def resolve_connection(
        self,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
    ) -> SemanticConnectionHint:
        best: tuple[int, str, str, str] | None = None
        for kind, rows in (available_connection_pools or {}).items():
            if not isinstance(rows, dict):
                continue
            for ref, row in rows.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                aliases = build_connection_aliases(kind, clean_ref, row)
                best_alias = ""
                best_score = 0
                for alias in aliases:
                    score = connection_label_match_score(message, alias)
                    if score > best_score:
                        best_score = score
                        best_alias = alias
                if best_score <= 0:
                    continue
                candidate = (best_score, str(kind).strip().lower(), clean_ref, best_alias)
                if best is None or candidate > best:
                    best = candidate
        if best is None:
            return SemanticConnectionHint()
        score, kind, ref, alias = best
        if score < 40:
            return SemanticConnectionHint()
        return SemanticConnectionHint(
            connection_kind=kind,
            connection_ref=ref,
            source="semantic_alias",
            note=f"alias:{alias}",
        )

    async def resolve_connection_with_llm(
        self,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
    ) -> SemanticConnectionHint:
        if self._llm_client is None:
            return SemanticConnectionHint()

        rows_for_prompt: list[str] = []
        valid_pairs: set[tuple[str, str]] = set()
        for kind, rows in sorted((available_connection_pools or {}).items()):
            if not isinstance(rows, dict):
                continue
            for ref, row in sorted(rows.items()):
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                valid_pairs.add((str(kind).strip().lower(), clean_ref))
                aliases = build_connection_aliases(kind, clean_ref, row)[:6]
                rows_for_prompt.append(
                    f"- kind: {kind} | ref: {clean_ref} | label: {connection_kind_label(kind)} | aliases: {', '.join(aliases) or '-'}"
                )
        if len(valid_pairs) < 2:
            return SemanticConnectionHint()

        preferred = str(preferred_kind or "").strip().lower()
        system_prompt = (
            "Du waehlst das passendste Connection-Profil fuer eine Nutzeranfrage. "
            "Antworte nur als JSON im Format "
            '{"kind":"<connection-kind oder leer>","ref":"<profil-ref oder leer>","confidence":"high|medium|low","reason":"kurz"}. '
            "Waehle nur ein Paar aus der Liste. Wenn nichts passt, gib leere Werte zurueck. "
            "Nutze nur medium oder high, wenn die Zuordnung wirklich plausibel ist."
        )
        user_prompt = "\n".join(
            [
                f"Nutzeranfrage: {str(message or '').strip()}",
                f"Bevorzugter Typ: {preferred or '-'}",
                "",
                "Verfuegbare Connection-Profile:",
                *rows_for_prompt,
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

    async def resolve_rss_ref(self, message: str, available_connections: dict[str, Any]) -> SemanticConnectionHint:
        rows = {
            str(ref).strip(): row
            for ref, row in (available_connections or {}).items()
            if str(ref).strip()
        }
        if self._llm_client is None or len(rows) < 2:
            return SemanticConnectionHint()

        prompt_lines: list[str] = []
        for ref, row in sorted(rows.items()):
            feed_url = str(getattr(row, "feed_url", "") if not isinstance(row, dict) else row.get("feed_url", "")).strip()
            aliases = self._build_rss_aliases(ref, row)
            prompt_lines.append(
                f"- ref: {ref} | url: {feed_url or '-'} | aliases: {', '.join(aliases) or '-'}"
            )

        system_prompt = (
            "Du waehlst das passende RSS-Profil fuer eine Nutzeranfrage. "
            "Antworte nur als JSON im Format "
            '{"ref":"<profil-ref oder leer>","confidence":"high|medium|low","reason":"kurz"}. '
            "Waehle nur einen Ref aus der Liste. Wenn nichts passt, gib einen leeren Ref zurueck."
        )
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
