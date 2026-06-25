import asyncio

from aria.core.connection_catalog import connection_insert_template, connection_kind_label, connection_toolbox_keywords
from aria.core.connection_semantic_resolver import (
    ConnectionSemanticResolver,
    SemanticConnectionCandidate,
    SemanticConnectionHint,
    build_connection_aliases,
    build_routing_decision_record,
    connection_label_match_score,
    format_routing_decision_record,
)


def test_build_connection_aliases_includes_metadata_fields() -> None:
    aliases = build_connection_aliases(
        'smb',
        'nas-docker',
        {
            'host': 'nas-demo.local',
            'share': 'docker',
            'root_path': '/volumes/docker',
            'title': 'NAS Docker Share',
            'description': 'Docker volume share for backups',
            'aliases': ['backup nas', 'docker storage'],
            'tags': ['nas', 'docker'],
        },
    )
    assert 'nas docker share' in aliases
    assert 'backup nas' in aliases
    assert 'docker storage' in aliases
    assert 'nas' in aliases
    assert 'docker' in aliases


def test_build_connection_aliases_extracts_short_host_alias_from_numbered_ref() -> None:
    aliases = build_connection_aliases(
        'smb',
        'nas-docker-01',
        {
            'host': '10.0.5.230',
            'share': 'docker',
            'root_path': '',
            'user': 'demo',
        },
    )
    assert 'nas-demo' in aliases
    assert 'nas-demo docker' in aliases


def test_connection_semantic_resolver_prefers_metadata_alias_match() -> None:
    resolver = ConnectionSemanticResolver(llm_client=None)
    hint = resolver.resolve_connection(
        'Zeige mir die Daten vom backup nas',
        {
            'smb': {
                'nas-docker': {
                    'host': 'nas-demo.local',
                    'share': 'docker',
                    'aliases': ['backup nas'],
                    'title': 'NAS Docker Share',
                }
            }
        },
    )
    assert hint.connection_kind == 'smb'
    assert hint.connection_ref == 'nas-docker'
    assert hint.source == 'semantic_alias'


def test_connection_semantic_resolver_collects_sorted_candidates() -> None:
    resolver = ConnectionSemanticResolver(llm_client=None)

    candidates = resolver.collect_connection_candidates(
        "rss news tech was gibts neues",
        {
            "rss": {
                "heise-online-news": {
                    "feed_url": "https://www.heise.de/rss/heise-atom.xml",
                    "title": "heise online News",
                    "tags": ["news", "tech"],
                },
                "area41-feed": {
                    "feed_url": "https://example.org/area41.xml",
                    "title": "AREA41 Feed",
                    "group_name": "News Tech",
                },
            }
        },
        preferred_kind="rss",
    )

    assert {item.connection_ref for item in candidates[:2]} == {"heise-online-news", "area41-feed"}
    assert candidates[0].score >= candidates[1].score
    assert candidates[0].source == "semantic_alias"
    assert candidates[0].note.startswith("alias:")


def test_connection_catalog_provides_shared_labels_templates_and_keywords() -> None:
    assert connection_kind_label("email") == "SMTP"
    assert "alerts-mail" in connection_insert_template("email", "create", "alerts-mail")
    assert "inventory-api" in connection_insert_template("http_api", "update", "inventory-api")
    assert "synology" in connection_toolbox_keywords("smb", ["nas-share"])


def test_connection_semantic_resolver_prefers_single_plausible_candidate_without_llm() -> None:
    class FakeLLMResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeLLMClient:
        async def chat(self, _messages, **kwargs):
            _ = kwargs
            return FakeLLMResponse('{"kind":"webhook","ref":"n8n-demo","confidence":"high","reason":"automation passt"}')

    resolver = ConnectionSemanticResolver(llm_client=FakeLLMClient())

    hint = asyncio.run(
        resolver.resolve_connection_with_llm(
            "Schick das an meine Automation",
            {
                "webhook": {"n8n-demo": {"title": "Automation Hook", "aliases": ["automation"]}},
                "discord": {"alerts-bot": {"title": "Alerts", "aliases": ["alerts"]}},
            },
            preferred_kind="webhook",
        )
    )

    assert hint.connection_kind == "webhook"
    assert hint.connection_ref == "n8n-demo"
    assert hint.source == "semantic_alias"


def test_connection_semantic_resolver_uses_llm_for_single_loose_candidate() -> None:
    class FakeLLMResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeLLMClient:
        def __init__(self) -> None:
            self.calls = 0

        async def chat(self, messages, **kwargs):
            self.calls += 1
            _ = kwargs
            prompt = "\n".join(str(message.get("content", "")) for message in messages)
            assert "ops-monitor-01" in prompt
            assert "ops-mgmt-01" in prompt
            return FakeLLMResponse(
                '{"kind":"ssh","ref":"ops-monitor-01","confidence":"high","reason":"monitoring server fits the request"}'
            )

    llm = FakeLLMClient()
    resolver = ConnectionSemanticResolver(llm_client=llm)

    hint = asyncio.run(
        resolver.resolve_connection_with_llm(
            "server monitoring status",
            {
                "ssh": {
                    "ops-monitor-01": {"title": "Monitoring Server"},
                    "ops-mgmt-01": {"title": "Management Host"},
                }
            },
            preferred_kind="ssh",
        )
    )

    assert llm.calls == 1
    assert hint.connection_kind == "ssh"
    assert hint.connection_ref == "ops-monitor-01"
    assert hint.source == "semantic_llm"


def test_connection_semantic_resolver_builds_rss_aliases_from_metadata() -> None:
    aliases = ConnectionSemanticResolver._build_rss_aliases(
        "heise-feed",
        {
            "feed_url": "https://example.org/feed.xml",
            "title": "Heise Security News",
            "description": "Aktuelle Heise Security Meldungen",
            "aliases": ["heise", "heise security"],
            "tags": ["security", "news"],
        },
    )

    assert "heise security news" in aliases
    assert "heise" in aliases
    assert "heise security" in aliases
    assert "security" in aliases


def test_build_connection_aliases_include_rss_group_name() -> None:
    aliases = build_connection_aliases(
        "rss",
        "area41-feed",
        {
            "feed_url": "https://example.org/feed.xml",
            "title": "AREA41 Feed",
            "group_name": "News Tech",
            "tags": ["lab"],
        },
    )

    assert "news tech" in aliases


def test_build_connection_aliases_adds_discord_alert_channel_hints() -> None:
    aliases = build_connection_aliases(
        "discord",
        "demo_user-aria-logs",
        {
            "title": "ARIA Logs",
            "allow_skill_messages": True,
            "alert_system_events": True,
        },
    )

    assert "alerts channel" in aliases
    assert "alert channel" in aliases
    assert "logs channel" in aliases


def test_build_connection_aliases_adds_website_docs_hints() -> None:
    aliases = build_connection_aliases(
        "website",
        "aria-docs",
        {
            "url": "https://example.org/docs",
            "group_name": "Docs",
            "title": "ARIA Docs",
            "description": "Technical documentation",
            "tags": ["documentation", "aria"],
        },
    )

    assert "aria docs" in aliases
    assert "docs" in aliases
    assert "documentation" in aliases
    assert "dokumentation" in aliases


def test_connection_label_match_score_ignores_generic_single_word_server_label() -> None:
    assert connection_label_match_score("prüfe den status vom backup server", "server") == 0
    assert connection_label_match_score("check health auf management server", "management server") > 0


def test_routing_decision_record_formats_candidates_and_selection() -> None:
    record = build_routing_decision_record(
        stage="rss_semantic_refine",
        preferred_kind="rss",
        candidates=[
            SemanticConnectionCandidate(
                connection_kind="rss",
                connection_ref="heise-online-news",
                source="semantic_alias",
                alias="news tech",
                score=166,
            ),
            SemanticConnectionCandidate(
                connection_kind="rss",
                connection_ref="area41-feed",
                source="semantic_alias",
                alias="news tech",
                score=171,
            ),
        ],
        hint=SemanticConnectionHint(
            connection_kind="rss",
            connection_ref="area41-feed",
            source="semantic_llm",
            note="semantic_llm:category",
        ),
    )

    lines = format_routing_decision_record(record)

    assert lines[0].startswith("Routing: rss_semantic_refine candidates=2 preferred=rss -> ")
    assert "`rss/heise-online-news` score=166 source=semantic_alias alias=news tech" in lines[0]
    assert "`rss/area41-feed` score=171 source=semantic_alias alias=news tech" in lines[0]
    assert lines[1] == (
        "Routing: rss_semantic_refine selected `rss/area41-feed` "
        "source=semantic_llm note=semantic_llm:category"
    )
