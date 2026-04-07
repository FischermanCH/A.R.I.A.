import asyncio

from aria.core.connection_catalog import connection_insert_template, connection_kind_label, connection_toolbox_keywords
from aria.core.connection_semantic_resolver import ConnectionSemanticResolver, build_connection_aliases


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


def test_connection_catalog_provides_shared_labels_templates_and_keywords() -> None:
    assert connection_kind_label("email") == "SMTP"
    assert "alerts-mail" in connection_insert_template("email", "create", "alerts-mail")
    assert "inventory-api" in connection_insert_template("http_api", "update", "inventory-api")
    assert "synology" in connection_toolbox_keywords("smb", ["nas-share"])


def test_connection_semantic_resolver_can_use_llm_for_generic_connection_choice() -> None:
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
