"""SFTP administration mutation handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse

from aria.modules.connections_profiles.admin import ConnectionAdminError
from aria.modules.runtime_guardrails.guardrails import guardrail_applies_to_connection


def register_sftp_mutation_route(
    app: FastAPI,
    *,
    sftp_save: Callable[..., Any],
) -> None:
    @app.post("/config/connections/sftp/save")
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
        return await sftp_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            host,
            service_url,
            port,
            user,
            password,
            key_path,
            timeout_seconds,
            root_path,
            guardrail_ref,
        )


async def handle_sftp_save(
    *,
    request: Request,
    connection_ref: str,
    original_ref: str,
    connection_title: str,
    connection_description: str,
    connection_aliases: str,
    connection_tags: str,
    host: str,
    service_url: str,
    port: int,
    user: str,
    password: str,
    key_path: str,
    timeout_seconds: int,
    root_path: str,
    guardrail_ref: str,
    base_dir: Path,
    sanitize_connection_name: Callable[[str | None], str],
    prepare_connection_save: Callable[..., tuple[dict[str, Any], Any, dict[str, Any], str, str, bool]],
    read_guardrails: Callable[[], dict[str, Any]],
    autofill_service_connection_metadata: Callable[..., Any],
    build_connection_metadata: Callable[..., dict[str, Any]],
    finalize_connection_save: Callable[..., Any],
    read_sftp_connections: Callable[[], dict[str, dict[str, Any]]],
    build_connection_status_row: Callable[..., dict[str, Any]],
    redirect_with_return_to: Callable[..., RedirectResponse],
    connection_mutation_text: Callable[..., str],
    connection_saved_test_info: Callable[..., str],
    friendly_connection_mutation_error: Callable[..., str],
) -> RedirectResponse:
    lang = str(getattr(request.state, "lang", "de") or "de")
    try:
        raw, store, rows, ref, original_ref_clean, _is_create = prepare_connection_save("sftp", connection_ref, original_ref)
        if not store:
            raise ConnectionAdminError("security_store_required")
        existing_secret_ref = original_ref_clean or ref
        existing_password = store.get_secret(f"connections.sftp.{existing_secret_ref}.password", default="")
        clean_password = str(password).strip() or existing_password
        clean_key_path = str(key_path).strip()
        if not clean_password and not clean_key_path:
            raise ConnectionAdminError("sftp_auth_missing")
        selected_guardrail_ref = _validated_guardrail_ref(
            guardrail_ref,
            connection_kind="sftp",
            label="SFTP",
            sanitize_connection_name=sanitize_connection_name,
            read_guardrails=read_guardrails,
        )
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
            "host": str(host).strip(),
            "port": max(1, int(port)),
            "user": str(user).strip(),
            "service_url": clean_service_url,
            "key_path": clean_key_path,
            "timeout_seconds": max(5, int(timeout_seconds)),
            "root_path": str(root_path).strip(),
            "guardrail_ref": selected_guardrail_ref,
            **build_connection_metadata(
                metadata["title"],
                metadata["description"],
                metadata["aliases"],
                metadata["tags"],
            ),
        }
        store.set_secret(f"connections.sftp.{ref}.password", clean_password if clean_password else "")
        await finalize_connection_save(
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
        info = connection_saved_test_info("SFTP", lang, success=True)
        if metadata_autofilled:
            info = f"{info} · {connection_mutation_text(lang, 'message_728')}"
        test_row = read_sftp_connections().get(ref, {})
        test_result = build_connection_status_row("sftp", ref, test_row, page_probe=False, base_dir=base_dir, lang=lang)
        if test_result["status"] == "ok":
            return redirect_with_return_to(
                f"/config/connections/sftp?saved=1&info={quote_plus(info)}"
                f"&sftp_ref={quote_plus(ref)}&sftp_test_status=ok",
                request,
                fallback="/config",
            )
        info = connection_saved_test_info("SFTP", lang, success=False)
        if metadata_autofilled:
            info = f"{info} · {connection_mutation_text(lang, 'message_740')}"
        return redirect_with_return_to(
            f"/config/connections/sftp?saved=1&info={quote_plus(info)}"
            f"&error={quote_plus(test_result['message'])}&sftp_ref={quote_plus(ref)}&sftp_test_status=error",
            request,
            fallback="/config",
        )
    except (OSError, ValueError) as exc:
        ref_hint = sanitize_connection_name(original_ref) or sanitize_connection_name(connection_ref)
        return redirect_with_return_to(
            f"/config/connections/sftp?error={quote_plus(friendly_connection_mutation_error(lang, exc, kind='sftp'))}&sftp_ref={quote_plus(ref_hint)}",
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
