from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from threading import RLock
from typing import Any, Mapping, Sequence

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from aria.modules.navigation_shell.navigation import NAV_NODES, PATH_NODE_PREFIXES
from aria.modules.registry import MODULE_MANIFESTS


UI_AUDIT_STATUSES = ("keep", "verify", "cut", "regroup")


@dataclass(frozen=True)
class UIAuditRoute:
    method: str
    path: str
    owner_module: str
    nav_reachable: bool
    nav_section: str
    nav_parent: str
    visibility: str
    nav_title: str

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


def _nav_value(node: Any, name: str, default: str = "") -> str:
    if isinstance(node, Mapping):
        return str(node.get(name, default) or default)
    return str(getattr(node, name, default) or default)


def _nav_section(node_id: str, nodes: Mapping[str, Any]) -> str:
    current_id = str(node_id or "").strip()
    seen: set[str] = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        node = nodes.get(current_id)
        if node is None:
            break
        parent = _nav_value(node, "parent")
        if not parent:
            break
        current_id = parent
    return current_id.split(".", 1)[0] if current_id else "unmapped"


def _nav_metadata(
    path: str,
    *,
    nav_nodes: Mapping[str, Any],
    path_node_prefixes: Sequence[tuple[str, str]],
) -> tuple[bool, str, str, str, str]:
    exact_id = ""
    for node_id, node in nav_nodes.items():
        route_path = _nav_value(node, "route_path")
        href_path = _nav_value(node, "href").split("?", 1)[0]
        if path == route_path or path == href_path:
            exact_id = str(node_id)
            break

    matched_id = exact_id
    if not matched_id:
        for prefix, node_id in path_node_prefixes:
            if path == prefix or path.startswith(f"{prefix}/"):
                matched_id = str(node_id)
                break

    node = nav_nodes.get(matched_id)
    if node is None:
        return False, "unmapped", "", "unmapped", ""
    return (
        bool(exact_id),
        _nav_section(matched_id, nav_nodes),
        _nav_value(node, "parent"),
        _nav_value(node, "visibility", "always"),
        _nav_value(node, "title_fallback", matched_id),
    )


def _registered_html_get_paths(app: FastAPI) -> set[str]:
    paths: set[str] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or "GET" not in route.methods:
            continue
        response_class = route.response_class
        try:
            is_html = issubclass(response_class, HTMLResponse)
        except TypeError:
            is_html = False
        if is_html and "{" not in route.path:
            paths.add(str(route.path))
    return paths


def build_ui_route_inventory(
    app: FastAPI,
    *,
    manifests: Mapping[str, Mapping[str, Any]] = MODULE_MANIFESTS,
    nav_nodes: Mapping[str, Any] = NAV_NODES,
    path_node_prefixes: Sequence[tuple[str, str]] = PATH_NODE_PREFIXES,
) -> list[UIAuditRoute]:
    html_get_paths = _registered_html_get_paths(app)
    owners: dict[str, str] = {}
    for module_id, manifest in manifests.items():
        owner = str(manifest.get("id") or module_id).strip()
        for route_path in manifest.get("routes", ()):
            path = str(route_path or "").strip()
            if path in html_get_paths:
                owners.setdefault(path, owner)

    rows: list[UIAuditRoute] = []
    for path, owner in owners.items():
        reachable, section, parent, visibility, title = _nav_metadata(
            path,
            nav_nodes=nav_nodes,
            path_node_prefixes=path_node_prefixes,
        )
        rows.append(
            UIAuditRoute(
                method="GET",
                path=path,
                owner_module=owner,
                nav_reachable=reachable,
                nav_section=section,
                nav_parent=parent,
                visibility=visibility,
                nav_title=title,
            )
        )
    return sorted(rows, key=lambda row: (row.nav_section, row.path, row.owner_module))


class UIAuditDecisionStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def _read(self) -> dict[str, dict[str, str]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        decisions = payload.get("decisions", {}) if isinstance(payload, Mapping) else {}
        if not isinstance(decisions, Mapping):
            return {}
        return {
            str(key): {
                "status": str(value.get("status") or "verify"),
                "note": str(value.get("note") or ""),
            }
            for key, value in decisions.items()
            if isinstance(value, Mapping)
        }

    def get(self, route_key: str) -> dict[str, str]:
        with self._lock:
            row = self._read().get(str(route_key), {})
        status = str(row.get("status") or "verify")
        return {"status": status if status in UI_AUDIT_STATUSES else "verify", "note": str(row.get("note") or "")}

    def save(self, route_key: str, *, status: str, note: str) -> None:
        clean_key = str(route_key or "").strip()
        clean_status = str(status or "").strip().lower()
        if not clean_key or clean_status not in UI_AUDIT_STATUSES:
            raise ValueError("ui_audit_decision_invalid")
        clean_note = str(note or "").strip()[:1000]
        with self._lock:
            decisions = self._read()
            decisions[clean_key] = {"status": clean_status, "note": clean_note}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary.write_text(
                json.dumps({"version": 1, "decisions": decisions}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)

    def export(self, routes: Sequence[UIAuditRoute]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for route in routes:
            decision = self.get(route.key)
            rows.append(
                {
                    "method": route.method,
                    "path": route.path,
                    "owner": route.owner_module,
                    "status": decision["status"],
                    "note": decision["note"],
                    "nav_reachable": route.nav_reachable,
                    "nav_section": route.nav_section,
                    "nav_parent": route.nav_parent,
                    "visibility": route.visibility,
                }
            )
        return {"version": 1, "routes": rows}


def audit_template_rows(routes: Sequence[UIAuditRoute], store: UIAuditDecisionStore) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in routes:
        row = asdict(route)
        row.update(store.get(route.key))
        row["key"] = route.key
        rows.append(row)
    return rows
