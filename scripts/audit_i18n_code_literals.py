#!/usr/bin/env python3
"""Audit German UI/output literals that still live in Python code.

Python runtime code should hold keys, structured contracts, and loaders. Visible
text belongs in ``aria/i18n/*.json``; German input lexicons and routing phrases
belong in ``aria/lexicons/*.json``. Use ``--strict`` in CI to fail when German
literals reappear in Python modules.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
ARIA_ROOT = ROOT / "aria"

GERMAN_MARKERS = (
    "ä",
    "ö",
    "ü",
    "Ä",
    "Ö",
    "Ü",
    "ß",
    "fuer",
    "für",
    "ueber",
    "über",
    "zurueck",
    "zurück",
    "fehlgeschlagen",
    "Fehler",
    "Pruefung",
    "Prüfung",
    "Bestaetigung",
    "Bestätigung",
    "Verbindung",
    "Verbindungen",
    "Rezept",
    "Rezepte",
    "Notiz",
    "Notizen",
    "Gedaechtnis",
    "Gedächtnis",
    "geloescht",
    "gelöscht",
    "ausgefuehrt",
    "ausgeführt",
    "ungueltig",
    "ungültig",
)

LOCALIZATION_CALLS = {"_msg", "localized_text", "translate", "_toolbox_label", "_toolbox_insert"}
STRICT_BLOCKED_CATEGORIES = ("raw_runtime_literal", "inline_localized", "llm_prompt", "input_lexicon")


@dataclass(frozen=True)
class AuditRow:
    rel_path: str
    line: int
    category: str
    sample: str


def iter_python_files(root: Path = ARIA_ROOT) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def enclosing_call(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.Call | None:
    cursor = node
    for _ in range(5):
        parent = parents.get(cursor)
        if parent is None:
            return None
        if isinstance(parent, ast.Call):
            return parent
        cursor = parent
    return None


def has_german_marker(value: str) -> bool:
    return any(marker in value for marker in GERMAN_MARKERS)


def looks_like_regex_or_command(value: str) -> bool:
    return any(token in value for token in ("\\b", "(?:", "(?P<", "^", "$", "\\s", "|"))


def classify(path: Path, node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> str:
    call = enclosing_call(node, parents)
    if call is not None and call_name(call.func) in LOCALIZATION_CALLS:
        return "inline_localized"
    value = str(node.value)
    if looks_like_regex_or_command(value):
        return "input_lexicon"
    if "prompt" in value.lower() or "antworte" in value.lower() or "json" in value.lower():
        return "llm_prompt"
    return "raw_runtime_literal"


def audit_python_files(files: Iterable[Path] | None = None) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for path in files or iter_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not has_german_marker(text):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        parents = parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value.strip()
            if not value or not has_german_marker(value):
                continue
            rel = path.relative_to(ROOT).as_posix()
            line = int(getattr(node, "lineno", 0) or 0)
            sample = " ".join(value.split())[:120]
            rows.append(AuditRow(rel, line, classify(path, node, parents), sample))
    return rows


def print_report(rows: Sequence[AuditRow]) -> None:
    counts: Counter[str] = Counter(row.category for row in rows)
    by_file: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_file[row.rel_path][row.category] += 1

    print("# German code literal audit")
    print()
    print("Category counts:")
    for category, count in counts.most_common():
        print(f"- {category}: {count}")
    print()
    print("Top files:")
    top_files = sorted(by_file.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:40]
    for rel, file_counts in top_files:
        summary = ", ".join(f"{key}={value}" for key, value in sorted(file_counts.items()))
        print(f"- {rel}: {sum(file_counts.values())} ({summary})")
    print()
    print("Findings, first 120:")
    for row in rows[:120]:
        print(f"- {row.rel_path}:{row.line}: {row.category}: {row.sample}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit German literals in ARIA Python runtime code.")
    parser.add_argument("--strict", action="store_true", help="Exit with status 1 when blocked categories are found.")
    parser.add_argument(
        "--blocked-category",
        action="append",
        choices=STRICT_BLOCKED_CATEGORIES,
        help="Category to block in strict mode. Can be repeated. Defaults to all categories.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = audit_python_files()
    print_report(rows)
    if not args.strict:
        return 0
    blocked = set(args.blocked_category or STRICT_BLOCKED_CATEGORIES)
    blocked_rows = [row for row in rows if row.category in blocked]
    if blocked_rows:
        print()
        print(f"Strict mode failed: {len(blocked_rows)} blocked German code literal finding(s).")
        return 1
    print()
    print("Strict mode passed: no blocked German code literal findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
