"""SSH administration mutation handlers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse

from aria.modules.connections_profiles.admin import ConnectionAdminError
from aria.modules.runtime_guardrails.guardrails import guardrail_applies_to_connection


def register_ssh_mutation_routes(
    app: FastAPI,
    *,
    ssh_save: Callable[..., Any],
    ssh_keygen: Callable[..., Any],
    ssh_key_exchange: Callable[..., Any],
    ssh_test: Callable[..., Any],
) -> None:
    @app.post("/config/connections/save")
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
        return await ssh_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            host,
            port,
            user,
            service_url,
            login_user,
            login_password,
            run_key_exchange,
            create_matching_sftp,
            key_path,
            timeout_seconds,
            strict_host_key_checking,
            guardrail_ref,
            allow_commands,
        )

    @app.post("/config/connections/keygen")
    async def config_connections_keygen(
        request: Request,
        connection_ref: str = Form(...),
        overwrite: str = Form("0"),
    ) -> RedirectResponse:
        return await ssh_keygen(request, connection_ref, overwrite)

    @app.post("/config/connections/key-exchange")
    async def config_connections_key_exchange(
        request: Request,
        connection_ref: str = Form(...),
        login_user: str = Form(""),
        login_password: str = Form(""),
    ) -> RedirectResponse:
        return await ssh_key_exchange(request, connection_ref, login_user, login_password)

    @app.post("/config/connections/test")
    async def config_connections_test(
        request: Request,
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        return await ssh_test(request, connection_ref)


async def handle_ssh_save(
    *,
    request: Request,
    connection_ref: str,
    original_ref: str,
    connection_title: str,
    connection_description: str,
    connection_aliases: str,
    connection_tags: str,
    host: str,
    port: int,
    user: str,
    service_url: str,
    login_user: str,
    login_password: str,
    run_key_exchange: str,
    create_matching_sftp: str,
    key_path: str,
    timeout_seconds: int,
    strict_host_key_checking: str,
    guardrail_ref: str,
    allow_commands: str,
    base_dir: Path,
    sanitize_connection_name: Callable[[str | None], str],
    prepare_connection_save: Callable[..., tuple[dict[str, Any], Any, dict[str, Any], str, str, bool]],
    read_guardrails: Callable[[], dict[str, Any]],
    autofill_service_connection_metadata: Callable[..., Any],
    build_connection_metadata: Callable[..., dict[str, Any]],
    perform_ssh_key_exchange: Callable[..., tuple[str, Path]],
    derive_matching_sftp_ref: Callable[[str], str],
    finalize_connection_save: Callable[..., Any],
    build_connection_status_row: Callable[..., dict[str, Any]],
    redirect_with_return_to: Callable[..., RedirectResponse],
    connection_mutation_text: Callable[..., str],
    friendly_ssh_setup_error: Callable[[str, Exception], str],
) -> RedirectResponse:
    lang = str(getattr(request.state, "lang", "de") or "de")
    try:
        raw, _store, rows, ref, original_ref_clean, is_create = prepare_connection_save("ssh", connection_ref, original_ref)
        allow_list = [line.strip() for line in re.split(r"[\n,]+", str(allow_commands)) if line.strip()]
        selected_guardrail_ref = _validated_guardrail_ref(
            guardrail_ref,
            connection_kind="ssh",
            label="SSH",
            sanitize_connection_name=sanitize_connection_name,
            read_guardrails=read_guardrails,
        )
        should_exchange = str(run_key_exchange).strip().lower() in {"1", "true", "on", "yes"}
        clean_host = str(host).strip()
        clean_user = str(user).strip()
        clean_service_url = str(service_url).strip()
        metadata, metadata_autofilled = await autofill_service_connection_metadata(
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
            **build_connection_metadata(
                metadata["title"],
                metadata["description"],
                metadata["aliases"],
                metadata["tags"],
            ),
        }
        info = connection_mutation_text(lang, "message_466")
        if metadata_autofilled:
            info = f"{info} · {connection_mutation_text(lang, 'message_468')}"
        if should_exchange and login_password.strip():
            exch_user, exch_key = perform_ssh_key_exchange(
                ref=ref,
                host=clean_host,
                port=max(1, int(port)),
                profile_user=clean_user,
                login_user=login_user,
                login_password=login_password,
            )
            row_value["user"] = exch_user
            row_value["key_path"] = str(exch_key)
            info = connection_mutation_text(lang, "message_480")
        matching_sftp_note = ""
        if is_create and str(create_matching_sftp).strip().lower() in {"1", "true", "on", "yes"}:
            connections = raw.setdefault("connections", {})
            if not isinstance(connections, dict):
                raise ConnectionAdminError("invalid_config")
            sftp_rows = connections.setdefault("sftp", {})
            if not isinstance(sftp_rows, dict):
                raise ConnectionAdminError("invalid_sftp_section")
            sftp_ref = derive_matching_sftp_ref(ref)
            key_path_for_sftp = str(row_value.get("key_path", "")).strip()
            if not key_path_for_sftp:
                matching_sftp_note = connection_mutation_text(lang, "message_492")
            elif sftp_ref in sftp_rows:
                matching_sftp_note = connection_mutation_text(lang, "message_498", sftp_ref=sftp_ref)
            else:
                sftp_rows[sftp_ref] = {
                    "host": clean_host,
                    "port": max(1, int(port)),
                    "user": str(row_value.get("user", "")).strip(),
                    "key_path": key_path_for_sftp,
                    "timeout_seconds": max(5, int(timeout_seconds)),
                    "root_path": "/",
                    **build_connection_metadata(
                        metadata["title"],
                        metadata["description"],
                        metadata["aliases"],
                        metadata["tags"],
                    ),
                }
                matching_sftp_note = connection_mutation_text(lang, "message_518", sftp_ref=sftp_ref)
        await finalize_connection_save(
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
            info = connection_mutation_text(lang, "message_534")
            if matching_sftp_note:
                info = f"{info} · {matching_sftp_note}"
        test_result = build_connection_status_row(
            "ssh",
            ref,
            row_value,
            page_probe=False,
            base_dir=base_dir,
            lang=lang,
        )
        if test_result["status"] == "ok":
            return redirect_with_return_to(
                f"/config/connections/ssh?saved=1&info={quote_plus(info + ' · ' + connection_mutation_text(lang, 'message_547'))}"
                f"&ref={quote_plus(ref)}&test_status=ok",
                request,
                fallback="/config",
            )
        return redirect_with_return_to(
            f"/config/connections/ssh?saved=1&info={quote_plus(info + ' · ' + connection_mutation_text(lang, 'message_553'))}"
            f"&error={quote_plus(test_result['message'])}&ref={quote_plus(ref)}&test_status=error",
            request,
            fallback="/config",
        )
    except (OSError, ValueError) as exc:
        ref_hint = sanitize_connection_name(original_ref) or sanitize_connection_name(connection_ref)
        suffix = f"&ref={quote_plus(ref_hint)}" if ref_hint else ""
        detail = friendly_ssh_setup_error(lang, exc)
        return redirect_with_return_to(
            f"/config/connections/ssh?error={quote_plus(detail)}{suffix}",
            request,
            fallback="/config",
        )


def _validated_guardrail_ref(
    guardrail_ref: str,
    *,
    connection_kind: str,
    label: str,
    sanitize_connection_name: Callable[[str | None], str],
    read_guardrails: Callable[[], dict[str, Any]],
) -> str:
    selected_guardrail_ref = sanitize_connection_name(guardrail_ref)
    if not selected_guardrail_ref:
        return ""
    guardrail_rows = read_guardrails()
    if selected_guardrail_ref not in guardrail_rows:
        raise ConnectionAdminError("guardrail_unknown")
    if not guardrail_applies_to_connection(guardrail_rows.get(selected_guardrail_ref), connection_kind):
        raise ConnectionAdminError("guardrail_incompatible", kind=label)
    return selected_guardrail_ref


async def handle_ssh_keygen(
    *,
    request: Request,
    connection_ref: str,
    overwrite: str,
    sanitize_connection_name: Callable[[str | None], str],
    ssh_keys_dir: Callable[[], Path],
    ensure_ssh_keypair: Callable[..., Path],
    read_raw_config: Callable[[], dict[str, Any]],
    write_raw_config: Callable[[dict[str, Any]], None],
    reload_runtime: Callable[[], None],
    redirect_with_return_to: Callable[..., RedirectResponse],
    connection_mutation_text: Callable[..., str],
    friendly_connection_mutation_error: Callable[..., str],
    friendly_ssh_setup_error: Callable[[str, Exception], str],
) -> RedirectResponse:
    try:
        ref = sanitize_connection_name(connection_ref)
        if not ref:
            raise ConnectionAdminError("invalid_ref")
        overwrite_enabled = str(overwrite).strip().lower() in {"1", "true", "on", "yes"}
        existing = ssh_keys_dir() / f"{ref}_ed25519"
        if (existing.exists() or existing.with_suffix(".pub").exists()) and not overwrite_enabled:
            raise ConnectionAdminError("ssh_key_exists")
        key_path = ensure_ssh_keypair(ref, overwrite=overwrite_enabled)

        raw = read_raw_config()
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
        write_raw_config(raw)
        reload_runtime()
        lang = str(getattr(request.state, "lang", "de") or "de")
        return redirect_with_return_to(
            f"/config/connections/ssh?saved=1&info={quote_plus(connection_mutation_text(lang, 'message_1802'))}&ref={quote_plus(ref)}",
            request,
            fallback="/config",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return redirect_with_return_to(
            f"/config/connections/ssh?error={quote_plus(detail)}",
            request,
            fallback="/config",
        )
    except (OSError, ValueError) as exc:
        lang = str(getattr(request.state, "lang", "de") or "de")
        detail = (
            friendly_connection_mutation_error(lang, exc, kind="ssh")
            if isinstance(exc, ConnectionAdminError)
            else friendly_ssh_setup_error(lang, exc)
        )
        return redirect_with_return_to(
            f"/config/connections/ssh?error={quote_plus(detail)}",
            request,
            fallback="/config",
        )


async def handle_ssh_key_exchange(
    *,
    request: Request,
    connection_ref: str,
    login_user: str,
    login_password: str,
    sanitize_connection_name: Callable[[str | None], str],
    read_ssh_connections: Callable[[], dict[str, dict[str, Any]]],
    perform_ssh_key_exchange: Callable[..., tuple[str, Path]],
    read_raw_config: Callable[[], dict[str, Any]],
    write_raw_config: Callable[[dict[str, Any]], None],
    reload_runtime: Callable[[], None],
    redirect_with_return_to: Callable[..., RedirectResponse],
    connection_mutation_text: Callable[..., str],
    friendly_connection_mutation_error: Callable[..., str],
    friendly_ssh_setup_error: Callable[[str, Exception], str],
) -> RedirectResponse:
    try:
        ref = sanitize_connection_name(connection_ref)
        if not ref:
            raise ConnectionAdminError("invalid_ref")
        if not login_password.strip():
            raise ConnectionAdminError("password_missing")

        rows = read_ssh_connections()
        row = rows.get(ref)
        if not row:
            raise ConnectionAdminError("profile_not_found")
        host = str(row.get("host", "")).strip()
        port = int(row.get("port", 22) or 22)
        profile_user = str(row.get("user", "")).strip()
        user, key_path = perform_ssh_key_exchange(
            ref=ref,
            host=host,
            port=port,
            profile_user=profile_user,
            login_user=login_user,
            login_password=login_password,
        )

        raw = read_raw_config()
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
        write_raw_config(raw)
        reload_runtime()
        lang = str(getattr(request.state, "lang", "de") or "de")
        return redirect_with_return_to(
            f"/config/connections/ssh?saved=1&info={quote_plus(connection_mutation_text(lang, 'message_1870'))}&ref={quote_plus(ref)}",
            request,
            fallback="/config",
        )
    except (OSError, ValueError) as exc:
        lang = str(getattr(request.state, "lang", "de") or "de")
        detail = (
            friendly_connection_mutation_error(lang, exc, kind="ssh")
            if isinstance(exc, ConnectionAdminError)
            else friendly_ssh_setup_error(lang, exc)
        )
        return redirect_with_return_to(
            f"/config/connections/ssh?error={quote_plus(detail)}",
            request,
            fallback="/config",
        )


async def handle_ssh_test(
    *,
    request: Request,
    connection_ref: str,
    base_dir: Path,
    sanitize_connection_name: Callable[[str | None], str],
    read_ssh_connections: Callable[[], dict[str, dict[str, Any]]],
    build_connection_status_row: Callable[..., dict[str, Any]],
    redirect_with_return_to: Callable[..., RedirectResponse],
    friendly_connection_mutation_error: Callable[..., str],
) -> RedirectResponse:
    try:
        lang = str(getattr(request.state, "lang", "de") or "de")
        ref = sanitize_connection_name(connection_ref)
        if not ref:
            raise ConnectionAdminError("invalid_ref")
        rows = read_ssh_connections()
        row = rows.get(ref)
        if not row:
            raise ConnectionAdminError("profile_not_found")
        test_result = build_connection_status_row("ssh", ref, row, page_probe=False, base_dir=base_dir, lang=lang)
        if test_result["status"] != "ok":
            raise ValueError(test_result["message"])
        info = test_result["message"]
        return redirect_with_return_to(
            f"/config/connections/ssh?saved=1&info={quote_plus(info)}&ref={quote_plus(ref)}&test_status=ok",
            request,
            fallback="/config",
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return redirect_with_return_to(
            f"/config/connections/ssh?error={quote_plus(friendly_connection_mutation_error(lang, exc))}&ref={quote_plus(connection_ref)}&test_status=error",
            request,
            fallback="/config",
        )
