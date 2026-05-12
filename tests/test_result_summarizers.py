from types import SimpleNamespace

from aria.core.result_summarizers import summarize_file_result_for_chat
from aria.core.result_summarizers import summarize_http_api_result_for_chat
from aria.core.result_summarizers import summarize_imap_result_for_chat
from aria.core.result_summarizers import summarize_rss_category_result_for_chat
from aria.core.result_summarizers import summarize_ssh_result_for_chat
from aria.core.text_utils import extract_json_object


def test_summarize_ssh_result_for_chat_disk_only() -> None:
    result = SimpleNamespace(
        metadata={
            "custom_command": "df -h /",
            "custom_stdout": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        40G   10G   28G  28% /\n",
        },
    )

    summary = summarize_ssh_result_for_chat(result, connection_ref="server-main", language="de")

    assert summary == "Festplattencheck für `server-main`: Root-Dateisystem /: 28% belegt, 28G frei (ok)."


def test_summarize_ssh_result_for_chat_full_healthcheck() -> None:
    result = SimpleNamespace(
        metadata={
            "custom_command": (
                "uptime -p && df -h && free -h && systemctl --failed --no-pager "
                "&& journalctl -p 3 -xb --no-pager -n 40"
            ),
            "custom_stdout": (
                "up 2 weeks, 3 days\n"
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1        40G   10G   28G  28% /\n"
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:           3.7Gi       430Mi       250Mi       1.5Gi       3.1Gi       3.4Gi\n"
                "Swap:             0B          0B          0B\n"
                "0 loaded units listed.\n"
                "-- No entries --\n"
            ),
        },
    )

    summary = summarize_ssh_result_for_chat(result, connection_ref="pihole1", language="de")

    assert summary == (
        "Server-Healthcheck für `pihole1`: Laufzeit 2 weeks, 3 days. "
        "Root-Dateisystem /: 28% belegt, 28G frei (ok). Verfügbarer RAM: 3.4Gi (ok). "
        "Systemd: keine fehlgeschlagenen Units. "
        "Journal: keine aktuellen Fehler im abgefragten Boot-Log-Ausschnitt. "
        "Fazit: unauffällig."
    )


def test_summarize_ssh_result_for_chat_full_healthcheck_english() -> None:
    result = SimpleNamespace(
        metadata={
            "custom_command": (
                "uptime -p && df -h && free -h && systemctl --failed --no-pager "
                "&& journalctl -p 3 -xb --no-pager -n 40"
            ),
            "custom_stdout": (
                "up 2 weeks, 3 days\n"
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1        40G   10G   28G  28% /\n"
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:           3.7Gi       430Mi       250Mi       1.5Gi       3.1Gi       3.4Gi\n"
                "Swap:             0B          0B          0B\n"
                "0 loaded units listed.\n"
                "-- No entries --\n"
            ),
        },
    )

    summary = summarize_ssh_result_for_chat(result, connection_ref="pihole1", language="en")

    assert summary == (
        "Server health check for `pihole1`: Uptime up 2 weeks, 3 days. "
        "Root filesystem /: 28% used, 28G free (ok). Available RAM: 3.4Gi (ok). "
        "Systemd: no failed units. "
        "Journal: no recent error entries in the sampled boot log. "
        "Conclusion: looks healthy."
    )


def test_summarize_ssh_result_for_chat_full_healthcheck_with_findings() -> None:
    result = SimpleNamespace(
        metadata={
            "custom_command": (
                "uptime -p && df -h && free -h && systemctl --failed --no-pager "
                "&& journalctl -p 3 -xb --no-pager -n 40"
            ),
            "custom_stdout": (
                "up 1 day\n"
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1        40G   37G   1.5G  94% /\n"
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:           3.7Gi       3.0Gi       150Mi       1.5Gi       500Mi       700Mi\n"
                "Swap:          2.0Gi       300Mi       1.7Gi\n"
                "1 loaded units listed.\n"
                "May 04 12:10:11 pihole1 kernel: I/O error on device sda\n"
            ),
        },
    )

    summary = summarize_ssh_result_for_chat(result, connection_ref="pihole1", language="de")

    assert summary == (
        "Server-Healthcheck für `pihole1`: Laufzeit 1 day. "
        "Root-Dateisystem /: 94% belegt, 1.5G frei (knapp). Verfügbarer RAM: 700Mi (knapp). "
        "Systemd: 1 fehlgeschlagene Units. "
        "Journal: 1 ernsthafte Storage-/Dateisystem-Fehlerzeilen; Platte und Dateisystem zeitnah pruefen. "
        "Swap in Nutzung: 300Mi von 2.0Gi. Fazit: Handlungsbedarf."
    )


def test_summarize_ssh_result_for_chat_full_healthcheck_humanizes_auth_noise() -> None:
    result = SimpleNamespace(
        metadata={
            "custom_command": (
                "uptime -p && df -h && free -h && systemctl --failed --no-pager "
                "&& journalctl -p 3 -xb --no-pager -n 40"
            ),
            "custom_stdout": (
                "up 8 weeks, 5 days, 21 hours\n"
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1        30G  5.0G   23G  22% /\n"
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:           3.7Gi       430Mi       250Mi       1.5Gi       3.1Gi       3.4Gi\n"
                "Swap:             0B          0B          0B\n"
                "0 loaded units listed.\n"
                "Apr 12 03:00:02 debsrv-pihole sudo[211347]: pam_unix(sudo:auth): conversation failed\n"
                "Apr 12 03:00:02 debsrv-pihole sudo[211347]: pam_unix(sudo:auth): conversation failed\n"
            ),
        },
    )

    summary = summarize_ssh_result_for_chat(result, connection_ref="pihole1", language="de")

    assert "pam_unix" not in summary
    assert "conversation failed" not in summary
    assert (
        "Journal: 2 sudo-/Login-Fehlerzeilen; vermutlich kein Health-Blocker, ausser das war unerwartet."
        in summary
    )
    assert summary.endswith("Fazit: unauffällig.")


def test_summarize_http_api_result_for_chat_status() -> None:
    text = '{"status":"ok","version":"2.0.0","services":{"database":"ok","queue":"ok"}}'

    summary = summarize_http_api_result_for_chat(
        text,
        connection_ref="inventory-api",
        path="/",
        notes=["api_status_like"],
        language="de",
        extract_json_object=extract_json_object,
    )

    assert summary == "API-Check für `inventory-api`: Status ok. Version 2.0.0. Dienste: database ok, queue ok."


def test_summarize_imap_result_for_chat_latest_mail() -> None:
    text = "Neueste Mails aus INBOX:\n1. Backup ok\nFrom: ops@example.org\n"

    summary = summarize_imap_result_for_chat(
        text,
        connection_ref="ops-inbox",
        capability="mail_read",
        language="de",
    )

    assert summary == "Postfachcheck für `ops-inbox`: 1 neueste Mail aus INBOX. Neueste Betreffe: Backup ok. Neuester Absender: ops@example.org."


def test_summarize_rss_category_result_for_chat_digest() -> None:
    text = "Neueste Einträge aus Kategorie `Security`:\n1. Alert A · Quelle: Feed Alpha\n2. Alert B · Quelle: Feed Beta\n"

    summary = summarize_rss_category_result_for_chat(text, language="de")

    assert summary == (
        "RSS-Digest für `Security`: 2 aktuelle Meldungen.\n\n"
        "1. Alert A\n"
        "   Quelle: Feed Alpha\n"
        "2. Alert B\n"
        "   Quelle: Feed Beta"
    )


def test_summarize_rss_category_result_for_chat_keeps_links_and_snippets() -> None:
    text = (
        "Neueste Einträge aus Kategorie `Security`:\n"
        "1. [Alert A](https://example.org/a) · Quelle: Feed Alpha\n"
        "   2026-05-11 12:30\n"
        "   Kritische Lücke in einem Netzwerkdienst.\n"
    )

    summary = summarize_rss_category_result_for_chat(text, language="de")

    assert summary == (
        "RSS-Digest für `Security`: 1 aktuelle Meldung.\n\n"
        "1. [Alert A](https://example.org/a)\n"
        "   Link: https://example.org/a\n"
        "   Quelle: Feed Alpha · 2026-05-11 12:30\n"
        "   Kurz: Kritische Lücke in einem Netzwerkdienst."
    )


def test_summarize_file_result_for_chat_list() -> None:
    text = "Inhalt von /srv:\n- backups/\n- config.yml\n- logs/\n"

    summary = summarize_file_result_for_chat(
        text,
        connection_ref="server-main",
        connection_kind="sftp",
        capability="file_list",
        path="/srv",
        language="de",
    )

    assert summary == "Dateiliste für `server-main` in `/srv`: 3 Einträge. Beispiele: backups/, config.yml, logs/."
