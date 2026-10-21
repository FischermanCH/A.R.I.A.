#!/usr/bin/env python3
"""Export der Feature-Seite für die Website (aria-agent.dev, Plugin «ARIA Features»).

Liest aus einem Git-Stand (Standard: main), nicht aus dem Arbeitsverzeichnis:
  - docs/website/features.json                          -> Texte (de/en), Abschnitte, Reihenfolge, Theme-Liste
  - docs/assets/screenshots/features/<lang>/<id>.webp   -> Bild pro Feature und Sprache
  - docs/assets/screenshots/themes/<lang>/<theme>.webp  -> Bild pro Theme und Sprache (Galerie)
  - aria/i18n/de.json, aria/i18n/en.json                -> Theme-Namen (config_appearance.theme_<id>)

Fehlt ein Bild, wird das Feature ohne Bild exportiert (Warnung auf stderr).
Ausgabe: JSON auf stdout (UTF-8), Bilder als Base64 mit SHA-256.
Nur Python-Standardbibliothek, ab Python 3.8.

Aufruf (im Repo-Verzeichnis):
  python3 scripts/export_features.py              # Stand von main
  python3 scripts/export_features.py --ref HEAD   # anderer Stand
"""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys

CONTENT = "docs/website/features.json"
SHOTS = "docs/assets/screenshots"
I18N = "aria/i18n/{lang}.json"
LANGS = ("de", "en")
MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MAX_IMAGE = 2 * 1024 * 1024
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def show(repo, ref, path):
    """Rohinhalt (bytes) aus dem Git-Stand oder None."""
    try:
        return git(repo, "show", "{}:{}".format(ref, path))
    except subprocess.CalledProcessError:
        return None


def warn(msg):
    print("WARNUNG: " + msg, file=sys.stderr)


def localized(value, what):
    """{"de": "...", "en": "..."} oder ein einzelner String (gilt dann für beide)."""
    if isinstance(value, str):
        return {lang: value for lang in LANGS}
    if not isinstance(value, dict):
        sys.exit("{}: Text fehlt oder hat ein falsches Format".format(what))
    return {lang: str(value[lang]) for lang in LANGS if value.get(lang)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", default="main", help="Git-Stand (Standard: main)")
    ap.add_argument("--repo", default=".", help="Pfad zum ARIA-Repo (Standard: aktuelles Verzeichnis)")
    args = ap.parse_args()

    commit = git(args.repo, "rev-parse", args.ref).decode().strip()
    raw = show(args.repo, args.ref, CONTENT)
    if raw is None:
        sys.exit("Nicht gefunden: {}:{}".format(args.ref, CONTENT))
    try:
        content = json.loads(raw.decode("utf-8"))
    except ValueError as e:
        sys.exit("{} ist kein gültiges JSON: {}".format(CONTENT, e))

    existing = set(git(args.repo, "ls-tree", "-r", "--name-only", args.ref, "--", SHOTS).decode().splitlines())

    def image(kind, ident, lang):
        for ext, mime in MIME.items():
            path = "{}/{}/{}/{}{}".format(SHOTS, kind, lang, ident, ext)
            if path not in existing:
                continue
            data = show(args.repo, args.ref, path)
            if data is None:
                continue
            if len(data) > MAX_IMAGE:
                sys.exit("Bild grösser als 2 MB: " + path)
            return {
                "path": path,
                "mime": mime,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "data": base64.b64encode(data).decode("ascii"),
            }
        return None

    def images(kind, ident):
        out = {}
        for lang in LANGS:
            img = image(kind, ident, lang)
            if img:
                out[lang] = img
        if not out:
            warn("kein Bild für {} «{}»".format(kind, ident))
        return out

    i18n = {}
    for lang in LANGS:
        b = show(args.repo, args.ref, I18N.format(lang=lang))
        i18n[lang] = json.loads(b.decode("utf-8")) if b else {}

    sections = []
    section_ids = set()
    for s in content.get("sections", []):
        if not ID_RE.match(str(s.get("id", ""))):
            sys.exit("Abschnitt mit ungültiger ID: {!r}".format(s.get("id")))
        section_ids.add(s["id"])
        sections.append({"id": s["id"], "title": localized(s.get("title"), "Abschnitt " + s["id"])})

    features = []
    seen = set()
    for order, f in enumerate(content.get("features", [])):
        fid = str(f.get("id", ""))
        if not ID_RE.match(fid) or fid in seen:
            sys.exit("Feature mit ungültiger oder doppelter ID: {!r}".format(fid))
        seen.add(fid)
        if f.get("hidden"):
            continue
        sec = f.get("section", "")
        if sec and sec not in section_ids:
            sys.exit("Feature «{}»: unbekannter Abschnitt «{}»".format(fid, sec))
        features.append(
            {
                "id": fid,
                "section": sec,
                "order": order,
                "title": localized(f.get("title"), "Feature " + fid + " (title)"),
                "text": localized(f.get("text"), "Feature " + fid + " (text)"),
                "image": images("features", fid),
            }
        )

    gallery = None
    g = content.get("gallery")
    if g:
        themes = []
        for t in g.get("themes", []):
            tid = str(t)
            if not ID_RE.match(tid):
                sys.exit("Theme mit ungültiger ID: {!r}".format(tid))
            key = "config_appearance.theme_" + tid.replace("-", "_")
            themes.append(
                {
                    "id": tid,
                    "label": {
                        lang: i18n[lang].get(key) or next((i18n[o].get(key) for o in LANGS if i18n[o].get(key)), tid)
                        for lang in LANGS
                    },
                    "image": images("themes", tid),
                }
            )
        gallery = {
            "title": localized(g.get("title", ""), "Galerie-Titel") if g.get("title") else {},
            "text": localized(g.get("text", ""), "Galerie-Text") if g.get("text") else {},
            "themes": themes,
        }

    out = {
        "format": 1,
        "source": {"ref": args.ref, "commit": commit, "repo": "FischermanCH/A.R.I.A."},
        "intro": localized(content["intro"], "intro") if content.get("intro") else {},
        "sections": sections,
        "features": features,
        "gallery": gallery,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
