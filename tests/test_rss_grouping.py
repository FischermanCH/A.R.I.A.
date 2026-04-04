from __future__ import annotations

import asyncio

from aria.core.rss_grouping import build_rss_status_groups


def test_rss_grouping_fallback_groups_security_and_news() -> None:
    rows = [
        {
            'ref': 'security-feed',
            'target': 'https://example.org/security/rss.xml',
            'status': 'ok',
            'message': 'ok',
        },
        {
            'ref': 'heise-online-news',
            'target': 'https://www.heise.de/rss/heise-atom.xml',
            'status': 'ok',
            'message': 'ok',
        },
    ]

    groups = asyncio.run(build_rss_status_groups(rows))

    names = {item['name'] for item in groups}
    assert 'Security' in names
    assert 'News & Tech' in names


def test_rss_grouping_prefers_llm_labels_when_available() -> None:
    class FakeResponse:
        content = '{"groups": [{"name": "Security & Alerts", "refs": ["feed-a", "feed-b", "feed-c", "feed-d", "feed-e"]}]}'

    class FakeLLM:
        async def chat(self, _messages):
            return FakeResponse()

    rows = [
        {'ref': 'feed-a', 'target': 'https://a.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-b', 'target': 'https://b.example.org/rss.xml', 'status': 'error', 'message': 'err'},
        {'ref': 'feed-c', 'target': 'https://c.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-d', 'target': 'https://d.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-e', 'target': 'https://e.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
    ]

    groups = asyncio.run(build_rss_status_groups(rows, FakeLLM()))

    assert len(groups) == 1
    assert groups[0]['name'] == 'Security & Alerts'
    assert groups[0]['total'] == 5
    assert groups[0]['issues'] == 1


def test_rss_grouping_keeps_manual_group_names_during_llm_refresh() -> None:
    class FakeResponse:
        content = '{"groups": [{"name": "LLM Vorschlag", "refs": ["auto-feed", "manual-feed", "feed-c", "feed-d", "feed-e"]}]}'

    class FakeLLM:
        async def chat(self, _messages):
            return FakeResponse()

    rows = [
        {'ref': 'manual-feed', 'group_name': 'Meine Security', 'target': 'https://manual.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'auto-feed', 'target': 'https://auto.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-c', 'target': 'https://c.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-d', 'target': 'https://d.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-e', 'target': 'https://e.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'feed-f', 'target': 'https://f.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
    ]

    groups = asyncio.run(build_rss_status_groups(rows, FakeLLM()))

    names_by_ref = {
        row['ref']: group['name']
        for group in groups
        for row in group['rows']
    }
    assert names_by_ref['manual-feed'] == 'Meine Security'
    assert names_by_ref['auto-feed'] == 'LLM Vorschlag'


def test_rss_grouping_sorts_groups_alphabetically() -> None:
    rows = [
        {'ref': 'z-feed', 'group_name': 'Zeta', 'target': 'https://z.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
        {'ref': 'a-feed', 'group_name': 'Alpha', 'target': 'https://a.example.org/rss.xml', 'status': 'error', 'message': 'err'},
        {'ref': 'm-feed', 'group_name': 'Monitoring', 'target': 'https://m.example.org/rss.xml', 'status': 'ok', 'message': 'ok'},
    ]

    groups = asyncio.run(build_rss_status_groups(rows))

    assert [group['name'] for group in groups] == ['Alpha', 'Monitoring', 'Zeta']
