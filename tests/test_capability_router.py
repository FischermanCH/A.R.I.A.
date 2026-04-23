from aria.core.capability_router import CapabilityRouter


def test_capability_router_detects_natural_file_read_phrase() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Kannst du mir den Inhalt von /etc/hosts auf server-main zeigen?",
        available_connection_refs=["server-main"],
    )
    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.explicit_connection_ref == "server-main"
    assert draft.path == "/etc/hosts"


def test_capability_router_detects_natural_file_write_phrase() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Erstelle auf server-main die Datei /tmp/info.txt mit dem Inhalt "Hallo ARIA"',
        available_connection_refs=["server-main"],
    )
    assert draft is not None
    assert draft.capability == "file_write"
    assert draft.explicit_connection_ref == "server-main"
    assert draft.path == "/tmp/info.txt"
    assert draft.content == "Hallo ARIA"


def test_capability_router_prefers_file_list_over_generic_show_phrase() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeige mir die Dateien im Ordner /tmp auf server-main",
        available_connection_refs=["server-main"],
    )
    assert draft is not None
    assert draft.capability == "file_list"
    assert draft.explicit_connection_ref == "server-main"
    assert draft.path == "/tmp"


def test_capability_router_uses_explicit_connection_ref_as_remote_hint() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Öffne /etc/hosts auf server-main",
        available_connection_refs=["server-main"],
    )
    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.explicit_connection_ref == "server-main"
    assert draft.path == "/etc/hosts"


def test_capability_router_prefers_smb_when_share_hint_and_smb_ref_exist() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeige mir die Dateien auf dem NAS share-office",
        available_connection_refs_by_kind={
            "sftp": ["server-main"],
            "smb": ["share-office"],
        },
    )
    assert draft is not None
    assert draft.capability == "file_list"
    assert draft.connection_kind == "smb"
    assert draft.explicit_connection_ref == "share-office"


def test_capability_router_uses_alias_match_as_remote_hint() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeige mir die Daten aus dem docker Verzeichnis von nas-demo",
        available_connection_refs_by_kind={
            "smb": ["nas-docker"],
        },
        available_connection_aliases_by_kind={
            "smb": {
                "nas-docker": ["nas-demo", "docker verzeichnis", "docker"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "file_list"
    assert draft.connection_kind == "smb"
    assert draft.explicit_connection_ref == "nas-docker"


def test_capability_router_detects_smb_list_for_data_from_host_phrase() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeige mir die Daten von nas-demo",
        available_connection_refs_by_kind={
            "smb": ["nas-docker"],
        },
        available_connection_aliases_by_kind={
            "smb": {
                "nas-docker": ["nas-demo", "backup nas"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "file_list"
    assert draft.connection_kind == "smb"
    assert draft.explicit_connection_ref == "nas-docker"


def test_capability_router_detects_smb_list_for_what_files_are_in_my_share_phrase() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Was für Dateien liegen in meinem Share",
        available_connection_refs_by_kind={
            "smb": ["nas-docker"],
        },
        available_connection_aliases_by_kind={
            "smb": {
                "nas-docker": ["mein share", "ronny share"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "file_list"
    assert draft.connection_kind == "smb"
    assert draft.explicit_connection_ref == "nas-docker"


def test_capability_router_detects_rss_feed_read() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeig mir den RSS Feed security-feed",
        available_connection_refs_by_kind={"rss": ["security-feed"]},
    )
    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == "security-feed"


def test_capability_router_detects_natural_rss_phrase_with_spaced_ref() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "was gibts neues auf heise online news",
        available_connection_refs_by_kind={"rss": ["heise-online-news"]},
    )
    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == "heise-online-news"


def test_capability_router_detects_shorter_natural_rss_phrase_with_spaced_ref() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "was gibts neues auf heise online",
        available_connection_refs_by_kind={"rss": ["heise-online-news"]},
    )
    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == "heise-online-news"


def test_capability_router_detects_natural_feed_request_without_explicit_ref_if_rss_exists() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "was gibts neues bei heise",
        available_connection_refs_by_kind={"rss": ["tech-news-1", "security-feed"]},
    )
    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == ""


def test_capability_router_detects_short_news_phrase_with_typo_as_rss_request() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "was für news gibs auf heise",
        available_connection_refs_by_kind={"rss": ["heise-news"]},
    )
    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == ""


def test_capability_router_does_not_steal_explicit_internet_search_as_feed_read() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "suche in internet nach den letzten news über den aibi bot",
        available_connection_refs_by_kind={"rss": ["heise-news"]},
    )
    assert draft is None


def test_capability_router_detects_webhook_send() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Sende per Webhook incident-hook "Server down auf mgmt"',
        available_connection_refs_by_kind={"webhook": ["incident-hook"]},
    )
    assert draft is not None
    assert draft.capability == "webhook_send"
    assert draft.connection_kind == "webhook"
    assert draft.explicit_connection_ref == "incident-hook"
    assert draft.content == "Server down auf mgmt"


def test_capability_router_detects_webhook_send_via_explicit_ref_name() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Schicke per n8n-test-webhook einen test mit inhalt "ARIA was here"',
        available_connection_refs_by_kind={"webhook": ["n8n-test-webhook"]},
    )
    assert draft is not None
    assert draft.capability == "webhook_send"
    assert draft.connection_kind == "webhook"
    assert draft.explicit_connection_ref == "n8n-test-webhook"
    assert draft.content == "ARIA was here"


def test_capability_router_detects_discord_send() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Schicke eine Test Nachricht nach Discord alerts-discord "ARIA lebt"',
        available_connection_refs_by_kind={"discord": ["alerts-discord"]},
    )
    assert draft is not None
    assert draft.capability == "discord_send"
    assert draft.connection_kind == "discord"
    assert draft.explicit_connection_ref == "alerts-discord"
    assert draft.content == "ARIA lebt"


def test_capability_router_detects_http_api_request() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Rufe die API inventory-api /health auf",
        available_connection_refs_by_kind={"http_api": ["inventory-api"]},
    )
    assert draft is not None
    assert draft.capability == "api_request"
    assert draft.connection_kind == "http_api"
    assert draft.explicit_connection_ref == "inventory-api"
    assert draft.path == "/health"


def test_capability_router_detects_calendar_read_for_google_calendar_profiles() -> None:
    router = CapabilityRouter()

    draft = router.classify(
        "Was steht morgen in meinem Kalender?",
        available_connection_refs_by_kind={"google_calendar": ["primary-calendar"]},
    )

    assert draft is not None
    assert draft.capability == "calendar_read"
    assert draft.connection_kind == "google_calendar"
    assert draft.explicit_connection_ref == ""
    assert draft.path == "tomorrow"


def test_capability_router_leaves_calendar_read_requests_without_google_calendar_profiles_unclaimed() -> None:
    router = CapabilityRouter()

    draft = router.classify("Was steht morgen in meinem Kalender?")

    assert draft is None


def test_capability_router_prefers_http_api_ref_over_similar_webhook_ref() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "rufe die API n8n-test-web-api /health auf",
        available_connection_refs_by_kind={
            "webhook": ["n8n-test-webhook"],
            "http_api": ["n8n-test-web-api"],
        },
    )
    assert draft is not None
    assert draft.capability == "api_request"
    assert draft.connection_kind == "http_api"
    assert draft.explicit_connection_ref == "n8n-test-web-api"
    assert draft.path == "/health"


def test_capability_router_detects_email_send() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Sende per Mail alerts-mail "Backup erfolgreich abgeschlossen"',
        available_connection_refs_by_kind={"email": ["alerts-mail"]},
    )
    assert draft is not None
    assert draft.capability == "email_send"
    assert draft.connection_kind == "email"
    assert draft.explicit_connection_ref == "alerts-mail"
    assert draft.content == "Backup erfolgreich abgeschlossen"


def test_capability_router_keeps_unknown_email_target_as_requested_ref() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Send email to ops-mail "Backup finished successfully"',
        language="en",
        available_connection_refs_by_kind={"email": ["alerts-mail"]},
    )
    assert draft is not None
    assert draft.capability == "email_send"
    assert draft.connection_kind == "email"
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == "ops-mail"


def test_capability_router_detects_email_send_via_title_alias_without_mail_keyword() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Schick das an alerts "Backup erfolgreich abgeschlossen"',
        available_connection_refs_by_kind={"email": ["alerts-mail"]},
        available_connection_aliases_by_kind={
            "email": {
                "alerts-mail": ["alerts", "alerts mail"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "email_send"
    assert draft.connection_kind == "email"
    assert draft.explicit_connection_ref == "alerts-mail"
    assert draft.content == "Backup erfolgreich abgeschlossen"


def test_capability_router_detects_imap_read() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeige mir die neuesten Mails im Postfach ops-inbox",
        available_connection_refs_by_kind={"imap": ["ops-inbox"]},
    )
    assert draft is not None
    assert draft.capability == "mail_read"
    assert draft.connection_kind == "imap"
    assert draft.explicit_connection_ref == "ops-inbox"


def test_capability_router_detects_mqtt_publish_via_title_alias_without_mqtt_keyword() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Schick das an den event bus "Backup fertig"',
        available_connection_refs_by_kind={"mqtt": ["event-bus"]},
        available_connection_aliases_by_kind={
            "mqtt": {
                "event-bus": ["event bus", "event"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "mqtt_publish"
    assert draft.connection_kind == "mqtt"
    assert draft.explicit_connection_ref == "event-bus"
    assert draft.content == "Backup fertig"


def test_capability_router_detects_imap_search() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Suche Mails in ops-inbox nach "Backup"',
        available_connection_refs_by_kind={"imap": ["ops-inbox"]},
    )
    assert draft is not None
    assert draft.capability == "mail_search"
    assert draft.connection_kind == "imap"
    assert draft.explicit_connection_ref == "ops-inbox"
    assert draft.content == "Backup"


def test_capability_router_detects_mqtt_publish() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        'Sende per MQTT event-bus auf topic aria/events "Backup fertig"',
        available_connection_refs_by_kind={"mqtt": ["event-bus"]},
    )
    assert draft is not None
    assert draft.capability == "mqtt_publish"
    assert draft.connection_kind == "mqtt"
    assert draft.explicit_connection_ref == "event-bus"
    assert draft.path == "aria/events"
    assert draft.content == "Backup fertig"


def test_capability_router_detects_ssh_command_on_explicit_profile() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Run uptime on pihole1",
        language="en",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "uptime"


def test_capability_router_keeps_unknown_ssh_target_as_requested_ref() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Run uptime on backup-node",
        language="en",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == "backup-node"
    assert draft.content == "uptime"


def test_capability_router_detects_ssh_command_with_trimmed_profile_ref() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Führe uptime auf pihole1 aus",
        available_connection_refs_by_kind={"ssh": [" pihole1 "]},
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "uptime"


def test_capability_router_detects_natural_ssh_uptime_request_via_alias() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeig mir die Laufzeit vom primären DNS Server",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
        available_connection_aliases_by_kind={
            "ssh": {
                "pihole1": ["Pi-hole Primary DNS Server", "dns server"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "uptime"


def test_capability_router_detects_how_long_server_runs_phrase_via_alias() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Wie lange läuft mein DNS Server schon?",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
        available_connection_aliases_by_kind={
            "ssh": {
                "pihole1": ["Pi-hole Primary DNS Server", "dns server"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "uptime"


def test_capability_router_detects_how_long_server_is_online_phrase_via_alias() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Wie lange ist mein DNS Server schon online?",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
        available_connection_aliases_by_kind={
            "ssh": {
                "pihole1": ["Pi-hole Primary DNS Server", "dns server"],
            }
        },
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "uptime"


def test_capability_router_detects_natural_ssh_uptime_request_without_target_for_qdrant() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Zeig mir die Laufzeit vom primären DNS Server",
        available_connection_refs_by_kind={"ssh": ["pihole1", "pihole2"]},
    )
    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == ""
    assert draft.content == "uptime"


def test_capability_router_normalizes_natural_disk_check_to_df_h() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "check mal die festplatte auf meinen dns server",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
        available_connection_aliases_by_kind={"ssh": {"pihole1": ["dns server"]}},
    )

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "df -h"


def test_capability_router_normalizes_free_space_follow_up_to_df_h() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "check mit dem befehl df wieviel festplatte noch frei ist auf meinen dns server",
        available_connection_refs_by_kind={"ssh": ["pihole1"]},
        available_connection_aliases_by_kind={"ssh": {"pihole1": ["dns server"]}},
    )

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "pihole1"
    assert draft.content == "df -h"


def test_capability_router_detects_english_file_read_phrase() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "Show me the contents of /etc/hosts on server-main",
        language="en",
        available_connection_refs=["server-main"],
    )
    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.explicit_connection_ref == "server-main"
    assert draft.path == "/etc/hosts"


def test_capability_router_detects_english_feed_request() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "what's new on heise online news",
        language="en",
        available_connection_refs_by_kind={"rss": ["heise-online-news"]},
    )
    assert draft is not None
    assert draft.capability == "feed_read"
    assert draft.connection_kind == "rss"
    assert draft.explicit_connection_ref == "heise-online-news"


def test_capability_router_keeps_unknown_explicit_discord_target_as_requested_ref() -> None:
    router = CapabilityRouter()

    draft = router.classify(
        'Send a test message to Discord alerts-discord "ARIA lives"',
        language="en",
        available_connection_refs_by_kind={"discord": ["fischerman-aria-messages"]},
    )

    assert draft is not None
    assert draft.capability == "discord_send"
    assert draft.connection_kind == "discord"
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == "alerts-discord"


def test_capability_router_ignores_generic_discord_channel_token_as_requested_ref() -> None:
    router = CapabilityRouter()

    draft = router.classify(
        'Send a test message to Discord channel "ARIA lives"',
        language="en",
        available_connection_refs_by_kind={"discord": ["fischerman-aria-messages"]},
    )

    assert draft is not None
    assert draft.capability == "discord_send"
    assert draft.connection_kind == "discord"
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == ""


def test_capability_router_keeps_multiword_discord_requested_ref_phrase() -> None:
    router = CapabilityRouter()

    draft = router.classify(
        'Send a test message to Discord my ops alerts channel "ARIA lives"',
        language="en",
        available_connection_refs_by_kind={"discord": ["fischerman-aria-messages"]},
    )

    assert draft is not None
    assert draft.capability == "discord_send"
    assert draft.connection_kind == "discord"
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == "ops alerts channel"


def test_capability_router_does_not_steal_english_web_search_as_feed_read() -> None:
    router = CapabilityRouter()
    draft = router.classify(
        "search the web for the latest news about the rabbit r1",
        language="en",
        available_connection_refs_by_kind={"rss": ["heise-news"]},
    )
    assert draft is None
