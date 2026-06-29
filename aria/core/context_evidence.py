from __future__ import annotations

from functools import lru_cache
import re


def evidence_terms(query: str, *, ignored_terms: set[str] | frozenset[str] | None = None) -> list[str]:
    ignored = {str(term or "").strip().lower() for term in (ignored_terms or set()) if str(term or "").strip()}
    normalized = re.sub(r"[^\w-]+", " ", str(query or "").lower(), flags=re.UNICODE)
    terms: list[str] = []
    for raw in normalized.split():
        clean = raw.strip("-_")
        if len(clean) < 3 or clean in ignored:
            continue
        parts = [part for part in clean.split("-") if len(part) >= 3]
        candidates = [clean, *parts] if parts else [clean]
        for candidate in candidates:
            if candidate and candidate not in ignored and candidate not in terms:
                terms.append(candidate)
    terms.sort(key=lambda term: ("-" in term or any(char.isdigit() for char in term), len(term), term), reverse=True)
    return terms[:12]


@lru_cache(maxsize=1)
def common_request_terms() -> frozenset[str]:
    return frozenset(
        {
            "about",
            "all",
            "alle",
            "alles",
            "and",
            "auf",
            "aus",
            "bei",
            "bitte",
            "configured",
            "dazu",
            "deine",
            "deinen",
            "deiner",
            "der",
            "die",
            "dies",
            "diese",
            "diesem",
            "diesen",
            "dieser",
            "for",
            "f" + "uer",
            "f" + chr(252) + "r",
            "frage",
            "gibt",
            "habe",
            "haben",
            "has",
            "have",
            "hast",
            "ich",
            "information",
            "informationen",
            "info",
            "infos",
            "ist",
            "liste",
            "list",
            "meine",
            "meinen",
            "meiner",
            "mit",
            "nach",
            "of",
            "show",
            "that",
            "the",
            "thema",
            "topic",
            "ue" + "ber",
            "und",
            "unter",
            "was",
            "welche",
            "welchen",
            "welcher",
            "what",
            "which",
            "zu",
            "zum",
            "zur",
            chr(252) + "ber",
        }
    )


@lru_cache(maxsize=1)
def inventory_soft_scope_terms() -> frozenset[str]:
    return frozenset({"beobachtet", "beobachten", "beobachtung", "monitor", "monitored", "monitoring", "observed", "watch", "watched"})


def request_scope_terms(
    surface_id: str,
    mode: str = "",
    *,
    connection_kinds: tuple[tuple[str, str], ...] = (),
    include_soft_scope: bool = True,
) -> set[str]:
    clean_surface = str(surface_id or "").strip().lower()
    ignored = {clean_surface, str(mode or "").strip().lower(), *common_request_terms()}
    ignored.update({"context", "inventory", "inventar", "search", "suche", "find", "lookup", "quelle", "quellen", "source", "sources"})
    if clean_surface == "connections":
        ignored.update({"connection", "connections", "feed", "feeds", "rss", "webseite", "webseiten", "website", "websites"})
        for kind, label in connection_kinds:
            for value in (kind, label, f"{kind}s", f"{label}s"):
                clean = str(value or "").strip().lower()
                if clean:
                    ignored.add(clean)
    if clean_surface == "notes":
        ignored.update({"note", "notes", "notiz", "notizen"})
    if include_soft_scope:
        ignored.update(inventory_soft_scope_terms())
    return {term for term in ignored if term}


def normalized_evidence_text(text: str) -> str:
    return re.sub(r"[^\w-]+", " ", str(text or "").lower(), flags=re.UNICODE)


def text_matches_evidence(
    query: str,
    text: str,
    *,
    ignored_terms: set[str] | frozenset[str] | None = None,
    require_all: bool = False,
) -> bool:
    terms = evidence_terms(query, ignored_terms=ignored_terms)
    if not terms:
        return True
    haystack = normalized_evidence_text(text)
    if require_all:
        return all(term in haystack for term in terms)
    return any(term in haystack for term in terms)


def inventory_matches(query: str, text: str) -> bool:
    clean_query = " ".join(str(query or "").lower().replace('"', " ").split())
    if not clean_query:
        return True
    haystack = str(text or "").lower()
    if clean_query in haystack:
        return True
    terms = [term for term in clean_query.split() if len(term) >= 3]
    return bool(terms and any(term in haystack for term in terms))


def inventory_query_terms(query: str) -> list[str]:
    clean_query = " ".join(str(query or "").lower().replace('"', " ").replace("'", " ").split())
    return [term for term in clean_query.split() if len(term) >= 3]
