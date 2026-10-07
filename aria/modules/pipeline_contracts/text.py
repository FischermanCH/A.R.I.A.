from __future__ import annotations

from pathlib import Path

from aria.modules.platform_primitives.i18n import I18NStore


_PIPELINE_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def pipeline_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _PIPELINE_I18N.t(language or "de", f"pipeline.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template
