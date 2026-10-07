from __future__ import annotations

import pytest

from aria.modules.config_ui import links as config_link_readpoints


def test_config_security_path_uses_config_ui_registry_readpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_module_route_path(owner: str, path: str) -> str:
        calls.append((owner, path))
        return "/admin/security"

    monkeypatch.setattr(config_link_readpoints, "module_route_path", fake_module_route_path)

    assert config_link_readpoints.config_security_path(guardrail_ref="safe ssh/profile") == (
        "/admin/security?guardrail_ref=safe%20ssh%2Fprofile"
    )
    assert calls == [("config_ui", "/config/security")]


def test_config_security_path_fails_closed_without_config_route_owner(monkeypatch) -> None:
    monkeypatch.setattr(config_link_readpoints, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/security"):
        config_link_readpoints.config_security_path()
