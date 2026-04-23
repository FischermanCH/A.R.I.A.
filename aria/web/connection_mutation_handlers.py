from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response


@dataclass(frozen=True)
class ConnectionMutationHandlerDeps:
    base_dir: Path
    msg: Any
    read_raw_config: Any
    write_raw_config: Any
    reload_runtime: Any
    redirect_with_return_to: Any
    sanitize_connection_name: Any
    delete_connection_profile: Any
    get_connection_delete_spec: Any
    trigger_connection_routing_refresh: Any
    prepare_connection_save: Any
    read_guardrails: Any
    guardrail_is_compatible: Any
    autofill_service_connection_metadata: Any
    build_connection_metadata: Any
    connection_saved_test_info: Any
    perform_ssh_key_exchange: Any
    derive_matching_sftp_ref: Any
    finalize_connection_save: Any
    build_connection_status_row: Any
    friendly_ssh_setup_error: Any
    read_ssh_connections: Any
    read_discord_connections: Any
    read_sftp_connections: Any
    read_smb_connections: Any
    read_webhook_connections: Any
    read_email_connections: Any
    read_imap_connections: Any
    read_http_api_connections: Any
    read_google_calendar_connections: Any
    read_searxng_connections: Any
    read_website_connections: Any
    normalize_rss_feed_url_for_dedupe: Any
    read_rss_poll_interval_minutes: Any
    read_rss_connections: Any
    build_opml_document: Any
    parse_opml_feeds: Any
    next_rss_import_ref: Any
    is_valid_csrf_submission: Any
    read_mqtt_connections: Any
    ssh_keys_dir: Any
    ensure_ssh_keypair: Any
    autofill_website_connection_metadata: Any


@dataclass(frozen=True)
class ConnectionMutationHandlers:
    rss_poll_interval_save: Any
    connection_delete: Any
    ssh_save: Any
    discord_save: Any
    sftp_save: Any
    smb_save: Any
    webhook_save: Any
    smtp_save: Any
    imap_save: Any
    http_api_save: Any
    google_calendar_save: Any
    searxng_save: Any
    rss_save: Any
    website_save: Any
    rss_export_opml: Any
    rss_import_opml: Any
    rss_ping_now: Any
    mqtt_save: Any
    ssh_keygen: Any
    ssh_key_exchange: Any
    ssh_test: Any


def build_connection_mutation_handlers(deps: ConnectionMutationHandlerDeps) -> ConnectionMutationHandlers:
    BASE_DIR = deps.base_dir
    _msg = deps.msg
    _read_raw_config = deps.read_raw_config
    _write_raw_config = deps.write_raw_config
    _reload_runtime = deps.reload_runtime
    _redirect_with_return_to = deps.redirect_with_return_to
    _sanitize_connection_name = deps.sanitize_connection_name
    _delete_connection_profile = deps.delete_connection_profile
    _get_connection_delete_spec = deps.get_connection_delete_spec
    _trigger_connection_routing_refresh = deps.trigger_connection_routing_refresh
    _prepare_connection_save = deps.prepare_connection_save
    _read_guardrails = deps.read_guardrails
    guardrail_is_compatible = deps.guardrail_is_compatible
    _autofill_service_connection_metadata = deps.autofill_service_connection_metadata
    _build_connection_metadata = deps.build_connection_metadata
    _connection_saved_test_info = deps.connection_saved_test_info
    _perform_ssh_key_exchange = deps.perform_ssh_key_exchange
    _derive_matching_sftp_ref = deps.derive_matching_sftp_ref
    _finalize_connection_save = deps.finalize_connection_save
    build_connection_status_row = deps.build_connection_status_row
    _friendly_ssh_setup_error = deps.friendly_ssh_setup_error
    _read_ssh_connections = deps.read_ssh_connections
    _read_discord_connections = deps.read_discord_connections
    _read_sftp_connections = deps.read_sftp_connections
    _read_smb_connections = deps.read_smb_connections
    _read_webhook_connections = deps.read_webhook_connections
    _read_email_connections = deps.read_email_connections
    _read_imap_connections = deps.read_imap_connections
    _read_http_api_connections = deps.read_http_api_connections
    _read_google_calendar_connections = deps.read_google_calendar_connections
    _read_searxng_connections = deps.read_searxng_connections
    _read_website_connections = deps.read_website_connections
    _normalize_rss_feed_url_for_dedupe = deps.normalize_rss_feed_url_for_dedupe
    _read_rss_poll_interval_minutes = deps.read_rss_poll_interval_minutes
    _read_rss_connections = deps.read_rss_connections
    build_opml_document = deps.build_opml_document
    parse_opml_feeds = deps.parse_opml_feeds
    _next_rss_import_ref = deps.next_rss_import_ref
    _is_valid_csrf_submission = deps.is_valid_csrf_submission
    _read_mqtt_connections = deps.read_mqtt_connections
    _ssh_keys_dir = deps.ssh_keys_dir
    _ensure_ssh_keypair = deps.ensure_ssh_keypair
    _autofill_website_connection_metadata = deps.autofill_website_connection_metadata

    def _normalize_website_url(value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            return ""
        parsed = urlparse(clean)
        if not parsed.scheme and parsed.netloc:
            clean = f"https:{clean}"
            parsed = urlparse(clean)
        if not parsed.scheme and parsed.path and "." in parsed.path and " " not in parsed.path:
            clean = f"https://{clean}"
            parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URL muss mit http:// oder https:// erreichbar sein.")
        if not parsed.netloc:
            raise ValueError("URL ist unvollständig.")
        return clean

    def _infer_website_group_name(
        *,
        url: str,
        title: str,
        tags: str,
        existing_group_name: str,
        lang: str,
    ) -> str:
        manual = str(existing_group_name or "").strip()
        if manual:
            return manual[:64]
        haystack = " ".join(
            [
                str(url or "").strip().lower(),
                str(title or "").strip().lower(),
                str(tags or "").strip().lower(),
            ]
        )
        grouped_terms = [
            (("docs", "documentation", "manual", "guide", "reference", "api"), ("Dokumentation", "Documentation")),
            (("news", "blog", "release", "updates", "changelog"), ("News", "News")),
            (("security", "cve", "incident", "advisory"), ("Security", "Security")),
            (("github", "gitlab", "repo", "code", "developer"), ("Entwicklung", "Development")),
            (("research", "paper", "study", "ai", "ml"), ("Forschung", "Research")),
            (("status", "uptime", "monitor", "ops"), ("Betrieb", "Operations")),
            (("product", "pricing", "shop", "store"), ("Produkte", "Products")),
        ]
        for terms, labels in grouped_terms:
            if any(term in haystack for term in terms):
                return (labels[0] if lang.startswith("de") else labels[1])[:64]
        parsed = urlparse(url)
        host = str(parsed.netloc or "").strip().lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            root = host.split(".", 1)[0].replace("-", " ").strip()
            if root:
                return root[:64]
        return ("Allgemein" if lang.startswith("de") else "General")[:64]
    async def config_connections_rss_poll_interval_save(
        request: Request,
        poll_interval_minutes: int = Form(60),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            poll_interval = max(1, min(int(poll_interval_minutes), 10080))
            raw = _read_raw_config()
            raw.setdefault("rss", {})
            if not isinstance(raw["rss"], dict):
                raw["rss"] = {}
            raw["rss"]["poll_interval_minutes"] = poll_interval
            connections = raw.setdefault("connections", {})
            if not isinstance(connections, dict):
                raw["connections"] = {}
                connections = raw["connections"]
            rss_rows = connections.setdefault("rss", {})
            if not isinstance(rss_rows, dict):
                connections["rss"] = {}
                rss_rows = connections["rss"]
            for row in rss_rows.values():
                if isinstance(row, dict):
                    row["poll_interval_minutes"] = poll_interval
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                "/config/connections/rss?saved=1&mode=edit"
                f"&info={quote_plus(_msg(lang, f'RSS-Ping-Intervall global auf {poll_interval} Minuten gesetzt.', f'Global RSS ping interval set to {poll_interval} minutes.'))}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/connections/rss?mode=edit&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
            )

    async def config_connections_delete(
        request: Request,
        kind: str = Form(...),
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        try:
            spec = _delete_connection_profile(kind, connection_ref)
            await _trigger_connection_routing_refresh(wait=True)
            return _redirect_with_return_to(
                f"{spec['page']}?saved=1&info={quote_plus(str(spec['success_message']))}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            try:
                spec = _get_connection_delete_spec(kind)
                ref_query = str(spec.get("ref_query", "")).strip()
                ref_suffix = f"&{ref_query}={quote_plus(connection_ref)}" if ref_query else ""
                target_page = str(spec.get("page", "/config"))
            except ValueError:
                target_page = "/config"
                ref_suffix = ""
            return _redirect_with_return_to(
                f"{target_page}?error={quote_plus(str(exc))}{ref_suffix}",
                request,
                fallback="/config",
            )

    async def config_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        port: int = Form(22),
        user: str = Form(""),
        service_url: str = Form(""),
        login_user: str = Form(""),
        login_password: str = Form(""),
        run_key_exchange: str = Form("1"),
        create_matching_sftp: str = Form("0"),
        key_path: str = Form(""),
        timeout_seconds: int = Form(20),
        strict_host_key_checking: str = Form("accept-new"),
        guardrail_ref: str = Form(""),
        allow_commands: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("ssh", connection_ref, original_ref)
            allow_list = [line.strip() for line in re.split(r"[\n,]+", str(allow_commands)) if line.strip()]
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "ssh",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu SSH.")
            should_exchange = str(run_key_exchange).strip().lower() in {"1", "true", "on", "yes"}
            clean_host = str(host).strip()
            clean_user = str(user).strip()
            clean_service_url = str(service_url).strip()
            metadata, metadata_autofilled = await _autofill_service_connection_metadata(
                connection_ref=ref,
                service_url=clean_service_url,
                current_title=connection_title,
                current_description=connection_description,
                current_aliases=connection_aliases,
                current_tags=connection_tags,
                lang=lang,
            )
            row_value = {
                "host": clean_host,
                "port": max(1, int(port)),
                "user": clean_user,
                "service_url": clean_service_url,
                "key_path": str(key_path).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "strict_host_key_checking": str(strict_host_key_checking).strip() or "accept-new",
                "guardrail_ref": selected_guardrail_ref,
                "allow_commands": allow_list,
                **_build_connection_metadata(
                    metadata["title"],
                    metadata["description"],
                    metadata["aliases"],
                    metadata["tags"],
                ),
            }
            info = _msg(lang, "Profil gespeichert", "Profile saved")
            if metadata_autofilled:
                info = f"{info} · {_msg(lang, 'Routing-Hinweise automatisch ergänzt', 'Routing hints filled automatically')}"
            if should_exchange and login_password.strip():
                exch_user, exch_key = _perform_ssh_key_exchange(
                    ref=ref,
                    host=clean_host,
                    port=max(1, int(port)),
                    profile_user=clean_user,
                    login_user=login_user,
                    login_password=login_password,
                )
                row_value["user"] = exch_user
                row_value["key_path"] = str(exch_key)
                info = _msg(lang, "Profil gespeichert + Key-Exchange erfolgreich", "Profile saved + key exchange successful")
            matching_sftp_note = ""
            if _is_create and str(create_matching_sftp).strip().lower() in {"1", "true", "on", "yes"}:
                connections = raw.setdefault("connections", {})
                if not isinstance(connections, dict):
                    raise ValueError("Ungültige Connection-Konfiguration.")
                sftp_rows = connections.setdefault("sftp", {})
                if not isinstance(sftp_rows, dict):
                    raise ValueError("Ungültige SFTP-Sektion.")
                sftp_ref = _derive_matching_sftp_ref(ref)
                key_path_for_sftp = str(row_value.get("key_path", "")).strip()
                if not key_path_for_sftp:
                    matching_sftp_note = _msg(
                        lang,
                        "Passendes SFTP-Profil nicht erzeugt: erst SSH-Key speichern oder Key-Exchange ausführen.",
                        "Matching SFTP profile not created: save an SSH key first or run key exchange.",
                    )
                elif sftp_ref in sftp_rows:
                    matching_sftp_note = _msg(
                        lang,
                        f"Passendes SFTP-Profil `{sftp_ref}` existiert bereits und blieb unverändert.",
                        f"Matching SFTP profile `{sftp_ref}` already exists and was left unchanged.",
                    )
                else:
                    sftp_rows[sftp_ref] = {
                        "host": clean_host,
                        "port": max(1, int(port)),
                        "user": str(row_value.get("user", "")).strip(),
                        "key_path": key_path_for_sftp,
                        "timeout_seconds": max(5, int(timeout_seconds)),
                        "root_path": "/",
                        **_build_connection_metadata(
                            metadata["title"],
                            metadata["description"],
                            metadata["aliases"],
                            metadata["tags"],
                        ),
                    }
                    matching_sftp_note = _msg(
                        lang,
                        f"Passendes SFTP-Profil `{sftp_ref}` mitgespeichert",
                        f"Matching SFTP profile `{sftp_ref}` created",
                    )
            await _finalize_connection_save(
                "ssh",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            if matching_sftp_note:
                info = f"{info} · {matching_sftp_note}"
            if should_exchange and not login_password.strip():
                info = _msg(lang, "Profil gespeichert (ohne Key-Exchange: Passwort fehlt)", "Profile saved (without key exchange: password missing)")
                if matching_sftp_note:
                    info = f"{info} · {matching_sftp_note}"
            test_result = build_connection_status_row(
                "ssh",
                ref,
                row_value,
                page_probe=False,
                base_dir=BASE_DIR,
                lang=lang,
            )
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/ssh?saved=1&info={quote_plus(info + ' · ' + _msg(lang, 'Verbindung erfolgreich getestet', 'connection test succeeded'))}"
                    f"&ref={quote_plus(ref)}&test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(info + ' · ' + _msg(lang, 'Verbindungstest fehlgeschlagen', 'connection test failed'))}"
                f"&error={quote_plus(test_result['message'])}&ref={quote_plus(ref)}&test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            suffix = f"&ref={quote_plus(ref_hint)}" if ref_hint else ""
            detail = _friendly_ssh_setup_error(lang, exc)
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(detail)}{suffix}",
                request,
                fallback="/config",
            )

    async def config_discord_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        webhook_url: str = Form(""),
        timeout_seconds: int = Form(10),
        send_test_messages: str = Form("0"),
        allow_skill_messages: str = Form("0"),
        alert_skill_errors: str = Form("0"),
        alert_safe_fix: str = Form("0"),
        alert_connection_changes: str = Form("0"),
        alert_system_events: str = Form("0"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("discord", connection_ref, original_ref)
            clean_webhook = str(webhook_url).strip()
            if not store:
                raise ValueError("Security Store ist für Discord-Webhooks erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_webhook = store.get_secret(f"connections.discord.{existing_secret_ref}.webhook_url", default="")
            if not clean_webhook:
                clean_webhook = existing_webhook
            if not clean_webhook:
                raise ValueError("Discord-Webhook-URL fehlt.")
            row_value = {
                "timeout_seconds": max(5, int(timeout_seconds)),
                "send_test_messages": str(send_test_messages).strip().lower() in {"1", "true", "on", "yes"},
                "allow_skill_messages": str(allow_skill_messages).strip().lower() in {"1", "true", "on", "yes"},
                "alert_skill_errors": str(alert_skill_errors).strip().lower() in {"1", "true", "on", "yes"},
                "alert_safe_fix": str(alert_safe_fix).strip().lower() in {"1", "true", "on", "yes"},
                "alert_connection_changes": str(alert_connection_changes).strip().lower() in {"1", "true", "on", "yes"},
                "alert_system_events": str(alert_system_events).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.discord.{ref}.webhook_url", clean_webhook)
            await _finalize_connection_save(
                "discord",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.discord.{original_ref_clean}.webhook_url",
                        f"connections.discord.{ref}.webhook_url",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_discord_connections().get(ref, {})
            test_result = build_connection_status_row("discord", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/discord?saved=1&info={quote_plus(_connection_saved_test_info('Discord', lang, success=True))}"
                    f"&discord_ref={quote_plus(ref)}&discord_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/discord?saved=1&info={quote_plus(_connection_saved_test_info('Discord', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&discord_ref={quote_plus(ref)}&discord_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/discord?error={quote_plus(str(exc))}&discord_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_sftp_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        service_url: str = Form(""),
        port: int = Form(22),
        user: str = Form(""),
        password: str = Form(""),
        key_path: str = Form(""),
        timeout_seconds: int = Form(10),
        root_path: str = Form(""),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("sftp", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für SFTP-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.sftp.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            clean_key_path = str(key_path).strip()
            if not clean_password and not clean_key_path:
                raise ValueError("SFTP braucht Passwort oder Key-Pfad.")
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "sftp",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu SFTP.")
            clean_service_url = str(service_url).strip()
            metadata, metadata_autofilled = await _autofill_service_connection_metadata(
                connection_ref=ref,
                service_url=clean_service_url,
                current_title=connection_title,
                current_description=connection_description,
                current_aliases=connection_aliases,
                current_tags=connection_tags,
                lang=lang,
            )
            row_value = {
                "host": str(host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "service_url": clean_service_url,
                "key_path": clean_key_path,
                "timeout_seconds": max(5, int(timeout_seconds)),
                "root_path": str(root_path).strip(),
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(
                    metadata["title"],
                    metadata["description"],
                    metadata["aliases"],
                    metadata["tags"],
                ),
            }
            store.set_secret(f"connections.sftp.{ref}.password", clean_password if clean_password else "")
            await _finalize_connection_save(
                "sftp",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.sftp.{original_ref_clean}.password",
                        f"connections.sftp.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            info = _connection_saved_test_info("SFTP", lang, success=True)
            if metadata_autofilled:
                info = f"{info} · {_msg(lang, 'Routing-Hinweise automatisch ergänzt', 'Routing hints filled automatically')}"
            test_row = _read_sftp_connections().get(ref, {})
            test_result = build_connection_status_row("sftp", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/sftp?saved=1&info={quote_plus(info)}"
                    f"&sftp_ref={quote_plus(ref)}&sftp_test_status=ok",
                    request,
                    fallback="/config",
                )
            info = _connection_saved_test_info("SFTP", lang, success=False)
            if metadata_autofilled:
                info = f"{info} · {_msg(lang, 'Routing-Hinweise automatisch ergänzt', 'Routing hints filled automatically')}"
            return _redirect_with_return_to(
                f"/config/connections/sftp?saved=1&info={quote_plus(info)}"
                f"&error={quote_plus(test_result['message'])}&sftp_ref={quote_plus(ref)}&sftp_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/sftp?error={quote_plus(str(exc))}&sftp_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_smb_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        share: str = Form(""),
        port: int = Form(445),
        user: str = Form(""),
        password: str = Form(""),
        timeout_seconds: int = Form(10),
        root_path: str = Form(""),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("smb", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für SMB-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.smb.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("SMB-Passwort fehlt.")
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "smb",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu SMB.")
            row_value = {
                "host": str(host).strip(),
                "share": str(share).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "root_path": str(root_path).strip(),
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.smb.{ref}.password", clean_password)
            await _finalize_connection_save(
                "smb",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.smb.{original_ref_clean}.password",
                        f"connections.smb.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_smb_connections().get(ref, {})
            test_result = build_connection_status_row("smb", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/smb?saved=1&info={quote_plus(_connection_saved_test_info('SMB', lang, success=True))}&smb_ref={quote_plus(ref)}&smb_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/smb?saved=1&info={quote_plus(_connection_saved_test_info('SMB', lang, success=False))}&error={quote_plus(test_result['message'])}&smb_ref={quote_plus(ref)}&smb_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/smb?error={quote_plus(str(exc))}&smb_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_webhook_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        url: str = Form(""),
        timeout_seconds: int = Form(10),
        method: str = Form("POST"),
        content_type: str = Form("application/json"),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("webhook", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für Webhook-URLs erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_url = store.get_secret(f"connections.webhook.{existing_secret_ref}.url", default="")
            clean_url = str(url).strip() or existing_url
            if not clean_url:
                raise ValueError("Webhook-URL fehlt.")
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "webhook",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu Webhook.")
            row_value = {
                "timeout_seconds": max(5, int(timeout_seconds)),
                "method": str(method).strip().upper() or "POST",
                "content_type": str(content_type).strip() or "application/json",
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.webhook.{ref}.url", clean_url)
            await _finalize_connection_save(
                "webhook",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.webhook.{original_ref_clean}.url",
                        f"connections.webhook.{ref}.url",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_webhook_connections().get(ref, {})
            test_result = build_connection_status_row("webhook", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/webhook?saved=1&info={quote_plus(_connection_saved_test_info('Webhook', lang, success=True))}&webhook_ref={quote_plus(ref)}&webhook_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/webhook?saved=1&info={quote_plus(_connection_saved_test_info('Webhook', lang, success=False))}&error={quote_plus(test_result['message'])}&webhook_ref={quote_plus(ref)}&webhook_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/webhook?error={quote_plus(str(exc))}&webhook_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_smtp_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        smtp_host: str = Form(""),
        port: int = Form(587),
        user: str = Form(""),
        password: str = Form(""),
        from_email: str = Form(""),
        to_email: str = Form(""),
        timeout_seconds: int = Form(10),
        starttls: str = Form("1"),
        use_ssl: str = Form("0"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("email", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für SMTP-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.email.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("SMTP-Passwort fehlt.")
            row_value = {
                "smtp_host": str(smtp_host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "from_email": str(from_email).strip(),
                "to_email": str(to_email).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "starttls": str(starttls).strip().lower() in {"1", "true", "on", "yes"},
                "use_ssl": str(use_ssl).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.email.{ref}.password", clean_password)
            await _finalize_connection_save(
                "email",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.email.{original_ref_clean}.password",
                        f"connections.email.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_email_connections().get(ref, {})
            test_result = build_connection_status_row("email", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/smtp?saved=1&info={quote_plus(_connection_saved_test_info('SMTP', lang, success=True))}&email_ref={quote_plus(ref)}&email_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/smtp?saved=1&info={quote_plus(_connection_saved_test_info('SMTP', lang, success=False))}&error={quote_plus(test_result['message'])}&email_ref={quote_plus(ref)}&email_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/smtp?error={quote_plus(str(exc))}&email_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_imap_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        port: int = Form(993),
        user: str = Form(""),
        password: str = Form(""),
        mailbox: str = Form("INBOX"),
        timeout_seconds: int = Form(10),
        use_ssl: str = Form("1"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("imap", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für IMAP-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.imap.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("IMAP-Passwort fehlt.")
            row_value = {
                "host": str(host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "mailbox": str(mailbox).strip() or "INBOX",
                "timeout_seconds": max(5, int(timeout_seconds)),
                "use_ssl": str(use_ssl).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.imap.{ref}.password", clean_password)
            await _finalize_connection_save(
                "imap",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.imap.{original_ref_clean}.password",
                        f"connections.imap.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_imap_connections().get(ref, {})
            test_result = build_connection_status_row("imap", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/imap?saved=1&info={quote_plus(_connection_saved_test_info('IMAP', lang, success=True))}&imap_ref={quote_plus(ref)}&imap_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/imap?saved=1&info={quote_plus(_connection_saved_test_info('IMAP', lang, success=False))}&error={quote_plus(test_result['message'])}&imap_ref={quote_plus(ref)}&imap_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/imap?error={quote_plus(str(exc))}&imap_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_http_api_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        base_url: str = Form(""),
        auth_token: str = Form(""),
        timeout_seconds: int = Form(10),
        health_path: str = Form("/"),
        method: str = Form("GET"),
        guardrail_ref: str = Form(""),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("http_api", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für HTTP-API-Tokens erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_token = store.get_secret(f"connections.http_api.{existing_secret_ref}.auth_token", default="")
            clean_token = str(auth_token).strip() or existing_token
            guardrail_rows = _read_guardrails()
            selected_guardrail_ref = _sanitize_connection_name(guardrail_ref)
            if selected_guardrail_ref and selected_guardrail_ref not in guardrail_rows:
                raise ValueError("Unbekanntes Guardrail-Profil.")
            if selected_guardrail_ref and not guardrail_is_compatible(
                str(guardrail_rows.get(selected_guardrail_ref, {}).get("kind", "")).strip(),
                "http_api",
            ):
                raise ValueError("Guardrail-Profil passt nicht zu HTTP API.")
            row_value = {
                "base_url": str(base_url).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "health_path": str(health_path).strip() or "/",
                "method": str(method).strip().upper() or "GET",
                "guardrail_ref": selected_guardrail_ref,
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.http_api.{ref}.auth_token", clean_token)
            await _finalize_connection_save(
                "http_api",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.http_api.{original_ref_clean}.auth_token",
                        f"connections.http_api.{ref}.auth_token",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_http_api_connections().get(ref, {})
            test_result = build_connection_status_row("http_api", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/http-api?saved=1&info={quote_plus(_connection_saved_test_info('HTTP API', lang, success=True))}&http_api_ref={quote_plus(ref)}&http_api_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/http-api?saved=1&info={quote_plus(_connection_saved_test_info('HTTP API', lang, success=False))}&error={quote_plus(test_result['message'])}&http_api_ref={quote_plus(ref)}&http_api_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/http-api?error={quote_plus(str(exc))}&http_api_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_google_calendar_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        calendar_id: str = Form("primary"),
        client_id: str = Form(""),
        client_secret: str = Form(""),
        refresh_token: str = Form(""),
        timeout_seconds: int = Form(10),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("google_calendar", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für Google-Calendar-Secrets erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_client_secret = store.get_secret(f"connections.google_calendar.{existing_secret_ref}.client_secret", default="")
            existing_refresh_token = store.get_secret(f"connections.google_calendar.{existing_secret_ref}.refresh_token", default="")
            clean_client_secret = str(client_secret).strip() or existing_client_secret
            clean_refresh_token = str(refresh_token).strip() or existing_refresh_token
            if not clean_client_secret:
                raise ValueError("OAuth Client Secret fehlt.")
            if not clean_refresh_token:
                raise ValueError("Refresh-Token fehlt.")
            row_value = {
                "calendar_id": str(calendar_id).strip() or "primary",
                "client_id": str(client_id).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.google_calendar.{ref}.client_secret", clean_client_secret)
            store.set_secret(f"connections.google_calendar.{ref}.refresh_token", clean_refresh_token)
            await _finalize_connection_save(
                "google_calendar",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.google_calendar.{original_ref_clean}.client_secret",
                        f"connections.google_calendar.{ref}.client_secret",
                    ),
                    (
                        f"connections.google_calendar.{original_ref_clean}.refresh_token",
                        f"connections.google_calendar.{ref}.refresh_token",
                    ),
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_google_calendar_connections().get(ref, {})
            test_result = build_connection_status_row("google_calendar", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/google-calendar?saved=1&info={quote_plus(_connection_saved_test_info('Google Calendar', lang, success=True))}&google_calendar_ref={quote_plus(ref)}&google_calendar_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/google-calendar?saved=1&info={quote_plus(_connection_saved_test_info('Google Calendar', lang, success=False))}&error={quote_plus(test_result['message'])}&google_calendar_ref={quote_plus(ref)}&google_calendar_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/google-calendar?error={quote_plus(str(exc))}&google_calendar_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_searxng_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        timeout_seconds: int = Form(10),
        language: str = Form("de-CH"),
        safe_search: int = Form(1),
        categories: list[str] = Form([]),
        engines: list[str] = Form([]),
        time_range: str = Form(""),
        max_results: int = Form(5),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("searxng", connection_ref, original_ref)
            existing_row = rows.get(original_ref_clean) if original_ref_clean else rows.get(ref)
            if not isinstance(existing_row, dict):
                existing_row = {}
            row_value = {
                "base_url": resolve_searxng_base_url(str(existing_row.get("base_url", "")).strip()),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "language": str(language).strip() or "de-CH",
                "safe_search": max(0, min(int(safe_search), 2)),
                "categories": [item.strip() for item in categories if item.strip()][:12] or ["general"],
                "engines": [item.strip() for item in engines if item.strip()][:20],
                "time_range": str(time_range).strip().lower(),
                "max_results": max(1, min(int(max_results), 20)),
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            await _finalize_connection_save(
                "searxng",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            test_row = _read_searxng_connections().get(ref, {})
            test_result = build_connection_status_row("searxng", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/searxng?saved=1&info={quote_plus(_connection_saved_test_info('SearXNG', lang, success=True))}"
                    f"&searxng_ref={quote_plus(ref)}&searxng_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/searxng?saved=1&info={quote_plus(_connection_saved_test_info('SearXNG', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&searxng_ref={quote_plus(ref)}&searxng_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/searxng?error={quote_plus(str(exc))}&searxng_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_rss_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        feed_url: str = Form(""),
        group_name: str = Form(""),
        timeout_seconds: int = Form(10),
        poll_interval_minutes: int = Form(60),
    ) -> RedirectResponse:
        try:
            del poll_interval_minutes
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, create_new_mode = _prepare_connection_save("rss", connection_ref, original_ref)
            clean_feed_url = _normalize_rss_feed_url_for_dedupe(feed_url)
            if not clean_feed_url:
                raise ValueError("Feed-URL fehlt.")
            for existing_ref, row in rows.items():
                if existing_ref == original_ref_clean:
                    continue
                existing_feed_url = _normalize_rss_feed_url_for_dedupe(str(row.get("feed_url", "")).strip())
                if existing_feed_url and existing_feed_url == clean_feed_url:
                    raise ValueError(f"RSS-Feed-URL ist bereits im Profil '{existing_ref}' erfasst.")
            row_value = {
                "feed_url": clean_feed_url,
                "group_name": str(group_name or "").strip()[:64],
                "timeout_seconds": max(5, int(timeout_seconds)),
                "poll_interval_minutes": _read_rss_poll_interval_minutes(raw),
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            await _finalize_connection_save(
                "rss",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            test_row = _read_rss_connections().get(ref, {})
            test_result = build_connection_status_row("rss", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                target_url = (
                    f"/config/connections/rss?saved=1&info={quote_plus(_connection_saved_test_info('RSS', lang, success=True))}"
                    f"&rss_test_status=ok&rss_ref={quote_plus(ref)}&mode=edit"
                )
                return _redirect_with_return_to(target_url, request, fallback="/config")
            target_url = (
                f"/config/connections/rss?saved=1&info={quote_plus(_connection_saved_test_info('RSS', lang, success=False))}"
                f"&error={quote_plus(test_result['message'])}&rss_test_status=error&rss_ref={quote_plus(ref)}&mode=edit"
            )
            return _redirect_with_return_to(target_url, request, fallback="/config")
        except (OSError, ValueError) as exc:
            original_ref_clean = _sanitize_connection_name(original_ref)
            target_url = f"/config/connections/rss?error={quote_plus(str(exc))}"
            if original_ref_clean:
                target_url += f"&rss_ref={quote_plus(original_ref_clean)}"
            else:
                target_url += "&create_new=1"
            return _redirect_with_return_to(target_url, request, fallback="/config")

    async def config_website_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        url: str = Form(""),
        group_name: str = Form(""),
        timeout_seconds: int = Form(10),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, _store, rows, ref, original_ref_clean, _create_new_mode = _prepare_connection_save("website", connection_ref, original_ref)
            clean_url = _normalize_website_url(url)
            if not clean_url:
                raise ValueError("URL fehlt.")
            for existing_ref, row in rows.items():
                if existing_ref == original_ref_clean:
                    continue
                existing_url_raw = str(row.get("url", "")).strip()
                existing_url = _normalize_website_url(existing_url_raw) if existing_url_raw else ""
                if existing_url and existing_url == clean_url:
                    raise ValueError(f"URL ist bereits im Profil '{existing_ref}' erfasst.")
            metadata, metadata_autofilled = await _autofill_website_connection_metadata(
                connection_ref=ref,
                url=clean_url,
                current_title=connection_title,
                current_description=connection_description,
                current_aliases=connection_aliases,
                current_tags=connection_tags,
                group_name=group_name,
                lang=lang,
            )
            resolved_group_name = _infer_website_group_name(
                url=clean_url,
                title=metadata["title"],
                tags=metadata["tags"],
                existing_group_name=group_name,
                lang=lang,
            )
            row_value = {
                "url": clean_url,
                "group_name": resolved_group_name,
                "timeout_seconds": max(5, int(timeout_seconds)),
                **_build_connection_metadata(
                    metadata["title"],
                    metadata["description"],
                    metadata["aliases"],
                    metadata["tags"],
                ),
            }
            await _finalize_connection_save(
                "website",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
            )
            test_row = _read_website_connections().get(ref, {})
            test_result = build_connection_status_row("website", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            saved_info = _connection_saved_test_info("Website", lang, success=test_result["status"] == "ok")
            if metadata_autofilled:
                saved_info = f"{saved_info} · {_msg(lang, 'Metadaten automatisch ergänzt', 'Metadata filled automatically')}"
            if test_result["status"] == "ok":
                target_url = (
                    f"/config/connections/websites?saved=1&info={quote_plus(saved_info)}"
                    f"&website_test_status=ok&website_ref={quote_plus(ref)}&mode=edit"
                )
                return _redirect_with_return_to(target_url, request, fallback="/config")
            target_url = (
                f"/config/connections/websites?saved=1&info={quote_plus(saved_info)}"
                f"&error={quote_plus(test_result['message'])}&website_test_status=error&website_ref={quote_plus(ref)}&mode=edit"
            )
            return _redirect_with_return_to(target_url, request, fallback="/config")
        except (OSError, ValueError) as exc:
            original_ref_clean = _sanitize_connection_name(original_ref)
            target_url = f"/config/connections/websites?error={quote_plus(str(exc))}"
            if original_ref_clean:
                target_url += f"&website_ref={quote_plus(original_ref_clean)}"
            else:
                target_url += "&create_new=1"
            return _redirect_with_return_to(target_url, request, fallback="/config")

    async def config_rss_connections_export_opml() -> Response:
        rows = _read_rss_connections()
        xml_payload = build_opml_document(
            [{"ref": ref, **row} for ref, row in rows.items()],
            title="ARIA RSS Export",
        )
        return Response(
            content=xml_payload,
            media_type="application/xml",
            headers={"Content-Disposition": 'attachment; filename="aria-rss-feeds.opml"'},
        )

    async def config_rss_connections_import_opml(
        request: Request,
        opml_file: UploadFile = File(...),
        poll_interval_minutes: int = Form(60),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(
                "/config/connections/rss?create_new=1&error=csrf_failed",
                request,
                fallback="/config",
            )
        try:
            del poll_interval_minutes
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw = _read_raw_config()
            raw.setdefault("connections", {})
            if not isinstance(raw["connections"], dict):
                raw["connections"] = {}
            raw["connections"].setdefault("rss", {})
            if not isinstance(raw["connections"]["rss"], dict):
                raw["connections"]["rss"] = {}
            rows = raw["connections"]["rss"]
            existing_urls = {
                _normalize_rss_feed_url_for_dedupe(str(value.get("feed_url", "")).strip())
                for value in rows.values()
                if isinstance(value, dict) and _normalize_rss_feed_url_for_dedupe(str(value.get("feed_url", "")).strip())
            }
            payload = (await opml_file.read()).decode("utf-8", errors="replace")
            entries = parse_opml_feeds(payload)
            imported_count = 0
            default_poll_interval = _read_rss_poll_interval_minutes(raw)
            for entry in entries:
                normalized_feed_url = _normalize_rss_feed_url_for_dedupe(entry.feed_url)
                if not normalized_feed_url or normalized_feed_url in existing_urls:
                    continue
                ref = _next_rss_import_ref(rows, entry.title, normalized_feed_url)
                group_name = str(entry.tags[0]).strip()[:64] if entry.tags else ""
                rows[ref] = {
                    "feed_url": normalized_feed_url,
                    "group_name": group_name,
                    "timeout_seconds": 10,
                    "poll_interval_minutes": default_poll_interval,
                    "title": entry.title,
                    "description": "",
                    "aliases": [],
                    "tags": list(entry.tags[1:] if group_name else entry.tags),
                }
                existing_urls.add(normalized_feed_url)
                imported_count += 1
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                "/config/connections/rss?saved=1&mode=edit"
                f"&info={quote_plus(_msg(lang, f'OPML-Import abgeschlossen · {imported_count} Feeds importiert', f'OPML import completed · {imported_count} feeds imported'))}",
                request,
                fallback="/config",
            )
        except Exception as exc:  # noqa: BLE001
            return _redirect_with_return_to(
                f"/config/connections/rss?create_new=1&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
            )

    async def config_rss_connections_ping_now(
        request: Request,
        rss_ref: str = Form(...),
    ) -> RedirectResponse:
        ref = _sanitize_connection_name(rss_ref)
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not ref:
            return _redirect_with_return_to(
                "/config/connections/rss?error=Connection-Ref+ist+ung%C3%BCltig.",
                request,
                fallback="/config",
            )
        try:
            test_row = _read_rss_connections().get(ref)
            if not isinstance(test_row, dict):
                raise ValueError("Connection-Profil nicht gefunden.")
            test_result = build_connection_status_row("rss", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    "/config/connections/rss?mode=edit"
                    f"&rss_ref={quote_plus(ref)}"
                    f"&rss_test_status=ok"
                    f"&info={quote_plus(str(test_result['message']))}",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                "/config/connections/rss?mode=edit"
                f"&rss_ref={quote_plus(ref)}"
                f"&rss_test_status=error"
                f"&error={quote_plus(str(test_result['message']))}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"/config/connections/rss?mode=edit&rss_ref={quote_plus(ref)}&rss_test_status=error&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
            )

    async def config_mqtt_connections_save(
        request: Request,
        connection_ref: str = Form(...),
        original_ref: str = Form(""),
        connection_title: str = Form(""),
        connection_description: str = Form(""),
        connection_aliases: str = Form(""),
        connection_tags: str = Form(""),
        host: str = Form(""),
        port: int = Form(1883),
        user: str = Form(""),
        password: str = Form(""),
        topic: str = Form(""),
        timeout_seconds: int = Form(10),
        use_tls: str = Form("0"),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            raw, store, rows, ref, original_ref_clean, _is_create = _prepare_connection_save("mqtt", connection_ref, original_ref)
            if not store:
                raise ValueError("Security Store ist für MQTT-Passwörter erforderlich.")
            existing_secret_ref = original_ref_clean or ref
            existing_password = store.get_secret(f"connections.mqtt.{existing_secret_ref}.password", default="")
            clean_password = str(password).strip() or existing_password
            if not clean_password:
                raise ValueError("MQTT-Passwort fehlt.")
            row_value = {
                "host": str(host).strip(),
                "port": max(1, int(port)),
                "user": str(user).strip(),
                "topic": str(topic).strip(),
                "timeout_seconds": max(5, int(timeout_seconds)),
                "use_tls": str(use_tls).strip().lower() in {"1", "true", "on", "yes"},
                **_build_connection_metadata(connection_title, connection_description, connection_aliases, connection_tags),
            }
            store.set_secret(f"connections.mqtt.{ref}.password", clean_password)
            await _finalize_connection_save(
                "mqtt",
                raw=raw,
                rows=rows,
                ref=ref,
                original_ref=original_ref_clean,
                row_value=row_value,
                store=store,
                secret_renames=[
                    (
                        f"connections.mqtt.{original_ref_clean}.password",
                        f"connections.mqtt.{ref}.password",
                    )
                ] if original_ref_clean and original_ref_clean != ref else [],
            )
            test_row = _read_mqtt_connections().get(ref, {})
            test_result = build_connection_status_row("mqtt", ref, test_row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] == "ok":
                return _redirect_with_return_to(
                    f"/config/connections/mqtt?saved=1&info={quote_plus(_connection_saved_test_info('MQTT', lang, success=True))}&mqtt_ref={quote_plus(ref)}&mqtt_test_status=ok",
                    request,
                    fallback="/config",
                )
            return _redirect_with_return_to(
                f"/config/connections/mqtt?saved=1&info={quote_plus(_connection_saved_test_info('MQTT', lang, success=False))}&error={quote_plus(test_result['message'])}&mqtt_ref={quote_plus(ref)}&mqtt_test_status=error",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            ref_hint = _sanitize_connection_name(original_ref) or _sanitize_connection_name(connection_ref)
            return _redirect_with_return_to(
                f"/config/connections/mqtt?error={quote_plus(str(exc))}&mqtt_ref={quote_plus(ref_hint)}",
                request,
                fallback="/config",
            )

    async def config_connections_keygen(
        request: Request,
        connection_ref: str = Form(...),
        overwrite: str = Form("0"),
    ) -> RedirectResponse:
        try:
            ref = _sanitize_connection_name(connection_ref)
            if not ref:
                raise ValueError("Connection-Ref ist ungültig.")
            overwrite_enabled = str(overwrite).strip().lower() in {"1", "true", "on", "yes"}
            existing = _ssh_keys_dir() / f"{ref}_ed25519"
            if (existing.exists() or existing.with_suffix(".pub").exists()) and not overwrite_enabled:
                raise ValueError("Key existiert bereits. 'Overwrite' aktivieren zum Ersetzen.")
            key_path = _ensure_ssh_keypair(ref, overwrite=overwrite_enabled)

            raw = _read_raw_config()
            raw.setdefault("connections", {})
            if not isinstance(raw["connections"], dict):
                raw["connections"] = {}
            raw["connections"].setdefault("ssh", {})
            if not isinstance(raw["connections"]["ssh"], dict):
                raw["connections"]["ssh"] = {}
            raw["connections"]["ssh"].setdefault(ref, {})
            if not isinstance(raw["connections"]["ssh"][ref], dict):
                raw["connections"]["ssh"][ref] = {}
            raw["connections"]["ssh"][ref]["key_path"] = str(key_path)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(_msg(str(getattr(request.state, 'lang', 'de') or 'de'), 'SSH-Key erstellt', 'SSH key created'))}&ref={quote_plus(ref)}",
                request,
                fallback="/config",
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(detail)}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(_friendly_ssh_setup_error(lang, exc))}",
                request,
                fallback="/config",
            )

    async def config_connections_key_exchange(
        request: Request,
        connection_ref: str = Form(...),
        login_user: str = Form(""),
        login_password: str = Form(""),
    ) -> RedirectResponse:
        try:
            ref = _sanitize_connection_name(connection_ref)
            if not ref:
                raise ValueError("Connection-Ref ist ungültig.")
            if not login_password.strip():
                raise ValueError("Passwort fehlt.")

            rows = _read_ssh_connections()
            row = rows.get(ref)
            if not row:
                raise ValueError("Connection-Profil nicht gefunden.")
            host = str(row.get("host", "")).strip()
            port = int(row.get("port", 22) or 22)
            profile_user = str(row.get("user", "")).strip()
            user, key_path = _perform_ssh_key_exchange(
                ref=ref,
                host=host,
                port=port,
                profile_user=profile_user,
                login_user=login_user,
                login_password=login_password,
            )

            raw = _read_raw_config()
            raw.setdefault("connections", {})
            if not isinstance(raw["connections"], dict):
                raw["connections"] = {}
            raw["connections"].setdefault("ssh", {})
            if not isinstance(raw["connections"]["ssh"], dict):
                raw["connections"]["ssh"] = {}
            raw["connections"]["ssh"].setdefault(ref, {})
            if not isinstance(raw["connections"]["ssh"][ref], dict):
                raw["connections"]["ssh"][ref] = {}
            raw["connections"]["ssh"][ref]["user"] = user
            raw["connections"]["ssh"][ref]["key_path"] = str(key_path)
            _write_raw_config(raw)
            _reload_runtime()
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(_msg(str(getattr(request.state, 'lang', 'de') or 'de'), 'Key-Exchange erfolgreich', 'Key exchange successful'))}&ref={quote_plus(ref)}",
                request,
                fallback="/config",
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(_friendly_ssh_setup_error(lang, exc))}",
                request,
                fallback="/config",
            )

    async def config_connections_test(
        request: Request,
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            ref = _sanitize_connection_name(connection_ref)
            if not ref:
                raise ValueError("Connection-Ref ist ungültig.")
            rows = _read_ssh_connections()
            row = rows.get(ref)
            if not row:
                raise ValueError("Connection-Profil nicht gefunden.")
            test_result = build_connection_status_row("ssh", ref, row, page_probe=False, base_dir=BASE_DIR, lang=lang)
            if test_result["status"] != "ok":
                raise ValueError(test_result["message"])
            info = test_result["message"]
            return _redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(info)}&ref={quote_plus(ref)}&test_status=ok",
                request,
                fallback="/config",
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return _redirect_with_return_to(
                f"/config/connections/ssh?error={quote_plus(str(exc))}&ref={quote_plus(connection_ref)}&test_status=error",
                request,
                fallback="/config",
            )

    return ConnectionMutationHandlers(
        rss_poll_interval_save=config_connections_rss_poll_interval_save,
        connection_delete=config_connections_delete,
        ssh_save=config_connections_save,
        discord_save=config_discord_connections_save,
        sftp_save=config_sftp_connections_save,
        smb_save=config_smb_connections_save,
        webhook_save=config_webhook_connections_save,
        smtp_save=config_smtp_connections_save,
        imap_save=config_imap_connections_save,
        http_api_save=config_http_api_connections_save,
        google_calendar_save=config_google_calendar_connections_save,
        searxng_save=config_searxng_connections_save,
        rss_save=config_rss_connections_save,
        website_save=config_website_connections_save,
        rss_export_opml=config_rss_connections_export_opml,
        rss_import_opml=config_rss_connections_import_opml,
        rss_ping_now=config_rss_connections_ping_now,
        mqtt_save=config_mqtt_connections_save,
        ssh_keygen=config_connections_keygen,
        ssh_key_exchange=config_connections_key_exchange,
        ssh_test=config_connections_test,
    )
