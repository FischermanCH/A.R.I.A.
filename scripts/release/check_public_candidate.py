#!/usr/bin/env python3
"""Fail closed on private release content, missing screenshots, and OCR hits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
TEXT_PATTERNS = (
    re.compile(r"\b172\.31\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b[a-z0-9.-]+\.lan\b", re.I),
    re.compile(r"\b[a-z0-9.-]+\.black(?:\.[a-z0-9.-]+)?\b", re.I),
    re.compile(r"/(?:home|Users)/(?!user\b|aria\b|app\b|runner\b|tmp\b|opt\b|var\b)[^/\s'\"`]+"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[opsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile("-" * 5 + r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY" + "-" * 5),
)


def _candidate_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    return [
        ROOT / raw.decode("utf-8", "surrogateescape")
        for raw in result.stdout.split(b"\0") if raw
    ]


def _scan_text(path: Path, text: str) -> list[str]:
    # Test fixtures and scanners deliberately contain generic hostile samples;
    # the shipped product/docs/demo content has no such exemption.
    relative = path.relative_to(ROOT)
    scanner_sources = {
        Path(__file__).relative_to(ROOT),
        Path("scripts/demo/check_public_safety.py"),
        Path("website/scripts/check_content.py"),
    }
    if relative.parts[0] == "tests" or relative in scanner_sources:
        return []
    return [pattern.pattern for pattern in TEXT_PATTERNS if pattern.search(text)]


def _ocr(path: Path, image: str) -> str:
    if shutil.which("tesseract"):
        command = ["tesseract", str(path), "stdout", "-l", "eng+deu"]
    else:
        relative = path.relative_to(ROOT).as_posix()
        command = [
            "docker", "run", "--rm", "-v", f"{ROOT}:/scan:ro",
            "--entrypoint", "tesseract", image,
            f"/scan/{relative}", "stdout", "-l", "eng+deu",
        ]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument(
        "--ocr-image", default="jitesoft/tesseract-ocr:latest",
        help="Development-only OCR image used when no local tesseract exists.",
    )
    args = parser.parse_args()
    offenders: list[str] = []
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    if any(path == ".codex" or path.startswith(".codex/") for path in tracked):
        offenders.append("tracked:.codex")
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for finding in _scan_text(path, text):
            offenders.append(f"{path.relative_to(ROOT)}:{finding}")

    searx_roots = [ROOT / "dist", ROOT / "docker", ROOT / "aria-setup"]
    for root in searx_roots:
        paths = root.rglob("*") if root.is_dir() else (root,)
        for path in paths:
            if path.is_file():
                try:
                    if re.search(r"searxng|searx", path.read_text(encoding="utf-8"), re.I):
                        offenders.append(f"searx:{path.relative_to(ROOT)}")
                except UnicodeDecodeError:
                    pass

    manifest_path = ROOT / "docs/assets/screenshots/manifest.json"
    if not manifest_path.is_file():
        offenders.append("screenshots:manifest_missing")
        images: list[Path] = []
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        images = sorted((ROOT / "docs/assets/screenshots").glob("??/*.webp"))
        if len(images) != 40 or len(manifest.get("screenshots", [])) != 40:
            offenders.append(f"screenshots:count={len(images)}")
        for path in images:
            if path.stat().st_size > 400_000:
                offenders.append(f"screenshots:size:{path.relative_to(ROOT)}")
            if args.ocr:
                for finding in _scan_text(path, _ocr(path, args.ocr_image)):
                    offenders.append(f"ocr:{path.relative_to(ROOT)}:{finding}")
    if offenders:
        raise SystemExit("public_candidate_check=failed\n" + "\n".join(offenders))
    print(f"public_candidate_check=passed files={len(_candidate_paths())} screenshots={len(images)} ocr={'yes' if args.ocr else 'no'}")


if __name__ == "__main__":
    main()
