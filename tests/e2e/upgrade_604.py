#!/usr/bin/env python3
"""Browser/data assertions for the isolated Alpha604 -> current release test."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any

import httpx
from playwright.sync_api import Browser, Page, sync_playwright


ADMIN = "releaseadmin"
SECOND_USER = "releaseuser"
PASSWORD = "release-e2e-password"
CHAT_MARKER = "alpha604 chat history survives"
FACT_TEXT = "My launch color is copper"
PREFERENCE_TEXT = "I prefer quiet status summaries"
RECIPE_NAME = "Alpha604 Upgrade Recipe"
CONNECTION_TITLE = "Alpha604 Upgrade SSH"


def _login(page: Page, base_url: str, username: str, *, bootstrap: bool = False) -> None:
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    page.locator("#login-username").fill(username)
    page.locator("#login-password").fill(PASSWORD)
    confirm = page.locator("#login-password-confirm")
    if bootstrap and confirm.count():
        confirm.fill(PASSWORD)
    page.locator("form.login-form button[type=submit]").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def _logout(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    if "/login" not in page.url:
        page.evaluate("""async () => fetch('/logout', {method: 'POST', credentials: 'same-origin'})""")
        page.context.clear_cookies()


def _script(fake_url: str, scenario: str, steps: list[dict[str, Any]]) -> None:
    response = httpx.post(
        f"{fake_url}/__control/reset",
        json={"scenario": scenario, "steps": steps},
        timeout=10,
        trust_env=False,
    )
    response.raise_for_status()


def _submit(page: Page, selector: str) -> None:
    form = page.locator(selector)
    assert form.count() == 1, selector
    form.locator("button[type=submit]").click()
    page.wait_for_load_state("domcontentloaded")


def _qdrant_collections(qdrant_url: str) -> set[str]:
    response = httpx.get(f"{qdrant_url}/collections", timeout=10, trust_env=False)
    response.raise_for_status()
    return {str(row["name"]) for row in response.json()["result"]["collections"]}


def _seed_legacy_collection(qdrant_url: str, name: str, marker: str) -> None:
    client = httpx.Client(timeout=10, trust_env=False)
    response = client.put(
        f"{qdrant_url}/collections/{name}",
        json={"vectors": {"size": 32, "distance": "Cosine"}},
    )
    response.raise_for_status()
    response = client.put(
        f"{qdrant_url}/collections/{name}/points?wait=true",
        json={"points": [{"id": 1, "vector": [0.01] * 32, "payload": {"marker": marker}}]},
    )
    response.raise_for_status()


def seed_604(browser: Browser, base_url: str, fake_url: str, qdrant_url: str, evidence: Path) -> None:
    page = browser.new_page()
    _login(page, base_url, ADMIN, bootstrap=True)

    # Create the second user through Alpha604's admin UI.
    page.goto(f"{base_url}/config/users", wait_until="domcontentloaded")
    user_form = page.locator('form[action="/config/users/create"]')
    user_form.locator('[name="create_username"]').fill(SECOND_USER)
    user_form.locator('[name="create_password"]').fill(PASSWORD)
    user_form.locator('[name="create_role"]').select_option("user")
    _submit(page, 'form[action="/config/users/create"]')
    assert SECOND_USER in page.locator("body").inner_text()

    # Store a real connection through Alpha604's supported configuration route.
    page.goto(f"{base_url}/config/connections/ssh", wait_until="domcontentloaded")
    connection_form = page.locator('form[action="/config/connections/save"]').first
    connection_form.locator('[name="connection_ref"]').fill("upgrade-host")
    connection_form.locator('[name="connection_title"]').fill(CONNECTION_TITLE)
    connection_form.locator('[name="host"]').fill("upgrade-host.example")
    connection_form.locator('[name="user"]').fill("aria-e2e")
    run_key_exchange = connection_form.locator('[name="run_key_exchange"]')
    if run_key_exchange.count():
        run_key_exchange.uncheck()
    connection_form.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")

    # Persist chat history using the strict fake provider.
    _script(fake_url, "upgrade-chat-seed", [
        {"type": "text", "text": '{"is_feedback":false,"sentiment":"mixed","summary":"","artifact_hint":"","reason":"ordinary chat"}'},
        {"type": "text", "text": '{"needs_context":false,"context_directions":[],"context_depth":"none","intents":["chat"],"surfaces":[],"collections":[],"actions":[],"context_requests":[],"queries":[],"priority":[],"target_scope_authority":"","scope_operation":"new_scope","answer_mode":"direct_answer","risk":"none","needs_confirmation":false,"confidence":0.99,"reason":"ordinary chat"}'},
        {"type": "text", "text": '{"intents":["chat"],"confidence":0.99,"reason":"ordinary chat"}'},
        {"type": "text", "text": '{"action":"none","capability":"","connection_kind":"","target_scope":"","target_scope_authority":"","connection_refs":[],"target_intent":"","content":"","confidence":0.99,"reason":"no connection action"}'},
        {"type": "text", "text": CHAT_MARKER},
    ])
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    page.locator("#message").fill("Keep this upgrade marker")
    page.locator("#send-btn").click()
    page.wait_for_function(
        "marker => document.body.innerText.includes(marker)", arg=CHAT_MARKER, timeout=30_000,
    )

    # Store a personal memory and preference through the Alpha604 UI.
    for memory_type, text in (("fact", FACT_TEXT), ("preference", PREFERENCE_TEXT)):
        page.goto(f"{base_url}/memories/create", wait_until="domcontentloaded")
        page.locator('[name="memory_type"]').select_option(memory_type)
        page.locator('[name="text"]').fill(text)
        _submit(page, 'form[action="/memories/create"]')
        assert "error=" not in page.url.lower(), page.url

    # Import a stored recipe through Alpha604's UI/API.
    page.goto(f"{base_url}/recipes/start", wait_until="domcontentloaded")
    recipe = {
        "id": "alpha604-upgrade-recipe",
        "name": RECIPE_NAME,
        "version": "1.0.0",
        "description": "Recipe retained by the public upgrade test",
        "category": "custom",
        "enabled": False,
        "steps": [{"type": "chat_send", "params": {"message": "upgrade recipe ok"}}],
    }
    upload = page.locator('form[action="/recipes/import"] input[type="file"]')
    upload.set_input_files({
        "name": "alpha604-upgrade-recipe.json",
        "mimeType": "application/json",
        "buffer": json.dumps(recipe).encode(),
    })
    _submit(page, 'form[action="/recipes/import"]')

    # Seed actual Qdrant legacy learning data written in the Alpha604 collection shape.
    _seed_legacy_collection(qdrant_url, f"aria_learning_candidates_{ADMIN}", "legacy learning admin")
    _seed_legacy_collection(qdrant_url, f"aria_learning_evals_{SECOND_USER}", "legacy learning second user")

    before = sorted(_qdrant_collections(qdrant_url))
    assert f"aria_learning_candidates_{ADMIN}" in before
    assert f"aria_learning_evals_{SECOND_USER}" in before
    assert any(ADMIN in name and ("facts" in name or "preferences" in name) for name in before), before

    _logout(page, base_url)
    _login(page, base_url, SECOND_USER)
    assert "/login" not in page.url
    evidence.write_text(json.dumps({"collections_before": before}, indent=2), encoding="utf-8")
    page.close()


def verify_target(browser: Browser, base_url: str, fake_url: str, qdrant_url: str, evidence: Path) -> None:
    before = set(json.loads(evidence.read_text(encoding="utf-8"))["collections_before"])
    page = browser.new_page()
    _login(page, base_url, ADMIN)

    # Config incl. connection, chat history, personal memory and stored recipe survived.
    page.goto(f"{base_url}/config/connections/ssh", wait_until="domcontentloaded")
    assert CONNECTION_TITLE in page.locator("body").inner_text()
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    assert CHAT_MARKER in page.locator("body").inner_text()
    page.goto(f"{base_url}/memories", wait_until="domcontentloaded")
    memory_payload = page.locator("[data-memory-browser-payload]").text_content() or ""
    assert FACT_TEXT in memory_payload
    assert PREFERENCE_TEXT in memory_payload
    page.goto(f"{base_url}/recipes/mine", wait_until="domcontentloaded")
    assert RECIPE_NAME in page.locator("body").inner_text()

    # Recall the preserved personal memory in a real current-release native chat turn.
    _script(fake_url, "upgrade-memory-recall", [
        {"type": "tool_use", "name": "memory_context_read", "input": {"query": "launch color", "memory_type": "all"}},
        {"type": "text", "text": f"UPGRADE_RECALL_OK: {FACT_TEXT}"},
    ])
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    page.locator("#message").fill("What do you remember about my launch color?")
    page.locator("#send-btn").click()
    page.wait_for_function(
        "() => document.body.innerText.includes('UPGRADE_RECALL_OK')", timeout=30_000,
    )

    # Cleanup legacy learning collections through the actual maintenance browser form.
    page.goto(f"{base_url}/memories/maintenance", wait_until="domcontentloaded")
    assert page.locator('form[action="/memories/maintenance/cleanup-legacy-learning"]').count() == 1
    _submit(page, 'form[action="/memories/maintenance/cleanup-legacy-learning"]')
    assert "maint-cleanup" in page.url

    after = _qdrant_collections(qdrant_url)
    assert f"aria_learning_candidates_{ADMIN}" not in after
    assert f"aria_learning_evals_{SECOND_USER}" in after
    protected = {name for name in before if ADMIN in name and "learning_" not in name}
    assert protected.issubset(after), {"missing": sorted(protected - after)}

    # Re-check personal data after cleanup and both logins after the image transition.
    page.goto(f"{base_url}/memories", wait_until="domcontentloaded")
    assert FACT_TEXT in (page.locator("[data-memory-browser-payload]").text_content() or "")
    _logout(page, base_url)
    _login(page, base_url, SECOND_USER)
    assert "/login" not in page.url
    page.close()

    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload.update({
        "collections_after": sorted(after),
        "automatic_migrations": [
            "auth SQLite and both users reused in place",
            "config and SSH connection loaded without rewrite",
            "chat history, recipe files and Qdrant memories reused in place",
        ],
        "manual_actions": [
            "back up config/data and Qdrant before upgrade",
            "run legacy learning cleanup once per user",
            "remove old SearXNG/Valkey containers manually after verification",
        ],
        "warnings": ["Legacy learning collections are intentionally retained until opt-in cleanup."],
    })
    evidence.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_fresh(browser: Browser, base_url: str, fake_url: str, evidence: Path) -> None:
    page = browser.new_page()
    _login(page, base_url, ADMIN, bootstrap=True)
    _script(fake_url, "fresh-install-chat", [{"type": "text", "text": "FRESH_INSTALL_OK"}])
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    page.locator("#message").fill("fresh install smoke")
    page.locator("#send-btn").click()
    page.wait_for_function("() => document.body.innerText.includes('FRESH_INSTALL_OK')", timeout=30_000)
    for path in ("/health", "/memories", "/recipes", "/stats"):
        response = page.request.get(f"{base_url}{path}")
        assert response.status < 500, (path, response.status)
    evidence.write_text(json.dumps({"fresh_install": "passed"}, indent=2), encoding="utf-8")
    page.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("seed604", "verify_target", "fresh"))
    parser.add_argument("--base-url", default=os.environ.get("ARIA_E2E_BASE_URL", ""))
    parser.add_argument("--fake-url", default=os.environ.get("ARIA_E2E_FAKE_URL", ""))
    parser.add_argument("--qdrant-url", default=os.environ.get("ARIA_E2E_QDRANT_URL", ""))
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        if args.stage == "seed604":
            seed_604(browser, args.base_url, args.fake_url, args.qdrant_url, args.evidence)
        elif args.stage == "verify_target":
            verify_target(browser, args.base_url, args.fake_url, args.qdrant_url, args.evidence)
        else:
            verify_fresh(browser, args.base_url, args.fake_url, args.evidence)
        browser.close()


if __name__ == "__main__":
    main()
