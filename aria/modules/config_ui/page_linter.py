from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


RULE_IDS = tuple(f"R{number}" for number in range(1, 19)) + tuple(f"R{number}" for number in range(25, 33))
THEME_RULE_IDS = tuple(f"R{number}" for number in range(19, 25))

_GERMAN_STOP_WORDS = frozenset(
    {
        "alle",
        "als",
        "das",
        "der",
        "die",
        "diesem",
        "dieser",
        "diese",
        "ein",
        "eine",
        "einer",
        "für",
        "ist",
        "kein",
        "keine",
        "löschen",
        "mit",
        "nicht",
        "oder",
        "sind",
        "speichern",
        "und",
        "verbindung",
        "verbindungen",
        "wird",
        "zurück",
    }
)

_ABSTRACT_STATS_PHRASES = (
    "Mindestens eine passive Prüfung braucht Aufmerksamkeit.",
    "Passiver Status",
    "Passiver Status aus der letzten Startprüfung",
    "ARIA verarbeitet diese Seite lokal.",
    "At least one passive check needs attention.",
    "Passive status",
    "ARIA is serving this page locally.",
)


def detect_german_ui_terms(
    visible_texts: Sequence[str],
    *,
    allowed_texts: Sequence[str] = (),
) -> list[str]:
    """Return visible English-UI rows that still look like German copy.

    Callers must pass user-entered values in ``allowed_texts``.  The detector is
    deliberately text-only: it never treats profile names or content as UI
    authority and does not attempt language-dependent routing.
    """

    allowed = {re.sub(r"\s+", " ", str(value or "").strip()).casefold() for value in allowed_texts}
    findings: list[str] = []
    seen: set[str] = set()
    for raw in visible_texts:
        text = re.sub(r"\s+", " ", str(raw or "").strip())
        folded = text.casefold()
        if not text or folded in allowed:
            continue
        words = set(re.findall(r"[a-zäöüß]+", folded))
        stop_hits = words & _GERMAN_STOP_WORDS
        has_german_glyph = bool(re.search(r"[äöüß]", folded))
        # A single short article such as "die" may be a proper name. Strong
        # action nouns and two independent function words are reliable UI leaks.
        strong = bool(stop_hits & {"für", "löschen", "speichern", "verbindung", "verbindungen", "zurück"})
        if not (has_german_glyph or strong or len(stop_hits) >= 2):
            continue
        if folded not in seen:
            findings.append(text[:240])
            seen.add(folded)
    return findings


@dataclass(frozen=True)
class PageLintFinding:
    path: str
    rule: str
    message: str
    allowed: bool = False
    reason: str = ""


@dataclass(frozen=True)
class PageLintResult:
    pages: int
    rule_ids: tuple[str, ...]
    findings: tuple[PageLintFinding, ...]

    @property
    def blocking_findings(self) -> tuple[PageLintFinding, ...]:
        return tuple(row for row in self.findings if not row.allowed)

    @property
    def passed(self) -> bool:
        return not self.blocking_findings


def _truth(snapshot: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = snapshot.get(key, default)
    return bool(value)


def _rows(snapshot: Mapping[str, Any], key: str) -> list[Any]:
    value = snapshot.get(key, ())
    return list(value) if isinstance(value, (list, tuple)) else []


def _allow_map(payload: Mapping[str, Any] | None) -> dict[tuple[str, str], str]:
    rows = payload.get("entries", ()) if isinstance(payload, Mapping) else ()
    result: dict[tuple[str, str], str] = {}
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, Mapping):
            continue
        path = str(row.get("path") or "").strip()
        rule = str(row.get("rule") or "").strip().upper()
        reason = str(row.get("reason") or "").strip()
        if path and rule in RULE_IDS and reason:
            result[(path, rule)] = reason
    return result


def _page_findings(snapshot: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    path = str(snapshot.get("path") or "<unknown>")
    page_type = str(snapshot.get("page_type") or "").strip()
    title_count = int(snapshot.get("title_count") or 0)
    purposes = [str(value).strip() for value in _rows(snapshot, "purposes") if str(value).strip()]

    if page_type not in {"overview", "detail", "create", "settings", "tool"} or not _truth(
        snapshot, "inherits_page_base", bool(page_type)
    ):
        yield "R1", "missing or invalid page-type base marker"
    if title_count != 1:
        yield "R2", f"expected one page title, found {title_count}"
    if purposes and not _truth(snapshot, "purpose_directly_after_title", True):
        yield "R2", "purpose is not directly below the title"
    if len(purposes) > 1 or _truth(snapshot, "generic_or_duplicate_purpose"):
        yield "R2", "purpose is duplicated or generic"
    if path == "/" and purposes:
        yield "R3", "chat must not render a purpose/help line"
    if page_type == "overview":
        if not _truth(snapshot, "visible_inventory", True):
            yield "R4", "overview inventory is missing or collapsed"
        if int(snapshot.get("open_statistics_blocks") or 0) > 0:
            yield "R4", "overview statistics must be collapsed"
        if int(snapshot.get("statistics_blocks") or 0) > 1:
            yield "R4", "overview has more than one statistics block"
        expected_count = snapshot.get("inventory_expected_count")
        if expected_count is not None:
            expected = int(expected_count or 0)
            rendered = int(snapshot.get("inventory_rendered_count") or 0)
            if rendered != expected:
                yield "R4", f"overview renders {rendered} inventory items, expected {expected} seeded items"
    if page_type == "detail":
        if int(snapshot.get("statistics_blocks") or 0):
            yield "R5", "detail contains overview statistics"
        if _truth(snapshot, "has_create_action"):
            yield "R5", "detail contains a create action"
    for value in _rows(snapshot, "duplicate_text_blocks"):
        yield "R6", f"duplicated text block: {str(value)[:100]}"
    for value in _rows(snapshot, "summary_body_duplicates"):
        yield "R6", f"summary text repeated in section body: {str(value)[:100]}"
    for value in _rows(snapshot, "abstract_denied_terms"):
        yield "R6", f"abstract status text on owner page: {str(value)[:100]}"
    for value in _rows(snapshot, "visible_technical_ids"):
        yield "R7", f"technical identifier visible outside expert details: {str(value)[:80]}"
    for value in _rows(snapshot, "ascii_umlaut_terms"):
        yield "R8", f"ASCII umlaut transliteration in German UI: {value}"
    for value in _rows(snapshot, "english_denied_terms"):
        yield "R9", f"English UI term in German page: {value}"
    for value in _rows(snapshot, "plain_action_elements"):
        yield "R10", f"action is not a styled button/link: {str(value)[:80]}"
    for value in _rows(snapshot, "dead_internal_links"):
        yield "R10", f"dead internal link: {str(value)[:100]}"
    if _truth(snapshot, "filter_uses_primary_style"):
        yield "R11", "filter/tab uses primary-action styling"
    for value in _rows(snapshot, "filter_primary_presentations"):
        yield "R11", f"filter/tab is effectively primary-styled: {str(value)[:80]}"
    if int(snapshot.get("max_primary_actions_per_section") or 0) > 1:
        yield "R12", "section contains more than one primary action"
    for value in _rows(snapshot, "primary_actions_per_section"):
        if isinstance(value, Mapping) and int(value.get("count") or 0) > 1:
            yield "R12", (
                f"section contains {int(value.get('count') or 0)} primary-styled controls: "
                f"{str(value.get('section') or '<unnamed>')[:80]}"
            )
    for value in _rows(snapshot, "primary_actions_per_repeated_item"):
        if isinstance(value, Mapping) and int(value.get("count") or 0) > 0:
            yield "R12", (
                f"repeated item contains a primary-styled control: "
                f"{str(value.get('item') or '<unnamed>')[:80]}"
            )
    for value in _rows(snapshot, "danger_actions_without_danger_style"):
        yield "R12", f"danger action lacks danger presentation: {str(value)[:80]}"
    if _truth(snapshot, "danger_not_final"):
        yield "R12", "danger action is outside the final danger zone"
    for value in _rows(snapshot, "secret_hits"):
        yield "R13", f"seeded secret rendered: {str(value)[:40]}"
    for value in _rows(snapshot, "bad_count_labels"):
        yield "R14", f"bad count label: {str(value)[:80]}"
    for value in _rows(snapshot, "visible_snake_case"):
        yield "R15", f"raw config key visible: {value}"
    for value in _rows(snapshot, "bad_control_dimensions"):
        yield "R16", f"implausible control dimensions: {value}"
    for value in _rows(snapshot, "editable_detail_identifiers"):
        yield "R17", f"detail identifier is editable: {str(value)[:80]}"
    canonical_parent = str(snapshot.get("canonical_parent_section") or "").strip()
    rendered_parent = str(snapshot.get("rendered_parent_section") or "").strip()
    if not canonical_parent or not rendered_parent:
        yield "R18", "canonical or rendered parent section is missing"
    elif canonical_parent != rendered_parent:
        yield "R18", f"rendered parent {rendered_parent!r} does not match canonical {canonical_parent!r}"
    for value in _rows(snapshot, "german_denied_terms"):
        yield "R25", f"German UI text in English page: {str(value)[:120]}"
    for value in _rows(snapshot, "invalid_back_links"):
        yield "R26", f"invalid or non-canonical back link: {str(value)[:120]}"
    if page_type == "overview" and int(snapshot.get("overview_create_action_count") or 0) > 1:
        yield "R27", "overview contains more than one create action"
    for value in _rows(snapshot, "visible_raw_values"):
        yield "R28", f"raw timestamp, UUID, hash, or path outside technical details: {str(value)[:100]}"
    for value in _rows(snapshot, "bad_locale_values"):
        yield "R29", f"number, byte, percent, or currency value is not locale-formatted: {str(value)[:100]}"
    for value in _rows(snapshot, "form_geometry_issues"):
        yield "R30", f"form label/geometry issue: {str(value)[:120]}"
    for value in _rows(snapshot, "journal_period_issues"):
        yield "R30", f"journal period selector issue: {str(value)[:120]}"
    if path == "/" and not _truth(snapshot, "chat_composer_in_viewport", True):
        yield "R31", "chat composer is outside the visual viewport"
    if path == "/":
        for value in _rows(snapshot, "chat_mobile_layout_issues"):
            yield "R31", f"mobile chat layout issue: {str(value)[:120]}"
    if path == "/":
        expected_user_turns = int(snapshot.get("chat_user_turns_expected") or 0)
        rendered_user_turns = int(snapshot.get("chat_user_turns_rendered") or 0)
        if rendered_user_turns != expected_user_turns:
            yield "R32", (
                f"chat renders {rendered_user_turns} user bubbles for "
                f"{expected_user_turns} persisted user turns"
            )


def lint_page_snapshots(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    allowlist: Mapping[str, Any] | None = None,
) -> PageLintResult:
    allowed = _allow_map(allowlist)
    findings: list[PageLintFinding] = []
    for snapshot in snapshots:
        path = str(snapshot.get("path") or "<unknown>")
        for rule, message in _page_findings(snapshot):
            reason = allowed.get((path, rule), "") or allowed.get(("*", rule), "")
            findings.append(PageLintFinding(path, rule, message, bool(reason), reason))
    return PageLintResult(len(snapshots), RULE_IDS, tuple(findings))


def _theme_findings(snapshot: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    secondary = [row for row in _rows(snapshot, "secondary") if isinstance(row, Mapping)]
    if any(
        float(row.get("border_contrast") or 0.0) < 3.0
        or _truth(row, "filled")
        or _truth(row, "plain_text")
        for row in secondary
    ):
        yield "R19", "secondary action is filled, plain text, or lacks a 3:1 visible border"
    if any(int(value or 0) > 1 for value in _rows(snapshot, "primary_per_section")) or int(
        snapshot.get("primary_in_repeated_items") or 0
    ):
        yield "R20", "primary action count exceeds one per section or appears in a repeated item"
    danger_inline = [row for row in _rows(snapshot, "danger_inline") if isinstance(row, Mapping)]
    danger_final = [row for row in _rows(snapshot, "danger_final") if isinstance(row, Mapping)]
    if any(not _truth(row, "redish") or _truth(row, "filled") for row in danger_inline) or any(
        not _truth(row, "filled") for row in danger_final
    ):
        yield "R21", "danger action does not follow inline-outline/final-filled semantics"
    if any(_truth(row, "filled") for row in _rows(snapshot, "tabs") if isinstance(row, Mapping)):
        yield "R22", "tab or filter is rendered as a filled button"
    for value in _rows(snapshot, "contrast_failures"):
        yield "R23", f"WCAG AA contrast failure: {str(value)[:100]}"
    for value in _rows(snapshot, "geometry_mismatches"):
        yield "R24", f"role geometry differs across themes: {str(value)[:100]}"


def lint_theme_snapshots(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    allowlist: Mapping[str, Any] | None = None,
) -> PageLintResult:
    rows = allowlist.get("entries", ()) if isinstance(allowlist, Mapping) else ()
    allowed: dict[tuple[str, str], str] = {}
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, Mapping):
            continue
        target = str(row.get("path") or "").strip()
        rule = str(row.get("rule") or "").strip().upper()
        reason = str(row.get("reason") or "").strip()
        if target and rule in THEME_RULE_IDS and reason:
            allowed[(target, rule)] = reason
    findings: list[PageLintFinding] = []
    for snapshot in snapshots:
        theme = str(snapshot.get("theme") or "unknown").strip()
        path = str(snapshot.get("path") or "<unknown>")
        target = f"{theme}:{path}"
        for rule, message in _theme_findings(snapshot):
            reason = allowed.get((target, rule), "") or allowed.get(("*", rule), "")
            findings.append(PageLintFinding(target, rule, message, bool(reason), reason))
    return PageLintResult(len(snapshots), THEME_RULE_IDS, tuple(findings))


def _json_payload(result: PageLintResult) -> dict[str, Any]:
    return {
        "version": 1,
        "pages": result.pages,
        "rules": list(result.rule_ids),
        "passed": result.passed,
        "blocking_findings": len(result.blocking_findings),
        "findings": [row.__dict__ for row in result.findings],
    }


def render_markdown(result: PageLintResult) -> str:
    lines = [
        "# Page linter 0.1.0-alpha1007",
        "",
        f"- Pages: {result.pages}",
        f"- Rules: {len(result.rule_ids)} (R1–R18, R25–R32)",
        f"- Result: {'PASS' if result.passed else 'FAIL'}",
        f"- Blocking findings: {len(result.blocking_findings)}",
        f"- Reviewed allow-list findings: {len(result.findings) - len(result.blocking_findings)}",
        "",
        "## Findings",
        "",
    ]
    if not result.findings:
        lines.append("No violations.")
    else:
        for row in result.findings:
            suffix = f" — allowed: {row.reason}" if row.allowed else ""
            lines.append(f"- **{row.rule}** `{row.path}`: {row.message}{suffix}")
    return "\n".join(lines) + "\n"


def write_reports(result: PageLintResult, markdown_path: Path, json_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    json_path.write_text(
        json.dumps(_json_payload(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_theme_reports(
    result: PageLintResult,
    markdown_path: Path,
    json_path: Path,
    *,
    themes: Sequence[str],
) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Theme linter 0.1.0-alpha1007",
        "",
        f"- Rendered page/theme combinations: {result.pages}",
        f"- Themes: {len(themes)} ({', '.join(themes)})",
        "- Rules: 6 (R19–R24)",
        f"- Result: {'PASS' if result.passed else 'FAIL'}",
        f"- Blocking findings: {len(result.blocking_findings)}",
        "",
        "## Findings",
        "",
    ]
    if not result.findings:
        lines.append("No violations.")
    else:
        for row in result.findings:
            suffix = f" — allowed: {row.reason}" if row.allowed else ""
            lines.append(f"- **{row.rule}** `{row.path}`: {row.message}{suffix}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = _json_payload(result)
    payload["themes"] = list(themes)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint rendered ARIA page snapshots.")
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    snapshots_payload = json.loads(args.snapshots.read_text(encoding="utf-8"))
    snapshots = snapshots_payload.get("pages", snapshots_payload)
    if not isinstance(snapshots, list):
        raise SystemExit("snapshot payload must be a list or {'pages': [...]}")
    allowlist = json.loads(args.allowlist.read_text(encoding="utf-8"))
    result = lint_page_snapshots(snapshots, allowlist=allowlist)
    write_reports(result, args.markdown, args.json_path)
    print(
        f"page-linter: {'PASS' if result.passed else 'FAIL'} "
        f"pages={result.pages} rules={len(result.rule_ids)} findings={len(result.blocking_findings)}"
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
