from __future__ import annotations

from pathlib import Path

from aria.modules.config_ui.page_linter import lint_page_snapshots
from aria.modules.navigation_shell.ui_helpers import render_assistant_message_html


ROOT = Path(__file__).resolve().parents[1]


def test_chat_fill_layout_propagates_viewport_height_only_to_message_scroller() -> None:
    css = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")

    assert ".app-shell:has(.chat-layout-fill) > .ui-page-frame" in css
    assert ".ui-page-visible-list:has(> .chat-layout-fill)" in css
    assert ".chat-layout-fill .chat-box-wrap" in css
    assert ".chat-layout-fill .chat-box" in css
    assert ".chat-layout-fill .chat-form" in css
    assert "flex: 0 0 auto" in css


def test_safe_markdown_tables_are_bounded_inside_chat_messages() -> None:
    rows = "\n".join(
        f"| Row {index} | {'very-wide-value-' * 20}{index} |" for index in range(15)
    )
    rendered = str(render_assistant_message_html(
        "Job finished.\n\n| Item | Result |\n|---|---|\n" + rows
    ))
    css = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")

    assert '<div class="assistant-table-wrap"><table>' in rendered
    assert rendered.count("<tr>") == 16
    assert ".assistant-table-wrap" in css
    assert "overflow-x: auto" in css
    assert "max-width: 100%" in css


def test_safe_notice_markdown_renders_bold_code_and_lists_without_raw_html() -> None:
    source = (
        "**Status** with `job_id`\n\n"
        "- first item\n- <script>unsafe()</script>\n\n"
        "1. inspect\n2. finish\n\n"
        "```text\nraw <b>tool output</b>\n```"
    )
    rendered = str(render_assistant_message_html(source))

    assert "<strong>Status</strong>" in rendered
    assert "<code>job_id</code>" in rendered
    assert "<ul><li>first item</li><li>&lt;script&gt;unsafe()&lt;/script&gt;</li></ul>" in rendered
    assert "<ol><li>inspect</li><li>finish</li></ol>" in rendered
    assert "<pre><code>raw &lt;b&gt;tool output&lt;/b&gt;</code></pre>" in rendered
    assert "<script>" not in rendered


def test_history_and_polled_job_notices_share_server_side_safe_renderer() -> None:
    chat = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    partial = (ROOT / "aria/templates/_chat_messages.html").read_text(encoding="utf-8")

    assert "render_assistant_message_html(item.text)" in chat
    assert "render_assistant_message_html(assistant_message)" in partial
    assert 'data-safe-markdown="true"' in chat
    assert 'data-safe-markdown="true"' in partial
    assert 'fetch("/jobs/" + encodeURIComponent(jobId) + "/notice"' in chat
    assert 'messages.insertAdjacentHTML("beforeend", noticeHtml)' in chat


def test_theme_metric_changes_keep_only_an_already_pinned_chat_at_latest() -> None:
    chat = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")

    assert "keepMessagesPinnedToLatest = messagesAtLatest()" in chat
    assert "themeLayoutObserver.observe(document.body" in chat
    assert "themeChanged && keepMessagesPinnedToLatest" in chat


def test_r31_blocks_chat_when_composer_is_outside_visual_viewport() -> None:
    common = {
        "path": "/",
        "page_type": "overview",
        "inherits_page_base": True,
        "title_count": 1,
        "canonical_parent_section": "chat",
        "rendered_parent_section": "chat",
    }
    failed = lint_page_snapshots([{**common, "chat_composer_in_viewport": False}])
    failed_mobile = lint_page_snapshots([{
        **common,
        "chat_composer_in_viewport": True,
        "chat_mobile_layout_issues": ["iphone landscape message ratio 0.31"],
    }])
    passed = lint_page_snapshots([{**common, "chat_composer_in_viewport": True}])

    assert any(row.rule == "R31" for row in failed.blocking_findings)
    assert any(row.rule == "R31" for row in failed_mobile.blocking_findings)
    assert not any(row.rule == "R31" for row in passed.blocking_findings)
