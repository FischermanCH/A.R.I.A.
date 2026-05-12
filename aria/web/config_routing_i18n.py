from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request

from aria.core.i18n import I18NStore


_CONFIG_ROUTING_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def config_routing_lang(request: Request) -> str:
    return str(getattr(request.state, "lang", "de") or "de")


def config_routing_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _CONFIG_ROUTING_I18N.t(language or "de", f"config_routing_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template
