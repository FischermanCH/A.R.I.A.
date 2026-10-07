"""Registry-backed links owned by the Website UI module."""

from __future__ import annotations

from urllib.parse import quote_plus

from aria.modules import module_route_path


def websites_config_path() -> str:
    resolved = module_route_path("website_ui", "/config/connections/websites")
    if resolved is None:
        raise RuntimeError("website_ui route is not registered: /config/connections/websites")
    return resolved


def website_create_path() -> str:
    return f"{websites_config_path()}?mode=create#create-new"


def website_manage_path(website_ref: str | None) -> str:
    clean_ref = str(website_ref or "").strip()
    if not clean_ref:
        return websites_config_path()
    return f"{websites_config_path()}?website_ref={quote_plus(clean_ref)}#manage-existing"


__all__ = ["website_create_path", "website_manage_path", "websites_config_path"]
