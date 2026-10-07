"""SFTP administration page context authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from aria.modules.platform_primitives.i18n import I18NStore

ConnectionPageRenderer = Callable[..., HTMLResponse]

_SFTP_ADMIN_CONTEXT_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def register_sftp_connections_detail_route(
    app: FastAPI,
    *,
    render_connection_page: ConnectionPageRenderer,
    context_builder: Callable[..., dict[str, Any]],
) -> None:
    @app.get("/config/connections/sftp", response_class=HTMLResponse)
    async def config_connections_sftp_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        sftp_ref: str = "",
        sftp_test_status: str = "",
        copy_from_ssh_ref: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return render_connection_page(
            request,
            kind="sftp",
            saved=saved,
            info=info,
            error=error,
            context_builder=context_builder,
            selected_ref_raw=sftp_ref,
            test_status=sftp_test_status,
            copy_from_ssh_ref=copy_from_ssh_ref,
            mode=mode,
        )


def _text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _SFTP_ADMIN_CONTEXT_I18N.t(language or "de", f"connection_context_helpers.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


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


def _attach_sftp_guardrail_context(
    context: dict[str, Any],
    *,
    build_guardrail_ref_options: Callable[..., list[dict[str, str]]],
    guardrail_rows: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    options = build_guardrail_ref_options(
        guardrail_rows,
        connection_kind="sftp",
        lang=str(context.get("lang", "de") or "de"),
    )
    context["connection_guardrail_ref_options"] = options
    context["connection_guardrail_hint_key"] = "config_security.file_guardrail_hint"
    context["connection_guardrail_hint"] = (
        "File guardrails inspect operation and path before ARIA reads, writes, or lists directories."
    )
    return options


def build_sftp_connections_context(
    *,
    base_dir: Path,
    sanitize_connection_name: Callable[[str | None], str],
    build_connection_ref_options: Callable[..., list[dict[str, Any]]],
    build_connection_intro: Callable[..., dict[str, Any]],
    build_connection_summary_cards: Callable[..., list[dict[str, Any]]],
    build_connection_status_block: Callable[..., dict[str, Any]],
    build_schema_form_fields: Callable[..., list[dict[str, Any]]],
    build_guardrail_ref_options: Callable[..., list[dict[str, str]]],
    attach_connection_edit_urls: Callable[..., list[dict[str, Any]]],
    build_connection_status_rows: Callable[..., list[dict[str, Any]]],
    read_guardrails: Callable[[], dict[str, dict[str, Any]]],
    read_ssh_connections: Callable[[], dict[str, dict[str, Any]]],
    read_sftp_connections: Callable[[], dict[str, dict[str, Any]]],
    selected_ref_raw: str = "",
    test_status: str = "",
    copy_from_ssh_ref: str = "",
    lang: str = "de",
) -> dict[str, Any]:
    guardrail_rows = read_guardrails()
    sftp_rows = read_sftp_connections()
    ssh_rows = read_ssh_connections()
    sftp_refs = sorted(sftp_rows.keys())
    selected_sftp_ref = sanitize_connection_name(selected_ref_raw) or (sftp_refs[0] if sftp_refs else "")
    selected_sftp = dict(sftp_rows.get(selected_sftp_ref, {}))
    ssh_refs = sorted(ssh_rows.keys())
    selected_ssh_seed_ref = sanitize_connection_name(copy_from_ssh_ref)
    selected_ssh_seed = ssh_rows.get(selected_ssh_seed_ref, {})
    if selected_ssh_seed:
        seed_key_path = str(selected_ssh_seed.get("key_path", "")).strip()
        seed_key_present = False
        if seed_key_path:
            seed_key_file = Path(seed_key_path)
            if not seed_key_file.is_absolute():
                seed_key_file = (base_dir / seed_key_file).resolve()
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
    sftp_status_rows = attach_connection_edit_urls(
        "sftp",
        build_connection_status_rows(
            "sftp",
            sftp_rows,
            selected_ref=selected_sftp_ref,
            cached_only=True,
            base_dir=base_dir,
            lang=lang,
        ),
    )
    sftp_healthy_count = sum(1 for item in sftp_status_rows if item["status"] == "ok")
    sftp_issue_count = sum(1 for item in sftp_status_rows if item["status"] == "error")
    key_path_hint = _text(
        lang,
        "sftp_key_path_hint",
        "When set, SFTP uses this key instead of a password. Useful for profiles derived from SSH.",
    )
    password_hint = "The password is stored in the secure store and never written into config.yaml."
    context = {
        "lang": lang,
        "connection_intro": build_connection_intro(
            kind="sftp",
            summary_cards=build_connection_summary_cards(
                kind="sftp",
                profiles=len(sftp_refs),
                healthy=sftp_healthy_count,
                issues=sftp_issue_count,
                extra_cards=[
                    _sftp_auth_status_card(selected_sftp),
                ],
            ),
        ),
        "connection_status_block": build_connection_status_block(
            kind="sftp",
            rows=sftp_status_rows,
        ),
        "sftp_refs": sftp_refs,
        "sftp_ref_options": build_connection_ref_options(sftp_rows),
        "selected_sftp_ref": selected_sftp_ref,
        "selected_sftp": selected_sftp,
        "sftp_edit_form_fields": build_schema_form_fields(
            kind="sftp",
            values=dict(selected_sftp),
            prefix="sftp_edit",
            ref_value=selected_sftp_ref,
            placeholders={
                "connection_ref": "z.B. files-sftp",
                "host": "files.example.local",
                "service_url": "https://files.example.local",
                "user": "backup",
                "root_path": "/data",
                "key_path": "/app/data/ssh_keys/files-sftp_ed25519",
            },
            required_fields={"host", "user", "port", "timeout_seconds"},
            field_hints={
                "key_path": key_path_hint,
            },
            secrets_with_hints={"password": password_hint},
            ordered_fields=["host", "service_url", "user", "port", "timeout_seconds", "root_path", "key_path", "password"],
        ),
        "sftp_new_form_fields": build_schema_form_fields(
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
            placeholders={
                "connection_ref": "z.B. files-sftp",
                "host": "files.example.local",
                "service_url": "https://files.example.local",
                "user": "backup",
                "root_path": "/data",
                "key_path": "/app/data/ssh_keys/files-sftp_ed25519",
            },
            required_fields={"host", "user", "port", "timeout_seconds"},
            field_hints={
                "key_path": key_path_hint,
            },
            secrets_with_hints={"password": password_hint},
            ordered_fields=["host", "service_url", "user", "port", "timeout_seconds", "root_path", "key_path", "password"],
        ),
        "ssh_refs": ssh_refs,
        "ssh_ref_options": build_connection_ref_options(ssh_rows),
        "selected_ssh_seed_ref": selected_ssh_seed_ref,
        "selected_ssh_seed": selected_ssh_seed,
        "sftp_status_rows": sftp_status_rows,
        "sftp_healthy_count": sftp_healthy_count,
        "sftp_issue_count": sftp_issue_count,
        "sftp_test_status": str(test_status).strip().lower(),
    }
    context["sftp_guardrail_ref_options"] = _attach_sftp_guardrail_context(
        context,
        build_guardrail_ref_options=build_guardrail_ref_options,
        guardrail_rows=guardrail_rows,
    )
    return context
