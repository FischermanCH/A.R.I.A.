from __future__ import annotations

from pathlib import Path

from aria.modules import MODULE_MANIFESTS
from aria.modules.read_model import (
    module_asset_path,
    module_catalog_entries,
    module_nav_node_id,
    module_prompt_path,
    module_public_path_prefix,
    module_registry_diagnostics,
    module_route_path,
    module_route_prefix_path,
    module_static_asset_path,
    module_static_asset_prefix_path,
    module_status_rows,
    module_template_name,
)


def test_module_status_rows_returns_stable_sorted_read_model() -> None:
    rows = module_status_rows()

    assert rows
    assert [row["id"] for row in rows] == sorted(row["id"] for row in rows)
    assert {row["id"] for row in rows} == set(MODULE_MANIFESTS)


def test_module_status_rows_keeps_safety_flags_false_for_current_registry() -> None:
    rows = module_status_rows()

    assert all(row["build_allowed"] is False for row in rows)
    assert all(row["runtime_access_allowed"] is False for row in rows)
    assert all(row["acceptance"] for row in rows)
    assert sum(len(row["depends_on"]) for row in rows) == 416
    assert sum(len(row["external_dependencies"]) for row in rows) == 62
    assert sum(bool(row["dependency_cycle"]) for row in rows) == 0


def test_module_status_rows_can_project_explicit_manifest_mapping() -> None:
    rows = module_status_rows(
        {
            "zeta": {
                "id": "zeta",
                "name": "Zeta",
                "status": "metadata_only",
                "lifecycle": "contract_only",
                "risk": "low",
                "parent": "demo",
                "build_allowed": False,
                "runtime_access_allowed": False,
                "acceptance": ".codex/aria_acceptance/demo.json",
                "extra": "not exposed",
            }
        }
    )

    assert rows == (
        {
            "id": "zeta",
            "name": "Zeta",
            "status": "metadata_only",
            "lifecycle": "contract_only",
            "risk": "low",
            "parent": "demo",
            "build_allowed": False,
            "runtime_access_allowed": False,
            "acceptance": ".codex/aria_acceptance/demo.json",
            "depends_on": (),
            "external_boundaries": (),
            "external_dependencies": (),
            "external_boundary_categories": (),
            "external_boundary_dispositions": (),
            "python": (),
            "integration_points": (),
            "used_by": (),
            "dependency_cycle": (),
        },
    )


def test_module_registry_diagnostics_reports_passive_dependency_summary() -> None:
    diagnostics = module_registry_diagnostics()

    assert diagnostics == {
        "module_count": 106,
        "validation_issue_count": 0,
        "internal_dependency_count": 416,
        "external_dependency_count": 62,
        "external_boundary_category_counts": {
            "data_boundary": 9,
            "kernel_platform": 21,
            "library_service": 24,
            "runtime_callback": 8,
        },
        "external_boundary_disposition_counts": {"durable": 62},
        "external_boundary_unclassified_count": 0,
        "python_file_claim_count": 264,
        "integration_point_count": 66,
        "duplicate_python_owner_count": 0,
        "invalid_python_claim_count": 0,
        "invalid_integration_point_count": 0,
        "dependency_cycle_count": 0,
        "dependency_cycle_module_count": 0,
        "dependency_cycles": (),
        "legacy_alias_count": 2,
        "legacy_alias_durable_count": 2,
        "legacy_alias_migration_candidate_count": 0,
        "legacy_alias_canonical_target_count": 2,
        "legacy_manifest_reference_count": 0,
        "legacy_alias_removal_ready": True,
    }


def test_module_registry_diagnostics_respects_explicit_empty_registry() -> None:
    assert module_status_rows({}) == ()
    assert module_registry_diagnostics({}) == {
        "module_count": 0,
        "validation_issue_count": 0,
        "internal_dependency_count": 0,
        "external_dependency_count": 0,
        "external_boundary_category_counts": {},
        "external_boundary_disposition_counts": {},
        "external_boundary_unclassified_count": 0,
        "python_file_claim_count": 0,
        "integration_point_count": 0,
        "duplicate_python_owner_count": 0,
        "invalid_python_claim_count": 0,
        "invalid_integration_point_count": 0,
        "dependency_cycle_count": 0,
        "dependency_cycle_module_count": 0,
        "dependency_cycles": (),
        "legacy_alias_count": 2,
        "legacy_alias_durable_count": 2,
        "legacy_alias_migration_candidate_count": 0,
        "legacy_alias_canonical_target_count": 2,
        "legacy_manifest_reference_count": 0,
        "legacy_alias_removal_ready": True,
    }


def test_module_static_asset_path_resolves_registered_release_update_asset() -> None:
    path = module_static_asset_path("release_update", "update-reconnect-sw.js", Path("/workspace"))

    assert path == Path("/workspace/aria/static/update-reconnect-sw.js")


def test_module_static_asset_path_resolves_registered_navigation_shell_assets() -> None:
    assert module_static_asset_path("navigation_shell", "style.css", Path("/workspace")) == Path(
        "/workspace/aria/static/style.css"
    )
    assert module_static_asset_path("navigation_shell", "favicon.ico", Path("/workspace")) == Path(
        "/workspace/aria/static/favicon.ico"
    )
    assert module_static_asset_path("navigation_shell", "favicon-48x48.png", Path("/workspace")) == Path(
        "/workspace/aria/static/favicon-48x48.png"
    )
    assert module_static_asset_path("navigation_shell", "logo-aria-v01.png", Path("/workspace")) == Path(
        "/workspace/aria/static/logo-aria-v01.png"
    )
    assert module_static_asset_path("navigation_shell", "vendor/htmx-1.9.12.min.js", Path("/workspace")) == Path(
        "/workspace/aria/static/vendor/htmx-1.9.12.min.js"
    )


def test_module_static_asset_prefix_path_resolves_registered_navigation_shell_backgrounds() -> None:
    assert module_static_asset_prefix_path("navigation_shell", "background-grid-signal.webp", Path("/workspace")) == Path(
        "/workspace/aria/static/background-grid-signal.webp"
    )
    assert module_static_asset_prefix_path("navigation_shell", "background-custom.webp", Path("/workspace")) == Path(
        "/workspace/aria/static/background-custom.webp"
    )


def test_module_route_path_resolves_navigation_shell_favicon_route() -> None:
    assert module_route_path("navigation_shell", "/favicon.ico") == "/favicon.ico"


def test_module_route_path_resolves_registered_chat_surface_home_route() -> None:
    assert module_route_path("chat_surface", "/") == "/"


def test_module_template_name_resolves_registered_chat_surface_template() -> None:
    assert module_template_name("chat_surface", "chat.html") == "chat.html"


def test_module_static_asset_path_rejects_unknown_or_nested_assets() -> None:
    assert module_static_asset_path("release_update", "missing.js", Path("/workspace")) is None
    assert module_static_asset_path("release_update", "../update-reconnect-sw.js", Path("/workspace")) is None
    assert module_static_asset_path("navigation_shell", "vendor/../style.css", Path("/workspace")) is None
    assert module_static_asset_path("missing", "update-reconnect-sw.js", Path("/workspace")) is None
    assert module_static_asset_prefix_path("navigation_shell", "style.css", Path("/workspace")) is None
    assert module_static_asset_prefix_path("navigation_shell", "nested/background-grid-signal.webp", Path("/workspace")) is None
    assert module_static_asset_prefix_path("missing", "background-grid-signal.webp", Path("/workspace")) is None


def test_module_prompt_path_resolves_registered_recipe_prompt_roots() -> None:
    assert module_prompt_path("recipe_store", "prompts/recipes/ops-report.md", Path("/workspace")) == Path(
        "/workspace/prompts/recipes/ops-report.md"
    )
    assert module_prompt_path(
        "recipe_legacy_skill_compat", "prompts/skills/ops-report.md", Path("/workspace")
    ) == Path(
        "/workspace/prompts/skills/ops-report.md"
    )
    assert module_prompt_path("recipes", "prompts/recipes/ops-report.md", Path("/workspace")) is None


def test_module_prompt_path_rejects_unowned_or_unsafe_paths() -> None:
    assert module_prompt_path("recipe_store", "prompts/custom/ops-report.md", Path("/workspace")) is None
    assert module_prompt_path("recipe_store", "prompts/recipes/../secrets.md", Path("/workspace")) is None
    assert module_prompt_path("recipe_store", "/prompts/recipes/ops-report.md", Path("/workspace")) is None
    assert module_prompt_path("missing", "prompts/recipes/ops-report.md", Path("/workspace")) is None


def test_module_public_path_prefix_resolves_only_registered_static_boundary() -> None:
    assert module_public_path_prefix("navigation_shell", "/static/style.css") == "/static/style.css"
    assert module_public_path_prefix("navigation_shell", "/static/vendor/app.js") == "/static/vendor/app.js"
    assert module_public_path_prefix("navigation_shell", "/static") is None
    assert module_public_path_prefix("navigation_shell", "/staticx/style.css") is None
    assert module_public_path_prefix("navigation_shell", "/static/../config") is None
    assert module_public_path_prefix("navigation_shell", "/static\\style.css") is None
    assert module_public_path_prefix("missing", "/static/style.css") is None
    assert (
        module_public_path_prefix(
            "navigation_shell",
            "/staticx/style.css",
            manifests={"navigation_shell": {"public_path_prefixes": ["/static"]}},
        )
        is None
    )


def test_module_asset_path_resolves_registered_static_help_docs_product_asset() -> None:
    path = module_asset_path(
        "static_help_docs",
        "aria_schichten_architektur.svg",
        Path("/workspace"),
        asset_field="product_info_assets",
    )

    assert path == Path("/workspace/docs/product/aria_schichten_architektur.svg")


def test_module_asset_path_rejects_unknown_nested_or_escaping_assets() -> None:
    manifests = {
        "demo": {
            "id": "demo",
            "assets": {
                "ok.svg": "docs/product/ok.svg",
                "escape.svg": "../escape.svg",
                "absolute.svg": "/tmp/absolute.svg",
            },
        }
    }

    assert module_asset_path("demo", "ok.svg", Path("/workspace"), manifests=manifests) == Path(
        "/workspace/docs/product/ok.svg"
    )
    assert module_asset_path("demo", "missing.svg", Path("/workspace"), manifests=manifests) is None
    assert module_asset_path("demo", "../ok.svg", Path("/workspace"), manifests=manifests) is None
    assert module_asset_path("demo", "escape.svg", Path("/workspace"), manifests=manifests) is None
    assert module_asset_path("demo", "absolute.svg", Path("/workspace"), manifests=manifests) is None
    assert module_asset_path("missing", "ok.svg", Path("/workspace"), manifests=manifests) is None


def test_module_catalog_entries_resolves_static_help_docs_product_docs() -> None:
    entries = module_catalog_entries("static_help_docs", "product_docs")

    assert [entry["id"] for entry in entries] == ["overview", "feature-list", "architecture"]
    assert entries[0]["path"] == "docs/product/overview.md"
    assert entries[2]["assets"]


def test_module_catalog_entries_resolves_static_help_docs_help_docs_and_groups() -> None:
    help_docs = module_catalog_entries("static_help_docs", "help_docs")
    groups = module_catalog_entries("static_help_docs", "help_doc_groups", require_path=False)

    assert [entry["id"] for entry in help_docs] == [
        "home",
        "quick-start",
        "chat",
        "navigation",
        "memory",
        "notes",
        "skills",
        "agentic",
        "connections",
        "releases",
        "pricing",
        "qdrant",
        "security",
        "alpha-help-system",
        "help-system",
    ]
    assert [entry["id"] for entry in groups] == ["wiki", "reference"]
    assert {entry["group"] for entry in help_docs} == {"wiki", "reference"}


def test_module_catalog_entries_resolves_static_help_docs_file_editor_entries() -> None:
    entries = module_catalog_entries("static_help_docs", "file_editor_entries")

    assert [entry["id"] for entry in entries] == ["memory_help", "pricing_help", "security_help"]
    assert [entry["path"] for entry in entries] == [
        "docs/help/memory.md",
        "docs/help/pricing.md",
        "docs/help/security.md",
    ]
    assert {entry["mode"] for entry in entries} == {"readonly"}
    assert {entry["group"] for entry in entries} == {"help"}


def test_module_catalog_entries_rejects_missing_or_incomplete_entries() -> None:
    manifests = {
        "demo": {
            "id": "demo",
            "catalog": [
                {"id": "ok", "path": "docs/ok.md", "extra": "kept"},
                {"id": "", "path": "docs/missing-id.md"},
                {"id": "missing-path"},
                "not-a-mapping",
            ],
        }
    }

    assert module_catalog_entries("demo", "catalog", manifests=manifests) == (
        {"id": "ok", "path": "docs/ok.md", "extra": "kept"},
    )
    assert module_catalog_entries("demo", "missing", manifests=manifests) == ()
    assert module_catalog_entries("missing", "catalog", manifests=manifests) == ()
    assert module_catalog_entries("demo", "catalog", require_path=False, manifests=manifests) == (
        {"id": "ok", "path": "docs/ok.md", "extra": "kept"},
        {"id": "missing-path"},
    )


def test_module_template_name_resolves_registered_release_update_templates() -> None:
    assert module_template_name("release_update", "updates.html") == "updates.html"
    assert module_template_name("release_update", "updates_running.html") == "updates_running.html"


def test_module_template_name_resolves_registered_static_help_docs_templates() -> None:
    assert module_template_name("static_help_docs", "help.html") == "help.html"
    assert module_template_name("static_help_docs", "licenses.html") == "licenses.html"
    assert module_template_name("static_help_docs", "product_info.html") == "product_info.html"


def test_module_template_name_resolves_registered_config_backup_template() -> None:
    assert module_template_name("config_backup", "config_backup.html") == "config_backup.html"


def test_module_template_name_resolves_registered_stats_ui_templates() -> None:
    assert module_template_name("stats_ui", "stats.html") == "stats.html"
    assert module_template_name("stats_ui", "activities.html") == "activities.html"
    assert module_template_name("stats_ui", "_stats_pricing_panel.html") == "_stats_pricing_panel.html"


def test_module_template_name_resolves_registered_auth_ui_templates() -> None:
    assert module_template_name("auth_ui", "login.html") == "login.html"
    assert module_template_name("auth_ui", "session_expired.html") == "session_expired.html"


def test_module_template_name_resolves_registered_agent_jobs_template() -> None:
    assert module_template_name("chat_execution_composition", "agent_jobs.html") == "agent_jobs.html"


def test_module_template_name_resolves_registered_connections_ui_readonly_templates() -> None:
    assert module_template_name("connections_ui_readonly", "connections_hub.html") == "connections_hub.html"
    assert module_template_name("connections_ui_readonly", "connections_status.html") == "connections_status.html"
    assert module_template_name("connections_ui_readonly", "connections_types.html") == "connections_types.html"
    assert module_template_name("connections_ui_readonly", "connections_templates.html") == "connections_templates.html"


def test_module_template_name_resolves_registered_recipes_ui_templates() -> None:
    assert module_template_name("recipes_ui", "recipes_overview.html") == "recipes_overview.html"
    assert module_template_name("recipes_ui", "recipes_start.html") == "recipes_start.html"
    assert module_template_name("recipes_ui", "recipes_mine.html") == "recipes_mine.html"
    assert module_template_name("recipes_ui", "recipes_learned.html") is None
    assert module_template_name("recipes_ui", "recipes_wizard.html") == "recipes_wizard.html"
    assert module_template_name("recipes_ui", "recipes_missing.html") is None


def test_module_template_name_resolves_registered_rss_ui_template() -> None:
    assert module_template_name("rss_ui", "config_connections_rss.html") == "config_connections_rss.html"


def test_module_template_name_resolves_registered_website_ui_template() -> None:
    assert module_template_name("website_ui", "config_connections_websites.html") == "config_connections_websites.html"


def test_module_template_name_resolves_registered_simple_connection_ui_templates() -> None:
    assert module_template_name("discord_ui", "config_connections_discord.html") == "config_connections_discord.html"
    assert module_template_name("imap_ui", "config_connections_imap.html") == "config_connections_imap.html"
    assert module_template_name("mqtt_ui", "config_connections_mqtt.html") == "config_connections_mqtt.html"
    assert module_template_name("smb_ui", "config_connections_smb.html") == "config_connections_smb.html"
    assert module_template_name("smtp_ui", "config_connections_smtp.html") == "config_connections_smtp.html"


def test_module_template_name_resolves_registered_critical_connection_ui_templates() -> None:
    assert (
        module_template_name("google_calendar_ui", "config_connections_google_calendar.html")
        == "config_connections_google_calendar.html"
    )
    assert module_template_name("http_api_admin_ui", "config_connections_http_api.html") == "config_connections_http_api.html"
    assert module_template_name("http_api_admin_ui", "config_connections_webhook.html") == "config_connections_webhook.html"
    assert module_template_name("ssh_admin_ui", "config_connections_ssh.html") == "config_connections_ssh.html"
    assert module_template_name("sftp_admin_ui", "config_connections_sftp.html") == "config_connections_sftp.html"
    assert module_template_name("http_api", "config_connections_http_api.html") is None
    assert module_template_name("ssh", "config_connections_ssh.html") is None


def test_module_template_name_resolves_registered_ops_config_templates() -> None:
    assert module_template_name("ops_config_backup", "config_operations.html") == "config_operations.html"
    assert module_template_name("ops_config_backup", "config_logs.html") == "config_logs.html"
    assert module_template_name("ops_config_backup", "config_operations_reindex.html") is None


def test_module_template_name_resolves_registered_config_ui_templates() -> None:
    assert module_template_name("config_ui", "config.html") == "config.html"
    assert module_template_name("config_ui", "config_hub.html") == "config_hub.html"
    assert module_template_name("config_ui", "config_admin_modules.html") == "config_admin_modules.html"
    assert module_template_name("config_ui", "config_intelligence.html") == "config_intelligence.html"
    assert module_template_name("config_ui", "config_persona.html") == "config_persona.html"
    assert module_template_name("config_ui", "config_access.html") == "config_access.html"
    assert module_template_name("config_ui", "config_workbench.html") is None
    assert module_template_name("config_ui", "config_llm.html") == "config_llm.html"
    assert module_template_name("config_ui", "config_llm_debug.html") == "config_llm_debug.html"
    assert module_template_name("config_ui", "config_embeddings.html") == "config_embeddings.html"
    assert module_template_name("config_ui", "config_files.html") == "config_files.html"
    assert module_template_name("config_ui", "config_error_interpreter.html") == "config_error_interpreter.html"
    assert module_template_name("config_ui", "config_appearance.html") == "config_appearance.html"
    assert module_template_name("config_ui", "config_language.html") == "config_language.html"
    assert module_template_name("config_ui", "config_prompts.html") == "config_prompts.html"
    assert module_template_name("config_ui", "config_connections_mcp.html") == "config_connections_mcp.html"
    assert module_template_name("config_ui", "config_routing.html") is None
    assert module_template_name("config_ui", "config_routing_workbench.html") is None
    assert module_template_name("config_ui", "config_skill_routing.html") is None
    assert module_template_name("config_ui", "config_admin_mode.html") == "config_admin_mode.html"
    assert module_template_name("config_ui", "config_security.html") == "config_security.html"
    assert module_template_name("config_ui", "config_users.html") == "config_users.html"
    assert module_template_name("config_ui", "_config_nav.html") == "_config_nav.html"
    assert module_template_name("config_ui", "_config_page_header.html") == "_config_page_header.html"
    assert module_template_name("config_ui", "_config_workbench_section.html") is None
    assert module_template_name("config_ui", "config_unregistered.html") is None


def test_module_template_name_resolves_registered_memory_admin_ui_templates() -> None:
    assert module_template_name("memory_admin_ui", "memories_overview.html") == "memories_overview.html"
    assert module_template_name("memory_admin_ui", "memories_import.html") == "memories_import.html"
    assert module_template_name("memory_admin_ui", "memories_create.html") == "memories_create.html"
    assert module_template_name("memory_admin_ui", "memories_maintenance.html") == "memories_maintenance.html"
    assert module_template_name("memory_admin_ui", "config_memory.html") == "config_memory.html"
    assert module_template_name("memory_admin_ui", "memories_auto_memory.html") == "memories_auto_memory.html"
    assert module_template_name("memory_admin_ui", "memories_learning_candidate_apply_preview.html") is None
    assert module_template_name("memory_admin_ui", "memories_missing.html") is None


def test_module_template_name_rejects_unknown_or_nested_templates() -> None:
    assert module_template_name("release_update", "missing.html") is None
    assert module_template_name("release_update", "../updates.html") is None
    assert module_template_name("missing", "updates.html") is None


def test_module_route_path_resolves_registered_release_update_routes() -> None:
    assert module_route_path("release_update", "/health") == "/health"
    assert module_route_path("release_update", "/update-reconnect-sw.js") == "/update-reconnect-sw.js"
    assert module_route_path("release_update", "/updates") == "/updates"
    assert module_route_path("release_update", "/updates/running") == "/updates/running"
    assert module_route_path("release_update", "/updates/relogin") == "/updates/relogin"
    assert module_route_path("release_update", "/updates/run") == "/updates/run"
    assert module_route_path("release_update", "/updates/status") == "/updates/status"


def test_module_route_path_resolves_registered_config_backup_routes() -> None:
    assert module_route_path("config_backup", "/config/backup") == "/config/backup"
    assert module_route_path("config_backup", "/config/backup/export") == "/config/backup/export"
    assert module_route_path("config_backup", "/config/backup/import") == "/config/backup/import"


def test_module_route_path_resolves_registered_ops_config_backup_routes() -> None:
    assert module_route_path("ops_config_backup", "/memories/reindex") is None
    assert module_route_path("ops_config_backup", "/config/operations/service-restart") == "/config/operations/service-restart"
    assert module_route_path("ops_config_backup", "/config/logs/save") == "/config/logs/save"
    assert module_route_path("ops_config_backup", "/config/logs/cleanup") == "/config/logs/cleanup"
    assert module_route_path("ops_config_backup", "/config/logs/reset") == "/config/logs/reset"
    assert module_route_path("ops_config_backup", "/config/logs/factory-reset") == "/config/logs/factory-reset"


def test_ops_config_backup_route_readpoints_cover_passive_visible_actions() -> None:
    assert module_route_path("ops_config_backup", "/memories/reindex/run") == "/memories/reindex/run"
    assert module_route_path("ops_config_backup", "/memories/reindex/save") == "/memories/reindex/save"


def test_module_route_path_resolves_registered_memory_export_route() -> None:
    assert module_route_path("memory_export", "/memories/export") == "/memories/export"


def test_module_route_path_resolves_registered_notes_routes() -> None:
    assert module_route_path("notes", "/notes") == "/notes"
    assert module_route_path("notes", "/notes/save") == "/notes/save"
    assert module_route_path("notes", "/notes/delete") == "/notes/delete"
    assert module_route_path("notes", "/notes/move") == "/notes/move"
    assert module_route_path("notes", "/notes/bulk/move") == "/notes/bulk/move"
    assert module_route_path("notes", "/notes/folders/create") == "/notes/folders/create"
    assert module_route_path("notes", "/notes/folders/rename") == "/notes/folders/rename"
    assert module_route_path("documents", "/notes") is None


def test_module_route_path_resolves_registered_memory_admin_ui_routes() -> None:
    assert module_route_path("memory_admin_ui", "/memories") == "/memories"
    assert module_route_path("memory_admin_ui", "/memories/import") == "/memories/import"
    assert module_route_path("memory_admin_ui", "/memories/create") == "/memories/create"
    assert module_route_path("memory_admin_ui", "/memories/maintenance") == "/memories/maintenance"
    assert module_route_path("memory_admin_ui", "/memories/config") == "/memories/config"
    assert module_route_path("memory_admin_ui", "/config/memory") == "/config/memory"
    assert module_route_path("memory_admin_ui", "/memories/auto-memory") == "/memories/auto-memory"
    assert module_route_path("memory_admin_ui", "/memories/learning-worker/job/{job_id}") is None
    assert module_route_path("memory_admin_ui", "/memories/learning-worker/flush") is None
    assert module_route_path("memory_admin_ui", "/memories/learning-candidate/apply-preview") is None


def test_memory_admin_ui_route_readpoints_cover_passive_visible_urls() -> None:
    for route_path in (
        "/memories/upload",
        "/memories/maintenance",
        "/memories/config/backend-save",
        "/memories/config/select",
        "/memories/config/create",
        "/memories/config/compression-save",
        "/memories/config/compress",
        "/memories/auto-memory/delete-point",
        "/memories/browser/delete-point",
        "/memories/browser/delete-document",
        "/memories/auto-memory/claim-action",
        "/memories/auto-memory/correct-claim",
        "/memories/auto-memory/delete-claim",
    ):
        assert module_route_path("memory_admin_ui", route_path) == route_path


def test_module_route_path_resolves_registered_static_help_docs_routes() -> None:
    assert module_route_path("static_help_docs", "/help") == "/help"
    assert module_route_path("static_help_docs", "/licenses") == "/licenses"
    assert module_route_path("static_help_docs", "/product-info") == "/product-info"
    assert (
        module_route_path("static_help_docs", "/product-info/assets/{asset_name}")
        == "/product-info/assets/{asset_name}"
    )


def test_module_route_path_resolves_registered_stats_ui_routes() -> None:
    assert module_route_path("stats_ui", "/stats") == "/stats"
    assert module_route_path("stats_ui", "/activities") == "/activities"
    assert module_route_path("stats_ui", "/stats/reset") == "/stats/reset"
    assert module_route_path("stats_ui", "/stats/pricing/refresh") == "/stats/pricing/refresh"
    assert module_route_path("stats_ui", "/stats/pricing/alias/delete") == "/stats/pricing/alias/delete"


def test_module_route_path_resolves_registered_auth_ui_routes() -> None:
    assert module_route_path("auth_ui", "/login") == "/login"
    assert module_route_path("auth_ui", "/logout") == "/logout"
    assert module_route_path("auth_ui", "/session-expired") == "/session-expired"


def test_module_route_path_resolves_registered_connections_ui_readonly_routes() -> None:
    assert module_route_path("connections_ui_readonly", "/connections") == "/connections"
    assert module_route_path("connections_ui_readonly", "/connections/status") == "/connections/status"
    assert module_route_path("connections_ui_readonly", "/connections/types") == "/connections/types"
    assert module_route_path("connections_ui_readonly", "/connections/templates") == "/connections/templates"


def test_module_route_path_resolves_registered_connections_profiles_routes() -> None:
    assert module_route_path("connections_profiles", "/config/connections/delete") == "/config/connections/delete"
    assert module_route_path("connections_profiles", "/config/connections/import-sample") == "/config/connections/import-sample"


def test_module_route_path_resolves_registered_recipes_ui_routes() -> None:
    assert module_route_path("recipes_ui", "/recipes") == "/recipes"
    assert module_route_path("recipes_ui", "/recipes/start") == "/recipes/start"
    assert module_route_path("recipes_ui", "/recipes/mine") == "/recipes/mine"
    assert module_route_path("recipes_ui", "/recipes/learned") is None
    assert module_route_path("recipes_ui", "/recipes/wizard") == "/recipes/wizard"
    assert module_route_path("recipes_ui", "/recipes/wizard/save") == "/recipes/wizard/save"
    assert module_route_path("recipes_ui", "/recipes/import-sample") == "/recipes/import-sample"
    assert module_route_path("recipes_ui", "/recipes/learned/promote-preview") is None


def test_module_route_path_resolves_registered_rss_ui_routes() -> None:
    assert module_route_path("rss_ui", "/config/connections/rss") == "/config/connections/rss"
    assert (
        module_route_path("rss_ui", "/config/connections/rss/poll-interval/save")
        == "/config/connections/rss/poll-interval/save"
    )
    assert module_route_path("rss_ui", "/config/connections/rss/export-opml") == "/config/connections/rss/export-opml"
    assert module_route_path("rss_ui", "/config/connections/rss/import-opml") == "/config/connections/rss/import-opml"
    assert module_route_path("rss_ui", "/config/connections/rss/ping-now") == "/config/connections/rss/ping-now"
    assert module_route_path("rss_ui", "/config/connections/rss/save") == "/config/connections/rss/save"
    assert (
        module_route_path("rss_ui", "/config/connections/rss/suggest-metadata")
        == "/config/connections/rss/suggest-metadata"
    )


def test_module_route_path_resolves_registered_website_ui_routes() -> None:
    assert module_route_path("website_ui", "/config/connections/websites") == "/config/connections/websites"
    assert module_route_path("website_ui", "/config/connections/websites/save") == "/config/connections/websites/save"
    assert (
        module_route_path("website_ui", "/config/connections/websites/suggest-metadata")
        == "/config/connections/websites/suggest-metadata"
    )


def test_module_route_path_resolves_registered_simple_connection_ui_routes() -> None:
    assert module_route_path("discord_ui", "/config/connections/discord") == "/config/connections/discord"
    assert module_route_path("discord_ui", "/config/connections/discord/save") == "/config/connections/discord/save"
    assert module_route_path("imap_ui", "/config/connections/imap") == "/config/connections/imap"
    assert module_route_path("imap_ui", "/config/connections/imap/save") == "/config/connections/imap/save"
    assert module_route_path("mqtt_ui", "/config/connections/mqtt") == "/config/connections/mqtt"
    assert module_route_path("mqtt_ui", "/config/connections/mqtt/save") == "/config/connections/mqtt/save"
    assert module_route_path("smb_ui", "/config/connections/smb") == "/config/connections/smb"
    assert module_route_path("smb_ui", "/config/connections/smb/save") == "/config/connections/smb/save"
    assert module_route_path("smtp_ui", "/config/connections/smtp") == "/config/connections/smtp"
    assert module_route_path("smtp_ui", "/config/connections/smtp/save") == "/config/connections/smtp/save"


def test_module_route_path_resolves_registered_critical_connection_ui_routes() -> None:
    assert (
        module_route_path("google_calendar_ui", "/config/connections/google-calendar")
        == "/config/connections/google-calendar"
    )
    assert (
        module_route_path("google_calendar_ui", "/config/connections/google-calendar/save")
        == "/config/connections/google-calendar/save"
    )
    assert module_route_path("http_api_admin_ui", "/config/connections/http-api") == "/config/connections/http-api"
    assert module_route_path("http_api_admin_ui", "/config/connections/http-api/save") == "/config/connections/http-api/save"
    assert module_route_path("http_api_admin_ui", "/config/connections/webhook") == "/config/connections/webhook"
    assert module_route_path("http_api_admin_ui", "/config/connections/webhook/save") == "/config/connections/webhook/save"
    assert module_route_path("ssh_admin_ui", "/config/connections/save") == "/config/connections/save"
    assert module_route_path("ssh_admin_ui", "/config/connections/key-exchange") == "/config/connections/key-exchange"
    assert module_route_path("ssh_admin_ui", "/config/connections/keygen") == "/config/connections/keygen"
    assert module_route_path("ssh_admin_ui", "/config/connections/ssh") == "/config/connections/ssh"
    assert module_route_path("ssh_admin_ui", "/config/connections/ssh/suggest-metadata") == "/config/connections/ssh/suggest-metadata"
    assert module_route_path("sftp_admin_ui", "/config/connections/sftp") == "/config/connections/sftp"
    assert module_route_path("sftp_admin_ui", "/config/connections/sftp/save") == "/config/connections/sftp/save"
    assert (
        module_route_path("sftp_admin_ui", "/config/connections/sftp/suggest-metadata")
        == "/config/connections/sftp/suggest-metadata"
    )
    assert module_route_path("http_api", "/config/connections/http-api") is None
    assert module_route_path("ssh", "/config/connections/ssh") is None


def test_module_route_path_resolves_registered_config_ui_routes() -> None:
    assert module_route_path("config_ui", "/config") == "/config"
    assert module_route_path("config_ui", "/config/admin-mode") == "/config/admin-mode"
    assert module_route_path("config_ui", "/config/security") == "/config/security"
    assert module_route_path("config_ui", "/config/security/guardrails/draft") == "/config/security/guardrails/draft"
    assert module_route_path("config_ui", "/config/security/guardrails/save") == "/config/security/guardrails/save"
    assert module_route_path("config_ui", "/config/security/guardrails/test") == "/config/security/guardrails/test"
    assert module_route_path("config_ui", "/config/security/guardrails/delete") == "/config/security/guardrails/delete"
    assert (
        module_route_path("config_ui", "/config/security/guardrails/import-sample")
        == "/config/security/guardrails/import-sample"
    )
    assert module_route_path("config_ui", "/config/users") == "/config/users"
    assert module_route_path("config_ui", "/config/users/security-save") == "/config/users/security-save"
    assert module_route_path("config_ui", "/config/users/create") == "/config/users/create"
    assert module_route_path("config_ui", "/config/users/update") == "/config/users/update"
    assert module_route_path("config_ui", "/config/intelligence") == "/config/intelligence"
    assert module_route_path("config_ui", "/config/persona") == "/config/persona"
    assert module_route_path("config_ui", "/config/workbench") is None
    assert module_route_path("config_ui", "/config/routing") is None
    assert module_route_path("config_ui", "/config/routing/qdrant/save") is None
    assert module_route_path("config_ui", "/config/routing-index/rebuild") is None
    assert module_route_path("config_ui", "/config/workbench/routing") is None
    assert module_route_path("config_ui", "/config/skill-routing") is None
    assert module_route_path("config_ui", "/config/skill-routing/save") is None
    assert module_route_path("config_ui", "/config/skill-routing/suggest") is None
    assert module_route_path("config_ui", "/config/skill-routing/suggest-all") is None
    assert module_route_path("config_ui", "/config/skill-routing/rebuild") is None
    assert module_route_path("config_ui", "/config/routing-index/status") == "/config/routing-index/status"
    assert module_route_path("config_ui", "/config/routing-index/test") == "/config/routing-index/test"
    assert module_route_path("config_ui", "/config/llm") == "/config/llm"
    assert module_route_path("config_ui", "/config/embeddings") == "/config/embeddings"
    assert module_route_path("config_ui", "/config/prompts") == "/config/prompts"
    assert module_route_path("config_ui", "/config/appearance") == "/config/appearance"
    assert module_route_path("config_ui", "/config/language") == "/config/language"
    assert module_route_path("config_ui", "/config/files") == "/config/files"
    assert module_route_path("config_ui", "/config/files/save") == "/config/files/save"
    assert module_route_path("config_ui", "/config/error-interpreter") == "/config/error-interpreter"
    assert module_route_path("config_ui", "/config/llm/debug") == "/config/llm/debug"
    assert module_route_path("config_ui", "/config/admin-mode/save") == "/config/admin-mode/save"
    assert module_route_path("config_ui", "/config/appearance/save") == "/config/appearance/save"
    assert module_route_path("config_ui", "/config/language/save") == "/config/language/save"
    assert module_route_path("config_ui", "/config/language/file/save") == "/config/language/file/save"
    assert module_route_path("config_ui", "/config/prompts/save") == "/config/prompts/save"
    assert module_route_path("config_ui", "/config/error-interpreter/save") == "/config/error-interpreter/save"
    assert module_route_path("config_ui", "/config/llm/debug/clear") == "/config/llm/debug/clear"
    assert module_route_path("config_ui", "/config/llm/models") == "/config/llm/models"
    assert module_route_path("config_ui", "/config/llm/test") == "/config/llm/test"
    assert module_route_path("config_ui", "/config/llm/profile/load") == "/config/llm/profile/load"
    assert module_route_path("config_ui", "/config/llm/profile/delete") == "/config/llm/profile/delete"
    assert module_route_path("config_ui", "/config/llm/save") == "/config/llm/save"
    assert module_route_path("config_ui", "/config/llm/profile/save") == "/config/llm/profile/save"
    assert module_route_path("config_ui", "/config/embeddings/test") == "/config/embeddings/test"
    assert module_route_path("config_ui", "/config/embeddings/profile/load") == "/config/embeddings/profile/load"
    assert module_route_path("config_ui", "/config/embeddings/profile/delete") == "/config/embeddings/profile/delete"
    assert module_route_path("config_ui", "/config/embeddings/models") == "/config/embeddings/models"
    assert module_route_path("config_ui", "/config/embeddings/save") == "/config/embeddings/save"
    assert module_route_path("config_ui", "/config/embeddings/profile/save") == "/config/embeddings/profile/save"
    assert module_route_path("config_ui", "/config/connections/mcp") == "/config/connections/mcp"
    assert module_route_path("config_ui", "/config/connections/mcp/save") == "/config/connections/mcp/save"
    assert module_route_path("config_ui", "/config/connections/mcp/master") == "/config/connections/mcp/master"
    assert module_route_path("config_ui", "/config/connections/mcp/reconnect") == "/config/connections/mcp/reconnect"
    assert module_route_path("config_ui", "/config/connections/mcp/delete") == "/config/connections/mcp/delete"


def test_module_route_path_resolves_registered_chat_execution_composition_routes() -> None:
    assert module_route_path("chat_execution_composition", "/chat") == "/chat"
    assert module_route_path("chat_execution_composition", "/chat/progress") == "/chat/progress"
    assert module_route_path("chat_execution_composition", "/chat/history/clear") == "/chat/history/clear"
    assert module_route_path("chat_execution_composition", "/jobs") == "/jobs"
    assert module_route_path("chat_execution_composition", "/jobs/panel") == "/jobs/panel"
    assert module_route_path(
        "chat_execution_composition", "/jobs/{job_id}/notice"
    ) == "/jobs/{job_id}/notice"
    assert module_route_path(
        "chat_execution_composition", "/jobs/{job_id}/cancel"
    ) == "/jobs/{job_id}/cancel"
    assert module_route_path("action_pending_chat_boundary", "/chat") is None


def test_module_route_path_rejects_unknown_or_absolute_url_like_routes() -> None:
    assert module_route_path("release_update", "/missing") is None
    assert module_route_path("release_update", "//updates") is None
    assert module_route_path("missing", "/updates") is None


def test_module_route_prefix_path_resolves_registered_config_ui_prefix() -> None:
    assert module_route_prefix_path("config_ui", "/config") == "/config"
    assert module_route_prefix_path("config_ui", "/config/admin/modules") == "/config/admin/modules"
    assert module_route_prefix_path("ops_config_backup", "/config/logs") == "/config/logs"
    assert module_route_prefix_path("ops_config_backup", "/config/logs/cleanup") == "/config/logs/cleanup"
    assert module_route_prefix_path("recipes_ui", "/recipes/mine") == "/recipes/mine"


def test_module_route_prefix_path_rejects_unknown_or_absolute_url_like_paths() -> None:
    assert module_route_prefix_path("config_ui", "/connections") is None
    assert module_route_prefix_path("config_ui", "//config") is None
    assert module_route_prefix_path("missing", "/config") is None


def test_module_nav_node_id_resolves_registered_navigation_shell_node() -> None:
    assert module_nav_node_id("navigation_shell", "admin.modules", available_node_ids=("admin.modules",)) == "admin.modules"
    assert module_nav_node_id("navigation_shell", "settings.overview", available_node_ids=("settings.overview",)) == "settings.overview"


def test_module_nav_node_id_rejects_unknown_module_node_or_unavailable_node() -> None:
    assert module_nav_node_id("navigation_shell", "missing.node", available_node_ids=("admin.modules",)) is None
    assert module_nav_node_id("missing", "admin.modules", available_node_ids=("admin.modules",)) is None
    assert module_nav_node_id("navigation_shell", "admin.modules", available_node_ids=("settings.overview",)) is None
