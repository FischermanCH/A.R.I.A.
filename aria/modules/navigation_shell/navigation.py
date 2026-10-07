"""Navigation metadata and projections owned by the Navigation Shell module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aria.modules import module_nav_node_id, module_route_path


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
    route_owner: str = ""
    route_path: str = ""
    route_query: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NavGroup:
    id: str
    title_key: str
    title_fallback: str
    desc_key: str
    desc_fallback: str
    item_ids: tuple[str, ...]
    landing_item_id: str = ""


NAV_NODES: dict[str, NavNode] = {
    "settings.overview": NavNode("settings.overview", "/config", "settings", "config.overview_title", "Settings", route_owner="config_ui", route_path="/config"),
    "settings.persona": NavNode(
        "settings.persona",
        "/config/persona",
        "prompts",
        "config.persona_title",
        "Personality & style",
        parent="settings.overview",
        desc_key="config.domain_persona_desc",
        desc_fallback="Prompt style, theme, and language in one place.",
        route_owner="config_ui",
        route_path="/config/persona",
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
        route_owner="config_ui",
        route_path="/config/prompts",
        route_query=(("return_to", "/config/persona"),),
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
        route_owner="config_ui",
        route_path="/config/appearance",
        route_query=(("return_to", "/config/persona"),),
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
        route_owner="config_ui",
        route_path="/config/language",
        route_query=(("return_to", "/config/persona"),),
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
        route_owner="release_update",
        route_path="/updates",
        route_query=(("return_to", "/config"),),
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
        route_owner="connections_ui_readonly",
        route_path="/connections",
    ),
    "connections.status": NavNode(
        "connections.status",
        "/connections/status",
        "stats",
        "connections_overview.nav_status",
        "Live-Status",
        parent="connections.overview",
        route_owner="connections_ui_readonly",
        route_path="/connections/status",
    ),
    "connections.types": NavNode(
        "connections.types",
        "/connections/types",
        "settings",
        "connections_overview.section_types_title",
        "Connection types",
        parent="connections.overview",
        route_owner="connections_ui_readonly",
        route_path="/connections/types",
    ),
    "connections.templates": NavNode(
        "connections.templates",
        "/connections/templates",
        "upload",
        "connections_overview.nav_templates",
        "Templates",
        parent="connections.overview",
        route_owner="connections_ui_readonly",
        route_path="/connections/templates",
    ),
    "recipes.overview": NavNode(
        "recipes.overview",
        "/recipes",
        "skills",
        "base.nav_skills",
        "Recipes",
        parent="settings.overview",
        desc_key="config.recipes_settings_desc",
        desc_fallback="Stored workflows, templates, and learned patterns in one place.",
        route_owner="recipes_ui",
        route_path="/recipes",
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
        route_owner="recipes_ui",
        route_path="/recipes/mine",
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
        route_owner="recipes_ui",
        route_path="/recipes/start",
    ),
    "admin.intelligence": NavNode(
        "admin.intelligence",
        "/config/intelligence",
        "llm",
        "config.h1",
        "Tune intelligence",
        parent="settings.overview",
        visibility="advanced",
        desc_key="config.domain_intelligence_desc",
        desc_fallback="LLM and embedding profiles for reasoning, answers, and semantic search.",
        route_owner="config_ui",
        route_path="/config/intelligence",
    ),
    "admin.llm_profiles": NavNode(
        "admin.llm_profiles", "/config/llm", "llm", "config.hub_llm_profiles_title", "LLM profiles",
        parent="admin.intelligence", visibility="advanced",
        desc_key="config.hub_llm_profiles_desc",
        desc_fallback="Configure chat models, providers, limits, and model profiles.",
        route_owner="config_ui", route_path="/config/llm",
    ),
    "admin.embeddings": NavNode(
        "admin.embeddings", "/config/embeddings", "search", "config.hub_embeddings_title", "Embeddings",
        parent="admin.intelligence", visibility="advanced",
        desc_key="config.hub_embeddings_desc",
        desc_fallback="Configure the embedding model used for semantic retrieval.",
        route_owner="config_ui", route_path="/config/embeddings",
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
        route_owner="config_ui",
        route_path="/config/access",
    ),
    "admin.users": NavNode(
        "admin.users", "/config/users", "users", "config.hub_users_title", "Users & roles",
        parent="admin.access", visibility="advanced",
        desc_key="config.hub_users_desc",
        desc_fallback="Manage local users, roles, and account access.",
        route_owner="config_ui", route_path="/config/users",
    ),
    "admin.guardrails": NavNode(
        "admin.guardrails", "/config/security", "security", "config.hub_guardrails_title", "Guardrails",
        parent="admin.access", visibility="advanced",
        desc_key="config.hub_guardrails_desc",
        desc_fallback="Review access controls and command guardrail profiles.",
        route_owner="config_ui", route_path="/config/security",
    ),
    "admin.modules": NavNode(
        "admin.modules",
        "/config/admin/modules",
        "settings",
        "config.modules_title",
        "Module Registry",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config.modules_desc",
        desc_fallback="Read-only module ownership, status, risk, and acceptance overview.",
        route_owner="config_ui",
        route_path="/config/admin/modules",
    ),
    "admin.ui_audit": NavNode(
        "admin.ui_audit",
        "/config/admin/ui-audit",
        "search",
        "config_ui_audit.title",
        "UI route audit",
        parent="admin.overview",
        visibility="advanced",
        desc_key="config_ui_audit.subtitle",
        desc_fallback="Inventory and tag the registered user-facing UI routes.",
        route_owner="config_ui",
        route_path="/config/admin/ui-audit",
    ),
    "admin.mode": NavNode(
        "admin.mode",
        "/config/admin-mode",
        "security",
        "config.admin_mode_title",
        "Admin mode",
        visibility="advanced",
        desc_key="config.admin_mode_desc",
        desc_fallback="Control access to advanced administration surfaces.",
        route_owner="config_ui",
        route_path="/config/admin-mode",
    ),
    "admin.files": NavNode(
        "admin.files",
        "/config/files",
        "files",
        "config.files_title",
        "Files",
        visibility="advanced",
        desc_key="config.files_desc",
        desc_fallback="Inspect and edit supported local configuration files.",
        route_owner="config_ui",
        route_path="/config/files",
    ),
    "admin.error_interpreter": NavNode(
        "admin.error_interpreter",
        "/config/error-interpreter",
        "search",
        "config.error_interpreter_title",
        "Error interpreter",
        visibility="advanced",
        desc_key="config.error_interpreter_desc",
        desc_fallback="Inspect technical errors with bounded diagnostics.",
        route_owner="config_ui",
        route_path="/config/error-interpreter",
    ),
    "admin.llm_debug": NavNode(
        "admin.llm_debug",
        "/config/llm/debug",
        "llm",
        "config.llm_debug_title",
        "LLM debug",
        visibility="advanced",
        desc_key="config.llm_debug_desc",
        desc_fallback="Inspect model gateway diagnostics and recent debug data.",
        route_owner="config_ui",
        route_path="/config/llm/debug",
    ),
    "admin.native_toolcall_selftest": NavNode(
        "admin.native_toolcall_selftest",
        "/config/native-toolcall-selftest",
        "tools",
        "config.native_toolcall_selftest_title",
        "Native tool-call self-test",
        visibility="advanced",
        desc_key="config.native_toolcall_selftest_desc",
        desc_fallback="Run the explicit native provider tool-call diagnostic.",
        route_owner="native_toolcall_selftest",
        route_path="/config/native-toolcall-selftest",
    ),
    "about.licenses": NavNode(
        "about.licenses",
        "/licenses",
        "document",
        "base.nav_licenses",
        "License agreements",
        desc_key="config.licenses_desc",
        desc_fallback="Read ARIA and third-party license agreements.",
        route_owner="static_help_docs",
        route_path="/licenses",
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
        route_owner="recipes_ui",
        route_path="/recipes/system",
    ),
    "memory.overview": NavNode(
        "memory.overview",
        "/memories",
        "memories",
        "memories.nav_memory",
        "Memory",
        route_owner="memory_admin_ui",
        route_path="/memories",
    ),
    "memory.import": NavNode(
        "memory.import",
        "/memories/import",
        "upload",
        "memories.nav_import",
        "Import",
        parent="memory.overview",
        route_owner="memory_admin_ui",
        route_path="/memories/import",
    ),
    "memory.create": NavNode(
        "memory.create",
        "/memories/create",
        "plus",
        "memories.create_title",
        "Create memory",
        parent="memory.overview",
        route_owner="memory_admin_ui",
        route_path="/memories/create",
    ),
    "memory.auto": NavNode(
        "memory.auto",
        "/memories/auto-memory",
        "memories",
        "config_memory.auto_kicker",
        "Personal model",
        parent="memory.overview",
        visibility="advanced",
        desc_key="config_memory.auto_learning_subtitle",
        desc_fallback="ARIA can remember durable facts and learn stable user conventions from chat feedback.",
        route_owner="memory_admin_ui",
        route_path="/memories/auto-memory",
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
        route_owner="memory_admin_ui",
        route_path="/memories/maintenance",
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
        route_owner="ops_config_backup",
        route_path="/config/operations",
    ),
    "admin.backup": NavNode(
        "admin.backup", "/config/backup", "download", "config.hub_backup_title", "Backup",
        parent="admin.operations", visibility="advanced",
        desc_key="config.hub_backup_desc",
        desc_fallback="Export or restore ARIA configuration safely.",
        route_owner="config_backup", route_path="/config/backup",
    ),
    "admin.logs": NavNode(
        "admin.logs", "/config/logs", "document", "config.hub_logs_title", "Logs",
        parent="admin.operations", visibility="advanced",
        desc_key="config.hub_logs_desc",
        desc_fallback="Inspect retention and cleanup settings for runtime logs.",
        route_owner="ops_config_backup", route_path="/config/logs",
    ),
    "admin.activities": NavNode(
        "admin.activities",
        "/activities",
        "activities",
        "base.nav_activities",
        "Execution History",
        parent="admin.overview",
        visibility="advanced",
        desc_key="base.nav_activities_desc",
        desc_fallback="Review recipe, web, and system runs with status and duration.",
        route_owner="stats_ui",
        route_path="/activities",
    ),
}


SECTION_ITEMS: dict[str, tuple[str, ...]] = {
    "settings": (
        "settings.overview",
        "settings.persona",
        "connections.overview",
        "recipes.overview",
        "settings.updates",
    ),
    "memory": (
        "memory.overview",
        "memory.import",
        "memory.create",
        "memory.auto",
        "admin.memory.maintenance",
    ),
    "recipes": ("settings.overview", "recipes.overview", "recipes.mine", "recipes.start"),
    "persona": ("settings.overview", "settings.persona", "persona.prompts", "persona.appearance", "persona.language"),
    "connections": (
        "settings.overview",
        "connections.overview",
        "connections.status",
        "connections.types",
        "connections.templates",
    ),
}

ADMIN_SECTION_ITEMS: tuple[str, ...] = ("settings.overview",)


SECTION_NAV_LABELS: dict[str, tuple[str, str]] = {
    "settings": ("config.nav_label", "Settings navigation"),
    "memory": ("memories_overview.nav_label", "Memory Navigation"),
    "recipes": ("recipes.nav_label", "Recipes navigation"),
    "persona": ("config.persona_nav_label", "Persoenlichkeit & Stil Navigation"),
    "connections": ("connections_overview.nav_label", "Connections navigation"),
    "admin": ("config.nav_label", "Settings navigation"),
}

SECTION_ROOT_IDS: dict[str, str] = {
    "settings": "settings.overview",
    "memory": "memory.overview",
    "admin": "settings.overview",
}


CONFIG_HUB_GROUPS: tuple[NavGroup, ...] = (
    NavGroup(
        "persona", "config.hub_group_persona", "Personality & style", "config.hub_group_persona_desc",
        "Language, appearance, and personal interaction style.",
        ("settings.persona", "persona.appearance", "persona.language", "persona.prompts"),
        landing_item_id="settings.persona",
    ),
    NavGroup(
        "connections", "config.hub_group_connections", "Connections", "config.hub_group_connections_desc",
        "External systems, profiles, templates, and live status.",
        ("connections.overview", "connections.status", "connections.types", "connections.templates"),
        landing_item_id="connections.overview",
    ),
    NavGroup(
        "recipes_learning", "config.hub_group_recipes", "Recipes & learning", "config.hub_group_recipes_desc",
        "Create, review, and maintain reusable workflows.",
        ("recipes.overview", "recipes.mine", "recipes.start", "admin.recipes.system"),
        landing_item_id="recipes.overview",
    ),
    NavGroup(
        "knowledge_memory", "config.hub_group_memory", "Knowledge & memory", "config.hub_group_memory_desc",
        "Browse, add, import, and maintain remembered knowledge.",
        ("memory.overview", "memory.create", "memory.import", "memory.auto", "admin.memory.maintenance"),
        landing_item_id="memory.overview",
    ),
    NavGroup(
        "ai_models", "config.hub_group_ai", "AI & models", "config.hub_group_ai_desc",
        "Model assignments, profiles, embeddings, and intelligence settings.",
        ("admin.intelligence", "admin.llm_profiles", "admin.embeddings"),
        landing_item_id="admin.intelligence",
    ),
    NavGroup(
        "security_access", "config.hub_group_security", "Security & access", "config.hub_group_security_desc",
        "Users, roles, guardrails, and administration access.",
        ("admin.access", "admin.users", "admin.guardrails", "admin.mode"),
        landing_item_id="admin.access",
    ),
    NavGroup(
        "operations", "config.hub_group_operations", "Operations", "config.hub_group_operations_desc",
        "Logs, backups, activities, updates, and service maintenance.",
        ("admin.operations", "admin.backup", "admin.logs", "settings.updates", "admin.activities"),
        landing_item_id="admin.operations",
    ),
    NavGroup(
        "system_development", "config.hub_group_system", "System & development", "config.hub_group_system_desc",
        "Advanced diagnostics, files, modules, and developer tools.",
        ("admin.files", "admin.error_interpreter", "admin.llm_debug", "admin.native_toolcall_selftest", "admin.modules", "admin.ui_audit"),
    ),
    NavGroup(
        "about", "config.hub_group_about", "About", "config.hub_group_about_desc",
        "Version information and legal information.", ("about.licenses",),
    ),
)

ADMIN_GROUPS: tuple[NavGroup, ...] = ()

PATH_NODE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/config/llm/debug", "admin.llm_debug"),
    ("/config/llm", "admin.llm_profiles"),
    ("/config/embeddings", "admin.embeddings"),
    ("/config/users", "admin.users"),
    ("/config/security", "admin.guardrails"),
    ("/config/files", "admin.files"),
    ("/config/error-interpreter", "admin.error_interpreter"),
    ("/config/backup", "admin.backup"),
    ("/config/logs", "admin.logs"),
    ("/config/operations", "admin.operations"),
    ("/config/intelligence", "admin.intelligence"),
    ("/config/access", "admin.access"),
    ("/config/admin/modules", "admin.modules"),
    ("/config/admin/ui-audit", "admin.ui_audit"),
    ("/config/appearance", "persona.appearance"),
    ("/config/language", "persona.language"),
    ("/config/prompts", "persona.prompts"),
    ("/config/persona", "settings.persona"),
    ("/config", "settings.overview"),
    ("/updates", "settings.updates"),
    ("/connections/status", "connections.status"),
    ("/connections/types", "connections.types"),
    ("/connections/templates", "connections.templates"),
    ("/connections", "connections.overview"),
    ("/recipes/start", "recipes.start"),
    ("/recipes/templates", "recipes.start"),
    ("/recipes/system", "admin.recipes.system"),
    ("/recipes/mine", "recipes.mine"),
    ("/recipes", "recipes.overview"),
    ("/memories/create", "memory.create"),
    ("/memories/import", "memory.import"),
    ("/memories/maintenance", "admin.memory.maintenance"),
    ("/memories/auto-memory", "memory.auto"),
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
        "admin": "settings.overview",
        "intelligence": "admin.intelligence",
        "access": "admin.access",
        "operations": "admin.operations",
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
    return bool(getattr(state, "can_access_advanced_config", False)) and str(
        getattr(state, "auth_role", "") or ""
    ).strip().lower() == "admin"


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
        "href": _node_href(node),
        "icon": node.icon,
        "title_key": effective_title_key,
        "title_fallback": effective_title_fallback,
        "desc_key": node.desc_key,
        "desc_fallback": node.desc_fallback,
        "active": bool(active),
        "visible": _can_see_node(request, node),
        "parent_link": bool(parent_link),
    }


def _node_href(node: NavNode) -> str:
    owner = str(node.route_owner or "").strip()
    route_path = str(node.route_path or "").strip()
    if not owner:
        return node.href
    resolved = module_route_path(owner, route_path)
    if resolved is None:
        raise RuntimeError(f"{owner} route is not registered: {route_path}")
    if not node.route_query:
        return resolved
    return f"{resolved}?{'&'.join(f'{key}={value}' for key, value in node.route_query)}"


def resolve_nav_id(request: Any, nav_id: str = "", legacy_section: str = "", legacy_value: str = "") -> str:
    clean_nav_id = str(nav_id or "").strip()
    owned_nav_id = module_nav_node_id("navigation_shell", clean_nav_id, available_node_ids=tuple(NAV_NODES))
    if owned_nav_id:
        return owned_nav_id
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
        return "settings"
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


def config_hub_groups(request: Any) -> list[dict[str, Any]]:
    current_id = resolve_nav_id(request) or "settings.overview"
    current_ancestors = _ancestor_ids(current_id)
    groups: list[dict[str, Any]] = []
    for group in CONFIG_HUB_GROUPS:
        landing_node = NAV_NODES.get(group.landing_item_id)
        landing_href = (
            _node_href(landing_node)
            if landing_node is not None and _can_see_node(request, landing_node)
            else ""
        )
        visible_item_ids = tuple(
            item_id for item_id in group.item_ids if _can_see_node(request, NAV_NODES[item_id])
        )
        card_item_ids = tuple(item_id for item_id in visible_item_ids if item_id != group.landing_item_id)
        if not card_item_ids and group.landing_item_id in visible_item_ids:
            card_item_ids = (group.landing_item_id,)
        items = [
            _node_dict(request, NAV_NODES[item_id], active=item_id == current_id or item_id in current_ancestors)
            for item_id in card_item_ids
        ]
        if not items and not landing_href:
            continue
        groups.append(
            {
                "id": group.id,
                "title_key": group.title_key,
                "title_fallback": group.title_fallback,
                "desc_key": group.desc_key,
                "desc_fallback": group.desc_fallback,
                "landing_href": landing_href,
                "items": items,
            }
        )
    return groups
