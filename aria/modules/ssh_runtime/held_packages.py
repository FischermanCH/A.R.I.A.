"""Parse held-package names from SSH package-manager output."""

from __future__ import annotations

import re
from pathlib import Path

from aria.modules.platform_primitives.i18n import I18NStore


_SSH_RUNTIME_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def extract_held_packages(text: str) -> list[str]:
    content = str(text or "")
    if not content.strip():
        return []
    rows = [line.strip() for line in content.splitlines()]
    packages: list[str] = []
    seen: set[str] = set()
    collecting = False
    for line in rows:
        low = line.lower()
        held_markers = (
            str(_SSH_RUNTIME_I18N.t("en", "ssh_runtime.held_back_marker", "kept back")),
            str(_SSH_RUNTIME_I18N.t("de", "ssh_runtime.held_back_marker", "kept back")),
        )
        if any(marker and marker.lower() in low for marker in held_markers):
            collecting = True
            after_colon = line.split(":", 1)[1] if ":" in line else ""
            candidates = re.findall(r"[a-z0-9][a-z0-9+_.-]*", after_colon.lower())
            for token in candidates:
                if token in {"the", "following", "packages", "have", "been", "kept", "back"}:
                    continue
                if token not in seen:
                    seen.add(token)
                    packages.append(token)
            continue
        if collecting:
            if not line:
                collecting = False
                continue
            if ":" in line and not re.search(r"\b[a-z0-9][a-z0-9+_.-]*\b", line.lower()):
                collecting = False
                continue
            candidates = re.findall(r"[a-z0-9][a-z0-9+_.-]*", line.lower())
            if not candidates:
                collecting = False
                continue
            for token in candidates:
                if token in {"reading", "building", "dependency", "state", "information", "done"}:
                    continue
                if token not in seen:
                    seen.add(token)
                    packages.append(token)
            continue
        inline_match = re.search(r"kept back:\s*(.+)$", low)
        if not inline_match:
            continue
        for token in re.findall(r"[a-z0-9][a-z0-9+_.-]*", inline_match.group(1)):
            if token not in seen:
                seen.add(token)
                packages.append(token)
    return packages[:30]
