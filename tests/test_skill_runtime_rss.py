from aria.core.skill_runtime import CustomSkillRuntime


def test_clean_feed_url_removes_tracking_parameters() -> None:
    url = (
        "https://www.heise.de/news/test.html"
        "?wt_mc=rss.red.ho.ho.atom.beitrag.beitrag&utm_source=rss&id=42"
    )
    cleaned = CustomSkillRuntime._clean_feed_url(url)
    assert cleaned == "https://www.heise.de/news/test.html?id=42"


def test_format_feed_timestamp_parses_iso_timestamp() -> None:
    formatted = CustomSkillRuntime._format_feed_timestamp("2026-03-28T20:00:00+01:00")
    assert formatted == "2026-03-28 20:00"


def test_format_feed_timestamp_parses_rfc2822_timestamp() -> None:
    formatted = CustomSkillRuntime._format_feed_timestamp("Sat, 28 Mar 2026 20:00:00 +0100")
    assert formatted == "2026-03-28 20:00"
