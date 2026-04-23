from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response


@dataclass(frozen=True)
class ConnectionMutationRouteDeps:
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


def register_connection_mutation_routes(app: FastAPI, deps: ConnectionMutationRouteDeps) -> None:
    @app.post("/config/connections/rss/poll-interval/save")
    async def config_connections_rss_poll_interval_save(
        request: Request,
        poll_interval_minutes: int = Form(60),
    ) -> RedirectResponse:
        return await deps.rss_poll_interval_save(request, poll_interval_minutes)

    @app.post("/config/connections/delete")
    async def config_connections_delete(
        request: Request,
        kind: str = Form(...),
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        return await deps.connection_delete(request, kind, connection_ref)

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
        return await deps.ssh_save(
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

    @app.post("/config/connections/discord/save")
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
        return await deps.discord_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            webhook_url,
            timeout_seconds,
            send_test_messages,
            allow_skill_messages,
            alert_skill_errors,
            alert_safe_fix,
            alert_connection_changes,
            alert_system_events,
        )

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
        return await deps.sftp_save(
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

    @app.post("/config/connections/smb/save")
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
        return await deps.smb_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            host,
            share,
            port,
            user,
            password,
            timeout_seconds,
            root_path,
            guardrail_ref,
        )

    @app.post("/config/connections/webhook/save")
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
        return await deps.webhook_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            url,
            timeout_seconds,
            method,
            content_type,
            guardrail_ref,
        )

    @app.post("/config/connections/smtp/save")
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
        return await deps.smtp_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            smtp_host,
            port,
            user,
            password,
            from_email,
            to_email,
            timeout_seconds,
            starttls,
            use_ssl,
        )

    @app.post("/config/connections/imap/save")
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
        return await deps.imap_save(
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
            password,
            mailbox,
            timeout_seconds,
            use_ssl,
        )

    @app.post("/config/connections/http-api/save")
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
        return await deps.http_api_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            base_url,
            auth_token,
            timeout_seconds,
            health_path,
            method,
            guardrail_ref,
        )

    @app.post("/config/connections/google-calendar/save")
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
        return await deps.google_calendar_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            calendar_id,
            client_id,
            client_secret,
            refresh_token,
            timeout_seconds,
        )

    @app.post("/config/connections/searxng/save")
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
        return await deps.searxng_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            timeout_seconds,
            language,
            safe_search,
            categories,
            engines,
            time_range,
            max_results,
        )

    @app.post("/config/connections/rss/save")
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
        return await deps.rss_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            feed_url,
            group_name,
            timeout_seconds,
            poll_interval_minutes,
        )

    @app.post("/config/connections/websites/save")
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
        return await deps.website_save(
            request,
            connection_ref,
            original_ref,
            connection_title,
            connection_description,
            connection_aliases,
            connection_tags,
            url,
            group_name,
            timeout_seconds,
        )

    @app.get("/config/connections/rss/export-opml")
    async def config_rss_connections_export_opml() -> Response:
        return await deps.rss_export_opml()

    @app.post("/config/connections/rss/import-opml")
    async def config_rss_connections_import_opml(
        request: Request,
        opml_file: UploadFile = File(...),
        poll_interval_minutes: int = Form(60),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        return await deps.rss_import_opml(request, opml_file, poll_interval_minutes, csrf_token)

    @app.post("/config/connections/rss/ping-now")
    async def config_rss_connections_ping_now(
        request: Request,
        rss_ref: str = Form(...),
    ) -> RedirectResponse:
        return await deps.rss_ping_now(request, rss_ref)

    @app.post("/config/connections/mqtt/save")
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
        return await deps.mqtt_save(
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
            password,
            topic,
            timeout_seconds,
            use_tls,
        )

    @app.post("/config/connections/keygen")
    async def config_connections_keygen(
        request: Request,
        connection_ref: str = Form(...),
        overwrite: str = Form("0"),
    ) -> RedirectResponse:
        return await deps.ssh_keygen(request, connection_ref, overwrite)

    @app.post("/config/connections/key-exchange")
    async def config_connections_key_exchange(
        request: Request,
        connection_ref: str = Form(...),
        login_user: str = Form(""),
        login_password: str = Form(""),
    ) -> RedirectResponse:
        return await deps.ssh_key_exchange(request, connection_ref, login_user, login_password)

    @app.post("/config/connections/test")
    async def config_connections_test(
        request: Request,
        connection_ref: str = Form(...),
    ) -> RedirectResponse:
        return await deps.ssh_test(request, connection_ref)
