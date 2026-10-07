"""SSH administration page context authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse


ConnectionPageRenderer = Callable[..., HTMLResponse]


def register_ssh_connections_detail_route(
    app: FastAPI,
    *,
    render_connection_page: ConnectionPageRenderer,
    context_builder: Callable[..., dict[str, Any]],
) -> None:
    @app.get("/config/connections/ssh", response_class=HTMLResponse)
    async def config_connections_ssh_page(
        request: Request,
        saved: int = 0,
        info: str = "",
        error: str = "",
        ref: str = "",
        test_status: str = "",
        mode: str = "edit",
    ) -> HTMLResponse:
        return render_connection_page(
            request,
            kind="ssh",
            saved=saved,
            info=info,
            error=error,
            context_builder=context_builder,
            selected_ref_raw=ref,
            test_status=test_status,
            mode=mode,
        )


def _attach_ssh_guardrail_context(
    context: dict[str, Any],
    *,
    build_guardrail_ref_options: Callable[..., list[dict[str, str]]],
    guardrail_rows: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    options = build_guardrail_ref_options(
        guardrail_rows,
        connection_kind="ssh",
        lang=str(context.get("lang", "de") or "de"),
    )
    context["connection_guardrail_ref_options"] = options
    context["connection_guardrail_hint_key"] = "config_security.guardrails_subtitle"
    context["connection_guardrail_hint"] = (
        "Reusable security profiles for individual services. "
        "Guardrails can be attached to compatible connections and extended modularly later."
    )
    return options


def build_ssh_connections_context(
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
    selected_ref_raw: str = "",
    test_status: str = "",
    lang: str = "de",
) -> dict[str, Any]:
    rows = read_ssh_connections()
    guardrail_rows = read_guardrails()
    refs = sorted(rows.keys())
    selected_ref = sanitize_connection_name(selected_ref_raw) or (refs[0] if refs else "")
    selected = rows.get(selected_ref, {})
    connection_status_rows = attach_connection_edit_urls(
        "ssh",
        build_connection_status_rows(
            "ssh",
            rows,
            selected_ref=selected_ref,
            cached_only=True,
            base_dir=base_dir,
            lang=lang,
        ),
    )
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
    context = {
        "lang": lang,
        "connection_intro": build_connection_intro(
            kind="ssh",
            summary_cards=build_connection_summary_cards(
                kind="ssh",
                profiles=len(refs),
                healthy=healthy_count,
                issues=issue_count,
                extra_cards=[
                    {
                        "label_key": "config_conn.key_status",
                        "label": "Key status",
                        "value": (
                            "ready"
                            if private_key_exists and public_key_exists
                            else ("partial" if private_key_exists or public_key_exists else "missing")
                        ),
                        "value_key": (
                            "config_conn.ready"
                            if private_key_exists and public_key_exists
                            else (
                                "config_conn.partial"
                                if private_key_exists or public_key_exists
                                else "config_conn.missing"
                            )
                        ),
                        "hint_key": "",
                        "hint": f"Private key: {'ok' if private_key_exists else 'missing'} / Public key: {'ok' if public_key_exists else 'missing'}",
                    },
                ],
            ),
        ),
        "connection_status_block": build_connection_status_block(
            kind="ssh",
            rows=connection_status_rows,
        ),
        "refs": refs,
        "ref_options": build_connection_ref_options(rows),
        "selected_ref": selected_ref,
        "selected": selected,
        "ssh_edit_base_form_fields": build_schema_form_fields(
            kind="ssh",
            values=dict(selected),
            prefix="ssh_edit",
            ref_value=selected_ref,
            placeholders={
                "connection_ref": "z.B. main-ssh",
                "host": "server.example.local",
                "user": "admin",
            },
            required_fields={"host", "user", "port", "timeout_seconds"},
            ordered_fields=["host", "user", "port", "timeout_seconds"],
        ),
        "ssh_new_base_form_fields": build_schema_form_fields(
            kind="ssh",
            values={"port": 22, "timeout_seconds": 20},
            prefix="ssh_new",
            ref_value="",
            placeholders={
                "connection_ref": "z.B. main-ssh",
                "host": "server.example.local",
                "user": "admin",
            },
            required_fields={"host", "user", "port", "timeout_seconds"},
            ordered_fields=["host", "user", "port", "timeout_seconds"],
        ),
        "ssh_edit_advanced_form_fields": build_schema_form_fields(
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
        "ssh_new_advanced_form_fields": build_schema_form_fields(
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
        "test_status": str(test_status).strip().lower(),
    }
    context["guardrail_ref_options"] = _attach_ssh_guardrail_context(
        context,
        build_guardrail_ref_options=build_guardrail_ref_options,
        guardrail_rows=guardrail_rows,
    )
    return context
