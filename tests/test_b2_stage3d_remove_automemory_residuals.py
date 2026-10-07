from __future__ import annotations

from pathlib import Path

from aria.modules import MODULE_MANIFESTS, module_registry_diagnostics
from aria.modules.configuration_foundations.config import load_settings


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_retired_automemory_and_learning_effect_symbols_are_absent() -> None:
    production = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "aria").rglob("*.py"))

    for retired in (
        "AutoMemoryConfig",
        "ARIA_AUTO_MEMORY_ENABLED",
        "is_auto_memory_enabled",
        "legacy_learning_effect",
    ):
        assert retired not in production


def test_legacy_auto_memory_config_section_is_ignored(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
llm:
  model: fake
auto_memory:
  enabled: true
  agentic_extraction_enabled: true
  session_recall_top_k: 99
  learning_governor:
    retention_policy_version: 1
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert not hasattr(settings, "auto_memory")
    assert "auto_memory" not in settings.model_dump()


def test_memory_overview_removes_only_retired_status_projection() -> None:
    routes = _source("aria/modules/memory_admin_ui/routes.py")
    template = _source("aria/templates/_memory_drilldown_browser.html")

    assert '"title": _msg(lang, "Auto-Memory & Lernen", "Auto-memory & learning")' not in routes
    assert '"auto_memory_enabled":' not in routes
    assert "learning_effect" not in template
    assert "memory_browser" in routes
    assert "memory_graph" in routes
    assert "memory-drilldown" in template


def test_connected_status_config_and_cookie_surfaces_are_absent() -> None:
    sources = {
        relative: _source(relative)
        for relative in (
            "aria/main.py",
            "aria/modules/runtime_bootstrap/memory_helpers.py",
            "aria/modules/chat_surface/routes.py",
            "aria/modules/chat_execution_composition/routes.py",
            "aria/modules/chat_execution_composition/flow.py",
            "aria/modules/memory_admin_ui/routes.py",
            "aria/modules/recipes_ui/routes.py",
            "aria/modules/release_update/routes.py",
            "config/config.example.yaml",
        )
    }

    assert all("settings.auto_memory" not in source for source in sources.values())
    assert all("auto_memory_cookie" not in source for source in sources.values())
    assert "/api/auto-memory/status" not in sources["aria/modules/release_update/routes.py"]
    assert "auto_memory:" not in sources["config/config.example.yaml"]


def test_registry_shape_and_core_memory_owners_remain() -> None:
    diagnostics = module_registry_diagnostics()

    assert diagnostics["module_count"] == 106
    assert diagnostics["validation_issue_count"] == 0
    assert diagnostics["dependency_cycle_count"] == 0
    assert "memory" in MODULE_MANIFESTS
    assert "memory_learning_bridge" in MODULE_MANIFESTS
