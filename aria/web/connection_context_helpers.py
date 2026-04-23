from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


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
    read_searxng_connections: Callable[[], dict[str, dict[str, Any]]]
    read_mqtt_connections: Callable[[], dict[str, dict[str, Any]]]
    probe_searxng_stack_service: Callable[..., dict[str, Any]]
    resolve_searxng_base_url: Callable[[str], str]
    searxng_category_options: list[tuple[str, str]]
    searxng_engine_options: list[tuple[str, str]]


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
    build_searxng_connections_context: Any
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


def _sftp_auth_status_card(selected_sftp: dict[str, Any]) -> dict[str, str]:
    if selected_sftp.get("key_path"):
        return {
            "label_key": "config_conn.auth_status",
            "label": "Auth status",
            "value": "Key",
            "value_key": "config_conn.sftp_key_mode",
            "hint_key": "config_conn.sftp_key_hint",
            "hint": "SFTP can use the configured SSH key directly.",
        }
    if selected_sftp.get("password_present"):
        return {
            "label_key": "config_conn.auth_status",
            "label": "Auth status",
            "value": "Password",
            "value_key": "config_conn.sftp_password_mode",
            "hint_key": "config_conn.sftp_password_hint",
            "hint": "Password is stored in the secure store, not in config.yaml.",
        }
    return {
        "label_key": "config_conn.auth_status",
        "label": "Auth status",
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
    _read_searxng_connections = deps.read_searxng_connections
    _read_mqtt_connections = deps.read_mqtt_connections
    probe_searxng_stack_service = deps.probe_searxng_stack_service
    resolve_searxng_base_url = deps.resolve_searxng_base_url
    _SEARXNG_CATEGORY_OPTIONS = deps.searxng_category_options
    _SEARXNG_ENGINE_OPTIONS = deps.searxng_engine_options

    def _build_ssh_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
            rows = _read_ssh_connections()
            guardrail_rows = _read_guardrails()
            guardrail_ref_options = _build_guardrail_ref_options(guardrail_rows, connection_kind="ssh", lang=lang)
            refs = sorted(rows.keys())
            selected_ref = _sanitize_connection_name(selected_ref_raw) or (refs[0] if refs else "")
            selected = rows.get(selected_ref, {})
            connection_status_rows = _attach_connection_edit_urls("ssh", build_connection_status_rows(
                "ssh",
                rows,
                selected_ref=selected_ref,
                cached_only=True,
                base_dir=BASE_DIR,
                lang=lang,
            ))
            healthy_count = sum(1 for item in connection_status_rows if item["status"] == "ok")
            issue_count = sum(1 for item in connection_status_rows if item["status"] == "error")
            public_key = ""
            private_key_exists = False
            public_key_exists = False
            key_path = str(selected.get("key_path", "")).strip()
            if key_path:
                expanded = Path(key_path).expanduser()
                private_key_exists = expanded.exists() and expanded.is_file()
                pub_path = expanded if expanded.suffix == ".pub" else expanded.with_suffix(expanded.suffix + ".pub")
                if pub_path.exists() and pub_path.is_file():
                    public_key_exists = True
                    try:
                        public_key = pub_path.read_text(encoding="utf-8").strip()
                    except OSError:
                        public_key = ""
            return {
                "connection_intro": _build_connection_intro(
                    kind="ssh",
                    summary_cards=_build_connection_summary_cards(
                        kind="ssh",
                        profiles=len(refs),
                        healthy=healthy_count,
                        issues=issue_count,
                        extra_cards=[
                            {
                                "label_key": "config_conn.key_status",
                                "label": "Key status",
                                "value": "ready" if private_key_exists and public_key_exists else ("partial" if private_key_exists or public_key_exists else "missing"),
                                "value_key": "config_conn.ready" if private_key_exists and public_key_exists else ("config_conn.partial" if private_key_exists or public_key_exists else "config_conn.missing"),
                                "hint_key": "",
                                "hint": f"Private key: {'ok' if private_key_exists else 'missing'} · Public key: {'ok' if public_key_exists else 'missing'}",
                            },
                        ],
                    ),
                ),
                "connection_status_block": _build_connection_status_block(
                    kind="ssh",
                    rows=connection_status_rows,
                    collapse_threshold=5,
                ),
                "refs": refs,
                "ref_options": _build_connection_ref_options(rows),
                "selected_ref": selected_ref,
                "selected": selected,
                "ssh_edit_base_form_fields": _build_schema_form_fields(
                    kind="ssh",
                    values=dict(selected),
                    prefix="ssh_edit",
                    ref_value=selected_ref,
                    placeholders={
                        "connection_ref": "z.B. main-ssh",
                        "host": "server.example.local",
                        "service_url": "https://service.example.local",
                        "user": "admin",
                    },
                    required_fields={"host", "user", "port", "timeout_seconds"},
                    ordered_fields=["host", "service_url", "user", "port", "timeout_seconds"],
                ),
                "ssh_new_base_form_fields": _build_schema_form_fields(
                    kind="ssh",
                    values={"port": 22, "timeout_seconds": 20},
                    prefix="ssh_new",
                    ref_value="",
                    placeholders={
                        "connection_ref": "z.B. main-ssh",
                        "host": "server.example.local",
                        "service_url": "https://service.example.local",
                        "user": "admin",
                    },
                    required_fields={"host", "user", "port", "timeout_seconds"},
                    ordered_fields=["host", "service_url", "user", "port", "timeout_seconds"],
                ),
                "ssh_edit_advanced_form_fields": _build_schema_form_fields(
                    kind="ssh",
                    values=dict(selected),
                    prefix="ssh_edit_adv",
                    ref_value=selected_ref,
                    include_ref=False,
                    select_options={
                        "strict_host_key_checking": ["accept-new", "yes", "no"],
                    },
                    field_hints={
                        "allow_commands": "One line per command. Empty = no permission for ssh_command.",
                    },
                    ordered_fields=["strict_host_key_checking", "key_path", "allow_commands"],
                ),
                "ssh_new_advanced_form_fields": _build_schema_form_fields(
                    kind="ssh",
                    values={"strict_host_key_checking": "accept-new"},
                    prefix="ssh_new_adv",
                    ref_value="",
                    include_ref=False,
                    select_options={
                        "strict_host_key_checking": ["accept-new", "yes", "no"],
                    },
                    field_hints={
                        "allow_commands": "One line per command. Empty = no permission for ssh_command.",
                    },
                    ordered_fields=["strict_host_key_checking", "key_path", "allow_commands"],
                ),
                "connection_status_rows": connection_status_rows,
                "healthy_count": healthy_count,
                "issue_count": issue_count,
                "public_key": public_key,
                "private_key_exists": private_key_exists,
                "public_key_exists": public_key_exists,
                "guardrail_rows": guardrail_rows,
                "guardrail_ref_options": guardrail_ref_options,
                "test_status": str(test_status).strip().lower(),
            }

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
            context["connection_intro"] = _build_connection_intro(
                kind="discord",
                summary_cards=_build_connection_summary_cards(
                    kind="discord",
                    profiles=len(context.get("discord_refs", [])),
                    healthy=int(context.get("discord_healthy_count", 0) or 0),
                    issues=int(context.get("discord_issue_count", 0) or 0),
                    extra_cards=[
                        _secret_status_card(
                            label_key="config_conn.webhook_status",
                            label="Webhook status",
                            secret_present=bool(context.get("selected_discord", {}).get("webhook_present")),
                            connected_hint_key="config_conn.discord_webhook_hint",
                            connected_hint="Webhook URL is stored in the secure store, not in config.yaml.",
                        ),
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="discord",
                rows=list(context.get("discord_status_rows", [])),
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
            guardrail_rows = _read_guardrails()
            sftp_rows = _read_sftp_connections()
            ssh_rows = _read_ssh_connections()
            sftp_refs = sorted(sftp_rows.keys())
            selected_sftp_ref = _sanitize_connection_name(selected_ref_raw) or (sftp_refs[0] if sftp_refs else "")
            selected_sftp = dict(sftp_rows.get(selected_sftp_ref, {}))
            ssh_refs = sorted(ssh_rows.keys())
            selected_ssh_seed_ref = _sanitize_connection_name(copy_from_ssh_ref)
            selected_ssh_seed = ssh_rows.get(selected_ssh_seed_ref, {})
            if selected_ssh_seed:
                seed_key_path = str(selected_ssh_seed.get("key_path", "")).strip()
                seed_key_present = False
                if seed_key_path:
                    seed_key_file = Path(seed_key_path)
                    if not seed_key_file.is_absolute():
                        seed_key_file = (BASE_DIR / seed_key_file).resolve()
                    seed_key_present = seed_key_file.exists()
                selected_sftp = {
                    **selected_sftp,
                    "host": str(selected_ssh_seed.get("host", "")).strip(),
                    "port": int(selected_ssh_seed.get("port", 22) or 22),
                    "user": str(selected_ssh_seed.get("user", "")).strip(),
                    "key_path": seed_key_path,
                    "key_present": seed_key_present,
                    "timeout_seconds": int(selected_ssh_seed.get("timeout_seconds", 10) or 10),
                }
            sftp_status_rows = build_connection_status_rows(
                "sftp",
                sftp_rows,
                selected_ref=selected_sftp_ref,
                cached_only=True,
                base_dir=BASE_DIR,
                lang=lang,
            )
            sftp_healthy_count = sum(1 for item in sftp_status_rows if item["status"] == "ok")
            sftp_issue_count = sum(1 for item in sftp_status_rows if item["status"] == "error")
            return {
                "connection_intro": _build_connection_intro(
                    kind="sftp",
                    summary_cards=_build_connection_summary_cards(
                    kind="sftp",
                    profiles=len(sftp_refs),
                    healthy=sftp_healthy_count,
                    issues=sftp_issue_count,
                    extra_cards=[
                            _sftp_auth_status_card(selected_sftp),
                        ],
                    ),
                ),
                "connection_status_block": _build_connection_status_block(
                    kind="sftp",
                    rows=sftp_status_rows,
                    collapse_threshold=5,
                ),
                "sftp_refs": sftp_refs,
                "sftp_ref_options": _build_connection_ref_options(sftp_rows),
                "selected_sftp_ref": selected_sftp_ref,
                "selected_sftp": selected_sftp,
                "sftp_edit_form_fields": _build_schema_form_fields(
                    kind="sftp",
                    values=dict(selected_sftp),
                    prefix="sftp_edit",
                    ref_value=selected_sftp_ref,
                    placeholders={"connection_ref": "z.B. files-sftp", "host": "files.example.local", "service_url": "https://files.example.local", "user": "backup", "root_path": "/data", "key_path": "/app/data/ssh_keys/files-sftp_ed25519"},
                    required_fields={"host", "user", "port", "timeout_seconds"},
                    field_hints={"key_path": "Wenn gesetzt, nutzt SFTP diesen Key statt Passwort. Ideal für Profile, die du aus SSH übernommen hast."},
                    secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
                    ordered_fields=["host", "service_url", "user", "port", "timeout_seconds", "root_path", "key_path", "password"],
                ),
                "sftp_new_form_fields": _build_schema_form_fields(
                    kind="sftp",
                    values={
                        "host": str(selected_ssh_seed.get("host", "")).strip(),
                        "service_url": str(selected_ssh_seed.get("service_url", "")).strip(),
                        "user": str(selected_ssh_seed.get("user", "")).strip(),
                        "port": int(selected_ssh_seed.get("port", 22) or 22),
                        "timeout_seconds": int(selected_ssh_seed.get("timeout_seconds", 10) or 10),
                        "key_path": str(selected_ssh_seed.get("key_path", "")).strip(),
                    },
                    prefix="sftp_new",
                    ref_value=selected_ssh_seed_ref,
                    placeholders={"connection_ref": "z.B. files-sftp", "host": "files.example.local", "service_url": "https://files.example.local", "user": "backup", "root_path": "/data", "key_path": "/app/data/ssh_keys/files-sftp_ed25519"},
                    required_fields={"host", "user", "port", "timeout_seconds"},
                    field_hints={"key_path": "Wenn gesetzt, nutzt SFTP diesen Key statt Passwort. Ideal für Profile, die du aus SSH übernommen hast."},
                    secrets_with_hints={"password": "The password is stored in the secure store and never written into config.yaml."},
                    ordered_fields=["host", "service_url", "user", "port", "timeout_seconds", "root_path", "key_path", "password"],
                ),
                "ssh_refs": ssh_refs,
                "ssh_ref_options": _build_connection_ref_options(ssh_rows),
                "selected_ssh_seed_ref": selected_ssh_seed_ref,
                "selected_ssh_seed": selected_ssh_seed,
                "sftp_status_rows": sftp_status_rows,
                "sftp_healthy_count": sftp_healthy_count,
                "sftp_issue_count": sftp_issue_count,
                "sftp_test_status": str(test_status).strip().lower(),
                "sftp_guardrail_ref_options": _build_guardrail_ref_options(guardrail_rows, connection_kind="sftp", lang=lang),
            }

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
            context["connection_intro"] = _build_connection_intro(
                kind="smb",
                summary_cards=_build_connection_summary_cards(
                    kind="smb",
                    profiles=len(context.get("smb_refs", [])),
                    healthy=int(context.get("smb_healthy_count", 0) or 0),
                    issues=int(context.get("smb_issue_count", 0) or 0),
                    extra_cards=[
                        _secret_status_card(
                            label_key="config_conn.password_status",
                            label="Password status",
                            secret_present=bool(context.get("selected_smb", {}).get("password_present")),
                            connected_hint_key="config_conn.smb_password_hint",
                            connected_hint="Password is stored in the secure store, not in config.yaml.",
                        ),
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="smb",
                rows=list(context.get("smb_status_rows", [])),
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
            context["smb_guardrail_ref_options"] = _build_guardrail_ref_options(guardrail_rows, connection_kind="smb", lang=lang)
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
            context["connection_intro"] = _build_connection_intro(
                kind="webhook",
                summary_cards=_build_connection_summary_cards(
                    kind="webhook",
                    profiles=len(context.get("webhook_refs", [])),
                    healthy=int(context.get("webhook_healthy_count", 0) or 0),
                    issues=int(context.get("webhook_issue_count", 0) or 0),
                    extra_cards=[
                        _secret_status_card(
                            label_key="config_conn.webhook_status",
                            label="Webhook status",
                            secret_present=bool(context.get("selected_webhook", {}).get("url_present")),
                            connected_hint_key="config_conn.webhook_secret_hint",
                            connected_hint="The webhook URL is stored in the secure store, not in config.yaml.",
                        ),
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="webhook",
                rows=list(context.get("webhook_status_rows", [])),
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
            context["webhook_guardrail_ref_options"] = _build_guardrail_ref_options(guardrail_rows, connection_kind="webhook", lang=lang)
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
            context["connection_intro"] = _build_connection_intro(
                kind="email",
                summary_cards=_build_connection_summary_cards(
                    kind="email",
                    profiles=len(context.get("email_refs", [])),
                    healthy=int(context.get("email_healthy_count", 0) or 0),
                    issues=int(context.get("email_issue_count", 0) or 0),
                    extra_cards=[
                        _secret_status_card(
                            label_key="config_conn.password_status",
                            label="Password status",
                            secret_present=bool(context.get("selected_email", {}).get("password_present")),
                            connected_hint_key="config_conn.email_password_hint",
                            connected_hint="Password is stored in the secure store, not in config.yaml.",
                        ),
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="email",
                rows=list(context.get("email_status_rows", [])),
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
            context["connection_intro"] = _build_connection_intro(
                kind="imap",
                summary_cards=_build_connection_summary_cards(
                    kind="imap",
                    profiles=len(context.get("imap_refs", [])),
                    healthy=int(context.get("imap_healthy_count", 0) or 0),
                    issues=int(context.get("imap_issue_count", 0) or 0),
                    extra_cards=[
                        _secret_status_card(
                            label_key="config_conn.password_status",
                            label="Password status",
                            secret_present=bool(context.get("selected_imap", {}).get("password_present")),
                            connected_hint_key="config_conn.imap_password_hint",
                            connected_hint="Password is stored in the secure store, not in config.yaml.",
                        ),
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="imap",
                rows=list(context.get("imap_status_rows", [])),
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
            context["connection_intro"] = _build_connection_intro(
                kind="http_api",
                summary_cards=_build_connection_summary_cards(
                    kind="http_api",
                    profiles=len(context.get("http_api_refs", [])),
                    healthy=int(context.get("http_api_healthy_count", 0) or 0),
                    issues=int(context.get("http_api_issue_count", 0) or 0),
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
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="http_api",
                rows=list(context.get("http_api_status_rows", [])),
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
            context["http_api_guardrail_ref_options"] = _build_guardrail_ref_options(guardrail_rows, connection_kind="http_api", lang=lang)
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
            auth_ready = bool(selected.get("client_secret_present")) and bool(selected.get("refresh_token_present"))
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
                            "hint": "The read-only calendar target ARIA will query first.",
                        },
                        _secret_status_card(
                            label_key="config_conn.sign_in_status",
                            label="Sign-in status",
                            secret_present=auth_ready,
                            connected_hint_key="config_conn.google_calendar_auth_hint",
                            connected_hint="OAuth client secret and refresh token are stored in the secure store.",
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
                    "calendar_id": "primary",
                    "client_id": "1234567890-abc.apps.googleusercontent.com",
                },
                required_fields={"calendar_id", "client_id", "timeout_seconds"},
                field_hints={
                    "client_id": (
                        "OAuth-Client aus Google Cloud > Google Auth platform > Clients."
                        if lang == "de"
                        else "OAuth client from Google Cloud > Google Auth platform > Clients."
                    ),
                    "calendar_id": (
                        "Für den Hauptkalender einfach `primary` verwenden. Für andere Kalender die Calendar ID aus Google Calendar > Einstellungen > Kalender integrieren kopieren."
                        if lang == "de"
                        else "Use `primary` for the main calendar. For other calendars, copy the Calendar ID from Google Calendar > Settings > Integrate calendar."
                    ),
                    "timeout_seconds": (
                        "Read-only Probe-Timeout gegen Google in Sekunden."
                        if lang == "de"
                        else "Read-only probe timeout against Google in seconds."
                    ),
                },
                secrets_with_hints={
                    "client_secret": "OAuth client secret is stored in the secure store.",
                    "refresh_token": "Refresh token is stored in the secure store and keeps read-only access alive.",
                },
                ordered_fields=["client_id", "calendar_id", "timeout_seconds", "client_secret", "refresh_token"],
            )
            context["google_calendar_new_form_fields"] = _build_schema_form_fields(
                kind="google_calendar",
                values={"calendar_id": "primary", "timeout_seconds": 10},
                prefix="google_calendar_new",
                ref_value="",
                placeholders={
                    "connection_ref": "z.B. primary-calendar",
                    "calendar_id": "primary",
                    "client_id": "1234567890-abc.apps.googleusercontent.com",
                },
                required_fields={"calendar_id", "client_id", "timeout_seconds", "client_secret", "refresh_token"},
                field_hints={
                    "client_id": (
                        "OAuth-Client aus Google Cloud > Google Auth platform > Clients."
                        if lang == "de"
                        else "OAuth client from Google Cloud > Google Auth platform > Clients."
                    ),
                    "calendar_id": (
                        "Für den Hauptkalender einfach `primary` verwenden. Für andere Kalender die Calendar ID aus Google Calendar > Einstellungen > Kalender integrieren kopieren."
                        if lang == "de"
                        else "Use `primary` for the main calendar. For other calendars, copy the Calendar ID from Google Calendar > Settings > Integrate calendar."
                    ),
                    "timeout_seconds": (
                        "Read-only Probe-Timeout gegen Google in Sekunden."
                        if lang == "de"
                        else "Read-only probe timeout against Google in seconds."
                    ),
                },
                secrets_with_hints={
                    "client_secret": "OAuth client secret is stored in the secure store.",
                    "refresh_token": "Refresh token is stored in the secure store and keeps read-only access alive.",
                },
                ordered_fields=["client_id", "calendar_id", "timeout_seconds", "client_secret", "refresh_token"],
            )
            return context

    def _build_searxng_connections_context(selected_ref_raw: str = "", test_status: str = "", lang: str = "de") -> dict[str, Any]:
            context = _build_generic_connections_context(
                "searxng",
                _read_searxng_connections(),
                lang=lang,
                selected_ref_raw=selected_ref_raw,
                test_status=test_status,
                ref_key="searxng_refs",
                selected_ref_key="selected_searxng_ref",
                selected_key="selected_searxng",
                rows_key="searxng_status_rows",
                healthy_key="searxng_healthy_count",
                issue_key="searxng_issue_count",
                test_status_key="searxng_test_status",
            )
            context["searxng_stack_status"] = probe_searxng_stack_service(lang=lang)
            selected_profile = dict(context.get("selected_searxng", {}))
            selected_categories = {
                str(item).strip()
                for item in (selected_profile.get("categories") or [])
                if str(item).strip()
            }
            selected_engines = {
                str(item).strip()
                for item in (selected_profile.get("engines") or [])
                if str(item).strip()
            }
            existing_refs = set(context.get("searxng_refs", []))
            suggested_ref = "web-search"
            counter = 2
            while suggested_ref in existing_refs:
                suggested_ref = f"web-search-{counter}"
                counter += 1
            default_profile = {
                "timeout_seconds": 10,
                "language": "de-CH",
                "safe_search": 1,
                "categories": ["general"],
                "engines": [],
                "time_range": "",
                "max_results": 5,
                "title": "Websuche" if lang.startswith("de") else "Web search",
                "description": (
                    "Standardprofil fuer allgemeine Websuche ueber den lokalen SearXNG-Stack."
                    if lang.startswith("de")
                    else "Default profile for general web search via the local SearXNG stack."
                ),
                "aliases_text": "websuche, internet, suche" if lang.startswith("de") else "web search, internet, search",
                "tags_text": "web, search",
            }
            context["searxng_default_base_url"] = resolve_searxng_base_url("")
            context["searxng_stack_available"] = bool(context["searxng_stack_status"].get("available"))
            context["searxng_suggested_ref"] = suggested_ref
            context["searxng_language_options"] = ["de-CH", "de-DE", "en-GB", "en-US", "fr-CH"]
            context["searxng_safe_search_options"] = [
                {"value": "0", "label": "0 - aus / off"},
                {"value": "1", "label": "1 - normal"},
                {"value": "2", "label": "2 - strikt / strict"},
            ]
            context["searxng_time_range_options"] = [
                {"value": "", "label": "kein Standard / none"},
                {"value": "day", "label": "day"},
                {"value": "month", "label": "month"},
                {"value": "year", "label": "year"},
            ]
            context["searxng_edit_profile"] = {
                **default_profile,
                **selected_profile,
            }
            context["searxng_new_profile"] = dict(default_profile)
            context["searxng_category_options"] = [
                {"value": value, "label": label, "checked": value in selected_categories}
                for value, label in _SEARXNG_CATEGORY_OPTIONS
            ]
            context["searxng_engine_options"] = [
                {"value": value, "label": label, "checked": value in selected_engines}
                for value, label in _SEARXNG_ENGINE_OPTIONS
            ]
            context["searxng_new_category_options"] = [
                {"value": value, "label": label, "checked": value in {"general"}}
                for value, label in _SEARXNG_CATEGORY_OPTIONS
            ]
            context["searxng_new_engine_options"] = [
                {"value": value, "label": label, "checked": False}
                for value, label in _SEARXNG_ENGINE_OPTIONS
            ]
            context["connection_intro"] = _build_connection_intro(
                kind="searxng",
                summary_cards=_build_connection_summary_cards(
                    kind="searxng",
                    profiles=len(context.get("searxng_refs", [])),
                    healthy=int(context.get("searxng_healthy_count", 0) or 0),
                    issues=int(context.get("searxng_issue_count", 0) or 0),
                    extra_cards=[
                        {
                            "label_key": "config_conn.endpoint",
                            "label": "Target",
                            "value": resolve_searxng_base_url(str(selected_profile.get("base_url", "")).strip()),
                            "hint_key": "config_conn.searxng_base_url_hint",
                            "hint": "ARIA uses the fixed in-stack SearXNG JSON API target.",
                        },
                        {
                            "label_key": "config_conn.searxng_max_results",
                            "label": "Max. Treffer",
                            "value": str(selected_profile.get("max_results", 5) or 5),
                            "hint_key": "config_conn.searxng_max_results_hint",
                            "hint": "How many hits ARIA should bring into the chat context by default.",
                        },
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="searxng",
                rows=list(context.get("searxng_status_rows", [])),
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
            context["connection_intro"]["back_url"] = "/config/connections/rss"
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
            context["connection_intro"]["back_url"] = "/config/connections/websites"
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
            context["connection_intro"] = _build_connection_intro(
                kind="mqtt",
                summary_cards=_build_connection_summary_cards(
                    kind="mqtt",
                    profiles=len(context.get("mqtt_refs", [])),
                    healthy=int(context.get("mqtt_healthy_count", 0) or 0),
                    issues=int(context.get("mqtt_issue_count", 0) or 0),
                    extra_cards=[
                        _secret_status_card(
                            label_key="config_conn.password_status",
                            label="Password status",
                            secret_present=bool(context.get("selected_mqtt", {}).get("password_present")),
                            connected_hint_key="config_conn.mqtt_password_hint",
                            connected_hint="Password is stored in the secure store, not in config.yaml.",
                        ),
                    ],
                ),
            )
            context["connection_status_block"] = _build_connection_status_block(
                kind="mqtt",
                rows=list(context.get("mqtt_status_rows", [])),
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
        build_searxng_connections_context=_build_searxng_connections_context,
        build_rss_connections_context=_build_rss_connections_context,
        build_website_connections_context=_build_website_connections_context,
        build_mqtt_connections_context=_build_mqtt_connections_context,
    )
