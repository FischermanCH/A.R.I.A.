from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from aria.modules.config_ui.ui_audit import (
    UIAuditDecisionStore,
    build_ui_route_inventory,
)
from test_config_routes import _build_profile_config_app


def _inventory_app() -> FastAPI:
    app = FastAPI()

    @app.get("/visible", response_class=HTMLResponse)
    async def visible() -> HTMLResponse:
        return HTMLResponse("visible")

    @app.post("/visible")
    async def mutate() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api")
    async def api() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_ui_audit_discovers_manifest_owned_registered_html_get_routes() -> None:
    rows = build_ui_route_inventory(
        _inventory_app(),
        manifests={"demo": {"id": "demo", "routes": ["/visible", "/api", "/missing"]}},
        nav_nodes={
            "demo.visible": {
                "id": "demo.visible",
                "href": "/visible",
                "route_path": "/visible",
                "title_fallback": "Visible",
                "visibility": "advanced",
                "parent": "admin.overview",
            }
        },
        path_node_prefixes=(("/visible", "demo.visible"),),
    )

    assert [row.path for row in rows] == ["/visible"]
    assert rows[0].method == "GET"
    assert rows[0].owner_module == "demo"
    assert rows[0].nav_reachable is True
    assert rows[0].visibility == "advanced"
    assert rows[0].nav_parent == "admin.overview"


def test_ui_audit_store_persists_status_note_and_exports_current_routes(tmp_path: Path) -> None:
    path = tmp_path / "data" / "runtime" / "ui_audit_decisions.json"
    store = UIAuditDecisionStore(path)
    store.save("GET /visible", status="cut", note="merge into settings")

    reloaded = UIAuditDecisionStore(path)
    assert reloaded.get("GET /visible") == {"status": "cut", "note": "merge into settings"}
    payload = reloaded.export(
        build_ui_route_inventory(
            _inventory_app(),
            manifests={"demo": {"id": "demo", "routes": ["/visible"]}},
            nav_nodes={},
            path_node_prefixes=(),
        )
    )

    assert payload["routes"] == [
        {
            "method": "GET",
            "path": "/visible",
            "owner": "demo",
            "status": "cut",
            "note": "merge into settings",
            "nav_reachable": False,
            "nav_section": "unmapped",
            "nav_parent": "",
            "visibility": "unmapped",
        }
    ]
    assert json.loads(path.read_text(encoding="utf-8"))["decisions"]["GET /visible"]["status"] == "cut"


def test_ui_audit_page_persists_and_exports_registered_routes(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path)

    page = client.get("/config/admin/ui-audit")
    assert page.status_code == 200
    assert "GET /config/admin/modules" in page.text
    assert "GET /config/admin/ui-audit" in page.text
    assert page.text.count('<form method="post" action="/config/admin/ui-audit/save-all"') == 1
    assert '<div class="ui-audit-row"' in page.text
    assert "fetch(saveUrl" not in page.text
    assert "saveRow(" not in page.text
    assert 'name="route_key"' in page.text
    assert 'name="status"' in page.text
    assert 'name="note"' in page.text
    assert "Save all" in page.text

    saved = client.post(
        "/config/admin/ui-audit/save-all",
        data={
            "csrf_token": "test-csrf",
            "route_key": ["GET /config/admin/modules", "GET /config/admin/ui-audit"],
            "status": ["regroup", "keep"],
            "note": ["move beside diagnostics", "keep audit"],
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert saved.headers["location"] == "/config/admin/ui-audit?saved=1"

    exported = client.get("/config/admin/ui-audit/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    row = next(item for item in exported.json()["routes"] if item["path"] == "/config/admin/modules")
    assert row["owner"] == "config_ui"
    assert row["status"] == "regroup"
    assert row["note"] == "move beside diagnostics"
    audit_row = next(item for item in exported.json()["routes"] if item["path"] == "/config/admin/ui-audit")
    assert audit_row["status"] == "keep"
    assert audit_row["note"] == "keep audit"


def test_ui_audit_page_translates_its_title(tmp_path: Path) -> None:
    english_client = _build_profile_config_app(tmp_path / "en", lang="en")
    german_client = _build_profile_config_app(tmp_path / "de", lang="de")

    english_page = english_client.get("/config/admin/ui-audit")
    german_page = german_client.get("/config/admin/ui-audit")

    assert english_page.status_code == 200
    assert german_page.status_code == 200
    assert "UI route audit" in english_page.text
    assert "UI-Routen-Audit" in german_page.text
    assert "Save all" in english_page.text
    assert "config_ui_audit.title" not in english_page.text
    assert "config_ui_audit.title" not in german_page.text


def test_ui_audit_routes_are_admin_only(tmp_path: Path) -> None:
    client = _build_profile_config_app(tmp_path, auth_role="user")

    page = client.get("/config/admin/ui-audit", follow_redirects=False)
    exported = client.get("/config/admin/ui-audit/export")
    saved = client.post(
        "/config/admin/ui-audit/save-all",
        data={"route_key": ["GET /config/admin/modules"], "status": ["cut"], "note": ["blocked"]},
        follow_redirects=False,
    )

    assert page.status_code == 303
    assert page.headers["location"] == "/config?error=no_admin"
    assert exported.status_code == 403
    assert saved.status_code == 403
