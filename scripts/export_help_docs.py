#!/usr/bin/env python3
"""Export der ARIA-Hilfe für die Website (aria-agent.dev, Plugin «ARIA Hilfe»).

Liest aus einem Git-Stand (Standard: main), nicht aus dem Arbeitsverzeichnis:
  - aria/modules/static_help_docs/manifest.py  -> welche Dokumente, Gruppen, Reihenfolge, Icons
  - aria/i18n/de.json, aria/i18n/en.json        -> Titel, Kurzbeschreibungen, Gruppennamen
  - die Markdown-Dateien je Sprache             -> <pfad>.de.md / <pfad>.en.md / <pfad>.md

Ausgabe: JSON auf stdout (UTF-8). Nur Python-Standardbibliothek, ab Python 3.8.

Aufruf (im Repo-Verzeichnis):
  python3 scripts/export_help_docs.py              # Stand von main
  python3 scripts/export_help_docs.py --ref HEAD   # anderer Stand
"""

import argparse
import json
import os
import re
import subprocess
import sys
import types

MANIFEST = "aria/modules/static_help_docs/manifest.py"
I18N = "aria/i18n/{lang}.json"
LANGS = ("de", "en")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def show(repo, ref, path):
    """Dateiinhalt aus dem Git-Stand oder None, wenn es die Datei dort nicht gibt."""
    try:
        return git(repo, "show", "{}:{}".format(ref, path)).decode("utf-8")
    except subprocess.CalledProcessError:
        return None


def load_manifest(source):
    # manifest.py ist reine Daten (Dicts/Listen); ohne Import des aria-Pakets ausführen.
    mod = types.ModuleType("aria_help_manifest")
    exec(compile(source, MANIFEST, "exec"), mod.__dict__)  # noqa: S102 – Datei aus dem eigenen Repo
    return mod.MODULE_MANIFEST


def detect_lang(text):
    """Grobe Spracherkennung für Grunddateien ohne .de/.en-Endung."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in {"und", "der", "die", "das", "nicht", "ist", "mit", "für", "fuer", "wird", "eine"} for w in words)
    en = sum(w in {"and", "the", "is", "not", "with", "for", "you", "this", "that", "are", "can"} for w in words)
    return "de" if de >= en else "en"


def language_files(repo, ref, path):
    """Liefert {"de": (pfad, text), "en": (pfad, text)} – so vollständig wie vorhanden."""
    base, ext = os.path.splitext(path)
    found = {}
    for lang in LANGS:
        p = "{}.{}{}".format(base, lang, ext)
        text = show(repo, ref, p)
        if text is not None:
            found[lang] = (p, text)
    plain = show(repo, ref, path)
    if plain is not None:
        lang = detect_lang(plain)
        found.setdefault(lang, (path, plain))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", default="main", help="Git-Stand (Standard: main)")
    ap.add_argument("--repo", default=".", help="Pfad zum ARIA-Repo (Standard: aktuelles Verzeichnis)")
    args = ap.parse_args()

    commit = git(args.repo, "rev-parse", args.ref).decode().strip()
    manifest_src = show(args.repo, args.ref, MANIFEST)
    if manifest_src is None:
        sys.exit("Manifest nicht gefunden: {}:{}".format(args.ref, MANIFEST))
    manifest = load_manifest(manifest_src)

    i18n = {}
    for lang in LANGS:
        raw = show(args.repo, args.ref, I18N.format(lang=lang))
        i18n[lang] = json.loads(raw) if raw else {}

    def label(key, default, lang):
        return i18n.get(lang, {}).get(key) or default

    groups = []
    for g in manifest.get("help_doc_groups", []):
        groups.append(
            {
                "id": g["id"],
                "label": {lang: label(g.get("label_i18n", ""), g.get("label_default", g["id"]), lang) for lang in LANGS},
            }
        )

    docs = []
    for order, d in enumerate(manifest.get("help_docs", [])):
        files = language_files(args.repo, args.ref, d["path"])
        if not files:
            print("WARNUNG: keine Datei für {} ({})".format(d["id"], d["path"]), file=sys.stderr)
            continue
        docs.append(
            {
                "id": d["id"],
                "group": d.get("group", ""),
                "icon": d.get("icon", ""),
                "order": order,
                "title": {lang: label(d.get("label_i18n", ""), d.get("label_default", d["id"]), lang) for lang in LANGS},
                "summary": {lang: label(d.get("summary_i18n", ""), d.get("summary_default", ""), lang) for lang in LANGS},
                "path": {lang: files[lang][0] for lang in files},
                "markdown": {lang: files[lang][1] for lang in files},
            }
        )

    out = {
        "format": 1,
        "source": {"ref": args.ref, "commit": commit, "repo": "FischermanCH/A.R.I.A."},
        "groups": groups,
        "docs": docs,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
