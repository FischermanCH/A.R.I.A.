"""Registry-backed links owned by the Config UI module."""

from __future__ import annotations

from urllib.parse import quote

from aria.modules import module_route_path


def config_security_path(*, guardrail_ref: str = "") -> str:
    base_path = module_route_path("config_ui", "/config/security")
    if base_path is None:
        raise RuntimeError("config_ui route is not registered: /config/security")
    clean_ref = str(guardrail_ref or "").strip()
    if not clean_ref:
        return base_path
    return f"{base_path}?guardrail_ref={quote(clean_ref, safe='')}"


__all__ = ["config_security_path"]
