from __future__ import annotations

from aria.modules import MODULE_MANIFESTS


def test_sftp_has_separate_provider_namespace_from_ssh() -> None:
    assert "sftp" in MODULE_MANIFESTS
    assert "sftp_admin_ui" in MODULE_MANIFESTS
    assert MODULE_MANIFESTS["sftp_admin_ui"]["parent"] == "sftp"
    assert MODULE_MANIFESTS["ssh_admin_ui"]["parent"] == "ssh"


def test_ssh_admin_ui_no_longer_claims_sftp_routes_or_templates() -> None:
    ssh_admin = MODULE_MANIFESTS["ssh_admin_ui"]
    sftp_admin = MODULE_MANIFESTS["sftp_admin_ui"]

    assert all("sftp" not in route for route in ssh_admin.get("routes", ()))
    assert all("sftp" not in prefix for prefix in ssh_admin.get("routes_prefixes", ()))
    assert "config_connections_sftp.html" not in ssh_admin.get("templates", ())
    assert "/config/connections/sftp" in sftp_admin["routes"]
    assert "config_connections_sftp.html" in sftp_admin["templates"]


def test_sftp_modules_do_not_import_ssh_modules() -> None:
    for module_id in ("sftp", "sftp_admin_ui"):
        manifest = MODULE_MANIFESTS[module_id]
        assert not any(str(dep).startswith("ssh") for dep in manifest.get("depends_on", ()))
        assert not any("/ssh" in str(path) for path in manifest.get("python", ()))


def test_connection_status_runtime_delegates_ssh_and_sftp_to_provider_modules() -> None:
    import aria.modules.connections_runtime_status.runtime as connection_runtime
    from aria.modules.sftp.status import sftp_target, test_sftp_connection
    from aria.modules.ssh_runtime.status import ssh_target, test_ssh_connection

    assert MODULE_MANIFESTS["sftp"]["python"] == [
        "aria/modules/sftp/action_resolution.py",
        "aria/modules/sftp/profile_admin.py",
        "aria/modules/sftp/runtime_execution.py",
        "aria/modules/sftp/status.py",
    ]
    assert MODULE_MANIFESTS["ssh_runtime"]["python"][-1] == "aria/modules/ssh_runtime/status.py"
    assert connection_runtime._CONNECTION_TESTERS["sftp"] is test_sftp_connection  # type: ignore[attr-defined]
    assert connection_runtime._CONNECTION_TARGETS["sftp"] is sftp_target  # type: ignore[attr-defined]
    assert connection_runtime._CONNECTION_TESTERS["ssh"] is test_ssh_connection  # type: ignore[attr-defined]
    assert connection_runtime._CONNECTION_TARGETS["ssh"] is ssh_target  # type: ignore[attr-defined]


def test_connection_context_runtime_delegates_ssh_and_sftp_to_provider_modules() -> None:
    import aria.modules.connections_ui_readonly.context_helpers as connection_context
    from aria.modules.sftp_admin_ui.context import build_sftp_connections_context
    from aria.modules.ssh_admin_ui.context import build_ssh_connections_context

    assert MODULE_MANIFESTS["sftp_admin_ui"]["python"] == [
        "aria/modules/sftp_admin_ui/context.py",
        "aria/modules/sftp_admin_ui/metadata.py",
        "aria/modules/sftp_admin_ui/mutations.py",
        "aria/modules/sftp_admin_ui/reader.py",
    ]
    assert MODULE_MANIFESTS["ssh_admin_ui"]["python"] == [
        "aria/modules/ssh_admin_ui/context.py",
        "aria/modules/ssh_admin_ui/metadata.py",
        "aria/modules/ssh_admin_ui/mutations.py",
        "aria/modules/ssh_admin_ui/reader.py",
        "aria/modules/ssh_admin_ui/support.py",
    ]
    assert connection_context.provider_sftp_connections_context is build_sftp_connections_context
    assert connection_context.provider_ssh_connections_context is build_ssh_connections_context


def test_connection_metadata_routes_delegate_ssh_and_sftp_to_provider_modules() -> None:
    import aria.modules.connections_ui_readonly.metadata_routes as metadata_routes
    from aria.modules.sftp_admin_ui.metadata import register_sftp_metadata_route
    from aria.modules.ssh_admin_ui.metadata import register_ssh_metadata_route

    assert metadata_routes.register_sftp_metadata_route is register_sftp_metadata_route
    assert metadata_routes.register_ssh_metadata_route is register_ssh_metadata_route


def test_connection_detail_routes_delegate_ssh_and_sftp_registration_to_provider_modules() -> None:
    import aria.modules.connections_ui_readonly.detail_routes as detail_routes
    from aria.modules.sftp_admin_ui.context import register_sftp_connections_detail_route
    from aria.modules.ssh_admin_ui.context import register_ssh_connections_detail_route

    assert detail_routes.register_sftp_connections_detail_route is register_sftp_connections_detail_route
    assert detail_routes.register_ssh_connections_detail_route is register_ssh_connections_detail_route


def test_connection_mutation_routes_delegate_ssh_and_sftp_registration_to_provider_modules() -> None:
    import aria.modules.connections_mutations.routes as mutation_routes
    from aria.modules.sftp_admin_ui.mutations import register_sftp_mutation_route
    from aria.modules.ssh_admin_ui.mutations import register_ssh_mutation_routes

    assert mutation_routes.register_sftp_mutation_route is register_sftp_mutation_route
    assert mutation_routes.register_ssh_mutation_routes is register_ssh_mutation_routes


def test_connection_reader_helpers_delegate_ssh_metadata_and_website_seed_to_provider_modules() -> None:
    import aria.modules.connections_ui_readonly.reader_helpers as reader_helpers
    from aria.modules.ssh_admin_ui.metadata import autofill_service_connection_metadata
    from aria.modules.ssh_admin_ui.metadata import extract_ssh_service_seed
    from aria.modules.ssh_admin_ui.metadata import suggest_ssh_metadata_with_llm
    from aria.modules.website_ui.metadata import extract_website_service_seed

    assert reader_helpers.provider_extract_ssh_service_seed is extract_ssh_service_seed
    assert reader_helpers.provider_suggest_ssh_metadata_with_llm is suggest_ssh_metadata_with_llm
    assert reader_helpers.provider_autofill_service_connection_metadata is autofill_service_connection_metadata
    assert reader_helpers.extract_website_service_seed is extract_website_service_seed
    assert "aria/modules/website_ui/metadata.py" in MODULE_MANIFESTS["website_ui"]["python"]


def test_connection_readers_delegate_ssh_and_sftp_to_provider_modules() -> None:
    import aria.modules.connections_ui_readonly.reader_helpers as reader_helpers
    from aria.modules.sftp_admin_ui.reader import read_sftp_connections
    from aria.modules.ssh_admin_ui.reader import read_ssh_connections

    assert reader_helpers.provider_read_sftp_connections is read_sftp_connections
    assert reader_helpers.provider_read_ssh_connections is read_ssh_connections


def test_connection_mutation_handlers_delegate_ssh_key_actions_to_ssh_admin_ui() -> None:
    import aria.modules.connections_mutations.handlers as mutation_handlers
    from aria.modules.sftp_admin_ui.mutations import handle_sftp_save
    from aria.modules.ssh_admin_ui.mutations import handle_ssh_key_exchange
    from aria.modules.ssh_admin_ui.mutations import handle_ssh_keygen
    from aria.modules.ssh_admin_ui.mutations import handle_ssh_save
    from aria.modules.ssh_admin_ui.mutations import handle_ssh_test

    assert mutation_handlers.handle_ssh_save is handle_ssh_save
    assert mutation_handlers.handle_sftp_save is handle_sftp_save
    assert mutation_handlers.handle_ssh_keygen is handle_ssh_keygen
    assert mutation_handlers.handle_ssh_key_exchange is handle_ssh_key_exchange
    assert mutation_handlers.handle_ssh_test is handle_ssh_test


def test_connection_mutation_support_delegates_ssh_support_to_ssh_admin_ui() -> None:
    import aria.modules.connections_mutations.support_helpers as support_helpers
    from aria.modules.ssh_admin_ui.support import derive_matching_sftp_ref
    from aria.modules.ssh_admin_ui.support import ensure_ssh_keypair
    from aria.modules.ssh_admin_ui.support import friendly_ssh_setup_error
    from aria.modules.ssh_admin_ui.support import perform_ssh_key_exchange
    from aria.modules.ssh_admin_ui.support import read_ssh_connection_profiles
    from aria.modules.ssh_admin_ui.support import ssh_keys_dir

    assert support_helpers.provider_ssh_keys_dir is ssh_keys_dir
    assert support_helpers.provider_ensure_ssh_keypair is ensure_ssh_keypair
    assert support_helpers.provider_friendly_ssh_setup_error is friendly_ssh_setup_error
    assert support_helpers.provider_perform_ssh_key_exchange is perform_ssh_key_exchange
    assert support_helpers.read_ssh_connection_profiles is read_ssh_connection_profiles
    assert support_helpers.provider_derive_matching_sftp_ref is derive_matching_sftp_ref
    assert support_helpers.derive_matching_sftp_ref("node-ssh") == "node-sftp"


def test_connection_profile_admin_delegates_ssh_and_sftp_rows_to_provider_modules() -> None:
    import aria.modules.connections_profiles.admin as profile_admin
    from aria.modules.sftp.profile_admin import build_sftp_connection_profile
    from aria.modules.sftp.profile_admin import update_sftp_connection_profile
    from aria.modules.ssh.profile_admin import build_ssh_connection_profile
    from aria.modules.ssh.profile_admin import update_ssh_connection_profile

    assert MODULE_MANIFESTS["ssh"]["python"] == ["aria/modules/ssh/profile_admin.py"]
    assert profile_admin.CONNECTION_PROFILE_CREATE_BUILDERS["ssh"] is build_ssh_connection_profile
    assert profile_admin.CONNECTION_PROFILE_CREATE_BUILDERS["sftp"] is build_sftp_connection_profile
    assert profile_admin.CONNECTION_PROFILE_UPDATE_BUILDERS["ssh"] is update_ssh_connection_profile
    assert profile_admin.CONNECTION_PROFILE_UPDATE_BUILDERS["sftp"] is update_sftp_connection_profile


def test_generic_capability_runtime_delegates_ssh_outcome_to_ssh_runtime() -> None:
    import aria.modules.capability_runtime.handler as capability_handler
    from aria.modules.ssh_runtime.outcome import ssh_runtime_outcome_metadata

    assert "aria/modules/ssh_runtime/outcome.py" in MODULE_MANIFESTS["ssh_runtime"]["python"]
    assert capability_handler.ssh_runtime_outcome_metadata is ssh_runtime_outcome_metadata


def test_pipeline_capability_execution_delegates_ssh_and_sftp_runtime_to_provider_modules() -> None:
    import aria.modules.pipeline_capability_execution.executor as execution
    from aria.modules.sftp.runtime_execution import execute_sftp_file_list
    from aria.modules.sftp.runtime_execution import execute_sftp_file_read
    from aria.modules.sftp.runtime_execution import execute_sftp_file_write
    from aria.modules.ssh_runtime.capability_execution import execute_ssh_command

    assert "sftp" in MODULE_MANIFESTS["pipeline_capability_execution"]["depends_on"]
    assert "ssh_runtime" in MODULE_MANIFESTS["pipeline_capability_execution"]["depends_on"]
    assert execution.execute_sftp_file_read is execute_sftp_file_read
    assert execution.execute_sftp_file_write is execute_sftp_file_write
    assert execution.execute_sftp_file_list is execute_sftp_file_list
    assert execution.provider_execute_ssh_command is execute_ssh_command


def test_runtime_execution_registry_gets_ssh_adapter_ids_from_ssh_runtime() -> None:
    import aria.modules.runtime_execution_registry.registry as runtime_registry
    from aria.modules.ssh_runtime.registry import SPECIALIZED_RUNTIME_ADAPTER_IDS

    assert "aria/modules/ssh_runtime/registry.py" in MODULE_MANIFESTS["ssh_runtime"]["python"]
    assert runtime_registry.SSH_SPECIALIZED_RUNTIME_ADAPTER_IDS is SPECIALIZED_RUNTIME_ADAPTER_IDS
    assert "builtin.ssh" in runtime_registry.SPECIALIZED_RUNTIME_ADAPTER_IDS


def test_ssh_manifests_do_not_claim_sftp_runtime_or_ui_boundaries() -> None:
    for module_id, manifest in MODULE_MANIFESTS.items():
        if not module_id.startswith("ssh"):
            continue
        combined = " ".join(
            str(value)
            for field in ("routes", "routes_prefixes", "templates", "explicitly_excluded", "notes")
            for value in manifest.get(field, ())
        ).lower()
        assert "sftp" not in combined, module_id
