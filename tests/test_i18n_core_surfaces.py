from __future__ import annotations

import json
import re
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "aria" / "templates"
I18N_ROOT = Path(__file__).resolve().parents[1] / "aria" / "i18n"
KEY_PATTERN = re.compile(r"tr\(request,\s*'([^']+)'")
CORE_TEMPLATES = [
    "base.html",
    "config.html",
    "stats.html",
]


def _template_keys(name: str) -> set[str]:
    text = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
    return {match.group(1) for match in KEY_PATTERN.finditer(text)}


def test_core_surface_i18n_keys_exist_in_de_and_en() -> None:
    de = json.loads((I18N_ROOT / "de.json").read_text(encoding="utf-8"))
    en = json.loads((I18N_ROOT / "en.json").read_text(encoding="utf-8"))

    missing: list[str] = []
    for template in CORE_TEMPLATES:
        for key in sorted(_template_keys(template)):
            if key not in de:
                missing.append(f"de:{template}:{key}")
            if key not in en:
                missing.append(f"en:{template}:{key}")

    assert not missing, "Missing i18n keys:\n" + "\n".join(missing)
