from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_semantic_resolver import SemanticConnectionCandidate
from aria.core.connection_semantic_resolver import connection_label_match_score
from aria.core.connection_semantic_resolver import normalize_connection_alias
from aria.core.connection_semantic_resolver import split_connection_tokens
from aria.core.rss_digest_options import build_rss_digest_options_note
from aria.core.rss_digest_options import infer_rss_digest_options
from aria.core.rss_grouping import build_rss_status_groups


RSS_GROUP_BUNDLE_PREFIX = "__rss_group_bundle__:"


@dataclass(slots=True)
class RssSingleProfileSelection:
    connection_ref: str
    semantic_candidates: list[SemanticConnectionCandidate]
    debug_line: str


def build_rss_group_bundle_note(group_name: str, refs: list[str]) -> str:
    payload = {
        "group": str(group_name or "").strip(),
        "refs": [str(item or "").strip() for item in list(refs or []) if str(item or "").strip()],
    }
    return RSS_GROUP_BUNDLE_PREFIX + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def parse_rss_group_bundle_note(notes: list[str] | tuple[str, ...] | None) -> tuple[str, list[str]] | None:
    for item in list(notes or []):
        text = str(item or "").strip()
        if not text.startswith(RSS_GROUP_BUNDLE_PREFIX):
            continue
        try:
            payload = json.loads(text[len(RSS_GROUP_BUNDLE_PREFIX) :])
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        group_name = str(payload.get("group", "") or "").strip()
        refs = [str(ref or "").strip() for ref in list(payload.get("refs", []) or []) if str(ref or "").strip()]
        if group_name and refs:
            return group_name, refs
    return None


def rss_exact_feed_ref_requested(
    query: str,
    *,
    connection_ref: str,
    requested_connection_ref: str = "",
) -> bool:
    clean_ref = str(connection_ref or "").strip().lower()
    if not clean_ref:
        return False
    clean_query = str(query or "").strip().lower()
    if clean_ref and clean_ref in clean_query:
        return True
    requested_ref = str(requested_connection_ref or "").strip().lower()
    return bool(requested_ref and requested_ref == clean_ref)


def _rss_connection_rows(settings: Any) -> dict[str, Any]:
    rows = getattr(getattr(settings, "connections", object()), "rss", {})
    return rows if isinstance(rows, dict) else {}


def rss_group_bundle_from_config_groups(settings: Any, message: str, *, selected_ref: str = "") -> tuple[str, list[str]] | None:
    grouped: dict[str, list[str]] = {}
    for ref, row in _rss_connection_rows(settings).items():
        clean_ref = str(ref or "").strip()
        if not clean_ref:
            continue
        group_name = str(row.get("group_name", "") if isinstance(row, dict) else getattr(row, "group_name", "") or "").strip()
        if group_name:
            grouped.setdefault(group_name, []).append(clean_ref)

    best: tuple[int, str, list[str]] | None = None
    clean_selected = str(selected_ref or "").strip()
    for group_name, refs in grouped.items():
        unique_refs = sorted({str(item or "").strip() for item in refs if str(item or "").strip()})
        if len(unique_refs) < 2:
            continue
        score = connection_label_match_score(message, group_name)
        if score <= 0:
            continue
        if clean_selected and clean_selected in unique_refs:
            score += 5
        candidate = (score, group_name, unique_refs)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None
    _, group_name, refs = best
    return group_name, refs


async def rss_group_bundle_for_query(settings: Any, message: str, *, selected_ref: str = "") -> tuple[str, list[str]] | None:
    config_bundle = rss_group_bundle_from_config_groups(settings, message, selected_ref=selected_ref)
    if config_bundle is not None:
        return config_bundle

    status_rows: list[dict[str, Any]] = []
    for ref, row in _rss_connection_rows(settings).items():
        clean_ref = str(ref or "").strip()
        if not clean_ref:
            continue
        if isinstance(row, dict):
            feed_url = str(row.get("feed_url", "") or "").strip()
            group_name = str(row.get("group_name", "") or "").strip()
            title = str(row.get("title", "") or "").strip()
        else:
            feed_url = str(getattr(row, "feed_url", "") or "").strip()
            group_name = str(getattr(row, "group_name", "") or "").strip()
            title = str(getattr(row, "title", "") or "").strip()
        status_rows.append(
            {
                "ref": clean_ref,
                "target": feed_url,
                "group_name": group_name,
                "title": title,
                "status": "ok",
                "message": "ok",
            }
        )
    grouped_rows = [row for row in list(await build_rss_status_groups(status_rows) or []) if isinstance(row, dict)]

    best: tuple[int, str, list[str]] | None = None
    clean_selected = str(selected_ref or "").strip()
    for row in grouped_rows:
        refs = [
            str(item.get("ref", "") or "").strip()
            for item in list(row.get("rows", []) or [])
            if isinstance(item, dict) and str(item.get("ref", "") or "").strip()
        ]
        if len(refs) < 2:
            continue
        group_name = str(row.get("name", "") or "").strip()
        score = connection_label_match_score(message, group_name)
        if score <= 0:
            continue
        if clean_selected and clean_selected in refs:
            score += 5
        candidate = (score, group_name, refs)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None
    _, group_name, refs = best
    return group_name, refs


def rss_group_name_from_alias(alias: str) -> str:
    clean = normalize_connection_alias(alias)
    tokens = set(split_connection_tokens(clean))
    if "security" in tokens:
        return "Security"
    if "apple" in tokens:
        return "Apple"
    if "heise" in tokens:
        return "Heise"
    if {"project", "personal", "blog"} & tokens:
        return "Personal"
    if {"entwicklung", "developer", "developers", "development", "dev"} & tokens:
        return "Entwicklung"
    if {"tech", "news"} <= tokens or "tech" in tokens:
        return "News & Tech"
    return ""


def rss_group_bundle_from_candidate_aliases(
    message: str,
    *,
    selected_ref: str = "",
    candidate_rows: list[dict[str, Any]] | None = None,
) -> tuple[str, list[str]] | None:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in list(candidate_rows or []):
        if not isinstance(row, dict):
            continue
        kind = normalize_connection_kind(str(row.get("connection_kind", "") or ""))
        if kind != "rss":
            continue
        alias = normalize_connection_alias(str(row.get("alias", "") or ""))
        ref = str(row.get("connection_ref", "") or "").strip()
        if alias and ref:
            buckets.setdefault(alias, []).append(row)

    best: tuple[int, str, list[str]] | None = None
    clean_selected = str(selected_ref or "").strip()
    for alias, rows in buckets.items():
        refs = [str(item.get("connection_ref", "") or "").strip() for item in rows if str(item.get("connection_ref", "") or "").strip()]
        if len(refs) < 2:
            continue
        score = connection_label_match_score(message, alias)
        if score <= 0:
            continue
        if clean_selected and clean_selected in refs:
            score += 5
        group_name = rss_group_name_from_alias(alias) or alias.title()
        candidate = (score, group_name, sorted(set(refs)))
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None
    _, group_name, refs = best
    return group_name, refs


async def rss_digest_options_note_for_query(message: str, *, llm_client: Any | None, language: str = "") -> str:
    options = await infer_rss_digest_options(message, llm_client=llm_client, language=language)
    return build_rss_digest_options_note(options)


def rss_candidates_need_semantic_refine(candidates: list[SemanticConnectionCandidate]) -> bool:
    rss_candidates = [item for item in list(candidates or []) if str(item.connection_kind or "").strip().lower() == "rss"]
    if len(rss_candidates) < 2:
        return False
    top_score = int(getattr(rss_candidates[0], "score", 0) or 0)
    second_score = int(getattr(rss_candidates[1], "score", 0) or 0)
    if top_score <= 0 or second_score <= 0:
        return False
    return top_score == second_score


class RssActionSelectionPolicy:
    def __init__(
        self,
        *,
        settings: Any,
        llm_client: Any | None,
    ) -> None:
        self._settings = settings
        self._llm_client = llm_client

    @staticmethod
    def exact_feed_ref_requested(
        query: str,
        *,
        connection_ref: str,
        requested_connection_ref: str = "",
    ) -> bool:
        return rss_exact_feed_ref_requested(
            query,
            connection_ref=connection_ref,
            requested_connection_ref=requested_connection_ref,
        )

    @staticmethod
    def select_single_profile(
        message: str,
        *,
        effective_kind: str,
        explicit_ref: str,
        requested_ref_hint: str,
        candidate_connections: dict[str, Any],
        collect_candidates: Any,
    ) -> RssSingleProfileSelection | None:
        if (
            normalize_connection_kind(effective_kind) != "rss"
            or len(candidate_connections) != 1
            or str(explicit_ref or "").strip()
            or str(requested_ref_hint or "").strip()
        ):
            return None
        only_ref = str(next(iter(candidate_connections.keys()), "") or "").strip()
        if not only_ref:
            return None
        candidates = collect_candidates(
            message,
            {"rss": candidate_connections},
            preferred_kind="rss",
        )
        return RssSingleProfileSelection(
            connection_ref=only_ref,
            semantic_candidates=list(candidates or []),
            debug_line=f"Routing Debug: single_rss_profile selected ref={only_ref}",
        )

    @staticmethod
    def candidates_need_semantic_refine(candidates: list[SemanticConnectionCandidate]) -> bool:
        return rss_candidates_need_semantic_refine(candidates)

    @staticmethod
    def build_group_bundle_note(group_name: str, refs: list[str]) -> str:
        return build_rss_group_bundle_note(group_name, refs)

    @staticmethod
    def parse_group_bundle_note(notes: list[str] | tuple[str, ...] | None) -> tuple[str, list[str]] | None:
        return parse_rss_group_bundle_note(notes)

    def group_bundle_from_config_groups(self, message: str, *, selected_ref: str = "") -> tuple[str, list[str]] | None:
        return rss_group_bundle_from_config_groups(self._settings, message, selected_ref=selected_ref)

    async def group_bundle_for_query(self, message: str, *, selected_ref: str = "") -> tuple[str, list[str]] | None:
        return await rss_group_bundle_for_query(self._settings, message, selected_ref=selected_ref)

    @staticmethod
    def group_name_from_alias(alias: str) -> str:
        return rss_group_name_from_alias(alias)

    @staticmethod
    def group_bundle_from_candidate_aliases(
        message: str,
        *,
        selected_ref: str = "",
        candidate_rows: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[str]] | None:
        return rss_group_bundle_from_candidate_aliases(
            message,
            selected_ref=selected_ref,
            candidate_rows=candidate_rows,
        )

    async def digest_options_note_for_query(self, message: str, *, language: str = "") -> str:
        return await rss_digest_options_note_for_query(
            message,
            llm_client=self._llm_client,
            language=language,
        )
