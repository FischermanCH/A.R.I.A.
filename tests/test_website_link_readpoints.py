from __future__ import annotations

import pytest

import aria.modules.website_runtime.runtime as website_runtime
from aria.modules.website_ui import links as website_link_readpoints


def test_website_paths_use_website_ui_registry_readpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_module_route_path(owner: str, path: str) -> str:
        calls.append((owner, path))
        return "/admin/websites"

    monkeypatch.setattr(website_link_readpoints, "module_route_path", fake_module_route_path)

    assert website_link_readpoints.websites_config_path() == "/admin/websites"
    assert website_link_readpoints.website_create_path() == "/admin/websites?mode=create#create-new"
    assert website_link_readpoints.website_manage_path("docs/site") == "/admin/websites?website_ref=docs%2Fsite#manage-existing"
    assert calls == [
        ("website_ui", "/config/connections/websites"),
        ("website_ui", "/config/connections/websites"),
        ("website_ui", "/config/connections/websites"),
    ]


def test_website_paths_fail_closed_without_website_route_owner(monkeypatch) -> None:
    monkeypatch.setattr(website_link_readpoints, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="website_ui route is not registered: /config/connections/websites"):
        website_link_readpoints.websites_config_path()


def test_website_runtime_empty_and_manage_links_use_readpoint_helpers(monkeypatch) -> None:
    monkeypatch.setattr(website_runtime, "website_create_path", lambda: "/admin/websites?mode=create#create-new")
    monkeypatch.setattr(website_runtime, "website_manage_path", lambda ref: f"/admin/websites?website_ref={ref}#manage-existing")

    empty = website_runtime.build_website_list_text({}, language="de")
    group_empty = website_runtime.build_website_list_text({}, group_name="Docs", language="de")
    listing = website_runtime.build_website_list_text(
        {"aria-docs": {"title": "ARIA Docs", "url": "https://example.org", "group_name": "Docs"}},
        language="de",
    )
    read = website_runtime.build_website_read_text(
        "aria-docs",
        {"title": "ARIA Docs", "url": "https://example.org", "group_name": "Docs"},
        language="de",
    )

    assert "`/admin/websites?mode=create#create-new`" in empty
    assert "`/admin/websites?mode=create#create-new`" in group_empty
    assert "`/admin/websites?website_ref=aria-docs#manage-existing`" in listing
    assert "`/admin/websites?website_ref=aria-docs#manage-existing`" in read
    assert "/config/connections/websites" not in "\n".join([empty, group_empty, listing, read])
