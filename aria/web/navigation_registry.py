from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NavNode:
    id: str
    href: str
    icon: str
    title_key: str
    title_fallback: str
    parent: str = ""
    visibility: str = "always"
    desc_key: str = ""
    desc_fallback: str = ""


@dataclass(frozen=True)
class NavGroup:
    id: str
    title_key: str
    title_fallback: str
    desc_key: str
    desc_fallback: str
    item_ids: tuple[str, ...]


NAV_NODES: dict[str, NavNode] = {
    "settings.overview": NavNode("settings.overview", "/config", "settings", "config.overview_title", "Settings"),
    "settings.persona": NavNode(
        "settings.persona",
        "/config/persona",
        "prompts",
        "config.persona_title",
        "Personality & style",
        parent="settings.overview",
        desc_key="config.domain_persona_desc",
        desc_fallback="Prompt style, theme, and language in one place.",
    ),
    "persona.prompts": NavNode(
        "persona.prompts",
        "/config/prompts?return_to=/config/persona",
        "prompts",
        "config.prompt_title",
        "Prompt Studio",
        parent="settings.persona",
        visibility="advanced",
        desc_key="config.prompt_desc",
        desc_fallback="Edit persona and recipe prompts directly in the browser.",
    ),
    "persona.appearance": NavNode(
        "persona.appearance",
        "/config/appearance?return_to=/config/persona",
        "appearance",
        "config.appearance_title",
        "Appearance & Theme",
        parent="settings.persona",
        desc_key="config.appearance_desc",
        desc_fallback="Choose the visual style, accent palette, and background atmosphere for your ARIA.",
    ),
    "persona.language": NavNode(
        "persona.language",
        "/config/language?return_to=/config/persona",
        "language",
        "config.language_title",
        "Language & Translation",
        parent="settings.persona",
        desc_key="config.language_desc",
        desc_fallback="Set default language and edit language files in Advanced mode.",
    ),
    "settings.updates": NavNode(
        "settings.updates",
        "/updates?return_to=/config",
        "updates",
        "base.nav_updates",
        "Updates",
        parent="settings.overview",
        desc_key="config.updates_desc",
        desc_fallback="Version, release notes, and controlled update paths in one place.",
    ),
    "connections.overview": NavNode(
        "connections.overview",
        "/connections",
        "connections",
        "config.connections_title",
        "Connections",
        parent="settings.overview",
        desc_key="config.connections_settings_desc",
        desc_fallback="Manage external systems, sources, and access in a user-friendly way.",
    ),
    "connections.status": NavNode("connections.status", "/connections/status", "stats", "connections_overview.nav_status", "Live-Status", parent="connections.overview"),
    "connections.types": NavNode("connections.types", "/connections/types", "settings", "connections_overview.section_types_title", "Connection types", parent="connections.overview"),
    "connections.templates": NavNode("connections.templates", "/connections/templates", "upload", "connections_overview.nav_templates", "Templates", parent="connections.overview"),
    "recipes.overview": NavNode(
        "recipes.overview",
        "/recipes",
        "skills",
        "base.nav_skills",
        "Recipes",
        parent="settings.overview",
        desc_key="config.recipes_settings_desc",
        desc_fallback="Stored workflows, templates, and learned patterns in one place.",
    ),
    "recipes.mine": NavNode(
        "recipes.mine",
        "/recipes/mine",
        "skills",
        "recipes.my_recipes_title",
        "My recipes",
        parent="recipes.overview",
        desc_key="recipes.mine_page_card_desc",
        desc_fallback="Only your own recipes, separate from core abilities and templates.",
    ),
    "recipes.start": NavNode(
        "recipes.start",
        "/recipes/start",
        "plus",
        "recipes.new_templates_title",
        "New / templates",
        parent="recipes.overview",
        desc_key="recipes.start_page_card_desc",
        desc_fallback="Wizard and JSON import at one starting point without overloading recipe lists.",
    ),
    "recipes.learned": NavNode(
        "recipes.learned",
        "/recipes/learned",
        "stats",
        "learned_recipes.title",
        "Learned recipes",
        parent="recipes.overview",
        desc_key="learned_recipes.page_card_desc",
        desc_fallback="Successful patterns with experience, review status, and later promotion in one place.",
    ),
    "admin.overview": NavNode(
        "admin.overview",
        "/config/admin",
        "settings",
        "base.nav_admin",
        "Admin",
        parent="settings.overview",
        visibility="advanced",
        desc_key="config.domain_admin_desc",
        desc_fallback="Technical system areas, security, and operations tools bundled.",
    ),
    "admin.intelligence": NavNode(
        "admin.intelligence",
        "/config/intelligence",
        "llm",
        "config.h1",
        "Tune intelligence",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.domain_intelligence_desc",
        desc_fallback="LLM and embedding profiles for reasoning, answers, and semantic search.",
    ),
    "admin.access": NavNode(
        "admin.access",
        "/config/access",
        "security",
        "config.access_title",
        "Access & security",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.domain_access_desc",
        desc_fallback="Users, roles, and guardrails for safe operation.",
    ),
    "admin.workbench": NavNode(
        "admin.workbench",
        "/config/workbench",
        "routing",
        "config.workbench_title",
        "Workbench (Advanced)",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.domain_workbench_desc",
        desc_fallback="Dry-runs, file tools, and advanced technical helpers.",
    ),
    "admin.recipes.system": NavNode(
        "admin.recipes.system",
        "/recipes/system",
        "settings",
        "base.nav_recipes_system",
        "System recipes",
        parent="admin.overview",
        visibility="advanced",
        desc_key="recipes.system_page_card_desc",
        desc_fallback="ARIA's built-in core abilities bundled in one place.",
    ),
    "admin.recipes.learned": NavNode(
        "admin.recipes.learned",
        "/recipes/learned/maintenance",
        "stats",
        "base.nav_recipes_learned_admin",
        "Maintain learned recipes",
        parent="admin.overview",
        visibility="advanced",
        desc_key="learned_recipes.desc_simple",
        desc_fallback="Review list for successful patterns. They become directly executable only after explicit promotion.",
    ),
    "memory.overview": NavNode("memory.overview", "/memories", "memories", "memories.nav_memory", "Memory"),
    "memory.import": NavNode("memory.import", "/memories/import", "upload", "memories.nav_import", "Import", parent="memory.overview"),
    "memory.create": NavNode("memory.create", "/memories/create", "plus", "memories.create_title", "Create memory", parent="memory.overview"),
    "admin.memory.auto": NavNode(
        "admin.memory.auto",
        "/memories/auto-memory",
        "memories",
        "config_memory.auto_kicker",
        "Auto-Memory & Lernen",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config_memory.auto_learning_subtitle",
        desc_fallback="ARIA can remember durable facts and learn stable user conventions from chat feedback.",
    ),
    "admin.memory.maintenance": NavNode(
        "admin.memory.maintenance",
        "/memories/maintenance",
        "settings",
        "base.nav_memory_maintenance",
        "Memory maintenance",
        parent="memory.overview",
        visibility="advanced",
        desc_key="memories_maintenance.subtitle",
        desc_fallback="Technical memory tools live here so the memory browser stays focused.",
    ),
    "admin.operations": NavNode(
        "admin.operations",
        "/config/operations",
        "updates",
        "config.operations_title",
        "Operations & transfer",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.domain_operations_desc",
        desc_fallback="Logs, backups, and service maintenance as one operations area.",
    ),
    "admin.activities": NavNode(
        "admin.activities",
        "/activities",
        "activities",
        "base.nav_activities",
        "Activities",
        parent="admin.overview",
        visibility="advanced",
        desc_key="base.nav_activities_desc",
        desc_fallback="View system activity and technical events.",
    ),
    "admin.group.config": NavNode(
        "admin.group.config",
        "/config/admin/config",
        "settings",
        "config.admin_group_config_title",
        "System configuration",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.admin_group_config_desc",
        desc_fallback="Models, access, and advanced technical tools.",
    ),
    "admin.group.recipes": NavNode(
        "admin.group.recipes",
        "/config/admin/recipes",
        "skills",
        "config.admin_group_recipes_title",
        "Recipes & learning",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.admin_group_recipes_desc",
        desc_fallback="Review and maintain system recipes and learned patterns.",
    ),
    "admin.group.memory": NavNode(
        "admin.group.memory",
        "/config/admin/memory",
        "memories",
        "config.admin_group_memory_title",
        "Memory",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.admin_group_memory_desc",
        desc_fallback="Automatic learning, memory maintenance, and technical memory tools.",
    ),
    "admin.group.operations": NavNode(
        "admin.group.operations",
        "/config/admin/operations",
        "updates",
        "config.admin_group_operations_title",
        "Operations",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.admin_group_operations_desc",
        desc_fallback="Service maintenance, backups, logs, and technical events.",
    ),
}


SECTION_ITEMS: dict[str, tuple[str, ...]] = {
    "settings": (
        "settings.overview",
        "settings.persona",
        "connections.overview",
        "recipes.overview",
        "settings.updates",
        "admin.overview",
    ),
    "memory": ("memory.overview", "memory.import", "memory.create", "admin.memory.maintenance"),
    "recipes": ("settings.overview", "recipes.overview", "recipes.mine", "recipes.start", "recipes.learned"),
    "persona": ("settings.overview", "settings.persona", "persona.prompts", "persona.appearance", "persona.language"),
    "connections": (
        "settings.overview",
        "connections.overview",
        "connections.status",
        "connections.types",
        "connections.templates",
    ),
}

ADMIN_SECTION_ITEMS: tuple[str, ...] = (
    "admin.overview",
    "admin.group.config",
    "admin.group.recipes",
    "admin.group.memory",
    "admin.group.operations",
)


SECTION_NAV_LABELS: dict[str, tuple[str, str]] = {
    "settings": ("config.nav_label", "Settings navigation"),
    "memory": ("memories_overview.nav_label", "Memory Navigation"),
    "recipes": ("recipes.nav_label", "Recipes navigation"),
    "persona": ("config.persona_nav_label", "Persoenlichkeit & Stil Navigation"),
    "connections": ("connections_overview.nav_label", "Connections navigation"),
    "admin": ("config.admin_overview_link", "Admin navigation"),
}

SECTION_ROOT_IDS: dict[str, str] = {
    "settings": "settings.overview",
    "memory": "memory.overview",
    "admin": "admin.overview",
}


ADMIN_GROUPS: tuple[NavGroup, ...] = (
    NavGroup(
        "config",
        "config.admin_group_config_title",
        "System configuration",
        "config.admin_group_config_desc",
        "Models, access, and advanced technical tools.",
        ("admin.intelligence", "admin.access", "admin.workbench"),
    ),
    NavGroup(
        "recipes",
        "config.admin_group_recipes_title",
        "Recipes & learning",
        "config.admin_group_recipes_desc",
        "Review and maintain system recipes and learned patterns.",
        ("admin.recipes.system", "admin.recipes.learned"),
    ),
    NavGroup(
        "memory",
        "config.admin_group_memory_title",
        "Memory",
        "config.admin_group_memory_desc",
        "Automatic learning, memory maintenance, and technical memory tools.",
        ("admin.memory.auto",),
    ),
    NavGroup(
        "operations",
        "config.admin_group_operations_title",
        "Operations",
        "config.admin_group_operations_desc",
        "Service maintenance, backups, logs, and technical events.",
        ("admin.operations", "admin.activities"),
    ),
)

PATH_NODE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/config/llm", "admin.intelligence"),
    ("/config/embeddings", "admin.intelligence"),
    ("/config/users", "admin.access"),
    ("/config/security", "admin.access"),
    ("/config/files", "admin.workbench"),
    ("/config/error-interpreter", "admin.workbench"),
    ("/config/routing", "admin.workbench"),
    ("/config/skill-routing", "admin.workbench"),
    ("/config/backup", "admin.operations"),
    ("/config/logs", "admin.operations"),
    ("/config/operations", "admin.operations"),
    ("/config/intelligence", "admin.intelligence"),
    ("/config/access", "admin.access"),
    ("/config/workbench", "admin.workbench"),
    ("/config/admin/config", "admin.group.config"),
    ("/config/admin/recipes", "admin.group.recipes"),
    ("/config/admin/memory", "admin.group.memory"),
    ("/config/admin/operations", "admin.group.operations"),
    ("/config/appearance", "persona.appearance"),
    ("/config/language", "persona.language"),
    ("/config/prompts", "persona.prompts"),
    ("/config/persona", "settings.persona"),
    ("/config/admin", "admin.overview"),
    ("/config", "settings.overview"),
    ("/updates", "settings.updates"),
    ("/connections/status", "connections.status"),
    ("/connections/types", "connections.types"),
    ("/connections/templates", "connections.templates"),
    ("/connections", "connections.overview"),
    ("/recipes/start", "recipes.start"),
    ("/recipes/templates", "recipes.start"),
    ("/recipes/system", "admin.recipes.system"),
    ("/recipes/learned/maintenance", "admin.recipes.learned"),
    ("/recipes/learned", "recipes.learned"),
    ("/recipes/mine", "recipes.mine"),
    ("/recipes", "recipes.overview"),
    ("/memories/create", "memory.create"),
    ("/memories/import", "memory.import"),
    ("/memories/maintenance", "admin.memory.maintenance"),
    ("/memories/auto-memory", "admin.memory.auto"),
    ("/memories/config", "admin.memory.maintenance"),
    ("/memories", "memory.overview"),
    ("/activities", "admin.activities"),
)


LEGACY_NAV_IDS = {
    "config": {
        "overview": "settings.overview",
        "persona": "settings.persona",
        "prompts": "persona.prompts",
        "appearance": "persona.appearance",
        "language": "persona.language",
        "updates": "settings.updates",
        "admin": "admin.overview",
        "intelligence": "admin.intelligence",
        "access": "admin.access",
        "operations": "admin.operations",
        "workbench": "admin.workbench",
    },
    "memory": {
        "memory": "memory.overview",
        "overview": "memory.overview",
        "import": "memory.import",
        "create": "memory.create",
        "maintenance": "admin.memory.maintenance",
    },
    "recipes": {
        "overview": "recipes.overview",
        "mine": "recipes.mine",
        "start": "recipes.start",
        "learned": "recipes.learned",
        "system": "admin.recipes.system",
    },
    "connections": {
        "overview": "connections.overview",
        "status": "connections.status",
        "types": "connections.types",
        "templates": "connections.templates",
    },
}


def _request_path(request: Any) -> str:
    try:
        return str(request.url.path or "/")
    except Exception:
        return "/"


def _can_see_node(request: Any, node: NavNode) -> bool:
    if node.visibility != "advanced":
        return True
    state = getattr(request, "state", None)
    return bool(getattr(state, "can_access_advanced_config", False))


def _visible_nav_id_or_same_href_fallback(request: Any, node_id: str) -> str:
    node = NAV_NODES.get(node_id)
    if not node or _can_see_node(request, node):
        return node_id
    for candidate_id, candidate in NAV_NODES.items():
        if candidate_id == node_id:
            continue
        if candidate.href == node.href and _can_see_node(request, candidate):
            return candidate_id
    return node_id


def _node_dict(
    request: Any,
    node: NavNode,
    *,
    active: bool,
    parent_link: bool = False,
    title_key: str = "",
    title_fallback: str = "",
) -> dict[str, Any]:
    effective_title_key = title_key or node.title_key
    effective_title_fallback = title_fallback or node.title_fallback
    return {
        "id": node.id,
        "href": node.href,
        "icon": node.icon,
        "title_key": effective_title_key,
        "title_fallback": effective_title_fallback,
        "desc_key": node.desc_key,
        "desc_fallback": node.desc_fallback,
        "active": bool(active),
        "visible": _can_see_node(request, node),
        "parent_link": bool(parent_link),
    }


def resolve_nav_id(request: Any, nav_id: str = "", legacy_section: str = "", legacy_value: str = "") -> str:
    clean_nav_id = str(nav_id or "").strip()
    if clean_nav_id in NAV_NODES:
        return clean_nav_id
    clean_section = str(legacy_section or "").strip()
    clean_value = str(legacy_value or "").strip()
    legacy = LEGACY_NAV_IDS.get(clean_section, {}).get(clean_value, "")
    if legacy:
        return legacy
    path = _request_path(request)
    for prefix, node_id in PATH_NODE_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return node_id
    return ""


def _ancestor_ids(node_id: str) -> set[str]:
    ancestors: set[str] = set()
    current = NAV_NODES.get(node_id)
    while current and current.parent:
        ancestors.add(current.parent)
        current = NAV_NODES.get(current.parent)
    return ancestors


def _admin_section_item_ids(current_id: str) -> tuple[str, ...]:
    return ADMIN_SECTION_ITEMS


def _admin_group_nav_id_for_current(current_id: str) -> str:
    clean_current = str(current_id or "").strip()
    if clean_current.startswith("admin.group."):
        return clean_current
    for group in ADMIN_GROUPS:
        if clean_current in group.item_ids:
            return f"admin.group.{group.id}"
    return ""


def _context_section_for(current_id: str, legacy_section: str = "") -> str:
    if current_id == "admin.memory.maintenance":
        return "memory"
    if current_id.startswith("admin."):
        return "admin"
    if current_id == "settings.persona" or current_id.startswith("persona."):
        return "settings"
    if current_id.startswith("connections."):
        return "settings"
    if current_id.startswith("recipes."):
        return "settings"
    if current_id.startswith("settings."):
        return "settings"
    if current_id.startswith("memory."):
        return "memory"
    clean_legacy = str(legacy_section or "").strip()
    if clean_legacy in SECTION_ITEMS or clean_legacy == "admin":
        return clean_legacy
    return ""


def context_nav_items(request: Any, current_nav_id: str = "", legacy_section: str = "", legacy_value: str = "") -> list[dict[str, Any]]:
    current_id = _visible_nav_id_or_same_href_fallback(
        request,
        resolve_nav_id(request, current_nav_id, legacy_section, legacy_value),
    )
    section = _context_section_for(current_id, legacy_section)
    if not section:
        return []
    return nav_section_items(request, section, current_id, "")


def context_nav_context(request: Any, current_nav_id: str = "", legacy_section: str = "", legacy_value: str = "") -> dict[str, Any]:
    current_id = _visible_nav_id_or_same_href_fallback(
        request,
        resolve_nav_id(request, current_nav_id, legacy_section, legacy_value),
    )
    section = _context_section_for(current_id, legacy_section)
    label_key, label_fallback = SECTION_NAV_LABELS.get(section, ("", "Navigation"))
    return {
        "section": section,
        "current_id": current_id,
        "aria_key": label_key,
        "aria_fallback": label_fallback,
        "items": nav_section_items(request, section, current_id, "") if section else [],
    }


def nav_section_items(request: Any, section_id: str, current_nav_id: str = "", legacy_value: str = "") -> list[dict[str, Any]]:
    section = str(section_id or "").strip()
    current_id = resolve_nav_id(request, current_nav_id, section, legacy_value)
    current_ancestors = _ancestor_ids(current_id)
    rows: list[dict[str, Any]] = []
    item_ids = _admin_section_item_ids(current_id) if section == "admin" else SECTION_ITEMS.get(section, ())
    for item_id in item_ids:
        node = NAV_NODES.get(item_id)
        if not node or not _can_see_node(request, node):
            continue
        if section == "settings" and item_id == "admin.overview" and _request_path(request) != "/config":
            continue
        parent_link = False
        if section == "admin":
            active = item_id == current_id or item_id == _admin_group_nav_id_for_current(current_id)
        else:
            active = item_id == current_id or (item_id in current_ancestors and item_id != SECTION_ROOT_IDS.get(section, ""))
        title_key = ""
        title_fallback = ""
        rows.append(
            _node_dict(
                request,
                node,
                active=active,
                parent_link=parent_link,
                title_key=title_key,
                title_fallback=title_fallback,
            )
        )
    return rows


def admin_nav_groups(request: Any, group_filter: str = "") -> list[dict[str, Any]]:
    current_id = resolve_nav_id(request)
    current_ancestors = _ancestor_ids(current_id)
    clean_filter = str(group_filter or "").strip()
    groups: list[dict[str, Any]] = []
    for group in ADMIN_GROUPS:
        if clean_filter and group.id != clean_filter:
            continue
        items: list[dict[str, Any]] = []
        for item_id in group.item_ids:
            node = NAV_NODES[item_id]
            if not _can_see_node(request, node):
                continue
            items.append(_node_dict(request, node, active=item_id == current_id or item_id in current_ancestors))
        groups.append(
            {
                "id": group.id,
                "title_key": group.title_key,
                "title_fallback": group.title_fallback,
                "desc_key": group.desc_key,
                "desc_fallback": group.desc_fallback,
                "items": items,
            }
        )
    return groups


def settings_nav_groups(request: Any) -> list[dict[str, Any]]:
    current_id = resolve_nav_id(request)
    if not current_id:
        current_id = "settings.overview"
    current_ancestors = _ancestor_ids(current_id)
    groups: list[dict[str, Any]] = []
    child_ids_by_parent: dict[str, list[str]] = {}
    for node_id, node in NAV_NODES.items():
        if node.parent:
            child_ids_by_parent.setdefault(node.parent, []).append(node_id)
    for item_id in SECTION_ITEMS["settings"]:
        if item_id == "settings.overview":
            continue
        node = NAV_NODES[item_id]
        if not _can_see_node(request, node):
            continue
        items: list[dict[str, Any]] = []
        if item_id == "admin.overview":
            child_ids = ADMIN_SECTION_ITEMS[1:]
        else:
            child_ids = tuple(child_ids_by_parent.get(item_id, ()))
        for child_id in child_ids:
            child = NAV_NODES[child_id]
            if not _can_see_node(request, child):
                continue
            active = child_id == current_id or child_id in current_ancestors
            if item_id == "admin.overview":
                active = active or child_id == _admin_group_nav_id_for_current(current_id)
            items.append(_node_dict(request, child, active=active))
        if not items:
            items.append(_node_dict(request, node, active=item_id == current_id or item_id in current_ancestors))
        groups.append(
            {
                "id": item_id,
                "title_key": node.title_key,
                "title_fallback": node.title_fallback,
                "desc_key": node.desc_key,
                "desc_fallback": node.desc_fallback,
                "items": items,
            }
        )
    return groups
