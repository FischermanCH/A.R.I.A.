from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from aria.modules import module_route_path
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.sftp_admin_ui.context import build_sftp_connections_context as provider_sftp_connections_context
from aria.modules.ssh_admin_ui.context import build_ssh_connections_context as provider_ssh_connections_context


_CONNECTION_CONTEXT_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _context_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CONNECTION_CONTEXT_I18N.t(language or "de", f"connection_context_helpers.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _connection_ui_path(module_id: str, route_path: str) -> str:
    resolved = module_route_path(module_id, route_path)
    if resolved is None:
        raise RuntimeError(f"{module_id} route is not registered: {route_path}")
    return resolved


@dataclass(frozen=True)
class ConnectionContextHelperDeps:
    base_dir: Path
    sanitize_connection_name: Callable[[str | None], str]
    build_generic_connections_context: Callable[..., dict[str, Any]]
    build_connection_ref_options: Callable[..., list[dict[str, Any]]]
    build_connection_intro: Callable[..., dict[str, Any]]
    build_connection_summary_cards: Callable[..., list[dict[str, Any]]]
    build_connection_status_block: Callable[..., dict[str, Any]]
    build_schema_form_fields: Callable[..., list[dict[str, Any]]]
    build_schema_toggle_sections: Callable[..., list[dict[str, Any]]]
    build_guardrail_ref_options: Callable[..., list[dict[str, str]]]
    attach_connection_edit_urls: Callable[..., list[dict[str, Any]]]
    build_connection_status_rows: Callable[..., list[dict[str, Any]]]
    read_guardrails: Callable[[], dict[str, dict[str, Any]]]
    read_ssh_connections: Callable[[], dict[str, dict[str, Any]]]
    read_discord_connections: Callable[[], dict[str, dict[str, Any]]]
    read_sftp_connections: Callable[[], dict[str, dict[str, Any]]]
    read_smb_connections: Callable[[], dict[str, dict[str, Any]]]
    read_webhook_connections: Callable[[], dict[str, dict[str, Any]]]
    read_email_connections: Callable[[], dict[str, dict[str, Any]]]
    read_imap_connections: Callable[[], dict[str, dict[str, Any]]]
    read_http_api_connections: Callable[[], dict[str, dict[str, Any]]]
    read_google_calendar_connections: Callable[[], dict[str, dict[str, Any]]]
    read_rss_poll_interval_minutes: Callable[..., int]
    read_rss_connections: Callable[[], dict[str, dict[str, Any]]]
    read_website_connections: Callable[[], dict[str, dict[str, Any]]]
    read_mqtt_connections: Callable[[], dict[str, dict[str, Any]]]


@dataclass(frozen=True)
class ConnectionContextHelperBundle:
    build_ssh_connections_context: Any
    build_discord_connections_context: Any
    build_sftp_connections_context: Any
    build_smb_connections_context: Any
    build_webhook_connections_context: Any
    build_email_connections_context: Any
    build_imap_connections_context: Any
    build_http_api_connections_context: Any
    build_google_calendar_connections_context: Any
    build_rss_connections_context: Any
    build_website_connections_context: Any
    build_mqtt_connections_context: Any


def _secret_status_card(
    *,
    label_key: str,
    label: str,
    secret_present: bool,
    connected_hint_key: str,
    connected_hint: str,
    optional_when_missing: bool = False,
    optional_hint_key: str = "config_conn.optional_auth_hint",
    optional_hint: str = "The connection can work without a token, but protected endpoints may ask for sign-in later.",
) -> dict[str, str]:
    if secret_present:
        return {
            "label_key": label_key,
            "label": label,
            "value": "connected",
            "value_key": "config_conn.connected",
            "hint_key": connected_hint_key,
            "hint": connected_hint,
        }
    if optional_when_missing:
        return {
            "label_key": label_key,
            "label": label,
            "value": "optional",
            "value_key": "config_conn.optional",
            "hint_key": optional_hint_key,
            "hint": optional_hint,
        }
    return {
        "label_key": label_key,
        "label": label,
        "value": "sign_in_needed",
        "value_key": "config_conn.sign_in_needed",
        "hint_key": "config_conn.sign_in_needed_hint",
        "hint": "ARIA still needs a login or stored secret before this connection can be used.",
    }


def build_connection_context_helpers(deps: ConnectionContextHelperDeps) -> ConnectionContextHelperBundle:
    BASE_DIR = deps.base_dir
    _sanitize_connection_name = deps.sanitize_connection_name
    _build_generic_connections_context = deps.build_generic_connections_context
    _build_connection_ref_options = deps.build_connection_ref_options
    _build_connection_intro = deps.build_connection_intro
    _build_connection_summary_cards = deps.build_connection_summary_cards
    _build_connection_status_block = deps.build_connection_status_block
    _build_schema_form_fields = deps.build_schema_form_fields
    _build_schema_toggle_sections = deps.build_schema_toggle_sections
    _build_guardrail_ref_options = deps.build_guardrail_ref_options
    _attach_connection_edit_urls = deps.attach_connection_edit_urls
    build_connection_status_rows = deps.build_connection_status_rows
    _read_guardrails = deps.read_guardrails
    _read_ssh_connections = deps.read_ssh_connections
    _read_discord_connections = deps.read_discord_connections
    _read_sftp_connections = deps.read_sftp_connections
    _read_smb_connections = deps.read_smb_connections
    _read_webhook_connections = deps.read_webhook_connections
    _read_email_connections = deps.read_email_connections
    _read_imap_connections = deps.read_imap_connections
    _read_http_api_connections = deps.read_http_api_connections
    _read_google_calendar_connections = deps.read_google_calendar_connections
    _read_rss_poll_interval_minutes = deps.read_rss_poll_interval_minutes
    _read_rss_connections = deps.read_rss_connections
    _read_website_connections = deps.read_website_connections
    _read_mqtt_connections = deps.read_mqtt_connections

    def _attach_guardrail_context(
        context: dict[str, Any],
        *,
        connection_kind: str,
        guardrail_rows: dict[str, dict[str, Any]],
    ) -> list[dict[str, str]]:
        options = _build_guardrail_ref_options(guardrail_rows, connection_kind=connection_kind, lang=str(context.get("lang", "de") or "de"))
        if connection_kind in {"sftp", "smb"}:
            hint_key = "config_security.file_guardrail_hint"
            hint = "File guardrails inspect operation and path before ARIA reads, writes, or lists directories."
        elif connection_kind in {"webhook", "http_api"}:
            hint_key = "config_security.http_guardrail_hint"
            hint = "HTTP guardrails inspect target URL, method, and relevant request fragments before ARIA executes the request."
        else:
            hint_key = "config_security.guardrails_subtitle"
            hint = "Reusable security profiles for individual services. Guardrails can be attached to compatible connections and extended modularly later."
        context["connection_guardrail_ref_options"] = options
        context["connection_guardrail_hint_key"] = hint_key
        context["connection_guardrail_hint"] = hint
        return options

    def _attach_connection_intro_and_status(
        context: dict[str, Any],
        *,
        kind: str,
        refs_key: str,
        healthy_key: str,
        issue_key: str,
        rows_key: str,
        extra_cards: list[dict[str, Any]] | None = None,
    ) -> None:
        context["connection_intro"] = _build_connection_intro(
            kind=kind,
            summary_cards=_build_connection_summary_cards(
                kind=kind,
                profiles=len(context.get(refs_key, [])),
                healthy=int(context.get(healthy_key, 0) or 0),
                issues=int(context.get(issue_key, 0) or 0),
                extra_cards=extra_cards or [],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind=kind,
            rows=list(context.get(rows_key, [])),
        )

    def _build_ssh_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        return provider_ssh_connections_context(
            base_dir=BASE_DIR,
            sanitize_connection_name=_sanitize_connection_name,
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
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            lang=lang,
        )

    def _build_discord_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "discord",
            _read_discord_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="discord_refs",
            selected_ref_key="selected_discord_ref",
            selected_key="selected_discord",
            rows_key="discord_status_rows",
            healthy_key="discord_healthy_count",
            issue_key="discord_issue_count",
            test_status_key="discord_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="discord",
            refs_key="discord_refs",
            healthy_key="discord_healthy_count",
            issue_key="discord_issue_count",
            rows_key="discord_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.webhook_status",
                    label="Webhook status",
                    secret_present=bool(context.get("selected_discord", {}).get("webhook_present")),
                    connected_hint_key="config_conn.discord_webhook_hint",
                    connected_hint="Webhook URL is stored in the secure store, not in config.yaml.",
                ),
            ],
        )
        context["discord_edit_form_fields"] = _build_schema_form_fields(
            kind="discord",
            values=dict(context.get("selected_discord", {})),
            prefix="discord_edit",
            ref_value=str(context.get("selected_discord_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. alerts"},
            required_fields={"timeout_seconds"},
            secrets_with_hints={"webhook_url": "The webhook URL is stored in the secure store and never written into config.yaml. Leave it empty to keep the existing secret."},
            ordered_fields=["timeout_seconds", "webhook_url"],
        )
        context["discord_new_form_fields"] = _build_schema_form_fields(
            kind="discord",
            values={"timeout_seconds": 10},
            prefix="discord_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. alerts"},
            required_fields={"timeout_seconds", "webhook_url"},
            secrets_with_hints={"webhook_url": "The webhook URL is stored in the secure store and never written into config.yaml. Leave it empty to keep the existing secret."},
            ordered_fields=["timeout_seconds", "webhook_url"],
        )
        context["discord_edit_toggle_sections"] = _build_schema_toggle_sections(
            kind="discord",
            values=dict(context.get("selected_discord", {})),
            prefix="discord_edit",
            section_names=["behaviour", "events"],
        )
        context["discord_new_toggle_sections"] = _build_schema_toggle_sections(
            kind="discord",
            values={"send_test_messages": True, "allow_skill_messages": True},
            prefix="discord_new",
            section_names=["behaviour", "events"],
        )
        return context

    def _build_sftp_connections_context(
        selected_ref_raw: str = "",
        test_status: str = "",
        copy_from_ssh_ref: str = "",
        lang: str = "de",
    ) -> dict[str, Any]:
        return provider_sftp_connections_context(
            base_dir=BASE_DIR,
            sanitize_connection_name=_sanitize_connection_name,
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
            read_sftp_connections=_read_sftp_connections,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            copy_from_ssh_ref=copy_from_ssh_ref,
            lang=lang,
        )

    def _build_smb_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        context = _build_generic_connections_context(
            "smb",
            _read_smb_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="smb_refs",
            selected_ref_key="selected_smb_ref",
            selected_key="selected_smb",
            rows_key="smb_status_rows",
            healthy_key="smb_healthy_count",
            issue_key="smb_issue_count",
            test_status_key="smb_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="smb",
            refs_key="smb_refs",
            healthy_key="smb_healthy_count",
            issue_key="smb_issue_count",
            rows_key="smb_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.password_status",
                    label="Password status",
                    secret_present=bool(context.get("selected_smb", {}).get("password_present")),
                    connected_hint_key="config_conn.smb_password_hint",
                    connected_hint="Password is stored in the secure store, not in config.yaml.",
                ),
            ],
        )
        context["smb_edit_form_fields"] = _build_schema_form_fields(
            kind="smb",
            values=dict(context.get("selected_smb", {})),
            prefix="smb_edit",
            ref_value=str(context.get("selected_smb_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. team-share", "host": "nas.example.local", "share": "documents", "user": "backup", "root_path": "/"},
            required_fields={"host", "share", "port", "user", "timeout_seconds"},
            secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
            ordered_fields=["host", "share", "port", "user", "timeout_seconds", "root_path", "password"],
        )
        context["smb_new_form_fields"] = _build_schema_form_fields(
            kind="smb",
            values={"port": 445, "timeout_seconds": 10},
            prefix="smb_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. team-share", "host": "nas.example.local", "share": "documents", "user": "backup", "root_path": "/"},
            required_fields={"host", "share", "port", "user", "timeout_seconds", "password"},
            secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
            ordered_fields=["host", "share", "port", "user", "timeout_seconds", "root_path", "password"],
        )
        context["lang"] = lang
        context["smb_guardrail_ref_options"] = _attach_guardrail_context(context, connection_kind="smb", guardrail_rows=guardrail_rows)
        return context

    def _build_webhook_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        context = _build_generic_connections_context(
            "webhook",
            _read_webhook_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="webhook_refs",
            selected_ref_key="selected_webhook_ref",
            selected_key="selected_webhook",
            rows_key="webhook_status_rows",
            healthy_key="webhook_healthy_count",
            issue_key="webhook_issue_count",
            test_status_key="webhook_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="webhook",
            refs_key="webhook_refs",
            healthy_key="webhook_healthy_count",
            issue_key="webhook_issue_count",
            rows_key="webhook_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.webhook_status",
                    label="Webhook status",
                    secret_present=bool(context.get("selected_webhook", {}).get("url_present")),
                    connected_hint_key="config_conn.webhook_secret_hint",
                    connected_hint="The webhook URL is stored in the secure store, not in config.yaml.",
                ),
            ],
        )
        context["webhook_edit_form_fields"] = _build_schema_form_fields(
            kind="webhook",
            values=dict(context.get("selected_webhook", {})),
            prefix="webhook_edit",
            ref_value=str(context.get("selected_webhook_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. incident-hook", "url": "https://example.org/webhook", "content_type": "application/json"},
            required_fields={"timeout_seconds", "method", "content_type"},
            select_options={"method": ["POST", "PUT", "PATCH"]},
            secrets_with_hints={"url": "The webhook URL is stored in the secure store, not in config.yaml."},
            ordered_fields=["timeout_seconds", "method", "content_type", "url"],
        )
        context["webhook_new_form_fields"] = _build_schema_form_fields(
            kind="webhook",
            values={"timeout_seconds": 10, "method": "POST", "content_type": "application/json"},
            prefix="webhook_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. incident-hook", "url": "https://example.org/webhook", "content_type": "application/json"},
            required_fields={"timeout_seconds", "method", "content_type", "url"},
            select_options={"method": ["POST", "PUT", "PATCH"]},
            secrets_with_hints={"url": "The webhook URL is stored in the secure store, not in config.yaml."},
            ordered_fields=["timeout_seconds", "method", "content_type", "url"],
        )
        context["lang"] = lang
        context["webhook_guardrail_ref_options"] = _attach_guardrail_context(context, connection_kind="webhook", guardrail_rows=guardrail_rows)
        return context

    def _build_email_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "email",
            _read_email_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="email_refs",
            selected_ref_key="selected_email_ref",
            selected_key="selected_email",
            rows_key="email_status_rows",
            healthy_key="email_healthy_count",
            issue_key="email_issue_count",
            test_status_key="email_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="email",
            refs_key="email_refs",
            healthy_key="email_healthy_count",
            issue_key="email_issue_count",
            rows_key="email_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.password_status",
                    label="Password status",
                    secret_present=bool(context.get("selected_email", {}).get("password_present")),
                    connected_hint_key="config_conn.email_password_hint",
                    connected_hint="Password is stored in the secure store, not in config.yaml.",
                ),
            ],
        )
        context["email_edit_form_fields"] = _build_schema_form_fields(
            kind="email",
            values=dict(context.get("selected_email", {})),
            prefix="email_edit",
            ref_value=str(context.get("selected_email_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. mail-alerts", "smtp_host": "smtp.example.org", "user": "alert@example.org"},
            required_fields={"smtp_host", "port", "user", "from_email", "timeout_seconds"},
            boolean_defaults={"starttls": True, "use_ssl": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["smtp_host", "port", "user", "from_email", "to_email", "timeout_seconds", "starttls", "use_ssl", "password"],
        )
        context["email_new_form_fields"] = _build_schema_form_fields(
            kind="email",
            values={"port": 587, "timeout_seconds": 10, "starttls": True},
            prefix="email_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. mail-alerts", "smtp_host": "smtp.example.org", "user": "alert@example.org"},
            required_fields={"smtp_host", "port", "user", "from_email", "timeout_seconds", "password"},
            boolean_defaults={"starttls": True, "use_ssl": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["smtp_host", "port", "user", "from_email", "to_email", "timeout_seconds", "starttls", "use_ssl", "password"],
        )
        return context

    def _build_imap_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "imap",
            _read_imap_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="imap_refs",
            selected_ref_key="selected_imap_ref",
            selected_key="selected_imap",
            rows_key="imap_status_rows",
            healthy_key="imap_healthy_count",
            issue_key="imap_issue_count",
            test_status_key="imap_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="imap",
            refs_key="imap_refs",
            healthy_key="imap_healthy_count",
            issue_key="imap_issue_count",
            rows_key="imap_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.password_status",
                    label="Password status",
                    secret_present=bool(context.get("selected_imap", {}).get("password_present")),
                    connected_hint_key="config_conn.imap_password_hint",
                    connected_hint="Password is stored in the secure store, not in config.yaml.",
                ),
            ],
        )
        context["imap_edit_form_fields"] = _build_schema_form_fields(
            kind="imap",
            values=dict(context.get("selected_imap", {})),
            prefix="imap_edit",
            ref_value=str(context.get("selected_imap_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. mail-inbox", "host": "imap.example.org", "user": "imap-user@example.org"},
            required_fields={"host", "port", "user", "mailbox", "timeout_seconds"},
            boolean_defaults={"use_ssl": True},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "mailbox", "timeout_seconds", "use_ssl", "password"],
        )
        context["imap_new_form_fields"] = _build_schema_form_fields(
            kind="imap",
            values={"port": 993, "mailbox": "INBOX", "timeout_seconds": 10, "use_ssl": True},
            prefix="imap_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. mail-inbox", "host": "imap.example.org", "user": "imap-user@example.org"},
            required_fields={"host", "port", "user", "mailbox", "timeout_seconds", "password"},
            boolean_defaults={"use_ssl": True},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "mailbox", "timeout_seconds", "use_ssl", "password"],
        )
        return context

    def _build_http_api_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        guardrail_rows = _read_guardrails()
        context = _build_generic_connections_context(
            "http_api",
            _read_http_api_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="http_api_refs",
            selected_ref_key="selected_http_api_ref",
            selected_key="selected_http_api",
            rows_key="http_api_status_rows",
            healthy_key="http_api_healthy_count",
            issue_key="http_api_issue_count",
            test_status_key="http_api_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="http_api",
            refs_key="http_api_refs",
            healthy_key="http_api_healthy_count",
            issue_key="http_api_issue_count",
            rows_key="http_api_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.token_status",
                    label="Token status",
                    secret_present=bool(context.get("selected_http_api", {}).get("auth_token_present")),
                    connected_hint_key="config_conn.http_api_token_hint",
                    connected_hint="Bearer token is stored in the secure store when provided.",
                    optional_when_missing=True,
                ),
            ],
        )
        context["http_api_edit_form_fields"] = _build_schema_form_fields(
            kind="http_api",
            values=dict(context.get("selected_http_api", {})),
            prefix="http_api_edit",
            ref_value=str(context.get("selected_http_api_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. inventory-api", "base_url": "https://api.example.org"},
            required_fields={"base_url", "health_path", "method", "timeout_seconds"},
            select_options={"method": ["GET", "POST", "HEAD"]},
            secrets_with_hints={"auth_token": "Bearer token is stored in the secure store when provided."},
            ordered_fields=["base_url", "health_path", "method", "timeout_seconds", "auth_token"],
        )
        context["http_api_new_form_fields"] = _build_schema_form_fields(
            kind="http_api",
            values={"health_path": "/", "method": "GET", "timeout_seconds": 10},
            prefix="http_api_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. inventory-api", "base_url": "https://api.example.org"},
            required_fields={"base_url", "health_path", "method", "timeout_seconds"},
            select_options={"method": ["GET", "POST", "HEAD"]},
            secrets_with_hints={"auth_token": "Bearer token is stored in the secure store when provided."},
            ordered_fields=["base_url", "health_path", "method", "timeout_seconds", "auth_token"],
        )
        context["lang"] = lang
        context["http_api_guardrail_ref_options"] = _attach_guardrail_context(context, connection_kind="http_api", guardrail_rows=guardrail_rows)
        return context

    def _build_google_calendar_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "google_calendar",
            _read_google_calendar_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="google_calendar_refs",
            selected_ref_key="selected_google_calendar_ref",
            selected_key="selected_google_calendar",
            rows_key="google_calendar_status_rows",
            healthy_key="google_calendar_healthy_count",
            issue_key="google_calendar_issue_count",
            test_status_key="google_calendar_test_status",
        )
        selected = dict(context.get("selected_google_calendar", {}))
        auth_ready = bool(selected.get("ical_url_present"))
        context["connection_intro"] = _build_connection_intro(
            kind="google_calendar",
            summary_cards=_build_connection_summary_cards(
                kind="google_calendar",
                profiles=len(context.get("google_calendar_refs", [])),
                healthy=int(context.get("google_calendar_healthy_count", 0) or 0),
                issues=int(context.get("google_calendar_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.calendar_target",
                        "label": "Calendar",
                        "value": str(selected.get("calendar_id", "")).strip() or "primary",
                        "value_key": "",
                        "hint_key": "config_conn.google_calendar_target_hint",
                        "hint": "The read-only iCal feed ARIA will query first.",
                    },
                    _secret_status_card(
                        label_key="config_conn.sign_in_status",
                        label="Sign-in status",
                        secret_present=auth_ready,
                        connected_hint_key="config_conn.google_calendar_auth_hint",
                        connected_hint="The secret iCal URL is stored in the secure store.",
                    ),
                ],
            ),
        )
        context["connection_status_block"] = _build_connection_status_block(
            kind="google_calendar",
            rows=list(context.get("google_calendar_status_rows", [])),
        )
        context["google_calendar_edit_form_fields"] = _build_schema_form_fields(
            kind="google_calendar",
            values=selected,
            prefix="google_calendar_edit",
            ref_value=str(context.get("selected_google_calendar_ref", "")).strip(),
            placeholders={
                "connection_ref": "z.B. primary-calendar",
                "ical_url": "https://calendar.google.com/calendar/ical/...",
            },
            required_fields={"ical_url", "timeout_seconds"},
            field_hints={
                "ical_url": _context_text(lang, "google_ical_url_hint", "Copy the Secret address in iCal format from Google Calendar > Settings > Integrate calendar."),
                "timeout_seconds": _context_text(lang, "google_timeout_hint", "Read-only probe timeout against Google in seconds."),
            },
            secrets_with_hints={
                "ical_url": "Stored in the secure store. Keep this link private.",
            },
            ordered_fields=["ical_url", "timeout_seconds"],
        )
        context["google_calendar_new_form_fields"] = _build_schema_form_fields(
            kind="google_calendar",
            values={"timeout_seconds": 10},
            prefix="google_calendar_new",
            ref_value="primary-calendar",
            placeholders={
                "connection_ref": "z.B. primary-calendar",
                "ical_url": "https://calendar.google.com/calendar/ical/...",
            },
            required_fields={"ical_url", "timeout_seconds"},
            field_hints={
                "ical_url": _context_text(lang, "google_ical_url_hint", "Copy the Secret address in iCal format from Google Calendar > Settings > Integrate calendar."),
                "timeout_seconds": _context_text(lang, "google_timeout_hint", "Read-only probe timeout against Google in seconds."),
            },
            secrets_with_hints={
                "ical_url": "Stored in the secure store. Keep this link private.",
            },
            ordered_fields=["ical_url", "timeout_seconds"],
        )
        return context

    def _build_rss_connections_context(
        selected_ref_raw: str = "",
        test_status: str = "",
        create_new: bool = False,
        lang: str = "de",
    ) -> dict[str, Any]:
        selected_ref_requested = bool(_sanitize_connection_name(selected_ref_raw))
        context = _build_generic_connections_context(
            "rss",
            _read_rss_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            blank_selected=bool(create_new),
            ref_key="rss_refs",
            selected_ref_key="selected_rss_ref",
            selected_key="selected_rss",
            rows_key="rss_status_rows",
            healthy_key="rss_healthy_count",
            issue_key="rss_issue_count",
            test_status_key="rss_test_status",
        )
        context["connection_intro"] = _build_connection_intro(
            kind="rss",
            summary_cards=_build_connection_summary_cards(
                kind="rss",
                profiles=len(context.get("rss_refs", [])),
                healthy=int(context.get("rss_healthy_count", 0) or 0),
                issues=int(context.get("rss_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.endpoint",
                        "label": "Target",
                        "value": "ready" if context.get("selected_rss", {}).get("feed_url") else "missing",
                        "value_key": "config_conn.ready" if context.get("selected_rss", {}).get("feed_url") else "config_conn.missing",
                        "hint_key": "config_conn.rss_feed_hint",
                        "hint": "Feed URL is stored directly in config.yaml.",
                    },
                ],
            ),
        )
        context["connection_intro"]["back_url"] = _connection_ui_path("rss_ui", "/config/connections/rss")
        context["connection_intro"]["back_label_key"] = "config_conn.back_to_rss_overview"
        context["connection_intro"]["back_label"] = "Back to RSS overview"
        context["connection_status_block"] = _build_connection_status_block(
            kind="rss",
            rows=list(context.get("rss_status_rows", [])),
        )
        context["rss_poll_interval_minutes"] = _read_rss_poll_interval_minutes()
        rss_group_options = sorted(
            {
                str(row.get("group_name", "")).strip()
                for row in context.get("rss_status_rows", [])
                if isinstance(row, dict) and str(row.get("group_name", "")).strip()
            },
            key=str.lower,
        )
        context["rss_create_new"] = bool(create_new)
        context["rss_selected_explicit"] = selected_ref_requested
        context["rss_edit_form_fields"] = _build_schema_form_fields(
            kind="rss",
            values=dict(context.get("selected_rss", {})),
            prefix="rss_edit",
            ref_value=str(context.get("selected_rss_ref", "")).strip(),
            placeholders={
                "connection_ref": "z.B. security-feed",
                "feed_url": "https://example.org/feed.xml",
                "group_name": "z.B. Security",
            },
            datalist_options={"group_name": rss_group_options},
            required_fields={"feed_url", "timeout_seconds"},
            ordered_fields=["feed_url", "group_name", "timeout_seconds"],
        )
        context["rss_new_form_fields"] = _build_schema_form_fields(
            kind="rss",
            values={"group_name": "", "timeout_seconds": 10},
            prefix="rss_new",
            ref_value="",
            placeholders={
                "connection_ref": "z.B. security-feed",
                "feed_url": "https://example.org/feed.xml",
                "group_name": "z.B. Security",
            },
            datalist_options={"group_name": rss_group_options},
            required_fields={"feed_url", "timeout_seconds"},
            ordered_fields=["feed_url", "group_name", "timeout_seconds"],
        )
        return context

    def _build_website_connections_context(
        selected_ref_raw: str = "",
        test_status: str = "",
        create_new: bool = False,
        lang: str = "de",
    ) -> dict[str, Any]:
        selected_ref_requested = bool(_sanitize_connection_name(selected_ref_raw))
        context = _build_generic_connections_context(
            "website",
            _read_website_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            blank_selected=bool(create_new),
            ref_key="website_refs",
            selected_ref_key="selected_website_ref",
            selected_key="selected_website",
            rows_key="website_status_rows",
            healthy_key="website_healthy_count",
            issue_key="website_issue_count",
            test_status_key="website_test_status",
        )
        selected = dict(context.get("selected_website", {}))
        context["connection_intro"] = _build_connection_intro(
            kind="website",
            summary_cards=_build_connection_summary_cards(
                kind="website",
                profiles=len(context.get("website_refs", [])),
                healthy=int(context.get("website_healthy_count", 0) or 0),
                issues=int(context.get("website_issue_count", 0) or 0),
                extra_cards=[
                    {
                        "label_key": "config_conn.endpoint",
                        "label": "Target",
                        "value": "ready" if selected.get("url") else "missing",
                        "value_key": "config_conn.ready" if selected.get("url") else "config_conn.missing",
                        "hint_key": "config_conn.website_url_hint",
                        "hint": "ARIA loads the saved page URL directly and keeps the source grouped with similar websites.",
                    },
                ],
            ),
        )
        context["connection_intro"]["back_url"] = _connection_ui_path("website_ui", "/config/connections/websites")
        context["connection_intro"]["back_label_key"] = "config_conn.back_to_website_overview"
        context["connection_intro"]["back_label"] = "Back to watched websites"
        context["connection_status_block"] = _build_connection_status_block(
            kind="website",
            rows=list(context.get("website_status_rows", [])),
        )
        website_group_options = sorted(
            {
                str(row.get("group_name", "")).strip()
                for row in context.get("website_status_rows", [])
                if isinstance(row, dict) and str(row.get("group_name", "")).strip()
            },
            key=str.lower,
        )
        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        for row in list(context.get("website_status_rows", [])):
            group_name = str(row.get("group_name", "")).strip() or ("Allgemein" if lang == "de" else "General")
            grouped_rows.setdefault(group_name, []).append(row)
        context["website_status_groups"] = [
            {
                "name": group_name,
                "rows": rows,
                "total": len(rows),
                "healthy": sum(1 for item in rows if item.get("status") == "ok"),
                "issues": sum(1 for item in rows if item.get("status") == "error"),
            }
            for group_name, rows in sorted(grouped_rows.items(), key=lambda item: item[0].lower())
        ]
        context["website_create_new"] = bool(create_new)
        context["website_selected_explicit"] = selected_ref_requested
        context["website_edit_form_fields"] = _build_schema_form_fields(
            kind="website",
            values=selected,
            prefix="website_edit",
            ref_value=str(context.get("selected_website_ref", "")).strip(),
            placeholders={
                "connection_ref": "z.B. aria-docs",
                "url": "https://example.org/docs",
                "group_name": "z.B. Dokumentation",
            },
            datalist_options={"group_name": website_group_options},
            required_fields={"url", "timeout_seconds"},
            ordered_fields=["url", "group_name", "timeout_seconds"],
        )
        context["website_new_form_fields"] = _build_schema_form_fields(
            kind="website",
            values={"group_name": "", "timeout_seconds": 10},
            prefix="website_new",
            ref_value="",
            placeholders={
                "connection_ref": "z.B. aria-docs",
                "url": "https://example.org/docs",
                "group_name": "z.B. Dokumentation",
            },
            datalist_options={"group_name": website_group_options},
            required_fields={"url", "timeout_seconds"},
            ordered_fields=["url", "group_name", "timeout_seconds"],
        )
        return context

    def _build_mqtt_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
        context = _build_generic_connections_context(
            "mqtt",
            _read_mqtt_connections(),
            lang=lang,
            selected_ref_raw=selected_ref_raw,
            test_status=test_status,
            ref_key="mqtt_refs",
            selected_ref_key="selected_mqtt_ref",
            selected_key="selected_mqtt",
            rows_key="mqtt_status_rows",
            healthy_key="mqtt_healthy_count",
            issue_key="mqtt_issue_count",
            test_status_key="mqtt_test_status",
        )
        _attach_connection_intro_and_status(
            context,
            kind="mqtt",
            refs_key="mqtt_refs",
            healthy_key="mqtt_healthy_count",
            issue_key="mqtt_issue_count",
            rows_key="mqtt_status_rows",
            extra_cards=[
                _secret_status_card(
                    label_key="config_conn.password_status",
                    label="Password status",
                    secret_present=bool(context.get("selected_mqtt", {}).get("password_present")),
                    connected_hint_key="config_conn.mqtt_password_hint",
                    connected_hint="Password is stored in the secure store, not in config.yaml.",
                ),
            ],
        )
        context["mqtt_edit_form_fields"] = _build_schema_form_fields(
            kind="mqtt",
            values=dict(context.get("selected_mqtt", {})),
            prefix="mqtt_edit",
            ref_value=str(context.get("selected_mqtt_ref", "")).strip(),
            placeholders={"connection_ref": "z.B. event-bus", "host": "mqtt.example.local", "user": "mqtt-user", "topic": "aria/events"},
            required_fields={"host", "port", "user", "timeout_seconds"},
            boolean_defaults={"use_tls": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "topic", "timeout_seconds", "use_tls", "password"],
        )
        context["mqtt_new_form_fields"] = _build_schema_form_fields(
            kind="mqtt",
            values={"port": 1883, "timeout_seconds": 10, "use_tls": False},
            prefix="mqtt_new",
            ref_value="",
            placeholders={"connection_ref": "z.B. event-bus", "host": "mqtt.example.local", "user": "mqtt-user", "topic": "aria/events"},
            required_fields={"host", "port", "user", "timeout_seconds", "password"},
            boolean_defaults={"use_tls": False},
            secrets_with_hints={"password": "Password is stored in the secure store, not in config.yaml."},
            ordered_fields=["host", "port", "user", "topic", "timeout_seconds", "use_tls", "password"],
        )
        return context

    return ConnectionContextHelperBundle(
        build_ssh_connections_context=_build_ssh_connections_context,
        build_discord_connections_context=_build_discord_connections_context,
        build_sftp_connections_context=_build_sftp_connections_context,
        build_smb_connections_context=_build_smb_connections_context,
        build_webhook_connections_context=_build_webhook_connections_context,
        build_email_connections_context=_build_email_connections_context,
        build_imap_connections_context=_build_imap_connections_context,
        build_http_api_connections_context=_build_http_api_connections_context,
        build_google_calendar_connections_context=_build_google_calendar_connections_context,
        build_rss_connections_context=_build_rss_connections_context,
        build_website_connections_context=_build_website_connections_context,
        build_mqtt_connections_context=_build_mqtt_connections_context,
    )
