from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.action_pending_chat_boundary.flows as canonical_pending_flows
import aria.modules.chat_admin_composition.actions as canonical_admin_actions
import aria.modules.chat_admin_composition.flows as canonical_admin_flows
import aria.modules.chat_execution_composition.flow as canonical_execution_flow
import aria.modules.chat_execution_composition.route_helpers as canonical_route_helpers
import aria.modules.chat_execution_composition.routes as canonical_execution_routes
import aria.modules.notes.chat_flows as canonical_notes_flows
import aria.modules.website_runtime.chat_flows as canonical_websites_flows
from aria.modules.registry import MODULE_MANIFESTS


MODULE_PAIRS = (
    ("aria.modules.chat_admin_composition.actions", canonical_admin_actions),
    ("aria.modules.chat_admin_composition.flows", canonical_admin_flows),
    ("aria.modules.action_pending_chat_boundary.flows", canonical_pending_flows),
    ("aria.modules.notes.chat_flows", canonical_notes_flows),
    ("aria.modules.website_runtime.chat_flows", canonical_websites_flows),
    ("aria.modules.chat_execution_composition.route_helpers", canonical_route_helpers),
    ("aria.modules.chat_execution_composition.flow", canonical_execution_flow),
    ("aria.modules.chat_execution_composition.routes", canonical_execution_routes),
)


def test_legacy_chat_execution_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_moved_chat_implementations_keep_repository_contract_and_i18n_roots() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    aria_root = repository_root / "aria"

    assert canonical_pending_flows.BASE_DIR == repository_root
    assert canonical_admin_flows._CHAT_ADMIN_I18N.base_dir == aria_root / "i18n"
    assert canonical_notes_flows._NOTES_COMMAND_CONTRACT_PATH == aria_root / "contracts" / "notes_commands.json"
    assert canonical_notes_flows._I18N.base_dir == aria_root / "i18n"
    assert canonical_execution_flow._CHAT_EXECUTION_I18N.base_dir == aria_root / "i18n"
    assert canonical_execution_routes._CHAT_EXECUTION_ROUTES_I18N.base_dir == aria_root / "i18n"


def test_product_code_imports_canonical_chat_execution_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_main_and_template_use_canonical_chat_execution_owner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    main_source = (repository_root / "aria" / "main.py").read_text(encoding="utf-8")
    routes_source = (
        repository_root / "aria" / "modules" / "chat_execution_composition" / "routes.py"
    ).read_text(encoding="utf-8")
    template_source = (repository_root / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "from aria.modules.chat_execution_composition.flow import ChatExecutionDeps" in main_source
    assert "from aria.modules.chat_execution_composition.routes import ChatExecutionRouteDeps" in main_source
    assert "from aria.modules.chat_execution_composition.route_helpers import (" in routes_source
    assert "from aria.modules.chat_execution_composition.route_helpers import" not in main_source
    assert "module_route_path('chat_execution_composition', '/chat')" in template_source
    assert "module_route_path('chat_execution_composition', '/chat/progress')" in template_source
    assert "module_route_path('chat_execution_composition', '/chat/history/clear')" in template_source


def test_chat_composition_dependency_direction_is_acyclic_and_explicit() -> None:
    admin_dependencies = set(MODULE_MANIFESTS["chat_admin_composition"]["depends_on"])
    pending_dependencies = set(MODULE_MANIFESTS["action_pending_chat_boundary"]["depends_on"])
    execution_dependencies = set(MODULE_MANIFESTS["chat_execution_composition"]["depends_on"])
    pipeline_pending_dependencies = set(MODULE_MANIFESTS["pipeline_pending_action_contracts"]["depends_on"])

    assert "chat_admin_composition" in pending_dependencies
    assert "pipeline_pending_action_contracts" in pending_dependencies
    assert "action_pending_chat_boundary" not in pipeline_pending_dependencies
    assert {"chat_admin_composition", "action_pending_chat_boundary"}.issubset(execution_dependencies)
    assert "chat_execution_composition" not in admin_dependencies
    assert "chat_execution_composition" not in pending_dependencies
