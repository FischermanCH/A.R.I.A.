from __future__ import annotations

from aria.core.rss_opml import build_opml_document, parse_opml_feeds


def test_parse_opml_feeds_keeps_nested_group_tags_and_deduplicates_urls() -> None:
    raw_xml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <body>
    <outline text="Security">
      <outline text="CERT Feed" title="CERT Feed" type="rss" xmlUrl="https://cert.example.org/feed.xml" category="alerts, advisories" />
      <outline text="Duplicate CERT" type="rss" xmlUrl="https://cert.example.org/feed.xml" />
    </outline>
    <outline text="Tech">
      <outline text="Kernel News" type="rss" xmlUrl="https://kernel.example.org/rss.xml" />
    </outline>
  </body>
</opml>
"""

    feeds = parse_opml_feeds(raw_xml)

    assert [feed.feed_url for feed in feeds] == [
        "https://cert.example.org/feed.xml",
        "https://kernel.example.org/rss.xml",
    ]
    assert feeds[0].title == "CERT Feed"
    assert feeds[0].tags == ["Security", "alerts", "advisories"]
    assert feeds[1].tags == ["Tech"]


def test_build_opml_document_prefers_group_name_and_preserves_extra_tags() -> None:
    feeds = [
        {
            "ref": "cert-feed",
            "title": "CERT Feed",
            "feed_url": "https://cert.example.org/feed.xml",
            "group_name": "Threat Intel",
            "tags": ["Security", "alerts", "advisories"],
        },
        {
            "ref": "kernel-news",
            "title": "Kernel News",
            "feed_url": "https://kernel.example.org/rss.xml",
            "tags": ["Tech"],
        },
    ]

    opml = build_opml_document(feeds, title="ARIA Test Export")

    assert '<?xml version=' in opml
    assert '<title>ARIA Test Export</title>' in opml
    assert '<outline text="Threat Intel" title="Threat Intel">' in opml
    assert '<outline text="CERT Feed" title="CERT Feed" type="rss" xmlUrl="https://cert.example.org/feed.xml" category="Security, alerts, advisories" />' in opml
    assert '<outline text="Tech" title="Tech">' in opml
    assert '<outline text="Kernel News" title="Kernel News" type="rss" xmlUrl="https://kernel.example.org/rss.xml" />' in opml
