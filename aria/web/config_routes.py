from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from aria.web.config_misc_helpers import (
    build_editor_entries_from_paths,
    embedding_fingerprint_for_values,
    embedding_switch_requires_confirmation,
    format_session_timeout_label,
    is_valid_csrf_submission,
    memory_point_totals,
    resolve_embedding_model_label,
    sanitize_reference_name_local,
    short_fingerprint,
)
from aria.web.connection_ui_helpers import (
    _SEARXNG_CATEGORY_OPTIONS,
    _SEARXNG_ENGINE_OPTIONS,
    attach_connection_edit_urls,
    attach_mixed_connection_edit_urls,
    build_connection_intro,
    build_connection_status_block,
    build_connection_summary_cards,
    build_schema_form_fields,
    build_schema_toggle_sections,
    connection_edit_url,
)
from aria.web.connection_support_helpers import (
    apply_factory_reset_to_raw_config,
    build_connection_metadata,
    build_connection_ref_options,
    build_sample_connection_rows,
    build_sample_guardrail_rows,
    clear_qdrant_factory_data,
    derive_matching_sftp_ref,
    ensure_ssh_keypair_impl,
    friendly_ssh_setup_error_impl,
    normalize_connection_meta_list,
    normalize_rss_feed_url_for_dedupe,
    perform_ssh_key_exchange_impl,
    read_connection_metadata,
    read_ssh_connections_impl,
    SAMPLE_GUARDRAILS_DIR,
    ssh_keys_dir_impl,
    split_guardrail_terms,
    wipe_directory_contents,
)
from aria.web.connection_admin_helpers import ConnectionAdminHelperDeps, ConnectionAdminHelpers
from aria.web.connection_context_helpers import ConnectionContextHelperDeps, build_connection_context_helpers
from aria.web.connection_detail_routes import ConnectionDetailRouteDeps, register_connection_detail_routes
from aria.web.connection_metadata_routes import ConnectionMetadataRouteDeps, register_connection_metadata_routes
from aria.web.connection_mutation_routes import ConnectionMutationRouteDeps, register_connection_mutation_routes
from aria.web.connection_mutation_handlers import (
    ConnectionMutationHandlerDeps,
    build_connection_mutation_handlers,
)
from aria.web.connection_page_helpers import (
    ConnectionPageHelperDeps,
    build_connection_page_helpers,
)
from aria.web.connections_surface_helpers import (
    ConnectionsSurfaceHelperDeps,
    build_connections_page_context_helper,
)
from aria.web.connection_reader_helpers import ConnectionReaderHelperDeps, build_connection_reader_helpers
from aria.web.connections_surface_routes import ConnectionsSurfaceRouteDeps, register_connections_surface_routes
from aria.web.config_access_detail_routes import (
    ConfigAccessDetailRouteDeps,
    register_config_access_detail_routes,
)
from aria.web.config_operations_detail_routes import (
    ConfigOperationsDetailRouteDeps,
    register_config_operations_detail_routes,
)
from aria.web.config_persona_routes import ConfigPersonaRouteDeps, register_config_persona_routes
from aria.web.config_intelligence_workbench_routes import (
    ConfigIntelligenceWorkbenchRouteDeps,
    register_config_intelligence_workbench_routes,
)
from aria.web.config_navigation_helpers import build_config_navigation_helpers
from aria.web.config_profile_helpers import ConfigProfileHelperDeps, build_config_profile_helpers
from aria.web.config_support_helpers import ConfigSupportHelperDeps, build_config_support_helpers
from aria.web.config_routing_detail_routes import (
    ConfigRoutingDetailRouteDeps,
    register_config_routing_detail_routes,
)
from aria.web.config_surface_routes import ConfigSurfaceRouteDeps, ConfigSurfaceRouter, register_config_surface_routes
from aria.web.config_surface_helpers import (
    ConfigOverviewHelperDeps,
    build_config_overview_checks_helper,
    build_surface_path_resolver,
    format_config_info_message,
)
from aria.core.connection_admin import CONNECTION_ADMIN_SPECS
from aria.core.connection_catalog import (
    connection_edit_page,
    connection_field_specs,
    connection_menu_rows,
    connection_overview_meta,
    connection_ref_query_param,
    connection_status_meta,
    connection_template_name,
    connection_ui_sections,
    normalize_connection_kind,
)
from aria.core.config import resolve_searxng_base_url
from aria.core.connection_health import delete_connection_health
from aria.core.connection_runtime import (
    build_connection_status_row,
    build_connection_status_rows,
    build_settings_connection_status_rows,
    probe_searxng_stack_service,
)
from aria.core.guardrails import guardrail_is_compatible
from aria.core.pipeline import Pipeline
from aria.core.runtime_diagnostics import probe_embeddings, probe_llm
from aria.core.routing_admin import build_connection_routing_index_status
from aria.core.routing_admin import rebuild_connection_routing_index
from aria.core.routing_admin import test_connection_routing_query
from aria.core.update_helper_client import fetch_update_helper_status
from aria.core.update_helper_client import resolve_update_helper_config
from aria.core.update_helper_client import trigger_update_helper_service_restart
from aria.core.routing_hints import (
    connection_metadata_is_sparse,
    suggest_connection_metadata_with_llm,
)
from aria.core.rss_grouping import build_rss_status_groups
from aria.core.rss_grouping import load_cached_rss_status_groups, save_cached_rss_status_groups
from aria.core.rss_opml import build_opml_document, parse_opml_feeds


(
    SettingsGetter,
    PipelineGetter,
    UsernameResolver,
    AuthSessionResolver,
    StringSanitizer,
    RoleSanitizer,
    DefaultCollectionResolver,
    AuthEncoder,
    ActiveAdminCounter,
    RawConfigReader,
    RawConfigWriter,
    RuntimeReloader,
    TextReader,
    LinesParser,
    ModelChecker,
    PromptResolver,
    PromptLister,
    FileLister,
    FileResolver,
    FileEditorEntryLister,
    FileEditorFileResolver,
    ModelLoader,
    IntGetter,
    ProfilesGetter,
    ActiveProfileGetter,
    ActiveProfileSetter,
    SecureStoreGetter,
    LanguageRowsGetter,
    LanguageResolver,
    CacheClearer,
    CustomSkillManifestLoader,
    CustomSkillFileResolver,
    CustomSkillSaver,
    TriggerIndexBuilder,
    SkillRoutingInfoFormatter,
    KeywordSuggester,
) = (
    Callable[[], Any],
    Callable[[], Pipeline],
    Callable[[Request], str],
    Callable[[Request], dict[str, Any] | None],
    Callable[[str | None], str],
    Callable[[str | None], str],
    Callable[[str], str],
    Callable[[str, str], str],
    Callable[[list[dict[str, Any]]], int],
    Callable[[], dict[str, Any]],
    Callable[[dict[str, Any]], None],
    Callable[[], None],
    Callable[[], str],
    Callable[[str], list[str]],
    Callable[[str], bool],
    Callable[[str], Path],
    Callable[[], list[dict[str, Any]]],
    Callable[[], list[str]],
    Callable[[str], Path],
    Callable[[], list[dict[str, Any]]],
    Callable[[str], Path],
    Callable[[str, str], list[str]],
    Callable[[], int],
    Callable[[dict[str, Any], str], dict[str, dict[str, Any]]],
    Callable[[dict[str, Any], str], str],
    Callable[[dict[str, Any], str, str], None],
    Callable[[dict[str, Any] | None], Any],
    Callable[[], list[str]],
    Callable[[str, str], str],
    Callable[[], None],
    Callable[[], tuple[list[dict[str, Any]], list[str]]],
    Callable[[str], Path],
    Callable[[dict[str, Any]], dict[str, Any]],
    Callable[[], dict[str, Any]],
    Callable[[str, str], str],
    Callable[..., Awaitable[list[str]]],
)
_RSS_METADATA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 ARIA/1.0"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}
EMBEDDING_SWITCH_CONFIRM_PHRASE = "EMBEDDINGS WECHSELN"
_resolve_embedding_model_label = resolve_embedding_model_label
_embedding_fingerprint_for_values = embedding_fingerprint_for_values
_short_fingerprint = short_fingerprint
_memory_point_totals = memory_point_totals
_embedding_switch_requires_confirmation = embedding_switch_requires_confirmation
_friendly_ssh_setup_error_impl = friendly_ssh_setup_error_impl
_WEB_METADATA_HEADERS = {
    **_RSS_METADATA_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}
_sanitize_reference_name_local = sanitize_reference_name_local
_is_valid_csrf_submission = is_valid_csrf_submission
_format_session_timeout_label = format_session_timeout_label
_build_editor_entries_from_paths = build_editor_entries_from_paths
_build_schema_form_fields = build_schema_form_fields
_build_schema_toggle_sections = build_schema_toggle_sections
_build_connection_intro = build_connection_intro
_build_connection_status_block = build_connection_status_block
_connection_edit_url = connection_edit_url
_attach_connection_edit_urls = attach_connection_edit_urls
_attach_mixed_connection_edit_urls = attach_mixed_connection_edit_urls
_build_connection_summary_cards = build_connection_summary_cards
_wipe_directory_contents = wipe_directory_contents
_apply_factory_reset_to_raw_config = apply_factory_reset_to_raw_config
_clear_qdrant_factory_data = clear_qdrant_factory_data
_ssh_keys_dir_impl = ssh_keys_dir_impl
_ensure_ssh_keypair_impl = ensure_ssh_keypair_impl
_read_ssh_connections_impl = read_ssh_connections_impl
_normalize_connection_meta_list = normalize_connection_meta_list
_read_connection_metadata = read_connection_metadata
_build_connection_metadata = build_connection_metadata
_derive_matching_sftp_ref = derive_matching_sftp_ref
_normalize_rss_feed_url_for_dedupe = normalize_rss_feed_url_for_dedupe
_split_guardrail_terms = split_guardrail_terms
_build_connection_ref_options = build_connection_ref_options
_build_sample_connection_rows = build_sample_connection_rows
_build_sample_guardrail_rows = build_sample_guardrail_rows
_perform_ssh_key_exchange_impl = perform_ssh_key_exchange_impl

class _DynamicProxy:
    def __init__(self, getter: Callable[[], Any]) -> None:
        self._getter = getter
    def __getattr__(self, name: str) -> Any:
        return getattr(self._getter(), name)

@dataclass(slots=True)
class ConfigRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    error_interpreter_path: Path
    llm_provider_presets: dict[str, dict[str, str]]
    embedding_provider_presets: dict[str, dict[str, str]]
    auth_cookie: str
    lang_cookie: str
    username_cookie: str
    memory_collection_cookie: str
    get_auth_session_max_age_seconds: IntGetter
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_username_from_request: UsernameResolver
    get_auth_session_from_request: AuthSessionResolver
    sanitize_role: RoleSanitizer
    sanitize_username: StringSanitizer
    sanitize_connection_name: StringSanitizer
    sanitize_skill_id: StringSanitizer
    sanitize_profile_name: StringSanitizer
    default_memory_collection_for_user: DefaultCollectionResolver
    encode_auth_session: AuthEncoder
    get_auth_manager: Callable[[], Any | None]
    active_admin_count: ActiveAdminCounter
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    read_error_interpreter_raw: TextReader
    parse_lines: LinesParser
    is_ollama_model: ModelChecker
    resolve_prompt_file: PromptResolver
    list_prompt_files: PromptLister
    list_editable_files: FileLister
    resolve_edit_file: FileResolver
    list_file_editor_entries: FileEditorEntryLister
    resolve_file_editor_file: FileEditorFileResolver
    load_models_from_api_base: ModelLoader
    get_profiles: ProfilesGetter
    get_active_profile_name: ActiveProfileGetter
    set_active_profile: ActiveProfileSetter
    get_secure_store: SecureStoreGetter
    lang_flag: Callable[[str], str]
    lang_label: Callable[[str], str]
    available_languages: LanguageRowsGetter
    resolve_lang: LanguageResolver
    clear_i18n_cache: CacheClearer
    load_custom_skill_manifests: CustomSkillManifestLoader
    custom_skill_file: CustomSkillFileResolver
    save_custom_skill_manifest: CustomSkillSaver
    refresh_skill_trigger_index: TriggerIndexBuilder
    format_skill_routing_info: SkillRoutingInfoFormatter
    suggest_skill_keywords_with_llm: KeywordSuggester

def register_config_routes(app: FastAPI, deps: ConfigRouteDeps) -> None:
    TEMPLATES = deps.templates
    BASE_DIR = deps.base_dir
    ERROR_INTERPRETER_PATH = deps.error_interpreter_path
    LLM_PROVIDER_PRESETS = deps.llm_provider_presets
    EMBEDDING_PROVIDER_PRESETS = deps.embedding_provider_presets
    AUTH_COOKIE = deps.auth_cookie
    USERNAME_COOKIE = deps.username_cookie
    MEMORY_COLLECTION_COOKIE = deps.memory_collection_cookie
    get_auth_session_max_age_seconds = deps.get_auth_session_max_age_seconds

    settings = _DynamicProxy(deps.get_settings)
    pipeline = _DynamicProxy(deps.get_pipeline)

    _get_username_from_request = deps.get_username_from_request
    _get_auth_session_from_request = deps.get_auth_session_from_request
    _sanitize_role = deps.sanitize_role
    _sanitize_username = deps.sanitize_username
    _sanitize_connection_name = deps.sanitize_connection_name
    _sanitize_skill_id = deps.sanitize_skill_id
    _sanitize_profile_name = deps.sanitize_profile_name
    _default_memory_collection_for_user = deps.default_memory_collection_for_user
    _encode_auth_session = deps.encode_auth_session
    _get_auth_manager = deps.get_auth_manager
    _active_admin_count = deps.active_admin_count
    _read_raw_config = deps.read_raw_config
    _write_raw_config = deps.write_raw_config
    _reload_runtime = deps.reload_runtime
    _read_error_interpreter_raw = deps.read_error_interpreter_raw
    _parse_lines = deps.parse_lines
    _is_ollama_model = deps.is_ollama_model
    _resolve_prompt_file = deps.resolve_prompt_file
    _list_prompt_files = deps.list_prompt_files
    _list_editable_files = deps.list_editable_files
    _resolve_edit_file = deps.resolve_edit_file
    _list_file_editor_entries = deps.list_file_editor_entries
    _resolve_file_editor_file = deps.resolve_file_editor_file
    _load_models_from_api_base = deps.load_models_from_api_base
    _get_profiles = deps.get_profiles
    _get_active_profile_name = deps.get_active_profile_name
    _set_active_profile = deps.set_active_profile
    _get_secure_store = deps.get_secure_store
    _lang_flag = deps.lang_flag
    _lang_label = deps.lang_label
    _load_custom_skill_manifests = deps.load_custom_skill_manifests
    _custom_skill_file = deps.custom_skill_file
    _save_custom_skill_manifest = deps.save_custom_skill_manifest
    _refresh_skill_trigger_index = deps.refresh_skill_trigger_index
    _format_skill_routing_info = deps.format_skill_routing_info
    _suggest_skill_keywords_with_llm = deps.suggest_skill_keywords_with_llm

    _connection_admin_helpers = ConnectionAdminHelpers(
        ConnectionAdminHelperDeps(
            connection_admin_specs=CONNECTION_ADMIN_SPECS,
            connection_edit_page=connection_edit_page,
            connection_ref_query_param=connection_ref_query_param,
            normalize_connection_kind=normalize_connection_kind,
            delete_connection_health=delete_connection_health,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            get_secure_store=_get_secure_store,
            sanitize_connection_name=_sanitize_connection_name,
            settings=settings,
            pipeline=pipeline,
        )
    )
    _get_connection_delete_spec = _connection_admin_helpers.get_connection_delete_spec
    _trigger_connection_routing_refresh = _connection_admin_helpers.trigger_connection_routing_refresh
    _delete_connection_profile = _connection_admin_helpers.delete_connection_profile
    _prepare_connection_save = _connection_admin_helpers.prepare_connection_save
    _finalize_connection_save = _connection_admin_helpers.finalize_connection_save

    _config_navigation_helpers = build_config_navigation_helpers()
    _cookie_name_for_request = _config_navigation_helpers.cookie_name_for_request
    _cookie_scope_for_request = _config_navigation_helpers.cookie_scope_for_request
    _sanitize_return_to = _config_navigation_helpers.sanitize_return_to
    _resolve_return_to = _config_navigation_helpers.resolve_return_to
    _redirect_with_return_to = _config_navigation_helpers.redirect_with_return_to
    _set_logical_back_url = _config_navigation_helpers.set_logical_back_url

    _config_profile_helpers = build_config_profile_helpers(
        ConfigProfileHelperDeps(
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            sanitize_connection_name=_sanitize_connection_name,
            get_active_profile_name=_get_active_profile_name,
            settings=settings,
            pipeline=pipeline,
        )
    )
    _friendly_route_error = _config_profile_helpers.friendly_route_error
    _friendly_ssh_setup_error = _config_profile_helpers.friendly_ssh_setup_error
    _embedding_memory_guard_context = _config_profile_helpers.embedding_memory_guard_context
    _guard_embedding_switch = _config_profile_helpers.guard_embedding_switch
    _connection_saved_test_info = _config_profile_helpers.connection_saved_test_info
    _active_profile_runtime_meta = _config_profile_helpers.active_profile_runtime_meta
    _profile_test_redirect_url = _config_profile_helpers.profile_test_redirect_url
    _profile_test_result_message = _config_profile_helpers.profile_test_result_message
    _import_sample_connection_manifest = _config_profile_helpers.import_sample_connection_manifest

    def _msg(lang: str, de: str, en: str) -> str:
        return _config_profile_helpers.msg(lang, de, en)

    class _I18NProxy:
        def available_languages(self) -> list[str]:
            return deps.available_languages()

        def resolve_lang(self, code: str, default_lang: str = "de") -> str:
            return deps.resolve_lang(code, default_lang)

        def clear_cache(self) -> None:
            deps.clear_i18n_cache()

    I18N = _I18NProxy()

    prompts_root = (BASE_DIR / "prompts").resolve()
    skills_root = (BASE_DIR / "aria" / "skills").resolve()

    _connection_reader_helpers = build_connection_reader_helpers(
        ConnectionReaderHelperDeps(
            base_dir=BASE_DIR,
            pipeline=pipeline,
            read_raw_config=_read_raw_config,
            get_secure_store=_get_secure_store,
            sanitize_connection_name=_sanitize_connection_name,
            normalize_rss_feed_url_for_dedupe=_normalize_rss_feed_url_for_dedupe,
            read_connection_metadata=_read_connection_metadata,
            resolve_searxng_base_url=resolve_searxng_base_url,
            suggest_connection_metadata_with_llm=suggest_connection_metadata_with_llm,
            connection_metadata_is_sparse=connection_metadata_is_sparse,
            web_metadata_headers=_WEB_METADATA_HEADERS,
            rss_metadata_headers=_RSS_METADATA_HEADERS,
        )
    )
    _read_ssh_connections = _connection_reader_helpers.read_ssh_connections
    _read_discord_connections = _connection_reader_helpers.read_discord_connections
    _read_sftp_connections = _connection_reader_helpers.read_sftp_connections
    _read_smb_connections = _connection_reader_helpers.read_smb_connections
    _read_webhook_connections = _connection_reader_helpers.read_webhook_connections
    _read_email_connections = _connection_reader_helpers.read_email_connections
    _read_imap_connections = _connection_reader_helpers.read_imap_connections
    _read_http_api_connections = _connection_reader_helpers.read_http_api_connections
    _read_google_calendar_connections = _connection_reader_helpers.read_google_calendar_connections
    _read_rss_poll_interval_minutes = _connection_reader_helpers.read_rss_poll_interval_minutes
    _suggest_rss_metadata_with_llm = _connection_reader_helpers.suggest_rss_metadata_with_llm
    _suggest_ssh_metadata_with_llm = _connection_reader_helpers.suggest_ssh_metadata_with_llm
    _autofill_service_connection_metadata = _connection_reader_helpers.autofill_service_connection_metadata
    _suggest_website_metadata_with_llm = _connection_reader_helpers.suggest_website_metadata_with_llm
    _autofill_website_connection_metadata = _connection_reader_helpers.autofill_website_connection_metadata
    _read_rss_connections = _connection_reader_helpers.read_rss_connections
    _read_website_connections = _connection_reader_helpers.read_website_connections
    _read_searxng_connections = _connection_reader_helpers.read_searxng_connections
    _read_mqtt_connections = _connection_reader_helpers.read_mqtt_connections
    _next_rss_import_ref = _connection_reader_helpers.next_rss_import_ref

    _connections_surface_path = build_surface_path_resolver(
        sanitize_return_to=_sanitize_return_to,
        allowed_paths={"/connections", "/connections/status", "/connections/types", "/connections/templates"},
        fallback="/connections",
    )

    _config_surface_path = build_surface_path_resolver(
        sanitize_return_to=_sanitize_return_to,
        allowed_paths={"/config", "/config/intelligence", "/config/persona", "/config/access", "/config/operations", "/config/workbench"},
        fallback="/config",
    )

    def _format_config_info_message(lang: str, info: str) -> str:
        return format_config_info_message(lang, info, msg=_msg)

    _build_config_overview_checks = build_config_overview_checks_helper(
        ConfigOverviewHelperDeps(read_raw_config=_read_raw_config, msg=_msg)
    )

    _config_support_helpers = build_config_support_helpers(
        ConfigSupportHelperDeps(
            base_dir=BASE_DIR,
            sample_guardrails_dir=SAMPLE_GUARDRAILS_DIR,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            sanitize_connection_name=_sanitize_connection_name,
            sanitize_reference_name_local=sanitize_reference_name_local,
            msg=_msg,
            guardrail_is_compatible=guardrail_is_compatible,
            ssh_keys_dir_impl=_ssh_keys_dir_impl,
            ensure_ssh_keypair_impl=_ensure_ssh_keypair_impl,
            perform_ssh_key_exchange_impl=_perform_ssh_key_exchange_impl,
            prompts_root=prompts_root,
            skills_root=skills_root,
        )
    )
    _import_sample_guardrail_manifest = _config_support_helpers.import_sample_guardrail_manifest
    _ssh_keys_dir = _config_support_helpers.ssh_keys_dir
    _ensure_ssh_keypair = _config_support_helpers.ensure_ssh_keypair
    _file_affects_runtime = _config_support_helpers.file_affects_runtime
    _save_text_file_and_maybe_reload = _config_support_helpers.save_text_file_and_maybe_reload
    _perform_ssh_key_exchange = _config_support_helpers.perform_ssh_key_exchange
    _read_guardrails = _config_support_helpers.read_guardrails
    _build_guardrail_ref_options = _config_support_helpers.build_guardrail_ref_options

    _config_surface_router = ConfigSurfaceRouter(
        ConfigSurfaceRouteDeps(
            templates=TEMPLATES,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            set_logical_back_url=_set_logical_back_url,
            config_surface_path=_config_surface_path,
            build_config_overview_checks=_build_config_overview_checks,
            format_config_info_message=_format_config_info_message,
            msg=_msg,
            get_secure_store=_get_secure_store,
            resolve_update_helper_config=lambda *, secure_store=None: resolve_update_helper_config(secure_store=secure_store),
            fetch_update_helper_status=lambda helper_config, timeout=1.2: fetch_update_helper_status(helper_config, timeout=timeout),
            trigger_update_helper_service_restart=lambda helper_config, service, timeout=2.5: trigger_update_helper_service_restart(helper_config, service, timeout=timeout),
        )
    )
    _build_config_page_context = _config_surface_router.build_config_page_context
    _render_config_surface = _config_surface_router.render_config_surface
    register_config_surface_routes(app, _config_surface_router)
    register_config_persona_routes(
        app,
        ConfigPersonaRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            lang_cookie=deps.lang_cookie,
            get_settings=lambda: settings,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            build_config_page_context=_build_config_page_context,
            redirect_with_return_to=_redirect_with_return_to,
            friendly_route_error=_friendly_route_error,
            msg=_msg,
            cookie_name_for_request=_cookie_name_for_request,
            list_prompt_files=_list_prompt_files,
            resolve_prompt_file=_resolve_prompt_file,
            save_text_file_and_maybe_reload=_save_text_file_and_maybe_reload,
            lang_flag=_lang_flag,
            lang_label=_lang_label,
            available_languages=I18N.available_languages,
            resolve_lang=I18N.resolve_lang,
            clear_i18n_cache=I18N.clear_cache,
        ),
    )
    register_config_operations_detail_routes(
        app,
        ConfigOperationsDetailRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            error_interpreter_path=ERROR_INTERPRETER_PATH,
            auth_cookie=deps.auth_cookie,
            username_cookie=deps.username_cookie,
            memory_collection_cookie=deps.memory_collection_cookie,
            get_settings=lambda: settings,
            get_pipeline=lambda: pipeline,
            build_config_page_context=_build_config_page_context,
            redirect_with_return_to=_redirect_with_return_to,
            friendly_route_error=_friendly_route_error,
            msg=_msg,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            get_secure_store=_get_secure_store,
            reload_runtime=_reload_runtime,
            refresh_skill_trigger_index=_refresh_skill_trigger_index,
            apply_factory_reset_to_raw_config=_apply_factory_reset_to_raw_config,
            wipe_directory_contents=_wipe_directory_contents,
            clear_qdrant_factory_data=_clear_qdrant_factory_data,
            cookie_name_for_request=_cookie_name_for_request,
        ),
    )
    register_config_access_detail_routes(
        app,
        ConfigAccessDetailRouteDeps(
            templates=TEMPLATES,
            auth_cookie=deps.auth_cookie,
            username_cookie=deps.username_cookie,
            memory_collection_cookie=deps.memory_collection_cookie,
            get_settings=lambda: settings,
            get_auth_manager=_get_auth_manager,
            get_auth_session_from_request=_get_auth_session_from_request,
            sanitize_username=_sanitize_username,
            sanitize_role=_sanitize_role,
            sanitize_connection_name=_sanitize_connection_name,
            build_config_page_context=_build_config_page_context,
            redirect_with_return_to=_redirect_with_return_to,
            friendly_route_error=_friendly_route_error,
            msg=_msg,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            active_admin_count=_active_admin_count,
            read_guardrails=_read_guardrails,
            build_guardrail_ref_options=_build_guardrail_ref_options,
            build_sample_guardrail_rows=_build_sample_guardrail_rows,
            import_sample_guardrail_manifest=_import_sample_guardrail_manifest,
            split_guardrail_terms=_split_guardrail_terms,
            format_session_timeout_label=format_session_timeout_label,
            default_memory_collection_for_user=_default_memory_collection_for_user,
            encode_auth_session=_encode_auth_session,
            get_auth_session_max_age_seconds=get_auth_session_max_age_seconds,
            cookie_name_for_request=_cookie_name_for_request,
            cookie_scope_for_request=_cookie_scope_for_request,
        ),
    )
    register_config_routing_detail_routes(
        app,
        ConfigRoutingDetailRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            get_settings=lambda: settings,
            get_pipeline=lambda: pipeline,
            get_auth_session_from_request=_get_auth_session_from_request,
            sanitize_role=_sanitize_role,
            sanitize_skill_id=_sanitize_skill_id,
            build_config_page_context=_build_config_page_context,
            redirect_with_return_to=_redirect_with_return_to,
            msg=_msg,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            parse_lines=_parse_lines,
            set_logical_back_url=lambda request: _set_logical_back_url(request, fallback="/config/workbench"),
            load_custom_skill_manifests=_load_custom_skill_manifests,
            custom_skill_file=_custom_skill_file,
            save_custom_skill_manifest=_save_custom_skill_manifest,
            refresh_skill_trigger_index=_refresh_skill_trigger_index,
            format_skill_routing_info=_format_skill_routing_info,
            suggest_skill_keywords_with_llm=_suggest_skill_keywords_with_llm,
            build_connection_routing_index_status=build_connection_routing_index_status,
            test_connection_routing_query=test_connection_routing_query,
            rebuild_connection_routing_index=rebuild_connection_routing_index,
        ),
    )
    register_config_intelligence_workbench_routes(
        app,
        ConfigIntelligenceWorkbenchRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            error_interpreter_path=ERROR_INTERPRETER_PATH,
            llm_provider_presets=LLM_PROVIDER_PRESETS,
            embedding_provider_presets=EMBEDDING_PROVIDER_PRESETS,
            get_settings=lambda: settings,
            get_pipeline=lambda: pipeline,
            get_username_from_request=_get_username_from_request,
            sanitize_profile_name=_sanitize_profile_name,
            is_ollama_model=_is_ollama_model,
            build_config_page_context=_build_config_page_context,
            redirect_with_return_to=_redirect_with_return_to,
            friendly_route_error=_friendly_route_error,
            msg=_msg,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            get_profiles=_get_profiles,
            get_active_profile_name=_get_active_profile_name,
            set_active_profile=_set_active_profile,
            get_secure_store=_get_secure_store,
            load_models_from_api_base=_load_models_from_api_base,
            set_logical_back_url=lambda request: _set_logical_back_url(request, fallback="/config"),
            config_surface_path=_config_surface_path,
            format_config_info_message=_format_config_info_message,
            active_profile_runtime_meta=_active_profile_runtime_meta,
            embedding_memory_guard_context=_embedding_memory_guard_context,
            guard_embedding_switch=_guard_embedding_switch,
            profile_test_redirect_url=_profile_test_redirect_url,
            profile_test_result_message=_profile_test_result_message,
            probe_llm=lambda *args, **kwargs: probe_llm(*args, **kwargs),
            probe_embeddings=lambda *args, **kwargs: probe_embeddings(*args, **kwargs),
            list_file_editor_entries=_list_file_editor_entries,
            resolve_edit_file=_resolve_edit_file,
            resolve_file_editor_file=_resolve_file_editor_file,
            build_editor_entries_from_paths=build_editor_entries_from_paths,
            read_error_interpreter_raw=_read_error_interpreter_raw,
            save_text_file_and_maybe_reload=_save_text_file_and_maybe_reload,
        ),
    )

    _build_connections_page_context = build_connections_page_context_helper(
        ConnectionsSurfaceHelperDeps(
            base_dir=BASE_DIR,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            set_logical_back_url=_set_logical_back_url,
            msg=_msg,
            format_config_info_message=_format_config_info_message,
            attach_mixed_connection_edit_urls=_attach_mixed_connection_edit_urls,
            connections_surface_path=_connections_surface_path,
            read_searxng_connections=_read_searxng_connections,
            build_sample_connection_rows=_build_sample_connection_rows,
            build_settings_connection_status_rows=build_settings_connection_status_rows,
            connection_menu_rows=connection_menu_rows,
            probe_searxng_stack_service=probe_searxng_stack_service,
        )
    )

    _connection_page_helpers = build_connection_page_helpers(
        ConnectionPageHelperDeps(
            base_dir=BASE_DIR,
            templates=TEMPLATES,
            get_settings=lambda: settings,
            get_username_from_request=_get_username_from_request,
            set_logical_back_url=_set_logical_back_url,
            sanitize_connection_name=_sanitize_connection_name,
            build_connection_ref_options=_build_connection_ref_options,
            build_connection_status_rows=build_connection_status_rows,
            attach_connection_edit_urls=_attach_connection_edit_urls,
            connection_template_name=connection_template_name,
        )
    )
    _build_generic_connections_context = _connection_page_helpers.build_generic_connections_context
    _base_connections_page_context = _connection_page_helpers.base_connections_page_context
    _render_connection_page = _connection_page_helpers.render_connection_page

    _connection_context_helpers = build_connection_context_helpers(
        ConnectionContextHelperDeps(
            base_dir=BASE_DIR,
            sanitize_connection_name=_sanitize_connection_name,
            build_generic_connections_context=_build_generic_connections_context,
            build_connection_ref_options=_build_connection_ref_options,
            build_connection_intro=_build_connection_intro,
            build_connection_summary_cards=_build_connection_summary_cards,
            build_connection_status_block=_build_connection_status_block,
            build_schema_form_fields=_build_schema_form_fields,
            build_guardrail_ref_options=_build_guardrail_ref_options,
            attach_connection_edit_urls=_attach_connection_edit_urls,
            build_connection_status_rows=build_connection_status_rows,
            read_guardrails=_read_guardrails,
            read_ssh_connections=_read_ssh_connections,
            read_discord_connections=_read_discord_connections,
            read_sftp_connections=_read_sftp_connections,
            read_smb_connections=_read_smb_connections,
            read_webhook_connections=_read_webhook_connections,
            read_email_connections=_read_email_connections,
            read_imap_connections=_read_imap_connections,
            read_http_api_connections=_read_http_api_connections,
            read_google_calendar_connections=_read_google_calendar_connections,
            read_rss_poll_interval_minutes=_read_rss_poll_interval_minutes,
            read_rss_connections=_read_rss_connections,
            read_website_connections=_read_website_connections,
            read_searxng_connections=_read_searxng_connections,
            read_mqtt_connections=_read_mqtt_connections,
            probe_searxng_stack_service=probe_searxng_stack_service,
            resolve_searxng_base_url=resolve_searxng_base_url,
            searxng_category_options=_SEARXNG_CATEGORY_OPTIONS,
            searxng_engine_options=_SEARXNG_ENGINE_OPTIONS,
        )
    )
    _build_ssh_connections_context = _connection_context_helpers.build_ssh_connections_context
    _build_discord_connections_context = _connection_context_helpers.build_discord_connections_context
    _build_sftp_connections_context = _connection_context_helpers.build_sftp_connections_context
    _build_smb_connections_context = _connection_context_helpers.build_smb_connections_context
    _build_webhook_connections_context = _connection_context_helpers.build_webhook_connections_context
    _build_email_connections_context = _connection_context_helpers.build_email_connections_context
    _build_imap_connections_context = _connection_context_helpers.build_imap_connections_context
    _build_http_api_connections_context = _connection_context_helpers.build_http_api_connections_context
    _build_google_calendar_connections_context = _connection_context_helpers.build_google_calendar_connections_context
    _build_searxng_connections_context = _connection_context_helpers.build_searxng_connections_context
    _build_rss_connections_context = _connection_context_helpers.build_rss_connections_context
    _build_website_connections_context = _connection_context_helpers.build_website_connections_context
    _build_mqtt_connections_context = _connection_context_helpers.build_mqtt_connections_context













    register_connection_metadata_routes(
        app,
        ConnectionMetadataRouteDeps(
            sanitize_connection_name=_sanitize_connection_name,
            normalize_rss_feed_url_for_dedupe=_normalize_rss_feed_url_for_dedupe,
            suggest_ssh_metadata_with_llm=_suggest_ssh_metadata_with_llm,
            suggest_rss_metadata_with_llm=_suggest_rss_metadata_with_llm,
            suggest_website_metadata_with_llm=_suggest_website_metadata_with_llm,
            msg=_msg,
        ),
    )

    register_connections_surface_routes(
        app,
        ConnectionsSurfaceRouteDeps(
            templates=TEMPLATES,
            build_connections_page_context=_build_connections_page_context,
            connections_surface_path=_connections_surface_path,
            import_sample_connection_manifest=_import_sample_connection_manifest,
            msg=_msg,
        ),
    )
    register_connection_detail_routes(
        app,
        ConnectionDetailRouteDeps(
            templates=TEMPLATES,
            base_dir=BASE_DIR,
            render_connection_page=_render_connection_page,
            base_connections_page_context=_base_connections_page_context,
            build_ssh_connections_context=_build_ssh_connections_context,
            build_discord_connections_context=_build_discord_connections_context,
            build_sftp_connections_context=_build_sftp_connections_context,
            build_smb_connections_context=_build_smb_connections_context,
            build_webhook_connections_context=_build_webhook_connections_context,
            build_email_connections_context=_build_email_connections_context,
            build_imap_connections_context=_build_imap_connections_context,
            build_http_api_connections_context=_build_http_api_connections_context,
            build_google_calendar_connections_context=_build_google_calendar_connections_context,
            build_searxng_connections_context=_build_searxng_connections_context,
            build_rss_connections_context=_build_rss_connections_context,
            build_website_connections_context=_build_website_connections_context,
            build_mqtt_connections_context=_build_mqtt_connections_context,
            build_rss_status_groups=build_rss_status_groups,
            load_cached_rss_status_groups=load_cached_rss_status_groups,
            save_cached_rss_status_groups=save_cached_rss_status_groups,
            connection_template_name=connection_template_name,
            pipeline=pipeline,
            msg=_msg,
        ),
    )

    _connection_mutation_handlers = build_connection_mutation_handlers(
        ConnectionMutationHandlerDeps(
            base_dir=BASE_DIR,
            msg=_msg,
            read_raw_config=_read_raw_config,
            write_raw_config=_write_raw_config,
            reload_runtime=_reload_runtime,
            redirect_with_return_to=_redirect_with_return_to,
            sanitize_connection_name=_sanitize_connection_name,
            delete_connection_profile=_delete_connection_profile,
            get_connection_delete_spec=_get_connection_delete_spec,
            trigger_connection_routing_refresh=_trigger_connection_routing_refresh,
            prepare_connection_save=_prepare_connection_save,
            read_guardrails=_read_guardrails,
            guardrail_is_compatible=guardrail_is_compatible,
            autofill_service_connection_metadata=_autofill_service_connection_metadata,
            build_connection_metadata=_build_connection_metadata,
            connection_saved_test_info=_connection_saved_test_info,
            perform_ssh_key_exchange=_perform_ssh_key_exchange,
            derive_matching_sftp_ref=_derive_matching_sftp_ref,
            finalize_connection_save=_finalize_connection_save,
            build_connection_status_row=build_connection_status_row,
            friendly_ssh_setup_error=_friendly_ssh_setup_error,
            read_ssh_connections=_read_ssh_connections,
            read_discord_connections=_read_discord_connections,
            read_sftp_connections=_read_sftp_connections,
            read_smb_connections=_read_smb_connections,
            read_webhook_connections=_read_webhook_connections,
            read_email_connections=_read_email_connections,
            read_imap_connections=_read_imap_connections,
            read_http_api_connections=_read_http_api_connections,
            read_google_calendar_connections=_read_google_calendar_connections,
            read_searxng_connections=_read_searxng_connections,
            read_website_connections=_read_website_connections,
            normalize_rss_feed_url_for_dedupe=_normalize_rss_feed_url_for_dedupe,
            read_rss_poll_interval_minutes=_read_rss_poll_interval_minutes,
            read_rss_connections=_read_rss_connections,
            build_opml_document=build_opml_document,
            parse_opml_feeds=parse_opml_feeds,
            next_rss_import_ref=_next_rss_import_ref,
            is_valid_csrf_submission=is_valid_csrf_submission,
            read_mqtt_connections=_read_mqtt_connections,
            ssh_keys_dir=_ssh_keys_dir,
            ensure_ssh_keypair=_ensure_ssh_keypair,
            autofill_website_connection_metadata=_autofill_website_connection_metadata,
        )
    )

    register_connection_mutation_routes(
        app,
        ConnectionMutationRouteDeps(
            rss_poll_interval_save=_connection_mutation_handlers.rss_poll_interval_save,
            connection_delete=_connection_mutation_handlers.connection_delete,
            ssh_save=_connection_mutation_handlers.ssh_save,
            discord_save=_connection_mutation_handlers.discord_save,
            sftp_save=_connection_mutation_handlers.sftp_save,
            smb_save=_connection_mutation_handlers.smb_save,
            webhook_save=_connection_mutation_handlers.webhook_save,
            smtp_save=_connection_mutation_handlers.smtp_save,
            imap_save=_connection_mutation_handlers.imap_save,
            http_api_save=_connection_mutation_handlers.http_api_save,
            google_calendar_save=_connection_mutation_handlers.google_calendar_save,
            searxng_save=_connection_mutation_handlers.searxng_save,
            rss_save=_connection_mutation_handlers.rss_save,
            website_save=_connection_mutation_handlers.website_save,
            rss_export_opml=_connection_mutation_handlers.rss_export_opml,
            rss_import_opml=_connection_mutation_handlers.rss_import_opml,
            rss_ping_now=_connection_mutation_handlers.rss_ping_now,
            mqtt_save=_connection_mutation_handlers.mqtt_save,
            ssh_keygen=_connection_mutation_handlers.ssh_keygen,
            ssh_key_exchange=_connection_mutation_handlers.ssh_key_exchange,
            ssh_test=_connection_mutation_handlers.ssh_test,
        ),
    )
