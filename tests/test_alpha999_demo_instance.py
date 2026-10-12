from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import yaml

from aria.modules.config_ui.page_linter import lint_page_snapshots


ROOT = Path(__file__).resolve().parents[1]


def test_demo_qdrant_seeder_accepts_plain_text_health_response() -> None:
    module_path = ROOT / "scripts/demo/seed_qdrant.py"
    spec = importlib.util.spec_from_file_location("aria_demo_seed_qdrant", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._decode_response(b"healthz check passed") == {"text": "healthz check passed"}
    assert module._decode_response(b'{"result":true}') == {"result": True}


def test_demo_safety_scan_excludes_shipped_scripts_but_keeps_rendered_data() -> None:
    module_path = ROOT / "scripts/demo/check_public_safety.py"
    spec = importlib.util.spec_from_file_location("aria_demo_public_safety", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    html = '<script>const token = csrfToken();</script><p>visible secret=demo-value</p>'
    scanned = module._scannable_html(html)
    assert "csrfToken" not in scanned
    assert "visible secret=demo-value" in scanned
    assert module._language_path("/stats?view=month", "en") in {
        "/stats?view=month&lang=en", "/stats?lang=en&view=month",
    }


def _seed_hashes() -> dict[str, str]:
    subprocess.run(
        [str(ROOT / ".venv/bin/python"), "scripts/demo/seed.py", "--root", str(ROOT)],
        cwd=ROOT, check=True,
    )
    base = ROOT / "demo/generated"
    return {
        str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in base.rglob("*")
        if path.is_file()
        and not (path.parent == base / "config" and path.name != "config.yaml")
        and path.name not in {"aria_secure.sqlite", "aria_secure.sqlite-shm", "aria_secure.sqlite-wal"}
        and not path.name.startswith("activity_journal.sqlite3-")
        and not path.name.startswith("agent_jobs.sqlite3-")
    }


def test_demo_seed_is_repeatable_and_rich() -> None:
    config_directory = ROOT / "demo/generated/config"
    config_directory.mkdir(parents=True, exist_ok=True)
    directory_inode = config_directory.stat().st_ino
    first = _seed_hashes()
    assert config_directory.stat().st_ino == directory_inode
    second = _seed_hashes()
    assert config_directory.stat().st_ino == directory_inode
    assert first == second
    manifest = json.loads((ROOT / "demo/generated/data/demo-seed-manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        "anchor": "2026-10-10T14:30:00+00:00", "connections": 13, "jobs": 7,
        "journal_entries": 60, "recipes": 3, "rss_feeds": 32, "schema": 1,
        "seed": "alpha1007-demo-v1", "user": "demo-admin",
    }
    config = yaml.safe_load((ROOT / "demo/generated/config/config.yaml").read_text(encoding="utf-8"))
    assert len(config["connections"]) == 12
    assert len(config["mcp_servers"]) == 1
    assert len(config["connections"]["rss"]) == 32
    assert len({row.get("group_name", "") for row in config["connections"]["rss"].values()}) >= 4
    assert config["agentic_loop"]["enabled"] is False
    assert config["ui"]["debug_mode"] is True


def test_demo_stack_has_fixed_isolated_names_and_safe_controls() -> None:
    compose = (ROOT / "demo/compose.yml").read_text(encoding="utf-8")
    common = (ROOT / "scripts/demo/common.sh").read_text(encoding="utf-8")
    reset = (ROOT / "scripts/demo/reset.sh").read_text(encoding="utf-8")
    assert "name: aria-demo" in compose
    assert "aria-demo-data" in compose and "aria-demo-qdrant" in compose and "aria-demo-net" in compose
    assert '${ARIA_DEMO_PORT:-8090}:8800' in compose
    assert 'DEMO_PROJECT="aria-demo"' in common
    assert "down -v --remove-orphans" in reset
    assert "config/config.yaml" not in compose
    assert "/var/lib/docker/volumes" not in compose
    assert "./generated/config:/app/config:rw" in compose


def test_demo_sources_are_public_safe() -> None:
    files = [
        ROOT / "demo/compose.yml", ROOT / "demo/README.md",
        *sorted((ROOT / "scripts/demo").glob("*")),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files if path.is_file())
    forbidden = (
        r"\b172\.31\.\d{1,3}\.\d{1,3}\b", r"\b[a-z0-9.-]+\.lan\b",
        r"\b[a-z0-9.-]+\.black(?:\.[a-z0-9.-]+)?\b", r"/home/fischerman", r"/Users/",
        r"\bsk-[A-Za-z0-9_-]{12,}\b",
    )
    assert [pattern for pattern in forbidden if re.search(pattern, text, re.I)] == []
    assert "example.com" in text and "example.org" in text


def test_demo_commands_and_scanner_are_documented() -> None:
    readme = (ROOT / "demo/README.md").read_text(encoding="utf-8")
    for command in ("scripts/demo/start.sh", "scripts/demo/stop.sh", "scripts/demo/reset.sh"):
        assert command in readme
    scanner = (ROOT / "scripts/demo/check_public_safety.py").read_text(encoding="utf-8")
    assert '("de", "en")' in scanner
    assert '"matrix", "paper"' in scanner
    assert 'test-results/demo-screenshots' in scanner
    assert 'if "Download is starting" in str(exc)' in scanner
    assert "page.set_default_navigation_timeout(60_000)" in scanner
    seed = (ROOT / "scripts/demo/seed.py").read_text(encoding="utf-8")
    assert "_reset_directory_contents(config_dir)" not in seed
    assert "_write_text_atomic(\n        config_dir / \"config.yaml\"" in seed


def test_demo_page_linter_distinguishes_repeated_data_and_chat_content() -> None:
    chat = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    fragment = (ROOT / "aria/templates/_chat_messages.html").read_text(encoding="utf-8")
    debug = (ROOT / "aria/templates/config_llm_debug.html").read_text(encoding="utf-8")
    linter = (ROOT / "tests/e2e/scenarios.py").read_text(encoding="utf-8")

    assert 'data-ui-user-content' in fragment
    assert 'article.dataset.uiUserContent = ""' in chat
    assert 'class="js-agent-job-action ui-secondary-action" data-agent-job-action="pause"' in chat
    assert 'class="js-agent-job-action ui-primary-action" data-agent-job-action="confirm"' in chat
    assert "data-ui-repeated-item" in debug
    assert "[data-agent-job-card], [data-ui-repeated-item]" in linter
    updates = (ROOT / "aria/templates/updates.html").read_text(encoding="utf-8")
    assert '<pre class="help-document docs-content-surface" data-ui-user-content>{{ update_status.release_notes }}</pre>' in updates
    assert '<pre class="help-document docs-content-surface" data-ui-user-content>{{ release.notes }}</pre>' in updates
    browser_driver = (ROOT / "tests/e2e/browser_driver.py").read_text(encoding="utf-8")
    assert '"/updates/status:"' in browser_driver


def test_r32_requires_one_rendered_user_bubble_per_persisted_turn() -> None:
    failed = lint_page_snapshots([{
        "path": "/", "chat_user_turns_expected": 2, "chat_user_turns_rendered": 1,
    }])
    passed = lint_page_snapshots([{
        "path": "/", "chat_user_turns_expected": 2, "chat_user_turns_rendered": 2,
    }])
    assert any(row.rule == "R32" for row in failed.blocking_findings)
    assert not any(row.rule == "R32" for row in passed.blocking_findings)

    chat = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    assert "extractUserFromHtml" in chat
    assert 'pendingUserNode.insertAdjacentHTML("afterend", userHtml)' in chat
    assert "data-chat-user-turns-expected=" in chat
